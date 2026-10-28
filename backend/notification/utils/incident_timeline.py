"""
Cronologia unificada d'una incidència: totes les interaccions i canvis en ordre,
per reconstruir-ne la tramitació (traçabilitat i càrrega de la prova).
"""
from django.conf import settings
from django.utils import translation
from django.utils.translation import gettext as _


def _user(user):
    return user.username if user else None


def build_timeline(incident):
    """Return the incident events sorted by date (most recent first)."""
    from coredata.models import CallRegister
    from logger.models import LogIncidentChange, LogIncidentStatusChange

    events = []

    def add(date, kind, title, detail=None, user=None):
        if date:
            events.append({'date': date, 'kind': kind, 'title': title, 'detail': detail, 'user': _user(user)})

    with translation.override(settings.LANGUAGE_CODE):
        add(incident.created_at, 'created', _("Incident registered"),
            incident.channel.name if incident.channel else None, incident.created_by)

        for log in LogIncidentStatusChange.objects.filter(object=incident).select_related('previous_status', 'current_status', 'user'):
            if log.previous_status_id is None:
                continue
            add(log.timestamp, 'status', _("Status change"),
                f"{log.previous_status.name if log.previous_status else '-'} → {log.current_status.name if log.current_status else '-'}",
                log.user)

        for log in LogIncidentChange.objects.filter(object=incident).select_related('user'):
            add(log.timestamp, 'change', _("Field modified: %(field)s") % {'field': log.field},
                f"{log.old_value or '-'} → {log.new_value or '-'}", log.user)

        for call in CallRegister.objects.filter(incident=incident).select_related('user', 'person_contact'):
            contact = call.email if call.channel == 'EMAIL' else call.phone
            detail = [contact or (call.person_contact.phone if call.person_contact else None),
                      _("answered") if call.answered else _("not answered"), call.comment]
            if call.channel == 'EMAIL':
                title = _("Inbound email") if call.direction == CallRegister.DIRECTION_INBOUND else _("Outbound email")
            else:
                title = _("Inbound call") if call.direction == CallRegister.DIRECTION_INBOUND else _("Outbound call")
            add(call.call_start or call.time_call or call.created_at, 'call', title,
                ' · '.join(str(item) for item in detail if item), call.user)

        for report in incident.reports.select_related('user', 'deleted_by'):
            add(report.created_at, 'report', _("Report %(token)s") % {'token': report.token}, report.description, report.user)
            if not report.is_active:
                add(report.deleted_at, 'report_deleted', _("Report %(token)s deleted") % {'token': report.token},
                    report.deletion_reason, report.deleted_by)

        for observation in incident.observations.select_related('user'):
            add(observation.created_at, 'observation', _("Observation"), observation.observation, observation.user)

        for task in incident.tasks.all():
            add(task.created_at, 'task', _("Task: %(name)s") % {'name': task.name or '-'},
                task.set_date.isoformat() if task.set_date else None)

        add(incident.receipt_sent_at, 'receipt', _("Receipt sent"), incident.contact_email)
        add(incident.closed_at, 'closed', _("Incident closed"), incident.resolution)
        if not incident.is_active:
            add(incident.deleted_at, 'deleted', _("Incident deleted"), None, incident.deleted_by)

    events.sort(key=lambda event: event['date'], reverse=True)
    return events
