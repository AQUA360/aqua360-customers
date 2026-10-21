from django.core.exceptions import ImproperlyConfigured
from django.db import transaction
from rest_framework import serializers
from django_filters import rest_framework as filters

from communication.models import CommunicationUseType
from communication.serializers.value_objects_serializer import CommunicationUseTypeSerializer
from documentmanager.serializers import DocumentSerializer
from ..models import *
import logging

logger = logging.getLogger(__name__)


class ConnectionStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = ConnectionStatus
        fields = '__all__'

class ConnectionTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ConnectionType
        fields = '__all__'

class ConnectionUseTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ConnectionUseType
        fields = '__all__'

class ConnectionInstallationTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ConnectionInstallationType
        fields = '__all__'

class ConnectionValveTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ConnectionValveType
        fields = '__all__'

class ConnectionMaterialSerializer(serializers.ModelSerializer):
    class Meta:
        model = ConnectionMaterial
        fields = '__all__'

class ConnectionDiameterSerializer(serializers.ModelSerializer):
    class Meta:
        model = ConnectionDiameter
        fields = '__all__'

class ConnectionRequestStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = ConnectionRequestStatus
        fields = '__all__'

class ClusterStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClusterStatus
        fields = '__all__'

class ClusterNozzleStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClusterNozzleStatus
        fields = '__all__'

class ClusterNozzleTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClusterNozzleType
        fields = '__all__'

class SupplyPointTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = SupplyPointType
        fields = '__all__'

class SupplyPointStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = SupplyPointStatus
        fields = '__all__'

class SupplyPointSourceSerializer(serializers.ModelSerializer):
    class Meta:
        model = SupplyPointSource
        fields = '__all__'

class SupplyPointSupplyTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = SupplyPointSupplyType
        fields = '__all__'

class MeterStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = MeterStatus
        fields = '__all__'

class SupplyCutStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = SupplyCutStatus
        fields = '__all__'

class MeterCaliberSerializer(serializers.ModelSerializer):
    class Meta:
        model = MeterCaliber
        fields = '__all__'

class SupplyPointPlacementSerializer(serializers.ModelSerializer):
    class Meta:
        model = SupplyPointPlacement
        fields = '__all__'

class SupplyCutCauseSerializer(serializers.ModelSerializer):
    class Meta:
        model = SupplyCutCause
        fields = '__all__'
        
class MeterManufacturerSerializer(serializers.ModelSerializer):
    class Meta:
        model = MeterManufacturer
        fields = '__all__'

class MeterModelSerializer(serializers.ModelSerializer):
    class Meta:
        model = MeterModel
        fields = '__all__'

class CompanyTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = CompanyType
        fields = '__all__'

def apply_config_email_password(config_email, password=None, clear_password=False):
    """Desa (xifrada) o treu la contrasenya SMTP del correu; una contrasenya buida manté l'actual."""
    if password:
        try:
            config_email.set_password(password)
        except ImproperlyConfigured:
            logger.exception("No s'ha pogut xifrar la contrasenya del correu")
            raise serializers.ValidationError({'password': "Falta configurar el xifratge de contrasenyes al servidor."})
    elif clear_password:
        config_email.encrypted_password = None


def pop_config_email_password(config_email_data):
    """Treu del diccionari els camps de contrasenya (no són camps del model) i els retorna."""
    config_email_data.pop('has_password', None)
    return config_email_data.pop('password', None), bool(config_email_data.pop('clear_password', False))


def ensure_single_default_email(config_emails):
    """Només un correu per defecte: el primer marcat o, si no n'hi ha cap, el primer."""
    if not config_emails:
        return
    default_email = next((email for email in config_emails if email.is_default), config_emails[0])
    for email in config_emails:
        if email.is_default != (email is default_email):
            email.is_default = email is default_email
            email.save(update_fields=['is_default'])


class CompanyConfigEmailSerializer(serializers.ModelSerializer):
    # La contrasenya només s'escriu; en llegir només se sap si n'hi ha (has_password).
    password = serializers.CharField(write_only=True, required=False, allow_blank=True, allow_null=True, trim_whitespace=False)
    clear_password = serializers.BooleanField(write_only=True, required=False, default=False)

    class Meta:
        model = CompanyConfigEmail
        exclude = ['encrypted_password']

    def create(self, validated_data):
        password = validated_data.pop('password', None)
        clear_password = validated_data.pop('clear_password', False)
        instance = CompanyConfigEmail(**validated_data)
        apply_config_email_password(instance, password, clear_password)
        instance.save()
        return instance

    def update(self, instance, validated_data):
        password = validated_data.pop('password', None)
        clear_password = validated_data.pop('clear_password', False)
        apply_config_email_password(instance, password, clear_password)
        return super().update(instance, validated_data)
    
    def to_representation(self, instance):
        data = super().to_representation(instance)
        data['has_password'] = instance.has_password
        data['label'] = f"{instance.mail_send_user} <{instance.use_type.name}>"
        data['value'] = instance.id
        data['use_type'] = {
            'value': instance.use_type.id,
            'label': instance.use_type.name,
            'token': instance.use_type.token,
        }
        return data

