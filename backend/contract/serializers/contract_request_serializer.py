from django.db import transaction
from rest_framework import serializers
from billing.serializers.general_payment_serializer import GeneralPaymentSerializer
from claimrequest.models import VulnerabilityRequest
from contract.serializers.bonification_serializer import BonificationSerializer
from contract.serializers.contract_clause_serializer import ContractClauseSerializer
from contract.serializers.contract_request_representative_serializer import ContractRequestRepresentativeSerializer
from coredata.models import PersonCNAE, PersonContact
from coredata.serializers import PersonAddressSerializer, PersonCNAESerializer, PersonContactSerializer, PersonSerializer
from auth.serializers import UserMinimalSerializer
from documentmanager.serializers import DocumentSerializer
from documentmanager.utils.main_utils import upload_document
from logger.models import LogContractRequestStatus
from order.serializers.order_serializer import OrderSerializer
from order.serializers.value_objects_serializer import OrderTypeSerializer
from pricing.models import PriceRate
from pricing.serializers.price_rate_serializer import PriceRateSerializer
from service.models import SupplyPoint
from service.serializers.supply_point_serializer import SupplyPointContractsSerializer, SupplyPointMinimalSerializer
from .value_objects_serializer import BailTypeSerializer, ContractCategorySerializer, ContractClientTypeSerializer, ContractDebtManagementSerializer, ContractRepresentativeTypeSerializer, ContractRequestDocumentationSerializer, ContractRequestStatusSerializer, ContractUseTypeSerializer
from ..models import ContractPriceRate, ContractRequest, ContractRequestRepresentative, ContractRequestStatus, ContractRequestObservation, ContractTerminationRequest
from .variable_serializer import VariableSerializer
from .contract_request_type_serializer import ContractRequestTypeSerializer
from .contract_request_base_serializer import ContractRequestSerializer


class ContractRequestRepresentativeSerializer(serializers.ModelSerializer):
    person = PersonSerializer(required=False, allow_null=True)
    type = ContractRepresentativeTypeSerializer(required=False, allow_null=True)

    class Meta:
        model = ContractRequestRepresentative
        fields = '__all__'

class ContractRequestRepresentativeSaveSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContractRequestRepresentative
        fields = ['person', 'type']

class ContractRequestObservationSerializer(serializers.ModelSerializer):
    user = UserMinimalSerializer(required=False, allow_null=True)
    class Meta:
        model = ContractRequestObservation
        fields = '__all__'
    
    
