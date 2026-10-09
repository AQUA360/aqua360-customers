import os
import zipfile
import io
from io import BytesIO
from django.conf import settings
from django.http import HttpResponse, Http404
from rest_framework import viewsets, status
from rest_framework.decorators import action, api_view
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from rest_framework.response import Response
from datetime import datetime
from pydantic import ValidationError

from service.models import Exploitation
from service.serializers.company_serializer import CompanySerializer
from .models import Document, DocumentSign
from .serializers import DocumentSerializer, DocumentSignSerializer
from .utils.document_sign_config import is_document_sign_enabled

from rest_framework import viewsets
from rest_framework.response import Response
from rest_framework.decorators import action
from .models import Document
from .serializers import DocumentSerializer
from .utils.main_utils import *
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
import threading

from PyPDF2 import PdfMerger
class DocumentViewSet(viewsets.ModelViewSet):
    queryset = Document.objects.all()
    serializer_class = DocumentSerializer
    permission_classes = [IsAuthenticated]

    
    @action(detail=False, methods=['post'])
    def upload_document(self, request):
        file = request.FILES['file']
        service = request.data.get('service')
        entity = request.data.get('entity')
        field = request.data.get('field')
        entity_id = request.data.get('entity_id')
        entity_name = request.data.get('entity_name')
        document_name = request.data.get('document_name')

        document = upload_document(file, entity, field, entity_id, entity_name, service, document_name)

        serializer = self.get_serializer(document)
        return Response({"document": serializer.data})
        """ if service == 'aws':
            return Response({"presigned_url": document.location_url, "document": serializer.data})
        else:
            return Response({"document": serializer.data}) """

    @action(detail=True, methods=['get'])
    def view_document(self, request, pk=None):
        document = self.get_object()
        download_info = download_document(document)
        if download_info and isinstance(download_info, HttpResponse):
            download_info['Access-Control-Expose-Headers'] = 'Content-Disposition'
        return download_info

        """ try:
            if hasattr(download_info, 'getvalue'):
                file_bytes = download_info.getvalue()
            elif hasattr(download_info, 'content'):
                file_bytes = download_info.content
            else:
                file_bytes = download_info
        except Exception:
            return download_info

        temp_rel_path = f"tmp/documents/{datetime.now().strftime('%Y%m%d')}_{document.document_name.replace('/','')}"
        saved_path = default_storage.save(temp_rel_path, ContentFile(file_bytes))
        file_url = request.build_absolute_uri(default_storage.url(saved_path))

        def _delete_later(path: str, delay_seconds: int = 100) -> None:
            def _run():
                try:
                    default_storage.delete(path)
                except Exception:
                    pass
            t = threading.Timer(delay_seconds, _run)
            t.daemon = True
            t.start()

        _delete_later(saved_path, delay_seconds=20)

        return Response({"file_url": file_url}) """
    
    @action(detail=False, methods=['post'])
    def delete_documents(self, request):
        print("deleting documents")
        print(request.data)
        
        doc_ids = request.data['doc_ids']
        print(doc_ids)
        deleted_count = 0
        for doc_id in doc_ids:
            try:
                document = Document.objects.get(id=doc_id)
                document.is_active = False
                document.save()
                """ delete_document(document)  
                document.delete()   """
                deleted_count += 1
            except Document.DoesNotExist:
                print(f"Document with ID {doc_id} not found.")
            except Exception as e:
                print(f"Error deleting document with ID {doc_id}: {e}")
        
        if deleted_count == len(doc_ids):
            return Response({"success": f"Successfully deleted {deleted_count} documents."}, status=status.HTTP_200_OK)
        else:
            return Response({"message": f"Deleted {deleted_count} documents. Some documents could not be deleted."}, status=status.HTTP_207_MULTI_STATUS)

    
    @action(detail=False, methods=['post'])
    def download_documents(self, request):
        doc_ids = request.data['doc_ids']
        try:
            service = None
            documents = Document.objects.filter(id__in=doc_ids).order_by('id')
            if not documents.exists():
                return Response(
                    {"error": "No documents found with the provided IDs"},
                    status=status.HTTP_404_NOT_FOUND,
                )
            
            all_cloud = all(document.service in ['aws', 'azure'] for document in documents)
            if all_cloud:
                service = documents[0].service

            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                if all_cloud:
                    files = download_multiple_documents(doc_ids, service)
                    for filename, file_content in files:
                        zip_file.writestr(filename, file_content)
                else:
                    for document in documents:
                        document_content = download_document(document)
                        if not document_content:
                            return Response(
                                {"error": f"Failed to download document with id {document.id}"},
                                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            )
                        try:
                            file_content = document_content.getvalue()
                        except AttributeError:
                            file_content = document_content.content

                        zip_file.writestr(document.document_name.replace('/','_'), file_content)

            response = HttpResponse(
                zip_buffer.getvalue(), content_type='application/x-zip-compressed'
            )
            response['Content-Disposition'] = 'attachment; filename="documents.zip"'
            response['Access-Control-Expose-Headers'] = 'Content-Disposition'
            
            return response

        except Exception as e:
            return Response(
                {"error": f"Error processing download: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=False, methods=['post'])
    def download_single_pdf_document(self, request):
        doc_ids = request.data['doc_ids']
        print("doc_ids")
        print(doc_ids)
        try:
            service = None
            documents = Document.objects.filter(id__in=doc_ids)
            if not documents.exists():
                return Response(
                    {"error": "No documents found with the provided IDs"},
                    status=status.HTTP_404_NOT_FOUND,
                )
            
            merger = PdfMerger()
            
            all_cloud = all(document.service in ['aws', 'azure'] for document in documents)
            if all_cloud:
                print("all_cloud")
                service = documents[0].service
            if all_cloud:
                files = download_multiple_documents(doc_ids, service)
                for filename, file_content in files:
                    merger.append(BytesIO(file_content))
            else:
                for document in documents:
                    document_content = download_document(document)
                    if not document_content:
                        return Response(
                            {"error": f"Failed to download document with id {document.id}"},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        )
                    try:
                        file_content = document_content.getvalue()
                    except AttributeError:
                        file_content = document_content.content
                    merger.append(BytesIO(file_content))
            
            merged_pdf_buffer = BytesIO()
            merger.write(merged_pdf_buffer)
            merger.close()
            
            exploitation = Exploitation.objects.filter(is_active=True).first()
            company = CompanySerializer(exploitation.company).data
            
            signed_pdf_buffer = sign_pdf(merged_pdf_buffer, company, '', '')
            
            response = HttpResponse(
                signed_pdf_buffer.getvalue(), content_type='application/pdf'
            )
            response['Content-Disposition'] = 'attachment; filename="documents.pdf"'
            response['Access-Control-Expose-Headers'] = 'Content-Disposition'
            
            return response
        except Exception as e:
            return Response(
                {"error": f"Error processing download: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
    
class DocumentSignViewSet(viewsets.ModelViewSet):
    queryset = (
        DocumentSign.objects
        .select_related('contract', 'contract_request', 'contract_file', 'contract_file_signed')
        .order_by('-created_at')
    )
    serializer_class = DocumentSignSerializer
    permission_classes = [IsAuthenticated, DjangoModelPermissions]

    def perform_create(self, serializer):
        # L'alta només crea el registre (Pending). L'enviament a Aqua360 és POST .../send/.
        serializer.save()

    def destroy(self, request, *args, **kwargs):
        # Aqua360 Sign no documenta cap cancel·lació de sessió. Esborrem el registre
        # local; un callback posterior d'aquesta referència respondrà 404.
        document_sign = self.get_object()
        document_sign.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=['post'])
    def send(self, request, pk=None):
        from integrations.outbound.signing.exceptions import SigningApiError
        from integrations.outbound.signing.services import create_document_sign_session

        if not is_document_sign_enabled():
            return Response(
                {"error": "La signatura de documents (DocumentSign) no està habilitada"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        document_sign = self.get_object()
        force = bool(request.data.get('force', False))
        callback_url = request.data.get('callback_url') or None

        try:
            result = create_document_sign_session(
                document_sign, callback_url=callback_url, force=force
            )
        except SigningApiError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        document_sign.refresh_from_db()
        serializer = self.get_serializer(document_sign, context={'request': request})
        return Response({"result": result, "document_sign": serializer.data})

    @action(detail=True, methods=['post'], url_path='retrieve', url_name='retrieve')
    def retrieve_signed(self, request, pk=None):
        """
        Consulta Aqua360 si la signatura ja s'ha completat. Només JSON:
        si ja està firmada, desa el PDF i passa a Signed; si no, no canvia res
        i no retorna el PDF original.
        """
        from integrations.outbound.signing.exceptions import SigningApiError
        from integrations.outbound.signing.polling import retrieve_signed_document

        if not is_document_sign_enabled():
            return Response(
                {"error": "La signatura de documents (DocumentSign) no està habilitada"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        document_sign = self.get_object()
        already_signed = (
            document_sign.status == DocumentSign.STATUS_SIGNED
            and document_sign.contract_file_signed_id
        )
        can_ask = document_sign.status in (
            DocumentSign.STATUS_SENDED,
            DocumentSign.STATUS_EXPIRED,
        ) or (
            document_sign.status == DocumentSign.STATUS_SIGNED
            and not document_sign.contract_file_signed_id
        )
        if already_signed:
            serializer = self.get_serializer(document_sign, context={'request': request})
            return Response(serializer.data)
        if not can_ask:
            return Response(
                {
                    "error": "El document encara no s'ha enviat a signar.",
                    "status": document_sign.status,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            retrieve_signed_document(document_sign)
        except SigningApiError as exc:
            document_sign.refresh_from_db()
            return Response(
                {
                    "error": str(exc),
                    "status": document_sign.status,
                    "error_report": document_sign.error_report,
                },
                status=status.HTTP_502_BAD_GATEWAY,
            )

        document_sign.refresh_from_db()
        serializer = self.get_serializer(document_sign, context={'request': request})
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def by_contract(self, request):
        contract_id = request.query_params.get('contract_id')
        contract_request_id = request.query_params.get('contract_request_id')
        if not contract_id and not contract_request_id:
            return Response(
                {"error": "contract_id or contract_request_id query param is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        document_signs = self.get_queryset()
        if contract_id:
            document_signs = document_signs.filter(contract_id=contract_id)
        else:
            document_signs = document_signs.filter(contract_request_id=contract_request_id)

        serializer = self.get_serializer(document_signs, many=True, context={'request': request})
        return Response({"document_signs": serializer.data})

    @action(detail=False, methods=['get'])
    def all_documents(self, request):
        document_signs = self.get_queryset()

        status_param = request.query_params.get('status')
        if status_param:
            document_signs = document_signs.filter(status=status_param)

        serializer = self.get_serializer(document_signs, many=True, context={'request': request})
        return Response({"document_signs": serializer.data})

    @action(detail=True, methods=['get'])
    def download(self, request, pk=None):
        document_sign = self.get_object()

        if (
            document_sign.status != DocumentSign.STATUS_SIGNED
            or not document_sign.contract_file_signed_id
        ):
            return Response(
                {"error": "El document signat encara no està disponible"},
                status=status.HTTP_404_NOT_FOUND,
            )

        document = document_sign.contract_file_signed
        try:
            download_info = download_document(document)
        except Http404:
            return Response(
                {"error": "El document signat encara no està disponible"},
                status=status.HTTP_404_NOT_FOUND,
            )
        if not isinstance(download_info, HttpResponse):
            return Response(
                {"error": "El document signat encara no està disponible"},
                status=status.HTTP_404_NOT_FOUND,
            )

        filename = (document.document_name or f"document-sign-{document_sign.id}.pdf").replace('"', '')
        download_info['Content-Type'] = 'application/pdf'
        download_info['Content-Disposition'] = f'attachment; filename="{filename}"'
        download_info['Access-Control-Expose-Headers'] = 'Content-Disposition'
        return download_info


def get_all_documents(doc_ids):
    try:
        service = None
        documents = Document.objects.filter(id__in=doc_ids)
        if not documents.exists():
            return None
        
        all_cloud = all(document.service in ['aws', 'azure'] for document in documents)
        if all_cloud:
            service = documents[0].service
            return download_multiple_documents(doc_ids, service)
        
        files = []
        for document in documents:
            document_content = download_document(document)
            if not document_content:
                continue
            
            try:
                file_content = document_content.getvalue()
            except AttributeError:
                file_content = document_content.content
            
            files.append((document.document_name, file_content))
        
        return files

    except Exception as e:
        print(f"Error processing download: {str(e)}")
        return None
