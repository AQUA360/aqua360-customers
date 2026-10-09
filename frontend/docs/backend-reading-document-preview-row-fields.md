# Camps complets a cada fila del preview (`validate`) — implementat

**Estat:** implementat al backend (veure `docs/backend-reading-document-flow.md` § Validar / preview i § Accions per fila).  
**Frontend:** `components/molecules/AddReadings.vue` ja mostra aquestes columnes.

---

## Contracte actual (`rows[]`)

Totes les `action` (`would_create`, `would_update`, `not_found`, `skip`) retornen el mateix conjunt de camps, amb els **valors efectius** que usaria el processament:

| Camp | Notes |
|------|--------|
| `origin` | Fitxer o defecte `TELECONTROL` |
| `is_control` | `true` només si el valor parsejat és `"true"` (case-insensitive); altrament `false` |
| `leak_value` | Enter; `0` si buit / no parsejable |
| `observation` | String (pot ser `""`) |
| `raw_reading_value` | Valor cru del fitxer |
| `previous_reading_value` | Si es coneix |
| `comm_module` / `supply_point_id` / `reading_date_raw` | Quan apliquen |

Més els camps d’identificació: `row_index`, `action`, `reason`, `meter_code`, `contract_token`, `reading_date`, `reading_value`.

---

## Cache

Si `last_preview` és d’una versió antiga (sense aquests camps), el pròxim `validate` reconstrueix sola (`preview_schema_version`). També es pot forçar amb `refresh=true` («Tornar a validar» al frontend).

---

## Frontend

Columnes a la taula de preview:

`#` · comptador · mòdul · contracte · data · lectura · valor raw · lectura anterior · origen · control · fuita · observació · acció
