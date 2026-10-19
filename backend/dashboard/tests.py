import datetime
from decimal import Decimal

from django.contrib.auth.models import Permission, User
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from billing.models import Invoice, InvoiceType, Reading, ReadingBatch, ReadingBatchStatus
from coredata.models import MainPermission
from dashboard.cards.base import period_range
from dashboard.defaults import DEFAULT_LAYOUT
from dashboard.models import UserDashboard
from order.models import Order, OrderStatus

LAYOUT_URL = '/dashboard/layout/'
CARDS_URL = '/dashboard/cards/'


def data_url(key, **params):
    """Build a dashboard card data URL with optional query parameters."""
    query = '&'.join(f'{k}={v}' for k, v in params.items())
    return f'{CARDS_URL}{key}/data/' + (f'?{query}' if query else '')


class DashboardTestCase(TestCase):

    def setUp(self):
        """Create dashboard permissions, users and an authenticated API client."""
        for key, models in [('order', 'order.order'), ('billing', 'billing.invoice'), ('reading', 'billing.reading')]:
            MainPermission.objects.create(name=key, view_key=f'view_{key}', change_key=f'change_{key}', affected_models=models)
        self.admin = User.objects.create_superuser(username='admin', password='x')
        self.basic = User.objects.create_user(username='basic', password='x')
        self.client = APIClient()
        self.client.force_authenticate(self.admin)


class TestPeriodRange(TestCase):

    def test_ranges(self):
        """Check inclusive bounds for daily, weekly, monthly, quarterly and yearly periods."""
        today = datetime.date(2026, 8, 19)  # dimecres
        self.assertEqual(period_range('today', today), (today, today))
        self.assertEqual(period_range('week', today), (datetime.date(2026, 8, 17), datetime.date(2026, 8, 23)))
        self.assertEqual(period_range('month', today), (datetime.date(2026, 8, 1), datetime.date(2026, 8, 31)))
        self.assertEqual(period_range('quarter', today), (datetime.date(2026, 7, 1), datetime.date(2026, 9, 30)))
        self.assertEqual(period_range('quarter', datetime.date(2026, 11, 2)), (datetime.date(2026, 10, 1), datetime.date(2026, 12, 31)))
        self.assertEqual(period_range('year', today), (datetime.date(2026, 1, 1), datetime.date(2026, 12, 31)))


