"""Procés d'insolvència d'una persona (#2633)."""
from datetime import date

from django.contrib.auth.models import Permission, User
from django.test import TestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from billing.models import GeneralPayment, InsolvencyProcess, Invoice, InvoiceStatus, Payment
from billing.utils.insolvency_service import (
    InsolvencyProcessError,
    close_insolvency_process,
    create_insolvency_process,
    insolvent_holder_contracts,
    is_person_insolvent,
)
from billing.utils.payment_service import disconnect_payment_signals, reconnect_payment_signals
from billing.serializers.insolvency_process_serializer import InsolvencyProcessSerializer
from billing.views.insolvency_process_view import InsolvencyProcessViewSet
from billing.views.sepa_payment_document_generate_view import get_insolvent_holders
from contract.models import Contract, ContractDataChange, ContractDebtManagement, ContractLog, PaymentType
from coredata.models import ConfigProject, Person, PersonAnomaly, PersonBank


def _perm(label):
    app_label, codename = label.split('.')
    return Permission.objects.get(content_type__app_label=app_label, codename=codename)


class InsolvencyProcessTestCase(TestCase):
    def setUp(self):
        disconnect_payment_signals()
        self.addCleanup(reconnect_payment_signals)
        ConfigProject.objects.get_or_create(token='contract_terminated_status', defaults={'value': '0'})
        ConfigProject.objects.update_or_create(token='direct_debit_token', defaults={'value': 'DIRECT_DEBIT'})
        ConfigProject.objects.update_or_create(token='invoice_status_cancelled_token', defaults={'value': '-9'})
        self.cancelled = InvoiceStatus.objects.create(token='-9', name='Anul·lada')

        self.user = User.objects.create_user('insolvency-2633', 'insolvency-2633@example.com', 'x')
        self.direct_debit = PaymentType.objects.create(token='DIRECT_DEBIT', name='Domiciliació')
        self.transfer = PaymentType.objects.create(token='BANK_TRANSFER', name='Transferència')

        self.person = Person.objects.create(token='PERSON-INSOLVENT-2633', name='Prova')
        self.other = Person.objects.create(token='PERSON-OTHER-2633', name='Altra')
        bank = PersonBank.objects.create(person=self.person, iban='ES0000000000000000000000')
        self.payment = GeneralPayment.objects.create(token='GP-2633', type=self.direct_debit, IBAN=bank)
        self.contract = Contract.objects.create(token='C-2633', holder=self.person, is_active=True,
                                                payment=self.payment)
        self.other_contract = Contract.objects.create(token='C-OTHER-2633', holder=self.other, is_active=True)

        self.before = Invoice.objects.create(token='F-OLD', person=self.person, contract=self.contract,
                                             issue_date=date(2026, 1, 10))
        self.after = Invoice.objects.create(token='F-NEW', person=self.person, contract=self.contract,
                                            issue_date=date(2026, 3, 1))
        self.after_cancelled = Invoice.objects.create(token='F-CANC', person=self.person, contract=self.contract,
                                                      issue_date=date(2026, 3, 2), status=self.cancelled)
        self.other_invoice = Invoice.objects.create(token='F-OTHER', person=self.other, issue_date=date(2026, 3, 1))

    def _create(self, **kwargs):
        data = dict(person=self.person, kind=InsolvencyProcess.KIND_CREDITORS, start_date=date(2026, 2, 1),
                    user=self.user)
        data.update(kwargs)
        return create_insolvency_process(**data)

    def test_create_activates_insolvent_anomaly_and_links_all_invoices_since_date(self):
        process = self._create()
        self.assertTrue(is_person_insolvent(self.person))
        self.assertEqual(process.anomaly.anomaly_type.token, 'insolvent')
        self.assertEqual(process.anomaly.start_date, date(2026, 2, 1))
        # Ni l'anterior a la data, ni l'anul·lada, ni la d'una altra persona
        self.assertEqual(list(process.invoices.values_list('id', flat=True)), [self.after.id])

    def test_invoices_issued_while_open_enter_the_process(self):
        process = self._create()
        later = Invoice.objects.create(token='F-LATER', person=self.person, contract=self.contract,
                                       issue_date=date(2026, 5, 1))
        data = InsolvencyProcessSerializer(process).data
        self.assertEqual([invoice['id'] for invoice in data['invoices']], [self.after.id, later.id])
        close_insolvency_process(process, self.user, date(2026, 6, 1))
        self.assertEqual(set(process.invoices.values_list('id', flat=True)), {self.after.id, later.id})

    def test_only_one_open_process_per_person(self):
        self._create()
        with self.assertRaises(InsolvencyProcessError):
            self._create()

    def test_payment_change_without_save_side_effects(self):
        process = self._create(payment_changes=[{'contract_id': self.contract.id, 'payment_type_id': self.transfer.id}])
        self.contract.refresh_from_db()
        self.assertEqual(self.contract.payment.type, self.transfer)
        self.assertEqual(self.contract.payment.IBAN_id, self.payment.IBAN_id)
        self.payment.refresh_from_db()
        self.assertFalse(self.payment.is_active)
        change = process.contracts.get()
        self.assertEqual((change.previous_payment_type, change.new_payment_type), (self.direct_debit, self.transfer))
        self.assertTrue(ContractLog.objects.filter(contract=self.contract, field_name='payment').exists())
        self.assertTrue(ContractDataChange.objects.filter(contract=self.contract, new_payment_type=self.transfer).exists())

    def test_payment_change_rejects_contract_of_other_person(self):
        with self.assertRaises(InsolvencyProcessError):
            self._create(payment_changes=[{'contract_id': self.other_contract.id, 'payment_type_id': self.transfer.id}])
        self.other_contract.refresh_from_db()
        self.assertIsNone(self.other_contract.payment_id)

    def test_direct_debit_requires_bank_account(self):
        contract = Contract.objects.create(token='C-NOIBAN-2633', holder=self.person, is_active=True,
                                           payment=GeneralPayment.objects.create(token='GP-T', type=self.transfer))
        with self.assertRaises(InsolvencyProcessError):
            self._create(payment_changes=[{'contract_id': contract.id, 'payment_type_id': self.direct_debit.id}])
        self.assertFalse(InsolvencyProcess.objects.exists())

    def test_close_resolves_anomaly(self):
        process = self._create()
        close_insolvency_process(process, self.user, date(2026, 6, 1))
        process.refresh_from_db()
        self.assertEqual(process.status, InsolvencyProcess.STATUS_CLOSED)
        self.assertEqual(process.anomaly.end_date, date(2026, 6, 1))
        self.assertFalse(is_person_insolvent(self.person))
        with self.assertRaises(InsolvencyProcessError):
            close_insolvency_process(process, self.user)

    def test_debt_management_insolvent_while_open_and_restored_on_close(self):
        insolvent = ContractDebtManagement.objects.create(token='insolvent', name='Insolvent')
        previous = ContractDebtManagement.objects.create(token='employee', name='Empleats')
        Contract.objects.filter(pk=self.contract.pk).update(debt_management=previous)
        manual = Contract.objects.create(token='C-MANUAL-2633', holder=self.person, is_active=True)
        process = self._create()
        self.contract.refresh_from_db()
        manual.refresh_from_db()
        self.assertEqual((self.contract.debt_management, manual.debt_management), (insolvent, insolvent))
        self.assertTrue(ContractLog.objects.filter(contract=self.contract, field_name='debt_management').exists())
        self.other_contract.refresh_from_db()
        self.assertIsNone(self.other_contract.debt_management)
        # Si algú l'ha canviat a mà durant el procés, en tancar no es toca
        Contract.objects.filter(pk=manual.pk).update(debt_management=previous)
        close_insolvency_process(process, self.user, date(2026, 6, 1))
        self.contract.refresh_from_db()
        manual.refresh_from_db()
        self.assertEqual((self.contract.debt_management, manual.debt_management), (previous, previous))
        self.assertTrue(process.contracts.get(contract=self.contract).debt_management_restored)
        self.assertFalse(process.contracts.get(contract=manual).debt_management_restored)

    def test_close_restores_previous_payment_type_on_request(self):
        process = self._create(payment_changes=[{'contract_id': self.contract.id, 'payment_type_id': self.transfer.id}])
        close_insolvency_process(process, self.user, date(2026, 6, 1), restore_payment=True)
        self.contract.refresh_from_db()
        self.assertEqual(self.contract.payment.type, self.direct_debit)
        self.assertEqual(self.contract.payment.IBAN_id, self.payment.IBAN_id)
        self.assertTrue(process.contracts.get().payment_restored)

    def test_close_keeps_payment_type_by_default_or_if_changed_since(self):
        process = self._create(payment_changes=[{'contract_id': self.contract.id, 'payment_type_id': self.transfer.id}])
        close_insolvency_process(process, self.user, date(2026, 6, 1))
        self.contract.refresh_from_db()
        self.assertEqual(self.contract.payment.type, self.transfer)
        other = self._create(start_date=date(2026, 7, 1),
                             payment_changes=[{'contract_id': self.contract.id, 'payment_type_id': self.direct_debit.id}])
        changed = GeneralPayment.objects.create(token='GP-MANUAL', type=self.transfer)
        Contract.objects.filter(pk=self.contract.pk).update(payment=changed)
        close_insolvency_process(other, self.user, date(2026, 8, 1), restore_payment=True)
        self.contract.refresh_from_db()
        self.assertEqual(self.contract.payment, changed)

    def test_close_before_anomaly_start_writes_nothing(self):
        process = self._create()
        with self.assertRaises(InsolvencyProcessError):
            close_insolvency_process(process, self.user, date(2026, 1, 1))
        process.refresh_from_db()
        self.assertEqual(process.status, InsolvencyProcess.STATUS_OPEN)

    def test_claim_requests_leave_out_holders_with_open_process(self):
        from claimrequest.tasks import _build_claim_request_filters
        for token in ('claim_request_status_accepted_token', 'claim_request_status_pending_token'):
            ConfigProject.objects.get_or_create(token=token, defaults={'value': token})
        contracts = Contract.objects.filter(id__in=[self.contract.id, self.other_contract.id])
        process = self._create()
        contract_filters = _build_claim_request_filters({})[-1]
        self.assertEqual(list(contracts.filter(contract_filters).values_list('id', flat=True)), [self.other_contract.id])
        close_insolvency_process(process, self.user, date(2026, 6, 1))
        contract_filters = _build_claim_request_filters({})[-1]
        self.assertEqual(set(contracts.filter(contract_filters).values_list('id', flat=True)),
                         {self.contract.id, self.other_contract.id})

    def test_indefinite_supply_cut_blocked_while_open(self):
        from service.models import SupplyCut, SupplyCutCause, SupplyPoint
        from service.utils.supply_cut_service import SupplyCutActivationError, validate_activation
        point = SupplyPoint.objects.create(token='SP-2633')
        Contract.objects.filter(pk=self.contract.pk).update(supply_point_default=point)
        cut = SupplyCut.objects.create(token='CUT-2633', cause=SupplyCutCause.objects.create(token='debt'))
        cut.supply_points.add(point)
        temporary = SupplyCut.objects.create(
            token='CUT-TMP-2633', cause=SupplyCutCause.objects.create(token='works', is_temporary=True))
        temporary.supply_points.add(point)
        process = self._create()
        with self.assertRaises(SupplyCutActivationError) as raised:
            validate_activation(cut)
        self.assertEqual(raised.exception.detail['code'], 'insolvency_blocked')
        validate_activation(temporary)
        close_insolvency_process(process, self.user, date(2026, 6, 1))
        validate_activation(cut)

    def test_insolvent_holder_contracts(self):
        self._create()
        contracts = insolvent_holder_contracts(Contract.objects.filter(id__in=[self.contract.id, self.other_contract.id]))
        self.assertEqual([contract.id for contract in contracts], [self.contract.id])

    def test_remittance_insolvent_holders(self):
        self._create()
        Payment.objects.create(token='P-1', invoice=self.after, amount=10)
        Payment.objects.create(token='P-2', invoice=self.other_invoice, amount=10)
        Payment.objects.create(token='P-3', invoice=self.before, amount=10, is_excluded=True)
        holders, total = get_insolvent_holders(Payment.objects.all())
        self.assertEqual(total, 1)
        self.assertEqual([(row['id'], row['payments']) for row in holders], [(self.person.id, 1)])


