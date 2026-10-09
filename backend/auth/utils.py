from coredata.models import MainPermission
from django.apps import apps
from django.contrib.auth.models import Permission

def manage_group_permissions(group, permissions):
    #Add default permissions to group
    default_permission = MainPermission.objects.get(is_default=True)
    affected_models = default_permission.affected_models.split(',')
    for affected_model in affected_models:
        model_string = affected_model.strip()
        if '.' in model_string:
            app_name, model_name = model_string.split('.')
            view_permission = Permission.objects.get(
                content_type__app_label=app_name,
                content_type__model=model_name,
                codename='view_' + model_name
            )
            group.permissions.add(view_permission)
            codenames = ['change_' + model_name, 'delete_' + model_name, 'add_' + model_name]
            for codename in codenames:
                change_permission = Permission.objects.get(
                    content_type__app_label=app_name,
                    content_type__model=model_name,
                    codename=codename
                )
                group.permissions.add(change_permission)
    
    for permission in permissions:
        # permissions_data coming from the frontend may not include fine-grained
        # "affected_data". In that case, apply hasView/hasChange uniformly to all
        # affected models for that MainPermission.
        main_permission = MainPermission.objects.get(view_key=permission['viewKey'])
        affected_models = main_permission.affected_models.split(',')
        can_view = permission.get('hasView', False)
        can_change = permission.get('hasChange', False)
        affected_data_list = permission.get('affected_data') or []

        for affected_model in affected_models:
            model_string = affected_model.strip()
            if '.' in model_string:
                app_name, model_name = model_string.split('.')

                # Default: if no per-model config, fall back to global can_change
                model_can_change = can_change

                # If detailed affected_data is present, refine per model
                for affected_data in affected_data_list:
                    if affected_data.get('model') == model_name:
                        model_can_change = affected_data.get('can_change', can_change)
                        break
                
                if not can_view:
                    model_permissions = Permission.objects.filter(
                        content_type__app_label=app_name,
                        content_type__model=model_name
                    )
                    group.permissions.remove(*model_permissions)
                else:
                    view_permission = Permission.objects.get(
                        content_type__app_label=app_name,
                        content_type__model=model_name,
                        codename='view_' + model_name
                    )
                    group.permissions.add(view_permission)
                    codenames = ['change_' + model_name, 'delete_' + model_name, 'add_' + model_name]
                    for codename in codenames:
                        change_permission = Permission.objects.get(
                            content_type__app_label=app_name,
                            content_type__model=model_name,
                            codename=codename
                        )
                        if not model_can_change:
                            group.permissions.remove(change_permission)
                        else:
                            group.permissions.add(change_permission)
    
    return group
                    
    