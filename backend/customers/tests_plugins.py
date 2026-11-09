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
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            package = root / "demo" / "demo"
            package.mkdir(parents=True)
            (package / "__init__.py").write_text("MARKER = 1\n", encoding="utf-8")
            entry = str(root / "demo")
            try:
                names = plugin_app_names(Path("/unused"), ["demo"], plugins_root=root)
                self.assertEqual(names, ["demo"])
                self.assertEqual(importlib.import_module("demo").MARKER, 1)
            finally:
                sys.modules.pop("demo", None)
                if entry in sys.path:
                    sys.path.remove(entry)
                importlib.invalidate_caches()
