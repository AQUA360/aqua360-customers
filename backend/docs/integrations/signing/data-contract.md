# Contracte de dades — Aqua360 Sign

Integració **outbound + inbound** amb [Aqua360 Sign](https://sign.aqua360.cloud) per enviar un PDF a signar (OTP) i recuperar el PDF segellat.

**Codi:**

| Direcció | Ubicació |
|----------|----------|
| Outbound (el PA crida Sign) | `integrations/outbound/signing/` |
| Inbound (Sign crida el PA) | `integrations/inbound/signing/` |

El PDF **no** viatja dins del webhook. Sign només notifica l'esdeveniment; el PA es baixa el fitxer amb `GET /api/sessions/<session_id>/documents/<document_id>/signed/`.

---

## Flux

1. El PA genera (o reutilitza) el PDF i fa `POST /api/sessions/` amb `X-API-Key`.
2. Sign envia al signant l'enllaç i, en verificar l'OTP, estampa la marca SES.
3. Sign fa `POST` a `callback_url` (`session.signed`).
4. El PA es baixa el PDF i el desa. Si el webhook no arriba, el sondeig (`poll_signing_sessions`) fa la mateixa feina només amb trànsit de sortida.

Hi ha dos orígens al PA. Els dos acaben a la mateixa API de Sign:

| Origen | `external_reference` | On queda el PDF firmat |
|--------|----------------------|------------------------|
| Sol·licitud (`ContractRequest`) | `ContractRequest.token`, o l'id numèric si no té token | `ContractRequest.contract_file`. Si ja existeix el `Contract` vinculat, també `Contract.contract_file` |
| Document per firmar (`DocumentSign`) | `docsign-<id>` | `DocumentSign.contract_file_signed` |

`docsign-` evita que l'id d'un `DocumentSign` coincideixi amb l'id d'una `ContractRequest`.

---

## Configuració (`.env`)

```env
SIGNING_BASE_URL=https://sign.aqua360.cloud
SIGNING_API_KEY=
SIGNING_CALLBACK_URL=https://customers.aqua360.cloud/signing/callback/
SIGNING_TIMEOUT=30
SIGN_CALLBACK_API_KEY=

# Només si Sign no pot arribar al webhook (IP privada) o com a xarxa de seguretat
SIGNING_POLL_ENABLED=False
SIGNING_POLL_MINUTES=10
```

| Variable | Ús |
|----------|----|
| `SIGNING_BASE_URL` | Host de Sign, sense barra final. El client hi afegeix `/api/sessions/`. |
| `SIGNING_API_KEY` | Clau del Client a Sign. Capçalera outbound `X-API-Key`. Ha de coincidir amb la del tenant a l'admin de Sign. |
| `SIGNING_CALLBACK_URL` | URL que el PA envia com a `callback_url` si la petició no en porta una. Ha de ser accessible **des de Sign**. |
| `SIGN_CALLBACK_API_KEY` | Si té valor, el webhook inbound exigeix la mateixa clau a `X-API-Key` (també accepta `Aqua360-Api-Key`). Si és buit, el webhook no valida la clau. A Sign és el `callback_api_key` del Client. |
| `SIGNING_POLL_ENABLED` | Programa `poll_signing_sessions` al Celery beat. |
| `SIGNING_POLL_MINUTES` | Cada quants minuts (per defecte 10). |

A més, `ConfigProject` `DOCUMENT_SIGN_ENABLED` ha de valer `true`. Sense això, ni l'API ni les comandes d'enviament arriben a Sign.

`SIGNING_CALLBACK_URL` depèn de `API_URL_PREFIX`:

| `API_URL_PREFIX` | Webhook |
|------------------|---------|
| `False` | `POST /signing/callback/` |
| `True` | `POST /api/signing/callback/` |

---

## Outbound — crear sessió

```
POST {SIGNING_BASE_URL}/api/sessions/
Content-Type: multipart/form-data
X-API-Key: <SIGNING_API_KEY>
```

| Camp | Obligatori | Origen al PA |
|------|------------|--------------|
| `recipient_name` | Sí | Titular, o `otp_name` al `DocumentSign` |
| `recipient_email` | Sí | Contacte per defecte, o `otp_email` |
| `recipient_phone` | No (recomanat: és el telèfon de l'OTP) | Contacte, o `otp_phone` |
| `external_reference` | Sí, el PA sempre l'envia | Token de la sol·licitud, o `docsign-<id>` |
| `callback_url` | Sí | `SIGNING_CALLBACK_URL` si no es passa una altra |
| `documents` | Sí | PDF del contracte o de la sol·licitud |
| `document_metadata` | No | JSON: `title`, `external_document_id`, `sort_order` |

Resposta `201`:

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "pending",
  "signing_url": "https://sign.aqua360.cloud/s/AbCd…/",
  "expires_at": "2026-07-02T12:00:00+02:00",
  "email_sent": true
}
```

`signing_url` només es retorna en crear la sessió. `email_sent: false` vol dir que Sign ha creat la sessió però no ha pogut enviar el correu.

Consulta i descàrrega (les fa el webhook, el sondeig i `retrieve`; no cal cridar-les a mà):

| Mètode | Ruta |
|--------|------|
| `GET` | `/api/sessions/<session_id>/` |
| `GET` | `/api/sessions/<session_id>/documents/<document_id>/signed/` |

Un `403` és clau rebutjada. Un `404` en consultar una sessió d'un altre client també és el comportament de Sign (no filtra l'existència).

### Punts d'entrada al PA

| Camí | Què fa |
|------|--------|
| `POST /contract/contract-request/{id}/send-for-signing/` | Envia la sol·licitud. Cos opcional: `recipient_name`, `recipient_email`, `recipient_phone`, `callback_url`, `force` |
| `POST /documentmanager/document-sign/` | Crea el `DocumentSign` en estat Pending (`1`). No parla amb Sign |
| `POST /documentmanager/document-sign/{id}/send/` | Envia el PDF. Cos opcional: `callback_url`, `force`. Estat `2` (Sended) |
| `POST /documentmanager/document-sign/{id}/retrieve/` | Consulta Sign. Si ja està firmat, desa el PDF i passa a Signed (`3`). Només JSON |
| `GET /documentmanager/document-sign-download/{id}/` | Serveix el PDF firmat només si l'estat és Signed (`3`) |
| `DELETE /documentmanager/document-sign/{id}/` | Esborra el registre local (`204`) |

`force` torna a enviar encara que el `DocumentSign` ja estigui firmat (o la sol·licitud ja tingui `contract_file`). Un reenviament correcte desvincula el PDF firmat anterior: encara no n'hi ha un de la sessió nova.

`retrieve` no retorna el binari. Si Sign encara no el dóna per firmat, la resposta és `200` amb el `DocumentSign` tal com està (`2` o `4`). Si Sign el dóna per caducat, l'estat passa a `4`. Si Sign falla, l'estat passa a `-1`, s'omple `error_report` i la resposta és `502`.

`document-sign-download` no serveix mai el PDF original. `contract_file_signed_url` al JSON només ve informat quan l'estat és `3`, i apunta a aquest mateix endpoint (cal `Authorization`).

Aqua360 Sign no documenta cap cancel·lació de sessió. El `DELETE` només esborra el registre al PA; l'enllaç OTP pot seguir viu a Sign fins que caduqui. Un callback posterior d'aquella referència respon `404`.

En finalitzar l'alta, el `DocumentSign` de la sol·licitud es vincula també al `Contract` (es conserva `contract_request`). El llistat `document-signs-by-contract/?contract_id=` el troba.

---

## Inbound — webhook

```
POST /signing/callback/
Content-Type: application/json
X-API-Key: <SIGN_CALLBACK_API_KEY>    # només si està configurada
User-Agent: Aqua360-Sign/1.0
```

```json
{
  "event": "session.signed",
  "external_reference": "CTR-2026-001",
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "signed",
  "signed_at": "2026-06-25T14:30:00+02:00",
  "recipient_name": "Anna Garcia",
  "recipient_email": "anna@example.com",
  "document_count": 1,
  "documents": [
    {
      "id": 1,
      "title": "Contracte subministrament",
      "external_document_id": "42",
      "signed": true,
      "signed_at": "2026-06-25T14:30:00+02:00",
      "has_stamped_file": true
    }
  ]
}
```

| Camp | Notes |
|------|-------|
| `event` | `session.signed` (el que envia Sign) o `session.expired` |
| `external_reference` | Token o id de la sol·licitud, o `docsign-<id>` |
| `session_id` | Idempotència: si la `ContractSigningSession` ja és `signed`, la resposta és `already_processed: true` |
| `documents[].id` | Cal per descarregar el PDF. Sense un document amb `signed: true` i `id`, el `DocumentSign` no es marca com a firmat |

| Codi | Motiu |
|------|-------|
| `403` | `SIGN_CALLBACK_API_KEY` configurada i la capçalera no coincideix |
| `400` | Esdeveniment no suportat, falta `external_reference`, o no s'ha pogut baixar el PDF d'un `DocumentSign` |
| `404` | Ni sol·licitud ni `DocumentSign` amb aquesta referència |
| `200` | `{"ok": true}` |

Les crides (inbound i outbound) queden a `IntegrationRequestLog` amb provider `signing`. El sondeig periòdic no registra les consultes que van bé, només els errors.

---

## Sondeig

Quan Sign no pot arribar al backend (el host resol a una IP privada, o el `POST` es perd), el webhook no escriu el PDF. La comanda fa la mateixa feina en sentit contrari:

```bash
python manage.py poll_signing_sessions
python manage.py poll_signing_sessions --dry-run
python manage.py poll_signing_sessions --document-sign 12
python manage.py poll_signing_sessions --session 550e8400-e29b-41d4-a716-446655440000
```

Recorre els `DocumentSign` en estat `SENDED` i les `ContractSigningSession` en estat `pending`. Si Sign les dóna per firmades, baixa el PDF i el desa amb les mateixes funcions que el callback. Si les dóna per caducades, les marca `expired`. El que ja està firmat no es reprocessa.

Amb `SIGNING_POLL_ENABLED=True` ho fa el beat cada `SIGNING_POLL_MINUTES`.

---

## Comprovar la connexió

No hi ha cap endpoint de health a Sign. La comprovació és un `GET` d'una sessió que no existeix (`00000000-0000-0000-0000-000000000000`):

| Resposta | Vol dir |
|----------|---------|
| `404` JSON (`{"detail": "Not found."}`) | Sign respon i **ha acceptat** la clau |
| `403` | La clau no és vàlida o el client està inactiu |
| HTML, timeout o error de connexió | No s'ha arribat a l'API (URL, DNS, tallafoc o proxy) |

No crea cap sessió, no envia cap correu i no toca cap contracte.

```bash
python manage.py check_signing_connection
```

Des del contenidor de l'aplicació, amb el mateix `.env` que el procés web. Mostra la URL, la clau emmascarada, si el webhook i el sondeig estan configurats, i si `DOCUMENT_SIGN_ENABLED` és cert.

El mateix probe, sense la comanda (servidor que encara no té el deploy):

```bash
curl -sS -D - -o /tmp/sign-probe.json \
  -H "Accept: application/json" \
  -H "X-API-Key: ${SIGNING_API_KEY}" \
  "${SIGNING_BASE_URL%/}/api/sessions/00000000-0000-0000-0000-000000000000/"
```

Cal un `HTTP/1.1 404` i un cos JSON. Un `404` en HTML és un altre servidor.

Això només prova el camí **de sortida**. Que Sign pugui fer el `POST` de tornada depèn que `SIGNING_CALLBACK_URL` sigui accessible des d'Internet. Si no ho és, activa `SIGNING_POLL_ENABLED`.

### Enviar un document de debò

Això sí que crea una sessió i envia el correu al signant:

```bash
python manage.py send_contract_request_for_signing --contract-request-id 55
python manage.py send_contract_request_for_signing --contract-request-id 780 \
  --recipient-email signant@example.com
```

| Opció | Descripció |
|-------|------------|
| `--contract-request-id` | ID de la sol·licitud (obligatori) |
| `--recipient-name` / `--recipient-email` / `--recipient-phone` | Dades del signant; si no es passen, surten del titular i del contacte |
| `--callback-url` | Per defecte `SIGNING_CALLBACK_URL` |
| `--force` | Torna a enviar encara que ja hi hagi `contract_file` |

---

## Tests

```bash
python manage.py test integrations.outbound.signing.tests integrations.inbound.signing.tests \
  --settings=customers.settings_test
```
