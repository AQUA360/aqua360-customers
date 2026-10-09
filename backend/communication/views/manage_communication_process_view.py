import re
from datetime import datetime, time as datetime_time
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from django.db.models import Q, Prefetch
from django.utils import timezone
from django.utils.dateparse import parse_date
from claimrequest.models import ClaimRequestPayment
from celery.result import AsyncResult
from communication.models import Communication, CommunicationProcess
from communication.tasks import get_communication_process_data
from communication.serializers.communication_serializer import CommunicationListSerializer, CommunicationMinimalSerializer
from contract.models import Contract
from coredata.models import Address, ConfigProject, Person, PersonAddress, PersonContact
from service.models import SupplyCut, SupplyPoint
from billing.models import Invoice, Payment

# Cache for config tokens to avoid repeated DB queries
_CONFIG_CACHE = {}

# Tipus d'adreça acceptats per als filtres de destinataris. S'ha de validar
# explícitament: un valor desconegut a filter_by_contract acabaria ignorant el
# selector d'adreça i validant el destinatari amb uns criteris diferents dels
# que demana l'usuari, en silenci.
ADDRESS_TYPES = ('default', 'contract', 'invoice')

def get_config_token(token_key):
    """Get config value with caching to avoid repeated DB queries"""
    if token_key not in _CONFIG_CACHE:
        try:
            _CONFIG_CACHE[token_key] = ConfigProject.objects.get(token=token_key).value
        except ConfigProject.DoesNotExist:
            _CONFIG_CACHE[token_key] = None
    return _CONFIG_CACHE[token_key]

def company_filter(filter_data, prefix=''):
    """Exclou els contractes assignats a una empresa diferent de la seleccionada al pas 1
    (només quan el projecte fa servir múltiples empreses). Els contractes sense empresa es mantenen."""
    company = filter_data.get('company')
    if not company:
        return Q()
    return Q(**{f'{prefix}company__id': company}) | Q(**{f'{prefix}company__isnull': True})

def get_person_full_name(person):
    
    if person.surname:
        full_name = f"{person.name} {person.surname}".strip()
    else:
        full_name = person.name.strip() if person.name else ""
    
    return re.sub(r'\s+', ' ', full_name).strip()

def build_person_data_fast(person):
    """
    Fast person data builder without serializer overhead.
    Returns minimal person information with communication capability flags.
    """
    # Check if person has active contacts with phone/email
    has_sms = False
    has_email = False
    has_electronic_invoice = False
    for contact in person.contacts.all():
        if contact.is_active:
            if contact.phone and not has_sms:
                has_sms = True
            if contact.email and not has_email:
                has_email = True
            if has_sms and has_email:
                break
    
    # Check if person has active addresses
    has_address = any(addr.is_active for addr in person.addresses.all())
    
    return {
        'id': person.id,
        'token': person.token,  # Keep token for grouping logic
        'full_name': get_person_full_name(person),
        'has_email': has_email,
        'has_sms': has_sms,
        'has_address': has_address,
        'has_electronic_invoice': has_electronic_invoice
    }

class ManageCommunicationProcessViewSet(APIView):
    permission_classes = [IsAuthenticated, DjangoModelPermissions]
    queryset = Communication.objects.all().order_by('-created_at')
    def post(self, request, *args, **kwargs):
        try:
            task = get_communication_process_data.delay(request.data)
            return Response({"task_id": task.id}, status=status.HTTP_202_ACCEPTED)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        # persons = []
        # time_start = time.time()
        
        # if filter_type == 'CONTRACT':
        #     persons = filter_by_contract(filter_data, group_same)
        # elif filter_type == 'BILLING':
        #     persons = filter_by_billing(filter_data, group_same)
        # elif filter_type == 'CONTRACTREQUEST':
        #     persons = filter_by_contract_request(filter_data, group_same)
        # elif filter_type == 'ADDRESS':
        #     persons = filter_by_address(filter_data, group_same)
        # elif filter_type == 'PERSON':
        #     persons = filter_by_person(filter_data, group_same)
        # elif filter_type == 'SUPPLYPOINT':
        #     persons = filter_by_supply_point(filter_data, group_same)
        # elif filter_type == 'COMMUNICATION':
        #     persons = filter_by_communication(filter_data, group_same)
        # elif filter_type == 'DRAFT':
        #     persons = filter_by_draft(filter_data, group_same)
        # elif filter_type == 'FIXED':
        #     if 'entity' in filter_data and filter_data['entity'] == 'billing':
        #         persons = filter_by_fixed_billing(filter_data, group_same)
        #     elif 'entity' in filter_data and filter_data['entity'] == 'claimrequest':
        #         persons = filter_by_claim_request(filter_data, group_same)
        #     elif 'entity' in filter_data and filter_data['entity'] == 'sepa_payments':
        #         persons = filter_by_sepa_remittance(filter_data, group_same)
        # time_end = time.time()
        # print(f"Time taken: {time_end - time_start} seconds")
        # return Response({"persons": persons}, status=status.HTTP_202_ACCEPTED)

