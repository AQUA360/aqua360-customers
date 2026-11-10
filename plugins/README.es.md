# Plugins

[Català](./README.md) · [Español](./README.es.md) · [English](./README.en.md)

Aquí se dejan los plugins de cliente mientras se trabaja en local. Esta carpeta no es una app Django y su contenido, salvo estos README, no entra en el repositorio público ni en la imagen de GitHub.

El cargador, las rutas y la imagen del servidor están documentados en [backend/docs/plugins.md](../backend/docs/plugins.md). Esto de aquí es la convención de cómo tiene que ser un plugin.

Una funcionalidad que no tienen todas las instalaciones va en un plugin. Lo que viaja con el producto (Giswater, Odoo, smart metering) sigue en la app `integrations`. Una variación pequeña de una función o de una plantilla sigue `*_personalized.py`.

## Repositorio

Cada plugin es un repositorio aparte. Se clona aquí:

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

`<nom>` es un identificador de Python (`^[A-Za-z_][A-Za-z0-9_]*$`). El directorio interno se llama igual que el repositorio padre. El módulo que se importa es `<nom>`: el cargador añade `plugins/<nom>/` al `sys.path`, no el directorio del paquete.

<!-- coderabbit-ai-generated:v1 -->

<!-- coderabbit-ai-generated-section:v1:ab5cd0948834526a50b36c61057ee4a7679e1edff6d37c687438b3b469fe2040 -->

Con el Compose por defecto, añadir `PLUGINS` al `.env` no hace accesible la copia local dentro de los contenedores. Cread `docker-compose.override.yml` en la raíz del repositorio con este montaje de `./plugins` en `/plugins` en los servicios Django (el consumidor GMAO solo se ejecuta con su perfil):

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

Con la estructura anterior, poned `PLUGINS=<nom>` en el `.env` (varios nombres separados por comas). El cargador encontrará `/plugins/<nom>/<nom>/`. Este override se carga automáticamente con el Compose por defecto; si definís `COMPOSE_FILE`, incluidlo explícitamente en la lista. Como alternativa, construid la imagen privada del apartado «Imagen», que hace importable el paquete dentro del contenedor.

<!-- /coderabbit-ai-generated:v1 -->

El núcleo no importa el plugin. `AppConfig.ready()` registra las señales, y basta.

## Activación

`PLUGINS` en el `.env` es la lista separada por comas. Sin la variable no se carga ningún plugin. Si un nombre no se puede importar, el proceso no arranca.

<!-- coderabbit-ai-generated:v1 -->

<!-- coderabbit-ai-generated-section:v1:9f0688249f7f4fd93e59febedd5d92e5e8c7945d5a9fca19a422c672120807a4 -->

`PLUGINS` se lee al arrancar el proceso y no se graba en la imagen. Después de cambiarlo o quitarlo del `.env`, recread los servicios afectados con `docker compose up -d --force-recreate backend celery-worker celery-beat` (añadid `gmao-consumer` si el perfil GMAO está activo). Reiniciar los contenedores no es suficiente: los contenedores existentes conservan el entorno con el que se crearon.

<!-- /coderabbit-ai-generated:v1 -->

## Buenas prácticas

- Una señal que falla se registra y no impide el `save()` del producto.
- Una tarea Celery se encola dentro de `transaction.on_commit`. El worker, el beat y el consumidor GMAO tienen que usar la misma imagen que el backend, porque si no, la tarea no existe.
- `QuerySet.update()` no dispara señales. El cambio que el plugin tiene que observar tiene que pasar por `save()` del modelo.
- Los secretos se leen del entorno, dentro del plugin. No se añaden a `customers/settings.py`.
- La configuración que cambia por instalación va a `ConfigProject`, sembrada por una migración del plugin con el valor vacío. Vacío quiere decir que el plugin no hace nada.
- Las migraciones son de la app del plugin y solo corren donde `PLUGINS` la incluye. La dependencia con el producto se declara explícitamente.
<!-- coderabbit-ai-generated:v1 -->

<!-- coderabbit-ai-generated-section:v1:d51a4740279ecc538851b6d1da9704a80c2e0967ea809d5ff51231b1c2485d0d -->

- Con `API_URL_PREFIX=True`, un `urls.py` se publica en `/api/<nom>/`; si el producto ya usa el prefijo del nombre, queda en `/api/plugins/<nom>/`. Con `API_URL_PREFIX` desactivado, las direcciones son `/<nom>/` y `/plugins/<nom>/`, respectivamente. Sin rutas, no se pone `urls.py`.

<!-- /coderabbit-ai-generated:v1 -->
- El nombre no tiene que coincidir con un módulo ya importado ni con un paquete de la imagen.
- El repositorio público no nombra ningún plugin concreto. El nombre, la URL y los secretos viven en el repositorio del plugin.

## Imagen

La imagen pública no lleva plugins. El plugin se publica aparte, con una imagen fina a partir de una release que ya contenga el cargador:

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

<!-- coderabbit-ai-generated-section:v1:792eb173d671748ff74117dfd98884216b5c404967df66733c20cc2c8fc5779b -->

Desde el repositorio del plugin, construid la imagen pasando explícitamente el argumento de compilación `CUSTOMERS_VERSION`. Sustituid `<versió>` por una etiqueta publicada del backend que contenga el cargador; sustituid también el marcador de la etiqueta privada:

```bash
docker build --build-arg CUSTOMERS_VERSION="<versió>" -t "ghcr.io/exemple/backend-amb-plugin:v<versió>" .
```

Cuando sale una release nueva del producto, se reconstruye esta imagen con la nueva versión base. En el `.env` del cliente, sustituid `<versió>` por una versión publicada del frontend compatible con el backend privado:

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

`docker-compose.image.yml` pone `BACKEND_IMAGE` en el backend, en el worker, en el beat y en el consumidor GMAO, y les quita el `build`. El frontend sigue la imagen pública: un plugin que solo reacciona a señales no añade pantallas, porque el frontend ya va compilado.

<!-- coderabbit-ai-generated:v1 -->

<!-- coderabbit-ai-generated-section:v1:e42b59b61f0cd367e15bb4c1e9b83cdd2c41936881da91e891166c0b9a12533f -->

El paquete de GHCR del plugin es privado. Cada servidor debe utilizar un personal access token clásico distinto, con scope `read:packages`, fecha de caducidad y rotación planificada antes de que caduque. La cuenta asociada debe tener acceso solo a los paquetes necesarios. Haced `docker login ghcr.io` en cada servidor con el usuario de sistema que ejecuta `docker compose pull`. Los servidores que solo usan la imagen pública no necesitan credenciales.

<!-- /coderabbit-ai-generated:v1 -->

Una deploy key abre el `git clone` del repositorio del plugin. No autoriza el `docker pull` del paquete.

<!-- coderabbit-ai-generated:v1 -->

<!-- coderabbit-ai-generated-section:v1:d249458f0d31b3a8597429d50f52dff29fd85856ccbd1eb0367e56dcddaa26c6 -->

Los tokens no se hacen commit. Guardadlos de forma segura y revocad los tokens antiguos después de la rotación.

<!-- /coderabbit-ai-generated:v1 -->
