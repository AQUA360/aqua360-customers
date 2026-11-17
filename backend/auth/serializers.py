from django.contrib.auth.models import Group, User, Permission
from rest_framework import serializers

from auth.utils import manage_group_permissions
from .permissions import PermissionManager
from django.contrib.auth.hashers import make_password
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
    
    new_pwd = serializers.CharField(write_only=True, required=False, allow_blank=True, allow_null=True)
    class Meta:
        model = User
        fields = [
            'id', 'first_name', 'last_name', 
            'username', 'email', 'group_name', 
            'permissions', 'group_id', 'is_superuser', 'new_pwd']

    def get_group_name(self, obj):
        return obj.groups.first().name if obj.groups.first() else None

    def get_permissions(self, obj):
        return PermissionManager.get_user_permissions(obj)
    
    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation['group_id'] = instance.groups.first().id if instance.groups.first() else None
        return representation

    def validate(self, attrs):
        new_pwd = attrs.get('new_pwd')
        if new_pwd:
            # Usuari sense desar amb les dades finals, per comparar la contrasenya amb el nom, el correu...
            fields = ('username', 'email', 'first_name', 'last_name')
            user = User(**{f: attrs.get(f) or (getattr(self.instance, f) if self.instance else '') for f in fields})
            is_superuser = attrs.get('is_superuser', self.instance.is_superuser if self.instance else False)
            try:
                validate_user_password(new_pwd, user, is_superuser)
            except DjangoValidationError as error:
                raise serializers.ValidationError({'new_pwd': list(error.messages)})
        return attrs

    def create(self, validated_data):
        user_request = self.context.get('request').user
        username = validated_data.pop('username')
        email = validated_data.pop('email')
        new_pwd = validated_data.pop('new_pwd', None)
        is_superuser = validated_data.pop('is_superuser', False)
        group_id = validated_data.pop('group_id', None)
        
        if not new_pwd:
            raise serializers.ValidationError({"new_pwd": "This field is required when creating a new user."})
            
        if is_superuser:
            if user_request.is_superuser:
                user = User.objects.create_superuser(username, email, new_pwd, **validated_data)
            else:
                raise PermissionDenied("You are not allowed to create a superuser")
        else:
            user = User.objects.create_user(username, email, new_pwd, **validated_data)
            
        if group_id:
            try:
                group = Group.objects.get(id=group_id)
                user.groups.add(group)
            except Group.DoesNotExist:
                pass
        return user

    def update(self, instance, validated_data):
        new_pwd = validated_data.pop('new_pwd', None)
        username = validated_data.pop('username', None)
        email = validated_data.pop('email', None)
        first_name = validated_data.pop('first_name', None)
        last_name = validated_data.pop('last_name', None)
        is_superuser = validated_data.pop('is_superuser', None)
        group_id_passed = 'group_id' in validated_data
        group_id = validated_data.pop('group_id', None)
        
        user_request = self.context.get('request').user
        
        if username:
            instance.username = username
        if email:
            instance.email = email
        if first_name:
            instance.first_name = first_name
        if last_name:
            instance.last_name = last_name
        if new_pwd:
            instance.password = make_password(new_pwd)
            
        if is_superuser is not None:
            if user_request.is_superuser:
                instance.is_superuser = is_superuser
                instance.is_staff = is_superuser
            else:
                raise PermissionDenied("You are not allowed to modify superuser status")
                
        instance.save()
        
        if group_id_passed:
            instance.groups.clear()
            if group_id:
                try:
                    group = Group.objects.get(id=group_id)
                    instance.groups.add(group)
                except Group.DoesNotExist:
                    pass
                    
        return instance

class UserMinimalSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = User
        fields = [ 'id', 'first_name', 'last_name', 'username', 'email' ]

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
        if not user.is_superuser or not user_permissions['can_add']:
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
        if not user.is_superuser or not user_permissions['can_change']:
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