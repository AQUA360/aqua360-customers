from django_filters import rest_framework as filters
from django.db.models import Q
from logger.models import LogIncidentStatusChange

class LogIncidentStatusChangeFilter(filters.FilterSet):
    
    class Meta:
        model = LogIncidentStatusChange
        fields = ["object","timestamp"]
