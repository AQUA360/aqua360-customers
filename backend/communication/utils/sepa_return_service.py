from billing.models import Payment
from coredata.models import ConfigProject


def parse_sepa_return_ids(sepa_return_ids):
    """Ids de devolucions SEPA a partir d'un id, una llista o un text "1,2,3".

    El procés de comunicació desa l'objecte fixat com a text (fixed_data_id), i
    s'hi poden triar diverses devolucions alhora.
    """
    if sepa_return_ids is None:
        return []
    if isinstance(sepa_return_ids, (list, tuple, set)):
        values = sepa_return_ids
    else:
        values = str(sepa_return_ids).split(',')
    ids = []
    for value in values:
        value = str(value).strip()
        if value.isdigit() and int(value) not in ids:
            ids.append(int(value))
    return ids


def get_sepa_return_pending_payments(sepa_return_ids):
    """Rebuts d'una o diverses devolucions SEPA que encara s'han de reclamar.

    Els que ja s'han tornat a cobrar (o s'han anul·lat) des de la devolució no
    s'han d'avisar: queden fora tant dels destinataris com dels adjunts.
    """
    settled_status_tokens = list(ConfigProject.objects.filter(
        token__in=['payment_status_paid_token', 'payment_status_cancelled_token']
    ).values_list('value', flat=True))
    return Payment.objects.filter(
        remittances_returns__id__in=parse_sepa_return_ids(sepa_return_ids),
        is_active=True,
    ).exclude(status__token__in=settled_status_tokens).distinct()
