# Releases i versionat SemVer

[Català](./README.ca.md) · [Español](./README.es.md) · [English](./README.en.md)

> **Històric fins a la `v1.135.02`.** Des d'aleshores hi ha una sola versió per a tot el monorepo i les seccions de versió, baseline i càlcul d'aquest document ja no s'apliquen. La política vigent, incloses les regles dels changelogs, és a [`RELEASES/README.ca.md`](../../../RELEASES/README.ca.md). Les notes antigues es conserven.

Aquesta carpeta guarda el pla i les notes de cada release del backend.

## Convenció del CHANGELOG

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

Des de la `v1.135.02`, el tag git i la versió única del monorepo es calculen combinant els changelogs de backend i frontend segons [`RELEASES/README.ca.md`](../../../RELEASES/README.ca.md).
