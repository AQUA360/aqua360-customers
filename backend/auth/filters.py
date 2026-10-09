from django_filters import rest_framework as filters
from django.db.models import Q
from django.contrib.auth.models import User, Group

class UserFilter(filters.FilterSet):
    search = filters.CharFilter(method='filter_search')
    
    group = filters.CharFilter(method='filter_group')
    no_group = filters.CharFilter(method='filter_no_group')
    hide_admin = filters.BooleanFilter(method='filter_hide_admin')
    class Meta:
        model = User
        fields = ['group', 'no_group', 'hide_admin', 'search']
    
    def filter_search(self, queryset, name, value):
        return queryset.filter(
            Q(username__icontains=value) |
            Q(first_name__icontains=value) |
            Q(last_name__icontains=value) |
            Q(email__icontains=value)
        )
    
    def filter_group(self, queryset, name, value):
        if value:
            value_ids = value.split(',')
            return queryset.filter(groups__id__in=value_ids)
        return queryset
    
    def filter_no_group(self, queryset, name, value):
        if value:
            value_ids = value.split(',')
            return queryset.exclude(groups__id__in=value_ids)
        return queryset
    
    def filter_hide_admin(self, queryset, name, value):
        if value:
            return queryset.filter(is_superuser=False)
        return queryset


class GroupFilter(filters.FilterSet):
    search = filters.CharFilter(method='filter_search')
    class Meta:
        model = Group
        fields = ['search']
    
    def filter_search(self, queryset, name, value):
        return queryset.filter(name__icontains=value)