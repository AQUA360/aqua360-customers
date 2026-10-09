from django.db import transaction
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from rest_framework.response import Response
from rest_framework import status
from contract.models import ACADocument, ACADocumentChange
from contract.serializers.aca_document_serializer import ACADocumentSerializer
from ..utils.aca_document_service import process_document
from ..utils.aca_exchange_file_parser import details_to_changes, looks_like_exchange_file, parse_exchange_file
from datetime import datetime
from auth.permissions import PermissionManager
from contract.permissions import ContractPermission

ACA_DOCUMENT_TYPES = {'AT': 'Ampliació de trams', 'CS': 'Canon Social'}


class ACADocumentViewSet(viewsets.ModelViewSet):
    queryset = ACADocument.objects.all().order_by('token')
    serializer_class = ACADocumentSerializer
    permission_classes = [IsAuthenticated, ContractPermission]
    search_fields = ['token', 'name']
    ordering_fields = ['token', 'name']
    
    @action(detail=False, methods=['get'], url_path='permissions')
    def permissions(self, request):
        pk = request.query_params.get('id')
        if pk:
            from django.contrib.auth.models import Group
            user_permissions = PermissionManager.get_model_permissions(request.user, 'auth', 'group')
            if not user_permissions['can_view'] or not user_permissions['can_change'] or not request.user.is_superuser:
                return Response( None, status=status.HTTP_403_FORBIDDEN )
            group = Group.objects.filter(id=pk).first()
            if not group:
                return Response( None, status=status.HTTP_404_NOT_FOUND )
            group_permissions = PermissionManager.get_model_group_permissions(group, 'acadocument')
            return Response(group_permissions, status=status.HTTP_200_OK)
        permissions = PermissionManager.get_model_permissions(request.user, 'acadocument', 'contract')
        return Response(permissions, status=status.HTTP_200_OK)
    
    def get_permissions(self):
        if self.action == 'permissions':
            return [IsAuthenticated()]
        return super().get_permissions()

    def create(self, request, *args, **kwargs):
        serializer = ACADocumentSerializer(data=request.data)
        if serializer.is_valid():
            try:
                # Get the uploaded file
                uploaded_file = serializer.validated_data['file']
                name = uploaded_file.name

                # Nom del fitxer segons l'ACA: [TA-]{AT|CS}CCCCaammddXnnn.txt (els tancaments
                # que envia l'ACA porten el prefix "TA-"; "TA_" és el que es feia servir abans).
                closing = name[:3].upper() in ('TA-', 'TA_')
                main_name = name[3:] if closing else name

                raw = uploaded_file.read()
                uploaded_file.seek(0)

                if looks_like_exchange_file(raw):
                    # Fitxer d'intercanvi de 350 posicions: la capçalera mana sobre el nom.
                    parsed = parse_exchange_file(raw)
                    header = parsed['header']
                    application = header['application'] or main_name[:2]
                    supplier = header['supplier_code']
                    date = header['generation_date']
                    changes_data = details_to_changes(parsed['details'], application)
                    if changes_data and all(change['closing'] for change in changes_data):
                        closing = True
                else:
                    application = main_name[:2]
                    supplier = main_name[2:6]
                    date = None
                    changes_data = process_document(uploaded_file)

                doc_type = ACA_DOCUMENT_TYPES.get(application.upper(), 'Desconegut')
                if not date:
                    try:
                        date = datetime.strptime(main_name[6:12], '%y%m%d').date()
                    except ValueError:
                        date = None
                source = 'ACA' if main_name[12:13].upper() == 'A' else 'Entitat subministradora'
                number = main_name[13:16]

                with transaction.atomic():
                    # Create the ACADocument record with additional fields
                    doc = serializer.save(
                        name=name,
                        type=doc_type,
                        supplier=supplier,
                        date=date,
                        source=source,
                        number=number,
                        closing=closing,
                        is_active=True
                    )

                    # Create related ACADocumentChange records
                    for change_data in changes_data:
                        ACADocumentChange.objects.create(
                            aca_document=doc,  # Link to the newly created ACADocument
                            **change_data       # Unpack dictionary data for fields
                        )

                return Response({"data": ACADocumentSerializer(doc).data}, status=status.HTTP_201_CREATED)

            except Exception as e:
                return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
