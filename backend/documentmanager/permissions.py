from auth.permissions import DjangoModelViewPermissions


class DocumentPermission(DjangoModelViewPermissions):
    """Permisos de `DocumentViewSet` (només lectura per l'API, més les accions de descàrrega
    i d'esborrat). Descarregar és llegir encara que es faci amb POST (llista d'ids), i
    esborrar demana `delete_document`; les altres accions segueixen DjangoModelViewPermissions."""

    read_only_actions = ('view_document', 'download_documents', 'download_single_pdf_document')

    def has_permission(self, request, view):
        if getattr(view, 'action', None) == 'delete_documents':
            user = request.user
            return bool(user and user.is_authenticated and user.has_perm('documentmanager.delete_document'))
        return super().has_permission(request, view)