def filter_by_draft(filter_data, group_same):
    print("filter_by_draft")
    print(filter_data)
    print(group_same)
    process_id = filter_data.get('id', None)
    communication_process = CommunicationProcess.objects.get(id=process_id)
    readings = communication_process.readings.all()
    
    persons_dict = {}
    
    contract_info = None
    contract_email = None

    persons_dict = {}
    
    if readings.exists():
        for reading in readings:
            print("reading: ", reading)
            person = reading.contract.holder
            person_data = build_person_data_fast(person)
            
            person_data['exclude'] = False
            
            if reading.contract:
                contract_info = {
                    'id': reading.contract.id,
                    'token': reading.contract.token,
                    'supply_address': str(reading.contract.supply_point_default.address) if reading.contract.supply_point_default else None,
                }
                person_data['has_electronic_reading'] = False
                # Get email from contract's person_contact_email
                if reading.contract.person_contact_email and reading.contract.person_contact_email.email:
                    contract_email = reading.contract.person_contact_email.email.strip().lower()
            
            reading_info = {
                'id': reading.id,
                'meter_code': reading.meter.code,
                'reading_date': reading.reading_date,
                'reading_value': reading.reading_value,
                'calculated_value': reading.calculated_value,
                'leak_value': reading.leak_value,
                'origin': reading.origin,
            }
            
            
            if len(group_same) > 0:
                # Include email in grouping key so contracts of the same person
                # with different configured emails are not merged together
                email_part = contract_email if contract_email else ""
                group_key = f"{person_data['token']}|{email_part}"

                if group_key in persons_dict:
                    # Add to existing group
                    persons_dict[group_key]['total_communication'] += 1
                    persons_dict[group_key]['contracts'].append(contract_info)
                    persons_dict[group_key]['readings'].append(reading_info)
                else:
                    # Create new group
                    person_data['contracts'] = [contract_info]
                    person_data['total_communication'] = 1
                    persons_dict[group_key] = person_data
                    persons_dict[group_key]['readings'] = [reading_info]
            else:
                # No grouping - each person/contract is separate
                unique_key = f"{person_data['token']}|{reading.contract.id}"
                person_data['contracts'] = [contract_info]
                person_data['readings'] = [reading_info]
                person_data['total_communication'] = 1
                persons_dict[unique_key] = person_data
            
    persons = list(persons_dict.values())
    persons.sort(key=lambda x: x['id'])
    return persons


def filter_by_communication(filter_data, group_same):
    comm_end_created_date = filter_data.get('comm_end_created_date', None)
    comm_start_created_date = filter_data.get('comm_start_created_date', None)
    comm_statuses = filter_data.get('comm_statuses', [])
    in_process = filter_data.get('in_process', False)
    comm_types = filter_data.get('comm_types', [])
    comm_use_types = filter_data.get('comm_use_types', [])
    contains_invoices = filter_data.get('containsInvoices', [])
    contains_readings = filter_data.get('containsReadings', [])
    contract_ids = [contract['id'] for contract in filter_data.get('contracts', [])]
    person_ids = [person['id'] for person in filter_data.get('persons', [])]
    message_types = filter_data.get('message_types', [])
    
    filters = Q(process__isnull=(not in_process))
    if comm_end_created_date:
        parsed_created_date = parse_date(comm_end_created_date) if isinstance(comm_end_created_date, str) else None
        if parsed_created_date:
            end_of_day = datetime.combine(parsed_created_date, datetime_time.max)
            filters &= Q(created_at__lte=timezone.make_aware(end_of_day)) | Q(created_at__isnull=True)
        else:
            filters &= Q(created_at__lte=comm_end_created_date) | Q(created_at__isnull=True)
    
    if comm_start_created_date:
        parsed_created_date = parse_date(comm_start_created_date) if isinstance(comm_start_created_date, str) else None
        if parsed_created_date:
            start_of_day = datetime.combine(parsed_created_date, datetime_time.min)
            filters &= Q(created_at__gte=timezone.make_aware(start_of_day)) | Q(created_at__isnull=True)
        else:
            filters &= Q(created_at__gte=comm_start_created_date) | Q(created_at__isnull=True)
    if len(comm_statuses) > 0:
        filters &= Q(status__id__in=comm_statuses)
    if len(comm_types) > 0:
        filters &= Q(types__id__in=comm_types)
    if len(comm_use_types) > 0:
        filters &= Q(use_type__id__in=comm_use_types)
    if contract_ids:
        filters &= Q(contracts__id__in=contract_ids)
    if person_ids:
        filters &= Q(person__id__in=person_ids)
    if len(message_types) > 0:
        filters &= Q(types__token__in=message_types)
        
    if 'has_invoices' in contains_invoices and not 'no_has_invoices' in contains_invoices:
        filters &= Q(invoices__isnull=False)
    if 'no_has_invoices' in contains_invoices and not 'has_invoices' in contains_invoices:
        filters &= Q(invoices__isnull=True)
    if 'has_readings' in contains_readings and not 'no_has_readings' in contains_readings:
        filters &= Q(readings__isnull=False)
    if 'no_has_readings' in contains_readings and not 'has_readings' in contains_readings:
        filters &= Q(readings__isnull=True)
    
    print("filters communication")
    print(filters)
    
    communications = Communication.objects.filter(filters)
    if filter_data.get('company'):
        communications = communications.exclude(
            contracts__in=Contract.objects.exclude(company_filter(filter_data))
        ).distinct()
    serialized_communications = CommunicationListSerializer(communications, many=True).data
    return serialized_communications

