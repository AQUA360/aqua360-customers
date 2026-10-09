import datetime
from rest_framework import serializers
from django.core.exceptions import ObjectDoesNotExist
from auth.serializers import UserMinimalSerializer
from billing.models import CommitmentDeposit, CommitmentDepositStatus
from django.utils import timezone
from contract.models import Contract
from service.models import SupplyPoint
from django.db.models import Min
from .models import CallRegister, ConfigProject, Address, Person, PersonAddress, PersonContact, PersonPiggyBank, PersonPiggyBankMovement, PersonRecord, PostalCode, Country, Street, StreetNumber, StreetNumberType, StreetType, City, Province, PersonBank, PersonCNAE, CNAE, Bank, PersonDeliquency, PersonObservation, MainPermission, IdentificationType, ReturnReason
from django.apps import apps
from .street_types import resolve_street_type



class IdentificationTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = IdentificationType
        fields = '__all__'
class ConfigProjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = ConfigProject
        fields = ['token','name', 'value','file']
class CnaeSerializer(serializers.ModelSerializer):
    class Meta:
        model = CNAE
        fields = ['id','token','description']

class StreetTypeSerializer(serializers.ModelSerializer):
    abbreviation = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    
    class Meta:
        model = StreetType
        fields = ['abbreviation', 'name', 'id']

    def to_internal_value(self, data):
        # El catàleg de tipus de via és TANCAT (71 codis de l'ACA): es busca, mai es crea.
        if isinstance(data, StreetType):
            return data
        if not isinstance(data, dict):
            raise serializers.ValidationError("Tipus de via no vàlid.")

        resolved = resolve_street_type(data.get('abbreviation'), data.get('name'))
        if resolved is not None:
            return resolved

        # El client pot reenviar el tipus tal com el rep (id + abreviació antiga que ja no
        # resol). Si la fila existeix, es fa servir; si no, no se'n crea cap.
        street_type_id = data.get('id')
        if street_type_id not in (None, ""):
            try:
                return StreetType.objects.get(pk=street_type_id)
            except (StreetType.DoesNotExist, TypeError, ValueError):
                pass
        return None

    def run_validation(self, data=serializers.empty):
        (is_empty_value, data) = self.validate_empty_values(data)
        if is_empty_value:
            return data

        value = self.to_internal_value(data)
        if value is not None:
            return value

        # Tipus no reconegut: el carrer es guarda sense tipus. No es pot deixar
        # que Serializer.validate() retorni None: DRF ho afirma i la petició
        # acaba en 500 (POST /service/meter/). Al recurs arrel és un 400.
        if self.parent is None:
            raise serializers.ValidationError("Tipus de via no reconegut al catàleg.")
        return None

class StreetSerializer(serializers.ModelSerializer):
    type_abbreviation = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    type_name = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    type = StreetTypeSerializer(required=False, allow_null=True)
    street_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)

    class Meta:
        model = Street
        fields = '__all__'

    def to_internal_value(self, data):
        if isinstance(data, (int, str)) and str(data).isdigit():
            try:
                return Street.objects.get(id=int(data))
            except Street.DoesNotExist:
                raise serializers.ValidationError(f"Street with id {data} does not exist.")
        
        if isinstance(data, dict):
            data = data.copy()
            if 'city' in data and isinstance(data['city'], dict):
                data['city'] = data['city'].get('id') or data['city'].get('code') or data['city'].get('pk')
                
        return super().to_internal_value(data)

    def create(self, validated_data):
        type_data = validated_data.pop('type', None)

        if isinstance(type_data, StreetType):
            street_type = type_data
        elif isinstance(type_data, dict):
            street_type = resolve_street_type(
                type_data.get('abbreviation'), type_data.get('name')
            )
        else:
            street_type = None

        city = validated_data.get('city', None)

        # Normalitzem per evitar duplicats per espais o NULL vs ''
        street_name = validated_data.get('name', '').strip()
        street_name_2 = validated_data.get('name_2') or ''

        street, _ = Street.objects.get_or_create(
            name=street_name,
            name_2=street_name_2,
            city=city,
            type=street_type
        )
        return street

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation['type_abbreviation'] = instance.type.abbreviation if instance.type else None
        representation['type_name'] = instance.type.name if instance.type else None
        representation['city_name'] = instance.city.name if instance.city else None
        representation['city'] = CityMinimalSerializer(instance.city).data if instance.city else None
        return representation



class StreetNumberTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = StreetNumberType
        fields = '__all__'
    def to_internal_value(self, data):
        # Assumeix que `data` conté `abbreviation` i opcionalment `name`
        if isinstance(data, StreetNumberType):
            street_number_type = data
        elif isinstance(data, dict):
            street_number_type, _ = StreetNumberType.objects.get_or_create(
                type=data.get('type'),
                defaults={'description': data.get('description', data.get('type'))}
            )
        else:
            street_number_type, _ = StreetNumberType.objects.get_or_create(
                type=data,
                defaults={'description': data}
            )
        return street_number_type

class StreetNumberSerializer(serializers.ModelSerializer):
    number_type_type = serializers.CharField(required=False, allow_null=True, source='number_type.type')
    street_number_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)

    class Meta:
        model = StreetNumber
        fields = ['number', 'number_end', 'number_suffix', 'number_end_suffix', 'number_type_type', 'id', 'street_number_id']

    def to_internal_value(self, data):
        if isinstance(data, (int, str)) and str(data).isdigit():
            try:
                return StreetNumber.objects.get(id=int(data))
            except StreetNumber.DoesNotExist:
                raise serializers.ValidationError(f"StreetNumber with id {data} does not exist.")
        return super().to_internal_value(data)

    def to_representation(self, instance):
        rep = super().to_representation(instance)
        rep['number_type'] = StreetNumberTypeSerializer(instance.number_type).data if instance.number_type else None  # Include number type type in the output
        del rep['number_type_type']  # Remove number type type from the output
        return rep

    def create(self, validated_data):
        number_type_data = validated_data.pop('number_type', None)

        if isinstance(number_type_data, StreetNumberType):
            number_type = number_type_data
        elif isinstance(number_type_data, dict):
            number_type, _ = StreetNumberType.objects.get_or_create(
                type=number_type_data.get('type'),
                defaults={'description': number_type_data.get('description', number_type_data.get('type'))}
            )
        else:
            number_type = None

        number_suffix = validated_data.get('number_suffix') or ''
        number_end_suffix = validated_data.get('number_end_suffix') or ''

        street_number, _ = StreetNumber.objects.get_or_create(
            number_type=number_type,
            number=validated_data.get('number'),
            number_end=validated_data.get('number_end'),
            number_suffix=number_suffix,
            number_end_suffix=number_end_suffix,
            street=validated_data.get('street')
        )

        return street_number


