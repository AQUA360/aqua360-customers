from django_filters import rest_framework as filters
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import serializers, viewsets
from rest_framework.permissions import DjangoModelPermissions, IsAuthenticated

from coredata.models import Holiday


class HolidaySerializer(serializers.ModelSerializer):
    exploitation_name = serializers.CharField(source='exploitation.name', read_only=True)

    class Meta:
        model = Holiday
        fields = '__all__'


class HolidayFilter(filters.FilterSet):
    year = filters.NumberFilter(field_name='date__year')
    exploitation = filters.NumberFilter(field_name='exploitation__id')

    class Meta:
        model = Holiday
        fields = ['year', 'exploitation']


class HolidayViewSet(viewsets.ModelViewSet):
    """Calendari de festius per al càlcul de dies hàbils (el manté cada client)."""
    queryset = Holiday.objects.select_related('exploitation').order_by('date')
    serializer_class = HolidaySerializer
    permission_classes = [IsAuthenticated, DjangoModelPermissions]
    filter_backends = [DjangoFilterBackend]
    filterset_class = HolidayFilter
    pagination_class = None