def filter_by_contract(filter_data, group_same):
    filters = Q()
    contract_ids = [contract['id'] for contract in filter_data.get('contracts', [])]
    use_types = filter_data.get('use_types', [])
    client_types = filter_data.get('client_types', [])
    categories = filter_data.get('categories', [])
    contract_statuses = filter_data.get('contract_statuses', [])
    rejection_reasons = filter_data.get('rejection_reasons', [])
    address_type = filter_data.get('address_type', 'default')
    person_types = filter_data.get('person_type', ['holder'])
    message_types = filter_data.get('message_types', [])
    
    contract_status_token = get_config_token('contract_active_token')
    
    # Only apply default status filter if no specific statuses are provided
    if len(contract_statuses) > 0:
        filters &= Q(status__id__in=contract_statuses)
    else:
        filters &= Q(status__token=contract_status_token)
    
    filters &= Q(is_active=True)
    filters &= company_filter(filter_data)
    if len(contract_ids) > 0:
        filters &= Q(id__in=contract_ids)
    if len(use_types) > 0:
        filters &= Q(use_type__id__in=use_types)
    if len(client_types) > 0:
        filters &= Q(client_type__id__in=client_types)
    if len(categories) > 0:
        filters &= Q(category__id__in=categories)
    if len(rejection_reasons) > 0:
        filters &= Q(invoice__payments__reject__id__in=rejection_reasons)
    
    if 'debt_managements' in filter_data:
        include_null = "null" in filter_data.get('debt_managements', []) or len(filter_data.get('debt_managements', [])) == 0
        debt_managements = [v for v in filter_data.get('debt_managements', []) if v != "null"]
        debt_query = Q()
        if debt_managements:
            debt_query |= Q(debt_management__id__in=debt_managements)
        if include_null:
            debt_query |= Q(debt_management__isnull=True)
        filters &= debt_query

    # Build the base queryset with all necessary relations
    base_qs = Contract.objects.filter(filters).select_related(
        'use_type',
        'client_type',
        'category',
        'status',
        'debt_management',
        'holder',
        'address_contact',
        'person_contact_email',
        'supply_point_default',
        'supply_point_default__address'
    )
    

    # Add person-type specific prefetches
    prefetch_map = {}
    for person_type in person_types:
        base_qs = base_qs.select_related(person_type)
        
        # Always prefetch contacts to avoid N+1 in serializer
        prefetch_map[f'{person_type}__contacts'] = Prefetch(
            f'{person_type}__contacts',
            queryset=PersonContact.objects.filter(is_active=True)
        )
        
        if address_type == 'default':
            # Prefetch addresses for each person type
            prefetch_map[f'{person_type}__addresses'] = Prefetch(
                f'{person_type}__addresses',
                queryset=PersonAddress.objects.filter(
                    is_active=True
                ).select_related('address', 'address__city', 'address__province', 'address__country', 'address__street', 'address__street_number')
            )

    if prefetch_map:
        base_qs = base_qs.prefetch_related(*prefetch_map.values())

    # No limits - process all contracts
    contracts = base_qs.distinct()
    
    # Use dictionary for O(1) lookup instead of O(n) linear search
    persons_dict = {}
    
    for contract in contracts:
        contract_has_valid_person = False
        for person_type in person_types:
            person = getattr(contract, person_type, None)
            if not person:
                continue
            
            # Validate person has communication methods
            if address_type == 'default':
                if not check_person_communication(person, message_types, contract):
                    continue
            elif address_type == 'contract':
                if not check_person_communication_by_contract(contract, message_types):
                    continue
            
            # Use fast builder instead of serializer
            person_data = build_person_data_fast(person)
            person_data['exclude'] = False
            
            # Build contract info
            contract_info = {
                'id': contract.id,
                'token': contract.token,
                'supply_address': str(contract.supply_point_default.address) if contract.supply_point_default else None,
            }
            if contract and contract.payment and contract.payment.accounting_office:
                person_data['has_electronic_invoice'] = True

            # Get email from contract's person_contact_email
            contract_email = None
            if contract.person_contact_email and contract.person_contact_email.email:
                contract_email = contract.person_contact_email.email.strip().lower()

            if len(group_same) > 0:
                # Include email in grouping key so contracts of the same person
                # with different configured emails are not merged together
                email_part = contract_email if contract_email else ""
                group_key = f"{person_data['token']}|{email_part}"

                if group_key in persons_dict:
                    # Add to existing group
                    persons_dict[group_key]['total_communication'] += 1
                    persons_dict[group_key]['contracts'].append(contract_info)
                else:
                    # Create new group
                    person_data['contracts'] = [contract_info]
                    person_data['total_communication'] = 1
                    persons_dict[group_key] = person_data
            else:
                # No grouping - each person/contract is separate
                unique_key = f"{person_data['token']}|{contract.id}"
                person_data['contracts'] = [contract_info]
                person_data['total_communication'] = 1
                persons_dict[unique_key] = person_data
            
            contract_has_valid_person = True
    
    # Convert dictionary to list and sort once at the end
    persons = list(persons_dict.values())
    persons.sort(key=lambda x: x['id'])
    
    return persons

def filter_by_contract_request(filter_data, group_same):
    filters = Q()
    contract_ids = [contract['id'] for contract in filter_data.get('contracts', [])]
    contract_statuses = filter_data.get('contract_statuses', [])
    clauses = filter_data.get('clauses', [])
    
    person_types = filter_data.get('person_type', ['holder'])
    message_types = filter_data.get('message_types', [])
    address_type = filter_data.get('address_type', 'default')

    if len(contract_ids) > 0:
        filters &= Q(id__in=contract_ids)
    if len(contract_statuses) > 0:
        filters &= Q(status__id__in=contract_statuses)
    if len(clauses) > 0:
        filters &= Q(clauses__id__in=clauses)
    filters &= company_filter(filter_data)
    
    base_qs = Contract.objects.filter(filters).select_related(
        'holder', 
        'address_contact', 
        'person_contact_email',
        'supply_point_default',
        'supply_point_default__address'
    )

    prefetch_map = {}
    for person_type in person_types:
        base_qs = base_qs.select_related(person_type)
        
        # Always prefetch contacts to avoid N+1 in serializer
        prefetch_map[f'{person_type}__contacts'] = Prefetch(
            f'{person_type}__contacts',
            queryset=PersonContact.objects.filter(is_active=True)
        )
        
        if address_type == 'default':
            prefetch_map[f'{person_type}__addresses'] = Prefetch(
                f'{person_type}__addresses',
                queryset=PersonAddress.objects.filter(
                    is_active=True
                ).select_related('address', 'address__city', 'address__province', 'address__country', 'address__street', 'address__street_number')
            )

    if prefetch_map:
        base_qs = base_qs.prefetch_related(*prefetch_map.values())

    # No limits - process all contracts
    contracts = base_qs.distinct()
    
    # Use dictionary for O(1) lookup instead of O(n) linear search
    persons_dict = {}
    
    for contract in contracts:
        contract_has_valid_person = False
        for person_type in person_types:
            person = getattr(contract, person_type, None)
            if not person:
                continue
            
            # Validate person has communication methods
            if address_type == 'default':
                if not check_person_communication(person, message_types, contract):
                    continue
            elif address_type == 'contract':
                if not check_person_communication_by_contract(contract, message_types):
                    continue
            
            # Use fast builder instead of serializer
            person_data = build_person_data_fast(person)
            person_data['exclude'] = False
            
            # Build contract info
            contract_info = {
                'id': contract.id,
                'token': contract.token,
                'supply_address': str(contract.supply_point_default.address) if contract.supply_point_default else None,
            }

            # Get email from contract's person_contact_email
            contract_email = None
            if contract.person_contact_email and contract.person_contact_email.email:
                contract_email = contract.person_contact_email.email.strip().lower()

            if len(group_same) > 0:
                # Include email in grouping key so contracts of the same person
                # with different configured emails are not merged together
                email_part = contract_email if contract_email else ""
                group_key = f"{person_data['token']}|{email_part}"

                if group_key in persons_dict:
                    persons_dict[group_key]['total_communication'] += 1
                    persons_dict[group_key]['contracts'].append(contract_info)
                else:
                    person_data['contracts'] = [contract_info]
                    person_data['total_communication'] = 1
                    persons_dict[group_key] = person_data
            else:
                unique_key = f"{person_data['token']}|{contract.id}"
                person_data['contracts'] = [contract_info]
                person_data['total_communication'] = 1
                persons_dict[unique_key] = person_data
            
            contract_has_valid_person = True
    
    # Convert dictionary to list and sort once at the end
    persons = list(persons_dict.values())
    persons.sort(key=lambda x: x['id'])
    
    return persons

