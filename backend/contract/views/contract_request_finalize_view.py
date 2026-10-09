# contract/views/contract_request_finalize_view.py

from rest_framework import status, views
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions

from contract.models import ContractRequest, ContractRequestStatus
from coredata.models import ConfigProject
from order.models import OrderStatus
from contract.utils.contract_request_service import contract_request_finalize
from contract.serializers.contract_request_serializer import ContractRequestSerializer

class FinalizeContractRequestView(views.APIView):
    permission_classes = [IsAuthenticated, DjangoModelPermissions]
    queryset = ContractRequest.objects.all().order_by('-created_at')
    def put(self, request, contract_request_id):
        try:
            # Obtenir el ContractRequest i validar dades
            contract_request = ContractRequest.objects.get(id=contract_request_id)
            from contract.utils.contract_request_service import contract_request_validate_data
            errors = contract_request_validate_data(contract_request)
            if errors:
                return Response({
                    "error": "La sol·licitud conté dades incompletes o incorrectes per poder finalitzar-la.",
                    "errors": errors
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Cridar la funció de servei
            contract_request = contract_request_finalize(request.user, contract_request_id)
            # Serialitzar el ContractRequest actualitzat
            serializer = ContractRequestSerializer(contract_request, context={'request': request})
            return Response(serializer.data, status=status.HTTP_200_OK)
        except ContractRequest.DoesNotExist:
            return Response({"error": "ContractRequest no trobat."}, status=status.HTTP_404_NOT_FOUND)
        except ConfigProject.DoesNotExist:
            return Response({"error": "Configuració requerida no trobat."}, status=status.HTTP_400_BAD_REQUEST)
        except ContractRequestStatus.DoesNotExist:
            return Response({"error": "Status 'pendent' no trobat."}, status=status.HTTP_400_BAD_REQUEST)
        except OrderStatus.DoesNotExist:
            return Response({"error": "OrderStatus 'PENDING' no trobat."}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            print(f"Ha ocorregut un error inesperat: {e}")
            return Response({"error": f"Ha ocorregut un error inesperat: {e}" }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
