import copy
import datetime
from django.http import Http404
from rest_framework.decorators import action
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.response import Response
from rest_framework import status
from django.db.models import Q, Prefetch
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from auth.permissions import PermissionManager
from billing.models import Payment, PaymentStatus
from billing.utils.invoice_service import generate_payment_id
from billing.utils.payment_service import generate_payment_movement
from contract.models import PaymentType
from coredata.models import ConfigProject, Person, PersonAddress, PersonContact, PersonBank, PersonObservation, PersonCNAE, PersonPiggyBankMovement, PersonLog
from coredata.serializers import PersonCommunicationSerializer, PersonSerializer, PersonAddressSerializer, AddressSerializer, PersonMinimalSerializer
from coredata.filters.person_filter import PersonFilter
from coredata.filters.address_filter import AddressFilter, PersonAddressFilter
from coredata.permissions import PersonPermission
from coredata.utils.address_utils import get_address_complete_without_city
from coredata.utils.name_utils import generate_token

class PersonViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows Person to be viewed or edited.
    """
    queryset = Person.objects.all()
    permission_classes = [IsAuthenticated, DjangoModelPermissions]
    filter_backends = [DjangoFilterBackend, OrderingFilter, SearchFilter]
    filterset_class = PersonFilter
    search_fields = ['token', 'name', 'surname']
    ordering_fields = ['token', 'name', 'surname','is_juridic']
    
    def get_queryset(self):
        queryset = Person.objects.select_related(
            'deliquency'
        ).prefetch_related(
            Prefetch('addresses', queryset=PersonAddress.objects.select_related(
                'address__street__type',
                'address__street_number__street',
                'address__street_number__number_type',
                'address__city__province__country',
                'address__province__country',
                'address__country'
            )),
            Prefetch('contacts', queryset=PersonContact.objects.filter(is_active=True).order_by('-is_default', '-created_at')),
            Prefetch('banks', queryset=PersonBank.objects.select_related(
                'bank',
                'country'
            ).filter(is_active=True).order_by('-is_default', '-created_at')),
            Prefetch('observations', queryset=PersonObservation.objects.select_related('user').order_by('-created_at')),
            Prefetch('cnaes', queryset=PersonCNAE.objects.select_related('cnae').filter(is_active=True))
        ).order_by('token')
        return queryset
    
    def get_serializer_class(self):
        if self.action == 'list':  # Corresponds to GET / (list view)
            return PersonMinimalSerializer
        elif self.action == 'retrieve':  # Corresponds to GET /id (detail view)
            return PersonSerializer
        return PersonSerializer
    
    @action(detail=True, methods=['put'], url_path='add-balance')
    def add_balance_to_person(self, request,pk):
        instance = self.get_object()
        
        
        user = request.user
        amount = request.data.get('amount', 0)
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
        
        billing_address = instance.addresses.filter(is_billing=True).first()
        if not billing_address:
            instance.addresses.first()
        
        address_final = get_address_complete_without_city(billing_address.address) if billing_address else ""
        location_final = (billing_address.address.postal_code + " " + billing_address.address.city.name) if billing_address else ""
        
        date_now = timezone.now()
        
        new_payment = Payment.objects.create(
            token=generate_payment_id('04'),
            name=str(_("Manually added Balance")),
            person=instance,
            customer_final=instance.name + ((" " + instance.surname) if instance.surname else ''),
            customer_token_final=instance.token,
            payer_final=instance.name + ((" " + instance.surname) if instance.surname else ''),
            payer_token_final=instance.token,
            amount=amount,
            payment_type=payment_type.name,
            payment_type_token= payment_type.token,
            address_final=address_final,
            location_final=location_final,
            status=payment_status_piggy,
            payment_date= movement_date,
            due_date= movement_date,
        )
            
        piggy_bank_movement = PersonPiggyBankMovement.objects.create(
            token=generate_token(PersonPiggyBankMovement),
            person_piggy_bank=instance.piggy_bank,
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

    @action(detail=True, methods=['get'], url_path='logs')
    def logs(self, request, pk=None):
        person = self.get_object()

        logs = list(
            PersonLog.objects.filter(person=person)
            .select_related('user')
            .order_by('-created_at')
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

        return Response(log_entries, status=status.HTTP_200_OK)
    
    @action(detail=False, methods=['post'], url_path='communication-detail')
    def get_communication_detail(self, request):
        person_data = request.data.get('person_data', [])
        show_vulnerable = request.data.get('show_vulnerable', False)
        show_juridic = request.data.get('show_juridic', False)
        search_query = request.data.get('search_query', '')
        
        # Get unique person IDs to fetch persons efficiently
        unique_person_ids = list(set([item['id'] for item in person_data]))
        
        # Fetch all unique persons once with prefetching
        persons_dict = {}
        persons_qs = Person.objects.filter(id__in=unique_person_ids).select_related(
            'deliquency'
        ).prefetch_related(
            Prefetch('addresses', queryset=PersonAddress.objects.select_related(
                'address__street__type',
                'address__street_number__street',
                'address__street_number__number_type',
                'address__city__province__country',
                'address__province__country',
                'address__country'
            )),
            Prefetch('contacts', queryset=PersonContact.objects.filter(is_active=True).order_by('-is_default', '-created_at')),
            Prefetch('banks', queryset=PersonBank.objects.select_related(
                'bank',
                'country'
            ).filter(is_active=True).order_by('-is_default', '-created_at')),
            Prefetch('observations', queryset=PersonObservation.objects.select_related('user').order_by('-created_at')),
            Prefetch('cnaes', queryset=PersonCNAE.objects.select_related('cnae').filter(is_active=True)),
            'contract_request_holder'
        )
        
        # Create a dictionary for quick lookup
        for person in persons_qs:
            persons_dict[person.id] = person
        
        # Process each person_data item individually to preserve duplicates
        persons_list = []
        for item in person_data:
            person_id = item['id']
            person = persons_dict.get(person_id)
            
            if not person:
                continue
            
            # Apply filters
            if show_juridic and not person.is_juridic:
                continue
            if show_vulnerable and person.vulnerability_level <= 0:
                continue
            if search_query:
                search_lower = search_query.lower()
                search_match = (
                    (person.name and search_lower in person.name.lower()) or
                    (person.surname and search_lower in person.surname.lower()) or
                    (person.token and search_lower in person.token.lower()) or
                    any(search_lower in cr.token.lower() for cr in person.contract_request_holder.all() if cr.token)
                )
                if not search_match:
                    continue
            
            # Create a shallow copy of the person to avoid modifying the same instance
            # This ensures each entry has its own contract_ids and invoice_ids
            person_copy = copy.copy(person)
            
            # Attach contracts and invoices for this specific entry
            person_copy.contract_ids = item.get('contracts', [])
            person_copy.invoice_ids = item.get('invoices', [])
            person_copy.reading_ids = item.get('readings', [])
            
            # Add to list (allowing duplicates)
            persons_list.append(person_copy)
            
        serialized_persons = PersonCommunicationSerializer(persons_list, many=True).data
        return Response({
            'persons': serialized_persons
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
            group_permissions = PermissionManager.get_model_group_permissions(group, 'person')
            return Response(group_permissions, status=status.HTTP_200_OK)
        permissions = PermissionManager.get_model_permissions(request.user, 'person', 'coredata')
        return Response(permissions, status=status.HTTP_200_OK)
    
    def get_permissions(self):
        if self.action == 'permissions':
            return [IsAuthenticated()]
        return super().get_permissions()

class PersonAddressViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows Person addresses to be viewed or edited.
    """
    queryset = PersonAddress.objects.all().order_by('id')
    serializer_class = PersonAddressSerializer
    permission_classes = [IsAuthenticated, PersonPermission]
    filter_backends = [DjangoFilterBackend, OrderingFilter, SearchFilter]
    filterset_class = PersonAddressFilter
    search_fields = ['token',]
    ordering_fields = ['token',]

class PersonByTokenViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows Street to be viewed or edited.
    """
    queryset = Person.objects.all().order_by('name')
    serializer_class = PersonSerializer
    permission_classes = [IsAuthenticated, PersonPermission]
    filter_backends = [DjangoFilterBackend, OrderingFilter, SearchFilter]
    lookup_field = 'token'

    def get_queryset(self):
        token = self.kwargs.get('token')
        print(token)
        person = Person.objects.filter(token=token)
        if person.exists():
            return person
        else:
            raise Http404("Person not found")

    def retrieve(self, request, *args, **kwargs):
        # Hi ha documents genèrics (p. ex. 99999999R) compartits per centenars de persones:
        # el detall per token no en pot triar cap.
        count = self.get_queryset().count()
        if count > 1:
            return Response(
                {'detail': f"Hi ha {count} persones amb el document {self.kwargs.get('token')}.", 'count': count},
                status=status.HTTP_409_CONFLICT,
            )
        return super().retrieve(request, *args, **kwargs)