def filter_by_billing(filter_data, group_same):
    filters = Q()
    invoice_ids = [invoice['id'] for invoice in filter_data.get('invoices', [])]
    billing_ids = [billing['id'] for billing in filter_data.get('billings', [])]
    invoice_statuses = filter_data.get('invoice_statuses', [])
    origins = filter_data.get('origins', [])
    rejection_reasons = filter_data.get('rejection_reasons', [])
    rejection_types = filter_data.get('rejection_types', [])
    payment_types = filter_data.get('payment_types', [])
    expire_start_date = filter_data.get('expire_start_date', None)
    expire_end_date = filter_data.get('expire_end_date', None)
    issue_start_date = filter_data.get('issue_start_date', None)
    issue_end_date = filter_data.get('issue_end_date', None)
    return_start_date = filter_data.get('return_start_date', None)
    return_end_date = filter_data.get('return_end_date', None)
    consumption = filter_data.get('consumption', None)
    modification = filter_data.get('modification', None)
    series = filter_data.get('series', None)
    companies = filter_data.get('companies', [])
    address_type = filter_data.get('address_type', 'default')
    message_types = filter_data.get('message_types', [])
    group_by_customer = filter_data.get('group_by_customer', False)
    
    if len(invoice_ids) > 0:
        filters &= Q(id__in=invoice_ids)
    if len(billing_ids) > 0:
        filters &= Q(billing__id__in=billing_ids)
    if len(invoice_statuses) > 0:
        filters &= Q(status__id__in=invoice_statuses)
    if len(origins) > 0:
        filters &= Q(origin__id__in=origins)
    if len(rejection_reasons) > 0:
        filters &= Q(payments__reject__id__in=rejection_reasons)
        filters &= Q(reject__id__in=rejection_reasons)
    if len(rejection_types) > 0:
        filters &= Q(payments__reject__type__id__in=rejection_types)
        filters &= Q(reject__type__id__in=rejection_types)
    if len(payment_types) > 0:
        filters &= Q(payment_type_token_final__in=payment_types)
    if len(companies) > 0:
        filters &= Q(company__id__in=companies)
    filters &= company_filter(filter_data, 'contract__')
    if expire_start_date:
        filters &= Q(due_date__gte=expire_start_date)
    if expire_end_date:
        filters &= Q(due_date__lte=expire_end_date)
    if issue_start_date:
        filters &= Q(sent_at__gte=issue_start_date)
    if issue_end_date:
        filters &= Q(sent_at__lte=issue_end_date)
    if return_start_date:
        filters &= Q(payments__reject_date__gte=return_start_date)
    if return_end_date:
        filters &= Q(payments__reject_date__lte=return_end_date)
    if series:
        filters &= Q(serie_token_final__in=series)
    if consumption:
        consumption_filter = Q()
        if 'responsible_consumption' in consumption:
            consumption_filter |= Q(responsible_consumption=True)
        if 'irresponsible_consumption' in consumption:
            consumption_filter |= Q(responsible_consumption=False)
        filters &= consumption_filter
    if modification:
        modification_filter = Q()
        if 'manually_modified' in modification:
            modification_filter |= Q(manually_modified=True)
        if 'not_modified' in modification:
            modification_filter |= Q(manually_modified=False)
        filters &= modification_filter
    
    
    # Optimize: prefetch all related data to avoid N+1 queries - NO LIMITS
    invoices = Invoice.objects.filter(filters).select_related(
        'contract', 
        'contract__holder',
        'contract__address_contact',
        'contract__address_contact__address',
        'contract__address_contact__address__city',
        'contract__address_contact__address__province',
        'contract__person_contact_email',
        'contract__supply_point_default',
        'contract__supply_point_default__address'
    ).prefetch_related(
        'contract__person_contact_sms'
    )
    
    # Pre-fetch all persons in bulk to avoid repeated queries
    person_identifiers = {}
    for inv in invoices:
        if inv.customer_token_final and inv.customer_final:
            
            normalized_name = re.sub(r'\s+', ' ', inv.customer_final.strip()).strip()
            key = (inv.customer_token_final, normalized_name)
            person_identifiers[key] = True
    
    person_objects = {}
    if person_identifiers:
        # Get all unique tokens
        person_tokens = list(set([token for token, _ in person_identifiers.keys()]))
        # Fetch all persons with these tokens
        persons = Person.objects.filter(token__in=person_tokens).prefetch_related(
            Prefetch('contacts', queryset=PersonContact.objects.filter(is_active=True)),
            Prefetch('addresses', queryset=PersonAddress.objects.filter(is_active=True).select_related(
                'address', 'address__city', 'address__province', 'address__country', 'address__street', 'address__street_number'
            ))
        )
        
        for person in persons:
            person_full_name = get_person_full_name(person)
            if person.token:
                key = (person.token, person_full_name)
                person_objects[key] = person
    
    persons_dict = {}
    
    for invoice in invoices:
        if not invoice.customer_token_final or not invoice.customer_final:
            continue
        # Use composite key (token, customer_final) for lookup
        normalized_name = re.sub(r'\s+', ' ', invoice.customer_final.strip()).strip()
        lookup_key = (invoice.customer_token_final, normalized_name)
        person = person_objects.get(lookup_key)

        if not person:
            continue
        
        # Validate person has communication methods
        if address_type == 'default':
            if not check_person_communication(person, message_types, invoice.contract):
                continue
        elif address_type == 'contract':
            if not invoice.contract:
                continue
            if not check_person_communication_by_contract(invoice.contract, message_types):
                continue
        elif address_type == 'invoice':
            if not check_person_communication_by_invoice(invoice, message_types):
                continue
        
        # Use fast builder instead of serializer (10x faster)
        person_data = build_person_data_fast(person)
        person_data['exclude'] = False
        
        # Build contract and invoice info
        contract_info = None
        contract_email = None
        if invoice.contract:
            contract_info = {
                'id': invoice.contract.id,
                'token': invoice.contract.token,
                'supply_address': str(invoice.contract.supply_point_default.address) if invoice.contract.supply_point_default else None,
            }
            if invoice.contract and invoice.accounting_office_final:
                    person_data['has_electronic_invoice'] = True
            # Get email from contract's person_contact_email
            if invoice.contract.person_contact_email and invoice.contract.person_contact_email.email:
                contract_email = invoice.contract.person_contact_email.email.strip().lower()
        
        invoice_info = {
            'id': invoice.id,
            'serie_final': invoice.serie_final,
        }
        
        if len(group_same) > 0:
            # Include email in grouping key to separate persons with different emails by contract
            email_part = contract_email if contract_email else ""
            group_key = f"{person_data['token']}|{person_data['full_name']}|{email_part}"
            
            if group_key in persons_dict:
                persons_dict[group_key]['total_communication'] += 1
                if contract_info and contract_info not in persons_dict[group_key]['contracts']:
                    persons_dict[group_key]['contracts'].append(contract_info)
                persons_dict[group_key]['invoices'].append(invoice_info)
            else:
                person_data['contracts'] = [contract_info] if contract_info else []
                person_data['invoices'] = [invoice_info]
                person_data['total_communication'] = 1
                persons_dict[group_key] = person_data
        else:
            # Include email in unique key as well
            email_part = contract_email if contract_email else ""
            unique_key = f"{person_data['token']}|{person_data['full_name']}|{email_part}|{invoice.id}"
            person_data['contracts'] = [contract_info] if contract_info else []
            person_data['invoices'] = [invoice_info]
            person_data['total_communication'] = 1
            persons_dict[unique_key] = person_data
    
    # Convert dictionary to list and sort once at the end
    persons = list(persons_dict.values())
    persons.sort(key=lambda x: x['id'])

    return persons

