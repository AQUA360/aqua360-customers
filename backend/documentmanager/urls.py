from django.urls import include, path
from rest_framework import routers
from .views import DocumentViewSet, DocumentSignViewSet
from .views_export.export_job_view import ExportJobViewSet

router = routers.DefaultRouter()
router.register(r'document', DocumentViewSet)
router.register(r'document-sign', DocumentSignViewSet)
# Cua general de descàrregues de l'usuari (ExportJob)
router.register(r'export-job', ExportJobViewSet, basename='export-job')

urlpatterns = [
    path('', include(router.urls)),
    path('view-document/<int:pk>/', DocumentViewSet.as_view({'get': 'view_document'}), name='view_document'),
    path('upload-document/', DocumentViewSet.as_view({'post': 'upload_document'}), name='upload_document'),
    path('download-documents/', DocumentViewSet.as_view({'post': 'download_documents'}), name='download_documents'),
    path('download-single-pdf-document/', DocumentViewSet.as_view({'post': 'download_single_pdf_document'}), name='download_single_pdf_document'),
    path('delete-document/', DocumentViewSet.as_view({'post': 'delete_documents'}), name='delect_documents'),
    path('document-signs-by-contract/', DocumentSignViewSet.as_view({'get': 'by_contract'}), name='document_signs_by_contract'),
    path('document-signs-all/', DocumentSignViewSet.as_view({'get': 'all_documents'}), name='document_signs_all'),
    path('document-sign-download/<int:pk>/', DocumentSignViewSet.as_view({'get': 'download'}), name='document_sign_download'),
]
