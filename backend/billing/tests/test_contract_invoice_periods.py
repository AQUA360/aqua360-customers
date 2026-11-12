from datetime import date

from django.test import TestCase

from billing.filter.invoice_filter import InvoiceFilter
from billing.models import (
    Biller, Billing, Invoice, InvoiceStatus, InvoiceType, Payment, PaymentMovement, PaymentStatus, Reading,
)
from billing.serializers.invoice_serializer import InvoiceMinimalSerializer
from billing.utils.invoice_list_queryset import invoice_list_queryset
from billing.utils.invoice_period import (
    EXPIRED, NO_PERIOD, PAID, PENDING, SETTLED, invoice_billing_cycles, invoice_payment_states,
    invoice_payment_summaries, invoice_relations_map, period_year_counts,
)
from contract.models import Contract, ContractRequest
from coredata.models import ConfigProject
from pricing.models import ProductOrigin


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
            ('origin_reading_token', 'aigua'),
        ):
            ConfigProject.objects.update_or_create(token=token, defaults={'value': value})
        cls.invoice_type = InvoiceType.objects.create(token='INVOICE', name='Factura')
        cls.status = InvoiceStatus.objects.create(token='PENDING', name='Pendent', position=1)
        cls.contract_request = ContractRequest.objects.create(token='SOL-1')
        cls.contract = Contract.objects.create(token='CON-1', contract_request=cls.contract_request)
        cls.other_contract = Contract.objects.create(token='CON-2')

    def invoice(self, token, **kwargs):
        kwargs.setdefault('contract', self.contract)
        kwargs.setdefault('status', self.status)
        return Invoice.objects.create(token=token, type=self.invoice_type, **kwargs)

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


