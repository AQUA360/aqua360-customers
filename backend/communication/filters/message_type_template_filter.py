from django_filters import rest_framework as filters
from django.db.models import Q
from ..models import MessageTypeTemplate

class MessageTypeTemplateFilter(filters.FilterSet):
    message_template = filters.CharFilter(method='filter_message_template')
    
    class Meta:
        model = MessageTypeTemplate
        fields = ['message_template']
   
    def filter_message_template(self, queryset, name, value):
        if value:
            return queryset.filter(message_templates__id=value)
        return queryset