# Convenció de CHANGELOG + SemVer (frontend)

[Català](./README.ca.md) · [Español](./README.es.md) · [English](./README.en.md)

Aquest document alinea el versionat del frontend amb el del backend: **Conventional Commits + SemVer**, sense inflar el MINOR amb canvis petits.

## Format de versió

`MAJOR.MINOR.PATCH` amb **2 dígits** al MINOR i al PATCH:

```
1.50.00
1.51.01
1.73.00
```

## Baseline

| | |
|---|---|
| Data d’inici del control | `[05-05-2026]` |
| Versió baseline | `1.50.00` |
| Fitxers de changelog | `CHANGELOGS/CURRENT_CHANGELOG.ca.md`, `CHANGELOGS/2026/*.md` |

El dia baseline queda fixat a `1.50.00`. Els dies posteriors apliquen el bump (vegeu més avall).

## Seccions del changelog diari

| Secció | Conventional Commit | SemVer | Què hi va (frontend) |
|---|---|---|---|
| `### FEAT` | `feat` | **MINOR** (+1, PATCH=`00`) | Funcionalitat visible: pantalla/ruta nova, flux nou, mòdul, informe UI, integració visible, acció d’usuari nova |
| `### FIX` | `fix` | **PATCH** (+1) | Correccions de bugs UI/UX |
| `### CHORE` | `chore` / `docs` / `ci` / `style` | **PATCH** (+1) | Utilitats, configs, i18n, estils sense feature, deps menors, scripts, docs, eliminacions de manteniment |
| `### MODIFIED` | `refactor` / `perf` | **PATCH** (+1) | Canvis a pantalles/fluxos existents sense capacitat nova clara |
| `### BREAKING` | `BREAKING CHANGE` | **MAJOR** (+1, reset MINOR/PATCH) | Canvis que trenquen contracte amb API, rutes, store o UX incompatible |

**Regla del dia:** el tipus més alt mana **una sola vegada**

`BREAKING` > `FEAT` > `FIX` / `CHORE` / `MODIFIED`

### Criteris FEAT vs CHORE

**FEAT**

- Nova ruta / vista / pàgina / modal de flux de negoci
- Nou mòdul o feature flag que activa producte
- Nova taula/informe/dashboard amb valor de negoci
- Nova integració visible
- Nova acció d’usuari (botó/flux que abans no existia)

**CHORE**

- Components interns, composables, helpers sense UI de producte nova
- Estils, icones, i18n, accessibility polish
- Config (env, eslint, vite), deps, CI
- Refactors de carpetes, tipatge, tests
- Camps/columnes menors dins d’una pantalla ja existent

**En cas de dubte → CHORE (PATCH).**

## Estructura d’escriptura

```markdown
## [DD-MM-YYYY]

### FEAT
#### BILLING
    - Descripció de la funcionalitat visible.

### FIX
#### CONTRACT
    - Descripció de la correcció.

### CHORE
#### CORE
    - i18n / estil / helper…

### MODIFIED
#### READINGS
    - Canvi a un flux existent sense capacitat nova clara.
```

**No** usar `ADDED` ni `FIXED` (ni `MODIFY`). Usar sempre `FEAT` / `FIX` / `CHORE` / `MODIFIED` / `BREAKING`.

## Càlcul de versió (dia a dia)

1. Fixar baseline: `05-05-2026` = `1.50.00`.
2. Recórrer cada `## [DD-MM-YYYY]` en ordre cronològic (si hi ha dos blocs el mateix dia, es fusionen les seccions).
3. Per cada dia posterior al baseline:
   - Si hi ha `BREAKING` → `MAJOR += 1`, `MINOR = 00`, `PATCH = 00`
   - Si no, i hi ha `FEAT` → `MINOR += 1`, `PATCH = 00`
   - Si no, i hi ha `FIX` / `CHORE` / `MODIFIED` → `PATCH += 1`
4. La versió de l’últim dia = versió de release “si es publica avui”.

Exemple:

```
1.50.00  ← baseline (05-05-2026)
   FEAT  → 1.51.00
   FIX   → 1.51.01
   CHORE → 1.51.02
   FEAT  → 1.52.00   (el PATCH es reinicia)
```

## Deliverables de release

Quan es tanqui un període, crear:

- `CHANGELOGS/RELEASES/<versió>.{ca,es,en}.md` — notes de release (metodologia, taula dia→versió, highlights)
- Opcional: `CHANGELOGS/RELEASES/PLAN_RELEASE_<versió>.{ca,es,en}.md` — pla/checklist

El **tag git** no és d’aquest component: es fa a la **release de producte** del monorepo (`RELEASES/` a l’arrel). Vegeu [`RELEASES/README.ca.md`](../../../RELEASES/README.ca.md).

## Referència

La darrera release calculada està a `CHANGELOGS/RELEASES/` (vegeu el fitxer de versió més alt).
