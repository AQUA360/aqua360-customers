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

El núcleo no importa el plugin. `AppConfig.ready()` registra las señales, y basta.

## Activación

`PLUGINS` en el `.env` es la lista separada por comas. Sin la variable no se carga ningún plugin. Si un nombre no se puede importar, el proceso no arranca.

`PLUGINS` se lee al arrancar el contenedor. No se graba en la imagen: quitarlo del `.env` tiene que dejar el proceso sin ese plugin.

## Buenas prácticas

- Una señal que falla se registra y no impide el `save()` del producto.
- Una tarea Celery se encola dentro de `transaction.on_commit`. El worker, el beat y el consumidor GMAO tienen que usar la misma imagen que el backend, porque si no, la tarea no existe.
- `QuerySet.update()` no dispara señales. El cambio que el plugin tiene que observar tiene que pasar por `save()` del modelo.
- Los secretos se leen del entorno, dentro del plugin. No se añaden a `customers/settings.py`.
- La configuración que cambia por instalación va a `ConfigProject`, sembrada por una migración del plugin con el valor vacío. Vacío quiere decir que el plugin no hace nada.
- Las migraciones son de la app del plugin y solo corren donde `PLUGINS` la incluye. La dependencia con el producto se declara explícitamente.
- Un `urls.py` se publica en `/<nom>/`. Si el producto ya usa ese prefijo, queda en `/plugins/<nom>/`. Sin rutas, no se pone `urls.py`.
- El nombre no tiene que coincidir con un módulo ya importado ni con un paquete de la imagen.
- El repositorio público no nombra ningún plugin concreto. El nombre, la URL y los secretos viven en el repositorio del plugin.

## Imagen

La imagen pública no lleva plugins. El plugin se publica aparte, con una imagen fina a partir de una release que ya contenga el cargador:

```dockerfile
ARG CUSTOMERS_VERSION=local
FROM ghcr.io/aqua360/aqua360-customers-backend:${CUSTOMERS_VERSION}

COPY exemple /opt/plugins/exemple
ENV PYTHONPATH=/opt/plugins
```

Cuando sale una release nueva del producto, se reconstruye esta imagen con el `FROM` de esa etiqueta. En el `.env` del cliente:

```dotenv
COMPOSE_FILE=docker-compose.yml:docker-compose.image.yml
BACKEND_IMAGE=ghcr.io/exemple/backend-amb-plugin:v<versió>
PLUGINS=exemple
```

`docker-compose.image.yml` pone `BACKEND_IMAGE` en el backend, en el worker, en el beat y en el consumidor GMAO, y les quita el `build`. El frontend sigue la imagen pública: un plugin que solo reacciona a señales no añade pantallas, porque el frontend ya va compilado.

El paquete de GHCR del plugin es privado. Para bajarlo basta con un solo personal access token clásico, scope `read:packages` y sin caducidad. El mismo `docker login` se repite en cada servidor que tenga que bajar esta imagen, con el usuario de sistema que ejecuta `docker compose pull`. No se crea un usuario de GitHub por máquina. Los servidores que solo usan la imagen pública no necesitan credencial.

Una deploy key abre el `git clone` del repositorio del plugin. No autoriza el `docker pull` del paquete.

El token no se hace commit. GitHub borra los tokens que pasan un año sin ningún uso; un `docker pull` desde cualquier servidor lo mantiene vivo.