class PostalCodeSerializer(serializers.ModelSerializer):
    class Meta:
        model = PostalCode
        fields = '__all__'

class CountrySerializer(serializers.ModelSerializer):
    class Meta:
        model = Country
        fields = '__all__'

    def to_internal_value(self, data):
        if isinstance(data, int):
            return data
        return super().to_internal_value(data)


class ProvinceSerializer(serializers.ModelSerializer):
    country = CountrySerializer(required=False, allow_null=True)
    class Meta:
        model = Province
        fields = '__all__'

class CitySerializer(serializers.ModelSerializer):
    postal_codes = PostalCodeSerializer(many=True, required=False, allow_null=True)
    province = ProvinceSerializer(required=False, allow_null=True)  # Acceptem el nom de la província com a string
    class Meta:
        model = City
        fields = '__all__'

class CityMinimalSerializer(serializers.ModelSerializer):
    class Meta:
        model = City
        fields = ['id', 'name', 'token']

class AddressSerializer(serializers.ModelSerializer):
    street = StreetSerializer(required=False, allow_null=True)
    street_number = StreetNumberSerializer(required=False, allow_null=True)
    city = serializers.CharField(write_only=True, required=False, allow_null=True)
    province = serializers.CharField(write_only=True, required=False, allow_null=True)
    country = serializers.IntegerField(write_only=True, required=False, allow_null=True)

    class Meta:
        model = Address
        fields = '__all__'

    def to_internal_value(self, data):
        if not isinstance(data, dict):
            return super().to_internal_value(data)
            
        mutable_data = data.copy()
        for field in ['city', 'province', 'country']:
            if field in mutable_data and isinstance(mutable_data[field], dict):
                mutable_data[field] = mutable_data[field].get('id') or mutable_data[field].get('code') or mutable_data[field].get('pk')
        
        return super().to_internal_value(mutable_data)

    def validate_city(self, value):
        initial_data = getattr(self, 'initial_data', {})
        if not isinstance(initial_data, dict):
            initial_data = {}

        country_id = initial_data.get('country')
        if isinstance(country_id, dict):
            country_id = country_id.get('id') or country_id.get('code') or country_id.get('pk')

        if not country_id and self.instance and self.instance.country:
             country_id = self.instance.country.id
             
        if country_id:
            try:
                country = Country.objects.get(id=country_id)
                if country.iso_code != 'ES':
                    return value
            except (Country.DoesNotExist, TypeError, ValueError):
                pass
        
        try:
            value = int(value)
            city, _ = City.objects.get_or_create(id=value)
            return city
        except (ValueError, TypeError):
            province_val = initial_data.get('province')
            province = self.validate_province(province_val) if province_val else None
            from coredata.utils.location_utils import resolve_city
            city = resolve_city(value, province)
            return city

    def validate_province(self, value):
        initial_data = getattr(self, 'initial_data', {})
        if not isinstance(initial_data, dict):
            initial_data = {}
            
        country_id = initial_data.get('country')
        if isinstance(country_id, dict):
            country_id = country_id.get('id') or country_id.get('code') or country_id.get('pk')

        if not country_id and self.instance and self.instance.country:
             country_id = self.instance.country.id

        if country_id:
            try:
                country = Country.objects.get(id=country_id)
                if country.iso_code != 'ES':
                    return value
            except (Country.DoesNotExist, TypeError, ValueError):
                pass

        try:
            value = int(value)
            province, _ = Province.objects.get_or_create(id=value)
            return province
        except (ValueError, TypeError):
            country = self.validate_country(country_id) if country_id else None
            province, _ = Province.objects.get_or_create(name=value, country = country)
            return province

    def validate_country(self, value):
        if value is None:
            return None
        if isinstance(value, dict):
            value = value.get('id') or value.get('code') or value.get('pk')
        try:
            country, _ = Country.objects.get_or_create(id=value)
            return country
        except (Country.DoesNotExist, TypeError, ValueError):
            return None

    def create(self, validated_data):
        street_data = validated_data.pop('street', None)
        street_number_data = validated_data.pop('street_number', None)

        street = None
        if isinstance(street_data, Street):
            street = street_data
        elif street_data:
            type_abbreviation = street_data.pop('type_abbreviation', None)
            type_name = street_data.pop('type_name', '')

            street_type = resolve_street_type(type_abbreviation, type_name)

            # Cerquem o creem el carrer. Mai no modifiquem un que ja existeixi.
            # Normalitzem per evitar duplicats per espais o NULL vs ''
            street_name = street_data.get('name', '').strip()
            street_name_2 = street_data.get('name_2') or ''

            try:
                street, created_street = Street.objects.get_or_create(
                    type=street_type,
                    name=street_name,
                    name_2=street_name_2,
                    city=validated_data.get('city')
                )
            except:
                street = Street.objects.filter(
                    type=street_type,
                    name=street_name,
                    name_2=street_name_2,
                    city=validated_data.get('city')
                ).first()

        street_number = None
        if isinstance(street_number_data, StreetNumber):
            street_number = street_number_data
        elif street_number_data:
            street_number_type_data = street_number_data.pop('number_type', None)
            number_type_type_data = street_number_type_data.pop('type') if street_number_type_data else None

            street_number_type = None
            if number_type_type_data:
                street_number_type, _ = StreetNumberType.objects.get_or_create(
                    type=number_type_type_data
                )

            # Cerquem o creem el número de carrer lligat al carrer. Mai no modifiquem un que ja existeixi.
            # Normalitzem sufixos per evitar duplicats per NULL vs ''
            number = street_number_data.get('number', None)
            number_end = street_number_data.get('number_end', None)
            number_suffix = street_number_data.get('number_suffix') or ''
            number_end_suffix = street_number_data.get('number_end_suffix') or ''

            try:
                street_number, created_sn = StreetNumber.objects.get_or_create(
                    street=street,
                    number_type=street_number_type,
                    number = number,
                    number_end = number_end,
                    number_suffix = number_suffix,
                    number_end_suffix = number_end_suffix
                )
            except:
                street_number = StreetNumber.objects.filter(
                    street=street,
                    number_type=street_number_type,
                    number = number,
                    number_end = number_end,
                    number_suffix = number_suffix,
                    number_end_suffix = number_end_suffix
                ).first()
        
        city_input = validated_data.pop('city', None)
        province_input = validated_data.pop('province', None)
        
        if isinstance(city_input, City):
            validated_data['city'] = city_input
            validated_data['city_name'] = None
        else:
            validated_data['city'] = None
            validated_data['city_name'] = city_input
            
        if isinstance(province_input, Province):
            validated_data['province'] = province_input
            validated_data['province_name'] = None
        else:
            validated_data['province'] = None
            validated_data['province_name'] = province_input

        try:
            address, created = Address.objects.get_or_create(
                street=street,
                street_number=street_number,
                **validated_data
            )
        except:
            address = Address.objects.filter(
                street=street,
                street_number=street_number,
                **validated_data
            ).first()

        return address

    def update(self, instance, validated_data):
        street_data = validated_data.pop('street', None)
        street_number_data = validated_data.pop('street_number', None)

        if street_data:
            if isinstance(street_data, Street):
                instance.street = street_data
            else:
                type_abbreviation = street_data.pop('type_abbreviation', None)
                type_name = street_data.pop('type_name', '')

                street_type = resolve_street_type(type_abbreviation, type_name)

                # Cerquem o creem el carrer. Mai no modifiquem un que ja existeixi.
                # Normalitzem per evitar duplicats per espais o NULL vs ''
                street_name = street_data.get('name', '').strip()
                street_name_2 = street_data.get('name_2') or ''

                try:
                    street, created_street = Street.objects.get_or_create(
                        type=street_type,
                        name=street_name,
                        name_2=street_name_2,
                        city=validated_data.get('city')
                    )
                except:
                    street = Street.objects.filter(
                        type=street_type,
                        name=street_name,
                        name_2=street_name_2,
                        city=validated_data.get('city')
                    ).first()
                instance.street = street

        if street_number_data:
            if isinstance(street_number_data, StreetNumber):
                instance.street_number = street_number_data
            else:
                street_number_type_data = street_number_data.pop('number_type', None)
                number_type_type_data = street_number_type_data.pop('type') if street_number_type_data else None

                street_number_type = None
                if number_type_type_data:
                    street_number_type, _ = StreetNumberType.objects.get_or_create(
                        type=number_type_type_data
                    )

                # Cerquem o creem el número de carrer lligat al carrer. Mai no modifiquem un que ja existeixi.
                # Normalitzem sufixos per evitar duplicats per NULL vs ''
                number = street_number_data.get('number', None)
                number_end = street_number_data.get('number_end', None)
                number_suffix = street_number_data.get('number_suffix') or ''
                number_end_suffix = street_number_data.get('number_end_suffix') or ''

                try:
                    street_number, created_sn = StreetNumber.objects.get_or_create(
                        street=instance.street,
                        number_type=street_number_type,
                        number = number,
                        number_end = number_end,
                        number_suffix = number_suffix,
                        number_end_suffix = number_end_suffix
                    )
                except:
                    street_number = StreetNumber.objects.filter(
                        street=instance.street,
                        number_type=street_number_type,
                        number = number,
                        number_end = number_end,
                        number_suffix = number_suffix,
                        number_end_suffix = number_end_suffix
                    ).first()
                instance.street_number = street_number
        
        city_input = validated_data.pop('city', None)
        province_input = validated_data.pop('province', None)

        if city_input is not None:
            if isinstance(city_input, City):
                instance.city = city_input
                instance.city_name = None
            else:
                instance.city = None
                instance.city_name = city_input
        
        if province_input is not None:
            if isinstance(province_input, Province):
                instance.province = province_input
                instance.province_name = None
            else:
                instance.province = None
                instance.province_name = province_input

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        instance.save()
        return instance

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation['address_complete'] = str(instance)
        
        """ representation['street_name'] = instance.street.name if instance.street else None
        representation['street_type'] = instance.street.type.id if instance.street and instance.street.type else None
        representation['street_type_name'] = instance.street.type.name if instance.street and instance.street.type else None """
        representation['street_complete'] = str(instance.street)
        representation['name'] = str(instance)

        representation['city'] = CitySerializer(instance.city).data
        representation['province'] = ProvinceSerializer(instance.province).data
        representation['country'] = CountrySerializer(instance.country).data
        return representation

