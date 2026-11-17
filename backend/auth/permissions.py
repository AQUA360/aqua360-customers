from coredata.models import MainPermission


AUTH_USER_MGMT_MODELS = frozenset({'user', 'group', 'permission'})


class PermissionManager:

    @classmethod
    def get_permission_mappings(cls):
        mappings = {}
        
        main_permissions = MainPermission.objects.filter(is_active=True)
        
        for main_perm in main_permissions:
            if main_perm.view_key:
                view_permissions = []
                if main_perm.affected_models:
                    models = [model.strip() for model in main_perm.affected_models.split(',')]
                    for model in models:
                        if '.' in model:
                            app_name, model_name = model.split('.')
                            view_permissions.append(f'view_{model_name.lower()}')
                
                mappings[main_perm.view_key] = view_permissions
            
            if main_perm.change_key:
                change_permissions = []
                if main_perm.affected_models:
                    models = [model.strip() for model in main_perm.affected_models.split(',')]
                    for model in models:
                        if '.' in model:
                            app_name, model_name = model.split('.')
                            change_permissions.append(f'change_{model_name.lower()}')
                
                mappings[main_perm.change_key] = change_permissions
        
        return mappings

    @classmethod
    def get_superuser_only_change_keys(cls):
        """change_key dels MainPermission que només pot tenir el superusuari."""
        return set(
            MainPermission.objects.filter(
                is_active=True,
                change_requires_superuser=True,
            ).exclude(change_key='').values_list('change_key', flat=True)
        )

    @classmethod
    def _is_auth_user_mgmt(cls, model_name, module_name):
        """Accepta tant (model, app) com l'ordre legacy (auth, model) dels call sites."""
        return (
            (module_name == 'auth' and model_name in AUTH_USER_MGMT_MODELS)
            or (model_name == 'auth' and module_name in AUTH_USER_MGMT_MODELS)
        )
    
    @classmethod
    def get_user_permissions(cls, user):
        permission_mappings = cls.get_permission_mappings()
        
        if not user.is_authenticated:
            return {key: False for key in permission_mappings.keys()}
        
        from auth.roles import is_canonical_superuser

        # Només `customers` té permisos de superuser (gestió d'usuaris).
        if is_canonical_superuser(user):
            return {key: True for key in permission_mappings.keys()}

        superuser_only_change_keys = cls.get_superuser_only_change_keys()

        # Admin (is_staff o is_superuser residual): tot excepte change de usuaris/grups.
        # view_user es manté per poder seleccionar usuaris/grups (calendar, reports, etc.).
        if user.is_staff or user.is_superuser:
            return {
                key: (key not in superuser_only_change_keys)
                for key in permission_mappings.keys()
            }
        
        user_permissions = set()
        for group in user.groups.all():
            group_permissions = group.permissions.all()
            user_permissions.update(group_permissions.values_list('codename', flat=True))
        
        user_permissions.update(user.user_permissions.values_list('codename', flat=True))
        permissions = {}
        for permission_key, required_permissions in permission_mappings.items():
            if permission_key in superuser_only_change_keys:
                permissions[permission_key] = False
                continue
            if not required_permissions:
                permissions[permission_key] = False
                continue
            
            permissions[permission_key] = any(perm in user_permissions for perm in required_permissions)
        return permissions
    
    @classmethod
    def has_permission(cls, user, permission_key):
        permissions = cls.get_user_permissions(user)
        return permissions.get(permission_key, False)
    
    @classmethod
    def get_model_permissions(cls, user, model_name, module_name):
        from auth.roles import is_canonical_superuser

        if is_canonical_superuser(user):
            return {
                'can_view': True,
                'can_add': True,
                'can_change': True,
                'can_delete': True,
            }
        # Admin: pot veure usuaris/grups (selecció); no pot crear/editar/eliminar.
        if user.is_staff or user.is_superuser:
            if cls._is_auth_user_mgmt(model_name, module_name):
                return {
                    'can_view': True,
                    'can_add': False,
                    'can_change': False,
                    'can_delete': False,
                }
            return {
                'can_view': True,
                'can_add': True,
                'can_change': True,
                'can_delete': True,
            }
        return {
            'can_view': user.has_perm(f'{module_name}.view_{model_name}'),
            'can_add': user.has_perm(f'{module_name}.add_{model_name}'),
            'can_change': user.has_perm(f'{module_name}.change_{model_name}'),
            'can_delete': user.has_perm(f'{module_name}.delete_{model_name}'),
        } 
    
    @classmethod
    def get_model_group_permissions(cls, group, model_name):
        group_permissions = group.permissions.all()
        permission_codes = set(group_permissions.values_list('codename', flat=True))
        
        return {
            'can_view': f'view_{model_name}' in permission_codes,
            'can_add': f'add_{model_name}' in permission_codes,
            'can_change': f'change_{model_name}' in permission_codes,
            'can_delete': f'delete_{model_name}' in permission_codes,
        } 
