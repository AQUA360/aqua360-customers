from rest_framework import serializers
from coredata.models import Address
from coredata.serializers import AddressSerializer
from pricing.serializers.translatable_mixin import MultiTranslatableFieldMixin
from service.serializers.company_bank_serializer import CompanyBankSerializer
from service.serializers.value_objects_serializer import CompanyConfigSerializer, CompanyTypeSerializer
from ..models import ( Company, CompanyBank, CompanyConfig, CompanyType )


class CompanyMinimalSerializer(serializers.ModelSerializer):
    class Meta:
        model = Company
        fields = ("id", "name", "alias", "is_active")


class CompanySerializer(MultiTranslatableFieldMixin, serializers.ModelSerializer):
    address = serializers.IntegerField(write_only=True)
    logo_delete = serializers.BooleanField(write_only=True, required=False, allow_null=True)
    company_banks = CompanyBankSerializer(many=True, read_only=True)
    config = CompanyConfigSerializer(read_only=True, required=False, allow_null=True)
    type = CompanyTypeSerializer(read_only=True, required=False, allow_null=True)
    company_banks_ids = serializers.ListField(child=serializers.IntegerField(), write_only=True, required=False, allow_null=True)
    config_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    type_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)

    translatable_fields = [
        {
            "field_name": "invoice_footer_text_translations",
            "attr": "invoice_footer_text",
            "related_name": "invoice_footer_text_i18n",
        },
        {
            "field_name": "data_protection_law_text_translations",
            "attr": "data_protection_law_text",
            "related_name": "data_protection_law_text_i18n",
        },
    ]

    class Meta:
        model = Company
        fields = '__all__'

    def create(self, validated_data):
        translations = self.pop_multi_translations(validated_data)
        company_banks_ids = validated_data.pop('company_banks_ids', None)
        config_id = validated_data.pop('config_id', None)
        type_id = validated_data.pop('type_id', None)
        address_data = validated_data.pop('address')

        address, _ = Address.objects.get_or_create(
            id=address_data
        )

        if 'logo_delete' in validated_data:
            validated_data.pop('logo_delete')

        is_default = validated_data.get('is_default', False)
        if is_default:
            Company.objects.all().update(is_default=False)

        company = Company.objects.create(
            address=address,
            **validated_data
        )

        if type_id:
            type = CompanyType.objects.get(id=type_id)
            company.type = type
            company.save()
        
        if config_id:
            config = CompanyConfig.objects.get(id=config_id)
            company.config = config
            company.save()
        
        if company_banks_ids:
            company_banks = CompanyBank.objects.filter(id__in=company_banks_ids)
            company.company_banks.add(*company_banks)
        
        company.is_active = True
        company.save()

        self._apply_multi_translations(company, translations)

        return company

    def update(self, instance, validated_data):
        translations = self.pop_multi_translations(validated_data)
        company_banks_ids = validated_data.pop('company_banks_ids', None)
        config_id = validated_data.pop('config_id', None)
        address_data = validated_data.pop('address')
        type_id = validated_data.pop('type_id', None)
        address, _ = Address.objects.get_or_create(
            id=address_data
        )

        if type_id:
            type = CompanyType.objects.get(id=type_id)
            instance.type = type

        is_default = validated_data.get('is_default', False)
        if is_default:
            Company.objects.all().update(is_default=False)

        if validated_data.get('logo_delete'):
            instance.logo.delete(save=False)
            instance.logo = None
            validated_data.pop('logo_delete')

        instance.address = address

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        if config_id:
            config = CompanyConfig.objects.get(id=config_id)
            instance.config = config
            
        if company_banks_ids:
            company_banks = CompanyBank.objects.filter(id__in=company_banks_ids)
            instance.company_banks.clear()
            instance.company_banks.add(*company_banks)
        else:
            instance.company_banks.clear()

        instance.save()

        self._apply_multi_translations(instance, translations)

        return instance

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation['address'] = AddressSerializer(instance.address).data
        representation['address_complete'] = str(instance.address)
        return representation