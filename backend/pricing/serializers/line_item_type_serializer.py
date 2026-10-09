from rest_framework import serializers

from coredata.utils.name_utils import check_token_exists, generate_token
from pricing.serializers.adjustment_serializer import AdjustmentSerializer
from pricing.serializers.billing_range_serializer import BillingRangeSerializer
from pricing.serializers.price_interval_serializer import PriceIntervalSerializer
from pricing.serializers.price_rate_serializer import create_price_rate_log
from pricing.serializers.price_variable_interval_serializer import PriceVariableIntervalSerializer
from pricing.serializers.translatable_mixin import TranslatableFieldMixin
from pricing.serializers.value_objects_serializer import ArticleCodeSerializer, BillingPeriodSerializer, QuantitySerializer, TaxSerializer, VariableCalculationSerializer


from ..models import BillingPeriod, BillingRange, LineItemType, PriceInterval, PriceVariableInterval, Quantity, Tax, VariableCalculation

class LineItemTypeSerializer(TranslatableFieldMixin, serializers.ModelSerializer):
    
    price_variable = PriceVariableIntervalSerializer(read_only=True, required=False, allow_null=True)
    price_interval = PriceIntervalSerializer(read_only=True, required=False, allow_null=True)
    billing_range = BillingRangeSerializer(read_only=True, required=False, allow_null=True)
    adjustments = AdjustmentSerializer(many=True, read_only=True, required=False, allow_null=True)
    article = ArticleCodeSerializer(read_only=True, required=False, allow_null=True)
    
        
    class Meta:
        model = LineItemType
        fields = '__all__'
    
    def to_representation(self, instance):
        representation = super().to_representation(instance)
        
        representation["billing_period"] = BillingPeriodSerializer(instance.billing_period).data
        representation["quantity"] = VariableCalculationSerializer(instance.quantity).data
        representation["tax"] = TaxSerializer(instance.tax).data
        representation["product_billing_active"] = instance.billing_range.price_rate.product.billing_active if instance.billing_range else None
        representation["product_billing_inactive"] = instance.billing_range.price_rate.product.billing_inactive if instance.billing_range else None
        representation["price_rate_token"] = instance.billing_range.price_rate.token if instance.billing_range else None
        
        
        return representation
    