class AddressSerializerReduced(serializers.ModelSerializer):
    street = StreetSerializer(required=False, allow_null=True)
    street_number = StreetNumberSerializer(required=False, allow_null=True)

    class Meta:
        model = Address
        fields = '__all__'

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation['address_complete'] = str(instance)
        
        representation['street_name'] = instance.street.name if instance.street else None
        representation['street_type'] = instance.street.type.id if instance.street and instance.street.type else None
        representation['street_type_name'] = instance.street.type.name if instance.street and instance.street.type else None
        
        # Eliminats els sobre-escrits manuals que trencaven la representació de street_number com a objecte
        # representation['street_number'] = instance.street_number.number if instance.street_number else None
        # representation['street_number_end'] = instance.street_number.number_end if instance.street_number else None
        # ...
        
        representation['street_complete'] = str(instance.street)
        representation['name'] = str(instance)

        representation['city_name'] = instance.city.name if instance.city else instance.city_name
        representation['province_name'] = instance.province.name if instance.province else instance.province_name
        return representation
    

class AddressMinimalSerializer(serializers.ModelSerializer):
    class Meta:
        model = Address
        fields = ['id', 'postal_code', 'city', 'city_name', 'province', 'province_name', 'country']


class CallRegisterSerializer(serializers.ModelSerializer):
    user = UserMinimalSerializer(read_only=True, required=False, allow_null=True)
    class Meta:
        model = CallRegister
        fields = '__all__'
    
    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation['contract_token'] = instance.contract.token if instance.contract else None
        representation['person_name'] = str(instance.person_contact.person)
        representation['person_token'] = instance.person_contact.person.token
        representation['phone'] = instance.person_contact.phone
        return representation
    
    def create(self, validated_data):
        user = self.context['request'].user
        validated_data['user'] = user
        return super().create(validated_data)

class PersonAddressSerializer(serializers.ModelSerializer):
    person = serializers.IntegerField(write_only=True)
    address = serializers.IntegerField(write_only=True)
    id = serializers.IntegerField(required=False, allow_null=True)
    class Meta:
        model = PersonAddress
        fields = '__all__'

    def to_internal_value(self, data):
        print("data", data)
        mutable_data = data.copy()
        address_input = mutable_data.pop('address', None) or mutable_data.pop('address_id', None)
        
        if address_input:
            if isinstance(address_input, dict):
                # addr_serializer = AddressSerializer(data=address_input)
                # addr_serializer.is_valid(raise_exception=True)
                # address_obj = addr_serializer.save()
                # SERIALIZER VALIDATION NOT NEEDED HERE
                mutable_data['address'] = address_input['id']
            else:
                mutable_data['address'] = address_input
                
        return super().to_internal_value(mutable_data)

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        try:
            representation['address'] = AddressSerializerReduced(instance.address).data
        except:
            representation['address'] = None

        try:
            address_complete = str(instance.address)
            representation['simple_address_complete'] = address_complete
            if instance.attention_to:
                address_complete = f"{address_complete} - Att.: {instance.attention_to}"
            representation['address_complete'] = address_complete
        except:
            representation['address_complete'] = None
            representation['simple_address_complete'] = None
        
        return representation

    def validate_address(self, value):
        if isinstance(value, Address):
            return value
        try:
            address = Address.objects.get(id=value)
            return address
        except ObjectDoesNotExist:
            raise serializers.ValidationError(f"Address with id {value} does not exist.")

    def validate_person(self, value):
        if isinstance(value, Person):
            return value
        try:
            person = Person.objects.get(id=value)
            return person
        except ObjectDoesNotExist:
            raise serializers.ValidationError(f"Person with id {value} does not exist.")
    
    def create(self, validated_data):
        person = validated_data.pop('person')
        address = validated_data.pop('address')

        person_address = PersonAddress.objects.create(person=person, address=address, **validated_data)
        return person_address
       

