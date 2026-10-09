# Signatura OTP — flux del frontend

El widget `components/molecules/DocumentSignStatus.vue` gestiona tot el cicle de vida d’un `DocumentSign`. Sempre treballa amb **l’últim registre** del contracte o de la sol·licitud (`id` més alt).

**Servei:** `$DocumentSignApiService` (`plugins/api/documentmanager/document-sign-api.js`)  
**Estats:** `utils/document-sign.ts` (`1` Pending, `2` Sended, `3` Signed, `4` Expired, `-1` Error)

El flag `DOCUMENT_SIGN_ENABLED` (`stores/useConfigStore.ts`) ha d’estar actiu; si no, no es pinta res.

Contracte d’API (confirmat amb backend): [backend-endpoints.md](./backend-endpoints.md).

---

## On surt el widget

| Pantalla | Component pare | Notes |
|----------|----------------|-------|
| Pas de resum de l’alta | `ContractRequestSummary.vue` | Bloc «Document» |
| Fitxa de la sol·licitud (`ContractRequestRegion`) | `ContractRequestDetail.vue` | Bloc «Contracte» (`showContractSection`) |
| Pestanya Documents (contracte o sol·licitud) | `ContractDocumentsData.vue` | |
| Llistat global | `pages/contract/document-signs/index.vue` | No usa el widget; replica sol·licitar / descarregar |

Identificador enviat al widget:

- Si hi ha contracte real → `contractId`
- Si l’alta encara no n’ha creat → `contractRequestId`
- En finalitzar l’alta el backend vincula el `DocumentSign` al contracte i conserva `contract_request`; el llistat per `contract_id` el troba.

---

## Flux d’usuari i crides

```text
[cap DocumentSign]
      │  POST /documentmanager/document-sign/
      │  POST /documentmanager/document-sign/{id}/send/
      ▼
[status = 2 Sended]
      │
      ├─ Sol·licitar document signat
      │     POST /documentmanager/document-sign/{id}/retrieve/
      │     (consulta Aqua360, JSON, sense binari)
      │        ├─ 200 status = 3  →  es pot descarregar
      │        ├─ 200 status = 2 o 4  →  toast «encara no està signat»
      │        └─ 502 status = -1  →  error_report (toast de l’apiManager)
      │
      ├─ Reiniciar
      │     DELETE /documentmanager/document-sign/{id}/
      │     esborra el registre local; l’enllaç OTP pot seguir viu fins que caduqui
      │
      └─ (status = -1 Error) Reenviar
            POST /documentmanager/document-sign/{id}/send/  { "force": true }
            desvincula el PDF signat de la sessió anterior
```

El webhook d’Aqua360 fa la mateixa feina que `retrieve` quan el signant acaba; el front no en depèn. Després de cada mutació el widget refresca la llista.

---

## Endpoints que el front crida

Prefix: `/documentmanager/`. Auth: `Authorization: Token …`.

### Pintar l’estat

| Situació | Mètode | URL | Resposta esperada |
|----------|--------|-----|-------------------|
| Fitxa de contracte | `GET` | `/document-signs-by-contract/?contract_id={id}` | `{ "document_signs": [...] }` |
| Fitxa de sol·licitud (sense contracte) | `GET` | `/document-signs-by-contract/?contract_request_id={id}` | igual |
| Llistat global | `GET` | `/document-signs-all/?status={codi}` | igual (`status` opcional) |

Camps: `id`, `status`, `otp_name`, `otp_email`, `contract`, `contract_request`, `contract_token`, `contract_request_token`, `contract_file_url`, `contract_file_signed_url`, `signed_at`, `created_at`, `error_report`.

`status_display` s’ignora; l’etiqueta es tradueix pel codi numèric.

### Crear i enviar

| Acció UI | Mètode | URL | Body |
|----------|--------|-----|------|
| Enviar (formulari) | `POST` | `/document-sign/` | `{ contract \| contract_request, contract_file, otp_name, otp_email, otp_phone }` |
| | `POST` | `/document-sign/{id}/send/` | `{ "force": false }` |
| Reenviar (Error / Pending) | `POST` | `/document-sign/{id}/send/` | `{ "force": true }` o `{ "force": false }` |

Després d’enviar, `status = 2`. Un reenviament correcte desvincula el PDF signat anterior: el botó **Descarregar** desapareix fins que la nova signatura es tanqui.

### Sol·licitar el document signat

Botó visible si `status` és `2` (Sended) o `4` (Expired).

| Mètode | URL |
|--------|-----|
| `POST` | `/document-sign/{id}/retrieve/` |

No descarrega el binari. El front mira `status === 3` a la resposta / llista refresca:

1. `status === 3` → toast d’èxit i apareix **Descarregar** (`contract_file_signed_url`).
2. `status` 2 o 4 → toast «El document encara no està signat».
3. `502` → `status = -1` + `error_report`; l’apiManager ja mostra l’error.

### Descarregar

Només si `status === 3` (hi ha `contract_file_signed_url`).

| Mètode | URL |
|--------|-----|
| `GET` | `contract_file_signed_url` (mateixa descàrrega, cal `Authorization`) |
| `GET` | `/document-sign-download/{id}/` (fallback) |

`openAuthenticatedFileUrl` fa el `fetch` amb el token. **No** s’usa `contract_file_url` (PDF original).

### Reiniciar

| Mètode | URL | Èxit |
|--------|-----|------|
| `DELETE` | `/document-sign/{id}/` | 204; el widget torna a l’estat inicial |

Permès en qualsevol estat, inclòs `3`. Aqua360 no cancel·la la sessió: l’enllaç enviat al signant pot seguir actiu fins que caduqui; un callback posterior d’aquella referència serà 404. El diàleg de confirmació ho explica.

---

## Botons per estat

| `status` | Sol·licitar | Descarregar | Enviar | Reenviar | Reiniciar |
|----------|-------------|-------------|--------|----------|-----------|
| (cap registre) | — | — | formulari OTP | — | — |
| `1` Pending | — | — | sí | — | sí |
| `2` Sended | sí | — | — | — | sí |
| `3` Signed | — | sí | — | — | sí |
| `4` Expired | sí | — | — | — | sí |
| `-1` Error | — | — | — | `force: true` | sí |

---

## Fitxers clau

| Fitxer | Rol |
|--------|-----|
| `components/molecules/DocumentSignStatus.vue` | Widget |
| `plugins/api/documentmanager/document-sign-api.js` | Client HTTP |
| `utils/document-sign.ts` | Codis, etiquetes i18n, colors |
| `pages/contract/document-signs/index.vue` | Llistat |
| `stores/useConfigStore.ts` | `documentSignEnabled` |