def filter_by_address(filter_data, group_same):
    filters = Q()
    street = filter_data.get('street', None)
    postal_code = filter_data.get('postal_code', None)
    city = filter_data.get('city', None)
    province = filter_data.get('province', None)
    address_ids = [address['id'] for address in filter_data.get('addresses', [])]
    address_type = filter_data.get('address_type', 'default')
    message_types = filter_data.get('message_types', [])
    
    contract_status_token = get_config_token('contract_active_token')
    
    if (address_ids):
        filters &= Q(id__in=address_ids)
    if (street):
        filters &= Q(street__id=street)
    if (postal_code):
        filters &= Q(postal_code__icontains=postal_code)
    if (city):
        filters &= Q(city__id=city)
    if (province):
        filters &= Q(province__id=province)
    
    addresses = Address.objects.filter(filters)
    persons = []
    
    if address_type == 'contract':
        contracts = Contract.objects.filter( address_contact__address__in=addresses, status__token=contract_status_token, is_active=True
        ).select_related('holder','address_contact','address_contact__address','address_contact__address__city','address_contact__address__province','person_contact_email'
        ).prefetch_related(
            'person_contact_sms'
        )
        
        if len(contracts) > 0:
            filter_contract_data = {
                    'company': filter_data.get('company'),
                    'message_types': message_types,
                    'contracts': [{'id': contract.id} for contract in contracts],
                    'person_type': ['holder', 'tenant', 'owner'],
                    'address_type': 'contract'
                }
            persons = filter_by_contract(filter_contract_data, group_same)
        
            
    elif address_type == 'default':
        # Prefetch person contacts to avoid N+1
        person_addresses = PersonAddress.objects.filter(
            address__in=addresses, is_active=True
        ).select_related('person', 'address').prefetch_related(
            Prefetch('person__contacts', queryset=PersonContact.objects.filter(is_active=True)),
            Prefetch('person__addresses', queryset=PersonAddress.objects.filter(is_active=True).select_related(
                'address', 'address__city', 'address__province', 'address__country', 'address__street', 'address__street_number'
            ))
        )
        
        # Use dictionary for O(1) lookup
        persons_dict = {}
        
        for person_address in person_addresses:
            person = person_address.person
            
            # Validate person has communication methods
            if not check_person_communication(person, message_types):
                continue
            
            # Use fast builder instead of serializer
            person_data = build_person_data_fast(person_address.person)
            person_data['exclude'] = False
            
            if len(group_same) > 0:
                # Create grouping key
                group_key = person_data['token']
                
                if group_key in persons_dict:
                    persons_dict[group_key]['total_communication'] += 1
                else:
                    person_data['total_communication'] = 1
                    persons_dict[group_key] = person_data
            else:
                unique_key = f"{person_data['token']}|{person_address.id}"
                person_data['total_communication'] = 1
                persons_dict[unique_key] = person_data
    
    persons = list(persons_dict.values())
    persons.sort(key=lambda x: x['id'])
    return persons

