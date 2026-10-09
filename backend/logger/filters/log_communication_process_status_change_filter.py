from django_filters import rest_framework as filters
from django.db.models import Q
from logger.models import LogCommunicationProcessStatusChange

class LogCommunicationProcessStatusChangeFilter(filters.FilterSet):
    
    class Meta:
        model = LogCommunicationProcessStatusChange
        fields = ["object","timestamp"]
