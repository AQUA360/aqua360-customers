# Integració Odoo (outbound)

Integració outbound del Programa d'Abonats amb **Odoo 19 Community** (ERP Comptabilitat).

**Estat:** Fase 1 — mappers, client HTTP i comandes de prova.

## Documentació

| Document | Ubicació |
|----------|----------|
| Contracte de dades | [`docs/integrations/odoo/data-contract.md`](../../../docs/integrations/odoo/data-contract.md) |
| Pla d'implementació | [`docs/integrations/odoo/plan.md`](../../../docs/integrations/odoo/plan.md) |

## Estructura

```
integrations/outbound/odoo/
├── client.py           # HTTP POST + IntegrationRequestLog
├── services.py         # push_invoice(), push_payment_movement()
├── mappers.py          # PA → JSON Odoo
├── exceptions.py
├── tests.py
└── fixtures/
```

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
ODOO_BASE_URL=
ODOO_API_KEY=
ODOO_TIMEOUT=30
ODOO_PUSH_ENABLED=False
ODOO_PUSH_INVOICES=True
ODOO_PUSH_PAYMENTS=True
```

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
```

`--output-dir` implica `--dry-run`: genera un fitxer JSON per document i un `manifest.json` amb l'índex.

Des de codi:

```python
from integrations.outbound.odoo.services import push_invoice, push_payment_movement

push_invoice(invoice_id=123)
push_payment_movement(movement_id=456)
```

## Tests

```bash
python manage.py test integrations.outbound.odoo.tests
```
