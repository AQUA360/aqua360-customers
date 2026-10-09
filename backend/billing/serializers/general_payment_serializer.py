from rest_framework import serializers
from auth.serializers import UserMinimalSerializer
from billing.models import GeneralPayment, GeneralPaymentMandateLog, GeneralPaymentSepaDocument
from billing.serializers.general_payment_sepa_serializer import GeneralPaymentSepaDocumentSerializer
from billing.utils.payment_service import generate_mandate_id
from contract.models import PaymentType
from contract.serializers.value_objects_serializer import PaymentTypeSerializer
from coredata.models import PersonBank
from coredata.serializers import PersonBankSerializer
from documentmanager.utils.main_utils import delete_document
from service.models import CompanyBank
from service.serializers.company_bank_serializer import CompanyBankSerializer

class GeneralPaymentMandateLogSerializer(serializers.ModelSerializer):
    user = UserMinimalSerializer(read_only=True)
    class Meta:
        model = GeneralPaymentMandateLog
        fields = '__all__'

class GeneralPaymentSerializer(serializers.ModelSerializer):
    IBAN = PersonBankSerializer(read_only=True)
    company_iban = CompanyBankSerializer(read_only=True)
    mandate_logs = GeneralPaymentMandateLogSerializer(read_only=True, many=True)
    
    person_bank = serializers.PrimaryKeyRelatedField(
        queryset=PersonBank.objects.all(),
        write_only=True,
        source='IBAN',  
        required=False,
        allow_null=True,
    )
    company_bank = serializers.PrimaryKeyRelatedField(
        queryset=CompanyBank.objects.all(),
        write_only=True,
        source='company_iban',  
        required=False,
        allow_null=True,
    )
    
    iban_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    company_iban_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    type_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    token = serializers.CharField(write_only=True, required=False, allow_null=True)
    sepa_document = GeneralPaymentSepaDocumentSerializer(read_only=True, required=False, allow_null=True)
    mandate_token = serializers.CharField(write_only=True, required=False, allow_null=True)
    mandate_overwrite = serializers.CharField(write_only=True, required=False, allow_null=True)
    
    class Meta:
        model = GeneralPayment
        fields = '__all__'
    
    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation['type'] = PaymentTypeSerializer(instance.type).data if instance.type else None
        return representation
    
    def create(self, validated_data):
        print("creating general payment")
        iban = None
        
        mandate_token = validated_data.pop('mandate_token', None)
        mandate_overwrite = validated_data.pop('mandate_overwrite', None)
        iban_id = validated_data.pop('iban_id', None)
        company_iban_id = validated_data.pop('company_iban_id', None)
        type_id = validated_data.pop('type_id', None)
        if type_id: 
            try:
                type = PaymentType.objects.get(id=type_id)
                validated_data['type'] = type
            except:
                pass
        if iban_id:
            try:
                iban = PersonBank.objects.get(id=iban_id)
                validated_data['IBAN'] = iban
                iban = iban.iban
            except:
                pass
        if company_iban_id:
            try:
                company_iban = CompanyBank.objects.get(id=company_iban_id)
                validated_data['company_iban'] = company_iban
                iban = company_iban.iban
            except:
                pass
        if 'IBAN' in validated_data:
            iban = validated_data.get('IBAN').iban if validated_data.get('IBAN') else None
        token = validated_data.pop('token', None)
        if token:
            validated_data['token'] = token
        
        instance = GeneralPayment.objects.create(**validated_data)
        
        if mandate_token and iban:
            instance.mandate_id = generate_mandate_id(instance, mandate_token)
            GeneralPaymentMandateLog.objects.create(
                general_payment=instance, 
                previous_mandate_id=None,
                new_mandate_id=instance.mandate_id,
                user=self.context['request'].user, 
                is_manual=False)
            instance.save()
        else:
            if mandate_overwrite:
                GeneralPaymentMandateLog.objects.create(
                    general_payment=instance, 
                    previous_mandate_id=None,
                    new_mandate_id=mandate_overwrite,
                    user=self.context['request'].user, 
                    is_manual=True)
                instance.mandate_id = mandate_overwrite
                instance.save()
        
        return instance
    
    def _reference_count(self, instance):
        """Quantes entitats apunten a aquesta GeneralPayment.

        `Contract.payment` és una FK normal, no un OneToOne: la importació
        inicial va crear una GeneralPayment per (titular, compte) i hi va
        vincular tots els contractes d'aquell titular, de manera que la fila
        pot estar compartida.
        """
        from contract.models import Contract, ContractRequest, GeneralInvoice
        from service.models import ConnectionRequest
        return (
            Contract.objects.filter(payment=instance).count()
            + GeneralInvoice.objects.filter(payment=instance).count()
            + ContractRequest.objects.filter(payment=instance).count()
            + ConnectionRequest.objects.filter(payment=instance).count()
        )

    def _split(self, instance):
        """Còpia la GeneralPayment per no arrossegar la resta de contractes.

        Els mandate logs i el document SEPA es queden a la fila original:
        pertanyen a l'historial dels contractes que no s'estan modificant. La
        còpia arrenca sense document SEPA, que és el que toca quan hi ha un
        compte nou (cal una ordre de domiciliació nova).
        """
        copy = GeneralPayment.objects.get(pk=instance.pk)
        copy.pk = None
        copy.save()
        return copy

    def update(self, instance, validated_data):
        previous_iban = instance.IBAN.iban if instance.IBAN else None
        mandate_token = validated_data.pop('mandate_token', None)
        mandate_overwrite = validated_data.pop('mandate_overwrite', None)
        type_id = validated_data.pop('type_id', None)
        type = validated_data.pop('type', None)
        if type:
            type_id = type.id
        iban_id = validated_data.pop('iban_id', None)
        IBAN_data = validated_data.pop('IBAN', None)
        company_iban_id = validated_data.pop('company_iban_id', None)
        token = validated_data.pop('token', None)

        # --- Valors nous, encara sense escriure res -------------------------
        # Cal saber si la modalitat de pagament canvia ABANS de tocar la fila:
        # si canvia i la fila és compartida, s'ha de copiar en lloc de mutar-la.
        new_type = instance.type
        new_person_bank = instance.IBAN
        new_company_bank = instance.company_iban

        if type_id:
            new_type = PaymentType.objects.get(id=type_id)
            # El tipus manda sobre el compte: només la domiciliació en té.
            new_person_bank = None
            new_company_bank = None
            if new_type.token == 'DIRECT_DEBIT':
                if iban_id:
                    new_person_bank = PersonBank.objects.get(id=iban_id)
                elif IBAN_data:
                    new_person_bank = PersonBank.objects.get(id=IBAN_data.id)
                if company_iban_id:
                    new_company_bank = CompanyBank.objects.get(id=company_iban_id)

        # --- Copy-on-write --------------------------------------------------
        # Només es duplica si la modalitat de pagament canvia de debò I la fila
        # està compartida. Un titular amb un sol compte no genera cap fila nova.
        payment_changed = (
            new_type != instance.type
            or new_person_bank != instance.IBAN
            or new_company_bank != instance.company_iban
        )
        target = instance
        if payment_changed and self._reference_count(instance) > 1:
            target = self._split(instance)

        # Els camps de factura electrònica només es toquen si venen al payload:
        # desar la domiciliació no ha de buidar les dades DIR3.
        for field in ('accounting_office', 'managing_body', 'processing_unit', 'command', 'record'):
            if field in validated_data:
                setattr(target, field, validated_data.pop(field))

        if target is instance and type_id:
            # Canvi de tipus sobre la mateixa fila: si deixa de ser domiciliació,
            # el document SEPA ja no hi té sentit. En una còpia no cal, perquè la
            # còpia neix sense document i l'original el conserva.
            sepa_document = GeneralPaymentSepaDocument.objects.filter(general_payment=instance).first()
            if sepa_document and new_type.token != 'DIRECT_DEBIT':
                delete_document(sepa_document.file)
                sepa_document.delete()

        target.type = new_type
        target.IBAN = new_person_bank
        target.company_iban = new_company_bank

        if token:
            target.token = token
        new_iban = target.IBAN.iban if target.IBAN else None

        is_overwrite = False
        new_mandate_id = None
        if mandate_overwrite and mandate_overwrite != "" and mandate_overwrite != target.mandate_id:
            new_mandate_id = mandate_overwrite
            is_overwrite = True
        elif mandate_token and previous_iban != new_iban and new_iban:
            new_mandate_id = generate_mandate_id(target, mandate_token)

        if new_mandate_id and ((previous_iban != new_iban and new_iban) or is_overwrite):
            GeneralPaymentMandateLog.objects.get_or_create(
                general_payment=target,
                previous_mandate_id=target.mandate_id,
                new_mandate_id=new_mandate_id,
                user=self.context['request'].user,
                is_manual=is_overwrite)
            target.mandate_id = new_mandate_id

        target.save()
        return target
        
        

