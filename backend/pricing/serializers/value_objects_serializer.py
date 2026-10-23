from rest_framework import serializers
from pricing.utils.formula_evaluator import normalize_decimal_comma, replace_percentage, validate
from ..models import Quantity, BillingPeriod, Tax, AdjustmentOperation, VariableCalculation, AdjustmentIntervalStretch, ProductOrigin, ArticleCode

def validate_formula_field(value, percentages=False):
    """Valida la fórmula en desar-la i corregeix la coma decimal (0,5 -> 0.5).

    `percentages`: les fórmules dels conceptes de factura amb productes admeten 21% (vegeu
    replace_percentage).
    """
    if not value:
        return value
    value = normalize_decimal_comma(value)
    error = validate(replace_percentage(value) if percentages else value)
    if error:
        raise serializers.ValidationError(error)
    return value


class AdjustmentOperationSerializer(serializers.ModelSerializer):
    class Meta:
        model = AdjustmentOperation
        fields = '__all__'

class VariableCalculationSerializer(serializers.ModelSerializer):
    class Meta:
        model = VariableCalculation
        fields = '__all__'

class QuantitySerializer(serializers.ModelSerializer):
    class Meta:
        model = Quantity
        fields = '__all__'


class BillingPeriodSerializer(serializers.ModelSerializer):
    class Meta:
        model = BillingPeriod
        fields = '__all__'

class TaxSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tax
        fields = '__all__'
        
class AdjustmentIntervalStretchSerializer(serializers.ModelSerializer):
    class Meta:
        model = AdjustmentIntervalStretch
        fields = '__all__'

    def validate_formula(self, value):
        return validate_formula_field(value)
    
class ProductOriginSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductOrigin
        fields = '__all__'

class ArticleCodeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ArticleCode
        fields = '__all__'