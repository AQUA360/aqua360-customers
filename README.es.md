# Aqua360 Customers

Aplicación web de facturación y gestión de abonados de agua. Este repositorio contiene todo el código necesario para instalarla y ejecutarla (API, tareas en segundo plano, interfaz de usuario y servicios de soporte).

## Requisitos

- [Docker](https://docs.docker.com/get-docker/) y Docker Compose (incluido en Docker Desktop).

## Guía rápida: arrancar con Docker

### 1. Directorio del proyecto

```bash
cd /path/al/projecte/aqua360-customers
```

### 2. Variables de entorno (`.env`)

El `docker-compose.yml` carga el archivo `.env` (`env_file`) en los servicios `backend`, `celery-worker`, `celery-beat`, `gmao-consumer` y `frontend`, así que **debe existir** en la raíz del proyecto:

```bash
cp env.docker.example .env
```

Edita `.env` si es necesario. Por ejemplo, si el puerto **5432** ya lo utiliza un PostgreSQL del sistema, define `POSTGRES_PORT=5433` (solo el puerto en la máquina host).

Cualquier variable del `.env` (p. ej. `EMAIL_*`, `MSGRAPH_*`, `DOMAIN_MEDIA`, `CSRF_TRUSTED_ORIGINS`) llega a los contenedores. Las variables de conexión a la BD y a Redis (`DATABASE_*`, `CELERY_BROKER_URL`) las fija el propio compose, y el resto tienen valor por defecto en `docker-compose.yml`. `ENV` y `LANGUAGE` se aplican al build y a la ejecución del frontend.

### 3. Construir y arrancar todos los servicios

Primera vez o después de cambios en los Dockerfiles o dependencias:

```bash
docker compose up --build
```

La primera construcción puede tardar bastante (imágenes base, `pip`, `npm run build`).

Para ejecutar en segundo plano:

```bash
docker compose up --build -d
docker compose logs -f
```

### 3.b Si solo ha cambiado el `.env`

No hace falta reconstruir imágenes si no has tocado Dockerfiles ni dependencias.

```bash
docker compose up -d --force-recreate
```

Esto recrea los contenedores para que tomen los nuevos valores de las variables de entorno.

Si has cambiado `NUXT_PUBLIC_API_HOST` (variable usada en el build del frontend), entonces sí hace falta rebuild:

```bash
docker compose up -d --build frontend
```

### 4. Estado de los contenedores

```bash
docker compose ps
```

Todos los servicios deberían estar en ejecución (y `healthy` donde corresponda). Todos tienen `restart: unless-stopped`, excepto `gmao-consumer` (`on-failure`: sale sin error si RabbitMQ está desactivado).

| Servicio | Función |
|---|---|
| `db` | PostgreSQL 16 |
| `redis` | Broker de Celery |
| `backend` | API Django |
| `celery-worker` | Tareas en segundo plano |
| `celery-beat` | Tareas programadas |
| `gmao-consumer` | Consumidor GMAO (`manage.py run_gmao_consumer`) |
| `frontend` | Interfaz Nuxt |

### 5. Administración y datos de prueba

Con los servicios en marcha, en otro terminal (desde la raíz del proyecto no hace falta hacer `cd` al backend si usas `exec` como se muestra abajo).

**Entorno de demostración con Prometeo** - el script `backend/prometeo/reset_db.sh` regenera un mundo de prueba (explotaciones, contratos, lecturas, etc.):

```bash
docker compose exec backend bash prometeo/reset_db.sh
```

Esto ejecuta `flush` sobre la base de datos: **borra todos los datos** y vuelve a cargar el conjunto generado por Prometeo. También crea un superusuario y un token mediante el comando de gestión `create_superuser_and_token` (consulta el propio script si quieres cambiar credenciales).

**Solo un superusuario** (sin vaciar ni regenerar el mundo):

```bash
docker compose exec backend python manage.py createsuperuser
```

Para ejecutar el mismo script sin Docker, hay que estar dentro de `backend/` con el entorno Python activo; consulta los comentarios al principio de `prometeo/reset_db.sh`.

### 6. URLs

| Qué abres | URL |
|-----------|-----|
| Interfaz de usuario | http://localhost:3000 |
| Panel de administración | http://localhost:8000/admin/ |

La interfaz web usa la URL de la API definida por `NUXT_PUBLIC_API_HOST` (por defecto `http://localhost:8000`). Si la cambias, hay que **reconstruir** la imagen correspondiente del compose.

### 7. Parar

```bash
docker compose down
```

Los datos de PostgreSQL se guardan en el volumen Docker y se conservan entre arranques. Para eliminar también los volúmenes:

```bash
docker compose down -v
```

## Despliegue a producción (resumen)

### Flujo recomendado

```bash
git pull
docker compose build frontend backend celery-worker celery-beat gmao-consumer
docker compose up -d backend
docker compose exec backend python manage.py migrate --noinput
docker compose up -d celery-worker celery-beat gmao-consumer
docker compose up -d frontend
```

### Despliegue automatizado (Ansible)

Los servidores se despliegan con el playbook `playbooks/AquaCustomersDocker` del repositorio `aqua360-customers-deploy` (`99-all.yaml` los ejecuta todos en orden, con el inventario del cliente):

| Playbook | Qué hace |
|---|---|
| `00-users-workdir` | Usuarios y directorio de trabajo `/var/www/<exploitation>` |
| `01-compose-env` | Copia `docker-compose.yml`, genera el `.env` desde el inventario y crea `backups/`, `docker-data/`, `backend/` y `frontend/` |
| `02-git-clone` | Clona el código y ejecuta `docker compose up --build -d` |
| `03-nginx-docker-cloudflare` | Certificados Cloudflare Origin y sitios Nginx hacia los puertos Docker |
| `04-backup-db` | `backup_db.sh` (`pg_dump` dentro del contenedor `db`) y cron de backups |
| `05-copy-backup-to-test` | Copia diaria del último backup al servidor de test |
| `06-restore` | `restore.sh` y limpieza de BD antiguas (retención de 3 días) |
| `07-readonly-db-user` | Usuario PostgreSQL de solo lectura |

En los servidores, los puertos del host no son los por defecto (`POSTGRES_PORT=5433`, `REDIS_PORT=6380`, `BACKEND_PORT=8001`, `FRONTEND_PORT=3001`) y se pueden cambiar por cliente en el inventario (`docker_*_port`) para que varias explotaciones compartan servidor. El `docker-compose.yml` de este repositorio es el mismo que despliega el playbook.

### Corte de servicio: qué esperar

- `docker compose build ...` **no** corta el servicio: solo construye imágenes.
- `docker compose up -d ...` puede provocar un **microcorte** al recrear contenedores (en un solo host y una sola réplica por servicio).
- Durante el `up`, el servicio antiguo puede seguir unos instantes, pero en el momento del reemplazo puede haber unos segundos de no disponibilidad.
- Si hace falta casi cero downtime, se debe hacer blue/green o rolling updates con reverse proxy/orquestador.

## Documentación adicional

- Servidor y entorno de desarrollo sin Docker: `backend/README.md`
- Interfaz (Nuxt): `frontend/README.md`
