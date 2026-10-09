import datetime
from logging import config
from django.db import transaction
from rest_framework import serializers
from auth.serializers import UserMinimalSerializer
from service.serializers.connection_request_serializer import (
    ConnectionRequestListSerializer,
)
from django.conf import settings
from ..models import Order, OrderObservation, OrderStatus, Operator
from service.serializers.supply_point_serializer import SupplyPointMinimalSerializer
from service.serializers.connection_serializer import ConnectionMinimalSerializer
from coredata.serializers import AddressMinimalSerializer, AddressSerializer, CitySerializer
from coredata.utils.name_utils import generate_token
from ..utils.claim_request_order_service import get_order_type_initials
from .value_objects_serializer import (
    OrderStatusSerializer,
    OrderTypeSerializer,
    OrderTypeMinimalSerializer,
    OrderReasonMinimalSerializer,
)
from .operator_serializer import OperatorSerializer
from coredata.models import Address, ConfigProject


class OrderObservationSerializer(serializers.ModelSerializer):
    user = UserMinimalSerializer(required=False, allow_null=True)

    class Meta:
        model = OrderObservation
        fields = "__all__"


class OrderSerializer(serializers.ModelSerializer):
    supply_point = SupplyPointMinimalSerializer(
        read_only=True, required=False, allow_null=True
    )
    connection = ConnectionMinimalSerializer(
        read_only=True, required=False, allow_null=True
    )
    connection_request = ConnectionRequestListSerializer(
        read_only=True, required=False, allow_null=True
    )
    incident = serializers.SerializerMethodField()
    related_incidents = serializers.SerializerMethodField()
    address = AddressSerializer(read_only=True, required=False, allow_null=True)
    total_reports = serializers.SerializerMethodField()
    check_response = serializers.SerializerMethodField()
    created_by = UserMinimalSerializer(read_only=True)

    def get_total_reports(self, instance):
        return instance.reports.count()

    def get_check_response(self, instance):
        return getattr(instance, "check_response", None)

    def get_incident(self, instance):
        from notification.serializers.incident_serializer import IncidentListSerializer

        return (
            IncidentListSerializer(instance.incident).data
            if instance.incident
            else None
        )

    def get_contract(self, instance):
        from contract.serializers.contract_serializer import ContractMinimalSerializer

        return (
            ContractMinimalSerializer(instance.contract).data
            if instance.contract
            else None
        )

    def get_contract_request(self, instance):
        from contract.serializers.contract_request_serializer import (
            ContractRequestSerializer,
        )

        return (
            ContractRequestSerializer(instance.contract_request).data
            if instance.contract_request
            else None
        )

    def get_related_incidents(self, obj):
        # Incidències que referencien l'ordre més la que l'ha originada
        from django.db.models import Q
        from notification.models import Incident
        return Incident.objects.filter(
            Q(order_incident=obj) | Q(orders=obj)
        ).distinct().count()

    contract_token = serializers.CharField(source="contract.token", read_only=True)
    contract_request_token = serializers.CharField(
        source="contract_request.token", read_only=True
    )

    operators = OperatorSerializer(
        many=True, read_only=True, required=False, allow_null=True
    )

    observations = OrderObservationSerializer(
        many=True, required=False, allow_null=True
    )
    related_contract_token = serializers.CharField(read_only=True)

    class Meta:
        model = Order
        fields = "__all__"

    def to_representation(self, instance):
        from .value_objects_serializer import OrderPrioritySerializer

        representation = super().to_representation(instance)

        representation["type"] = (
            OrderTypeMinimalSerializer(instance.type).data if instance.type else None
        )
        representation["reason"] = (
            OrderReasonMinimalSerializer(instance.reason).data
            if instance.reason
            else None
        )
        representation["status"] = OrderStatusSerializer(instance.status).data
        representation["priority"] = (
            OrderPrioritySerializer(instance.priority).data
            if instance.priority
            else None
        )

        # Afegim el contract serialitzat
        if instance.contract:
            from contract.serializers.contract_serializer import (
                ContractMinimalSerializer,
            )

            representation["contract"] = ContractMinimalSerializer(
                instance.contract
            ).data

        return representation


