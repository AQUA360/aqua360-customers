from django.urls import path
from documentmanager.views import DocumentViewSet
from lecturapp.views import (
    AuthenticationView,
    operator_logout,
    operator_profile,
    validate_token,
)
from . import views

urlpatterns = [
    # Authentication endpoints (reused from lecturapp)
    path("auth/login/", AuthenticationView.as_view(), name="got-login"),
    path("auth/logout/", operator_logout, name="got-logout"),
    path("auth/profile/", operator_profile, name="got-profile"),
    path("auth/validate-token/", validate_token, name="got-validate-token"),
    # Order management endpoints
    path("orders/", views.operator_orders, name="got-orders"),
    path("orders-list/", views.operator_orders_list, name="got-orders-list"),
    path("exploitations/", views.exploitations, name="got-exploitations"),
    # Lecture User Management
    path("orders/lecture-users/", views.order_lecture_users, name="got-lecture-users"),
    # View Document
    path("orders/view-document/<int:pk>/", views.view_document, name="view_document"),
    # Order Detail
    path("orders/<int:order_id>/", views.order_detail, name="got-order-detail"),
    # Get Order Form (dynamic form structure for this order type)
    path("orders/<int:order_id>/form/", views.get_order_form, name="got-order-form"),
    # Get Order Form (dynamic form structure for this order type)
    path("orders/report/", views.get_orders_report, name="got-order-report"),
    # Assign Lecture User to Order
    path(
        "orders/<int:order_id>/assign-lecture-user/",
        views.assign_lecture_user,
        name="got-assign-lecture-user",
    ),
    # Add Observation to Order
    path(
        "orders/<int:order_id>/add-observation/",
        views.add_order_observation,
        name="got-order-add-observation",
    ),
    # Order Reports
    path(
        "orders/<int:order_id>/reports/",
        views.order_report,
        name="got-order-report-detail",
    ),
    # Add Report to Order
    path(
        "orders/<int:order_id>/add-report/",
        views.add_order_report,
        name="got-order-add-report",
    ),
    # Upload Form Photo (for dynamic forms with photo fields)
    path(
        "orders/<int:order_id>/upload-form-photo/",
        views.upload_form_photo,
        name="got-order-upload-form-photo",
    ),
    # Remove Form Photo (delete uploaded photo before report creation)
    path(
        "orders/<int:order_id>/remove-form-photo/",
        views.remove_form_photo,
        name="got-order-remove-form-photo",
    ),
    # Add Document to Order Report
    path(
        "orders/<int:order_id>/reports/<int:report_id>/add-document/",
        views.add_order_report_document,
        name="got-order-add-report-document",
    ),
    # Finalize Order
    path(
        "orders/<int:order_id>/finalize/",
        views.finalize_order,
        name="got-order-finalize",
    ),
]
