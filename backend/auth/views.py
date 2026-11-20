from rest_framework import viewsets, generics
from rest_framework.decorators import action
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.authtoken.views import ObtainAuthToken
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.throttling import ScopedRateThrottle
from axes.handlers.proxy import AxesProxyHandler

from django.shortcuts import render
from django.utils.translation import gettext_lazy as _
from django.contrib.auth.models import Group, User, Permission

from auth.filters import UserFilter, GroupFilter
from auth.roles import CANONICAL_SUPERUSER_USERNAME, get_user_role, is_canonical_superuser
from auth.serializers import GroupSerializer, UserSerializer, PermissionSerializer
from auth.permissions import PermissionManager
from coredata.permissions import can_edit_config_project


WRITE_ACTIONS = ('create', 'update', 'partial_update', 'destroy')


def check_user_management_permission(request, action, resource):
    """Usuaris i grups: GET obert a autenticats (selecció); escriptura només superusuari.

    La UI de gestió (settings) segueix gated per `view_user` al front.
    """
    if action in WRITE_ACTIONS and not is_canonical_superuser(request.user):
        raise PermissionDenied(f"Only a superuser can modify {resource}.")


def check_superuser_target(user, target):
    """Només el superusuari canònic pot modificar o eliminar un altre superusuari."""
    if target.is_superuser and not is_canonical_superuser(user):
        raise PermissionDenied("You are not allowed to modify a superuser")


class LoginIPThrottle(ScopedRateThrottle):
    """Límit per IP sempre, també si la petició porta un token vàlid (no per usuari)."""

    def get_cache_key(self, request, view):
        return self.cache_format % {'scope': self.scope, 'ident': self.get_ident(request)}


class CustomAuthToken(ObtainAuthToken):
    # Límit d'intents per IP (scope "login"); el bloqueig per usuari el fa django-axes
    throttle_classes = [LoginIPThrottle]
    throttle_scope = 'login'
    # Si s'informa, només els usuaris d'aquest grup obtenen token (logins d'integracions)
    required_group = None

    def post(self, request, *args, **kwargs):
        # Usuari bloquejat per massa intents fallits: 429 explícit (sense validar la contrasenya)
        credentials = {'username': request.data.get('username')}
        if not AxesProxyHandler.is_allowed(request._request, credentials):
            return Response(
                {'detail': 'Too many failed login attempts. Try again later.'},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )
        serializer = self.serializer_class(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)

        user = serializer.validated_data['user']
        if self.required_group and not user.groups.filter(name=self.required_group).exists():
            # Mateixa resposta que amb credencials incorrectes: no revela si l'usuari existeix
            raise ValidationError(
                {'non_field_errors': [_('Unable to log in with provided credentials.')]},
                code='authorization',
            )
        token, created = Token.objects.get_or_create(user=user)

        return Response({
            'username': user.username,
            'token': token.key
        })
    

class UserViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows users to be viewed or edited.
    """
    queryset = User.objects.all().order_by('-date_joined')
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]
    filterset_class = UserFilter

    def get_permissions(self):
        if self.action == 'permissions':
            return [IsAuthenticated()]
        check_user_management_permission(self.request, self.action, "users")
        return super().get_permissions()

    def update(self, request, *args, **kwargs):
        # Abans de validar les dades: si no pot tocar el superusuari, 403 (no errors de contrasenya)
        check_superuser_target(request.user, self.get_object())
        return super().update(request, *args, **kwargs)

    def perform_destroy(self, instance):
        if instance.username == CANONICAL_SUPERUSER_USERNAME:
            raise PermissionDenied(
                f"The '{CANONICAL_SUPERUSER_USERNAME}' account cannot be deleted"
            )
        check_superuser_target(self.request.user, instance)
        super().perform_destroy(instance)

    @action(detail=False, methods=['get'], url_path='permissions')
    def permissions(self, request):
        pk = request.query_params.get('id')
        if pk:
            user_permissions = PermissionManager.get_model_permissions(request.user, 'group', 'auth')
            if (
                not user_permissions['can_view']
                or not user_permissions['can_change']
                or not is_canonical_superuser(request.user)
            ):
                return Response( None, status=status.HTTP_403_FORBIDDEN )
            group = Group.objects.filter(id=pk).first()
            if not group:
                return Response( None, status=status.HTTP_404_NOT_FOUND )
            group_permissions = PermissionManager.get_model_group_permissions(group, 'user')
            return Response(group_permissions, status=status.HTTP_200_OK)
        permissions = PermissionManager.get_model_permissions(request.user, 'user', 'auth')
        return Response(permissions, status=status.HTTP_200_OK)


class GroupViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows groups to be viewed or edited.
    """
    queryset = Group.objects.all().order_by('name')
    serializer_class = GroupSerializer
    permission_classes = [IsAuthenticated]
    filterset_class = GroupFilter
    
    def get_permissions(self):
        if self.action == 'permissions':
            return [IsAuthenticated()]
        check_user_management_permission(self.request, self.action, "groups")
        return super().get_permissions()

    def perform_destroy(self, instance):
        # Mateix criteri que create/update del GroupSerializer.
        user = self.request.user
        if not is_canonical_superuser(user) or not user.has_perm('auth.delete_group'):
            raise PermissionDenied("You are not allowed to delete this group")
        super().perform_destroy(instance)

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context
    
    @action(detail=False, methods=['get'], url_path='permissions')
    def permissions(self, request):
        pk = request.query_params.get('id')
        if pk:
            user_permissions = PermissionManager.get_model_permissions(request.user, 'group', 'auth')
            if (
                not user_permissions['can_view']
                or not user_permissions['can_change']
                or not is_canonical_superuser(request.user)
            ):
                return Response( None, status=status.HTTP_403_FORBIDDEN )
            group = Group.objects.filter(id=pk).first()
            if not group:
                return Response( None, status=status.HTTP_404_NOT_FOUND )
            group_permissions = PermissionManager.get_model_group_permissions(group, 'group')
            return Response(group_permissions, status=status.HTTP_200_OK)
        permissions = PermissionManager.get_model_permissions(request.user, 'group', 'auth')
        return Response(permissions, status=status.HTTP_200_OK)



class UserPermissionsView(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]
    
    @action(detail=False, methods=['get'], url_path='my-permissions')
    def my_permissions(self, request):
        """Return the current user's identity, groups, and configuration edit permission."""
        user_permissions = PermissionManager.get_user_permissions(request.user)
        
        response_data = {
            'user': {
                'id': request.user.id,
                'username': request.user.username,
                'first_name': request.user.first_name,
                'last_name': request.user.last_name,
                'email': request.user.email,
                'is_superuser': request.user.is_superuser,
                'is_staff': request.user.is_staff,
                'role': get_user_role(request.user),
            },
            'permissions': user_permissions,
            'groups': list(request.user.groups.values_list('name', flat=True)),
            'can_edit_config_project': can_edit_config_project(request.user),
        }
        
        return Response(response_data, status=status.HTTP_200_OK)
    
    @action(detail=False, methods=['get'], url_path='permissions')
    def permissions(self, request):
        pk = request.query_params.get('id')
        if pk:
            user_permissions = PermissionManager.get_model_permissions(request.user, 'group', 'auth')
            if (
                not user_permissions['can_view']
                or not user_permissions['can_change']
                or not is_canonical_superuser(request.user)
            ):
                return Response( None, status=status.HTTP_403_FORBIDDEN )
            group = Group.objects.filter(id=pk).first()
            if not group:
                return Response( None, status=status.HTTP_404_NOT_FOUND )
            group_permissions = PermissionManager.get_model_group_permissions(group, 'permission')
            return Response(group_permissions, status=status.HTTP_200_OK)
        permissions = PermissionManager.get_model_permissions(request.user, 'permission', 'auth')
        return Response(permissions, status=status.HTTP_200_OK)
    
    def get_permissions(self):
        if self.action == 'permissions':
            return [IsAuthenticated()]
        return super().get_permissions()