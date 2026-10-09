# Frontend release plan `1.73.00`

[Català](./PLAN_RELEASE_1.73.00.ca.md) · [Español](./PLAN_RELEASE_1.73.00.es.md) · [English](./PLAN_RELEASE_1.73.00.en.md)

## Goal

Compute and document the frontend SemVer from the daily changelogs, using the same methodology as the backend.

## Agreed baseline

| Field | Value |
|---|---|
| Day | `05-05-2026` |
| Version | `1.50.00` |
| Reason | First day with a change-control changelog on the frontend (numerically aligned with the backend control start) |

## Checklist

- [x] Document convention in `CHANGELOGS/RELEASES/README.{ca,es,en}.md`
- [x] Transform historical sections (`ADDED`/`FIXED`/`MODIFY`/`REMOVED` → `FEAT`/`FIX`/`CHORE`/`MODIFIED`)
- [x] Classify `ADDED` as FEAT (visible product) vs CHORE (doubt → CHORE)
- [x] Walk days chronologically and apply bumps
- [x] Generate `CHANGELOGS/RELEASES/1.73.00.{ca,es,en}.md`
- [ ] (Optional) Update `package.json` → `"1.73.00"` when product asks
- [ ] (Optional) Product git tag when product asks

## Calculation result

- **Version if published with the last changelog day (`16-07-2026`): `1.73.00`**
- Days with FEAT (MINOR) bump: 23
- Days with PATCH bump (`FIX`/`CHORE`/`MODIFIED`): 25
- BREAKING days: 0

## Notes

- The number does **not** need to match the backend (backend reference ≈ `1.81.00` on 17-07-2026); each layer computes its own.
- Days with two `## [same date]` blocks are merged for the bump (highest type of the day wins once).
