from django.urls import path

from .views import DashboardCardDataView, DashboardCardListView, DashboardLayoutView, SidebarLayoutView

urlpatterns = [
    path('layout/', DashboardLayoutView.as_view(), name='dashboard-layout'),
    path('sidebar/', SidebarLayoutView.as_view(), name='dashboard-sidebar'),
    path('cards/', DashboardCardListView.as_view(), name='dashboard-cards'),
    path('cards/<str:key>/data/', DashboardCardDataView.as_view(), name='dashboard-card-data'),
]
