import datetime
from unittest import mock

from django.contrib.auth.models import Permission, User
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from coredata.models import ConfigProject
from notification.models import CalendarTask, CalendarTaskRecurrence, Notification, NotificationPreference
from notification.tasks import notify_today_tasks, send_daily_tasks_email
from notification.utils import recurrence as recurrence_utils
from notification.utils.auto_tasks import CHANGE_METER_PENDING, sync_change_meter_task
from order.models import Order, OrderStatus, OrderType

TASK_URL = '/notification/calendar-task/'


def make_user(username, **kwargs):
    """Create a test user with calendar task model permissions."""
    user = User.objects.create_user(username=username, password='x', **kwargs)
    user.user_permissions.add(*Permission.objects.filter(content_type__app_label='notification', codename__endswith='calendartask'))
    return user


class TestRecurrenceRule(TestCase):

    def test_weekly_on_selected_weekdays(self):
        """Check that weekly recurrence generates only the selected weekdays."""
        # 2026-10-05 és dilluns
        recurrence = CalendarTaskRecurrence(
            frequency='weekly', interval=1, weekdays=[0, 2], start_date=datetime.date(2026, 10, 5),
        )
        dates = recurrence_utils.occurrence_dates(recurrence, datetime.date(2026, 10, 5), datetime.date(2026, 10, 18))
        self.assertEqual(dates, [
            datetime.date(2026, 10, 5), datetime.date(2026, 10, 7),
            datetime.date(2026, 10, 12), datetime.date(2026, 10, 14),
        ])

    def test_monthly_with_interval_and_end_date(self):
        """Check that monthly intervals respect the recurrence end date."""
        recurrence = CalendarTaskRecurrence(
            frequency='monthly', interval=2, start_date=datetime.date(2026, 1, 15), end_date=datetime.date(2026, 6, 1),
        )
        dates = recurrence_utils.occurrence_dates(recurrence, datetime.date(2026, 1, 1), datetime.date(2026, 12, 31))
        self.assertEqual(dates, [datetime.date(2026, 1, 15), datetime.date(2026, 3, 15), datetime.date(2026, 5, 15)])

    def test_generate_is_idempotent(self):
        """Check that repeated generation does not duplicate existing occurrences."""
        today = timezone.localdate()
        recurrence = CalendarTaskRecurrence.objects.create(frequency='daily', start_date=today, name='Diària')
        created = recurrence_utils.generate_occurrences(recurrence, until=today + datetime.timedelta(days=4))
        self.assertEqual(created, 5)
        recurrence.generated_until = None
        self.assertEqual(recurrence_utils.generate_occurrences(recurrence, until=today + datetime.timedelta(days=4)), 0)
        self.assertEqual(recurrence.tasks.count(), 5)


