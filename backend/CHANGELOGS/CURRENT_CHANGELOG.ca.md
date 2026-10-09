# Changelog Backend

## [09-10-2026]

### FEAT

#### BILLING (`billing/templatetags/billing_filters.py`, `billing/utils/invoice_pdf.py`, `billing/views/invoice_pdf_view.py`, `billing/templatetags/svg_converter.py`, `billing/templates/invoice_template.html`, `billing/templates/invoice_request_template.html` — període del facturador i QR web)
    - Nou filtre `invoice_biller_period`. El rang (p. ex. Gener-Març/2026) surt de `Biller.period_type` i `Biller.initial_month`. El mes de la factura (`billing_period_year` / `billing_period_month`, o la data de la lectura si no hi són) només indica quin cicle és. El nom del lot no es llegeix.
    - Si el lot no té facturador, o la factura no és de consum, el filtre retorna buit i la fila no es pinta.
    - No es modifica `billing_period`, `invoice_period`, `get_quarter`, `quarter_period` ni `get_period_months`. Una plantilla que no cridi `invoice_biller_period` no el fa servir.
    - Al context del PDF s'afegeix `qr_web` si existeix. Les plantilles que no escriuen `{{ qr_web }}` no canvien.
    - Nous tags d'icona a `svg_converter`: Facebook, X, Instagram, WhatsApp, portàtil i gota d'aigua.

#### OV (`ov/views.py`, `ov/serializers.py`, `ov/urls.py`, `docs/ov/openapi.yaml` — claus de resposta en anglès, `is_account_holder` condicional al DNI, alias legacy 302 i pujada del mandat SEPA)
    - Les respostes OV passen a claus en anglès: `titular_contrato`→`contract_holder`, `titular_domiciliacion`→`direct_debit_holder`, `acciones_permitidas`→`allowed_actions` (`ContractListItemOVSerializer`); `dni_titular_cuenta`→`account_holder_dni`, `es_titular_cuenta`→`is_account_holder`, `direccion_titular`→`holder_address` (`ContractFullDetailSerializer`); `direccion_tributaria`→`tax_address` amb `anonimizada`→`is_anonymized`, `direccion`→`address`, `codigo_postal`→`postal_code`, `ciudad`→`city`, `provincia`→`province`, `pais`→`country` (`InvoiceFullDetailSerializer`).
    - `is_account_holder` ara depèn del paràmetre de consulta `dni` i no del titular del contracte: es compara el `dni` normalitzat (sense espais i en majúscules) amb el titular de la compte de domiciliació (`PersonBank.dni`, o `Person.token` si el camp ve buit). Sense `dni` (o buit) la clau **no apareix** a la resposta — s'elimina a `to_representation`; a `/ov/contracts/` el `dni` és obligatori així que sempre hi és.
    - La màscara d'IBAN de `/ov/contract/{token}/` segueix la mateixa bandera: es desenmascara només quan `is_account_holder` és `true` (és a dir, `dni` enviat i coincident); qualsevol altre cas queda enmascarat (8 primers caràcters + asteriscos + 8 últims).
    - `GET /ov/contract-detail/` passa a ser un alias legacy: redirigeix `302` a `GET /ov/contract/{token}/` (`reverse('contract-detail-by-token-ov')`) conservant la resta de paràmetres de consulta (`dni`, `limit`, `page`, …). La vista no toca la base de dades: un `contract_token` desconegut cau al `404` de la vista destí; si falta el paràmetre respon `400`. S'elimina el `print` de depuració.
    - Nou `POST /ov/procedures/{contract_token}/upload-sepa-signed/` (multipart `sepa` + `iban`): `SepaDocumentUploadSerializer` valida l'extensió del fitxer (`.pdf`, `.jpg`, `.jpeg`, `.png`, `.gif`, `.webp`, `.bmp`) i l'IBAN amb `validate_iban` (sense espais i en majúscules). El contracte inexistible dona `404 {error: "Contract not found"}`; errors de camp en format DRF (`400`); un IBAN que no coincideixi amb `payment.IBAN.iban` (comparació normalitzada) dona `400 {error: "The IBAN does not match the contract's current active account."}`. Abans de respondre `201` es registra el mock amb `logger.info`; la resposta és `{"contract_token": <token>, "success": true}` i l'emmagatzematge definitiu queda pendent.
    - La ruta del contador canvia a `/ov/meter/{contract_token}/` (paràmetre de ruta renombrat de `token`; `contractTokenPath` queda per a `/ov/contract/{token}/`).
    - `ContractsListOVView` passa `context={"request": request}` als serialitzadors: sense request la lectura del `dni` de consulta no funcionaria.
    - `docs/ov/openapi.yaml` actualitzat en totes les fases: files de la taula de resum, paràmetres nous `dniOptional`/`contractTokenMeterPath`/`contractTokenSepaPath`, descripció d'IBAN i exemples en anglès, esquemes `ContractListItem`/`ContractFullDetail`/`InvoiceFullDetail` reanomenats (+ `is_account_holder` a la llista), l'antiga ruta documentada com a `302` amb capçalera `Location` (sense `200`), el nou endpoint SEPA amb `SignedMandateUploadResponse {contract_token, success}` i 400 `oneOf` (`ValidationErrors` o `ErrorMessage`). El component `procedureIdPath` queda suprimit.

