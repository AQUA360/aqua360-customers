import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase

from coredata.models import ConfigProject
from service.models import Meter, MeterStatus, SupplyPoint
from service.services.meter_change_service import MeterChangeService


class MeterChangeDatesTest(TestCase):
    """En un canvi de comptador, la data del canvi és la d'instal·lació del nou i la de desinstal·lació del vell."""

    CHANGE_DATE = datetime.date(2026, 9, 15)

    @classmethod
    def setUpTestData(cls):
        for token, value in (
            ('contract_active_token', 'ACTIVE'),
            ('meter_status_active_token', '1'),
            ('meter_status_inactive_token', '-1'),
        ):
            ConfigProject.objects.update_or_create(token=token, defaults={'value': value})
        cls.status_active, _ = MeterStatus.objects.get_or_create(token='1', defaults={'name': 'Actiu'})
        MeterStatus.objects.get_or_create(token='-1', defaults={'name': 'Inactiu'})
        cls.user = get_user_model().objects.create_user(username='meter-change-dates', password='x')

    def _change(self, old_meter, new_meter, supply_point, change_date=CHANGE_DATE):
        MeterChangeService(user=self.user).apply(
            supply_point_id=supply_point.id,
            prev_meter_id=old_meter.id if old_meter else None,
            new_meter_id=new_meter.id,
            origin=None,
            change_date=change_date,
            previous_reading_data={},
            new_reading_data={},
        )
        new_meter.refresh_from_db()
        if old_meter:
            old_meter.refresh_from_db()

    def test_sets_dates_when_empty(self):
        old_meter = Meter.objects.create(code='OLD-1', status=self.status_active)
        new_meter = Meter.objects.create(code='NEW-1', status=self.status_active)
        sp = SupplyPoint.objects.create(token='SP-DATES-1', meter=old_meter)

        self._change(old_meter, new_meter, sp, change_date='2026-09-15')

        self.assertEqual(new_meter.installation_at, self.CHANGE_DATE)
        self.assertEqual(old_meter.uninstallation_at, self.CHANGE_DATE)

    def test_keeps_existing_dates(self):
        installed = datetime.date(2026, 1, 1)
        uninstalled = datetime.date(2026, 2, 1)
        old_meter = Meter.objects.create(code='OLD-2', status=self.status_active, uninstallation_at=uninstalled)
        new_meter = Meter.objects.create(code='NEW-2', status=self.status_active, installation_at=installed)
        sp = SupplyPoint.objects.create(token='SP-DATES-2', meter=old_meter)

        self._change(old_meter, new_meter, sp)

        self.assertEqual(new_meter.installation_at, installed)
        self.assertEqual(old_meter.uninstallation_at, uninstalled)

    def test_old_meter_still_in_use_is_not_uninstalled(self):
        old_meter = Meter.objects.create(code='OLD-3', status=self.status_active, is_general=True)
        new_meter = Meter.objects.create(code='NEW-3', status=self.status_active)
        sp = SupplyPoint.objects.create(token='SP-DATES-3', meter=old_meter)
        SupplyPoint.objects.create(token='SP-DATES-3B', meter=old_meter)

        self._change(old_meter, new_meter, sp)

        self.assertEqual(new_meter.installation_at, self.CHANGE_DATE)
        self.assertIsNone(old_meter.uninstallation_at)
