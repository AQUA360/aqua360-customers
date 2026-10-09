from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter, SearchFilter

from coredata.models import Address
from coredata.serializers import AddressSerializer
from coredata.filters.address_filter import AddressFilter
from coredata.permissions import AddressPermission

class AddressViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows Address to be viewed or edited.
    """
    queryset = Address.objects.all().order_by('street__name', 'street_number__number', 'street_number__number_end', 'street_number__number_suffix', 'street_number__number_end_suffix', 'floor', 'door', 'building')
    serializer_class = AddressSerializer
    permission_classes = [IsAuthenticated, AddressPermission]

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.is_shared():
            # If shared, we don't modify the existing one.
            # Instead, we find or create a new one with the combined data.
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            new_instance = serializer.save()
            return Response(self.get_serializer(new_instance).data, status=status.HTTP_201_CREATED)
        
        return super().update(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.is_shared():
            # For partial updates on shared addresses, we must merge 
            # with current data to find/create the correct new address.
            current_data = self.get_serializer(instance).data
            merged_data = {**current_data, **request.data}
            
            # Remove read-only or problematic fields if any
            merged_data.pop('id', None)
            
            serializer = self.get_serializer(data=merged_data)
            serializer.is_valid(raise_exception=True)
            new_instance = serializer.save()
            return Response(self.get_serializer(new_instance).data, status=status.HTTP_201_CREATED)

        return super().partial_update(request, *args, **kwargs)

    filter_backends = [DjangoFilterBackend, OrderingFilter, SearchFilter]
    filterset_class = AddressFilter
    search_fields = ['street__name', 'street__name_2', 'street_number__number_type__type', 'street_number__number', 'street_number__number_end', 'street_number__number_suffix', 'street_number__number_end_suffix', 'floor', 'door', 'building','street__type__name', 'city_name', 'province_name']
    ordering_fields = ['street__name', 'street__name_2', 'street_number__number', 'street_number__number_end', 'street_number__number_suffix', 'street_number__number_end_suffix', 'floor', 'door', 'building','street__type__name', 'city_name', 'province_name']
