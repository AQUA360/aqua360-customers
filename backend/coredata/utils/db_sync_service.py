"""Activar/desactivar la sincronització nocturna de dades de prod a l'entorn de test.

Cada nit, un cron de l'host del servidor de test restaura a la BD de test l'última còpia
de prod (`restore.sh`, scripts del desplegament). L'aplicació no pot executar res a l'host, i
l'opció no es pot desar a la BD (la restauració la sobreescriuria amb la de prod), així que
es desa com un fitxer a una carpeta compartida amb l'host (`settings.DB_SYNC_CONTROL_DIR`,
muntada a `/app/sync-control`): mentre hi ha el fitxer `disabled`, `restore.sh` no restaura.

Només està disponible quan `settings.ENV` és `test`, `staging` o `local`.
"""

import os
import tempfile
from pathlib import Path

from django.conf import settings
from django.utils import timezone

TEST_ENV_NAMES = frozenset({"test", "staging", "local"})

DISABLED_FILE = "disabled"


class DbSyncError(Exception):
    """Error de negoci: el missatge és un codi que el frontend tradueix."""

    def __init__(self, code):
        super().__init__(code)
        self.code = code


def is_test_environment():
    return (getattr(settings, "ENV", "") or "").strip().lower() in TEST_ENV_NAMES


def _control_dir():
    return Path(settings.DB_SYNC_CONTROL_DIR)


def _control_dir_ok():
    directory = _control_dir()
    return directory.is_dir() and os.access(directory, os.W_OK)


def _read_disabled():
    """Contingut del fitxer `disabled` (`clau=valor` per línia) o None si no existeix."""
    try:
        lines = (_control_dir() / DISABLED_FILE).read_text(encoding="utf-8").splitlines()
    except OSError:
        return None
    data = {}
    for line in lines:
        key, sep, value = line.partition("=")
        if sep:
            data[key.strip()] = value.strip()
    return data


def _write_atomic(name, content):
    """Escriu sencer o res: l'host no ha de llegir mai un fitxer a mitges."""
    directory = _control_dir()
    fd, tmp = tempfile.mkstemp(dir=directory, prefix=".tmp.")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(content)
        os.chmod(tmp, 0o664)
        os.replace(tmp, directory / name)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _sanitize_username(username):
    return "".join(c for c in (username or "") if c.isalnum() or c in "._@+-")[:150]


def get_status():
    disabled = _read_disabled()
    return {
        "env": settings.ENV,
        "control_dir_ok": _control_dir_ok(),
        "nightly_enabled": disabled is None,
        "disabled_by": (disabled or {}).get("disabled_by") or None,
        "disabled_at": (disabled or {}).get("disabled_at") or None,
    }


def set_nightly_enabled(enabled, user):
    if not _control_dir_ok():
        raise DbSyncError("control_dir_unavailable")
    if enabled:
        try:
            (_control_dir() / DISABLED_FILE).unlink()
        except FileNotFoundError:
            pass
    else:
        _write_atomic(
            DISABLED_FILE,
            f"disabled_by={_sanitize_username(user.username)}\n"
            f"disabled_at={timezone.now().isoformat(timespec='seconds')}\n",
        )
    return get_status()