class InsolvencyProcessApiTestCase(TestCase):
    def setUp(self):
        ConfigProject.objects.get_or_create(token='contract_terminated_status', defaults={'value': '0'})
        self.person = Person.objects.create(token='PERSON-API-2633', name='Prova')
        self.user = User.objects.create_user('insolvency-api-2633', 'insolvency-api-2633@example.com', 'x')
        self.user.user_permissions.add(_perm('billing.view_payment'), _perm('billing.add_payment'))
        self.viewer = User.objects.create_user('insolvency-viewer-2633', 'insolvency-viewer-2633@example.com', 'x')
        self.viewer.user_permissions.add(_perm('billing.view_payment'))
        self.factory = APIRequestFactory()

    def _post(self, user, actions, data, **kwargs):
        request = self.factory.post('/billing/insolvency-process/', data, format='json')
        force_authenticate(request, user=User.objects.get(pk=user.pk))
        return InsolvencyProcessViewSet.as_view(actions)(request, **kwargs)

    def test_create_and_close(self):
        response = self._post(self.user, {'post': 'create'}, {
            'person_id': self.person.id, 'kind': 'second_chance', 'start_date': '2026-02-01', 'case_number': 'EXP-1',
        })
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data['status'], 'open')
        response = self._post(self.user, {'post': 'close'}, {'end_date': '2026-06-01', 'restore_payment': True},
                              pk=response.data['id'])
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['status'], 'closed')
        self.assertEqual(str(response.data['end_date']), '2026-06-01')

    def test_invalid_data_returns_400(self):
        response = self._post(self.user, {'post': 'create'}, {'person_id': self.person.id, 'kind': 'x', 'start_date': '2026-02-01'})
        self.assertEqual(response.status_code, 400)
        response = self._post(self.user, {'post': 'create'}, {'person_id': self.person.id, 'kind': 'creditors', 'start_date': 'no'})
        self.assertEqual(response.status_code, 400)
        self.assertFalse(PersonAnomaly.objects.exists())

    def test_create_requires_add_payment(self):
        response = self._post(self.viewer, {'post': 'create'}, {
            'person_id': self.person.id, 'kind': 'creditors', 'start_date': '2026-02-01'})
        self.assertEqual(response.status_code, 403)

    def test_preview(self):
        response = self._post(self.user, {'post': 'preview'}, {'person_id': self.person.id, 'start_date': '2026-02-01'})
        self.assertEqual(response.status_code, 200, response.data)
        self.assertFalse(response.data['is_insolvent'])
        self.assertEqual(response.data['invoices'], [])


