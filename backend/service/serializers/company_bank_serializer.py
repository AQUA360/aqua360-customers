from rest_framework import serializers

from coredata.models import Bank, Country, ConfigProject
from coredata.serializers import BankSerializer, CountrySerializer
from ..models import Company, CompanyBank

class CompanyBankSerializer(serializers.ModelSerializer):
    
    country = CountrySerializer(read_only=True, required=False, allow_null=True)
    bank = BankSerializer(read_only=True, required=False, allow_null=True)
    
    #write_only=True
    country_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    bank_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    company_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    
    barcode_suffix = serializers.CharField(required=False, allow_null=True)
    
    # Nom de l'empresa titular del compte: el selector de bancs de la remesa SEPA
    # pot llistar comptes de mes d'una empresa (una explotacio en pot servir
    # diverses) i cal poder distingir-los.
    company_name = serializers.SerializerMethodField(read_only=True)
    
    def get_company_name(self, obj):
        if not obj.company:
            return None
        return obj.company.alias or obj.company.name
    
    class Meta:
        model = CompanyBank
        fields = '__all__'
        
    def create(self, validated_data):
        print("create bank company")
        print(validated_data)
        
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
        
        barcode_suffix = validated_data.pop('barcode_suffix', None)
        
        if barcode_suffix:
            ConfigProject.objects.update_or_create(
                token='reference_suffix_barcode_token', 
                defaults={'value': barcode_suffix}
            )

        return super(CompanyBankSerializer, self).create(validated_data)
    
    def update(self, instance, validated_data):
        print("update bank company")
        print(validated_data)
        
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
       
        barcode_suffix = validated_data.pop('barcode_suffix', None)
        
        if barcode_suffix:
            ConfigProject.objects.update_or_create(
                token='reference_suffix_barcode_token', 
                defaults={'value': barcode_suffix}
            )

        instance.save()
        return instance

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        config = ConfigProject.objects.filter(token='reference_suffix_barcode_token').first()
        representation['barcode_suffix'] = str(config.value).strip() if config and config.value else '501'
        return representation