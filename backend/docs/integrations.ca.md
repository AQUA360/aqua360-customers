# Integracions

L'app Django `integrations` centralitza les connexions del Programa d'Abonats (PA) amb sistemes externs. Està registrada a `INSTALLED_APPS` com `"integrations"`.

- **Outbound**: el PA crida APIs externes (`integrations/outbound/<proveïdor>/`).
- **Inbound**: sistemes externs criden endpoints del PA (`integrations/inbound/<proveïdor>/`).

`outbound` i `inbound` són paquets Python interns dins la mateixa app; no són apps Django separades.

## Integracions

La documentació detallada per integració viu a [`docs/integrations/`](integrations/README.md) i als README del codi:

| Integració | Direcció | Codi | Documentació |
|------------|----------|------|--------------|
| Giswater | Outbound + Inbound | `integrations/outbound/giswater/`, `integrations/inbound/giswater/` | [`integrations/outbound/giswater/README.md`](../integrations/outbound/giswater/README.md) |
| Aqua360 Sign | Outbound + Inbound | `integrations/outbound/signing/`, `integrations/inbound/signing/` | [`docs/integrations/signing/`](integrations/signing/data-contract.md) |
| Odoo (ERP Comptabilitat) | Outbound | `integrations/outbound/odoo/` | [`docs/integrations/odoo/`](integrations/odoo/data-contract.md) · [`integrations/outbound/odoo/README.md`](../integrations/outbound/odoo/README.md) |
| Smartmetering | Inbound | `integrations/inbound/smartmetering/` | [`docs/integrations/smartmetering/`](integrations/smartmetering/data-contract.md) · aquest document (secció Smartmetering) |

---

## Estructura de l'app

```
integrations/
├── __init__.py
├── apps.py
├── admin.py
├── models.py
├── urls.py
├── tasks.py
├── management/commands/
├── outbound/
│   ├── giswater/       # client, auth, services, sync, mappers, tasks, tests
│   ├── signing/        # client, services, polling, tests
│   └── odoo/           # client, services, mappers, tests, fixtures
└── inbound/
    ├── giswater/       # views, urls, services, mappers, openapi.yaml, tests
    ├── smartmetering/  # views, urls, services, mappers, serializers, openapi.yaml, tests
    └── signing/        # views, services, tests
```

### Responsabilitats per capa

Cada integració segueix la mateixa separació de rols:

