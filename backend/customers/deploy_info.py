"""Informació del deploy que s'està executant.

Al monorepo les imatges es construeixen a GitHub Actions
(`.github/workflows/imatges.yml`), que passa la versió, el commit i la data
del build com a build args. El `Dockerfile` executa aquest mòdul
(`python -m customers.deploy_info <fitxer>`) per escriure `deploy_info.json` a
l'arrel del codi (`BASE_DIR`). Aquí es llegeix per servir-la a
`/coredata/deploy-info/` i que el frontend la mostri al NavSidebar.

La data de deploy és la del build de la imatge: una imatge és immutable i
reiniciar el contenidor no la canvia.

En desenvolupament el fitxer no existeix: s'intenta llegir el commit del git
local (el `.git` del monorepo és a la carpeta pare i `git -C` el troba) i, si
tampoc hi ha git, es retornen els camps buits.
"""

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from django.conf import settings

DEPLOY_INFO_FILENAME = "deploy_info.json"
REPO_NAME = "aqua360-customers"
COMPONENT = "backend"

_cache = None
_cache_mtime = None


def _empty_info(source):
    return {
        "repo": REPO_NAME,
        "component": COMPONENT,
        "deployed_at": None,
        "commit": "",
        "commit_full": "",
        "commit_date": "",
        "commit_subject": "",
        "branch": "",
        "release": "",
        "source": source,
    }


def _utc_now_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def build_from_env(env=None):
    """Construeix la informació del deploy a partir dels build args de la imatge.

    Variables: `APP_VERSION`, `GIT_COMMIT`, `GIT_COMMIT_DATE`, `GIT_BRANCH` i
    `BUILD_DATE`. Sense `BUILD_DATE` (build fet al servidor sense els args) es
    fa servir l'hora actual, que és la del build.
    """
    env = os.environ if env is None else env
    commit_full = (env.get("GIT_COMMIT") or "").strip()
    info = _empty_info("build")
    info.update({
        "deployed_at": (env.get("BUILD_DATE") or "").strip() or _utc_now_iso(),
        "commit": commit_full[:8],
        "commit_full": commit_full,
        "commit_date": (env.get("GIT_COMMIT_DATE") or "").strip(),
        "branch": (env.get("GIT_BRANCH") or "").strip(),
        "release": (env.get("APP_VERSION") or "").strip(),
    })
    return info


def write_deploy_info(path, env=None):
    """Escriu `deploy_info.json` (el fa servir el Dockerfile en construir la imatge)."""
    info = build_from_env(env)
    Path(path).write_text(json.dumps(info, indent=2) + "\n", encoding="utf-8")
    return info


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

    info = _empty_info("git")
    info.update({
        # Sense deploy no hi ha data de deploy: s'informa la del commit i el
        # frontend ja mostra que és una còpia de desenvolupament.
        "commit": commit_full[:8],
        "commit_full": commit_full,
        "commit_date": _git(base_dir, "log", "-1", "--format=%cI"),
        "commit_subject": _git(base_dir, "log", "-1", "--format=%s"),
        "branch": _git(base_dir, "rev-parse", "--abbrev-ref", "HEAD"),
        "release": _git(base_dir, "describe", "--tags", "--always"),
    })
    return info


def get_deploy_info(refresh=False):
    """Retorna un dict amb la informació del deploy actual (mai None).

    Es memoritza en memòria i es rellegeix si el fitxer canvia de data de
    modificació.
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
        info = _empty_info("unknown")

    _cache, _cache_mtime = info, mtime
    return info


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("Ús: python -m customers.deploy_info <fitxer de sortida>")
    print(json.dumps(write_deploy_info(sys.argv[1])))
