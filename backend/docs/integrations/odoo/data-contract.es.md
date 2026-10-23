# Contrato de datos — Interfaz Aqua360 → Odoo

Contrato de datos **push** desde Aqua360 (Aventec) hacia **Odoo 19 Community**.

Aqua360 empuja facturas, rectificativas y movimientos (pagos). Odoo actúa como receptor: no renumera, no genera Verifactu propio (vive en Aqua360) y no origina pagos ni remesas. La resolución del JSON custom se hace con OCA fastapi (`rest-framework`), con `get_or_create` por `aqua_id` en cada modelo relacionado.

**OpenAPI (para integradores):** [`openapi.yaml`](openapi.yaml) — importable en [Swagger Editor](https://editor.swagger.io), Postman o Redoc. Especificación OpenAPI 3.0, con las descripciones en castellano.

La versión de trabajo en catalán es [`data-contract.md`](data-contract.md). La estructura de los ejemplos JSON es la misma; los textos visibles están en castellano.

> **Fuente:** `Contracte_de_dades__Interfcie_Aqua360__Odoo.pdf`  
> **Especificación técnica del conector Odoo (PoC):** documento aparte, junto a Odoo (módulo `aqua360_connector`).

---

## Principios de diseño

### `aqua_id` como ancla

`aqua_id` = el ID propio de Aqua para cada objeto y relacionado. Es el ancla de idempotencia y de mapeo; el upsert busca por este campo, **nunca por `name`**.

La respuesta de la API devuelve el `id` de Odoo.

### Creación al vuelo (`get_or_create` por `aqua_id`)

- partner
- diario
- producto

Si Aqua no envía el `aqua_id` de un relacionado que hay que crear, el conector **rechaza** el documento (evita duplicados sin ancla).

### NO se crean al vuelo

Deben **preexistir** en Odoo; se resuelven por código o falla:

- impuestos (`tax_ids`)
- modos de pago (`payment_mode_id`)

Por eso llevan `id` a secas, no `aqua_id`.

### Numeración + Verifactu

Los fija Aqua360. El diario en Odoo queda marcado con numeración externa; Odoo respeta `name` tal cual y no declara por SII/Verifactu.

### Contabilidad

Aqua no sabe de ella. Odoo deriva las cuentas (contrapartida del pago, cuentas de línea) del partner y del producto. **Ninguna cuenta viaja en el JSON.**

### Totales de control

Las líneas y la cabecera llevan `amount_*` / `price_*`; Odoo recalcula y **rechaza si no cuadran**.

---

## 1 · Factura / Rectificativa

Estructura única. Lo único que varía es `move_type` (`out_invoice` / `out_refund`); la rectificativa añade `reversed_aqua_id` para enlazar con la original.

`partner_id.aqua_id` es el token del contrato (`contract.token`, o `contract_request.token`, o `contract_termination.contract.token`). Sin contrato, es `customer_token_final`. `partner_id.name` es `customer_final`. `partner_id.vat` es siempre `customer_token_final`.

### Ejemplo — factura

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
    "name": "Facturación agua"
  },
  "payment_mode_id": {
    "id": "SEPA-DOM",
    "name": "Domiciliación SEPA"
  },
  "invoice_line_ids": [
    {
      "product_id": {
        "aqua_id": "CONS-AGUA-B1",
        "name": "Consumo agua bloque 1"
      },
      "name": "Consumo agua bloque 1 (0-10 m³)",
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
        "name": "Cuota de servicio"
      },
      "name": "Cuota de servicio trimestral",
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

### Ejemplo — rectificativa

Mismo cuerpo; cambian dos campos:

```json
{
  "move_type": "out_refund",
  "reversed_aqua_id": "2026Q3-000123"
}
```

---

## 2 · Movimiento / Pago

**v1:** un solo emparejamiento pago ↔ factura.

- `journal_id` es opcional (si no viene, cae al diario por defecto del conector).
- Sin cuenta contable (Odoo deriva la contrapartida del partner).

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
  "memo": "Cobro recibido FA2026/000123 - remesa REM-2026-0007",
  "payment_mode_id": {
    "id": "SEPA-DOM",
    "name": "Domiciliación SEPA"
  },
  "journal_id": {
    "aqua_id": "BANC-SABADELL",
    "name": "Banco Sabadell"
  },
  "reconcile": {
    "invoice_aqua_id": "2026Q3-000123"
  }
}
```

### v1.1

Mismo JSON que v1. Solo cambian estos casos:

- **Devolución** (`PaymentMovement.is_positive=False`): `amount` negativo. `payment_type` sigue siendo `inbound`.
- **Sin factura:** `reconcile.invoice_aqua_id` vacío (`""`). No es un error; el movimiento va a una bolsa del cliente.

```json
{
  "amount": -27.50,
  "reconcile": {
    "invoice_aqua_id": ""
  }
}
```

---

## 3 · Mapeo a Odoo 19 CE

| JSON | Campo Odoo | Modelo | Notas |
|------|------------|--------|-------|
| `aqua_id` (cabecera) | `aqua_id` (custom) | `account.move` | Ancla de idempotencia |
| `move_type` | `move_type` | `account.move` | `out_invoice` / `out_refund` |
| `name` | `name` | `account.move` | Núm. externo; Odoo no renumera |
| `reversed_aqua_id` | — | lógica del conector | Resuelve el `account.move` original |
| `invoice_date` | `invoice_date` | `account.move` | |
| `invoice_date_due` | `invoice_date_due` | `account.move` | |
| `partner_id` | `partner_id` | `account.move` | `get_or_create` por `aqua_id` |
| `journal_id` | `journal_id` | `account.move` | `get_or_create` por `aqua_id` |
| `payment_mode_id` | `payment_mode_id` | `account.move` | OCA `account_payment_mode`; preexiste, se resuelve por `id` |
| `invoice_line_ids` | `invoice_line_ids` | `account.move` | |
| `product_id` | `product_id` | `account.move.line` | `get_or_create` por `aqua_id` |
| `name` (línea) | `name` | `account.move.line` | Descripción |
| `quantity` | `quantity` | `account.move.line` | |
| `price_unit` | `price_unit` | `account.move.line` | |
| `discount` | `discount` | `account.move.line` | Porcentaje, no importe |
| `tax_ids` | `tax_ids` | `account.move.line` | Many2many; preexiste, se resuelve por código |
| `price_subtotal` / `price_tax` / `price_total` | íd. | `account.move.line` | Control |
| `amount_untaxed` / `amount_tax` / `amount_total` | íd. | `account.move` | Control |
| `aqua_id` (pago) | `aqua_id` (custom) | `account.payment` | |
| `payment_type` | `payment_type` | `account.payment` | `inbound` |
| `partner_id` | `partner_id` | `account.payment` | |
| `amount` | `amount` | `account.payment` | Positivo en un cobro; negativo en una devolución (v1.1). El `payment_type` no cambia |
| `date` | `date` | `account.payment` | |
| `memo` | `memo` | `account.payment` | Texto libre (correcto en 19) |
| `payment_mode_id` | `payment_mode_id` | `account.payment` | OCA; preexiste |
| `journal_id` | `journal_id` | `account.payment` | Opcional → diario por defecto del conector |
| `reconcile.invoice_aqua_id` | — | lógica FastAPI | Resuelve `account.move` y concilia el apunte a cobrar |

---

## 4 · Implementación (lado Odoo)

La nota para el desarrollador (PoC con FastAPI/OCA: stack, módulo `aqua360_connector`, schemas, resolución de relacionados y conciliación) consta en un **documento propio**, separado de este contrato.

---

## 5 · Pendientes v2

| Funcionalidad | Descripción |
|---------------|-------------|
| Compromiso | Crear un compromiso y conciliar contra él |
| Conciliación múltiple | Un pago contra varias facturas (remesas agrupadas) |
| Acuse / estado de vuelta | Si Aqua360 necesita saber qué documentos ha aceptado o rechazado Odoo para reintentar |
| Devoluciones / impagados | R-transactions SEPA: deshacer la conciliación y devolver la factura a pendiente |