class BillingCycleTests(ContractInvoicePeriodsBase):
    """El període és el cicle del facturador, no el mes d'emissió."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.water = ProductOrigin.objects.create(token='aigua', name='Aigua')
        cls.quarterly = Billing.objects.create(
            token='FAC-T', biller=Biller.objects.create(name='Trimestral', period_type='trimestral', initial_month='jan'))
        cls.from_november = Billing.objects.create(
            token='FAC-N', biller=Biller.objects.create(name='Des de novembre', period_type='trimestral', initial_month='nov'))

    def consumption(self, token, issue, period=None, billing=None, readings=(), **kwargs):
        period = period or (issue.year, issue.month)
        invoice = self.invoice(token, origin=self.water, billing=billing or self.quarterly, issue_date=issue,
                               billing_period_year=period[0], billing_period_month=period[1], **kwargs)
        invoice.readings.set(readings)
        return invoice

    def reading(self, day, previous_day=None):
        previous = Reading.objects.create(reading_date=previous_day) if previous_day else None
        return Reading.objects.create(reading_date=day, previous_reading=previous)

    def cycles(self):
        cycles = invoice_billing_cycles(Invoice.objects.filter(contract=self.contract))
        return {
            invoice.token: cycles[invoice.id] and (
                cycles[invoice.id]['start_year'], cycles[invoice.id]['start_month'],
                cycles[invoice.id]['end_year'], cycles[invoice.id]['end_month'])
            for invoice in Invoice.objects.filter(contract=self.contract)
        }

    def test_issued_after_the_quarter_belongs_to_the_quarter_of_its_readings(self):
        self.consumption('OCT', date(2026, 10, 7), readings=[self.reading(date(2026, 9, 10), date(2026, 6, 11))])

        self.assertEqual(self.cycles()['OCT'], (2026, 7, 2026, 9))

    def test_without_readings_the_quarter_ends_the_month_before_billing(self):
        self.consumption('JAN', date(2026, 1, 2))

        self.assertEqual(self.cycles()['JAN'], (2025, 10, 2025, 12))

    def test_cycle_follows_the_initial_month_of_the_biller(self):
        self.consumption('NOV', date(2026, 2, 3), billing=self.from_november,
                         readings=[self.reading(date(2026, 1, 20), date(2025, 10, 20))])

        self.assertEqual(self.cycles()['NOV'], (2025, 11, 2026, 1))
        self.assertEqual(period_year_counts(self.filtered({})), [{'year': 2026, 'count': 1}])

    def test_one_off_invoice_stays_in_its_month(self):
        self.invoice('ALTA', issue_date=date(2026, 5, 4), billing_period_year=2026, billing_period_month=5)

        self.assertEqual(self.cycles()['ALTA'], (2026, 5, 2026, 5))

    def test_reading_shared_by_several_periods_uses_the_stored_period(self):
        shared = self.reading(date(2021, 12, 20), date(2021, 9, 20))
        self.consumption('OLD-1', date(2022, 3, 1), period=(2019, 5), readings=[shared])
        self.consumption('OLD-2', date(2022, 3, 1), period=(2020, 8), readings=[shared])

        cycles = self.cycles()

        self.assertEqual(cycles['OLD-1'], (2019, 4, 2019, 6))
        self.assertEqual(cycles['OLD-2'], (2020, 7, 2020, 9))

    def test_credit_note_takes_the_cycle_of_the_cancelled_invoice(self):
        reading = self.reading(date(2025, 12, 11), date(2025, 9, 11))
        self.consumption('ABONAMENT', date(2026, 5, 20), readings=[reading])
        self.consumption('ORIGINAL', date(2026, 1, 2), readings=[reading], return_token='ABONAMENT')

        cycles = self.cycles()

        self.assertEqual(cycles['ORIGINAL'], (2025, 10, 2025, 12))
        self.assertEqual(cycles['ABONAMENT'], (2025, 10, 2025, 12))


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

    def test_inactive_related_invoice_is_not_linked(self):
        self.invoice('ABONAMENT', is_active=False)
        self.invoice('ORIGINAL', return_token='ABONAMENT')

        rows = self.serialize()

        self.assertNotIn('rectifying_invoice', rows['ORIGINAL'])

    def test_duplicated_token_of_another_contract_is_not_linked(self):
        self.invoice('ABONAMENT', contract=self.other_contract)
        self.invoice('ORIGINAL', return_token='ABONAMENT')
        self.invoice('REFETA', contract=self.other_contract, refactored_token='ORIGINAL')

        rows = self.serialize()

        self.assertNotIn('rectifying_invoice', rows['ORIGINAL'])
        self.assertNotIn('refactor_invoice', rows['ORIGINAL'])

    def test_registration_request_invoice_is_linked_to_its_credit_note(self):
        credit = self.invoice('ABONAMENT', contract=None, contract_request=self.contract_request)
        original = self.invoice('ORIGINAL', contract=None, contract_request=self.contract_request,
                                return_token='ABONAMENT')

        relations = invoice_relations_map([original, credit], 'INVOICE')

        self.assertEqual(relations[original.id]['rectifying_invoice']['id'], credit.id)
        self.assertEqual(relations[credit.id]['rectified_invoice']['id'], original.id)


class ContractInvoicesCountTests(ContractInvoicePeriodsBase):
    """El total de la pestanya té el mateix abast que les pestanyes d'any (sense excloses)."""

    def test_count_skips_excluded_invoices(self):
        from contract.serializers.contract_serializer import ContractSerializer
        self.invoice('VISIBLE', issue_date=date(2025, 1, 1))
        self.invoice('REQUEST', contract=None, contract_request=self.contract_request, issue_date=date(2025, 1, 1))
        self.invoice('EXCLUDED', issue_date=date(2025, 1, 1), is_excluded=True)

        count = ContractSerializer().get_invoices_count(self.contract)

        self.assertEqual(count, sum(row['count'] for row in period_year_counts(self.filtered({}))))
        self.assertEqual(count, 2)


class InvoicePaymentStateTests(ContractInvoicePeriodsBase):
    """Resum de cobrament de cada període: pagades, pendents i vençudes."""

    def test_states_by_status_and_due_date(self):
        ConfigProject.objects.update_or_create(token='invoice_status_dropped_token', defaults={'value': 'DROPPED'})
        statuses = {token: InvoiceStatus.objects.create(token=token, name=token)
                    for token in ('PAID', 'EXPIRED', 'CANCELLED', 'DROPPED', 'SENT')}
        today = date(2026, 6, 1)
        invoices = {
            'paid': self.invoice('PAID'),
            'expired': self.invoice('EXPIRED'),
            'cancelled': self.invoice('CANCELLED'),
            'dropped': self.invoice('DROPPED'),
            'pending': self.invoice('SENT', due_date=date(2026, 6, 30)),
            'overdue': self.invoice('LATE', due_date=date(2026, 5, 1)),
        }
        # Sense passar pels senyals de canvi d'estat (necessiten més configuració)
        for key, status in (('paid', 'PAID'), ('expired', 'EXPIRED'), ('cancelled', 'CANCELLED'),
                            ('dropped', 'DROPPED'), ('pending', 'SENT'), ('overdue', 'SENT')):
            Invoice.objects.filter(id=invoices[key].id).update(status=statuses[status])

        states = invoice_payment_states(list(Invoice.objects.select_related('status')), today)

        self.assertEqual({key: states[invoice.id] for key, invoice in invoices.items()}, {
            'paid': PAID, 'expired': EXPIRED, 'cancelled': SETTLED, 'dropped': SETTLED,
            'pending': PENDING, 'overdue': EXPIRED,
        })