| Fitxer | Rol |
|--------|-----|
| `client.py` | Comunicació HTTP amb el sistema extern (cap lògica de negoci del PA) |
| `services.py` | Orquestració i API interna per al resta del projecte |
| `mappers.py` | Transformació entre formats externs i models interns |
| `tasks.py` | Tasques Celery (quan n'hi ha) |
| `exceptions.py` | Errors específics del proveïdor |

Des de la resta del PA s'importen serveis (`services.py`), no clients HTTP directament.

---

## Models

### `IntegrationRequestLog`

Registre centralitzat de crides HTTP d'integració (inbound i outbound). Consultable a l'admin: `/admin/integrations/integrationrequestlog/`.

Camps principals: `provider`, `direction`, `method`, `endpoint`, `request_payload`, `response_payload`, `status_code`, `success`, `error_message`, `object_type`, `object_id`, `created_at`.

Els clients outbound (Giswater, Sign, Odoo) persisteixen un log a cada crida.

### `ContractSigningSession`

Sessió de signatura vinculada a `contract.ContractRequest`. Emmagatzema `session_id`, estat, URL de signatura, dades del destinatari i timestamps.

---

## Giswater

Integració bidireccional amb Giswater per consultar connecs des del PA i exposar contractes i lectures cap a Giswater.

**API Swagger externa:** [https://<instancia>.bgeo360.com/giswater/v1/docs](https://<instancia>.bgeo360.com/giswater/v1/docs)

### Outbound

Codi: `integrations/outbound/giswater/`

Documentació operativa: `integrations/outbound/giswater/README.md`

#### Configuració (`.env`)

```env
GISWATER_BASE_URL=https://<instancia>.bgeo360.com/giswater/v1
GISWATER_TIMEOUT=30

# OAuth Keycloak (si GISWATER_KEYCLOAK_URL està definit)
GISWATER_KEYCLOAK_URL=https://portal.bgeo360.com/auth
GISWATER_REALM=<realm>
GISWATER_CLIENT_ID=aqua360
GISWATER_CLIENT_SECRET=

# HTTP Basic Auth (fallback si GISWATER_KEYCLOAK_URL està buit)
GISWATER_USERNAME=
GISWATER_PASSWORD=

GISWATER_TOKEN=

GISWATER_SYNC_CONNECS_ENABLED=False
GISWATER_SYNC_CONNECS_HOUR=3
GISWATER_SYNC_CONNECS_MINUTE=0
```

`GISWATER_BASE_URL` ha d'incloure `/v1`. Les variables es carreguen amb `python-decouple` a `customers/settings.py`.

#### Autenticació

- Si `GISWATER_KEYCLOAK_URL` està definit → OAuth via Keycloak (`client_credentials`). El token no es persisteix; es demana a cada crida HTTP.
- Si `GISWATER_KEYCLOAK_URL` està buit → HTTP Basic Auth amb `GISWATER_USERNAME` / `GISWATER_PASSWORD`.

```bash
python manage.py validate_giswater_auth
```

#### Comandes de consola

| Comanda | Què fa |
|---------|--------|
| `validate_giswater_auth` | Comprova Keycloak o Basic Auth segons configuració |
| `fetch_giswater_connecs` | Crida `GET /basic/getlist?schema=ws&tableName=ve_connec` i guarda log |
| `sync_giswater_connections` | Sincronitza dades cap a `Connection` del PA |

```bash
python manage.py validate_giswater_auth
python manage.py fetch_giswater_connecs
python manage.py fetch_giswater_connecs --save-json /tmp/giswater_connecs.json
python manage.py fetch_giswater_connecs --preview-chars 1000
python manage.py sync_giswater_connections
python manage.py sync_giswater_connections --only-not-found
python manage.py sync_giswater_connections --csv /tmp/giswater_not_found.csv
```

Opcions de `fetch_giswater_connecs`:

| Opció | Descripció |
|-------|------------|
| `--save-json RUTA` | Guarda la resposta JSON completa en un fitxer |
| `--preview-chars N` | Caràcters de previsualització per consola (default: 500) |

Opcions de `sync_giswater_connections`:

| Opció | Descripció |
|-------|------------|
| `--only-not-found` | Mostra només els `customer_code` sense `Connection` activa al PA |
| `--csv RUTA` | Exporta `not_found` a CSV (separador `;`). `-` = stdout |

Mapatge Giswater → `Connection` (connecs de tipus **ESCO**):

| Giswater (`body.data.fields[]`) | `Connection` |
|----------------------------------|--------------|
| `customer_code` | `token` (clau de cerca) |
| `connec_id` | `code_gis` |
| `lat` | `latitude` |
| `long` | `longitude` |

Estadístiques de sync: `total_fields`, `esco_tokens`, `skipped`, `updated`, `not_found`, `unchanged`.

#### Celery

| Tasca | Descripció |
|-------|------------|
| `integrations.tasks.fetch_giswater_connecs_task` | Obté connecs (sense sync) |
| `integrations.tasks.sync_giswater_connections_task` | Sync completa Giswater → Connection |

Programació diària amb Celery Beat si `GISWATER_SYNC_CONNECS_ENABLED=True` (veure `customers/celery.py`).

#### Tests

```bash
python manage.py test integrations.outbound.giswater.tests integrations.outbound.giswater.test_sync
```

### Inbound

Codi: `integrations/inbound/giswater/`

OpenAPI: `integrations/inbound/giswater/openapi.yaml` — importable a [Swagger Editor](https://editor.swagger.io), Postman o Redoc.

Les rutes inbound estan versionades sota `/giswater/v1/`. Canvis trencadors de format es publicaran com a `/giswater/v2/`, etc.

#### Autenticació

Autenticació per token de Django REST Framework (`rest_framework.authtoken`), la mateixa que la resta de l'API del PA.

L'usuari ha de pertànyer al grup Django `giswater`. El middleware restringeix aquest grup
només a rutes sota `/giswater/` (igual que el grup `ov` només pot accedir a `/ov/`).
Qualsevol altra ruta retorna `403 Forbidden`.

1. Crear l'usuari i el grup (variables `GISWATER_USER_*` al `.env`):

```
python manage.py get_or_create_giswater_user
```

O crear-lo manualment a l'admin Django i assignar-lo al grup `giswater`.

2. Obtenir el token amb login:

```
POST /auth/login/
```

```json
{
  "username": "giswater",
  "password": "…"
}
```

Resposta:

```json
{
  "username": "giswater",
  "token": "7b21d0b21ac28cd8721688b5db7d484adc32101f"
}
```

També es pot generar el token des de l'admin Django o amb `Token.objects.get_or_create(user=…)`.

3. Incloure el token a cada crida:

```
Authorization: Token 7b21d0b21ac28cd8721688b5db7d484adc32101f
```

#### Llistat de contractes

```
GET /giswater/v1/contracts/
GET /giswater/v1/contracts/?connection_token=CONN-001
GET /giswater/v1/contracts/?connection_code_gis=12547
```

Filtres opcionals (query string):

| Paràmetre | Descripció |
|-----------|------------|
| `connection_token` | Token de la connexió (`Connection.token`) del `supply_point_default` |
| `connection_code_gis` | Identificador connec a Giswater (`Connection.code_gis`) |

Si s'indiquen ambdós filtres, s'apliquen en conjunció (AND). Sense filtres, retorna tots els contractes. Si no hi ha coincidències, retorna una llista buida (`[]`).

```json
[
  {
    "connection": {
      "token": "CONN-001",
      "code_gis": "12547",
      "exploitation_token": "EXP-01",
      "diameter": "D20",
      "dma_token": "DMA-01",
      "latitude": 41.480614,
      "longitude": 2.323578
    },
    "supply_point": {
      "token": "SP-001",
      "address": "Barcelona, 08000",
      "meter_code": "MTR-001"
    },
    "contract": {
      "token": "CTR-001",
      "holder": {
        "name": "Anna",
        "surname": "Garcia"
      },
      "holder_full_name": "Anna Garcia"
    }
  }
]
```

Si un contracte no té `supply_point_default` o connexió associada, els camps `connection` i/o `supply_point` seran `null`.

#### Lectures d'un contracte

```
GET /giswater/v1/contracts/{contract_token}/readings/
```

Paràmetre d'URL: `contract_token` = `Contract.token`.

Retorna les `Reading` amb `contract_id` coincident, `is_active=True`, ordenades per `reading_date` descendent:

```json
[
  {
    "id": 123,
    "meter_code": "MTR-001",
    "reading_date": "2026-01-15",
    "reading_value": 100.5,
    "consumption": 12.0,
    "is_control": false,
    "origin": "manual",
    "is_estimated": false,
    "estimated_used": null,
    "supply_point_token": "SP-001",
    "consumption_days": 30,
    "billing_consumption": 11.5
  }
]
```

| Codi | Motiu |
|------|-------|
| `401` | Falta o és incorrecte el token (`Authorization: Token …`) |
| `404` | Contracte no trobat |
| `200` | Llista de lectures (pot ser buida) |

Les crides es registren a `IntegrationRequestLog` (provider `giswater`, direction `inbound`).

#### Tests

```bash
python manage.py test integrations.inbound.giswater.tests
```

---

## Smartmetering

Integració **inbound**: sistemes de smart metering consulten contractes (abonats) al PA.

**Codi:** `integrations/inbound/smartmetering/`

**Contracte de dades:** [`docs/integrations/smartmetering/data-contract.md`](integrations/smartmetering/data-contract.md)

OpenAPI per a integradors: [`docs/integrations/smartmetering/openapi.yaml`](integrations/smartmetering/openapi.yaml) — importable a [Swagger Editor](https://editor.swagger.io), Postman o Redoc. Còpia d'implementació (amb mapatge intern): `integrations/inbound/smartmetering/openapi.yaml`.

El payload replica `vw_abonats_aqua360`, però es calcula des dels models Django. La vista SQL no cal que estigui desplegada.

Les rutes inbound estan versionades sota `/smartmetering/v1/`.

### Autenticació

Autenticació per token de Django REST Framework (`rest_framework.authtoken`), la mateixa que la resta de l'API del PA.

L'usuari ha de pertànyer al grup Django `smartmetering`. El middleware restringeix aquest grup
només a rutes sota `/smartmetering/` (igual que `giswater` a `/giswater/` i `ov` a `/ov/`).
Qualsevol altra ruta retorna `403 Forbidden`.

1. Crear l'usuari i el grup (variables `SMARTMETERING_USER_*` al `.env`):

```
python manage.py get_or_create_smartmetering_user
```

O crear-lo manualment a l'admin Django i assignar-lo al grup `smartmetering`.

2. Obtenir el token amb login:

```
POST /auth/login/
```

```json
{
  "username": "smartmetering",
  "password": "…"
}
```

Resposta:

```json
{
  "username": "smartmetering",
  "token": "7b21d0b21ac28cd8721688b5db7d484adc32101f"
}
```

3. Incloure el token a cada crida:

```
Authorization: Token 7b21d0b21ac28cd8721688b5db7d484adc32101f
```

### Llistat d'abonats (contractes)

```
GET /smartmetering/v1/contracts/
GET /smartmetering/v1/contracts/?policy=CTR-001
GET /smartmetering/v1/contracts/?meter=MTR-001
```

Només contractes amb `is_active=true`. Filtres opcionals (query string):

| Paràmetre | Descripció |
|-----------|------------|
| `policy` | Token del contracte (`Contract.token`) |
| `meter` | Codi del comptador (`Meter.code`) del `supply_point_default` |

Si s'indiquen ambdós filtres, s'apliquen en conjunció (AND). Sense filtres, retorna tots els contractes actius. Si no hi ha coincidències, retorna una llista buida (`[]`).

```json
[
  {
    "policy": "CTR-001",
    "meter": "MTR-001",
    "rate": "Domèstica",
    "service_point": "Barcelona, 08000",
    "inst_date": "2024-03-15",
    "comm_module": "MOD-99",
    "comm_technology": "NB-IoT",
    "manufacturer": "Elster",
    "model": "A1700",
    "network_provider": "Vodafone",
    "expl_id": "EXP-01",
    "dma_id": "DMA-01",
    "contract_active": true,
    "customer": "Anna Garcia",
    "cadastral_ref": "08001A00010001",
    "connect_id": "12"
  }
]
```

`contract_active` és `true` quan `Contract.status.token` coincideix amb `ConfigProject.contract_active_token` (equivalent portable a `status_id = 2` de la vista). `expl_id` i `dma_id` són `Exploitation.token` i `DMA.token` (equivalents portables als PK de la vista). Relacions absents → `null`.

Les crides es registren a `IntegrationRequestLog` (provider `smartmetering`, direction `inbound`).

### Tests

```bash
python manage.py test integrations.inbound.smartmetering.tests
```

---

## Aqua360 Sign

Integració outbound + inbound amb **Aqua360 Sign**: el PA envia el PDF d'una sol·licitud (`ContractRequest`) o d'un `DocumentSign`, i recupera el PDF segellat pel webhook o pel sondeig.

**Codi:** `integrations/outbound/signing/`, `integrations/inbound/signing/`

**Documentació:** [`docs/integrations/signing/data-contract.md`](integrations/signing/data-contract.md) (payloads, configuració, webhook, sondeig i comandes).

### Comprovar la connexió

```bash
python manage.py check_signing_connection
```

Fa `GET` d'una sessió inexistent. Un `404` JSON vol dir que Sign ha acceptat `SIGNING_API_KEY`. No crea cap sessió ni envia cap correu. El detall (i el `curl` equivalent per a un servidor que encara no té la comanda) és al contracte de dades.

### Tests

```bash
python manage.py test integrations.outbound.signing.tests integrations.inbound.signing.tests
```

---

## Odoo — ERP Comptabilitat

Integració **outbound** per enviar factures, rectificatives i moviments de pagament des d'Aqua360 cap a **Odoo 19 Community**.

**Codi:** `integrations/outbound/odoo/`

**Estat actual:** Fase 1 — mappers, client HTTP, comandes de consola i tests. Sense automatització Celery ni webhook de resposta.

**Documentació:**

| Document | Descripció |
|----------|------------|
| [`docs/integrations/odoo/data-contract.md`](integrations/odoo/data-contract.md) | Contracte de dades (JSON, mapatges, principis) |
| [`docs/integrations/odoo/plan.md`](integrations/odoo/plan.md) | Pla d'implementació (fases, mapatge des de `billing`) |
| [`integrations/outbound/odoo/README.md`](../integrations/outbound/odoo/README.md) | Resum operatiu al repositori de codi |

### Mapatge de models PA

| Concepte Odoo | Model PA |
|---------------|----------|
| Impostos (`tax_ids`) | `pricing.Tax.token` |
| Diari facturació (`journal_id`) | `billing.InvoiceSerie` (via `Invoice.serie`) |
| Mode de pagament | `contract.PaymentType.token` |
| NIF/CIF partner (`vat`) | `Invoice.customer_token_final` |
| Moviment comptable | `billing.PaymentMovement` (no `Payment` directament) |

### Contracte de dades (resum)

- **`aqua_id`**: àncora d'idempotència (`Invoice.token`, `PaymentMovement.token`).
- **Creació al vol** a Odoo: partner, diari, producte (`get_or_create` per `aqua_id`).
- **Preexistència obligatòria** a Odoo: impostos (`tax_ids`) i modes de pagament (`payment_mode_id`).
- **Numeració i Verifactu**: les fixa Aqua360; Odoo respecta `name` sense renumerar.
- **v1**: un `PaymentMovement` positiu es concilia amb una sola factura.
- **v1.1**: devolució (`is_positive=False`) amb el mateix JSON i `amount` negatiu. Sense factura, `invoice_aqua_id` va buit (bossa del client).

### Configuració (`.env`)

```env
ODOO_BASE_URL=
ODOO_API_KEY=
ODOO_TIMEOUT=30
ODOO_PUSH_ENABLED=False
ODOO_PUSH_INVOICES=True
ODOO_PUSH_PAYMENTS=True
```

Variables afegides a `.env.example` i carregades a `customers/settings.py`.

### Comandes de consola

```bash
# Generar JSON sense enviar
python manage.py push_invoice_to_odoo --invoice-id 123 --dry-run
python manage.py push_payment_movement_to_odoo --movement-id 456 --dry-run

# Enviar a Odoo (requereix ODOO_BASE_URL i ODOO_API_KEY)
python manage.py push_invoice_to_odoo --invoice-id 123
python manage.py push_payment_movement_to_odoo --movement-id 456
```

### Tests

```bash
python manage.py test integrations.outbound.odoo.tests
```

### Fora d'abast (v2)

- Compromisos de pagament i conciliació múltiple (remeses agrupades)
- Acusament d'estat acceptat/rebutjat per reintents
- Desfer la conciliació a Odoo en devolucions SEPA (el JSON amb `amount` negatiu és v1.1)
