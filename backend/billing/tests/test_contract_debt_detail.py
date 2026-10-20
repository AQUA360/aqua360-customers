from datetime import date
from decimal import Decimal

from django.test import TestCase

from billing.models import (
    Invoice, JoinedPayment, JoinedPaymentStatus, Payment, PaymentRemittance, PaymentStatus,
)
from billing.utils.joined_payment_service import get_contract_debt_detail, get_pending_client_data
from billing.utils.payment_service import disconnect_payment_signals, reconnect_payment_signals
from contract.models import Contract
from coredata.models import ConfigProject


class TestContractDebtDetail(TestCase):
    """Detall del deute d'un contracte (regió que s'obre clicant el deute).

    Ha de llistar els mateixos pagaments que suma vw_contract_debt i indicar
    quins no es poden liquidar perquè ja són en una remesa pendent d'enviar o
    en un pagament agrupat actiu.
    """

    def setUp(self):
        disconnect_payment_signals()
        self.addCleanup(reconnect_payment_signals)

        ConfigProject.objects.get_or_create(
            token='contract_terminated_status', defaults={'value': '0'})
        status_tokens = {
            'payment_status_paid_token': ('0', 'Pagat'),
            'payment_status_pending_token': ('1', 'Pendent'),
            'payment_status_expired_token': ('-1', 'Vençut'),
            'payment_status_returned_token': ('-2', 'Retornat'),
            'payment_status_sent_token': ('2', 'Processat'),
            'payment_status_endowment_token': ('-3', 'Morositat'),
            'payment_status_irrecoverable_token': ('-5', 'Irrecuperable'),
            'payment_status_commitment_token': ('4', 'En compromís'),
            'payment_status_cancelled_token': ('-6', 'Abonat'),
        }
        self.status = {}
        for config_token, (token, name) in status_tokens.items():
            ConfigProject.objects.update_or_create(token=config_token, defaults={'value': token})
            self.status[token] = PaymentStatus.objects.create(token=token, name=name)

        for config_token, token in {
            'joined_payment_status_paid_token': '0',
            'joined_payment_status_pending_token': '1',
            'joined_payment_status_expired_token': '-1',
            'joined_payment_status_cancelled_token': '-2',
        }.items():
            ConfigProject.objects.update_or_create(token=config_token, defaults={'value': token})
        self.joined_pending = JoinedPaymentStatus.objects.create(token='1', name='Pendent', is_default=True)
        self.joined_cancelled = JoinedPaymentStatus.objects.create(token='-2', name='Anul·lat')

        self.contract = Contract.objects.create(token='C-DEBT')
        self.other_contract = Contract.objects.create(token='C-OTHER')
        self.invoice = Invoice.objects.create(token='F-1', contract=self.contract, serie_final='FC/1')

    def payment(self, token, amount, status, invoice=None, contract=None):
        return Payment.objects.create(
            token=token, amount=Decimal(amount), status=self.status[status],
            invoice=invoice if invoice is not None else self.invoice,
            contract=contract, due_date=date(2026, 1, 1))

    def by_token(self, detail):
        return {item['token']: item for item in detail['payments']}

    def test_total_coincideix_amb_el_deute_i_exclou_pagats_i_negatius(self):
        self.payment('P-PENDING', '10.00', '1')
        self.payment('P-EXPIRED', '5.50', '-1')
        self.payment('P-COMMIT', '3.00', '4')
        self.payment('P-PAID', '7.00', '0')
        self.payment('P-CANCELLED', '8.00', '-6')
        self.payment('P-NEGATIVE', '-4.00', '1')

        detail = get_contract_debt_detail(self.contract.id)
        items = self.by_token(detail)

        self.assertEqual(set(items), {'P-PENDING', 'P-EXPIRED', 'P-COMMIT'})
        self.assertEqual(detail['total_debt'], Decimal('18.50'))
        # En compromís compta al deute però no es liquida amb un pagament agrupat
        self.assertTrue(items['P-COMMIT']['in_debt'])
        self.assertFalse(items['P-COMMIT']['is_settleable'])
        self.assertEqual(detail['total_settleable'], Decimal('15.50'))

    def test_pagament_en_remesa_pendent_d_enviar(self):
        payment = self.payment('P-REM', '12.00', '1')
        remittance = PaymentRemittance.objects.create(token='REM-1')
        remittance.payments.add(payment)

        detail = get_contract_debt_detail(self.contract.id)
        item = self.by_token(detail)['P-REM']

        self.assertTrue(item['in_debt'])
        self.assertFalse(item['is_settleable'])
        self.assertEqual(item['remittance']['token'], 'REM-1')
        self.assertTrue(item['remittance']['is_pending_send'])
        self.assertEqual(detail['total_in_pending_remittance'], Decimal('12.00'))
        self.assertEqual(detail['total_settleable'], Decimal('0'))

    def test_pagament_en_remesa_enviada_i_retornat_es_pot_liquidar(self):
        payment = self.payment('P-RET', '9.00', '-2')
        remittance = PaymentRemittance.objects.create(token='REM-2', sent_at=date(2026, 2, 1))
        remittance.payments.add(payment)

        item = self.by_token(get_contract_debt_detail(self.contract.id))['P-RET']

        self.assertTrue(item['is_settleable'])
        self.assertFalse(item['remittance']['is_pending_send'])

    def test_pagament_en_pagament_agrupat_actiu(self):
        in_active = self.payment('P-JOINED', '6.00', '1')
        in_cancelled = self.payment('P-JOINED-CANCELLED', '4.00', '1')
        JoinedPayment.objects.create(token='JP-1', status=self.joined_pending).payments.add(in_active)
        JoinedPayment.objects.create(token='JP-2', status=self.joined_cancelled).payments.add(in_cancelled)

        detail = get_contract_debt_detail(self.contract.id)
        items = self.by_token(detail)

        self.assertFalse(items['P-JOINED']['is_settleable'])
        self.assertEqual(items['P-JOINED']['joined_payment']['token'], 'JP-1')
        self.assertTrue(items['P-JOINED-CANCELLED']['is_settleable'])
        self.assertIsNone(items['P-JOINED-CANCELLED']['joined_payment'])
        self.assertEqual(detail['total_in_joined_payment'], Decimal('6.00'))

    def test_pagament_de_factura_del_contracte_sense_contracte_al_pagament(self):
        # Molts pagaments només tenen el contracte a la factura: s'han de poder liquidar
        self.payment('P-NO-CONTRACT', '11.00', '1')

        pending = get_pending_client_data({'contract': self.contract.id})

        self.assertEqual([p['token'] for p in pending['pending_payments']], ['P-NO-CONTRACT'])

    def test_no_inclou_pagaments_d_altres_contractes(self):
        other_invoice = Invoice.objects.create(token='F-2', contract=self.other_contract)
        self.payment('P-OTHER', '20.00', '1', invoice=other_invoice)

        detail = get_contract_debt_detail(self.contract.id)

        self.assertEqual(detail['payments'], [])
        self.assertEqual(detail['total_debt'], Decimal('0'))

    def test_document_agafa_el_contracte_de_la_factura(self):
        from billing.utils.joined_payment_service import _payments_for_template

        self.payment('P-DOC', '10.00', '1')
        payments = _payments_for_template(Payment.objects.filter(token='P-DOC'))

        # Les plantilles recorren `payments.all`
        self.assertEqual([p.contract.token for p in payments.all()], ['C-DEBT'])
        # Només en memòria: el pagament no es modifica
        self.assertIsNone(Payment.objects.get(token='P-DOC').contract)