class ContractRequestSaveSerializer(serializers.ModelSerializer):
    token = serializers.CharField(required=False, allow_blank=True)

    # Order Types separats per comes
    order_types = serializers.CharField(write_only=True, required=False, allow_null=True, allow_blank=True)

    # Bail Types separats per comes
    bail_types = serializers.CharField(write_only=True, required=False, allow_null=True, allow_blank=True)
    
    # Camps escrits
    representatives = ContractRequestRepresentativeSaveSerializer(many=True, required=False)
    observation = serializers.CharField(write_only=True, required=False, allow_null=True, allow_blank=True)
    
    cnaes_ids = serializers.PrimaryKeyRelatedField( many=True, queryset=PersonCNAE.objects.all(), required=False )
    price_rates_ids = serializers.ListField(write_only=True, required=False, allow_null=True)
    contract_termination_requests = serializers.ListField(write_only=True, required=False, allow_null=True)
    registration_price_rates_ids = serializers.ListField(child=serializers.IntegerField(), write_only=True, required=False, allow_null=True)
    supply_point_ids = serializers.ListField(child=serializers.IntegerField(), write_only=True, required=False, allow_null=True)
    sms_phones = serializers.ListField(child=serializers.IntegerField(), write_only=True, required=False, allow_null=True)
    # Afegeix el camp 'contacts'
    contacts = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=PersonContact.objects.all(),
        required=False
    )

    last_reading = serializers.FloatField(required=False, allow_null=True)
    last_leak_reading = serializers.FloatField(required=False, allow_null=True)
    last_reading_at = serializers.DateTimeField(required=False, allow_null=True)
    supply_point_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    meter_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    mandate_id = serializers.CharField(write_only=True, required=False, allow_null=True)
    
    class Meta:
        model = ContractRequest
        fields = '__all__'
    
    @transaction.atomic
    def create(self, validated_data):
        # Extraiem les dades de representants i contacts
        print("in create")
        representatives_data = validated_data.pop('representatives', [])
        contacts_data = validated_data.pop('contacts', [])
        observation = validated_data.pop('observation', None)
        order_types = validated_data.pop('order_types', None)
        bail_types = validated_data.pop('bail_types', None)
        price_rates_ids = validated_data.pop('price_rates_ids', None)
        registration_price_rates_ids = validated_data.pop('registration_price_rates_ids', None)
        supply_point_ids = validated_data.pop('supply_point_ids', None)

        last_reading = validated_data.pop('last_reading', None)
        last_leak_reading = validated_data.pop('last_leak_reading', None)
        last_reading_at = validated_data.pop('last_reading_at', None)
        reading_supply_point_id = validated_data.pop('supply_point_id', None)
        reading_meter_id = validated_data.pop('meter_id', None)
        
        # Assignem l'estat per defecte
        default_status = ContractRequestStatus.objects.filter(is_default=True).first()
        if default_status:
            validated_data['status'] = default_status
        
        # Creem l'objecte ContractRequest sense el camp 'contacts'
        obj = ContractRequest.objects.create(**validated_data)
        
        # Assignem els contacts utilitzant .set()
        if contacts_data:
            obj.contacts.set(contacts_data)

        # Order Types (ids separat per comes)
        if order_types is not None:
            print('order_types_create', order_types)
            order_type_ids = [int(id.strip()) for id in order_types.split(',') if id.strip().isdigit()]
        else:
            print('order_types_create', order_types)
            order_type_ids = []

        obj.order_types.set(order_type_ids)
        
        # Bail Types (bail_types ids separat per comes)
        if bail_types:
            bail_type_ids = [int(id.strip()) for id in bail_types.split(',') if id.strip().isdigit()]
            obj.bail_types.set(bail_type_ids)
        
        if price_rates_ids is not None:
            obj.price_rates.set(price_rates_ids)
        
        if registration_price_rates_ids is not None:
            obj.registration_price_rates.set(registration_price_rates_ids)
        
        if supply_point_ids is not None:
            obj.supply_points.set(supply_point_ids)

        # Canvi de nom: es preomplen les variables del contracte actiu anterior
        if obj.is_change_of_name:
            from contract.utils.contract_service import copy_change_of_name_variables
            copy_change_of_name_variables(obj)

        # Crear representants
        for representative_data in representatives_data:
            ContractRequestRepresentative.objects.create(contract_request=obj, **representative_data)
        
        if obj.type:
            contract_price_rates = []
            for price_rate in obj.type.price_rates.all():
                for supply_point in obj.supply_points.all():
                    try:
                        contract_price_rate, _ = ContractPriceRate.objects.get_or_create(
                            supply_point=supply_point,
                            price_rate=price_rate
                        )
                    except:
                        contract_price_rate = ContractPriceRate.objects.filter(
                            supply_point=supply_point,
                            price_rate=price_rate
                        ).first()
                    contract_price_rates.append(contract_price_rate)
            obj.price_rates.set(contract_price_rates)
            obj.registration_price_rates.set(obj.type.registration_price_rates.all())
            obj.order_types.set(obj.type.order_types.all())
        
        # Registrar canvis d'estat
        self.log_status_change(None, obj, observation)

        if last_reading is not None and last_reading_at:
            from billing.models import Reading
            reading_sp = SupplyPoint.objects.get(id=reading_supply_point_id or obj.supply_point_default_id)
            previous_reading = Reading.objects.filter(supply_point=reading_sp, reading_date__lt=last_reading_at).exclude(is_control=True).order_by('-reading_date').first()
            if reading_meter_id:
                previous_reading = Reading.objects.filter(supply_point=reading_sp, meter__id=reading_meter_id, reading_date__lt=last_reading_at).exclude(is_control=True).order_by('-reading_date').first()
            
            total_days = (last_reading_at.date() - previous_reading.reading_date).days if previous_reading else 0
            
            reading_data = {
                'token': f"{reading_sp.meter.code if reading_sp.meter else 'NOMETER'}/MANUAL",
                'reading_date': last_reading_at,
                'reading_value': last_reading,
                'leak_value': last_leak_reading,
                'origin': 'Manual',
                'calculated_value': float(last_reading) - float(previous_reading.reading_value) if previous_reading else float(last_reading),
                'supply_point': reading_sp,
                'meter': previous_reading.meter if previous_reading else reading_sp.meter,
                'previous_reading': previous_reading,
                'consumption_days': total_days,
                'contract_request': obj,
                'is_control': False,
                'is_estimated': False,
                'is_active': True,
                'is_initial': True,
                'is_close': True
            }
            reading = Reading.objects.create(**reading_data)
            
            # Link reading to associated termination requests
            for tr in obj.contract_termination_requests.all():
                tr.readings.add(reading)
                if obj.bill_cut_reading:
                    tr.bill_cut_reading = True
                    tr.save()

        return obj
    
    @transaction.atomic
    def update(self, instance, validated_data):
        # Verificar si 'representatives' i 'contacts' han estat enviats en les dades d'entrada
        representatives_present = 'representatives' in self.initial_data
        representatives_data = validated_data.pop('representatives', None)
        contacts_data = validated_data.pop('contacts', None)
        observation = validated_data.pop('observation', None)
        order_types = validated_data.pop('order_types', None)
        bail_types = validated_data.pop('bail_types', None)
        cnaes = validated_data.pop('cnaes_ids', None)
        sms_phones = validated_data.pop('sms_phones', None)
        person_contact_sms = validated_data.pop('person_contact_sms', None)
        contract_termination_requests = validated_data.pop('contract_termination_requests', None)
        print("contract_termination_requests", contract_termination_requests)

        last_reading = validated_data.pop('last_reading', None)
        last_leak_reading = validated_data.pop('last_leak_reading', None)
        last_reading_at = validated_data.pop('last_reading_at', None)
        reading_supply_point_id = validated_data.pop('supply_point_id', None)
        reading_meter_id = validated_data.pop('meter_id', None)
        mandate_id = validated_data.pop('mandate_id', None)
        if 'payment' in validated_data:
            print("payment found")
        
        if contract_termination_requests is not None:
            contract_termination_requests = ContractTerminationRequest.objects.filter(id__in=contract_termination_requests)
            instance.contract_termination_requests.add(*contract_termination_requests)
        
        if sms_phones is not None:
            # Convert IDs to PersonContact objects
            person_contacts = PersonContact.objects.filter(id__in=sms_phones)
            instance.person_contact_sms.set(person_contacts)
        
        if 'cnaes' in validated_data:
            cnaes = validated_data.pop('cnaes')
        price_rates_ids = validated_data.pop('price_rates_ids', None) if 'price_rates_ids' in validated_data else validated_data.pop('price_rates', None)
        registration_price_rates_ids = validated_data.pop('registration_price_rates_ids', None) if 'registration_price_rates_ids' in validated_data else validated_data.pop('registration_price_rates', None)
        supply_point_ids = validated_data.pop('supply_point_ids', None) if 'supply_point_ids' in validated_data else validated_data.pop('supply_points', None)

        previous_status = instance.status
        
        previous_holder = instance.holder
        
        # Important: Do not update person if it's None in the request data
        if 'person' in validated_data and validated_data['person'] is None:
            validated_data.pop('person')
        
        # Actualitzar camps de ContractRequest
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        
        # Assignar els contacts si estan presents
        if contacts_data is not None:
            instance.contacts.set(contacts_data)

        # Order Types (ids separat per comes)
        if order_types is not None:
            print('order_types', order_types)
            order_type_ids = [int(id.strip()) for id in order_types.split(',') if id.strip().isdigit()]
            print('order_type_ids', order_type_ids)
            instance.order_types.set(order_type_ids)
        elif order_types == "":
            print('order_types', order_types)
            order_type_ids = []
            print('order_type_ids', order_type_ids)
            instance.order_types.set(order_type_ids)

        

        # Bail Types (bail_types ids separat per comes)
        if bail_types is not None:
            bail_type_ids = [int(id.strip()) for id in bail_types.split(',') if id.strip().isdigit()]
            instance.bail_types.set(bail_type_ids)
        
        if price_rates_ids is not None:
            instance.price_rates.clear()
            use_general_price_rates = validated_data.get('use_general_price_rates', instance.use_general_price_rates)
            print("use_general_price_rates", use_general_price_rates)
            for price_rate in price_rates_ids:
                supply_point_id = price_rate.get('supply_point').get('id')
                price_rate_instance = PriceRate.objects.get(id=price_rate.get('price_rate').get('id'))
                supply_point_instance = SupplyPoint.objects.get(id=supply_point_id)
                try:
                    contract_price_rate, _ = ContractPriceRate.objects.get_or_create(
                        price_rate=price_rate_instance, 
                        supply_point=supply_point_instance
                    )
                except:
                    contract_price_rate = ContractPriceRate.objects.filter(
                        price_rate=price_rate_instance, 
                        supply_point=supply_point_instance
                    ).first()
                if use_general_price_rates:
                    if instance.supply_point_default_id == supply_point_id:
                        instance.price_rates.add(contract_price_rate)
                else:
                    instance.price_rates.add(contract_price_rate)
        
        
        if registration_price_rates_ids is not None:
            instance.registration_price_rates.set(registration_price_rates_ids)

        if supply_point_ids is not None:
            instance.supply_points.set(supply_point_ids)

        # if mandate_id is not None and mandate_id != "":
        #     if instance.payment:
        #         instance.payment.mandate_id = mandate_id
        #         instance.payment.save()

        if previous_holder != instance.holder:
            try:
                vulnerability_request = VulnerabilityRequest.objects.get(contract_request=instance)
                vulnerability_request.contract_request = None
                if vulnerability_request.person is None and vulnerability_request.contract is None:
                    vulnerability_request.delete()
                else:
                    vulnerability_request.save()
            except:
                pass

        # Gestionar representants
        if representatives_present:
            # Eliminar tots els representants existents
            instance.representatives.all().delete()
            # Crear nous representants si hi ha dades
            if representatives_data:
                for representative_data in representatives_data:
                    ContractRequestRepresentative.objects.create(contract_request=instance, **representative_data)
        
        if cnaes is not None:
            instance.cnaes.set(cnaes)
        
        if validated_data.get('contract_file'):
            instance.contract_file_template.delete()
        
        instance.save()
        
        # Registrar canvis d'estat
        self.log_status_change(previous_status, instance, observation)

        if last_reading is not None and last_reading_at:
            from billing.models import Reading
            reading_sp = SupplyPoint.objects.get(id=reading_supply_point_id or instance.supply_point_default_id)
            
            existing_reading = Reading.objects.filter(contract_request=instance, reading_date=last_reading_at).exclude(is_control=True).first()
            
            if existing_reading:
                existing_reading.reading_value = last_reading
                existing_reading.leak_value = last_leak_reading if last_leak_reading else 0
                existing_reading.calculated_value = float(last_reading) - float(existing_reading.previous_reading.reading_value) if existing_reading.previous_reading else float(last_reading)
                existing_reading.save()
            else:
                previous_reading = Reading.objects.filter(supply_point=reading_sp, reading_date__lt=last_reading_at).exclude(is_control=True).order_by('-reading_date').first()
                if reading_meter_id:
                    previous_reading = Reading.objects.filter(supply_point=reading_sp, meter__id=reading_meter_id, reading_date__lt=last_reading_at).exclude(is_control=True).order_by('-reading_date').first()
                
                total_days = (last_reading_at.date() - previous_reading.reading_date).days if previous_reading else 0
                
                reading_data = {
                    'token': f"{reading_sp.meter.code if reading_sp.meter else 'NOMETER'}/MANUAL",
                    'reading_date': last_reading_at,
                    'reading_value': last_reading,
                    'leak_value': last_leak_reading,
                    'origin': 'Manual',
                    'calculated_value': float(last_reading) - float(previous_reading.reading_value) if previous_reading else float(last_reading),
                    'supply_point': reading_sp,
                    'meter': previous_reading.meter if previous_reading else reading_sp.meter,
                    'previous_reading': previous_reading,
                    'consumption_days': total_days,
                    'contract_request': instance,
                    'is_control': False,
                    'is_estimated': False,
                    'is_active': True,
                    'is_initial': True,
                    'is_close': True
                }
                reading = Reading.objects.create(**reading_data)

                # Link reading to associated termination requests
                for tr in instance.contract_termination_requests.all():
                    tr.readings.add(reading)
                    if instance.bill_cut_reading:
                        tr.bill_cut_reading = True
                        tr.save()

        return instance
    
    def validate(self, data):
        if not self.instance and 'token' not in data:
            raise serializers.ValidationError({"token": "This field is required."})
        
        if data.get('observation') is None:
            if 'observation' in data:
                data.pop('observation')
        return data
    
    def log_status_change(self, previous_status, instance, observation=None):
        request = self.context.get('request')
        user = request.user if request else None
        
        if previous_status != instance.status:
            LogContractRequestStatus.objects.create(
                object=instance,
                previous_status=previous_status,
                current_status=instance.status,
                user=user,
                observation=observation
            )

