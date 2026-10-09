from django.conf import settings
from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.response import Response

from django_filters.rest_framework import DjangoFilterBackend

from django.db.models import Prefetch, F, CharField, Value
from django.db.models.functions import Concat


from django_filters.rest_framework import DjangoFilterBackend
from billing.permissions import GeneralPaymentPermission

from billing.filter.general_payment_sepa_filter import GeneralPaymentSepaDocumentFilter
from billing.models import GeneralPayment, GeneralPaymentSepaDocument
from billing.serializers.general_payment_sepa_serializer import GeneralPaymentSepaDocumentSaveSerializer, GeneralPaymentSepaDocumentSerializer
from documentmanager.utils.main_utils import upload_document

class GeneralPaymentSepaDocumentViewSet(viewsets.ModelViewSet):
    queryset = GeneralPaymentSepaDocument.objects.all().order_by('id')
    permission_classes = [IsAuthenticated, GeneralPaymentPermission]
    filter_backends = (DjangoFilterBackend,)
    filterset_class = GeneralPaymentSepaDocumentFilter
    search_fields = ['person_bank','file']
    ordering_fields = ['person_bank','file']
    
    def get_serializer_class(self):
        if self.request.method in ['GET']:
            return GeneralPaymentSepaDocumentSerializer
        return GeneralPaymentSepaDocumentSaveSerializer
    
    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context
    
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        general_payment = GeneralPayment.objects.get(id=request.data.get('general_payment'))
        
        # Determine person_bank
        person_bank = general_payment.IBAN if general_payment.IBAN else general_payment.company_iban
        
        # Get a valid name for the folder
        folder_name = "SEPA"
        if person_bank:
            if hasattr(person_bank, 'name') and person_bank.name:
                folder_name = person_bank.name
            elif hasattr(person_bank, 'person') and person_bank.person:
                folder_name = f"{person_bank.person.name} {person_bank.person.surname or ''}".strip()
            elif hasattr(person_bank, 'company') and person_bank.company:
                folder_name = person_bank.company.name
            elif hasattr(person_bank, 'iban') and person_bank.iban:
                folder_name = person_bank.iban
        
        folder_name = folder_name.replace(' ', '_').upper()

        if GeneralPaymentSepaDocument.objects.filter(general_payment=general_payment).exists():
            GeneralPaymentSepaDocument.objects.filter(general_payment=general_payment).delete()

        file = request.data.pop('file')
        serializer.is_valid(raise_exception=True)
        service = settings.DOCUMENT_MANAGER_SERVICES.get("contract")
        document = upload_document(file[0], 'SEPA', 'CONTRACT', general_payment.id, general_payment.token, folder_name, service, file[0].name)
        
        validated_data = serializer.validated_data
        validated_data['file'] = document 

        self.perform_create(serializer)

        instance = serializer.instance
        read_serializer = GeneralPaymentSepaDocumentSerializer(instance, context=self.get_serializer_context())
        headers = self.get_success_headers(read_serializer.data)

        return Response(read_serializer.data, status=status.HTTP_201_CREATED, headers=headers, content_type='application/json')

    def update(self, request, *args, **kwargs):
        print("updating sepa document")
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        read_serializer = GeneralPaymentSepaDocumentSerializer(instance, context=self.get_serializer_context())
        return Response(read_serializer.data, status=status.HTTP_200_OK, content_type='application/json')
    
    