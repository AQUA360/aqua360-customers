from django.urls import include, path
from rest_framework import routers

from documentmanager.views_export.generic_export_view import GenericExportView

from .views import (
    CustomAuthToken,
    UserViewSet,
    GroupViewSet,
    UserPermissionsView
)

router = routers.DefaultRouter()
router.register(r'user', UserViewSet)
router.register(r'group', GroupViewSet)
router.register(r'permission', UserPermissionsView, basename='user-permissions')

urlpatterns = [
    path('login/', CustomAuthToken.as_view(), name='login'),
    # Accepta també POST sense barra final: sense aquest patró,
    # APPEND_SLASH (CommonMiddleware) retorna 301 i els clients HTTP
    # re-envien la redirecció com a GET i perden el cos, fallant l'auth.
    # Mateixa vista; nom distint perquè `reverse('login')` no canvia.
    path('login', CustomAuthToken.as_view(), name='login-no-slash'),
    # Han d'anar abans d'`include(router.urls)`: el router registra `<recurs>/<pk>/`
    # amb un patró de pk genèric que, si es col·loca abans, capturaria "export" com a pk.
    path('group/export/', GenericExportView.as_view(entity='group'), name='group-export'),
    path('user/export/', GenericExportView.as_view(entity='user'), name='user-export'),
    path('', include(router.urls)),
]