class OrderSaveSerializer(serializers.ModelSerializer):
    operators = serializers.PrimaryKeyRelatedField(
        queryset=Operator.objects.all(), many=True, required=False, allow_null=True
    )
    address = serializers.PrimaryKeyRelatedField(queryset=Address.objects.all(), required=False, allow_null=True)

    def to_internal_value(self, data):
        mutable_data = data.copy()
        address_input = mutable_data.pop('address', None) or mutable_data.pop('address_id', None)
        print("address_input", address_input)
        if address_input:
            if isinstance(address_input, dict):
                addr_id = address_input.get('id')
                mutable_data['address'] = addr_id
            else:
                mutable_data['address'] = address_input
                
        return super().to_internal_value(mutable_data)

    # observation = serializers.CharField(write_only=True, required=False, allow_null=True, allow_blank=True)
    class Meta:
        model = Order
        fields = "__all__"

    @transaction.atomic
    def create(self, validated_data):
        print(validated_data)
        operators_data = validated_data.pop("operators", [])

        default_status = OrderStatus.objects.get(is_default=True)
        if default_status and not ("status" in validated_data):
            validated_data["status"] = default_status

        if settings.RABBITMQ_ENABLED:
            
            config = ConfigProject.objects.filter(
                token="sent_order_status_token"
            ).first()
            if config:
                sent_status_token = config.value
            else:
                import logging

                logger = logging.getLogger(__name__)
                logger.warning(
                    "ConfigProject for 'sent_order_status_token' not found. Using '-5' as default. This may not work well."
                )
                sent_status_token = "-5"
            validated_data["status"] = OrderStatus.objects.get(
                token=sent_status_token
            )

        # Obtenir les inicials del tipus d'ordre
        order_type = validated_data.get("type")
        if order_type and order_type.token:
            order_type_initials = get_order_type_initials(order_type.token)
        else:
            order_type_initials = "OR"

        # Determinar el prefix i ID de l'objecte relacionat
        object_prefix = ""
        object_id = ""
        if (
            "contract_request" in validated_data
            and validated_data["contract_request"] is not None
        ):
            object_prefix = "CR"
            object_id = str(validated_data.get("contract_request").id)
        elif "incident" in validated_data and validated_data["incident"] is not None:
            object_prefix = "IN"
            incident = validated_data.get("incident")
            object_id = str(incident.id)
            if incident.contract:
                validated_data["contract"] = incident.contract
                validated_data["supply_point"] = incident.contract.supply_point_default
        elif "contract" in validated_data and validated_data["contract"] is not None:
            object_prefix = "CT"
            object_id = str(validated_data.get("contract").id)
        elif (
            "contract_termination_request" in validated_data
            and validated_data["contract_termination_request"] is not None
        ):
            object_prefix = "CTR"
            object_id = str(validated_data.get("contract_termination_request").id)
        elif (
            "supply_point" in validated_data
            and validated_data["supply_point"] is not None
        ):
            object_prefix = "SP"
            object_id = str(validated_data.get("supply_point").id)
        elif (
            "connection" in validated_data and validated_data["connection"] is not None
        ):
            object_prefix = "CN"
            object_id = str(validated_data.get("connection").id)
        elif (
            "connection_request" in validated_data
            and validated_data["connection_request"] is not None
        ):
            object_prefix = "CNR"
            object_id = str(validated_data.get("connection_request").id)
        else:
            object_prefix = "OR"
            object_id = str(validated_data.get("id", ""))

        # Inferred address and coordinates logic
        if not validated_data.get("address"):
            if (
                validated_data.get("supply_point")
                and validated_data["supply_point"].address
            ):
                validated_data["address"] = validated_data["supply_point"].address
            elif (
                validated_data.get("contract")
                and validated_data["contract"].supply_point_default
                and validated_data["contract"].supply_point_default.address
            ):
                validated_data["address"] = validated_data[
                    "contract"
                ].supply_point_default.address
            elif validated_data.get("connection_request"):
                cr = validated_data["connection_request"]
                if cr.address_street and cr.address_street_number:
                    # Try to find or create Address
                    try:
                        address_params = {
                            "street": cr.address_street,
                            "street_number": cr.address_street_number,
                            "city": cr.address_city,
                            "postal_code": cr.address_postal_code.code
                            if cr.address_postal_code
                            else None,
                        }
                        address = Address.objects.filter(**address_params).first()
                        if not address:
                            address = Address.objects.create(**address_params)
                        
                        validated_data["address"] = address
                    except Exception:
                        pass

                # Also copy coordinates if null
                if validated_data.get("latitude") is None:
                    validated_data["latitude"] = cr.latitude
                if validated_data.get("longitude") is None:
                    validated_data["longitude"] = cr.longitude

        # Inferred reason logic
        if not validated_data.get("reason") and validated_data.get("type"):
            reasons = validated_data["type"].reasons.all()
            if reasons.count() == 1:
                validated_data["reason"] = reasons.first()

        # Generar token amb format: {yymmdd}/{prefix_objecte}{id_objecte}/{inicials_tipus_ordre}{id_incremental}
        # Utilitzem generate_token però afegim els separadors "/" manualment
        import datetime

        now = datetime.datetime.now()
        date_part = now.strftime("%y%m%d")
        last_instance = Order.objects.order_by("-id").first()
        next_id = (last_instance.id if last_instance else 0) + 1
        id_part = f"{next_id:03d}"[-3:]
        token = f"{date_part}/{object_prefix}{object_id}/{order_type_initials}{id_part}"

        validated_data["token"] = token

        request = self.context.get("request")
        if request and hasattr(request, "user"):
            validated_data["created_by"] = request.user

        obj = Order.objects.create(**validated_data)

        # TODO: Assignar operators
        obj.operators.set(operators_data)

        return obj

    @transaction.atomic
    def update(self, instance, validated_data):
        # Verificar si 'representatives' ha estat enviat en les dades d'entrada
        operators_present = "operators" in self.initial_data
        operators_data = validated_data.pop("operators", [])
        print("-----update-----")
        print(validated_data)
        order_closed_status_token = ConfigProject.objects.get(token="order_status_completed_token").value
        order_validate_status_token = ConfigProject.objects.get(token="for_validate_order_status_token").value
        order_status = validated_data.get("status", None)
        if order_status and order_status.token not in [order_closed_status_token, order_validate_status_token]:
            validated_data["completed_at"] = None
        
        # Actualitzar camps de ContractRequest
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        # TODO: Gestionar operadors
        if operators_present:
            instance.operators.set(operators_data)
        return instance

    def validate(self, data):
        if not self.instance and "token" not in data:
            raise serializers.ValidationError({"token": "This field is required."})
        return data


