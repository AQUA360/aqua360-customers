"""
Utilitats de les incidències (gestió SAC).

L'aplicació dona les eines; cada client decideix com les fa servir: terminis,
avisos, escalats, pauses i justificant es configuren per tipus o per
estat i, si no es configuren, no fan res.
"""
import datetime
import logging
import uuid

from django.conf import settings
from django.db import transaction
from django.template import Context, Template
from django.utils import timezone, translation
from django.utils.translation import gettext as _

from coredata.models import ConfigProject
from coredata.utils.working_days import add_working_days, count_working_days, subtract_working_days
from notification.models import Incident, IncidentType, Notification

logger = logging.getLogger(__name__)

NOTIFICATION_MODULE = 'incident'
NOTIFICATION_ENTITY = 'incidents'
DEFAULT_RETENTION_YEARS = 5


def get_config(token, default=None):
    """Return a ConfigProject value or the default when it is missing or empty."""
    config = ConfigProject.objects.filter(token=token).first()
    return config.value if config and config.value not in (None, '') else default


def get_closed_status_token():
    """Return the token of the incident status that means closed."""
    return get_config('incident_status_closed_token', '2')


def incident_exploitation(incident):
    """Explotació de la incidència (per als festius propis de l'explotació)."""
    for path in (
        ('contract', 'supply_point_default', 'connection', 'exploitation'),
        ('supply_point', 'connection', 'exploitation'),
        ('cluster', 'connection', 'exploitation'),
    ):
        value = incident
        for attr in path:
            value = getattr(value, attr, None)
            if value is None:
                break
        if value is not None:
            return value
    return None


def _end_of_day(date):
    """Final del dia en hora local: els terminis en dies vencen a la mitjanit."""
    return timezone.make_aware(datetime.datetime.combine(date, datetime.time(23, 59, 59)))


def shift(moment, amount, unit, exploitation=None, backwards=False):
    """Mou una data i hora la quantitat indicada en la unitat del termini."""
    if unit == IncidentType.UNIT_HOURS:
        delta = datetime.timedelta(hours=amount)
        return moment - delta if backwards else moment + delta
    if unit == IncidentType.UNIT_NATURAL_DAYS:
        delta = datetime.timedelta(days=amount)
        return moment - delta if backwards else moment + delta
    local = timezone.localtime(moment)
    move = subtract_working_days if backwards else add_working_days
    date = move(local.date(), amount, exploitation)
    return timezone.make_aware(datetime.datetime.combine(date, local.time().replace(tzinfo=None)))


def compute_due_at(incident_type, start, exploitation=None):
    """
    Data límit segons el termini del tipus a partir de start (data i hora de
    registre). Retorna None si el tipus no té termini.
    """
    if not incident_type or incident_type.due_term is None or start is None:
        return None
    if incident_type.due_unit == IncidentType.UNIT_HOURS:
        return start + datetime.timedelta(hours=incident_type.due_term)
    start_date = timezone.localtime(start).date()
    if incident_type.due_unit == IncidentType.UNIT_NATURAL_DAYS:
        return _end_of_day(start_date + datetime.timedelta(days=incident_type.due_term))
    return _end_of_day(add_working_days(start_date, incident_type.due_term, exploitation))


def pending_incidents(queryset=None):
    """Restrict a queryset to active incidents that are not closed."""
    if queryset is None:
        queryset = Incident.objects.all()
    return queryset.filter(is_active=True).exclude(status__token=get_closed_status_token())


def is_overdue(incident, closed_token=None, now=None):
    """Pendent, sense pausa i amb la data límit passada."""
    if not incident.due_at or incident.paused_at:
        return False
    if incident.due_at >= (now or timezone.now()):
        return False
    closed_token = closed_token if closed_token is not None else get_closed_status_token()
    return not (incident.status and incident.status.token == closed_token)


# --- Avisos ---------------------------------------------------------------

def _notify(user_ids, name, description, incident=None):
    """Create one in-app notification per user, linked to the incident when given."""
    for user_id in {user_id for user_id in user_ids if user_id}:
        Notification.objects.create(
            token=str(uuid.uuid4()),
            name=name,
            description=description,
            module=NOTIFICATION_MODULE,
            entity=NOTIFICATION_ENTITY,
            object_id=str(incident.id) if incident else None,
            is_active=True,
            user_id=user_id,
        )


