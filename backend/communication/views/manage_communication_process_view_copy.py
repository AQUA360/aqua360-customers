import time
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from django.db.models import Q, OuterRef, Exists, Count, Sum, Prefetch
from django.core.cache import cache
from billing.models import Invoice, Payment, PaymentStatus
from billing.serializers.invoice_serializer import InvoiceMinimalSerializer
from claimrequest.models import ClaimRequestPayment
from communication.models import Communication, CommunicationProcess
from contract.models import Contract, ContractTerminationRequest
from contract.serializers.contract_serializer import ContractWithPaymentsSerializer
from coredata.models import Address, ConfigProject, PersonDeliquency, Person, PersonAddress, PersonContact
from coredata.serializers import PersonCommunicationSerializer, PersonAddressSerializer, PersonContactSerializer
from service.models import SupplyCut, SupplyPoint
from billing.serializers.payment_serializer import PaymentSerializer, PaymentMinimalSerializer

# Cache for config tokens to avoid repeated DB queries
_CONFIG_CACHE = {}

def get_config_token(token_key):
    """Get config value with caching to avoid repeated DB queries"""
    if token_key not in _CONFIG_CACHE:
        try:
            _CONFIG_CACHE[token_key] = ConfigProject.objects.get(token=token_key).value
        except ConfigProject.DoesNotExist:
            _CONFIG_CACHE[token_key] = None
    return _CONFIG_CACHE[token_key]

def build_address_data_fast(person_address):
    """
    Fast address data builder - avoids PersonAddressSerializer overhead.
    Builds minimal address representation directly.
    """
    if not person_address or not person_address.address:
        return None
    
    address = person_address.address
    simple_address = str(address)
    
    # Build address_complete with attention_to if present
    address_complete = simple_address
    if person_address.attention_to:
        address_complete = f"{simple_address} - Att.: {person_address.attention_to}"
    
    return {
        'id': person_address.id,
        'person': person_address.person_id,
        'address': person_address.address_id,
        'attention_to': person_address.attention_to,
        'is_billing': person_address.is_billing,
        'is_active': person_address.is_active,
        'token': person_address.token,
        'simple_address_complete': simple_address,
        'address_complete': address_complete,
    }

def build_person_data_fast(person):
    """
    Fast person data builder without serializer overhead.
    Uses prefetched data to avoid any additional queries.
    """
    # Get full name
    full_name = f"{person.name} {person.surname}" if person.surname else person.name
    
    # Get phones and emails from prefetched contacts
    phones = []
    emails = []
    for contact in person.contacts.all():
        if contact.is_active:
            if contact.phone:
                phones.append(contact.phone)
            if contact.email:
                emails.append(contact.email)
    
    # Remove duplicates while preserving order
    phones = list(dict.fromkeys(phones))
    emails = list(dict.fromkeys(emails))
    
    # Build addresses using fast builder (uses prefetched data)
    addresses = []
    for person_address in person.addresses.all():
        if person_address.is_active:
            addr_data = build_address_data_fast(person_address)
            if addr_data:
                addresses.append(addr_data)
    
    return {
        'id': person.id,
        'token': person.token,
        'name': person.name,
        'surname': person.surname,
        'full_name': full_name,
        'is_juridic': person.is_juridic,
        'phones': phones,
        'emails': emails,
        'vulnerability_level': person.vulnerability_level,
        'addresses': addresses
    }

