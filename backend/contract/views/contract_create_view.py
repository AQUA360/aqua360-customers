# contract/views/contract_request_finalize_view.py

from rest_framework import status, views
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions

from contract.models import ContractRequest,Contract
from coredata.models import ConfigProject
from order.models import OrderStatus
from ..utils.contract_service import contract_create
from contract.serializers.contract_serializer import ContractSerializer
from contract.permissions import ContractRequestPermission
from contract.utils.contract_request_service import contract_request_change_status

class ContractCreateView(views.APIView):
    permission_classes = [IsAuthenticated, ContractRequestPermission]
    def get_queryset(self):
        return Contract.objects.all()
    
    def put(self, request, contract_request_id):
        try:
            # Cridar la funció de servei
            contract = contract_create(request.user, contract_request_id)
            # Serialitzar el ContractRequest actualitzat
            serializer = ContractSerializer(contract)
            # passem el status del contract_request a finalitzat
            # 4. Actualitzar l'estat del ContractRequest
            contract_request = ContractRequest.objects.get(id=contract_request_id)
            contract_request_finalize_token_config = ConfigProject.objects.get(token='contract_request_finalize_token')
            if contract_request.status.token != contract_request_finalize_token_config.value:
                contract_request_change_status(request.user, contract_request, contract_request_finalize_token_config.value)

            return Response(serializer.data, status=status.HTTP_200_OK)
        except ContractRequest.DoesNotExist:
            return Response({"error": "ContractRequest no trobat."}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"error": "Ha ocorregut un error inesperat."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
