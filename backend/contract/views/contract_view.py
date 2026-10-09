import datetime
from decimal import Decimal
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.http import HttpResponse

from rest_framework.decorators import action
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from rest_framework.pagination import PageNumberPagination
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from auth.permissions import PermissionManager
from billing.utils.invoice_service import generate_payment_id
from contract.filters.contract_filter import ContractFilter

from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter
from contract.utils.contract_pdf_service import contract_change_use_type_communication_pdf
from coredata.utils.address_utils import get_address_complete_without_city
from coredata.utils.name_utils import generate_token
from django.utils import timezone

from contract.middleware import set_current_user
from contract.serializers.contract_serializer import ContractLogSerializer, ContractMinimalListSerializer, ContractGeneralInvoiceSerializer
from contract.serializers.contract_pinned_serializer import PinnedContractMinimalSerializer, PinnedContractSerializer
from contract.utils.contract_service import contract_bank_change, updateTotalMembers
from contract.utils.contract_csv_export import build_contract_export_csv_bytes
from contract.utils.contract_list_queryset import (
    annotate_contract_list_debt_amount,
    contract_list_page_queryset,
    default_contract_list_queryset,
)
from contract.models import Contract, ContractDataChange, ContractLog, ContractPriceRate, ContractRequestDocumentation, ContractDocumentationType, PaymentType, PiggyBankMovement
from contract.serializers.contract_serializer import ContractSerializer, ContractListSerializer
from contract.serializers.contract_data_change_edit_serializer import ContractDataChangeEditSerializer
from contract.utils.contract_data_change_queryset import contract_data_change_queryset
from billing.models import Invoice, InvoiceStatus, Payment, PaymentStatus
from coredata.models import ConfigProject
from django.contrib.auth.models import Group
from django.conf import settings
from django.core.cache import cache
from documentmanager.utils.main_utils import upload_document
from billing.utils.payment_service import generate_payment_movement
from statistics.utils.report_service import delete_file_later

CONTRACT_LIST_CACHE_KEY_PREFIX = "contract_list"
CONTRACT_LIST_CACHE_TIMEOUT = getattr(settings, "CONTRACT_LIST_CACHE_TIMEOUT", 1500)
# Only cache page 1, one cache per exploitation, ordering and status=2.
# Allow search param only when empty (not in key).
CONTRACT_LIST_CACHEABLE_PARAMS = {"page", "search", "exploitation", "ordering", "status"}


class ContractOrderingFilter(OrderingFilter):
    def filter_queryset(self, request, queryset, view):
        ordering = self.get_ordering(request, queryset, view)
        if not ordering:
            return queryset
        if any(field.lstrip("-") == "debt_amount" for field in ordering):
            queryset = annotate_contract_list_debt_amount(queryset)
        return queryset.order_by(*ordering)


