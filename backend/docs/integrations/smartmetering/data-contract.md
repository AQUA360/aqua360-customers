# Contracte de dades — Smartmetering inbound

Consulta **inbound** de contractes del Programa d'Abonats (PA) per a sistemes de smart metering.

El payload replica el contracte de dades de la vista SQL [`vw_abonats_aqua360`](../../sql/vw_abonats_aqua360.sql), però **sempre** es resol des dels models Django. La vista no cal que estigui desplegada.

**Endpoint:** `GET /smartmetering/v1/contracts/`

**Codi:** `integrations/inbound/smartmetering/`

**OpenAPI (per a integradors):** [`openapi.yaml`](openapi.yaml) — importable a [Swagger Editor](https://editor.swagger.io), Postman o Redoc. És l'especificació pública de l'API (OpenAPI 3.0, l'estàndard que va succeir Swagger); no és *Open Data* (conjunts de dades públiques).

---

## Mapatge (vista SQL → models PA)

| Camp API / vista | Origen al PA |
|------------------|--------------|
| `policy` | `Contract.token` |
| `meter` | `Meter.code` via `supply_point_default.meter` |
| `rate` | `ContractUseType.name` via `Contract.use_type` (Domèstic, Comercial, Industrial, Municipal, Agrícola, …). No és la tarifa de preu: un contracte pot tenir-ne més d'una. |
| `service_point` | `Address.address_search` via `supply_point_default.address` |
| `inst_date` | `Meter.installation_at` (ISO `YYYY-MM-DD`) |
| `comm_module` | `Meter.comm_module` |
| `comm_technology` | `Meter.comm_technology` |
| `manufacturer` | `Meter.manufacturer` |
| `model` | `Meter.model` |
| `network_provider` | `Meter.network_provider` |
| `expl_id` | `Exploitation.token` via `supply_point_default.connection.exploitation` |
| `dma_id` | `DMA.token` via `supply_point_default.connection.dma` |
| `contract_active` | `true` si `Contract.status.token` = valor de `ConfigProject` `contract_active_token` |
| `customer` | `holder.name` + `holder.surname` |
| `cadastral_ref` | `SupplyPoint.cadastral` |
| `connect_id` | `Connection.id` com a text |

Filtres del queryset (com la vista): només `Contract.is_active=true`. Relacions absents → `null` (equivalent als `LEFT JOIN`).

### Diferències respecte la vista SQL

- La vista usa `c.status_id = 2`, un PK d'entorn. L'API usa `ConfigProject.contract_active_token`, el mateix criteri que la resta del PA.
- La vista usa `cn.exploitation_id` i `cn.dma_id` (PK). L'API usa `Exploitation.token` i `DMA.token`. Els noms dels camps continuen sent `expl_id` i `dma_id`.
- La vista usa el nom de la `PriceRate` activa més recent. L'API usa `ContractUseType.name` (`use_type`), el segment que espera smartmetering.

---

## Exemple

```json
[
  {
    "policy": "CTR-001",
    "meter": "MTR-001",
    "rate": "Domèstica",
    "service_point": "Barcelona, 08000",
    "inst_date": "2024-03-15",
    "comm_module": "MOD-99",
    "comm_technology": "NB-IoT",
    "manufacturer": "Elster",
    "model": "A1700",
    "network_provider": "Vodafone",
    "expl_id": "EXP-01",
    "dma_id": "DMA-01",
    "contract_active": true,
    "customer": "Anna Garcia",
    "cadastral_ref": "08001A00010001",
    "connect_id": "12"
  }
]
```
