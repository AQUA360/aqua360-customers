# Integració Odoo (outbound)

Integració outbound del Programa d'Abonats amb **Odoo 19 Community** (ERP Comptabilitat).

**Estat:** Lots bulk (fins a 1000) + inbound de resultat final.

## Documentació

| Document | Ubicació |
|----------|----------|
| Contracte de dades | [`docs/integrations/odoo/data-contract.md`](../../../docs/integrations/odoo/data-contract.md) |
| Contracte de dades (castellà) | [`docs/integrations/odoo/data-contract.es.md`](../../../docs/integrations/odoo/data-contract.es.md) |
| OpenAPI | [`docs/integrations/odoo/openapi.yaml`](../../../docs/integrations/odoo/openapi.yaml) |
| Pla d'implementació | [`docs/integrations/odoo/plan.md`](../../../docs/integrations/odoo/plan.md) |
| Perfil Enterprise SaaS (JSON-2) | [`docs/integrations/odoo/perfil-saas.es.md`](../../../docs/integrations/odoo/perfil-saas.es.md) |

## Estructura

```
integrations/outbound/odoo/
├── client.py           # HTTP POST individual + batch + IntegrationRequestLog
├── services.py         # push_invoice(), push_*_batch()
├── batch_utils.py      # batch_id, chunks ≤1000
├── mappers.py          # PA → JSON Odoo
├── exceptions.py
├── tests.py
└── fixtures/

integrations/inbound/odoo/
├── views.py            # POST /odoo/v1/batch-results/ (Bearer)
└── services.py         # Desa final_response a SendBatch
```

## Lots

Cos: `{ "batch_id": "<token>", "items": [ <mateix JSON individual>, ... ] }`.

Resposta immediata `202` (acceptat) o `200` (ja rebut). El resultat final arriba a
`POST /odoo/v1/batch-results/` (Authorization: Bearer) amb el mateix JSON que
`GET /aqua360/batch/{batch_id}`.

UI: `/integrations/batches/` (visible al NavSidebar si `ConfigProject.ODOO_ENABLED=true`).
API interna: `/send-batch/batch/` (`integrations.urls_send_batch`; inbound Odoo roman a `/odoo/v1/`).
El ViewSet resol el client via `integrations.utils.send_batch_providers` (token de `SendBatchProvider`).

## Mapatge clau

| Odoo | Model PA |
|------|----------|
| `tax_ids` | `pricing.Tax.token` |
| `journal_id` (factura) | `billing.InvoiceSerie.token` |
| `payment_mode_id` | `contract.PaymentType.token` |
| `partner_id.aqua_id` | Token del contracte, o `Invoice.customer_token_final` |
| `partner_id.vat` | `Invoice.customer_token_final` |
| Pagament (v1) | `billing.PaymentMovement` (`is_positive=True`) |
| Pagament (v1.1) | Mateix JSON; `amount` negatiu si `is_positive=False`. Sense factura, `invoice_aqua_id` buit |

## Configuració (`.env`)

```env
ODOO_TRANSPORT=fastapi
ODOO_BASE_URL=
ODOO_API_KEY=
ODOO_TIMEOUT=30
ODOO_PUSH_ENABLED=False
ODOO_PUSH_INVOICES=True
ODOO_PUSH_PAYMENTS=True
ODOO_INBOUND_BEARER_TOKEN=
```

`ODOO_TRANSPORT=json2` embolcalla el mateix JSON del contracte (`x_aqua_id` + `x_aqua_json`) i l'envia a `/json/2/x_aqua_invoice/create` o `/json/2/x_aqua_payment/create`, amb `Authorization: Bearer`. Un document per crida; el lot es tanca amb la resposta síncrona. Els compromisos no s'envien. Detall: [`perfil-saas.es.md`](../../../docs/integrations/odoo/perfil-saas.es.md).

Flags `ConfigProject`:
- `ODOO_ENABLED` (`true`/`false`): mostra el menú de lots al front.
- Cicle d'estat del lot (`SendBatchStatus.token`):
  - `send_batch_status_pending_token` (`0`): creat / error d'enviament → «tornar a enviar».
  - `send_batch_status_processing_token` (`1`): enviament acceptat (HTTP 200/202).
  - `send_batch_status_finalized_token` (`2`): resposta d'estat del lot tractable
    (GET status o inbound), amb o sense errors d'ítems.

`SendBatchProvider` + `SendBatchType.endpoint` identifiquen la integració destí.
ConfigProject `send_batch_provider_odoo_token` (per defecte `odoo`) apunta al
`SendBatchProvider.token` que usen els serveis outbound Odoo.

## Ús

```bash
# Una factura (mostra JSON)
python manage.py push_invoice_to_odoo --invoice-id 123 --dry-run

# Totes les factures d'un dia → desar JSON per al proveïdor Odoo
python manage.py push_invoice_to_odoo \
  --issue-date 2026-03-25 \
  --output-dir integrations/outbound/odoo/exports/2026-03-25

# Moviments de cartera (v1: positius; v1.1: també devolucions)
python manage.py push_payment_movement_to_odoo \
  --invoice-issue-date 2026-07-25 \
  --output-dir integrations/outbound/odoo/exports/2026-07-25-payments

# Enviament real (quan Odoo estigui llest)
python manage.py push_invoice_to_odoo --invoice-id 123
python manage.py push_payment_movement_to_odoo --movement-id 456

# Lot bulk de factures (SendBatch)
python manage.py push_invoice_batch_to_odoo --billing-id 42 --dry-run
python manage.py push_invoice_batch_to_odoo --invoice-ids 10,11,12 --dry-run
python manage.py push_invoice_batch_to_odoo --billing-id 42 --no-send
python manage.py push_invoice_batch_to_odoo --billing-id 42 --invoice-ids 10,11

# Lot bulk de moviments de pagament (SendBatch)
python manage.py push_payment_movement_batch_to_odoo --movement-ids 10,11,12 --dry-run
python manage.py push_payment_movement_batch_to_odoo --billing-id 42 --dry-run
python manage.py push_payment_movement_batch_to_odoo --remittance-id 7 --no-send
python manage.py push_payment_movement_batch_to_odoo --invoice-issue-date 2026-07-25

# Lot bulk de compromisos (CommitmentDeposit → create/cancel)
python manage.py push_commitment_deposit_batch_to_odoo --commitment-ids 10,11,12 --dry-run
python manage.py push_commitment_deposit_batch_to_odoo --billing-id 42 --dry-run
python manage.py push_commitment_deposit_batch_to_odoo --contract-id 99 --no-send
python manage.py push_commitment_deposit_batch_to_odoo --commitment-ids 10 --action cancel
```

`--output-dir` implica `--dry-run`: genera un fitxer JSON per document i un `manifest.json` amb l'índex.

Des de codi:

```python
from integrations.outbound.odoo.services import (
    push_invoice,
    push_invoice_batch,
    push_payment_movement,
    push_payment_movement_batch,
    push_commitment_deposit_batch,
)

push_invoice(invoice_id=123)
push_payment_movement(movement_id=456)
push_invoice_batch([123, 124, 125], billing=billing)
push_payment_movement_batch([456, 457])
push_commitment_deposit_batch([10, 11], action="create")
push_commitment_deposit_batch([10], action="cancel")
```

## Tests

```bash
python manage.py test integrations.outbound.odoo.tests integrations.inbound.odoo.tests
```
