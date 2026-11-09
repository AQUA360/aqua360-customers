from importlib.util import find_spec

from django.conf import settings
from decouple import config
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include, re_path

from billing.views.reading_batch_generate_view import TaskProgressView

from customers.views import root_view, protected_media_view

app_urls = [
    path('admin/', admin.site.urls),
    path('auth/', include('auth.urls')),
    path('coredata/', include('coredata.urls')),
    path('logger/', include('logger.urls')),
    path('service/', include('service.urls')),
    path('contract/', include('contract.urls')),
    path('order/', include('order.urls')),
    path('pricing/', include('pricing.urls')),
    path('billing/', include('billing.urls')),
    path('claimrequest/', include('claimrequest.urls')),
    path('task-progress/<str:task_id>/', TaskProgressView.as_view(), name='task-progress'),
    path('search/', include('search.urls')),
    path('documentmanager/', include('documentmanager.urls')),
    path('notification/', include('notification.urls')),
    path('dashboard/', include('dashboard.urls')),
    path('statistics/', include('statistics.urls')),
    path('fraud/', include('fraud.urls')),
    path('communication/', include('communication.urls')),
    path('lecturapp/', include('lecturapp.urls')),
    path('ov/',include('ov.urls')),
    path('got/', include('got.urls')),
    path('verifactu/', include('verifactu.urls')),
    path('signing/', include('integrations.urls')),
    path('giswater/v1/', include('integrations.inbound.giswater.urls')),
    path('smartmetering/v1/', include('integrations.inbound.smartmetering.urls')),
    path('odoo/v1/', include('integrations.inbound.odoo.urls')),
    path('gmao/v1/', include('integrations.inbound.gmao.urls')),
    # API interna genèrica de lots d'enviament (Odoo avui; altres integracions demà).
    path('send-batch/', include('integrations.urls_send_batch')),
]

# Apps locals (LOCAL_OWN_APPS al .env, p. ex. `importexport`): es munten a `/<app>/` si tenen urls.py.
for _app in settings.LOCAL_OWN_APPS:
    if find_spec(f"{_app}.urls") is not None:
        app_urls.append(path(f"{_app}/", include(f"{_app}.urls")))

def _registered_prefixes(routes):
    """Primer segment de cada ruta ja registrada, sense paràmetres."""
    prefixes = set()
    for route in routes:
        pattern = getattr(route, "pattern", None)
        if pattern is None:
            continue
        head = str(pattern).strip("/").split("/", 1)[0]
        if head and "<" not in head:
            prefixes.add(head)
    return prefixes


def append_plugin_routes(routes, app_names):
    """Munta les urls de cada plugin sense tapar una ruta anterior.

    El prefix és ``/<app>/``. Si ja existeix, el plugin queda a
    ``/plugins/<app>/``: la ruta incorporada es conserva i la del plugin
    segueix sent accessible.
    """
    for app in app_names:
        if find_spec(f"{app}.urls") is None:
            continue
        prefix = f"plugins/{app}/" if app in _registered_prefixes(routes) else f"{app}/"
        routes.append(path(prefix, include(f"{app}.urls")))


# Plugins de client (PLUGINS al .env), només si el plugin publica rutes.
append_plugin_routes(app_urls, settings.PLUGIN_APPS)

urlpatterns = [
    path('', root_view),
]

if config("API_URL_PREFIX", 'False') == 'True':
    urlpatterns += [path('api/', include((app_urls, None)))]
else:
    urlpatterns += app_urls

urlpatterns += [
    re_path(r'^media/(?P<path>.+)$', protected_media_view),
]