class OrderListSerializer(serializers.ModelSerializer):
    incident_token = serializers.CharField(source="incident.token", read_only=True)
    related_contract_token = serializers.CharField(read_only=True)

    # operator_token = serializers.CharField(source='operator.token', read_only=True)
    type_token = serializers.CharField(source="type.token", read_only=True)
    type_name = serializers.CharField(source="type.name", read_only=True)
    reason_token = serializers.CharField(source="reason.token", read_only=True)
    reason_name = serializers.CharField(source="reason.name", read_only=True)
    address_complete = serializers.CharField(source="address.__str__", read_only=True)

    # operators_token = serializers.CharField(source='operators.token', read_only=True)
    created_by = UserMinimalSerializer(read_only=True)
    operators = OperatorSerializer(
        many=True, read_only=True, required=False, allow_null=True
    )

    class Meta:
        model = Order
        fields = [
            "id",
            "token",
            "created_at",
            "related_contract_token",
            "address_complete",
            "incident_token",
            "type_token",
            "type_name",
            "reason_token",
            "reason_name",
            "dueDateAt",
            "created_by",
            "operators",
            "completed_at",
        ]

    def to_representation(self, instance):
        from .value_objects_serializer import OrderPrioritySerializer

        representation = super().to_representation(instance)

        representation["type"] = (
            OrderTypeMinimalSerializer(instance.type).data if instance.type else None
        )
        representation["reason"] = (
            OrderReasonMinimalSerializer(instance.reason).data
            if instance.reason
            else None
        )
        representation["status"] = OrderStatusSerializer(instance.status).data
        representation["priority"] = (
            OrderPrioritySerializer(instance.priority).data
            if instance.priority
            else None
        )
        
        if instance.address:
            representation["address"] = {
                "address_complete": str(instance.address),
                "city": CitySerializer(instance.address.city).data if instance.address.city else None,
            }
        if instance.supply_point:
            representation["supply_point"] = {
                "id": instance.supply_point.id,
                "token": instance.supply_point.token,
                "city": CitySerializer(instance.supply_point.address.city).data if instance.supply_point.address.city else None,
                "address_complete": str(instance.supply_point.address),
            }
        if instance.connection:
            connection_address_complete = ""
            if(str(instance.connection.address_street) and str(instance.connection.address_street) != 'None'):
                connection_address_complete += str(instance.connection.address_street)
            if(str(instance.connection.address_street_number) and str(instance.connection.address_street_number) != 'None'):
                connection_address_complete += ", " + str(instance.connection.address_street_number)
            representation["connection"] = {
                "id": instance.connection.id,
                "token": instance.connection.token,
                "city": CitySerializer(instance.connection.address_city).data if instance.connection.address_city else None,
                "address_complete": connection_address_complete,
            }

        # Afegim el contract serialitzat
        if instance.contract:
            representation["contract"] = {
                "id": instance.contract.id,
                "token": instance.contract.token,
            }
        if instance.contract_request:
            representation["contract_request"] = {
                "id": instance.contract_request.id,
                "token": instance.contract_request.token,
            }

        return representation


class OrderMinimalSerializer(serializers.ModelSerializer):
    type = OrderTypeSerializer(read_only=True, required=False, allow_null=True)
    status = OrderStatusSerializer(read_only=True, required=False, allow_null=True)
    supply_point_id = serializers.IntegerField(source="supply_point.id", read_only=True)

    class Meta:
        model = Order
        fields = ["id", "created_at", "token", "type", "status", "supply_point_id"]
