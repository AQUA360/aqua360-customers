from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from billing.models import Invoice, Payment, PaymentStatus
from contract.models import Contract
from contract.utils.contract_list_queryset import contract_debt_amounts_by_contract_id
from coredata.models import ConfigProject
from pricing.models import ProductOrigin
from service.models import Exploitation
from service.serializers.exploitation_serializer import ExploitationSerializer
from statistics.models import BillingConsumption
from statistics.utils.billing_amount_average import (
    TotalAmountAvgCache,
    get_total_amount_avg,
    is_high_amount_for_period,
)
from statistics.utils.incasol import resolve_incasol_num


class IncasolNumResolutionTests(TestCase):
    """`resolve_incasol_num` ha de prioritzar el número de l'explotació i caure al
    ConfigProject global quan l'explotació no en té, perquè les instal·lacions que
    encara no han omplert el camp no canviïn de comportament."""

    def setUp(self):
        self.exploitation = Exploitation.objects.create(name='Explotació A', token='A')

    def test_global_config_when_no_exploitation(self):
        ConfigProject.objects.create(token='incasol_num', name='Núm concert INCASOL', value='0000')
        self.assertEqual(resolve_incasol_num(None), '0000')

    def test_exploitation_value_wins(self):
        ConfigProject.objects.create(token='incasol_num', name='Núm concert INCASOL', value='0000')
        self.exploitation.incasol_num = '1234'
        self.exploitation.save()
        self.assertEqual(resolve_incasol_num(self.exploitation.id), '1234')

    def test_empty_exploitation_value_falls_back_to_global(self):
        ConfigProject.objects.create(token='incasol_num', name='Núm concert INCASOL', value='0000')
        self.exploitation.incasol_num = ''
        self.exploitation.save()
        self.assertEqual(resolve_incasol_num(self.exploitation.id), '0000')

    def test_unknown_exploitation_falls_back_to_global(self):
        ConfigProject.objects.create(token='incasol_num', name='Núm concert INCASOL', value='0000')
        self.assertEqual(resolve_incasol_num(999999), '0000')

    def test_default_when_nothing_configured(self):
        self.assertEqual(resolve_incasol_num(self.exploitation.id), '')

    def test_serializer_reads_and_writes_the_field(self):
        serializer = ExploitationSerializer(
            instance=self.exploitation,
            data={'incasol_num': '4321'},
            partial=True,
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        serializer.save()
        self.exploitation.refresh_from_db()
        self.assertEqual(self.exploitation.incasol_num, '4321')
        self.assertEqual(
            ExploitationSerializer(self.exploitation).data['incasol_num'], '4321'
        )

    def test_serializer_can_clear_the_field(self):
        self.exploitation.incasol_num = '4321'
        self.exploitation.save()
        serializer = ExploitationSerializer(
            instance=self.exploitation,
            data={'incasol_num': ''},
            partial=True,
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        serializer.save()
        self.exploitation.refresh_from_db()
        self.assertEqual(self.exploitation.incasol_num, '')


class HighAmountWaterInvoicesTests(TestCase):
    """L'avís d'import alt només compara amb factures d'aigua (no les d'alta ni altres)."""

    @classmethod
    def setUpTestData(cls):
        ConfigProject.objects.update_or_create(token='origin_reading_token', defaults={'value': 'aigua'})
        cls.water, _ = ProductOrigin.objects.get_or_create(token='aigua', defaults={'name': 'Aigua'})
        cls.other, _ = ProductOrigin.objects.get_or_create(token='altres', defaults={'name': 'Altres'})
        cls.contract = Contract.objects.bulk_create([Contract(
            token='HA-NEW', registration_date=timezone.now().date(), is_active=True,
        )])[0]

    def _invoice(self, origin, total, year=None, month=None):
        invoice = Invoice.objects.bulk_create([Invoice(
            contract=self.contract, origin=origin, total_final=Decimal(total),
            billing_period_year=year, billing_period_month=month,
        )])[0]
        BillingConsumption.objects.create(
            invoice=invoice, contract=self.contract, year=year, month=month, total_amount=Decimal(total),
        )
        return invoice

    def test_new_contract_with_only_registration_invoice_has_no_average(self):
        Invoice.objects.bulk_create([Invoice(contract=self.contract, origin=self.other, total_final=Decimal('11.11'))])

        self.assertIsNone(get_total_amount_avg([self.contract]))
        self.assertFalse(is_high_amount_for_period(Decimal('40'), [self.contract], 2026, 10))
        cache = TotalAmountAvgCache([self.contract.id])
        self.assertFalse(cache.is_high_amount(Decimal('40'), self.contract.id, 2026, 10))

    def test_average_ignores_non_water_invoices(self):
        self._invoice(self.other, '11.11', 2026, 8)
        self._invoice(self.water, '30', 2026, 9)

        self.assertEqual(get_total_amount_avg([self.contract]), 30.0)
        self.assertFalse(is_high_amount_for_period(Decimal('40'), [self.contract], 2026, 10))
        self.assertTrue(is_high_amount_for_period(Decimal('50'), [self.contract], 2026, 10))
        cache = TotalAmountAvgCache([self.contract.id])
        self.assertEqual(cache.total_avg(self.contract.id), 30.0)
        self.assertFalse(cache.is_high_amount(Decimal('40'), self.contract.id, 2026, 10))
        self.assertTrue(cache.is_high_amount(Decimal('50'), self.contract.id, 2026, 10))

    def test_seasonal_average_ignores_non_water_invoices(self):
        self._invoice(self.water, '100', 2025, 1)
        self._invoice(self.water, '20', 2025, 10)
        self._invoice(self.other, '5', 2025, 10)

        # Mitjana completa 60 i la del període (octubre 2025) 20: 95 supera 1,5 vegades totes dues.
        self.assertTrue(is_high_amount_for_period(Decimal('95'), [self.contract], 2026, 10))
        cache = TotalAmountAvgCache([self.contract.id])
        self.assertEqual(cache.seasonal_avg(self.contract.id, 2026, 10), 20.0)


class ContractDebtViewTests(TestCase):
    """vw_contract_debt: els pagaments "En saldo" estan cobrats amb el saldo i no són deute."""

    @classmethod
    def setUpTestData(cls):
        cls.contract = Contract.objects.bulk_create([Contract(
            token='DEBT-VIEW', registration_date=timezone.now().date(), is_active=True,
        )])[0]
        cls.invoice = Invoice.objects.bulk_create([Invoice(contract=cls.contract, total_final=Decimal('50'))])[0]

    def _payment(self, status_token, amount):
        status, _ = PaymentStatus.objects.get_or_create(token=status_token, defaults={'name': status_token})
        # bulk_create: sense els signals de Payment, que necessiten tot el ConfigProject.
        Payment.objects.bulk_create([Payment(invoice=self.invoice, status=status, amount=Decimal(amount))])

    def _debt(self):
        return contract_debt_amounts_by_contract_id([self.contract.id]).get(self.contract.id, Decimal('0'))

    def test_balance_payment_is_not_debt(self):
        self._payment('5', '12.02')

        self.assertEqual(self._debt(), Decimal('0'))

    def test_balance_payment_does_not_hide_unpaid_payments(self):
        self._payment('5', '12.02')
        self._payment('-1', '30.00')
        self._payment('0', '20.00')

        self.assertEqual(self._debt(), Decimal('30.00'))


class DatedUseTypeTests(TestCase):
    """Tipus d'ús del contracte en el moment de generar la factura (historial ContractLog)."""

    @classmethod
    def setUpTestData(cls):
        from contract.models import ContractLog, ContractUseType

        cls.domestic = ContractUseType.objects.create(token='T-DOM', name='Tipus A')
        cls.commercial = ContractUseType.objects.create(token='T-COM', name='Tipus B')
        cls.industrial = ContractUseType.objects.create(token='T-IND', name='Tipus C')
        now = timezone.now()
        cls.t0 = now - timezone.timedelta(days=30)
        cls.t1 = now - timezone.timedelta(days=20)
        cls.t2 = now - timezone.timedelta(days=10)

        # Contracte amb historial: A -> B (t1) -> C (t2). Ara és C.
        cls.changed, cls.unchanged, cls.renamed = Contract.objects.bulk_create([
            Contract(token='DUT-1', use_type=cls.industrial, is_active=True),
            Contract(token='DUT-2', use_type=cls.domestic, is_active=True),
            Contract(token='DUT-3', use_type=cls.domestic, is_active=True),
        ])
        logs = ContractLog.objects.bulk_create([
            ContractLog(contract=cls.changed, field_name='use_type', old_value='Tipus A', new_value='Tipus B'),
            ContractLog(contract=cls.changed, field_name='use_type', old_value='Tipus B', new_value='Tipus C'),
            # Nom que ja no existeix: es fa servir el tipus d'ús actual.
            ContractLog(contract=cls.renamed, field_name='use_type', old_value='Nom antic', new_value='Tipus A'),
        ])
        ContractLog.objects.filter(id=logs[0].id).update(created_at=cls.t1)
        ContractLog.objects.filter(id=logs[1].id).update(created_at=cls.t2)
        ContractLog.objects.filter(id=logs[2].id).update(created_at=cls.t1)

        def invoice(contract, created_at):
            inv = Invoice.objects.bulk_create([Invoice(contract=contract)])[0]
            Invoice.objects.filter(id=inv.id).update(created_at=created_at)
            inv.refresh_from_db()
            return inv

        cls.expected = {}
        for contract, created_at, use_type in [
            (cls.changed, cls.t0, cls.domestic),      # abans del primer canvi: old_value del primer
            (cls.changed, cls.t1, cls.commercial),    # mateix instant que el canvi: new_value
            (cls.changed, now - timezone.timedelta(days=15), cls.commercial),
            (cls.changed, now, cls.industrial),
            (cls.unchanged, cls.t0, cls.domestic),    # sense historial: actual
            (cls.renamed, cls.t0, cls.domestic),      # nom inexistent: actual
        ]:
            cls.expected[invoice(contract, created_at).id] = use_type

        # Factura sense contracte, només amb la baixa: es fa servir el contracte de la baixa.
        from contract.models import ContractTerminationRequest
        termination = ContractTerminationRequest.objects.bulk_create([ContractTerminationRequest(contract=cls.changed)])[0]
        inv = Invoice.objects.bulk_create([Invoice(contract_termination=termination)])[0]
        Invoice.objects.filter(id=inv.id).update(created_at=cls.t0)
        cls.expected[inv.id] = cls.domestic

    def test_sql_annotation(self):
        from statistics.utils.dated_use_type import annotate_dated_use_type

        rows = annotate_dated_use_type(
            Invoice.objects.filter(id__in=self.expected), invoice_prefix='', name=True,
        ).values('id', 'dated_use_type_id', 'dated_use_type_name')
        self.assertEqual(len(rows), len(self.expected))
        for row in rows:
            self.assertEqual(row['dated_use_type_id'], self.expected[row['id']].id)
            self.assertEqual(row['dated_use_type_name'], self.expected[row['id']].name)

    def test_python_resolution_matches(self):
        from statistics.utils.dated_use_type import resolve_dated_use_types

        invoices = Invoice.objects.filter(id__in=self.expected).select_related(
            'contract__use_type', 'contract_termination__contract__use_type',
        )
        resolved = resolve_dated_use_types(
            (inv, inv.contract or (inv.contract_termination.contract if inv.contract_termination else None))
            for inv in invoices
        )
        self.assertEqual(resolved, self.expected)
