# CHANGELOG + SemVer convention (frontend)

[Català](./README.ca.md) · [Español](./README.es.md) · [English](./README.en.md)

This document aligns frontend versioning with the backend: **Conventional Commits + SemVer**, without inflating MINOR for small changes.

## Version format

`MAJOR.MINOR.PATCH` with **2 digits** for MINOR and PATCH:

```
1.50.00
1.51.01
1.73.00
```

## Baseline

| | |
|---|---|
| Control start date | `[05-05-2026]` |
| Baseline version | `1.50.00` |
| Changelog files | `CHANGELOGS/CURRENT_CHANGELOG.ca.md`, `CHANGELOGS/2026/*.md` |

The baseline day is fixed at `1.50.00`. Later days apply the bump (see below).

## Daily changelog sections

| Section | Conventional Commit | SemVer | What goes here (frontend) |
|---|---|---|---|
| `### FEAT` | `feat` | **MINOR** (+1, PATCH=`00`) | Visible functionality: new screen/route, new flow, module, UI report, visible integration, new user action |
| `### FIX` | `fix` | **PATCH** (+1) | UI/UX bug fixes |
| `### CHORE` | `chore` / `docs` / `ci` / `style` | **PATCH** (+1) | Utilities, configs, i18n, styles without a feature, minor deps, scripts, docs, maintenance removals |
| `### MODIFIED` | `refactor` / `perf` | **PATCH** (+1) | Changes to existing screens/flows without a clear new capability |
| `### BREAKING` | `BREAKING CHANGE` | **MAJOR** (+1, reset MINOR/PATCH) | Changes that break API contract, routes, store or incompatible UX |

**Day rule:** the highest type wins **once**

`BREAKING` > `FEAT` > `FIX` / `CHORE` / `MODIFIED`

### FEAT vs CHORE criteria

**FEAT**

- New route / view / page / business-flow modal
- New module or feature flag that enables product
- New table/report/dashboard with business value
- New visible integration
- New user action (button/flow that did not exist before)

**CHORE**

- Internal components, composables, helpers without new product UI
- Styles, icons, i18n, accessibility polish
- Config (env, eslint, vite), deps, CI
- Folder refactors, typing, tests
- Minor fields/columns inside an existing screen

**When in doubt → CHORE (PATCH).**

## Writing structure

```markdown
## [DD-MM-YYYY]

### FEAT
#### BILLING
    - Description of the visible functionality.

### FIX
#### CONTRACT
    - Description of the fix.

### CHORE
#### CORE
    - i18n / style / helper…

### MODIFIED
#### READINGS
    - Change to an existing flow without a clear new capability.
```

Do **not** use `ADDED` or `FIXED` (or `MODIFY`). Always use `FEAT` / `FIX` / `CHORE` / `MODIFIED` / `BREAKING`.

## Day-by-day version calculation

1. Fix baseline: `05-05-2026` = `1.50.00`.
2. Walk each `## [DD-MM-YYYY]` in chronological order (if two blocks share a day, merge sections).
3. For each day after baseline:
   - If `BREAKING` → `MAJOR += 1`, `MINOR = 00`, `PATCH = 00`
   - Else if `FEAT` → `MINOR += 1`, `PATCH = 00`
   - Else if `FIX` / `CHORE` / `MODIFIED` → `PATCH += 1`
4. Last day’s version = release version “if published today”.

Example:

```
1.50.00  ← baseline (05-05-2026)
   FEAT  → 1.51.00
   FIX   → 1.51.01
   CHORE → 1.51.02
   FEAT  → 1.52.00   (PATCH resets)
```

## Release deliverables

When closing a period, create:

- `CHANGELOGS/RELEASES/<version>.{ca,es,en}.md` — release notes (methodology, day→version table, highlights)
- Optional: `CHANGELOGS/RELEASES/PLAN_RELEASE_<version>.{ca,es,en}.md` — plan/checklist

The **git tag** is not for this component: it is created on the monorepo **product release** (`RELEASES/` at the root). See [`RELEASES/README.en.md`](../../../RELEASES/README.en.md).

## Reference

The latest computed release is under `CHANGELOGS/RELEASES/` (see the highest version file).
