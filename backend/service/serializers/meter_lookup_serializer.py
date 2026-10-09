from rest_framework import serializers


class MeterLookupStatusSerializer(serializers.Serializer):
    id = serializers.IntegerField(allow_null=True)
    token = serializers.CharField(allow_null=True)
    name = serializers.CharField(allow_null=True)
    color = serializers.CharField(allow_null=True, required=False)


class MeterLookupCaliberSerializer(serializers.Serializer):
    token = serializers.CharField(allow_null=True)
    name = serializers.CharField(allow_null=True)


class MeterLookupSupplyPointSerializer(serializers.Serializer):
    token = serializers.CharField(allow_null=True)
    status = MeterLookupStatusSerializer(allow_null=True)
    address_search = serializers.CharField(allow_null=True, allow_blank=True)


class MeterLookupContractSerializer(serializers.Serializer):
    token = serializers.CharField(allow_null=True)
    status = MeterLookupStatusSerializer(allow_null=True)
    facturable = serializers.BooleanField()


class MeterLookupLastReadingSerializer(serializers.Serializer):
    reading_date = serializers.DateField(allow_null=True)
    reading_value = serializers.DecimalField(
        max_digits=10, decimal_places=2, allow_null=True
    )
    consumption = serializers.DecimalField(
        max_digits=10, decimal_places=2, allow_null=True
    )
    batch_token = serializers.CharField(allow_null=True)


class MeterLookupSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    code = serializers.CharField(allow_null=True)
    exploitation = serializers.CharField(allow_null=True, allow_blank=True)
    status = MeterLookupStatusSerializer(allow_null=True)
    caliber = MeterLookupCaliberSerializer(allow_null=True)
    installation_at = serializers.DateField(allow_null=True)
    uninstallation_at = serializers.DateField(allow_null=True)
    has_remote_reading = serializers.BooleanField()
    manufacturer = serializers.CharField(allow_null=True, allow_blank=True)
    manufacturing_year = serializers.IntegerField(allow_null=True)
    comm_technology = serializers.CharField(allow_null=True, allow_blank=True)
    supply_point = MeterLookupSupplyPointSerializer(allow_null=True)
    contracts = MeterLookupContractSerializer(many=True)
    last_reading = MeterLookupLastReadingSerializer(allow_null=True)
