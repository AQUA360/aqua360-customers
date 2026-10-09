# Releases i versionat SemVer

[Català](./README.ca.md) · [Español](./README.es.md) · [English](./README.en.md)

Aquesta carpeta guarda el pla i les notes de cada release del backend.

## Convenció del CHANGELOG (a partir d’ara)

Les seccions del changelog diari mapejen a Conventional Commits i SemVer:

| Secció CHANGELOG | Conventional Commit | SemVer | Què hi va |
|---|---|---|---|
| `### FEAT` | `feat` | **MINOR** (+1, PATCH = `00`) | Funcionalitat de producte (endpoint, model, informe, flux) |
| `### FIX` | `fix` | **PATCH** (+1) | Correccions de bugs |
| `### CHORE` | `chore` / `docs` / `ci` | **PATCH** (+1) | Afegits menors: helpers, scripts, ConfigProject, watchdogs, docs, camps interns |
| `### MODIFIED` | `refactor` / `perf` | **PATCH** (+1) | Canvis a comportament existent sense feature nova |
| `### BREAKING` | `BREAKING CHANGE` | **MAJOR** (+1) | Canvis incompatibles d’API/contracte |

### Regles d’escriptura

- Si és **nou i visible per l’usuari/API** → `FEAT`
- Si és **nou però intern/ops/detall** → `CHORE` (no usar `ADDED` genèric)
- `ADDED` / `FIXED` són legacy als fitxers antics (`202605`, `202606`, part de `CURRENT`); als nous dies usar `FEAT` / `FIX` / `CHORE`
- En un mateix dia, el tipus més alt mana: `BREAKING` > `FEAT` > `FIX`/`CHORE`/`MODIFIED`

### Exemple

```markdown
## [18-07-2026]

### FEAT
#### BILLING
    - Nou endpoint `PUT /api/billing/billing/<id>/cancel/` per cancel·lar un lot.

### CHORE
#### STATISTICS
    - Helper de parseig de dates a `report_advanced_billing_service.py`.
    - Nova clau `ConfigProject` `DOCUMENT_SIGN_ENABLED` (default `false`).

### FIX
#### BILLING
    - NameError en la generació de PDF de factures.
```

## Format de versió

`MAJOR.MINOR.PATCH` amb 2 dígits al MINOR i PATCH (ex. `1.50.00`, `1.51.01`).

## Fitxers

| Fitxer | Contingut |
|---|---|
| `<versió>.{ca,es,en}.md` | Notes de release concretes |
| `README.md` | Índex d’idiomes |

## Release de producte (monorepo)

Aquesta carpeta versiona només el **component backend**.

El tag git i la versió conjunta (backend + frontend) es documenten a [`RELEASES/README.ca.md`](../../../RELEASES/README.ca.md) a l’arrel del monorepo (`product = max(backend, frontend)`).
