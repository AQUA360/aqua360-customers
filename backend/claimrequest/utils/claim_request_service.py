from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
import datetime
from django.utils import timezone
from billing.models import Invoice, InvoiceStatus
from claimrequest.models import ClaimRequest, ClaimRequestStatus, ClaimRequestStepTemplate, ClaimRequestStep
from contract.models import Bail, Contract
from coredata.models import ConfigProject, Person
from order.models import Order, OrderStatus
from django.db.models import Count, Q, Sum


def closed_termination_tokens():
    """Estats que donen una baixa per tancada: cancel·lada i finalitzada (dels
    quatre possibles, amb esborrany i pendent). Sense els dos configurats no es
    pot distingir una baixa oberta d'una tancada."""
    return list(
        ConfigProject.objects.filter(
            token__in=['contract_termination_cancelled_token', 'contract_termination_completed_token']
        ).values_list('value', flat=True)
    )


def claim_letter_address(contract):
    """Adreça postal de les cartes de reclamació: la de contacte del contracte,
    després la de facturació i, si no n'hi ha cap, una adreça activa del titular.
    Mai l'adreça de subministrament, que no ha de ser on es rep el correu."""
    for person_address in (contract.address_contact, contract.address_billing):
        if person_address and person_address.is_active and person_address.address:
            return person_address.address
    if contract.holder:
        holder_addresses = contract.holder.addresses.filter(is_active=True, address__isnull=False)
        person_address = holder_addresses.filter(is_billing=True).order_by('id').first() or holder_addresses.order_by('id').first()
        if person_address:
            return person_address.address
    return None


def is_open_termination(termination):
    """Una baixa demanada però ni acabada ni cancel·lada: el contracte encara hi
    és i, per tant, encara hi ha a qui reclamar."""
    if termination is None or not termination.is_active:
        return False
    closed = closed_termination_tokens()
    if len(closed) < 2:
        return False
    return bool(termination.status and termination.status.token not in closed)


def is_closed_termination(termination):
    """Baixa finalitzada o cancel·lada. Sense els dos estats configurats, o sense
    estat a la baixa, no es pot afirmar que estigui tancada."""
    if termination is None:
        return False
    closed = closed_termination_tokens()
    if len(closed) < 2:
        return False
    return bool(termination.status and termination.status.token in closed)


def _prefer_active_contract(contracts):
    """D'entre diversos candidats, el que està d'alta; si no, el més nou."""
    active_contract_token = ConfigProject.objects.filter(
        token='contract_active_token'
    ).values_list('value', flat=True).first()
    if active_contract_token:
        contract = contracts.filter(status__token=active_contract_token).first()
        if contract:
            return contract
    return contracts.first()


def _request_supply_point_ids(contract_request):
    supply_point_ids = set(contract_request.supply_points.values_list('id', flat=True))
    if contract_request.supply_point_default_id:
        supply_point_ids.add(contract_request.supply_point_default_id)
    return supply_point_ids


def _contract_matches_request_identity(contract, contract_request):
    """El codi sol no identifica el contracte: el titular i algun punt de
    subministrament de la sol·licitud han de ser els del contracte."""
    if not contract_request.holder_id or contract.holder_id != contract_request.holder_id:
        return False
    supply_point_ids = _request_supply_point_ids(contract_request)
    if not supply_point_ids:
        return False
    if contract.supply_point_default_id in supply_point_ids:
        return True
    return contract.supply_points.filter(id__in=supply_point_ids).exists()


def contract_from_finished_request(contract_request):
    """Contracte d'una sol·licitud finalitzada que no té el vincle directe.

    Una sol·licitud finalitzada sempre va acabar en contracte, però amb dades
    migrades el contracte pot no apuntar enrere a la sol·licitud
    (`Contract.contract_request` buit). Es busca primer pel codi, que el contracte
    hereta de la sol·licitud (`contract_service._contract_create_locked`), només
    si el titular i el punt de subministrament també coincideixen. Si no, o si
    el codi el va heretar un canvi de nom, pel punt de subministrament i el
    titular. En un canvi de nom el titular canvia, per això serveix per distingir
    el contracte dels anteriors del mateix punt.
    """
    if contract_request is None:
        return None

    finalize_token = ConfigProject.objects.filter(
        token='contract_request_finalize_token'
    ).values_list('value', flat=True).first()
    if not finalize_token:
        return None
    if not contract_request.status or contract_request.status.token != finalize_token:
        return None

    if contract_request.token:
        contract = _prefer_active_contract(
            Contract.objects.filter(token=contract_request.token, is_active=True).order_by('-id')
        )
        if contract and _contract_matches_request_identity(contract, contract_request):
            return contract

    if not contract_request.holder_id:
        return None

    supply_point_ids = _request_supply_point_ids(contract_request)
    if not supply_point_ids:
        return None

    return _prefer_active_contract(
        Contract.objects.filter(
            Q(supply_points__id__in=supply_point_ids) | Q(supply_point_default_id__in=supply_point_ids),
            holder_id=contract_request.holder_id,
            is_active=True,
        ).distinct().order_by('-id')
    )


def resolve_invoice_contract(invoice):
    """Contracte al qual s'ha de reclamar una factura.

    Les factures emeses durant una sol·licitud d'alta no tenen `contract`: només
    s'hi arriba per la sol·licitud. A nivell de base de dades una sol·licitud
    admet més d'un contracte (`Contract.contract_request` no és únic), per això
    `filter().first()` i no `get()`, que petaria amb `MultipleObjectsReturned`.

    Les que només pengen d'una sol·licitud de baixa (`contract_termination`) es
    reclamen al contracte de la baixa mentre aquesta no estigui acabada, igual que
    les factures d'un contracte que ha entrat en baixa. Un cop la baixa és
    finalitzada o cancel·lada es queden sense contracte a propòsit: no hi ha ningú
    a qui reclamar-les, encara que la factura conservi `contract`.
    """
    if invoice is None:
        return None
    if invoice.contract_termination_id and is_closed_termination(invoice.contract_termination):
        return None
    if invoice.contract_id:
        return invoice.contract
    if invoice.contract_request_id:
        contract = Contract.objects.filter(
            contract_request_id=invoice.contract_request_id
        ).order_by('-id').first()
        if contract:
            return contract
        return contract_from_finished_request(invoice.contract_request)
    if invoice.contract_termination_id and is_open_termination(invoice.contract_termination):
        return invoice.contract_termination.contract
    return None


def is_claimable_contract(contract, active_status_token):
    """Un contracte de baixa (o esborrat logicament) no es pot reclamar: no se li
    pot comunicar res, perquè el filtre de destinataris només accepta contractes
    actius."""
    return bool(
        contract
        and contract.is_active
        and contract.status
        and contract.status.token == active_status_token
    )


def process_claim_request_next_step(claim_request_id):
    """
    Processa el següent pas d'una petició de reclamació
    """
    claim_request = ClaimRequest.objects.get(id=claim_request_id)
    
    # Obtenim els contractes a través de ClaimRequestPayment
    contracts = Contract.objects.filter(
        id__in=claim_request.payments.values_list('contract_id', flat=True)
    ).distinct()
    
    if contracts.count() == 0:
        return claim_request
    
    # Obtenim el següent pas
    current_step = claim_request.current_step
    if current_step and current_step.next_step:
        claim_request.current_step = current_step.next_step
        claim_request.save()
    
    return claim_request