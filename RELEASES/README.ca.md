# Releases (monorepo)

[Català](./README.ca.md) · [Español](./README.es.md) · [English](./README.en.md)

Aquesta carpeta documenta les releases d'Aqua360 Customers. Hi ha **una sola versió** per a tot el monorepo (backend, frontend, Docker i documentació): és la que es tageja, es publica a GitHub i es desplega.

Les versions de component (backend `1.135.01`, frontend `1.123.00`) queden congelades com a històric a `backend/CHANGELOGS/RELEASES/` i `frontend/CHANGELOGS/RELEASES/`, i no es tornen a calcular. La primera versió única parteix de `1.135.02`.

## Format

`MAJOR.MINOR.PATCH` amb 2 dígits al MINOR i al PATCH:

```
1.136.00
1.136.01
```

El tag git porta prefix `v` → `v1.136.00`.

## Càlcul de la versió

El bump es calcula **dia a dia** sobre els dos changelogs junts (`backend/CHANGELOGS/CURRENT_CHANGELOG.ca.md` i `frontend/CHANGELOGS/CURRENT_CHANGELOG.ca.md`), des del darrer tag. Per a cada dia compta el tipus més alt dels dos fitxers:

| Secció del changelog | Conventional Commit | Bump |
|---|---|---|
| `### BREAKING` | `BREAKING CHANGE` | **MAJOR** (+1, MINOR i PATCH = `00`) |
| `### FEAT` | `feat` | **MINOR** (+1, PATCH = `00`) |
| `### FIX` | `fix` | **PATCH** (+1) |
| `### CHORE` | `chore` / `docs` / `ci` | **PATCH** (+1) |
| `### MODIFIED` | `refactor` / `perf` | **PATCH** (+1) |

Exemple: si el 20-10 el backend té `FIX` i el frontend `FEAT`, aquell dia compta com a `FEAT`.

- Si només canvien Docker, CI o documentació d'operacions, es puja el PATCH.
- Si el número que toca ja té tag, se salta al següent i s'explica a les notes.

## Changelogs

Els `CURRENT_CHANGELOG.ca.md` es mantenen separats per àrea, perquè cada equip hi escriu el seu dia a dia; només la versió és comuna.

- Un bloc `## [DD-MM-YYYY]` per dia, amb les seccions de la taula anterior i el mòdul (`#### BILLING`, `#### OV`…).
- Si és nou i visible per a l'usuari o l'API → `FEAT`. Si és nou però intern, d'operacions o un detall → `CHORE`.
- Les entrades afegides a un dia ja tagejat es mouen al dia nou.
- Quan canvia el mes, els blocs del mes tancat passen a l'arxiu mensual `CHANGELOGS/<any>/<AAAAMM>_CHANGELOG.ca.md`.

## Flux de release

1. **Calcular la versió** amb els dos changelogs junts (vegeu més amunt).
2. **Branca** `release/<versió>` des de `develop` actualitzat.
3. **Tancar els changelogs** de backend i frontend (i l'arxiu mensual si ha canviat el mes).
4. **Notes** a `RELEASES/<versió>.{ca,es,en}.md` amb la plantilla de sota. Les tres llengües diuen el mateix.
5. **Commit** `release: v<versió>` i PR `release/<versió>` → `main`, revisada i fusionada a mà.
6. **Tag anotat** sobre el commit de fusió de `main`:

```bash
git checkout main && git pull
git tag -a v<versió> -m "Release v<versió>"
git push origin v<versió>
```

7. **GitHub Release** publicada (no en esborrany) a partir del tag, perquè el workflow Imatges construeixi les imatges:

```bash
gh release create v<versió> --verify-tag --title "v<versió>" --notes-file RELEASES/<versió>.ca.md
```

8. **PR `main` → `develop`** perquè les notes i qualsevol hotfix tornin a `develop`.
9. **Desplegar** sempre des del tag (`CUSTOMERS_VERSION=v<versió>`), mai des d'un commit de `main` sense tag.

Un hotfix surt de `main`, puja el PATCH i segueix els passos 4 a 8.

## Fitxers

| Fitxer | Contingut |
|---|---|
| `RELEASES/README.{ca,es,en}.md` | Aquesta política (un fitxer per idioma) |
| `RELEASES/README.md` | Índex d'idiomes |
| `RELEASES/<versió>.{ca,es,en}.md` | Notes de la release |
| `RELEASES/PLAN_RELEASE_<versió>.{ca,es,en}.md` | Opcional: checklist o pla de releases grans |

Ja no es creen fitxers a `backend/CHANGELOGS/RELEASES/` ni a `frontend/CHANGELOGS/RELEASES/`.

## Plantilla `RELEASES/<versió>.ca.md`

```markdown
# Release v<versió> — DD-MM-YYYY

[Català](./<versió>.ca.md) · [Español](./<versió>.es.md) · [English](./<versió>.en.md)

Baseline: `v<versió anterior>` (DD-MM-YYYY).

## Taula dia → bump → versió

| Dia | Backend | Frontend | Bump | Versió |
|---|---|---|---|---|
| DD-MM-YYYY | — | — | `BASELINE` | `<versió anterior>` |
| DD-MM-YYYY | FIX | FEAT | `FEAT` | `<…>` |
| DD-MM-YYYY | FIX | — | `PATCH` | **`<versió>`** |

## Highlights

- …

## Canvis

### Backend

- FEAT: …
- FIX: …

### Frontend

- FEAT: …
- FIX: …

## Observacions

- Migracions: <llista> o «Sense migracions».
- Variables d'entorn, ConfigProject, opscripts i incompatibilitats.
- Imatges: amb `CUSTOMERS_VERSION=v<versió>` al `.env`, `docker compose pull && docker compose up -d`.
```

## Què no fer

- Tornar a calcular versions separades de backend i frontend.
- Calcular el bump només amb un dels dos changelogs.
- Tagejar abans de fusionar les notes a `main`, o amb un tag lleuger (sense `-a`).
- Reutilitzar un número ja tagejat.
- Deixar la GitHub Release en esborrany.
- Desplegar un commit de `main` sense tag.
