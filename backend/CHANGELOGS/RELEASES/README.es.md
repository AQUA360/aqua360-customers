# Releases y versionado SemVer

[Català](./README.ca.md) · [Español](./README.es.md) · [English](./README.en.md)

Esta carpeta guarda el plan y las notas de cada release del backend.

## Convención del CHANGELOG (a partir de ahora)

Las secciones del changelog diario mapean a Conventional Commits y SemVer:

| Sección CHANGELOG | Conventional Commit | SemVer | Qué incluye |
|---|---|---|---|
| `### FEAT` | `feat` | **MINOR** (+1, PATCH = `00`) | Funcionalidad de producto (endpoint, modelo, informe, flujo) |
| `### FIX` | `fix` | **PATCH** (+1) | Correcciones de bugs |
| `### CHORE` | `chore` / `docs` / `ci` | **PATCH** (+1) | Añadidos menores: helpers, scripts, ConfigProject, watchdogs, docs, campos internos |
| `### MODIFIED` | `refactor` / `perf` | **PATCH** (+1) | Cambios a comportamiento existente sin feature nueva |
| `### BREAKING` | `BREAKING CHANGE` | **MAJOR** (+1) | Cambios incompatibles de API/contrato |

### Reglas de escritura

- Si es **nuevo y visible para el usuario/API** → `FEAT`
- Si es **nuevo pero interno/ops/detalle** → `CHORE` (no usar `ADDED` genérico)
- `ADDED` / `FIXED` son legacy en ficheros antiguos (`202605`, `202606`, parte de `CURRENT`); en días nuevos usar `FEAT` / `FIX` / `CHORE`
- En un mismo día, el tipo más alto manda: `BREAKING` > `FEAT` > `FIX`/`CHORE`/`MODIFIED`

### Ejemplo

```markdown
## [18-07-2026]

### FEAT
#### BILLING
    - Nuevo endpoint `PUT /api/billing/billing/<id>/cancel/` para cancelar un lote.

### CHORE
#### STATISTICS
    - Helper de parseo de fechas en `report_advanced_billing_service.py`.
    - Nueva clave `ConfigProject` `DOCUMENT_SIGN_ENABLED` (default `false`).

### FIX
#### BILLING
    - NameError en la generación de PDF de facturas.
```

## Formato de versión

`MAJOR.MINOR.PATCH` con 2 dígitos en MINOR y PATCH (p. ej. `1.50.00`, `1.51.01`).

## Archivos

| Archivo | Contenido |
|---|---|
| `<versión>.{ca,es,en}.md` | Notas de release concretas |
| `README.md` | Índice de idiomas |

## Release de producto (monorepo)

Esta carpeta versiona solo el **componente backend**.

El tag git y la versión conjunta (backend + frontend) se documentan en [`RELEASES/README.es.md`](../../../RELEASES/README.es.md) en la raíz del monorepo (`product = max(backend, frontend)`).
