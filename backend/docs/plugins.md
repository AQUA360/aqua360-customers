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
| Imatge del servidor | `BACKEND_IMAGE` al `docker-compose.yml` (backend, worker, beat i consumidor GMAO) |
| Codi del plugin | Fora del repositori: `/plugins/` és al `.gitignore` |

`PLUGINS` és una llista separada per comes. El procés no arrenca si un nom no es pot importar. Sense la variable, no es carrega cap plugin.

En local, el carregador busca `plugins/<nom>/<nom>/` a l'arrel del monorepo (el directori pare de `backend/`) i l'afegeix al `sys.path`. Si el paquet ja és a la imatge, l'usa directament. El clon ha de quedar a `plugins/<nom>`, perquè el paquet que s'importa és `plugins/<nom>/<nom>/`.

## Imatge i desplegament

`.github/workflows/imatges.yml` publica `ghcr.io/aqua360/aqua360-customers-backend` i `…-frontend`. El registre és públic i la imatge no porta plugins. Qui necessiti un plugin construeix una imatge fina a partir de la release, al seu repositori:

```dockerfile
ARG CUSTOMERS_VERSION=local
FROM ghcr.io/aqua360/aqua360-customers-backend:${CUSTOMERS_VERSION}

COPY exemple /opt/plugins/exemple
ENV PYTHONPATH=/opt/plugins
ENV PLUGINS=exemple
```

Al `.env` d'aquella instal·lació, `BACKEND_IMAGE` apunta a aquesta imatge i `PLUGINS` n'anomena l'app. `CUSTOMERS_VERSION` continua triant el frontend i, si no hi ha `BACKEND_IMAGE`, també el backend.

El desplegament no canvia: `docker compose pull && docker compose up -d`. Sense `BACKEND_IMAGE` es baixa la imatge pública. El frontend es queda a la imatge pública: un plugin que només reacciona a senyals no hi afegeix pantalles, perquè el frontend ja va compilat.

Quan surt una release nova del producte, es reconstrueix la imatge del plugin amb el `FROM` d'aquella etiqueta. El worker i el beat han d'usar la mateixa imatge que el backend. Si no, una tasca en cua no troba el codi del plugin. `BACKEND_IMAGE` ja els cobreix, i també el consumidor GMAO.

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
- Un `urls.py` es publica a `/<nom>/`.
- El plugin llegeix els seus secrets de l'entorn. No s'afegeixen a `customers/settings.py`.
- Un `QuerySet.update()` no dispara senyals de Django. El canvi ha de passar per `save()` del model.
