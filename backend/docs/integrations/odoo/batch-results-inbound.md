# Batch results inbound (Aqua360)

How an external system (typically Odoo / the connector) notifies Aqua360 that a
send-batch has finished processing.

Related docs:

- Outbound bulk contract: [`batch-sending-v1.0.pdf`](batch-sending-v1.0.pdf)
- Data contract: [`data-contract.md`](data-contract.md)

---

## 1. Is it operative?

**Yes**, if all of the following are true on the Aqua360 environment:

1. The app is reachable from the caller (public URL or VPN / allowlisted IP as agreed).
2. `ODOO_INBOUND_BEARER_TOKEN` is set in Aqua360 `.env` (non-empty).
3. The `batch_id` in the body already exists in Aqua360 as a `SendBatch.token`
   (created when Aqua360 sent / prepared the lot).

If the bearer token is missing or wrong → **401**.  
If `batch_id` is unknown → **404**.

Aqua360 may also pull status with `GET` on the provider side; this inbound
endpoint is the **push** path when the provider finishes the lot.

---

## 2. What the caller needs

| Item | Value |
|------|--------|
| Method | `POST` |
| URL | `{AQUA360_BASE_URL}/odoo/v1/batch-results/` |
| Header | `Authorization: Bearer <ODOO_INBOUND_BEARER_TOKEN>` |
| Header | `Content-Type: application/json` |
| Body | Same JSON as provider `GET /aqua360/batch/{batch_id}` (see below) |

Notes:

- Share the bearer token out of band (secret). Do not put it in the JSON body.
- If Aqua360 is mounted under an `/api/` prefix in that environment, include it
  in the base URL (same rule as other Aqua360 HTTP APIs).
- Idempotent enough for retries: a newer `finished_at` updates the lot; an older
  `finished_at` is rejected as stale (`accepted: false`).

---

## 3. Request body

Minimal shape Aqua360 expects:

```json
{
  "batch_id": "FACT-202610-001",
  "type": "invoices",
  "status": "done",
  "received_at": "2026-10-21T13:04:00Z",
  "finished_at": "2026-10-21T13:08:12Z",
  "summary": {
    "total": 2,
    "ok": 1,
    "duplicate_ignored": 0,
    "error": 1,
    "pending": 0
  },
  "results": [
    {
      "aqua_id": "01000028192",
      "odoo_id": 442,
      "status": "ok",
      "message": null
    },
    {
      "aqua_id": "01000028193",
      "odoo_id": null,
      "status": "error",
      "message": "Payment mode with code 'CASH' not found"
    }
  ]
}
```

### Fields

| Field | Required | Description |
|-------|----------|-------------|
| `batch_id` | **Yes** | Must match the Aqua360 lot token (`SendBatch.token`). |
| `type` | Recommended | `invoices` \| `payments` \| `commitment_create` \| `commitment_cancel`. |
| `status` | Recommended | Provider lot status (e.g. `done`). Aqua360 stores the payload as-is; lifecycle status becomes **finalized** when the payload is treatable. |
| `received_at` | Optional | ISO-8601 datetime when the provider received the lot. |
| `finished_at` | Recommended | ISO-8601 datetime when processing finished. Used for stale-result checks. |
| `summary` | Recommended | Counts: `total`, `ok`, `duplicate_ignored`, `error`, `pending`. |
| `results` | Recommended | Per-item outcomes. Item-level `error` is fine; the callback is still accepted. |

### Per-item `results[]`

| Field | Description |
|-------|-------------|
| `aqua_id` | Aqua360 object token sent in the outbound item. |
| `odoo_id` | Provider internal id when created/updated; `null` on failure. |
| `status` | e.g. `ok`, `error`, `duplicate_ignored`. |
| `message` | Error / info text; `null` when ok. |

A payload is treated as a **final** result when it includes `results`, and/or
`finished_at`, and/or a `summary` object (or a finished-like `status`). Item
errors do **not** prevent acceptance.

---

## 4. What the caller receives

### 200 — accepted

```json
{
  "batch_id": "FACT-202610-001",
  "accepted": true,
  "status": "2",
  "finished_at": "2026-10-21T13:08:12+00:00"
}
```

`status` here is the **Aqua360** lot status token (`2` = finalized by default).

### 200 — not applied (stale)

If Aqua360 already has a newer `finished_at`:

```json
{
  "batch_id": "FACT-202610-001",
  "accepted": false,
  "reason": "stale_finished_at",
  "status": "2"
}
```

### Errors

| HTTP | Body | When |
|------|------|------|
| 401 | `{"detail": "UNAUTHORIZED"}` | Missing/wrong/empty bearer token. |
| 404 | `{"detail": "Batch not found for batch_id '…'."}` | Unknown `batch_id`. |
| 400 | `{"detail": "…"}` | Invalid body (e.g. missing `batch_id`) or unexpected error. |

---

## 5. What Aqua360 does with a successful callback

1. Stores the full JSON on the lot (`final_response`).
2. Updates `summary`, `received_at`, `finished_at` when present.
3. Moves the lot lifecycle to **finalized** (ConfigProject
   `send_batch_status_finalized_token`, default `2`).
4. Writes an `IntegrationRequestLog` (provider `odoo`, direction inbound).

UI: operators see the lot as finalized, with per-item errors available for
inspection / selective resend. Resend creates a **new** lot linked via
`related_batch`; it does not mutate the original `batch_id`.

---

## 6. Example curl

```bash
curl -X POST "https://<aqua360-host>/odoo/v1/batch-results/" \
  -H "Authorization: Bearer ${ODOO_INBOUND_BEARER_TOKEN}" \
  -H "Content-Type: application/json" \
  -d @batch-result.json
```

---

## 7. Checklist for the external team

- [ ] Receive the shared `ODOO_INBOUND_BEARER_TOKEN` and the Aqua360 base URL.
- [ ] After finishing a lot, `POST` the same document you would return on
      `GET /aqua360/batch/{batch_id}`.
- [ ] Send header `Authorization: Bearer <token>`.
- [ ] Always send the original `batch_id` Aqua360 used when posting the lot.
- [ ] Include `results` / `summary` / `finished_at` so Aqua360 can finalize.
- [ ] Retry on network failure; respect `accepted: false` + `stale_finished_at`.
- [ ] Do not wait for a special “success-only” payload — item errors are expected
      and still finalize the lot.