class ManageCommunicationProcessViewSet(APIView):
    permission_classes = [IsAuthenticated, DjangoModelPermissions]
    queryset = Communication.objects.all().order_by('-created_at')
    def post(self, request, *args, **kwargs):
        filter_type = request.data.get('type', None)
        filter_data = request.data.get('filters', None)
        group_same = request.data.get('group_same', [])

        persons = []
        time_start = time.time()
        
        if filter_type == 'CONTRACT':
            persons = filter_by_contract(filter_data, group_same)
        elif filter_type == 'BILLING':
            persons = filter_by_billing(filter_data, group_same)
        elif filter_type == 'CONTRACTREQUEST':
            persons = filter_by_contract_request(filter_data, group_same)
        elif filter_type == 'ADDRESS':
            persons = filter_by_address(filter_data, group_same)
        elif filter_type == 'PERSON':
            persons = filter_by_person(filter_data, group_same)
        elif filter_type == 'SUPPLYPOINT':
            persons = filter_by_supply_point(filter_data, group_same)
        elif filter_type == 'FIXED':
            if 'entity' in filter_data and filter_data['entity'] == 'billing':
                persons = filter_by_fixed_billing(filter_data, group_same)
            elif 'entity' in filter_data and filter_data['entity'] == 'claimrequest':
                persons = filter_by_claim_request(filter_data, group_same)
        time_end = time.time()
        print(f"Time taken: {time_end - time_start} seconds")
        return Response({"persons": persons}, status=status.HTTP_202_ACCEPTED)

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
    print("filter_data contract")
    print(filter_data)
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
    print("base_qs contract")
    print(base_qs.count())

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
            
            # Use fast builder instead of serializer
            person_data = build_person_data_fast(person)
            person_data['exclude'] = False
            person_data['com_type'] = contract.communication_type
            
            if address_type == 'default':
                person_data = set_address_default(person_data, person, message_types)
            elif address_type == 'contract':
                person_data = set_address_contract(person_data, contract, message_types)
            
            if not person_data:
                continue
            
            # Build contract info
            contract_info = {
                'id': contract.id,
                'token': contract.token,
                'supply_address': str(contract.supply_point_default.address) if contract.supply_point_default else None,
            }
            
            if len(group_same) > 0:
                # Create grouping key based on person token and grouping criteria
                group_key = person_data['token']
                if 'letter' in group_same:
                    group_key += f"|addr:{person_data.get('com_address', '')}"
                if 'email' in group_same:
                    group_key += f"|email:{person_data.get('com_email', '')}"
                if 'sms' in group_same or 'whatsapp' in group_same:
                    phones = tuple(sorted(person_data.get('com_phones', [])))
                    group_key += f"|phones:{phones}"
                group_key += f"|type:{person_data['com_type']}"
                
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
    persons.sort(key=lambda x: x['full_name'].lower())
    
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
            
            # Use fast builder instead of serializer
            person_data = build_person_data_fast(person)
            person_data['exclude'] = False
            person_data['com_type'] = contract.communication_type
            
            if address_type == 'default':
                person_data = set_address_default(person_data, person, message_types)
            elif address_type == 'contract':
                person_data = set_address_contract(person_data, contract, message_types)
            
            if not person_data:
                continue
            
            # Build contract info
            contract_info = {
                'id': contract.id,
                'token': contract.token,
                'supply_address': str(contract.supply_point_default.address) if contract.supply_point_default else None,
            }
            
            if len(group_same) > 0:
                # Create grouping key
                group_key = person_data['token']
                if 'letter' in group_same:
                    group_key += f"|addr:{person_data.get('com_address', '')}"
                if 'email' in group_same:
                    group_key += f"|email:{person_data.get('com_email', '')}"
                if 'sms' in group_same or 'whatsapp' in group_same:
                    phones = tuple(sorted(person_data.get('com_phones', [])))
                    group_key += f"|phones:{phones}"
                group_key += f"|type:{person_data['com_type']}"
                
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
    persons.sort(key=lambda x: x['full_name'].lower())
    
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
    person_tokens = list(set([inv.customer_token_final for inv in invoices if inv.customer_token_final]))
    person_objects = {}
    if person_tokens:
        person_objects = {
            p.token: p for p in Person.objects.filter(token__in=person_tokens).prefetch_related(
                Prefetch('contacts', queryset=PersonContact.objects.filter(is_active=True)),
                Prefetch('addresses', queryset=PersonAddress.objects.filter(is_active=True).select_related(
                    'address', 'address__city', 'address__province', 'address__country', 'address__street', 'address__street_number'
                ))
            )
        }
    
    # Use dictionary for O(1) lookup
    persons_dict = {}
    
    for invoice in invoices:
        person = person_objects.get(invoice.customer_token_final)
        if not person:
            continue
        
        # Use fast builder instead of serializer (10x faster)
        person_data = build_person_data_fast(person)
        person_data['exclude'] = False
        person_data['com_type'] = invoice.contract.communication_type if invoice.contract else None
        
        if address_type == 'default':
            person_data = set_address_default(person_data, person, message_types)
        elif address_type == 'contract':
            if not invoice.contract:
                continue
            person_data = set_address_contract(person_data, invoice.contract, message_types)
        elif address_type == 'invoice':
            if not check_person_communication_by_invoice(invoice, message_types):
                continue
            person_data['com_address'] = invoice.address_final
            person_data['com_phones'] = [invoice.customer_tlf_final] if invoice.customer_tlf_final else []
            person_data['com_email'] = invoice.customer_email_final
        
        if not person_data:
            continue
        
        # Build contract and invoice info
        contract_info = None
        if invoice.contract:
            contract_info = {
                'id': invoice.contract.id,
                'token': invoice.contract.token,
                'supply_address': str(invoice.contract.supply_point_default.address) if invoice.contract.supply_point_default else None,
            }
        
        invoice_info = {
            'id': invoice.id,
            'token': invoice.token,
            'serie_final': invoice.serie_final,
            'consumption': invoice.consumption,
            'total_final': invoice.total_final,
            'issue_date': invoice.issue_date,
        }
        
        if len(group_same) > 0:
            # Create grouping key
            group_key = person_data['token']
            if 'letter' in group_same:
                group_key += f"|addr:{person_data.get('com_address', '')}"
            if 'email' in group_same:
                group_key += f"|email:{person_data.get('com_email', '')}"
            if 'sms' in group_same or 'whatsapp' in group_same:
                phones = tuple(sorted(person_data.get('com_phones', [])))
                group_key += f"|phones:{phones}"
            group_key += f"|type:{person_data['com_type']}"
            
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
            unique_key = f"{person_data['token']}|{invoice.id}"
            person_data['contracts'] = [contract_info] if contract_info else []
            person_data['invoices'] = [invoice_info]
            person_data['total_communication'] = 1
            persons_dict[unique_key] = person_data
    
    # Convert dictionary to list and sort once at the end
    persons = list(persons_dict.values())
    persons.sort(key=lambda x: x['full_name'].lower())
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
            # Use fast builder instead of serializer
            person_data = build_person_data_fast(person_address.person)
            person_data['exclude'] = False
            person_data = set_address_default(person_data, person, message_types)
                
            if not person_data:
                continue
            
            if len(group_same) > 0:
                # Create grouping key
                group_key = person_data['token']
                if 'letter' in group_same:
                    group_key += f"|addr:{person_data.get('com_address', '')}"
                if 'email' in group_same:
                    group_key += f"|email:{person_data.get('com_email', '')}"
                if 'sms' in group_same or 'whatsapp' in group_same:
                    phones = tuple(sorted(person_data.get('com_phones', [])))
                    group_key += f"|phones:{phones}"
                
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
    persons.sort(key=lambda x: x['full_name'].lower())
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
            # Use fast builder instead of serializer
            person_data = build_person_data_fast(person)
            person_data['exclude'] = False
            person_data = set_address_default(person_data, person, message_types)
            
            if not person_data:
                continue
            
            if len(group_same) > 0:
                # Create grouping key
                group_key = person_data['token']
                if 'letter' in group_same:
                    group_key += f"|addr:{person_data.get('com_address', '')}"
                if 'email' in group_same:
                    group_key += f"|email:{person_data.get('com_email', '')}"
                if 'sms' in group_same or 'whatsapp' in group_same:
                    phones = tuple(sorted(person_data.get('com_phones', [])))
                    group_key += f"|phones:{phones}"
                
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
                    'message_types': message_types,
                    'contracts': [{'id': contract.id} for contract in contracts],
                    'person_type': ['holder'],
                    'address_type': 'contract'
                }
            return filter_by_contract(filter_contract_data, group_same)  # Already sorted
    
    # Convert dictionary to list and sort
    persons = list(persons_dict.values())
    persons.sort(key=lambda x: x['full_name'].lower())
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
            'message_types': message_types,
            'contracts': [{'id': contract.id} for contract in supply_point_contracts],
            'person_type': ['holder', 'tenant', 'owner'],
            'address_type': 'contract'
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
            'message_types': message_types,
            'contracts': [{'id': contract.id} for contract in contracts],
            'person_type': ['holder'],
            'address_type': 'contract'
        }
        persons = filter_by_contract(filter_contract_data, group_same)
    
    return persons