class TestCalendarTaskApi(TestCase):

    def setUp(self):
        """Authenticate a calendar task user and record today for API tests."""
        self.user = make_user('tasques')
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.today = timezone.localdate()

    def test_create_recurring_task_generates_occurrences(self):
        """Check that creating a weekly series generates occurrences for its owner."""
        response = self.client.post(TASK_URL, {
            'name': 'Revisar dipòsit',
            'set_date': self.today.isoformat(),
            'recurrence_rule': {'frequency': 'weekly', 'interval': 1, 'weekdays': []},
        }, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data['set_date'], self.today.isoformat())
        recurrence = CalendarTaskRecurrence.objects.get()
        tasks = recurrence.tasks.order_by('set_date')
        self.assertGreater(tasks.count(), 10)
        self.assertEqual(tasks[1].set_date, self.today + datetime.timedelta(days=7))
        self.assertTrue(all(t.user_id == self.user.id for t in tasks))

    def test_update_series_changes_only_future_pending(self):
        """Check that series edits preserve earlier and completed occurrences."""
        self.client.post(TASK_URL, {
            'name': 'Original', 'set_date': self.today.isoformat(),
            'recurrence_rule': {'frequency': 'daily', 'interval': 1},
        }, format='json')
        tasks = list(CalendarTask.objects.order_by('set_date')[:4])
        CalendarTask.objects.filter(pk=tasks[3].pk).update(task_done=True)

        response = self.client.patch(f'{TASK_URL}{tasks[1].id}/', {'name': 'Nou', 'apply_to_series': True}, format='json')
        self.assertEqual(response.status_code, 200, response.data)

        names = dict(CalendarTask.objects.values_list('id', 'name'))
        self.assertEqual(names[tasks[0].id], 'Original')
        self.assertEqual(names[tasks[1].id], 'Nou')
        self.assertEqual(names[tasks[2].id], 'Nou')
        self.assertEqual(names[tasks[3].id], 'Original')  # ja feta
        self.assertEqual(CalendarTaskRecurrence.objects.get().name, 'Nou')

    def test_delete_series_from_occurrence(self):
        """Check that deleting future occurrences also stops further generation."""
        self.client.post(TASK_URL, {
            'name': 'Diària', 'set_date': self.today.isoformat(),
            'recurrence_rule': {'frequency': 'daily', 'interval': 1},
        }, format='json')
        tasks = list(CalendarTask.objects.order_by('set_date')[:3])
        response = self.client.delete(f'{TASK_URL}{tasks[2].id}/?series=true')
        self.assertEqual(response.status_code, 204)
        self.assertEqual(CalendarTask.objects.count(), 2)
        recurrence = CalendarTaskRecurrence.objects.get()
        self.assertEqual(recurrence.end_date, tasks[1].set_date)
        # La generació diària ja no n'afegeix de noves
        self.assertEqual(recurrence_utils.generate_occurrences(recurrence), 0)

    def test_marking_done_records_who_and_when(self):
        """Check completion records the user and time and reopening clears the time."""
        task = CalendarTask.objects.create(name='Puntual', set_date=self.today, user=self.user)
        response = self.client.patch(f'{TASK_URL}{task.id}/', {'task_done': True}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        task.refresh_from_db()
        self.assertIsNotNone(task.done_at)
        self.assertEqual(task.done_by, self.user)

        self.client.patch(f'{TASK_URL}{task.id}/', {'task_done': False}, format='json')
        task.refresh_from_db()
        self.assertIsNone(task.done_at)

    def test_summary_and_overdue_filter(self):
        """Check summary counts and overdue filtering respect task visibility."""
        other = make_user('altre')
        CalendarTask.objects.create(name='Avui', set_date=self.today, user=self.user)
        CalendarTask.objects.create(name='Ahir', set_date=self.today - datetime.timedelta(days=1), user=None)
        CalendarTask.objects.create(name='D\'un altre', set_date=self.today, user=other)

        response = self.client.get(f'{TASK_URL}summary/')
        self.assertEqual(response.data, {'today': 1, 'overdue': 1})

        response = self.client.get(f'{TASK_URL}?overdue=true')
        self.assertEqual([t['name'] for t in response.data['results']], ['Ahir'])


class TestImmediateTaskNotification(TestCase):
    """Les tasques per a avui s'avisen just després de desar-les, sense esperar a la nit."""

    def setUp(self):
        """Authenticate a task user for notification tests with commit callbacks."""
        self.user = make_user('immediata')
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.today = timezone.localdate()

    def post(self, data):
        """Create a task, execute commit callbacks and assert a successful response."""
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(TASK_URL, data, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        return response

    def notifications(self):
        """Return calendar notifications belonging to the test user."""
        return Notification.objects.filter(user=self.user, module='notification', entity='calendar')

    def test_task_for_today_notifies_on_save(self):
        """Check a task due today notifies on save and is not notified again nightly."""
        response = self.post({'name': 'Trucar al client', 'set_date': self.today.isoformat()})
        notification = self.notifications().get()
        self.assertIn('Trucar al client', notification.description)
        self.assertEqual(notification.object_id, self.today.isoformat())
        self.assertIsNotNone(CalendarTask.objects.get(pk=response.data['id']).notified_at)

        # La tasca nocturna ja no la torna a avisar
        self.assertEqual(notify_today_tasks()['notified_tasks'], 0)

    def test_future_task_notifies_when_moved_to_today(self):
        """Check moving a task to today notifies once despite later edits."""
        response = self.post({'name': 'Demà', 'set_date': (self.today + datetime.timedelta(days=1)).isoformat()})
        self.assertFalse(self.notifications().exists())

        with self.captureOnCommitCallbacks(execute=True):
            self.client.patch(f"{TASK_URL}{response.data['id']}/", {'set_date': self.today.isoformat()}, format='json')
        self.assertEqual(self.notifications().count(), 1)

        # Editar-la un altre cop no genera una altra notificació
        with self.captureOnCommitCallbacks(execute=True):
            self.client.patch(f"{TASK_URL}{response.data['id']}/", {'name': 'Avui'}, format='json')
        self.assertEqual(self.notifications().count(), 1)

    def test_recurring_task_starting_today_notifies_only_today(self):
        """Check a new series notifies only its occurrence due today."""
        self.post({
            'name': 'Diària', 'set_date': self.today.isoformat(),
            'recurrence_rule': {'frequency': 'daily', 'interval': 1},
        })
        self.assertEqual(self.notifications().count(), 1)
        self.assertEqual(CalendarTask.objects.filter(notified_at__isnull=False).count(), 1)
        self.assertGreater(CalendarTask.objects.filter(notified_at__isnull=True).count(), 1)

    def test_done_task_is_not_notified(self):
        """Check that creating an already completed task sends no notification."""
        self.post({'name': 'Ja feta', 'set_date': self.today.isoformat(), 'task_done': True})
        self.assertFalse(self.notifications().exists())


class TestTaskIsolation(TestCase):
    """Les tasques privades d'un usuari no són visibles ni modificables per a un altre."""

    def setUp(self):
        """Create private and shared tasks and authenticate a different user."""
        self.owner = make_user('propietari')
        self.other = make_user('altre_usuari')
        self.today = timezone.localdate()
        self.private = CalendarTask.objects.create(name='Privada', set_date=self.today, user=self.owner)
        self.shared = CalendarTask.objects.create(name='De tothom', set_date=self.today, user=None)
        self.client = APIClient()
        self.client.force_authenticate(self.other)

    def test_other_user_cannot_read_or_modify_private_task(self):
        """Check another user cannot read, change or delete a private task."""
        url = f'{TASK_URL}{self.private.id}/'
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(self.client.patch(url, {'task_done': True}, format='json').status_code, 404)
        self.assertEqual(self.client.delete(url).status_code, 404)
        self.private.refresh_from_db()
        self.assertFalse(self.private.task_done)

    def test_lists_and_summary_only_include_visible_tasks(self):
        """Check task lists and summary counts exclude other users private tasks."""
        names = [t['name'] for t in self.client.get(f'{TASK_URL}?set_date={self.today.isoformat()}').data['results']]
        self.assertEqual(names, ['De tothom'])
        self.assertEqual(self.client.get(f'{TASK_URL}summary/').data, {'today': 1, 'overdue': 0})
        self.assertEqual(self.client.get(f'{TASK_URL}summary/?assigned=me').data, {'today': 0, 'overdue': 0})

    def test_preferences_are_per_user(self):
        """Check enabling email for one user leaves another user preferences unchanged."""
        self.client.put('/notification/preference/', {'email_daily_tasks': True}, format='json')
        owner_client = APIClient()
        owner_client.force_authenticate(self.owner)
        self.assertFalse(owner_client.get('/notification/preference/').data['email_daily_tasks'])

    def test_anonymous_is_rejected(self):
        """Check task and preference endpoints reject anonymous requests."""
        anonymous = APIClient()
        self.assertIn(anonymous.get(TASK_URL).status_code, (401, 403))
        self.assertIn(anonymous.get('/notification/preference/').status_code, (401, 403))


class TestRecurrenceEdgeCases(TestCase):

    def setUp(self):
        """Create recurrence owners and authenticate the series owner."""
        self.owner = make_user('serie_a')
        self.other = make_user('serie_b')
        self.today = timezone.localdate()
        self.client = APIClient()
        self.client.force_authenticate(self.owner)

    def create_series(self, **rule):
        """Create a series with optional rule overrides and execute commit callbacks."""
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(TASK_URL, {
                'name': 'Sèrie', 'set_date': rule.pop('start', self.today).isoformat(),
                'recurrence_rule': {'frequency': 'daily', 'interval': 1, **rule},
            }, format='json')
        return response

    def test_series_of_other_user_cannot_be_changed_from_shared_occurrence(self):
        """Check a shared occurrence grants no access to edit its private series."""
        self.create_series()
        shared = CalendarTask.objects.order_by('set_date')[1]
        CalendarTask.objects.filter(pk=shared.pk).update(user=None)

        other = APIClient()
        other.force_authenticate(self.other)
        url = f'{TASK_URL}{shared.id}/'
        response = other.patch(url, {'name': 'Canviat', 'apply_to_series': True, 'user_id': self.other.id}, format='json')
        self.assertEqual(response.status_code, 403)
        self.assertEqual(other.delete(f'{url}?series=true').status_code, 403)

        self.assertFalse(CalendarTask.objects.filter(user=self.other).exists())
        self.assertFalse(CalendarTask.objects.filter(name='Canviat').exists())
        self.assertEqual(CalendarTaskRecurrence.objects.get().user, self.owner)

        # Sí que pot editar només aquesta ocurrència, que és de tothom
        self.assertEqual(other.patch(url, {'name': 'Només aquesta'}, format='json').status_code, 200)

    def test_series_starting_beyond_horizon(self):
        """Check a series starting beyond the usual horizon still has an occurrence."""
        start = self.today + datetime.timedelta(days=200)
        response = self.create_series(start=start, frequency='yearly')
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data['set_date'], start.isoformat())

    def test_end_date_before_start_is_rejected(self):
        """Check recurrence validation rejects an end date before its start."""
        response = self.create_series(end_date=(self.today - datetime.timedelta(days=1)).isoformat())
        self.assertEqual(response.status_code, 400)

    def test_monthly_on_31st_uses_last_day_of_shorter_months(self):
        """Check monthly and yearly recurrence clamps dates to shorter month ends."""
        recurrence = CalendarTaskRecurrence(frequency='monthly', interval=1, start_date=datetime.date(2027, 1, 31))
        dates = recurrence_utils.occurrence_dates(recurrence, datetime.date(2027, 1, 1), datetime.date(2027, 5, 31))
        self.assertEqual(dates, [
            datetime.date(2027, 1, 31), datetime.date(2027, 2, 28), datetime.date(2027, 3, 31),
            datetime.date(2027, 4, 30), datetime.date(2027, 5, 31),
        ])
        leap = CalendarTaskRecurrence(frequency='yearly', interval=1, start_date=datetime.date(2028, 2, 29))
        self.assertEqual(
            recurrence_utils.occurrence_dates(leap, datetime.date(2028, 1, 1), datetime.date(2030, 12, 31)),
            [datetime.date(2028, 2, 29), datetime.date(2029, 2, 28), datetime.date(2030, 2, 28)],
        )

    def test_moved_task_is_notified_again(self):
        """Check moving an already notified task to today triggers a new notification."""
        task = CalendarTask.objects.create(
            name='Ja avisada', set_date=self.today - datetime.timedelta(days=5), user=self.owner, notified_at=timezone.now(),
        )
        with self.captureOnCommitCallbacks(execute=True):
            self.client.patch(f'{TASK_URL}{task.id}/', {'set_date': self.today.isoformat()}, format='json')
        self.assertEqual(Notification.objects.filter(user=self.owner).count(), 1)


class TestTaskNotifications(TestCase):

    def setUp(self):
        """Create a user with email and record today for scheduled notification tests."""
        self.user = make_user('avisos', email='avisos@example.com')
        self.today = timezone.localdate()

    def test_notifies_once_per_user_and_task(self):
        """Check due tasks are grouped per user and notified only once."""
        CalendarTask.objects.create(name='A', set_date=self.today, user=self.user)
        CalendarTask.objects.create(name='B', set_date=self.today - datetime.timedelta(days=3), user=self.user)
        CalendarTask.objects.create(name='Futura', set_date=self.today + datetime.timedelta(days=1), user=self.user)
        CalendarTask.objects.create(name='Feta', set_date=self.today, user=self.user, task_done=True)

        result = notify_today_tasks()
        self.assertEqual(result, {'notified_tasks': 2, 'notifications': 1})
        self.assertEqual(Notification.objects.filter(user=self.user).count(), 1)

        # L'endemà no es torna a avisar de les mateixes tasques
        self.assertEqual(notify_today_tasks(), {'notified_tasks': 0, 'notifications': 0})

    def test_daily_email_only_for_subscribed_users(self):
        """Check daily email includes only personal tasks for subscribed users."""
        unsubscribed = make_user('sense_correu', email='altre@example.com')
        NotificationPreference.objects.create(user=self.user, email_daily_tasks=True)
        CalendarTask.objects.create(name='A', set_date=self.today, user=self.user)
        CalendarTask.objects.create(name='B', set_date=self.today, user=unsubscribed)
        CalendarTask.objects.create(name='De tothom', set_date=self.today, user=None)

        with mock.patch('notification.utils.staff_email.send_staff_email') as send:
            result = send_daily_tasks_email()

        self.assertEqual(result, {'sent': 1})
        send.assert_called_once()
        to, subject, html = send.call_args.args
        self.assertEqual(to, 'avisos@example.com')
        self.assertIn('A', html)
        self.assertNotIn('De tothom', html)

    def test_preference_endpoint(self):
        """Check preference retrieval and updates for a user with email."""
        client = APIClient()
        client.force_authenticate(self.user)
        self.assertEqual(client.get('/notification/preference/').data, {'email_daily_tasks': False, 'has_email': True})
        response = client.put('/notification/preference/', {'email_daily_tasks': True}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(NotificationPreference.objects.get(user=self.user).email_daily_tasks)


class TestChangeMeterAutoTask(TestCase):

    def setUp(self):
        """Create order types, statuses and a creator for automatic task tests."""
        ConfigProject.objects.create(token='order_status_completed_token', value='10')
        self.creator = make_user('creador')
        self.completed = OrderStatus.objects.create(token='10', name='Tancada')
        self.in_progress = OrderStatus.objects.create(token='5', name='En curs')
        self.change_meter = OrderType.objects.create(token='change_meter', name='Canvi de comptador')
        self.other_type = OrderType.objects.create(token='read_meter', name='Lectura')

    def make_order(self, order_type):
        """Create an in-progress order of the requested type for the test creator."""
        return Order.objects.create(token=f'OT-{order_type.token}', type=order_type, status=self.in_progress, created_by=self.creator)

    def open_tasks(self, order):
        """Return unfinished meter change follow-up tasks for an order."""
        return CalendarTask.objects.filter(order=order, source_key=CHANGE_METER_PENDING, task_done=False)

    def test_closing_order_opens_task_and_applying_closes_it(self):
        """Check completing an order creates one follow-up and applying closes it."""
        order = self.make_order(self.change_meter)
        order.status = self.completed
        order.save()

        task = self.open_tasks(order).get()
        self.assertEqual(task.source, CalendarTask.SOURCE_AUTO)
        self.assertEqual(task.user, self.creator)

        # Tornar a desar l'ordre tancada no en crea una altra
        order.save()
        self.assertEqual(self.open_tasks(order).count(), 1)

        order.change_meter_applied_at = timezone.now()
        order.change_meter_applied_by = self.creator
        sync_change_meter_task(order)
        self.assertFalse(self.open_tasks(order).exists())
        task.refresh_from_db()
        self.assertTrue(task.task_done)
        self.assertEqual(task.done_by, self.creator)

    def test_task_closed_by_hand_is_not_recreated(self):
        """Check a manually completed follow-up is not recreated on another save."""
        order = self.make_order(self.change_meter)
        order.status = self.completed
        order.save()
        CalendarTask.objects.filter(order=order).update(task_done=True)

        order.save()  # qualsevol altre desat de l'ordre tancada
        self.assertEqual(CalendarTask.objects.filter(order=order).count(), 1)

    def test_other_order_types_do_not_create_tasks(self):
        """Check completing unrelated orders creates no meter change task."""
        order = self.make_order(self.other_type)
        order.status = self.completed
        order.save()
        self.assertFalse(CalendarTask.objects.filter(order=order).exists())
