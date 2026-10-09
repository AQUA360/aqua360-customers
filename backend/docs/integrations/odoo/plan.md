# Pla d'implementació — Integració Odoo (outbound)

Integració **outbound** del Programa d'Abonats (PA) amb l'ERP de comptabilitat **Odoo 19 Community** via l'API FastAPI del connector `aqua360_connector`.

**Contracte de dades:** [`data-contract.md`](data-contract.md)

---

## Objectiu

Empènyer des d'Aqua360 cap a Odoo:

1. **Factures** (`out_invoice`)
2. **Rectificatives** (`out_refund`)
3. **Pagaments / moviments** (`account.payment` + conciliació amb factura)

Odoo és receptor passiu: no renumera, no fa Verifactu, no origina remeses. Aqua360 conserva la numeració (`serie_final`), Verifactu i la lògica de cobrament.

---

## Arquitectura

```
Invoice / Payment (billing)
        ↓
   mappers.py          ← transforma models PA → JSON contracte Odoo
        ↓
   services.py         ← orquestració, validació prèvia, retry
        ↓
   client.py           ← HTTP POST cap a Odoo FastAPI
        ↓
IntegrationRequestLog  ← auditoria centralitzada (provider: odoo)
        ↓
   Odoo 19 CE (aqua360_connector)
```

### Flux recomanat (v1)

| Esdeveniment al PA | Acció outbound |
|--------------------|----------------|
| Factura confirmada / emitida | `push_invoice(invoice_id)` |
| Rectificativa creada (`parent_invoice` != null) | `push_invoice(invoice_id)` amb `move_type=out_refund` |
| Pagament cobrat (`Payment.paid_at` informat) | `push_payment(payment_id)` |

La sincronització pot ser **síncrona** (signal/post_save) o **async** (Celery). Recomanació inicial: Celery amb reintents, igual que Giswater.

---

## Estructura de codi prevista

```
integrations/outbound/odoo/
├── README.md           # Resum operatiu (enllaça docs/integrations/odoo/)
├── client.py           # Client HTTP + IntegrationRequestLog
├── services.py         # push_invoice(), push_payment(), push_pending()
├── mappers.py          # map_invoice_to_odoo(), map_payment_to_odoo()
├── exceptions.py       # OdooApiError, OdooValidationError
├── tasks.py            # Tasques Celery
├── tests.py            # Tests unitaris (mappers + client mock)
└── fixtures/
    ├── invoice_sample.json
    └── payment_movement_sample.json

integrations/management/commands/
├── push_invoice_to_odoo.py           # Prova manual d'una factura
├── push_payment_movement_to_odoo.py  # Prova manual d'un moviment de pagament
└── sync_pending_odoo.py              # Reenvia pendents fallits (futur v2)
```

Seguir la mateixa convenció que `integrations/outbound/giswater/`: el `client.py` només parla HTTP; la lògica de negoci va a `services.py`; la transformació a `mappers.py`.

---

## Configuració (`.env`)

```env
ODOO_BASE_URL=https://odoo.exemple.cat/aqua360/v1
ODOO_API_KEY=
ODOO_TIMEOUT=30

# Opcional: activar push automàtic
ODOO_PUSH_ENABLED=False
ODOO_PUSH_INVOICES=True
ODOO_PUSH_PAYMENTS=True
```

Carregar des de `customers/settings.py` amb `python-decouple`, com la resta d'integracions.

---

## Mapatge PA → JSON Odoo

### Factura (`billing.Invoice`)

| Camp Odoo | Origen PA | Notes |
|-----------|-----------|-------|
| `aqua_id` | `Invoice.token` | Clau d'idempotència; cal assegurar-se que és estable i únic |
| `move_type` | `Invoice.parent_invoice` | `out_refund` si té `parent_invoice`; sinó `out_invoice` |
| `name` | `Invoice.serie_final` | Número extern de factura |
| `reversed_aqua_id` | `Invoice.parent_invoice.token` | Només rectificatives |
| `invoice_date` | `Invoice.issue_date` | ISO `YYYY-MM-DD` |
| `invoice_date_due` | `Invoice.due_date` | |
| `partner_id.aqua_id` | Token del contracte, o `Invoice.customer_token_final` | `contract.token`, si no `contract_request.token` (mateix token que el contracte), si no `contract_termination.contract.token`. Sense contracte: `customer_token_final` |
| `partner_id.name` | `Invoice.customer_final` | |
| `partner_id.vat` | `Invoice.customer_token_final` | Sempre |
| `journal_id.aqua_id` | `Invoice.serie.token` | `billing.InvoiceSerie` — diari Odoo |
| `journal_id.name` | `Invoice.serie.name` | |
| `payment_mode_id.id` | `Invoice.payment_type_token_final` | `contract.PaymentType.token` |
| `payment_mode_id.name` | `Invoice.payment_type_final` | `contract.PaymentType.name` |
| `amount_untaxed` | `Invoice.subtotal_final` | |
| `amount_tax` | `subtotal_final` + `total_final` | `total_final - subtotal_final` |
| `amount_total` | `Invoice.total_final` | |