def filter_by_person(filter_data, group_same):
    filters = Q()
    person_ids = [person['id'] for person in filter_data.get('persons', [])]
    bank = filter_data.get('bank', None)
    vulnerability = [int(v) for v in filter_data.get('vulnerability', [])]
    morosity = filter_data.get('morosity', [])
    juridic = filter_data.get('juridic', [])
    address_type = filter_data.get('address_type', 'default')
    message_types = filter_data.get('message_types', [])
    
    if len(person_ids) > 0:
        filters &= Q(id__in=person_ids)
    if len(vulnerability) > 0:
        filters &= Q(vulnerability_level__in=vulnerability)
    if len(morosity) > 0:
        if 'is_not_debtor' in morosity:
            filters &= Q(deliquency__isnull=True) | Q(deliquency__is_debtor=False)
        if 'is_debtor' in morosity:
            filters &= Q(deliquency__isnull=False) & Q(deliquency__is_debtor=True)
    if len(juridic):
        juridic_filter = Q()
        if '0' in juridic:
            juridic_filter |= Q(is_juridic=False)
        if '1' in juridic:
            juridic_filter |= Q(is_juridic=True)
        filters &= juridic_filter
    if bank:
        filters &= Q(banks__bank__id=bank)
    
    # Prefetch related data to avoid N+1 queries
    filtered_persons = Person.objects.filter(filters).prefetch_related(
        Prefetch('contacts', queryset=PersonContact.objects.filter(is_active=True)),
        Prefetch('addresses', queryset=PersonAddress.objects.filter(is_active=True).select_related(
            'address', 'address__city', 'address__province', 'address__country', 'address__street', 'address__street_number'
        ))
    )
    
    persons_dict = {}
    if address_type == 'default':
        for person in filtered_persons:
            # Validate person has communication methods
            if not check_person_communication(person, message_types):
                continue
            
            # Use fast builder instead of serializer
            person_data = build_person_data_fast(person)
            person_data['exclude'] = False
            
            if len(group_same) > 0:
                # Create grouping key
                group_key = person_data['token']
                
                if group_key in persons_dict:
                    persons_dict[group_key]['total_communication'] += 1
                else:
                    person_data['total_communication'] = 1
                    persons_dict[group_key] = person_data
            else:
                unique_key = f"{person_data['token']}|{person.id}"
                person_data['total_communication'] = 1
                persons_dict[unique_key] = person_data
        
    elif address_type == 'contract':
        print("filtered persons")
        for person in filtered_persons:
            print(person)
        contract_status_token = get_config_token('contract_active_token')
        #GET ONLY HOLDERS
        contracts = Contract.objects.filter( Q(holder__in=filtered_persons) ).filter(
                status__token=contract_status_token, is_active=True
                ).distinct().select_related('holder','address_contact','address_contact__address','address_contact__address__city','address_contact__address__province','person_contact_email'
        ).prefetch_related(
            'person_contact_sms'
        )
        """  contracts = Contract.objects.filter(
            Q(holder__in=filtered_persons) | Q(tenant__in=filtered_persons) | Q(owner__in=filtered_persons)
            ).filter(
                status__token=contract_status_token, is_active=True
                ).distinct().select_related('holder','address_contact','address_contact__address','address_contact__address__city','address_contact__address__province','person_contact_email'
        ).prefetch_related(
            'person_contact_sms'
        ) """
        
        
        if len(contracts) > 0:
            filter_contract_data = {
                    'company': filter_data.get('company'),
                    'message_types': message_types,
                    'contracts': [{'id': contract.id} for contract in contracts],
                    'person_type': ['holder'],
                    'address_type': 'contract'
                }
            return filter_by_contract(filter_contract_data, group_same)  # Already sorted
    
    # Convert dictionary to list and sort
    persons = list(persons_dict.values())
    persons.sort(key=lambda x: x['id'])
    return persons

def filter_by_supply_point(filter_data, group_same):
    filters = Q()
    supply_point_ids = [supply_point['id'] for supply_point in filter_data.get('supply_points', [])]
    statuses = filter_data.get('statuses', [])
    types = filter_data.get('types', [])
    supply_types = filter_data.get('supply_types', [])
    connection_types = filter_data.get('connection_types', [])
    sources = filter_data.get('sources', [])
    exploitation = filter_data.get('exploitation', None)
    connection = filter_data.get('connection', None)
    installed_at_start_date = filter_data.get('installed_at_start_date', None)
    installed_at_end_date = filter_data.get('installed_at_end_date', None)
    message_types = filter_data.get('message_types', [])
    
    persons = []
    
    if len(supply_point_ids) > 0:
        filters &= Q(id__in=supply_point_ids)
    if len(statuses) > 0:
        filters &= Q(status__id__in=statuses)
    if len(types):
        filters &= Q(type__id__in=types)
    if len(supply_types):
        filters &= Q(supply_type__id__in=supply_types)
    if len(connection_types):
        filters &= Q(connection__type__id__in=connection_types)
    if len(sources):
        filters &= Q(source__id__in=sources)
    if exploitation:
        filters &= Q(connection__exploitation__id=exploitation)
    if connection:
        filters &= Q(connection__id=connection)
    if installed_at_start_date:
        filters &= Q(installation_at__gte=installed_at_start_date)
    if installed_at_end_date:
        filters &= Q(installation_at__lte=installed_at_end_date)
        
    supply_points = SupplyPoint.objects.filter(filters)
    print("supply_points")
    print(supply_points)
    supply_point_contracts = Contract.objects.filter(supply_points__in=supply_points).distinct()
    print("supply_point_contracts")
    print(supply_point_contracts)
    
    if len(supply_point_contracts) > 0:
        filter_contract_data = {
            'company': filter_data.get('company'),
            'message_types': message_types,
            'contracts': [{'id': contract.id} for contract in supply_point_contracts],
            'person_type': ['holder', 'tenant', 'owner'],
            'address_type': 'contract'
        }
        
        persons = filter_by_contract(filter_contract_data, group_same)
    
    return persons

