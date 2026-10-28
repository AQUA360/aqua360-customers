"""Abocament i restauració de l'esquema de test.

L'abocament es fa després d'aplicar totes les migracions. Conserva l'estat
final: taules, vistes, triggers, funcions i les dades que insereixen les
migracions.
"""

import os
import re
import shutil
import subprocess
import sys

class SchemaDumpError(RuntimeError):
    pass


def _require_client():
    missing = [tool for tool in ("pg_dump", "psql") if shutil.which(tool) is None]
    if missing:
        raise SchemaDumpError(
            "No s'ha trobat "
            + " ni ".join(missing)
            + " al PATH. Cal el paquet postgresql-client, de la mateixa versió "
            "major que el servidor de proves."
        )


def _connection_args(settings_dict, dbname):
    args = []
    host = settings_dict.get("HOST")
    if host:
        args += ["--host", str(host)]
    port = settings_dict.get("PORT")
    if port:
        args += ["--port", str(port)]
    user = settings_dict.get("USER")
    if user:
        args += ["--username", str(user)]
    args += ["--dbname", dbname]
    return args


def _env(settings_dict):
    env = os.environ.copy()
    password = settings_dict.get("PASSWORD")
    if password:
        env["PGPASSWORD"] = str(password)
    return env


def _run(cmd, env, **kwargs):
    result = subprocess.run(cmd, env=env, **kwargs)
    if result.returncode != 0:
        stderr = result.stderr or ""
        if isinstance(stderr, bytes):
            stderr = stderr.decode("utf-8", errors="replace")
        if stderr:
            sys.stderr.write(stderr)
        raise SchemaDumpError(f"{cmd[0]} ha acabat amb codi {result.returncode}.")
    return result


def sanitize_dump(sql):
    """Treu metaordres de psql que canvien entre versions del client.

    \\restrict/\\unrestrict i SET transaction_timeout apareixen en abocaments
    fets amb un client més nou que el servidor PostgreSQL 16. Fora dels blocs
    COPY, no formen part de l'esquema.
    """
    out = []
    in_copy = False
    for line in sql.splitlines(keepends=True):
        bare = line.rstrip("\r\n")
        if in_copy:
            out.append(line)
            if bare == "\\.":
                in_copy = False
            continue
        if bare.startswith("COPY ") and bare.endswith("FROM stdin;"):
            in_copy = True
            out.append(line)
            continue
        if bare.startswith("\\restrict ") or bare.startswith("\\unrestrict "):
            continue
        if bare.startswith("SET transaction_timeout "):
            continue
        out.append(line)
    body = "".join(out)
    header = (
        "-- Esquema de test generat per build_test_schema.\n"
        "-- Estat final de les migracions: taules, vistes, triggers i dades inicials.\n"
        "-- Es reconstrueix quan canvia qualsevol fitxer de migració. No editar a mà.\n\n"
    )
    return header + body


def dump_database(settings_dict, dbname, output_path):
    _require_client()
    output_path = os.path.abspath(output_path)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    cmd = [
        "pg_dump",
        "--format=plain",
        "--no-owner",
        "--no-acl",
        "--no-comments",
        "--encoding=UTF8",
        *_connection_args(settings_dict, dbname),
    ]
    with open(output_path, "w", encoding="utf-8") as stdout:
        _run(
            cmd,
            _env(settings_dict),
            stdout=stdout,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
        )
    with open(output_path, encoding="utf-8") as handle:
        cleaned = sanitize_dump(handle.read())
    with open(output_path, "w", encoding="utf-8") as handle:
        handle.write(cleaned)
    if "django_migrations" not in cleaned:
        raise SchemaDumpError(
            f"L'abocament {output_path} no conté django_migrations. "
            "Les migracions no s'han aplicat."
        )


def load_sql_file(settings_dict, dbname, sql_path):
    _require_client()
    cmd = [
        "psql",
        "--set",
        "ON_ERROR_STOP=1",
        "--quiet",
        "--no-psqlrc",
        "--file",
        os.path.abspath(sql_path),
        *_connection_args(settings_dict, dbname),
    ]
    _run(
        cmd,
        _env(settings_dict),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
    )


def client_major():
    if shutil.which("pg_dump") is None:
        return None
    result = subprocess.run(
        ["pg_dump", "--version"],
        capture_output=True,
        text=True,
        check=False,
    )
    match = re.search(r"(\d+)\.\d+", result.stdout or "")
    return int(match.group(1)) if match else None
