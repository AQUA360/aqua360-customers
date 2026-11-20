"""Cap vista DRF nova sense permís propi (tiquets 2652 i 2654).

Recorre totes les rutes del projecte i comprova, sense fer peticions, els permisos de
cada vista (vegeu customers/view_permissions_audit.py). Les vistes que avui ja són
obertes són a customers/view_permissions_baseline.txt; la llista només s'ha d'escurçar.
"""

from django.test import SimpleTestCase
from rest_framework import permissions as drf_permissions

from auth.permissions import DjangoModelViewPermissions
from customers.view_permissions_audit import (
    EXEMPT_VIEWS,
    collect_open_views,
    is_open_permission,
    iter_drf_routes,
    load_baseline,
)


def _module_available(name):
    """Si el mòdul de la vista existeix en aquesta còpia (les apps privades no hi són a la CI)."""
    from importlib.util import find_spec

    module = name.rsplit('.', 1)[0]
    try:
        return find_spec(module) is not None
    except ModuleNotFoundError:
        return False


class ViewPermissionsRoutesTestCase(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.open_views = collect_open_views()
        cls.baseline = load_baseline()

    def test_no_new_open_views(self):
        new = sorted(set(self.open_views) - set(self.baseline))
        detail = '\n'.join(f"  {name}: {', '.join(sorted(self.open_views[name]['methods']))}" for name in new)
        self.assertFalse(
            new,
            "Vistes noves que qualsevol usuari autenticat pot cridar. Doneu-los un permís propi "
            "(p. ex. auth.permissions.DjangoModelViewPermissions o el de l'app), o si són públiques "
            "a propòsit, afegiu-les a EXEMPT_VIEWS amb el motiu:\n" + detail,
        )

    def test_baseline_has_no_stale_entries(self):
        stale = sorted(
            name for name in set(self.baseline) - set(self.open_views) if _module_available(name)
        )
        self.assertFalse(
            stale,
            "Aquestes vistes de la baseline ja no existeixen o ja tenen permís propi: traieu-les de "
            "customers/view_permissions_baseline.txt (manage.py view_permissions_audit --write-baseline):\n  "
            + '\n  '.join(stale),
        )

    def test_baseline_without_duplicates(self):
        duplicates = sorted({name for name in self.baseline if self.baseline.count(name) > 1})
        self.assertFalse(duplicates, f'Línies repetides a la baseline: {duplicates}')

    def test_exempt_views_are_routed(self):
        routed = {name for name, _callback, _cls in iter_drf_routes()}
        self.assertFalse(sorted(set(EXEMPT_VIEWS) - routed), 'Excepcions de vistes que ja no tenen ruta')


class OpenPermissionClassifierTestCase(SimpleTestCase):
    def test_classification(self):
        is_auth = drf_permissions.IsAuthenticated()
        model = drf_permissions.DjangoModelPermissions()
        view_model = DjangoModelViewPermissions()

        class OwnPermission(drf_permissions.BasePermission):
            def has_permission(self, request, view):
                return False

        own = OwnPermission()
        self.assertTrue(is_open_permission(is_auth, 'GET'))
        self.assertTrue(is_open_permission(drf_permissions.AllowAny(), 'POST'))
        self.assertTrue(is_open_permission(model, 'GET'))
        self.assertFalse(is_open_permission(model, 'POST'))
        self.assertFalse(is_open_permission(view_model, 'GET'))
        self.assertFalse(is_open_permission(view_model, 'HEAD'))
        self.assertFalse(is_open_permission(own, 'GET'))
        self.assertFalse(is_open_permission(drf_permissions.IsAdminUser(), 'GET'))
        self.assertTrue(is_open_permission((drf_permissions.DjangoModelPermissions | OwnPermission)(), 'GET'))
        self.assertFalse(is_open_permission((drf_permissions.DjangoModelPermissions | OwnPermission)(), 'POST'))
        self.assertFalse(is_open_permission((drf_permissions.IsAuthenticated & OwnPermission)(), 'GET'))
