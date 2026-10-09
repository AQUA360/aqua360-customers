from django_filters import rest_framework as filters
from ..models import GeneralNote
from django.db.models import Q

class GeneralNoteFilter(filters.FilterSet):
    search = filters.CharFilter(method='filter_search')
    is_seen = filters.BooleanFilter(method='filter_is_seen')
    is_active = filters.BooleanFilter(field_name='is_active', label='Is Active')
    
    class Meta:
        model = GeneralNote
        fields = ['search', 'is_seen', 'is_active']
   
    def filter_search(self, queryset, name, value):
        return queryset.filter(
            Q(token__icontains=value) |
            Q(name__icontains=value) |
            Q(description__icontains=value) |
            Q(module__icontains=value) |
            Q(entity__icontains=value) 
        )
        
    def filter_is_seen(self, queryset, name, value):
        if not hasattr(self, 'request'):
            return queryset
            
        user = self.request.user if self.request else None
        if user:
            if value:
                return queryset.filter(read_by=user)
            else:
                return queryset.exclude(read_by=user)
        return queryset
    