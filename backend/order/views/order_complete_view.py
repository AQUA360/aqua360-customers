from rest_framework import status, views
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions

from ..models import Order, OrderStatus
from coredata.models import ConfigProject
from ..utils.order_service import order_complete, order_invalidate
from ..services.rabbit import publish_order_invalidation_event
from ..serializers.order_serializer import OrderSerializer

class CompleteOrderView(views.APIView):
    permission_classes = [IsAuthenticated, DjangoModelPermissions]
    queryset = Order.objects.all().order_by('-created_at')
    
    def put(self, request, order_id):
        try:
            # Cridar la funció de servei
            order = order_complete(request.user, order_id)
            # Serialitzar el ContractRequest actualitzat
            serializer = OrderSerializer(order)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Order.DoesNotExist:
            return Response({"error": "Order no trobat."}, status=status.HTTP_404_NOT_FOUND)
        except ConfigProject.DoesNotExist:
            return Response({"error": "Configuració requerida no trobat."}, status=status.HTTP_400_BAD_REQUEST)
        except OrderStatus.DoesNotExist:
            return Response({"error": "Status 'pendent' no trobat."}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            print(e)
            return Response({"error": "Ha ocorregut un error inesperat."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
class InvalidateOrderView(views.APIView):
    permission_classes = [IsAuthenticated, DjangoModelPermissions]
    queryset = Order.objects.all().order_by('-created_at')
    
    def put(self, request, order_id):
        try:
            # Cridar la funció de servei
            order = order_invalidate(request.user, order_id)
            
            publish_order_invalidation_event(order)  # Publicar evento de invalidación
            
            # Serialitzar el ContractRequest actualitzat
            serializer = OrderSerializer(order)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Order.DoesNotExist:
            return Response({"error": "Order no trobat."}, status=status.HTTP_404_NOT_FOUND)
        except ConfigProject.DoesNotExist:
            return Response({"error": "Configuració requerida no trobat."}, status=status.HTTP_400_BAD_REQUEST)
        except OrderStatus.DoesNotExist:
            return Response({"error": "Status 'pendent' no trobat."}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            print(e)
            return Response({"error": "Ha ocorregut un error inesperat."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)