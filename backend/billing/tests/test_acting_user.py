from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from billing.models import Payment
from billing.signals import payment_status_changed, update_payment
from billing.utils.payment_service import get_acting_user
from contract.middleware import set_current_user
from customers.celery import CURRENT_USER_HEADER, attach_current_user, clear_current_user, restore_current_user
from order.middleware import get_current_user


class ActingUserTests(SimpleTestCase):
    def setUp(self):
        self.user = SimpleNamespace(pk=7, username='operator')
        self.addCleanup(set_current_user, None)

    def test_explicit_user_wins_over_current_user(self):
        other = SimpleNamespace(pk=8)
        set_current_user(self.user)
        self.assertIs(get_acting_user(other), other)

    def test_without_user_falls_back_to_current_user(self):
        set_current_user(self.user)
        self.assertIs(get_acting_user(None), self.user)

    def test_without_user_or_current_user_is_none(self):
        self.assertIsNone(get_acting_user(None))

    def test_order_middleware_shares_current_user(self):
        set_current_user(self.user)
        self.assertIs(get_current_user(), self.user)

    def test_payment_status_change_is_logged_with_current_user(self):
        set_current_user(self.user)
        original = SimpleNamespace(status='pending')
        instance = MagicMock(pk=1, status=MagicMock(token='paid'), payment_type_token='TRANSFER')
        sender = MagicMock()
        sender.objects.get.return_value = original
        with patch('billing.signals.ConfigProject.objects.get', return_value=SimpleNamespace(value='paid')), \
                patch('billing.signals.log_payment_status') as log_status, \
                patch('billing.signals.generate_payment_movement') as movement:
            payment_status_changed(sender, instance)
        self.assertIs(log_status.call_args.args[2], self.user)
        self.assertIs(movement.call_args.args[5], self.user)

    def test_commitment_deposit_payment_uses_current_user(self):
        set_current_user(self.user)
        status_map = {key: key for key in (
            'payment_status_paid_token', 'payment_status_expired_token',
            'payment_status_endowment_token', 'payment_status_irrecoverable_token',
            'payment_status_returned_token', 'payment_status_cancelled_token',
            'payment_status_commitment_token', 'payment_status_piggy_token',
        )}
        payment = SimpleNamespace(
            id=1, status='payment_status_paid_token', invoice=None, commitment_deposit=object(),
            payment_type_token='TRANSFER', payment_date='2026-10-29',
        )
        with patch('billing.signals.ConfigProject.objects.get'), \
                patch('billing.signals.get_status_map', return_value=status_map), \
                patch('billing.signals.wallet_payment_deposit_update') as wallet_update:
            update_payment(Payment, payment, created=False)
        wallet_update.assert_called_once_with(payment, self.user)


class CeleryCurrentUserTests(SimpleTestCase):
    def setUp(self):
        self.addCleanup(set_current_user, None)

    def make_task(self, is_eager=False, **headers):
        return SimpleNamespace(request=SimpleNamespace(is_eager=is_eager, **headers))

    def test_publish_attaches_current_user(self):
        set_current_user(SimpleNamespace(pk=7))
        headers = {}
        attach_current_user(headers=headers)
        self.assertEqual(headers[CURRENT_USER_HEADER], 7)

    def test_publish_keeps_explicit_user(self):
        set_current_user(SimpleNamespace(pk=7))
        headers = {CURRENT_USER_HEADER: None}
        attach_current_user(headers=headers)
        self.assertIsNone(headers[CURRENT_USER_HEADER])

    def test_publish_without_user_has_no_user(self):
        headers = {}
        attach_current_user(headers=headers)
        self.assertIsNone(headers[CURRENT_USER_HEADER])

    def test_task_runs_as_enqueuing_user_and_clears_it(self):
        user = SimpleNamespace(pk=7)
        task = self.make_task(**{CURRENT_USER_HEADER: 7})
        with patch('django.contrib.auth.models.User.objects.filter') as filter_users:
            filter_users.return_value.first.return_value = user
            restore_current_user(task=task)
        filter_users.assert_called_once_with(pk=7)
        self.assertIs(get_current_user(), user)
        clear_current_user(task=task)
        self.assertIsNone(get_current_user())

    def test_task_without_user_runs_without_user(self):
        set_current_user(SimpleNamespace(pk=7))
        restore_current_user(task=self.make_task())
        self.assertIsNone(get_current_user())

    def test_eager_task_keeps_request_user(self):
        user = SimpleNamespace(pk=7)
        set_current_user(user)
        task = self.make_task(is_eager=True)
        restore_current_user(task=task)
        clear_current_user(task=task)
        self.assertIs(get_current_user(), user)
