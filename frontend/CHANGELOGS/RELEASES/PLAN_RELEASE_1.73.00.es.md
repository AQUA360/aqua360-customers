# Plan de release frontend `1.73.00`

[Català](./PLAN_RELEASE_1.73.00.ca.md) · [Español](./PLAN_RELEASE_1.73.00.es.md) · [English](./PLAN_RELEASE_1.73.00.en.md)

## Objetivo

Calcular y documentar la versión SemVer del frontend a partir de los changelogs diarios, con la misma metodología que el backend.

## Baseline acordada

| Campo | Valor |
|---|---|
| Día | `05-05-2026` |
| Versión | `1.50.00` |
| Motivo | Primer día con changelog de control de cambios en el frontend (alineado numéricamente con el inicio del control en el backend) |

## Checklist

- [x] Documentar convención en `CHANGELOGS/RELEASES/README.{ca,es,en}.md`
- [x] Transformar secciones históricas (`ADDED`/`FIXED`/`MODIFY`/`REMOVED` → `FEAT`/`FIX`/`CHORE`/`MODIFIED`)
- [x] Clasificar `ADDED` en FEAT (producto visible) vs CHORE (duda → CHORE)
- [x] Recorrer días en orden cronológico y aplicar bump
- [x] Generar `CHANGELOGS/RELEASES/1.73.00.{ca,es,en}.md`
- [ ] (Opcional) Actualizar `package.json` → `"1.73.00"` cuando producto lo pida
- [ ] (Opcional) Tag git de producto cuando producto lo pida

## Resultado del cálculo

- **Versión si se publica con el último día de changelog (`16-07-2026`): `1.73.00`**
- Días con bump FEAT (MINOR): 23
- Días con bump PATCH (`FIX`/`CHORE`/`MODIFIED`): 25
- Días BREAKING: 0

## Notas

- El número **no tiene** que coincidir con el backend (referencia backend ≈ `1.81.00` a 17-07-2026); cada capa calcula la suya.
- Días con dos bloques `## [misma fecha]` se fusionan para el bump (el tipo más alto del día manda una sola vez).
