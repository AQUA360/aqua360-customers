# Plugins

[Català](./README.md) · [Español](./README.es.md) · [English](./README.en.md)

Aquí es deixen els plugins de client mentre es treballa en local. Aquesta carpeta no és una app Django i el seu contingut, tret d'aquests README, no entra al repositori públic ni a la imatge de GitHub.

El carregador, les rutes i la imatge del servidor estan documentats a [backend/docs/plugins.md](../backend/docs/plugins.md). Això d'aquí és la convenció de com ha de ser un plugin.

Una funcionalitat que no tenen totes les instal·lacions va en un plugin. El que viatja amb el producte (Giswater, Odoo, smart metering) segueix a l'app `integrations`. Una variació petita d'una funció o d'una plantilla segueix `*_personalized.py`.

## Repositori

Cada plugin és un repositori a part. Es clona aquí:

```text
plugins/<nom>/
  Dockerfile
  <nom>/
    __init__.py
    apps.py
    signals.py
    tasks.py
    migrations/
```

`<nom>` és un identificador de Python (`^[A-Za-z_][A-Za-z0-9_]*$`). El directori intern es diu igual que el repositori pare. El mòdul que s'importa és `<nom>`: el carregador afegeix `plugins/<nom>/` al `sys.path`, no el directori del paquet.

<!-- coderabbit-ai-generated:v1 -->

<!-- coderabbit-ai-generated-section:v1:f5f7026274c95def4495d32de400e79ead80ec13fc531a0c8b14ff171989b4b3 -->

Amb el Compose per defecte, afegir `PLUGINS` al `.env` no fa accessible la còpia local als contenidors. Creeu `docker-compose.override.yml` a l’arrel del repositori amb aquest muntatge de `./plugins` a `/plugins` als serveis Django (el consumidor GMAO només s’executa amb el seu perfil):

```yaml
services:
  backend:
    volumes:
      - ./plugins:/plugins:ro
  celery-worker:
    volumes:
      - ./plugins:/plugins:ro
  celery-beat:
    volumes:
      - ./plugins:/plugins:ro
  gmao-consumer:
    volumes:
      - ./plugins:/plugins:ro
```

Amb l’estructura anterior, poseu `PLUGINS=<nom>` al `.env` (diversos noms separats per comes). El carregador trobarà `/plugins/<nom>/<nom>/`. Aquest override es carrega automàticament amb el Compose per defecte; si definiu `COMPOSE_FILE`, incloeu-lo explícitament a la llista. Com a alternativa, construïu la imatge privada de l’apartat «Imatge», que fa importable el paquet dins del contenidor.

<!-- /coderabbit-ai-generated:v1 -->

El nucli no importa el plugin. `AppConfig.ready()` registra els senyals, i prou.

## Activació

`PLUGINS` al `.env` és la llista separada per comes. Sense la variable no es carrega cap plugin. Si un nom no es pot importar, el procés no arrenca.

<!-- coderabbit-ai-generated:v1 -->

<!-- coderabbit-ai-generated-section:v1:11f13042bd9940eb89f9742ca56d246a83cde0c03ba0449455712c00e076e79f -->

`PLUGINS` es llegeix en arrencar el procés i no es grava a la imatge. Després de canviar-lo o treure’l del `.env`, recreeu els serveis afectats amb `docker compose up -d --force-recreate backend celery-worker celery-beat` (afegiu `gmao-consumer` si el perfil GMAO està actiu). Reiniciar els contenidors no és suficient: els contenidors existents conserven l’entorn amb què es van crear.

<!-- /coderabbit-ai-generated:v1 -->

## Bones pràctiques

- Un senyal que falla es registra i no impedeix el `save()` del producte.
- Una tasca Celery s'encua dins de `transaction.on_commit`. El worker, el beat i el consumidor GMAO han d'usar la mateixa imatge que el backend, perquè si no, la tasca no existeix.
- `QuerySet.update()` no dispara senyals. El canvi que el plugin ha d'observar ha de passar per `save()` del model.
- Els secrets es llegeixen de l'entorn, dins del plugin. No s'afegeixen a `customers/settings.py`.
- La configuració que canvia per instal·lació va a `ConfigProject`, sembrada per una migració del plugin amb el valor buit. Buit vol dir que el plugin no fa res.
- Les migracions són de l'app del plugin i només corren on `PLUGINS` la inclou. La dependència amb el producte es declara explícitament.
<!-- coderabbit-ai-generated:v1 -->

