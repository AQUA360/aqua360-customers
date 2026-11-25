# API de l'Oficina Virtual (OV) — documentació OpenAPI

Especificació OpenAPI 3.0 dels endpoints de l'Oficina Virtual, per a integradors.
Es pot importar a [Swagger Editor](https://editor.swagger.io), Postman o Redoc.

| Idioma | Fitxer |
|---|---|
| Castellà | [`openapi.yaml`](openapi.yaml) |
| Català | [`openapi.ca.yaml`](openapi.ca.yaml) |

## Mantenir les dues versions

**Qualsevol canvi a l'API de l'OV s'ha de fer a les dues versions** en el mateix
canvi: endpoints, paràmetres, esquemes, respostes, exemples i textos.

- Només es tradueixen els textos (`description`, `summary`, `title`, la introducció
  d'`info` i els noms de les etiquetes). Les claus, rutes, noms de camps, enums i
  exemples són idèntics a les dues versions: els exemples reprodueixen literalment
  el que retorna l'API.
- [`test_openapi_consistency.py`](test_openapi_consistency.py) ho comprova a les
  proves del backend: a cada versió, la taula de resum ha de quadrar amb `paths:`, i
  les dues versions han de tenir exactament la mateixa estructura. Si s'afegeix un
  endpoint o un camp només a una de les dues, el test falla.
