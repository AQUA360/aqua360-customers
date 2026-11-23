"""Relació entre lots de lectures i facturacions.

Un lot pot tenir lectures assignades a més d'una facturació (p. ex. quan el facturador
separa per empresa). El lot només es pot donar per facturat quan totes aquestes
facturacions estan processades.
"""
from django.db.models import Exists, OuterRef

from billing.models import Billing
from coredata.models import ConfigProject


def _cancelled_status_tokens():
    tokens = {'-1'}
    value = ConfigProject.objects.filter(token='billing_batch_cancelled').values_list('value', flat=True).first()
    if value:
        tokens.add(value)
    return tokens


def blocking_billings(processed_status_token):
    """Facturacions que impedeixen tancar un lot: actives, no processades ni cancel·lades.

    Les facturacions d'excloses (`is_excluded`) no compten, com abans: el lot es dona
    per facturat quan acaba la facturació principal.
    """
    return Billing.objects.filter(is_active=True, is_excluded=False).exclude(
        status__token__in=_cancelled_status_tokens() | {processed_status_token}
    )


def fully_billed_batches(batches, processed_status_token):
    """Filtra `batches` als lots sense cap lectura a una facturació encara pendent."""
    pending = blocking_billings(processed_status_token).filter(
        readings__batch_id=OuterRef('pk'),
        readings__is_active=True,
    )
    return batches.model.objects.filter(id__in=batches.values('id')).exclude(Exists(pending))


def assign_company_readings(billing, readings_by_sp, readings_general_canonical):
    """Assigna a una facturació d'empresa les lectures dels lots que són dels seus contractes.

    Les lectures canòniques de comptador general sense contracte es comparteixen entre
    empreses: no es mouen d'una facturació a una altra, sinó que se'n creen les còpies
    (`copied_from`) només per als contractes de l'empresa de la facturació.
    Retorna el nombre de lectures assignades o creades.
    """
    from billing.models import Reading
    from billing.utils.reading_service import fanout_general_meter_readings

    company_readings = Reading.objects.filter(
        id__in=(readings_by_sp | readings_general_canonical).filter(
            contract__company_id=billing.company_id
        ).values('id')
    )
    count = company_readings.update(billing=billing)

    shared_canonical = list(readings_general_canonical.filter(contract__isnull=True).distinct())
    if shared_canonical:
        # La primera facturació que la reclama se la queda com a referència del lot.
        Reading.objects.filter(
            id__in=[reading.id for reading in shared_canonical], billing__isnull=True
        ).update(billing=billing)
        count += len(fanout_general_meter_readings(billing, readings=shared_canonical))
    return count
