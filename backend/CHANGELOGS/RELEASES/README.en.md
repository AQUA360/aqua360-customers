# Releases and SemVer versioning

[Català](./README.ca.md) · [Español](./README.es.md) · [English](./README.en.md)

This folder holds the plan and notes for each backend release.

## CHANGELOG convention (from now on)

Daily changelog sections map to Conventional Commits and SemVer:

| CHANGELOG section | Conventional Commit | SemVer | What goes here |
|---|---|---|---|
| `### FEAT` | `feat` | **MINOR** (+1, PATCH = `00`) | Product functionality (endpoint, model, report, flow) |
| `### FIX` | `fix` | **PATCH** (+1) | Bug fixes |
| `### CHORE` | `chore` / `docs` / `ci` | **PATCH** (+1) | Minor additions: helpers, scripts, ConfigProject, watchdogs, docs, internal fields |
| `### MODIFIED` | `refactor` / `perf` | **PATCH** (+1) | Changes to existing behaviour without a clear new feature |
| `### BREAKING` | `BREAKING CHANGE` | **MAJOR** (+1) | Incompatible API/contract changes |

### Writing rules

- If it is **new and visible to the user/API** → `FEAT`
- If it is **new but internal/ops/detail** → `CHORE` (do not use generic `ADDED`)
- `ADDED` / `FIXED` are legacy in older files (`202605`, `202606`, parts of `CURRENT`); for new days use `FEAT` / `FIX` / `CHORE`
- On the same day, the highest type wins: `BREAKING` > `FEAT` > `FIX`/`CHORE`/`MODIFIED`

### Example

```markdown
## [18-07-2026]

### FEAT
#### BILLING
    - New endpoint `PUT /api/billing/billing/<id>/cancel/` to cancel a batch.

### CHORE
#### STATISTICS
    - Date-parsing helper in `report_advanced_billing_service.py`.
    - New `ConfigProject` key `DOCUMENT_SIGN_ENABLED` (default `false`).

### FIX
#### BILLING
    - NameError when generating invoice PDFs.
```

## Version format

`MAJOR.MINOR.PATCH` with 2 digits for MINOR and PATCH (e.g. `1.50.00`, `1.51.01`).

## Files

| File | Content |
|---|---|
| `<version>.{ca,es,en}.md` | Concrete release notes |
| `README.md` | Language index |

## Product release (monorepo)

This folder versions only the **backend component**.

The git tag and joint version (backend + frontend) are documented in [`RELEASES/README.en.md`](../../../RELEASES/README.en.md) at the monorepo root (`product = max(backend, frontend)`).
