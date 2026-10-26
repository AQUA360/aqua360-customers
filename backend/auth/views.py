from rest_framework import viewsets, generics
from rest_framework.decorators import action
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.authtoken.views import ObtainAuthToken
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied

from django.shortcuts import render
from django.contrib.auth.models import Group, User, Permission

from auth.filters import UserFilter, GroupFilter
from auth.serializers import GroupSerializer, UserSerializer, PermissionSerializer
from auth.permissions import PermissionManager
from coredata.permissions import can_edit_config_project


WRITE_ACTIONS = ('create', 'update', 'partial_update', 'destroy')


def check_user_management_permission(request, action, resource):
    """Usuaris i grups: llegir requereix `view_user` i escriure `change_user`."""
    if not PermissionManager.has_permission(request.user, 'view_user'):
        raise PermissionDenied(f"You don't have permission to view {resource}.")
    if action in WRITE_ACTIONS and not PermissionManager.has_permission(request.user, 'change_user'):
        raise PermissionDenied(f"You don't have permission to modify {resource}.")


def check_superuser_target(user, target):
    """Només un superusuari pot modificar o eliminar un altre superusuari."""
    if target.is_superuser and not user.is_superuser:
        raise PermissionDenied("You are not allowed to modify a superuser")


class CustomAuthToken(ObtainAuthToken):
    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)

        user = serializer.validated_data['user']
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

    def perform_update(self, serializer):
        check_superuser_target(self.request.user, serializer.instance)
        super().perform_update(serializer)

    def perform_destroy(self, instance):
        check_superuser_target(self.request.user, instance)
        super().perform_destroy(instance)

    @action(detail=False, methods=['get'], url_path='permissions')
    def permissions(self, request):
        pk = request.query_params.get('id')
        if pk:
            user_permissions = PermissionManager.get_model_permissions(request.user, 'auth', 'group')
            if not user_permissions['can_view'] or not user_permissions['can_change'] or not request.user.is_superuser:
                return Response( None, status=status.HTTP_403_FORBIDDEN )
            group = Group.objects.filter(id=pk).first()
            if not group:
                return Response( None, status=status.HTTP_404_NOT_FOUND )
            group_permissions = PermissionManager.get_model_group_permissions(group, 'user')
            return Response(group_permissions, status=status.HTTP_200_OK)
        permissions = PermissionManager.get_model_permissions(request.user, 'auth', 'user')
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
        if not user.is_superuser or not user.has_perm('auth.delete_group'):
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
            user_permissions = PermissionManager.get_model_permissions(request.user, 'auth', 'group')
            if not user_permissions['can_view'] or not user_permissions['can_change'] or not request.user.is_superuser:
                return Response( None, status=status.HTTP_403_FORBIDDEN )
            group = Group.objects.filter(id=pk).first()
            if not group:
                return Response( None, status=status.HTTP_404_NOT_FOUND )
            group_permissions = PermissionManager.get_model_group_permissions(group, 'group')
            return Response(group_permissions, status=status.HTTP_200_OK)
        permissions = PermissionManager.get_model_permissions(request.user, 'auth', 'group')
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
            user_permissions = PermissionManager.get_model_permissions(request.user, 'auth', 'group')
            if not user_permissions['can_view'] or not user_permissions['can_change'] or not request.user.is_superuser:
                return Response( None, status=status.HTTP_403_FORBIDDEN )
            group = Group.objects.filter(id=pk).first()
            if not group:
                return Response( None, status=status.HTTP_404_NOT_FOUND )
            group_permissions = PermissionManager.get_model_group_permissions(group, 'permission')
            return Response(group_permissions, status=status.HTTP_200_OK)
        permissions = PermissionManager.get_model_permissions(request.user, 'auth', 'permission')
        return Response(permissions, status=status.HTTP_200_OK)
    
    def get_permissions(self):
        if self.action == 'permissions':
            return [IsAuthenticated()]
        return super().get_permissions()