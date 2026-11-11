import importlib
import sys
import tempfile
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase

from customers.plugins import plugin_app_names


class PluginAppNamesTests(SimpleTestCase):
    def test_empty_list_loads_nothing(self):
        self.assertEqual(plugin_app_names(Path("/unused"), []), [])
        self.assertEqual(plugin_app_names(Path("/unused"), ["", "  "]), [])

    def test_unknown_plugin_stops_startup(self):
        with self.assertRaises(ImproperlyConfigured):
            plugin_app_names(Path("/unused"), ["plugin_que_no_existeix"])

    def test_invalid_name_is_rejected(self):
        with self.assertRaises(ImproperlyConfigured):
            plugin_app_names(Path("/unused"), ["../plugin"])

    def test_local_checkout_is_importable(self):
        """Una còpia local s'importa i la seva vista es resol sota el prefix."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            package = root / "demo" / "demo"
            package.mkdir(parents=True)
            (package / "__init__.py").write_text("MARKER = 1\n", encoding="utf-8")
            (package / "urls.py").write_text(
                "from django.http import HttpResponse\n"
                "from django.urls import path\n"
                "def ping(request):\n"
                "    return HttpResponse('ok')\n"
                "urlpatterns = [path('ping/', ping, name='ping')]\n",
                encoding="utf-8",
            )
            entry = str(root / "demo")
            try:
                names = plugin_app_names(Path("/unused"), ["demo"], plugins_root=root)
                self.assertEqual(names, ["demo"])
                self.assertEqual(importlib.import_module("demo").MARKER, 1)

                from django.urls import include, path

                from customers.urls import append_plugin_routes

                routes = []
                append_plugin_routes(routes, names)
                match = path("", include(routes)).resolve("demo/ping/")
                self.assertEqual(match.url_name, "ping")
            finally:
                sys.modules.pop("demo.urls", None)
                sys.modules.pop("demo", None)
                if entry in sys.path:
                    sys.path.remove(entry)
                importlib.invalidate_caches()

    def test_local_checkout_rejects_an_already_imported_module(self):
        """Un nom que ja és un mòdul carregat no es fa passar pel paquet local."""
        import json

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            package = root / "json" / "json"
            package.mkdir(parents=True)
            (package / "__init__.py").write_text("MARKER = 1\n", encoding="utf-8")
            entry = str(root / "json")
            try:
                with self.assertRaises(ImproperlyConfigured):
                    plugin_app_names(Path("/unused"), ["json"], plugins_root=root)
                self.assertIs(sys.modules["json"], json)
            finally:
                if entry in sys.path:
                    sys.path.remove(entry)
                importlib.invalidate_caches()

    def test_existing_prefix_stays_and_the_plugin_moves(self):
        """Una ruta ja registrada es conserva; el plugin queda a /plugins/<nom>/."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            package = root / "routeplug" / "routeplug"
            package.mkdir(parents=True)
            (package / "__init__.py").write_text("", encoding="utf-8")
            (package / "urls.py").write_text(
                "from django.http import HttpResponse\n"
                "from django.urls import path\n"
                "def ping(request):\n"
                "    return HttpResponse('ok')\n"
                "urlpatterns = [path('ping/', ping, name='plugin-ping')]\n",
                encoding="utf-8",
            )
            entry = str(root / "routeplug")
            try:
                plugin_app_names(Path("/unused"), ["routeplug"], plugins_root=root)
                from django.http import HttpResponse
                from django.urls import path

                from customers.urls import append_plugin_routes

                def kept(request):
                    return HttpResponse("kept")

                routes = [path("routeplug/", kept, name="kept")]
                append_plugin_routes(routes, ["routeplug"])
                self.assertEqual(routes[0].resolve("routeplug/").url_name, "kept")
                self.assertEqual(
                    routes[1].resolve("plugins/routeplug/ping/").url_name,
                    "plugin-ping",
                )
            finally:
                sys.modules.pop("routeplug.urls", None)
                sys.modules.pop("routeplug", None)
                if entry in sys.path:
                    sys.path.remove(entry)
                importlib.invalidate_caches()