class InvoicePaymentSummaryTests(ContractInvoicePeriodsBase):
    """Columna «Estat de pagament»: estat del cobrament i retorns bancaris de cada factura."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        for token, value in (('payment_status_cancelled_token', 'P-CANCELLED'),
                             ('payment_status_returned_token', 'P-RETURNED')):
            ConfigProject.objects.update_or_create(token=token, defaults={'value': value})
        cls.payment_statuses = {
            token: PaymentStatus.objects.create(token=token, name=token.title(), color='#000')
            for token in ('P-PENDING', 'P-PAID', 'P-RETURNED', 'P-CANCELLED')
        }

    def payment(self, invoice, status, **kwargs):
        # bulk_create: sense els senyals de canvi d'estat del pagament (necessiten més configuració)
        return Payment.objects.bulk_create([
            Payment(invoice=invoice, status=self.payment_statuses[status], **kwargs)])[0]

    def returned(self, payment, movement_date, **kwargs):
        PaymentMovement.objects.bulk_create([PaymentMovement(
            payment=payment, current_status=self.payment_statuses['P-RETURNED'],
            movement_date=movement_date, is_positive=False, **kwargs)])

    def summary(self, invoice):
        return invoice_payment_summaries([invoice])[invoice.id]

    def test_returned_and_paid_again_keeps_the_return(self):
        invoice = self.invoice('RETURNED-PAID')
        payment = self.payment(invoice, 'P-PAID')
        self.returned(payment, date(2026, 3, 5))
        self.returned(payment, date(2026, 4, 5))

        summary = self.summary(invoice)

        self.assertEqual(summary['payment_status']['token'], 'P-PAID')
        self.assertEqual(summary['returned_at'], date(2026, 4, 5))
        self.assertEqual(summary['returned_count'], 2)

    def test_returned_before_the_due_date(self):
        invoice = self.invoice('RETURNED', due_date=date(2099, 1, 1))
        self.returned(self.payment(invoice, 'P-RETURNED'), date(2026, 3, 5))

        summary = self.summary(invoice)

        self.assertEqual(summary['payment_status']['token'], 'P-RETURNED')
        self.assertEqual(summary['returned_count'], 1)

    def test_cancelled_return_and_inactive_payment_do_not_count(self):
        invoice = self.invoice('CANCELLED-RETURN')
        payment = self.payment(invoice, 'P-PAID')
        self.returned(payment, date(2026, 3, 5), is_active=False)
        self.returned(self.payment(invoice, 'P-PENDING', is_active=False), date(2026, 3, 6))

        summary = self.summary(invoice)

        self.assertEqual(summary['payment_status']['token'], 'P-PAID')
        self.assertIsNone(summary['returned_at'])
        self.assertEqual(summary['returned_count'], 0)

    def test_cancelled_payment_is_skipped_unless_it_is_the_only_one(self):
        replaced = self.invoice('REPLACED')
        self.payment(replaced, 'P-PENDING')
        self.payment(replaced, 'P-CANCELLED')
        only_cancelled = self.invoice('ONLY-CANCELLED')
        self.payment(only_cancelled, 'P-CANCELLED')
        without_payments = self.invoice('NO-PAYMENTS')

        summaries = invoice_payment_summaries([replaced, only_cancelled, without_payments])

        self.assertEqual(summaries[replaced.id]['payment_status']['token'], 'P-PENDING')
        self.assertEqual(summaries[only_cancelled.id]['payment_status']['token'], 'P-CANCELLED')
        self.assertIsNone(summaries[without_payments.id]['payment_status'])

    def test_two_queries_whatever_the_number_of_invoices(self):
        invoices = [self.invoice(f'MANY-{index}') for index in range(5)]
        for invoice in invoices:
            self.returned(self.payment(invoice, 'P-PAID'), date(2026, 3, 5))

        # Configuració, cobraments i retorns
        with self.assertNumQueries(3):
            invoice_payment_summaries(invoices)

    def test_invoice_lists_send_the_summary_only_when_asked(self):
        invoice = self.invoice('LISTED')
        self.returned(self.payment(invoice, 'P-PAID'), date(2026, 3, 5))
        queryset = invoice_list_queryset().filter(id=invoice.id)

        with_summary = InvoiceMinimalSerializer(queryset, many=True, context={'with_payment_summary': True}).data[0]
        without_summary = InvoiceMinimalSerializer(queryset, many=True).data[0]

        self.assertEqual(with_summary['payment_summary']['payment_status']['token'], 'P-PAID')
        self.assertEqual(with_summary['payment_summary']['returned_at'], date(2026, 3, 5))
        self.assertNotIn('payment_summary', without_summary)