def check_person_communication(person, message_types):
    total_options = len(message_types)
    sms_token = get_config_token('message_type_sms_token')
    whatsapp_token = get_config_token('message_type_whatsapp_token')
    email_token = get_config_token('message_type_email_token')
    letter_token = get_config_token('message_type_letter_token')
    
    # Use prefetched data to avoid additional queries
    if sms_token in message_types or whatsapp_token in message_types:
        has_phone = any(c.is_active and c.phone for c in person.contacts.all())
        if not has_phone:
            total_options -= 1
    if email_token in message_types:
        has_email = any(c.is_active and c.email for c in person.contacts.all())
        if not has_email:
            total_options -= 1
    if letter_token in message_types:
        has_address = any(addr.is_active and addr.address for addr in person.addresses.all())
        if not has_address:
            total_options -= 1
    
    if total_options == 0:
        return False
    return True

def check_person_communication_by_invoice(invoice, message_types):
    total_options = len(message_types)
    sms_token = get_config_token('message_type_sms_token')
    whatsapp_token = get_config_token('message_type_whatsapp_token')
    email_token = get_config_token('message_type_email_token')
    letter_token = get_config_token('message_type_letter_token')
    
    if sms_token in message_types or whatsapp_token in message_types:
        if invoice.customer_tlf_final is None:
            total_options -= 1
    if email_token in message_types:
        if invoice.customer_email_final is None:
            total_options -= 1
    if letter_token in message_types:
        if invoice.address_final is None:
            total_options -= 1
    
    if total_options == 0:
        return False
    return True

