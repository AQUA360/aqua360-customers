#!/usr/bin/env bash
# Entrada per al servei celery-beat del compose (sense migrate).
set -euo pipefail
cd /app

# Estat del beat (last_run_at/total_run_count de cada tasca) FORA de /app.
#
# Per què: `Dockerfile` fa `COPY . /app/`, i mentre el fitxer d'estat va estar
# al repo cada imatge nova el portava amb marques de temps velles. En arrencar,
# el PersistentScheduler conserva el `last_run_at` desat i troba vençudes totes
# les tasques (les mensuals incloses), de manera que cada desplegament les
# executava totes de cop. Amb aquest camí, el fitxer viu en un directori que no
# forma part del context de build ni del `COPY`.
#
# Per defecte, doncs, cada contenidor nou comença amb l'estat buit: el
# PersistentScheduler posa `last_run_at = ara` a cada entrada nova, i per tant
# no dispara res en arrencar; la primera execució ja és a l'hora del crontab.
# Si es vol que l'estat sobrevisqui a recrear el contenidor (per exemple per no
# perdre una execució quan es desplega just a l'hora de la tasca), n'hi ha prou
# de muntar un volum a /var/lib/celery al docker-compose.yml del client:
#
#   celery-beat:
#     volumes:
#       - ./docker-data/celery-beat:/var/lib/celery
#
# ATENCIÓ: no s'ha de muntar un volum que contingui un estat antic, perquè
# tornaríem al problema d'origen.
CELERYBEAT_SCHEDULE_PATH="${CELERYBEAT_SCHEDULE_PATH:-/var/lib/celery/celerybeat-schedule}"
mkdir -p "$(dirname "$CELERYBEAT_SCHEDULE_PATH")"

python manage.py compilemessages
exec celery -A customers beat --loglevel=INFO --schedule="$CELERYBEAT_SCHEDULE_PATH"
