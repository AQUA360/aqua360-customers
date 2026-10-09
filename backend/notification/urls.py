from django.urls import include, path
from rest_framework import routers

from notification.views.calendar_task_view import CalendarTaskViewSet
from notification.views.general_note_view import GeneralNoteViewSet
from notification.views.incident_documentation_view import IncidentDocumentationViewSet
from notification.views.incident_view import IncidentViewSet
from notification.views.incident_report_view import IncidentReportViewSet
from notification.views.incident_status_view import IncidentStatusViewSet
from notification.views.incident_type_view import IncidentTypeViewSet
from notification.views.incident_observation_view import IncidentObservationViewSet
from notification.views.notification_view import NotificationViewSet

from .views import *

router = routers.DefaultRouter()

router.register(r'notification', NotificationViewSet)
router.register(r'calendar-task', CalendarTaskViewSet)
router.register(r'general-note', GeneralNoteViewSet)

router.register(r'incident', IncidentViewSet)
router.register(r'incident-report', IncidentReportViewSet)
router.register(r'incident-documentation', IncidentDocumentationViewSet)
router.register(r'incident-status', IncidentStatusViewSet)
router.register(r'incident-type', IncidentTypeViewSet)
router.register(r'incident-observation', IncidentObservationViewSet)

urlpatterns = [
    path('', include(router.urls)),
]