class ContractRequestMinimalSerializer(serializers.ModelSerializer):
    status_name = serializers.CharField(source='status.name', read_only=True)
    status_color = serializers.CharField(source='status.color', read_only=True)
    holder_id = serializers.CharField(read_only=True, source='holder.id')
    owner_id = serializers.CharField(read_only=True, source='owner.id')
    tenant_id = serializers.CharField(read_only=True, source='tenant.id')
    class Meta:
        model = ContractRequest
        fields = ['id', 'token', 'approved_at', 'status_name', 'status_color', 'holder_id', 'owner_id', 'tenant_id']
        
class ContractRequestListSerializer(serializers.ModelSerializer):
    supply_point_default_token = serializers.CharField(source='supply_point_default.token', read_only=True)
    type_token = serializers.CharField(source='type.token', read_only=True)
    type_name = serializers.CharField(source='type.name', read_only=True)
    status_token = serializers.CharField(source='status.token', read_only=True)
    status_name = serializers.CharField(source='status.name', read_only=True)
    status_color = serializers.CharField(source='status.color', read_only=True)
    person_token = serializers.CharField(source='person.token', read_only=True)
    person_name = serializers.CharField(source='person.name', read_only=True)
    person_surname = serializers.CharField(source='person.surname', read_only=True)
    
    class Meta:
        model = ContractRequest
        fields = [
            'id',
            'token',
            'created_at',
            'supply_point_default_token',
            'type_token',
            'type_name',
            'status_token',
            'status_name',
            'status_color',
            'person_token',
            'person_name',
            'person_surname'
        ]
        
    def to_representation(self, instance):
        representation = super().to_representation(instance)
        
        if instance.holder:
            holder_name = instance.holder.name or ''
            holder_surname = instance.holder.surname or ''
            representation['holder_full_name'] = f"{holder_name} {holder_surname}".strip()
        else:
            representation['holder_full_name'] = ''
            
        try:
            supply_point = SupplyPoint.objects.filter(id = instance.supply_point_default_id).first()
            if supply_point:
                representation['supply_point'] = str(supply_point.address)
        except:
            print("supply_point not loaded")

        meters = []
        for supply_point in instance.supply_points.all():
            if supply_point.meter:
                meters.append(supply_point.meter.code)
        
        representation['meters'] = ", ".join(meters) if meters else ''
        
        return representation
