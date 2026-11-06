from rest_framework import serializers

from contract.models import Contract
from service.models import SupplyPoint
from service.utils.route_scope import effective_route, effective_route_position, has_own_route_position


class RouteSupplyPointTabContractSerializer(serializers.ModelSerializer):
    status = serializers.SerializerMethodField()
    facturable = serializers.SerializerMethodField()

    class Meta:
        model = Contract
        fields = ('token', 'status', 'facturable')

    def get_status(self, obj):
        if not obj.status:
            return None
        return {
            'id': obj.status.id,
            'token': obj.status.token,
            'name': obj.status.name,
            'color': getattr(obj.status, 'color', None),
        }

    def get_facturable(self, obj):
        return not bool(obj.block_billing)


class RouteSupplyPointTabSerializer(serializers.ModelSerializer):
    route = serializers.SerializerMethodField()
    route_position = serializers.SerializerMethodField()
    own_route_position = serializers.SerializerMethodField()
    property = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()
    meter = serializers.SerializerMethodField()
    has_reading = serializers.SerializerMethodField()
    reading = serializers.SerializerMethodField()
    contracts = serializers.SerializerMethodField()

    class Meta:
        model = SupplyPoint
        fields = (
            'id',
            'route',
            'route_position',
            'own_route_position',
            'property',
            'token',
            'status',
            'meter',
            'has_reading',
            'reading',
            'contracts',
        )

    def get_route(self, obj):
        route = effective_route(obj)
        if not route:
            return None
        return {'token': route.token, 'name': route.name}

    def get_route_position(self, obj):
        route_position = effective_route_position(obj)
        if not route_position:
            return None
        return {
            'token': route_position.token,
            'position': route_position.position,
        }

    def get_own_route_position(self, obj):
        # True si el punt té posició de ruta pròpia (no heretada de la finca)
        return has_own_route_position(obj)

    def get_property(self, obj):
        prop = obj.property
        if not prop:
            return None
        return {'token': prop.token}

    def get_status(self, obj):
        if not obj.status:
            return None
        return {
            'id': obj.status.id,
            'token': obj.status.token,
            'name': obj.status.name,
            'color': getattr(obj.status, 'color', None),
        }

    def get_meter(self, obj):
        if not obj.meter:
            return None
        return {'code': obj.meter.code}

    def get_has_reading(self, obj):
        return False

    def get_reading(self, obj):
        return None

    def get_contracts(self, obj):
        contracts = list(obj.contracts.all())
        contracts.sort(key=lambda c: ((c.token or '').lower(), c.id or 0))
        return RouteSupplyPointTabContractSerializer(contracts, many=True).data
