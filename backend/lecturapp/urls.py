from django.urls import path, include
from rest_framework.routers import DefaultRouter

from billing.views.reader_alert_view import ReaderAlertAppViewSet
from notification.views.incident_view import IncidentAppViewSet
from service.views.route_position_view import RoutePositionAppViewSet
from service.views.supply_point_placement_view import SupplyPointPlacementAppViewSet
from . import views

# Create a router for ViewSets
router = DefaultRouter()
router.register(r'operators', views.ReadingOperatorViewSet, basename='reading-operator')
router.register(r'reader-alerts', ReaderAlertAppViewSet, basename='reader-alert-app')
router.register(r'supply-placements', SupplyPointPlacementAppViewSet, basename='supply-placement-app')
router.register(r'positions', RoutePositionAppViewSet, basename='route-position-app')
router.register(r'incidents', IncidentAppViewSet, basename='incident-app')

urlpatterns = [
    # Authentication endpoints
    path('auth/login/', views.AuthenticationView.as_view(), name='lecturapp-login'),
    path('auth/validate-token/', views.validate_token, name='lecturapp-validate-token'),
    path('auth/password-change/', views.password_change, name='lecturapp-password-change'),
    path('auth/logout/', views.operator_logout, name='lecturapp-logout'),
    path('auth/profile/', views.operator_profile, name='lecturapp-profile'),
    
    # Protected endpoints
    path('reading-batches/', views.reading_batches, name='lecturapp-reading-batches'),
    path('reading-batch/<int:reading_batch_id>/routes/', views.reading_batch_routes, name='lecturapp-reading-batch-routes'),
    path('reading-batch/<int:reading_batch_id>/routes/detailed/', views.reading_batch_routes_detailed, name='lecturapp-reading-batch-routes-detailed'),
    path('reading-batch/routes/detailed/status/<str:task_id>/', views.reading_batch_routes_detailed_status, name='lecturapp-reading-batch-routes-detailed-status'),
    path('sync-readings/<int:reading_batch_id>/', views.sync_readings, name='lecturapp-sync-readings'),
    # Include router URLs (all require authentication)
    path('', include(router.urls)),
] 