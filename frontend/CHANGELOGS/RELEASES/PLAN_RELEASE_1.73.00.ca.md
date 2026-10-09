# Pla de release frontend `1.73.00`

[Català](./PLAN_RELEASE_1.73.00.ca.md) · [Español](./PLAN_RELEASE_1.73.00.es.md) · [English](./PLAN_RELEASE_1.73.00.en.md)

## Objectiu

Calcular i documentar la versió SemVer del frontend a partir dels changelogs diaris, amb la mateixa metodologia que el backend.

## Baseline acordada

| Camp | Valor |
|---|---|
| Dia | `05-05-2026` |
| Versió | `1.50.00` |
| Motiu | Primer dia amb changelog de control de canvis al frontend (alineat numèricament amb l'inici del control al backend) |

## Checklist

- [x] Documentar convenció a `CHANGELOGS/RELEASES/README.ca.md`
- [x] Transformar seccions històriques (`ADDED`/`FIXED`/`MODIFY`/`REMOVED` → `FEAT`/`FIX`/`CHORE`/`MODIFIED`)
- [x] Classificar `ADDED` en FEAT (producte visible) vs CHORE (dubte → CHORE)
- [x] Recórrer dies en ordre cronològic i aplicar bump
- [x] Generar `CHANGELOGS/RELEASES/1.73.00.ca.md`
- [ ] (Opcional) Actualitzar `package.json` → `"1.73.00"` quan producte ho demani
- [ ] (Opcional) Tag git `v1.73.00` quan producte ho demani

## Resultat del càlcul

- **Versió si es publica amb l'últim dia de changelog (`16-07-2026`): `1.73.00`**
- Dies amb bump FEAT (MINOR): 23
- Dies amb bump PATCH (`FIX`/`CHORE`/`MODIFIED`): 25
- Dies BREAKING: 0

## Notes

- El número **no cal** que coincideixi amb el backend (referència backend ≈ `1.81.00` a 17-07-2026); cada repo calcula el seu.
- Dies amb dos blocs `## [mateixa data]` es fusionen per al bump (el tipus més alt del dia mana una sola vegada).
