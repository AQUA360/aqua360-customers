# Convención de CHANGELOG + SemVer (frontend)

[Català](./README.ca.md) · [Español](./README.es.md) · [English](./README.en.md)

Este documento alinea el versionado del frontend con el del backend: **Conventional Commits + SemVer**, sin inflar el MINOR con cambios pequeños.

## Formato de versión

`MAJOR.MINOR.PATCH` con **2 dígitos** en MINOR y PATCH:

```
1.50.00
1.51.01
1.73.00
```

## Baseline

| | |
|---|---|
| Fecha de inicio del control | `[05-05-2026]` |
| Versión baseline | `1.50.00` |
| Ficheros de changelog | `CHANGELOGS/CURRENT_CHANGELOG.ca.md`, `CHANGELOGS/2026/*.md` |

El día baseline queda fijado en `1.50.00`. Los días posteriores aplican el bump (véase más abajo).

## Secciones del changelog diario

| Sección | Conventional Commit | SemVer | Qué incluye (frontend) |
|---|---|---|---|
| `### FEAT` | `feat` | **MINOR** (+1, PATCH=`00`) | Funcionalidad visible: pantalla/ruta nueva, flujo nuevo, módulo, informe UI, integración visible, acción de usuario nueva |
| `### FIX` | `fix` | **PATCH** (+1) | Correcciones de bugs UI/UX |
| `### CHORE` | `chore` / `docs` / `ci` / `style` | **PATCH** (+1) | Utilidades, configs, i18n, estilos sin feature, deps menores, scripts, docs, eliminaciones de mantenimiento |
| `### MODIFIED` | `refactor` / `perf` | **PATCH** (+1) | Cambios a pantallas/flujos existentes sin capacidad nueva clara |
| `### BREAKING` | `BREAKING CHANGE` | **MAJOR** (+1, reset MINOR/PATCH) | Cambios que rompen contrato con API, rutas, store o UX incompatible |

**Regla del día:** el tipo más alto manda **una sola vez**

`BREAKING` > `FEAT` > `FIX` / `CHORE` / `MODIFIED`

### Criterios FEAT vs CHORE

**FEAT**

- Nueva ruta / vista / página / modal de flujo de negocio
- Nuevo módulo o feature flag que activa producto
- Nueva tabla/informe/dashboard con valor de negocio
- Nueva integración visible
- Nueva acción de usuario (botón/flujo que antes no existía)

**CHORE**

- Componentes internos, composables, helpers sin UI de producto nueva
- Estilos, iconos, i18n, accessibility polish
- Config (env, eslint, vite), deps, CI
- Refactors de carpetas, tipado, tests
- Campos/columnas menores dentro de una pantalla ya existente

**En caso de duda → CHORE (PATCH).**

## Estructura de escritura

```markdown
## [DD-MM-YYYY]

### FEAT
#### BILLING
    - Descripción de la funcionalidad visible.

### FIX
#### CONTRACT
    - Descripción de la corrección.

### CHORE
#### CORE
    - i18n / estilo / helper…

### MODIFIED
#### READINGS
    - Cambio a un flujo existente sin capacidad nueva clara.
```

**No** usar `ADDED` ni `FIXED` (ni `MODIFY`). Usar siempre `FEAT` / `FIX` / `CHORE` / `MODIFIED` / `BREAKING`.

## Cálculo de versión (día a día)

1. Fijar baseline: `05-05-2026` = `1.50.00`.
2. Recorrer cada `## [DD-MM-YYYY]` en orden cronológico (si hay dos bloques el mismo día, se fusionan las secciones).
3. Por cada día posterior al baseline:
   - Si hay `BREAKING` → `MAJOR += 1`, `MINOR = 00`, `PATCH = 00`
   - Si no, y hay `FEAT` → `MINOR += 1`, `PATCH = 00`
   - Si no, y hay `FIX` / `CHORE` / `MODIFIED` → `PATCH += 1`
4. La versión del último día = versión de release “si se publica hoy”.

Ejemplo:

```
1.50.00  ← baseline (05-05-2026)
   FEAT  → 1.51.00
   FIX   → 1.51.01
   CHORE → 1.51.02
   FEAT  → 1.52.00   (el PATCH se reinicia)
```

## Entregables de release

Cuando se cierre un periodo, crear:

- `CHANGELOGS/RELEASES/<versión>.{ca,es,en}.md` — notas de release (metodología, tabla día→versión, highlights)
- Opcional: `CHANGELOGS/RELEASES/PLAN_RELEASE_<versión>.{ca,es,en}.md` — plan/checklist

El **tag git** no es de este componente: se hace en la **release de producto** del monorepo (`RELEASES/` en la raíz). Véase [`RELEASES/README.es.md`](../../../RELEASES/README.es.md).

## Referencia

La última release calculada está en `CHANGELOGS/RELEASES/` (véase el fichero de versión más alto).
