import json

from coredata.models import ConfigProject
from ..models import Order
from service.models import Meter
from django.utils import timezone
from service.services.meter_change_service import MeterChangeService


def _has_value(value):
    """0 és un valor vàlid; només és buit None o un text en blanc."""
    if value is None:
        return False
    if isinstance(value, str):
        return value.strip() != ''
    return True


class OrderChangeMeterValidationService:
    """
    Valida i aplica el canvi de comptador d'una Order llegint les respostes
    dels seus OrderReport/OrderFormSubmission i comparant-les amb el mapeig
    de camps parametritzat a ConfigProject
    (token: change_meter_field_mapping).
    """

    def __init__(self, order: Order):
        self.order = order

    def _field_mapping(self):
        config = ConfigProject.objects.get(
            token='change_meter_field_mapping'
        )
        return json.loads(config.value)

    def _all_answers(self):
        """
        Recull totes les respostes (token -> response) de tots els
        informes de l'ordre, mirant els OrderFormSubmission vinculats.
        """
        values = {}

        for report in self.order.reports.all():
            submission = getattr(
                report,
                'orderformsubmission',
                None
            )

            if not submission:
                continue

            for field in (submission.filled_form or []):
                if isinstance(field, dict) and field.get('token'):
                    values[field['token']] = field.get('response')

        return values

    def _resolve_supply_point(self):
        return self.order.supply_point

    def validate(self):
        mapping = self._field_mapping()
        answers = self._all_answers()

        missing = [
            m['form_field']
            for m in mapping
            if not _has_value(answers.get(m['form_field']))
        ]

        return {
            'can_apply': len(missing) == 0,
            'missing_fields': missing,
        }

    def preview(self):
        answers = self._all_answers()

        mapping = {
            m['customers_field']: answers.get(m['form_field'])
            for m in self._field_mapping()
        }

        supply_point = self._resolve_supply_point()

        supply_point_data = None
        system_meter = None

        if supply_point:
            supply_point_data = {
                'id': supply_point.id,
                'token': supply_point.token,
                'address': (
                    str(supply_point.address)
                    if supply_point.address
                    else None
                ),
            }

            system_meter = supply_point.meter

        meter_old_code = mapping.get('meter_old')
        meter_new_code = mapping.get('meter_new')

        meter_new = (
            Meter.objects.filter(code=meter_new_code).first()
            if meter_new_code
            else None
        )

        return {
            'supply_point': supply_point_data,
            'meter_old': {
                'form_code': meter_old_code,
                'system_meter': (
                    {
                        'id': system_meter.id,
                        'code': system_meter.code,
                    }
                    if system_meter
                    else None
                ),
                'matches': bool(
                    system_meter
                    and meter_old_code
                    and system_meter.code == meter_old_code
                ),
            },
            'reading_old': mapping.get('reading_old'),
            'meter_new': {
                'form_code': meter_new_code,
                'exists': meter_new is not None,
                'meter': (
                    {
                        'id': meter_new.id,
                        'code': meter_new.code,
                    }
                    if meter_new
                    else None
                ),
            },
            'reading_new': mapping.get('reading_new'),
        }

    def apply(self, user):
        result = self.validate()
        if not result['can_apply']:
            raise ValueError(result['missing_fields'])

        answers = self._all_answers()
        mapping = self._field_mapping()
        data = {m['customers_field']: answers.get(m['form_field']) for m in mapping}

        supply_point = self._resolve_supply_point()
        if not supply_point:
            raise ValueError(['supply_point'])

        new_meter = Meter.objects.filter(code=data.get('meter_new')).first()
        if not new_meter:
            raise ValueError(['meter_new'])

        prev_meter = supply_point.meter

        service = MeterChangeService(user=user)
        service.apply(
            supply_point_id=supply_point.id,
            prev_meter_id=prev_meter.id if prev_meter else None,
            new_meter_id=new_meter.id,
            origin='order_change_meter',
            change_date=None,  # cau al fallback date.today() dins MeterChangeService
            previous_reading_data={
                'reading_value': data.get('reading_old'),
                'calculated_value': data.get('reading_old'),
                'is_close': True,
                'leak_value': 0,
            },
            new_reading_data={
                'reading_value': data.get('reading_new'),
                'calculated_value': data.get('reading_new'),
                'is_close': False,
                'leak_value': 0,
            },
        )

        self.order.change_meter_applied_at = timezone.now()
        self.order.change_meter_applied_by = user
        self.order.save(update_fields=['change_meter_applied_at', 'change_meter_applied_by'])

        return {'applied': True, 'data': data}