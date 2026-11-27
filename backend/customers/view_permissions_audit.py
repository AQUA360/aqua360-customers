"""Auditoria estàtica dels permisos de lectura de les vistes DRF.

Recorre totes les rutes de l'urlconf del projecte, instancia cada vista DRF com
la instanciaria la petició (amb l'acció de cada ruta del ViewSet) i n'avalua
`get_permissions()` sense fer cap petició HTTP. Una vista és "oberta" si algun
dels seus mètodes (llevat d'OPTIONS) el pot fer qualsevol usuari autenticat:
només `IsAuthenticated`/`AllowAny`, o `DjangoModelPermissions` tal com ve de DRF
(no demana cap permís per a GET/HEAD).

El fa servir `customers/tests_view_permissions_routes.py` i l'ordre
`manage.py view_permissions_audit`, que també regenera la llista de vistes
obertes acceptades (`view_permissions_baseline.txt`).
"""

from pathlib import Path

from django.conf import settings
from django.urls import URLPattern, URLResolver, get_resolver
from rest_framework import exceptions as drf_exceptions
from rest_framework import permissions as drf_permissions
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory
from rest_framework.views import APIView

BASELINE_PATH = Path(__file__).with_name('view_permissions_baseline.txt')

# Permisos que no limiten per model ni per rol: qualsevol usuari autenticat passa.
OPEN_PERMISSION_CLASSES = (
    drf_permissions.AllowAny,
    drf_permissions.IsAuthenticated,
    drf_permissions.IsAuthenticatedOrReadOnly,
    drf_permissions.BasePermission,
)

# Accions que tots els ViewSets exposen amb `IsAuthenticated` a propòsit.
EXEMPT_ACTIONS = {
    # Retorna els permisos del propi usuari per a la pantalla; amb ?id= (permisos
    # d'un grup) ja comprova a dins que l'usuari pot gestionar grups.
    'permissions': "permisos de l'usuari mateix per a la pantalla",
}

# Vistes obertes a propòsit (públiques o amb autenticació pròpia). Clau: mòdul.Classe.
# Les vistes de l'OV i de les integracions entrants amb token (Giswater, Smart Metering)
# NO són aquí: el middleware només limita els usuaris d'aquests grups, però un usuari
# intern també les pot cridar, i per això són a la baseline.
EXEMPT_VIEWS = {
    'auth.views.CustomAuthToken': 'login (obté el token)',
    'auth.views.LogoutView': 'tanca la sessió pròpia (revoca el token de la petició)',
    'auth.views.UserPermissionsView': "permisos de l'usuari mateix",
    'auth.views.OwnProfileView': "fitxa de l'usuari mateix (sempre request.user; canviar el correu demana la contrasenya)",
    'auth.views.ChangeOwnPasswordView': "contrasenya de l'usuari mateix (sempre request.user; demana l'actual)",
    'auth.views.PasswordResetRequestView': 'recuperació de contrasenya des del login (sense sessió, límit per IP)',
    'auth.views.PasswordResetConfirmView': "enllaç de recuperació de contrasenya (sense sessió, token d'un sol ús, límit per IP)",
    'integrations.inbound.gmao.views.GMAOLoginView': 'login de la integració GMAO',
    'integrations.inbound.odoo.views.OdooBatchResultView': 'callback amb Bearer token propi',
    'integrations.inbound.signing.views.SigningCallbackView': 'callback de signatura amb clau pròpia',
    'communication.views.sms_callback_view.SmsCallbackView': "callback del proveïdor d'SMS",
    'lecturapp.views.AuthenticationView': "login de l'app de lectures",
    'lecturapp.views.validate_token': "validació del token de l'app de lectures",
    'lecturapp.views.ReadingOperatorViewSet': "autenticació pròpia de l'app de lectures",
    'billing.views.reader_alert_view.ReaderAlertAppViewSet': "autenticació pròpia de l'app de lectures",
    'notification.views.incident_view.IncidentAppViewSet': "autenticació pròpia de l'app de lectures",
    'service.views.route_position_view.RoutePositionAppViewSet': "autenticació pròpia de l'app de lectures",
    'service.views.supply_point_placement_view.SupplyPointPlacementAppViewSet': "autenticació pròpia de l'app de lectures",
    'coredata.views.deploy_info_view.DeployInfoView': 'versió del desplegament, sense dades de clients',
    'documentmanager.views_export.export_job_view.ExportJobViewSet': "cua de descàrregues de l'usuari: el queryset és sempre el de request.user",
    'rest_framework.routers.APIRootView': "índex d'URLs de l'API, sense dades",
}

HTTP_METHODS = ('get', 'post', 'put', 'patch', 'delete')


def _view_name(view_class):
    # @api_view crea una WrappedAPIView amb el __name__ i el __module__ de la funció.
    return f'{view_class.__module__}.{view_class.__name__}'


def _excluded_apps():
    """Apps privades o de client (fora del repositori): no s'auditen, perquè a la CI no hi són."""
    return set(getattr(settings, 'LOCAL_OWN_APPS', [])) | set(getattr(settings, 'PLUGIN_APPS', []))


