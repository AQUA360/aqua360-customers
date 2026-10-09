import datetime
from rest_framework import serializers
from django.db import transaction


from coredata.utils.name_utils import generate_token
from pricing.serializers.price_rate_minimal_serializer import PriceRateMinimalSerializer
from pricing.serializers.publication_serializer import PublicationMinimalSerializer
from pricing.utils.billing_range_service import billing_range_duplicate
from ..models import BillingRange, PriceRate



class BillingRangeSerializer(serializers.ModelSerializer):
    publication = PublicationMinimalSerializer(read_only=True, required=False, allow_null=True)
    price_rate = PriceRateMinimalSerializer(read_only=True, required=False, allow_null=True)
    class Meta:
        model = BillingRange
        fields = '__all__'
        
    def to_representation(self, instance):
        representation = super().to_representation(instance)
        from pricing.serializers.line_item_type_serializer import LineItemTypeListSerializer
        representation["line_item_types"] = [LineItemTypeListSerializer(line_item_type).data for line_item_type in instance.line_item_types.all()]
        return representation

class BillingRangeSaveSerializer(serializers.ModelSerializer):
    token = serializers.CharField(required=False, allow_blank=True)
    
    publication_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    end_active = serializers.DateTimeField(write_only=True, required=False, allow_null=True)
    price_rate_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    duplicate_check = serializers.BooleanField(write_only=True, required=False, allow_null=True)
    class Meta:
        model = BillingRange
        fields = '__all__'
    
    @transaction.atomic
    def create(self, validated_data):
        print(validated_data)
        price_rate_id = validated_data.pop('price_rate_id', None)
        previous_br = None
        price_rate = validated_data.pop('price_rate', None)
        duplicate_check = validated_data.pop('duplicate_check', None)
        validated_data["token"] = generate_token(BillingRange)
        end_active = validated_data.pop('end_active', None)
        start = validated_data.get('start', None)
        if 'publication' in validated_data:
            publication = validated_data.pop('publication')
            validated_data['publication'] = publication
        # Resolve price_rate object to perform validation
        price_rate_obj = None
        if price_rate_id:
            try:
                price_rate_obj = PriceRate.objects.get(id=price_rate_id)
            except PriceRate.DoesNotExist:
                pass
        elif price_rate:
            price_rate_obj = price_rate

        if start and price_rate_obj:
            try:
                previous_br = BillingRange.objects.get(end=None, price_rate=price_rate_obj)
                if previous_br and previous_br.start >= start:
                    raise serializers.ValidationError(
                        {"start": f"La data d'inici ha de ser posterior a la data d'inici de l'interval anterior ({previous_br.start})."}
                    )
            except BillingRange.DoesNotExist:
                previous_br = None

        try:
            if previous_br:
                previous_br.end = start if start else end_active
                previous_br.save()
        except BillingRange.DoesNotExist:
            print('\nno previous br')
        
        
        try:
            if price_rate_id:
                price_rate = PriceRate.objects.get(id = price_rate_id)
                validated_data['price_rate'] = price_rate_id
            elif price_rate:
                validated_data['price_rate'] = price_rate
            
        except PriceRate.DoesNotExist:
            print('\nno price rate')
            
        new_billing_range = super(BillingRangeSaveSerializer, self).create(validated_data)
        
        if end_active and start and start > datetime.datetime.now().date():
            price_rate.billing_range_active = price_rate.billing_range_active
        else:
            """ if price_rate.billing_range_active:
                billing_range_change = BillingRangeChange.objects.create(
                    billing_range = price_rate.billing_range_active,
                    change_date = validated_data.get('start', end_active),
                    has_billed = False
                    )
                price_rate.prev_billing_range = billing_range_change """
            price_rate.billing_range_active = new_billing_range
        price_rate.save()
        
        if duplicate_check:
            print(previous_br.id)
            print(new_billing_range.id)
            billing_range_duplicate(None, previous_br.id, new_billing_range.id)
        
        return new_billing_range
    
    @transaction.atomic
    def update(self, instance, validated_data):
        if 'publication' in validated_data:
            publication = validated_data.pop('publication')
            validated_data['publication'] = publication
        if 'publication_id' in validated_data:
            publication = PublicationMinimalSerializer().validate(validated_data['publication_id'])
            validated_data['publication'] = publication
        
        return super(BillingRangeSaveSerializer, self).update(instance, validated_data)
 
class BillingRangeMinimalSerializer(serializers.ModelSerializer):
    class Meta:
        model = BillingRange
        fields = ['id', 'token', 'start', 'end']
        