def filter_by_supply_cut(filter_data, group_same):
    """Destinataris dels contractes afectats per un o més talls de subministrament.

    Accepta tant la cerca genèrica (type SUPPLYCUT, amb `supply_cuts`) com el
    objecte fixat des d'un tall concret (type FIXED, entity supplycut, amb `id`).
    """
    filters = Q()
    object_id = filter_data.get('id', None)
    cut_ids = [cut['id'] for cut in filter_data.get('supply_cuts', [])]
    statuses = filter_data.get('statuses', [])
    causes = filter_data.get('causes', [])
    date_start = filter_data.get('date_start', None)
    date_end = filter_data.get('date_end', None)
    exec_start = filter_data.get('exec_start', None)
    exec_end = filter_data.get('exec_end', None)
    message_types = filter_data.get('message_types', [])
    # Adreça on s'envia la comunicació. El pas 1 la tria explícitament; si no
    # arriba (objecte fixat, p. ex. la notificació d'un tall) l'adreça és la del
    # punt de subministrament, com fa filter_by_supply_point. No es fa servir
    # 'default' per defecte: check_person_communication exigeix correu/adreça de
    # la persona i deixa fora gent que es pot notificar igualment.
    address_type = filter_data.get('address_type', None) or 'contract'
    if address_type not in ADDRESS_TYPES:
        raise ValueError(f"Unknown address_type: {address_type!r}")

    persons = []

    if object_id:
        filters &= Q(id=object_id)
    if len(cut_ids) > 0:
        filters &= Q(id__in=cut_ids)
    if len(statuses) > 0:
        filters &= Q(status__id__in=statuses)
    if len(causes) > 0:
        filters &= Q(cause__id__in=causes)
    if date_start:
        filters &= Q(date_start__gte=date_start)
    if date_end:
        filters &= Q(date_start__lte=date_end)
    if exec_start:
        filters &= Q(exec_start__gte=exec_start)
    if exec_end:
        filters &= Q(exec_start__lte=exec_end)

    supply_cuts = SupplyCut.objects.filter(filters)
    cut_contracts = Contract.objects.filter(
        supply_points__supply_cuts__in=supply_cuts).distinct()

    if len(cut_contracts) > 0:
        filter_contract_data = {
            'company': filter_data.get('company'),
            'message_types': message_types,
            'contracts': [{'id': contract.id} for contract in cut_contracts],
            'person_type': ['holder', 'tenant', 'owner'],
            'address_type': address_type
        }

        persons = filter_by_contract(filter_contract_data, group_same)

    return persons

def filter_by_fixed_billing(filter_data, group_same):
    object_id = filter_data.get('id', None)
    message_types = filter_data.get('message_types', [])
    statuses = filter_data.get('statuses', [])
    payment_types = filter_data.get('payment_types', [])
    payment_types = filter_data.get('payment_types', [])
    issue_start_date = filter_data.get('issue_start_date', None)
    issue_end_date = filter_data.get('issue_end_date', None)
    expire_start_date = filter_data.get('expire_start_date', None)
    expire_end_date = filter_data.get('expire_end_date', None)
    
    invoices = Invoice.objects.filter(is_active=True, billing__id=object_id).distinct()
    persons = []
    
    if len(invoices) > 0:
        filter_billing_data = {
                'company': filter_data.get('company'),
                'message_types': message_types,
                'invoices': [{'id': invoice.id} for invoice in invoices],
                'address_type': 'invoice',
                'invoice_statuses': statuses,
                'payment_types': payment_types,
                'issue_start_date': issue_start_date,
                'issue_end_date': issue_end_date,
                'expire_start_date': expire_start_date,
                'expire_end_date': expire_end_date,
            }
        persons = filter_by_billing(filter_billing_data, group_same)
        
    return persons

def filter_by_claim_request(filter_data, group_same):
    filters = Q()
    object_id = filter_data.get('id', None)
    filters &= Q(claim_request__id=object_id)
    message_types = filter_data.get('message_types', [])
    statuses = filter_data.get('statuses', [])
    commitment_statuses = filter_data.get('commitment_statuses', [])
    payment_types = filter_data.get('payment_types', [])
    payment_types = filter_data.get('payment_types', [])
    issue_start_date = filter_data.get('issue_start_date', None)
    issue_end_date = filter_data.get('issue_end_date', None)
    expire_start_date = filter_data.get('expire_start_date', None)
    expire_end_date = filter_data.get('expire_end_date', None)
    return_start_date = filter_data.get('return_start_date', None)
    return_end_date = filter_data.get('return_end_date', None)
    
    if len(statuses) > 0:
        filters &= Q(payment__invoice__status__id__in=statuses)
    if len(commitment_statuses) > 0:
        filters &= Q(payment__commitment_deposit__status__id__in=commitment_statuses)
    if len(payment_types) > 0:
        filters &= Q(payment__payment_type_token__in=payment_types)
    if issue_start_date:
        issue_date_filter = Q()
        issue_date_filter |= Q(payment__invoice__sent_at__gte=issue_start_date)
        filters &= issue_date_filter
        
    if issue_end_date:
        issue_date_filter = Q()
        issue_date_filter |= Q(payment__invoice__sent_at__lte=issue_end_date)
        filters &= issue_date_filter
    if expire_start_date:
        expire_date_filter = Q()
        expire_date_filter |= Q(payment__invoice__due_date__gte=expire_start_date)
        filters &= expire_date_filter
    
    if expire_end_date:
        expire_date_filter = Q()
        expire_date_filter |= Q(payment__invoice__due_date__lte=expire_end_date)
        expire_date_filter |= Q(payment__commitment_deposit__due_date__lte=expire_end_date)
        filters &= expire_date_filter
    
    if return_start_date:
        return_date_filter = Q()
        return_date_filter |= Q(payment__invoice__return_date__gte=return_start_date)
        filters &= return_date_filter
    
    if return_end_date:
        return_date_filter = Q()
        return_date_filter |= Q(payment__invoice__return_date__lte=return_end_date)
        filters &= return_date_filter
    
    claim_request_payment = ClaimRequestPayment.objects.filter(filters)
    contracts = Contract.objects.filter(id__in=claim_request_payment.values_list('contract', flat=True))
    persons = []
    if len(contracts) > 0:
        filter_contract_data = {
            'company': filter_data.get('company'),
            'message_types': message_types,
            'contracts': [{'id': contract.id} for contract in contracts],
            'person_type': ['holder'],
            'address_type': 'contract'
        }
        persons = filter_by_contract(filter_contract_data, group_same)
    
    return persons

