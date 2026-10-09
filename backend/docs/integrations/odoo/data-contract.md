# Contracte de dades — Interfície Aqua360 → Odoo

Contracte de dades **push** des d'Aqua360 (Aventec) cap a **Odoo 19 Community**.

Aqua360 empeny factures, rectificatives i moviments (pagaments). Odoo actua com a receptor: no renumera, no genera Verifactu propi (viu a Aqua360) i no origina pagaments ni remeses. La resolució del JSON custom es fa amb OCA fastapi (`rest-framework`), amb `get_or_create` per `aqua_id` a cada model relacionat.

> **Font:** `Contracte_de_dades__Interfcie_Aqua360__Odoo.pdf`  
> **Especificació tècnica del connector Odoo (PoC):** document separat al costat d'Odoo (mòdul `aqua360_connector`).

---

## Principis de disseny

### `aqua_id` com a àncora

`aqua_id` = l'ID propi d'Aqua per a cada objecte i relacionat. És l'àncora d'idempotència i de mapatge; l'upsert fa lookup per aquest camp, **mai per `name`**.

La resposta de l'API retorna l'`id` d'Odoo.

### Creació al vol (`get_or_create` per `aqua_id`)

- partner
- diari
- producte

Si Aqua no envia `aqua_id` d'un relacionat que cal crear, el connector **rebutja** el document (evita duplicats sense àncora).

### NO es creen al vol

Han de **preexistir** a Odoo; es resolen per codi o falla:

- impostos (`tax_ids`)
- modes de pagament (`payment_mode_id`)

Per això porten `id` a seques, no `aqua_id`.

### Numeració + Verifactu

Els fixa Aqua360. El diari a Odoo queda marcat com a numeració externa; Odoo respecta `name` tal qual i no declara per SII/Verifactu.

### Comptabilitat

Aqua no en sap res. Odoo deriva els comptes (contrapartida del pagament, comptes de línia) del partner i del producte. **Cap compte viatja al JSON.**

### Totals de control

Les línies i la capçalera porten `amount_*` / `price_*`; Odoo recalcula i **rebutja si no quadren**.

---

## 1 · Factura / Rectificativa

Estructura única. L'únic que varia és `move_type` (`out_invoice` / `out_refund`); la rectificativa afegeix `reversed_aqua_id` per enllaçar amb l'original.

`partner_id.aqua_id` és el token del contracte (`contract.token`, o `contract_request.token`, o `contract_termination.contract.token`). Sense contracte, és `customer_token_final`. `partner_id.name` és `customer_final`. `partner_id.vat` és sempre `customer_token_final`.

### Exemple — factura

```json
{
  "aqua_id": "2026Q3-000123",
  "move_type": "out_invoice",
  "name": "FA2026/000123",
  "invoice_date": "2026-07-15",
  "invoice_date_due": "2026-08-15",
  "partner_id": {
    "aqua_id": "CTR-004521",
    "name": "Joan Puig Vidal",
    "vat": "ABON-004521"
  },
  "journal_id": {
    "aqua_id": "VENT-AGUA",
    "name": "Facturació aigua"
  },
  "payment_mode_id": {
    "id": "SEPA-DOM",
    "name": "Domiciliació SEPA"
  },
  "invoice_line_ids": [
    {
      "product_id": {
        "aqua_id": "CONS-AGUA-B1",
        "name": "Consum aigua bloc 1"
      },
      "name": "Consum aigua bloc 1 (0-10 m³)",
      "quantity": 10.0,
      "price_unit": 0.65,
      "discount": 0.0,
      "tax_ids": ["IVA10"],
      "price_subtotal": 6.50,
      "price_tax": 0.65,
      "price_total": 7.15
    },
    {
      "product_id": {
        "aqua_id": "CUOTA-SERV",
        "name": "Quota de servei"
      },
      "name": "Quota de servei trimestral",
      "quantity": 1.0,
      "price_unit": 18.50,
      "discount": 0.0,
      "tax_ids": ["IVA10"],
      "price_subtotal": 18.50,
      "price_tax": 1.85,
      "price_total": 20.35
    }
  ],
  "amount_untaxed": 25.00,
  "amount_tax": 2.50,
  "amount_total": 27.50
}
```

### Exemple — rectificativa

Mateix cos, canvien dos camps:

```json
{
  "move_type": "out_refund",
  "reversed_aqua_id": "2026Q3-000123"
}
```

---

## 2 · Moviment / Pagament

**v1:** un sol emparellament pagament ↔ factura.