class CompanyConfigSerializer(serializers.ModelSerializer):
    company = serializers.SerializerMethodField()
    company_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    company_config_emails = CompanyConfigEmailSerializer(many=True, read_only=True, required=False, allow_null=True)
    
    
    config_emails_data = serializers.ListField(child=serializers.DictField(), write_only=True, required=False, allow_null=True)
    
    class Meta:
        model = CompanyConfig
        fields = '__all__'

    def get_company(self, obj):
        company_data = {
            'id': obj.company_configs.first().id,
            'name': obj.company_configs.first().name,
            'phone': obj.company_configs.first().phone,
            'email': obj.company_configs.first().email,
            'address_complete': str(obj.company_configs.first().address),
        }
        return company_data
    
    @transaction.atomic
    def create(self, validated_data):
        company_id = validated_data.pop('company_id', None)
        config_emails_data = validated_data.pop('config_emails_data', None)
        
        instance = super().create(validated_data)
        if company_id:
            company = Company.objects.get(id=company_id)
            company.config = instance
            company.save()
        
        if config_emails_data:
            use_types = CommunicationUseType.objects.all()
            new_config_emails = []
            for config_email_data in config_emails_data:
                use_type = use_types.filter(id=config_email_data.pop('use_type').get('value')).first()
                password, clear_password = pop_config_email_password(config_email_data)
                config_email = CompanyConfigEmail(
                    company_config=instance,
                    use_type=use_type,
                    **config_email_data
                )
                apply_config_email_password(config_email, password, clear_password)
                config_email.save()
                new_config_emails.append(config_email)
            ensure_single_default_email(new_config_emails)
        
        return instance

    @transaction.atomic
    def update(self, instance, validated_data):
        config_emails_data = validated_data.pop('config_emails_data', None)
        use_types = CommunicationUseType.objects.all()
        if config_emails_data:
            previous_config_emails = instance.company_config_emails.all()
            new_config_emails = []
            for config_email_data in config_emails_data:
                use_type = use_types.filter(id=config_email_data.pop('use_type').get('value')).first()
                password, clear_password = pop_config_email_password(config_email_data)
                if config_email_data.get('id'):
                    config_email = previous_config_emails.filter(id=config_email_data.pop('id')).first()
                    config_email.use_type = use_type
                    config_email.mail_send_user = config_email_data.pop('mail_send_user')
                    config_email.mail_send_mail = config_email_data.pop('mail_send_mail')
                    config_email.is_default = config_email_data.pop('is_default')
                    config_email.token = config_email_data.pop('token', config_email.token)
                    apply_config_email_password(config_email, password, clear_password)
                    config_email.save()
                    new_config_emails.append(config_email)
                else:
                    new_config_email = CompanyConfigEmail(
                        company_config=instance,
                        use_type=use_type,
                        **config_email_data
                    )
                    apply_config_email_password(new_config_email, password, clear_password)
                    new_config_email.save()
                    new_config_emails.append(new_config_email)
            ensure_single_default_email(new_config_emails)
            previous_config_emails.exclude(mail_send_mail__in=[config_email.mail_send_mail for config_email in new_config_emails]).update(is_active=False)
            # instance.company_config_emails.clear()
            instance.company_config_emails.set(new_config_emails)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance


class ConnectionDocumentationTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ConnectionDocumentationType
        fields = '__all__'


class ConnectionDocumentationFileSerializer(serializers.ModelSerializer):
    file = DocumentSerializer(read_only=True, required=False, allow_null=True)
    type = ConnectionDocumentationTypeSerializer(read_only=True, required=False, allow_null=True)

    class Meta:
        model = ConnectionDocumentationFile
        fields = ['id', 'file', 'type', 'is_active']


class ClusterDocumentationTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClusterDocumentationType
        fields = '__all__'


class ClusterDocumentationFileSerializer(serializers.ModelSerializer):
    file = DocumentSerializer(read_only=True, required=False, allow_null=True)
    type = ClusterDocumentationTypeSerializer(read_only=True, required=False, allow_null=True)

    class Meta:
        model = ClusterDocumentationFile
        fields = ['id', 'file', 'type', 'is_active']
