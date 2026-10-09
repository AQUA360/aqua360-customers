"""Vistes del resum d'activitat diària.

- `DailyActivitySummaryView` (GET): el JSON que pinta la pantalla i el widget del
  dashboard del frontal.
- `ReportDailyActivitySummary` (POST): encola l'Excel amb el mateix càlcul.

Les dues resolen aquí quins usuaris es poden consultar: per defecte el propi, i
qualsevol altre (o tots) només si l'usuari té permís de veure usuaris. La tasca de
Celery no té `request.user`, per tant el POST hi ha d'enviar els `user_ids` ja
validats dins del payload.
"""

from django.contrib.auth.models import User
from rest_framework import status, views
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from auth.permissions import PermissionManager
from statistics.tasks import run_report_task
from statistics.utils.daily_activity_service import (
    SCREEN_SOURCE_DETAIL_LIMIT,
    SCREEN_TIMELINE_LIMIT,
    build_daily_activity,
    get_excluded_activity_user_ids,
    get_excluded_activity_usernames,
    parse_activity_dates,
)


def _can_view_other_users(user):
    """Mateix criteri que el llistat d'usuaris (`UserViewSet`): `view_user`."""
    if user.is_superuser:
        return True
    try:
        return bool(PermissionManager.has_permission(user, 'view_user'))
    except Exception:
        return False


NO_PERMISSION_ERROR = "No tens permís per consultar l'activitat d'altres usuaris."
INVALID_USERS_ERROR = "Els usuaris demanats no són vàlids."
EXCLUDED_USERS_ERROR = "L'activitat d'aquest usuari no es pot consultar."


def resolve_activity_users(request, requested_user_ids, wants_all=False):
    """Quins usuaris pot consultar qui fa la petició.

    Retorna `(user_ids, error, http_status)`. Sense res demanat, l'usuari mateix.
    `wants_all` o uns ids que no són el propi requereixen permís de veure usuaris;
    si no n'hi ha, es respon 403 en lloc de retallar la selecció en silenci.
    """
    can_view_others = _can_view_other_users(request.user)

    # Els comptes tècnics queden fora de qualsevol selecció, també per als
    # administradors. L'excepció és un mateix: si el login que fa la petició és un
    # d'aquests comptes, pot veure la seva pròpia activitat (a algunes
    # instal·lacions aquest compte és també el login d'administració).
    excluded_ids = get_excluded_activity_user_ids() - {request.user.id}

    if wants_all:
        if not can_view_others:
            return None, NO_PERMISSION_ERROR, status.HTTP_403_FORBIDDEN
        all_ids = User.objects.filter(is_active=True).exclude(id__in=excluded_ids)
        return list(all_ids.values_list('id', flat=True)), None, None

    if not requested_user_ids:
        return [request.user.id], None, None

    try:
        user_ids = [int(user_id) for user_id in requested_user_ids if user_id not in (None, '')]
    except (TypeError, ValueError):
        return None, INVALID_USERS_ERROR, status.HTTP_400_BAD_REQUEST

    if not user_ids:
        return [request.user.id], None, None

    if set(user_ids) != {request.user.id} and not can_view_others:
        return None, NO_PERMISSION_ERROR, status.HTTP_403_FORBIDDEN

    allowed_ids = [user_id for user_id in user_ids if user_id not in excluded_ids]
    if not allowed_ids:
        # Demanar només comptes tècnics no és un error de permisos de l'usuari:
        # aquesta activitat no la pot veure ningú, i el missatge ho ha de dir.
        return None, EXCLUDED_USERS_ERROR, status.HTTP_403_FORBIDDEN

    return allowed_ids, None, None


def _parse_requested_users(param):
    """`user_id=3`, `user_ids=3,4` o `user_id=all` → (llista d'ids, wants_all)."""
    if param in (None, ''):
        return [], False
    if isinstance(param, (list, tuple)):
        values = [str(value) for value in param]
    else:
        values = [value.strip() for value in str(param).split(',') if value.strip()]
    if any(value.lower() == 'all' for value in values):
        return [], True
    return values, False


class DailyActivitySummaryView(views.APIView):
    """`GET /statistics/daily-activity-summary`

    Paràmetres: `date` (o `date_from`/`date_to`), `user_id`/`user_ids` (ids separats
    per comes, o `all`), `include_details` (per defecte cert) i `timeline_limit`.
    Sense dates, el dia d'avui.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        params = request.query_params
        requested_users, wants_all = _parse_requested_users(
            params.get('user_ids') or params.get('user_id')
        )
        user_ids, error, error_status = resolve_activity_users(request, requested_users, wants_all)
        if error:
            return Response({'error': error}, status=error_status)

        include_details = str(params.get('include_details', 'true')).lower() not in ('false', '0', 'no')

        try:
            timeline_limit = int(params.get('timeline_limit', SCREEN_TIMELINE_LIMIT))
        except (TypeError, ValueError):
            timeline_limit = SCREEN_TIMELINE_LIMIT
        timeline_limit = max(1, min(timeline_limit, SCREEN_TIMELINE_LIMIT))

        date_from, date_to = parse_activity_dates(
            params.get('date_from') or params.get('date'),
            params.get('date_to') or params.get('date'),
        )

        activity = build_daily_activity(
            user_ids, date_from, date_to,
            include_details=include_details,
            source_detail_limit=SCREEN_SOURCE_DETAIL_LIMIT,
            timeline_limit=timeline_limit,
        )
        activity['date_from'] = activity['date_from'].isoformat()
        activity['date_to'] = activity['date_to'].isoformat()
        activity['can_view_other_users'] = _can_view_other_users(request.user)
        # El frontal treu aquests comptes del selector d'usuari sense haver-los
        # de portar escrits: així la llista viu en un únic lloc (el backend).
        activity['excluded_usernames'] = [
            username for username in get_excluded_activity_usernames()
            if username != request.user.username
        ]
        return Response(activity, status=status.HTTP_200_OK)


class ReportDailyActivitySummary(views.APIView):
    """`POST /statistics/billing/daily-activity-summary` → task_id de l'Excel."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        data = dict(request.data or {})
        requested_users, wants_all = _parse_requested_users(
            data.get('user_ids') or data.get('user_id')
        )
        user_ids, error, error_status = resolve_activity_users(request, requested_users, wants_all)
        if error:
            return Response({'error': error}, status=error_status)

        date_from, date_to = parse_activity_dates(
            data.get('date_from') or data.get('date'),
            data.get('date_to') or data.get('date'),
        )
        data['user_ids'] = user_ids
        data.pop('user_id', None)
        data['date_from'] = date_from.isoformat()
        data['date_to'] = date_to.isoformat()
        # `run_report_task` normalitza `date_range` cap a start_date/end_date i a l'inrevés;
        # l'hi donem ja fet perquè el rang que surt a la cua d'informes sigui el bo.
        data['date_range'] = [date_from.isoformat(), date_to.isoformat()]

        try:
            task = run_report_task.delay('daily_activity_summary_report', data)
            return Response({'task_id': task.id, 'status': 'pending'}, status=status.HTTP_202_ACCEPTED)
        except Exception as error:
            return Response({'error': str(error)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