def _iter_patterns(patterns):
    for entry in patterns:
        if isinstance(entry, URLResolver):
            yield from _iter_patterns(entry.url_patterns)
        elif isinstance(entry, URLPattern):
            yield entry


def is_open_permission(permission, method):
    """Si el permís deixa passar qualsevol usuari autenticat per a `method` (en majúscules)."""
    if isinstance(permission, drf_permissions.OR):
        return is_open_permission(permission.op1, method) or is_open_permission(permission.op2, method)
    if isinstance(permission, drf_permissions.AND):
        return is_open_permission(permission.op1, method) and is_open_permission(permission.op2, method)
    if type(permission) in OPEN_PERMISSION_CLASSES:
        return True
    if isinstance(permission, drf_permissions.DjangoModelPermissions):
        # Si la subclasse no canvia has_permission, decideix el perms_map; si el canvia,
        # és una regla pròpia i es dona per bona.
        if type(permission).has_permission is drf_permissions.DjangoModelPermissions.has_permission:
            return not permission.perms_map.get(method)
        return False
    # Qualsevol altre permís (de l'app, IsAdminUser, NOT...) es considera propi.
    return False


def _permissions_for(view_class, initkwargs, method, action, factory):
    """Instancia la vista per a (mètode, acció) i retorna (permisos, nota).
    Permisos None si get_permissions() ja denega la petició anònima."""
    view = view_class(**initkwargs)
    view.args = ()
    view.kwargs = {}
    view.format_kwarg = None
    view.headers = {}
    if action is not None:
        view.action = action
    view.request = Request(factory.generic(method.upper(), '/'))
    overridden = view_class.get_permissions is not APIView.get_permissions
    try:
        return view.get_permissions(), ('get_permissions' if overridden else '')
    except (drf_exceptions.NotAuthenticated, drf_exceptions.PermissionDenied):
        # get_permissions ja comprova l'usuari (la petició és anònima): té control propi.
        return None, 'get_permissions'
    except Exception:  # noqa: BLE001 - la vista necessita una petició real: només els declarats
        return [cls() for cls in view.permission_classes], 'get_permissions no avaluable'


def _route_methods(callback, view_class):
    """[(mètode, acció)] que atén la ruta. Acció None per a les APIView."""
    actions = getattr(callback, 'actions', None)
    if actions:
        return [(method, action) for method, action in actions.items() if method in HTTP_METHODS]
    return [(method, None) for method in HTTP_METHODS if hasattr(view_class, method)]


def iter_drf_routes(urlconf=None):
    """(nom, callback, classe) de cada ruta servida per una vista DRF."""
    for pattern in _iter_patterns(get_resolver(urlconf).url_patterns):
        callback = pattern.callback
        view_class = getattr(callback, 'cls', None)
        if view_class is not None and issubclass(view_class, APIView):
            yield _view_name(view_class), callback, view_class


def collect_open_views(urlconf=None):
    """{nom de la vista: {'methods': set('GET list', ...), 'notes': set()}} de les vistes obertes."""
    factory = APIRequestFactory()
    excluded_apps = _excluded_apps()
    open_views = {}
    for name, callback, view_class in iter_drf_routes(urlconf):
        if name.split('.', 1)[0] in excluded_apps or name in EXEMPT_VIEWS:
            continue
        initkwargs = getattr(callback, 'initkwargs', {}) or {}
        for method, action in _route_methods(callback, view_class):
            if action in EXEMPT_ACTIONS:
                continue
            perms, note = _permissions_for(view_class, initkwargs, method, action, factory)
            if perms is not None and all(is_open_permission(perm, method.upper()) for perm in perms):
                entry = open_views.setdefault(name, {'methods': set(), 'notes': set()})
                entry['methods'].add(f'{method.upper()} {action}' if action else method.upper())
                if note:
                    entry['notes'].add(note)
    return open_views


def load_baseline(path=BASELINE_PATH):
    """Noms de la baseline, sense comentaris ni línies buides."""
    names = []
    for line in path.read_text(encoding='utf-8').splitlines():
        line = line.split('#', 1)[0].strip()
        if line:
            names.append(line)
    return names


BASELINE_HEADER = """\
# Vistes DRF que avui es poden cridar sense un permís propi (tiquets 2652/2654).
#
# Cada línia és una vista (mòdul.Classe) "oberta": qualsevol usuari autenticat en pot
# fer algun mètode perquè només té IsAuthenticated/AllowAny o DjangoModelPermissions
# de DRF (que no demana res per a GET). Algunes ho comproven dins del codi de la
# vista, cosa que aquest test no veu: cal revisar-les mòdul a mòdul. El test customers/tests_view_permissions_routes.py falla si apareix una vista
# oberta que no és aquí (vista nova sense permís) o si una d'aquí ja no existeix o ja
# no és oberta: aquesta llista només s'ha d'escurçar a mesura que es migren els
# mòduls (p. ex. a auth.permissions.DjangoModelViewPermissions).
#
# Regenerar-la (després de migrar vistes, no per acceptar-ne de noves):
#   python manage.py view_permissions_audit --write-baseline
"""


def write_baseline(names, path=BASELINE_PATH):
    path.write_text(BASELINE_HEADER + '\n' + ''.join(f'{name}\n' for name in sorted(names)), encoding='utf-8')