- `journal_id` és opcional (si no ve, cau al diari per defecte del connector).
- Sense compte comptable (Odoo deriva la contrapartida del partner).

```json
{
  "aqua_id": "MOV-0007-000123",
  "payment_type": "inbound",
  "partner_id": {
    "aqua_id": "CTR-004521",
    "name": "Joan Puig Vidal",
    "vat": "ABON-004521"
  },
  "amount": 27.50,
  "date": "2026-07-20",
  "memo": "Cobrament rebut FA2026/000123 - remesa REM-2026-0007",
  "payment_mode_id": {
    "id": "SEPA-DOM",
    "name": "Domiciliació SEPA"
  },
  "journal_id": {
    "aqua_id": "BANC-SABADELL",
    "name": "Banc Sabadell"
  },
  "reconcile": {
    "invoice_aqua_id": "2026Q3-000123"
  }
}
```

### v1.1

Mateix JSON que v1. Només canvien aquests casos:

- **Devolució** (`PaymentMovement.is_positive=False`): `amount` negatiu. `payment_type` segueix sent `inbound`.
- **Sense factura:** `reconcile.invoice_aqua_id` buit (`""`). No és un error; el moviment va cap a una bossa del client.

```json
{
  "amount": -27.50,
  "reconcile": {
    "invoice_aqua_id": ""
  }
}
```

---

## 3 · Mapatge a Odoo 19 CE

| JSON | Camp Odoo | Model | Notes |
|------|-----------|-------|-------|
| `aqua_id` (capçalera) | `aqua_id` (custom) | `account.move` | Àncora idempotència |
| `move_type` | `move_type` | `account.move` | `out_invoice` / `out_refund` |
| `name` | `name` | `account.move` | Núm. extern; Odoo no renumera |
| `reversed_aqua_id` | — | lògica connector | Resol `account.move` original |
| `invoice_date` | `invoice_date` | `account.move` | |
| `invoice_date_due` | `invoice_date_due` | `account.move` | |
| `partner_id` | `partner_id` | `account.move` | `get_or_create` per `aqua_id` |
| `journal_id` | `journal_id` | `account.move` | `get_or_create` per `aqua_id` |
| `payment_mode_id` | `payment_mode_id` | `account.move` | OCA `account_payment_mode`; preexisteix, resol per `id` |
| `invoice_line_ids` | `invoice_line_ids` | `account.move` | |
| `product_id` | `product_id` | `account.move.line` | `get_or_create` per `aqua_id` |
| `name` (línia) | `name` | `account.move.line` | Descripció |
| `quantity` | `quantity` | `account.move.line` | |
| `price_unit` | `price_unit` | `account.move.line` | |
| `discount` | `discount` | `account.move.line` | Percentatge, no import |
| `tax_ids` | `tax_ids` | `account.move.line` | Many2many; preexisteix, resol per codi |
| `price_subtotal` / `price_tax` / `price_total` | íd. | `account.move.line` | Control |
| `amount_untaxed` / `amount_tax` / `amount_total` | íd. | `account.move` | Control |
| `aqua_id` (pagament) | `aqua_id` (custom) | `account.payment` | |
| `payment_type` | `payment_type` | `account.payment` | `inbound` |
| `partner_id` | `partner_id` | `account.payment` | |
| `amount` | `amount` | `account.payment` | Positiu; signe pel `payment_type` |
| `date` | `date` | `account.payment` | |
| `memo` | `memo` | `account.payment` | Text lliure (correcte a 19) |
| `payment_mode_id` | `payment_mode_id` | `account.payment` | OCA; preexisteix |
| `journal_id` | `journal_id` | `account.payment` | Opcional → default connector |
| `reconcile.invoice_aqua_id` | — | lògica FastAPI | Resol `account.move` i concilia AML receivable |

---

## 4 · Implementació (costat Odoo)

La nota per al desenvolupador (PoC amb FastAPI/OCA: stack, mòdul `aqua360_connector`, schemas, resolució de relacionats i conciliació) consta en un **document propi** separat d'aquest contracte.

---

## 5 · Pendents v2

| Funcionalitat | Descripció |
|---------------|------------|
| Compromís | Crear compromís i conciliar contra ell |
| Conciliació múltiple | Un pagament contra diverses factures (remeses agrupades) |
| Acusament / estat de tornada | Si Aqua360 necessita saber quins documents Odoo ha acceptat/rebutjat per reintentar |
| Devolucions / impagats | R-transactions SEPA: desfer conciliació i tornar la factura a pendent |