class LineItemTypeSaveSerializer(TranslatableFieldMixin, serializers.ModelSerializer):

    price_variable_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    price_interval_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    billing_range_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    billing_period_token = serializers.CharField(write_only=True, required=False, allow_null=True)
    quantity_token = serializers.CharField(write_only=True, required=False, allow_null=True)
    tax_token = serializers.CharField(write_only=True, required=False, allow_null=True)
    proration = serializers.BooleanField(write_only=True, required=False, allow_null=True)
    class Meta:
        model = LineItemType
        fields = '__all__'

    def create(self, validated_data):
        print(validated_data)
        price_variable = validated_data.pop('price_variable_id', None)
        price_interval = validated_data.pop('price_interval_id', None)
        billing_period = validated_data.pop('billing_period_token', None)
        quantity = validated_data.pop('quantity_token', None)
        tax = validated_data.pop('tax_token', None)
        billing_range_id = validated_data.pop('billing_range_id', None)
        
        last_id = LineItemType.objects.order_by('-id').first().id if LineItemType.objects.order_by('-id').first() else 0
        validated_data["token"] = check_token_exists(str(billing_range_id) + str(last_id), LineItemType)
        
        if(price_interval):
            price_interval = PriceInterval.objects.get(id=price_interval)
            validated_data['price_interval'] = price_interval
        
        if price_variable:
            price_variable = PriceVariableInterval.objects.get(id=price_variable)
            validated_data['price_variable'] = price_variable
        
        if billing_period:
            billing_period = BillingPeriod.objects.get(token=billing_period)
            validated_data['billing_period'] = billing_period
        else:
            validated_data['billing_period'] = None
        
        if quantity:
            quantity = VariableCalculation.objects.get(token=quantity)
            validated_data['quantity'] = quantity
        
        if billing_range_id:
            billing_range = BillingRange.objects.get(id=billing_range_id)
            validated_data['billing_range'] = billing_range
        
        if tax:
            tax = Tax.objects.get(token=tax)
            validated_data['tax'] = tax
        
        return super().create(validated_data)
    
    def update(self, instance, validated_data):
        print('on update')
        print(validated_data)
        
        price_variable_id = validated_data.pop('price_variable_id', None)
        price_interval_id = validated_data.pop('price_interval_id', None)
        billing_range_id = validated_data.pop('billing_range_id', None)
        tax_token = validated_data.pop('tax_token', None)
        quantity_token = validated_data.pop('quantity_token', None)
        billing_period_token = validated_data.pop('billing_period_token', None)
        translations = validated_data.pop('name_translations', None)
        user = self.context['request'].user
        #adjustments = validated_data.pop('adjustments', None)

        def current_price_rate():
            return instance.billing_range.price_rate if instance.billing_range else None

        if validated_data.get('proration'):
            if not instance.proration or instance.proration != validated_data.get('proration'):
                create_price_rate_log(
                    current_price_rate(),
                    'proration',
                    instance.proration,
                    validated_data.get('proration'),
                    user,
                    instance.name
                )
            instance.proration = validated_data.get('proration')

        if(billing_range_id):
            billing_range = BillingRange.objects.get(id=billing_range_id)
            if not instance.billing_range or instance.billing_range.id != billing_range.id:
                create_price_rate_log(
                    current_price_rate(),
                    'billing_range',
                    instance.billing_range.name if instance.billing_range else None,
                    billing_range.name if billing_range else None,
                    user,
                    instance.name
                )
            instance.billing_range = billing_range

        if tax_token:
            tax = Tax.objects.get(token=tax_token)
            if not instance.tax or instance.tax.token != tax.token:
                create_price_rate_log(
                    current_price_rate(),
                    'tax',
                    instance.tax.name if instance.tax else None,
                    tax.name if tax else None,
                    user,
                    instance.name
                )
            instance.tax = tax

        if quantity_token:
            quantity = VariableCalculation.objects.get(token=quantity_token)
            if not instance.quantity or instance.quantity.token != quantity.token:
                create_price_rate_log(
                    current_price_rate(),
                    'quantity',
                    instance.quantity.name if instance.quantity else None,
                    quantity.name if quantity else None,
                    user,
                    instance.name
                )
            instance.quantity = quantity
        else:
            if instance.quantity:
                create_price_rate_log(
                    current_price_rate(),
                    'quantity',
                    instance.quantity.name if instance.quantity else None,
                    None,
                    user,
                    instance.name
                )
            instance.quantity = None

        if billing_period_token:
            billing_period = BillingPeriod.objects.get(token=billing_period_token)
            if not instance.billing_period or instance.billing_period.token != billing_period.token:
                create_price_rate_log(
                    current_price_rate(),
                    'billing_period',
                    instance.billing_period.name if instance.billing_period else None,
                    billing_period.name if billing_period else None,
                    user,
                    instance.name
                )
            instance.billing_period = billing_period
        else:
            if instance.billing_period:
                create_price_rate_log(
                    current_price_rate(),
                    'billing_period',
                    instance.billing_period.name if instance.billing_period else None,
                    None,
                    user,
                    instance.name
                )
            instance.billing_period = None

        if validated_data.get('name'):
            if not instance.name or instance.name != validated_data.get('name'):
                print("instance name: ", instance.name)
                print("validated name: ", validated_data.get('name'))
                print("instance name != validated name: ", instance.name != validated_data.get('name'))
                create_price_rate_log(
                    current_price_rate(),
                    'name',
                    instance.name if instance.name else None,
                    validated_data.get('name'),
                    user,
                    instance.name
                )
            instance.name = validated_data.pop('name')

        if instance.price != validated_data.get('price'):
            create_price_rate_log(
                current_price_rate(),
                'price',
                instance.price,
                validated_data.get('price'),
                user,
                instance.name
            )
        if instance.proportional_price != validated_data.get('proportional_price'):
            create_price_rate_log(
                current_price_rate(),
                'proportional_price',
                instance.proportional_price,
                validated_data.get('proportional_price'),
                user,
                instance.name
            )
        if instance.price_interval != validated_data.get('price_interval'):
            create_price_rate_log(
                current_price_rate(),
                'price_interval',
                instance.price_interval.token if instance.price_interval else None,
                validated_data.get('price_interval'),
                user,
                instance.name
            )
        if instance.price_variable != validated_data.get('price_variable'):
            create_price_rate_log(
                current_price_rate(),
                'price_variable',
                instance.price_variable.token if instance.price_variable else None,
                validated_data.get('price_variable'),
                user,
                instance.name
            )
        if instance.formula != validated_data.get('formula'):
            create_price_rate_log(
                current_price_rate(),
                'formula',
                instance.formula,
                validated_data.get('formula'),
                user,
                instance.name
            )
        
        instance.price = None
        instance.proportional_price = None
        instance.price_interval = None
        instance.price_variable = None

        if validated_data.get('price'):
            instance.price = validated_data.get('price')

        elif validated_data.get('proportional_price'):
            instance.proportional_price = validated_data.get('proportional_price')

        elif price_interval_id:
            try:
                price_interval = PriceInterval.objects.get(id=price_interval_id)
                instance.price_interval = price_interval
            except PriceInterval.DoesNotExist:
                raise ValueError(f"PriceInterval with id {price_interval_id} does not exist.")

        elif price_variable_id:
            try:
                price_variable = PriceVariableInterval.objects.get(id=price_variable_id)
                instance.price_variable = price_variable
            except PriceVariableInterval.DoesNotExist:
                raise ValueError(f"PriceVariableInterval with id {price_variable_id} does not exist.")

        elif validated_data.get('formula'):
            instance.formula = validated_data.get('formula')

        if not (price_variable_id or price_interval_id or 
                validated_data.get('proportional_price') or 
                validated_data.get('price') or
                validated_data.get('formula')):
            instance.price = None
            instance.proportional_price = None
            instance.price_interval = None
            instance.price_variable = None
            instance.formula = None
        for attr, value in validated_data.items():
            previous_value = getattr(instance, attr)
            if previous_value != value:
                create_price_rate_log(
                    current_price_rate(),
                    attr,
                    previous_value if previous_value else None,
                    value,
                    user,
                    instance.name
                )
            setattr(instance, attr, value)
        instance.save()
        if translations is not None:
            self._apply_translations(instance, translations)

        return instance
        

