from django.contrib.auth import get_user_model
from django.test import TestCase
from django.test import RequestFactory

from billing.models import GeneralPayment
from billing.serializers.general_payment_serializer import GeneralPaymentSerializer
from contract.models import Contract, PaymentType
from coredata.models import ConfigProject, Person, PersonBank


class TestGeneralPaymentSplit(TestCase):
    """Copy-on-write de GeneralPayment quan la fila la comparteixen contractes.

    `Contract.payment` és una FK normal: la importació inicial de dades va crear
    una GeneralPayment per (titular, compte) i hi va vincular tots els contractes
    d'aquell titular. Canviar-hi la domiciliació mutava la fila i el canvi
    apareixia a tots els contractes alhora.
    """

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='test_split', password='test_split')
        self.request = RequestFactory().put('/')
        self.request.user = self.user

        # El post_save de Contract consulta aquesta config
        ConfigProject.objects.get_or_create(
            token='contract_terminated_status', defaults={'value': '0'})

        self.direct_debit = PaymentType.objects.create(token='DIRECT_DEBIT', name='Domiciliació')
        self.cash = PaymentType.objects.create(token='CASH', name='Efectiu')

        self.person = Person.objects.create(name='Titular', token='00000000T')
        self.bank_a = PersonBank.objects.create(
            person=self.person, iban='ES9121000418450200051332', is_active=True)
        self.bank_b = PersonBank.objects.create(
            person=self.person, iban='ES7921000813610123456789', is_active=True)

        self.payment = GeneralPayment.objects.create(
            token='00000000T_BANK_1', type=self.direct_debit, IBAN=self.bank_a)
        self.contract_a = Contract.objects.create(token='C-A', payment=self.payment)
        self.contract_b = Contract.objects.create(token='C-B', payment=self.payment)

    def change_payment(self, contract, data):
        """El que fa el front: PUT del payment i vincle del retorn al contracte."""
        serializer = GeneralPaymentSerializer(
            contract.payment, data=data, partial=True, context={'request': self.request})
        serializer.is_valid(raise_exception=True)
        saved = serializer.save()
        contract.payment = saved
        contract.save()
        return saved

    def test_canvi_iban_en_fila_compartida_no_afecta_laltre_contracte(self):
        saved = self.change_payment(self.contract_a, {
            'iban_id': self.bank_b.id,
            'type_id': self.direct_debit.id,
            'mandate_token': self.contract_a.token,
        })

        self.assertNotEqual(saved.id, self.payment.id)
        self.contract_b.refresh_from_db()
        self.assertEqual(self.contract_b.payment_id, self.payment.id)
        self.assertEqual(self.contract_b.payment.IBAN_id, self.bank_a.id)
        self.contract_a.refresh_from_db()
        self.assertEqual(self.contract_a.payment.IBAN_id, self.bank_b.id)

    def test_canvi_tipus_en_fila_compartida_no_afecta_laltre_contracte(self):
        self.change_payment(self.contract_a, {'type_id': self.cash.id})

        self.contract_b.refresh_from_db()
        self.assertEqual(self.contract_b.payment_id, self.payment.id)
        self.assertEqual(self.contract_b.payment.type_id, self.direct_debit.id)
        self.contract_a.refresh_from_db()
        self.assertEqual(self.contract_a.payment.type_id, self.cash.id)

    def test_fila_no_compartida_no_es_duplica(self):
        self.contract_b.payment = None
        self.contract_b.save()
        before = GeneralPayment.objects.count()

        saved = self.change_payment(self.contract_a, {
            'iban_id': self.bank_b.id,
            'type_id': self.direct_debit.id,
            'mandate_token': self.contract_a.token,
        })

        self.assertEqual(saved.id, self.payment.id)
        self.assertEqual(GeneralPayment.objects.count(), before)

    def test_desar_sense_canvis_no_duplica_fila_compartida(self):
        before = GeneralPayment.objects.count()

        saved = self.change_payment(self.contract_a, {
            'iban_id': self.bank_a.id,
            'type_id': self.direct_debit.id,
            'mandate_token': self.contract_a.token,
        })

        self.assertEqual(saved.id, self.payment.id)
        self.assertEqual(GeneralPayment.objects.count(), before)

    def test_la_copia_no_arrossega_les_dades_de_factura_electronica(self):
        self.payment.accounting_office = 'L01000000'
        self.payment.save()

        saved = self.change_payment(self.contract_a, {
            'iban_id': self.bank_b.id,
            'type_id': self.direct_debit.id,
            'mandate_token': self.contract_a.token,
        })

        self.assertEqual(saved.accounting_office, 'L01000000')
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.accounting_office, 'L01000000')
