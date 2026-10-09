from rest_framework import serializers

from pricing.utils.price_interval_stretch_service import variable_prixed_price_interval_stretch_order
from pricing.serializers.value_objects_serializer import ArticleCodeSerializer

from ..models import ArticleCode, PriceVariableInterval, PriceVariableIntervalStretch


class PriceVariableIntervalStretchSerializer(serializers.ModelSerializer):
    
    name = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    name_stretch = serializers.CharField(required=False, allow_null=True)
    related_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    article = ArticleCodeSerializer(read_only=True, required=False, allow_null=True)
    article_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    
    class Meta:
        model = PriceVariableIntervalStretch
        fields = '__all__'
        
    def create(self, validated_data):
        print(validated_data)
        end_stretch = validated_data.pop('name', None)
        price_interval_id = validated_data.pop('related_id', None)
        validated_data["name_stretch"] = end_stretch
        validated_data['stretch'] = 1
        if end_stretch or int(end_stretch) == 0:
            validated_data['end_stretch'] = int(end_stretch)
        
        if price_interval_id:
            price_interval = PriceVariableInterval.objects.get(id=price_interval_id)
            validated_data['price_variable_interval'] = price_interval
        
            
        new_price_interval_stretch = super(PriceVariableIntervalStretchSerializer, self).create(validated_data)
        variable_prixed_price_interval_stretch_order(None, new_price_interval_stretch.id, True)
        return new_price_interval_stretch
    
    def update(self, instance, validated_data):
        article_id = validated_data.pop('article_id', None)
        if article_id:
            article = ArticleCode.objects.get(id=article_id)
            validated_data['article'] = article
        new_price_interval_stretch = super(PriceVariableIntervalStretchSerializer, self).update(instance, validated_data)
        variable_prixed_price_interval_stretch_order(None, new_price_interval_stretch.id, False)
        return new_price_interval_stretch