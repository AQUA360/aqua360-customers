# Importació de documents de lectura — guia per al frontend

Documentació de l'API per importar fitxers de lectures (CSV/XLSX) al sistema, amb **validació prèvia** abans d'entrades definitives i capacitat de **corregir i reprocessar**.

**Base URL:** `/billing/reading-document/`  
**Autenticació:** sessió/token habitual de l'aplicació (`IsAuthenticated`).  
**Permisos:** es reutilitzen els de `Reading` (`view_reading`, `add_reading`, etc.) via `ReadingPermission`.

> **Requisit backend:** cal tenir aplicada la migració `billing.0301_readingdocument_status` per als camps `status`, `task_id`, `processed_at` i `last_preview`.

---

## Resum del flux recomanat (nou)

```text
1. POST /billing/reading-document/     (auto_process=false)
      ↓
2. GET  /billing/reading-document/{id}/validate/
      ↓  (usuari revisa stats + mostra de files)
3a. POST /billing/reading-document/{id}/process/     → entra al sistema
3b. PATCH /billing/reading-document/{id}/              → corregeix fitxer/plantilla
      ↓
   Torna al pas 2
3c. POST /billing/reading-document/{id}/reprocess/     → reprocessa després de corregir
```

### Flux legacy (comportament anterior, encara vàlid)