def filter_by_sepa_remittance(filter_data, group_same):
    filters = Q()
    object_id = filter_data.get('id', None)
    filters &= Q(remittances__id=object_id)
    message_types = filter_data.get('message_types', [])
    statuses = filter_data.get('statuses', [])
    commitment_statuses = filter_data.get('commitment_statuses', [])
    payment_types = filter_data.get('payment_types', [])
    payment_types = filter_data.get('payment_types', [])
    issue_start_date = filter_data.get('issue_start_date', None)
    issue_end_date = filter_data.get('issue_end_date', None)
    expire_start_date = filter_data.get('expire_start_date', None)
    expire_end_date = filter_data.get('expire_end_date', None)
    return_start_date = filter_data.get('return_start_date', None)
    return_end_date = filter_data.get('return_end_date', None)
    
    if len(statuses) > 0:
        filters &= Q(payment__invoice__status__id__in=statuses)
    if len(payment_types) > 0:
        filters &= Q(payment__payment_type_token__in=payment_types)
    if issue_start_date:
        issue_date_filter = Q()
        issue_date_filter |= Q(payment__invoice__sent_at__gte=issue_start_date)
        filters &= issue_date_filter
        
    if issue_end_date:
        issue_date_filter = Q()
        issue_date_filter |= Q(payment__invoice__sent_at__lte=issue_end_date)
        filters &= issue_date_filter
    if expire_start_date:
        expire_date_filter = Q()
        expire_date_filter |= Q(payment__invoice__due_date__gte=expire_start_date)
        filters &= expire_date_filter
    
    if expire_end_date:
        expire_date_filter = Q()
        expire_date_filter |= Q(payment__invoice__due_date__lte=expire_end_date)
        expire_date_filter |= Q(payment__commitment_deposit__due_date__lte=expire_end_date)
        filters &= expire_date_filter
    
    if return_start_date:
        return_date_filter = Q()
        return_date_filter |= Q(payment__invoice__return_date__gte=return_start_date)
        filters &= return_date_filter
    
    if return_end_date:
        return_date_filter = Q()
        return_date_filter |= Q(payment__invoice__return_date__lte=return_end_date)
        filters &= return_date_filter
    
    # Get all payments belonging to the specified remittance and filters
    payments = Payment.objects.filter(filters).select_related(
        'contract',
        'invoice__contract',
        'commitment_deposit__contract',
    )

    # Collect related contracts from different paths (direct, invoice, commitment)
    contract_ids = set()
    for payment in payments:
        if payment.contract_id:
            contract_ids.add(payment.contract_id)
        if payment.invoice and payment.invoice.contract_id:
            contract_ids.add(payment.invoice.contract_id)
        if payment.commitment_deposit and payment.commitment_deposit.contract_id:
            contract_ids.add(payment.commitment_deposit.contract_id)

    contracts = Contract.objects.filter(id__in=contract_ids)
    persons = []
    if len(contracts) > 0:
        filter_contract_data = {
            'company': filter_data.get('company'),
            'message_types': message_types,
            'contracts': [{'id': contract.id} for contract in contracts],
            'person_type': ['holder'],
            'address_type': 'contract'
        }
        persons = filter_by_contract(filter_contract_data, group_same)
    
    return persons

def check_person_communication(person, message_types, contract=None):
    total_options = len(message_types)
    email_token = get_config_token('message_type_email_token')
    letter_token = get_config_token('message_type_letter_token')
    electronic_invoice_token = "electronic_inv"
    
    # Use prefetched data to avoid additional queries
    if email_token in message_types:
        has_email = any(c.is_active and c.email for c in person.contacts.all())
        if not has_email:
            total_options -= 1
    if letter_token in message_types:
        has_address = any(addr.is_active and addr.address for addr in person.addresses.all())
        if not has_address:
            total_options -= 1
    if electronic_invoice_token in message_types:
        if not (contract and contract.payment and contract.payment.accounting_office):
            total_options -= 1
    
    if total_options == 0:
        return False
    return True

def check_person_communication_by_invoice(invoice, message_types):
    total_options = len(message_types)
    email_token = get_config_token('message_type_email_token')
    letter_token = get_config_token('message_type_letter_token')
    electronic_invoice_token = "electronic_inv"
    
    if email_token in message_types:
        if invoice.customer_email_final is None:
            total_options -= 1
    if letter_token in message_types:
        if invoice.address_final is None:
            total_options -= 1
    if electronic_invoice_token in message_types:
        if not (invoice and invoice.accounting_office_final):
            total_options -= 1
    
    
    if total_options == 0:
        return False
    return True

def check_person_communication_by_contract(contract, message_types):
    total_options = len(message_types)
    email_token = get_config_token('message_type_email_token')
    letter_token = get_config_token('message_type_letter_token')
    
    if email_token in message_types:
        if contract.person_contact_email is None:
            total_options -= 1
    if letter_token in message_types:
        if contract.address_contact is None:
            total_options -= 1
    
    if total_options == 0:
        return False
    return True
