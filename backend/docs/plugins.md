# Plugins

El producte es publica en obert i la imatge de GitHub només porta el codi d'aquest repositori. Una funcionalitat d'un client, o pròpia de l'empresa i que no tenen tots els clients, va en un plugin: una app Django a part, activada en aquella instal·lació.

La carpeta `plugins/` de l'arrel del monorepo és on es deixa el codi en local. No és una app Django. Cada plugin és la seva pròpia app (`iotcom`, no `plugins.iotcom`), amb les seves migracions, senyals i tasques. El nucli no l'importa.

Les integracions que viatgen amb el producte (Giswater, Odoo, smart metering) segueixen a l'app `integrations`. Una variació petita d'una funció o d'una plantilla segueix el mecanisme `*_personalized.py`. `LOCAL_OWN_APPS` queda per a eines internes que no es publiquen, com `importexport`.

## Què hi ha al repositori públic

| Peça | On |
| --- | --- |
| Carregador | `customers/plugins.py` |
| Activació | `PLUGINS` al `.env`, afegit a `INSTALLED_APPS` des de `customers/settings.py` |
| Rutes | `customers/urls.py` munta `/<app>/` només si el plugin té `urls.py` |
| Imatge del servidor | `BACKEND_IMAGE` al `docker-compose.yml` (backend, worker, beat i consumidor GMAO) |
| Codi del plugin | Fora del repositori: `/plugins/` és al `.gitignore` |

`PLUGINS` és una llista separada per comes (`PLUGINS=iotcom`). El procés no arrenca si un nom no es pot importar. Sense la variable, no es carrega cap plugin.

En local, el carregador busca `plugins/<nom>/<nom>/` a l'arrel del monorepo (el directori pare de `backend/`) i l'afegeix al `sys.path`. Si el paquet ja és a la imatge, l'usa directament.

## Imatge i desplegament

`.github/workflows/imatges.yml` publica `ghcr.io/aqua360/aqua360-customers-backend` i `…-frontend`. El registre és públic. El plugin es construeix en un repositori privat, amb una imatge fina que parteix de la release:

```dockerfile
ARG CUSTOMERS_VERSION=local
FROM ghcr.io/aqua360/aqua360-customers-backend:${CUSTOMERS_VERSION}

COPY iotcom /opt/plugins/iotcom
ENV PYTHONPATH=/opt/plugins
ENV PLUGINS=iotcom
```

Es publica, per exemple, com a `ghcr.io/aqua360/aqua360-customers-backend-iotcom:v1.152.00`. Al `.env` d'aquell client:

```dotenv
CUSTOMERS_VERSION=v1.152.00
BACKEND_IMAGE=ghcr.io/aqua360/aqua360-customers-backend-iotcom:v1.152.00
PLUGINS=iotcom
```

El desplegament no canvia: `docker compose pull && docker compose up -d`. Sense `BACKEND_IMAGE` es baixa la imatge pública. El frontend es queda a la imatge pública: un plugin que només reacciona a senyals no hi afegeix pantalles, perquè el frontend ja va compilat.

Quan surt una release nova del producte, es reconstrueix la imatge privada amb el `FROM` d'aquella etiqueta. Si el plugin canvia sense release de producte, es publica una etiqueta nova (`v1.152.00-iotcom.2`) i només es canvia `BACKEND_IMAGE` en aquell client. El servidor necessita un `docker login ghcr.io` que pugui llegir el paquet privat.

El worker i el beat han d'usar la mateixa imatge. Si no, la tasca en cua no troba el codi del plugin. `BACKEND_IMAGE` ja els cobreix, i també el consumidor GMAO.

Per provar-ho en aquest monorepo, primer es reconstrueix la imatge local (porta el carregador) i després la del plugin:

```bash
docker compose build backend
docker build -f plugins/iotcom/Dockerfile \
  --build-arg CUSTOMERS_VERSION=local-${COMPOSE_PROJECT_NAME:-aqua360-customers-module-monorepo-dockers} \
  -t ghcr.io/aqua360/aqua360-customers-backend-iotcom:local \
  plugins/iotcom
```

`BACKEND_IMAGE` apunta a aquesta etiqueta. Posar `PLUGINS=iotcom` amb la imatge pública fa que el procés no arrenqui: el paquet no hi és.

## Contracte d'un plugin

Estructura mínima:

```text
plugins/iotcom/
  Dockerfile
  iotcom/
    __init__.py
    apps.py          # ready() connecta els senyals
    signals.py
    tasks.py         # Celery, si n'hi ha
    migrations/
```

- `AppConfig.name` és el nom de l'app (`iotcom`). `ready()` registra els senyals. El nucli no importa el plugin.
- Les migracions són de l'app (`iotcom.0001_…`) i només corren on `PLUGINS` la inclou.
- Les tasques es descobreixen soles perquè l'app és a `INSTALLED_APPS`.
- Un `urls.py` es publica a `/iotcom/`.
- El plugin llegeix els seus secrets de l'entorn. No s'afegeixen a `customers/settings.py`.
- Un `QuerySet.update()` no dispara senyals de Django. El canvi ha de passar per `save()` del model.

## IOTCOM

Primer plugin. Quan un comptador (`service.Meter`) es desa i l'estat passa a ser l'estat Instal·lat configurat, i la tecnologia de comunicació és una de les d'IOTCOM, s'encua `iotcom.sync_meter_installation`. El POST es fa després del commit. Tornar a desar el comptador sense canviar l'estat no l'envia una altra vegada. Crear-lo ja en aquest estat sí que l'envia. Canviar només la tecnologia mentre ja està instal·lat no l'envia.

La migració `iotcom.0001` crea dues files de `ConfigProject` buides. El camp és `token`. Mentre el valor és buit, no s'envia res.

| `ConfigProject.token` | Valor |
| --- | --- |
| `iotcom_commtechnology_tokens` | Noms de tecnologia separats per comes, punts i coma o salts de línia. Es comparen amb `Meter.comm_technology`, sense distingir majúscules. `MeterCommTechnology` només té `name`; el comptador desa aquest nom a `comm_technology`. |
| `iotcom_meter_install_token` | `token` de `MeterStatus` que significa Instal·lat, no el nom visible. |

Al `.env` del client:

```dotenv
IOTCOM_URL=https://exemple.iotcom/ruta-del-post
IOTCOM_TOKEN=el-token
IOTCOM_TIMEOUT=30
```

`IOTCOM_URL` és l'adreça completa del POST. El token viatja a `Authorization: Bearer`. Si falta l'URL o el token, es registra l'error i no s'envia; desar el comptador no falla. Un error de xarxa o una resposta HTTP d'error es torna a provar fins a cinc vegades, amb espera creixent.

El cos del POST:

```json
{
  "id": 1,
  "code": "M-1",
  "code2": null,
  "token": null,
  "comm_technology": "iotcom",
  "status_token": "installed",
  "status_name": "Instal·lat",
  "installation_at": "2026-11-09",
  "manufacturer": null,
  "model": null,
  "comm_module": null,
  "network_provider": null,
  "latitude": null,
  "longitude": null
}
```

Aquest cos és el que envia el plugin ara. Quan hi hagi el contracte de l'API d'IOTCOM, s'ajusta a `iotcom/sync.py` (`installation_payload`) sense canviar el carregador ni la imatge pública.