class PersonAddressMinimalSerializer(serializers.ModelSerializer):
    #address = serializers.IntegerField(write_only=True)
    person = serializers.IntegerField(write_only=True)

    class Meta:
        model = PersonAddress
        fields = '__all__'
    
    def to_internal_value(self, data):
        mutable_data = data.copy()
        if 'address_id' in mutable_data and mutable_data['address_id'] is not None:
            mutable_data['address'] = mutable_data.pop('address_id')
        return super().to_internal_value(mutable_data)

    def to_representation(self, instance):
        representation = super().to_representation(instance)

        try:
            address_complete = str(instance.address)
            representation['simple_address_complete'] = address_complete
            if instance.attention_to:
                address_complete = f"{address_complete} - Att.: {instance.attention_to}"
            representation['address_complete'] = address_complete
        except:
            representation['address_complete'] = None
            representation['simple_address_complete'] = None
        
        return representation

class PersonAddressSaveSerializer(serializers.ModelSerializer):
    class Meta:
        model = PersonAddress
        fields = '__all__'
    

class PersonContactSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(required=False, allow_null=True)
    class Meta:
        model = PersonContact
        fields = '__all__'
    
    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation['person_full_name'] = str(instance.person) if instance.person else None
        representation['person_token'] = instance.person.token if instance.person else None
        return representation

class PersonContactSaveSerializer(serializers.ModelSerializer):
    class Meta:
        model = PersonContact
        fields = '__all__'


class BankSerializer(serializers.ModelSerializer):
    class Meta:
        model = Bank
        fields = '__all__'

    def to_internal_value(self, data):
        if isinstance(data, int):
            return data
        return super().to_internal_value(data)


class PersonCommunicationSerializer(serializers.ModelSerializer):
    
    address = serializers.SerializerMethodField()
    sms_phone = serializers.SerializerMethodField()
    email = serializers.SerializerMethodField()
    full_name = serializers.SerializerMethodField()
    invoices = serializers.SerializerMethodField()
    contracts = serializers.SerializerMethodField()
    readings = serializers.SerializerMethodField()
    electronic_invoice = serializers.SerializerMethodField()
    electronic_invoice_data = serializers.SerializerMethodField()
    com_type = serializers.SerializerMethodField()
    
    class Meta:
        model = Person
        fields = [
            'id', 'token', 'name', 
            'surname', 'address', 'sms_phone', 'email', 
            'full_name', 'is_juridic', 'vulnerability_level', 
            'invoices', 'com_type', 'contracts', 
            'electronic_invoice', 'electronic_invoice_data',
            'readings'
        ]
    
    def get_contracts(self, instance):
        return instance.contract_ids if instance.contract_ids else []
    
    def get_readings(self, instance):
        if instance.reading_ids:
            from billing.models import Reading
            readings = Reading.objects.filter(id__in=instance.reading_ids)
            return [{
                'id': reading.id,
                'reading_date': reading.reading_date,
                'reading_value': reading.reading_value,
                'leak_value': reading.leak_value,
                'meter_code': reading.meter.code if reading.meter else None,
                'calculated_value': reading.calculated_value,
                'previous_reading_value': reading.previous_reading.reading_value if reading.previous_reading else None,
                'previous_reading_date': reading.previous_reading.reading_date if reading.previous_reading else None,
            } for reading in readings]
        return []
    
    def get_com_type(self, instance):
        if instance.contract_ids:
            contract = Contract.objects.get(id=instance.contract_ids[0])
            return contract.communication_type
        return None
    
    def get_electronic_invoice(self, instance):
        if instance.contract_ids:
            contract = Contract.objects.get(id=instance.contract_ids[0])
            return True if contract.payment and contract.payment.accounting_office else False
        return False
    
    def get_electronic_invoice_data(self, instance):
        if instance.contract_ids and instance.invoice_ids:
            contract = Contract.objects.get(id=instance.contract_ids[0])
            return {
                'accounting_office': contract.payment.accounting_office,
                'managing_body': contract.payment.managing_body,
                'processing_unit': contract.payment.processing_unit,
            } if contract.payment and contract.payment.accounting_office else None
        return None
    
    def get_full_name(self, instance):
        if instance.surname:
            return f"{instance.name} {instance.surname}"
        return instance.name
    
    def get_sms_phone(self, instance):
        if instance.contract_ids and len(instance.contract_ids) > 0:
            phones = instance.contacts.filter(is_active=True, contract_contact_sms__id__in=instance.contract_ids).values_list('phone', flat=True).distinct()
        else:
            phones = instance.contacts.filter(is_active=True).values_list('phone', flat=True).distinct()
        if phones:
            return ','.join(phones)
        else:
            return None
    
    def get_address(self, instance):
        if instance.contract_ids and len(instance.contract_ids) > 0:
            addresses = instance.addresses.filter(is_active=True, contracts_contact__id__in=instance.contract_ids).distinct()
        else:
            addresses = instance.addresses.filter(is_active=True).distinct()
        if addresses:
            return str(addresses[0].address)
        else:
            return None
    
    def get_email(self, instance):
        if instance.contract_ids and len(instance.contract_ids) > 0:
            emails = instance.contacts.filter(is_active=True, contract_contact_email__id__in=instance.contract_ids).values_list('email', flat=True).distinct()
        else:
            emails = instance.contacts.filter(is_active=True).values_list('email', flat=True).distinct()
        if emails:
            return emails[0]
        else:
            return None
    
    def get_invoices(self, instance):
        if instance.invoice_ids:
            from billing.models import Invoice
            invoices = Invoice.objects.filter(id__in=instance.invoice_ids)
            return [{
                'id': invoice.id,
                'serie_final': invoice.serie_final,
                'issue_date': invoice.issue_date,
                'consumption': invoice.consumption,
                'total': invoice.total_final,
            } for invoice in invoices]
        return []