### Línia de factura (`billing.InvoiceLineItem`)

| Camp Odoo | Origen PA | Notes |
|-----------|-----------|-------|
| `product_id.aqua_id` | `Product.token` | Via `line_item.product` |
| `product_id.name` | `product_name` o `Product.name` | |
| `name` | `name` / `description` | Descripció visible a Odoo |
| `quantity` | `units` | |
| `price_unit` | `price_unit` | |
| `discount` | *0.0* v1 | Si hi ha descomptes via `AppliedAdjustment`, valorar v2 |
| `tax_ids[]` | `pricing.Tax.token` | Via `line_item.tax`; ha de preexistir a Odoo |
| `price_subtotal` | `price` | Base imposable |
| `price_tax` | `tax_price` | |
| `price_total` | `total` | |

### Moviment de pagament (`billing.PaymentMovement`)

És l'**origen real** del push de pagaments a Odoo (no `Payment` directament). Només s'envien moviments amb `is_positive=True` i factura associada.

| Camp Odoo | Origen PA | Notes |
|-----------|-----------|-------|
| `aqua_id` | `PaymentMovement.token` | Identificador estable del moviment |
| `payment_type` | `"inbound"` | Fix v1 |
| `partner_id` | Factura associada | `payoff_invoice` o `payment.invoice` → mateix mapatge partner |
| `amount` | `Payment.amount` | Valor absolut positiu |
| `date` | `PaymentMovement.movement_date` | |
| `memo` | Construït | `"Cobrament rebut {serie_final} - remesa {remittance.token}"` |
| `payment_mode_id.id` | `PaymentMovement.payment_type.token` | `contract.PaymentType` |
| `payment_mode_id.name` | `PaymentMovement.payment_type.name` | |
| `journal_id.aqua_id` | `PaymentRemittance.company_bank.token` | `service.CompanyBank`; opcional |
| `journal_id.name` | `CompanyBank.bank.name` o token | |
| `reconcile.invoice_aqua_id` | `payoff_invoice.token` o `payment.invoice.token` | v1: un moviment → una factura |

### v1.1 — Devolucions i moviments sense factura

Mateix JSON que v1. S'envien també les devolucions (`is_positive=False`). Si no es declara factura, el moviment va cap a una bossa del client.

| Camp Odoo | Origen PA | Notes |
|-----------|-----------|-------|
| `payment_type` | `"inbound"` | El signe va a `amount` |
| `partner_id` | Factura, o el pagament | Sense factura: `Payment.customer_token_final` / `customer_final` |
| `amount` | `Payment.amount` | Negatiu si `is_positive=False` (devolució del pagament) |
| `memo` | Construït | Sense `serie_final` si no hi ha factura |
| `reconcile.invoice_aqua_id` | token de factura o `""` | Buit si el pagament no té factura |

---

## Taula de correspondència (configuració)

Els tokens del PA es passen directament com a codi Odoo quan coincideixen. Cal assegurar-se que Odoo té preconfigurats:

| Model PA | Camp | Exemple token PA | Codi Odoo |
|----------|------|------------------|-----------|
| `pricing.Tax` | `token` | `IVA10` | `IVA10` |
| `contract.PaymentType` | `token` | `DIRECT_DEBIT` | `SEPA-DOM` (confirmar amb Odoo) |
| `billing.InvoiceSerie` | `token` | `VENT-AGUA` | Diari de facturació |
| `service.CompanyBank` | `token` | `BANC-SABADELL` | Diari bancari |

Si els codis difereixen entre PA i Odoo, caldrà un diccionari de mapatge a `settings.py` o model d'administració.

---

## Endpoints Odoo (previstos)

> Confirmar amb l'equip del connector Odoo abans d'implementar el client.

