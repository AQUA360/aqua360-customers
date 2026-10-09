# Changelog Backend

## [30-06-2026]

### FEAT
#### BILLING
    - ReadingDocumentNotFound guarda els valors de les lectures entrades per fitxer que NO ha trobat pas un comptador o relació per afegir

#### INTEGRATIONS
- **Nova app Django `integrations`**: Centralitza integracions externes del PA amb paquets interns `outbound/` (crides cap a tercers) i `inbound/` (webhooks entrants). Inclou el model `IntegrationRequestLog` per registrar crides HTTP i consulta des de l'admin.
- **Integració Giswater (outbound)**: Client OAuth via Keycloak, consulta de connecs (`GET /basic/getlist`), sincronització cap a `Connection` i commands `validate_giswater_auth`, `fetch_giswater_connecs` i `sync_giswater_connections`. Tasques Celery opcionals.
- **Integració Aqua360 Sign (outbound + inbound)**: Enviament del PDF d'una `ContractRequest` a signar (`POST /contract/contract-request/{id}/send-for-signing/`), webhook `POST /signing/callback/` amb autenticació `X-API-Key`, model `ContractSigningSession` i command `send_contract_request_for_signing`. El PDF es genera en memòria via `contract/utils/contract_pdf_service.py` i el document signat es desa a `ContractRequest.contract_file`.
- **Integració Giswater (inbound)**: Endpoints perquè Giswater (o altres tercers) consultin dades del PA:
  - `GET /giswater/contracts/`: export de tots els contractes amb connexió (`supply_point_default.connection`), punt de subministrament (adreça, comptador) i titular.
  - `GET /giswater/contracts/{token}/readings/`: lectures actives del contracte (`is_active=true`), ordenades per `reading_date` descendent, amb consum i dades de facturació.
  - Registre de crides a `IntegrationRequestLog` (provider `giswater`, direction `inbound`).
  - Especificació OpenAPI per a tercers: `integrations/inbound/giswater/openapi.yaml`.
  - Tests: `integrations.inbound.giswater.tests`.
- **Documentació**: Detall de configuració, fluxos, endpoints, commands i tests a `docs/integrations.md` (seccions Giswater outbound, Giswater inbound i Aqua360 Sign).

#### STATISTICS
- **Noves columnes a l'informe d'impagats global (`generate_wallet_all_unpaid_summary`)**: S'han afegit tres columnes noves a la pestanya de detall de l'Excel ("Detall rebuts"):

### CHORE
#### INTEGRATIONS
  - Autenticació amb token DRF d'usuari Django (`Authorization: Token …`); no cal login si el client rep el token directament.

#### STATISTICS
  - **NOM TITULAR**: nom i cognoms del titular del contracte associat al pagament.
  - **VIA DE COMUNICACIÓ**: tipus de comunicació del contracte (`Email` si és `DIGITAL`/`BOTH`, `Postal` si és `PAPER`/`PHYSICAL`).
  - **VALOR VIA DE COMUNICACIÓ**: adreça de correu electrònic (si comunicació digital) o adreça postal del punt de subministrament (si comunicació postal).
  - S'ha ampliat el `select_related` per incloure `holder` i `person_contact_email` del contracte en les tres cadenes possibles (via `invoice`, `commitment_deposit` o directe).

### MODIFIED
#### CLAIM REQUEST
    - S'ha afegit l'opció de poder lligar documents als passos de gestions de impagats i de seleccionar X contractes en específic per demanar sols. de vulnerabilitat.
    - S'han modificat i afegit camps al excel de sol. de vulnerabilitat

#### SERVICE
    - S'ha canviat el serializer de la llista d'ordres i es torna a fer servir per un un list

#### CONTRACT
- **Dades dinàmiques al PDF del contracte (`contract_template.html` i `contract_template_personalized.html`)**: S'han substituït els valors estàtics per variables dinàmiques a la secció "Característiques de la instal·lació i cabal contractat":
  - **Tipus d'ús**: obtingut de `contract_request.use_type.name` (model `ContractUseType`).
  - **Cabal contractat, Referència butlletí, Data butlletí, Cèdula d'habitabilitat núm. i Data cèdula**: obtinguts dels registres `ContractRequestDocumentation` associats al contracte, indexats pel camp `token` de `ContractDocumentationType` (`cabal_contractat`, `butlleti_instalador`, `data_butlleti`, `cedula_habitabilitat`, `data_cedula`).
  - **Data publicació BOP**: obtinguda de la cadena `price_rates → ContractPriceRate → PriceRate.billing_range_active → BillingRange.publication → Publication.boe_date`.
  - **Correcció de la query `documentation_texts`**: S'ha corregit un bug on es filtrava per `contract_request=X AND contract=None` simultàniament (retornava sempre 0 resultats). Ara s'usa la condició correcta segons si l'objecte és `Contract` o `ContractRequest`. També s'ha corregit la lectura del token de document, que usava el camp `type` (sempre `None`) en lloc del camp correcte `contract_type`.

### FIX
#### READING
    - **Reduir construcció payload smart metering**:Reduir la carga útil (payload) del backend al frontend per mostrar les dades de lectura de smart metering.
    - Canviar que en processar el lot, la comprovació dels valors, si era 0 o 1, es comportava com a booleà, però el que voliem mirar es si contenia valor, per lo tant s'han canviar les condicions del condicional per revisar que la lectura no sigui None. 

#### BILLING
- **Correcció del format del fitxer WinCen (amplada de camps i caràcters no vàlids)**: S'han corregit tres problemes en la generació del fitxer d'exportació WinCen (`wincen_service.py`):
  - **Desbordament de camps**: `ljust` i `rjust` no truncaven valors que superaven l'amplada reservada, fent que les línies sobrepassessin els 154 caràcters i desplaçaven tots els camps posteriors (dates, lectures, imports). S'han afegit els helpers `_fixed_left` i `_fixed_right` que garanteixen amplada exacta truncant amb `[:width]` abans de justificar.
  - **Barres i espais al codi de factura**: El camp `invoice` (14 caràcters) ara elimina les barres `/` i els espais del valor `serie_final`/`token` abans d'escriure'l al fitxer, evitant identificadors amb caràcters no vàlids.
  - **Farciment amb zeros**: Els camps d'explotació (4 car.), contracte (8 car.) i factura (14 car.) ara s'omplen amb zeros a l'esquerra (`zfill`) quan el valor és curt, en lloc d'espais, seguint el mateix criteri que els camps numèrics.
- **Script de validació del fitxer WinCen (`wincen_validator.py`)**: Nou script autònom per validar i extreure les dades d'un fitxer `.dat` WinCen. Comprova que cada línia tingui exactament 154 caràcters, parseja tots els camps (strings, dates, enters, imports en cèntims) i mostra un resum amb errors, total de línies i suma d'imports. Admet l'opció `--csv <fitxer>` per exportar totes les dades extretes a CSV.
- **Correcció de corrector d'unitats**: S'ha arreglat el funcionament del corrector d'unitats per poder multiplicar el valor per un factor, només en preu fix de moment.

## [29-06-2026]

### FEAT
#### CONTRACT
- **Nou endpoint `POST /contract/contract/<id>/save-documentation/`**: Permet crear un registre de documentació (`ContractRequestDocumentation`) associat a un contracte sense fitxer adjunt, acceptant els camps `contract_type` i `text`. Retorna el `ContractSerializer` complet.
- **Nou endpoint `POST /contract/contract-request/<id>/save-documentation/`**: Equivalent a l'anterior però per a sol·licituds de contracte. Crea un `ContractRequestDocumentation` vinculat a la `ContractRequest` i retorna el `ContractRequestSerializer` complet.
- **Camp `text` a `ContractRequestDocumentation`**: S'ha afegit el camp `text` (`CharField`, màx. 500 caràcters, nullable) al model `ContractRequestDocumentation` per emmagatzemar una descripció o anotació textual associada a cada document. Migració `0226_add_text_to_contractrequestdocumentation` aplicada. El camp s'inclou automàticament a la resposta del serialitzador (`fields = '__all__'`).

### MODIFIED
#### CONTRACT
- **Unificació de logs de contracte a un sol endpoint**: L'endpoint `GET /contract/contract/<id>/logs/` ara retorna conjuntament els registres de `ContractLog` i `ContractDataChange` en un únic array pla ordenat per `created_at` descendent, eliminant la necessitat de fer múltiples crides des del frontend. Cada entrada inclou sempre els camps `id` (únic, amb prefix `log_` o `dc_`), `created_at`, `field_name`, `old_value`, `new_value`, `operation_token`, `user` i `source` (`"log"` o `"data_change"`). Els registres duplicats (mateix `field_name` i `created_at` a menys de 5 segons de diferència entre les dues taules) es deduplicen automàticament, mantenint l'entrada de `data_change` i descartant el `log` redundant.
- **Endpoints `save-file` de contracte i sol·licitud de contracte**: Corregit l'error `AttributeError: This QueryDict instance is immutable` en llegir els fitxers ara directament de `request.FILES` en lloc de copiar el `QueryDict`. Afegit el camp `text` al multipart per associar una anotació textual al document pujat.

