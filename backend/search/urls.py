from django.urls import path, include
from rest_framework import routers
from .view import search_results
from search.views.search_history_view import HistoryViewSet

router = routers.DefaultRouter()

router.register(r'history', HistoryViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path('results/', search_results, name='search_results'),
]
