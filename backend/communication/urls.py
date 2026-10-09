from django.urls import include, path
from rest_framework import routers

from documentmanager.views_export.generic_export_view import GenericExportView

from communication.views.communication_type_view import CommunicationUseTypeViewSet
from communication.views.communication_view import CommunicationViewSet
from communication.views.communication_status_view import CommunicationStatusViewSet
from communication.views.communication_observation_view import CommunicationObservationViewSet
from communication.views.communication_process_view import CommunicationProcessViewSet
from communication.views.communication_process_status_view import CommunicationProcessStatusViewSet
from communication.views.communication_process_observation_view import CommunicationProcessObservationViewSet
from communication.views.communication_file_view import CommunicationFileViewSet
from communication.views.message_view import MessageViewSet
from communication.views.message_type_view import MessageTypeViewSet
from communication.views.message_type_template_view import MessageTypeTemplateViewSet
from communication.views.message_template_view import MessageTemplateViewSet
from communication.views.message_origin_view import MessageOriginViewSet
from communication.views.manage_communication_process_view import ManageCommunicationProcessViewSet
from communication.views.manage_send_communications_view import ManageSendCommunicationsViewSet
from communication.views.communication_generate_files_view import CommunicationGenerateFilesViewSet
from communication.views.sms_callback_view import SmsCallbackView

router = routers.DefaultRouter()
router.register(r'communication', CommunicationViewSet)
router.register(r'communication-status', CommunicationStatusViewSet)
router.register(r'communication-use-type', CommunicationUseTypeViewSet)
router.register(r'communication-observation', CommunicationObservationViewSet)
router.register(r'communication-process', CommunicationProcessViewSet)
router.register(r'communication-process-status', CommunicationProcessStatusViewSet)
router.register(r'communication-process-observation', CommunicationProcessObservationViewSet)
router.register(r'communication-file', CommunicationFileViewSet)
router.register(r'message', MessageViewSet)
router.register(r'message-type', MessageTypeViewSet)
router.register(r'message-type-template', MessageTypeTemplateViewSet)
router.register(r'message-template', MessageTemplateViewSet)
router.register(r'message-origin', MessageOriginViewSet)


urlpatterns = [
    # Han d'anar abans d'`include(router.urls)`: el router registra `<recurs>/<pk>/`
    # amb un patró de pk genèric que, si es col·loca abans, capturaria "export" com a pk.
    path('communication-process/export/', GenericExportView.as_view(entity='communication_process'), name='communication-process-export'),
    path('message-template/export/', GenericExportView.as_view(entity='message_template'), name='message-template-export'),
    path('', include(router.urls)),
    path('communication-process/get-data', ManageCommunicationProcessViewSet.as_view(http_method_names=['post']), name='manage-claims'),
    path('communication-generate-files', CommunicationGenerateFilesViewSet.as_view(http_method_names=['post']), name='communication-generate-files'),
    path('communication-generate-files/status/<str:task_id>/', CommunicationGenerateFilesViewSet.as_view(http_method_names=['get']), name='communication-generate-files-status'),
    path('send-communications/', ManageSendCommunicationsViewSet.as_view(http_method_names=['post']), name='send-communications'),
    path('sms-callback/', SmsCallbackView.as_view(), name='sms-callback'),
    path('communication-process/<int:id>/send-messages/', ManageSendCommunicationsViewSet.as_view(http_method_names=['get']), name='send-messages'),
]