class ContractViewSet(viewsets.ModelViewSet):
    serializer_class = ContractSerializer
    permission_classes = [IsAuthenticated, DjangoModelPermissions]
    filterset_class = ContractFilter
    filter_backends = [DjangoFilterBackend, ContractOrderingFilter]
    search_fields = [
        'token', 'category',  'holder__token', 'address_complete', 
        'supply_point__token', 'client_type__name', 'use_type__name', 
        'supply_point__name', 'created_at'
    ]
    ordering_fields = [
        'token', 'status', 'category', 'client_type', 'created_at', 'holder__name',
        'use_type', 'holder', 'supply_point_default', 'supply_point_default__address__address_search',
        'supply_point_default__meter__code', 'debt_amount',
    ]

    def get_queryset(self):
        if self.action == 'list':
            return contract_list_page_queryset().filter(is_active=True)
        return default_contract_list_queryset()
    
    def get_serializer_class(self):
        if self.action == 'list':
            return ContractMinimalListSerializer
        elif self.action == 'retrieve':
            return ContractSerializer
        return super().get_serializer_class()

    def _contract_list_cache_key(self, request):
        """Build cache key for page 1 only, by exploitation and ordering, and only for status=2 with empty search."""
        query_params = request.query_params
        param_keys = set(query_params.keys())
        if param_keys - CONTRACT_LIST_CACHEABLE_PARAMS:
            return None
        if query_params.get("page", "1") != "1":
            return None
        if (query_params.get("search") or "").strip():
            return None  # non-empty search: do not cache (would need different results)
        if query_params.get("status") != "2":
            return None
        exploitation = query_params.get("exploitation") or "all"
        ordering = query_params.get("ordering") or "default"
        return f"{CONTRACT_LIST_CACHE_KEY_PREFIX}:status_2:exploitation_{exploitation}:page_1:order_{ordering}"

    def list(self, request, *args, **kwargs):
        """Serve page 1 from cache for status=2 when only cacheable params are used."""
        cache_key = self._contract_list_cache_key(request)
        if cache_key:
            cached = cache.get(cache_key)
            if cached is not None:
                print(f"Contract list: served from cache (key={cache_key})")
                return Response(cached, status=status.HTTP_200_OK)

        response = super().list(request, *args, **kwargs)

        if cache_key:
            cache.set(cache_key, response.data, timeout=CONTRACT_LIST_CACHE_TIMEOUT)
            print(f"Contract list: cache miss, stored in cache (key={cache_key})")

        return response
    
    def update(self, request, *args, **kwargs):
        set_current_user(request.user)
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        updateTotalMembers(request.user, request.data, instance)
        self.perform_update(serializer)
        instance = serializer.instance
        if request.query_params.get('edit') == 'data-change':
            instance = contract_data_change_queryset().filter(pk=instance.pk).first()
            read_serializer = ContractDataChangeEditSerializer(
                instance,
                context=self.get_serializer_context(),
            )
        else:
            read_serializer = ContractSerializer(
                instance,
                context=self.get_serializer_context(),
            )
        return Response(read_serializer.data, status=status.HTTP_200_OK, content_type='application/json')

    @action(detail=True, methods=['get'], url_path='data-change')
    def data_change(self, request, pk=None):
        """Dades mínimes per al formulari de modificació (sense comptadors ni llistats pesats)."""
        instance = contract_data_change_queryset().filter(pk=pk).first()
        if not instance:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        serializer = ContractDataChangeEditSerializer(
            instance,
            context=self.get_serializer_context(),
        )
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    @action(detail=True, methods=['put'], url_path='toggle-billable')
    def toggle_billable(self, request,pk):
        set_current_user(request.user)
        instance = self.get_object()
        
        instance.block_billing = not instance.block_billing
        instance.save(update_fields=['block_billing'])

        return Response({
            "block_billing": instance.block_billing,
        }, status=status.HTTP_200_OK)
    
    @action(detail=True, methods=['put'], url_path='set-bop-price-rate')
    def set_bop_price_rate(self, request, pk=None):
        """Marca quin ContractPriceRate del contracte és la referència de la tarifa BOP."""
        set_current_user(request.user)
        instance = self.get_object()
        contract_price_rate_id = request.data.get('contract_price_rate_id', None)

        if not contract_price_rate_id:
            raise ValidationError("contract_price_rate_id is required")

        try:
            contract_price_rate = instance.price_rates.get(id=contract_price_rate_id)
        except ContractPriceRate.DoesNotExist:
            raise ValidationError("contract_price_rate_id does not belong to this contract")

        instance.price_rates.filter(is_bop_reference=True).update(is_bop_reference=False)
        contract_price_rate.is_bop_reference = True
        contract_price_rate.save(update_fields=['is_bop_reference'])

        serializer = ContractSerializer(instance, context=self.get_serializer_context())
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['get'], url_path='minimal')
    def get_minimal(self, request,pk):
        instance = self.get_object()
        serializer = ContractMinimalListSerializer(instance, context=self.get_serializer_context())
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    
    @action(detail=True, methods=['get'], url_path='contracts')
    def get_contracts_by_holder(self, request,pk):
        id = pk
        active_contract = ConfigProject.objects.get(token='contract_active_token').value
        contracts = Contract.objects.filter(holder__id=id, status__token=active_contract)
        print("total_contracts: ", contracts.count())
        serializer = ContractGeneralInvoiceSerializer(contracts, many=True, context=self.get_serializer_context())
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    
    @action(detail=True, methods=['put'], url_path='save-file')
    def upload_contract_document(self, request, pk):
        set_current_user(request.user)
        instance = self.get_object()
        is_contract = request.data.get('is_contract', False)
        file = request.FILES.getlist('file') or None
        contract_type_id = request.data.get('contract_type', None)
        text = request.data.get('text', None)

        try:
            contract_type = ContractDocumentationType.objects.get(id=contract_type_id)
        except Exception as e:
            contract_type = None

        if not file:
            raise ValidationError("File is required")
        service = settings.DOCUMENT_MANAGER_SERVICES.get("contract")
        document = upload_document(file[0], 'CONTRACT', 'CONTRACT', instance.id, instance.token, '', service, file[0].name.replace(' ', '_').replace('/', '_'), instance.created_at)
        if is_contract.upper() == 'TRUE':
            instance.contract_file = document
            instance.save()
        else:
            new_documentation = ContractRequestDocumentation.objects.create(
                contract=instance,
                file=document,
                contract_type=contract_type,
                text=text,
            )
        serializer = ContractSerializer(instance, context=self.get_serializer_context())

        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], url_path='save-documentation')
    def save_documentation(self, request, pk=None):
        set_current_user(request.user)
        instance = self.get_object()
        contract_type_id = request.data.get('contract_type', None)
        text = request.data.get('text', None)

        try:
            contract_type = ContractDocumentationType.objects.get(id=contract_type_id)
        except Exception:
            contract_type = None

        ContractRequestDocumentation.objects.create(
            contract=instance,
            contract_type=contract_type,
            text=text,
        )
        serializer = ContractSerializer(instance, context=self.get_serializer_context())
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'], url_path='bank-change')
    def update_contract_bank_accounts(self, request, pk=None):
        try:
            file = request.data.get('file', None)
            is_saving = request.data.get('save', False)
            if isinstance(is_saving, str):
                is_saving = is_saving.upper() == 'TRUE'
            user = request.user
            print("is_saving", is_saving)
            result = contract_bank_change(file, is_saving, user)
            
            return Response(result, status=status.HTTP_200_OK)
            
        except Contract.DoesNotExist:
            return Response(
                {"error": "Contract not found"}, 
                status=status.HTTP_404_NOT_FOUND
            )
            
    @action(detail=True, methods=['get'], url_path='logs')
    def logs(self, request, pk=None):
        try:
            contract = self.get_object()

            logs = list(
                ContractLog.objects.filter(contract=contract)
                .select_related('user')
                .values('id', 'created_at', 'field_name', 'old_value', 'new_value', 'operation_token',
                        'user__id', 'user__username', 'user__first_name', 'user__last_name', 'user__email')
            )
            log_entries = [
                {
                    'id': f"log_{r['id']}",
                    'created_at': r['created_at'],
                    'field_name': r['field_name'],
                    'old_value': r['old_value'],
                    'new_value': r['new_value'],
                    'operation_token': r['operation_token'],
                    'source': 'log',
                    'user': {
                        'id': r['user__id'],
                        'username': r['user__username'],
                        'first_name': r['user__first_name'],
                        'last_name': r['user__last_name'],
                        'email': r['user__email'],
                    } if r['user__id'] else None,
                }
                for r in logs
            ]

            data_changes = (
                ContractDataChange.objects.filter(contract=contract)
                .select_related(
                    'user',
                    'new_person_contact_email', 'previous_person_contact_email',
                    'new_address_contact', 'previous_address_contact',
                    'new_address_billing', 'previous_address_billing',
                    'new_payment', 'previous_payment',
                    'new_payment_type', 'previous_payment_type',
                )
            )
            dc_entries = []
            for dc in data_changes:
                changes = []
                if dc.new_person_contact_email_id != dc.previous_person_contact_email_id:
                    changes.append({
                        'field_name': 'person_contact_email',
                        'old_value': dc.previous_person_contact_email.email if dc.previous_person_contact_email else None,
                        'new_value': dc.new_person_contact_email.email if dc.new_person_contact_email else None,
                    })
                if dc.new_address_contact_id != dc.previous_address_contact_id:
                    changes.append({
                        'field_name': 'address_contact',
                        'old_value': str(dc.previous_address_contact) if dc.previous_address_contact else None,
                        'new_value': str(dc.new_address_contact) if dc.new_address_contact else None,
                    })
                if dc.new_address_billing_id != dc.previous_address_billing_id:
                    changes.append({
                        'field_name': 'address_billing',
                        'old_value': str(dc.previous_address_billing) if dc.previous_address_billing else None,
                        'new_value': str(dc.new_address_billing) if dc.new_address_billing else None,
                    })
                if dc.new_payment_id != dc.previous_payment_id:
                    changes.append({
                        'field_name': 'payment_IBAN',
                        'old_value': dc.previous_payment.iban if dc.previous_payment else None,
                        'new_value': dc.new_payment.iban if dc.new_payment else None,
                    })
                if dc.new_payment_type_id != dc.previous_payment_type_id:
                    changes.append({
                        'field_name': 'payment_type',
                        'old_value': dc.previous_payment_type.name if dc.previous_payment_type else None,
                        'new_value': dc.new_payment_type.name if dc.new_payment_type else None,
                    })
                if dc.new_language != dc.previous_language:
                    changes.append({
                        'field_name': 'language',
                        'old_value': dc.previous_language,
                        'new_value': dc.new_language,
                    })

                user_data = {
                    'id': dc.user.id,
                    'username': dc.user.username,
                    'first_name': dc.user.first_name,
                    'last_name': dc.user.last_name,
                    'email': dc.user.email,
                } if dc.user else None

                if changes:
                    for i, change in enumerate(changes):
                        dc_entries.append({
                            'id': f"dc_{dc.id}_{i}",
                            'created_at': dc.created_at,
                            'operation_token': dc.token,
                            'source': 'data_change',
                            'user': user_data,
                            **change,
                        })
                else:
                    dc_entries.append({
                        'id': f"dc_{dc.id}",
                        'created_at': dc.created_at,
                        'operation_token': dc.token,
                        'field_name': None,
                        'old_value': None,
                        'new_value': None,
                        'source': 'data_change',
                        'user': user_data,
                    })

            # Dedup: drop log entries that duplicate a data_change (same/equivalent field, within 5s)
            from datetime import timedelta

            # data_change field_name → ContractLog field_name(s) that represent the same change
            FIELD_EQUIVALENTS = {
                'payment_type': {'payment_type', 'payment'},
                'payment_IBAN': {'payment_IBAN', 'payment'},
                'person_contact_email': {'person_contact_email'},
                'address_contact': {'address_contact'},
                'address_billing': {'address_billing'},
                'language': {'language'},
            }

            absorbed_log_ids = set()
            for dc in dc_entries:
                equivalent_fields = FIELD_EQUIVALENTS.get(dc['field_name'], {dc['field_name']})
                for log in log_entries:
                    if log['id'] in absorbed_log_ids:
                        continue
                    if log['field_name'] not in equivalent_fields:
                        continue
                    delta = abs((dc['created_at'] - log['created_at']).total_seconds())
                    if delta <= 5:
                        # Inherit user from log if data_change has none
                        if dc['user'] is None and log['user'] is not None:
                            dc['user'] = log['user']
                        absorbed_log_ids.add(log['id'])

            filtered_logs = [l for l in log_entries if l['id'] not in absorbed_log_ids]
            combined = sorted(filtered_logs + dc_entries, key=lambda x: x['created_at'], reverse=True)
            return Response(combined, status=status.HTTP_200_OK)
        except Contract.DoesNotExist:
            return Response(
                {"error": "Contract not found"},
                status=status.HTTP_404_NOT_FOUND
            )
            
    @action(detail=True, methods=['get'], url_path='pinned')
    def pinned(self, request, pk=None):
        
        contract_id = pk
        if not contract_id or contract_id == '' or contract_id == 'null':
            pinned_contract = Contract.objects.filter(user_pinned=request.user).first()
        else:
            pinned_contract = Contract.objects.select_related(
                'supply_point_default', 'status', 'holder'
            ).filter(id=contract_id).first()
            
        if not pinned_contract:
            return Response( None, status=status.HTTP_200_OK )
        serializer = PinnedContractMinimalSerializer(pinned_contract, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    @action(detail=True, methods=['get'], url_path='pinned-full')
    def pinned_full(self, request, pk=None):
        
        contract_id = pk
        pinned_contract = Contract.objects.filter(id=contract_id).first()
        if not pinned_contract:
            return Response( None, status=status.HTTP_200_OK )
        serializer = PinnedContractSerializer(pinned_contract, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    @action(detail=True, methods=['get'], url_path='communication-pdf')
    def get_use_type_change_communication_pdf(self, request, pk=None):
        user = request.user
        contract_id = pk
        use_type_id = request.query_params.get('use_type', None)
        contract_type_id = request.query_params.get('contract_type', None)
        
        pdf_bytes, filename = contract_change_use_type_communication_pdf(
            contract_id, use_type_id, contract_type_id, request
        )
        
        temp_rel_path = f"tmp/contract_docs/{filename}"
        saved_path = default_storage.save(
            temp_rel_path, ContentFile(pdf_bytes)
        )
        file_url = request.build_absolute_uri(default_storage.url(saved_path))
        
        delete_file_later(saved_path, delay_seconds=20)
        
        return Response({"file_url": file_url}, status=status.HTTP_200_OK )
    
    @action(detail=True, methods=['put'], url_path='add-balance')
    def add_balance_to_contract(self, request,pk):
        set_current_user(request.user)
        instance = self.get_object()
        
        # print(request.data)
        # return Response({
        #     "block_billing": instance.block_billing,
        # }, status=status.HTTP_200_OK)
        user = request.user
        raw_amount = request.data.get('amount', 0) or 0
        amount = Decimal(str(raw_amount))
        movement_date = request.data.get('movement_date', None)
        payment_method_id = request.data.get('payment_method_id', None)
        
        try:
            movement_date_inst = datetime.datetime.strptime(movement_date, "%Y-%m-%d").date()
        except Exception as e:
            movement_date_inst = movement_date
        try:
            payment_type = PaymentType.objects.get(id=payment_method_id)
        except Exception as e:
            payment_type = None
        
        instance.piggy_bank.amount = float(instance.piggy_bank.amount) + float(amount)
        instance.piggy_bank.save()
        
        
        # type_token = ConfigProject.objects.get(token="payment_type_balance_token").value
        # payment_type = PaymentType.objects.get(token=type_token)
        
        payment_status_paid = PaymentStatus.objects.get(token=ConfigProject.objects.get(token='payment_status_paid_token').value)
        payment_status_pending = PaymentStatus.objects.get(token=ConfigProject.objects.get(token='payment_status_pending_token').value)
        payment_status_piggy = PaymentStatus.objects.get(token=ConfigProject.objects.get(token='payment_status_piggy_token').value)
        
        billing_address = instance.address_billing.address if instance.address_billing else instance.supply_point_default.address
        
        address_final = get_address_complete_without_city(billing_address)
        location_final = billing_address.postal_code + " " + billing_address.city.name
        
        date_now = timezone.now()
        
        new_payment = Payment.objects.create(
            token=generate_payment_id('04'),
            name=str(_("Manually added Balance")),
            contract=instance,
            customer_final=instance.holder.name + " " + instance.holder.surname,
            customer_token_final=instance.holder.token,
            payer_final=instance.holder.name + " " + instance.holder.surname,
            payer_token_final=instance.holder.token,
            amount=amount,
            payment_type=payment_type.name,
            payment_type_token= payment_type.token,
            address_final=address_final,
            location_final=location_final,
            status=payment_status_piggy,
            payment_date= movement_date,
            due_date= movement_date,
        )
        
        piggy_bank_movement = PiggyBankMovement.objects.create(
            token=generate_token(PiggyBankMovement),
            piggy_bank=instance.piggy_bank,
            amount=amount,
            is_positive=amount > 0,
            movement_date=movement_date,
            payment=new_payment,
            user=user,
        )
        
        new_payment.status = payment_status_pending
        generate_payment_movement(
            new_payment, payment_status_piggy, movement_date,
            payment_type.token, None, user
        )
        
        return Response({
            "balance_added": amount,
        }, status=status.HTTP_200_OK)
    
    
    @action(detail=False, methods=['get'], url_path='permissions')
    def permissions(self, request):
        pk = request.query_params.get('id')
        if pk:
            user_permissions = PermissionManager.get_model_permissions(request.user, 'auth', 'group')
            if not user_permissions['can_view'] or not user_permissions['can_change'] or not request.user.is_superuser:
                return Response( None, status=status.HTTP_403_FORBIDDEN )
            group = Group.objects.filter(id=pk).first()
            if not group:
                return Response( None, status=status.HTTP_404_NOT_FOUND )
            group_permissions = PermissionManager.get_model_group_permissions(group, 'contract')
            return Response(group_permissions, status=status.HTTP_200_OK)
        permissions = PermissionManager.get_model_permissions(request.user, 'contract', 'contract')
        return Response(permissions, status=status.HTTP_200_OK)
    
    @action(detail=False, methods=['get'], url_path='export/excel')
    def export_csv(self, request, *args, **kwargs):
        try:
            # Obtenir els paràmetres del query string
            query_params = request.query_params.dict()
            
            # Iniciar la tasca de Celery de manera asíncrona
            from contract.tasks import export_contracts_csv_task
            task = export_contracts_csv_task.delay(query_params)
            
            return Response({
                "task_id": task.id,
                "status": "pending",
                "message": "Generació de l'exportació de contractes iniciada correctament. Utilitza el task_id per comprovar l'estat."
            }, status=status.HTTP_202_ACCEPTED)
            
        except Exception as e:
            return Response(
                {"error": f"Error en iniciar l'exportació: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def get_permissions(self):
        if self.action == 'permissions':
            return [IsAuthenticated()]
        return super().get_permissions()