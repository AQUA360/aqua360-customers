from rest_framework import serializers
from auth.serializers import UserMinimalSerializer
from ..models import History

class HistorySerializer(serializers.ModelSerializer):
    user = UserMinimalSerializer(read_only=True)
    
    class Meta:
        model = History
        fields = '__all__'
    
    