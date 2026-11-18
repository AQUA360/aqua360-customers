from django.conf import settings
from PIL import Image, UnidentifiedImageError
from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.response import Response

from django_filters.rest_framework import DjangoFilterBackend

from django.db.models import Prefetch, F, CharField, Value
from django.db.models.functions import Concat

from django_filters.rest_framework import DjangoFilterBackend

from documentmanager.utils.main_utils import upload_document
from fraud.filters.fraud_image_filter import FraudImageFilter
from fraud.models import FraudImage, FraudReport
from fraud.serializers.value_objects_serializer import FraudImageSerializer
from fraud.permissions import FraudPermission

# Mida màxima d'una imatge de frau. Els nginx dels desplegaments accepten 20M, així que talla el backend.
MAX_FRAUD_IMAGE_BYTES = 10 * 1024 * 1024
# Formats acceptats, comprovats amb la imatge real (no amb l'extensió ni el content-type del navegador).
ALLOWED_FRAUD_IMAGE_FORMATS = {'JPEG', 'PNG'}


def _is_valid_image(file):
    """Cert si el fitxer és realment una imatge JPEG o PNG que es pot descodificar sencera."""
    try:
        file.seek(0)
        with Image.open(file) as image:
            if image.format not in ALLOWED_FRAUD_IMAGE_FORMATS:
                return False
            image.verify()
        # verify() no descodifica els píxels: cal tornar a obrir el fitxer i carregar-lo per
        # rebutjar imatges truncades. El límit de píxels de Pillow evita les bombes de descompressió.
        file.seek(0)
        with Image.open(file) as image:
            image.load()
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError, SyntaxError, ValueError):
        return False
    finally:
        file.seek(0)
    return True


class FraudImageViewSet(viewsets.ModelViewSet):
    queryset = FraudImage.objects.all().order_by('id')
    permission_classes = [IsAuthenticated, FraudPermission]
    filter_backends = (DjangoFilterBackend,)
    filterset_class = FraudImageFilter
    search_fields = ['type','file']
    ordering_fields = ['type','file']
    
    def get_serializer_class(self):
        return FraudImageSerializer
    
    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context
    
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        
        try:
            report_id = int(request.data.get('id'))
        except (TypeError, ValueError):
            return Response({'detail': 'Invalid fraud report id'}, status=status.HTTP_400_BAD_REQUEST)
        fraud_report = FraudReport.objects.filter(id=report_id, fraud__isnull=False).select_related('fraud').first()
        if fraud_report is None:
            return Response({'detail': 'Fraud report not found'}, status=status.HTTP_404_NOT_FOUND)

        file = request.FILES.get('file')
        if file is None:
            return Response({'detail': 'Missing image file'}, status=status.HTTP_400_BAD_REQUEST)
        if file.size > MAX_FRAUD_IMAGE_BYTES:
            return Response({'detail': 'Image too large'}, status=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE)
        if not _is_valid_image(file):
            return Response({'detail': 'Invalid image'}, status=status.HTTP_400_BAD_REQUEST)

        request.data.pop('id', None)
        request.data.pop('file', None)
        
        serializer.is_valid(raise_exception=True)
        
        service = settings.DOCUMENT_MANAGER_SERVICES.get("fraud")
        document = upload_document(file, fraud_report.fraud.token, 'FRAUD', fraud_report.id, fraud_report.token, '', service, file.name)
        validated_data = serializer.validated_data
        validated_data['fraud_report'] = fraud_report
        validated_data['file'] = document 
        
        self.perform_create(serializer)
        instance = serializer.instance
        read_serializer = FraudImageSerializer(instance, context=self.get_serializer_context())
        headers = self.get_success_headers(read_serializer.data)
        return Response(read_serializer.data, status=status.HTTP_201_CREATED, headers=headers, content_type='application/json')

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        instance = serializer.instance
        read_serializer = FraudImageSerializer(instance, context=self.get_serializer_context())
        return Response(read_serializer.data, status=status.HTTP_200_OK, content_type='application/json')