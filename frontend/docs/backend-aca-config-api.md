# Requeriments frontend — Configuració ACA

Document de requeriments per integrar des del frontend la configuració ACA i l'ompliment del camp `Contract.use_aca`.

> **Base URL**: `/` o `/api/` segons `API_URL_PREFIX` del backend.
>
> Totes les crides requereixen autenticació: `Authorization: Bearer <token>`.

---

## Flux recomanat

1. L'usuari edita els `ConfigProject` relacionats amb ACA al formulari.
2. El frontend desa els valors amb **bulk update**.
3. El frontend consulta **quants contractes pendents** tenen `use_aca` null/buit.
4. Si n'hi ha, l'usuari pot:
   - fer un **dry-run** (previsualització sense guardar), o
   - executar l'**ompliment real** en segon pla.
5. Després de l'execució real, tornar a consultar les estadístiques per verificar que `pending_use_aca` ha baixat.

---

## 1. Desar configuració ACA (`ConfigProject`)

### `POST /coredata/config-project/bulk-update-values/`

Actualitza en bloc el `value` de diversos `ConfigProject`.

**Permís**: usuari autenticat (`IsAuthenticated`).

**Request body** — array directe (no cal wrapper):

```json
[
  {"token": "uses_aca", "value": true},
  {"token": "aca_cs_token", "value": "ACA-CANON"},
  {"token": "token_product_aca", "value": "1002"},
  {"token": "token_price_rate_aca_dom", "value": "CANON-DOM"},
  {"token": "contract_use_aca_mun_tokens", "value": "CANON-MUN"},
  {"token": "contract_use_aca_ind_tokens", "value": "CANON-IND"},
  {"token": "contract_use_aca_dom_tokens", "value": "CANON-DOM"},
  {"token": "contract_use_aca_gan_tokens", "value": "CANON-AGRICOLA-0"},
  {"token": "contract_use_aca_dir_variable_token", "value": "factura-aca"}
]
```

**Notes**:
- `value` accepta `string`, `number`, `boolean` o `null`.
- Els booleans es normalitzen a string (`true` → `"True"`, `false` → `"False"`).
- Només s'actualitza el camp `value`; el `token` identifica el registre.

**Response 200**:

```json
{
  "updated": [
    {
      "token": "uses_aca",
      "name": "Bool fa servir use_aca",
      "value": "True",
      "file": null
    }
  ],
  "errors": []
}
```

**Response 400** (cap actualització vàlida):

```json
{
  "updated": [],
  "errors": [
    {"token": "token_inexistent", "detail": "ConfigProject no trobat."}
  ]
}
```

**Response parcial 200** (alguns ok, altres error):

```json
{
  "updated": [ ... ],
  "errors": [
    {"token": "token_inexistent", "detail": "ConfigProject no trobat."}
  ]
}
```

### Endpoints auxiliars (ja existents)

| Mètode | URL | Ús |
|--------|-----|-----|
| `GET` | `/coredata/config-project/` | Llistar totes les configs |
| `GET` | `/coredata/config-project/{token}/` | Obtenir una config |
| `GET` | `/coredata/config-project/{token}/value/` | Només el `value` |
| `PATCH` | `/coredata/config-project/{token}/` | Actualitzar un sol registre |

---

## 2. Consultar contractes pendents de `use_aca`

### `GET /contract/contract-use-aca/`

Retorna estadístiques dels contractes actius respecte al camp `use_aca`.

**Permís**: `contract.view_contract`

**Response 200**:

```json
{
  "uses_aca_enabled": true,
  "active_contracts": 1250,
  "pending_use_aca": 87,
  "filled_use_aca": 1163
}
```

| Camp | Descripció |
|------|------------|
| `uses_aca_enabled` | `true` si `ConfigProject.uses_aca` està activat |
| `active_contracts` | Total contractes actius |
| `pending_use_aca` | Contractes actius amb `use_aca` **null o buit** (`""`) |
| `filled_use_aca` | Contractes actius amb `use_aca` informat |

**Response 403**: usuari sense permís de lectura de contractes.

### Ús al frontend

- Mostrar un avís/comptador del tipus: *"87 contractes sense use_aca"*.
- Si `uses_aca_enabled === false`, desactivar o amagar l'acció d'omplir.
- Si `pending_use_aca === 0`, no cal oferir l'ompliment (o mostrar missatge informatiu).

---

## 3. Executar ompliment de `use_aca`

### `POST /contract/contract-use-aca/`

Executa la lògica de `fill_contract_use_aca` (script backend que omple `Contract.use_aca` segons tarifes CANON i configuració ACA).

**Permís**: `contract.change_contract`

### Opció A — Dry-run (previsualització, síncron)

```json
{
  "dry_run": true
}
```

**Response 200**:

```json
{
  "skipped": false,
  "reason": null,
  "dry_run": true,
  "update_all_contracts": false,
  "total_contracts": 87,
  "updated_count": 42,
  "skipped_count": 45,
  "error_count": 0,
  "skipped_reasons": {
    "no_canon_price_rate": 10,
    "token_no_match": 5,
    "already_correct": 0,
    "no_price_rates": 30
  },
  "skipped_examples": {
    "no_canon_price_rate": ["CT-001", "CT-002"],
    "token_no_match": ["CT-010 (token: CANON-XYZ)"],
    "already_correct": [],
    "no_price_rates": ["CT-100", "CT-101"]
  }
}
```

| Camp | Descripció |
|------|------------|
| `skipped` | `true` si no s'ha executat (p.ex. `uses_aca` desactivat) |
| `reason` | Motiu si `skipped=true` (p.ex. `"uses_aca_disabled"`) |
| `total_contracts` | Contractes processats |
| `updated_count` | Contractes que s'actualitzarien (o s'han actualitzat si no és dry-run) |
| `skipped_count` | Suma de tots els motius de salt |
| `skipped_reasons` | Desglossament per motiu |
| `skipped_examples` | Fins a 5 exemples per motiu (tokens de contracte) |

### Opció B — Execució real (async, per defecte)

```json
{}
```

o explícitament:

```json
{
  "async": true
}
```

**Response 202**:

```json
{
  "status": "pending",
  "task_id": "abc-123-def-456",
  "message": "Ompliment de use_aca iniciat en segon pla. Utilitza el task_id per comprovar l'estat."
}
```

### Opció C — Execució real síncrona (només si cal)

```json
{
  "async": false
}
```

Retorna el mateix objecte de resultat que el dry-run, però amb `dry_run: false` i canvis reals a BD. **No recomanat** si hi ha molts contractes.

### Paràmetre opcional

```json
{
  "update_all_contracts": true
}
```

- Per defecte `false`: només processa contractes actius amb `use_aca` null/buit.
- Si `true`: reprocessa **tots** els contractes actius.

### Seguiment de tasca async

```http
GET /task-progress/{task_id}/
```

**Response SUCCESS** (exemple):

```json
{
  "state": "SUCCESS",
  "percent": 100,
  "current": 1,
  "total": 1,
  "result": {
    "skipped": false,
    "dry_run": false,
    "total_contracts": 87,
    "updated_count": 42,
    "skipped_count": 45,
    "error_count": 0,
    "skipped_reasons": { ... },
    "skipped_examples": { ... }
  }
}
```

---

## 4. UI / UX suggerida

### Pantalla configuració ACA

- Formulari amb els tokens ACA rellevants.
- Botó **Desar** → `POST /coredata/config-project/bulk-update-values/`.
- Secció **Contractes use_aca**:
  - Comptador en temps real via `GET /contract/contract-use-aca/`.
  - Botó **Simular ompliment** → `POST` amb `{"dry_run": true}`; mostrar resum (`updated_count`, `skipped_reasons`).
  - Botó **Omplir use_aca** → `POST` amb `{}`; mostrar spinner i consultar `task-progress`.
  - Després de SUCCESS, refrescar comptador.

### Missatges d'error

| Situació | Acció frontend |
|----------|----------------|
| `403` | Mostrar "Sense permisos" |
| `bulk-update` amb `errors` | Mostrar quins tokens han fallat |
| `skipped: true, reason: "uses_aca_disabled"` | Informar que ACA no està activat |
| `pending_use_aca === 0` | Missatge: "Tots els contractes actius tenen use_aca informat" |

---

## 5. Tokens `ConfigProject` rellevants per ACA

| Token | Tipus habitual | Exemple |
|-------|----------------|---------|
| `uses_aca` | boolean → string | `true` / `"True"` |
| `aca_cs_token` | string | `"ACA-CANON"` |
| `token_product_aca` | string | `"1002"` |
| `token_price_rate_aca_dom` | string | `"CANON-DOM"` |
| `contract_use_aca_mun_tokens` | string | `"CANON-MUN"` |
| `contract_use_aca_ind_tokens` | string | `"CANON-IND"` |
| `contract_use_aca_dom_tokens` | string | `"CANON-DOM"` |
| `contract_use_aca_gan_tokens` | string | `"CANON-AGRICOLA-0"` |
| `contract_use_aca_dir_variable_token` | string | `"factura-aca"` |

---

## 6. Valors possibles de `Contract.use_aca`

| Codi | Significat |
|------|------------|
| `Q` | Usos ramaders sense cànon |
| `D` | Domèstics |
| `I` | Industrials |
| `A` | Municipal |
| `E` | Exempts |
| `M` | Mesures directes |

---

## 7. Checklist d'integració

- [ ] Crida bulk-update amb array directe (no objecte wrapper).
- [ ] Gestiona booleans al payload (`uses_aca: true`).
- [ ] Consulta estadístiques abans i després de l'ompliment.
- [ ] Ofereix dry-run abans de l'execució real.
- [ ] Per execució real, usa async i `task-progress`.
- [ ] Comprova permisos `contract.view_contract` i `contract.change_contract`.
- [ ] Mostra errors parcials del bulk-update si n'hi ha.
