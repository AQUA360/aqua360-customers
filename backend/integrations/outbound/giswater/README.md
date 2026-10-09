# Integració Giswater (outbound)

Integració outbound del Programa d'Abonats (PA) amb l'API de [Giswater](https://<instancia>.bgeo360.com/giswater/v1/docs).

**Ubicació:** `integrations/outbound/giswater/`

## Índex

1. [Objectiu](#objectiu)
2. [Estructura de fitxers](#estructura-de-fitxers)
3. [Configuració](#configuració)
4. [Autenticació](#autenticació)
5. [Client HTTP i crida de connecs](#client-http-i-crida-de-connecs)
6. [Estructura de la resposta JSON](#estructura-de-la-resposta-json)
7. [Logs d'integració](#logs-dintegració)
8. [Sincronització amb Connection](#sincronització-amb-connection)
9. [Celery i Celery Beat](#celery-i-celery-beat)
10. [Management commands](#management-commands)
11. [Ús des del codi](#ús-des-del-codi)
12. [Excepcions](#excepcions)
13. [Tests](#tests)
14. [Criteris de disseny](#criteris-de-disseny)
15. [Resolució de problemes](#resolució-de-problemes)

---

## Objectiu

Centralitzar la comunicació amb Giswater per:

1. **Consultar connecs** via `GET /basic/getlist?schema=ws&tableName=ve_connec`
2. **Sincronitzar dades** cap al model `Connection` del PA (`service.models.Connection`)

Flux general:

```
Keycloak (token) → Giswater API (connecs) → mappers → Connection (PA)
```

---

## Estructura de fitxers

```
integrations/outbound/giswater/
├── README.md           # Aquest document
├── auth.py             # OAuth Keycloak o HTTP Basic Auth
├── client.py           # Client HTTP Giswater + logging automàtic
├── services.py         # fetch_connecs()
├── sync.py             # sync_connections_from_giswater()
├── mappers.py          # Parseig JSON i mapatge Giswater → Connection
├── exceptions.py       # GiswaterApiError, GiswaterAuthError
├── tasks.py            # Tasques Celery
├── tests.py            # Tests del client i auth
├── test_sync.py        # Tests de sincronització
└── fixtures/
    └── connecs_sample.json

integrations/management/commands/
├── validate_giswater_auth.py
├── fetch_giswater_connecs.py
└── sync_giswater_connections.py
```

---

## Configuració

### Variables d'entorn (`.env`)

```env
# API Giswater — IMPORTANT: ha d'incloure /v1
GISWATER_BASE_URL=https://<instancia>.bgeo360.com/giswater/v1
GISWATER_TIMEOUT=30

# OAuth via Keycloak (si GISWATER_KEYCLOAK_URL està definit)
GISWATER_KEYCLOAK_URL=https://portal.bgeo360.com/auth
GISWATER_REALM=<realm>
GISWATER_CLIENT_ID=aqua360
GISWATER_CLIENT_SECRET=

# HTTP Basic Auth (fallback si GISWATER_KEYCLOAK_URL està buit)
GISWATER_USERNAME=
GISWATER_PASSWORD=

# Token estàtic (opcional, només per proves; deixar buit en producció)
GISWATER_TOKEN=

# Sincronització programada amb Connection
GISWATER_SYNC_CONNECS_ENABLED=False
GISWATER_SYNC_CONNECS_HOUR=3
GISWATER_SYNC_CONNECS_MINUTE=0
```

### `customers/settings.py`

Les variables es carreguen amb `python-decouple`:

```python
GISWATER_BASE_URL = config("GISWATER_BASE_URL", default="")
GISWATER_TOKEN = config("GISWATER_TOKEN", default="")
GISWATER_TIMEOUT = config("GISWATER_TIMEOUT", default=30, cast=int)
GISWATER_KEYCLOAK_URL = config("GISWATER_KEYCLOAK_URL", default="")
GISWATER_REALM = config("GISWATER_REALM", default="")
GISWATER_CLIENT_ID = config("GISWATER_CLIENT_ID", default="")
GISWATER_CLIENT_SECRET = config("GISWATER_CLIENT_SECRET", default="")
GISWATER_USERNAME = config("GISWATER_USERNAME", default="")
GISWATER_PASSWORD = config("GISWATER_PASSWORD", default="")
GISWATER_SYNC_CONNECS_ENABLED = config("GISWATER_SYNC_CONNECS_ENABLED", default=False, cast=bool)
GISWATER_SYNC_CONNECS_HOUR = config("GISWATER_SYNC_CONNECS_HOUR", default=3, cast=int)
GISWATER_SYNC_CONNECS_MINUTE = config("GISWATER_SYNC_CONNECS_MINUTE", default=0, cast=int)
```

L'app `integrations` ha d'estar registrada a `OWN_APPS` a `customers/settings.py`.

---

## Autenticació

Hi ha dos modes, resolts automàticament:

| Condició | Mode |
|----------|------|
| `GISWATER_KEYCLOAK_URL` definit | OAuth Bearer via Keycloak (`client_credentials`) |
| `GISWATER_KEYCLOAK_URL` buit | HTTP Basic Auth (`GISWATER_USERNAME` / `GISWATER_PASSWORD`) |

### Ordre de resolució

El `GiswaterClient` obté l'autenticació en aquest ordre:

1. Token passat explícitament al constructor (`GiswaterClient(token="...")`) → Bearer
2. `GISWATER_TOKEN` del `.env` (opcional) → Bearer
3. Si `GISWATER_KEYCLOAK_URL` → token OAuth dinàmic via `get_access_token()`
4. Altrament → HTTP Basic Auth amb `GISWATER_USERNAME` / `GISWATER_PASSWORD`

### OAuth (Keycloak)

Giswater requereix autenticació **Bearer** via Keycloak amb el flux `client_credentials`.

El token **no es persisteix** a la base de dades ni al `.env` (excepte si s'usa `GISWATER_TOKEN` manualment). A cada crida, el `GiswaterClient` obté un token fresc de Keycloak via `get_access_token()`. El token caduca als ~300 segons (`expires_in`), però com que es demana a cada petició no cal cachejar-lo de moment.

#### Flux manual (curl)

```bash
KEYCLOAK_URL=https://portal.bgeo360.com/auth
REALM=exploitation_name

TOKEN=$(curl -s -X POST "$KEYCLOAK_URL/realms/$REALM/protocol/openid-connect/token" \
  -d "grant_type=client_credentials" \
  -d "client_id=aqua360" \
  -d "client_secret=EL_TEU_SECRET" | jq -r .access_token)

echo "$TOKEN"
```

### HTTP Basic Auth

Quan no hi ha Keycloak, l'API accepta `Authorization: Basic` (usuari + contrasenya), com al Swagger (`HTTPBasic`).

```bash
curl -u "$GISWATER_USERNAME:$GISWATER_PASSWORD" \
  "$GISWATER_BASE_URL/basic/getlist?schema=ws&tableName=ve_connec"
```

### Validar l'autenticació

```bash
python manage.py validate_giswater_auth
```

Amb Keycloak mostra la longitud del token i una versió enmascarada. Amb Basic Auth confirma que usuari/contrasenya estan configurats.

---

## Client HTTP i crida de connecs

### Endpoint

```
GET {GISWATER_BASE_URL}/basic/getlist?schema=ws&tableName=ve_connec
```

Exemple real:

```
GET https://EXPLOITATIONNAME.bgeo360.com/giswater/v1/basic/getlist?schema=ws&tableName=ve_connec
Authorization: Bearer <token>
```   

Documentació Swagger: [https://EXPLOITATIONNAME.bgeo360.com/giswater/v1/docs](https://EXPLOITATIONNAME.bgeo360.com/giswater/v1/docs)

### Provar la crida i guardar JSON

```bash
python manage.py fetch_giswater_connecs
```

Amb fitxer de sortida:

```bash
python manage.py fetch_giswater_connecs --save-json /tmp/giswater_connecs.json
```

Opcions:

| Flag | Descripció |
|------|------------|
| `--save-json RUTA` | Guarda la resposta JSON completa en un fitxer |
| `--preview-chars N` | Caràcters de previsualització per consola (default: 500) |

---

## Estructura de la resposta JSON

La llista de connecs **no** està dins de `body.form`. L'estructura rellevant és:

```json
{
  "status": "Accepted",
  "message": { "level": 3, "text": "Process done successfully" },
  "body": {
    "form": {
      "headers": [ ... ]
    },
    "data": {
      "fields": [
        {
          "connec_id": 12547,
          "connec_type": "ESCO",
          "customer_code": "3410103",
          "lat": 41.48061398054251,
          "long": 2.32357789570044,
          ...
        }
      ]
    }
  }
}
```

**Ruta d'accés als registres:** `body.data.fields[]`

`body.form` només conté metadades de capçaleres de taula (columnes), no les dades.

---

## Logs d'integració

Cada crida HTTP a Giswater es registra automàticament al model `IntegrationRequestLog`.

### Camps registrats

| Camp | Valor |
|------|-------|
| `provider` | `giswater` |
| `direction` | `outbound` |
| `method` | `GET` |
| `endpoint` | `/basic/getlist` |
| `request_payload` | `{"schema": "ws", "tableName": "ve_connec"}` |
| `response_payload` | JSON complet de la resposta (si èxit) |
| `status_code` | Codi HTTP |
| `success` | `True` / `False` |
| `error_message` | Missatge d'error (si falla) |

### On consultar-los

**Admin Django:**

```
/admin/integrations/integrationrequestlog/
```

**Shell Django:**

```python
from integrations.models import IntegrationRequestLog

log = IntegrationRequestLog.objects.latest("created_at")
log.response_payload   # resposta JSON
log.error_message      # si ha fallat
log.success            # True/False
```

**Base de dades:** taula `integrations_integrationrequestlog`

---

## Sincronització amb Connection

Actualitza el model `Connection` (`service/models.py`) amb dades de Giswater.

### Filtre

Només es processen registres amb:

```
connec_type == "ESCO"
```

### Mapatge de camps

| Giswater (`body.data.fields[]`) | `Connection` (PA) | Notes |
|----------------------------------|-------------------|-------|
| `customer_code` | `token` | Clau de cerca (no s'escriu) |
| `connec_id` | `code_gis` | Convertit a string |
| `lat` | `latitude` | `DecimalField(9,6)` |
| `long` | `longitude` | `DecimalField(9,6)` |

### Lògica de sincronització

1. Crida `fetch_connecs()` → obté tots els connecs de Giswater
2. Extreu `body.data.fields[]`
3. Filtra `connec_type == "ESCO"` i descarta registres sense `customer_code`
4. Busca `Connection` amb `token == customer_code` i `is_active=True`
5. Actualitza `code_gis`, `latitude`, `longitude` (només si han canviat)
6. Retorna estadístiques

### Estadístiques retornades

| Camp | Descripció |
|------|------------|
| `total_fields` | Total de registres rebuts de Giswater |
| `esco_tokens` | `customer_code` únics ESCO vàlids |
| `skipped` | Registres ESCO sense `customer_code` o `connec_id` |
| `updated` | Connexions actualitzades |
| `unchanged` | Connexions trobades però sense canvis |
| `not_found` | `customer_code` de Giswater sense `Connection` al PA |
| `not_found_tokens` | Llista detallada dels `not_found` (customer_code, code_gis, lat, long) |

### Casos especials

- Si hi ha **diverses `Connection`** amb el mateix `token`, s'actualitzen totes.
- Si un `customer_code` apareix **múltiples vegades** a Giswater, prevaleix l'últim registre processat.
- Registres sense `customer_code` o sense `connec_id` es compten com a `skipped`.

### Execució manual

```bash
python manage.py sync_giswater_connections
```

Si hi ha `not_found`, el command mostra automàticament el detall:

```
not_found (1): customer_code de Giswater sense Connection activa amb token coincident
  customer_code=3373640  code_gis=12546  lat=41.478743  long=2.298797
```

Només veure els not_found (sortida text):

```bash
python manage.py sync_giswater_connections --only-not-found
```

Exportar not_found a CSV:

```bash
python manage.py sync_giswater_connections --only-not-found --csv /tmp/giswater_not_found.csv
```

CSV a stdout (per redireccionar o pipe):

```bash
python manage.py sync_giswater_connections --only-not-found --csv -
```

També es pot exportar CSV després d'una sync completa:

```bash
python manage.py sync_giswater_connections --csv /tmp/giswater_not_found.csv
```

Columnes del CSV (separador `;`): `customer_code`, `code_gis`, `latitude`, `longitude`.

Consultar des del codi:

```python
stats = sync_connections_from_giswater()
stats["not_found_tokens"]
# [{"customer_code": "3373640", "code_gis": "12546", "latitude": ..., "longitude": ...}, ...]
```

Exemple de sortida:

```
Sincronització completada
  total_fields: 3
  esco_tokens: 2
  skipped: 1
  updated: 1
  not_found: 1
  unchanged: 0
```

---

## Celery i Celery Beat

### Tasques disponibles

| Tasca | Mòdul | Descripció |
|-------|-------|------------|
| `fetch_giswater_connecs_task` | `integrations.tasks` | Obté connecs de Giswater (sense sync) |
| `sync_giswater_connections_task` | `integrations.tasks` | Sync completa Giswater → Connection |

### Execució manual via Celery

```python
from integrations.tasks import fetch_giswater_connecs_task, sync_giswater_connections_task

fetch_giswater_connecs_task.delay()
sync_giswater_connections_task.delay()
```

### Programació amb Celery Beat

Activar al `.env`:

```env
GISWATER_SYNC_CONNECS_ENABLED=True
GISWATER_SYNC_CONNECS_HOUR=3
GISWATER_SYNC_CONNECS_MINUTE=0
```

Configuració a `customers/celery.py`:

- La tasca `sync-giswater-connections` **només s'afegeix al beat schedule** si `GISWATER_SYNC_CONNECS_ENABLED=True`
- Per defecte s'executa **cada dia a les 3:00**
- Si `GISWATER_SYNC_CONNECS_ENABLED=False`, la tasca retorna `{"status": "skipped", ...}`

**Important:** reiniciar celery worker i celery beat després de canviar el `.env`.

```bash
# Exemple
celery -A customers worker -l info
celery -A customers beat -l info
```

---

## Management commands

| Command | Descripció |
|---------|------------|
| `python manage.py validate_giswater_auth` | Valida Keycloak o Basic Auth segons configuració |
| `python manage.py fetch_giswater_connecs` | Crida API i mostra previsualització; guarda log |
| `python manage.py fetch_giswater_connecs --save-json RUTA` | Igual + fitxer JSON |
| `python manage.py sync_giswater_connections` | Sync Giswater → Connection |
| `python manage.py sync_giswater_connections --only-not-found` | Només llista not_found |
| `python manage.py sync_giswater_connections --csv RUTA` | Exporta not_found a CSV (`-` = stdout) |

---

## Ús des del codi

### Autenticació

```python
from integrations.outbound.giswater.auth import get_access_token, get_http_auth, uses_keycloak

if uses_keycloak():
    token = get_access_token()
else:
    headers, auth = get_http_auth()  # Basic Auth
```

### Obtenir connecs

```python
from integrations.outbound.giswater.services import fetch_connecs

connecs = fetch_connecs()
```

### Crida genèrica

```python
from integrations.outbound.giswater.client import GiswaterClient

client = GiswaterClient()
data = client.get_list(schema="ws", table_name="ve_connec")
```

### Sincronitzar connexions

```python
from integrations.outbound.giswater.sync import sync_connections_from_giswater

stats = sync_connections_from_giswater()
# {"total_fields": 3, "esco_tokens": 2, "updated": 1, ...}
```

### Parsejar JSON manualment

```python
from integrations.outbound.giswater.mappers import (
    extract_connec_fields,
    build_connection_updates_by_token,
)

fields = extract_connec_fields(response)
updates, skipped = build_connection_updates_by_token(fields)
```

---

## Excepcions

| Excepció | Origen | Quan es produeix |
|----------|--------|------------------|
| `GiswaterAuthError` | `auth.py` | Error Keycloak/Basic, credencials faltants, resposta sense `access_token` |
| `GiswaterApiError` | `client.py` | Error HTTP Giswater, connexió fallida, JSON invàlid |

---

## Tests

```bash
python manage.py test integrations.outbound.giswater.tests integrations.outbound.giswater.test_sync
```

Fixtures de prova: `integrations/outbound/giswater/fixtures/connecs_sample.json`

---

## Criteris de disseny

| Fitxer | Responsabilitat |
|--------|-----------------|
| `auth.py` | Autenticació OAuth Keycloak o HTTP Basic Auth |
| `client.py` | Només comunicació HTTP amb Giswater + logging |
| `services.py` | API semàntica d'alt nivell (`fetch_connecs`) |
| `mappers.py` | Transformació de dades Giswater → format PA |
| `sync.py` | Orquestració de la sincronització amb `Connection` |
| `tasks.py` | Tasques Celery (background) |

**Regles:**

- No cridar `requests` directament des de la resta del projecte.
- No barrejar lògica de negoci del PA dins del client.
- Els logs HTTP queden centralitzats a `IntegrationRequestLog`.

---

## Resolució de problemes

### Error 404 `{"detail":"Not found"}`

La `GISWATER_BASE_URL` no inclou `/v1`. Corregir:

```env
# Incorrecte
GISWATER_BASE_URL=https://<instancia>.bgeo360.com/giswater

# Correcte
GISWATER_BASE_URL=https://<instancia>.bgeo360.com/giswater/v1
```

### `not_found` alt a la sincronització

El `customer_code` de Giswater no coincideix amb cap `Connection.token` activa al PA. Verificar que les connexions tenen el `token` correcte.

### `skipped` > 0

Registres ESCO sense `customer_code` o sense `connec_id` a Giswater.

### Sync no s'executa amb Celery Beat

1. Verificar `GISWATER_SYNC_CONNECS_ENABLED=True` al `.env`
2. Reiniciar celery beat
3. Comprovar que el worker està actiu

### Token OAuth

```bash
python manage.py validate_giswater_auth
```

---

## Documentació general

Per al context de l'app `integrations` (inbound/outbound, models, convencions), veure `docs/integrations.md`.