Si el `POST` de creació **no** envia `auto_process=false` (o l'envia com a `true`), el document es processa **immediatament** via Celery, sense pas de validació. És el comportament que tenia el frontend abans del canvi.

---

## Màquina d'estats (`status`)

| Valor | Significat | Accions frontend suggerides |
|-------|------------|-----------------------------|
| `pending` | Fitxer pujat, encara no processat (o re-editat) | Mostrar botó **Validar** i **Processar** |
| `processing` | Tasca Celery en curs | Deshabilitar accions; fer polling de `task_id` |
| `processed` | Processament completat | Mostrar resultats (`num_readings`, `not_found_readings`) |
| `failed` | La tasca ha fallat | Mostrar error; permetre corregir fitxer i `reprocess` |

**Transicions rellevants:**

- `POST` amb `auto_process=false` → `pending`
- `POST` amb `auto_process=true` (defecte) → `processing` (+ `task_id`)
- `validate` → manté o posa `pending`; omple `last_preview`
- `PATCH` amb fitxer o plantilla nova → `pending` (neteja `last_preview`, `processed_at`, `task_id`) si no estava `processing`
- `process` / `reprocess` → `processing`
- Fi de Celery OK → `processed` + `processed_at`
- Fi de Celery KO → `failed`

---

## Endpoints

### Llistat

| Mètode | URL | Descripció |
|--------|-----|------------|
| `GET` | `/billing/reading-document/` | Llista documents |
| `POST` | `/billing/reading-document/` | Puja document (opcionalment processa) |
| `GET` | `/billing/reading-document/{id}/` | Detall document |
| `PATCH` | `/billing/reading-document/{id}/` | Actualitza document (fitxer, plantilla, batch…) |
| `DELETE` | `/billing/reading-document/{id}/` | Elimina document |
| `GET` \| `POST` | `/billing/reading-document/{id}/validate/` | **Preview** síncron (no escriu lectures) |
| `POST` | `/billing/reading-document/{id}/process/` | Confirma i processa (Celery) |
| `POST` | `/billing/reading-document/{id}/reprocess/` | Torna a processar (neteja `not_found` anteriors) |
| `GET` | `/billing/reading-document/template/` | Descarrega CSV plantilla buida |
| `GET` | `/billing/reading-document/permissions/` | Permisos de l'usuari |
| `GET` | `/task-progress/{task_id}/` | Estat de la tasca Celery |

### Plantilles de mapping (recurs relacionat)

| Mètode | URL | Descripció |
|--------|-----|------------|
| `GET` | `/statistics/reading-batch-import-template/` | Llista plantilles |
| `GET` | `/statistics/reading-batch-import-template/{id}/` | Detall plantilla + columnes |
| `GET` | `/statistics/reading-batch-import-column/?template={id}` | Columnes d'una plantilla |

---

## 1. Crear document (`POST`)

**URL:** `POST /billing/reading-document/`  
**Content-Type:** `multipart/form-data`

| Camp | Tipus | Obligatori | Descripció |
|------|-------|------------|------------|
| `file` | fitxer | Sí | CSV o XLSX amb les lectures |
| `template` | enter | No | ID de `ReadingBatchImportTemplate` per mapar columnes |
| `batch` | enter | No | ID de `ReadingBatch` (opcional) |
| `auto_process` | booleà / string | No | **Defecte: `true`**. Posar `false` per activar el flux de validació |

**Valors acceptats per `auto_process` com a string:** `false`, `0`, `no`, `off` → no processa. Qualsevol altre valor → processa.

#### Exemple (flux nou — només pujar)

```http
POST /billing/reading-document/
Content-Type: multipart/form-data

file: LECTURES_LECTOR_CSV.csv
template: 2
auto_process: false
```

**Resposta `201 Created`:**

```json
{
  "id": 12,
  "token": "260715012",
  "file": "http://127.0.0.1:8000/media/uploads/billing/readings/LECTURES_....csv",
  "batch": null,
  "template": 2,
  "status": "pending",
  "task_id": null,
  "processed_at": null,
  "last_preview": null,
  "not_found_readings": [],
  "num_readings": 0
}
```

#### Exemple (flux legacy — processament immediat)

```http
POST /billing/reading-document/
Content-Type: multipart/form-data

file: LECTURES_LECTOR_CSV.csv
template: 2
```

**Resposta `201`:** `status: "processing"`, `task_id: "<uuid>"`.

---

## 2. Validar / preview (`GET` o `POST`)

**URL:** `GET /billing/reading-document/{id}/validate/`  
També accepta `POST` (mateix comportament).

**Query params / body (opcional):**

| Param | Tipus | Defecte | Descripció |
|-------|-------|---------|------------|
| `max_rows` | int | `25` | Mida de pàgina de `rows` |
| `offset` | int | `0` | Desplaçament dins el conjunt **ja filtrat** |
| `page` | int | — | Alternativa 1-based a `offset` (`offset = (page-1) * page_size`) |
| `page_size` | int | — | Equivalent a `max_rows` quan s'usa `page` |
| `action` | string | (totes) | Filtre: `would_create`, `would_update`, `not_found`, `skip` |
| `reason` | string | — | Només amb `action=skip`: `skipped_existing`, `skipped_no_date`, `no_supply_points`, `no_contracts` |
| `search` | string | — | Cerca parcial a `meter_code`, `comm_module`, `contract_token` |
| `ordering` | string | `row_index` | `row_index` o `-row_index` |
| `refresh` | bool | `false` | Força a tornar a llegir el CSV (ignora `last_preview`) |

**Comportament clau:**

1. **`stats`**: sempre del fitxer sencer (independent de filtre/pàgina).
2. Es **filtra abans de paginar** sobre totes les entrades de preview (no «primeres N del CSV i després filtre»).
3. Si existeix un `last_preview` complet al document, filtre/pàgina es serveixen **sense reprocessar el CSV**.
4. `PATCH` de fitxer/plantilla invalida `last_preview`. `refresh=true` o primer `validate` després d'un canvi reconstrueix la cache.
5. Una mateixa fila CSV pot generar diverses entrades a `rows` (diversos contractes); `filtered_total` compta entrades de preview.

**Resposta `200 OK`:**

```json
{
  "stats": {
    "rows": 319,
    "skipped_no_date": 0,
    "not_found_meter": 106,
    "no_supply_points": 0,
    "no_contracts": 0,
    "skipped_existing": 213,
    "would_create": 0,
    "would_update": 0
  },
  "labels": {
    "comm_module_label": "Meter address",
    "reading_date_label": "Receive time",
    "reading_value_label": "Value"
  },
  "template_is_liters": true,
  "rows": [
    {
      "row_index": 1,
      "action": "skip",
      "reason": "skipped_existing",
      "meter_code": "SEN20144326",
      "comm_module": "SEN20144326",
      "contract_token": "18260107",
      "supply_point_id": 1601,
      "reading_date": "2026-07-01",
      "reading_date_raw": "1/7/26 9:47",
      "reading_value": 0,
      "raw_reading_value": "32",
      "previous_reading_value": 28,
      "origin": "TELECONTROL",
      "is_control": false,
      "leak_value": 0,
      "observation": ""
    }
  ],
  "filtered_total": 106,
  "total_rows": 319,
  "rows_truncated": true,
  "offset": 0,
  "max_rows": 25,
  "action": "not_found",
  "reason": null,
  "search": null,
  "ordering": "row_index"
}
```

Cada entrada de `rows[]` inclou sempre el mateix conjunt de camps de lectura (valor efectiu que s'importaria), també en `skip` / `not_found`:

| Camp | Notes |
|------|--------|
| `origin` | Fitxer o defecte `TELECONTROL` (mateixa lògica que el processament) |
| `is_control` | `true` només si el valor parsejat és `"true"` (case-insensitive) |
| `leak_value` | Enter; `0` si buit / no parsejable |
| `observation` | String (pot ser `""`) |
| `raw_reading_value` | Valor cru del fitxer |
| `previous_reading_value` | Si es coneix la lectura anterior |
| `comm_module` / `supply_point_id` / `reading_date_raw` | Quan apliquen |

> Si la cache `last_preview` és d’una versió anterior (sense aquests camps), el pròxim `validate` la reconstrueix sola (`preview_schema_version`). També es pot forçar amb `refresh=true`.

| Camp | Descripció |
|------|------------|
| `filtered_total` | Entrades que compleixen el filtre (per paginar al frontend) |
| `total_rows` | Total d'entrades de preview del fitxer (sense filtre) |
| `rows_truncated` | `true` si `offset + len(rows) < filtered_total` |
| `rows` | Només la pàgina demanada, ja filtrada |

**Exemples:**

```http
GET /billing/reading-document/12/validate/?offset=0&max_rows=25
GET /billing/reading-document/12/validate/?action=not_found&offset=0&max_rows=25
GET /billing/reading-document/12/validate/?action=not_found&offset=25&max_rows=25
GET /billing/reading-document/12/validate/?action=skip&reason=skipped_existing&page=1&page_size=25
GET /billing/reading-document/12/validate/?search=SEN201&refresh=true
```

**Ús previst al frontend:**

| Acció usuari | Crida |
|--------------|--------|
| Obrir preview | `validate/?offset=0&max_rows=25` |
| Filtre «no trobats» | `validate/?action=not_found&offset=0&max_rows=25` |
| Canviar pàgina | mateix filtre + `offset` / `page` nou |
| «Tornar a validar» | `validate/?refresh=true&offset=0&max_rows=25` |

**Errors:**

| Codi | Motiu |
|------|-------|
| `400` | Document sense fitxer; `action`/`reason`/`ordering` invàlids; enters negatius o mal formats |

---

## 3. Confirmar processament (`POST /process`)

**URL:** `POST /billing/reading-document/{id}/process/`  
**Body:** buit (o `{}`)

**Resposta `202 Accepted`:**

```json
{
  "task_id": "9c268da1-f004-4abe-8021-89b08174f5b5"
}
```

**Resposta `409 Conflict`:** ja s'està processant.

```json
{
  "task_id": "9c268da1-...",
  "detail": "El document ja s'està processant."
}
```

---

## 4. Reprocessar (`POST /reprocess`)

**URL:** `POST /billing/reading-document/{id}/reprocess/`

Igual que `process`, però:

- Esborra els `ReadingDocumentNotFound` anteriors del document abans de processar.
- Útil després de `PATCH` amb fitxer o plantilla corregits.

**Resposta:** mateix format que `process` (`202` + `task_id`).

> **Nota:** les lectures ja creades en un processament anterior **no s'esborren**. En reprocessar, les files amb lectura existent es marquen com a `skipped_existing` durant el preview i es salten en el processament real.

---

## 5. Actualitzar document (`PATCH`)

**URL:** `PATCH /billing/reading-document/{id}/`  
**Content-Type:** `multipart/form-data` (si hi ha fitxer nou)

| Camp | Descripció |
|------|------------|
| `file` | Nou fitxer CSV/XLSX |
| `template` | Nova plantilla de mapping |

Si canvia `file` o `template` i el document **no** està `processing`:

- `status` → `pending`
- `last_preview` → `null`
- `processed_at` → `null`
- `task_id` → `null`

Després del `PATCH`, cal tornar a cridar `validate` abans de `process`/`reprocess`.

---

## 6. Detall i llistat

### Detall (`GET /billing/reading-document/{id}/`)

Camps rellevants per al frontend:

```json
{
  "id": 12,
  "token": "260715012",
  "file": "http://.../media/uploads/billing/readings/....csv",
  "batch": null,
  "template": {
    "id": 2,
    "name": "PLANTILLA_1",
    "is_liters": true,
    "columns": [
      { "id": 30, "original_name": "comm_module", "mapped_name": "Meter address" },
      { "id": 31, "original_name": "reading_value", "mapped_name": "Value" },
      { "id": 32, "original_name": "reading_date", "mapped_name": "Receive time" },
      { "id": 34, "original_name": "is_control", "mapped_name": "Control" }
    ]
  },
  "status": "processed",
  "task_id": "9c268da1-...",
  "processed_at": "2026-07-15T16:44:40+02:00",
  "last_preview": { "...": "..." },
  "not_found_readings": [
    {
      "id": 1,
      "meter_code": "10100176442",
      "reading_value": 59927,
      "reading_date": "2026-07-01",
      "origin": null,
      "is_control": false,
      "leak_value": 0,
      "observation": ""
    }
  ],
  "num_readings": 280
}
```

### Llistat (`GET /billing/reading-document/`)

Afegeix respecte al model base:

- `num_readings`
- `num_not_found_readings`

---

## 7. Seguiment de la tasca Celery

**URL:** `GET /task-progress/{task_id}/`

```json
// En curs
{ "state": "PENDING" }

// Èxit
{
  "state": "SUCCESS",
  "percent": 100,
  "current": 1,
  "total": 1,
  "result": {
    "rows": 319,
    "skipped_no_date": 0,
    "not_found_meter": 12,
    "created": 280,
    "updated": 12,
    ...
  }
}

// Error
{
  "state": "FAILURE",
  "error": "..."
}
```

**Estratègia de polling suggerida:**

1. Després de `process`/`reprocess`, guardar `task_id`.
2. Poll cada 1–2 s a `/task-progress/{task_id}/`.
3. Quan `state === "SUCCESS"` o `"FAILURE"`, fer `GET /billing/reading-document/{id}/` per refrescar `status`, `num_readings`, `not_found_readings`.

Alternativa: només fer polling del document (`status` + `num_readings`) sense `task-progress`.

---

## Estadístiques del preview (`stats`)

| Clau | Significat | Color UI suggerit |
|------|------------|-------------------|
| `rows` | Total files llegides del fitxer | Neutre |
| `would_create` | Lectures noves que es crearien | Verd |
| `would_update` | Lectures existents que s'actualitzarien (acumulació de consum) | Taronja |
| `not_found_meter` | Files on no s'ha trobat el comptador | Vermell |
| `skipped_existing` | Ja existeix una lectura per aquella data/contracte | Groc |
| `skipped_no_date` | Data no parsejable o columna buida | Vermell |
| `no_supply_points` | Comptador trobat però sense punt de subministrament | Taronja |
| `no_contracts` | Comptador trobat però sense contracte actiu/vàlid | Taronja |

En el processament real (Celery), `would_create` → lectures creades; `would_update` → lectures actualitzades. Els comptadors de `stats` del resultat de la tasca usen `created` i `updated` (mateix significat).

---

## Accions per fila al preview (`rows[]`)

Cada element de `rows` pot tenir una `action` o `reason` diferent. Una mateixa fila del CSV pot generar **múltiples entrades** a `rows` si el comptador té diversos contractes.

**Contracte de camps:** totes les entrades (`would_create`, `would_update`, `not_found`, `skip`) comparteixen el mateix conjunt de camps de lectura. Els valors són els **efectius** que usaria el processament (p. ex. `origin` defecte `TELECONTROL`, `is_control: false`, `leak_value: 0` si buit).

### `action: "would_create"`

Es crearia una lectura nova.

```json
{
  "row_index": 1,
  "action": "would_create",
  "reason": null,
  "meter_code": "SEN20144326",
  "comm_module": "SEN20144326",
  "contract_token": "301107",
  "supply_point_id": 1601,
  "reading_date": "2026-07-01",
  "reading_date_raw": "1/7/26 9:47",
  "reading_value": 0,
  "raw_reading_value": "32",
  "previous_reading_value": 28,
  "origin": "TELECONTROL",
  "is_control": false,
  "leak_value": 0,
  "observation": ""
}
```

### `action: "would_update"`

S'actualitzaria una lectura anterior (acumulació dins del mateix període de facturació).

```json
{
  "row_index": 2,
  "action": "would_update",
  "reason": null,
  "meter_code": "SEN20144330",
  "comm_module": "SEN20144330",
  "contract_token": "301296",
  "supply_point_id": 1485,
  "reading_date": "2026-07-01",
  "reading_date_raw": "1/7/26 8:34",
  "reading_value": 10,
  "raw_reading_value": "10187",
  "previous_reading_value": 9,
  "origin": "TELECONTROL",
  "is_control": false,
  "leak_value": 0,
  "observation": ""
}
```

### `action: "not_found"`

No s'ha resolt el comptador.

```json
{
  "row_index": 4,
  "action": "not_found",
  "reason": null,
  "meter_code": "10100176442",
  "comm_module": "10100176442",
  "contract_token": null,
  "supply_point_id": null,
  "reading_date": "2026-07-01",
  "reading_date_raw": "1/7/26 10:00",
  "reading_value": 59927,
  "raw_reading_value": "59927718",
  "previous_reading_value": null,
  "origin": "TELECONTROL",
  "is_control": false,
  "leak_value": 0,
  "observation": ""
}
```

### `action: "skip"` (amb `reason`)

| `reason` | Significat |
|----------|------------|
| `skipped_no_date` | No s'ha pogut llegir la data (`reading_date_raw` inclòs) |
| `no_supply_points` | Comptador sense punts de subministrament |
| `no_contracts` | Sense contracte actiu o terminat vàlid |
| `skipped_existing` | Ja hi ha lectura per aquella data o posterior |

```json
{
  "row_index": 3,
  "action": "skip",
  "reason": "skipped_existing",
  "meter_code": "SEN20175659",
  "comm_module": "SEN20175659",
  "contract_token": "301295",
  "supply_point_id": 2055,
  "reading_date": "2026-07-01",
  "reading_date_raw": "1/7/26 9:49",
  "reading_value": 2,
  "raw_reading_value": "2314",
  "previous_reading_value": 2,
  "origin": "TELECONTROL",
  "is_control": false,
  "leak_value": 0,
  "observation": ""
}
```

### `rows_truncated`

Si `true`, encara queden més entrades després de la pàgina actual (`offset + len(rows) < filtered_total`). Usar `filtered_total` per calcular el nombre total de pàgines.

---

## Plantilles i mapping de columnes

El fitxer d'entrada pot tenir capçaleres arbitràries. La **plantilla** (`ReadingBatchImportTemplate`) mapa cada camp intern a una columna del fitxer via `ReadingBatchImportColumn`:

| `original_name` (camp intern) | Exemple `mapped_name` (capçalera CSV) |
|-------------------------------|---------------------------------------|
| `meter` | (buit si no s'usa) |
| `comm_module` | `Meter address` |
| `reading_value` | `Value` |
| `reading_date` | `Receive time` |
| `is_control` | `Control` |
| `origin` | |
| `observation` | |
| `leak_value` | |
| `contract` | |
| `reading` | (valor alternatiu de lectura) |

El preview retorna el mapping efectiu a `labels` (útil per depurar si una columna no es llegeix).

### `is_liters` (plantilla)

Si `template.is_liters === true`, el valor numèric del fitxer s'interpreta com a **litres** i es divideix per 1000 abans de guardar (p. ex. `10187` → `10` m³). Això afecta tant el preview com el processament.

---

## Resolució del comptador (ordre de cerca)

Per cada fila, el backend intenta trobar el `Meter` en aquest ordre:

1. **Columna `meter`** (si està mapada): per `code`, `token`, variants amb trim/padding (8–10 dígits).
2. **Columna `comm_module`** (p. ex. `Meter address`): cerca exacta a `Meter.comm_module`.
3. **Columna `contract`** (si existeix al fitxer): agafa el comptador del `supply_point_default` del contracte.

Si cap opció funciona → `not_found_meter`.

---

## Formats de fitxer suportats

| Format | Extensió | Notes |
|--------|----------|-------|
| CSV | `.csv` | Delimitador `;`, `,` o tab (detecció automàtica per la capçalera) |
| Excel | `.xlsx`, `.xlsm` | Primera fulla activa |

### Formats de data acceptats (exemples)

- `1/7/26 9:47` → `%d/%m/%y %H:%M`
- `01/07/2026 09:47` → `%d/%m/%Y %H:%M`
- `2026-07-01`
- Altres variants (veure `parse_reading_document_date` al backend)

---

## Esbós de pantalla per al frontend

```text
┌─────────────────────────────────────────────────────────────┐
│  Importar lectures                                          │
├─────────────────────────────────────────────────────────────┤
│  Plantilla: [PLANTILLA_1 ▼]     Fitxer: [Seleccionar CSV]   │
│                                                             │
│  [Pujar i validar]                                          │
├─────────────────────────────────────────────────────────────┤
│  Resum (stats)                                              │
│  ┌──────────┬──────────┬──────────┬──────────┐              │
│  │ 319 files│ 280 noves│ 12 error │ 10 exist.│              │
│  └──────────┴──────────┴──────────┴──────────┘              │
│                                                             │
│  Taula preview (rows, paginada si rows_truncated)           │
│  # │ Comptador    │ Contracte │ Data       │ Acció          │
│  1 │ SEN20144326  │ 301107    │ 2026-07-01 │ Crear          │
│  4 │ 10100176442  │ —         │ 2026-07-01 │ No trobat      │
│                                                             │
│  [Canviar fitxer]  [Tornar a validar]  [Confirmar entrada]  │
└─────────────────────────────────────────────────────────────┘
```

### Flux d'interacció

| Pas | Acció usuari | Crida API |
|-----|--------------|-----------|
| 1 | Selecciona plantilla + fitxer | — |
| 2 | «Pujar i validar» | `POST` amb `auto_process=false` |
| 3 | (automàtic) | `GET .../validate/?offset=0&max_rows=25` |
| 4 | Revisa taula i resum | Mostra `stats` + `rows` paginades; `filtered_total` per paginar |
| 4b | Clic filtre (p. ex. no trobats) | `GET .../validate/?action=not_found&offset=0&max_rows=25` |
| 4c | Canviar pàgina | mateix filtre + nou `offset` |
| 5a | Tot OK → «Confirmar» | `POST .../process/` → polling → `GET` detall |
| 5b | Cal corregir → nou fitxer | `PATCH` → `GET .../validate/?refresh=true&...` → tornar al pas 4 |
| 5c | Ja processat, cal repetir | `POST .../reprocess/` |

### Botons segons `status`

| `status` | Botons habilitats |
|----------|-------------------|
| `pending` | Validar, Processar, Canviar fitxer/plantilla |
| `processing` | Cap (spinner + polling) |
| `processed` | Veure resultats, Reprocessar, Canviar fitxer |
| `failed` | Validar, Reprocessar, Canviar fitxer |

---

## `not_found_readings` (després del processament)

Quan el processament real acaba, les files sense comptador es persisteixen a `not_found_readings`:

```json
{
  "id": 1,
  "meter_code": "10100176442",
  "reading_value": 59927,
  "reading_date": "2026-07-01",
  "origin": null,
  "is_control": false,
  "leak_value": 0,
  "observation": "",
  "token": "10100176442/DOC260701"
}
```

El frontend pot mostrar aquesta llista com a «lectures no importades» després de confirmar.

---

## Permisos

`GET /billing/reading-document/permissions/` retorna els permisos de l'usuari sobre `readingdocument` (via `PermissionManager`).

Les accions de creació/edició requereixen els permisos habituals de `Reading` (`add_reading`, `change_reading`, etc.).

---

## Errors habituals i com mostrar-los

| Símptoma | Causa probable | Què mirar al preview |
|----------|----------------|----------------------|
| `num_readings: 0`, `stats.rows > 0`, `skipped_no_date === rows` | Columna de data mal mapada o delimitador incorrecte | `labels.reading_date_label`, files amb `reason: skipped_no_date` |
| Molts `not_found_meter` | `comm_module` no coincideix amb la BD | Files `action: not_found`; revisar `meter_comm_updates` o dades de comptador |
| Molts `skipped_existing` | Document ja importat abans | Normal en reprocessar; informar l'usuari |
| `status: failed` | Error inesperat a Celery | `GET /task-progress/{task_id}/` → `error` |
| `409` en processar | Tasca ja en curs | Esperar o mostrar `task_id` existent |

---

## Referència ràpida curl

```bash
# 1. Pujar sense processar
curl -X POST http://127.0.0.1:8000/billing/reading-document/ \
  -H "Authorization: Token <token>" \
  -F "file=@LECTURES_LECTOR_CSV.csv" \
  -F "template=2" \
  -F "auto_process=false"

# 2. Validar
curl "http://127.0.0.1:8000/billing/reading-document/12/validate/?max_rows=50" \
  -H "Authorization: Token <token>"

# 3. Confirmar
curl -X POST http://127.0.0.1:8000/billing/reading-document/12/process/ \
  -H "Authorization: Token <token>"

# 4. Corregir fitxer
curl -X PATCH http://127.0.0.1:8000/billing/reading-document/12/ \
  -H "Authorization: Token <token>" \
  -F "file=@LECTURES_corregit.csv"

# 5. Reprocessar
curl -X POST http://127.0.0.1:8000/billing/reading-document/12/reprocess/ \
  -H "Authorization: Token <token>"
```

---

## Fitxers backend de referència

| Fitxer | Contingut |
|--------|-----------|
| `billing/views/reading_document_view.py` | ViewSet i accions `validate`/`process`/`reprocess` |
| `billing/serializers/reading_document_serializer.py` | Serialització i camp `auto_process` |
| `billing/utils/reading_document_import_service.py` | Lògica de preview (`build_reading_document_preview`) |
| `billing/tasks.py` | Processament real (`process_reading_document_file`) |
| `billing/models.py` | Models `ReadingDocument`, `ReadingDocumentNotFound` |
| `statistics/models.py` | `ReadingBatchImportTemplate`, `ReadingBatchImportColumn` |
