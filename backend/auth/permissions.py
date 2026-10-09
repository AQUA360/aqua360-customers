from coredata.models import MainPermission


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
    def get_user_permissions(cls, user):
        # Get dynamic permission mappings
        permission_mappings = cls.get_permission_mappings()
        
        if not user.is_authenticated:
            permissions = {key: False for key in permission_mappings.keys()}
            return permissions
        
        if user.is_superuser:
            permissions = {key: True for key in permission_mappings.keys()}
            return permissions
        
        user_permissions = set()
        for group in user.groups.all():
            group_permissions = group.permissions.all()
            user_permissions.update(group_permissions.values_list('codename', flat=True))
        
        user_permissions.update(user.user_permissions.values_list('codename', flat=True))
        permissions = {}
        for permission_key, required_permissions in permission_mappings.items():
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
        return {
            'can_view': user.has_perm(f'{module_name}.view_{model_name}'),
            'can_add': user.has_perm(f'{module_name}.add_{model_name}'),
            'can_change': user.has_perm(f'{module_name}.change_{model_name}'),
            'can_delete': user.has_perm(f'{module_name}.delete_{model_name}'),
        } 
    
    @classmethod
    def get_model_group_permissions(cls, group, model_name):
        # Get all permissions for the group
        group_permissions = group.permissions.all()
        permission_codes = set(group_permissions.values_list('codename', flat=True))
        
        return {
            'can_view': f'view_{model_name}' in permission_codes,
            'can_add': f'add_{model_name}' in permission_codes,
            'can_change': f'change_{model_name}' in permission_codes,
            'can_delete': f'delete_{model_name}' in permission_codes,
        } 