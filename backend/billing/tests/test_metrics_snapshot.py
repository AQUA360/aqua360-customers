from datetime import date

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from billing.models import Billing, BillingStatus, Reading, ReadingBatch, ReadingBatchStatus
from billing.serializers.reading_batch_serializer import (
    ReadingBatchMinimalSerializer,
    ReadingBatchSerializer,
    reading_batch_list_config_tokens,
)
from billing.utils.metrics_snapshot_service import sync_reading_batch_snapshot
from contract.models import Contract, ContractStatus
from coredata.models import ConfigProject
from service.models import Meter, MeterStatus, SupplyPoint, SupplyPointStatus


def config_value(token, default_value):
    """Valor d'un ConfigProject (es reaprofita si la BBDD ja el té)."""
    return ConfigProject.objects.get_or_create(token=token, defaults={'value': default_value})[0].value


def status_for(model, config_token, default_value):
    value = config_value(config_token, default_value)
    return model.objects.get_or_create(token=value, defaults={'name': value})[0]


class ReadingBatchMetricsSnapshotTests(TestCase):
    """En tancar un lot de lectura es fixen els comptadors; en reobrir-lo es tornen a calcular en viu."""

    def setUp(self):
        reading_batch_list_config_tokens.cache_clear()
        self.addCleanup(reading_batch_list_config_tokens.cache_clear)

        active_contract = config_value('contract_active_token', 'SNAP-ACTIVE')
        config_value('supply_point_status_activate_token', 'SNAP-SP-ACTIVE')
        config_value('token_meter_status_no_meter', 'SNAP-NO-METER')
        config_value('contract_terminated_status', 'SNAP-TERMINATED')
        self.contract_status = ContractStatus.objects.get_or_create(token=active_contract, defaults={'name': 'Actiu'})[0]

        self.pending = ReadingBatchStatus.objects.create(token='SNAP-PENDING', name='Pendent')
        self.processing = status_for(ReadingBatchStatus, 'reading_batch_processing_token', 'SNAP-PROCESSING')
        self.finish = status_for(ReadingBatchStatus, 'batch_status_finish_token', 'SNAP-FINISH')
        self.billed = status_for(ReadingBatchStatus, 'reading_batch_billed_token', 'SNAP-BILLED')

        meter_status = MeterStatus.objects.get_or_create(token='SNAP-METER-OK', defaults={'name': 'Actiu'})[0]
        sp_status = SupplyPointStatus.objects.get_or_create(token='SNAP-SP', defaults={'name': 'Actiu'})[0]
        self.meter = Meter.objects.create(code='SNAP-METER', status=meter_status)
        self.supply_point = SupplyPoint.objects.create(token='SNAP-SP', meter=self.meter, status=sp_status)
        self.add_contract('SNAP-C1')

        self.batch = ReadingBatch.objects.create(name='Lot snapshot', status=self.pending)
        self.batch.fix_meters.set([self.meter])

    def add_contract(self, token):
        contract = Contract.objects.create(token=token, status=self.contract_status, is_active=True)
        contract.supply_points.add(self.supply_point)
        return contract

    def list_row(self):
        # Els comptadors en viu es cachegen 180 s per conjunt de rutes/comptadors.
        cache.clear()
        batch = ReadingBatch.objects.get(pk=self.batch.pk)
        return ReadingBatchMinimalSerializer([batch], many=True).data[0]

    def set_status(self, status):
        self.batch.status = status
        self.batch.save()
        self.batch.refresh_from_db()

    def test_lot_obert_calcula_en_viu(self):
        self.assertIsNone(self.batch.metrics_snapshot)
        self.assertEqual(self.list_row()['num_contracts'], 1)

        self.add_contract('SNAP-C2')

        row = self.list_row()
        self.assertEqual(row['num_contracts'], 2)
        self.assertIsNone(row['metrics_frozen_at'])

    def test_en_tancar_el_lot_es_fixen_els_comptadors(self):
        self.set_status(self.finish)

        snapshot = self.batch.metrics_snapshot
        self.assertEqual(snapshot['num_contracts'], 1)
        self.assertEqual(snapshot['num_supplies'], 1)
        self.assertEqual(snapshot['summary']['num_contracts'], 1)
        self.assertIn('frozen_at', snapshot)

        self.add_contract('SNAP-C2')

        row = self.list_row()
        self.assertEqual(row['num_contracts'], 1)
        self.assertEqual(row['num_supplies'], 1)
        self.assertIsNotNone(row['metrics_frozen_at'])
        detail = ReadingBatchSerializer(ReadingBatch.objects.get(pk=self.batch.pk)).data
        self.assertEqual(detail['num_supplies'], 1)
        self.assertIsNotNone(detail['metrics_frozen_at'])

    def test_passar_a_facturat_conserva_la_foto_del_tancament(self):
        self.set_status(self.finish)
        frozen_at = self.batch.metrics_snapshot['frozen_at']
        self.add_contract('SNAP-C2')

        self.set_status(self.billed)

        self.assertEqual(self.batch.metrics_snapshot['num_contracts'], 1)
        self.assertEqual(self.batch.metrics_snapshot['frozen_at'], frozen_at)

    def test_reobrir_el_lot_esborra_la_foto(self):
        self.set_status(self.finish)
        self.add_contract('SNAP-C2')

        self.set_status(self.processing)

        self.assertIsNone(self.batch.metrics_snapshot)
        self.assertEqual(self.list_row()['num_contracts'], 2)

    def test_lot_facturat_amb_update_sense_foto_es_fixa_en_sincronitzar(self):
        # Els lots passen a facturat amb queryset.update(), que no dispara post_save.
        ReadingBatch.objects.filter(pk=self.batch.pk).update(status=self.billed)
        batch = ReadingBatch.objects.get(pk=self.batch.pk)
        self.assertIsNone(batch.metrics_snapshot)

        sync_reading_batch_snapshot(batch)

        batch.refresh_from_db()
        self.assertEqual(batch.metrics_snapshot['num_contracts'], 1)

    def test_si_no_es_pot_calcular_la_foto_el_canvi_d_estat_es_desa(self):
        ConfigProject.objects.filter(token='contract_active_token').delete()
        reading_batch_list_config_tokens.cache_clear()

        with self.assertLogs('billing.utils.metrics_snapshot_service', level='ERROR'):
            self.set_status(self.finish)

        self.assertEqual(self.batch.status, self.finish)
        self.assertIsNone(self.batch.metrics_snapshot)


