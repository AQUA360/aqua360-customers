# Releases de producte (monorepo)

[Català](./README.ca.md) · [Español](./README.es.md) · [English](./README.en.md)

Aquesta carpeta documenta la **versió conjunta** del producte Aqua360 (backend + frontend) que es desplega junts des del monorepo.

Les versions de component es continuen calculant per separat:

| Component | Convenció SemVer | Notes de release |
|---|---|---|
| Backend | [`backend/CHANGELOGS/RELEASES/README.ca.md`](../backend/CHANGELOGS/RELEASES/README.ca.md) | `backend/CHANGELOGS/RELEASES/<versió>.{ca,es,en}.md` |
| Frontend | [`frontend/CHANGELOGS/RELEASES/README.ca.md`](../frontend/CHANGELOGS/RELEASES/README.ca.md) | `frontend/CHANGELOGS/RELEASES/<versió>.{ca,es,en}.md` |

## Capes de versió

| Capa | Què és | On | Exemple |
|---|---|---|---|
| Component backend | SemVer del changelog BE | `backend/CHANGELOGS/RELEASES/` | `1.72.00` |
| Component frontend | SemVer del changelog FE | `frontend/CHANGELOGS/RELEASES/` | `1.73.00` |
| **Producte** | Versió conjunta que es tageja a git | `RELEASES/` + tag git | `v1.74.00` |

No es força que backend i frontend tinguin el mateix número. El tag git representa el **conjunt desplegable** (commit + BE + FE).

## Format

Mateix format SemVer amb 2 dígits al MINOR i PATCH:

```
1.50.00
1.73.00
1.74.01
```

Tag git: prefix `v` → `v1.74.00`.

## Càlcul de la versió de producte

**Regla:** `product = max(backend, frontend)` el dia del release (comparació SemVer).

Exemples:

| Backend | Frontend | Producte |
|---|---|---|
| `1.72.00` | `1.73.00` | `1.73.00` |
| `1.75.02` | `1.74.00` | `1.75.02` |
| `1.80.00` | `1.80.00` | `1.80.00` |

Si cal un bump de producte sense canvi de components (p. ex. només `docker-compose`, docs d’ops), es pot pujar el PATCH de producte manualment i documentar-ho a les notes.

## Flux pràctic de release

1. **Tancar backend** — calcular SemVer BE i crear `backend/CHANGELOGS/RELEASES/<be>.{ca,es,en}.md`.
2. **Tancar frontend** — calcular SemVer FE i crear `frontend/CHANGELOGS/RELEASES/<fe>.{ca,es,en}.md`.
3. **Calcular producte** — `product = max(be, fe)`.
4. **Notes conjuntes** — crear `RELEASES/<product>.{ca,es,en}.md` (vegeu plantilla).
5. **Commit de release** — incloure els tres deliverables (BE, FE, producte).
6. **Tag anotat** al commit de release:

```bash
git tag -a v<product> -m "$(cat <<'EOF'
Release producte <product>

- backend: <be>
- frontend: <fe>
EOF
)"
git push origin v<product>
```

7. **Desplegar** sempre des del tag de producte (no des de `main` “a ull”).

## Fitxers

| Fitxer | Contingut |
|---|---|
| `RELEASES/README.{ca,es,en}.md` | Aquesta política (un fitxer per idioma) |
| `RELEASES/<versió>.{ca,es,en}.md` | Notes de la release de producte |
| `RELEASES/PLAN_RELEASE_<versió>.{ca,es,en}.md` | Opcional: checklist / pla |
| `RELEASES/README.md` | Índex d’idiomes |

## Plantilla `RELEASES/<versió>.ca.md`

```markdown
# Release producte <versió> — DD-MM-YYYY

| Component | Versió |
|---|---|
| Backend | <be> |
| Frontend | <fe> |
| Tag | v<versió> |

## Highlights

- …

## Notes de component

- Backend: [`backend/CHANGELOGS/RELEASES/<be>.ca.md`](../backend/CHANGELOGS/RELEASES/<be>.ca.md) (també `.es.md` / `.en.md`)
- Frontend: [`frontend/CHANGELOGS/RELEASES/<fe>.ca.md`](../frontend/CHANGELOGS/RELEASES/<fe>.ca.md) (també `.es.md` / `.en.md`)

## Observacions

- (incompatibilitats, migracions, flags ConfigProject, etc.)
```

## Tags git

| Tipus | Convenció | Quan |
|---|---|---|
| Producte (obligatori al release) | `v1.74.00` | Cada release conjunta |
| Component (opcional) | `backend/1.72.00`, `frontend/1.73.00` | Només si cal traçabilitat extra |

Per al dia a dia del monorepo n’hi ha prou amb el tag de producte.

## Què no fer

- Forçar el mateix número SemVer a BE i FE cada release.
- Tagejar només per data (`2026-07-21`) sense versió de producte.
- Deixar de versionar BE/FE per separat als seus changelogs.
- Desplegar un commit de `main` sense tag de producte associat.
