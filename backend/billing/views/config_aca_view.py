from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.decorators import action
from rest_framework import viewsets, status
from rest_framework.response import Response
from billing.filter.config_aca_filter import ConfigAcaFilter
from billing.models import ConfigAca
from billing.permissions import BillingPermission
from billing.serializers.config_aca_serializer import ConfigAcaSerializer
from contract.models import ContractUseType, VariableType
from pricing.models import PriceRate, Product

class ConfigAcaViewSet(viewsets.ModelViewSet):
  queryset = ConfigAca.objects.all().filter(is_active=True).order_by('config_project__name')
  permission_classes = [IsAuthenticated, BillingPermission]
  filter_backends = [DjangoFilterBackend, OrderingFilter, SearchFilter]
  serializer_class = ConfigAcaSerializer
  filterset_class = ConfigAcaFilter
  
  def get_serializer_context(self):
    context = super().get_serializer_context()
    context['request'] = self.request
    return context
  
  @action(detail=False, methods=['get'], url_path='all')
  def get_all(self, request):
      queryset = self.filter_queryset(self.get_queryset())
      serializer = self.get_serializer(queryset, many=True)
      
      return Response({
          'count': queryset.count(),
          'next': None,
          'previous': None,
          'results': serializer.data
      }, status=status.HTTP_200_OK)
  
  @action(detail=False, methods=['post'], url_path='update-configs')
  def update_configs(self, request):
    active_config_rows = request.data.get('active_config_rows')
    user = request.user
    if not user.is_authenticated:
      raise Exception("User not authenticated")
    for config_row in active_config_rows:
      try:
        config_aca = ConfigAca.objects.get(id=config_row.get('id'))
        print("config_aca found:", config_aca)
        
        product_values = config_row.get('products')
        price_rate_values = config_row.get('price_rates')
        variable_type_values = config_row.get('variable_types')
        contract_use_type_values = config_row.get('contract_use_types')
        
        same_config_projects = ConfigAca.objects.filter(config_project=config_aca.config_project).exclude(id=config_aca.id).distinct()
        token_values = []
        values = []
        if config_aca.token_type.lower() == 'product':
          values = Product.objects.filter(id__in=[product.get('id') for product in product_values])
          config_aca.products.set(values)
          token_values.extend(values.values_list('token', flat=True))
          token_values.extend(
            same_config_projects.filter(token_type='Product').values_list('products__token', flat=True)
          )

        if config_aca.token_type.lower() == 'pricerate':
          values = PriceRate.objects.filter(id__in=[price_rate.get('id') for price_rate in price_rate_values])
          config_aca.price_rates.set(values)
          token_values.extend(values.values_list('token', flat=True))
          token_values.extend(
            same_config_projects.filter(token_type='PriceRate').values_list('price_rates__token', flat=True)
          )

        if config_aca.token_type.lower() == 'variabletype':
          values = VariableType.objects.filter(id__in=[variable_type.get('id') for variable_type in variable_type_values])
          config_aca.variable_types.set(values)
          token_values.extend(values.values_list('token', flat=True))
          token_values.extend(
            same_config_projects.filter(token_type='VariableType').values_list('variable_types__token', flat=True)
          )

        if config_aca.token_type.lower() == 'contractusetype':
          values = ContractUseType.objects.filter(id__in=[contract_use_type.get('id') for contract_use_type in contract_use_type_values])
          config_aca.contract_use_types.set(values)
          token_values.extend(values.values_list('token', flat=True))
          token_values.extend(
            same_config_projects.filter(token_type='ContractUseType').values_list('contract_use_types__token', flat=True)
          )

        token_values = list(dict.fromkeys(token for token in token_values if token))
        config_aca.config_project.value = "|".join(token_values)
        config_aca.config_project.save()
          
        config_aca.last_changed_at = timezone.now()
        config_aca.last_changed_by = user
        config_aca.save()
      except Exception as e:
        raise e
        # print(e)
    serializer = self.get_serializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return Response(serializer.data, status=status.HTTP_200_OK)