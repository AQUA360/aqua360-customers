# Webhooks de salida — contrato de datos

[Català](data-contract.md) | [Español](data-contract.es.md)

Customers avisa a un sistema externo con un `POST` JSON cuando ocurren ciertos trámites.
Código: `integrations/outbound/webhooks/`.

## Configuración (`.env` de la instalación)

```env
WEBHOOKS_ENABLED=True
WEBHOOKS_URL=https://receptor.example/hooks
WEBHOOKS_SECRET=<secreto largo y aleatorio, compartido con el receptor>
INSTANCE_UID=<identificador de la instalación>
```

- Activado sin URL o sin secreto, los avisos se guardan como `disabled` y nunca se envían sin firmar (se pueden reenviar con `resend_webhooks --status disabled`).
- Los valores fijos (reintentos, ritmo, tamaño de los paquetes, intervalo de la comparación) están en `settings.py` (`WEBHOOKS_*`).

## Petición

Cabeceras:

| Cabecera | Valor |
|---|---|
| `X-Aqua360-Event` | Tipo de aviso (`invoice.paid`...) |
| `X-Aqua360-Event-Id` | UUID del aviso: es el mismo en cada reintento (idempotencia) |
| `X-Aqua360-Timestamp` | Segundos Unix del envío |
| `X-Aqua360-Signature` | `sha256=` + HMAC-SHA256(secreto, `"<timestamp>.<cuerpo>"`) en hexadecimal |

Cuerpo:

```json
{
  "event_id": "…",
  "event_type": "invoice.paid",
  "occurred_at": "2026-11-25T10:00:00+00:00",
  "version": "1.0",
  "source": {"system": "aqua360-customers", "instance": "…"},
  "data": { … }
}
```

Respuesta: cualquier `2xx` es entregado. `408`, `429`, `5xx` y errores de red se reintentan (1 min, 5 min, 15 min, 1 h, 3 h, 6 h y 12 h); el resto de `4xx` y las redirecciones no. Agotados, el aviso queda `failed` y se puede reenviar con `resend_webhooks`. El receptor debe usar `event_id` para ignorar duplicados.

## Avisos

| `event_type` | Cuándo | `data` |
|---|---|---|
| `contract.created` | Se crea un contrato al confirmar una solicitud de alta | `contract`, `contract_request`, `holder`, `supply_point` |
| `contract_termination.confirmed` | El contrato pasa a baja | `contract`, `termination_request`, `holder` |
| `contract_termination.cancelled` | Se deshace una baja | `contract`, `termination_request` |
| `contract_request.cancelled` | Una solicitud de alta pasa al estado anulado | `contract_request {id, code}`, `status {token, name}` |
| `invoice.issued` | Una factura suelta recibe el número legal (no presupuestos) | factura (ver `invoice_data`) |
| `billing.issued` | Facturación masiva confirmada | `billing`, `part`, `parts`, `invoices[]` |
| `invoice.paid` | La factura pasa al estado pagada | `part`, `parts`, `invoices[]` |
| `invoice.returned` | Un recibo activo de la factura pasa a devuelto | `part`, `parts`, `invoices[]` |
| `invoice.expired` | La factura pasa al estado vencida | `part`, `parts`, `invoices[]` |
| `invoice.cancelled` | La factura pasa a abonada (tenía cobros) o anulada (sin cobrar); `status` indica cuál | `part`, `parts`, `invoices[]` |

Cada registro lleva el id interno (estable) y el código. Las facturas llevan también el `token` (el mismo que usa la OV).

## Avisos de estado de pago (`invoice.paid`, `.returned`, `.expired`, `.cancelled`)

El estado de una factura cambia desde muchos sitios (recibos, remesas, devoluciones, vencimientos, cobros masivos, anulaciones). Para no perder ninguno, una tarea compara cada `WEBHOOKS_INVOICE_SCAN_MINUTES` (5 minutos) el estado de todas las facturas con el último estado avisado y avisa de los cambios. Por tanto:

- El aviso suele llegar **hasta 5 minutos** después del cambio (más el tiempo de envío). Puede tardar más si en una pasada cambian más de `WEBHOOKS_INVOICE_SCAN_LIMIT` (5.000) facturas, porque el resto van a la pasada siguiente, o si los datos de una factura no se pueden construir, que se reintenta en cada pasada.
- Si una factura cambia dos veces dentro del intervalo, **solo se avisa del estado final**; si vuelve al estado anterior, no se avisa.
- Si un recibo pasa a devuelto y a la vez cambia el estado de la factura, manda `invoice.returned`.
- Solo se avisa de facturas activas, con número y que no son presupuestos.
- Las facturas van en paquetes de `WEBHOOKS_BILLING_CHUNK_SIZE` (500); `part` y `parts` indican qué paquete es.
- La primera ejecución hace la foto sin avisar de nada.

Cada factura de `invoices[]`:

```json
{
  "id": 123,
  "token": "…",
  "number": "FC2026/000123",
  "serie": "FC",
  "issue_date": "2026-11-01",
  "due_date": "2026-11-30",
  "contract": {"id": 45, "code": "…"},
  "holder": {"id": 67},
  "previous_status": {"token": "…", "name": "Confirmada"},
  "status": {"token": "…", "name": "Pagada"},
  "direct_debit": true,
  "amounts": {"total": "110.00", "paid": "110.00", "pending": "0.00", "currency": "EUR"},
  "payment_date": "2026-11-20",
  "return": null
}
```

- `previous_status`: el último estado avisado (`null` si la factura es nueva).
- `amounts.paid`: suma de los recibos activos pagados; `pending`, lo que falta.
- `payment_date`: fecha del último cobro, solo en `invoice.paid`.
- `return`: solo en `invoice.returned`, `{"date": "AAAA-MM-DD", "reason": {"code": "AM04", "name": "…"}}` (la última devolución; `reason` puede ser `null`).
- Sin IBAN ni datos bancarios.

## Órdenes

| Orden | Para qué |
|---|---|
| `send_test_webhook` | Envía un `webhook.test` y muestra la respuesta del receptor |
| `resend_webhooks [--status failed\|disabled] [--type …] [--since AAAA-MM-DD]` | Reenvía avisos fallidos o guardados sin URL |
| `webhooks_invoice_baseline` | Rehace la foto del estado de las facturas sin avisar. Tras un tiempo con los webhooks desactivados, ejecútela **antes** de volver a activarlos; si no, se avisará de todos los cambios acumulados |

## Tests

```bash
python manage.py test integrations.tests_webhooks
```
