"""Informació del deploy que s'està executant.

`scripts/record_deploy.sh` escriu `deploy_info.json` a l'arrel del codi
desplegat (veure `config/deploy.rb` i `config/deploy_docker.rb`) amb la data
del deploy i el commit. Aquí només es llegeix, per servir-la a
`/coredata/deploy-info/` i que el frontend pugui mostrar-la al NavSidebar.

En desenvolupament el fitxer no existeix: s'intenta llegir el commit del git
local i, si tampoc hi ha git, es retornen els camps buits.
"""

import json
import subprocess
from pathlib import Path

from django.conf import settings

DEPLOY_INFO_FILENAME = "deploy_info.json"

_cache = None
_cache_mtime = None


def _read_json(path):
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _git(base_dir, *args):
    try:
        out = subprocess.run(
            ["git", "-C", str(base_dir), *args],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return out.stdout.strip() if out.returncode == 0 else ""


def _from_git(base_dir):
    """Informació derivada del git local (només entorns de desenvolupament)."""
    commit_full = _git(base_dir, "rev-parse", "HEAD")
    if not commit_full:
        return None

    return {
        "repo": "avsis-customers-backend",
        # Sense deploy no hi ha data de deploy: s'informa la del commit i el
        # frontend ja mostra que és una còpia de desenvolupament.
        "deployed_at": None,
        "commit": commit_full[:8],
        "commit_full": commit_full,
        "commit_date": _git(base_dir, "log", "-1", "--format=%cI"),
        "commit_subject": _git(base_dir, "log", "-1", "--format=%s"),
        "branch": _git(base_dir, "rev-parse", "--abbrev-ref", "HEAD"),
        "release": "",
        "source": "git",
    }


def get_deploy_info(refresh=False):
    """Retorna un dict amb la informació del deploy actual (mai None).

    Es memoritza en memòria i es rellegeix si el fitxer canvia de data de
    modificació, de manera que un deploy sobre el mateix procés (Docker amb
    volum muntat) no serveixi dades velles.
    """
    global _cache, _cache_mtime

    path = Path(settings.BASE_DIR) / DEPLOY_INFO_FILENAME
    try:
        mtime = path.stat().st_mtime
    except OSError:
        mtime = None

    if not refresh and _cache is not None and mtime == _cache_mtime:
        return _cache

    info = None
    if mtime is not None:
        info = _read_json(path)
        if info is not None:
            info.setdefault("source", "deploy")

    if info is None:
        info = _from_git(settings.BASE_DIR)

    if info is None:
        info = {
            "repo": "avsis-customers-backend",
            "deployed_at": None,
            "commit": "",
            "commit_full": "",
            "commit_date": "",
            "commit_subject": "",
            "branch": "",
            "release": "",
            "source": "unknown",
        }

    _cache, _cache_mtime = info, mtime
    return info
