from rest_framework import serializers

from coredata.models import Bank, Country
from coredata.serializers import BankSerializer, CountrySerializer
from ..models import Company, CompanyBank
from billing.utils.barcode_service import get_reference_suffix

class CompanyBankSerializer(serializers.ModelSerializer):
    
    country = CountrySerializer(read_only=True, required=False, allow_null=True)
    bank = BankSerializer(read_only=True, required=False, allow_null=True)
    
    #write_only=True
    country_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    bank_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    company_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    
    # Sufix que fan servir els codis de barres: el del compte o, si no en té, el global
    effective_barcode_suffix = serializers.SerializerMethodField(read_only=True)
    
    # Nom de l'empresa titular del compte: el selector de bancs de la remesa SEPA
    # pot llistar comptes de mes d'una empresa (una explotacio en pot servir
    # diverses) i cal poder distingir-los.
    company_name = serializers.SerializerMethodField(read_only=True)
    
    def get_company_name(self, obj):
        if not obj.company:
            return None
        return obj.company.alias or obj.company.name
    
    def get_effective_barcode_suffix(self, obj):
        return get_reference_suffix(obj)
    
    def validate_barcode_suffix(self, value):
        # Quadern 60 (format 507): el sufix de la referència és de 3 dígits
        value = (value or '').strip()
        if not value:
            return None
        if not (len(value) == 3 and value.isascii() and value.isdigit()):
            raise serializers.ValidationError('El sufix del codi de barres ha de tenir 3 dígits.')
        return value
    
    class Meta:
        model = CompanyBank
        fields = '__all__'
        
    def create(self, validated_data):
        print("create bank company")
        
        country_id = validated_data.pop('country_id', None)
        bank_id = validated_data.pop('bank_id', None)
        company_id = validated_data.pop('company_id', None)
        
        if country_id:
            country_instance = Country.objects.get(id=country_id)
            validated_data['country'] = country_instance
            
        if bank_id:
            bank_instance = Bank.objects.get(id=bank_id)
            validated_data['bank'] = bank_instance
            
        if company_id:
            print("company_id")
            company_instance = Company.objects.get(id=company_id)
            print(company_instance)
            validated_data['company'] = company_instance
        
        return super(CompanyBankSerializer, self).create(validated_data)
    
    def update(self, instance, validated_data):
        print("update bank company")
        
        country_id = validated_data.pop('country_id', None)
        bank_id = validated_data.pop('bank_id', None)
        
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        if country_id:
            country_instance = Country.objects.get(id=country_id)
            instance.country = country_instance
            
        if bank_id:
            bank_instance = Bank.objects.get(id=bank_id)
            instance.bank = bank_instance

        instance.save()
        return instance