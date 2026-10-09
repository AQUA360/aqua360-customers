# contract/views/contract_request_finalize_view.py

from rest_framework import status, views
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from django.db.models import Count, Sum
from django.utils.translation import gettext as _

from billing.models import Billing, Invoice
from billing.serializers.invoice_serializer import InvoiceMinimalListSerializer
from django.shortcuts import get_object_or_404

from coredata.utils.other_utils import round_ceil


def highlighted(value):
    """Scalar standout row. `__highlight` / `__value` are frontend metadata, not data."""
    return {"__highlight": True, "__value": value}


class BillingPreInvoicesSummaryViewSet(views.APIView):
    permission_classes = [IsAuthenticated, DjangoModelPermissions]
    queryset = Billing.objects.all().order_by('-created_at')
    def get(self, request, id):
        try:
            if not id:
                return Response({"error": "billing id is required."}, status=status.HTTP_400_BAD_REQUEST)
            billing = get_object_or_404(Billing, id=id)

            invoices = Invoice.objects.filter(billing = billing)
            
            OTHERS_LABEL = _("Altres")

            payment_type_counts = invoices.values('payment_type_final').annotate(count=Count('id')).order_by()
            payment_type_dict = {(item['payment_type_final'] or OTHERS_LABEL): item['count'] for item in payment_type_counts.order_by('payment_type_final')}
            use_type_dict = {"": {"invoices": "consumption"}}
            use_type_counts = invoices.values('contract__use_type__name').annotate(count=Count('id'), sum=Sum('consumption')).order_by()
            use_type_dict.update({(item['contract__use_type__name'] or OTHERS_LABEL): {item['count']: f"{round_ceil(item['sum'])} m³"} for item in use_type_counts})

            total_consumption = sum(invoice.consumption or 0 for invoice in invoices)

            line_items_counts = invoices.values('line_items__product_name', 'line_items__price_rate_name').annotate(count=Count('id', distinct=True), sum=Sum('line_items__price'), sum_final=Sum('line_items__total')).order_by()
            products_agg = {}
            for item in line_items_counts:
                product_name = item['line_items__product_name'] or OTHERS_LABEL
                price_rate_name = item['line_items__price_rate_name'] or OTHERS_LABEL
                product = products_agg.setdefault(product_name, {"price_rates": {}, "total_sum": 0, "total_sum_final": 0})
                price_rate = product["price_rates"].setdefault(price_rate_name, {"count": 0, "sum": 0, "sum_final": 0})
                price_rate["count"] += item["count"]
                price_rate["sum"] += item["sum"] or 0
                price_rate["sum_final"] += item["sum_final"] or 0
                product["total_sum"] += item["sum"] or 0
                product["total_sum_final"] += item["sum_final"] or 0
            line_items_dict = {"": {"subtotal": "total"}}
            for product_name, product in products_agg.items():
                for price_rate_name, agg in product["price_rates"].items():
                    line_items_dict[f"{price_rate_name} {product_name}"] = {
                        f"{round(agg['sum'], 2)} €": f"{round(agg['sum_final'], 2)} €"
                    }
                # Product total after its price rates. `__highlight` is metadata
                # for the frontend (standout row); it must not be rendered as data.
                line_items_dict[product_name] = {
                    "__limit": 10,
                    "__highlight": True,
                    f"{round(product['total_sum'], 2)} €": f"{round(product['total_sum_final'], 2)} €",
                }

            tax_dict = {"": {"line_items": "total"}}
            tax_counts = invoices.values('line_items__tax_percent').annotate(count=Count('id', distinct=True), sum=Sum('line_items__tax_price')).order_by()
            tax_dict.update({f"{item['line_items__tax_percent']}" if item['line_items__tax_percent'] else OTHERS_LABEL: {item['count']: f"{ round(item['sum'], 2)} €"} for item in tax_counts})

            bonifications_counts = invoices.filter(
                contract__bonifications__isnull=False
                ).values('contract__bonifications__bonification_type__name').annotate(count=Count('id', distinct=True)).order_by()
            for item in bonifications_counts:
                print(item)
            bonifications_dict = {f"{item['contract__bonifications__bonification_type__name'] or OTHERS_LABEL}": f"{item['count']}" for item in bonifications_counts}

            variables_counts = invoices.filter(
                contract__variables__isnull=False
                ).values('contract__variables__type__name').annotate(count=Count('id', distinct=True)).order_by()
            variables_dict = {f"{item['contract__variables__type__name'] or OTHERS_LABEL}": f"{item['count']}" for item in variables_counts}

            messages_counts = invoices.filter(
                messages__isnull=False
                ).values('messages__title').annotate(count=Count('id', distinct=True)).order_by()
            messages_dict = {f"{item['messages__title'] or OTHERS_LABEL}": f"{item['count']}" for item in messages_counts}

            response = [{
                'num_invoices': highlighted(invoices.count()),
                'payment_types': payment_type_dict,
            },{
                'responsible_consumption': invoices.filter(responsible_consumption=True).count(),
                'subtotal_consumption': highlighted(f"{total_consumption} m³"),
                'use_types': use_type_dict
            },{
                'line_items': line_items_dict,
                'taxes': tax_dict,
                'total_billing': highlighted(str(sum(invoice.total_final for invoice in invoices))+' €'),
                'subtotal_billing': highlighted(str(sum(invoice.subtotal_final for invoice in invoices))+' €'),
            },{
                'bonifications': bonifications_dict,
                'variables': variables_dict,
                'messages': messages_dict
            }]

            return Response(response, status=status.HTTP_200_OK)
        
        except Exception as e:
            return Response({"error": f"Ha ocorregut un error inesperat: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
