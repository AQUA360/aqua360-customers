import importlib
import re
import sys
from importlib.util import find_spec
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

_APP_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _origin_in_package(spec, package_dir):
    """True si el mòdul resolt és el paquet local ``plugins/<nom>/<nom>/``."""
    origin = getattr(spec, "origin", None)
    if not origin:
        return False
    try:
        return Path(origin).resolve().is_relative_to(package_dir.resolve())
    except (OSError, ValueError):
        return False


def plugin_app_names(base_dir, names, plugins_root=None):
    """Retorna les apps de PLUGINS i fa importable una còpia local.

    Comprova ``plugins/<nom>/<nom>/`` i afegeix el directori pare
    ``plugins/<nom>/`` a ``sys.path``. Si aquest directori no hi és i el
    paquet ja està instal·lat a la imatge, l'usa. Un nom que no es pot
    importar, o que resol un mòdul ja carregat en lloc del paquet local,
    atura l'arrencada.
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

    missing = []
    collisions = []
    for name in cleaned:
        package_dir = root / name / name
        local = (package_dir / "__init__.py").is_file()
        spec = find_spec(name)
        if spec is None:
            missing.append(name)
        elif local and not _origin_in_package(spec, package_dir):
            collisions.append(name)
    if collisions:
        raise ImproperlyConfigured(
            "PLUGINS coincideix amb un mòdul ja carregat i no amb el paquet local: "
            + ", ".join(collisions)
            + ". Canvia el nom del plugin."
        )
    if missing:
        raise ImproperlyConfigured(
            "PLUGINS inclou apps que no es poden importar: "
            + ", ".join(missing)
            + ". Instal·la el paquet o deixa el codi a plugins/<nom>/<nom>/."
        )
    return cleaned
