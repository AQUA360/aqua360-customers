from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions

from contract.models import Bail
from contract.serializers.bail_serializer import BailSerializer
from contract.utils.bail_service import return_bail

class BailReturnViewSet(APIView):
  permission_classes = [IsAuthenticated, DjangoModelPermissions]
  queryset = Bail.objects.all()
  def put(self, request, *args, **kwargs):
    bail_id = self.kwargs.get('id')
        
    try:
        bail = return_bail(request.user, bail_id)
        serializer = BailSerializer(bail)
        return Response(serializer.data, status=status.HTTP_200_OK)
    except Bail.DoesNotExist:
        return Response({"error": "Bail no trobat"}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)  
    