<!-- coderabbit-ai-generated-section:v1:430b931c725c3b139b13c60128cd69b1ac8bde2ce40a359d1ba2090e63e7d298 -->

- Amb `API_URL_PREFIX=True`, un `urls.py` es publica a `/api/<nom>/`; si el producte ja usa el prefix del nom, queda a `/api/plugins/<nom>/`. Amb `API_URL_PREFIX` desactivat, les adreces són `/<nom>/` i `/plugins/<nom>/`, respectivament. Sense rutes, no es posa `urls.py`.

<!-- /coderabbit-ai-generated:v1 -->
- El nom no ha de coincidir amb un mòdul ja importat ni amb un paquet de la imatge.
- El repositori públic no anomena cap plugin concret. El nom, la URL i els secrets viuen al repositori del plugin.

## Imatge

La imatge pública no porta plugins. El plugin es publica a part, amb una imatge fina a partir d'una release que ja contingui el carregador:

<!-- coderabbit-ai-generated:v1 -->

<!-- coderabbit-ai-generated-section:v1:20d0ad0d724a38c62154c9494e967e54d7e41f08c3c74f5e9535dd1638aaf993 -->

```dockerfile
ARG CUSTOMERS_VERSION
FROM ghcr.io/aqua360/aqua360-customers-backend:${CUSTOMERS_VERSION}

COPY exemple /opt/plugins/exemple
ENV PYTHONPATH=/opt/plugins
```

<!-- /coderabbit-ai-generated:v1 -->

<!-- coderabbit-ai-generated:v1 -->

<!-- coderabbit-ai-generated-section:v1:b78476331e77a3fccd89096c0f7be7a73f36ed88d05051e1eedd2d656698a9d6 -->

Des del repositori del plugin, construïu la imatge passant explícitament l’argument de compilació `CUSTOMERS_VERSION`. Substituïu `<versió>` per una etiqueta publicada del backend que contingui el carregador; substituïu també el marcador de l’etiqueta privada:

```bash
docker build --build-arg CUSTOMERS_VERSION="<versió>" -t "ghcr.io/exemple/backend-amb-plugin:v<versió>" .
```

Quan surt una release nova del producte, es reconstrueix aquesta imatge amb la nova versió base. Al `.env` del client, substituïu `<versió>` per una versió publicada del frontend compatible amb el backend privat:

<!-- /coderabbit-ai-generated:v1 -->

<!-- coderabbit-ai-generated:v1 -->

<!-- coderabbit-ai-generated-section:v1:74fc40de8083a34d19e7024b42a05da5b4093afbfdef82a24b55ea16c46a4146 -->

```dotenv
COMPOSE_FILE=docker-compose.yml:docker-compose.image.yml
CUSTOMERS_VERSION=<versió>
BACKEND_IMAGE=ghcr.io/exemple/backend-amb-plugin:v<versió>
PLUGINS=exemple
```

<!-- /coderabbit-ai-generated:v1 -->

`docker-compose.image.yml` posa `BACKEND_IMAGE` al backend, al worker, al beat i al consumidor GMAO, i els treu el `build`. El frontend segueix la imatge pública: un plugin que només reacciona a senyals no hi afegeix pantalles, perquè el frontend ja va compilat.

<!-- coderabbit-ai-generated:v1 -->

<!-- coderabbit-ai-generated-section:v1:6b8f1e34fe3937c9524b7c9ea124395e3c377589726a53fc99c80e4a8892aade -->

El paquet de GHCR del plugin és privat. Cada servidor ha d’utilitzar un personal access token clàssic diferent, amb scope `read:packages`, data de caducitat i rotació planificada abans que caduqui. El compte associat ha de tenir accés només als paquets necessaris. Feu `docker login ghcr.io` a cada servidor amb l’usuari de sistema que executa `docker compose pull`. Els servidors que només usen la imatge pública no necessiten credencials.

<!-- /coderabbit-ai-generated:v1 -->

Una deploy key obre el `git clone` del repositori del plugin. No autoritza el `docker pull` del paquet.

<!-- coderabbit-ai-generated:v1 -->

<!-- coderabbit-ai-generated-section:v1:5fa69b8d6e4877738f15fe7f851ce5b05cd83f43bbb45a0d8c6fe96c0f26d085 -->

Els tokens no es commitegen. Deseu-los de manera segura i revoqueu els tokens antics després de la rotació.

<!-- /coderabbit-ai-generated:v1 -->
