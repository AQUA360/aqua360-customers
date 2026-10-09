from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from rest_framework.pagination import PageNumberPagination
from rest_framework import viewsets

from pricing.serializers.price_interval_stretch_serializer import PriceIntervalStretchSerializer
from pricing.serializers.price_variable_interval_stretch_serializer import PriceVariableIntervalStretchSerializer

from ..filters.line_item_type_filter import LineItemTypeFilter
from pricing.permissions import PriceRatePermission
from ..models import LineItemType
from ..serializers.line_item_type_serializer import LineItemTypeArticleSerializer, LineItemTypeSerializer, LineItemTypeListSerializer, LineItemTypeSaveSerializer

from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter, SearchFilter

class LineItemTypeViewSet(viewsets.ModelViewSet):
    queryset = LineItemType.objects.all()
    serializer_class = LineItemTypeSerializer
    permission_classes = [IsAuthenticated, PriceRatePermission]
    filterset_class = LineItemTypeFilter
    filter_backends = [DjangoFilterBackend]
    ordering_fields = '__all__'
    search_fields = '__all__'
    
    @action(detail=False, methods=['get'], url_path='list')
    def simple_list(self, request):
        queryset = self.get_queryset()
        paginator = PageNumberPagination()
        paginator.page_size = 50
        result_page = paginator.paginate_queryset(queryset, request)
        serializer = LineItemTypeListSerializer(result_page, many=True)
        return paginator.get_paginated_response(serializer.data)
    
    def get_serializer_class(self):
        if self.request.method in ['GET']:
            return LineItemTypeSerializer
        return LineItemTypeSaveSerializer
    
    
    @action(detail=False, methods=['get'], url_path='by-product')
    def get_by_product_article(self, request):
        product_id = request.query_params.get('product')
        line_items = LineItemType.objects.filter(
            billing_range__price_rates__isnull=False,
            billing_range__price_rate__product__id=product_id,
            billing_range__price_rate__product__is_active=True,
            billing_range__price_rate__is_active=True,
            billing_range__is_active=True,
            billing_range__end__isnull=True,
            is_active=True,
        ).order_by('billing_range__price_rate')
        paginator = PageNumberPagination()
        paginator.page_size = 50
        result_page = paginator.paginate_queryset(line_items, request)
        serializer = LineItemTypeArticleSerializer(result_page, many=True)
        return paginator.get_paginated_response(serializer.data)
    
    
    @action(detail=True, methods=['get'], url_path='stretches')
    def get_stretches(self, request, pk=None):
        instance = self.get_object()
        stretches = None
        serializer = None
        if instance.price_interval:
            stretches = instance.price_interval.price_interval_stretches.all().order_by('end_stretch')
            serializer = PriceIntervalStretchSerializer(stretches, many=True)
        elif instance.price_variable:
            stretches = instance.price_variable.price_variable_stretches.all().order_by('end_stretch')
            serializer = PriceVariableIntervalStretchSerializer(stretches, many=True)
        if not serializer:
            raise Exception("No stretches found")
        return Response(serializer.data, status=status.HTTP_200_OK, content_type='application/json')
    
    
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        instance = serializer.instance
        read_serializer = LineItemTypeSerializer(instance)
        headers = self.get_success_headers(read_serializer.data)
        return Response(read_serializer.data, status=status.HTTP_201_CREATED, headers=headers)
    
    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        instance = serializer.instance
        read_serializer = LineItemTypeSerializer(instance, context=self.get_serializer_context())
        return Response(read_serializer.data, status=status.HTTP_200_OK, content_type='application/json')