class LineItemTypeListSerializer(serializers.ModelSerializer):
    
    price_interval_token = serializers.CharField(read_only=True, source='price_interval.token')
    billing_range_token = serializers.CharField(read_only=True, source='billing_range.token')
    price_rate_name = serializers.CharField(read_only=True, source='billing_range.price_rate.name')
    quantity_name = serializers.CharField(read_only=True, source='quantity.name')
    
    class Meta:
        model = LineItemType
        fields = [
            'id', 'name', 'token', 
            'billing_range_token', 'tax', 'price_interval_token',
            'price','proportional_price', 'quantity_name', 
            'created_at', 'updated_at', 'price_rate_name']
    
    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation["tax"] = str(instance.tax)
        representation["price_interval"] = str(instance.price_interval)
        
        return representation

class LineItemTypeArticleSerializer(serializers.ModelSerializer):
    
    article = ArticleCodeSerializer(read_only=True, required=False, allow_null=True)
    
    class Meta:
        model = LineItemType
        fields = [
            'id', 'name', 'token', 'code', 'article', 'created_at', 'updated_at'
            ]
    
    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation["price_rate_name"] = str(instance.billing_range.price_rate.name) if instance.billing_range and instance.billing_range.price_rate else None
        representation["has_blocks"] = True if instance.price_interval or instance.price_variable else False
        representation["blocks_fix"] = True if instance.price_variable else False
        return representation

class LineItemTypeMinimalSerializer(serializers.ModelSerializer):
    
    
    class Meta:
        model = LineItemType
        fields = [
            'id', 'name', 'token', 
            'tax','price','proportional_price', 
            'created_at', 'updated_at',
        ]
    
    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation["tax"] = str(instance.tax)
        representation["price_interval"] = str(instance.price_interval)
        
        
        return representation