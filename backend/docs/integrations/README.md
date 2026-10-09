# Documentació d'integracions

Índex de la documentació detallada per integració. El document general de l'app `integrations` continua a [`../integrations.md`](../integrations.md).

| Integració | Direcció | Documentació |
|------------|----------|--------------|
| Giswater | Outbound + Inbound | [`integrations/outbound/giswater/README.md`](../../integrations/outbound/giswater/README.md) |
| Aqua360 Sign | Outbound + Inbound | [`signing/data-contract.md`](signing/data-contract.md) · [`../integrations.md`](../integrations.md#aqua360-sign) |
| Odoo (ERP Comptabilitat) | Outbound (Fase 1) | [`odoo/data-contract.md`](odoo/data-contract.md) · [`odoo/plan.md`](odoo/plan.md) · [`integrations/outbound/odoo/README.md`](../../integrations/outbound/odoo/README.md) |
| Smartmetering | Inbound | [`smartmetering/data-contract.md`](smartmetering/data-contract.md) · [`smartmetering/openapi.yaml`](smartmetering/openapi.yaml) · [`../integrations.md`](../integrations.md#smartmetering) |

## Convenció

Cada integració té una carpeta pròpia sota `docs/integrations/<nom>/` amb:

- **`data-contract.md`** — contracte de dades (payloads, mapatges, principis) quan aplique.
- **`openapi.yaml`** — especificació OpenAPI 3.0 per a integradors (l'estàndard que va succeir Swagger), quan l'API s'ha de compartir amb tercers.
- **`plan.md`** — pla d'implementació al PA (fases, mapatge des de models interns) quan encara hi ha treball pendent.

El codi viu sempre a `integrations/outbound/<nom>/` o `integrations/inbound/<nom>/`.
