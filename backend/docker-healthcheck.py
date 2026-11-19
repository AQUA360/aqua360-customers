"""Prova de salut de la imatge del backend (HEALTHCHECK del Dockerfile).

La mateixa imatge corre el backend (gunicorn), el celery worker, el celery beat i el consumidor
del GMAO, i el Dockerfile només en pot declarar una. Per això mira quin procés és el principal del
contenidor (PID 1; la imatge no porta `ps`):

- gunicorn: ha de respondre la pantalla d'entrar de l'admin, com la prova del docker-compose.
- celery o una ordre de `manage.py` (el consumidor del GMAO): si el procés hi és, el contenidor està
  bé (si s'atura, el contenidor s'atura amb ell).
- encara l'script d'arrencada (migracions, collectstatic...): encara no està a punt. Durant el
  `start-period` aquests errors no compten.

El docker-compose pot declarar la seva prova i llavors mana la seva.
"""

import sys
import urllib.request


def main():
    with open("/proc/1/cmdline", "rb") as f:
        cmdline = f.read().replace(b"\0", b" ")
    # Els scripts d'arrencada (`docker-entrypoint.sh`, `docker-celery-*.sh`) fan `exec` del procés
    # bo quan acaben: mentre el PID 1 és un d'ells, el contenidor encara arrenca.
    if b".sh" in cmdline:
        print("El contenidor encara arrenca:", cmdline.decode(errors="replace").strip())
        return 1
    if b"gunicorn" in cmdline:
        urllib.request.urlopen("http://127.0.0.1:8000/admin/login/", timeout=3)
        return 0
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001 - qualsevol error vol dir que no està bé
        print(exc)
        sys.exit(1)
