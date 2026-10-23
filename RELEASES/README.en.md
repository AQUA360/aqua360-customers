# Releases (monorepo)

[Català](./README.ca.md) · [Español](./README.es.md) · [English](./README.en.md)

This folder documents the releases of Aqua360 Customers. There is **a single version** for the whole monorepo (backend, frontend, Docker and documentation): it is the one that gets tagged, published on GitHub and deployed.

The component versions (backend `1.135.01`, frontend `1.123.00`) are frozen as history in `backend/CHANGELOGS/RELEASES/` and `frontend/CHANGELOGS/RELEASES/`, and are no longer calculated. The first single version starts from `1.135.02`.

## Format

`MAJOR.MINOR.PATCH` with 2 digits for MINOR and PATCH:

```
1.136.00
1.136.01
```

The git tag has a `v` prefix → `v1.136.00`.

## Calculating the version

The bump is calculated **day by day** over both changelogs together (`backend/CHANGELOGS/CURRENT_CHANGELOG.ca.md` and `frontend/CHANGELOGS/CURRENT_CHANGELOG.ca.md`), since the last tag. Each day counts as the highest type found in either file:

| Changelog section | Conventional Commit | Bump |
|---|---|---|
| `### BREAKING` | `BREAKING CHANGE` | **MAJOR** (+1, MINOR and PATCH = `00`) |
| `### FEAT` | `feat` | **MINOR** (+1, PATCH = `00`) |
| `### FIX` | `fix` | **PATCH** (+1) |
| `### CHORE` | `chore` / `docs` / `ci` | **PATCH** (+1) |
| `### MODIFIED` | `refactor` / `perf` | **PATCH** (+1) |

Example: if on 20-10 the backend has `FIX` and the frontend `FEAT`, that day counts as `FEAT`.

- If only Docker, CI or operations docs change, bump the PATCH.
- If the resulting number is already tagged, skip to the next one and explain it in the notes.

## Changelogs

The `CURRENT_CHANGELOG.ca.md` files stay separate per area, because each team writes its day-to-day changes there; only the version is shared.

- One `## [DD-MM-YYYY]` block per day, with the sections from the table above and the module (`#### BILLING`, `#### OV`…).
- New and visible to the user or the API → `FEAT`. New but internal, operational or a detail → `CHORE`.
- Entries added to an already tagged day are moved to the new day.
- When the month changes, the blocks of the closed month move to the monthly archive `CHANGELOGS/<year>/<YYYYMM>_CHANGELOG.ca.md`.

## Release flow

1. **Calculate the version** with both changelogs together (see above).
2. **Branch** `release/<version>` from an up-to-date `develop`.
3. **Close the changelogs** for backend and frontend (and the monthly archive if the month changed).
4. **Notes** in `RELEASES/<version>.{ca,es,en}.md` using the template below. All three languages say the same.
5. **Commit** `release: v<version>` and PR `release/<version>` → `main`, reviewed and merged by hand.
6. **Annotated tag** on the merge commit in `main`:

```bash
git checkout main && git pull
git tag -a v<version> -m "Release v<version>"
git push origin v<version>
```

7. **GitHub Release** published (not a draft) from the tag, so the Imatges workflow builds the images:

```bash
gh release create v<version> --verify-tag --title "v<version>" --notes-file RELEASES/<version>.en.md
```

8. **PR `main` → `develop`** so the notes and any hotfix return to `develop`.
9. **Deploy** always from the tag (`CUSTOMERS_VERSION=v<version>`), never from an untagged `main` commit.

A hotfix branches from `main`, bumps the PATCH and follows steps 4 to 8.

## Files

| File | Content |
|---|---|
| `RELEASES/README.{ca,es,en}.md` | This policy (one file per language) |
| `RELEASES/README.md` | Language index |
| `RELEASES/<version>.{ca,es,en}.md` | Release notes |
| `RELEASES/PLAN_RELEASE_<version>.{ca,es,en}.md` | Optional: checklist or plan for large releases |

No more files are created in `backend/CHANGELOGS/RELEASES/` or `frontend/CHANGELOGS/RELEASES/`.

## Template `RELEASES/<version>.en.md`

```markdown
# Release v<version> — DD-MM-YYYY

[Català](./<version>.ca.md) · [Español](./<version>.es.md) · [English](./<version>.en.md)

Baseline: `v<previous version>` (DD-MM-YYYY).

## Day → bump → version table

| Day | Backend | Frontend | Bump | Version |
|---|---|---|---|---|
| DD-MM-YYYY | — | — | `BASELINE` | `<previous version>` |
| DD-MM-YYYY | FIX | FEAT | `FEAT` | `<…>` |
| DD-MM-YYYY | FIX | — | `PATCH` | **`<version>`** |

## Highlights

- …

## Changes

### Backend

- FEAT: …
- FIX: …

### Frontend

- FEAT: …
- FIX: …

## Notes

- Migrations: <list> or "No migrations".
- Environment variables, ConfigProject, opscripts and incompatibilities.
- Images: with `CUSTOMERS_VERSION=v<version>` in `.env`, `docker compose pull && docker compose up -d`.
```

## Don't

- Calculate separate backend and frontend versions again.
- Calculate the bump from only one of the two changelogs.
- Tag before the notes are merged into `main`, or with a lightweight tag (without `-a`).
- Reuse an already tagged number.
- Leave the GitHub Release as a draft.
- Deploy an untagged `main` commit.
