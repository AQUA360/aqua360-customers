#!/usr/bin/env bash
# Entrada per al servei celery-worker del compose (sense migrate).
# Ignora els arguments extra que Docker afegeix del CMD per defecte de la imatge.
set -euo pipefail
cd /app
/app/docker-check-writable.sh /app/media
python manage.py compilemessages
exec celery -A customers worker --loglevel=INFO
