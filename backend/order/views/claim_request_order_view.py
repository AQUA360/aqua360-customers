from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

from order.models import Order

from ..utils.claim_request_order_service import create_orders_from_claim_request
from order.permissions import ClaimRequestOrderPermission

class ClaimRequestOrderView(APIView):
    permission_classes = [IsAuthenticated, ClaimRequestOrderPermission]
    queryset = Order.objects.all().order_by('-created_at')

    def post(self, request, type_token):
        try:
            # Validar el claim request
            claim_request_id = request.data.get('claim_request')
            contracts = request.data.get('contracts')
            if not claim_request_id:
                return Response({'error': 'claim_request és obligatori'}, status=status.HTTP_400_BAD_REQUEST)
            
            # Validar la data
            date_str = request.data.get('date')
            if not date_str:
                return Response({'error': 'date és obligatori'}, status=status.HTTP_400_BAD_REQUEST)
            
            # Utilitzar la funció utilitària
            created_orders, message = create_orders_from_claim_request(
                claim_request_id=claim_request_id,
                order_type_token=type_token,
                action_date=date_str,
                contracts=contracts,
                user=request.user
            )
            
            return Response({
                'message': message,
                'orders': created_orders
            }, status=status.HTTP_201_CREATED)
            
        except ValueError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR) 