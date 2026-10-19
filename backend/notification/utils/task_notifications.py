"""
Avisos (notificació dins l'aplicació) de les tasques del calendari.

Cada tasca s'avisa un sol cop (`notified_at`). Es fa en dos moments:
- en desar una tasca per a avui, just després de desar-la (`notify_due_today`);
- cada nit, per a les que arriben al seu dia o s'han quedat sense avisar
  (`notification.tasks.notify_today_tasks`).
"""
import uuid

from django.conf import settings
from django.db import transaction
from django.utils import timezone, translation
from django.utils.translation import gettext as _

from notification.models import CalendarTask, Notification


def _task_list_text(tasks, limit=5):
    """Join task names up to the limit and summarize any remaining tasks."""
    names = [t.name or '-' for t in tasks[:limit]]
    text = ', '.join(names)
    if len(tasks) > limit:
        text += ' ' + _("and %(count)s more") % {'count': len(tasks) - limit}
    return text


def notify_tasks(tasks):
    """
    Crea una notificació per usuari (i una per a les tasques de tothom) amb les
    tasques donades, i les marca com a avisades. Retorna el nombre de notificacions.
    """
    tasks = list(tasks)
    if not tasks:
        return 0
    today = timezone.localdate()
    by_user = {}
    for task in tasks:
        by_user.setdefault(task.user, []).append(task)

    with translation.override(settings.LANGUAGE_CODE):
        for user, user_tasks in by_user.items():
            if len(user_tasks) == 1:
                description = _("You have a pending task: %(task)s") % {'task': user_tasks[0].name or '-'}
            else:
                description = _("You have %(count)s pending tasks: %(tasks)s") % {
                    'count': len(user_tasks), 'tasks': _task_list_text(user_tasks),
                }
            dates = {t.set_date for t in user_tasks}
            Notification.objects.create(
                token=str(uuid.uuid4()),
                name=_("Pending tasks for today"),
                description=description,
                module='notification',
                entity='calendar',
                # Si totes són del mateix dia, la notificació obre el calendari en aquell dia
                object_id=(dates.pop() if len(dates) == 1 else today).isoformat(),
                is_active=True,
                user=user,
            )

    CalendarTask.objects.filter(id__in=[t.id for t in tasks]).update(notified_at=timezone.now())
    return len(by_user)


def pending_unnotified(queryset):
    """Restrict a queryset to active unfinished tasks not yet notified."""
    return queryset.filter(is_active=True, task_done=False, notified_at__isnull=True)


def notify_due_today(task_ids):
    """
    Un cop confirmada la transacció, avisa de les tasques d'avui encara no
    avisades. Es crida en crear o modificar tasques, perquè l'avís no hagi
    d'esperar a la tasca nocturna.
    """
    task_ids = [task_id for task_id in task_ids if task_id]
    if not task_ids:
        return

    def _notify():
        """Notify the selected tasks still due today and unnotified after commit."""
        tasks = pending_unnotified(
            CalendarTask.objects.filter(id__in=task_ids, set_date=timezone.localdate())
        ).select_related('user')
        notify_tasks(tasks)

    transaction.on_commit(_notify)
