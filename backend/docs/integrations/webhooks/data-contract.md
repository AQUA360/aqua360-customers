# Webhooks de sortida — contracte de dades

[Català](data-contract.md) | [Español](data-contract.es.md)

El Customers avisa un sistema extern amb un `POST` JSON quan passen certs tràmits.
Codi: `integrations/outbound/webhooks/`.

## Configuració (`.env` de la instal·lació)

```env
WEBHOOKS_ENABLED=True
WEBHOOKS_URL=https://receptor.example/hooks
WEBHOOKS_SECRET=<secret llarg i aleatori, compartit amb el receptor>
INSTANCE_UID=<identificador de la instal·lació>
```

- Activat sense URL o sense secret, els avisos es desen com a `disabled` i no s'envien mai sense signar (es poden reenviar amb `resend_webhooks --status disabled`).
- Els valors fixos (reintents, ritme, mida dels paquets, interval de la comparació) són a `settings.py` (`WEBHOOKS_*`).

## Petició

Capçaleres:

| Capçalera | Valor |
|---|---|
| `X-Aqua360-Event` | Tipus d'avís (`invoice.paid`...) |
| `X-Aqua360-Event-Id` | UUID de l'avís: és el mateix en cada reintent (idempotència) |
| `X-Aqua360-Timestamp` | Segons Unix de l'enviament |
| `X-Aqua360-Signature` | `sha256=` + HMAC-SHA256(secret, `"<timestamp>.<cos>"`) en hexadecimal |

Cos:

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

Resposta: qualsevol `2xx` és entregat. `408`, `429`, `5xx` i errors de xarxa es reintenten (1 min, 5 min, 15 min, 1 h, 3 h, 6 h i 12 h); la resta de `4xx` i les redireccions no. Exhaurits, l'avís queda `failed` i es pot reenviar amb `resend_webhooks`. El receptor ha de fer servir `event_id` per ignorar duplicats.

## Avisos

| `event_type` | Quan | `data` |
|---|---|---|
| `contract.created` | Es crea un contracte en confirmar una sol·licitud d'alta | `contract`, `contract_request`, `holder`, `supply_point` |
| `contract_termination.confirmed` | El contracte passa a baixa | `contract`, `termination_request`, `holder` |
| `contract_termination.cancelled` | Es desfà una baixa | `contract`, `termination_request` |
| `contract_request.cancelled` | Una sol·licitud d'alta passa a l'estat anul·lat | `contract_request {id, code}`, `status {token, name}` |
| `invoice.issued` | Una factura solta rep el número legal (no pressupostos) | factura (vegeu `invoice_data`) |
| `billing.issued` | Facturació massiva confirmada | `billing`, `part`, `parts`, `invoices[]` |
| `invoice.paid` | La factura passa a l'estat pagada | `part`, `parts`, `invoices[]` |
| `invoice.returned` | Un rebut actiu de la factura passa a retornat | `part`, `parts`, `invoices[]` |
| `invoice.expired` | La factura passa a l'estat vençuda | `part`, `parts`, `invoices[]` |
| `invoice.cancelled` | La factura passa a abonada (tenia cobraments) o anul·lada (sense cobrar); `status` diu quina | `part`, `parts`, `invoices[]` |

Cada registre porta l'id intern (estable) i el codi. Les factures porten també el `token` (el mateix que fa servir l'OV).

## Avisos d'estat de pagament (`invoice.paid`, `.returned`, `.expired`, `.cancelled`)

L'estat d'una factura canvia des de molts llocs (rebuts, remeses, devolucions, venciments, cobraments massius, anul·lacions). Per no perdre'n cap, una tasca compara cada `WEBHOOKS_INVOICE_SCAN_MINUTES` (5 minuts) l'estat de totes les factures amb el darrer estat avisat i avisa dels canvis. Per tant:

- L'avís sol arribar **fins a 5 minuts** després del canvi (més el temps d'enviament). Pot trigar més si en una passada canvien més de `WEBHOOKS_INVOICE_SCAN_LIMIT` (5.000) factures, perquè la resta van a la passada següent, o si les dades d'una factura no es poden construir, que es torna a provar a cada passada.
- Si una factura canvia dues vegades dins l'interval, **només s'avisa de l'estat final**; si torna a l'estat d'abans, no s'avisa.
- Si un rebut passa a retornat i alhora canvia l'estat de la factura, mana `invoice.returned`.
- Només s'avisa de factures actives, amb número i que no són pressupostos.
- Les factures van en paquets de `WEBHOOKS_BILLING_CHUNK_SIZE` (500); `part` i `parts` diuen quin paquet és.
- La primera execució fa la foto sense avisar de res.

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

- `previous_status`: el darrer estat avisat (`null` si la factura és nova).
- `amounts.paid`: suma dels rebuts actius pagats; `pending`, el que falta.
- `payment_date`: data del darrer cobrament, només a `invoice.paid`.
- `return`: només a `invoice.returned`, `{"date": "AAAA-MM-DD", "reason": {"code": "AM04", "name": "…"}}` (el darrer retorn; `reason` pot ser `null`).
- Sense IBAN ni dades bancàries.

## Ordres

| Ordre | Per a què |
|---|---|
| `send_test_webhook` | Envia un `webhook.test` i mostra la resposta del receptor |
| `resend_webhooks [--status failed\|disabled] [--type …] [--since AAAA-MM-DD]` | Torna a enviar avisos fallits o desats sense URL |
| `webhooks_invoice_baseline` | Refà la foto de l'estat de les factures sense avisar. Després d'un temps amb els webhooks desactivats, executeu-la **abans** de tornar-los a activar; si no, s'avisarà de tots els canvis acumulats |

## Tests

```bash
python manage.py test integrations.tests_webhooks
```
