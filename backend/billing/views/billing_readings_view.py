# contract/views/contract_request_finalize_view.py
from django.http import FileResponse
from rest_framework import status, views
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import generics
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from rest_framework.pagination import PageNumberPagination

from billing.filter.reading_filter import ReadingFilter
from billing.models import Billing, Reading
from billing.serializers.reading_serializer import ReadingByBatchMinimalSerializer
from django.shortcuts import get_object_or_404

class BillingReadingsViewSet(generics.ListAPIView):  # Changed to generics.ListAPIView
    permission_classes = [IsAuthenticated, DjangoModelPermissions]
    serializer_class = ReadingByBatchMinimalSerializer  # Added serializer_class
    pagination_class = PageNumberPagination  # Added pagination_class
    filter_backends = [DjangoFilterBackend]  # Added filter_backends
    filterset_class = ReadingFilter  # Added filterset_class
    queryset = Reading.objects.all().order_by('-created_at')
    def get_queryset(self):
        id = self.kwargs.get('id')  # Get the ID from the URL
        if not id:
            return Reading.objects.none() # Return an empty queryset

        billing = get_object_or_404(Billing, id=id)
        queryset = Reading.objects.filter(billing=billing).order_by('-created_at')
        return queryset

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset()) # Apply the filters

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
        