"""
Errors del processat de la facturació (pre-factures) que es poden mostrar a l'usuari.

Quan un contracte no es pot facturar, el lot continua amb la resta i l'error es desa a
`Billing.process_errors` amb un codi, un missatge entenedor i què cal revisar. Un cop
corregit, el contracte es torna a processar (`process-contract`) i l'error desapareix.

Els missatges no porten mai el text de l'excepció (pot exposar dades internes): el
detall va al log amb `logger.exception`.
"""
import logging

from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext as _

logger = logging.getLogger(__name__)


class BillingProcessError(Exception):
  """Error conegut del processat, amb codi i missatge per a l'usuari."""

  def __init__(self, code, message, hint=None):
    super().__init__(message)
    self.code = code
    self.message = message
    self.hint = hint


def _supply_point_label(reading):
  supply_point = getattr(reading, 'supply_point', None)
  if supply_point is None:
    return None
  return supply_point.name or supply_point.token


def validate_contract_readings(readings):
  """Comprova que les lectures del contracte tenen les dades que el càlcul necessita."""
  for reading in readings:
    supply_point = _supply_point_label(reading)
    if reading.meter_id is None:
      if supply_point:
        message = _('Hi ha una lectura sense comptador al punt de subministrament %(supply_point)s.') % {'supply_point': supply_point}
      else:
        message = _('Hi ha una lectura sense comptador.')
      raise BillingProcessError(
        'reading_without_meter',
        message,
        _("Assigneu el comptador al punt o anul·leu la lectura des de «Modificar lectures», i torneu a processar el contracte."),
      )
    if reading.reading_date is None:
      raise BillingProcessError(
        'reading_without_date',
        _('Hi ha una lectura sense data de lectura.'),
        _("Poseu la data a la lectura des de «Modificar lectures» i torneu a processar el contracte."),
      )
    if reading.calculated_value is None:
      raise BillingProcessError(
        'reading_without_consumption',
        _('Hi ha una lectura sense el consum calculat.'),
        _("Reviseu la lectura des de «Modificar lectures» (valor i lectura anterior) i torneu a processar el contracte."),
      )


def dedupe_contract_readings(contract, readings):
  """
  Valida les lectures i en deixa una per comptador (la primera de la llista, que ha de
  venir ordenada per data descendent o ascendent segons el que vulgui el cridador).
  """
  validate_contract_readings(readings)
  seen = set()
  result = []
  for reading in readings:
    key = (contract.token, reading.meter.code)
    if key in seen:
      continue
    seen.add(key)
    result.append(reading)
  return result


def _exception_chain(exc):
  """L'excepció i les que l'han provocada (el servei de factures les embolcalla)."""
  seen = set()
  while exc is not None and id(exc) not in seen:
    seen.add(id(exc))
    yield exc
    exc = exc.__cause__ or exc.__context__


def classify_billing_error(exc, contract_level=True):
  """
  Tradueix una excepció del processat a {code, message, hint} per a l'usuari.

  `contract_level`: l'error és d'un sol contracte (la pista diu de revisar-lo i tornar-lo
  a processar) o de tota la facturació (configuració, que normalment ha de mirar suport).
  """
  chain = list(_exception_chain(exc))

  for err in chain:
    if isinstance(err, BillingProcessError):
      return {'code': err.code, 'message': err.message, 'hint': err.hint}

  from coredata.models import ConfigProject
  from pricing.models import Tax

  for err in chain:
    if isinstance(err, Tax.DoesNotExist):
      return {
        'code': 'missing_zero_tax',
        'message': _("No hi ha cap impost amb percentatge 0."),
        'hint': _("Creeu l'impost del 0% a la configuració d'impostos i torneu a processar el contracte."),
      }
    if isinstance(err, ConfigProject.DoesNotExist):
      return {
        'code': 'missing_config',
        'message': _("Falta un paràmetre de configuració necessari per facturar."),
        'hint': _("Contacteu amb suport per revisar la configuració del projecte."),
      }
    if isinstance(err, ObjectDoesNotExist):
      if not contract_level:
        return {
          'code': 'missing_config',
          'message': _("Falta una dada de configuració necessària per facturar."),
          'hint': _("Contacteu amb suport per revisar la configuració del projecte."),
        }
      return {
        'code': 'missing_related_data',
        'message': _("Falta una dada relacionada necessària per facturar."),
        'hint': _("Reviseu les dades del contracte (tarifes, comptadors, lectures, forma de pagament) i torneu-lo a processar."),
      }

  if not contract_level:
    return {
      'code': 'unknown',
      'message': _("Error inesperat en processar la facturació."),
      'hint': _("Torneu-ho a provar amb «Reiniciar». Si l'error es repeteix, contacteu amb suport."),
    }
  return {
    'code': 'unknown',
    'message': _("Error inesperat en generar la factura."),
    'hint': _("Reviseu les dades del contracte (tarifes, comptadors i lectures) i torneu-lo a processar. Si l'error es repeteix, contacteu amb suport."),
  }


def build_contract_error(contract, exc):
  """Entrada de `Billing.process_errors` per a un contracte que no s'ha pogut facturar."""
  return {
    'contract_id': contract.id,
    'contract_token': contract.token,
    **classify_billing_error(exc),
    'at': timezone.now().isoformat(),
  }


def upsert_billing_process_error(billing_id, entry):
  """Afegeix o substitueix l'error d'un contracte a la llista de la facturació."""
  from billing.models import Billing

  with transaction.atomic():
    billing = Billing.objects.select_for_update().only('id', 'process_errors').get(id=billing_id)
    errors = [e for e in (billing.process_errors or []) if e.get('contract_id') != entry['contract_id']]
    errors.append(entry)
    billing.process_errors = errors
    billing.save(update_fields=['process_errors'])


def remove_billing_process_errors(billing_id, contract_ids):
  """Treu els errors dels contractes indicats (ja facturats o descartats). Retorna si n'ha tret cap."""
  from billing.models import Billing

  contract_ids = {int(c) for c in contract_ids}
  with transaction.atomic():
    billing = Billing.objects.select_for_update().only('id', 'process_errors').get(id=billing_id)
    current = billing.process_errors or []
    errors = [e for e in current if e.get('contract_id') not in contract_ids]
    if len(errors) == len(current):
      return False
    billing.process_errors = errors
    billing.save(update_fields=['process_errors'])
    return True
