from django.http import Http404
from rest_framework.decorators import action
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.pagination import PageNumberPagination
from statistics.models import AccountingCode
from statistics.serializers import AccountingCodeSerializer, AccountingCodeGroupedSerializer
from statistics.permissions import StatisticsPermission
from statistics.filters import AccountingCodeFilter

class AccountingCodeViewSet(viewsets.ModelViewSet):
    queryset = AccountingCode.objects.all().order_by('created_at')
    serializer_class = AccountingCodeSerializer
    permission_classes = [IsAuthenticated, StatisticsPermission]
    filter_backends = [DjangoFilterBackend, OrderingFilter, SearchFilter]
    ordering_fields = ['code', 'description']
    filterset_class = AccountingCodeFilter
    
    @action(detail=False, methods=['get'], url_path='grouped')
    def get_grouped_object(self, request):
        queryset = self.filter_queryset(self.get_queryset())
        paginator = PageNumberPagination()
        paginator.page_size = 50
        result_page = paginator.paginate_queryset(queryset, request)
        serializer = AccountingCodeGroupedSerializer(result_page, many=True)
        return paginator.get_paginated_response(serializer.data)