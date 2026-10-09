from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter, SearchFilter
from django.db.models import Q

from notification.filters.general_note_filter import GeneralNoteFilter
from notification.serializers.general_note_serializer import GeneralNoteSerializer
from ..models import GeneralNote

class GeneralNoteCustomPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100

class GeneralNoteViewSet(viewsets.ModelViewSet):
    queryset = GeneralNote.objects.all().filter(is_active=True).order_by('-created_at')
    permission_classes = [IsAuthenticated, DjangoModelPermissions]
    filter_backends = [DjangoFilterBackend, OrderingFilter, SearchFilter]
    filterset_class = GeneralNoteFilter
    search_fields = ['token','note']
    ordering_fields = ['token','note']
    pagination_class = GeneralNoteCustomPagination
  
    def get_serializer_class(self):
        return GeneralNoteSerializer
    
    @action(detail=False, methods=['get'], url_path='read')
    def simple_list(self, request):
        
        user = request.user if request else None
        print("adding user to read_by")
        print(user)
        
        
        unread_notes = GeneralNote.objects.exclude(read_by=user)
        for note in unread_notes:
            note.read_by.add(user)
            note.save()
        
        queryset = self.filter_queryset(self.get_queryset())
        paginator = GeneralNoteCustomPagination()
        paginator.page_size = 10
        result_page = paginator.paginate_queryset(queryset, request)
        serializer = self.get_serializer(result_page, many=True)
        return paginator.get_paginated_response(serializer.data)
  
    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context