# Releases de producto (monorepo)

[Català](./README.ca.md) · [Español](./README.es.md) · [English](./README.en.md)

Esta carpeta documenta la **versión conjunta** del producto Aqua360 (backend + frontend) que se despliega junta desde el monorepo.

Las versiones de componente se siguen calculando por separado:

| Componente | Convención SemVer | Notas de release |
|---|---|---|
| Backend | [`backend/CHANGELOGS/RELEASES/README.es.md`](../backend/CHANGELOGS/RELEASES/README.es.md) | `backend/CHANGELOGS/RELEASES/<versión>.es.md` |
| Frontend | [`frontend/CHANGELOGS/RELEASES/README.es.md`](../frontend/CHANGELOGS/RELEASES/README.es.md) | `frontend/CHANGELOGS/RELEASES/<versión>.es.md` |

## Capas de versión

| Capa | Qué es | Dónde | Ejemplo |
|---|---|---|---|
| Componente backend | SemVer del changelog BE | `backend/CHANGELOGS/RELEASES/` | `1.72.00` |
| Componente frontend | SemVer del changelog FE | `frontend/CHANGELOGS/RELEASES/` | `1.73.00` |
| **Producto** | Versión conjunta etiquetada en git | `RELEASES/` + tag git | `v1.74.00` |

No se fuerza que backend y frontend tengan el mismo número. El tag git representa el **conjunto desplegable** (commit + BE + FE).

## Formato

Mismo formato SemVer con 2 dígitos en MINOR y PATCH:

```
1.50.00
1.73.00
1.74.01
```

Tag git: prefijo `v` → `v1.74.00`.

## Cálculo de la versión de producto

**Regla:** `product = max(backend, frontend)` el día del release (comparación SemVer).

Ejemplos:

| Backend | Frontend | Producto |
|---|---|---|
| `1.72.00` | `1.73.00` | `1.73.00` |
| `1.75.02` | `1.74.00` | `1.75.02` |
| `1.80.00` | `1.80.00` | `1.80.00` |

Si hace falta un bump de producto sin cambio de componentes (p. ej. solo `docker-compose`, docs de ops), se puede subir el PATCH de producto manualmente y documentarlo en las notas.

## Flujo práctico de release

1. **Cerrar backend** — calcular SemVer BE y crear `backend/CHANGELOGS/RELEASES/<be>.{ca,es,en}.md`.
2. **Cerrar frontend** — calcular SemVer FE y crear `frontend/CHANGELOGS/RELEASES/<fe>.{ca,es,en}.md`.
3. **Calcular producto** — `product = max(be, fe)`.
4. **Notas conjuntas** — crear `RELEASES/<product>.{ca,es,en}.md` (véase plantilla).
5. **Commit de release** — incluir los tres entregables (BE, FE, producto).
6. **Tag anotado** en el commit de release:

```bash
git tag -a v<product> -m "$(cat <<'EOF'
Release producto <product>

- backend: <be>
- frontend: <fe>
EOF
)"
git push origin v<product>
```

7. **Desplegar** siempre desde el tag de producto (no desde `main` “a ojo”).

## Archivos

| Archivo | Contenido |
|---|---|
| `RELEASES/README.{ca,es,en}.md` | Esta política |
| `RELEASES/<versión>.{ca,es,en}.md` | Notas de la release de producto |
| `RELEASES/PLAN_RELEASE_<versión>.{ca,es,en}.md` | Opcional: checklist / plan |
| `RELEASES/README.md` | Índice de idiomas |

## Plantilla `RELEASES/<versión>.es.md`

```markdown
# Release producto <versión> — DD-MM-YYYY

| Componente | Versión |
|---|---|
| Backend | <be> |
| Frontend | <fe> |
| Tag | v<versión> |

## Highlights

- …

## Notas de componente

- Backend: [`backend/CHANGELOGS/RELEASES/<be>.es.md`](../backend/CHANGELOGS/RELEASES/<be>.es.md)
- Frontend: [`frontend/CHANGELOGS/RELEASES/<fe>.es.md`](../frontend/CHANGELOGS/RELEASES/<fe>.es.md)

## Observaciones

- (incompatibilidades, migraciones, flags ConfigProject, etc.)
```

## Tags git

| Tipo | Convención | Cuándo |
|---|---|---|
| Producto (obligatorio en el release) | `v1.74.00` | Cada release conjunta |
| Componente (opcional) | `backend/1.72.00`, `frontend/1.73.00` | Solo si hace falta trazabilidad extra |

Para el día a día del monorepo basta con el tag de producto.

## Qué no hacer

- Forzar el mismo número SemVer en BE y FE en cada release.
- Etiquetar solo por fecha (`2026-07-21`) sin versión de producto.
- Dejar de versionar BE/FE por separado en sus changelogs.
- Desplegar un commit de `main` sin tag de producto asociado.
