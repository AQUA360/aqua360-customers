from rest_framework import serializers

from ..models import ACABonificationRequest


class ACABonificationRequestSerializer(serializers.ModelSerializer):
    contract_id = serializers.IntegerField(source='bonification.contract_id', read_only=True)
    contract_token = serializers.CharField(source='bonification.contract.token', read_only=True)
    holder_name = serializers.SerializerMethodField()
    requested_at = serializers.DateTimeField(source='bonification.requested_at', read_only=True)

    class Meta:
        model = ACABonificationRequest
        fields = [
            'id', 'contract_id', 'contract_token', 'holder_name', 'requested_at',
            'num_persons_to_apply', 'authorizes_census_review',
            'aca_result', 'censat_adreca', 'num_persons_censats',
            'sent_at', 'aca_document',
        ]
        read_only_fields = ['num_persons_to_apply', 'sent_at', 'aca_document']

    def get_holder_name(self, obj):
        holder = obj.bonification.contract.holder if obj.bonification.contract else None
        if not holder:
            return None
        return f"{holder.name} {holder.surname or ''}".strip()