class PersonBankSaveSerializer(serializers.ModelSerializer):
    class Meta:
        model = PersonBank
        fields = '__all__'
    
    def to_internal_value(self, data):
        mutable_data = data.copy()
        if 'country' in mutable_data and isinstance(mutable_data['country'], dict):
            mutable_data['country'] = mutable_data['country'].get('id')
        
        if 'bank' in mutable_data and isinstance(mutable_data['bank'], dict):
            mutable_data['bank'] = mutable_data['bank'].get('id')

        return super().to_internal_value(mutable_data)

    def update(self, instance, validated_data):
        if validated_data.get('is_default'):
            instance.person.banks.exclude(pk=instance.pk).filter(is_default=True).update(is_default=False)

        is_active = validated_data.get('is_active', None)
        if is_active != None and not is_active:
            validated_data['deactivated_at'] = timezone.now()
            validated_data['is_default'] = False
            person = instance.person
            try:
                new_bank = person.banks.filter(is_default=False).first()
                new_bank.is_default = True
                new_bank.save()
            except:
                pass
        return super().update(instance, validated_data)
    

class CNAESerializer(serializers.ModelSerializer):
    class Meta:
        model = CNAE
        fields = '__all__'

class PersonCNAESerializer(serializers.ModelSerializer):
    class Meta:
        model = PersonCNAE
        fields = '__all__'

    def to_internal_value(self, data):
        mutable_data = data.copy()
        if 'cnae' in mutable_data and isinstance(mutable_data['cnae'], dict):
            mutable_data['cnae'] = mutable_data['cnae'].get('id')
        return super().to_internal_value(mutable_data)

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation['cnae'] = CNAESerializer(instance.cnae).data
        return representation

class PersonCNAESaveSerializer(serializers.ModelSerializer):
    class Meta:
        model = PersonCNAE
        fields = '__all__'

    def to_internal_value(self, data):
        mutable_data = data.copy()
        if 'cnae' in mutable_data and isinstance(mutable_data['cnae'], dict):
            mutable_data['cnae'] = mutable_data['cnae'].get('id')
        return super().to_internal_value(mutable_data)

class PersonDeliquencySerializer(serializers.ModelSerializer):
    class Meta:
        model = PersonDeliquency
        fields = '__all__'
 

class PersonBankMinimalSerializer(serializers.ModelSerializer):
    iban = serializers.ReadOnlyField()
    bank = BankSerializer(required=False, allow_null=True)
    
    iban_save = serializers.CharField(write_only=True, required=False, allow_null=True) 
    id_save = serializers.IntegerField(write_only=True, required=False, allow_null=True)  #for some reason when saving person, this value are not in validated data
    class Meta:
        model = PersonBank
        fields = '__all__'

    def to_internal_value(self, data):
        mutable_data = data.copy()
        if 'country' in mutable_data and isinstance(mutable_data['country'], dict):
            mutable_data['country'] = mutable_data['country'].get('id')
        
        if 'bank' in mutable_data and isinstance(mutable_data['bank'], dict):
            mutable_data['bank'] = mutable_data['bank'].get('id')

        return super().to_internal_value(mutable_data)


class PersonObservationSerializer(serializers.ModelSerializer):
    user = UserMinimalSerializer(required=False, allow_null=True)
    class Meta:
        model = PersonObservation
        fields = '__all__'

class PersonPiggyBankMovementSerializer(serializers.ModelSerializer):
    payment = serializers.SerializerMethodField()
    user = UserMinimalSerializer(read_only=True, required=False, allow_null=True)
    class Meta:
        model = PersonPiggyBankMovement
        fields = '__all__'
    
    def get_payment(self, obj):
        from billing.serializers.payment_serializer import PaymentMinimalSerializer
        if obj.payment:
            return PaymentMinimalSerializer(obj.payment).data
        return None

class PersonPiggyBankSerializer(serializers.ModelSerializer):
    class Meta:
        model = PersonPiggyBank
        fields = '__all__'
    
    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation['movements'] = PersonPiggyBankMovementSerializer(instance.person_movements.all().order_by('-movement_date', '-created_at'), many=True).data
        person = instance.person.first()
        representation['person'] = PersonMinimalContractSerializer(person).data if person else None
        return representation

class PersonRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = PersonRecord
        fields = '__all__'

