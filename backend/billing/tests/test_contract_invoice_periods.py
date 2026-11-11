from datetime import date

from django.test import TestCase

from billing.filter.invoice_filter import InvoiceFilter
from billing.models import Invoice, InvoiceStatus, InvoiceType
from billing.serializers.invoice_serializer import InvoiceMinimalSerializer
from billing.utils.invoice_list_queryset import invoice_list_queryset
from billing.utils.invoice_period import NO_PERIOD, invoice_relations_map, period_year_counts
from contract.models import Contract, ContractRequest
from coredata.models import ConfigProject


class ContractInvoicePeriodsBase(TestCase):

    @classmethod
    def setUpTestData(cls):
        for token, value in (
            ('invoice_type_invoice_token', 'INVOICE'),
            ('invoice_type_budget_token', 'BUDGET'),
            ('invoice_status_paid_token', 'PAID'),
            ('invoice_status_payoff_token', 'PAYOFF'),
            ('invoice_status_cancelled_token', 'CANCELLED'),
            ('invoice_status_expired_token', 'EXPIRED'),
            ('debt_vulnerable_token', 'VULNERABLE'),
            ('contract_terminated_status', 'TERMINATED'),
        ):
            ConfigProject.objects.update_or_create(token=token, defaults={'value': value})
        cls.invoice_type = InvoiceType.objects.create(token='INVOICE', name='Factura')
        cls.status = InvoiceStatus.objects.create(token='PENDING', name='Pendent', position=1)
        cls.contract_request = ContractRequest.objects.create(token='SOL-1')
        cls.contract = Contract.objects.create(token='CON-1', contract_request=cls.contract_request)
        cls.other_contract = Contract.objects.create(token='CON-2')

    def invoice(self, token, **kwargs):
        kwargs.setdefault('contract', self.contract)
        return Invoice.objects.create(token=token, type=self.invoice_type, status=self.status, **kwargs)

    def filtered(self, params):
        params = {'contract_with_request': str(self.contract.id), 'is_invoice': 'true', **params}
        return InvoiceFilter(params, queryset=invoice_list_queryset().filter(is_excluded=False)).qs


class ContractInvoicePeriodYearTests(ContractInvoicePeriodsBase):
    """L'any és el del període facturat i, si no n'hi ha, el de la data d'emissió."""

    def setUp(self):
        self.invoice('PERIOD-2024', billing_period_year=2024, billing_period_month=12, issue_date=date(2025, 1, 10))
        self.invoice('ISSUE-2025', issue_date=date(2025, 3, 1))
        self.invoice('NO-DATE')
        self.invoice('REQUEST', contract=None, contract_request=self.contract_request, issue_date=date(2023, 5, 1))
        self.invoice('OTHER', contract=self.other_contract, issue_date=date(2025, 3, 1))
        self.invoice('EXCLUDED', issue_date=date(2025, 4, 1), is_excluded=True)

    def tokens(self, year):
        return sorted(self.filtered({'period_year': year}).values_list('token', flat=True))

    def test_year_follows_billed_period_before_issue_date(self):
        self.assertEqual(self.tokens('2024'), ['PERIOD-2024'])
        self.assertEqual(self.tokens('2025'), ['ISSUE-2025'])

    def test_invoices_without_any_date_go_to_no_period(self):
        self.assertEqual(self.tokens(NO_PERIOD), ['NO-DATE'])

    def test_includes_invoices_of_the_registration_request(self):
        self.assertEqual(self.tokens('2023'), ['REQUEST'])

    def test_invalid_year_returns_nothing(self):
        self.assertEqual(self.tokens('abc'), [])

    def test_year_counts_newest_first_and_no_period_last(self):
        counts = period_year_counts(self.filtered({}))

        self.assertEqual(counts, [
            {'year': 2025, 'count': 1},
            {'year': 2024, 'count': 1},
            {'year': 2023, 'count': 1},
            {'year': NO_PERIOD, 'count': 1},
        ])


class InvoiceListRelationsTests(ContractInvoicePeriodsBase):
    """La llista de factures indica abonaments i refacturacions en les dues direccions."""

    def serialize(self):
        queryset = invoice_list_queryset().filter(contract=self.contract).order_by('token')
        data = InvoiceMinimalSerializer(queryset, many=True).data
        return {row['token']: row for row in data}

    def test_credit_note_and_rebilling_are_linked_both_ways(self):
        credit = self.invoice('ABONAMENT', serie_final='R-1')
        original = self.invoice('ORIGINAL', serie_final='F-1', return_token='ABONAMENT')
        rebilled = self.invoice('REFETA', serie_final='F-2', refactored_token='ORIGINAL')

        rows = self.serialize()

        self.assertEqual(rows['ORIGINAL']['rectifying_invoice']['id'], credit.id)
        self.assertEqual(rows['ORIGINAL']['refactor_invoice']['id'], rebilled.id)
        self.assertEqual(rows['ABONAMENT']['rectified_invoice']['id'], original.id)
        self.assertEqual(rows['REFETA']['refactored_invoice']['serie_final'], 'F-1')
        self.assertNotIn('rectifying_invoice', rows['REFETA'])

    def test_relations_take_two_queries_whatever_the_number_of_invoices(self):
        for index in range(5):
            self.invoice(f'B{index}', return_token=f'C{index}')
            self.invoice(f'C{index}', refactored_token=f'B{index}')
        invoices = list(Invoice.objects.filter(contract=self.contract))

        with self.assertNumQueries(2):
            relations = invoice_relations_map(invoices, 'INVOICE')

        self.assertEqual(sum(len(relation) for relation in relations.values()), 20)
