from django_filters import rest_framework as filters

from communication.models import CommunicationFile

class CommunicationFileFilter(filters.FilterSet):
    communication = filters.CharFilter(field_name='communication__id', lookup_expr='exact')

    class Meta:
        model = CommunicationFile
        fields = ['communication']