def _label(incident):
    return incident.name or incident.token or '-'


def _format_due(incident):
    local = timezone.localtime(incident.due_at)
    if incident.type and incident.type.due_unit == IncidentType.UNIT_HOURS:
        return local.strftime('%d/%m/%Y %H:%M')
    return local.strftime('%d/%m/%Y')


def notify_assignment(incident):
    """Un cop confirmada la transacció, avisa l'usuari assignat de la incidència."""
    if not incident.assigned_to_id:
        return

    def _send():
        """Create the assignment notification for the incident assignee."""
        with translation.override(settings.LANGUAGE_CODE):
            description = _("You have been assigned the incident %(incident)s") % {'incident': _label(incident)}
            if incident.due_at:
                description += ' ' + _("(due %(date)s)") % {'date': _format_due(incident)}
            _notify([incident.assigned_to_id], _("Incident assigned"), description, incident)

    transaction.on_commit(_send)


def notify_due_incidents(today=None):
    """
    Crea una notificació per usuari assignat amb les seves incidències pendents
    que vencen avui o ja han vençut. Retorna el nombre de notificacions.
    """
    today = today or timezone.localdate()
    incidents = pending_incidents().filter(
        assigned_to__isnull=False, due_at__isnull=False, paused_at__isnull=True,
        due_at__lte=_end_of_day(today),
    ).order_by('due_at')

    by_user = {}
    for incident in incidents:
        by_user.setdefault(incident.assigned_to_id, []).append(incident)

    with translation.override(settings.LANGUAGE_CODE):
        for user_id, user_incidents in by_user.items():
            text = ', '.join(_label(i) for i in user_incidents[:5])
            if len(user_incidents) > 5:
                text += ' ' + _("and %(count)s more") % {'count': len(user_incidents) - 5}
            if len(user_incidents) == 1:
                description = _("You have a pending incident due: %(incidents)s") % {'incidents': text}
            else:
                description = _("You have %(count)s pending incidents due: %(incidents)s") % {
                    'count': len(user_incidents), 'incidents': text,
                }
            # Amb una sola incidència la notificació l'obre directament
            _notify([user_id], _("Pending incidents"), description,
                    user_incidents[0] if len(user_incidents) == 1 else None)
    return len(by_user)


def escalation_recipients(incident_type):
    """Users to notify when an incident of this type is escalated."""
    user_ids = set()
    if incident_type.escalation_user_id:
        user_ids.add(incident_type.escalation_user_id)
    if incident_type.escalation_group_id:
        user_ids.update(
            incident_type.escalation_group.user_set.filter(is_active=True).values_list('id', flat=True)
        )
    return user_ids


def check_incident_deadlines(now=None):
    """
    Revisa els terminis de les incidències pendents i envia, un sol cop cadascun:
    l'avís previ al venciment (a l'assignat), l'escalat després del venciment
    (a l'usuari o grup del tipus) i l'avís de pausa massa llarga (a l'assignat).
    """
    now = now or timezone.now()
    result = {'warned': 0, 'escalated': 0, 'pause_warned': 0}
    incidents = pending_incidents().select_related('type', 'status', 'type__escalation_group')

    with translation.override(settings.LANGUAGE_CODE):
        for incident in incidents.filter(due_at__isnull=False, paused_at__isnull=True):
            incident_type = incident.type
            if not incident_type:
                continue
            exploitation = None
            if incident_type.due_unit == IncidentType.UNIT_BUSINESS_DAYS:
                exploitation = incident_exploitation(incident)

            if incident_type.warning_before is not None and not incident.warned_at and incident.assigned_to_id:
                if now >= shift(incident.due_at, incident_type.warning_before, incident_type.due_unit, exploitation, backwards=True):
                    _notify([incident.assigned_to_id], _("Incident about to expire"),
                            _("The incident %(incident)s is due %(date)s") % {
                                'incident': _label(incident), 'date': _format_due(incident)},
                            incident)
                    Incident.objects.filter(pk=incident.pk).update(warned_at=now)
                    result['warned'] += 1

            if incident_type.escalation_after is not None and not incident.escalated_at:
                if now >= shift(incident.due_at, incident_type.escalation_after, incident_type.due_unit, exploitation):
                    recipients = escalation_recipients(incident_type)
                    if recipients:
                        _notify(recipients, _("Incident escalated"),
                                _("The incident %(incident)s is overdue since %(date)s") % {
                                    'incident': _label(incident), 'date': _format_due(incident)},
                                incident)
                    Incident.objects.filter(pk=incident.pk).update(escalated_at=now)
                    result['escalated'] += 1

        for incident in incidents.filter(paused_at__isnull=False, pause_warned_at__isnull=True,
                                         status__max_pause_days__isnull=False):
            days = count_working_days(timezone.localtime(incident.paused_at).date(), timezone.localdate(now),
                                      incident_exploitation(incident))
            if days > incident.status.max_pause_days:
                _notify([incident.assigned_to_id or incident.created_by_id], _("Incident paused for too long"),
                        _("The incident %(incident)s has been in %(status)s for %(days)s business days") % {
                            'incident': _label(incident), 'status': incident.status.name, 'days': days},
                        incident)
                Incident.objects.filter(pk=incident.pk).update(pause_warned_at=now)
                result['pause_warned'] += 1
    return result


