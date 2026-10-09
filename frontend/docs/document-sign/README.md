# Signatura OTP (DocumentSign)

Documentació del flux de signatura OTP de documents de contracte (Aqua360 Sign).

| Fitxer | Contingut |
|--------|-----------|
| [frontend-flow.md](./frontend-flow.md) | Què fa el frontend, on surt el widget i quins endpoints crida |
| [backend-endpoints.md](./backend-endpoints.md) | Contracte d’API confirmat amb backend |

**Plugin:** `plugins/api/documentmanager/document-sign-api.js` (`$DocumentSignApiService`)  
**Prefix:** `/documentmanager/`  
**Flag:** `DOCUMENT_SIGN_ENABLED` (`config-project`). Si és `false`, s’amaga el widget i la pàgina `/contract/document-signs/`.
