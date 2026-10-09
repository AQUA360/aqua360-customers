# coredata/views/person_bank_view.py

from django.db import transaction
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.response import Response

from django_filters.rest_framework import DjangoFilterBackend

from django.db.models import Prefetch, F, CharField, Value
from django.db.models.functions import Concat

from service.models import CompanyBank
from service.serializers.company_bank_serializer import CompanyBankSerializer
from service.filters.company_bank_filter import CompanyBankFilter
from service.permissions import CompanyPermission
class CompanyBankViewSet(viewsets.ModelViewSet):
    queryset = CompanyBank.objects.all().order_by('token')
    serializer_class = CompanyBankSerializer
    permission_classes = [IsAuthenticated, CompanyPermission]
    filter_backends = [DjangoFilterBackend, OrderingFilter, SearchFilter]
    filterset_class = CompanyBankFilter
    
    
    @action(detail=False, methods=['post'])
    def set_default(self, request):
        """
        Marca quin compte de l'empresa és el predeterminat, deixant la resta
        sense marcar. És el compte que recull tot allò que el mapa
        d'encaminament no assigna enlloc
        (`billing/utils/remittance_routing.py::get_company_fallback_banks`), per
        això ha de ser únic per empresa.

        Cos: `{company, company_bank}`. Amb `company_bank` a null només es treu
        la marca a tots.
        """
        company_id = request.data.get('company')
        company_bank_id = request.data.get('company_bank')

        if not company_id:
            return Response(
                {"error": "Missing required field `company`"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        company_banks = CompanyBank.objects.filter(company_id=company_id)
        if company_bank_id and not company_banks.filter(id=company_bank_id).exists():
            return Response(
                {"error": "`company_bank` does not belong to `company`"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            company_banks.exclude(id=company_bank_id).update(is_default=False)
            if company_bank_id:
                company_banks.filter(id=company_bank_id).update(is_default=True)

        return Response(
            {"company": int(company_id), "company_bank": company_bank_id or None},
            status=status.HTTP_200_OK,
        )

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        instance = serializer.instance
        read_serializer = CompanyBankSerializer(instance, context=self.get_serializer_context())
        headers = self.get_success_headers(read_serializer.data)
        return Response(read_serializer.data, status=status.HTTP_201_CREATED, headers=headers, content_type='application/json')

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        instance = serializer.instance
        read_serializer = CompanyBankSerializer(instance, context=self.get_serializer_context())
        return Response(read_serializer.data, status=status.HTTP_200_OK, content_type='application/json')