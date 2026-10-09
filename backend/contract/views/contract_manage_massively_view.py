from datetime import datetime
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from django.db.models import Q
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions

from contract.models import Bonification, Contract, ContractClientType, ContractDebtManagement, ContractPriceRate, Variable, VariableType
from coredata.models import ConfigProject
from coredata.utils.name_utils import generate_token
from pricing.models import PriceRate, Product, ProductOrigin

from contract.serializers.contract_serializer import ContractSerializer

class ContractManageMassivelyViewSet(APIView):
    serializer_class = ContractSerializer
    permission_classes = [IsAuthenticated, DjangoModelPermissions]
  
    def get_queryset(self):
        return Contract.objects.all()
    
    def post(self, request, *args, **kwargs):
        
        variable_type_ids = request.data.get('variable_type_ids')
        bonification_type_ids = request.data.get('bonification_type_ids')
        client_type_ids = request.data.get('client_type_ids')
        category_ids = request.data.get('category_ids')
        use_type_ids = request.data.get('use_type_ids')
        product_ids = request.data.get('product_ids')
        price_rate_ids = request.data.get('price_rate_ids')
        operation = request.data.get('operation')
        saved_vars = request.data.get('saved_vars')
        is_saving = request.data.get('saving', True)
        
        print("operation: ", operation)
        
        filters = Q()
        if client_type_ids:
            filters &= Q(client_type__id__in=client_type_ids)
        if category_ids:
            filters &= Q(category__id__in=category_ids)
        if use_type_ids:
            filters &= Q(use_type__id__in=use_type_ids)
        if variable_type_ids and operation == "OFF":
            filters &= Q(variables__type__id__in=variable_type_ids)
        if bonification_type_ids and operation == "OFF":
            filters &= Q(bonifications__bonification_type__id__in=bonification_type_ids)
        if product_ids and operation == "OFF":
            filters &= Q(price_rates__product__id__in=product_ids)

        contracts = Contract.objects.filter(filters).distinct()
        
        print("contracts", contracts)
        if not is_saving:
            contract_ids = contracts.values_list('id', flat=True)
            total_contracts_debt_management = getContractsCount(contracts)
            total_contracts_client_type = getContractsClientCount(contracts)
            return Response(
                {
                    'contract_ids': contract_ids, 
                    'total_contracts_debt_management': total_contracts_debt_management,
                    'total_contracts_client_type': total_contracts_client_type
                    }
                )
            
        bonifications_list = []
        if bonification_type_ids and contracts.exists():
            bonifications_list = list(Bonification.objects.filter(contract__in=contracts).values_list('id', flat=True))
        
        if variable_type_ids and contracts.exists():
            variables = Variable.objects.filter(contract__in=contracts)
            if variables.exists():
                bonifications_list.extend(
                list(variables.values_list('bonification', flat=True).distinct())
            )
        
        bonifications = Bonification.objects.filter(id__in=bonifications_list)
        
        if operation == "OFF":
            print("ELIMINA")
            if bonifications.exists():
                for bonification in bonifications:
                    if bonification_type_ids and not variable_type_ids:
                        bonification._skip_variable = True
                    bonification.is_active = False
                    bonification.save()
                    print(bonification, "contract: ", bonification.contract)
                    
            if product_ids:
                products = Product.objects.filter(id__in=product_ids)
                if products.exists():
                    price_rates = list(products.values_list('price_rates', flat=True))

                    # Pre-fetch supply points for all contracts to avoid N+1 queries
                contracts_with_supply_points = contracts.prefetch_related('supply_points')
                
                for contract in contracts_with_supply_points:
                    contract._skip_claim_management = True
                    contract.price_rates.remove(*price_rates)  
                    contract.save()
        
        elif operation == "ADD":
            print("AGREGA")
            price_rates_list = PriceRate.objects.filter(id__in=price_rate_ids)
            price_rates_by_origin = get_price_rates(price_rates_list)
            reading_origin_token = ConfigProject.objects.get(token='origin_reading_token').value

            # Pre-fetch supply points for all contracts to avoid N+1 queries
            contracts_with_supply_points = contracts.prefetch_related('supply_points')
            
            for contract in contracts_with_supply_points:
                if price_rates_list and len(price_rates_list) > 0:
                    price_rates_reading = price_rates_by_origin[reading_origin_token]
                    registration_price_rates = []
                    for origin_token, price_rates in price_rates_by_origin.items():
                        if origin_token != reading_origin_token:
                            registration_price_rates.extend(price_rates)
                    
                    contract._skip_claim_management = True
                    #IF contract.price_rates HAS ONE OF THE PRICE RATES, DO NOT ADD THAT ONE AGAIN, THE REST DO ADD THEM
                    # for price_rate in price_rates_reading:
                    #     if price_rate not in contract.price_rates.all():
                    #         contract.price_rates.add(price_rate)
                            
                    # Collect all ContractPriceRate objects to create
                    contract_price_rates_to_create = []
                    supply_points = list(contract.supply_points.all())  # Convert to list to avoid repeated queries
                    for price_rate in price_rates_reading:
                        for sp in supply_points:
                            contract_price_rates_to_create.append(
                                ContractPriceRate(
                                    supply_point=sp,
                                    price_rate=price_rate
                                )
                            )
                    
                    # Bulk create all ContractPriceRate objects
                    created_contract_price_rates = ContractPriceRate.objects.bulk_create(
                        contract_price_rates_to_create
                    )
                    
                    # Add all created objects to contract in one operation
                    contract.price_rates.add(*created_contract_price_rates)
                            
                    contract.registration_price_rates.add(*registration_price_rates)
                    contract.save()
                if saved_vars and len(saved_vars) > 0:
                    counter = 0
                    for var in saved_vars:
                        var_type = VariableType.objects.get(id=var['id'])
                        start_at = None
                        end_at = None
                        if 'start_at' in var and var['start_at'].strip():  
                            start_at = datetime.strptime(var['start_at'], '%Y-%m-%d')

                        if 'end_at' in var and var['end_at'].strip():  
                            end_at = datetime.strptime(var['end_at'], '%Y-%m-%d')
                        variable = Variable.objects.create(
                            token=generate_token(Variable,  offset=counter),
                            contract=contract,
                            type=var_type,
                            value=var['value'] if 'value' in var else None,
                            name=var['name'] if 'name' in var else None,
                            start_at=start_at,
                            end_at=end_at,
                            bonification=var['bonification'] if 'bonification' in var else None,
                        )
                        counter += 1
        
        return Response('all contracts updated', status=status.HTTP_200_OK)

