"""Aplica als contractes les línies acceptades d'un ACADocument rebut de l'ACA.

Es crida des del signal `assign_variables` (contract/signals.py) quan el document
passa a l'estat configurat a ConfigProject 'aca_bonification_processed':
- línia d'alta: crea la Bonification del tipus del document (ConfigProject
  'aca_cs_token' per al Cànon social, 'aca_at_token' per a l'Ampliació de trams)
  amb una Variable per cada VariableType del tipus;
- línia de tancament (TA- al nom del fitxer o dígraf "TA"/codis 20-23 a la línia):
  dona de baixa la bonificació activa d'aquest tipus.

Cada línia queda marcada (`applied_at`, `bonification`) i no es torna a aplicar.
"""
from datetime import datetime, time

from django.db import transaction
from django.db.models import Value
from django.db.models.functions import Replace
from django.utils import timezone

from coredata.models import ConfigProject
from coredata.utils.name_utils import generate_token
from contract.models import Bonification, BonificationType, Contract, Variable

# Col·lectiu de tarifa social (llista 5.3 del document 05 de l'ACA) → sufix del
# BonificationType darrere de 'aca_cs_token' (ACA-CANON-ATUR, ACA-CANON-PENSIONS...).
# Tots els clients tenen els mateixos tipus. ACA-CANON-ENTITATS no té cap codi al fitxer.
SOCIAL_COLLECTIVE_TYPE_SUFFIX = {
    'AT': 'ATUR',
    'CJ': 'PENSIONS',
    'CI': 'PENSIONS',
    'NC': 'PENSIONS',
    'RM': 'PROTECCIO',
    'NB': 'PROTECCIO',
    'FA': 'PROTECCIO',
    'LM': 'PROTECCIO',
    '90': 'EXCLUSIO',
    '92': 'EXCLUSIO',
}

TYPE_CONFIG_TOKENS = {
    'Canon Social': 'aca_cs_token',
    'Ampliació de trams': 'aca_at_token',
}


def _config_token(document):
    if document.type in TYPE_CONFIG_TOKENS:
        return TYPE_CONFIG_TOKENS[document.type]
    # Documents pujats abans de desar el tipus normalitzat: es dedueix del nom.
    main_name = (document.name or '').split('_', 1)[-1].upper()
    if main_name.startswith('CS'):
        return 'aca_cs_token'
    if main_name.startswith('AT'):
        return 'aca_at_token'
    return None


def resolve_bonification_type(document, change=None):
    config_token = _config_token(document)
    config = ConfigProject.objects.filter(token=config_token).first() if config_token else None
    if not config or not config.value:
        return None

    suffix = SOCIAL_COLLECTIVE_TYPE_SUFFIX.get((getattr(change, 'social_collective', '') or '').upper())
    if config_token == 'aca_cs_token' and suffix:
        bonification_type = BonificationType.objects.filter(token__iexact=f'{config.value}-{suffix}').first()
        if bonification_type:
            return bonification_type

    # Hi pot haver diversos tipus amb el mateix prefix (ACA-CANON-PENSIONS, ACA-TRAM-75...):
    # primer el que coincideix exactament, i si no el més antic.
    return (
        BonificationType.objects.filter(token__iexact=config.value).first()
        or BonificationType.objects.filter(token__icontains=config.value).order_by('id').first()
    )


def _bonification_types(document):
    """Tots els tipus del document (per tancar una tarifa social no se sap el col·lectiu)."""
    config_token = _config_token(document)
    config = ConfigProject.objects.filter(token=config_token).first() if config_token else None
    if not config or not config.value:
        return BonificationType.objects.none()
    return BonificationType.objects.filter(token__icontains=config.value)


def find_contract(contract_code):
    """El número de pòlissa del fitxer és el token del contracte sense '/'
    (veure `build_detail_record` a aca_bonification_export_service)."""
    code = (contract_code or '').strip()
    if not code:
        return None
    contract = Contract.objects.filter(token=code).first()
    if contract:
        return contract
    return Contract.objects.annotate(
        plain_token=Replace('token', Value('/'), Value(''))
    ).filter(plain_token=code).first()