class PersonInsolvencyFilterTestCase(TestCase):
    def test_filter_persons_with_open_process(self):
        from coredata.filters.person_filter import PersonFilter
        ConfigProject.objects.get_or_create(token='contract_terminated_status', defaults={'value': '0'})
        user = User.objects.create_user('insolvency-filter-2633', 'insolvency-filter-2633@example.com', 'x')
        insolvent = Person.objects.create(token='P-INS-2633', name='Insolvent')
        closed = Person.objects.create(token='P-CLOSED-2633', name='Tancat')
        normal = Person.objects.create(token='P-NORMAL-2633', name='Normal')
        create_insolvency_process(person=insolvent, kind='creditors', start_date=date(2026, 2, 1), user=user)
        close_insolvency_process(
            create_insolvency_process(person=closed, kind='creditors', start_date=date(2026, 2, 1), user=user), user)
        queryset = Person.objects.filter(id__in=[insolvent.id, closed.id, normal.id])
        with_process = PersonFilter({'insolvency': 'true'}, queryset=queryset).qs
        without_process = PersonFilter({'insolvency': 'false'}, queryset=queryset).qs
        self.assertEqual(list(with_process.values_list('id', flat=True)), [insolvent.id])
        self.assertEqual(set(without_process.values_list('id', flat=True)), {closed.id, normal.id})