def get_price_rates(price_rates_list):
    origins = ProductOrigin.objects.all()
    print("origins", origins)
    #separate price_rates by origin
    price_rates_by_origin = {}
    for origin in origins:
        price_rates_by_origin[origin.token] = []
    for price_rate in price_rates_list:
        price_rates_by_origin[price_rate.product.origin.token].append(price_rate)
    
    return price_rates_by_origin

def getContractsCount(contracts):
    contracts_by_debt_management = {}
    #add to contracts_by_debt_management one for contracts without debt management
    contracts_by_debt_management['Sense tipus de deute'] = 0
    debt_managements = ContractDebtManagement.objects.all()
    for debt_management in debt_managements:
        contracts_by_debt_management[debt_management.name] = 0
    for contract in contracts:
        if contract.debt_management:
            contracts_by_debt_management[contract.debt_management.name] += 1
        else:
            contracts_by_debt_management['Sense tipus de deute'] += 1
    return contracts_by_debt_management

def getContractsClientCount(contracts):
    contracts_by_client_type = {}
    #add to contracts_by_client_type one for contracts without client type
    contracts_by_client_type['Sense tipus de client'] = 0
    client_types = ContractClientType.objects.all()
    for client in client_types:
        contracts_by_client_type[client.name] = 0
    for contract in contracts:
        if contract.client_type:
            contracts_by_client_type[contract.client_type.name] += 1
        else:
            contracts_by_client_type['Sense tipus de client'] += 1
    return contracts_by_client_type