class PersonSerializer(serializers.ModelSerializer):
    addresses = PersonAddressSerializer(many=True, required=False, allow_null=True)
    contacts = PersonContactSerializer(many=True, required=False, allow_null=True)
    banks = PersonBankMinimalSerializer(many=True, required=False, allow_null=True)
    identification_type = IdentificationTypeSerializer(read_only=True, required=False, allow_null=True)
    cnaes = PersonCNAESerializer(many=True, required=False, allow_null=True)
    deliquency = PersonDeliquencySerializer(required=False, allow_null=True)
    piggy_banks_count = serializers.SerializerMethodField()
    piggy_bank = serializers.SerializerMethodField()
    # contracts_related = serializers.SerializerMethodField()
    total_communications = serializers.SerializerMethodField()
    important_observations = serializers.SerializerMethodField()
    records = PersonRecordSerializer(many=True, required=False, allow_null=True)
    current_record = serializers.SerializerMethodField()

    addresses_count = serializers.SerializerMethodField()
    contacts_count = serializers.SerializerMethodField()
    banks_count = serializers.SerializerMethodField()
    cnaes_count = serializers.SerializerMethodField()
    contracts_holder_count = serializers.SerializerMethodField()
    contracts_owner_count = serializers.SerializerMethodField()
    contracts_tenant_count = serializers.SerializerMethodField()
    observations_count = serializers.SerializerMethodField()
    call_register_count = serializers.SerializerMethodField()
    communications_count = serializers.SerializerMethodField()
    
    identification_type_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    e_records = serializers.ListField(child=serializers.DictField(), required=False, allow_null=True)
    class Meta:
        model = Person
        fields = '__all__'
    
    def get_piggy_bank(self, instance):
        if instance.piggy_bank:
            return {
                'id': instance.piggy_bank.id,
                'token': instance.piggy_bank.token,
                'amount': instance.piggy_bank.amount,
            }
        return None
    
    def get_current_record(self, instance):
        current_year = timezone.now().year
        return instance.records.filter(year=current_year).first().e_record if instance.records.filter(year=current_year).first() else None
    
    def get_piggy_banks_count(self, instance):
        return instance.piggy_banks.count()
    
    def get_important_observations(self, instance):
        return PersonObservationSerializer(instance.observations.filter(is_important=True, is_active=True), many=True, context=self.context).data
    
    def get_total_communications(self, instance):
        return instance.communications.count()
    
    def get_addresses_count(self, instance):
        return instance.addresses.filter(is_active=True).values('address__id').distinct().count()
        
    def get_contacts_count(self, instance):
        return instance.contacts.filter(is_active=True).count()
        
    def get_banks_count(self, instance):
        return instance.banks.filter(is_active=True).count()
        
    def get_cnaes_count(self, instance):
        return instance.cnaes.count()
        
    def get_contracts_holder_count(self, instance):
        return instance.contracts_holder.filter(is_active=True).count()

    def get_contracts_owner_count(self, instance):
        # Excloure contractes on ja és holder
        return instance.contracts_owner.filter(is_active=True).exclude(
            holder=instance
        ).count()

    def get_contracts_tenant_count(self, instance):
        return instance.contracts_tenant.filter(is_active=True).exclude(
            holder=instance
        ).exclude(
            owner=instance
        ).count()
    
    def get_observations_count(self, instance):
        return instance.observations.filter(is_active=True).count()
        
    def get_call_register_count(self, instance):
        return CallRegister.objects.filter(person_contact__person=instance).count()
        
    def get_communications_count(self, instance):
        return instance.communications.filter(is_active=True).count()
    
    """ def get_banks(self, obj):
        return PersonBankSerializer(obj.banks.all(), many=True).data
    """
    
    def get_contracts_related(self, instance):
        return { 'contracts': [], 'total': 0 }
        from contract.models import Contract
        from contract.serializers.contract_serializer import ContractListSerializer
        contracts_contact = Contract.objects.filter(contacts__person=instance)
        contracts_sms = Contract.objects.filter(person_contact_sms__person=instance)
        contracts_email = Contract.objects.filter(person_contact_email__person=instance)
        
        contracts_contact_ids = set(contracts_contact.values_list('id', flat=True))
        contracts_sms_ids = set(contracts_sms.values_list('id', flat=True))
        contracts_email_ids = set(contracts_email.values_list('id', flat=True))
        all_contract_ids = contracts_contact_ids | contracts_sms_ids | contracts_email_ids
        
        all_contracts = Contract.objects.filter(id__in=all_contract_ids)
        
        contracts_data = ContractListSerializer(all_contracts, many=True, context=self.context).data
        for contract_data in contracts_data:
            contract_id = contract_data['id']
            extra_info = []
            
            if contract_id in contracts_contact_ids:
                extra_info.append('contact')
            if contract_id in contracts_sms_ids:
                extra_info.append('sms')
            if contract_id in contracts_email_ids:
                extra_info.append('email')
            
            contract_data['extra_info'] = extra_info
        
        contract_data = {
            'contracts': contracts_data,
            'total': len(all_contract_ids)
        }
        return contract_data
    
    def create(self, validated_data):
        print("\n\ncreating person")
        print(validated_data)
        addresses_data = validated_data.pop('addresses') if 'addresses' in validated_data else []
        contacts_data = validated_data.pop('contacts') if 'contacts' in validated_data else []
        banks_data = validated_data.pop('banks') if 'banks' in validated_data else []
        cnaes_data = validated_data.pop('cnaes') if 'cnaes' in validated_data else []
        
        e_records = validated_data.pop('e_records') if 'e_records' in validated_data else []
        
        
        
        token = validated_data.get('token')
        
        if Person.objects.filter(token=token).exists() and token != '' and token != '99999999R':
            raise serializers.ValidationError({"token": "TOKEN_ALREADY_EXISTS"})
        
        person = Person.objects.create(**validated_data)
        
        if addresses_data and len(addresses_data) > 0:
            for ap in addresses_data:
                ap['person'] = person
                address_person = PersonAddress.objects.create(**ap)
                person.addresses.add(address_person)
        
        if contacts_data and len(contacts_data) > 0:
            for c in contacts_data:
                c['person'] = person
                contact_person = PersonContact.objects.create(**c)
                person.contacts.add(contact_person)
        
        if banks_data and len(banks_data) > 0:
            for b in banks_data:
                b['person'] = person
                print("b")
                print(b)
                bank_person = PersonBank.objects.create(**b)
                person.banks.add(bank_person)
        
        if cnaes_data and len(cnaes_data) > 0:
            for c in cnaes_data:
                c['person'] = person
                cnae_person = PersonCNAE.objects.create(**c)
                person.cnaes.add(cnae_person)
        
        if e_records and len(e_records) > 0:
            for e in e_records:
                year = e.get('year')
                record = person.records.filter(year=year).first()
                if record:
                    record.e_record = e.get('e_record')
                    record.save()
                else:
                    record = PersonRecord.objects.create(
                        person=person,
                        year=year,
                        e_record=e.get('e_record')
                    )
                    person.records.add(record)
        
        person.save()
        
        if not person.piggy_bank:
            piggy_bank = PersonPiggyBank.objects.create(
                amount=0,
                token=person.token,
                is_active=True
            )
            person.piggy_bank = piggy_bank
            person.save()
            
        return person
    
    def update(self, instance, validated_data):
        print("updating person")
        
        # Only process these if they are present in the update payload
        has_addresses = 'addresses' in validated_data
        addresses_data = validated_data.pop('addresses') if has_addresses else []
        
        has_contacts = 'contacts' in validated_data
        contacts_data = validated_data.pop('contacts') if has_contacts else []
        
        has_banks = 'banks' in validated_data
        banks_data = validated_data.pop('banks') if has_banks else []
        
        has_cnaes = 'cnaes' in validated_data
        cnaes_data = validated_data.pop('cnaes') if has_cnaes else []
        
        e_records = validated_data.pop('e_records') if 'e_records' in validated_data else []
        
        if e_records and len(e_records) > 0:
            for e in e_records:
                year = e.get('year')
                record = instance.records.filter(year=year).first()
                if record:
                    record.e_record = e.get('e_record')
                    record.save()
                else:
                    record = PersonRecord.objects.create(
                        person=instance,
                        year=year,
                        e_record=e.get('e_record')
                    )
                    instance.records.add(record)
        
        if 'identification_type_id' in validated_data:
            id_type_id = validated_data.pop('identification_type_id')
            instance.identification_type = IdentificationType.objects.get(id=id_type_id) if id_type_id else None
        
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        if has_addresses:
            instance.addresses.clear()
            if addresses_data and len(addresses_data) > 0:
                for ap in addresses_data:
                    ap['person'] = instance
                    if 'id' in ap and ap['id']!= None:
                        address_person = PersonAddress.objects.get(id=ap['id'])
                        for attr, value in ap.items():
                            setattr(address_person, attr, value)
                        address_person.person = instance
                        address_person.save()
                    else:
                        address_person = PersonAddress.objects.create(**ap)
                    instance.addresses.add(address_person)
        
        if has_contacts:
            previous_contacts = list(instance.contacts.filter(is_active=True))
            instance.contacts.clear()
            if contacts_data and len(contacts_data) > 0:
                for c in contacts_data:
                    c['person'] = instance
                    if 'id' in c and c['id']!=None:
                        contact_person = PersonContact.objects.get(id=c['id'])
                        for attr, value in c.items():
                            setattr(contact_person, attr, value)
                        contact_person.person = instance
                        contact_person.save()
                    else:
                        contact_person = PersonContact.objects.create(**c)
                    instance.contacts.add(contact_person)

            current_contacts = instance.contacts.filter(is_active=True)
            current_contact_ids = set(current_contacts.values_list('id', flat=True))
            for contact in previous_contacts:
                if contact.email and contact.email.strip():
                    is_removed = False
                    if contact.id not in current_contact_ids:
                        is_removed = True
                    else:
                        updated_contact = current_contacts.get(id=contact.id)
                        if not updated_contact.email or not updated_contact.email.strip():
                            is_removed = True
                    if is_removed:
                        from contract.models import Contract
                        contracts = Contract.objects.filter(person_contact_email=contact)
                        for contract in contracts:
                            contract.person_contact_email = None
                            if contract.communication_type != 'NONE':
                                contract.communication_type = 'PAPER'
                            contract.save()
        
        if has_banks:
            instance.banks.clear()
            if banks_data and len(banks_data) > 0:
                for b in banks_data:
                    b['person'] = instance
                    
                    if 'iban_save' in b:
                        b['iban'] = b.pop('iban_save')

                    bank_person = None

                    if b.get('id_save'):
                        bank_person = PersonBank.objects.filter(id=b['id_save']).first()

                    if bank_person:
                        for attr, value in b.items():
                            setattr(bank_person, attr, value)
                        bank_person.person = instance
                        bank_person.save()
                    else:
                        b.pop('id_save', None)
                        bank_person = PersonBank.objects.create(**b)
                    instance.banks.add(bank_person)
            
        if has_cnaes:
            instance.cnaes.clear()
            if cnaes_data and len(cnaes_data) > 0:
                for c in cnaes_data:
                    c['person'] = instance
                    if 'id' in c:
                        cnae_person = PersonCNAE.objects.get(id=c['id'])
                        for attr, value in c.items():
                            setattr(cnae_person, attr, value)
                        cnae_person.person = instance
                        cnae_person.save()
                    else:
                        cnae_person = PersonCNAE.objects.create(**c)
                    instance.cnaes.add(cnae_person)
        
        instance.save()
        return instance
    
    def to_representation(self, instance):
        representation = super().to_representation(instance)
        
        from service.serializers.supply_point_serializer import SupplyPointMinimalSerializer
        from billing.models import Payment, PaymentStatus
        from django.db.models import Sum
        
        deposit_paid = CommitmentDepositStatus.objects.get(token=ConfigProject.objects.get(token='commitment_deposit_status_paid_token').value)
        commitment_deposit = CommitmentDeposit.objects.filter(customer_token_final=instance.token).exclude(status=deposit_paid)
        representation['commitment_deposits'] = commitment_deposit.count()
        
        representation['full_name'] = f"{instance.name} {instance.surname}" if not instance.is_juridic else instance.name
        
        # Helper function to calculate debt amount for a contract
        def get_contract_debt_amount(contract_id):
            payment_status_expired = PaymentStatus.objects.get(token=ConfigProject.objects.get(token='payment_status_expired_token').value)
            payment_status_returned = PaymentStatus.objects.get(token=ConfigProject.objects.get(token='payment_status_returned_token').value)
            payment_status_irrecoverable = PaymentStatus.objects.get(token=ConfigProject.objects.get(token='payment_status_irrecoverable_token').value)
            payment_status_endowment = PaymentStatus.objects.get(token=ConfigProject.objects.get(token='payment_status_endowment_token').value)
            contract_payments = Payment.objects.filter(
                invoice__contract_id=contract_id, 
                status__in=[payment_status_expired, payment_status_returned, payment_status_irrecoverable, payment_status_endowment]
            )
            payments_amount = contract_payments.aggregate(total=Sum('amount'))['total'] or 0
            return payments_amount
        
        if instance.contracts_holder.exists():
            # representation['contracts_holder'] = contracts_data
            pass
            
        if instance.contracts_owner.exists():
            # representation['contracts_owner'] = contracts_data
            pass
            
        if instance.contracts_tenant.exists():
            # representation['contracts_tenant'] = contracts_data
            pass
            
        return representation

