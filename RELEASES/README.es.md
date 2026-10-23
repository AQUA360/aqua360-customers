# Releases (monorepo)

[Català](./README.ca.md) · [Español](./README.es.md) · [English](./README.en.md)

Esta carpeta documenta las releases de Aqua360 Customers. Hay **una sola versión** para todo el monorepo (backend, frontend, Docker y documentación): es la que se etiqueta, se publica en GitHub y se despliega.

Las versiones de componente (backend `1.135.01`, frontend `1.123.00`) quedan congeladas como histórico en `backend/CHANGELOGS/RELEASES/` y `frontend/CHANGELOGS/RELEASES/`, y no se vuelven a calcular. La primera versión única parte de `1.135.02`.

## Formato

`MAJOR.MINOR.PATCH` con 2 dígitos en MINOR y PATCH:

```
1.136.00
1.136.01
```

El tag git lleva prefijo `v` → `v1.136.00`.

## Cálculo de la versión

El bump se calcula **día a día** sobre los dos changelogs juntos (`backend/CHANGELOGS/CURRENT_CHANGELOG.ca.md` y `frontend/CHANGELOGS/CURRENT_CHANGELOG.ca.md`), desde el último tag. Para cada día cuenta el tipo más alto de los dos ficheros:

| Sección del changelog | Conventional Commit | Bump |
|---|---|---|
| `### BREAKING` | `BREAKING CHANGE` | **MAJOR** (+1, MINOR y PATCH = `00`) |
| `### FEAT` | `feat` | **MINOR** (+1, PATCH = `00`) |
| `### FIX` | `fix` | **PATCH** (+1) |
| `### CHORE` | `chore` / `docs` / `ci` | **PATCH** (+1) |
| `### MODIFIED` | `refactor` / `perf` | **PATCH** (+1) |

Ejemplo: si el 20-10 el backend tiene `FIX` y el frontend `FEAT`, ese día cuenta como `FEAT`.

- Si solo cambian Docker, CI o documentación de operaciones, se sube el PATCH.
- Si el número que toca ya tiene tag, se salta al siguiente y se explica en las notas.

## Changelogs

Los `CURRENT_CHANGELOG.ca.md` se mantienen separados por área, porque cada equipo escribe en ellos su día a día; solo la versión es común.

- Un bloque `## [DD-MM-YYYY]` por día, con las secciones de la tabla anterior y el módulo (`#### BILLING`, `#### OV`…).
- Si es nuevo y visible para el usuario o la API → `FEAT`. Si es nuevo pero interno, de operaciones o un detalle → `CHORE`.
- Las entradas añadidas a un día ya etiquetado se mueven al día nuevo.
- Cuando cambia el mes, los bloques del mes cerrado pasan al archivo mensual `CHANGELOGS/<año>/<AAAAMM>_CHANGELOG.ca.md`.

## Flujo de release

1. **Calcular la versión** con los dos changelogs juntos (ver más arriba).
2. **Rama** `release/<versión>` desde `develop` actualizado.
3. **Cerrar los changelogs** de backend y frontend (y el archivo mensual si ha cambiado el mes).
4. **Notas** en `RELEASES/<versión>.{ca,es,en}.md` con la plantilla de abajo. Las tres lenguas dicen lo mismo.
5. **Commit** `release: v<versión>` y PR `release/<versión>` → `main`, revisada y fusionada a mano.
6. **Tag anotado** sobre el commit de fusión de `main`:

```bash
git checkout main && git pull
git tag -a v<versión> -m "Release v<versión>"
git push origin v<versión>
```

7. **GitHub Release** publicada (no en borrador) a partir del tag, para que el workflow Imatges construya las imágenes:

```bash
gh release create v<versión> --verify-tag --title "v<versión>" --notes-file RELEASES/<versión>.es.md
```

8. **PR `main` → `develop`** para que las notas y cualquier hotfix vuelvan a `develop`.
9. **Desplegar** siempre desde el tag (`CUSTOMERS_VERSION=v<versión>`), nunca desde un commit de `main` sin tag.

Un hotfix sale de `main`, sube el PATCH y sigue los pasos 4 a 8.

## Ficheros

| Fichero | Contenido |
|---|---|
| `RELEASES/README.{ca,es,en}.md` | Esta política (un fichero por idioma) |
| `RELEASES/README.md` | Índice de idiomas |
| `RELEASES/<versión>.{ca,es,en}.md` | Notas de la release |
| `RELEASES/PLAN_RELEASE_<versión>.{ca,es,en}.md` | Opcional: checklist o plan de releases grandes |

Ya no se crean ficheros en `backend/CHANGELOGS/RELEASES/` ni en `frontend/CHANGELOGS/RELEASES/`.

## Plantilla `RELEASES/<versión>.es.md`

```markdown
# Release v<versión> — DD-MM-YYYY

[Català](./<versión>.ca.md) · [Español](./<versión>.es.md) · [English](./<versión>.en.md)

Baseline: `v<versión anterior>` (DD-MM-YYYY).

## Tabla día → bump → versión

| Día | Backend | Frontend | Bump | Versión |
|---|---|---|---|---|
| DD-MM-YYYY | — | — | `BASELINE` | `<versión anterior>` |
| DD-MM-YYYY | FIX | FEAT | `FEAT` | `<…>` |
| DD-MM-YYYY | FIX | — | `PATCH` | **`<versión>`** |

## Highlights

- …

## Cambios

### Backend

- FEAT: …
- FIX: …

### Frontend

- FEAT: …
- FIX: …

## Observaciones

- Migraciones: <lista> o «Sin migraciones».
- Variables de entorno, ConfigProject, opscripts e incompatibilidades.
- Imágenes: con `CUSTOMERS_VERSION=v<versión>` en el `.env`, `docker compose pull && docker compose up -d`.
```

## Qué no hacer

- Volver a calcular versiones separadas de backend y frontend.
- Calcular el bump solo con uno de los dos changelogs.
- Etiquetar antes de fusionar las notas en `main`, o con un tag ligero (sin `-a`).
- Reutilizar un número ya etiquetado.
- Dejar la GitHub Release en borrador.
- Desplegar un commit de `main` sin tag.
