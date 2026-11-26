import json

from coredata.models import ConfigProject
from ..models import Order
from service.models import Meter
from django.utils import timezone
from service.services.meter_change_service import (
    MeterChangeService, METER_CHANGE_ORIGIN, get_meter_assignments_elsewhere,
)


OPTIONAL_FIELDS = {'reading_new'}
# En una instal·lació no hi ha comptador sortint.
INSTALLATION_OPTIONAL_FIELDS = OPTIONAL_FIELDS | {'meter_old', 'reading_old'}

DEFAULT_INSTALL_METER_ORDER_TYPE = 'install_meter'


def install_meter_order_type_token():
    """Token del tipus d'ordre d'instal·lació de comptador (configurable)."""
    config = ConfigProject.objects.filter(token='order_type_install_meter_token').first()
    return (config.value if config and config.value else DEFAULT_INSTALL_METER_ORDER_TYPE).strip()


def is_no_meter(meter):
    """Comptador fictici (estat «sense comptador»)."""
    if not meter or not meter.status:
        return False
    config = ConfigProject.objects.filter(token='token_meter_status_no_meter').first()
    return bool(config and meter.status.token == config.value)


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

    def is_installation(self):
        order_type = self.order.type if self.order else None
        token = (order_type.token or '').lower() if order_type else ''
        return bool(token) and token == install_meter_order_type_token().lower()

    def validate(self):
        mapping = self._field_mapping()
        answers = self._all_answers()

        # La lectura inicial del comptador nou és opcional: buida val 0.
        optional = INSTALLATION_OPTIONAL_FIELDS if self.is_installation() else OPTIONAL_FIELDS
        missing = [
            m['form_field']
            for m in mapping
            if m.get('customers_field') not in optional
            and not _has_value(answers.get(m['form_field']))
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
        is_installation = self.is_installation()
        # Instal·lació: el punt no té comptador o en té un de fictici, que es retira.
        installation_ok = is_installation and (not system_meter or is_no_meter(system_meter))

        meter_new = (
            Meter.objects.filter(code=meter_new_code).first()
            if meter_new_code
            else None
        )

        return {
            'supply_point': supply_point_data,
            'is_installation': is_installation,
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
                'matches': installation_ok or bool(
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
                # Altres punts on és ara el comptador nou: cal confirmar abans d'aplicar.
                'assigned_to': (
                    get_meter_assignments_elsewhere(
                        meter_new, supply_point.id if supply_point else None
                    )
                    if meter_new
                    else []
                ),
            },
            'reading_new': mapping.get('reading_new'),
        }

    def apply(self, user, confirm_reassign=False):
        """Apply validated meter readings and replacement, then close follow-up tasks."""
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

        # El comptador fictici d'una instal·lació no té lectura de tancament.
        skip_close_reading = self.is_installation() and is_no_meter(prev_meter)

        service = MeterChangeService(user=user, source='order', order=self.order)
        service.apply(
            supply_point_id=supply_point.id,
            prev_meter_id=prev_meter.id if prev_meter else None,
            new_meter_id=new_meter.id,
            origin=METER_CHANGE_ORIGIN,
            change_date=None,  # cau al fallback date.today() dins MeterChangeService
            confirm_reassign=confirm_reassign,
            # calculated_value=None => el servei calcula el consum contra
            # l'última lectura del mateix comptador (no és el valor de lectura).
            previous_reading_data=None if skip_close_reading else {
                'reading_value': data.get('reading_old'),
                'calculated_value': None,
                'is_close': True,
                'leak_value': 0,
            },
            new_reading_data={
                'reading_value': data.get('reading_new'),
                'calculated_value': None,
                'is_close': False,
                'leak_value': 0,
            },
        )

        self.order.change_meter_applied_at = timezone.now()
        self.order.change_meter_applied_by = user
        self.order.save(update_fields=['change_meter_applied_at', 'change_meter_applied_by'])

        from notification.utils.auto_tasks import sync_change_meter_task
        sync_change_meter_task(self.order, user)

        return {'applied': True, 'data': data}