# --- Pausa i tancament (es criden des del senyal de canvi d'estat) ---------

def apply_status_change(instance, previous_status, now=None):
    """
    Ajusta la incidència al canvi d'estat: data de tancament, inici i fi de la
    pausa del termini (en sortir de la pausa, la data límit s'allarga el temps
    que ha estat aturada) i, si es reobre, permet tornar a avisar.
    """
    now = now or timezone.now()
    closed_token = get_closed_status_token()
    new_status = instance.status

    if new_status and new_status.token == closed_token:
        instance.closed_at = now
    elif previous_status and previous_status.token == closed_token:
        instance.closed_at = None

    pauses_now = bool(new_status and new_status.pauses_due)
    if pauses_now and not instance.paused_at:
        instance.paused_at = now
    elif not pauses_now and instance.paused_at:
        if instance.due_at:
            unit = instance.type.due_unit if instance.type else IncidentType.UNIT_NATURAL_DAYS
            if unit == IncidentType.UNIT_BUSINESS_DAYS:
                days = count_working_days(timezone.localtime(instance.paused_at).date(), timezone.localdate(now),
                                          incident_exploitation(instance))
                instance.due_at = shift(instance.due_at, days, unit, incident_exploitation(instance))
            else:
                instance.due_at = instance.due_at + (now - instance.paused_at)
            # Amb una data límit nova, els avisos es poden tornar a enviar
            instance.warned_at = None
            instance.escalated_at = None
        instance.paused_at = None
        instance.pause_warned_at = None


def record_first_response(incident, when=None):
    """Desa la primera resposta (primer informe o trucada sortint) si encara no en té."""
    if incident and not incident.first_response_at:
        Incident.objects.filter(pk=incident.pk, first_response_at__isnull=True).update(
            first_response_at=when or timezone.now()
        )


# --- Retenció ---------------------------------------------------------------

def retention_years():
    try:
        return int(get_config('incident_retention_years', DEFAULT_RETENTION_YEARS))
    except (TypeError, ValueError):
        return DEFAULT_RETENTION_YEARS


def retention_limit(now=None):
    """Data a partir de la qual les incidències encara són dins del període de retenció."""
    now = now or timezone.now()
    try:
        return now.replace(year=now.year - retention_years())
    except ValueError:
        # 29 de febrer
        return now.replace(year=now.year - retention_years(), day=28)


def within_retention(incident):
    return bool(incident.created_at and incident.created_at >= retention_limit())


# --- Justificant de registre a l'abonat ------------------------------------

def recipient_email(incident):
    """Correu de contacte de la incidència o, si no en té, el de comunicacions del contracte."""
    if incident.contact_email:
        return incident.contact_email
    contract = incident.contract
    if contract and contract.person_contact_email and contract.person_contact_email.email:
        return contract.person_contact_email.email
    return None


def render_text(text, incident):
    """Substitueix les variables {referencia}, {titol}, {data}, {data_limit}, {tall_causa} i {tall_previsio}."""
    if not text:
        return ''
    cut = incident.supply_cut
    values = {
        'referencia': incident.token or '',
        'titol': incident.name or '',
        'data': timezone.localtime(incident.created_at).strftime('%d/%m/%Y %H:%M') if incident.created_at else '',
        'data_limit': _format_due(incident) if incident.due_at else '',
        'tall_causa': cut.cause.name if cut and cut.cause else '',
        'tall_previsio': timezone.localtime(cut.date_end).strftime('%d/%m/%Y %H:%M') if cut and cut.date_end else '',
    }
    for key, value in values.items():
        text = text.replace('{' + key + '}', value)
    return text


