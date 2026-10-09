from rest_framework import serializers
from ..models import ( ContractClause )

class ContractClauseSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContractClause
        fields = '__all__'