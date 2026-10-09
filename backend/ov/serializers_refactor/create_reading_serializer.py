from billing.models import Reading
from billing.utils.reading_service import check_billing_period
from contract.models import Contract
from service.models import Meter, SupplyPoint
from rest_framework import serializers
from coredata.utils.name_utils import generate_token

"""
{
"reading_at": "YYYY-mm-dd",
"contract": "<contract_token>",
"meter": "<meter_token>",
"reading": <reading_value>
}
"""


class CreateReadingSerializer(serializers.Serializer):
    reading_at = serializers.DateField(
        format="%Y-%m-%d", input_formats=["%Y-%m-%d"], required=True
    )
    contract = serializers.SlugRelatedField(
        slug_field="token", queryset=Contract.objects.all(), required=True
    )
    meter = serializers.SlugRelatedField(
        slug_field="token", queryset=Meter.objects.all(), required=True
    )
    reading = serializers.FloatField(required=True)

    def validate(self, data):
        contract = data.get("contract")
        meter = data.get("meter")

        # Check if contract has a supply_point_default
        supply_point = contract.supply_point_default
        if not supply_point:
            raise serializers.ValidationError(
                {"contract": "Contract does not have a default supply point."}
            )

        # Check if the supply_point_default's meter matches the provided meter
        if supply_point.meter != meter:
            raise serializers.ValidationError(
                {
                    "meter": "The provided meter does not match the contract's default supply point meter."
                }
            )

        # Store supply_point for use in create
        data["supply_point"] = supply_point
        return data

    def create(self, validated_data):
        contract = validated_data.get("contract")
        meter = validated_data.get("meter")
        supply_point = validated_data.get("supply_point")
        reading_value = validated_data.get("reading")
        reading_date = validated_data.get("reading_at")

        # if supply point is int get supply point by id
        if isinstance(supply_point, int):
            supply_point = SupplyPoint.objects.get(id=supply_point)
            
        # Generate token for the new reading
        token = generate_token(Reading, "-id", "OV" )

        previous_reading = Reading.objects.filter(
            contract=contract,
            reading_date__lte=reading_date,
            meter=meter,
            supply_point=supply_point,
            # reading_value__isnull=False,
            reading_date__isnull=False,
            is_control=False,
        ).order_by('-reading_date').first()
        
        
        can_enter_readings = check_billing_period(
            reading_date=reading_date,
            supply_point=supply_point,
            meter=meter,
            contract=contract,
            previous_reading=previous_reading,
            is_termination=False,
        )
        
        # Create the Reading instance
        reading = Reading.objects.create(
            token=token,
            contract=contract,
            supply_point=supply_point,
            meter=meter,
            reading_value=reading_value,
            reading_date=reading_date,
            origin="OV",  # Origin from Oficina Virtual
            is_active=True,
            is_control=not can_enter_readings,
            previous_reading=previous_reading,
            calculated_value=float(reading_value) - float(previous_reading.reading_value) if previous_reading else float(reading_value),
            real_consumption=float(reading_value) - float(previous_reading.reading_value) if previous_reading else float(reading_value),
        )

        return reading
