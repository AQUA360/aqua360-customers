# Filtre i paginació al preview de lectures — estat implementat

**Endpoint:** `GET|POST /billing/reading-document/{id}/validate/`  
**Doc de flux:** `docs/backend-reading-document-flow.md`  
**Frontend:** `components/molecules/AddReadings.vue` + `plugins/api/billing/reading-document-api.js`

> **Estat:** implementat al backend (filtre + paginació + cache `last_preview`) i consumit pel frontend.

---

## Params acceptats

| Param | Defecte | Ús |
|-------|---------|-----|
| `max_rows` | `25` | Mida de pàgina |
| `offset` | `0` | Desplaçament dins el conjunt filtrat |
| `page` / `page_size` | — | Alternativa 1-based a `offset`/`max_rows` |
| `action` | totes | `would_create`, `would_update`, `not_found`, `skip` |
| `reason` | — | Només amb `skip`: `skipped_existing`, `skipped_no_date`, `no_supply_points`, `no_contracts` |
| `search` | — | `meter_code` / `comm_module` / `contract_token` |
| `ordering` | `row_index` | o `-row_index` |
| `refresh` | `false` | Força rellegir el CSV i reconstruir la cache |

---

## Comportament

1. Es construeix el preview complet (totes les entrades + stats globals).
2. Es desa a `last_preview` (cache).
3. Es filtra i després es pagina → resposta amb `filtered_total`, `rows`, `rows_truncated`.
4. Els clics de filtre/pàgina reutilitzen la cache **sense** tornar a parsejar el CSV.
5. `?refresh=true` o un `PATCH` de fitxer/plantilla reconstrueix la cache.
6. Params invàlids → `400`.

### Exemple

```http
GET /billing/reading-document/12/validate/?action=not_found&offset=0&max_rows=25
```

Retorna files `not_found` encara que no estiguin al principi del CSV. `stats` segueix sent global; `filtered_total` és el total del filtre.

---

## Ús al frontend

| Acció usuari | Crida |
|--------------|--------|
| Pujar i validar / canviar fitxer | `validate/?page=1&page_size=25&refresh=true` |
| Clic filtro (p. ex. no trobats) | `validate/?action=not_found&page=1&page_size=25` (cache) |
| Skip amb raó | `validate/?action=skip&reason=skipped_existing&page=1&page_size=25` |
| Canviar pàgina | mateix filtre + `page` nou (cache) |
| «Tornar a validar» | mateix filtre/pàgina + `refresh=true` |

El frontend usa `page` / `page_size` (no `offset`/`max_rows`), i paginació amb `filtered_total`.

### Opcional pendent (UI)

- Camp de cerca (`search`) al preview
- Canvi d’ordenació (`ordering`)
