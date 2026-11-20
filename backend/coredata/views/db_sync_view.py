from django.http import Http404
from rest_framework import serializers, status
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from auth.roles import ROLE_ADMIN, ROLE_SUPERUSER, get_user_role
from coredata.utils import db_sync_service


class IsAdminRole(BasePermission):
    def has_permission(self, request, view):
        return get_user_role(request.user) in (ROLE_ADMIN, ROLE_SUPERUSER)


class DbSyncSettingsSerializer(serializers.Serializer):
    nightly_enabled = serializers.BooleanField()


class DbSyncView(APIView):
    """Sincronització nocturna de dades de prod a test (només test/staging/local i admins).

    - GET: si està activada (i qui l'ha desactivada i quan).
    - PATCH `{"nightly_enabled": bool}`: l'activa o la desactiva.

    Fora d'aquests entorns l'endpoint no existeix (404), sigui qui sigui l'usuari.
    """

    permission_classes = [IsAuthenticated, IsAdminRole]

    def initial(self, request, *args, **kwargs):
        if not db_sync_service.is_test_environment():
            raise Http404
        super().initial(request, *args, **kwargs)

    def get(self, request):
        return Response(db_sync_service.get_status())

    def patch(self, request):
        serializer = DbSyncSettingsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            data = db_sync_service.set_nightly_enabled(
                serializer.validated_data["nightly_enabled"], request.user
            )
        except db_sync_service.DbSyncError as error:
            return Response({"code": error.code}, status=status.HTTP_409_CONFLICT)
        return Response(data)