def _variable_value(variable_type, change):
    if variable_type.data_type == 'bool':
        return 'True'
    if 'MEMBRES' in (variable_type.token or '').upper() and (change.num_persons or '').isdigit():
        return str(int(change.num_persons))
    return None


def _line_person(change, contract):
    """La persona del contracte (titular, propietari o llogater) amb el DNI de la línia, o
    el titular. No es busca el DNI a tota la taula de persones: n'hi ha de genèrics
    (99999999R) compartits per centenars de persones."""
    for person in (contract.holder, contract.owner, contract.tenant):
        if person and change.person_NIF and person.token == change.person_NIF:
            return person
    return contract.holder


def _create_bonification(document, change, contract, bonification_type):
    existing = Bonification.objects.filter(
        contract=contract, bonification_type=bonification_type, is_active=True
    ).order_by('-id').first()
    if existing:
        return existing, False

    request_date = change.request_date or document.date or timezone.now().date()
    requested_at = timezone.make_aware(datetime.combine(request_date, time.min))
    person = _line_person(change, contract)

    bonification = Bonification(
        person=person,
        contract=contract,
        bonification_type=bonification_type,
        requested_at=requested_at,
        approved_at=timezone.now(),
        start_at=request_date,
        is_active=True,
        token=generate_token(Bonification),
    )
    # Ve de l'ACA: no ha de generar una ACABonificationRequest pendent de tornar-li a enviar
    # (`track_aca_bonification_request`).
    bonification._skip_signal = True
    bonification.save()

    # El cànon social es resol per anys; l'ampliació de trams no caduca (l'ACA n'envia el tancament).
    end_at = None
    if _config_token(document) == 'aca_cs_token':
        end_at = request_date.replace(year=request_date.year + 1)

    for variable_type in bonification_type.variable_types.all():
        value = _variable_value(variable_type, change)
        if value is None and variable_type.data_type != 'bool':
            continue
        Variable.objects.create(
            contract=contract,
            bonification=bonification,
            type=variable_type,
            name=variable_type.name,
            value=value,
            start_at=request_date,
            end_at=end_at,
            token=generate_token(Variable),
        )
    return bonification, True


def _close_bonification(document, change, contract):
    """Dona de baixa totes les bonificacions actives del tipus (n'hi pot haver de
    duplicades) i retorna la més recent."""
    bonifications = list(Bonification.objects.filter(
        contract=contract, bonification_type__in=_bonification_types(document), is_active=True
    ).order_by('-id'))
    end_at = change.request_date or document.date or timezone.now().date()
    for bonification in bonifications:
        # `deactivate_bonification` (contract/signals.py) dona de baixa les variables i la
        # desvincula del contracte.
        bonification.is_active = False
        bonification.end_at = end_at
        bonification.save()
    return bonifications[0] if bonifications else None


def apply_aca_document(document):
    """Retorna un dict amb el recompte de línies aplicades, tancades i saltades."""
    result = {'created': 0, 'closed': 0, 'skipped': []}
    pending = document.document_changes.filter(accepted=True, applied_at__isnull=True).order_by('id')
    for change in pending:
        contract = find_contract(change.contract_code)
        if not contract:
            result['skipped'].append({'id': change.id, 'reason': f"No s'ha trobat el contracte '{change.contract_code}'."})
            continue

        with transaction.atomic():
            if document.closing or change.closing:
                bonification = _close_bonification(document, change, contract)
                result['closed'] += 1 if bonification else 0
            else:
                bonification_type = resolve_bonification_type(document, change)
                if not bonification_type:
                    result['skipped'].append({'id': change.id, 'reason': f"No hi ha cap tipus de bonificació configurat per a '{document.type}'."})
                    continue
                bonification, created = _create_bonification(document, change, contract, bonification_type)
                result['created'] += 1 if created else 0

            change.bonification = bonification
            change.applied_at = timezone.now()
            change.save(update_fields=['bonification', 'applied_at', 'updated_at'])

    return result
