from django.conf import settings
from rest_framework import serializers
from django_filters import rest_framework as filters
from auth.serializers import UserMinimalSerializer
from billing.models import GeneralPayment
from contract.models import PaymentType
from coredata.models import ConfigProject, PersonBank, Street, StreetNumber, StreetNumberType
from coredata.serializers import PersonAddressSerializer, PersonMinimalSerializer, PersonSerializer, PersonMinimalAddressSerializer,StreetSerializer, StreetNumberSerializer, PostalCodeSerializer, CitySerializer
from service.serializers.DMA_serializer import DMASerializer
from service.serializers.company_serializer import CompanySerializer
from service.serializers.tank_serializer import TankSerializer
from ..models import ( CompanyBank, ConnectionRequest, ConnectionRequestObservation, ConnectionRequestStatus )
from .value_objects_serializer import ConnectionDiameterSerializer, ConnectionInstallationTypeSerializer, ConnectionMaterialSerializer, ConnectionRequestStatusSerializer, ConnectionTypeSerializer, ConnectionUseTypeSerializer, ConnectionValveTypeSerializer
from .connection_serializer import ConnectionSerializer

from urllib.parse import quote
from urllib.parse import urljoin


from logger.models import LogConnectionRequestStatus


class ConnectionRequestObservationSerializer(serializers.ModelSerializer):
    user = UserMinimalSerializer(required=False, allow_null=True)

    class Meta:
        model = ConnectionRequestObservation
        fields = '__all__'

class ConnectionRequestSerializer(serializers.ModelSerializer):
    connection = ConnectionSerializer(read_only=True, required=False, allow_null=True)
    person = PersonMinimalAddressSerializer(read_only=True, required=False, allow_null=True)
    company = CompanySerializer(read_only=True, required=False, allow_null=True)
    status = ConnectionRequestStatusSerializer(read_only=True, required=False, allow_null=True)
    address_street = StreetSerializer(read_only=True, required=False, allow_null=True)
    address_street_number = StreetNumberSerializer(read_only=True, required=False, allow_null=True)
    address_city = CitySerializer(read_only=True, required=False, allow_null=True)
    address_postal_code = PostalCodeSerializer(read_only=True, required=False, allow_null=True)
    
    type = ConnectionTypeSerializer(read_only=True, required=False, allow_null=True)
    installation_type = ConnectionInstallationTypeSerializer(read_only=True, required=False, allow_null=True)
    use_type = ConnectionUseTypeSerializer(read_only=True, required=False, allow_null=True)
    valve_type = ConnectionValveTypeSerializer(read_only=True, required=False, allow_null=True)
    diameter = ConnectionDiameterSerializer(read_only=True, required=False, allow_null=True)
    material = ConnectionMaterialSerializer(read_only=True, required=False, allow_null=True)
    tank = TankSerializer(read_only=True, required=False, allow_null=True)
    dma = DMASerializer(read_only=True, required=False, allow_null=True)
    address_billing = PersonAddressSerializer(read_only=True, required=False, allow_null=True)
    payment = serializers.SerializerMethodField()
    invoices = serializers.SerializerMethodField()
    
    class Meta:
        model = ConnectionRequest
        fields = '__all__'

    def get_invoices(self, obj):
        from billing.models import Invoice
        invoice_data = []
        invoices = Invoice.objects.filter(connection_request=obj)
        invoice_type_token = ConfigProject.objects.get(token='invoice_type_invoice_token').value
        for invoice in invoices:
            has_invoice = Invoice.objects.filter(budget_token=invoice.token, type__token=invoice_type_token).order_by('-created_at').first()
            invoice_data.append({
                'id': invoice.id,
                'token': invoice.token,
                'serie_final': invoice.serie_final,
                'title_final': invoice.title_final,
                'total_final': invoice.total_final,
                'status_name': invoice.status.name,
                'status_id': invoice.status.id,
                'status_token': invoice.status.token,
                'status_color': invoice.status.color,
                'type_token': invoice.type.token,
                'invoice_file_template': invoice.invoice_file_template is not None,
                'invoice_file': invoice.invoice_file.id if invoice.invoice_file else None,
                'budget_token': invoice.budget_token,
                'has_invoice': has_invoice is not None,
                'refactored_token': invoice.refactored_token
            })
        return invoice_data
    
    def to_representation(self, instance):
        representation = super().to_representation(instance)
        address_complete = ""
        if str(instance.address_street) and str(instance.address_street) != 'None':
            address_complete += str(instance.address_street)
        if str(instance.address_street_number) and str(instance.address_street_number) != 'None':
            address_complete += ", " + str(instance.address_street_number)
        representation['address_complete'] = address_complete

        if instance.blueprint:
            representation['blueprint'] = self.build_absolute_uri(instance.blueprint.url)
        return representation

    def build_absolute_uri(self, url):
        request = self.context.get('request')
        if request is not None:
            return request.build_absolute_uri(quote(url))
        return urljoin(settings.MEDIA_URL, quote(url))
    
    def get_payment(self, obj):
        from billing.serializers.general_payment_serializer import GeneralPaymentSerializer
        if obj.payment:
            return GeneralPaymentSerializer(obj.payment).data
        return None

