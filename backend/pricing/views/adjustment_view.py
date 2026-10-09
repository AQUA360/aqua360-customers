from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from rest_framework.pagination import PageNumberPagination
from rest_framework import viewsets

from ..models import Adjustment
from ..serializers.adjustment_serializer import AdjustmentSerializer, AdjustmentSaveSerializer
from ..filters.adjustment_filter import AdjustmentFilter
from pricing.permissions import PriceRatePermission
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter, SearchFilter

class AdjustmentViewSet(viewsets.ModelViewSet):
    queryset = Adjustment.objects.all().order_by('position')
    serializer_class = AdjustmentSerializer
    permission_classes = [IsAuthenticated, PriceRatePermission]
    filter_backends = [DjangoFilterBackend]
    filterset_class = AdjustmentFilter
    ordering_fields = '__all__'
    search_fields = '__all__'

    def get_serializer_class(self):
        if self.request.method in ['GET']:
            return AdjustmentSerializer
        return AdjustmentSaveSerializer
    

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        instance = serializer.instance
        read_serializer = AdjustmentSerializer(instance)
        headers = self.get_success_headers(read_serializer.data)
        return Response(read_serializer.data, status=status.HTTP_201_CREATED, headers=headers)
    
    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        instance = serializer.instance
        read_serializer = AdjustmentSerializer(instance, context=self.get_serializer_context())
        return Response(read_serializer.data, status=status.HTTP_200_OK, content_type='application/json')