RECEIPT_TEMPLATE = """
<html><head><meta charset="utf-8"><style>
body { font-family: Helvetica, Arial, sans-serif; font-size: 11pt; }
h1 { font-size: 16pt; }
td { padding: 4px 8px 4px 0; vertical-align: top; }
.label { color: #555; }
</style></head><body>
<h1>{{ title }}</h1>
{% if intro %}<p>{{ intro|linebreaksbr }}</p>{% endif %}
<table>
{% for label, value in rows %}<tr><td class="label">{{ label }}</td><td>{{ value|linebreaksbr }}</td></tr>{% endfor %}
</table>
<p class="label">{{ footer }}</p>
</body></html>
"""


def build_receipt_html(incident):
    """Return the receipt HTML with the incident reference, date and time, channel and content."""
    with translation.override(settings.LANGUAGE_CODE):
        rows = [
            (_("Reference"), incident.token or ''),
            (_("Date and time"), timezone.localtime(incident.created_at).strftime('%d/%m/%Y %H:%M:%S')),
            (_("Channel"), incident.channel.name if incident.channel else '-'),
            (_("Type"), incident.type.name if incident.type else '-'),
            (_("Subject"), incident.name or ''),
            (_("Content"), incident.description or ''),
        ]
        if incident.contract:
            rows.append((_("Contract"), incident.contract.token or ''))
        if incident.due_at:
            rows.append((_("Maximum resolution date"), _format_due(incident)))
        context = Context({
            'title': _("Registration receipt"),
            'intro': render_text(incident.type.receipt_text if incident.type else '', incident),
            'rows': rows,
            'footer': _("Keep this reference to check the status of your request."),
        })
        return Template(RECEIPT_TEMPLATE).render(context)


def generate_receipt(incident):
    """Genera el justificant en PDF, el desa al gestor documental i el vincula a la incidència."""
    from io import BytesIO

    from django.core.files.base import ContentFile

    from communication.utils.communication_service import _create_pdf_with_table_rowheight_retry
    from documentmanager.utils.main_utils import upload_document

    buffer = BytesIO()
    status = _create_pdf_with_table_rowheight_retry(build_receipt_html(incident), buffer)
    if status.err:
        raise Exception("Error generating incident receipt PDF")
    # Nom descriptiu i amb extensió perquè es reconegui com a PDF en descarregar-lo
    filename = f"Justificant_registre_incidencia_{incident.token}.pdf"
    document = upload_document(
        file=ContentFile(buffer.getvalue(), name=filename),
        entity="INCIDENT",
        field="RECEIPT",
        entity_id=incident.id,
        entity_token=incident.token,
        folder="",
        service=settings.DOCUMENT_MANAGER_SERVICES.get("incident", settings.DOCUMENT_MANAGER_SERVICES.get("statistics", "hdd")),
        document_name=filename,
        date=timezone.now(),
    )
    Incident.objects.filter(pk=incident.pk).update(receipt_document=document)
    incident.receipt_document = document
    return document, buffer.getvalue()


def send_receipt(incident):
    """
    Genera el justificant i l'envia per correu si hi ha adreça. Retorna True si
    s'ha enviat; el document es genera igualment perquè es pugui lliurar per
    altres vies.
    """
    from notification.utils.staff_email import send_staff_email

    document, pdf = generate_receipt(incident)
    email = recipient_email(incident)
    if not email:
        return False
    with translation.override(settings.LANGUAGE_CODE):
        subject = _("Receipt of your request %(reference)s") % {'reference': incident.token}
        html = build_receipt_html(incident)
    send_staff_email(email, subject, html, attachments=[(document.document_name or f"Justificant_registre_incidencia_{incident.token}.pdf", pdf)])
    Incident.objects.filter(pk=incident.pk).update(receipt_sent_at=timezone.now())
    return True


def blocking_incident(contract):
    """Incidència oberta del contracte d'un tipus que bloqueja les ofertes comercials."""
    if not contract:
        return None
    return pending_incidents(Incident.objects.filter(contract=contract, type__blocks_commercial=True)).first()
