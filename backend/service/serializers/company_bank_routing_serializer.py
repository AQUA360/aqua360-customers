from rest_framework import serializers

from coredata.serializers import BankSerializer
from service.models import CompanyBank, CompanyBankRouting


class CompanyBankRoutingSerializer(serializers.ModelSerializer):
    """
    Una fila del mapa d'encaminament: a quin compte de l'empresa va el que paga
    una entitat concreta (`payer_bank`), el que paga des de fora (`foreign`) o
    la resta (`default`).
    """

    bank = BankSerializer(read_only=True)
    bank_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    company_bank_iban = serializers.SerializerMethodField(read_only=True)
    company_bank_name = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = CompanyBankRouting
        fields = '__all__'

    def get_company_bank_iban(self, obj):
        return obj.company_bank.iban if obj.company_bank else None

    def get_company_bank_name(self, obj):
        if not obj.company_bank or not obj.company_bank.bank:
            return None
        return obj.company_bank.bank.name

    def validate(self, attrs):
        instance = self.instance
        match_type = attrs.get('match_type', instance.match_type if instance else CompanyBankRouting.MATCH_PAYER_BANK)
        company = attrs.get('company', instance.company if instance else None)
        company_bank = attrs.get('company_bank', instance.company_bank if instance else None)
        bank_id = attrs.get('bank_id', None)
        if bank_id is None and instance:
            bank_id = instance.bank_id

        if match_type == CompanyBankRouting.MATCH_PAYER_BANK and not bank_id:
            raise serializers.ValidationError(
                {'bank_id': "Cal indicar l'entitat del pagador."}
            )

        # A `foreign` i `default` l'entitat no hi pinta res: si arribés
        # informada, la restricció d'unicitat per empresa no s'aplicaria.
        if match_type != CompanyBankRouting.MATCH_PAYER_BANK:
            attrs['bank_id'] = None

        # El compte de destí ha de ser d'una empresa: no es valida que sigui de
        # `company` a propòsit — remesar factures d'una empresa al compte d'una
        # altra és una decisió de negoci, i a la pantalla de remeses ja surt com
        # a avís.
        if company_bank and not isinstance(company_bank, CompanyBank):
            raise serializers.ValidationError({'company_bank': "Compte no vàlid."})

        if not company:
            raise serializers.ValidationError({'company': "Cal indicar l'empresa."})

        return attrs

    def create(self, validated_data):
        bank_id = validated_data.pop('bank_id', None)
        validated_data['bank_id'] = bank_id
        return super().create(validated_data)

    def update(self, instance, validated_data):
        if 'bank_id' in validated_data:
            instance.bank_id = validated_data.pop('bank_id')
        return super().update(instance, validated_data)
