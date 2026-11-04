from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from billing.models import Reading
from billing.utils.reading_service import get_leak_estimate
from billing.views.reading_view import ReadingViewSet
from contract.models import Contract, ContractStatus
from coredata.models import ConfigProject
from service.models import Company, Meter, MeterStatus, SupplyPoint, SupplyPointStatus


class TestLeakEstimate(TestCase):
    """
    Proposta de consum habitual i de fuita a partir del consum dels darrers anys,
    comptats des de l'inici del període de la lectura amb fuita.
    """

    @classmethod
    def setUpTestData(cls):
        ConfigProject.objects.get_or_create(token='contract_active_token', defaults={'value': 'ACTIVE'})
        ConfigProject.objects.get_or_create(token='contract_terminated_status', defaults={'value': 'TERMINATED'})
        ConfigProject.objects.get_or_create(token='invoice_status_pending_token', defaults={'value': 'PENDING'})
        ConfigProject.objects.get_or_create(token='invoice_status_cancelled_token', defaults={'value': 'CANCELLED'})
        cls.contract_status, _ = ContractStatus.objects.get_or_create(token='ACTIVE', defaults={'name': 'Alta'})
        cls.sp_status, _ = SupplyPointStatus.objects.get_or_create(token='SP_ACTIVE', defaults={'name': 'Actiu'})
        cls.meter_status, _ = MeterStatus.objects.get_or_create(token='1', defaults={'name': 'Actiu'})
        cls.company = Company.objects.create(name='Company leak estimate')
        cls.user = get_user_model().objects.create_superuser(username='leak-estimate', password='x', email='')

    def setUp(self):
        self.meter = Meter.objects.create(code='LEAK-EST', status=self.meter_status)
        self.sp = SupplyPoint.objects.create(token='LEAK-EST-SP', meter=self.meter, status=self.sp_status)
        self.other_sp = SupplyPoint.objects.create(token='LEAK-EST-SP2', status=self.sp_status)
        self.contract = Contract.objects.create(
            company=self.company, token='LEAK-EST-C', status=self.contract_status,
            is_active=True, supply_point_default=self.sp,
        )
        self.contract.supply_points.add(self.sp, self.other_sp)

        def reading(reading_date, calculated_value, days, supply_point=None, **extra):
            return Reading.objects.create(
                contract=self.contract, supply_point=supply_point or self.sp, meter=self.meter,
                reading_date=reading_date, reading_value=0, calculated_value=calculated_value,
                consumption_days=days, **extra,
            )

        # Fora de la finestra de 2 anys
        reading(date(2023, 12, 1), 300, 90)
        # Historial: 90 m3 nets cadascuna (sense fuites ni correcció d'estimades)
        reading(date(2024, 4, 1), 90, 91)
        reading(date(2025, 1, 1), 120, 275, leak_value=30)
        reading(date(2026, 1, 1), 100, 365, estimated_used=10)
        # Excloses: control, altre punt de subministrament i la mateixa lectura amb fuita
        reading(date(2025, 6, 1), 1000, 30, is_control=True)
        reading(date(2025, 6, 1), 1000, 30, supply_point=self.other_sp)
        reading(date(2026, 4, 1), 200, 90)

    def estimate(self, **kwargs):
        return get_leak_estimate(self.contract, self.sp, date(2026, 4, 1), 90, 200, **kwargs)

    def test_mean_of_last_two_years(self):
        result = self.estimate()
        self.assertEqual(result['readings_count'], 3)
        self.assertEqual(result['history_consumption'], 270)
        self.assertEqual(result['history_days'], 731)
        self.assertEqual(result['window_end'], date(2026, 1, 1))
        # 270 / 731 * 90 = 33,24
        self.assertEqual(result['habitual_consumption'], 33)
        self.assertEqual(result['leak_value'], 167)

    def test_max_statistic_from_config(self):
        ConfigProject.objects.create(token='leak_estimate_statistic', value='max')
        result = self.estimate()
        self.assertEqual(result['statistic'], 'max')
        # 90 / 91 * 90 = 89,01
        self.assertEqual(result['habitual_consumption'], 89)
        self.assertEqual(result['leak_value'], 111)

    def test_years_back_from_config(self):
        ConfigProject.objects.create(token='leak_estimate_years', value='1')
        result = self.estimate()
        self.assertEqual(result['years'], 1)
        self.assertEqual(result['readings_count'], 1)
        self.assertEqual(result['habitual_consumption'], 22)  # 90 / 365 * 90

    def test_habitual_never_exceeds_consumption(self):
        result = get_leak_estimate(self.contract, self.sp, date(2026, 4, 1), 90, 20)
        self.assertEqual(result['habitual_consumption'], 20)
        self.assertEqual(result['leak_value'], 0)

    def test_without_history(self):
        self.assertIsNone(get_leak_estimate(self.contract, self.sp, date(2023, 6, 1), 30, 50))

    def post(self, data):
        view = ReadingViewSet.as_view({'post': 'leak_estimate'})
        request = APIRequestFactory().post('/billing/reading/leak-estimate/', data, format='json')
        force_authenticate(request, user=self.user)
        return view(request)

    def test_endpoint(self):
        response = self.post({
            'contract_id': self.contract.id, 'supply_point_id': self.sp.id,
            'reading_date': '2026-04-01', 'consumption_days': 90, 'consumption': 200,
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['habitual_consumption'], 33)
        self.assertEqual(response.data['leak_value'], 167)

    def test_endpoint_invalid_and_without_history(self):
        base = {'contract_id': self.contract.id, 'supply_point_id': self.sp.id, 'consumption_days': 90}
        self.assertEqual(self.post({**base, 'reading_date': 'x', 'consumption': 200}).status_code, 400)
        self.assertEqual(self.post({**base, 'reading_date': '2026-04-01', 'consumption': 0}).status_code, 400)
        self.assertEqual(
            self.post({**base, 'reading_date': '2026-04-01', 'consumption': 200, 'statistic': 'median'}).status_code,
            400,
        )
        self.assertEqual(self.post({**base, 'reading_date': '2023-06-01', 'consumption': 200}).status_code, 422)
