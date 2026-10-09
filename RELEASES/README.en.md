# Product releases (monorepo)

[Català](./README.ca.md) · [Español](./README.es.md) · [English](./README.en.md)

This folder documents the **joint version** of the Aqua360 product (backend + frontend) that is deployed together from the monorepo.

Component versions continue to be calculated separately:

| Component | SemVer convention | Release notes |
|---|---|---|
| Backend | [`backend/CHANGELOGS/RELEASES/README.en.md`](../backend/CHANGELOGS/RELEASES/README.en.md) | `backend/CHANGELOGS/RELEASES/<version>.en.md` |
| Frontend | [`frontend/CHANGELOGS/RELEASES/README.en.md`](../frontend/CHANGELOGS/RELEASES/README.en.md) | `frontend/CHANGELOGS/RELEASES/<version>.en.md` |

## Version layers

| Layer | Meaning | Location | Example |
|---|---|---|---|
| Backend component | BE changelog SemVer | `backend/CHANGELOGS/RELEASES/` | `1.72.00` |
| Frontend component | FE changelog SemVer | `frontend/CHANGELOGS/RELEASES/` | `1.73.00` |
| **Product** | Joint version tagged in git | `RELEASES/` + git tag | `v1.74.00` |

Backend and frontend are **not** required to share the same number. The git tag represents the **deployable set** (commit + BE + FE).

## Format

Same SemVer format with 2 digits for MINOR and PATCH:

```
1.50.00
1.73.00
1.74.01
```

Git tag: `v` prefix → `v1.74.00`.

## Product version calculation

**Rule:** `product = max(backend, frontend)` on release day (SemVer comparison).

Examples:

| Backend | Frontend | Product |
|---|---|---|
| `1.72.00` | `1.73.00` | `1.73.00` |
| `1.75.02` | `1.74.00` | `1.75.02` |
| `1.80.00` | `1.80.00` | `1.80.00` |

If a product bump is needed without component changes (e.g. only `docker-compose`, ops docs), bump the product PATCH manually and document it in the notes.

## Practical release flow

1. **Close backend** — compute BE SemVer and create `backend/CHANGELOGS/RELEASES/<be>.{ca,es,en}.md`.
2. **Close frontend** — compute FE SemVer and create `frontend/CHANGELOGS/RELEASES/<fe>.{ca,es,en}.md`.
3. **Compute product** — `product = max(be, fe)`.
4. **Joint notes** — create `RELEASES/<product>.{ca,es,en}.md` (see template).
5. **Release commit** — include all three deliverables (BE, FE, product).
6. **Annotated tag** on the release commit:

```bash
git tag -a v<product> -m "$(cat <<'EOF'
Product release <product>

- backend: <be>
- frontend: <fe>
EOF
)"
git push origin v<product>
```

7. **Deploy** always from the product tag (not from an ad-hoc `main` commit).

## Files

| File | Content |
|---|---|
| `RELEASES/README.{ca,es,en}.md` | This policy |
| `RELEASES/<version>.{ca,es,en}.md` | Product release notes |
| `RELEASES/PLAN_RELEASE_<version>.{ca,es,en}.md` | Optional: checklist / plan |
| `RELEASES/README.md` | Language index |

## Template `RELEASES/<version>.en.md`

```markdown
# Product release <version> — DD-MM-YYYY

| Component | Version |
|---|---|
| Backend | <be> |
| Frontend | <fe> |
| Tag | v<version> |

## Highlights

- …

## Component notes

- Backend: [`backend/CHANGELOGS/RELEASES/<be>.en.md`](../backend/CHANGELOGS/RELEASES/<be>.en.md)
- Frontend: [`frontend/CHANGELOGS/RELEASES/<fe>.en.md`](../frontend/CHANGELOGS/RELEASES/<fe>.en.md)

## Notes

- (incompatibilities, migrations, ConfigProject flags, etc.)
```

## Git tags

| Type | Convention | When |
|---|---|---|
| Product (required for a release) | `v1.74.00` | Every joint release |
| Component (optional) | `backend/1.72.00`, `frontend/1.73.00` | Only if extra traceability is needed |

Day-to-day, the product tag is enough for this monorepo.

## What not to do

- Force BE and FE to the same SemVer on every release.
- Tag by date only (`2026-07-21`) without a product version.
- Stop versioning BE/FE separately in their changelogs.
- Deploy a `main` commit without an associated product tag.
