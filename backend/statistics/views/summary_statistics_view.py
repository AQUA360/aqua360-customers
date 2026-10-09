from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.db.models import Sum, Avg, F, Count, Max, Q, DecimalField, FloatField, Value
from django.db.models.functions import Coalesce
from ..models import ContractConsumption, BillingConsumption
from contract.models import ContractUseType, Contract
import datetime


def _parse_bool_param(value):
    """Interpreta un query param booleà ('true'/'false', '1'/'0'). None si no s'envia
    o no es reconeix, per distingir 'no informat' de 'false' explícit."""
    if value is None:
        return None
    val = str(value).strip().lower()
    if val in ('true', '1', 'yes'):
        return True
    if val in ('false', '0', 'no'):
        return False
    return None


def _contract_filter_q(request, prefix=''):
    """Q amb els filtres opcionals active/is_billable sobre Contract (None si no
    s'ha informat cap dels dos). `is_billable` es el mateix criteri de 'facturable'
    usat a la resta de l'aplicació: Contract.block_billing=False."""
    active = _parse_bool_param(request.query_params.get('active'))
    is_billable = _parse_bool_param(request.query_params.get('is_billable'))
    if active is None and is_billable is None:
        return None
    conditions = {}
    if active is not None:
        conditions[f'{prefix}is_active'] = active
    if is_billable is not None:
        conditions[f'{prefix}block_billing'] = not is_billable
    return Q(**conditions)


class ConsumptionSummaryByUseType(APIView):
    """
    Endpoint que retorna el resum de consums (diari i totals) agrupat per tipus de contracte i el total global.
    Accepta els paràmetres opcionals `active` i `is_billable` (booleans) per filtrar
    els contractes agregats a cada resum; si no s'envien, es manté el comportament actual.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        active_param = _parse_bool_param(request.query_params.get('active'))
        is_billable_param = _parse_bool_param(request.query_params.get('is_billable'))

        # 1. Càlcul agrupat per tipus d'ús
        contracts_q = _contract_filter_q(request, prefix='contracts__')
        grouped_data = ContractUseType.objects.annotate(
            total_contracts=Count('contracts', distinct=True, filter=contracts_q),
            avg_daily_per_contract=Coalesce(
                Avg('contracts__consumption_stats__daily_consumption', filter=contracts_q),
                Value(0, output_field=DecimalField())
            ),
            total_daily_consumption=Coalesce(
                Sum('contracts__consumption_stats__daily_consumption', filter=contracts_q),
                Value(0, output_field=DecimalField())
            ),
            total_period_consumption=Coalesce(
                Sum('contracts__consumption_stats__consumption', filter=contracts_q),
                Value(0, output_field=DecimalField())
            )
        ).values(
            'id', 'name', 'token',
            'total_contracts',
            'avg_daily_per_contract',
            'total_daily_consumption',
            'total_period_consumption'
        )

        # 2. Càlcul de totals globals (tots els contractes d'una)
        # Fem servir noms diferents per les claus per evitar col·lisions amb els camps del model
        totals_qs = ContractConsumption.objects.filter(is_active=True)
        contract_direct_filters = {}
        if active_param is not None:
            contract_direct_filters['contract__is_active'] = active_param
        if is_billable_param is not None:
            contract_direct_filters['contract__block_billing'] = not is_billable_param
        if contract_direct_filters:
            totals_qs = totals_qs.filter(**contract_direct_filters)

        totals_data = totals_qs.aggregate(
            global_total_daily_consumption=Coalesce(Sum('daily_consumption'), Value(0, output_field=DecimalField())),
            global_total_period_consumption=Coalesce(Sum('consumption'), Value(0, output_field=DecimalField())),
            global_avg_daily_per_contract=Coalesce(Avg('daily_consumption'), Value(0, output_field=DecimalField()))
        )

        # total_contracts manté el comportament actual (is_active=True) quan `active`
        # no s'informa; quan s'informa, el sobreescriu.
        total_contracts_filters = {'is_active': active_param if active_param is not None else True}
        if is_billable_param is not None:
            total_contracts_filters['block_billing'] = not is_billable_param

        totals = {
            'total_contracts': Contract.objects.filter(**total_contracts_filters).count(),
            'total_daily_consumption': totals_data['global_total_daily_consumption'],
            'total_period_consumption': totals_data['global_total_period_consumption'],
            'avg_daily_per_contract': totals_data['global_avg_daily_per_contract']
        }

        return Response({
            'grouped': list(grouped_data),
            'totals': totals
        }, status=status.HTTP_200_OK)

class BillingSummaryByUseType(APIView):
    """
    Endpoint que retorna el resum de facturació agrupat per tipus de contracte i el total global.
    Accepta els paràmetres opcionals `active` i `is_billable` (booleans) per filtrar
    els contractes agregats a cada resum; si no s'envien, es manté el comportament actual.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        active_param = _parse_bool_param(request.query_params.get('active'))
        is_billable_param = _parse_bool_param(request.query_params.get('is_billable'))

        # 1. Càlcul agrupat per tipus d'ús
        contracts_q = _contract_filter_q(request, prefix='contracts__')
        grouped_data = ContractUseType.objects.annotate(
            total_invoices=Count('contracts__invoices', distinct=True, filter=contracts_q),
            total_amount=Coalesce(
                Sum('contracts__billing_stats__total_amount', filter=contracts_q),
                Value(0, output_field=DecimalField())
            ),
            avg_amount_per_invoice=Coalesce(
                Avg('contracts__billing_stats__total_amount', filter=contracts_q),
                Value(0, output_field=DecimalField())
            ),
            total_consumption_invoiced=Coalesce(
                Sum('contracts__billing_stats__consumption', filter=contracts_q),
                Value(0, output_field=FloatField())
            ),
            avg_daily_consumption_invoiced=Coalesce(
                Avg('contracts__billing_stats__consumption_daily_avg', filter=contracts_q),
                Value(0, output_field=FloatField())
            )
        ).values(
            'id', 'name', 'token',
            'total_invoices',
            'total_amount',
            'avg_amount_per_invoice',
            'total_consumption_invoiced',
            'avg_daily_consumption_invoiced'
        )

        # 2. Càlcul de totals globals
        totals_qs = BillingConsumption.objects.filter(is_active=True)
        contract_direct_filters = {}
        if active_param is not None:
            contract_direct_filters['contract__is_active'] = active_param
        if is_billable_param is not None:
            contract_direct_filters['contract__block_billing'] = not is_billable_param
        if contract_direct_filters:
            totals_qs = totals_qs.filter(**contract_direct_filters)

        totals_data = totals_qs.aggregate(
            global_total_amount=Coalesce(Sum('total_amount'), Value(0, output_field=DecimalField())),
            global_total_consumption_invoiced=Coalesce(Sum('consumption'), Value(0, output_field=FloatField())),
            global_avg_amount_per_invoice=Coalesce(Avg('total_amount'), Value(0, output_field=DecimalField())),
            global_avg_daily_consumption_invoiced=Coalesce(Avg('consumption_daily_avg'), Value(0, output_field=FloatField()))
        )

        totals = {
            'total_invoices': totals_qs.count(),
            'total_amount': totals_data['global_total_amount'],
            'total_consumption_invoiced': totals_data['global_total_consumption_invoiced'],
            'avg_amount_per_invoice': totals_data['global_avg_amount_per_invoice'],
            'avg_daily_consumption_invoiced': totals_data['global_avg_daily_consumption_invoiced']
        }

        return Response({
            'grouped': list(grouped_data),
            'totals': totals
        }, status=status.HTTP_200_OK)