class ConnectionRequestSaveSerializer(serializers.ModelSerializer):
    token = serializers.CharField(required=False, allow_blank=True)
    blueprint_delete = serializers.BooleanField(write_only=True, required=False, allow_null=True)

    # TODO: it could be a blank field
    observation = serializers.CharField(write_only=True, required=False, allow_null=True, allow_blank=True)
    payment = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    payment_type = serializers.IntegerField(write_only=True, required=False, allow_null=True)

    class Meta:
        model = ConnectionRequest
        fields = '__all__'

    def create(self, validated_data):
        # validated_data = self.parse_data(validated_data)
        # print(validated_data)
        
        
        if validated_data.get('blueprint_delete'):
            validated_data.pop('blueprint_delete')
        default_status = ConnectionRequestStatus.objects.get(is_default=True)
        if default_status:
            validated_data['status'] = default_status
        obj, _ = ConnectionRequest.objects.get_or_create(**validated_data)
        self.log_status_change(None, obj, validated_data.get('observation'))
        return obj

    def update(self, instance, validated_data):
        print("UPDATING CONNECTION REQUEST")
        print(validated_data)
        previous_status = instance.status
        company = validated_data.pop('company', None)
        person = validated_data.pop('person', None)
        payment = validated_data.pop('payment', None)
        payment_type = validated_data.pop('payment_type', None)
        
        if company and not person:
            validated_data['company'] = company
            validated_data['person'] = None
        elif person and not company:
            validated_data['person'] = person
            validated_data['company'] = None
        
        if payment:
            gen_pay = None
            gen_pay = GeneralPayment.objects.get(id=payment)
            print(gen_pay)
            validated_data['payment'] = gen_pay
        if payment_type and not payment:
            pay_type = PaymentType.objects.get(id=payment_type)
            pay_instance = GeneralPayment.objects.get_or_create(type=pay_type)[0]
            validated_data['payment'] = pay_instance
                
        
        # validated_data = self.parse_data(validated_data)
        if validated_data.get('blueprint_delete'):
            instance.blueprint.delete(save=False)
            instance.blueprint = None
            validated_data.pop('blueprint_delete')
            
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        self.log_status_change(previous_status, instance, validated_data.get('observation'))
        return instance

    def validate(self, data):
        if not self.instance and 'token' not in data:
            raise serializers.ValidationError({"token": "This field is required."})

        if data.get('blueprint_delete') == None:
            if 'blueprint_delete' in data:
                data.pop('blueprint_delete')
        
        if data.get('observation') == None:
            if 'observation' in data:
                data.pop('observation')

        print('validate data:')
        print(data)

        # data['address_street_number__number'] = data.get('address_street_number__number') or None
        # data['address_street_number__number_end'] = data.get('address_street_number__number_end') or None

        return data
    
    def log_status_change(self, previous_status, instance, observation=None):
        print("log_status_change")
        print(previous_status)
        print(instance.status)
        print(observation)

        request = self.context.get('request')
        user = request.user if request else None
        current_status = instance.status
        if previous_status != current_status:
            LogConnectionRequestStatus.objects.create(
                object=instance,
                previous_status=previous_status,
                current_status=current_status,
                user=user,
                observation=observation
            )

class ConnectionRequestListSerializer(serializers.ModelSerializer):
    status_token = serializers.CharField(source='status.token', read_only=True)
    status_name = serializers.CharField(source='status.name', read_only=True)
    status_color = serializers.CharField(source='status.color', read_only=True)
    connection_name = serializers.CharField(source='connection.name', read_only=True)
    connection_token = serializers.CharField(source='connection.token', read_only=True)
    street = serializers.CharField(source='address_street', read_only=True)
    street_number = serializers.CharField(source='address_street_number', read_only=True)
    exploitation_name = serializers.CharField(source='exploitation.name', read_only=True)
    exploitation_token = serializers.CharField(source='exploitation.token', read_only=True)
    person = PersonMinimalSerializer( read_only=True)
    company = serializers.SerializerMethodField()
    class Meta:
        model = ConnectionRequest
        fields = [
            'id',
            'token',
            'created_at',
            'status_token',
            'status_name',
            'status_color',
            'connection_name',
            'connection_token',
            'street',
            'street_number',
            'exploitation_name',
            'exploitation_token',
            'person',
            'company',
        ]
    
    def get_company(self, obj):
        if obj.company:
            return {
                'alias': obj.company.alias,
                'vat': obj.company.vat
            }
        return None