class InsolvencyAnomalyManagedByProcessTestCase(TestCase):
    def test_anomaly_of_open_process_cannot_be_resolved_or_deleted(self):
        from coredata.views.person_anomaly_view import PersonAnomalyViewSet
        ConfigProject.objects.get_or_create(token='contract_terminated_status', defaults={'value': '0'})
        user = User.objects.create_superuser('insolvency-anomaly-2633', 'insolvency-anomaly-2633@example.com', 'x')
        person = Person.objects.create(token='P-ANOM-2633', name='Prova')
        process = create_insolvency_process(person=person, kind='creditors', start_date=date(2026, 2, 1), user=user)
        factory = APIRequestFactory()
        for actions, method in (({'post': 'resolve'}, 'post'), ({'delete': 'destroy'}, 'delete')):
            request = getattr(factory, method)('/coredata/person-anomaly/', {}, format='json')
            force_authenticate(request, user=user)
            response = PersonAnomalyViewSet.as_view(actions)(request, pk=process.anomaly_id)
            self.assertEqual(response.status_code, 400)
        self.assertTrue(is_person_insolvent(person))


class InsolvencyErrorMessagesTestCase(TestCase):
    def test_every_raised_code_has_a_message(self):
        import re
        from pathlib import Path
        from billing.utils import insolvency_service
        from billing.views import insolvency_process_view
        codes = set()
        for module in (insolvency_service, insolvency_process_view):
            codes |= set(re.findall(r"InsolvencyProcessError\('([a-z_]+)'\)", Path(module.__file__).read_text()))
        self.assertTrue(codes)
        self.assertEqual(sorted(codes - set(insolvency_service.ERROR_MESSAGES)), [])
