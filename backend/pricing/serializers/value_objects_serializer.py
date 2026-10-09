from rest_framework import serializers
from ..models import Quantity, BillingPeriod, Tax, AdjustmentOperation, VariableCalculation, AdjustmentIntervalStretch, ProductOrigin, ArticleCode

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
    
class ProductOriginSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductOrigin
        fields = '__all__'

class ArticleCodeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ArticleCode
        fields = '__all__'