from django_filters import rest_framework as filters
from coredata.models import ConfigProject
from django.db.models import Q

class ConfigProjectFilter(filters.FilterSet):
    class Meta:
        model = ConfigProject
        fields = ['token']