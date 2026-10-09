from django.urls import include, path
from rest_framework import routers

from documentmanager.views_export.generic_export_view import GenericExportView

from pricing.views.accounting_cost_center_view import AccountingCostCenterViewSet
from pricing.views.article_code_view import ArticleCodeViewSet

from .views.price_rate_view import PriceRateViewSet
from .views.product_view import ProductViewSet
from .views.publication_view import PublicationViewSet
from .views.billing_range_view import BillingRangeViewSet
from .views.price_interval_view import PriceIntervalViewSet
from .views.adjustment_view import AdjustmentViewSet
from .views.line_item_type_view import LineItemTypeViewSet
from .views.price_interval_stretch_view import PriceIntervalStretchViewSet
from .views.tax_view import TaxViewSet
from .views.adjustment_interval_view import AdjustmentIntervalStretchViewSet
from .views.price_variable_interval_stretch_view import PriceVariableIntervalStretchViewSet
from .views.price_variable_interval_view import PriceVariableIntervalViewSet
from .views.adjustment_condition_view import AdjustmentConditionViewSet
from .views.product_origin_view import ProductOriginViewSet
from .views.variable_calculation_view import VariableCalculationViewSet
from .views.billing_period_view import BillingPeriodViewSet
from .views.accounting_pricing_view import AccountingPricingViewSet
from .views.accounting_concept_view import AccountingConceptViewSet
from .views.accounting_type_view import AccountingTypeViewSet

router = routers.DefaultRouter()
router.register(r'adjustment', AdjustmentViewSet)
router.register(r'adjustment-interval-stretch', AdjustmentIntervalStretchViewSet)
router.register(r'adjustment-condition', AdjustmentConditionViewSet)

router.register(r'price-rate', PriceRateViewSet)
router.register(r'product', ProductViewSet)
router.register(r'product-origin', ProductOriginViewSet)

router.register(r'publication', PublicationViewSet)
router.register(r'billing-range', BillingRangeViewSet)
router.register(r'billing-period', BillingPeriodViewSet)
router.register(r'line-item-type', LineItemTypeViewSet)
router.register(r'tax', TaxViewSet)
router.register(r'article-code', ArticleCodeViewSet)
router.register(r'variable-calculation', VariableCalculationViewSet)

router.register(r'price-interval', PriceIntervalViewSet)
router.register(r'price-interval-stretch', PriceIntervalStretchViewSet)
router.register(r'price-variable-interval-stretch', PriceVariableIntervalStretchViewSet)
router.register(r'price-variable-interval', PriceVariableIntervalViewSet)

router.register(r'accounting-pricing', AccountingPricingViewSet)
router.register(r'accounting-concept', AccountingConceptViewSet)
router.register(r'accounting-type', AccountingTypeViewSet)
router.register(r'accounting-cost-center', AccountingCostCenterViewSet)

urlpatterns = [
    # Han d'anar abans d'`include(router.urls)`: el router registra `<recurs>/<pk>/`
    # amb un patró de pk genèric que, si es col·loca abans, capturaria "export" com a pk.
    path('billing-range/export/', GenericExportView.as_view(entity='billing_range'), name='billing-range-export'),
    path('line-item-type/export/', GenericExportView.as_view(entity='line_item_type'), name='line-item-type-export'),
    path('price-rate/export/', GenericExportView.as_view(entity='price_rate'), name='price-rate-export'),
    path('product/export/', GenericExportView.as_view(entity='product'), name='product-export'),
    path('', include(router.urls)),
]