class TestLayout(DashboardTestCase):

    def test_default_layout_filtered_by_permissions(self):
        """Check that default cards are filtered by the requesting user permissions."""
        response = self.client.get(LAYOUT_URL)
        self.assertTrue(response.data['is_default'])
        self.assertEqual([c['key'] for c in response.data['layout']], [c['key'] for c in DEFAULT_LAYOUT])

        basic = APIClient()
        basic.force_authenticate(self.basic)
        keys = [c['key'] for c in basic.get(LAYOUT_URL).data['layout']]
        self.assertNotIn('orders_to_validate', keys)
        self.assertNotIn('invoices_issued', keys)
        self.assertIn('tasks_today', keys)

    def test_save_layout_cleans_size_and_config(self):
        """Check that saving normalizes card size, IDs and configuration."""
        response = self.client.put(LAYOUT_URL, {'layout': [
            {'key': 'invoices_issued', 'size': 'xl', 'config': {'period': 'year', 'unknown': 1}},
            {'id': 'abc', 'key': 'calendar', 'size': 'sm'},
        ]}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        layout = UserDashboard.objects.get(user=self.admin).layout
        self.assertEqual(layout[0]['size'], 'sm')
        self.assertEqual(layout[0]['config'], {'period': 'year'})
        self.assertTrue(layout[0]['id'])
        self.assertEqual(layout[1], {'id': 'abc', 'key': 'calendar', 'size': 'lg', 'config': {}})
        self.assertFalse(self.client.get(LAYOUT_URL).data['is_default'])

    def test_unknown_card_is_rejected(self):
        """Check that an unknown card key causes a validation error."""
        response = self.client.put(LAYOUT_URL, {'layout': [{'key': 'nope'}]}, format='json')
        self.assertEqual(response.status_code, 400)

    def test_reset_layout(self):
        """Check that resetting deletes the saved layout and restores defaults."""
        UserDashboard.objects.create(user=self.admin, layout=[{'key': 'calendar'}])
        response = self.client.delete(LAYOUT_URL)
        self.assertTrue(response.data['is_default'])
        self.assertFalse(UserDashboard.objects.exists())


class TestCards(DashboardTestCase):

    def test_catalog_by_permission(self):
        """Check that the card catalog excludes cards without permission."""
        keys = {c['key'] for c in self.client.get(CARDS_URL).data}
        self.assertIn('rebillings', keys)
        basic = APIClient()
        basic.force_authenticate(self.basic)
        keys = {c['key'] for c in basic.get(CARDS_URL).data}
        self.assertNotIn('rebillings', keys)

    def test_card_data_permission_and_unknown(self):
        """Check forbidden, unknown and frontend-only card data responses."""
        basic = APIClient()
        basic.force_authenticate(self.basic)
        self.assertEqual(basic.get(data_url('invoices_issued')).status_code, 403)
        self.assertEqual(self.client.get(data_url('nope')).status_code, 404)
        self.assertEqual(self.client.get(data_url('calendar')).status_code, 404)

    def test_user_with_group_permission_sees_card(self):
        """Check that a user granted order permission can fetch the order card."""
        self.basic.user_permissions.add(Permission.objects.get(codename='view_order'))
        basic = APIClient()
        basic.force_authenticate(self.basic)
        self.assertEqual(basic.get(data_url('orders_to_validate')).status_code, 200)

    def test_invoice_kpis(self):
        """Check invoice, cancellation and rebilling totals and user scope."""
        invoice_type = InvoiceType.objects.create(token='F', name='Factura')
        today = timezone.localdate()
        last_month = today.replace(day=1) - datetime.timedelta(days=1)
        Invoice.objects.bulk_create([
            Invoice(token='i1', type=invoice_type, is_confirmed=True, issue_date=today, total_final=Decimal('100')),
            Invoice(token='i2', type=invoice_type, is_confirmed=True, issue_date=today, total_final=Decimal('50')),
            Invoice(token='i3', type=invoice_type, is_confirmed=False, issue_date=today, total_final=Decimal('70')),
            Invoice(token='i4', type=invoice_type, is_confirmed=True, issue_date=last_month, total_final=Decimal('30')),
            Invoice(token='cn', type=invoice_type, is_confirmed=True, is_suppressed=True, issue_date=today, total_final=Decimal('-40')),
            Invoice(token='rb', type=invoice_type, is_confirmed=True, refactored_token='i9', issue_date=today, total_final=Decimal('20')),
            Invoice(token='orig', type=invoice_type, is_confirmed=True, return_token='cn', suppressed_by=self.admin, issue_date=last_month, total_final=Decimal('40')),
        ])

        data = self.client.get(data_url('invoices_issued', period='month')).data['data']
        self.assertEqual((data['count'], data['amount']), (3, Decimal('170')))
        self.assertEqual((data['previous_count'], data['previous_amount']), (2, Decimal('70')))

        data = self.client.get(data_url('invoice_cancellations', period='month')).data['data']
        self.assertEqual((data['count'], data['amount']), (1, Decimal('-40')))
        data = self.client.get(data_url('invoice_cancellations', period='month', only_mine='true')).data['data']
        self.assertEqual(data['count'], 1)
        other = APIClient()
        other.force_authenticate(User.objects.create_superuser(username='admin2', password='x'))
        self.assertEqual(other.get(data_url('invoice_cancellations', only_mine='true')).data['data']['count'], 0)

        data = self.client.get(data_url('rebillings', period='month')).data['data']
        self.assertEqual((data['count'], data['amount']), (1, Decimal('20')))

    def test_orders_to_validate(self):
        """Check validation counts and filtering to orders created by the user."""
        to_validate = OrderStatus.objects.create(token='2', name='Per validar')
        other = OrderStatus.objects.create(token='1', name='Pendent')
        Order.objects.create(token='o1', status=to_validate, created_by=self.admin)
        Order.objects.create(token='o2', status=to_validate, created_by=self.basic)
        Order.objects.create(token='o3', status=other)

        data = self.client.get(data_url('orders_to_validate')).data['data']
        self.assertEqual(data['count'], 2)
        self.assertEqual(data['status_id'], to_validate.id)
        data = self.client.get(data_url('orders_to_validate', scope='created_by_me')).data['data']
        self.assertEqual([o['token'] for o in data['items']], ['o1'])

    def test_reading_batches_progress(self):
        """Check pending batch progress excludes control readings."""
        pending = ReadingBatchStatus.objects.create(token='1', name='Pendent')
        billed = ReadingBatchStatus.objects.create(token='3', name='Facturat')
        batch = ReadingBatch.objects.create(name='Lot actual', status=pending)
        ReadingBatch.objects.create(name='Lot vell', status=billed)
        Reading.objects.bulk_create([
            Reading(batch=batch, reading_value=Decimal('10')),
            Reading(batch=batch, reading_value=None),
            Reading(batch=batch, reading_value=None),
            Reading(batch=batch, reading_value=Decimal('5')),
            Reading(batch=batch, reading_value=Decimal('5'), is_control=True),
        ])

        data = self.client.get(data_url('reading_batches_in_progress')).data['data']
        self.assertEqual(data['count'], 1)
        item = data['items'][0]
        self.assertEqual((item['readings_total'], item['readings_read'], item['progress']), (4, 2, 50))


class TestUserIsolation(DashboardTestCase):
    """Cada usuari té la seva disposició; cap usuari veu ni modifica la d'un altre."""

    def test_layout_is_per_user(self):
        """Check that saving and resetting layouts affect only their owner."""
        other = User.objects.create_superuser(username='admin_b', password='x')
        other_client = APIClient()
        other_client.force_authenticate(other)

        self.client.put(LAYOUT_URL, {'layout': [{'id': 'a1', 'key': 'calendar'}]}, format='json')

        # Un altre usuari (p. ex. al mateix navegador després de canviar de sessió) veu la seva
        response = other_client.get(LAYOUT_URL)
        self.assertTrue(response.data['is_default'])
        self.assertNotIn('a1', [c['id'] for c in response.data['layout']])

        other_client.put(LAYOUT_URL, {'layout': [{'id': 'b1', 'key': 'rebillings'}]}, format='json')
        self.assertEqual([c['id'] for c in self.client.get(LAYOUT_URL).data['layout']], ['a1'])
        self.assertEqual(UserDashboard.objects.count(), 2)

        # Restablir només afecta qui ho fa
        other_client.delete(LAYOUT_URL)
        self.assertEqual([c['id'] for c in self.client.get(LAYOUT_URL).data['layout']], ['a1'])

    def test_same_layout_from_any_session(self):
        """Check that another session for the same user retrieves the saved layout."""
        # La disposició és al servidor: una sessió nova (pestanya, incògnit, altre equip) la recupera
        self.client.put(LAYOUT_URL, {'layout': [{'id': 'a1', 'key': 'calendar', 'size': 'md'}]}, format='json')
        new_session = APIClient()
        new_session.force_authenticate(self.admin)
        self.assertEqual(new_session.get(LAYOUT_URL).data['layout'], [{'id': 'a1', 'key': 'calendar', 'size': 'md', 'config': {}}])

    def test_stored_card_without_permission_is_hidden(self):
        """Check that saved cards are hidden when their permission is absent."""
        UserDashboard.objects.create(user=self.basic, layout=[{'key': 'rebillings'}, {'key': 'calendar'}])
        basic = APIClient()
        basic.force_authenticate(self.basic)
        self.assertEqual([c['key'] for c in basic.get(LAYOUT_URL).data['layout']], ['calendar'])

    def test_anonymous_is_rejected(self):
        """Check that dashboard endpoints reject unauthenticated requests."""
        anonymous = APIClient()
        for url in [LAYOUT_URL, CARDS_URL, data_url('tasks_today')]:
            self.assertIn(anonymous.get(url).status_code, (401, 403))
        self.assertIn(anonymous.put(LAYOUT_URL, {'layout': []}, format='json').status_code, (401, 403))

    def test_tasks_card_only_shows_visible_tasks(self):
        """Check that task cards include only personal or shared tasks for the scope."""
        from notification.models import CalendarTask
        today = timezone.localdate()
        CalendarTask.objects.create(name='De l\'admin', set_date=today, user=self.admin)
        CalendarTask.objects.create(name='Del basic', set_date=today, user=self.basic)
        CalendarTask.objects.create(name='De tothom', set_date=today, user=None)

        names = {t['name'] for t in self.client.get(data_url('tasks_today')).data['data']['items']}
        self.assertEqual(names, {'De l\'admin', 'De tothom'})
        names = {t['name'] for t in self.client.get(data_url('tasks_today', scope='mine')).data['data']['items']}
        self.assertEqual(names, {'De l\'admin'})


class TestLayoutValidation(DashboardTestCase):

    def test_malformed_items_do_not_crash(self):
        """Check malformed configuration is normalized and invalid keys are rejected."""
        response = self.client.put(LAYOUT_URL, {'layout': [
            {'key': 'invoices_issued', 'config': 'no és un diccionari'},
            {'key': 'calendar', 'config': ['llista']},
        ]}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['layout'][0]['config'], {'period': 'month'})
        self.assertEqual(response.data['layout'][1]['config'], {})

        response = self.client.put(LAYOUT_URL, {'layout': [{'key': ['calendar']}]}, format='json')
        self.assertEqual(response.status_code, 400)
