from django.forms.utils import ValidationError
from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.response import Response
from datetime import datetime, timedelta
from rest_framework.decorators import action
from django.conf import settings
from documentmanager.utils.main_utils import upload_document

from ..models import ClaimRequestStepDocument, ClaimRequestStepTemplate, ClaimRequestStep, ClaimRequestStatus
from coredata.models import ConfigProject
from ..serializers import (
    ClaimRequestPaymentSerializer,
    ClaimRequestStepTemplateSerializer,
    ClaimRequestStepTemplateListSerializer,
    ClaimRequestStepTemplateSaveSerializer,
    ClaimRequestStepSerializer
)
from claimrequest.permissions import ClaimRequestPermission
class ClaimRequestStepTemplateViewSet(viewsets.ModelViewSet):
    queryset = ClaimRequestStepTemplate.objects.all().order_by('position')
    serializer_class = ClaimRequestStepTemplateSerializer
    permission_classes = [IsAuthenticated, ClaimRequestPermission]
    filter_backends = [DjangoFilterBackend, OrderingFilter, SearchFilter]
    search_fields = ['token','name']
    ordering_fields = ['token','name', 'duration','position']
    lookup_field = 'id'
    
    def get_serializer_class(self):
        if self.request.method in ['GET']:
            return ClaimRequestStepTemplateSerializer
        return ClaimRequestStepTemplateSaveSerializer
    
    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context

class ClaimRequestStepViewSet(viewsets.ModelViewSet):
    queryset = ClaimRequestStep.objects.all().order_by('-created_at')   
    serializer_class = ClaimRequestStepSerializer
    permission_classes = [IsAuthenticated, DjangoModelPermissions]
    filter_backends = [DjangoFilterBackend, OrderingFilter, SearchFilter]
    search_fields = ['token','name']
    ordering_fields = ['token','name', 'duration','position']
    lookup_field = 'id'

    def retrieve(self, request, *args, **kwargs):
        claim_request_id = kwargs.get('id')
        steps = ClaimRequestStep.objects.filter(claim_request_id=claim_request_id).order_by('position')
        serializer = self.get_serializer(steps, many=True)
        return Response(serializer.data) 
        
    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        
        # Comprovem si s'ha actualitzat action_date_at
        if 'action_date_at' in serializer.validated_data:
            action_date = serializer.validated_data['action_date_at']
            duration = instance.duration
            duration_type = instance.duration_type
            
            claim_pending_status_token = ConfigProject.objects.get(token='claim_request_status_pending_token').value
            claim_accepted_status_token = ConfigProject.objects.get(token='claim_request_status_accepted_token').value
            
            if instance.claim_request.status.token == claim_pending_status_token:
                instance.claim_request.status = ClaimRequestStatus.objects.get(token=claim_accepted_status_token)
                instance.claim_request.save()
            
            # Calculem due_date segons el tipus de duració
            if action_date and duration:
                if duration_type == 'NATURAL':
                    # Dies naturals: simplement afegim la duració
                    due_date = action_date + timedelta(days=duration)
                else:  # 'WORK'
                    # Dies hàbils: excloem només caps de setmana
                    due_date = action_date
                    days_added = 0
                    
                    while days_added < duration:
                        due_date += timedelta(days=1)
                        # Comprovem si no és cap de setmana (0=dilluns, 6=diumenge)
                        if due_date.weekday() < 5:  # Dilluns a divendres
                            days_added += 1
                
                serializer.validated_data['due_date'] = due_date
        
        self.perform_update(serializer)
        return Response(serializer.data) 
    
    @action(detail=True, methods=['get'], url_path='expenses')
    def get_expenses(self, request, *args, **kwargs):
        claim_request_step = self.get_object()

        expenses = claim_request_step.claim_request_payments.select_related(
            'payment',
            'contract'
        ).order_by('id')

        page = self.paginate_queryset(expenses)
        if page is not None:
            serializer = ClaimRequestPaymentSerializer(page, many=True, context=self.get_serializer_context())
            return self.get_paginated_response(serializer.data)

        serializer = ClaimRequestPaymentSerializer(expenses, many=True, context=self.get_serializer_context())
        return Response({
                'page': page.number if page else None,
                'count': expenses.count(),
                'results': serializer.data
            })
    
    @action(detail=False, methods=['post'], url_path='step-documentation')
    def save_file(self, request):
        file = request.data.pop('document', None)
        user = request.user
        claim_request_step_id = request.data.get('claim_request_step_id', None)

        if not file:
            raise ValidationError("File is required")
        if not claim_request_step_id:
            raise ValidationError("Claim request step id is required")

        try:
            claim_request_step = ClaimRequestStep.objects.get(id=claim_request_step_id)
        except ClaimRequestStep.DoesNotExist:
            raise ValidationError("Claim request step not found")
        
        service = settings.DOCUMENT_MANAGER_SERVICES.get("billing")
        document = upload_document(
            file[0],
            'VULNERABILITY',
            'CLAIM',
            claim_request_step.id,
            claim_request_step.token,
            '',
            service,
            file[0].name.replace(' ', '_').replace('/', '_'),
            claim_request_step.created_at
        )

        ClaimRequestStepDocument.objects.create(
            claim_request_step=claim_request_step,
            file=document,
            user=user
        )

        serializer = ClaimRequestStepSerializer(claim_request_step, context=self.get_serializer_context())
        return Response(serializer.data, status=status.HTTP_200_OK)