### FIX
#### BILLING
- **`TypeError` a `process_billing_batch` per `consumption_days` nul**: Corregit un error de producció (`TypeError: unsupported operand type(s) for +=: 'int' and 'NoneType'`) a `invoice_service.py` quan `reading.previous_reading.previous_reading.consumption_days` és `None`. Ara s'utilitza `or 0` com a fallback.

#### READINGS/SAMRT METERING
    - modificar el retorn de les dades de lectures de l'smart metering al front per poder veure el titular (holder) del contracte i treure la ciutat (city) de l'adreça del punt de subminstrament

## [26-06-2026]

### FIX
#### BILLING
    - **Comptatge de contractes sense comptador a `check-missing`**: L'endpoint `/billing/billing/<id>/check-missing/` ara compta i retorna el camp `no_meter` al resum de resposta, indicant quants contractes no s'han pogut facturar per manca de comptador actiu al punt de subministrament.
    - **Correcció del format del fitxer WinCen**: S'ha corregit la generació del fitxer d'exportació WinCen perquè les columnes es concatenin sense separadors (format de 154 caràcters fix), en lloc de separar-les per espais. S'ha afegit el diccionari `_W` amb les amplades de cada columna, s'ha eliminat el helper `_str_field` redundant i s'han simplificat les consultes `select_related` eliminant relacions no necessàries.
    - **`AttributeError` a `/billing/general-payment-sepa-document/`**: Corregit un error quan `general_payment.IBAN` i `general_payment.company_iban` són `None` i s'intentava accedir a `person_bank.name`. Ara s'utilitza el `folder_name` ja calculat amb tots els fallbacks.
    - **Camps `name` i `token` a `reading-batch-summary`**: L'endpoint `GET /billing/reading-batch-summary/?batch_id=<id>` ara retorna els camps `name` i `token` del lot de lectura a més de l'`id`.
    - **Data passada a remeses SEPA amb dia preferent de cobrament**: Quan es genera una remesa amb `use_remittance_date=True` i el dia preferent del contracte (`remittance_date`) ja ha passat en el mes de referència, la `ReqdColltnDt` del fitxer SEPA ara avança automàticament al mateix dia del mes següent, evitant el rebuig bancari per data passada. Corregit també un `NameError` per `today` no definit en el scope de `get_sepa_payments_and_batches` que impedia que l'agrupació per dia preferent funcionés correctament, generant una única remesa en lloc de separar-les per data.

## [25-06-2026]

### FIX
#### READINGS
    - Quan es modifiquen les lectures, afegir la conmprovació que que si no té previous_estimated_used per defecte posi 0 per poder comprar el valor i no salti l'error.

### FEAT
#### BILLING
    - Nou endpoint `POST /api/reading/recalculate-estimated/` per recalcular un llistat de lectures estimades. Torna a executar l'algorisme d'estimació (mitjana diària estadística × dies de consum) per a cada lectura indicada, actualitza el `calculated_value` i el `reading_value`, i sincronitza els moviments de la bossa d'estimades (`EstimatedBag` i `EstimatedBagMovement`) amb el nou valor calculat.
    - **Regeneració massiva de PDFs de facturació**: Nou endpoint `POST /api/billing/billing/<id>/regenerate-pdfs` que encua una tasca de tipus `REGENERATE_PDFS` a la `BillingQueue` per regenerar tots els PDFs de les factures actives d'una facturació. La tasca s'executa de forma seqüencial respectant la cua existent (no arrenca si hi ha una altra tasca en curs). El progrés es pot consultar amb `GET /api/billing/billing/regenerate-pdfs/status/<task_id>/`, que retorna `state`, `current`, `total` i `percent`.
    - **Nou `task_type` a `BillingQueue`**: S'ha afegit el tipus `REGENERATE_PDFS` ("Regeneració de PDFs de factures") als tipus de tasca de la cua de facturació.
    - **Exportació fitxer WinCen**: Nou endpoint `POST /api/billing/billing/<id>/wincen-export` que encua una tasca de tipus `WINCEN_EXPORT` a la `BillingQueue` per generar el fitxer d'exportació WinCen (format pipe-delimitat) amb tots els registres `ABONA`, `COMPT`, `LECTU`, `FACTU`, `LINFA` i `PAGAM` de les factures actives d'una facturació. Un cop finalitzada la tasca, el fitxer es desa com a `Document` al gestor documental via `save_report` i la URL permanent es persisteix al camp `file_url` del `BillingQueue`. El progrés es consulta amb `GET /api/billing/billing/wincen-export/status/<queue_item_id>/`, que retorna `status`, `current`, `total`, `percent` i `file_url`.
    - **Nou camp `file_url` a `BillingQueue`**: S'ha afegit el camp `file_url` (TextField nullable) per persistir la URL de descàrrega dels fitxers generats per tasques de tipus exportació (com `WINCEN_EXPORT`), evitant dependre de la caducitat dels resultats Celery.

#### STATISTICS
    - **Seguiment de progrés en temps real a `update-daily-consumption`**: La tasca Celery `calculate_median_consumption` ara crida `self.update_state()` cada 50 contractes (i al final) amb l'estat `PROGRESS` i les claus `current`, `total` i `percent`. S'ha afegit el nou endpoint `GET /api/statistics/task-status/<task_id>/` que retorna l'estat i el percentatge de progrés d'una tasca Celery a partir del seu `task_id`, permetent al front actualitzar la barra de progrés en temps real.

### MODIFIED
#### BILLING
    - El camp `use_type_final` ara s'inclou a la resposta de l'endpoint `GET /api/billing/billing/<id>/invoices`, retornant l'`id`, `token` i `name` del tipus d'ús del contracte associat a cada factura.

## [23-06-2026]

### FEAT
#### SERVICE
    - S'han afegit valor per diferenciar ABGAR i SMART METERING dels comptadors de telelectura. També un valor que un cop el comptador s'afegeix de telelectura SEMPRE quedarà com a true per poder cercar i tenir històric. També permet filtrar per aquests valors

#### STATISTICS
- **Cua seqüencial de reports (`ReportQueue`)**: S'ha creat un model de cua a la base de dades i un sistema asíncron mitjançant Celery per gestionar la cua d'informes de forma seqüencial, evitant sobrecarregar la CPU de l'aplicació. Disposa d'endpoints de seguiment del progrés en temps real (`GET /api/statistics/report-queue/` i `GET /api/statistics/report-queue/<id>/`) i lligam amb els documents generats per a la descàrrega final.

#### READINGS
    - Afegir obtenir i desar dades de l'Smart Metering en un data concreta + afegir la configuració per poder enllaçar l'smart metering amb el programa d'abonats

### CHORE
#### BILLING
    - Actualitzar comptadors de smart metering 'import_meter_change_smart_metering' i 'update_meter_remote_reading_smart_metering'
    - Al calcular els contractes pendents de facturar d'un billing, ara s'exclouen també les lectures que ja tenen un pressupost associat (`type_final='P'`), no només les que tenen factura definitiva (`type_final='F'`)

#### MIGRATION
    - Afegir una migració de token de l'Smart Metering per defecte amb valor null.

### MODIFIED
#### COMMUNICATION
    - Ara els esborranys de procés de comunicació per lectures va separat per explotació
    - Si no trobat from_email (mail_send_user) fer servir el bàsic (mail_send_mail)
#### PROMETEO
    - ConfigProject treure la clau: token_price_rate_aca_dom i millorar descripcions.

#### STATISTICS
- **Seguiment de progrés a Celery en temps real per a informes**: S'ha adaptat la tasca de Celery per detectar a través de reflexió (`inspect.signature`) si la funció generadora del report admet un paràmetre `task`. S'ha actualitzat el generador de l'informe de facturació detallada (`generate_register_billing_summary`) per acceptar-lo i actualitzar el progrés/percentatge de la tasca (`task.update_state`) periòdicament cada 50 factures.

