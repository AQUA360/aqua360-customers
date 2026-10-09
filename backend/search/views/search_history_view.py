from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from rest_framework.response import Response

from django_filters.rest_framework import DjangoFilterBackend

from ..filters.search_history_filter import SearchHistoryFilter
from search.serializers.search_history_serializer import HistorySerializer
from ..models import (History)

class HistoryViewSet(viewsets.ModelViewSet):
    queryset = History.objects.all().order_by('-searched_at')
    serializer_class = HistorySerializer
    filter_backends = (DjangoFilterBackend,)
    permission_classes = [IsAuthenticated, DjangoModelPermissions]
    filterset_class = SearchHistoryFilter

    def get_queryset(self):
        # Only return the search history of the authenticated user
        return super().get_queryset().filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)
        