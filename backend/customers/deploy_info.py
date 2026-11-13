"""Informació del deploy que s'està executant.

Al monorepo les imatges es construeixen a GitHub Actions
(`.github/workflows/imatges.yml`), que passa la versió, el commit i la data
del build com a build args. El `Dockerfile` executa aquest mòdul
(`python -m customers.deploy_info <fitxer>`) per escriure `deploy_info.json` a
l'arrel del codi (`BASE_DIR`). Aquí es llegeix per servir-la a
`/coredata/deploy-info/` i que el frontend la mostri al NavSidebar.

La data del build (`built_at`) és la de la imatge, que pot ser d'uns dies
abans que s'instal·li al client. La data del desplegament (`deployed_at`) surt
de l'historial `coredata.DeployRecord`: `record_deploy` hi desa cada versió
nova la primera vegada que s'executa (el backend, en arrencar el contenidor;
el frontend, quan el navegador l'informa).

En desenvolupament el fitxer no existeix: s'intenta llegir el commit del git
local (el `.git` del monorepo és a la carpeta pare i `git -C` el troba) i, si
tampoc hi ha git, es retornen els camps buits.
"""

import json
import logging
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from django.conf import settings

DEPLOY_INFO_FILENAME = "deploy_info.json"
REPO_NAME = "aqua360-customers"
COMPONENT = "backend"

logger = logging.getLogger(__name__)

_cache = None
_cache_mtime = None


def _empty_info(source):
    return {
        "repo": REPO_NAME,
        "component": COMPONENT,
        "deployed_at": None,
        "built_at": None,
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
    built_at = (env.get("BUILD_DATE") or "").strip() or _utc_now_iso()
    info.update({
        # Fins que no es registra el desplegament, la data és la del build.
        "deployed_at": built_at,
        "built_at": built_at,
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
            # Al fitxer, `deployed_at` és la data del build de la imatge.
            info.setdefault("built_at", info.get("deployed_at"))

    if info is None:
        info = _from_git(settings.BASE_DIR)

    if info is None:
        info = _empty_info("unknown")

    _cache, _cache_mtime = info, mtime
    return info


def _parse_datetime(value):
    from django.utils.dateparse import parse_datetime

    if not value or not isinstance(value, str):
        return None
    try:
        return parse_datetime(value)
    except ValueError:
        return None


def record_deploy(component, info):
    """Desa la versió a l'historial si és nova i en retorna la data del desplegament.

    Una versió és nova si no és la darrera registrada del component: tornar a
    una versió anterior també és un desplegament. Sense versió ni commit, o en
    desenvolupament (git local), no es desa res i es retorna None.
    """
    if info.get("source") in ("git", "unknown"):
        return None
    release = (info.get("release") or "").strip()[:100]
    commit = (info.get("commit_full") or info.get("commit") or "").strip()[:40]
    if not release and not commit:
        return None

    # Aquest mòdul també s'executa en construir la imatge, sense Django configurat.
    from django.db import DatabaseError, transaction
    from coredata.models import DeployRecord

    try:
        with transaction.atomic():
            last = DeployRecord.objects.select_for_update().filter(component=component).first()
            if last and last.release == release and last.commit == commit:
                return last.deployed_at
            record = DeployRecord.objects.create(
                component=component,
                release=release,
                commit=commit,
                branch=(info.get("branch") or "").strip()[:100],
                built_at=_parse_datetime(info.get("built_at")),
            )
            return record.deployed_at
    except DatabaseError:
        logger.exception("No s'ha pogut desar el desplegament del %s", component)
        return None


def with_deploy_date(component, info):
    """Còpia de `info` amb `deployed_at` = data del desplegament (de l'historial).

    Si no es pot registrar, es manté la data del build: és la millor que hi ha.
    """
    info = dict(info)
    deployed_at = record_deploy(component, info)
    if deployed_at is not None:
        info["deployed_at"] = deployed_at.isoformat().replace("+00:00", "Z")
    return info


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("Ús: python -m customers.deploy_info <fitxer de sortida>")
    print(json.dumps(write_deploy_info(sys.argv[1])))
