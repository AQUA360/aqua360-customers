from rest_framework import serializers

from logger.models import LogProductChange
from pricing.serializers.translatable_mixin import TranslatableFieldMixin
from pricing.serializers.value_objects_serializer import ProductOriginSerializer
from service.models import Company, Exploitation
from service.serializers.company_serializer import CompanySerializer
from service.serializers.exploitation_serializer import ExploitationMinimalSerializer

from ..models import LineItemType, Product, ProductOrigin


def create_product_log(instance, changed_field, previous_value, new_value, user):
    LogProductChange.objects.create(
        object=instance,
        changed_field=changed_field,
        previous_value=str(previous_value) if previous_value is not None else None,
        new_value=str(new_value) if new_value is not None else None,
        user=user
    )


class ProductSerializer(TranslatableFieldMixin, serializers.ModelSerializer):

    exploitation = ExploitationMinimalSerializer(read_only=True, required=False, allow_null=True)
    company = CompanySerializer(read_only=True, required=False, allow_null=True)
    origin = ProductOriginSerializer(read_only=True, required=False, allow_null=True)
    product_related_id = serializers.IntegerField(read_only=True, source='product_related.id')
    product_related_token = serializers.CharField(read_only=True, source='product_related.token')
    product_related_name = serializers.CharField(read_only=True, source='product_related.name')

    class Meta:
        model = Product
        fields = '__all__'

class ProductSaveSerializer(TranslatableFieldMixin, serializers.ModelSerializer):

    exploitation_id = serializers.CharField(write_only=True, required=False, allow_null=True)
    company_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    product_related_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    origin_token = serializers.CharField(write_only=True, required=False, allow_null=True)

    class Meta:
        model = Product
        fields = '__all__'

    def create(self, validated_data):
        print(validated_data)
        if 'exploitation_id' in validated_data and validated_data['exploitation_id']:
            exploitation = Exploitation.objects.get(id=validated_data.pop('exploitation_id'))
            validated_data['exploitation'] = exploitation
        
        if 'company_id' in validated_data:
            company = Company.objects.get(id=validated_data.pop('company_id'))
            validated_data['company'] = company
        
        if 'product_related_id' in validated_data and validated_data['product_related_id']:
            product_related = Product.objects.get(id=validated_data.pop('product_related_id'))
            validated_data['product_related'] = product_related
        
        if 'origin_token' in validated_data:
            origin = ProductOrigin.objects.get(token=validated_data.pop('origin_token'))
            validated_data['origin'] = origin
        
        return super(ProductSaveSerializer, self).create(validated_data)
    
    def update(self, instance, validated_data):
        translations = validated_data.pop('name_translations', None)
        user = self.context['request'].user

        if 'name' in validated_data:
            if instance.name != validated_data['name']:
                create_product_log(
                    instance, 'name', instance.name, validated_data['name'], user
                )
            instance.name = validated_data.pop('name')
        
        if 'exploitation_id' in validated_data and validated_data['exploitation_id']:
            exploitation = Exploitation.objects.get(id=validated_data.pop('exploitation_id'))
            if instance.exploitation != exploitation:
                create_product_log(
                    instance,
                    'exploitation',
                    instance.exploitation.name if instance.exploitation else None,
                    exploitation.name,
                    user
                )
            instance.exploitation = exploitation
        
        if 'company_id' in validated_data:
            company = Company.objects.get(id=validated_data.pop('company_id'))
            if instance.company != company:
                create_product_log(
                    instance,
                    'company',
                    instance.company.name if instance.company else None,
                    company.name if company else None,
                    user
                )
            validated_data['company'] = company
            instance.company = company
        
        if 'product_related_id' in validated_data and validated_data['product_related_id']:
            product_related = Product.objects.get(id=validated_data.pop('product_related_id'))
            if instance.product_related != product_related:
                create_product_log(
                    instance,
                    'product_related',
                    instance.product_related.name if instance.product_related else None,
                    product_related.name,
                    user
                )
            instance.product_related = product_related
        
        if 'origin_token' in validated_data:
            origin = ProductOrigin.objects.get(token=validated_data.pop('origin_token'))
            if instance.origin != origin:
                create_product_log(
                    instance,
                    'origin',
                    instance.origin.name if instance.origin else None,
                    origin.name if origin else None,
                    user
                )
            instance.origin = origin
        
        line_items = LineItemType.objects.filter(billing_range__price_rate__product=instance)
        first_line_item = line_items.first()
        
        if 'billing_active' in validated_data:
            billing_active = validated_data.get('billing_active')
            if billing_active and first_line_item and first_line_item.active_choice == None:
                line_items.filter(active_choice=None).update(active_choice='DAYS')
            elif not billing_active:
                line_items.update(active_choice=None)
        
        if 'billing_inactive' in validated_data:
            billing_inactive = validated_data.get('billing_inactive')
            if billing_inactive and first_line_item and first_line_item.inactive_choice == None:
                line_items.filter(inactive_choice=None).update(inactive_choice='DAYS')
            elif not billing_inactive:
                line_items.update(inactive_choice=None)
        
        for attr, value in validated_data.items():
            previous_value = getattr(instance, attr)
            if previous_value != value:
                create_product_log(instance, attr, previous_value, value, user)
            setattr(instance, attr, value)

        instance.save()
        if translations is not None:
            self._apply_translations(instance, translations)
        return instance

class ProductListSerializer(serializers.ModelSerializer):
    
    exploitation_id = serializers.IntegerField(read_only=True, source='exploitation.id')
    exploitation_name = serializers.CharField(read_only=True, source='exploitation.name')
    company_id = serializers.IntegerField(read_only=True, source='company.id')
    product_related_token = serializers.CharField(read_only=True, source='product_related.token')
    product_related_name = serializers.CharField(read_only=True, source='product_related.name')
    origin_name = serializers.CharField(read_only=True, source='origin.name')
    origin_token = serializers.CharField(read_only=True, source='origin.token')
    origin_id = serializers.IntegerField(read_only=True, source='origin.id')
    
    class Meta:
        model = Product
        fields = [
            'id', 'token', 'name', 
            'origin_name', 'origin_token', 'origin_id',
            'company_id', 'exploitation_id', 'product_related_token', 
            'product_related_name', 'created_at', 'updated_at', 
            'exploitation_name', 'order_priority'
        ]

class ProductMinimalSerializer(serializers.ModelSerializer):
    origin_token = serializers.CharField(read_only=True, source='origin.token')
    class Meta:
        model = Product
        fields = ['id', 'token', 'name', 'origin_token', 'billing_active', 'billing_inactive']