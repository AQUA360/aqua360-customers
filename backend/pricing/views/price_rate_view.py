# pricing/views.py
from rest_framework.decorators import action
from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from rest_framework.pagination import PageNumberPagination
from rest_framework import viewsets
from django.db.models import Q

from auth.permissions import PermissionManager
from ..models import PriceRate
from ..serializers.price_rate_serializer import PriceRateSerializer, PriceRateSaveSerializer, create_price_rate_log

from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter, SearchFilter
from pricing.filters.price_rate_filter import PriceRateFilter
from pricing.utils.deletion_service import price_rate_deletion_error

class PriceRateViewSet(viewsets.ModelViewSet):
    # Les tarifes sense producte també es mostren, perquè es puguin revisar i eliminar
    queryset = PriceRate.objects.filter(Q(product__isnull=True) | Q(product__is_active=True), is_active=True).order_by('token')
    serializer_class = PriceRateSerializer
    permission_classes = [IsAuthenticated, DjangoModelPermissions]
    filter_backends = [DjangoFilterBackend, OrderingFilter, SearchFilter]
    filterset_class = PriceRateFilter
    search_fields = ['token', 'product__token', 'name']
    ordering_fields = ['token', 'type', 'exploitation', 'product']
    
    
    def get_serializer_class(self):
        if self.request.method in ['GET']:
            return PriceRateSerializer
        return PriceRateSaveSerializer
    
    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context
    
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        instance = serializer.instance
        read_serializer = PriceRateSerializer(instance, context=self.get_serializer_context())
        headers = self.get_success_headers(read_serializer.data)
        return Response(read_serializer.data, status=status.HTTP_201_CREATED, headers=headers, content_type='application/json')

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        instance = serializer.instance
        read_serializer = PriceRateSerializer(instance, context=self.get_serializer_context())
        return Response(read_serializer.data, status=status.HTTP_200_OK, content_type='application/json')

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        data = self.get_serializer(instance).data
        # Només al detall: al llistat suposaria diverses consultes per fila
        data['is_deletable'] = price_rate_deletion_error(instance) is None
        return Response(data)

    def destroy(self, request, *args, **kwargs):
        """Esborrat lògic, només si la tarifa no s'ha fet servir en cap contracte ni factura ni està configurada."""
        instance = self.get_object()
        error = price_rate_deletion_error(instance)
        if error:
            return Response({'detail': error}, status=status.HTTP_400_BAD_REQUEST)
        instance.is_active = False
        instance.save(update_fields=['is_active', 'updated_at'])
        create_price_rate_log(instance, 'is_active', True, False, request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)
    
    @action(detail=False, methods=['get'], url_path='all')
    def all(self, request):
        """
        Get all price rates without pagination while maintaining the same response format.
        """
        queryset = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(queryset, many=True)
        
        return Response({
            'count': queryset.count(),
            'next': None,
            'previous': None,
            'results': serializer.data
        }, status=status.HTTP_200_OK)
    
    @action(detail=False, methods=['get'], url_path='permissions')
    def permissions(self, request):
        pk = request.query_params.get('id')
        if pk:
            from django.contrib.auth.models import Group
            user_permissions = PermissionManager.get_model_permissions(request.user, 'auth', 'group')
            if not user_permissions['can_view'] or not user_permissions['can_change'] or not request.user.is_superuser:
                return Response( None, status=status.HTTP_403_FORBIDDEN )
            group = Group.objects.filter(id=pk).first()
            if not group:
                return Response( None, status=status.HTTP_404_NOT_FOUND )
            group_permissions = PermissionManager.get_model_group_permissions(group, 'pricerate')
            return Response(group_permissions, status=status.HTTP_200_OK)
        permissions = PermissionManager.get_model_permissions(request.user, 'pricerate', 'pricing')
        return Response(permissions, status=status.HTTP_200_OK)
        
    def get_permissions(self):
        if self.action == 'permissions':
            return [IsAuthenticated()]
        return super().get_permissions()