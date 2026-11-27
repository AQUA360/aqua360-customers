from rest_framework import viewsets, generics
from rest_framework.decorators import action
from rest_framework import status
from rest_framework.authtoken.views import ObtainAuthToken
from rest_framework.permissions import AllowAny, IsAuthenticated, DjangoModelPermissions
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.throttling import ScopedRateThrottle
from axes.handlers.proxy import AxesProxyHandler
from axes.utils import reset as axes_reset

from django.shortcuts import render
from django.utils.translation import gettext_lazy as _
from django.contrib.auth.models import Group, User, Permission
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction

from auth.filters import UserFilter, GroupFilter
from auth.roles import CANONICAL_SUPERUSER_USERNAME, get_user_role, is_canonical_superuser, is_customers_account
from auth.serializers import GroupSerializer, OwnProfileSerializer, UserSerializer, PermissionSerializer
from auth.permissions import PermissionManager
from auth.validators import validate_user_password
from auth import password_reset_service
from coredata.authentication import issue_token_key
from coredata.permissions import can_edit_config_project


WRITE_ACTIONS = ('create', 'update', 'partial_update', 'destroy')


def check_user_management_permission(request, action, resource):
    """Usuaris i grups: GET obert a autenticats (selecció); escriptura només superusuari.

    La UI de gestió (settings) segueix gated per `view_user` al front.
    """
    if action in WRITE_ACTIONS and not is_canonical_superuser(request.user):
        raise PermissionDenied(f"Only a superuser can modify {resource}.")


def check_superuser_target(user, target, allow_self=False):
    """Un superusuari (o un is_superuser residual) només el pot modificar o eliminar el
    compte `customers`; amb allow_self, un superusuari addicional pot editar el seu compte."""
    if not target.is_superuser or is_customers_account(user):
        return
    if allow_self and target.pk == user.pk and is_canonical_superuser(user):
        return
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

        return Response({
            'username': user.username,
            'token': issue_token_key(user)
        })


class LogoutView(APIView):
    """Revoca el token amb què s'ha fet la petició (només aquesta sessió)."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if request.auth is not None:
            request.auth.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
    

def _request_text(request, field):
    """Camp de text del cos de la petició; 400 (no 500) si arriba un número, una llista..."""
    data = request.data if isinstance(request.data, dict) else {}
    value = data.get(field)
    if value is not None and not isinstance(value, str):
        raise ValidationError({field: [_('This field must be text.')]})
    return value


class PasswordResetRequestView(APIView):
    """Demana el correu de recuperació de la contrasenya des del login (sense sessió).

    POST {username} → sempre {status: "sent"}, s'hagi pogut enviar o no (usuari inexistent, sense
    correu, empresa sense correu configurat...): respondre diferent diria quins usuaris existeixen.
    El motiu real només queda al log; la pantalla diu que, si no arriba, s'adrecin a l'administrador.
    """
    authentication_classes = []
    permission_classes = [AllowAny]
    # Límit per IP (LoginIPThrottle llegeix l'scope de `throttle_scope`)
    throttle_classes = [LoginIPThrottle]
    throttle_scope = 'password_reset'

    def post(self, request):
        password_reset_service.request_password_reset(_request_text(request, 'username'), request)
        return Response({'status': password_reset_service.STATUS_SENT}, status=status.HTTP_200_OK)


class PasswordResetConfirmView(APIView):
    """Desa la contrasenya nova a partir de l'enllaç del correu (sense sessió).

    POST {uid, token} → {valid, strict_rules}: comprova l'enllaç abans d'ensenyar el formulari.
    POST {uid, token, new_password} → 204 i es tanquen totes les sessions de l'usuari.
    """
    authentication_classes = []
    permission_classes = [AllowAny]
    # Límit per IP propi, separat de la demanda del correu: cada recuperació en fa diverses
    # peticions (comprovar l'enllaç, contrasenyes rebutjades, desar) i, compartint-lo, una
    # oficina darrere d'una sola IP es quedaria sense recuperacions
    throttle_classes = [LoginIPThrottle]
    throttle_scope = 'password_reset_confirm'

    def post(self, request):
        uid = _request_text(request, 'uid')
        token = _request_text(request, 'token')
        new_password = _request_text(request, 'new_password')
        if new_password is None:
            user = password_reset_service.get_user_from_reset_token(uid, token)
            return Response({
                'valid': user is not None,
                'strict_rules': bool(user and is_canonical_superuser(user)),
            }, status=status.HTTP_200_OK)
        # Fer servir l'enllaç és atòmic: la fila de l'usuari queda bloquejada fins a desar i una
        # petició simultània amb el mateix token, en continuar, ja el troba gastat
        with transaction.atomic():
            user = password_reset_service.get_user_from_reset_token(uid, token, for_update=True)
            if user is None:
                raise ValidationError({'token': [_('The link is not valid or has expired. Request a new one.')]})
            try:
                validate_user_password(new_password, user, is_canonical_superuser(user))
            except DjangoValidationError as error:
                raise ValidationError({'new_password': list(error.messages)})
            user.set_password(new_password)
            user.save(update_fields=['password'])
        # Si l'usuari estava bloquejat per intents fallits, amb la contrasenya nova ja pot entrar
        axes_reset(username=user.username)
        return Response(status=status.HTTP_204_NO_CONTENT)


class OwnProfileView(generics.RetrieveUpdateAPIView):
    """Fitxa de l'usuari autenticat (consultar i canviar nom, cognoms i correu).

    Oberta a qualsevol usuari autenticat, sigui quin sigui el seu rol o permisos, i sempre
    sobre `request.user`: no accepta cap id d'usuari."""
    serializer_class = OwnProfileSerializer
    permission_classes = [IsAuthenticated]
    throttle_scope = 'password_change'

    def get_throttles(self):
        # Canviar el correu comprova la contrasenya actual: comparteix el límit del canvi de
        # contrasenya perquè no serveixi per endevinar-la. Consultar la fitxa no té límit.
        if self.request.method in ('PUT', 'PATCH'):
            return [ScopedRateThrottle()]
        return []

    def get_object(self):
        return self.request.user


class ChangeOwnPasswordView(APIView):
    """Canvi de la contrasenya de l'usuari autenticat, sigui quin sigui el seu rol o permisos.

    Només actua sobre `request.user` (no accepta cap id d'usuari): canviar la contrasenya
    d'un altre usuari es fa des de la gestió d'usuaris, reservada als superusuaris.
    Demana la contrasenya actual i aplica les mateixes regles que la gestió d'usuaris.
    En desar, es tanquen les altres sessions de l'usuari i es conserva l'actual.
    """
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'password_change'

    def post(self, request):
        user = request.user
        current_password = _request_text(request, 'current_password') or ''
        new_password = _request_text(request, 'new_password') or ''

        if not current_password or not user.check_password(current_password):
            raise ValidationError({'current_password': [_('The current password is not correct.')]})
        if not new_password:
            raise ValidationError({'new_password': [_('The new password is required.')]})
        if new_password == current_password:
            raise ValidationError({'new_password': [_('The new password must be different from the current one.')]})

        try:
            validate_user_password(new_password, user, is_canonical_superuser(user))
        except DjangoValidationError as error:
            raise ValidationError({'new_password': list(error.messages)})

        user.set_password(new_password)
        # El senyal de canvi de contrasenya tanca les sessions; es conserva la d'aquesta petició
        user._keep_token_key = getattr(request.auth, 'key', None)
        user.save(update_fields=['password'])
        return Response(status=status.HTTP_204_NO_CONTENT)


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
        check_superuser_target(request.user, self.get_object(), allow_self=True)
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