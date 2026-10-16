import datetime

from celery import shared_task
from django.utils import timezone
from django.utils.translation import gettext as _


@shared_task
def export_incidents_csv_task(query_params):
    try:
        from notification.models import Incident
        from notification.filters.incident_filter import IncidentFilter
        from notification.utils.incident_csv_export import build_incident_export_csv_bytes
        from documentmanager.utils.main_utils import upload_document
        from django.core.files.base import ContentFile
        from django.conf import settings
        
        # Filter the queryset according to the query_params received
        queryset = Incident.objects.all().order_by('status__position', '-created_at')
        filterset = IncidentFilter(
            data=query_params,
            queryset=queryset,
        )
        filtered = filterset.qs
        
        csv_bytes = build_incident_export_csv_bytes(filtered)
        
        filename = f"incidents_export_{timezone.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        service = settings.DOCUMENT_MANAGER_SERVICES.get("statistics", "hdd")
        content_file = ContentFile(csv_bytes, name=filename)
        
        document = upload_document(
            file=content_file,
            entity="INCIDENT",
            field="EXPORT",
            entity_id=0,
            entity_token="INCIDENT_EXPORT",
            folder="",
            service=service,
            document_name=filename,
            date=timezone.now()
        )
        
        return {
            "status": "success",
            "message": "Incidents export generated successfully",
            "document_id": document.id,
            "filename": filename
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Error generating incidents export: {str(e)}"
        }


@shared_task
def generate_recurring_tasks():
    """Allarga l'horitzó de les ocurrències de totes les tasques recurrents actives."""
    from notification.models import CalendarTaskRecurrence
    from notification.utils.recurrence import generate_occurrences

    created = 0
    for recurrence in CalendarTaskRecurrence.objects.filter(is_active=True):
        try:
            created += generate_occurrences(recurrence)
        except Exception as e:
            print(f"Error generating occurrences of recurrence {recurrence.id}: {e}")
    return {'created': created}


@shared_task
def notify_today_tasks():
    """
    Avisa (notificació dins l'aplicació) de les tasques pendents d'avui o
    endarrerides de les quals encara no s'havia avisat. Les que es creen per al
    mateix dia ja s'avisen en desar-les; aquesta tasca cobreix les que arriben
    al seu dia (p. ex. les ocurrències de les recurrents) i les que hagin quedat
    sense avisar.
    """
    from notification.models import CalendarTask
    from notification.utils.task_notifications import notify_tasks, pending_unnotified

    tasks = list(
        pending_unnotified(CalendarTask.objects.filter(set_date__lte=timezone.localdate()))
        .select_related('user').order_by('set_date', 'time', 'id')
    )
    notifications = notify_tasks(tasks)
    return {'notified_tasks': len(tasks), 'notifications': notifications}


@shared_task
def send_daily_tasks_email():
    """
    Correu de resum amb les tasques pendents d'avui i les endarrerides, per als
    usuaris que ho tenen activat a les preferències. Només inclou les tasques
    assignades a l'usuari (les de tothom ja surten a la notificació general).
    """
    from django.conf import settings
    from django.utils import translation
    from django.utils.html import escape
    from notification.models import CalendarTask, NotificationPreference
    from notification.utils.staff_email import send_staff_email

    today = timezone.localdate()
    sent = 0
    preferences = NotificationPreference.objects.filter(
        email_daily_tasks=True, user__is_active=True,
    ).exclude(user__email='').exclude(user__email__isnull=True).select_related('user')

    with translation.override(settings.LANGUAGE_CODE):
        for preference in preferences:
            user = preference.user
            tasks = list(
                CalendarTask.objects.filter(
                    is_active=True, task_done=False, set_date__lte=today, user=user,
                ).order_by('set_date', 'time', 'id')
            )
            if not tasks:
                continue

            rows = []
            for task in tasks:
                when = task.set_date.strftime('%d/%m/%Y')
                if task.time:
                    when += ' ' + task.time.strftime('%H:%M')
                overdue = task.set_date < today
                rows.append(
                    '<tr><td style="padding:4px 12px 4px 0;{style}">{when}</td>'
                    '<td style="padding:4px 0"><strong>{name}</strong>{desc}</td></tr>'.format(
                        style='color:#dc2626' if overdue else '',
                        when=escape(when),
                        name=escape(task.name or '-'),
                        desc=('<br><span style="color:#64748b">' + escape(task.description) + '</span>') if task.description else '',
                    )
                )
            subject = _("You have %(count)s pending tasks") % {'count': len(tasks)}
            html = '<p>{intro}</p><table>{rows}</table>'.format(
                intro=escape(_("These are your pending tasks for today, and the overdue ones:")),
                rows=''.join(rows),
            )
            try:
                send_staff_email(user.email, subject, html)
                sent += 1
            except Exception as e:
                print(f"Error sending daily tasks email to user {user.id}: {e}")
    return {'sent': sent}
