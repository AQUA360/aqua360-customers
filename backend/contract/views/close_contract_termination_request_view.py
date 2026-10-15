from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions

from datetime import datetime

from billing.models import Invoice
from contract.models import Contract, ContractStatus, ContractTerminationRequest, ContractTerminationStatus
from contract.serializers.contract_termination_request_serializer import ContractTerminationRequestSerializer
from coredata.models import ConfigProject
from order.models import Order
from service.models import SupplyPointStatus

class CloseContractTerminationRequestViewSet(APIView):
  queryset = ContractTerminationRequest.objects.all()
  permission_classes = [IsAuthenticated, DjangoModelPermissions]
  def put(self, request, *args, **kwargs):
    contract_terminated_token = 'contract_terminated_status'
    # Extract data for each child model from the request
    id = self.kwargs.get('id')
    status_data = request.data.get('status')
    supply_point_status = SupplyPointStatus.objects.get(id=status_data) if status_data else None
    
    termination_request = ContractTerminationRequest.objects.get(id=id)
    termination_pending_token = ConfigProject.objects.get(token = 'contract_termination_pending_token').value
    termination_completed_token = ConfigProject.objects.get(token = 'contract_termination_completed_token').value
    contract = Contract.objects.get(id = termination_request.contract.id)
    
    token = ConfigProject.objects.get(token = contract_terminated_token).value
    
    contract_status = ContractStatus.objects.get(token = token)
    contract.status = contract_status
    contract.termination_date = datetime.now().date()
    termination_request.approved_at = datetime.now()
    # Des de l'alta (canvi de nom) es finalitza "sense factura", tret que ja es factura
    # (factura o pressupost existent, o lectura de tall cobrada a l'alta). Després se'n pot
    # generar igualment el pressupost.
    if str(request.data.get('ignore_invoice', '')).lower() == 'true' and not termination_request.bill_cut_reading \
        and not Invoice.objects.filter(contract_termination=termination_request).exists():
      termination_request.ignore_invoice = True
    orders = None
    try:
      order_status = ConfigProject.objects.get(token = 'order_status_completed_token').value
      orders = Order.objects.filter(contract_termination_request=termination_request).exclude(status__token=order_status)
    except:
      pass
    if orders:
      termination_request.status = ContractTerminationStatus.objects.get(token=termination_pending_token)
      termination_request.save()
    else:
      termination_request.status = ContractTerminationStatus.objects.get(token=termination_completed_token)
      termination_request.save()
    contract.save()
    
    # Donar de baixa el punt i el comptador si és necessari
    from contract.utils.contract_request_service import check_and_deactivate_supply_point_and_meter
    # L'estat triat només s'aplica als punts sense altres contractes actius ni sol·licituds obertes.
    check_and_deactivate_supply_point_and_meter(termination_request, supply_point_status)
    
    serializer = ContractTerminationRequestSerializer(termination_request, context={'request': request})
        
    # Return the serialized response with 202 status
    return Response(serializer.data, status=status.HTTP_202_ACCEPTED)