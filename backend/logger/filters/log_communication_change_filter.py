from django_filters import rest_framework as filters
from django.db.models import Q
from logger.models import LogCommunicationChange

class LogCommunicationChangeFilter(filters.FilterSet):
    
    class Meta:
        model = LogCommunicationChange
        fields = ["object","timestamp"]
