import datetime
from types import SimpleNamespace
from unittest import mock

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from billing.models import PaymentRemittance
from contract.models import Contract, ContractLog
from coredata.models import Address, City
from service.models import SupplyPoint
from statistics.utils.daily_activity_service import (
    build_activity_by_city,
    generate_daily_activity_summary_report,
    get_activity_sources,
)

DAY = datetime.date(2026, 3, 10)


class DailyActivityByCityTests(TestCase):
    """L'Excel del resum d'activitat: taula de conceptes i repartiment per municipi."""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create(username='oficina', first_name='Anna', last_name='Oficina')
        city_a = City.objects.create(token='A', name='Municipi A')
        city_b = City.objects.create(token='B', name='Municipi B')
        sp_a, sp_b = SupplyPoint.objects.bulk_create([
            SupplyPoint(address=Address.objects.create(city=city_a)),
            SupplyPoint(address=Address.objects.create(city=city_b)),
        ])
        cls.contract_a, cls.contract_b = Contract.objects.bulk_create([
            Contract(token='CA', supply_point_default=sp_a),
            Contract(token='CB', supply_point_default=sp_b),
        ])
        when = timezone.make_aware(datetime.datetime.combine(DAY, datetime.time(10)))
        logs = ContractLog.objects.bulk_create([
            ContractLog(contract=cls.contract_a, field_name='payment', user=cls.user),
            ContractLog(contract=cls.contract_a, field_name='tenant', user=cls.user),
            ContractLog(contract=cls.contract_b, field_name='payment', user=cls.user),
        ])
        ContractLog.objects.filter(id__in=[log.id for log in logs]).update(created_at=when)
        PaymentRemittance.objects.bulk_create([
            PaymentRemittance(token='R1', sent_by=cls.user, sent_at=when, is_return=False),
        ])

    def test_every_source_city_path_is_a_valid_lookup(self):
        # Una consulta per font: si algun camí de municipi no existeix, peta aquí.
        build_activity_by_city([self.user.id], datetime.date(2020, 1, 1), DAY)
        self.assertTrue(all(isinstance(source.city_paths, tuple) for source in get_activity_sources()))

    def test_counts_are_split_by_supply_point_city(self):
        by_city = build_activity_by_city([self.user.id], DAY, DAY)

        self.assertEqual(by_city['Municipi A']['contract_logs'][self.user.id], 2)
        self.assertEqual(by_city['Municipi B']['contract_logs'][self.user.id], 1)
        # Una remesa no és de cap municipi.
        self.assertEqual(by_city[None]['remittances_sent'][self.user.id], 1)

    def test_blank_city_falls_back_to_the_next_path(self):
        from order.models import Order

        blank_sp = SupplyPoint.objects.bulk_create([SupplyPoint(address=Address.objects.create(city_name=''))])[0]
        contract = Contract.objects.bulk_create([Contract(token='CX', supply_point_default=blank_sp)])[0]
        order = Order.objects.bulk_create([
            Order(contract=contract, supply_point=self.contract_b.supply_point_default, created_by=self.user),
        ])[0]
        Order.objects.filter(id=order.id).update(
            created_at=timezone.make_aware(datetime.datetime.combine(DAY, datetime.time(11))),
        )

        by_city = build_activity_by_city([self.user.id], DAY, DAY)

        self.assertEqual(by_city['Municipi B']['orders_created'][self.user.id], 1)

    def _generate(self):
        captured = {}

        def fake_save_report(content, filename, name, type_id, start_date, end_date):
            captured['workbook'] = content
            return 1

        request = SimpleNamespace(data={
            'user_ids': [self.user.id], 'date_from': DAY.isoformat(), 'date_to': DAY.isoformat(),
        })
        with mock.patch('statistics.utils.daily_activity_service.save_report', side_effect=fake_save_report):
            _result, document_id, _filename = generate_daily_activity_summary_report(request)
        self.assertEqual(document_id, 1)
        return captured['workbook']

    def test_summary_sheet_has_concepts_with_category_subtotals_and_total(self):
        workbook = self._generate()

        self.assertEqual(workbook.sheetnames, ['Resum', 'Per municipi', 'Detall'])
        # Una columna per persona i el total.
        rows = [row[:3] for row in workbook['Resum'].iter_rows(values_only=True)]
        start = rows.index(('Concepte', 'Anna Oficina', 'Total'))
        table = rows[start + 1:rows.index(('TOTAL', 4, 4)) + 1]
        self.assertIn(('Modificacions de contracte', 3, 3), table)
        self.assertIn(('Gestions de contracte', 3, 3), table)
        # El subtotal va després de les accions de la seva categoria.
        self.assertLess(table.index(('Modificacions de contracte', 3, 3)), table.index(('Gestions de contracte', 3, 3)))
        self.assertEqual(table[-1], ('TOTAL', 4, 4))

    def test_city_sheet_has_one_table_per_city(self):
        workbook = self._generate()

        rows = list(workbook['Per municipi'].iter_rows(values_only=True))
        first_column = [row[0] for row in rows]
        self.assertEqual(rows[0][:2], ('Municipi', 'Total'))
        self.assertIn(('Municipi A', 2), [row[:2] for row in rows[1:4]])
        self.assertIn('Sense municipi', first_column)
        # Taula del municipi A: columna per usuari i total.
        header = rows[first_column.index('Municipi A', 4) + 1]
        self.assertEqual(header[:3], ('Concepte', 'Anna Oficina', 'Total'))
        self.assertIn(('Modificacions de contracte', 2, 2), [row[:3] for row in rows])