class PersonContractMinimalSerializer(serializers.ModelSerializer):
    addresses = serializers.SerializerMethodField()
    contacts = PersonContactSerializer(many=True, required=False, allow_null=True)
    banks = PersonBankMinimalSerializer(many=True, required=False, allow_null=True)
    deliquency = PersonDeliquencySerializer(required=False, allow_null=True)
    piggy_banks = serializers.SerializerMethodField()
    total_communications = serializers.SerializerMethodField()
    is_debtor = serializers.CharField(read_only=True, source='deliquency.is_debtor')
    debt_amount = serializers.DecimalField(read_only=True, source='deliquency.debt_amount', max_digits=10, decimal_places=2)
    current_record = serializers.SerializerMethodField()

    class Meta:
        model = Person
        fields = [
            'id', 'token', 'name', 
            'surname', 'is_juridic', 'is_debtor', 
            'debt_amount', 'vulnerability_level', 'piggy_banks', 
            'total_communications', 'deliquency', 'addresses', 
            'contacts', 'banks', 'cnaes', 'current_record'
                ]
    
    def get_current_record(self, instance):
        current_year = timezone.now().year
        return instance.records.filter(year=current_year).first().e_record if instance.records.filter(year=current_year).exists() else None
    
    def get_addresses(self, instance):
        min_ids = instance.addresses.values('address__id').annotate(
            min_id=Min('id')
        ).values_list('min_id', flat=True)
        
        distinct_addresses = instance.addresses.filter(id__in=min_ids)
        return PersonAddressMinimalSerializer(distinct_addresses, many=True).data
    
    def get_piggy_banks(self, instance):
        from contract.serializers.piggy_bank_serializer import PiggyBankMinimalSerializer
        if instance.piggy_banks.exists():
            return PiggyBankMinimalSerializer(instance.piggy_banks.all(), many=True).data
        return []

    def get_total_communications(self, instance):
        return instance.communications.count()
    
    """ def get_banks(self, obj):
        return PersonBankSerializer(obj.banks.all(), many=True).data
     """
    
    
    
    def to_representation(self, instance):
        representation = super().to_representation(instance)
        
        deposit_paid = CommitmentDepositStatus.objects.get(token=ConfigProject.objects.get(token='commitment_deposit_status_paid_token').value)
        commitment_deposit = CommitmentDeposit.objects.filter(customer_token_final=instance.token).exclude(status=deposit_paid)
        
        representation['commitment_deposits'] = commitment_deposit.count()
        
        representation['important_observations'] = PersonObservationSerializer(instance.observations.filter(is_important=True, is_active=True), many=True, context=self.context).data
        
        representation['full_name'] = f"{instance.name} {instance.surname}" if not instance.is_juridic else instance.name
        representation['contracts_holder'] = len([
            {'id': id}
            for id in instance.contracts_holder.values_list('id', flat=True)
        ])
        return representation

