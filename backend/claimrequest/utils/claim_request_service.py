from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
import datetime
from django.utils import timezone
from billing.models import Invoice, InvoiceStatus
from claimrequest.models import ClaimRequest, ClaimRequestStatus, ClaimRequestStepTemplate, ClaimRequestStep
from claimrequest.serializers import ClaimRequestSerializer
from contract.models import Bail, Contract
from coredata.models import ConfigProject, Person
from order.models import Order, OrderStatus
from django.db.models import Count, Sum

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