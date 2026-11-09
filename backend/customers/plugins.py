import importlib
import re
import sys
from importlib.util import find_spec
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

_APP_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def plugin_app_names(base_dir, names, plugins_root=None):
    """Retorna les apps de PLUGINS i fa importable una còpia local.

    Una còpia a ``plugins/<nom>/<nom>/`` (a l'arrel del monorepo, fora de la
    imatge pública) s'afegeix a ``sys.path``. Si el paquet ja està instal·lat
    a la imatge, s'usa directament. Un nom que no es pot importar atura
    l'arrencada.
    """
    cleaned = []
    for name in names:
        name = (name or "").strip()
        if not name or name in cleaned:
            continue
        if _APP_NAME.match(name) is None:
            raise ImproperlyConfigured(f"PLUGINS: nom d'app no vàlid: {name!r}")
        cleaned.append(name)
    if not cleaned:
        return []

    root = Path(plugins_root) if plugins_root is not None else Path(base_dir).parent / "plugins"
    added = False
    for name in cleaned:
        package_dir = root / name / name
        if (package_dir / "__init__.py").is_file():
            entry = str(root / name)
            if entry not in sys.path:
                sys.path.insert(0, entry)
                added = True
    if added:
        importlib.invalidate_caches()

    missing = [name for name in cleaned if find_spec(name) is None]
    if missing:
        raise ImproperlyConfigured(
            "PLUGINS inclou apps que no es poden importar: "
            + ", ".join(missing)
            + ". Instal·la el paquet o deixa el codi a plugins/<nom>/<nom>/."
        )
    return cleaned
