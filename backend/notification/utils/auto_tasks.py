"""
Tasques automàtiques del calendari.

Són tasques que crea el sistema quan detecta una feina pendent (p. ex. una OT de
canvi de comptador tancada sense haver aplicat el canvi) i que es tanquen soles
quan aquesta feina es resol. Cada tipus s'identifica amb un `source_key`; mentre
n'hi hagi una d'oberta per al mateix objecte, no se'n crea cap altra.

Per afegir un cas nou: definir-ne la clau, una funció `sync_<cas>(objecte)` que
cridi `open_auto_task`/`close_auto_tasks`, i enganxar-la al senyal o servei on
canvia l'estat de l'objecte.
"""
import json
import uuid

from django.conf import settings
from django.utils import timezone, translation
from django.utils.translation import gettext as _

from coredata.models import ConfigProject
from notification.models import CalendarTask

CHANGE_METER_PENDING = 'change_meter_pending'

# Tipus d'OT que impliquen un canvi de comptador (els mateixos que fa servir el
# frontend a ChangeMeterStatus.vue). Es poden sobreescriure amb el ConfigProject
# `order_type_change_meter_tokens` (llista JSON o tokens separats per comes).
DEFAULT_CHANGE_METER_ORDER_TYPES = ['change_meter', 'install_meter']


def _auto_tasks_of(source_key, order=None, contract=None):
    # Les tasques es lliguen a l'ordre si n'hi ha (encara que en canviï el contracte); si no, al contracte
    lookup = {'order': order} if order is not None else {'contract': contract}
    return CalendarTask.objects.filter(source=CalendarTask.SOURCE_AUTO, source_key=source_key, **lookup)


def open_auto_task(source_key, *, name, description=None, order=None, contract=None, user=None, color='amber'):
    """
    Crea la tasca si encara no n'hi ha cap del mateix tipus per al mateix objecte.
    Si n'hi ha una de feta (p. ex. tancada a mà perquè no calia fer res), no se'n
    torna a crear cap: l'ordre es pot tornar a desar moltes vegades.
    """
    task = _auto_tasks_of(source_key, order, contract).filter(is_active=True).order_by('task_done', '-id').first()
    if task:
        return task, False
    task = CalendarTask.objects.create(
        token=str(uuid.uuid4()),
        name=name,
        description=description,
        color=color,
        user=user,
        order=order,
        contract=contract,
        set_date=timezone.localdate(),
        source=CalendarTask.SOURCE_AUTO,
        source_key=source_key,
    )
    from notification.utils.task_notifications import notify_due_today
    notify_due_today([task.id])
    return task, True


def close_auto_tasks(source_key, *, order=None, contract=None, user=None):
    """Marca com a fetes les tasques obertes d'aquest tipus per a l'objecte."""
    return _auto_tasks_of(source_key, order, contract).filter(task_done=False).update(
        task_done=True, done_at=timezone.now(), done_by=user,
    )


def change_meter_order_types():
    config = ConfigProject.objects.filter(token='order_type_change_meter_tokens').first()
    if not config or not config.value:
        return DEFAULT_CHANGE_METER_ORDER_TYPES
    try:
        tokens = json.loads(config.value)
    except (TypeError, ValueError):
        tokens = config.value.split(',')
    return [str(t).strip().lower() for t in tokens if str(t).strip()]


def is_change_meter_order(order):
    return bool(order.type and (order.type.token or '').lower() in change_meter_order_types())


def sync_change_meter_task(order, user=None):
    """
    OT de canvi de comptador tancada i sense aplicar → tasca oberta;
    canvi ja aplicat → tasca tancada. La tasca s'assigna a qui va crear l'OT
    (o a tothom si no se sap).
    """
    if not is_change_meter_order(order):
        return None
    if order.change_meter_applied_at:
        close_auto_tasks(CHANGE_METER_PENDING, order=order, user=order.change_meter_applied_by or user)
        return None

    with translation.override(settings.LANGUAGE_CODE):
        name = _("Apply meter change")
        description = _("Order %(token)s is closed but the meter change has not been applied to the system yet.") % {
            'token': order.token or order.id,
        }
    task, _created = open_auto_task(
        CHANGE_METER_PENDING,
        name=name,
        description=description,
        order=order,
        contract=order.contract,
        user=order.created_by,
    )
    return task