class PersonMinimalAddressSerializer(serializers.ModelSerializer):
    addresses = PersonAddressSerializer(many=True, required=False, allow_null=True)
    banks = PersonBankMinimalSerializer(many=True, required=False, allow_null=True)
    is_debtor = serializers.CharField(read_only=True, source='deliquency.is_debtor')
    debt_amount = serializers.DecimalField(read_only=True, source='deliquency.debt_amount', max_digits=10, decimal_places=2)
    
    class Meta:
        model = Person
        fields = ['id', 'token', 'name', 'surname','is_debtor', 'debt_amount', 'is_juridic', 'addresses', 'banks']
    
    def to_representation(self, instance):
        representation = super().to_representation(instance)

        # representation['commitment_deposits'] = commitment_deposit.count()
        
        representation['important_observations'] = PersonObservationSerializer(instance.observations.filter(is_important=True, is_active=True), many=True, context=self.context).data
        
        representation['full_name'] = f"{instance.name} {instance.surname}" if not instance.is_juridic else instance.name
        return representation
    
class PersonMinimalSerializer(serializers.ModelSerializer):
    is_debtor = serializers.CharField(read_only=True, source='deliquency.is_debtor')
    debt_amount = serializers.DecimalField(read_only=True, source='deliquency.debt_amount', max_digits=10, decimal_places=2)
    
    class Meta:
        model = Person
        fields = ['id', 'token', 'name', 'surname', 'is_juridic', 'is_debtor', 'debt_amount', 'vulnerability_level']
    
    def to_representation(self, instance):
        representation = super().to_representation(instance)
        
        deposit_paid = CommitmentDepositStatus.objects.get(token=ConfigProject.objects.get(token='commitment_deposit_status_paid_token').value)
        commitment_deposit = CommitmentDeposit.objects.filter(customer_token_final=instance.token).exclude(status=deposit_paid)
        
        representation['commitment_deposits'] = commitment_deposit.count()
        
        representation['important_observations'] = PersonObservationSerializer(instance.observations.filter(is_important=True, is_active=True), many=True, context=self.context).data
        
        representation['full_name'] = f"{instance.name} {instance.surname}" if not instance.is_juridic else instance.name
        representation['contracts_holder'] = len([
            {'id': id}
            for id in instance.contracts_holder.values_list('id', flat=True)
        ])
        return representation

class PersonMinimalContractSerializer(serializers.ModelSerializer):
    is_debtor = serializers.CharField(read_only=True, source='deliquency.is_debtor')
    debt_amount = serializers.DecimalField(read_only=True, source='deliquency.debt_amount', max_digits=10, decimal_places=2)
    current_record = serializers.SerializerMethodField()
    
    class Meta:
        model = Person
        fields = ['id', 'token', 'name', 'surname', 'is_juridic', 'is_debtor', 'debt_amount', 'vulnerability_level', 'current_record']
    
    def get_current_record(self, instance):
        current_year = timezone.now().year
        return instance.records.filter(year=current_year).first().e_record if instance.records.filter(year=current_year).exists() else None
    
    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation['full_name'] = f"{instance.name} {instance.surname}" if not instance.is_juridic else instance.name
        
        return representation

class PersonBankSerializer(serializers.ModelSerializer):
    iban = serializers.ReadOnlyField()
    country = CountrySerializer(read_only=True, required=False, allow_null=True)
    person = PersonMinimalSerializer(read_only=True, required=False, allow_null=True)
    bank = BankSerializer(required=False, allow_null=True)
    
    class Meta:
        model = PersonBank
        fields = '__all__'
    
    def update(self, instance, validated_data):
        if validated_data.get('is_default'):
            instance.person.banks.exclude(pk=instance.pk).filter(is_default=True).update(is_default=False)

        is_active = validated_data.get('is_active', None)
        if is_active != None and not is_active:
            validated_data['deactivated_at'] = timezone.now()
        return super().update(instance, validated_data)


class PersonCardSerializer(serializers.ModelSerializer):
    
    contacts = PersonContactSerializer(many=True, required=False, allow_null=True)
    
    class Meta:
        model = Person
        fields = '__all__'
    
    def to_representation(self, instance):
        representation = super().to_representation(instance)
        
        representation['full_name'] = f"{instance.name} {instance.surname}" if not instance.is_juridic else instance.name
        
        if (instance.contacts.exists()):
            contact_instance = instance.contacts.filter(is_default=True).first() or instance.contacts.first()
        
            contact = PersonContactSerializer(contact_instance).data if contact_instance else None

            if contact:
                representation['email'] = contact.get('email')
                representation['phone'] = contact.get('phone')
        
        return representation


class MainPermissionSerializer(serializers.ModelSerializer):
    affected_data = serializers.SerializerMethodField()
    class Meta:
        model = MainPermission
        fields = ['id', 'name', 'view_key', 'change_key', 'affected_data', 'is_default', 'all_recommended']
    
    def get_affected_data(self, instance):
        affected_models = instance.affected_models.split(',')
        affected_data = []
        
        for model_string in affected_models:
            model_string = model_string.strip()
            if '.' in model_string:
                app_name, model_name = model_string.split('.')
                
                try:
                    if model_name == 'config':
                        affected_data.append({ 'model': 'Config', 'name': 'Settings' })
                        continue
                    
                    model_class = apps.get_model(app_name, model_name)
                    
                    verbose_name = getattr(model_class._meta, 'verbose_name', None)
                    
                    if not verbose_name:
                        import re
                        verbose_name = re.sub(r'([a-z])([A-Z])', r'\1 \2', model_name).title()
                    affected_data.append({ 'model': model_name, 'app': f"{app_name}/{verbose_name.lower().replace(' ', '-')}", 'name': verbose_name.lower().replace(' ', '_') })

                except Exception as e:
                    affected_data.append({ 'model': model_name, 'app': f"{app_name}/{verbose_name.lower().replace(' ', '-')}", 'name': model_name.title() })
        
        return affected_data

class ReturnReasonSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReturnReason
        fields = ["id", "code", "label", "position"]
