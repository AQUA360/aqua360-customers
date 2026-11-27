from rest_framework.permissions import BasePermission

from auth.permissions import DjangoModelViewPermissions


class InGroup(BasePermission):
    """Només usuaris autenticats d'un grup tècnic d'integració (giswater, smartmetering...).

    Els endpoints d'entrada exporten dades de tots els contractes: no els pot cridar qualsevol
    usuari intern autenticat, només el compte de servei de la integració."""

    group_name = None

    def has_permission(self, request, view):
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and user.groups.filter(name=self.group_name).exists()
        )


class IsGiswaterUser(InGroup):
    group_name = "giswater"


class IsSmartMeteringUser(InGroup):
    group_name = "smartmetering"


class ChangeActionsModelPermissions(DjangoModelViewPermissions):
    """DjangoModelViewPermissions amb accions POST que modifiquen l'objecte sense crear-ne cap
    (enviar a l'ERP, canviar posicions...): demanen `change_<model>` en lloc d'`add_<model>`."""

    change_actions = ()

    def has_permission(self, request, view):
        if getattr(view, "action", None) in self.change_actions:
            user = request.user
            if not user or not user.is_authenticated:
                return False
            model = self._queryset(view).model
            return user.has_perms(self.get_required_permissions("PATCH", model))
        return super().has_permission(request, view)


class SendBatchPermission(ChangeActionsModelPermissions):
    """Lots d'enviament a l'ERP: veure demana `view_sendbatch`; reenviar, reintentar i
    comprovar l'estat (que parlen amb l'ERP) demanen `change_sendbatch`."""

    read_only_actions = ("preview_payload",)
    change_actions = ("retry_send", "check_status", "resend_errors")


class SendBatchCatalogPermission(ChangeActionsModelPermissions):
    change_actions = ("update_positions", "update_default")


class SendBatchSettingsPermission(BasePermission):
    """Configuració agregada de SendBatch: GET demana veure els proveïdors i POST (que crea la
    configuració que falta) demana modificar-los."""

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if request.method in ("GET", "HEAD"):
            return user.has_perm("integrations.view_sendbatchprovider")
        if request.method == "OPTIONS":
            return True
        return user.has_perm("integrations.change_sendbatchprovider")
