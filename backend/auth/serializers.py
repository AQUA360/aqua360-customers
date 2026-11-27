from django.contrib.auth.models import Group, User, Permission
from rest_framework import serializers

from auth.roles import (
    CANONICAL_SUPERUSER_USERNAME,
    ROLE_ADMIN,
    ROLE_NONE,
    ROLE_SUPERUSER,
    can_be_superuser,
    get_user_role,
    is_canonical_superuser,
    is_customers_account,
)
from auth.utils import manage_group_permissions
from .permissions import PermissionManager
from django.contrib.auth.hashers import make_password
from django.db import transaction
from django.core.exceptions import PermissionDenied, ValidationError as DjangoValidationError
from django.utils.translation import gettext

from auth.validators import validate_user_password
from coredata.models import MainPermission


class PermissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Permission
        fields = ['name']

class UserSerializer(serializers.HyperlinkedModelSerializer):
    permissions = serializers.SerializerMethodField()
    group_name = serializers.SerializerMethodField()
    group_id = serializers.IntegerField(required=False, allow_null=True)
    role = serializers.ChoiceField(
        choices=[ROLE_SUPERUSER, ROLE_ADMIN, ROLE_NONE],
        required=False,
        write_only=True,
    )
    
    new_pwd = serializers.CharField(write_only=True, required=False, allow_blank=True, allow_null=True)
    class Meta:
        model = User
        fields = [
            'id', 'first_name', 'last_name', 
            'username', 'email', 'group_name', 
            'permissions', 'group_id', 'is_superuser', 'is_staff', 'role', 'new_pwd']

    def get_group_name(self, obj):
        return obj.groups.first().name if obj.groups.first() else None

    def get_permissions(self, obj):
        return PermissionManager.get_user_permissions(obj)
    
    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation['group_id'] = instance.groups.first().id if instance.groups.first() else None
        representation['role'] = get_user_role(instance)
        representation['can_be_superuser'] = can_be_superuser(instance.username)
        return representation

    def _apply_role(self, user, role, group_id=None, update_group=False):
        """Aplica rol. Només `customers` i els superusuaris addicionals poden ser superuser."""
        if role == ROLE_SUPERUSER:
            if not can_be_superuser(user.username):
                raise PermissionDenied(
                    "This account is not allowed to be a superuser"
                )
            user.is_superuser = True
            user.is_staff = True
            user.save()
            user.groups.clear()
            return user

        if user.username == CANONICAL_SUPERUSER_USERNAME:
            raise PermissionDenied(
                f"The '{CANONICAL_SUPERUSER_USERNAME}' account must remain a superuser"
            )

        if role == ROLE_ADMIN:
            user.is_superuser = False
            user.is_staff = True
            user.save()
            user.groups.clear()
            return user

        # ROLE_NONE: permisos només via grup
        user.is_superuser = False
        user.is_staff = False
        user.save()
        if update_group:
            user.groups.clear()
            if group_id:
                try:
                    user.groups.add(Group.objects.get(id=group_id))
                except Group.DoesNotExist:
                    pass
        return user

    def _normalize_residual_superuser(self, user):
        """Rebaixa is_superuser residual a admin (excepte els comptes que poden ser superuser)."""
        if not can_be_superuser(user.username) and user.is_superuser:
            user.is_superuser = False
            user.is_staff = True
            user.save(update_fields=['is_superuser', 'is_staff'])

    def validate(self, attrs):
        new_pwd = attrs.get('new_pwd')
        if new_pwd:
            # Usuari sense desar amb les dades finals, per comparar la contrasenya amb el nom, el correu...
            fields = ('username', 'email', 'first_name', 'last_name')
            user = User(**{f: attrs.get(f) or (getattr(self.instance, f) if self.instance else '') for f in fields})
            role = attrs.get('role')
            if role is not None:
                is_superuser = role == ROLE_SUPERUSER
            elif self.instance is not None:
                is_superuser = self.instance.is_superuser
            else:
                is_superuser = False
            try:
                validate_user_password(new_pwd, user, is_superuser)
            except DjangoValidationError as error:
                raise serializers.ValidationError({'new_pwd': list(error.messages)})
        return attrs

    def create(self, validated_data):
        user_request = self.context.get('request').user
        if not is_canonical_superuser(user_request):
            raise PermissionDenied("Only a superuser can create users")

        username = validated_data.pop('username')
        email = validated_data.pop('email')
        new_pwd = validated_data.pop('new_pwd', None)
        validated_data.pop('is_superuser', None)
        validated_data.pop('is_staff', None)
        role = validated_data.pop('role', None) or ROLE_NONE
        group_id = validated_data.pop('group_id', None)
        
        if not new_pwd:
            raise serializers.ValidationError({"new_pwd": "This field is required when creating a new user."})

        if username == CANONICAL_SUPERUSER_USERNAME:
            raise PermissionDenied(
                f"The '{CANONICAL_SUPERUSER_USERNAME}' account cannot be created via the API"
            )
        if role == ROLE_SUPERUSER:
            if not is_customers_account(user_request):
                raise PermissionDenied(
                    f"Only the '{CANONICAL_SUPERUSER_USERNAME}' account can grant superuser rights"
                )
            if not can_be_superuser(username):
                raise PermissionDenied(
                    "This account is not allowed to be a superuser"
                )

        user = User.objects.create_user(username, email, new_pwd, **validated_data)
        return self._apply_role(user, role, group_id=group_id, update_group=True)

    @transaction.atomic
    def update(self, instance, validated_data):
        user_request = self.context.get('request').user
        if not is_canonical_superuser(user_request):
            raise PermissionDenied("Only a superuser can update users")
        # Comprovar i desar sobre la fila bloquejada: un canvi de rol simultani (p. ex. una
        # revocació) no es pot perdre amb un desament fet amb dades antigues
        instance = User.objects.select_for_update().get(pk=instance.pk)
        if instance.pk == user_request.pk:
            if not is_canonical_superuser(instance):
                raise PermissionDenied("Only a superuser can update users")
        elif instance.is_superuser and not is_customers_account(user_request):
            # Com check_superuser_target, però sobre la fila bloquejada (pot haver canviat)
            raise PermissionDenied(
                f"Only the '{CANONICAL_SUPERUSER_USERNAME}' account can modify another superuser"
            )

        new_pwd = validated_data.pop('new_pwd', None)
        username = validated_data.pop('username', None)
        email = validated_data.pop('email', None)
        first_name = validated_data.pop('first_name', None)
        last_name = validated_data.pop('last_name', None)
        validated_data.pop('is_superuser', None)
        validated_data.pop('is_staff', None)
        role = validated_data.pop('role', None)
        group_id_passed = 'group_id' in validated_data
        group_id = validated_data.pop('group_id', None)

        target_username = username if username is not None else instance.username
        if instance.username == CANONICAL_SUPERUSER_USERNAME and target_username != CANONICAL_SUPERUSER_USERNAME:
            raise PermissionDenied(
                f"Cannot rename the '{CANONICAL_SUPERUSER_USERNAME}' superuser"
            )
        if target_username == CANONICAL_SUPERUSER_USERNAME and instance.username != CANONICAL_SUPERUSER_USERNAME:
            raise PermissionDenied(
                f"Cannot rename a user to '{CANONICAL_SUPERUSER_USERNAME}'"
            )
        # Un canvi de nom que fes perdre el rol de superusuari és una revocació: només `customers`
        if (
            target_username != instance.username
            and get_user_role(instance) == ROLE_SUPERUSER
            and not can_be_superuser(target_username)
            and not is_customers_account(user_request)
        ):
            raise PermissionDenied(
                f"Only the '{CANONICAL_SUPERUSER_USERNAME}' account can grant or revoke superuser rights"
            )
        # Validar el rol abans de mutar (contrasenya, etc.) per no deixar canvis parcials
        if role is not None:
            # Donar o treure drets de superusuari: només el compte `customers`
            current_role = get_user_role(instance)
            if (
                role != current_role
                and ROLE_SUPERUSER in (role, current_role)
                and not is_customers_account(user_request)
            ):
                raise PermissionDenied(
                    f"Only the '{CANONICAL_SUPERUSER_USERNAME}' account can grant or revoke superuser rights"
                )
            if role == ROLE_SUPERUSER and not can_be_superuser(target_username):
                raise PermissionDenied(
                    "This account is not allowed to be a superuser"
                )
            if target_username == CANONICAL_SUPERUSER_USERNAME and role != ROLE_SUPERUSER:
                raise PermissionDenied(
                    f"The '{CANONICAL_SUPERUSER_USERNAME}' account must remain a superuser"
                )

        if username:
            instance.username = username
        if email:
            instance.email = email
        if first_name:
            instance.first_name = first_name
        if last_name:
            instance.last_name = last_name
        if new_pwd:
            # validate() ho ha comprovat abans del bloqueig: es repeteix amb el rol final de la fila
            is_superuser = (role == ROLE_SUPERUSER) if role is not None else instance.is_superuser
            try:
                validate_user_password(new_pwd, instance, is_superuser)
            except DjangoValidationError as error:
                raise serializers.ValidationError({'new_pwd': list(error.messages)})
            instance.password = make_password(new_pwd)
        instance.save()

        if role is not None:
            self._apply_role(
                instance,
                role,
                group_id=group_id,
                update_group=(role == ROLE_NONE),
            )
        elif group_id_passed and get_user_role(instance) == ROLE_NONE:
            instance.groups.clear()
            if group_id:
                try:
                    instance.groups.add(Group.objects.get(id=group_id))
                except Group.DoesNotExist:
                    pass

        if instance.username == CANONICAL_SUPERUSER_USERNAME:
            instance.is_superuser = True
            instance.is_staff = True
            instance.save(update_fields=['is_superuser', 'is_staff'])
            instance.groups.clear()
        else:
            self._normalize_residual_superuser(instance)
                    
        return instance

class UserMinimalSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = User
        fields = [ 'id', 'first_name', 'last_name', 'username', 'email' ]

class OwnProfileSerializer(serializers.ModelSerializer):
    """Dades del propi usuari: pot canviar nom, cognoms i correu.

    El nom d'usuari, el rol i el grup només es mostren: els canvia un superusuari des de la
    gestió d'usuaris (el nom d'usuari decideix qui pot ser superusuari)."""
    email = serializers.EmailField(required=True, allow_blank=False, max_length=254)
    role = serializers.SerializerMethodField()
    group_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'username', 'first_name', 'last_name', 'email', 'role', 'group_name',
                  'date_joined', 'last_login']
        read_only_fields = ['id', 'username', 'date_joined', 'last_login']

    def get_role(self, obj):
        return get_user_role(obj)

    def get_group_name(self, obj):
        group = obj.groups.first()
        return group.name if group else None


class GroupSerializer(serializers.HyperlinkedModelSerializer):
    permissions = serializers.SerializerMethodField()
    users = serializers.SerializerMethodField()
    
    user_ids = serializers.ListField(child=serializers.IntegerField(), write_only=True)
    permissions_data = serializers.ListField(write_only=True)
    class Meta:
        model = Group
        fields = ['id', 'name', 'permissions', 'users', 'user_ids', 'permissions_data']
    
    def get_users(self, obj):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return []
        
        user_permissions = PermissionManager.get_user_permissions(request.user)
        if not user_permissions.get('view_user', False):
            return []
        
        users = obj.user_set.all().order_by('username')
        return [
            {
                'id': user.id,
                'username': user.username,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'email': user.email,
                'is_active': user.is_active,
                'date_joined': user.date_joined.isoformat() if user.date_joined else None,
                'last_login': user.last_login.isoformat() if user.last_login else None,
                'group_name': user.groups.first().name if user.groups.first() else None,
                'is_superuser': user.is_superuser,
                'is_staff': user.is_staff,
                'role': get_user_role(user),
            }
            for user in users
        ]
    
    def get_permissions(self, obj):
        group_permissions = obj.permissions.all()
        permission_codenames = set(group_permissions.values_list('codename', flat=True))
        
        permissions = {}
        for permission_key, required_permissions in PermissionManager.get_permission_mappings().items():
            if not required_permissions:  
                permissions[permission_key] = False
                continue
                
            permissions[permission_key] = any(
                perm in permission_codenames for perm in required_permissions
            )
        
        return permissions

    def validate_permissions_data(self, value):
        # Cada element ha de ser un objecte amb un viewKey existent; si no, 400 (abans donava 500)
        view_keys = set(MainPermission.objects.exclude(view_key__isnull=True).values_list('view_key', flat=True))
        for permission in value:
            if not isinstance(permission, dict) or permission.get('viewKey') not in view_keys:
                raise serializers.ValidationError(gettext("Invalid permission data."))
            affected_data = permission.get('affected_data') or []
            if not isinstance(affected_data, list) or not all(isinstance(item, dict) for item in affected_data):
                raise serializers.ValidationError(gettext("Invalid permission data."))
        return value

    def create(self, validated_data):
        user = self.context.get('request').user
        user_permissions = PermissionManager.get_model_permissions(user, 'group', 'auth')
        if not is_canonical_superuser(user) or not user_permissions['can_add']:
            raise PermissionDenied("You are not allowed to create this group")
        
        permissions = validated_data.pop('permissions_data', None)
        user_ids = validated_data.pop('user_ids', None)
        instance = super().create(validated_data)
        if permissions:
            instance = manage_group_permissions(instance, permissions)
        if user_ids:
            users = User.objects.filter(id__in=user_ids)
            for user in users:
                user.groups.clear()
            instance.user_set.set(users)
        return instance
    
    def update(self, instance, validated_data):
        user = self.context.get('request').user
        user_permissions = PermissionManager.get_model_permissions(user, 'group', 'auth')
        if not is_canonical_superuser(user) or not user_permissions['can_change']:
            raise PermissionDenied("You are not allowed to update this group")
        permissions = validated_data.pop('permissions_data', None)
        user_ids = validated_data.pop('user_ids', None)
        
        instance = super().update(instance, validated_data)
        
        if permissions:
            instance = manage_group_permissions(instance, permissions)
        
        if user_ids:
            users = User.objects.filter(id__in=user_ids)
            for user in users:
                user.groups.clear()
            instance.user_set.set(users)
        return instance
