# Signatura OTP — endpoints backend

Prefix: `/documentmanager/`  
Auth: token DRF (`IsAuthenticated`), com la resta de l’API.

Contracte **confirmat amb backend**. El flux tal com el crida el front: [frontend-flow.md](./frontend-flow.md).

El front opera sobre l’últim `DocumentSign` d’un contracte o d’una sol·licitud d’alta:

1. Crear la petició (nom / email / telèfon del signant + PDF del contracte)
2. Enviar-la al servei OTP (Aqua360)
3. **Sol·licitar** si ja està signat (`POST …/retrieve/`: consulta Aqua360, sense binari)
4. Si ho està, **descarregar** el PDF signat
5. **Reiniciar**: `DELETE` del registre local (l’enllaç OTP a Aqua360 pot seguir viu fins que caduqui)

El webhook d’Aqua360 fa la mateixa feina que `retrieve` quan el signant acaba; el front no en depèn.

---

## Estats (`DocumentSign.status`)

Coincideixen amb `utils/document-sign.ts`:

| Codi | Significat | Què pot fer l’usuari |
|------|------------|----------------------|
| `1` | Pending | Enviar |
| `2` | Sended | Sol·licitar document signat / Reiniciar |
| `3` | Signed | Descarregar / Reiniciar |
| `4` | Expired | Sol·licitar (per si Aqua360 el té) / Reiniciar |
| `-1` | Error | Reenviar (`force`) / Reiniciar |

`status_display` (etiquetes Django) arriba en anglès; el front tradueix pel **codi numèric**.

---

## Objecte `DocumentSign` (resposta JSON)

```json
{
  "id": 123,
  "status": 2,
  "otp_name": "Nom Cognom",
  "otp_email": "info@...",
  "otp_phone": "679...",
  "contract": 456,
  "contract_request": 789,
  "contract_token": "260929006",
  "contract_request_token": null,
  "contract_file": 111,
  "contract_file_url": "https://.../original.pdf",
  "contract_file_signed_url": null,
  "signed_at": null,
  "created_at": "2026-09-30T10:00:00Z",
  "error_report": null
}
```

Regles:

- `contract` **o** `contract_request` a l’alta. En **finalitzar l’alta**, el `DocumentSign` de la sol·licitud es vincula al contracte i **es conserva** `contract_request`. El llistat per `contract_id` el troba.
- `contract_file_url`: PDF original. Mai s’ofereix com a document signat.
- `contract_file_signed_url`: **només informat amb `status = 3`**. Apunta a la mateixa descàrrega que `document-sign-download`; cal header `Authorization`.
- `error_report`: text lliure si `status = -1`.

---

## Endpoints

#### `GET /documentmanager/document-sign/{id}/`

Detall d’un `DocumentSign`.

#### `POST /documentmanager/document-sign/`

Crea el registre. Body:

```json
{
  "contract": 456,
  "contract_request": null,
  "contract_file": 111,
  "otp_name": "...",
  "otp_email": "...",
  "otp_phone": "..."
}
```

Alta sense contracte: `contract_request` i no `contract`. Estat inicial: `1` (Pending).

#### `PUT /documentmanager/document-sign/{id}/`

Update estàndard.

#### `GET /documentmanager/document-signs-by-contract/?contract_id={id}`

```json
{ "document_signs": [ /* ... */ ] }
```

#### `GET /documentmanager/document-signs-by-contract/?contract_request_id={id}`

El mateix, filtrat per sol·licitud.

#### `GET /documentmanager/document-signs-all/?status={codi}`

Llistat global. `status` opcional. Inclou `contract`, `contract_request`, `contract_token`, `contract_request_token`.

#### `POST /documentmanager/document-sign/{id}/send/`

Envia el PDF a Aqua360.

Body:

```json
{
  "force": false,
  "callback_url": null
}
```

- `force: false`: primer enviament (Pending → Sended).
- `force: true`: reenviament.

Un **reenviament correcte desvincula el PDF signat** de la sessió anterior: no queda descarregable fins que la nova signatura es tanqui (`status = 3` de nou).

Si Aqua360 falla: `status = -1` + `error_report`.

#### `POST /documentmanager/document-sign/{id}/retrieve/`

Botó **«Sol·licitar document signat»**. Consulta Aqua360 i **no retorna cap binari**, només JSON del `DocumentSign`.

| Cas | HTTP | Efecte |
|-----|------|--------|
| Ja signat | **200** | Desa el PDF, `status = 3`, omple `contract_file_signed_url` i `signed_at` |
| Encara no | **200** | Es queda amb l’estat que ja tenia (`2` o `4`). El front mira `status === 3` |
| Aqua360 el dóna per caducat | **200** | `status = 4` |
| Aqua360 falla | **502** | `status = -1`, `error_report` |

#### `GET /documentmanager/document-sign-download/{id}/`

PDF signat, només si `status = 3`. Auth: `Authorization: Token …`.  
Si no està signat → **404**. Mai el PDF original.

`contract_file_signed_url` apunta a aquesta mateixa descàrrega.

#### `DELETE /documentmanager/document-sign/{id}/`

Botó **Reiniciar**. Esborra el registre local **en qualsevol estat, inclòs 3**. HTTP **204**.

Aqua360 Sign **no documenta cancel·lar la sessió**: l’enllaç OTP pot seguir viu fins que caduqui. Un callback posterior d’aquella referència respondrà **404**.

---

## Resum

| Acció UI | Mètode | Endpoint | Èxit |
|----------|--------|----------|------|
| Crear + Enviar | `POST` + `POST` | `document-sign/` → `document-sign/{id}/send/` | `status = 2` |
| Reenviar | `POST` | `document-sign/{id}/send/` `{ "force": true }` | `status = 2`; es desvincula el PDF signat anterior |
| Sol·licitar document signat | `POST` | `document-sign/{id}/retrieve/` | `status = 3` si Aqua360 ja el té; si no, `2`/`4`; Aqua360 ko → `502` |
| Descarregar | `GET` | `document-sign-download/{id}/` | PDF, només si `status = 3` |
| Reiniciar | `DELETE` | `document-sign/{id}/` | 204 local; l’enllaç OTP pot caducar sol |
| Pintar (contracte) | `GET` | `document-signs-by-contract/?contract_id=` | `{ document_signs: [] }` |
| Pintar (sol·licitud) | `GET` | `document-signs-by-contract/?contract_request_id=` | igual |
| Llistat global | `GET` | `document-signs-all/?status=` | igual |
