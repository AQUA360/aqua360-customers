from types import SimpleNamespace

from django.test import SimpleTestCase

from billing.utils.invoice_service import termination_payment_bank_for_contract_request


def _with_bank(bank_id, entity_id=1):
    payment = SimpleNamespace(IBAN_id=bank_id) if bank_id is not None else None
    return SimpleNamespace(id=entity_id, payment=payment)


class TestTerminationPaymentBankForContractRequest(SimpleTestCase):
    """Factura de baixa que cobra l'alta vinculada (Alta + Baixa vinculades).

    El diàleg de la baixa proposava el compte del contracte que es dona de baixa i la
    factura sortia a nom del titular de l'alta amb el compte de l'antic.
    """

    def setUp(self):
        self.contract = _with_bank(10)
        self.contract_request = _with_bank(20)

    def test_terminated_contract_bank_is_ignored(self):
        self.assertIsNone(termination_payment_bank_for_contract_request(10, self.contract_request, self.contract))
        self.assertIsNone(termination_payment_bank_for_contract_request('10', self.contract_request, self.contract))

    def test_contract_request_bank_is_kept(self):
        self.assertEqual(termination_payment_bank_for_contract_request(20, self.contract_request, self.contract), 20)

    def test_other_bank_chosen_in_dialog_is_kept(self):
        self.assertEqual(termination_payment_bank_for_contract_request(30, self.contract_request, self.contract), 30)

    def test_without_bank_from_dialog(self):
        self.assertIsNone(termination_payment_bank_for_contract_request(None, self.contract_request, self.contract))

    def test_contract_request_without_bank_keeps_dialog_bank(self):
        # Sense compte a l'alta no hi ha alternativa: es manté el que ha triat l'usuari
        self.assertEqual(termination_payment_bank_for_contract_request(10, _with_bank(None), self.contract), 10)

    def test_same_bank_on_both_is_kept(self):
        self.assertEqual(termination_payment_bank_for_contract_request(10, _with_bank(10), self.contract), 10)
