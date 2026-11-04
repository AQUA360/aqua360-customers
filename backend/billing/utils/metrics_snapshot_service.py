"""
Comptadors fixats (snapshot) dels lots de lectura i de les facturacions.

Mentre un lot o una facturació està obert, els comptadors (PS a llegir, contractes
a facturar...) es calculen en viu a partir de les rutes i dels contractes actius.
En tancar-se es desen a `metrics_snapshot`, perquè més endavant es vegi el que hi
havia en aquell moment i no l'estat actual. Si es reobre, s'esborren.
"""
import logging

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from coredata.models import ConfigProject

logger = logging.getLogger(__name__)


def _config_values(*tokens):
    return set(
        ConfigProject.objects.filter(token__in=tokens).values_list('value', flat=True)
    )


# --- Lots de lectura -------------------------------------------------------

def reading_batch_closed_status_tokens():
    """Pendent de facturar (lectures tancades) i facturat."""
    return _config_values('batch_status_finish_token', 'reading_batch_billed_token')


def build_reading_batch_snapshot(batch):
    from billing.serializers.reading_batch_serializer import (
        ReadingBatchMinimalSerializer,
        ReadingBatchSerializer,
    )
    from billing.utils.reading_batch_service import get_batch_supply_counts

    active_contract = ConfigProject.objects.get(token='contract_active_token').value

    snapshot = dict(ReadingBatchMinimalSerializer().compute_graph_metrics(batch))
    snapshot['num_active_supplies'] = ReadingBatchSerializer._count_active_supplies(batch)
    # Comptadors de la pantalla de configuració del lot (criteri propi, inclou subcomptadors).
    snapshot['summary'] = get_batch_supply_counts(batch, active_contract)
    snapshot['frozen_at'] = timezone.now()
    return snapshot


def sync_reading_batch_snapshot(batch, closed_tokens=None):
    """Fixa els comptadors si el lot està tancat i encara no en té; els esborra si s'ha reobert."""
    from billing.models import ReadingBatch

    if closed_tokens is None:
        closed_tokens = reading_batch_closed_status_tokens()
    is_closed = bool(batch.status_id) and batch.status.token in closed_tokens

    if is_closed and not batch.metrics_snapshot:
        try:
            with transaction.atomic():
                snapshot = build_reading_batch_snapshot(batch)
        except Exception:
            # Sense snapshot el lot segueix calculant en viu: no ha de bloquejar el canvi d'estat.
            logger.exception("No s'han pogut fixar els comptadors del lot de lectura %s", batch.pk)
            return
    elif not is_closed and batch.metrics_snapshot:
        snapshot = None
    else:
        return

    ReadingBatch.objects.filter(pk=batch.pk).update(metrics_snapshot=snapshot)
    batch.metrics_snapshot = snapshot


# --- Facturacions ----------------------------------------------------------

def billing_snapshot_status_tokens():
    """
    (estats on es fixa, estats on es conserva): es fixa en quedar processada i es
    conserva si torna a generar documents; qualsevol altre estat la reobre.
    """
    processed = _config_values('billing_batch_processed')
    return processed, processed | _config_values('billing_batch_processing_documents')


def build_billing_routes_summary(billing):
    """Lectures processades / lectures previstes per ruta de la facturació, en viu."""
    from billing.models import ReadingBatch, ReadingBatchStatus
    from contract.models import ContractStatus
    from service.models import SupplyPoint
    from service.serializers.route_serializer import RouteListSerializer

    if billing.is_excluded:
        return [{
            'route': {'name': "Lectures excloses"},
            'batch': None,
            'processed_at': billing.created_at,
            'processed_readings': billing.readings.count(),
            'warning': False
        }]

    pending_billing_status_token = ConfigProject.objects.get(token='batch_status_finish_token').value
    pending_billing_status = ReadingBatchStatus.objects.filter(token=pending_billing_status_token).order_by('created_at').first()
    reading_batches = ReadingBatch.objects.filter(status=pending_billing_status).all()

    contract_active_token = ConfigProject.objects.get(token='contract_active_token').value
    active_contract_status = ContractStatus.objects.get(token=contract_active_token)

    response = []
    for route in billing.routes.all():
        # Find the first batch in reading_batches that has this route
        batch = reading_batches.filter(routes=route).first()

        # Get all supply points that belong to this route with active contracts
        route_supply_points = SupplyPoint.objects.filter(
            property__route_position__route=route
        ).filter(
            Q(contracts__status=active_contract_status) | Q(default_contracts__status=active_contract_status)
        ).distinct()

        # Count readings in the batch that have these supply points
        readings_count = billing.readings.filter(
            supply_point__in=route_supply_points
        ).count()

        route_data = RouteListSerializer(route).data

        response.append({
            'route': route_data,
            'batch': batch.id if batch else None,
            'processed_at': batch.processed_at if batch else None,
            'processed_readings': readings_count,
            'warning': True if readings_count != route_data['num_total_readings'] else False
        })

    return response


def sync_billing_snapshot(billing):
    """Fixa el resum per ruta en processar la facturació; l'esborra si torna a un estat anterior."""
    from billing.models import Billing

    freeze_tokens, keep_tokens = billing_snapshot_status_tokens()
    status_token = billing.status.token if billing.status_id else None

    if status_token in freeze_tokens and not billing.metrics_snapshot:
        try:
            with transaction.atomic():
                snapshot = {
                    'routes': build_billing_routes_summary(billing),
                    'frozen_at': timezone.now(),
                }
        except Exception:
            # Sense snapshot la facturació segueix calculant en viu: no ha de bloquejar el canvi d'estat.
            logger.exception("No s'han pogut fixar els comptadors de la facturació %s", billing.pk)
            return
    elif status_token not in keep_tokens and billing.metrics_snapshot:
        snapshot = None
    else:
        return

    Billing.objects.filter(pk=billing.pk).update(metrics_snapshot=snapshot)
    billing.metrics_snapshot = snapshot
