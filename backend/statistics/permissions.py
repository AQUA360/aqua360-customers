from rest_framework import permissions
from rest_framework import exceptions
from billing.permissions import BillingPermission, PaymentPermission
from order.permissions import OrderPermission

class StatisticsPermission(permissions.BasePermission):
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            raise exceptions.MethodNotAllowed(request.method)
        
        order_permission = OrderPermission().has_permission(request, view)
        payment_permission = PaymentPermission().has_permission(request, view)
        billing_permission = BillingPermission().has_permission(request, view)
        
        return order_permission or payment_permission or billing_permission

class ReportViewPermission(permissions.BasePermission):
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            raise exceptions.MethodNotAllowed(request.method)
        
        order_view_permission = request.user.has_perm('order.view_order')
        payment_view_permission = request.user.has_perm('billing.view_payment')
        billing_view_permission = request.user.has_perm('billing.view_billing')
        
        return order_view_permission or payment_view_permission or billing_view_permission