### FIX
#### COREDATA
- **Canvi automàtic a comunicació per paper al treure el correu d'un abonat**: Si s'elimina un contacte de correu, es desactiva (`is_active=False`) o es desvincula de la persona (fins i tot si s'omet del llistat en desar la persona al endpoint `/coredata/person/<id>/`), els contractes relacionats es configuren automàticament amb tipus de comunicació per paper (`PAPER`) i es neteja el correu de contacte vinculat.

#### READINGS
    - Fer que les lectures de l'smart metering enllacin amb la lectura anterior, caluclin bé el nou consum i tingui el mateix comportament que el modificar lectures

#### BILLING
    - Al modificar lectures, si s'eliminen que es facin fora dels lots a on puguin estar. De igual manera, al lot de lectura filtrar les que estan actives
    - **Optimització de rendiment a l'endpoint `check-missing`**: S'ha reduït el temps de càrrega de l'endpoint d'inspecció de contractes no facturats (`/billing/billing/<id>/check-missing/`) de més de 30 segons a valors gairebé instantanis mitjançant la simplificació de la query de cerca per evitar consultes niades `IN` i avaluant la llista de contractes un sol cop en memòria per evitar recalcular-la en les 6 consultes posteriors de base de dades.

#### STATISTICS
- **Propagació de metadades de l'informe a la cua**: Corregit el flux de generació d'informes asíncrons (`run_report_task`) perquè la tasca de Celery obtingui el nom i el `type_id` de l'informe des del model `AvailableReport` vinculat a la cua i els injecti al payload. Això evita que els registres de `GeneralReport` es desin amb nom buit (`""`) i tipus `null`.

## [22-06-2026]

### FIX
#### BILLING
- **Inconsistència de comptadors entre `reading/by-batch-minimal/` i `reading-batch-summary/`**: El filtre `billed=true` del llistat de lectures per lot comptava qualsevol lectura amb factura associada (incloent provisionals `type_final='P'`), mentre que el camp `already_billed` del resum de lot només comptava factures definitives (`type_final='F'`). Corregit el filtre `filter_billed` a `reading_filter.py` perquè `billed=true` retorni únicament lectures amb factura definitiva i `billed=false` retorni les pendents (sense factura o amb provisional).

### MODIFIED
#### COMMUNICATION
    - Passed get communication process data to celery task

#### BILLING
    - Al abonar una factura, NO genera moviment a la propia factura sino només al abonament (en cas d'estar pagada)

### CHORE
#### WATCHDOG
- **Nou check `Factures amb Estat Inconsistent (Pagaments Pagats)`**: Detecta factures en un estat no pagat (Vençuda, Confirmada, Enviada, etc.) que tenen tots els seus pagaments associats en estat Pagat. Indica una inconsistència on el pagament ja s'ha registrat però l'estat de la factura no s'ha actualitzat correctament.
- **Nova comanda `watchdog_fix_invoice_status_from_payments`**: Corregeix les factures detectades pel check anterior actualitzant el seu estat a "Pagada". Suporta `--dry-run` per previsualitzar els canvis sense aplicar-los i `--id` per processar factures específiques (ex: `--id 123,456`).

## [19-06-2026]

### MODIFIED
#### BILLING
    - Modify reading keep previous estimated used reading

#### CLAIMREQUEST
    - Claim request (claim_manage_view.py) s'ha passat a CELERY
    - Petits canvis al save serializer de claim request, generació de claim_request_excel_generate_view.py
    - S'ha recuperat la generació de cartes de claim request a la comunicació

### CHORE
#### PRICING
- **Comanda `create_aca_publication_decret_2026`**: Nova comanda de gestió (`python manage.py create_aca_publication_decret_2026`) per crear la publicació del *Decret llei 3/2026, de 24 de març* i vincular-la automàticament als intervals de facturació (`BillingRange`) actius del cànon ACA (productes que continguin `CÀNON AIGUA (ACA)`) amb data d'inici posterior al 15/03/2026. La comanda també actualitza el camp `name` de cada `BillingRange` afectat amb el nom del decret. Suporta `--dry-run` per revisar els canvis sense aplicar-los. Si la publicació ja existeix (mateixa `reference`), no es torna a crear i simplement es revinculen els intervals.

### FIX
#### CONTRACT
- **Alertes de gestió de consums (`/contract/consumption-management/`)**: S'han corregit tres errors al `ConsumptionManagementViewSet`:
  - **`FieldError` en filtrar per `billing_batch`**: El lookup `billing__batch__id` era invàlid perquè `Billing` no té cap camp `batch`. Corregit a `billing__id`, que correspon directament al `billing_id` de la lectura.
  - **Determinació de lectures facturades**: El criteri per considerar una lectura com a "facturada" usava `billing__isnull=False` (lot de facturació), que és incorrecte. Ara es comprova si la lectura té alguna factura definitiva (via la relació M2M `invoices`) excloent les pre-factures (token `'1'`).
  - **Filtre `mode=current`**: Ara mostra lectures sense factura definitiva **i** posteriors a la data de l'última lectura amb factura definitiva del contracte, evitant que apareguin lectures antigues sense facturar anteriors a l'última facturació real.

### CHANGED
#### STATISTICS
- **Padró de facturació resumit (`statistics/billing/mini-register-billing-summary`)**: Redisseny de l'informe per incloure un desglossament per **tipus d'ús de contracte** (USE TYPE) en totes les files de mètriques (totals de m³, €, sense IVA) i en les files per producte/interval. Les columnes s'organitzen per explotació (si n'hi ha més d'una) amb subtotals per explotació i total general. Si només hi ha una explotació, no es mostra la fila d'explotació.
- **Padró de facturació principal (`statistics/billing/register-billing-summary`)**: S'han afegit dues columnes noves just després de `Periodicitat`:
  - **Tipus d'ús contracte**: nom del tipus d'ús del contracte (`use_type`).
  - **Ús ACA**: descripció llegible del codi ACA del contracte (`use_aca`), p.ex. "DOMÈSTICS", "INDUSTRIALS", etc.

### FEAT
#### SERVICE
- **Documentació adjunta a bateries (`ClusterDocumentationFile`)**: S'han afegit nous models i endpoints per gestionar fitxers adjunts a les bateries.
  - **Model `ClusterDocumentationType`** (`service/models.py`): Tipus de document per a bateries. Camps: `token`, `name`, `position`, `is_default`, `is_active`.
  - **Model `ClusterDocumentationFile`** (`service/models.py`): Fitxer adjunt vinculat a una bateria. FK a `Cluster`, FK a `Document` (documentmanager) i FK a `ClusterDocumentationType`. Camp `is_active` per a baixa lògica.
  - **Endpoint tipus de document** `GET|POST|PUT|DELETE /service/cluster-documentation-type/`: CRUD complet per gestionar els tipus de document de bateries. Inclou l'acció `POST /service/cluster-documentation-type/update-positions/` per reordenar.
  - **Endpoint upload** `PUT /service/cluster/{id}/save-file/`: Puja un fitxer associat a una bateria. Rep `file` (multipart) i `cluster_type` (id del `ClusterDocumentationType`). Retorna el serialitzador complet de la bateria incloent `documentation_files`.
  - **`ClusterSerializer`**: Ara retorna el camp `documentation_files` (llista d'objectes amb `id`, `file` {`id`, `document_name`, `file`, ...}, `type`, `is_active`).
- **Documentació adjunta a escomeses (`ConnectionDocumentationFile`)**: S'han afegit nous models i endpoints per gestionar fitxers adjunts a les escomeses.
  - **Model `ConnectionDocumentationType`** (`service/models.py`): Tipus de document per a escomeses. Camps: `token`, `name`, `position`, `is_default`, `is_active`.
  - **Model `ConnectionDocumentationFile`** (`service/models.py`): Fitxer adjunt vinculat a una escomesa. FK a `Connection`, FK a `Document` (documentmanager) i FK a `ConnectionDocumentationType`. Camp `is_active` per a baixa lògica.
  - **Endpoint tipus de document** `GET|POST|PUT|DELETE /service/connection-documentation-type/`: CRUD complet per gestionar els tipus de document d'escomeses. Inclou l'acció `POST /service/connection-documentation-type/update-positions/` per reordenar.
  - **Endpoint upload** `PUT /service/connection/{id}/save-file/`: Puja un fitxer associat a una escomesa. Rep `file` (multipart) i `connection_type` (id del `ConnectionDocumentationType`). Retorna el serialitzador complet de la escomesa incloent `documentation_files`.
  - **`ConnectionSerializer`**: Ara retorna el camp `documentation_files` (llista d'objectes amb `id`, `file` {`id`, `document_name`, `file`, ...}, `type`, `is_active`).
---

## [18-06-2026]

### FEAT
#### STATISTICS
    - S'afegit (de moment de manera bruta) un nou informe per declarar les factures al SGT

#### CONTRACT
    - **Filtre de mode històric/actual a la gestió de consums (`ConsumptionManagementViewSet`)**: S'ha afegit el paràmetre de consulta `mode` (`current` o `history`) a la gestió de consums per permetre filtrar les alertes (boques d'incendi, consums inactius i lectures duplicades) de manera que es pugui consultar o bé només les alertes posteriors a l'última facturació (`mode='current'`, per defecte) o bé tot l'historial d'alertes (`mode='history'`).

### CHORE
#### BILLING
    - **Comanda `rollback_sepa_remittance`**: Nova comanda de gestió (`python manage.py rollback_sepa_remittance <token>`) per revertir una remesa SEPA enviada. Reverteix l'estat dels pagaments a *Pendent* (netejant `paid_at` i `payment_date`), torna les factures associades a *Confirmada*, elimina els moviments de pagament generats per la remesa, desvincula els pagaments de la remesa i restableix la remesa a *Pendent d'enviament* — deixant tots els pagaments preparats per tornar a ser inclosos en una nova remesa. Suporta `--dry-run` per revisar els canvis sense aplicar-los i `--delete-remittance` per eliminar completament la remesa en lloc de restablir-la.

### FIX
#### BILLING
    - S'ha canviat l'ordre de l'escritura del fitxer de l'ACA que es genera mensualment

#### COMMUNICATIONS
    - Cambiar el filtre del contrador de les communcacions no enviades i que s'han d'enviar (remaining)
    - S'ha aplicat un filtre més mirant que les comunicacions no estiguin enviades en cas que no estiguin en un procés de comunicació, però volem enviar la seva comunicació.
    - **Càlcul d'alertes i lectures mancants al resum del lot de lectures**: S'ha corregit el comptatge de lectures amb alertes del lector/remotes, lectures sense valor i de punts de subministrament inactius fent servir un comptatge diferent per `supply_point_id` unívoc. També s'ha reescrit el càlcul de lectures mancants (`missing_readings`) perquè sigui consistent amb el llistat, calculant la diferència de conjunts de punts de subministrament del lot respecte als que tenen lectures reals i filtrant-los per contracte actiu.

## [17-06-2026]

### FEAT
#### CONTRACT
    - **Creació automàtica de comptador fictici en punts de subministrament sense comptador**: Quan es crea un contracte i algun punt de subministrament associat no té cap comptador assignat, ara es genera automàticament un comptador fictici amb codi `SC{yymmdd}{nnn}` (prefix `SC`, data del dia en format `yymmdd` i tres dígits autoincrementals basats en l'últim `id` de comptador). El comptador fictici s'assigna al punt de subministrament i rep l'estat "sense comptador" (`token_meter_status_no_meter`), de manera que la facturació, la generació de lots de lectures i la lecturapp el continuen excloent correctament.

### FIX
#### BILLING
    - **Assignació de `reject_date` en pagaments expirats**: A la tasca `check_payments_due_date`, quan un pagament passa a estat expirat, ara s'assigna també el camp `reject_date` amb la data de venciment original del pagament (`due_date`), no la data d'execució de la tasca. Això permet filtrar correctament els impagats per data de rebuig als informes de cartera.
    - **Vinculació de `previous_reading` en lectures estimades**: S'ha restaurat l'assignació del camp `previous_reading` (eliminat accidentalment al refactor del 20-04-2026) en crear o actualitzar lectures estimades a `get_estimated_reading_minimal_object`. Afecta tots els punts d'entrada d'estimació: endpoint manual, lots massius, facturació i estimació per contracte. Les lectures estimades generades amb boques d'incendi i aforaments també queden correctament vinculades a la lectura immediatament anterior no-control.
    - **Consum estimat d'aforaments**: Els aforaments (metres sense comptador acumulador, estat `no_meter_status`) ja no calculen el consum via estadística multi-anual, sinó que reutilitzen el `calculated_value` de l'última lectura no-control. Si no existeix cap lectura anterior, el consum s'estableix a 0.

#### STATISTICS
    - **Filtre per `reject_date` a `generate_wallet_all_unpaid_summary`**: L'informe d'impagats generals ara filtra els pagaments per `reject_date` (en lloc de `invoice__issue_date`) quan s'utilitza un rang de dates. Això fa que el filtre sigui coherent amb la data real de rebuig/expiració del pagament i amb el camp `reject_date` que ara s'assigna en la tasca de venciment.

#### CONTRACT
    - **Càrrega de la imatge de l'explotació i logo de l'empresa al PDF del contracte**: S'ha corregit la condició de càrrega de la imatge de l'explotació per comprovar que l'objecte té `id` vàlid. S'ha millorat la lògica de fallback del logo de l'empresa: si no té logo assignat, s'intenta obtenir el de la primera empresa disponible. S'ha adaptat la construcció del path del logo per suportar la variable `DOMAIN_MEDIA` (per a URLs remotes) a més del `MEDIA_ROOT` local, normalitzant el format del path independentment de si arriba com a URL o com a path relatiu.

### CHORE
#### BILLING
    - **Comanda `fix_estimated_readings_previous_reading`**: Nova comanda de gestió (`python manage.py fix_estimated_readings_previous_reading`) per corregir de forma retroactiva totes les lectures estimades existents que tenen `previous_reading` a NULL des del 20-04-2026. Busca la lectura no-control immediatament anterior per `supply_point` + `contract` i l'assigna. Suporta `--dry-run`, `--batch-id` i `--limit`.

#### COREDATA
    - **Filtre `has_streets` a ciutats**: S'ha afegit el filtre booleà `has_streets` al `CityFilter` per retornar únicament les ciutats que tenen almenys un carrer vinculat.

### MODIFIED
#### COREDATA
    - **Filtre de carrers per ciutat**: El filtre `city` de `StreetFilter` ara retorna els carrers de la ciutat indicada més tots els carrers sense `city_id` (no vinculats a cap municipi), per permetre seleccionar carrers genèrics no associats a una localitat concreta.
    - **Ordenació de carrers**: S'han afegit els camps `id` i `city__name` als `ordering_fields` de `StreetViewSet`, permetent ordenar el llistat de carrers per ID i per nom de la ciutat a més dels ja existents (nom i tipus).

#### PRICING
    - **Comanda `align_billing_ranges`**: La comanda ara filtra únicament les tarifes actives del producte "CÀNON AIGUA (ACA)" i restringeix la modificació a la data de fi del rang anterior al rang actiu actual, en lloc de recórrer i modificar tots els rangs en cadena.

## [16-06-2026]

### MODIFIED
#### BILLING
    - Al fer update d'una lectura des del serializer (vol dir que s'ha modificat des del lot de lectures) vol dir que ja tenen la lectura real. Busca i treu la bossa estimada i la modifica a real

### FEAT
#### BILLING
    - **Cua seqüencial de facturació (`BillingQueue`)**: S'ha creat una cua seqüencial a la base de dades per gestionar les tasques asíncrones de facturació i confirmació de documents, evitant la sobrecàrrega de la CPU i processant les tasques una darrere de l'altra.
    - **Seguiment de progrés en temps real**: S'ha integrat el progrés real de les tasques asíncrones de Celery a través de Redis utilitzant `ProgressRecorder`, exposant dinàmicament el percentatge i elements processats directament en consultar l'endpoint de la cua de facturació.

### CHORE
#### PRICING
    - **Comanda `align_billing_ranges`**: Nova comanda de gestió (`python manage.py align_billing_ranges --commit`) per a alinear de forma retrospectiva les dates de fi de tots els intervals de preus existents a la base de dades amb la data d'inici de l'interval següent.

#### BILLING
    - **Traducció del tipus de tasca de facturació**: S'han traduït els tipus de tasca `PRE_INVOICE` i `DEFINITIVE_INVOICE` al català ("Generació de prefactures" i "Generació de factures definitives") i s'ha exposat el camp traduït `task_type_display` a l'API de consulta de la cua.

### FIX
#### BILLING
    - Guardar lectura sense valor a lot de lectura
    - **Resolució d'UnboundLocalError i errors d'atributs a tasks.py**: S'han eliminat les importacions locals redundants de `Billing` i `ConfigProject` de dins dels mètodes de `tasks.py`. També s'ha corregit un error on s'intentava accedir a l'atribut `.contract` en enters (ID de contracte) a la tasca `process_billing_batch`, eliminant el bucle redundant i inicialitzant correctament la variable `contract_ids`.
    - **Càlcul d'intervals de facturació pròxims a dates límit**: S'ha corregit la comparació de fi d'interval de facturació a `get_value_by_change_price_rate_date` per a utilitzar un menor o igual (`<=`) en lloc de menor estricte (`<`). Això garanteix que quan un canvi de tarifa coincideix exactament amb la data de lectura final, l'interval antic absorbeixi correctament els dies de consum reals (99 dies en lloc de 0). A més, s'ha afegit un control a `create_from_lineitemtype` per descartar (retornant una llista buida) qualsevol interval de preu prorratejat que resulti en 0 o menys dies de consum, evitant així la generació de línies de quota fixa o consum duplicades amb valors buits (com ara conceptes addicionals de part fixa o variable a zero).

## [15-06-2026]

### CHORE
#### BILLING
    - S'ha afegit un comentario/observació pel pressupost
    - **Comanda `delete_invoice_line_items`**: Nova comanda de gestió (`python manage.py delete_invoice_line_items --token <token>`) per eliminar totes les línies (`InvoiceLineItem`) d'una o més factures sense esborrar la factura ni modificar-ne els totals (`subtotal_final`, `total_final`, `left_to_pay`). Suporta múltiples tokens separats per comes i `--dry-run`.

### FIX
#### BILLING
    - **Intervals de facturació i data de fi**: S'ha canviat la comparació de la data de fi de l'interval de facturació per a que sigui menor estricte (`<`) en lloc de menor o igual (`<=`) al comprovar la vigència del rang de facturació. Això evita que les lectures situades exactament a la data de canvi de rang corresponguin a dos intervals diferents simultàniament.
    - **Creació automàtica d'intervals de preus (BillingRange)**: En crear un nou interval de facturació de forma automàtica o des del serializer, la data de fi de l'interval anterior s'assigna de forma automàtica a la data d'inici del nou interval per mantenir la continuïtat. S'ha afegit una validació al serializer que impedeix la creació de nous intervals amb una data d'inici igual o anterior a la de l'interval anterior.

### MODIFIED
#### CLAIMREQUEST
    - Vulnerabilitat ara s'assigna només al titular (o llogater en cas d'haver-hi i tenir un titular juridic) i les variables i bonificacions s'assignen automàticament amb un tipus que es pot configurar

## [12-06-2026]

### MODIFIED
#### BILLING
    - **Exclusió i inclusió en bloc de factures a remesa SEPA**: S'ha afegit el mètode `post` a `SEPAPaymentInvoicesViewSet` (`sepa_payment_document_generate_view.py`) per permetre l'exclusió o inclusió massiva de factures coincidents amb els filtres actius del llistat, i s'ha habilitat la ruta corresponent a `urls.py`.

### FIX
#### BILLING
    - **Interval de facturació en canvis de comptador**: S'ha corregit la condició a `invoice_service.py` perquè detecti correctament el canvi de tarifa quan hi ha un canvi de comptador. En lloc de comparar la data d'inici del rang de facturació amb la lectura anterior del comptador nou (que era posterior), ara es compara únicament amb la data de la darrera lectura facturada (`prev_reading_date`), assegurant que es respectin els intervals i s'apliquin els trams tarifaris corresponents sense alterar la vinculació de lectures a la factura.

## [11-06-2026]

### FEAT
#### BILLING
    - **Processament individual i massiu de contractes**: S'han creat tres nous endpoints a `BillingViewSet` (`add-estimated-reading`, `add-to-batch`, `process-contract`) per processar lectures estimades, assignar-les a lots i calcular factures de forma individual per a un contracte. També s'ha afegit un endpoint massiu `/process-selected/` que llança una tasca de Celery (`process_selected_contracts_task`) per processar un llistat de contractes de forma asíncrona i retorna el `task_id`.

### MODIFIED
#### LECTURAPP
    - Sync readings si la lectura anterior es troba al mateix periode de la que esta entrant, l'anterior es fa de control i es fa canvia la previous reading
#### BILLING
    - Al filtrar lectures a un lot mirant des del punt de subm. sempre agafar els contracte actius

### FIX
#### BILLING
    - **Càlcul de data objectiu en l'estimació de lectures**: S'ha corregit la tasca `estimate_readings_task` de manera que quan es fa una estimació per marge de dies des de l'última lectura (`days_from_last`), es té en compte la darrera lectura de qualsevol tipus (incloent-hi lectures estimades) en lloc de filtrar únicament lectures reals (`is_estimated=False`), garantint que es prengui correctament la referència més recent disponible.
    - **Detecció de manca de comptador a check-missing**: L'endpoint `check-missing` ara comprova si els contractes no tenen cap comptador actiu i afegeix `"no_meter"` als motius de `missing_reasons`.
    - **NameError a process_selected_contracts_task**: Corregit un error `NameError: name 'Max' is not defined` a la tasca asíncrona de Celery en importar correctament `Min` i `Max` de `django.db.models`.

#### STATISTICS
    - **Import de Company a l'informe de recaptació**: S'ha corregit un error d'importació (`cannot import name 'Company' from 'coredata.models'`) a la funció `generate_recaptacio_conceptes_excel` de `report_billing_service.py` important el model `Company` correctament des de `service.models`.
    - **Traducció d'alertes al Padró de Facturació**: S'ha implementat la funció `get_translated_alert_notes` a `report_service.py` per traduir automàticament els tokens de les alertes de lectura (com ara `reading_alert_unusual` a "Lectura inusual" i `reading_alert_low_consumption` a "Consum baix") tant en català com en castellà i anglès a la columna "Observ. actual" del Padró de Facturació.

## [10-06-2026]

### FEAT
#### COMMUNICATION
    - **Filtre de dates i exportació a CSV**: S'han afegit els filtres de data `start_date` i `end_date` per filtrar comunicacions segons la seva data de creacion (`created_at`). També s'ha creat un nou endpoint d'exportació síncrona `export/csv/` que retorna un `StreamingHttpResponse` amb format CSV.

### CHORE
#### BILLING
    - **Comanda `generate_billing_invoices`**: Nova comanda de gestió (`python manage.py generate_billing_invoices --limit N`) per generar factures en entorns de demo. Selecciona Billings amb status Processat (token `4`) que tenen el lot de lectura associat (mateix token), ordenats del més recent al més antic, assigna les lectures al billing i engega `process_billing_batch`. Suporta `--sync` (sense Celery), `--dry-run`, `--force` (regenerar esborrant factures prèvies) i `--billing-id`.

#### CONTRACT
    - **Comanda `create_missing_initial_readings`**: Nova comanda de gestió (`python manage.py create_missing_initial_readings`) per a detectar contractes actius (amb estat d'alta / token `contract_active_token`) que no tenen cap lectura i crear-ne una d'inicial a la data de creació/alta del contracte, utilitzant el mateix valor que l'última lectura del comptador assignat. Suporta `--dry-run` i `--limit`.
    - **Filtre `block_billing`**: S'ha implementat el filtre opcional `block_billing` per filtrar contractes segons si tenen la facturació bloquejada. Aquest filtre s'aplica tant al llistat principal de contractes com a l'exportació asíncrona a Excel/CSV (`export/excel/`).
    - **Format de data verbal en català per al PDF del contracte**: S'ha afegit el helper `format_date_to_catalan_words` a `contract_pdf_view.py` per renderitzar la data de creació verbalment en català (p. ex., "27 de maig de 2025") a la plantilla del contracte.

#### IMPORTEXPORT
    - **Comanda `analyze_and_create_initial_readings`**: Nova comanda de gestió (`python manage.py analyze_and_create_initial_readings`) que busca contractes sense cap lectura inicial (`is_initial=True`) i en genera una de nova amb la data d'alta del contracte i el valor de la darrera lectura del mateix comptador. Suporta l'opció `--run`.

### MODIFIED
#### BILLING
    - **Endpoint `get_modification_data`**: S'ha adaptat l'endpoint per recuperar directament el valor de l'última lectura del comptador (`meter_last_reading_val`) per a ser utilitzat en la lectura inicial dels nous contractes.

### FIX
#### BILLING
    - **Llegida de data en fitxers SEPA (CreDtTm)**: S'ha modificat la interpretació de la data de creació (`CreDtTm`) en rebre fitxers SEPA del banc per recollir només la part de la data prèvia al caràcter `"T"`, ja que a la base de dades només es registra la data i no l'hora.
    - **Error de format de data a `manage_rejection_payments`**: S'ha corregit un error de parsing (`ValueError: unconverted data remains: T00:00:00`) a l'endpoint de gestió de rebutjos en cas que la data de retorn (`return_date`/`rjt_dt`) contingués la lletra `"T"` i informació d'hora.
    - **AttributeError a `get_modification_data`**: S'ha corregit una excepció `AttributeError: 'NoneType' object has no attribute 'id'` a l'endpoint de modificació de dades de lectura en cas que el punt de subministrament no tingui cap comptador assignat.
    - **Estimació en contractes nous de menys de 30 dies**: S'ha corregit el càlcul de data i consum de les lectures estimades per a contractes que s'hagin creat o donat d'alta fa menys de 30 dies respecte de la data mitjana del lot. Ara es calcula la lectura estimada per al dia actual o la data de lectura sol·licitada, i el consum estimat es calcula utilitzant la quota de consum mínim mensual proporcional als dies reals transcorreguts (dividit pel divisor normal de 30.44 dies).
#### SERVICE
    - **Actualització de boquilles (nozzles) i adreces de punt de subministrament des del cluster**: S'ha corregit un bug en actualitzar un cluster a l'endpoint `/service/cluster/<id>/` on els canvis realitzats als nozzles (com les adreces dels punts de subministrament, incloent-hi "Porta"/`floor`/`door`) no es desaven correctament a la base de dades. També s'ha afegit suport per a peticions on la llista de `nozzles` o els seus objectes s'envien serialitzats com a cadenes de text (JSON strings).

## [09-06-2026]

### CHORE
#### IMPORT / EXPORT
    - **Comanda `fill_street_city`**: Nova comanda de gestió (`python manage.py fill_street_city`) que assigna automàticament la població (`city_id`) a aquells carrers de la taula `coredata_street` que la tenen a `NULL`, a partir de les adreces (`coredata_address`) que hi estan vinculades, incloent-hi suport per a `--dry-run` i resolució de conflictes de múltiples poblacions.

#### WATCHDOG
    - **Nous watchdogs de factures i consums disparats**:
        - **`check_invoices_without_company`**: Cerca factures actives sense cap empresa assignada, filtrant per les factures generades pel nostre propi sistema (excloent importacions inicials mitjançant la barra `/` a `serie_final`).
        - **`check_invoices_without_exploitation`**: Cerca factures actives sense cap explotació assignada, amb el mateix filtratge per a factures pròpies.
        - **`check_anomalous_consumption_or_billing_stats`**: Cerca anomalies de consum a les estadístiques històriques del contracte (`ContractConsumption`), detectant si algun període/mes conté un consum diari que supera en més de 3 vegades la mitjana de la resta del mateix contracte (amb llindar mínim d'1.5 m3/dia per evitar soroll).

### FIX
#### STATISTICS
    - **Correccions a l'Informe de Recaptació per Conceptes (`generate_recaptacio_conceptes_excel`)**: S'han inclòs els conceptes personalitzats en una categoria virtual, s'han solucionat les diferències de cèntims per arredoniment entre pestanyes i s'ha alineat el deute cobrat de la pestanya d'empreses amb els moviments detallats.
#### BILLING
    - **Filtre per concepte de línia de factura (line_item)**: S'ha estès la cerca del filtre `line_item` per incloure no només el nom del producte (`product_name`) sinó també el nom (`name`) i la descripció (`description`) de la línia de factura (`InvoiceLineItem`). D'aquesta manera, es permet el filtratge de termes continguts a la descripció o al detall de la línia com ara el calibre (per exemple, "15 mm").
    - **Data d'estimació en contractes nous**: S'ha corregit un error on les estimacions en contractes de nova creació (que només tenen la lectura inicial) es forçaven a 90 dies nominals ignorant la data real demanada. S'ha eliminat la comprovació de `contract_readings.count() > 0` per permetre la normalització correcta a la data de la factura o final de cicle demanat.

### MODIFIED
#### BILLING
    - Als compromisos de pagament, ara es pot escollir entre el titular, llogater o propietari com a pagadors del compromís

#### COREDATA
    - Expedients s'han mogut a un nou model per tenir un expedient per any i poder filtrar-los al generar la factura electronica

#### SERVICE
    - S'ha canviat les adreces electròniques de CompanyConfig. Ara és un model CompanyConfigEmail per poder afegir +1 mail a la configuració (un per factures, un per notificacions...). Això implica canvi al guardar i enviar comunicacions. De moment NO tenen contrasenya diferent, tots comparteixen. Ja es canviarà quan ens trobem amb algun cas amb diferents pwd

## [08-06-2026]

### FIX
#### COMMUNICATION
    - S'ha afegit un try/catch en cas de tractar amb les plantilles anteriors. Al estar mal montades donen problemes al generar el png per front
#### BILLING
    - `invoice_pdf_view.py` i `invoice_pdf.py`: Afegit un mecanisme de fallback per a l'explotació i l'empresa en la generació de PDF de factures. Si una factura no té vinculada cap explotació ni cap empresa, ara es recupera automàticament l'explotació i l'empresa per defecte configurades per evitar problemes d'estils i errors de generació de PDF.
    - S'ha afegit un altre condicional per buscar un pagament per rnd quan és compromís en cas que no el trobi
    - `contract_serializer.py`: Mantingut l'optimització de retorn buit (`return []`) a `get_invoices` per evitar càrregues lentes en l'endpoint de detall general de contracte, traslladant la responsabilitat de la càrrega de factures asíncronament cap al front-end.
        - **Correcció de lectures i càlculs a la baixa de contracte**:
            - `invoice_service.py`: Corregida la lògica de cerca de lectura de fallback a `invoice_contract_termination_generate` per a que només agafi lectures a partir de la data de registre/alta del contracte, evitant facturar lectures de contractes anteriors (com la de 18 m³ del contracte vell).
            - `invoice_service.py` i `invoice_line_item_service.py`: Afegit suport per generar correctament el pressupost/factura de baixa sense lectures, calculant els dies actius (des de la data d'alta a la de baixa) per a cobrar la quota fixa proporcional i forçant a 0 m³ el consum variable en lloc d'1 m³ per defecte.
            - `generate_invoice_budget_view.py`: Evitada la creació de pressupostos duplicats (`PF/...`) en demanar de nou el pressupost d'una mateixa baixa mitjançant l'esborrat previ d'esborranys anteriors no confirmats, i controlat l'error `Invoice.DoesNotExist` en la seva regeneració.
            - `invoice_service.py`: Corregit el color i l'estil en la factura de baixa de contracte quan es disposa de lectures. S'ha inicialitzat l'`exploitation` des de la configuració per defecte del contracte per tal d'evitar que es generi amb la companyia a `None` i s'apliquin els colors de fallback per defecte.

### FEAT
#### BILLING
    - S'ha afegit un nou model per guardar els retorns de les remeses SEPA, a on guardarem els pagaments i el document de retorn.

#### STATISTICS
    - **Pestanya de Cobros a l'informe de Navision**: S'ha afegit una nova pestanya "Cobros" a l'informe `generate_billing_taxes_detailed_summary` (Navision Murcia) que llista tots els pagaments cobrats al període seleccionat amb el detall de productes i impostos prorratejats segons l'import del pagament.

### CHORE
#### BILLING
    - Funció per lligar persones amb les seves factures. Algunes s'hauràn de fer a mà
    - S'ha relacionat directament persona amb factura. Hi han factures sense objectes com contracte relacionat i poden haver-hi persones compartint mateix nom sense un dni correcte (99999999R) o amb un canvi de nie a dni
    - S'ha afegit 'invoice_view.py > obtain_invoice_documents' per poder obtenir les factures i descarregar-les en massa

#### NOTIFICATION
    - **Exportació asíncrona d'incidències en Excel**: S'ha afegit l'endpoint `GET /api/notification/incident/export/excel/` que rep els mateixos filtres que la llista d'incidències i activa la tasca de Celery `export_incidents_csv_task`. Aquesta tasca genera un llibre Excel (`.xlsx`) totalment estilat (capçaleres en negre amb text blanc en negreta, vores fines, amplades de columna autoajustades i la descripció a l'última columna) utilitzant el helper `build_incident_export_csv_bytes` i la llibreria `openpyxl`.

### MODIFIED
#### BILLING
    - Pre check readings s'ha eliminat el condicional de mirar sempre la lectura anterior per restar estimada si no té bossa de consum
    - Filtre de factura, s'ha tret cutomer_final i customer_token_final per person al fer la nova relació

#### STATISTICS
    - **Informe de temps de resposta a reclamacions**: S'ha modificat `generate_claim_response_time_report` per calcular i mostrar tots els estats d'incidència (oberta, pendent, tancada) en lloc d'excloure les que no són tancades. S'han agrupat les estadístiques de resum i de detall per Tipus de Reclamació i Estat, calculant la durada fins a la data de resolució per a les tancades i fins a la data actual per a la resta.
    - **Optimització de l'informe de Navision (Evitar consultes N+1)**: S'ha optimitzat l'informe `generate_billing_taxes_detailed_summary` pre-carregant relacions i fent filtratges en memòria Python. S'han eliminat milers de consultes repetitives que causaven un rendiment extremadament lent.

#### CONTRACT
    - **Data de registre al contracte PDF**: S'ha modificat el contracte PDF (`contract_template.html` i `contract_pdf_view.py`) per a prioritzar la data de registre (`registration_date`) si està definida, de manera que es mostri correctament la data d'alta modificada manualment.

## [05-06-2026]

### CHORE
#### BILLING
    - S'ha afegit l'opció d'obtenir un comprovant de pagaments per un pagament agrupat
    - **Filtre per concepte de línia de factura (line_item)**: S'ha afegit el filtre `line_item` a l'endpoint de factures (`/billing/invoice/`) a `InvoiceFilter` de `billing/filter/invoice_filter.py`, permetent filtrar factures cercant per la coincidència parcial (icontains) del nom del producte/concepte de la línia (`line_items__product_name`) de forma unívoca gràcies a l'ús de `distinct=True`.

#### SERVICE
    - **Historial de canvis a comptadors (Meter logs)**:
        - S'ha afegit un endpoint `GET /service/meter/<id>/logs/` al controlador `MeterViewSet` a `service/views/meter_view.py` per consultar l'historial de canvis d'un comptador a través de `MeterLog`.
        - S'ha configurat `MeterLogSerializer` a `service/serializers/meter_serializer.py` per retornar els canvis en l'estructura esperada pel front, retornant només el `username` del `user`, traduint els tokens d'operació i els noms de camps (p. ex. `status` a `status_name`), i resolent els IDs dels models relacionats a cadenes de text (com els estats `"Actiu"` / `"Baixa"` o el calibre).
        - S'ha afegit l'auditoria automàtica de la creació de comptadors al signal `post_save` de `service/signals.py` per complementar l'auditoria de modificacions existent en el `pre_save`.
        - S'han afegit les traduccions corresponents dels literals del log de comptadors (camps, operacions i valors com True/False a Sí/No) als fitxers de traduccions en català (`locale/ca/LC_MESSAGES/django.po`) i castellà (`locale/es/LC_MESSAGES/django.po`).

#### STATISTICS
    - S'ha afegit un informe que genera el deute pendent per abonat

#### WATCHDOG
    - **`watchdog_fix_contract_piggy_banks`**: Crea `PiggyBank` per als `Contract` sense `piggy_bank` (mateix criteri que el sniff «Contracts without Piggybanks») i enllaça la relació. Admet `--dry-run`, `--id` (IDs concrets separats per comes) i `--limit`.
    - **`watchdog sniff`**: Quan falla «Contracts without Piggybanks», recomana executar `watchdog_fix_contract_piggy_banks` (primer amb `--dry-run`).

### MODIFIED
#### COREDATA
     coredata/serializers.py: S'ha modificat la serialització de persones -> contractes perquè no es dupliquin contractes quan una mateixa persona té múltiples rols associats.

## [04-06-2026]

### FIX
#### STATISTICS
    - **Classificació de la quota de servei a l'informe de cobraments**: S'ha corregit un error a l'informe "Resum de pagaments cobrats" (`generate_cobraments_report`) on la quota de servei i el consum d'aigua es sumaven junts com a consum. S'ha ampliat la identificació de la quota de servei per detectar si algun dels camps `prod_name`, `rate_name` o `line_name` conté algun dels patrons genèrics `QUOTA`, `CUOTA`, `FIXA` o `FIJA`, cosa que permet separar-los correctament fins i tot quan comparteixen el mateix nom de producte (com `"AIGUA AIGUA ZONA 1"` a les factures antigues).
    - **Format sense prorratejar i columna Total Factura a l'informe de cobraments**: S'ha eliminat el prorrateig conceptual a les columnes d'imports i d'IVA (es mostren els valors de la factura sencers per a facilitar la identificació de compromisos de pagament parcials). S'ha afegit la columna `"Total Factura"` al costat de `"Subtotal sense IVA"`, s'ha eliminat `"Base IVA"`, s'han desglossat les columnes d'IVA adjacents per a cada producte i s'amaguen automàticament aquelles columnes d'IVA que només tinguin valor zero.
#### BILLING
    - **Correcció de format a la plantilla de compromís de pagament**: S'ha corregit un salt de línia incorrecte en el renderitzat de la variable `company.name` a la plantilla de document de compromís de pagament (`commitment_deposit_template.html`).
    - **Resolució de lectures de control modificades**: S'ha afegit una resolució recursiva en memòria a `generate_consumption_invoice_multiple` a `billing/utils/invoice_service.py` que mapeja qualsevol lectura de control (com ara una lectura de tancament editada des de la UI) a la seva corresponent modificació activa no-control, evitant que el motor utilitzi valors antics de consum (com passava al contracte `3455457`). També es mantenen vinculades a la factura totes les lectures contributives (incloses les de tancament) perquè es mostrin a la taula superior de la plantilla PDF.
    - **Reversió de la consolidació de línies de factura**: S'ha descartat l'agrupació de consums per tarifa en una única línia per a diferents comptadors (que impedia facturar comptadors amb tarifes o productes diferents), retornant a la generació de línies de factura separades per cada comptador/lectura.
    - **Prevenció de dobles comptatges de consum**: S'ha corregit un possible doble comptatge al mètode de càlcul de comptador general (`recalc_consumption_gen_meter`) quan la lectura de tancament del comptador antic i la nova lectura es facturen de forma conjunta a la mateixa factura o lot.

### CHORE
#### SERVICE
    - **Camps de ruta al llistat de finques**: S'ha afegit la ruta (`route`, amb ID, nom i codi) i la posició de la ruta (`route_position`) al serialitzador de llistat de finques (`PropertyListSerializer`) per a incloure aquesta informació a les peticions de l'endpoint `/service/property/`.

#### BILLING
    - **Test per a facturació multi-comptador**: S'ha creat la classe de test `TestMultiMeterBilling` al fitxer `billing/tests/test_multi_meter_billing.py` per validar tant la consolidació de consums per tarifa amb múltiples comptadors com la correcta resolució de lectures de control modificades, sense llançar-ne l'execució automàtica.

#### COREDATA
    - S'ha afegit a la persona el núm d'expedient per després afegir a les factures electròniques

### FEAT
#### BILLING
    - **Exportació de lectures per lot en CSV amb 4 consums anteriors**: S'ha afegit a l'exportació CSV de lectures per lot (`ReadingByBatchCSVExportView`) la recuperació i inclusió de 4 columnes addicionals amb els 4 consums (`calculated_value`) anteriors de cada contracte ordenats descendentment per data de lectura.

## [03-06-2026]

### FIX
#### SERVICE
    - **Ordenació per adreça i localitat al llistat de punts de subministrament**: S'ha corregit un error que es produïa en intentar ordenar per `address_complete` i `address_city` al llistat de punts de subministrament (`SupplyPoint`). S'han anotat els camps `address_complete` (com a `address__address_search`) i `address_city` (com a `address__city__name`) al queryset de `SupplyPointViewSet`.
#### BILLING
    - **Factures de devolució en negatiu**: S'ha implementat la lògica per tal que les factures de devolució de fiança (o qualsevol alta de contracte amb retorn, on `is_return` és True) guardin tots els seus imports (línies de detall `InvoiceLineItem` i totals de capçalera `Invoice`) com a valors negatius de forma consistent. A més, s'ha actualitzat la funció `update_invoice_totals` perquè, en cas de modificar/recalcular pre-factures existents que ja són de retorn, es mantinguin en negatiu tant els imports de les línies com els totals recalculats, garantint que el comportament de factures positives ordinàries no es vegi afectat.

### CHORE
#### SERVICE
    - **Camp `is_default` a `Company`**: S'ha afegit la columna `is_default` a la taula `Company` per indicar quina és la companyia per defecte. S'ha definit la migració de base de dades per assignar el valor inicial de forma dinàmica segons el valor configurat a `ConfigProject` (`main_company_token`). En el serialitzador `CompanySerializer` s'ha implementat la lògica que assegura la unicitat de la companyia per defecte (en crear o actualitzar una companyia com a defecte, es desmarca la resta).

#### PROMETEO
    - **Actualització de dades de configuració**: S'han afegit les configuracions de `ConfigProject` pendents als fitxers de fixtures locals de Prometeo (català i castellà) per incloure els tokens `use_multiple_companies`, `reading_alert_unusual_consumption_min_value` i `fire_connection_use_type_token`.

#### WATCHDOG
    - nou script python manage.py watchdog_fix_connection_exploitation que posa exploitation.first() a les escomeses que no tenen exploitation.
    - **`watchdog_fix_empty_bank_ibans`**: Elimina `PersonBank` i `CompanyBank` amb IBAN buit o invàlid (mateix criteri que el sniff); per defecte també esborra comptes referenciats i deixa les FK a NULL. Admet `--dry-run` i `--skip-in-use` (conservador).
    - **`watchdog sniff`**: Quan falla «PersonBank i CompanyBank IBANs vàlids», recomana executar `watchdog_fix_empty_bank_ibans` (primer amb `--dry-run`).

#### IMPORTEXPORT
    - **`create_clusters_from_properties`**: Crea `Cluster` amb el mateix token que la `Property` quan la finca té dos o més punts de subministrament; genera un `ClusterNozzle` per cada `SupplyPoint` i el vincula. Copia l'adreça (`address_street_id`, `address_street_number_id`, `address_postal_code_id`, `address_city_id`) i assigna `status_id` del `ClusterStatus` amb `is_default=True`. Opcions: `--dry-run`, `--property-token`, `--min-supply-points`, `--fix-existing` (corregeix clusters existents sense adreça ni estat).
    - **`fill_connection_address_from_property`**: Omple l'adreça de `Connection` des de la `Property` vinculada (via `Cluster` o `SupplyPoint`): `address_street`, `address_street_number`, `address_postal_code`, `address_city`. Per defecte només camps buits; opcions: `--dry-run`, `--connection-token`, `--force`.

### MODIFIED
#### BILLING
    - Ara es permet mantenir lectures estimades al modificar lectures d'un contracte i seleccionar si es vol fer servir la bossa d'estimades o no

#### IMPORTEXPORT
    - **`clusters_error`**: S'ha afegit `--dry-run` per previsualitzar esborrats sense desar. S'ha corregit la detecció del nozzle residual quan queda un sol nozzle actiu després de la neteja. Resum final amb recompte de nozzles i clusters afectats.

## [02-06-2026]

### MODIFIED
#### COMMUNICATION	
	- Al generar un procés de comunicació per lectures, separar comunicacions individuals per no trepitjar-se si hi ha una persona amb +1 contracte amb lectures de fuita
	- Quan s'envien comunicacions, sempre mira al final si el seu procés té totes com a enviades i es marca com a finalitzat
	- S'ha tornat a permetre generar les cartes relacionades a comunicacions amb tipus de canal 'letter'
	- Ara es permet treballar sobre un procés ja creat a mitges. De moment només està preparat per lectures però es pot modificar més endavant a més casos com factures
	- S'ha canviat el basic_letter base html i ara es passen més valors a renderitzar

#### BILLING
	- Ara el serializer de lectures al lot també mostra si es troben en un procés de comunicació pendent
    
#### SETTINGS
    - Afegit SECURE_PROXY_SSL_HEADER i CSRF_TRUSTED_ORIGINS per seguretat i per a què funcioni en dockers la protecció del media.
#### CONTRACT
    - **Gestió de baixes de contracte i fiances**:
        - S'ha implementat la restauració automàtica de fiances a l'estat "No Retornat" quan es cancel·la una sol·licitud de baixa de contracte (`ContractTerminationRequest`), netejant la data de retorn, la factura assignada i creant el log corresponent a `LogBailStatus`.
        - S'ha descomentat la lògica que actualitza a "Pendent" ('1') les ordres no finalitzades vinculades a una sol·licitud de baixa quan aquesta s'actualitza o es troba activa/pendent.
        - S'ha eliminat l'assignació prematura de la data de retorn (`return_date`) de la fiança quan només s'ha iniciat la sol·licitud de baixa.

### FIX
#### SETTINGS
    - **Error CSRF_TRUSTED_ORIGINS (4_0.E001)**: Corregit l'error en arrencar el servidor quan `CSRF_TRUSTED_ORIGINS` no està definit a l'entorn (`.env`), establint el valor per defecte a `"http://"` per evitar que split retorni una cadena buida sense esquema que provoqui un error de validació a Django.
#### CONTRACT
    - **Recompte de factures al contracte**: Corregit el mètode `get_invoices_count` de `ContractSerializer` per filtrar les factures pel tipus de document definit per `invoice_type_invoice_token` a la configuració del projecte (`ConfigProject`), evitant així incloure altres tipus de document (com ara pressupostos) en el recompte total de factures.
#### BILLING
    - **Control d'error en comprovar factures pagades**: Corregit un possible `AttributeError` a `check_paid_invoice` quan una factura es marca com a pagada però no té cap pagament registrat a la base de dades. A més, s'assegura que tant la data de pagament (`payment_date`) com la data de retorn (`return_date`) de la fiança quedin actualitzades amb la data real del pagament.
#### SERVICE
    - **Error de variable local no definida a CompanySerializer**: Corregit un error `UnboundLocalError` quan es creava una empresa (Company) i s'intentava assignar i desar el tipus (`type`) abans d'instanciar l'objecte de l'empresa. S'ha mogut l'assignació del tipus a continuació de la creació de l'objecte.

### CHORE
#### COMMUNICATION
	- S'ha afegit un nou mètode de filtrar un cop generem un procés de comunicació pendent en 'Esborrany'. De moment només funciona amb lectures
	- S'ha afegit l'opció d'afegir lectures a un nou procés de comunicació al estar en un lot de lectures. Aquestes NO es podran tornar a afegir a un altre procés fins que es finalitzi o cancel·li
	- S'ha afegit l'opció d'adjuntar factures al fer un procés de comunicació filtrat per facturació
	- Ara es pot lligar lectures a processos de communicació

## [01-06-2026]

### FEAT
#### CONTRACT
    - **Formulari de modificació de dades del contracte**: S'ha afegit l'endpoint `GET /api/contract/contract/<id>/data-change/` per carregar només les dades necessàries al formulari de canvi de dades (titular, adreces, pagament, contactes, etc.) sense comptadors ni llistats pesats. S'han creat `ContractDataChangeEditSerializer` i `contract_data_change_queryset()` amb `select_related` i `prefetch_related` per optimitzar la consulta. En actualitzar un contracte amb el query param `?edit=data-change`, la resposta del `PUT` retorna el mateix serialitzador lleuger en lloc del `ContractSerializer` complet.

#### LOGGER
    - **Log de telèfons de contracte**: S'ha afegit el model `LogContractPhones`, la migració `0050_logcontractphones`, el serialitzador `LogContractPhonesSerializer`, el filtre per contracte (`LogContractPhonesFilter`) i l'endpoint `/api/logger/contract-phones/` per consultar l'historial de canvis de telèfons associats a un contracte.

#### PROMETEO / STATISTICS
    - **Dades d'informes disponibles a Prometeo**: S'han exportat els registres de la taula `AvailableReport` a fitxers JSON (`statistics.AvailableReport.json`) a les carpetes `prometeo/data/` i `prometeo/data_es/` perquè en restaurar la base de dades amb l'script `reset_db.sh` es carreguin automàticament els informes per defecte.

### CHORE
#### CONTRACT
    - **Auditoria de canvis de telèfons del contracte**: En modificar la llista de telèfons del contracte (`phone_ids`), s'invoca `log_contract_phones_change` per registrar el valor anterior i el nou (números concatenats) sense alterar la lògica existent del M2M `contacts`.

#### COREDATA / CONTRACT
    - **Endpoint i Categoria de Permisos per a la Bossa de Saldo (Piggy Bank)**: S'ha registrat la categoria de permisos `piggy_bank` en la taula `MainPermission` (amb els camps `view_key='view_piggy_bank'` i `change_key='change_piggy_bank'`) a través de la nova migració `0104_add_piggy_bank_main_permission.py` i s'han actualitzat les llavors de Prometeo. També s'han definit els endpoints de permisos de lectura i modificació a `/contract/piggy-bank/permissions/` i `/coredata/person-piggy-bank/permissions/`.

#### AUTH
    - **Grup Administrador per defecte**: S'ha afegit la migració de dades `0105_create_administrador_group.py` per inicialitzar automàticament el grup d'usuaris "Administrador" a la base de dades.

#### IMPORTEXPORT
    - **Comanda per actualitzar codis SWIFT**: S'ha creat la nova comanda de Django `update_person_bank_swifts` per actualitzar de forma massiva els codis SWIFT buits de comptes bancaris de persones (`PersonBank`) utilitzant l'IBAN (via llibreria `schwifty`) o com a alternativa el BIC de l'entitat bancària (`Bank`). Disposa del paràmetre `--dry-run` per a poder simular els canvis abans d'aplicar-los.

### FIX
#### BILLING
    - **Error en facturar pressupost d'escomesa**: Corregit un error `AttributeError: 'ConnectionRequest' object has no attribute 'variables'` que es produïa en passar un pressupost d'escomesa a factura durant la generació del PDF, ja que els objectes `ConnectionRequest` no disposen del camp o relació `variables`. S'ha controlat la seva existència amb `hasattr`.
#### CONTRACT
    - **Correccions al serialitzador de contractes fixats (`PinnedContractSerializer`)**: Corregits possibles errors de tipus `AttributeError` quan el titular (`holder`) és `None` en accedir als seus camps en el mètode `to_representation`. S'ha eliminat una declaració duplicada del camp `category`. A més, s'han alineat els mètodes `get_debt_amount` i `get_active_commitment_deposits` per sincronitzar la lògica d'exclusions de deute i fiances compromeses amb el serialitzador principal (`ContractSerializer`), i s'han protegit amb control d'excepcions.

### MODIFIED
#### IMPORTEXPORT
    - **Exportació asíncrona de comptadors**: Moguda la generació del fitxer CSV a una tasca de Celery (`export_meters_csv_task`) per evitar problemes de timeout. L'endpoint d'exportació de comptadors ara retorna un `task_id` per a fer-ne seguiment.
#### CONTRACT
    - **Exportació asíncrona de contractes**: S'ha traslladat la generació del fitxer d'exportació a format CSV a segon pla mitjançant la tasca de Celery `export_contracts_csv_task` a l'endpoint d'exportació de contractes, retornant un `task_id` asíncron per controlar el possible timeout.
#### CONTRACT
    - **Vinculació automàtica de factures i lectures de tall**: S'ha implementat la vinculació automàtica de factures de sol·licitud i de lectures de tall (cut-off readings) de sol·licituds de baixa vinculades en el moment d'acceptar/finalitzar una sol·licitud de contracte (`ContractRequest`) i crear el contracte definitiu (`Contract`), evitant que quedin sense vincular.
#### MEDIA
    - **Protegit l'accés a /media amb token**: S'ha implementat la protecció de l'accés a /media amb un token per a evitar que usuaris no autoritzats puguin accedir a les imatges / fitxers.
#### AUTH
    - **Edició d'usuaris millorada (grups, administrador i contrasenya opcional)**: S'ha actualitzat `UserSerializer` per fer que el camp de la contrasenya (`new_pwd`) sigui opcional en editar un usuari. També s'ha habilitat l'edició del check "Administrador" (actualitza `is_superuser` i `is_staff` només si l'usuari que fa la petició és superuser) i la selecció de grup mitjançant el camp `group_id`.
