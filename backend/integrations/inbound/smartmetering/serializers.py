from rest_framework import serializers

from .mappers import map_abonat


class SmartMeteringAbonatSerializer(serializers.Serializer):
    """Serialitzador equivalent a les columnes de `vw_abonats_aqua360`."""

    policy = serializers.CharField(allow_null=True)
    meter = serializers.CharField(allow_null=True)
    rate = serializers.CharField(allow_null=True)
    service_point = serializers.CharField(allow_null=True)
    inst_date = serializers.DateField(allow_null=True)
    comm_module = serializers.CharField(allow_null=True)
    comm_technology = serializers.CharField(allow_null=True)
    manufacturer = serializers.CharField(allow_null=True)
    model = serializers.CharField(allow_null=True)
    network_provider = serializers.CharField(allow_null=True)
    expl_id = serializers.CharField(allow_null=True)
    dma_id = serializers.CharField(allow_null=True)
    contract_active = serializers.BooleanField()
    customer = serializers.CharField(allow_null=True)
    cadastral_ref = serializers.CharField(allow_null=True)
    connect_id = serializers.CharField(allow_null=True)

    def to_representation(self, instance):
        if isinstance(instance, dict):
            return instance
        return map_abonat(
            instance,
            active_status_token=self.context.get("active_status_token"),
        )
