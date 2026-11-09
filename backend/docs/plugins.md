# Plugins

El producte es publica en obert i la imatge de GitHub només porta el codi d'aquest repositori. Una funcionalitat que no tenen totes les instal·lacions va en un plugin: una app Django a part, activada allà on cal. El codi del plugin no és en aquest repositori.

La carpeta `plugins/` de l'arrel del monorepo és on es deixa el codi en local. No és una app Django. Cada plugin és la seva pròpia app, amb les seves migracions, senyals i tasques. El nucli no l'importa.

Les integracions que viatgen amb el producte (Giswater, Odoo, smart metering) segueixen a l'app `integrations`. Una variació petita d'una funció o d'una plantilla segueix el mecanisme `*_personalized.py`. `LOCAL_OWN_APPS` queda per a eines internes que no es publiquen, com `importexport`.

## Què hi ha al repositori públic

| Peça | On |
| --- | --- |
| Carregador | `customers/plugins.py` |
| Activació | `PLUGINS` al `.env`, afegit a `INSTALLED_APPS` des de `customers/settings.py` |
| Rutes | `customers/urls.py` munta `/<app>/` només si el plugin té `urls.py` |
| Imatge del servidor | `BACKEND_IMAGE` i `docker-compose.image.yml` (backend, worker, beat i consumidor GMAO) |
| Codi del plugin | Fora del repositori: `/plugins/` és al `.gitignore` |

`PLUGINS` és una llista separada per comes. El procés no arrenca si un nom no es pot importar. Sense la variable, no es carrega cap plugin.

En local, el carregador comprova que existeixi `plugins/<nom>/<nom>/` (a l'arrel del monorepo, el directori pare de `backend/`) i afegeix el directori pare `plugins/<nom>/` a `sys.path`, no el directori intern del paquet. El mòdul que s'importa és `<nom>`. Si aquest directori no hi és i el paquet ja és a la imatge, l'usa directament.

## Imatge i desplegament

`.github/workflows/imatges.yml` publica `ghcr.io/aqua360/aqua360-customers-backend` i `…-frontend`. El registre és públic i la imatge no porta plugins. Qui necessiti un plugin construeix una imatge fina a partir de la release, al seu repositori:

```dockerfile
ARG CUSTOMERS_VERSION=local
FROM ghcr.io/aqua360/aqua360-customers-backend:${CUSTOMERS_VERSION}

COPY exemple /opt/plugins/exemple
ENV PYTHONPATH=/opt/plugins
```

`PLUGINS` es defineix en engegar el contenidor, al `.env`. No va a la imatge: si es treu del `.env`, no queda cap valor anterior.

`docker compose build` i `up --build` etiqueten la imatge pública local (`ghcr.io/aqua360/aqua360-customers-backend` amb `CUSTOMERS_VERSION` o `local-<stack>`). Per consumir una imatge privada sense que aquesta compilació la reetiqueti, el `.env` ha de dir:

```dotenv
BACKEND_IMAGE=ghcr.io/exemple/backend-amb-plugin:v1.152.00
COMPOSE_FILE=docker-compose.yml:docker-compose.image.yml
PLUGINS=exemple
```

`docker-compose.image.yml` posa `BACKEND_IMAGE` al backend, al worker, al beat i al consumidor GMAO, i en treu el `build`. `CUSTOMERS_VERSION` continua triant el frontend.

El desplegament continua sent `docker compose pull && docker compose up -d`. Sense `docker-compose.image.yml` es fa servir la imatge pública. El frontend no canvia: un plugin que només reacciona a senyals no hi afegeix pantalles, perquè el frontend ja va compilat.

Quan surt una release nova del producte, es reconstrueix la imatge del plugin amb el `FROM` d'aquella etiqueta. El worker, el beat i el consumidor GMAO han de fer servir la mateixa imatge que el backend; el fitxer d'imatge els la posa tots.

Posar `PLUGINS` amb la imatge pública fa que el procés no arrenqui: el paquet no hi és.

## Contracte d'un plugin

Estructura mínima, amb `exemple` com a nom de l'app:

```text
plugins/exemple/
  Dockerfile
  exemple/
    __init__.py
    apps.py          # ready() connecta els senyals
    signals.py
    tasks.py         # Celery, si n'hi ha
    migrations/
```

- `AppConfig.name` és el nom de l'app. `ready()` registra els senyals. El nucli no importa el plugin.
- Les migracions són de l'app i només corren on `PLUGINS` la inclou.
- Les tasques es descobreixen soles perquè l'app és a `INSTALLED_APPS`.
- Un `urls.py` es publica a `/<nom>/`. Si aquest prefix ja el fa servir el producte, queda a `/plugins/<nom>/`.
- El plugin llegeix els seus secrets de l'entorn. No s'afegeixen a `customers/settings.py`.
- Un `QuerySet.update()` no dispara senyals de Django. El canvi ha de passar per `save()` del model.
