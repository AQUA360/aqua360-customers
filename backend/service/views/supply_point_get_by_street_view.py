import json
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from django.db.models import Q
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from contract.models import Contract
from contract.serializers.contract_serializer import ContractListSerializer
from service.models import SupplyPoint
from service.serializers.supply_point_serializer import SupplyPointListSerializer

class SupplyPointGetByStreetView(APIView):
    permission_classes = [IsAuthenticated, DjangoModelPermissions]
    queryset = SupplyPoint.objects.all()
    def post(self, request, *args, **kwargs):
        # selected_streets: llista de carrers (tall manual multi-carrer).
        # selected_street: valor escalar antic, es manté per compatibilitat.
        selected_streets = request.data.get('selected_streets', None)
        selected_street = request.data.get('selected_street', None)
        selected_numbers = request.data.get('selected_numbers', None)
        contract_ids = request.data.get('contract_ids', None)
        supply_point_ids = request.data.get('supply_point_ids', None)
        
        filters = Q()
        
        street_ids = []
        if selected_streets:
            street_ids = list(selected_streets)
        elif selected_street:
            street_ids = [selected_street]
        if len(street_ids) > 0:
            filters &= Q(address__street__id__in=street_ids)
        
        if selected_numbers:
            filters &= Q(address__street_number__id__in=selected_numbers)
        
        if contract_ids:
            filters &= Q(contracts__in=contract_ids)
        
        if supply_point_ids:
            filters &= Q(id__in=supply_point_ids)
        
        supply_points = SupplyPoint.objects.filter(filters).distinct()
        serialized_supply_points = SupplyPointListSerializer(supply_points, many=True).data
        
        contracts = Contract.objects.filter(supply_points__in=supply_points).distinct()
        serialized_contracts = ContractListSerializer(contracts, many=True).data

        return Response({'supply_points': serialized_supply_points, 'contracts': serialized_contracts}, status=status.HTTP_200_OK)