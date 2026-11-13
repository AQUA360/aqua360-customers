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
| Imatge del servidor | La pública, `ghcr.io/aqua360/aqua360-customers-backend:${CUSTOMERS_VERSION}` |
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

El `FROM` de cada plugin és sempre aquesta imatge pública. Un plugin no és la base d'un altre. El servidor també continua executant-la: el backend, el worker, el beat, el consumidor GMAO i el frontend. `CUSTOMERS_VERSION` és l'única etiqueta. No es defineix una imatge alternativa del backend.

`PLUGINS` es llegeix en engegar el contenidor. No es grava a la imatge. Al `.env`, cada plugin declara el seu registre sense etiqueta:

```dotenv
CUSTOMERS_VERSION=v1.152.00
PLUGINS=exemple,altre
PLUGIN_IMAGE_exemple=ghcr.io/exemple/plugin-exemple
PLUGIN_IMAGE_altre=ghcr.io/exemple/plugin-altre
```

`PLUGIN_IMAGE_<nom>` el fa servir el pas que copia `/opt/plugins/<nom>` sobre la imatge pública abans d'engegar. Dins d'un valor del `.env`, `${CUSTOMERS_VERSION}` no s'expandeix. `docker-compose.image.yml` no forma part d'aquest desplegament.

El frontend no canvia: un plugin que només reacciona a senyals no hi afegeix pantalles, perquè ja va compilat. Quan surt una release nova del producte, es reconstrueix la imatge de cada plugin amb el `FROM` d'aquella etiqueta, i es torna a copiar sobre la pública. El worker, el beat i el consumidor GMAO han d'arrencar la mateixa imatge que el backend, amb el codi dels plugins a dins. Si hi falta, el procés no arrenca.

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
