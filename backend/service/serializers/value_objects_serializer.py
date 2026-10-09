from rest_framework import serializers
from django_filters import rest_framework as filters

from communication.models import CommunicationUseType
from communication.serializers.value_objects_serializer import CommunicationUseTypeSerializer
from documentmanager.serializers import DocumentSerializer
from ..models import *

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

class CompanyConfigEmailSerializer(serializers.ModelSerializer):
    class Meta:
        model = CompanyConfigEmail
        fields = '__all__'
    
    def to_representation(self, instance):
        data = super().to_representation(instance)
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
            for config_email_data in config_emails_data:
                use_type = use_types.filter(id=config_email_data.pop('use_type').get('value')).first()
                CompanyConfigEmail.objects.create(
                    company_config=instance,
                    use_type=use_type,
                    **config_email_data
                )
        
        return instance

    def update(self, instance, validated_data):
        config_emails_data = validated_data.pop('config_emails_data', None)
        use_types = CommunicationUseType.objects.all()
        if config_emails_data:
            previous_config_emails = instance.company_config_emails.all()
            new_config_emails = []
            for config_email_data in config_emails_data:
                use_type = use_types.filter(id=config_email_data.pop('use_type').get('value')).first()
                if config_email_data.get('id'):
                    config_email = previous_config_emails.filter(id=config_email_data.pop('id')).first()
                    config_email.use_type = use_type
                    config_email.mail_send_user = config_email_data.pop('mail_send_user')
                    config_email.mail_send_mail = config_email_data.pop('mail_send_mail')
                    config_email.is_default = config_email_data.pop('is_default')
                    config_email.save()
                    new_config_emails.append(config_email)
                else:
                    new_config_email = CompanyConfigEmail.objects.create(
                        company_config=instance,
                        use_type=use_type,
                        **config_email_data
                    )
                    new_config_emails.append(new_config_email)
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