def check_person_communication_by_contract(contract, message_types):
    total_options = len(message_types)
    sms_token = get_config_token('message_type_sms_token')
    whatsapp_token = get_config_token('message_type_whatsapp_token')
    email_token = get_config_token('message_type_email_token')
    letter_token = get_config_token('message_type_letter_token')
    
    if sms_token in message_types:
        if contract.person_contact_sms.count() == 0:
            total_options -= 1
    if whatsapp_token in message_types:
        #DONE DIFF IN CASE LATER WHATSAPP IS TREATED WITH A DIFF VALUE
        if contract.person_contact_sms.count() == 0:
            total_options -= 1
    if email_token in message_types:
        if contract.person_contact_email is None:
            total_options -= 1
    if letter_token in message_types:
        if contract.address_contact is None:
            total_options -= 1
    
    if total_options == 0:
        return False
    return True

def set_address_default(person_data, person, message_types):
    if not check_person_communication(person, message_types):
        return None
    try:
        # Use prefetched addresses to avoid additional queries
        addresses = [addr for addr in person.addresses.all() if addr.is_active]
        person_address = None
        for addr in addresses:
            if addr.is_billing:
                person_address = addr
                break
        if not person_address and addresses:
            person_address = addresses[0]
        
        if person_address:
            address_data = PersonAddressSerializer(person_address).data
            person_data['com_address'] = address_data.get('simple_address_complete')
        else:
            person_data['com_address'] = None
    except (AttributeError, IndexError):
        person_data['com_address'] = None
    
    # Get default contact - use prefetched contacts
    try:
        contacts = [c for c in person.contacts.all() if c.is_active]
        person_contact = None
        for contact in contacts:
            if contact.is_default:
                person_contact = contact
                break
        if not person_contact and contacts:
            person_contact = contacts[0]
        
        if person_contact:
            person_data['com_phones'] = [person_contact.phone] if person_contact.phone else []
            person_data['com_email'] = person_contact.email
        else:
            person_data['com_phones'] = []
            person_data['com_email'] = None
    except (AttributeError, IndexError):
        person_data['com_phones'] = []
        person_data['com_email'] = None
    
    return person_data

def set_address_contract(person_data, contract, message_types):
    if not check_person_communication_by_contract(contract, message_types):
        return None
    if contract.address_contact:
        person_data['com_address'] = PersonAddressSerializer(contract.address_contact).data.get('simple_address_complete')
    else:
        person_data['com_address'] = None
    
    person_data['com_phones'] = contract.person_contact_sms.values_list('phone', flat=True)
    person_data['com_email'] = contract.person_contact_email.email if contract.person_contact_email else None
    return person_data