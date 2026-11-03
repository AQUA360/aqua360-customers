from types import SimpleNamespace
from unittest.mock import patch

from django.db.models.signals import pre_save
from django.test import SimpleTestCase

from billing.models import Payment
from billing.signals import payment_status_changed, update_payment


class PaymentSignalConnectionTests(SimpleTestCase):
    def setUp(self):
        pre_save.connect(payment_status_changed, sender=Payment)
        self.addCleanup(pre_save.connect, payment_status_changed, sender=Payment)

    def assert_status_signal_connected(self):
        self.assertTrue(pre_save.disconnect(payment_status_changed, sender=Payment))
        pre_save.connect(payment_status_changed, sender=Payment)

    def test_early_guards_keep_status_signal_connected(self):
        for instance, kwargs in (
            (SimpleNamespace(id=1), {'created': True}),
            (SimpleNamespace(id=None), {'created': False}),
            (SimpleNamespace(id=1, _skip_signal=True), {'created': False}),
            (SimpleNamespace(id=1), {'created': False, 'raw': True}),
        ):
            with self.subTest(kwargs=kwargs, instance=instance):
                update_payment(Payment, instance, **kwargs)
                self.assert_status_signal_connected()

    def test_configuration_error_reconnects_status_signal(self):
        with patch('billing.signals.ConfigProject.objects.get', side_effect=RuntimeError('config error')):
            with self.assertRaisesRegex(RuntimeError, 'config error'):
                update_payment(Payment, SimpleNamespace(id=1), created=False)
        self.assert_status_signal_connected()

    def test_payment_without_invoice_reconnects_status_signal(self):
        status_map = {key: key for key in (
            'payment_status_paid_token', 'payment_status_expired_token',
            'payment_status_endowment_token', 'payment_status_irrecoverable_token',
            'payment_status_returned_token', 'payment_status_cancelled_token',
            'payment_status_commitment_token', 'payment_status_piggy_token',
        )}
        payment = SimpleNamespace(
            id=1, status=status_map['payment_status_expired_token'], invoice=None, commitment_deposit=None,
        )
        with patch('billing.signals.ConfigProject.objects.get'), patch(
            'billing.signals.get_status_map', return_value=status_map,
        ):
            update_payment(Payment, payment, created=False)
        self.assert_status_signal_connected()

    def test_skipped_nested_update_does_not_reconnect_status_signal(self):
        pre_save.disconnect(payment_status_changed, sender=Payment)
        update_payment(Payment, SimpleNamespace(id=1, _skip_signal=True), created=False)
        self.assertFalse(pre_save.disconnect(payment_status_changed, sender=Payment))