#### OV (`ov/views.py`, `ov/serializers.py`, `ov/urls.py`, `docs/ov/openapi.yaml` — cancel·lació de domiciliació (revocació del mandat SEPA))
    - Nou `POST /ov/procedures/{contract_token}/cancel-direct-debit/` (`cancel-direct-debit-ov`): revoca el mandat SEPA i canvia la forma de pagament del contracte. Cos JSON amb `period` (període de facturació des del qual s'aplica, p. ex. `2026-3T`), `role` (rol de qui sol·licita, p. ex. `TITULAR`/`PAGADOR`) i `new_payment_type` (opcional, token del nou tipus de pagament).
    - Flujo: `404 {error: "Contract not found"}` si el contracte no existeix; `400` amb els errors de camp DRF si falta `period`/`role`; `400 {error: "Contract has no payment method"}` si el contracte no té `payment`; `400 {error: "Invalid payment type token"}` si `new_payment_type` no correspon a cap `PaymentType`; `500 {error: "Default payment type BANK_TRANSFER not found"}` si falta el tipus per defecte (només quan `new_payment_type` no ve).
    - Operació **idempotent**: si `contract.payment.type.token` ja és el tipus objectiu no s'escriu res (ni canvi de tipus, ni `ContractLog`, ni `ContractObservation`) i es respon `200 {"contract_token", "success": true, "message": "Direct debit already cancelled."}`. Si sí que hi ha canvi, dins d'un `transaction.atomic()` es desa el `previous_payment_type`, s'actualitza `contract.payment.type`, es crea un `ContractLog` del camp `payment_type` (token anterior o `"None"`, nou token, `operation_token` `LOG_<token>_<n>`, `user` de la request) i una `ContractObservation` amb el `period` i el `role` sol·licitats; respon `200 {"contract_token", "success": true, "message": "Direct debit cancelled successfully."}` amb `logger.info` previ.
    - `docs/ov/openapi.yaml`: file de la taula de resum, paràmetre `contractTokenCancelPath`, esquemes `CancelDirectDebitRequest`/`CancelDirectDebitResponse` i path amb exemples `cancelled`/`alreadyCancelled` (200), `fieldErrors`/`noPayment`/`invalidPaymentType` (400) i `500` documentat.

#### OV (`ov/views.py`, `ov/serializers.py`, `ov/urls.py`, `docs/ov/openapi.yaml` — GET /ov/contact-data/ (configuración del perfil))
    - Nou `GET /ov/contact-data/?contract_token=<token>` (`contact-data-ov`): la configuración del perfil del abonado, com a extensió de `/ov/billing-data/`. Devolve els mateixos 13 camps (`nif`, `tenant_name`, `supply_point_address`, `city`, `postal_code`, `paper_invoice`, `email`, `invoice_language`, `phone1`, `phone2`, `payment_type`, `iban`, `holder_name`) més `holder_address`, l'adreça postal del titular del contracte (`PersonAddress` amb `is_billing`, via `select_related("address")`; `null` si el titular no té adreça o no existeix).
    - `ContactDataOVSerializer` hereta de `BillingDataOVSerializer` i afegeix el `SerializerMethodField` `holder_address` amb la mateixa lògica de `ContractFullDetailSerializer` (guart de titular nul inclòs).
    - Errors: `400 {error: "Contract token is required"}` si falta el paràmetre de query (mateix criteri que `billing-data`), `404 {error: "Contract not found"}` si el contracte no existeix (mateix criteri que `/ov/contract/{token}/`) i `401` sense autenticació.
    - `docs/ov/openapi.yaml`: nou tag `Perfil`, file a la taula de resum, path amb `operationId: getContactData` (paràmetre `contractToken`, respostes 200/400/401/404) i esquema `ContactData` compost amb `allOf` sobre `BillingData` + `holder_address`.

### REFACTOR
#### DOCUMENTMANAGER/IMPORTEXPORT (cua de descàrregues i exportació genèrica fora d'`importexport`)
    - `ExportJob`, el seu serializer, els signals de Celery, `ExportJobViewSet`, `GenericExportView`, `export_jobs`, `export_registry`, `generic_export_service` i `export_permission_class` (abans `importexport/utils/permissions.py`, ara `documentmanager/utils/export_permissions.py`) passen a `documentmanager`. Les tasques `generic_export_task` i `cleanup_export_jobs` són ara `documentmanager.tasks.*` (beat actualitzat a `customers/celery.py`).
    - L'exportació CSV de comptadors (`MeterExportViewSet` i `export_meters_csv_task`) passa a `service` (`service/views/meter_export_view.py`, `service/tasks.py`). La URL `service/meter/export/csv/` no canvia.
    - La cua de descàrregues passa de `/importexport/export-job/` a `/documentmanager/export-job/` (el frontal s'actualitza alhora).
    - Migració `documentmanager.0018_exportjob`: si la taula `importexport_exportjob` existeix, la reanomena a `documentmanager_exportjob` i conserva les files; si no, la crea. `importexport.0002` només treu el model de l'estat i esborra la taula buida que `importexport.0001` hagi pogut crear en una BD nova. Provat en BD nova (tots dos ordres de migració) i en BD amb files existents.
    - Objectiu: que `importexport` quedi només amb les eines d'importació/exportació de dades de clients i pugui deixar de ser imprescindible.
    - Les tasques `importexport.tasks.*` que hi hagi a la cua de Celery en el moment del desplegament no es podran executar (nom canviat); cal desplegar amb la cua buida.

#### CORE/IMPORTEXPORT (codi de producció fora d'`importexport`)
    - Es mouen a l'app del seu domini els mòduls d'`importexport` que feia servir codi de producció o migracions; els noms de les comandes no canvien:
        - `contract/management/commands/`: `fill_contract_use_aca` (serializer, `contract_service`, `use_aca_service`) i `fill_contract_termination_date` (migració `contract.0218`).
        - `billing/management/commands/`: `feat_relate_modified_readings` i `fix_no_meter_readings` (migració `billing.0272`) i `recalculate_billing_invoices` (`recalculate_invoice`).
        - `billing/utils/basic_fix_utils.py` (migracions `billing.0288` i `0289`; `basic_fix_command` hi apunta).
        - `watchdog/management/commands/watchdog_variable_types.py` (`watchdog/services.py`).
        - `coredata/utils/location_utils.py` (`coredata/serializers.py` i els importadors).
        - `coredata/management/commands/create_superuser_and_token.py`.
    - La fixture dels tests passa de `importexport/fixtures/all_data.json` a `coredata/fixtures/tests/all_data.json`.
    - Verificat amb `importexport` i `prometeo` bloquejats: `check`, importació de tots els mòduls i `migrate` en una BD buida funcionen. Els tests de `billing.test_adjustment_service`, `service` i `contract` que carreguen la fixture ja fallaven abans (6 errors, la fixture té camps que ja no existeixen, p. ex. `CompanyConfig.mail_send_mail`).

### SECURITY
#### PROMETEO/FRONTEND (credencials versionades)
    - S'esborra `prometeo/auth_demo_with_tokens.json` (superusuari amb hash de contrasenya i dos tokens d'API fixos). `reset_db.sh` crea ara el superusuari i el token amb `create_superuser_and_token` i l'usuari OV amb `get_or_create_ov_user` (si hi ha `OV_USER_*`).
    - S'esborra `frontend/test-api.js`, un script de depuració amb un token fix.
    - Els tokens continuen a l'historial de git: cal regenerar-los als entorns que s'hagin creat amb `reset_db.sh`.

### FIX
#### BILLING/IMPORTEXPORT (`importexport/utils/fixes/basic_fix_utils.py` — migracions `billing.0288` i `0289` en una BD nova)
    - `cancel_payments_in_cancelled_commitments` i `fix_commitment_deposit_tokens` feien servir els models actuals (`from billing.models import CommitmentDeposit, ...`) en lloc dels històrics. En una BD buida, `migrate` petava a `billing.0289` amb `column billing_commitmentdeposit.start_date does not exist`, perquè el model actual inclou camps afegits per migracions posteriors (`billing.0321_commitment_start_date`). Ara fan servir `apps.get_model(...)`. Les BD ja migrades no es veuen afectades.

#### BILLING (`billing/opscripts/0007_fix_balance_return_movements.py` — BD nova sense `ConfigProject`)
    - El primer `ConfigProject.objects.get(token='invoice_status_paid_token')` quedava fora del `try` i feia petar `run_pending_scripts` (i, per tant, l'arrencada del contenidor `backend`) amb `ConfigProject.DoesNotExist` en una instal·lació nova. Ara, si el `ConfigProject` no existeix, l'script no fa res.
    - Revisats la resta d'opscripts (`billing`, `contract`, `coredata`, `statistics`): cap altre depèn d'un `ConfigProject` sense protegir.
    - Provat en local amb `docker compose up --build` sobre una BD buida: `migrate` i `run_pending_scripts` acaben bé i el `backend` queda `healthy`.

#### ORDER (`prometeo/data/order.OrderReason.json` — fixture de demo amb referència a un `OrderType` inexistent)
    - Les raons d'ordre 2 (frau), 4 (impagament) i 6 (baixa de contracte) referenciaven el tipus d'ordre 15, que no existeix a `order.OrderType.json` (hi ha 1–14 i 16–22). `loaddata prometeo/data/*.json` és atòmic i fallava amb `ForeignKeyViolation` a `order_orderreason_type`, de manera que `prometeo/reset_db.sh` deixava la BD sense cap dada base (`ContractStatus`, `BillingStatus`, `Bank`…) tot i acabar dient «loaded successfully». S'ha tret la referència penjada.
    - Provat en local amb `reset_db.sh --force`: es carreguen 2853 objectes de 95 fixtures, les importacions acaben amb 0 errors i es generen factures fins al lot 124 (2026M07).


## [08-10-2026]

### FEAT
#### STATISTICS/IMPORTEXPORT (`statistics/views/reports_views.py`, `importexport/utils/export_jobs.py` — padró de facturació a la cua de descàrregues)
    - `register-billing-summary` (Padró de facturació), `mini-register-billing-summary` (reduït) i `no-aca-register-billing-summary` (resum sense ACA) passen per la cua de descàrregues de l'usuari (`ExportJob`) amb el nou helper `enqueue_report_export()`. El padró, que es genera als últims passos de la facturació i pot tardar molts minuts (4,7 min de mitjana, màxim 15,7 min en local), ja es pot recuperar encara que l'usuari surti del lot.
    - La resposta manté `task_id` i hi afegeix `export_job_id`. `export_name` opcional al cos per al nom visible; no arriba a l'informe.
    - Un resultat `{"status": "warning"}` de `run_report_task` (p. ex. sense dades) es desa a la cua com a error amb el missatge de l'informe.
    - Provat en local amb un worker real (padró i padró reduït d'un lot de 12 factures).

#### IMPORTEXPORT (`importexport/models.py`, `importexport/signals.py`, `importexport/utils/export_jobs.py`, `importexport/views/export_job_view.py`, `importexport/tasks.py`, `customers/celery.py` — cua general de descàrregues)
    - Nou model `ExportJob` (migració `importexport/0001`): una fila per cada fitxer que un usuari demana generar en segon pla, amb `requested_by`, `kind`, `name`, `params`, `task_id`, `status` (pending/running/completed/failed/cancelled), `document` (o `file_url` per a fitxers temporals), error i dates. Abans el `document_id` només quedava al resultat de Celery i, si l'usuari marxava de la pàgina, el fitxer era inaccessible.
    - `enqueue_export(request, task, kind=, name=, args=, kwargs=)` crea la fila i despatxa la tasca amb el `task_id` generat abans (`on_commit`). Els signals `task_prerun`/`task_postrun` de Celery la passen a en curs i la tanquen amb el `document_id`/`file_url` retornat, **sense modificar les tasques**. Un resultat `{"status": "error"}` amb estat SUCCESS es desa com a error.
    - Nou `GET /importexport/export-job/` (només les de l'usuari connectat; `?active=true`), `GET /<id>/`, `DELETE /<id>/` (la treu del panell, no esborra el document), `POST /<id>/cancel/` (revoca la tasca) i `POST /clear-finished/`. El llistat reconcilia amb `AsyncResult` les que segueixen actives per si s'ha perdut el signal.
    - Tasca diària `cleanup_export_jobs` (00:45): dona per fallides les que porten més de 12 h actives i esborra les files de més de 30 dies (els documents es conserven).
    - L'exportació genèrica (`GenericExportView`, els ~40 `…/export/` dels llistats) i `POST /billing/reading/export-readings/` ja passen per la cua: la resposta manté `task_id` (compatible amb `/task-progress/`) i afegeix `export_job_id`. Query param opcional `export_name` per al nom visible.
    - Provat en local amb un worker real: pendent → en curs → completada amb document, cancel·lació, error, i que un altre usuari no veu la feina (404).

#### CONTRACT (`contract/utils/aca_exchange_file_parser.py`, `contract/utils/aca_document_apply_service.py`, `contract/views/aca_document_view.py`, `contract/signals.py` — importar bonificacions ACA des del fitxer TXT)
    - `POST /contract/aca-document/` accepta ara els fitxers d'intercanvi de l'ACA de 350 posicions (documents 04 Ampliació de trams i 05 Tarifa social del ZIP «Estructura dels fitxers» de l'ACA): `ATCCCCaammddXnnn.txt`, `CSCCCCaammddXnnn.txt` i els tancaments amb prefix `TA-` (també s'accepta l'antic `TA_`), a més de les taules HTML d'abans. Tipus, entitat i data surten de la capçalera; el `source` ara diu "ACA" només si el nom porta `A` (abans era sempre "ACA").
    - `ACADocumentChange` (migració `contract/0244`) guarda data de sol·licitud, nombre de persones (AT), col·lectiu de tarifa social i informe col·lectiu (CS), resultat del tràmit i si és un tancament (dígraf `TA` o codis 20-23). `accepted` es proposa a partir del resultat (01 o tancament); la resta queden per revisar.
    - En passar el document a l'estat `aca_bonification_processed`, `apply_aca_document` crea la bonificació amb les seves variables o, si és un tancament, dona de baixa l'activa del contracte. A la tarifa social el tipus surt del col·lectiu: AT → ACA-CANON-ATUR; CJ/CI/NC → PENSIONS; RM/NB/FA/LM → PROTECCIO; 90/92 → EXCLUSIO. Abans: creava bonificacions amb `contract=None` si no trobava la pòlissa, les duplicava a cada desat i triava el tipus per `icontains` sense ordre. Ara cada línia queda marcada (`applied_at`, `bonification`) i no es reaplica, i si el contracte ja té la bonificació activa la reutilitza. Les bonificacions que entren per aquí no generen `ACABonificationRequest` pendent de tornar a enviar a l'ACA.
    - Lectura del fitxer: Windows-1252 o UTF-8, amb CRLF o LF; el codi postal sense el zero de l'esquerra ("8310") es completa a 5 xifres. Es rebutja el fitxer si falta la capçalera, si hi ha un codi de registre desconegut, una línia de més de 350 caràcters o si el registre de total no quadra amb el nombre de sol·licituds. La pujada (document + línies) és atòmica.
    - Aplicació de cada línia: el contracte es busca pel número de pòlissa, exacte o amb el token sense '/' (mateix criteri que l'export); la persona entre el titular, propietari i llogater del contracte que tingui el DNI de la línia, i si no el titular (no es busca el DNI a tota la taula: n'hi ha de genèrics, com 99999999R, compartits per centenars de persones). `requested_at`/`start_at` són la data de sol·licitud de la línia. La variable de tarifa social caduca al cap d'un any (com feia el codi anterior); l'ampliació de trams no té data de fi, perquè l'ACA n'envia el tancament. A l'AT, el nombre de persones es desa a ACA-TRAM-MEMBRES i, via signal, a `Contract.total_persons`. Un tancament dona de baixa totes les bonificacions actives del tipus del document, també les duplicades (a CS no se sap el col·lectiu).
    - El signal `assign_variables` ja no aplica els AT generats per la pròpia aplicació (`source` entitat amb `ACABonificationRequest` vinculades) encara que es marquin com a processats.
    - `GET /coredata/person/token/<token>/` retorna 409 amb el nombre de persones quan el document està repetit (abans 500 per `MultipleObjectsReturned`). A la instal·lació A hi ha 820 persones amb 99999999R.
    - Tests unitaris del parser a `contract/tests/test_aca_exchange_file_parser.py` (dades sintètiques).
    - **Pendent / sabut**: no es genera el fitxer de resposta a l'ACA amb el resultat del tràmit de les sol·licituds rebudes amb `A` (ara només s'apliquen); no es generen fitxers CS de sortida ni el ZIP d'informes de vulnerabilitat (col·lectius 90/92); ACA-CANON-ENTITATS no té cap codi de col·lectiu al fitxer i no s'hi pot assignar. El frontal no cal tocar-lo: la pantalla de documents ACA ja accepta qualsevol fitxer.

### MODIFIED
#### IMPORTEXPORT/BILLING (`importexport/utils/export_registry.py`, `billing/tasks.py` — consultes per fila a les exportacions)
    - Factures: `select_related` de contracte, estat, forma de pagament i origen (feia ~4 consultes per factura). 73k factures: 114 s → 12 s.
    - Comptadors: el primer punt de subministrament es llegeix del prefetch (`.first()` l'ignorava perquè SupplyPoint no té `Meta.ordering`). 13k comptadors: 57 s → 2,3 s.
    - Punts de subministrament: `select_related` de tota la cadena que llegeix `str(Address)` (carrer, tipus, número, tipus de número, país). 12k punts: 35 s → 2,8 s.
    - Propietats: el nombre de punts de subministrament ve d'un `annotate(Count)` en lloc d'un `count()` per fila. 6k propietats: 5,2 s → 0,6 s.
    - Exportació de lectures: `select_related("meter")` i workbook `write_only` amb `iterator()`.
    - Contingut verificat idèntic a l'anterior (3.000 files per entitat, totes les columnes).

#### STATISTICS (`statistics/utils/report_service.py` — Padró de facturació)
    - El workbook es serialitzava dues vegades (`wb.save(filename)` a disc i un altre cop dins de `save_report`). Amb milers de columnes cada desat trigava ~40 s i era el temps que la tasca es quedava pendent després d'arribar al 100 %. Ara es desa un sol cop a memòria i els mateixos bytes van a la resposta i a `save_report`; ja no s'escriu cap fitxer temporal a disc.
    - `select_related` de la cadena que llegeix `str(Address)` i `get_address_complete_without_city` (carrer i tipus de via, número i tipus de número, població, país) a totes les adreces del contracte, de la baixa i del contracte de la sol·licitud (nou helper `_address_display_relations`). Feia ~12 consultes per factura: amb 1.730 factures, ~20.700 → 22 consultes.
    - Els màxims històrics que dimensionen les columnes (línies per producte, correctors per línia, lectures per factura) només compten les factures amb `issue_date` a partir de `ConfigProject` `ov_pdf_from` (2026-01-01 si no està configurat). Les factures importades d'anys enrere amb fins a 120 línies de cànon en una sola factura reservaven 120 blocs de CANON AIGUA (ACA), ~1.900 columnes buides a cada exportació. Les factures del rang exportat encara poden ampliar la reserva, de manera que no es perd cap import.
    - Workbook en mode `write_only` i sense estils (s'han tret el fons negre i la lletra blanca en negreta de les capçaleres i de la fila TOTAL del full resum). Les amplades de columna es mantenen, calculades des de les capçaleres.

### FIX
#### BILLING (`billing/views/billing_preinvoices_summary_view.py` — columnes Subtotal/Total girades al resum de facturació)
    - Al bloc «Conceptes» del resum de facturació del lot, la capçalera és `Subtotal | Total` però cada fila posava l'import amb IVA (`line_items.total`) a la columna Subtotal i la base (`line_items.price`) a la de Total, tant a les files de tarifa com a la fila destacada de cada producte. Ara la base va a Subtotal i l'import amb IVA a Total.

## [07-10-2026]

### FEAT
#### BILLING/COMMUNICATION (`billing/views/sepa_document_send_email_view.py`, `billing/views/sepa_pdf_view.py`, `billing/views/contract_sepa_pdf_view.py`, `billing/urls.py` — enviar el document SEPA per correu)
    - Nou `POST /billing/sepa-document/<id>/send-email/` (`id` del `GeneralPaymentSepaDocument`) amb cos `{email, contract_id, is_request?, company_config_id?, subject?, body?}`. Segueix el mateix flux que l'enviament de factures (`InvoiceSendEmailView`).
    - El PDF generat (`template`) es puja al gestor documental (`CONTRACT`/`SEPA` del contracte o sol·licitud) i s'adjunta a una `Communication` nova (persona = titular, vinculada al contracte si no és una sol·licitud), que s'envia amb `send_electronic_mail`.
    - Sense `company_config_id`, el remitent es dedueix de la companyia de l'explotació del contracte.
    - `SepaPDFDownloadViewSet` i `ContractSepaPDFView` retornen també `sepa_document_id`, a més de `pdf_url`.
    - **No s'ha provat amb un enviament real** (només resolució de la ruta i import amb Django).

#### OV (`ov/views.py`, `ov/serializers.py`, `ov/urls.py`, `customers/settings.py`, `docs/ov/openapi.yaml` — descàrrega de l'historial de consums i fix de format)
    - Nou `GET /ov/consumption/{id}/download/?contract_token=<token>[&format=pdf|csv]`: descarrega una única lectura del `GET /ov/consumptions/` (el `id` és el `Reading.id` del llistat). CSV real (columnes `id, period, reading, previous_reading, consumption, reading_date, is_estimated`); PDF és un stub fins que s'implementi la maquetació. Errors: `400` si falta `contract_token` o el `format` no és `pdf`/`csv`, `404 {error: "Contract not found"}` amb token desconegut i `404 {error: "Reading not found"}` si la lectura no existeix o no pertany al comptador del contracte.
    - Nou `POST /ov/consumptions/download/` amb cos `{contract_token, reading_ids?, date_from?, date_to?, format?}` (`format` `pdf|csv|zip`, per defecte `pdf`): descarrega només les lectures de `reading_ids` (filas marcades al frontal) o, si no s'indicam, tot el conjunt filtrable per `date_from`/`date_to` («Seleccionar tot»). `reading_ids` desconeguts responen `400` amb el camp concret, un `date_from` posterior a `date_to` `400` per camps (`ValidationErrors`), i un contracte inexistent `404`. CSV real; PDF i ZIP són stubs.
    - `docs/ov/openapi.yaml` ampliat amb els paths `/ov/consumption/{id}/download/` i `/ov/consumptions/download/`, els paràmetres `consumptionIdPath`/`contractToken`/`downloadFormat`, la resposta `ValidationErrors` i l'esquema `ConsumptionDownloadRequest`. `ConsumptionHistoryItem` exposa ara el camp `id` (obligatori), coherent amb el llistat.
    - `customers/settings.py`: `URL_FORMAT_OVERRIDE: None`. El `format` és un paràmetre de negoci dels endpoints de descàrrega OV (i del download de lots de lectures) i DRF el reservava per a la negociació de contingut (`?format=csv` provocava `404 {"detail": "No encontrado."}` abans d'entrar a la vista). La selecció de renderer continua funcionant via capçalera `Accept` i sufixos d'URL.
    - Nous tests de consistència `docs/ov/test_openapi_consistency.py` (cada path de l'OpenAPI documentat a la taula de resum i cada fila té el seu path) i verificació funcional en local: 35 casos (descàrregues csv/pdf/zip, errors 400/404/401, `reverse` de les dues rutes) tots verds. El runner de tests ja descobreix `docs/` com a paquet (`docs/__init__.py`, `docs/ov/__init__.py`).

#### OV (`ov/views.py`, `ov/serializers.py`, `ov/urls.py`, `docs/ov/openapi.yaml` — endpoint per llistar els períodes de facturació disponibles)
    - Nou `GET /ov/billing-periods/?contract_token=<token>`: llista dels periodes de facturació disponibles per al contracte, per al selector de «Primera domiciliació» del frontal. Els cicles (trimestral, bimestral, etc.) els defineix el PA i varien segons el contracte, per això el frontal no pot hardcodejar-los i el backend els exposa.
    - Cada període té `year` (`2026`), `period_code` (`1T`, `2T`, `3T`, `4T`), `months_label` (mesos naturals llegibles, p. ex. `julio-septiembre`) i `is_current` (període en curs, per als avisos del frontal). Esquema `BillingPeriodItem` documentat a `docs/ov/openapi.yaml`.
    - De moment la llista és un **mock fix** de 2 períodes (`1T` i `2T` del 2026) mentre no s'integri amb el PA; el `contract_token` es valida igual que la resta d'endpoints, amb `400 {error: "Contract token is required"}` si falta i `404 {error: "Contract not found"}` si el contracte no existeix.
#### INCIDENT (`notification/models.py`, `notification/migrations/0024_incident_cluster.py`, `notification/serializers/incident_serializer.py`, `notification/filters/incident_filter.py` — vincular una incidència a una bateria)
    - Camp nou `Incident.cluster` (FK a `Cluster`, `related_name='incidents'`), amb migració `0024_incident_cluster`.
    - `IncidentSerializer` retorna la bateria amb `ClusterListSerializer`. Per desar-la s'envia `cluster` amb l'id (`IncidentSaveSerializer` ja fa servir `__all__`).
    - `IncidentFilter`: paràmetre nou `?cluster=<id>`; el cercador també troba incidències pel token de la bateria, i el filtre per explotació inclou `cluster__connection__exploitation`.

#### CONTRACT/BILLING (`contract/utils/contract_service.py`, `billing/utils/request_initial_reading_service.py`, `billing/serializers/reading_serializer.py` — lectures posteriors a la lectura inicial passen al contracte nou)
    - En finalitzar l'alta, `contract_create()` crida `move_newer_readings_to_contract()` per cada lectura inicial: les lectures posteriors del mateix punt i comptador passen al contracte nou. Es fa en finalitzar i no en triar la lectura, així que si la sol·licitud no s'acaba no es mou res.
    - Només es mouen lectures dels contractes donats de baixa per la sol·licitud (no les còpies d'altres contractes que comparteixen comptador), pendents de facturar (`PENDING_READING_FILTER`), i ni de tancament ni inicials. Si la sol·licitud no té cap baixa vinculada, no es mou res.
    - Es desvinculen les prefactures del contracte anterior que incloguin aquestes lectures, i la primera lectura moguda passa a tenir la inicial com a `previous_reading` (el consum no canvia).
    - `ReadingSerializer` retorna `is_billed` (té factura definitiva). El frontal ho fa servir per deixar triar com a inicial només la darrera lectura facturada o una de posterior.
    - **Pendent**: no es mouen els moviments de bossa d'estimació de les lectures estimades ni es toca el `batch`. La restricció de la darrera facturada només és al frontal.
    - **No s'ha provat amb una alta real** (només compilació i import amb Django).

### FIX
#### ORDER/INCIDENT (`notification/filters/incident_filter.py`, `order/serializers/order_serializer.py`, `got/serializers.py` — la incidència que genera una ordre no sortia a la pestanya «Incidències» de l'ordre)
    - Hi ha dues relacions: `Incident.order_incident` (incidència sobre una ordre) i `Order.incident` (ordre generada des d'una incidència). La capçalera de l'ordre mostrava `order.incident`, però la pestanya i el comptador `related_incidents` només miraven `order_incident`.
    - El filtre `?order=` retorna ara les dues (`Q(order_incident__id) | Q(orders__id)`, amb `distinct`), i `related_incidents` les compta igual a `OrderSerializer` i `OrderGotSerializer`.

#### CONTRACT/LOGGER (`customers/settings.py`, `contract/middleware.py`, `service/middleware.py`, `contract/signals.py` — l'historial de modificacions no registrava l'usuari real)
    - L'API s'autentica amb `TokenAuthentication` de DRF, que es resol dins la vista. `order.middleware.CurrentUserMiddleware` i `contract.middleware.UserMiddleware` s'executaven abans, quan `request.user` encara era anònim, així que `get_current_user()` retornava sempre `None`. En aquest cas, `contract_pre_save` agafava el primer usuari de la BD (`customers`/«Administrador»).
    - `ov.middleware.RestrictOVUserMiddleware`, que ja resol l'usuari del token, passa a executar-se abans dels middlewares d'usuari actual.
    - `contract.middleware.UserMiddleware` no peta si `request.user` és `None` (token invàlid).
    - `service.middleware` no estava registrat a `MIDDLEWARE` i els signals de `service` sempre rebien `None`. Ara reutilitza el thread-local de `contract.middleware`.
    - Nou signal `contract_created_log`: en crear un contracte es desa a `ContractLog` una línia `created` amb el token i l'usuari que l'ha donat d'alta.
    - Provat amb la cadena de middlewares i un token d'un usuari de prova: `contract`, `order` i `service` reben l'usuari real; amb un token invàlid reben `None` sense errors.
    - **Pendent**: a Celery i a les comandes no hi ha usuari i les modificacions continuen assignant-se al primer usuari. Els registres antics no es corregeixen.

#### BILLING
    - Invoice service, al guardar 'real_consumption' NO estava tenint en compte les lectures de canvi de comptador. Ara té totes en compte.

#### CONTRACT/STATISTICS (`importexport/management/commands/fill_contract_use_aca.py`, `statistics/utils/report_billing_service.py` — la Declaració ACA petava i tots els contractes sortien com a ramaders)
    - Detectat a la instal·lació M (Docker dins del servidor L): la «Declaració ACA» fallava sempre amb `ArticleCode matching query does not exist`. L'error només quedava a `ReportQueue.error_message`, perquè l'informe corre a Celery.
    - `fill_contract_use_aca`: els `ConfigProject` `contract_use_aca_*_tokens` es partien amb `.split('|')`, i un valor buit donava `['']`. Com que la comparació és `token_key in token` i `'' in 'CANON-DOM'` sempre és cert, el token buit coincidia amb qualsevol tarifa. Tots els contractes rebien el mateix ús, normalment `Q` (ramader sense cànon), i les factures el copien a `used_aca` en emetre's. Ara es fa servir `split_config_tokens`, que descarta els tokens buits. Si la configuració no té cap token buit, el comportament és el mateix d'abans; si en té, el contracte que no coincideix amb cap tarifa es queda com estava. També afecta el recàlcul automàtic en canviar la tarifa d'un contracte.
    - `_get_aca_part_tokens`: si falten els `ArticleCode` `part_fixa`/`part_variable`, l'error diu quins falten i quines ordres cal executar (`watchdog_fix_aca_config` i `fix_aca_lineitemtype_articles`), en lloc d'un `DoesNotExist` genèric. Amb la configuració correcta, no canvia res.
    - **Dades corregides a producció (instal·lacions M i N, servidor L)**, igualades amb la resta de pobles: s'han creat els `ArticleCode` `part_fixa`, `part_variable` i `ramader_0`, s'han omplert els tokens ACA, s'ha posat `dir_variable` = `Factura-ACA` i s'han vinculat les línies PART FIXA/VARIABLE. També s'ha recalculat `use_aca` dels contractes: 492 a la instal·lació M i 398 a la instal·lació N; els 9 EXEMPT sense cànon de la instal·lació N han quedat buits. A la instal·lació N s'ha afegit `CANON-SOC` als tokens domèstics. S'ha realineat el `used_aca` de 480 i 383 factures, gairebé totes del 3T 2026. Hi ha backups i CSV amb els valors anteriors a `/var/www/<poble>/backups/*20261007*`.
    - **Desplegament**: a la instal·lació M el token municipal continua buit. Fins que no es desplegui aquest canvi, un canvi de tarifa d'un contracte el marcaria com a municipal (`A`).

#### COMMUNICATION (`communication/utils/message_service.py`, `communication/serializers/communication_serializer.py` — tipus de comunicació «Ambdues» envia per correu i per carta)
    - El contracte permet triar `communication_type = 'BOTH'` («Ambdues»), però l'enviament no el tenia en compte. A la generació massiva amb procés «default» sortia només per carta, i a la comunicació individual en mode «default» petava (`msg_type` sense assignar).
    - Ara, en tots dos camins, un contracte `BOTH` genera una sola comunicació amb els dos tipus (correu i carta), els missatges del procés de cada tipus, i `used_email` i `used_address` informats. Si no té correu només va per carta, i si no té adreça només per correu. La facturació electrònica (FACe) continua tenint prioritat a la massiva.
    - Els processos «digital» continuen enviant només correu, i els processos amb tipus triats explícitament no canvien.
    - Comunicació individual d'un contracte `DIGITAL` sense `used_email` a la petició: es desava l'objecte `PersonContact` a `used_email` (`EmailField`) i petava amb `TypeError`. Ara s'hi desa l'adreça electrònica.
    - **Pendent**: l'informe de cartera (`report_wallet_service`) compta `BOTH` com a digital, i `fix_communication_send`, com a carta.

## [06-10-2026]

### FEAT
#### OV (`ov/views.py`, `ov/serializers.py`, `ov/urls.py`, `ov/throttles.py`, `pagination/ov_pagination.py`, `docs/ov/openapi.yaml` — llistat de contractes per DNI i detall per token)
    - Nou `GET /ov/contracts/` que, donat un DNI, retorna tots els contractes on aquest DNI és tant el titular (`holder__token`) com el titular del compte de domiciliació (`payment__IBAN__person__token` o `payment__IBAN__dni`), amb selecció de `status` via `?estado=<status_token>`. Pensat perquè una Oficina Virtual resolgui el DNI que l'usuari acaba d'entrar sense haver d'encertar el token de contracte.
    - Nou `GET /ov/contract/{token}/` amb el detall complet del contracte (titular, estat, forma de pagament i IBAN, punt de subministrament per defecte amb adreça i ús). Respon `404` amb `{error: "Contract not found"}` si el token no existeix.
    - Paginació nova `pagination/ov_pagination.py` (`OVLimitPagination`): el tamany ve per `?limit=` (per defecte 20, topat a 100, i valors no numèrics o inferiors a 1 tornen al per defecte) i la resposta és l'embolcall `{count, page, limit, total_pages, results}` documentat a l'OpenAPI. Una pàgina fora de rang es tradueix en `400 {error: "Invalid page"}`.
    - `ov/throttles.py`: `DniEnumerationThrottle` limita `GET /ov/contracts/` a 10 req/min per usuari autenticat. La clau de cache és l'usuari i no el DNI demanat — qui sondeja la base canvia de DNI a cada trucada, així que un comptador per DNI no saltaria mai. Sense aquest límit l'endpoint permetria enumerar abonats endevinant números de document.
    - **Nota**: el comptador fa servir la cache per defecte de Django (`LocMemCache`), és a dir, es guarda per procés i el límit real és `rate * GUNICORN_WORKERS`; assenyalar `cache` a un backend compartit el faria exacte. `rate` va a la classe, així que no cal cap entrada a `DEFAULT_THROTTLE_RATES` ni cap canvi de settings.
    - `docs/ov/openapi.yaml` ampliat amb els dos endpoints, els seus paràmetres, els esquemes `ContractListResponse`/`ContractListResult` i el detall de contracte.
    - Tots dos endpoints són `IsAuthenticated` i continuen dins l'abast de `RestrictOVUserMiddleware`, que confina el grup `ov` a les rutes `/ov/`.
    - Nou `GET /ov/invoice/{token}/detail/` amb el detall complet d'una factura definitiva, ampliant el llistat `/ov/invoices/` amb el període de facturació, la direcció tributària (condicional), les tarifes amb la seva normativa i el desglossament fiscal del recibo.
    - Només retorna factures definitives: filtra per `type_final` = `invoice_type_invoice_token` i exclou les prefactures (estat token `1`), igual que `/ov/invoice-pdf/`. Un token de presupost respon `404 {error: "Invoice not found"}`.
    - La direcció tributària només apareix si la factura està domiciliada (`payment_type_token_final` = `direct_debit_token`) i desapareix completament si no ho està. Quan el pagador és un tercer (`payer_token_final` ≠ `customer_token_final`) s'anonimitza: `anonimizada: true` i s'omet el carrer, deixant només codi postal, ciutat, província i país. L'absència física de la clau s'aconsegueix a `InvoiceFullDetailSerializer.to_representation`, que treu el camp si el mètode retorna `None`.
    - `tariffs` es composa de les línies de la factura (`InvoiceLineItem`), amb la normativa (`normativa`) resolta per `price_rate → billing_range_active → publication` (referència BOE). `fiscal_breakdown` agrupa dinàmicament els totals per organització (empresa de la línia o la del producte/tarifa) i els suma.
    - `billing_period` s'exposa com a objecte `{year, month, days}` i `dwelling_code` retorna `null` (sense camp al model encara; pendent d'ampliar el model de dades).
    - `docs/ov/openapi.yaml` ampliat amb el path `/ov/invoice/{token}/detail/`, el paràmetre `invoiceTokenPath` i els esquemes `InvoiceFullDetail`, `TariffDetail` i `FiscalBreakdownItem`. L'endpoint és `IsAuthenticated`.
    - Nou `GET /ov/meter/{token}/` amb les cinc dades del contador del bloc fixe de lectura de la Oficina Virtual: número de sèrie, calibre, cifras, any de fabricació i data d'instal·lació. El token de la ruta és el del contracte; el contador es resol des de `supply_point_default.meter`, el mateix origen que `meter_serial_number` i `meter_caliber` de `/ov/contract/{token}/`.
    - Disseny `200-nulls`: si el contracte existeix però no té punt de subministrament per defecte ni contador, la resposta és `200` amb els cinc camps a `null` (tots `nullable` a l'esquema) perquè el frontal pinti un estat buit sense tractar un `404`; un token de contracte inexistent respon `404 {error: "Contract not found"}` (component `NotFound` compartit amb `/ov/contract/{token}/`).
    - `MeterDetailSerializer` fa servir `SerializerMethodField` amb guarts explícits als dos nivells (`supply_point_default` i `meter`) en lloc de cadenes `source=`: una cadena `source=` a través d'un `None` intermedi no ho deixa passar i petaria amb `500` (el mateix problema que ja es va resoldre al detall de contracte amb titular nul).
    - `manufacture_year` (enter) i no `manufacture_date`: el model `Meter` només té `manufacturing_year` (enter, nullable) — no existeix cap camp de data de fabricació al sistema de gestió. `installation_date` ve de `installation_at` (data) i `digits` del camp `digits` (enter, nullable, defecte 5).
    - `docs/ov/openapi.yaml` ampliat amb el path `/ov/meter/{token}/`, el paràmetre `contractTokenPath` (reutilitzat) i l'esquema `MeterDetail`.
    - `docs/ov/openapi.yaml`: `/ov/meter/{token}/` deixa d'heretar el tag `Contrato` i passa a tenir tag propi `Contador` (nou a l'array global de `tags`, just després de `Contrato`, amb descripció pròpia), per separar arquitectònicament els endpoints de comptador dels de contracte. Els tres paths de contracte (`contract-detail/`, `contracts/`, `contract/{token}/`) mantenen `Contrato`.
    - Nou `GET /ov/consumptions/`: historial de consums del contracte en nomenclatura HF (`{any}-{q}T`), una fila per lectura del contador de `supply_point_default.meter` ordenada de més nova a més antiga, amb `reading` (lectura actual), `previous_reading` (lectura anterior), `consumption` (consum real), `reading_date` i `is_estimated`. Pensat perquè l'Oficina Virtual pinti la gràfica de consums sense haver de recórrer a la facturació.
    - `previous_reading` es resol al backend amb la cadena `Reading.previous_reading`, insensible a lectures estimades i a canvis de comptador, com a alternativa al `previous_reading` reconstruït al BFF.
    - `period` prové del `billing_period_year`/`billing_period_month` de la factura vinculada quan la lectura en té i, si no, del trimestre natural de la `reading_date` (criteri acordat: la factura sempre que es pugui, la data com a fallback). Com que `period` és un camp computat, `ConsumptionHistoryItemSerializer` l'exposa amb `SerializerMethodField`.
    - Envolcall paginat estàndard `{count, next, previous, results}` amb la nova `OVConsumptionPagination` (`page_size` per defecte 50, topat a 100). Filtres `date_from`/`date_to` sobre `reading_date`, inclusius; `date_from` posterior a `date_to` o dates malformades responen `400`. `contract_token` desconegut respon `404 {error: "Contract not found"}` i una pàgina fora de rang `400 {error: "Invalid page"}`.
    - `docs/ov/openapi.yaml` ampliat amb el path `/ov/consumptions/`, els paràmetres `dateFrom`/`dateTo`/`pageSize` i els esquemes `ConsumptionHistoryResponse`/`ConsumptionHistoryItem`. L'endpoint és `IsAuthenticated`.

#### CONTRACT (`contract/utils/contract_service.py`, `contract/serializers/contract_request_serializer.py`, `prometeo/integration/<instal·lació>/copy_change_of_name_variables.py` — el canvi de nom traspassa les variables)
    - Fins ara, en un canvi de nom les variables del contracte anterior no passaven al nou contracte: només es traspassaven les que s'havien afegit a mà a la sol·licitud.
    - En crear una sol·licitud amb `is_change_of_name`, `copy_change_of_name_variables` hi copia les variables del contracte actiu del punt de subministrament per defecte. Es fa en crear la sol·licitud (pas 1) perquè surtin preomplertes al pas 4 (Tarifa i Variables) i es puguin revisar o esborrar; en crear el contracte es traspassen com la resta de variables de la sol·licitud.
    - Criteris (`get_change_of_name_copyable_variables`): variables amb `is_active`, vigents avui (sense `start_at`/`end_at` es considera vigent, com fa la facturació a `generate_variables`) i que no tinguin `aca` ni `social` al token de la variable ni del seu tipus: les bonificacions ACA i socials depenen del titular i s'han de tornar a sol·licitar. No es copia cap tipus que la sol·licitud ja tingui, ni la bonificació vinculada.
    - Es copien, no es mouen: el contracte anterior conserva les seves variables.

#### BILLING (`billing/models.py`, `billing/views/manage_commitment_deposit_request_view.py` — data d'inici del compromís de pagament)
    - `CommitmentDeposit` i `PaymentCommitment` guanyen el camp `start_date` (migració `billing/0321_commitment_start_date.py`. Al compromís és la data des de la qual es calculen els venciments i, a cada termini, l'inici del seu interval.
    - El pas 4 de `POST /billing/get-commitment-data/` llegeix `start_date_commitment` i el desa en crear un compromís nou (en ampliar-ne un d'existent no es modifica). Cada termini desa el seu `start_date`, en tots dos casos.
    - La data d'inici és informativa: el cobrament (`joined_payment_service`) continua filtrant només per estat, de manera que un termini es pot cobrar abans del seu inici.
    - Els compromisos existents queden amb `start_date` buit.

### FIX
#### BILLING (`billing/views/exclude_invoice_view.py`, `billing/views/exclude_billing_view.py`, `billing/views/billing_batch_generate_view.py`, `billing/tasks.py` — excluding a pre-invoice deletes it, so it is not billed with the original batch)
    - When a pre-invoice is excluded from the batch, it is deleted, and its readings are moved to the "excluded" batch. This batch inherits the biller and routes from the source; without a biller, generating pre-invoices for it would crash with an `'NoneType' object has no attribute 'period_type'` error.
    - The readings leave the original batch, so they are not billed with it; instead, they are billed when pre-invoices are generated for the excluded batch.
    - Final invoice generation does not include pre-invoices that remain marked as excluded. If an excluded batch lacks a biller, the source batch's biller is retrieved before reading the `period_type`.
#### CONTRACT (`contract/utils/contract_pdf_service.py` — data dels documents al PDF del contracte)
    - El PDF del contracte mostrava el número de la cèdula d'habitabilitat (text del document) però mai la data: només es buscava en un document a part amb token `data_cedula`, que no existeix, i el formulari de documents del front no demana cap data.
    - Nou `documentation_dates` al context del PDF, amb les mateixes claus que `documentation_texts` (token del tipus de document). Conté la mateixa data que el front mostra al costat de cada document: `created_at` del `ContractRequestDocumentation` o, si no n'hi ha, la `date` del fitxer. Es passa a hora local abans de formatar-la (`dd/mm/YYYY`) perquè un document pujat a prop de mitjanit no surti amb un dia de diferència respecte del front.
    - És la data de pujada del document, no la d'emissió de la cèdula o del butlletí.
    - El template personalitzat de la instal·lació L (`customers-clients-data`) en fa ús per a la cèdula i el butlletí d'instal·lador; s'han de desplegar alhora.

#### DEPLOY (`config/pull_templates_docker.rb` — les cartes d'impagats de la instal·lació L no es generaven als desplegaments Docker)
    - Detectat a la instal·lació I (Docker dins del servidor L): ni l'avís d'impagament ni la carta de suspensió generaven el PDF.
    - Causa: les plantilles de la instal·lació L encadenen la versió catalana i la castellana amb `{% include "pay_reminder_template_body_ca.html" %}` / `_body_es.html` (igual a `letter_suspension_template`). `copy_lang_template_variants` només copiava `{base}_{lang}.html` i `{base}_personalized_{lang}.html`, així que els fragments `_body_` no arribaven al contenidor i el render petava amb `TemplateDoesNotExist`. El desplegament sense Docker (`pull_templates.rb`) copia `pay_reminder_template*.html` i no tenia el problema.
    - `copy_lang_template_variants` copia també `{base}_body_*.html`. Afecta totes les plantilles que la fan servir; si un client no té fragments `_body_`, no canvia res.
    - Provat en local: amb només la plantilla principal es reprodueix el `TemplateDoesNotExist`; amb els fitxers que copia ara el script, el PDF es genera sense errors.
    - Cal tornar a desplegar les instal·lacions Docker de la instal·lació L (instal·lacions I i D) perquè s'apliqui.

#### BILLING/STATISTICS (`statistics/utils/billing_amount_average.py`, `statistics/tasks.py`, `billing/tasks.py`, `billing/views/billing_view.py`, `billing/utils/recalculate_invoice_service.py` — l'avís d'import alt té en compte el període de l'any)
    - L'avís d'import alt comparava cada factura només amb la mitjana de totes les factures del contracte, de manera que el rebut d'estiu (piscina, reg) saltava cada any. Ara l'avís només surt si l'import supera en un 50% la mitjana completa (com fins ara) **i també** la mitjana del mateix període d'anys anteriors. Si el contracte no té històric d'aquest període, queda només la mitjana completa. El canvi només pot treure avisos de pics estacionals recurrents, mai afegir-ne.
    - Període: el mes de facturació (`billing_period_month`) amb un mes de marge a cada banda, perquè una tanda trimestral no sempre s'emet el mateix mes. Només compten factures d'almenys 10 mesos enrere (anys anteriors) i amb import positiu.
    - Nou `statistics/utils/billing_amount_average.py` com a font única de la lògica (`is_high_amount_for_period` i `TotalAmountAvgCache` per a la generació massiva). Els quatre llocs que calculaven l'avís (generació massiva, contractes seleccionats, generació individual i recàlcul) ho feien cadascun d'una manera una mica diferent i ara fan servir el mòdul.
    - `BillingConsumption.total_amount_avg` passa a ser la mitjana del mateix període d'anys anteriors (amb la factura actual), i si no n'hi ha, la de totes les factures com fins ara. Els registres existents no s'han recalculat; només canvien les factures que es processin a partir d'ara. L'avís no en depèn, perquè calcula les mitjanes al moment.
    - Per què no s'ha substituït directament la mitjana completa per la del període: sortien més avisos que abans. Amb facturació mensual la finestra incloïa la factura del mes anterior (un pic tapava el mes següent), el període de l'any anterior es va facturar amb tarifes més baixes i els abonaments negatius esbiaixaven mitjanes de poques mostres.
    - Simulat sobre les factures del 2026 amb només l'històric anterior a cada factura: a la instal·lació A, estiu de 1.671 a 1.338 avisos (−20%) i resta de l'any de 594 a 548; a la instal·lació B, estiu de 1.258 a 1.184 i resta de 2.947 a 2.748. La versió en bloc i la individual donen el mateix resultat en 2.000 factures de la instal·lació A.
    - **Pendent / risc**: si el mateix període de l'any anterior ja tenia un import anòmal (p. ex. una fuita), una anomalia igual aquest any no saltarà. Passa sobretot quan només hi ha una factura anterior del període, cosa habitual a la instal·lació A.

#### BILLING (`billing/utils/reading_batch_service.py`, `billing/views/reading_batch_generate_view.py`, `billing/views/reading_batch_setup_view.py` — resum del lot de lectures: el número no quadrava amb el llistat)
    - Els comptadors del resum (`GET /billing/reading-batch-summary`) i els llistats que s'obren en clicar-los (`GET /billing/reading-batch/setup/{id}/?readings=<filtre>`) es calculaven amb consultes diferents. Els comptadors aplicaven `PENDING_READING_FILTER` i els llistats no, de manera que en un lot amb lectures ja facturades el llistat sortia més llarg que el número.
    - Nova `get_setup_filter_supply_point_ids(batch, filtre)` (i `SETUP_FILTERS`) com a font única de cada apartat (`missing`, `extra`, `reader_alert`, `remote_alert`, `no_reading_value`, `remote_reader`, `inactive_sp`): el comptador és la mida del conjunt i el llistat el pagina. Els apartats basats en lectures només compten les pendents de facturar. Els set blocs duplicats del setup queden en un.
    - Lectures sobrants: abans el comptador era `lectures_als_fitxers - punts_del_lot` i el llistat la diferència de conjunts (amb una condició que el deixava buit si als fitxers no hi havia més lectures que al lot). Ara tots dos són els punts de subministrament dels fitxers que no són del lot (`get_extra_supply_point_ids`).
    - Bloc de lectures processades: `total`, `total_billed` i el recompte de cada alerta es calculen sobre la mateixa base que `by-batch-minimal` (sense lectures tancades ni de control). Les alertes ja no exclouen les lectures amb factura, que el llistat sí que mostrava. Nous `total_warnings` i `total_correct`, iguals als llistats `alert=any` i `alert=null`.

#### PAYMENT (`billing/views/payment_view.py` — retorns SEPA: error 500 sense data de retorn i detecció del cobrament retornat)
    - `POST /billing/payment/manage-rejection-payments/` petava amb `ValueError: Cannot use None as a query value` des de `9977c6da` (05-10-2026): els moviments es filtraven per `movement_date__lte=return_date`, i `return_date` és `None` quan el frontal no envia la data i el primer pagament no porta `rjt_dt` (que és el que passava sempre, veure el changelog del frontal). Ara la data de cada pagament es resol primer amb `_resolve_rejection_date` (mai és `None`) i els moviments es filtren per aquesta data.
    - El retorn ja no depèn del `payment_type_token` actual del pagament, que canvia si després es cobra per una altra via: es busca l'últim moviment cobrat per domiciliació (`payment_type` DIRECT_DEBIT i estat pagat) fins a la data de retorn. Els pagaments històrics sense moviments continuen mirant el tipus del pagament. El moviment de retorn es genera com a DIRECT_DEBIT i amb el banc d'aquell cobrament.
    - Si aquell cobrament ja té un moviment de retorn amb el mateix motiu (p. ex. es torna a carregar el mateix fitxer), no se'n genera un segon: només s'actualitzen el motiu i la data de rebuig.
    - **Pendent**: com que no es miren moviments posteriors a la data de retorn, un pagament domiciliat cobrat per caixa després d'aquesta data es retornaria igualment.

### CHORE
#### OV (`ov/views.py`, `ov/serializers.py`, `ov/urls.py` — agrupació d'imports i rutes natives dins del mòdul)
    - Els imports afegits durant la implementació dels endpoints OV havien quedat escampats: tres `from ov.serializers import X` solts, `Q` i `NotFound` per fora dels seus grups i `ConfigProject` importat dins del mètode `get_queryset`. Ara van tots al capçal, dins del bloc `from ov.serializers import (...)` o del grup django/rest_framework que els toca, i `ConfigProject` és un import de mòdul.
    - `ov/urls.py`: les rutes `contracts/`, `contract/<token>/` i `invoice/<token>/detail/` es declaraven amb `urlpatterns.append()` i imports locals just abans de cada `append`; passen a ser entrades natives dins de la llista `urlpatterns`, amb els views al bloc `from .views import (...)` del capçal. Cap URL ni nom de ruta canvia: és un canvi pur d'estructura (`f88439dd`).

## [05-10-2026]

### FEAT
#### SERVICE/STATISTICS (`service/models.py`, `statistics/utils/incasol.py`, `report_service.py`, `report_incasol_liquidation_service.py` — número de concert INCASOL per explotació)
    - `Exploitation` guanya el camp `incasol_num` (migració `service/0130_exploitation_incasol_num.py`): el número de concert deixa de ser un únic valor global i passa a ser propi de cada explotació, editable des de la fitxa de l'explotació al frontal.
    - Nou `statistics/utils/incasol.py` amb `resolve_incasol_num(exploitation_id)`: retorna el número de l'explotació i, si és buit o no arriba `exploitation_id`, cau al `ConfigProject` global `incasol_num` de sempre. Cap instal·lació canvia de comportament fins que algú ompli el camp.
    - Els dos informes d'INCASOL hi passen l'`exploitation_id` que el formulari de reports ja enviava i que fins ara s'ignorava: l'XLSX «Fiances INCASOL» (`generate_bails_report`) i el TXT «Liquidació de Fiances INCASOL» (`generate_incasol_liquidation_report`). El prefix `S` i el número de liquidació (`77<trimestre><aa><num>`) es componen com abans.
    - **Pendent**: cap dels dos informes filtra encara les fiances per explotació; triar una explotació al formulari només determina el número de concert, no el conjunt de dades.
    - Nous tests `statistics.tests.IncasolNumResolutionTests` (7 casos: prioritat, fallback amb valor buit/explotació inexistent/sense id, i lectura, escriptura i esborrat del camp pel serializer).

### FIX
#### BILLING (`billing/utils/invoice_suppression_service.py`, `billing/views/invoice_view.py`, `billing/serializers/invoice_serializer.py` — anul·lar una factura sempre genera l'abonament)
    - La paperera «Anul·lar factura» del panell de factures personalitzades (`AddInvoiceBudget.vue` → `ChangeStatus.vue`) fa un `PUT /billing/invoice/<id>/` amb `status_token` Abonada (-6) o Anul·lada (-7). `InvoiceFullSerializer.update()` només canviava l'estat: la factura quedava anul·lada amb número de sèrie legal i sense abonament (FR) ni `return_token`. Els informes no quadraven entre ells (l'ACA les descarta i el Resum IVA les suma) i quedava un forat a la sèrie.
    - La lògica de `PUT /billing/invoice/<id>/return/` passa a `suppress_invoice()` (nou `invoice_suppression_service.py`), sense canvis de comportament. L'endpoint `/return/` la crida igual que abans.
    - `InvoiceFullSerializer.update()`: si l'estat destí és -6/-7 i la factura ho requereix (`invoice_needs_return`: factura emesa, no prefactura, no abonament i sense `return_token`), també passa per `suppress_invoice()`. Es genera la FR i l'estat triat es respecta, excepte que una factura amb cobraments no pot quedar mai com a Anul·lada. El saldo cobrat es retorna al moneder (`return_paid_total=True`), que és el que feia `check_cancel_invoice` en aquest camí. El motiu de text lliure continua anant a `Invoice.reason`.
    - Les prefactures continuen canviant només d'estat, perquè no tenen número legal.
    - **Pendent**: les factures ja anul·lades sense abonament no es regularitzen soles.

#### STATISTICS (`statistics/utils/report_billing_service.py` — informe ACA: el detall de factures no quadrava amb el resum)
    - Al full «Factures» de `generate_aca_summary_report` no sortien les factures d'ús ACA `I` de contractes ramaders/agrícoles (`use_type` = `contract_keeper_use_type_token`) amb preu diferent de 0. `ind_lines` excloïa els keepers, `ind_lines_free` només agafa línies amb preu 0, i el bloc `#KEEPER` que els recollia està comentat des de `0866736a`. El full resum sí que les comptava, perquè suma totes les línies ACA de l'explotació.
    - Es treu l'exclusió de keepers a `ind_lines`. Amb aquest canvi el detall quadra amb el resum (14.330,54 / 121.795,56). Efecte col·lateral: els volums «consumit» i «facturat» d'ús industrial gen/esp hi sumen el consum d'aquests contractes (+60 m³ al setembre), coherent amb el fet que paguen cànon industrial.
    - **Pendent**: `generate_aca_summary_report_second_ver` encara exclou els keepers d'`ind_lines` i els compta com a ramaders, així que el mateix contracte surt com a industrial en una versió i com a ramader en l'altra. `ind_lines_free` continua excloent els keepers amb ús `I` i preu 0.

#### BILLING/CONTRACT (`sepa_template.html`, `contract_sepa_pdf_view.py`, `sepa_pdf_view.py`, `contract_template*.html` i plantilles amb `company.website` — mandat SEPA i contracte incomplets)
    - Mandat SEPA: el codi postal, la població, la província i el país del deutor sortien buits perquè la plantilla llegia els noms d'una adreça serialitzada que només porta els ids. Les dues vistes passen ara l'adreça com a model (`debtor_address`).
    - Mandat SEPA: el «Nom del creditor» deia «Telèfon: <nom de l'empresa>».
    - Mandat SEPA domiciliat: la «Referència de l'ordre de domiciliació» era el número de contracte, però la remesa XML envia com a `MndtId` el `mandate_id` de la forma de pagament (p.ex. `261005007` al paper i `261005007P7513S000` al banc). Ara el paper mostra el `mandate_id`, i el número de contracte només si la forma de pagament no en té.
    - Contracte: el text deia sempre «Per a l'ús DOMÈSTIC» i el diàmetre sortia buit (la plantilla usava `diameter`, que no existeix al context). Ara mostra el tipus d'ús del contracte i el calibre del comptador.
    - Contracte, justificant de pagament, rebuts i factures: si l'empresa no té web, sortia «None»; ara queda buit.
#### PAYMENT
    - Al fer un retorn, mirar des de la dada de retorn i no després (no té sentit mirar moviments de futur si s'entra un retorn antic)
    - Modificat movement_date degut a error al fer un arreglo a payment movements per un pending script
#### BILLING/STATISTICS (`billing/tasks.py`, `statistics/tasks.py`, `customers/queue_utils.py` — matar tasques de la cua de facturació i d'informes)
    - El revoke a Celery (`terminate=True`, SIGKILL) ja es feia, però dins d'un `except: pass`: si el broker no responia, l'item quedava `failed` i la tasca continuava corrent. Ara `revoke_queue_task` registra l'error i llança `QueueTaskRevokeError`; les accions kill/skip/restart no toquen res i les vistes `.../action/` responen 503. Només es revoca si l'item està en `running`.
    - Una tasca que sobrevivia al kill acabava marcant l'item com a `completed` i engegava el següent, de manera que en corrien dues alhora. Ara les tasques tanquen l'item amb `_close_billing_queue_item` / `_close_report_queue_item`, que només actuen si l'item continua en `running` i amb el seu `task_id`. Les tasques ja no s'autoassignen el `task_id` en arrencar (una de revocada que arrenqués tard es quedaria un item reiniciat).
    - `process_next_queue_item` / `process_next_report_queue_item` generen el `task_id` abans d'encuar (`apply_async(task_id=...)`) i el desen alhora que l'estat `running`: un kill fet just en engegar l'item ja sap quina tasca ha de matar.
    - Kill/skip d'un PRE_INVOICE o DEFINITIVE_INVOICE pendent o en curs torna el `Billing` de «Processant» / «Processant documents» a «Pendent de confirmació», en lloc de deixar-lo encallat; restart el torna a l'estat de processant. Matar no desfà la feina feta: les prefactures o factures ja confirmades es queden.
    - Comprovat amb un worker real (pool prefork, Redis local): la tasca s'atura a l'instant i el procés fill mor. Nous tests `billing.tests.test_queue_actions` (24 casos).

#### COREDATA (`coredata/views/person_bank_view.py`, `coredata/utils/iban_validator_utils.py`, `coredata/opscripts/0002_fix_bank_bic_from_registry.py`, `prometeo/data*/coredata.Banks.json` — SWIFT/BIC dels comptes bancaris)
    - `PersonBankViewSet.resolve` (el que fan servir contractes, factures i compromisos): si l'IBAN ja existeix a la persona, el compte es continua reaprofitant però ara s'hi aplica el SWIFT/BIC que arriba si és diferent (`swift_updated: True` a la resposta). Abans es descartava i no hi havia manera de corregir només el BIC sense canviar l'IBAN. És el BIC del mateix compte, per això val per a tots els contractes que el comparteixen; la resta de dades del titular continuen sense tocar-se, i un SWIFT buit no esborra el desat.
    - El catàleg `Bank.bic` només portava el codi d'entitat de 4 lletres («BSAB» en lloc de «BSABESBB»), que no és un BIC vàlid. El frontal el copiava al `swift` dels comptes i la remesa SEPA el completava a cegues amb «ESMMXXX». Nou `get_spanish_bic(bank_code)` amb el BIC oficial del registre del Banc d'Espanya que porta schwifty.
    - Nou opscript `coredata/0002_fix_bank_bic_from_registry` (s'executa sol en desplegar): corregeix `Bank.bic` i el `swift` de `PersonBank`/`CompanyBank` amb IBAN espanyol que no té 8 ni 11 caràcters. Els codis que no surten al registre es deixen com estan.
    - Fixtures `prometeo/data*/coredata.Banks.json` amb el BIC complet (351 entrades per fitxer), perquè les instal·lacions noves no neixin amb el problema.
    - BILLING (`billing/views/sepa_pdf_view.py`, `contract_sepa_pdf_view.py`, `billing/utils/sepa_file_service.py`): els dos PDF de mandat SEPA construïen el BIC enganxant «ESMMXXX» a `Bank.bic` i ignoraven el `swift` del compte. Amb el BIC complet que posa l'opscript haurien sortit valors com «BSABESBBESMMXXX». Ara fan servir `resolve_account_bic()`: primer el SWIFT del compte, després el catàleg i el registre oficial, i només valors complets (8/11). Si no se'n pot determinar cap, el camp queda buit en lloc del marcador «XXXESMMXXX».
    - A la remesa XML, un BIC incomplet del deutor (còpies «BSAB» de factures ja emeses) es substitueix pel del registre oficial abans de completar-lo, en lloc de «BSABESMMXXX».
    - Nous tests `coredata.tests.SpanishBicTests` i `PersonBankResolveSwiftTests` (inclou `resolve_account_bic`).

#### CONTRACT (`contract/signals.py` — variable d'ampliació de trams ACA afegida solta)
    - `sync_contract_total_persons_from_aca_variable` només actuava si la variable "Membres d'ampliació de tram (ACA)" penjava d'una `Bonification`. Si s'afegia des de l'apartat **Variables** del contracte (`AddVariable.vue`), quedava solta: ni es vinculava a l'ampliació de trams del contracte, ni generava sol·licitud ACA, ni actualitzava `Contract.total_persons`.
    - Nou `_attach_variable_to_aca_bonification`: vincula la variable a la `Bonification` d'ampliació de trams activa del contracte i, si no n'hi ha cap, la crea (amb el titular i `requested_at`), de manera que segueix el mateix camí que quan s'afegeix des del formulari de bonificació. El vincle es fa amb `update()` per no reentrar als `post_save` de `Variable`.
    - Com que `sync_aca_bonification_num_persons` ja ha passat de llarg (la variable encara no tenia bonificació quan s'ha executat), s'informa el `num_persons_to_apply` de la sol·licitud ACA des d'aquí.
    - Nou helper `_aca_bonification_type()` amb la cerca del `BonificationType` per `ConfigProject.aca_at_token`, compartida amb `create_aca_bonification_on_total_persons_increase`.
    - Tot plegat continua condicionat a `uses_aca_enabled()`; la comprovació s'avança per no fer feina als projectes sense ACA.
    - **No s'ha provat amb dades reals.**

#### CONTRACT/CLAIMREQUEST/SERVICE/BILLING (`contract/filters/bail_filter.py`, `contract_request_filter.py`, `contract_termination_request_filter.py`, `claimrequest/filter/vulnerability_request_filter.py`, `service/filters/connection_request_filter.py`, `billing/filter/commitment_deposit_filter.py` — cercar per "Nom Cognom" a les llistes)
    - A la llista de fiances, cercar "Nom" + espai + "Cognom" no trobava la persona. `BailViewSet` no té `SearchFilter` als `filter_backends` (els seus `search_fields` són codi mort): qui cerca és `BailFilter.filter_search`, que feia un sol `icontains` amb la cadena sencera i **només contra `contract__holder__name`**. El cognom ni es mirava.
    - `BailFilter.filter_search` passa al patró que ja feia servir `ContractFilter`: es parteix el text per espais, cada paraula ha de coincidir en algun camp i totes han de coincidir (AND entre paraules, OR entre camps). S'hi afegeixen `contract__holder__surname` i `contract__holder__token`.
    - El mateix error hi era a quatre llistes més, corregides amb el mateix patró: sol·licituds de baixa de contracte, sol·licituds de vulnerabilitat (hi faltava també `person__surname`), sol·licituds d'escomesa i compromisos de pagament/dipòsits (hi faltava també `contract__holder__surname`).
    - `ContractRequestFilter` ja partia per paraules però no tenia `holder__surname`; afegit.
    - **Pendent**: a incidències (`notification/filters/incident_filter.py`) i a frau (`fraud/filters/fraud_filter.py`) el titular només es cerca per `token`, de manera que allà no es pot cercar per nom ni amb una sola paraula. És un canvi d'abast diferent i no s'ha tocat.
    - Sense migracions. Comprovat només que els fitxers compilen; no s'ha provat contra cap base de dades real.

## [02-10-2026]

### FEAT
#### ACCOUNTING
    - Nou model informatiu 'Centre de cost' pel AccountingPricing
    - Més criteris per filtrar i gestionar el AccountingPricing (falta aplicar els canvis a la generació de fitxer)

#### ORDER (`order/services/change_meter.py`, `order/views/order_view.py`, `order/tasks.py`, `order/models.py` — flux de canvi de comptador des de l'ordre de treball)
    - Noves accions a `OrderViewSet`: `GET /order/order/{id}/validate-change-meter/` que comprova si l'informe/s de l'ordre tenen totes les respostes necessàries, `GET /order/order/{id}/preview-change-meter/` compara el comptador sortint amb el del sistema i comprova si el comptador entrant ja existeix, i `POST /order/order/{id}/apply-change-meter/` que aplica el canvi.
    - El mapeig entre els tokens del formulari GOT i els camps interns (`meter_old`, `reading_old`, `meter_new`, `reading_new`) és parametritzable via `ConfigProject` (`change_meter_field_mapping`).
    - `Order` s'hi afegeix `change_meter_applied_at` i `change_meter_applied_by`, per deixar constància de qui i quan s'ha aplicat el canvi. Es crea una notificació interna (`create_change_meter_notification`, Celery) en aplicar-se.
    - L'aplicació del canvi reutilitza `MeterChangeService`. No és automàtica, només es dispara quan l'usuari ho confirma des del front.

#### SERVICE (`service/services/meter_change_service.py` — `MeterChangeService` extret de `save_meter_change`)
    - La lògica de `SupplyPointViewSet.save_meter_change`, moure el comptador al punt de subministrament, actualitzar estats, crear les lectures de tancament/inicial per cada contracte actiu, queda extreta a un servei reutilitzable, perquè la pugui fer servir tant la UI de punts de subministrament com el nou flux de canvi de comptador per ordre de treball.

#### ORDER (`order/serializers/order_report_serializer.py` — es desen les respostes del formulari d'un informe)
    - `OrderReportSerializer` no tocava mai `filled_form`: el `PUT` d'un informe guardava observació/dates/operari però les respostes del formulari (`OrderFormSubmission`) es quedaven congelades des de la creació. Ara `create`/`update` fusionen les respostes noves amb la submissió existent, conservant `name`/`type`/`required`/`response_url`.
    - El `0` numèric és una resposta vàlida (abans es tractava igual que buit en alguns punts de validació).

### CHORE
#### SERVICE (`service/serializers/supply_point_serializer.py` — `address_id` al `SupplyPointMinimalSerializer`)
    - S'exposa `address_id` perquè els formularis de creació de comptador que reben un `supply_point` (p. ex. des del flux de canvi de comptador) puguin precarregar la seva adreça.

## [01-10-2026]

### CHORE
#### DOCKER (`gunicorn.conf.py`, `Dockerfile` — workers de gunicorn configurables per variables d'entorn)
    - Els workers de gunicorn passen de 4 workers × 8 threads fixos a 2 workers × 4 threads per defecte. Amb diversos espais al mateix servidor, 4 workers per backend (~250 MB cadascun) esgotaven la RAM i el swap, i el servidor anava lent.
    - La configuració és al nou `gunicorn.conf.py` i es pot ajustar per servidor des del `docker-compose.yml`: `GUNICORN_WORKERS`, `GUNICORN_THREADS`, `GUNICORN_TIMEOUT`, `GUNICORN_MAX_REQUESTS` i `GUNICORN_MAX_REQUESTS_JITTER`. Un servidor que va sol pot posar-hi, per exemple, `GUNICORN_WORKERS=4` i `GUNICORN_THREADS=8`.
    - S'activa `max_requests` (1000, amb jitter de 100) perquè cada worker es recicli i no acumuli memòria.
    - **Desplegament**: cal reconstruir la imatge. Si algun compose sobreescriu `command:` per a gunicorn, cal treure'l o afegir-hi `-c /app/gunicorn.conf.py`.

### FEAT
#### WATCHDOG (`watchdog/persons_without_contact.py` — persones sense contacte ni adreça, en dos blocs)
    - El check únic «Persones sense contacte ni adreça» queda partit en dos:
        - **Persones sense contacte ni adreça ni cap contracte** (titular, propietari, llogater o representant): continua sent `FALLAT`. Són persones zombi. Nova comanda `watchdog_fix_delete_zombie_persons` (`--dry-run`, `--id`) per esborrar-les. No esborra les que tenen un compte bancari encara referenciat per un contracte, una factura, un pagament o un canvi de dades, perquè esborrar la persona esborraria el compte en cascada.
        - **Persones sense contacte ni adreça amb contracte actiu**: només `AVÍS`. L'estat actiu és `ConfigProject` `contract_active_token`. El missatge porta el token del contracte i el rol. S'ha d'entrar al contracte i sanejar-ho a mà; no hi ha comanda d'esborrat.
    - Una persona sense contacte ni adreça però amb un contracte que no està actiu no surt a cap dels dos. No és zombi i tampoc no és el cas que cal mirar a mà de seguida.
    - Si l'únic que falla són avisos, el resum del `watchdog sniff` ja no diu que les comprovacions han fallat.

#### WATCHDOG (`watchdog/services.py` — punts sense comptador només en contractes actius)
    - «Contracts with SupplyPoints no Meter» passa a «Contractes actius amb SupplyPoints sense Meter». Només mira contractes amb l'estat de `ConfigProject` `contract_active_token`. En una baixa és normal que el punt de subministrament ja no tingui comptador; el tornen a posar a l'alta.

#### BILLING (`billing/views/billing_invoices_view.py` — ordenar pre-factures per consum)
    - `billing/<id>/invoices` accepta `ordering=consumption`, per a la nova columna de consum de la llista de pre-factures del frontend.

### FIX
#### ORDER (`order/services/rabbit.py` — `exploitation_token` i darrera lectura a l'event `order.created`)
    - L'event `order.created` que s'envia a la GMAO porta dos camps nous, perquè els equips de camp tinguin més context de la feina.
    - **Nou `exploitation_token` a l'arrel del payload.** Es resol pel primer camí que funcioni, en aquest ordre: `Order → SupplyPoint → Connection → Exploitation`, `Order → Contract → SupplyPoint → Connection → Exploitation`, `Order → Connection → Exploitation` i `Order → ConnectionRequest → Exploitation`. Si el primer camí té l'Exploitation però sense token, es prova el següent. Si no es resol, s'envia `null`.
    - No es tenen en compte l'`address` ni les coordenades de l'ordre: `Exploitation` no té cap camp geoespacial ni cap relació amb `Address`, de manera que no hi ha cap ruta fiable i no es fan consultes geoespacials.
    - **Nou `last_reading_value`, `last_reading_date` i `last_reading_consumption` a `additional_info`**, amb la darrera lectura **real** del comptador del punt de subministrament de l'ordre (el de l'ordre mateix o, si no en té, el del contracte).
        - Només lectures reals: si la darrera lectura és estimada (`is_estimated=True`) es busca la real anterior. Mateix criteri que la CRM (`service/serializers/supply_point_serializer.py`).
        - Es descarten les lectures copiades (`copied_from`), que genera el fanout dels comptadors generals, perquè al camp li interessa la lectura física del comptador. Quan dues lectures comparteixen `reading_date` guanya la més recent (`-id`), de manera que el resultat és determinista. Actualment `copied_from` no s'usa en aquest desplegament: és una garantia per a quan s'utilitzi.
        - El consum ve de `Reading.calculated_value`, que és el consum del tram respecte a `previous_reading` (`reading_value - previous.reading_value`, vegeu `docs/agent/readings.md`), tal com demana el ticket. Si és `null`, s'envia `null` i no hi ha fallback a `real_consumption`.
        - **Atenció GMAO**: `calculated_value` pot ser `0` i no pas `null` en tres casos — una lectura inicial sense `previous_reading` (`billing/tasks.py`), un canvi de comptador a mitjà tram (`billing/utils/invoice_service.py`) i un valor negatiu pel cicle del comptador, que es deixa a 0. `0m3` vol dir «consum zero», no «consum desconegut»: no s'ha de renderitzar igual que un `null`.
        - El punt de subministrament és el de l'ordre o, si no en té, el `supply_point_default` del contracte. No es pren mai un punt de subministrament a l'atzar del M2M `Contract.supply_points`: un contracte pot tenir-ne vários (un client industrial o un ajuntament amb diverses instal·lacions) i enviar la lectura o l'explotació equivocada alEquip de camp és pitjor que no enviar res.
        - Sense comptador o sense lectures reals, els tres valors són `null`. Les tres claus sempre hi són; quan una és `null` les altres dues sí que poden tenir valor, de manera que la GMAO ha de pintar el consum que falti com a «—» i no tractar el grup com a tot o res.
        - El consum s'acompanya de la unitat (`25m3`).
    - Sense migracions. Tests a `order/tests/test_rabbit_publish.py` (45 tests). `order/tests.py` era un stub i s'ha substituït pel paquet `order/tests/`.
    - **GMAO**: cal acceptar el camp nou `exploitation_token` i les tres claus noves de `additional_info`. Són camps additius; la resta del payload no canvia.

#### WATCHDOG (`watchdog/persons_without_contact.py` — persones sense contacte ni adreça, en dos blocs)
    - El check únic «Persones sense contacte ni adreça» queda partit en dos:
        - **Persones sense contacte ni adreça ni cap contracte** (titular, propietari, llogater o representant): continua sent `FALLAT`. Són persones zombi. Nova comanda `watchdog_fix_delete_zombie_persons` (`--dry-run`, `--id`) per esborrar-les. No esborra les que tenen un compte bancari encara referenciat per un contracte, una factura, un pagament o un canvi de dades, perquè esborrar la persona esborraria el compte en cascada.
        - **Persones sense contacte ni adreça amb contracte actiu**: només `AVÍS`. L'estat actiu és `ConfigProject` `contract_active_token`. El missatge porta el token del contracte i el rol. S'ha d'entrar al contracte i sanejar-ho a mà; no hi ha comanda d'esborrat.
    - Una persona sense contacte ni adreça però amb un contracte que no està actiu no surt a cap dels dos. No és zombi i tampoc no és el cas que cal mirar a mà de seguida.
    - Si l'únic que falla són avisos, el resum del `watchdog sniff` ja no diu que les comprovacions han fallat.

#### WATCHDOG (`watchdog/services.py` — punts sense comptador només en contractes actius)
    - «Contracts with SupplyPoints no Meter» passa a «Contractes actius amb SupplyPoints sense Meter». Només mira contractes amb l'estat de `ConfigProject` `contract_active_token`. En una baixa és normal que el punt de subministrament ja no tingui comptador; el tornen a posar a l'alta.

#### BILLING (`billing/views/billing_invoices_view.py` — ordenar pre-factures per consum)
    - `billing/<id>/invoices` accepta `ordering=consumption`, per a la nova columna de consum de la llista de pre-factures del frontend.
