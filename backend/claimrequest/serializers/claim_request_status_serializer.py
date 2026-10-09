from rest_framework import serializers
from claimrequest.models import ClaimRequestStatus

class ClaimRequestStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClaimRequestStatus
        fields = '__all__' 