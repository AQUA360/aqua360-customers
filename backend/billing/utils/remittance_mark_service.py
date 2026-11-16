"""
"Marcar per remesar": marca a mà els pagaments que han d'entrar a la propera
remesa SEPA (`Payment.is_marked_for_remittance`). La generació de remeses pot
limitar-se només als pagaments marcats (`only_marked_for_remittance`).

- No es pot marcar un pagament que ja és en una remesa pendent d'enviar.
- En enviar la remesa, els seus pagaments es desmarquen.
"""
from django.utils import timezone

from billing.models import Payment
from coredata.models import ConfigProject


def in_pending_remittance(payments):
    """Pagaments del queryset que són en alguna remesa encara no enviada."""
    return payments.filter(remittances__isnull=False, remittances__sent_at__isnull=True)


def payment_in_pending_remittance(payment):
    return in_pending_remittance(Payment.objects.filter(pk=payment.pk)).exists()


def markable_invoice_payments(invoice):
    """Pagaments d'una factura que es poden marcar per remesar des de la factura:
    actius, per domiciliació bancària (SEPA), en estat pendent i que no són ja
    en una remesa pendent d'enviar."""
    pending_token = ConfigProject.objects.filter(
        token='payment_status_pending_token'
    ).values_list('value', flat=True).first()
    if not pending_token:
        return invoice.payments.none()
    payments = invoice.payments.filter(
        is_active=True,
        payment_type_token='DIRECT_DEBIT',
        status__token=pending_token,
    )
    return payments.exclude(id__in=in_pending_remittance(payments).values('id'))


def invoice_remittance_mark_summary(invoice):
    """{can_mark, marked}: si hi ha algun pagament que es pugui marcar (i encara
    no ho estigui) i quants pagaments de la factura estan marcats."""
    return {
        'can_mark': markable_invoice_payments(invoice).filter(is_marked_for_remittance=False).exists(),
        'marked': invoice.payments.filter(is_active=True, is_marked_for_remittance=True).count(),
    }


def _set_flag(payments, marked):
    # `update()` no dispara els senyals de pagament: només és un indicador i no
    # ha de generar moviments ni canvis d'estat.
    return payments.exclude(is_marked_for_remittance=marked).update(
        is_marked_for_remittance=marked, updated_at=timezone.now()
    )


def set_invoice_marked_for_remittance(invoice, marked):
    """Marca els pagaments marcables de la factura o desmarca tots els seus
    pagaments. Retorna quants n'ha canviat."""
    if marked:
        return _set_flag(markable_invoice_payments(invoice), True)
    return _set_flag(invoice.payments.all(), False)


def clear_remittance_marks(remittance_ids):
    """Desmarca els pagaments de les remeses indicades (en enviar-les)."""
    return _set_flag(Payment.objects.filter(remittances__id__in=remittance_ids), False)
