# Aqua360 Customers

Aplicació web de facturació i gestió d’abonats d’aigua. Aquest repositori conté tot el codi necessari per instal·lar-la i executar-la (API, tasques en segon pla, interfície d’usuari i serveis de suport).

## Requisits

- [Docker](https://docs.docker.com/get-docker/) i Docker Compose (inclòs a Docker Desktop).

## Guia ràpida: arrencar amb Docker

### 1. Directori del projecte

```bash
cd /path/al/projecte/aqua360-customers
```

### 2. Variables d’entorn (`.env`)

El `docker-compose.yml` carrega el fitxer `.env` (`env_file`) als serveis `backend`, `celery-worker`, `celery-beat`, `gmao-consumer` i `frontend`, així que **ha d’existir** a l’arrel del projecte:

```bash
cp env.docker.example .env
```

Edita `.env` si cal. Per exemple, si el port **5432** ja el fa servir un PostgreSQL del sistema, defineix `POSTGRES_PORT=5433` (només el port a la màquina host).

Qualsevol variable del `.env` (p. ex. `EMAIL_*`, `MSGRAPH_*`, `DOMAIN_MEDIA`, `CSRF_TRUSTED_ORIGINS`) arriba als contenidors. Les variables de connexió a la BD i a Redis (`DATABASE_*`, `CELERY_BROKER_URL`) les fixa el propi compose, i la resta tenen valor per defecte a `docker-compose.yml`. `ENV` i `LANGUAGE` s’apliquen al build i a l’execució del frontend.

### 3. Construir i arrencar tots els serveis

Primera vegada o després de canvis als Dockerfiles o dependències:

```bash
docker compose up --build
```

La primera construcció pot trigar força (imatges base, `pip`, `npm run build`).

Per executar en segon pla:

```bash
docker compose up --build -d
docker compose logs -f
```

### 3.b Si només ha canviat el `.env`

No cal reconstruir imatges si no has tocat Dockerfiles ni dependències.

```bash
docker compose up -d --force-recreate
```

Això recrea els contenidors perquè agafin els nous valors de variables d’entorn.

Si has canviat `NUXT_PUBLIC_API_HOST` (variable usada al build del frontend), llavors si que cal rebuild:

```bash
docker compose up -d --build frontend
```

### 4. Estat dels contenidors

```bash
docker compose ps
```

Tots els serveis haurien d’estar en execució (i `healthy` on correspongui). Tots tenen `restart: unless-stopped`, excepte `gmao-consumer` (`on-failure`: surt sense error si RabbitMQ està desactivat).

| Servei | Funció |
|---|---|
| `db` | PostgreSQL 16 |
| `redis` | Broker de Celery |
| `backend` | API Django |
| `celery-worker` | Tasques en segon pla |
| `celery-beat` | Tasques programades |
| `gmao-consumer` | Consumidor GMAO (`manage.py run_gmao_consumer`) |
| `frontend` | Interfície Nuxt |

### 5. Administració i dades de prova

Amb els serveis en marxa, en un altre terminal (des de l’arrel del projecte no cal fer `cd` al backend si uses `exec` com a sota).

**Entorn de demostració amb Prometeo** — el script `backend/prometeo/reset_db.sh` regenera un món de prova (explotacions, contractes, lectures, etc.):

```bash
docker compose exec backend bash prometeo/reset_db.sh
```

Això executa `flush` sobre la base de dades: **esborra totes les dades** i torna a carregar el conjunt generat per Prometeo. També crea un superusuari i token mitjançant la comanda de gestió `create_superuser_and_token` (vegeu el propi script si voleu canviar credencials).

**Només un superusuari** (sense buidar ni regenerar el món):

```bash
docker compose exec backend python manage.py createsuperuser
```

Per executar el mateix script sense Docker, cal estar dins de `backend/` amb l’entorn Python actiu; vegeu els comentaris al capdamunt de `prometeo/reset_db.sh`.

### 6. URLs

| Què obres              | URL                          |
|------------------------|------------------------------|
| Interfície d’usuari    | http://localhost:3000        |
| Panell d’administració | http://localhost:8000/admin/ |

La interfície web usa l’URL de l’API definida per `NUXT_PUBLIC_API_HOST` (per defecte `http://localhost:8000`). Si la canvies, cal **reconstruir** la imatge corresponent del compose.

### 7. Aturar

```bash
docker compose down
```

Les dades de PostgreSQL es guarden al volum Docker i es conserven entre arrencades. Per eliminar també els volums:

```bash
docker compose down -v
```

## Desplegament a producció (resum)

### Flux recomanat

```bash
git pull
docker compose build frontend backend celery-worker celery-beat gmao-consumer
docker compose up -d backend
docker compose exec backend python manage.py migrate --noinput
docker compose up -d celery-worker celery-beat gmao-consumer
docker compose up -d frontend
```

### Desplegament automatitzat (Ansible)

Els servidors es desplieguen amb el playbook `playbooks/AquaCustomersDocker` del repositori `aqua360-customers-deploy` (`99-all.yaml` els executa tots en ordre, amb l’inventari del client):

| Playbook | Què fa |
|---|---|
| `00-users-workdir` | Usuaris i directori de treball `/var/www/<exploitation>` |
| `01-compose-env` | Copia `docker-compose.yml`, genera el `.env` des de l’inventari i crea `backups/`, `docker-data/`, `backend/` i `frontend/` |
| `02-git-clone` | Clona el codi i executa `docker compose up --build -d` |
| `03-nginx-docker-cloudflare` | Certificats Cloudflare Origin i llocs Nginx cap als ports Docker |
| `04-backup-db` | `backup_db.sh` (`pg_dump` dins el contenidor `db`) i cron de backups |
| `05-copy-backup-to-test` | Còpia diària del darrer backup al servidor de test |
| `06-restore` | `restore.sh` i neteja de BD antigues (retenció de 3 dies) |
| `07-readonly-db-user` | Usuari PostgreSQL de només lectura |

Als servidors, els ports del host no són els per defecte (`POSTGRES_PORT=5433`, `REDIS_PORT=6380`, `BACKEND_PORT=8001`, `FRONTEND_PORT=3001`) i es poden canviar per client a l’inventari (`docker_*_port`) perquè diverses explotacions comparteixin servidor. El `docker-compose.yml` d’aquest repositori és el mateix que desplega el playbook.

### Tall de servei: què esperar

- `docker compose build ...` **no** talla servei: només construeix imatges.
- `docker compose up -d ...` pot provocar **microtall** en recrear contenidors (en un sol host i una sola rèplica per servei).
- Durant el `up`, el servei vell pot seguir uns instants, però en el moment del reemplaç hi pot haver uns segons de no disponibilitat.
- Si cal gairebé zero downtime, s’ha de fer blue/green o rolling updates amb reverse proxy/orquestrador.

## Documentació addicional

- Servidor i entorn de desenvolupament sense Docker: `backend/README.md`
- Interfície (Nuxt): `frontend/README.md`