| Mètode | Endpoint | Cos |
|--------|----------|-----|
| `POST` | `/invoices` | JSON factura / rectificativa |
| `POST` | `/payments` | JSON pagament + reconcile |

Resposta esperada: `{ "id": <odoo_id>, "aqua_id": "..." }` (confirmar schema exacte).

Autenticació: API key via capçalera (`Aqua360-Api-Key` o Bearer — confirmar).

---

## Idempotència i estat al PA

### v1 (mínim)

- Reutilitzar `IntegrationRequestLog` amb `provider=odoo`, `object_type=invoice|payment`, `object_id=<token>`.
- Si la crida té `success=True`, no reenviar llevat que sigui reintents manual.

### v2 (recomanat)

Model `OdooSyncStatus` (o camps a `Invoice` / `Payment`):

- `odoo_synced_at`
- `odoo_id`
- `odoo_last_error`

Permet acusament d'estat i reintents selectius (pendent al contracte v2).

---

## Fases d'implementació

### Fase 0 — Preparació

- [x] Documentar contracte de dades (`data-contract.md`)
- [x] Pla d'estructura i mapatge (`plan.md`)
- [x] Variables `.env.example` i `settings.py`
- [ ] Confirmar URL base, auth i schemas de resposta amb equip Odoo
- [x] Confirmar origen del NIF/CIF: `service.Company.vat` (via contracte/factura)
- [ ] Confirmar correspondència exacta tokens PA ↔ codis Odoo (PaymentType, Tax, sèries)

### Fase 1 — Esquelet + mappers

- [x] Crear `integrations/outbound/odoo/` (client, exceptions, mappers, services)
- [x] Tests unitaris dels mappers i client (mock)
- [x] Management command `push_invoice_to_odoo --invoice-id N --dry-run`
- [x] Management command `push_payment_movement_to_odoo --movement-id N --dry-run`

### Fase 2 — Client HTTP + logs

- [ ] `OdooClient` amb logging a `IntegrationRequestLog`
- [ ] `push_invoice()` i `push_payment()` a `services.py`
- [ ] Management commands de prova

### Fase 3 — Automatització

- [ ] Signals o hooks post-emissió de factura
- [ ] Hook post-cobrament de pagament
- [ ] Tasques Celery + configuració `ODOO_PUSH_ENABLED`

### Fase 4 — Operació

- [ ] Dashboard / admin per consultar logs Odoo
- [ ] Comanda de re-sync de fallits
- [ ] Documentar runbook d'errors habituals

---

## Decisions obertes

1. **Correspondència tokens PA ↔ Odoo:** `PaymentType.token` (p.ex. `DIRECT_DEBIT`) pot no coincidir amb el codi Odoo (`SEPA-DOM`). Cal taula de mapatge o alinear configuració.
2. **Rectificatives:** confirmar que `parent_invoice` és sempre el vincle correcte per `reversed_aqua_id`.
3. **Pagaments parcials / múltiples:** fora d'abast v1; caldrà v2 per remeses agrupades.
4. **Compromisos de pagament (`PaymentCommitment`):** fora d'abast v1.
5. **Moviments negatius (`is_positive=False`):** no s'envien a v1. A v1.1 s'envien amb el mateix JSON i `amount` negatiu.

---

## Tests

```bash
python manage.py test integrations.outbound.odoo.tests
```

Proves manuals:

```bash
python manage.py push_invoice_to_odoo --invoice-id 123 --dry-run
python manage.py push_invoice_to_odoo --invoice-id 123
python manage.py push_payment_movement_to_odoo --movement-id 456 --dry-run
python manage.py push_payment_movement_to_odoo --movement-id 456

# Exemples reals per al proveïdor (dry-run + desar JSON)
python manage.py push_invoice_to_odoo \
  --issue-date 2026-07-25 \
  --output-dir integrations/outbound/odoo/exports/2026-07-25

python manage.py push_payment_movement_to_odoo \
  --invoice-issue-date 2026-07-25 \
  --output-dir integrations/outbound/odoo/exports/2026-07-25-payments
```

---

## Referències

- Contracte de dades: [`data-contract.md`](data-contract.md)
- Codi (planificat): [`integrations/outbound/odoo/README.md`](../../../integrations/outbound/odoo/README.md)
- Convencions generals: [`../integrations.md`](../../integrations.md)
- Models de facturació: `billing/models.py` (`Invoice`, `InvoiceLineItem`, `Payment`, `PaymentMovement`)
