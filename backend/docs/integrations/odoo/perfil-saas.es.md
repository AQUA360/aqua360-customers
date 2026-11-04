# Perfil Enterprise SaaS (JSON-2)

Este perfil no cambia el contrato de datos. El JSON de factura, rectificativa y pago es el de [`data-contract.es.md`](data-contract.es.md). Cambia solo el transporte: Odoo Enterprise SaaS no admite el módulo `aqua360_connector` ni FastAPI, así que Aqua360 envía ese mismo JSON dentro de `x_aqua_json`.

## Cuándo aplica

En el `.env` de la instalación:

```env
ODOO_TRANSPORT=json2
ODOO_BASE_URL=https://<instancia>.odoo.com
ODOO_API_KEY=
ODOO_TIMEOUT=30
```

`ODOO_TRANSPORT` vacío o ausente equivale a `fastapi` (conector actual: `POST /invoices` y `POST /payments`).

Autenticación en `json2`: cabecera `Authorization: Bearer <ODOO_API_KEY>`. La clave no se documenta ni se commitea.

## Llamadas

Una factura o un pago por petición (`vals_list` de un solo elemento). La rectificativa usa el mismo modelo que la factura; `move_type` (`out_invoice` / `out_refund`) va dentro del JSON.

- `POST /json/2/x_aqua_invoice/create`
- `POST /json/2/x_aqua_payment/create`

```json
{
  "vals_list": [
    {
      "x_aqua_id": "<aqua_id del contrato>",
      "x_aqua_json": {}
    }
  ]
}
```

`create` responde con la lista de ids de Odoo, por ejemplo `[42]`.

Aqua360 no llama a `res.partner`, `account.move` ni `account.payment`. No hay webhook de resultados ni `GET /batch/{id}`: cada respuesta es síncrona. Los lotes de Aqua360 siguen agrupando el trabajo en local, hacen una llamada por documento y cierran el lote con ese resultado. El `endpoint` del tipo de lote (`/batch/invoices` o `/batch/payments`) solo indica si el documento es factura o pago; la ruta HTTP es la de arriba.

Los compromisos de pago no se envían en este perfil.

## Idempotencia

`create` inserta. La acción de servidor tiene que hacer upsert por `x_aqua_id`: si el registro ya existe, devolver su id y no duplicar. Aqua360 no reenvía un documento que ya ha terminado bien, pero un timeout puede repetir la llamada.

## Creación al vuelo

- Partner: sí, a partir de `partner_id` dentro de `x_aqua_json`. Aqua360 no llama a la API de `res.partner`.
- Diario, producto, impuestos y modo de pago: tienen que existir de antemano. Se identifican por `journal_id.aqua_id`, `product_id.aqua_id`, `tax_ids` y `payment_mode_id.id`. Si no están, la acción debe rechazar el documento.

## Agrupación contable

No se añade ningún campo. El asiento resumen se puede montar con lo que ya viaja en el JSON:

- Facturas (`out_invoice`): `journal_id.aqua_id` + año-mes de `invoice_date`.
- Rectificativas (`out_refund`): el mismo diario y año-mes, en un asiento aparte. `reversed_aqua_id` enlaza el original y no decide el grupo.
- Pagos: `journal_id.aqua_id` + año-mes de `date`.

Aqua360 envía un registro por factura y por movimiento. El resumen contable lo hace Odoo.

## Checklist previo

Tienen que existir en Odoo, con el mismo código que el token de Aqua360:

- Diarios de cada serie de facturación (`InvoiceSerie.token`) y de cada banco (`CompanyBank.token`).
- Productos (`Product.token`).
- Impuestos (`Tax.token`).
- Modos de pago (`PaymentType.token`).
