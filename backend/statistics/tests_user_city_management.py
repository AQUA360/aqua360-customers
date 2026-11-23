import datetime

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from billing.models import (
    Invoice, InvoiceLog, Payment, PaymentMovement, PaymentRemittance, PaymentStatus,
)
from contract.models import (
    Contract, ContractDataChange, ContractLog, ContractRequest, ContractRequestStatus,
    ContractTerminationRequest, ContractTerminationType, PaymentType,
)
from coredata.models import Address, City, PersonBank
from logger.models import LogContractRequestStatus, LogInvoiceDataChange
from service.models import SupplyPoint
from statistics.utils.daily_activity_service import build_daily_activity
from statistics.utils.report_user_city_management_service import (
    MASS_MODIFICATION_THRESHOLD,
    METRIC_BANK_ACCOUNT_CHANGE,
    METRIC_CHANGE_OF_NAME,
    METRIC_INVOICE_CREATED,
    METRIC_INVOICE_MASS_MODIFICATION,
    METRIC_INVOICE_MODIFICATION,
    METRIC_MANUAL_COLLECTION,
    METRIC_NEW_CONTRACT_REQUEST,
    METRIC_PAYMENT_TYPE_CHANGE,
    METRIC_REMITTANCE_COLLECTION,
    build_workbook,
    compute_user_city_management,
)

D = datetime.date
DATE_FROM, DATE_TO = D(2026, 3, 1), D(2026, 3, 31)


def at(day, hour=10, minute=0, second=0):
    return timezone.make_aware(datetime.datetime(2026, 3, day, hour, minute, second))


OUTSIDE = timezone.make_aware(datetime.datetime(2026, 4, 2, 10, 0))


class UserCityManagementTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create(username='oficina', first_name='Anna', last_name='Oficina')
        cls.other = User.objects.create(username='altra')
        cls.technical = User.objects.create(username='customers')

        city_a = City.objects.create(token='A', name='Municipi A')
        city_b = City.objects.create(token='B', name='Municipi B')
        sp_a = SupplyPoint.objects.bulk_create([SupplyPoint(address=Address.objects.create(city=city_a))])[0]
        sp_b = SupplyPoint.objects.bulk_create([SupplyPoint(address=Address.objects.create(city=city_b))])[0]
        cls.sp_a, cls.sp_b = sp_a, sp_b
        cls.contract_a, cls.contract_b = Contract.objects.bulk_create([
            Contract(token='CA', supply_point_default=sp_a),
            Contract(token='CB', supply_point_default=sp_b),
        ])
        cls.status_draft = ContractRequestStatus.objects.create(name='Esborrany')
        cls.paid = PaymentStatus.objects.create(token='0', name='Pagat')
        cls.pending = PaymentStatus.objects.create(token='1', name='Pendent')

    def _set(self, model, obj, field, value):
        model.objects.filter(id=obj.id).update(**{field: value})

    def _request(self, user, created_at, supply_point, is_change_of_name=False):
        request = ContractRequest.objects.bulk_create([ContractRequest(
            supply_point_default=supply_point, is_change_of_name=is_change_of_name,
        )])[0]
        self._set(ContractRequest, request, 'created_at', created_at)
        log = LogContractRequestStatus.objects.create(
            object=request, previous_status=None, current_status=self.status_draft, user=user,
        )
        self._set(LogContractRequestStatus, log, 'timestamp', created_at)
        return request

    def _compute(self):
        users, metrics, payments = compute_user_city_management(DATE_FROM, DATE_TO)
        return users, metrics, payments

    def test_contract_requests_split_into_change_of_name_and_new(self):
        self._request(self.user, at(5), self.sp_a)
        self._request(self.user, at(6), self.sp_a, is_change_of_name=True)
        linked = self._request(self.user, at(7), self.sp_b)
        termination_type = ContractTerminationType.objects.create(is_change_of_name=True)
        termination = ContractTerminationRequest.objects.bulk_create([
            ContractTerminationRequest(contract=self.contract_b, type=termination_type),
        ])[0]
        linked.contract_termination_requests.add(termination)
        # Fora del període, i una creada pel compte tècnic: no compten.
        self._request(self.user, OUTSIDE, self.sp_a)
        self._request(self.technical, at(8), self.sp_a)

        users, metrics, _payments = self._compute()

        self.assertNotIn(self.technical.id, users)
        self.assertEqual(metrics['Municipi A'][self.user.id][METRIC_NEW_CONTRACT_REQUEST], 1)
        self.assertEqual(metrics['Municipi A'][self.user.id][METRIC_CHANGE_OF_NAME], 1)
        self.assertEqual(metrics['Municipi B'][self.user.id][METRIC_CHANGE_OF_NAME], 1)

    def test_holder_edit_counts_as_change_of_name_but_not_contract_creation(self):
        edit = ContractLog.objects.create(contract=self.contract_a, field_name='holder',
                                          old_value='1', new_value='2', user=self.user)
        creation = ContractLog.objects.create(contract=self.contract_a, field_name='holder',
                                              old_value=None, new_value='2', user=self.user)
        for log in (edit, creation):
            self._set(ContractLog, log, 'created_at', at(3))

        _users, metrics, _payments = self._compute()

        self.assertEqual(metrics['Municipi A'][self.user.id][METRIC_CHANGE_OF_NAME], 1)

    def test_bank_account_changes_only_when_iban_changes_and_once_per_day(self):
        old_bank = PersonBank.objects.create(iban='ES0000000000000000000001')
        same_iban = PersonBank.objects.create(iban='ES0000000000000000000001')
        new_bank = PersonBank.objects.create(iban='ES0000000000000000000002')
        cash, transfer = PaymentType.objects.create(name='Efectiu'), PaymentType.objects.create(name='Transferència')
        changes = ContractDataChange.objects.bulk_create([
            ContractDataChange(contract=self.contract_a, user=self.user,
                               previous_payment=old_bank, new_payment=new_bank),
            ContractDataChange(contract=self.contract_a, user=self.user,
                               previous_payment=old_bank, new_payment=same_iban),
            ContractDataChange(contract=self.contract_a, user=self.user,
                               previous_payment_type=cash, new_payment_type=transfer),
            ContractDataChange(contract=self.contract_a, user=self.user,
                               previous_payment_type=cash, new_payment_type=cash),
        ])
        ContractDataChange.objects.filter(id__in=[c.id for c in changes]).update(created_at=at(4))
        # El mateix canvi també queda al log del contracte el mateix dia: compta una vegada.
        log = ContractLog.objects.create(contract=self.contract_a, field_name='payment_IBAN',
                                         old_value='x', new_value='y', user=self.user)
        self._set(ContractLog, log, 'created_at', at(4, 11))

        _users, metrics, _payments = self._compute()

        counts = metrics['Municipi A'][self.user.id]
        self.assertEqual(counts[METRIC_BANK_ACCOUNT_CHANGE], 1)
        self.assertEqual(counts[METRIC_PAYMENT_TYPE_CHANGE], 1)

    def test_collections_by_payment_type_and_remittance_apart(self):
        card = PaymentType.objects.create(name='Targeta')
        remittance = PaymentRemittance.objects.bulk_create([PaymentRemittance(token='R1')])[0]
        payment = Payment.objects.bulk_create([Payment(token='P1', contract=self.contract_b)])[0]
        movements = PaymentMovement.objects.bulk_create([
            PaymentMovement(payment=payment, user=self.user, previous_status=self.pending,
                            current_status=self.paid, payment_type=card, is_positive=True),
            PaymentMovement(payment=payment, user=self.user, previous_status=self.pending,
                            current_status=self.paid, payment_type=card, is_positive=True,
                            payment_remittance=remittance),
            # Processos del compte tècnic i moviments negatius no compten.
            PaymentMovement(payment=payment, user=self.technical, previous_status=self.pending,
                            current_status=self.paid, payment_type=card, is_positive=True),
            PaymentMovement(payment=payment, user=self.user, previous_status=self.paid,
                            current_status=self.pending, payment_type=card, is_positive=False),
        ])
        PaymentMovement.objects.filter(id__in=[m.id for m in movements]).update(timestamp=at(9))

        _users, metrics, payments = self._compute()

        counts = metrics['Municipi B'][self.user.id]
        self.assertEqual(counts[METRIC_MANUAL_COLLECTION], 1)
        self.assertEqual(counts[METRIC_REMITTANCE_COLLECTION], 1)
        self.assertEqual(payments['Municipi B'][self.user.id], {'Targeta': 1})

    def _invoice_log(self, invoice, token, fields, when, user=None):
        logs = InvoiceLog.objects.bulk_create([
            InvoiceLog(invoice=invoice, field_name=field, operation_token=token, user=user or self.user)
            for field in fields
        ])
        InvoiceLog.objects.filter(id__in=[log.id for log in logs]).update(created_at=when)

    def test_invoice_modifications_skip_automatic_changes_and_group_by_minute(self):
        invoice = Invoice.objects.bulk_create([Invoice(contract=self.contract_a)])[0]
        created = Invoice.objects.bulk_create([Invoice(contract=self.contract_a)])[0]
        self._invoice_log(created, 'op-created', ['Created'], at(2))
        self._invoice_log(invoice, 'op-status', ['status'], at(3))
        self._invoice_log(invoice, 'op-pdf', ['invoice_file', 'pdf_page_count'], at(3))
        self._invoice_log(invoice, 'op-edit-1', ['due_date', 'updated_at'], at(4, 9, 0, 5))
        self._invoice_log(invoice, 'op-edit-2', ['total_final', 'subtotal_final'], at(4, 9, 0, 40))
        self._invoice_log(invoice, 'op-edit-3', ['serie_final'], at(5))
        data_change = LogInvoiceDataChange.objects.create(object=invoice, user=self.user,
                                                          previous_iban='a', current_iban='b')
        self._set(LogInvoiceDataChange, data_change, 'timestamp', at(5, 9, 0, 20))

        _users, metrics, _payments = self._compute()

        counts = metrics['Municipi A'][self.user.id]
        self.assertEqual(counts[METRIC_INVOICE_CREATED], 1)
        # op-edit-1 i op-edit-2 (mateix minut) = 1; op-edit-3 = 1; el canvi de dades
        # és un altre minut = 1.
        self.assertEqual(counts[METRIC_INVOICE_MODIFICATION], 3)
        self.assertEqual(counts.get(METRIC_INVOICE_MASS_MODIFICATION, 0), 0)

    def test_mass_invoice_modifications_are_counted_apart(self):
        invoices = Invoice.objects.bulk_create([
            Invoice(contract=self.contract_a) for _ in range(MASS_MODIFICATION_THRESHOLD)
        ])
        for index, invoice in enumerate(invoices):
            self._invoice_log(invoice, f'op-mass-{index}',
                              ['payment_type_final', 'payment_type_token_final'], at(12, 8, 30, index))

        _users, metrics, _payments = self._compute()

        counts = metrics['Municipi A'][self.user.id]
        self.assertEqual(counts[METRIC_INVOICE_MASS_MODIFICATION], MASS_MODIFICATION_THRESHOLD)
        self.assertEqual(counts.get(METRIC_INVOICE_MODIFICATION, 0), 0)

    def test_management_without_contract_goes_to_no_city(self):
        invoice = Invoice.objects.bulk_create([Invoice()])[0]
        self._invoice_log(invoice, 'op-x', ['due_date'], at(6))

        _users, metrics, _payments = self._compute()

        self.assertEqual(metrics[None][self.user.id][METRIC_INVOICE_MODIFICATION], 1)

    def test_workbook_has_one_table_per_city_and_criteria(self):
        self._request(self.user, at(5), self.sp_a)
        self._invoice_log(Invoice.objects.bulk_create([Invoice()])[0], 'op-y', ['due_date'], at(6))
        users, metrics, payments = self._compute()

        workbook = build_workbook(DATE_FROM, DATE_TO, users, metrics, payments)

        self.assertEqual(workbook.sheetnames, ['Per municipi', 'Resum', 'Criteris'])
        first_column = [row[0] for row in workbook['Per municipi'].iter_rows(values_only=True)]
        self.assertIn('Municipi A', first_column)
        self.assertIn('Sense municipi', first_column)
        self.assertIn('Anna Oficina', first_column)


class DailyActivityJoinedPaymentsTests(TestCase):
    """El resum d'activitat petava en sumar `amount`, que JoinedPayment no té."""

    def test_joined_payments_are_summed_with_total_final(self):
        from billing.models import JoinedPayment

        user = User.objects.create(username='oficina')
        JoinedPayment.objects.bulk_create([JoinedPayment(user=user, total_final='12.50')])

        today = timezone.localdate()
        activity = build_daily_activity([user.id], today, today, include_details=True)

        collections = next(c for c in activity['categories'] if c['key'] == 'collections')
        source = next(s for s in collections['sources'] if s['key'] == 'joined_payments')
        self.assertEqual(source['count'], 1)
        self.assertEqual(float(source['amounts']['net']), 12.5)
