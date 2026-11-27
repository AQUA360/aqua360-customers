"""
Abast de la LecturApp: quins lots, comptadors i bateries pot llegir o escriure un operari.

L'app només treballa amb lots oberts (actius i que no estan finalitzats, cancel·lats ni
facturats). Dins d'un lot, només es poden desar lectures dels comptadors que el lot
inclou: els fixats al lot, els dels punts de les seves rutes (i els seus subcomptadors)
i els que ja hi tenen una lectura. Les bateries només es poden consultar si són d'una
finca que és en algun lot obert.
"""
from django.db.models import Q

from billing.models import ReadingBatch
from coredata.models import ConfigProject
from service.models import Cluster, Meter, SupplyPoint
from service.utils.route_scope import effective_route_q, reading_batch_supply_points_q

# Camps de ConfigProject amb els tokens dels estats de lot tancat
CLOSED_BATCH_STATUS_CONFIG_TOKENS = (
    'batch_status_finish_token',
    'batch_status_cancel_token',
    'batch_status_billed_token',
)


def closed_batch_status_tokens():
    """Tokens dels estats en què un lot ja no admet lectures de l'app."""
    return [
        value for value in ConfigProject.objects.filter(
            token__in=CLOSED_BATCH_STATUS_CONFIG_TOKENS,
        ).values_list('value', flat=True) if value
    ]


def open_reading_batches():
    """Lots que l'app pot veure i on pot escriure."""
    return ReadingBatch.objects.filter(is_active=True).exclude(
        status__token__in=closed_batch_status_tokens(),
    )


def get_open_reading_batch(reading_batch_id):
    """El lot si és obert; si no existeix o és tancat, None."""
    return open_reading_batches().filter(id=reading_batch_id).first()


def is_reading_batch_open(reading_batch):
    return open_reading_batches().filter(id=reading_batch.id).exists()


def meter_in_reading_batch(meter, reading_batch):
    """El comptador forma part del lot (directament, per ruta o perquè ja hi té lectura)."""
    return Meter.objects.filter(id=meter.id).filter(
        Q(reading_batches=reading_batch)
        | Q(meter_general__reading_batches=reading_batch)
        | Q(reading__batch=reading_batch)
        | reading_batch_supply_points_q(reading_batch, prefix='supply_points__')
        | reading_batch_supply_points_q(reading_batch, prefix='meter_general__supply_points__')
    ).exists()


def _supply_points_in_open_batches_q():
    open_batches = open_reading_batches()
    return (
        effective_route_q('route__reading_batches__in', open_batches)
        | Q(meter__reading_batches__in=open_batches)
    )


def property_in_open_batch(property_id):
    """La finca té algun punt en un lot obert (per ruta o per comptador fixat)."""
    return SupplyPoint.objects.filter(property_id=property_id).filter(
        _supply_points_in_open_batches_q(),
    ).exists()


def cluster_in_open_batch(cluster_id):
    """La bateria és d'una finca que és en algun lot obert."""
    cluster = Cluster.objects.filter(id=cluster_id).only('id', 'property_id').first()
    if not cluster:
        return False
    property_ids = set(
        SupplyPoint.objects.filter(
            cluster_nozzle__cluster_id=cluster_id, property_id__isnull=False,
        ).values_list('property_id', flat=True)
    )
    if cluster.property_id:
        property_ids.add(cluster.property_id)
    if not property_ids:
        return False
    return SupplyPoint.objects.filter(property_id__in=property_ids).filter(
        _supply_points_in_open_batches_q(),
    ).exists()
