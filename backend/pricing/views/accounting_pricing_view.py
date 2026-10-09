from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.decorators import action
from django_filters.rest_framework import DjangoFilterBackend

from django.db.models import Q, Prefetch, F, CharField, Value
from django.db.models.functions import Concat

from billing.permissions import BillingPermission
from pricing.models import AccountingPricing
from pricing.filters.accounting_pricing_filter import AccountingPricingFilter
from pricing.serializers.accounting_pricing_serializer import AccountingPricingGroupedSerializer, AccountingPricingSerializer
from pricing.utils.accounting_service import bulk_save_accounting_pricing


class AccountingPricingGroupedPagination(PageNumberPagination):
    page_size = 3
    page_size_query_param = 'page_size'
    max_page_size = 100

class AccountingPricingListedPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100


class AccountingPricingViewSet(viewsets.ModelViewSet):
    queryset = AccountingPricing.objects.filter(is_active=True).order_by('accounting_concept__token', 'token', 'name')
    permission_classes = [IsAuthenticated, BillingPermission]
    filter_backends = (DjangoFilterBackend, )
    filterset_class = AccountingPricingFilter
    pagination_class = AccountingPricingListedPagination
    
    def get_serializer_class(self):
        return AccountingPricingSerializer
    
    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context
    
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        instance = serializer.instance
        read_serializer = AccountingPricingSerializer(instance, context=self.get_serializer_context())
        headers = self.get_success_headers(read_serializer.data)
        return Response(read_serializer.data, status=status.HTTP_201_CREATED, headers=headers, content_type='application/json')

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        instance = serializer.instance
        read_serializer = AccountingPricingSerializer(instance, context=self.get_serializer_context())
        return Response(read_serializer.data, status=status.HTTP_200_OK, content_type='application/json')
    
    
    @action(detail=False, methods=['post'], url_path='find-existing')
    def find_existing_objects(self, request):
        data = request.data
        
        price_rates = request.data.get('price_rates', [])
        price_intervals = request.data.get('price_intervals', [])
        price_variables = request.data.get('price_variables', [])
        payment_types = request.data.get('payment_types', [])
        banks = request.data.get('banks', [])
        products = request.data.get('products', [])
        line_item_types = request.data.get('line_item_types', [])
        exploitation = request.data.get('exploitation', [])
        outgoing_payments = request.data.get('outgoing_payments', None)
        incoming_payments = request.data.get('incoming_payments', None)
        foreign_iban = request.data.get('foreign_iban', None)
        native_iban = request.data.get('native_iban', None)
        
        possible_existing_objects = AccountingPricing.objects.filter(
            accounting_concept__id=data['accounting_concept'],
            is_active=True,
        )
        filters = Q()
        if price_rates:
            filters |= Q(price_rates__in=price_rates)
        if price_intervals:
            filters |= Q(price_intervals__in=price_intervals)
        if price_variables:
            filters |= Q(price_variables__in=price_variables)
        if payment_types:
            filters |= Q(payment_types__in=payment_types)
        if products:
            filters |= Q(products__in=products)
        if line_item_types:
            filters |= Q(line_item_types__in=line_item_types)
        if exploitation:
            filters |= Q(exploitation__id=exploitation)
        if outgoing_payments and banks:
            filters |= Q(outgoing_payments=outgoing_payments)
        if incoming_payments and banks:
            filters |= Q(incoming_payments=incoming_payments)
        if foreign_iban and banks:
            filters |= Q(foreign_iban=foreign_iban)
        if native_iban and banks:
            filters |= Q(native_iban=native_iban)
        possible_existing_objects = possible_existing_objects.filter(filters, banks__in=banks)
        print("possible_existing_objects")
        print(possible_existing_objects)
        serialized_objects = AccountingPricingSerializer(possible_existing_objects, many=True)
        return Response({"results": serialized_objects.data}, status=status.HTTP_200_OK)
    
    @action(detail=False, methods=['post'], url_path='bulk-save')
    def bulk_save_accounting_pricing_values(self, request):
        # Since they could be grouped by different values, we pass all data and save it accordingly
        data = request.data
        user = request.user
        
        bulk_save_accounting_pricing(data, user)
        
        return Response({"ok": True}, status=status.HTTP_200_OK)
    
    
    @action(detail=False, methods=['get'], url_path='grouped')
    def grouped(self, request):
        queryset = self.filter_queryset(self.get_queryset()).select_related(
            'accounting_concept',
            'accounting_concept__type',
            'company',
            'exploitation',
            'created_by',
            'last_updated_by',
        ).prefetch_related(
            'products',
            'price_rates',
            'line_item_types',
            'price_intervals',
            'price_variables',
            'payment_types',
        )

        grouped = {}
        for pricing in queryset:
            concept = pricing.accounting_concept
            key = concept.pk if concept else None
            if key not in grouped:
                grouped[key] = {
                    'accounting_concept': concept,
                    'items': [],
                }
            grouped[key]['items'].append(pricing)

        groups = list(grouped.values())
        paginator = AccountingPricingGroupedPagination()
        page = paginator.paginate_queryset(groups, request, view=self)
        serializer = AccountingPricingGroupedSerializer(
            page if page is not None else groups,
            many=True,
            context=self.get_serializer_context(),
        )
        if page is not None:
            return paginator.get_paginated_response(serializer.data)
        return Response(serializer.data, status=status.HTTP_200_OK)