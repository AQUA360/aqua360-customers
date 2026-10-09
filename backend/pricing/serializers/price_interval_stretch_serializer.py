from rest_framework import serializers

from pricing.utils.price_interval_stretch_service import price_interval_stretch_order
from pricing.serializers.translatable_mixin import TranslatableFieldMixin
from pricing.serializers.value_objects_serializer import ArticleCodeSerializer

from ..models import ArticleCode, PriceInterval, PriceIntervalStretch


class PriceIntervalStretchSerializer(TranslatableFieldMixin, serializers.ModelSerializer):

    translations_field_name = 'name_stretch_translations'
    translation_attr = 'name_stretch'

    name = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    related_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    article = ArticleCodeSerializer(read_only=True, required=False, allow_null=True)
    article_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    class Meta:
        model = PriceIntervalStretch
        fields = '__all__'

    def create(self, validated_data):
        print(validated_data)
        end_stretch = validated_data.pop('name', None)
        price_interval_id = validated_data.pop('related_id', None)
        validated_data["name_stretch"] = end_stretch
        validated_data['stretch'] = 1
        if end_stretch:
            validated_data['end_stretch'] = end_stretch

        if price_interval_id:
            price_interval = PriceInterval.objects.get(id=price_interval_id)
            validated_data['price_interval'] = price_interval

        new_price_interval_stretch = super(PriceIntervalStretchSerializer, self).create(validated_data)
        #new_price_interval_stretch.stretch = price_interval_stretch_order(None, new_price_interval_stretch.id)
        price_interval_stretch_order(None, new_price_interval_stretch.id, True)
        return new_price_interval_stretch

    def update(self, instance, validated_data):
        article_id = validated_data.pop('article_id', None)
        if article_id:
            article = ArticleCode.objects.get(id=article_id)
            validated_data['article'] = article
        new_price_interval_stretch = super(PriceIntervalStretchSerializer, self).update(instance, validated_data)
        price_interval_stretch_order(None, new_price_interval_stretch.id, False)
        return new_price_interval_stretch