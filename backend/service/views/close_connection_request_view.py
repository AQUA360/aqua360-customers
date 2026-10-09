from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions

from datetime import datetime

from service.models import ConnectionRequest, Connection, ConnectionStatus
from service.serializers.connection_request_serializer import ConnectionRequestSerializer
from service.serializers.connection_serializer import ConnectionSerializer

class CloseConnectionRequestViewSet(APIView):
  permission_classes = [IsAuthenticated, DjangoModelPermissions]
  queryset = ConnectionRequest.objects.all()
  def put(self, request, *args, **kwargs):
    # Extract data for each child model from the request
    id = self.kwargs.get('id')
    print(id)
    
    connection = create_connection(id)
    
    return Response(ConnectionSerializer(connection).data, status=status.HTTP_201_CREATED)


def create_connection(connection_request_id):
  connection_request = ConnectionRequest.objects.get(id=connection_request_id)
  print("got connection request")
  default_status = ConnectionStatus.objects.get(is_default=True)
  print("got connection status")
  
  connection = Connection.objects.create(
    token = connection_request.token,
    address_street = connection_request.address_street,
    address_street_number = connection_request.address_street_number,
    address_postal_code = connection_request.address_postal_code,
    address_city = connection_request.address_city,
    exploitation = connection_request.exploitation,
    status = default_status,
    type = connection_request.type,
    installation_type = connection_request.installation_type,
    use_type = connection_request.use_type,
    valve_type = connection_request.valve_type,
    diameter = connection_request.diameter,
    material = connection_request.material,
    tank = connection_request.tank,
    dma = connection_request.dma,
    latitude = connection_request.latitude,
    longitude = connection_request.longitude,
    code_gis = connection_request.code_gis,
    flow_rate = connection_request.flow_rate,
    installation_at = datetime.now().date(),
    is_active = True
  )
  
  connection_request.connection = connection
  connection_request.save()
  
  return connection