class BillingMetricsSnapshotTests(TestCase):
    """En processar una facturació es fixa el resum per ruta que mostra BillingRoutesView."""

    def setUp(self):
        self.pending = status_for(BillingStatus, 'billing_batch_pending', 'SNAP-B-PENDING')
        self.processed = status_for(BillingStatus, 'billing_batch_processed', 'SNAP-B-PROCESSED')
        self.processing_documents = status_for(BillingStatus, 'billing_batch_processing_documents', 'SNAP-B-DOCS')

        # Facturació de lectures excloses: el resum és el recompte de lectures, sense rutes.
        self.billing = Billing.objects.create(name='Facturació snapshot', status=self.pending, is_excluded=True)
        self.add_reading()

        user = User.objects.create_superuser('snapshot-admin', 'snapshot@example.com', 'x')
        self.client = APIClient()
        self.client.force_authenticate(user)

    def add_reading(self):
        Reading.objects.create(billing=self.billing, reading_date=date(2026, 1, 1), reading_value=10)

    def set_status(self, status):
        self.billing.status = status
        self.billing.save()
        self.billing.refresh_from_db()

    def routes(self):
        response = self.client.get(reverse('billing-routes'), {'id': self.billing.id})
        self.assertEqual(response.status_code, 200, response.content)
        return response.json()

    def test_facturacio_oberta_calcula_en_viu(self):
        self.add_reading()

        self.assertIsNone(self.billing.metrics_snapshot)
        self.assertEqual(self.routes()[0]['processed_readings'], 2)

    def test_en_processar_es_fixa_el_resum(self):
        self.set_status(self.processed)
        self.add_reading()

        self.assertEqual(self.routes()[0]['processed_readings'], 1)
        response = self.client.get(reverse('billing-detail', args=[self.billing.id]))
        self.assertEqual(response.status_code, 200, response.content)
        self.assertIsNotNone(response.json()['metrics_frozen_at'])
        self.assertNotIn('metrics_snapshot', response.json())

    def test_generar_documents_conserva_el_resum(self):
        self.set_status(self.processed)
        self.add_reading()

        self.set_status(self.processing_documents)
        self.set_status(self.processed)

        self.assertEqual(self.routes()[0]['processed_readings'], 1)

    def test_tornar_a_pendent_esborra_el_resum(self):
        self.set_status(self.processed)
        self.add_reading()

        self.set_status(self.pending)

        self.assertIsNone(self.billing.metrics_snapshot)
        self.assertEqual(self.routes()[0]['processed_readings'], 2)
