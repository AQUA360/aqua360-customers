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

El nucli no importa el plugin. `AppConfig.ready()` registra els senyals, i prou.

## Activació

`PLUGINS` al `.env` és la llista separada per comes. Sense la variable no es carrega cap plugin. Si un nom no es pot importar, el procés no arrenca.

`PLUGINS` es llegeix en engegar el contenidor. No es grava a la imatge: treure'l del `.env` ha de deixar el procés sense aquell plugin.

## Bones pràctiques

- Un senyal que falla es registra i no impedeix el `save()` del producte.
- Una tasca Celery s'encua dins de `transaction.on_commit`. El worker, el beat i el consumidor GMAO han d'usar la mateixa imatge que el backend, perquè si no, la tasca no existeix.
- `QuerySet.update()` no dispara senyals. El canvi que el plugin ha d'observar ha de passar per `save()` del model.
- Els secrets es llegeixen de l'entorn, dins del plugin. No s'afegeixen a `customers/settings.py`.
- La configuració que canvia per instal·lació va a `ConfigProject`, sembrada per una migració del plugin amb el valor buit. Buit vol dir que el plugin no fa res.
- Les migracions són de l'app del plugin i només corren on `PLUGINS` la inclou. La dependència amb el producte es declara explícitament.
- Un `urls.py` es publica a `/<nom>/`. Si el producte ja usa aquest prefix, queda a `/plugins/<nom>/`. Sense rutes, no es posa `urls.py`.
- El nom no ha de coincidir amb un mòdul ja importat ni amb un paquet de la imatge.
- El repositori públic no anomena cap plugin concret. El nom, la URL i els secrets viuen al repositori del plugin.

## Imatge

La imatge pública no porta plugins. El plugin es publica a part, amb una imatge fina a partir d'una release que ja contingui el carregador:

```dockerfile
ARG CUSTOMERS_VERSION=local
FROM ghcr.io/aqua360/aqua360-customers-backend:${CUSTOMERS_VERSION}

COPY exemple /opt/plugins/exemple
ENV PYTHONPATH=/opt/plugins
```

Quan surt una release nova del producte, es reconstrueix aquesta imatge amb el `FROM` d'aquella etiqueta. Al `.env` del client:

```dotenv
COMPOSE_FILE=docker-compose.yml:docker-compose.image.yml
BACKEND_IMAGE=ghcr.io/exemple/backend-amb-plugin:v<versió>
PLUGINS=exemple
```

`docker-compose.image.yml` posa `BACKEND_IMAGE` al backend, al worker, al beat i al consumidor GMAO, i els treu el `build`. El frontend segueix la imatge pública: un plugin que només reacciona a senyals no hi afegeix pantalles, perquè el frontend ja va compilat.

El paquet de GHCR del plugin és privat. Per baixar-lo n'hi ha prou amb un sol personal access token clàssic, scope `read:packages` i sense caducitat. El mateix `docker login` es repeteix a cada servidor que hagi de baixar aquesta imatge, amb l'usuari de sistema que executa `docker compose pull`. No es crea un usuari de GitHub per màquina. Els servidors que només usen la imatge pública no necessiten credencial.

Una deploy key obre el `git clone` del repositori del plugin. No autoritza el `docker pull` del paquet.

El token no es committa. GitHub esborra els tokens que passen un any sense cap ús; un `docker pull` des de qualsevol servidor el manté viu.
