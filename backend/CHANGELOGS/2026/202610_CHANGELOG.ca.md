# Changelog Backend

## [23-10-2026]
### FEAT
#### COMMUNICATION (`communication/tasks.py`, `coredata/migrations/0143_add_attach_extra_docs_in_claims_config.py` — comunicacions d'impagats sense factures ni rebuts adjunts) (PR #115)
    - Nou `ConfigProject.attach_extra_docs_in_claims` (migració `coredata.0143`, valor per defecte `true`): amb `false`, a les comunicacions d'impagats només s'adjunta el document del pas (avís de pagament o carta de suspensió), sense els PDF de les factures ni els rebuts o el document agrupat.
    - Les factures dels pagaments reclamats continuen vinculades a la comunicació, de manera que les variables `%invoice.*` del cos del missatge es continuen resolent.
    - Migració de merge `coredata.0144` (dues `0143` en paral·lel). Tests a `communication/tests.py`.

#### BILLING (`billing/templatetags/billing_filters.py` — despeses de devolució a les cartes de reclamació) (PR #120)
    - Nou filtre `with_return_fee_invoices`: a cada factura reclamada hi afegeix les factures de despeses de devolució pendents que en pengen (també des de les rectificatives de la cadena), ordenades per data d'emissió i sense duplicats. Les factures de despeses reclamades directament es marquen com a tals.
    - Si la cerca falla, retorna només les factures reclamades, de manera que la carta no deixa de generar-se. Les plantilles que el facin servir requereixen aquest backend.

#### BILLING (`billing/utils/sepa_service.py`, `billing/utils/payment_service.py`, `billing/views/payment_view.py` — D_004-256, retorns de domiciliacions de factures canviades de mètode) (PR #113)
    - Retornar un rebut SEPA d'una factura que després s'ha canviat a un altre mètode de pagament registra la devolució i la torna a cobrar pel mètode nou. El fitxer de retorn ja no salta aquests pagaments i els marca com a canviats.
    - Els pagaments que continuen pagats no entren a la gestió d'impagats, i no es registra dues vegades la devolució del mateix rebut encara que el motiu sigui diferent.

### FIX
#### STATISTICS (`statistics/utils/report_billing_service.py` — informe de facturació per tarifa amb la variable de persones configurada) (PR #120)
    - L'informe importava una constant que s'havia eliminat en fer configurable la variable de persones de l'ampliació de trams ACA i fallava. Ara les variables de membres es busquen pels tokens de `ConfigProject.aca_tram_members_variable_token`, amb els mateixos criteris de vigència i valor.

#### STATISTICS (`statistics/utils/report_billing_service.py` — tipus d'ús vigent a la data de la factura) (PR #122)
    - El resum de facturació per tarifa agrupa cada factura pel tipus d'ús que tenia el contracte quan es va generar, segons l'historial de canvis del contracte, en lloc del tipus d'ús actual. Sense canvis registrats, o si el tipus d'ús s'ha reanomenat, es fa servir l'actual.

#### NOTIFICATION (`notification/serializers/notification_serializer.py`, `notification/filters/notification_filter.py` — llegir i arxivar notificacions per usuari) (PR #117)
    - Marcar com a llegida/no llegida i arxivar/desarxivar apliquen el valor enviat en lloc d'alternar l'estat, de manera que repetir l'acció ja no la desfà.
    - Arxivar ja no desa `is_active=False` a la notificació (l'amagava a tots els usuaris): només afegeix o treu l'usuari d'`archived_by`.
    - L'acció sobre totes les notificacions es limita a les de l'usuari i les generals. Corregit el filtre `is_seen` amb l'arxivament invertit.

#### PRICING/BILLING (`pricing/utils/formula_evaluator.py`, `billing/utils/adjustment_service.py`, `pricing/serializers/*` — avaluació segura de les fórmules de tarifes i ajustos) (PR #118, #121)
    - Les fórmules d'ajustos, trams i conceptes de factura ja no s'executen amb `eval`: només s'hi accepten números, operacions aritmètiques, comparacions, condicions (`x if ... else y`, `and`/`or`/`not`), variables `%nom` i les funcions `abs`, `min`, `max`, `round`, `int`, `float`, `math.ceil`, `math.floor` i `math.sqrt`. Es limiten la longitud, l'exponent, els decimals de `round` i els números massa grans o no finits.
    - En desar un ajust, un tram o un concepte de factura es rebutgen les fórmules no vàlides amb un missatge d'error; als conceptes amb productes s'hi admeten percentatges (`21%`), com en facturar.
    - Les fórmules que són només un número amb coma decimal (`0,5`) passen a punt (`0.5`), en desar i amb la migració `pricing.0132` per a les existents. Les condicions dels ajustos no es toquen.
    - Tests a `pricing/tests_formula_evaluator.py`.

#### BILLING (`billing/views/invoice_view.py`, `billing/serializers/payment_serializer.py` — canvi de mètode de pagament de factures pagades) (PR #113)
    - No es pot canviar el mètode de pagament d'una factura ja pagada (primer cal retornar-la) ni el tipus d'un pagament cobrat. En factures no pagades, el canvi només afecta els pagaments pendents.
    - Tests a `billing/tests/test_return_after_payment_method_change.py`. Cal desplegar-lo junt amb el frontend.

## [22-10-2026]

### FEAT
#### BILLING (`billing/utils/sepa_file_service.py` — 1907, número de factura al concepte dels rebuts SEPA) (PR #106)
    - El concepte dels rebuts d'aigua inclou el número de factura (`FRA` en català i castellà, `INV` en anglès); el dels compromisos de pagament llista les factures que cobren.
    - El concepte es limita als 140 caràcters de l'esquema SEPA: si no hi caben totes les factures, s'hi afegeix `+N` amb les que falten.
    - Els pagaments sense factura ni compromís parteixen del seu token i ja no hereten el concepte del pagament anterior. Tests a `billing/tests/test_sepa_concept.py`.

#### BILLING (`billing/utils/general_invoice_summary_service.py`, `general_invoice_summary_template.html` — consum al resum de la factura general) (PR #110)
    - El resum en PDF de la factura general té una columna nova «Consum (m3)» per factura (consum real o, si no n'hi ha, el facturat) i el total.

#### STATISTICS (`statistics/utils/report_billing_service.py` — resum de facturació per tarifa amb el format del resum en PDF) (PR #110)
    - L'Excel inclou capçalera amb l'empresa i la data, el període en mesos, els rangs de números de factura per sèrie i una columna nova de preu unitari aplicat.
    - Els productes surten amb la seva posició i l'IVA només s'indica si el producte en té més d'un tipus. Nou format dels totals i del resum de l'IVA.

#### CONTRACT (`watchdog/aca_config.py`, `contract/utils/aca_tram_service.py`, `contract/signals.py` — variable de persones de l'ampliació de trams ACA configurable) (PR #114)
    - La variable que es sincronitza amb el nombre de persones del contracte ja no es detecta perquè el token contingui `MEMBRES`: es configura a `ConfigProject.aca_tram_members_variable_token` (migració `coredata.0143`, per defecte `ACA-TRAM-MEMBRES`) i es tria a `/settings/config_aca/` (migració `billing.0326`, que crea la fila per explotació).
    - La coincidència és pel token sencer, sense distingir majúscules, i se n'admet més d'un separat per `|`. Si la configuració no existeix o és buida, es fa servir el token històric.
    - S'aplica a la bonificació en canviar el nombre de persones, a l'aplicació de fitxers de l'ACA, a l'exportació de sol·licituds i a l'informe de volum de gestions. El watchdog avisa si la configuració falta o apunta a un tipus de variable inexistent.
    - Tests a `contract/tests/test_aca_tram_service.py`.

### FIX
#### PRICING (`pricing/utils/deletion_service.py`, `pricing/views/*` — 2032, revisió de l'eliminació de tarifes i productes) (PR #104)
    - També es considera en ús una tarifa referenciada només pel concepte de la línia de factura.
    - No es poden eliminar les tarifes configurades com a despeses de devolució o drets de connexió (ni els productes que en tinguin), i el `400` indica el motiu.

#### BILLING (`billing/utils/payment_pdf_service.py` — 2027, la carta de pagament mostra el nou termini concedit) (PR #105)
    - La data límit de la carta de pagament és el nou termini concedit a la reclamació (el mateix que porta el codi de barres); si no n'hi ha, el venciment del pagament. Tests a `billing/tests/test_payment_pdf_limit_date.py`.

#### CONTRACT (`contract/views/contract_manage_massively_view.py` — filtre de producte a la gestió massiva de contractes) (PR #107)
    - El filtre per producte i l'eliminació massiva de productes fan servir la relació correcta amb la tarifa del contracte: ara es treuen del contracte les tarifes d'aquests productes.

#### BILLING (`billing/views/invoice_manage_massively_view.py` — pagament massiu de factures) (PR #108)
    - Només s'apliquen a factures (no a pressupostos) i s'exclouen les pagades, descartades, cancel·lades, en compromís, liquidades o pendents.
    - S'exclouen els pagaments per SEPA, saldo i TPV online; la resta de formes de pagament s'hi inclouen (abans només efectiu i SEPA).

#### BILLING (`billing/utils/reading_service.py`, `billing/tasks.py` — 1916, estimar lectures després d'un canvi de comptador) (PR #111)
    - Un canvi de comptador recent ja no bloqueja l'estimació: els dies del període es compten des de l'última lectura real anterior al canvi.
    - Amb diverses lectures el mateix dia es prioritza la del comptador nou, de manera que l'estimada en parteix sempre. Es descarten els períodes sense dies de consum. Tests a `billing/tests/test_estimate_after_meter_change.py`.

#### BILLING (`billing/utils/invoice_line_item_service.py`, `billing/views/epayment_document_generate_view.py` — arrodoniment dels imports proporcionals) (PR #112)
    - L'import de les línies proporcionals i el preu corregit s'arrodoneixen amb `round_ceil` i es calculen amb `Decimal`, també en la comprovació del preu unitari de la factura electrònica.

### MODIFIED
#### BILLING/COREDATA (`billing/utils/invoice_pdf.py`, `billing/views/invoice_pdf_view.py`, `coredata/utils/pdf_utils.py` — ACUSTOMERS-335, PDF de factura desat només al gestor documental) (PR #109)
    - El PDF definitiu de la factura només es desa al gestor documental (`invoice_file`); `invoice_file_template` queda per a la previsualització provisional. La URL retornada en generar-lo apunta al gestor documental.
    - Els PDF combinats de factures fan servir el document definitiu i, si no n'hi ha, la còpia antiga.
    - Nova ordre `clean_duplicated_invoice_pdfs` (`--dry-run`, `--skip-orphans`) i opscript `billing/0008` per esborrar les còpies duplicades i els PDF orfes antics de `uploads/billing/invoices`. Cal desplegar-lo junt amb el frontend. Tests a `billing/tests/test_invoice_pdf_storage.py`.

#### CLAIMREQUEST (`claimrequest/serializers/vulnerability_request_serializer.py` — data de fi de les variables de vulnerabilitat) (PR #110)
    - En acceptar una sol·licitud de vulnerabilitat, les variables creades ja no prenen la data de venciment de la sol·licitud: queden obertes tret que s'enviï `variables_end_at`. Cal desplegar-lo junt amb el frontend.

### CHORE
#### COREDATA (`initial_data/{ca,es}/config_project/local/ConfigProject.json` — fixtures de ConfigProject al dia amb les migracions) (PR #116)
    - Els dos fixtures queden amb els mateixos tokens, s'hi afegeixen els que creen les migracions i s'eliminen els que les migracions esborren. Només afecta instal·lacions noves.

## [21-10-2026]

### FEAT
#### BILLING (`billing/utils/joined_payment_service.py`, `billing/views/joined_payment_view.py` — 1897, detall del deute del contracte) (PR #90)
    - Nou `POST joined-payments/contract-debt/` (cos `{ "contract": <id> }`; `400` si falta): retorna els pagaments que formen el deute del contracte (els mateixos que suma `vw_contract_debt`) més els que es poden liquidar encara que no hi comptin (p. ex. terminis de compromisos de pagament). Per a cada pagament indica `in_debt`, `is_settleable`, la remesa més recent (pendent d'enviar o enviada) i el pagament agrupat actiu, amb els totals de deute, liquidable, en remesa pendent i en pagament agrupat.
    - Els pagaments pendents d'un contracte (liquidables amb un pagament agrupat) inclouen també els que només tenen el contracte a la factura (`invoice__contract`).
    - Document de pagament agrupat: la previsualització mostra el venciment, l'IBAN i el SWIFT (abans les plantilles els amagaven sense pagament agrupat desat), i la columna Contracte agafa el de la factura quan el pagament no en té.
    - Tests: `billing/tests/test_contract_debt_detail.py`. Cal desplegar-lo junt amb el frontend.

#### ORDER (`order/services/consumer.py`, `order/signals.py`, `order/serializers/order_serializer.py`, `documentmanager/utils/export_registry.py` — ordres creades directament al GMAO) (PR #93)
    - El consumer GMAO processa el nou event entrant `order.created` i replica l'ordre al CRM. Vinculació en tres nivells, sense errors ni DLQ si no hi ha coincidència: ordre pare (n'hereta contracte, punt de subministrament, tipus, motiu, prioritat i adreça), adreça de text lliure del GMAO (carrer, número, CP i municipi) resolta a un únic punt de subministrament actiu, o ordre òrfena.
    - Les ordres òrfenes es creen sense punt ni contracte i amb la descripció marcada amb `[REVISIÓ MANUAL]` i l'adreça rebuda. Idempotent pel `token` de l'ordre; l'estat es mapeja amb `gmao_integration_order_status_mapping` (o l'estat per defecte) i la data límit amb `due_date`.
    - Les ordres s'atribueixen a l'usuari de sistema `GMAO` (es crea automàticament, sense contrasenya utilitzable ni permisos) i no es tornen a publicar cap al GMAO (`_skip_publish` al senyal).
    - El llistat d'ordres (`OrderListSerializer`) i l'exportació XLSX inclouen `description`. Sense migracions. Tests: `order/tests/test_gmao_consumer_order_created.py`.

#### CONTRACT (`contract/utils/bail_service.py` — retorn de fiances sense factura) (PR #96)
    - Nou ConfigProject `BAIL_RETURN_INVOICE_DISABLED` (migració `coredata.0140_add_bail_return_invoice_disabled_config`, per defecte `false`).
    - Activat, el retorn immediat d'una fiança i el de la baixa del contracte la deixen «Retornada» sense generar la factura de retorn ni abonar l'import al saldo; tampoc cal forma de pagament ni saldo al contracte.
    - Desactivat, el comportament no canvia: sense forma de pagament a la baixa, la fiança continua sense retornar. Tests: `contract/tests/test_bail_return_without_invoice.py`.

#### PRICING (`pricing/models.py`, `pricing/utils/accounting_service.py`, `pricing/views/accounting_*_view.py` — comptabilitat configurable) (PR #97)
    - Tarifes comptables (`AccountingPricing`): separar les factures per origen (`separate_by_origin`), per tipus d'ús del contracte (`contract_types`) i per categoria de morositat (normal, dotació, irrecuperable), amb títol de línia propi (`declared_as`) i codi de retorn (`token_return`) per a les línies negatives o desdeclaracions.
    - Cobraments: separar per tipus de pagament (`separate_by_type`) i, en pagaments bancaris agrupats, per origen taquilla/correus (`payment_origin`, `separate_by_payment_origin`). El deure del compte de cobrament es compensa amb l'haver al compte de clients de la factura; els cobraments de factures en dotació o irrecuperables desdeclaren aquests comptes i, si cal, restauren el nivell anterior.
    - Nou model `AccountingAdditionalLine` i API `accounting-additional-line`: línies extra que es declaren amb els mateixos imports que el compte pare (amb concepte, codi i nom propis, i opció d'import negatiu). L'esborrat és lògic.
    - Nou model `AccountingConfig` i API `accounting-config/current/` (GET/PUT/PATCH): regles de declaració dels moviments de saldo (deure/haver, signe i compte de contrapartida per a entrades i devolucions, moviments com a negatius, i incloure pagaments amb estat saldo).
    - Les línies es generen agrupades o separades segons la configuració, amb l'IVA per percentatge i el codi de centre de cost. `AccountingConcept.category` admet `invoice` (per defecte).
    - L'informe comptable rep la data (`start_date` o rang) i carrega ell mateix factures, factures en dotació/irrecuperables i moviments. Missatge traduït quan no hi ha valors.
    - Migracions `pricing.0120` a `pricing.0130` (i `pricing.0131` al PR #100).

#### BILLING (`billing/models.py`, `billing/tasks.py`, `billing/views/manage_deliquency_view.py` — gestió de morositat) (PR #97)
    - Nous camps `Invoice.endowment_date` i `Invoice.irrecoverable_date` (migracions `billing.0321` i `billing.0322`), data en què la factura passa a dotació o a irrecuperable i que fa servir la comptabilitat.
    - La gestió de morositat és una tasca asíncrona (`manage_deliquency`) amb filtres per tipus d'ús, explotació, tipus de client, zona, estat del contracte, tipus de pagament, dates d'emissió, venciment i baixa, i nombre mínim/màxim de factures pendents. Cerca factures normals o en dotació (no les dues alhora).
    - En desar, marca les factures i els pagaments no pagats com a dotació o irrecuperables a data d'avui (amb registre del canvi d'estat del pagament). Les factures en dotació només poden passar a irrecuperables; per a les normals s'actualitza el deute del titular.

#### COMMUNICATION (`communication/utils/communication_service.py`, `integrations/outbound/broadcaster/` — SMS de les comunicacions via Broadcaster) (PR #100)
    - Els SMS de les comunicacions s'envien pel Broadcaster (mateix payload que Aqua360 Sign): text amb les variables resoltes i sense marques de format, telèfons mòbils en format internacional i sense duplicats. Les crides queden a `IntegrationRequestLog` sense telèfons ni text.
    - L'SMS s'envia abans del correu i l'estat final de la comunicació té en compte els dos canals; els motius d'error dels dos es conserven. Les comunicacions cancel·lades no es marquen com a enviades.
    - Nou camp `Communication.sms_sent_at` (migració `communication.0035`): un reintent per error del correu no torna a enviar l'SMS, ni es reenvia un correu ja enviat.
    - En crear una comunicació a mà, els telèfons desats són només els mòbils actius del contacte SMS del contracte, separats per comes. Noves variables d'entorn `BROADCASTER_*`. Tests a `communication/tests.py` i `integrations/outbound/broadcaster/tests.py`.

#### STATISTICS (`statistics/models.py`, `statistics/utils/daily_document_service.py` — termini dels documents diaris en dies hàbils) (PR #101)
    - Nou camp `DailyDocumentTemplate.is_work_days` (migració `statistics.0048`, per defecte `false`).
    - Activat, la data límit del document diari es calcula sumant dies laborables (de dilluns a divendres); si no, dies naturals com fins ara.

#### PRICING (`pricing/utils/deletion_service.py`, `pricing/views/price_rate_view.py`, `pricing/views/product_view.py` — 2032, eliminar tarifes i productes no utilitzats) (PR #103)
    - `DELETE` de tarifa i de producte fa un esborrat lògic, registrat a l'historial, només si no estan vinculats a cap contracte, sol·licitud, fiança ni factura; si no, `400` amb el motiu. Eliminar un producte desactiva també les seves tarifes.
    - El detall de tarifa i de producte retorna `is_deletable`.
    - El llistat de tarifes i el filtre per explotació inclouen les tarifes sense producte; en desar una tarifa el producte és obligatori. Tests a `pricing/tests_deletion.py`. Cal desplegar-lo junt amb el frontend.

### FIX
#### BILLING (`billing/views/generate_invoice_budget_view.py` — compte de l'empresa a la factura de baixa) (PR #88)
    - El compte de l'empresa triat al diàleg de facturació d'una baixa no arribava a la generació de la factura o pressupost de baixa (s'usava sempre el del pagament per defecte). Ara es passa i es fa servir.
    - Documentació (docstrings) dels fluxos de facturació de baixes i normalització de valors als logs.

#### BILLING (`service/utils/company_bank_service.py`, `billing/utils/invoice_pdf.py`, `billing/views/invoice_pdf_view.py`, `billing/utils/barcode_service.py` — compte bancari de l'empresa al PDF de la factura) (PR #99)
    - Nou `get_company_bank`: compte de cobrament assignat a la factura, o el per defecte i actiu, o el primer actiu, o el primer de l'empresa (ordenats per id).
    - El PDF de la factura (les dues vies de generació) i el codi de barres fan servir aquest mateix compte. Abans la generació del PDF podia agafar el primer compte de la llista en lloc del configurat per defecte.
    - El codi de barres usa el CIF específic del compte (`barcode_cif`) quan en té.

#### STATISTICS (`statistics/utils/report_progress.py`, `statistics/views/reports_views.py`, `statistics/utils/report_*` — colors i progrés dels informes) (PR #94)
    - Els colors dels informes Excel (capçaleres negres, farcits i vores) es desen amb canal alfa: alguns visors no pintaven les capçaleres.
    - Nou `report_progress`: els informes publiquen el progrés a la tasca perquè la cua d'informes mostri la barra (remeses, SII, SGT, deute pendent, resums ACA, facturació per tarifes, exportacions de contractes i tarifes, i resum de factures i lectures).

#### BILLING (`billing/utils/invoice_pdf.py`, `billing/views/invoice_pdf_view.py`, `billing/views/sepa_payment_document_generate_view.py`) (PR #97)
    - La plantilla de factura només mostra la lectura de tall anterior quan no està bloquejada per altres factures.
    - La cerca de pagaments per a la remesa SEPA també filtra per data d'emissió quan la factura no té data d'enviament ni de venciment dins del rang.
    - L'informe SII dona error si no hi ha factures, i el missatge d'error dels informes ja no porta el prefix «Generator returned error».

### MODIFIED
#### BILLING (`billing/views/manage_deliquency_view.py`, `billing/models.py` — API de gestió de morositat) (PR #97)
    - `POST` de gestió de morositat ja no respon amb les factures i contractes: llança la tasca `manage_deliquency` i retorna `{"task_id"}`, amb un payload de filtres nou. Canvi incompatible de l'API interna: cal desplegar-lo junt amb el frontend.
    - S'eliminen els camps `start_date` de `CommitmentDeposit` i `PaymentCommitment` (migració `billing.0324`); la gestió de compromisos ja no els desa.

#### STATISTICS (`report_billing_service.py` — resum de facturació per tarifa) (PR #94)
    - L'informe es reorganitza per producte i, dins de cada producte, per tipus d'ús del contracte, amb total per tipus d'ús i per producte i el rang de números de factura a la capçalera.
    - Cada línia indica concepte, tarifa i tram, i les marques AMPLIACIÓ (tram ampliat per nombre de persones) i SOCIAL. Acaba amb un resum de l'IVA per percentatge.

#### STATISTICS (`report_billing_product_dashboard_service.py` — Dashboard de facturació) (PR #95)
    - Nova columna «Lectura 1 · Dies periode» abans d'«Estimada»: dies de consum de la primera lectura de la factura (0 si no en té; buit si la factura no té lectures).

### CHORE
#### PRICING (`pricing/utils/accounting_service.py`) (PR #101)
    - Tret el `print` de factures i línies de la generació de comptabilitat.

#### INITIAL DATA (`initial_data/es/statistics.AvailableReport.json`, `initial_data/*/config_project/local/ConfigProject.json`) (PRs #96, #97)
    - El fixture d'informes en castellà s'iguala amb el català (informes de comptabilitat, deute pendent, SII i informe comptable). Nou `BAIL_RETURN_INVOICE_DISABLED` als ConfigProject de `ca` i `es`.

## [20-10-2026]

### FEAT
#### SERVICE (`service/utils/supply_cut_bulk_planner.py`, `service/utils/supply_cut_service.py`, `service/views/supply_cut_view.py`, `service/serializers/*`, `service/tasks.py` — 1913, protecció de persones vulnerables als talls de subministrament) (PR #67)
    - Nova detecció de persones vulnerables (titular, llogater o propietari amb nivell de vulnerabilitat > 0 en contractes actius) als punts del tall. Motiu permanent: bloqueig estricte amb `400` (`vulnerability_blocked`), sense manera d'evitar-lo. Motiu temporal: cal confirmar-ho (paraula `CONFIRMAR` a la creació manual i al canvi de motiu; `override_vulnerable` a la planificació massiva i a l'activació, `409` mentre no es confirmi).
    - La regla es torna a validar en activar el tall (`start-cut` i activació programada), perquè la vulnerabilitat pot haver-se registrat després de crear-lo; l'activació automàtica salta els talls permanents bloquejats.
    - `bulk-plan/preview/` i `bulk-plan/` accepten, a més de la llista d'identificadors, punts (`supply_points`) i contractes (`contract_ids`) triats manualment: es combinen sense duplicats, cada fila indica l'origen (`manual` o llista) i els no trobats es retornen per tipus (id del punt o token del contracte). La previsualització inclou `vulnerable` i el recompte.
    - Els serialitzadors de contracte i de punt de subministrament exposen `holder/tenant/owner_vulnerability_level`. Un tall ja creat ja no admet canviar-ne els punts per `PUT` (`400`). Tests a `service/tests_supply_cut_bulk_planner.py` i `service/tests_vulnerability_guard.py`. Cal desplegar-lo junt amb el frontend.

#### STATISTICS (`statistics/utils/report_billing_product_dashboard_service.py`, `statistics/tasks.py` — nou informe «Dashboard de facturació») (PR #84)
    - Nou informe Excel `billing_product_dashboard` a la secció de facturació (migració de dades `statistics.0047`), independent del padró de facturació, que no canvia.
    - Una fila per factura amb dades del client, el contracte i la factura, sector, tipus de pagament, tipus d'ús, ús ACA, estimació i observació de la lectura, tarifa social (S/N), ampliació de trams, consum i imports (subtotal, IVA i total), més tres columnes (subtotal, IVA, total) per producte i una d'«Altres».
    - Filtra per lot de facturació, rang de dates o rang de números de factura, explotació, estat i productes (`product_ids`, `400` si el format no és vàlid). Sense explotació concreta, genera un full per explotació amb totals al peu.

### FIX
#### BILLING (`billing/utils/invoice_service.py`, `billing/views/generate_invoice_budget_view.py`, `contract/serializers/contract_termination_request_serializer.py` — compte bancari de la factura de baixa que cobra l'alta) (PR #80)
    - En una baixa vinculada a una alta que cobra la lectura de tall, si el diàleg envia el compte del contracte que es dona de baixa i l'alta en té un altre, la factura fa servir el compte de l'alta.
    - El pagador de la factura de baixa és el titular del compte que es cobra, no el del pagament per defecte.
    - La sol·licitud de baixa exposa `billing_contract_request_payment` (pagament de l'alta vinculada) perquè el diàleg de facturació el proposi.
    - Logs de seguiment de la facturació de baixes i dels canvis de «facturar lectura de tall», sense dades bancàries. Tests: `billing/tests/test_termination_payment_bank.py`.

#### BILLING (`billing/utils/invoice_service.py` — període del cànon després d'un canvi de comptador ja facturat) (PR #83)
    - Si la lectura del canvi de comptador ja està facturada, el període de la factura següent comença en ella i no es torna a cobrar el tram del comptador antic. Afecta sobretot quan hi ha un canvi de tarifa (dos rangs de facturació) pel mig.
    - Tests: `billing/tests/test_meter_change_billing_range.py`.

#### SECURITY (vistes de `billing`, `contract`, `communication`, `service`, `statistics`, `documentmanager`, `ov`, `integrations`, `verifactu`, `lecturapp`, `got` i altres — alertes de code scanning) (PR #87, #89, #91, #92)
    - Les respostes d'error ja no retornen el text de l'excepció al client: es retorna un missatge genèric (p. ex. «Ha ocorregut un error inesperat.», o un d'específic per a signatura, telelectura, XML SEPA, contrasenya SMTP i cues) i el detall queda al log. Els codis d'estat HTTP es mantenen.
    - Accés a fitxers: la descàrrega de media, els documents desats al disc i les plantilles per idioma (factures i plantilles del projecte) no poden sortir de la seva carpeta, tampoc amb `..` ni enllaços simbòlics.
    - Expressions regulars amb risc de ReDoS substituïdes (sèries de factura, NIC de l'OV, noms de carrer a les rutes).
    - L'acció sobre un element de la cua de facturació i d'informes ja no retorna `error_message`, i `DocumentSign.error_report` desa un missatge genèric quan falla el servei de signatura. L'informe del watchdog ja no escriu els IBAN. Tests actualitzats (cues, contrasenya SMTP, signatura).

### CHORE
#### BILLING/DOCUMENTMANAGER (`billing/tasks.py`, `billing/utils/adjustment_service.py`, `billing/utils/invoice_line_item_service.py`, `documentmanager/utils/*_service.py` — dades sensibles als logs) (PR #85, #86)
    - Eliminats els missatges de depuració amb rutes i noms de documents dels serveis d'emmagatzematge (Alfresco, AWS, Azure, FTP, disc); els errors d'Alfresco ja no escriuen el contingut de la resposta.
    - Els errors de fórmules d'ajust mostren la fórmula original, sense els valors del contracte, i els missatges de facturació no inclouen identificadors.
    - Docstrings a les funcions afectades.

## [19-10-2026]
### FEAT
#### DASHBOARD/NOTIFICATION (`dashboard/*`, `notification/models.py`, `notification/tasks.py`, `notification/utils/*`, `notification/views/*`, `order/signals.py`, `customers/celery.py` — D_004-371, dashboard personalitzable i millores del calendari) (PR #60)
    - Nova app `dashboard` (migració `dashboard.0001`): disposició de la pàgina d'inici per usuari (`UserDashboard.layout`, amb una disposició per defecte si no en té). API `GET/PUT/DELETE /dashboard/layout/`, catàleg `GET /dashboard/cards/` filtrat pels permisos de l'usuari i dades de cada card per separat a `GET /dashboard/cards/<key>/data/` (activitat diària, tasques d'avui, ordres per validar, canvis de comptador pendents, lots de lectura en curs, factures emeses, anul·lacions, refacturacions, cerques recents, calendari i accessos directes).
    - Tasques del calendari (migració `notification.0025`): hora, enllaç a l'ordre de treball, qui i quan s'ha fet, i tasques recurrents (`CalendarTaskRecurrence`: diària, setmanal, mensual o anual), amb ocurrències generades per endavant cada nit. Esborrar amb `?series=true` atura la sèrie a partir d'aquella data. Nous filtres (`date_from`/`date_to`, `assigned`, `overdue`, `order`…), acció `summary` (pendents d'avui i endarrerides) i paginació llarga al llistat.
    - Avisos: la notificació de tasques pendents (`notification.tasks.notify_today_tasks`, que substitueix `billing.tasks.check_today_tasks`) ja no es repeteix cada dia per a la mateixa tasca; les tasques del mateix dia s'avisen en desar-les. Nou correu de resum diari a les 7:00 amb les tasques pendents i endarrerides de l'usuari, activable a `GET/PUT /notification/preference/`.
    - Tasca automàtica «Aplicar canvi de comptador» quan es tanca una ordre de canvi de comptador sense aplicar el canvi; es tanca sola en aplicar-lo. Tipus d'ordre configurables amb el `ConfigProject` opcional `order_type_change_meter_tokens` (per defecte `change_meter` i `install_meter`). Cal desplegar-lo junt amb el frontend.

#### BILLING (`billing/validators/sepa_xsd_validator.py`, `billing/validators/pain.001.001.03.xsd`, `billing/views/sepa_xsd_validate_view.py` — validació dels fitxers de transferències) (PR #64)
    - La validació XSD de fitxers accepta el paràmetre `type`: `sepa` (per defecte, rebuts pain.008.001.02) o `trf` (transferències pain.001.001.03, amb l'XSD SEPA de la Deutsche Kreditwirtschaft). Un tipus desconegut retorna `400`.
    - Seguretat: l'XML pujat es llegeix sense resoldre entitats, sense DTD i sense xarxa; un fitxer amb `DOCTYPE` es rebutja («DTD not allowed»).
    - Tests a `billing/tests/test_sepa_xsd_validator.py`. Cal desplegar-lo junt amb el frontend.

#### COMMUNICATION/COREDATA (`communication/views/manage_communication_process_view.py`, `communication/models.py`, `coredata/utils/phone_utils.py`, `communication/utils/*` — 1964, flux de comunicació dels talls de subministrament) (PR #70)
    - Els SMS només s'envien a mòbils (pla de numeració espanyol; els estrangers es donen per bons si tenen una llargada vàlida). Contractes i sol·licituds rebutgen afegir un telèfon fix com a telèfon SMS; els fixos ja vinculats es mantenen. Sense mòbil, la comunicació arriba pels altres canals del procés.
    - La cerca de destinataris retorna les persones que no poden rebre cap dels canals triats, amb el motiu (sense telèfon, telèfon fix, sense correu, sense adreça, sense factura electrònica, exclusió manual), i es desen al procés en el nou model `CommunicationProcessExclusion` (migració `communication.0033`), visible a `exclusions` del procés.
    - Nou origen de missatges «Tall de subministrament» amb una plantilla d'avís per a SMS, correu i carta en l'idioma de la instal·lació (migració `communication.0034`, també a `initial_data`). Noves variables `%supplycut.time_start` i `%supplycut.time_end`; les dates i hores del tall surten en hora local.
    - Nova comanda `check_sms_phones` (només informa) per llistar els telèfons SMS de contractes actius que no són mòbils. Cal desplegar-lo junt amb el frontend.

#### BILLING (`billing/views/billing_invoices_view.py`, `billing/views/reading_view.py`, `billing/tasks.py`, `documentmanager/utils/generic_export_service.py` — ACUSTOMERS-353, exportació a Excel dels avisos de lectures i pre-factures) (PR #73)
    - Nous `POST billing/<id>/invoices/export` i `POST reading/by-batch-minimal/export`: exporten a Excel (en segon pla) les factures del resum de pre-factures i les lectures del resum del lot amb els mateixos filtres, cerca i ordenació que el llistat.
    - L'Excel inclou dades de facturació, consum, lectures i avisos. Cal permís d'exportació sobre factures o lectures. Tests a `billing/tests/test_warnings_export.py`. Cal desplegar-lo junt amb el frontend.

#### STATISTICS (`statistics/utils/report_billing_service.py`, `statistics/opscripts/0003_add_billing_summary_by_rate_report.py` — resum de facturació per tarifa, tram i tarifa social) (PR #75)
    - Nou informe «Resum de facturació per tarifa, tram i tarifa social»: el resum de facturació desglossat per concepte, tarifa, tram i ajust de tarifa social (núm. de factures, unitats, base, IVA i total), amb subtotals per producte que quadren amb el resum general.
    - Mateixa selecció de factures que el resum de facturació (lot, període o rang de sèrie, explotació i filtres); els abonaments resten. L'informe es registra amb l'opscript `statistics/0003`.

#### SERVICE (`service/serializers/meter_serializer.py` — carrer del punt de subministrament al comptador) (PR #69)
    - Els punts de subministrament del detall del comptador inclouen `street_complete` (tipus de via i nom del carrer), perquè el frontend en mostri l'adreça quan el comptador no en té.

### FIX
#### BILLING (`billing/utils/sepa_file_service.py` — fitxer XML de les transferències de retorn) (PR #62, PR #64)
    - Al fitxer de transferències (pain.001), l'ordenant i la part iniciadora s'identifiquen com a organització (`OrgId`) en lloc de persona física (`PrvtId`).
    - Les transferències ja no porten `LclInstrm` amb `DIVI` (és un codi de propòsit, no un instrument local). Les remeses de cobrament mantenen `CORE` i `PrvtId` com fins ara.

#### LECTURAPP (`lecturapp/serializers.py`, `lecturapp/tasks.py` — lots de lectura només de telecontrol) (PR #71)
    - Un lot de lectura amb telecontrol i sense lectures manuals enviava a l'app tots els comptadors, perquè només es mirava `include_telecontrol`. Ara també es té en compte `include_manual` i el lot només inclou els comptadors de telecontrol (posicions, comptadors, lectures i recompte).

#### BILLING/COREDATA (`billing/views/sepa_payment_document_generate_view.py`, `coredata/views/person_piggy_bank_view.py` — transferències de retorn) (PR #74)
    - El filtre per contracte de la generació de transferències inclou ara els pagaments sense factura ni dipòsit lligats directament al contracte (p. ex. la devolució del saldo).
    - La devolució del saldo de la guardiola d'una persona fallava perquè no es llegia `mark_as_paid` de la petició; ara s'accepta (per defecte `true`).

#### COREDATA (`coredata/serializers.py` — adreces amb ciutat escrita a mà i carrer nou) (PR #77)
    - Desar una adreça estrangera o amb la ciutat escrita a mà amb un carrer nou donava error: el carrer rebia la ciutat en text. Ara el carrer es crea sense ciutat i l'adreça desa el nom de la ciutat com a text; les ciutats del catàleg continuen associant-se a l'adreça i al carrer. Tests a `coredata/tests.py`.

#### DOCUMENTMANAGER (`documentmanager/utils/csv_safety.py`, `documentmanager/utils/xlsx_safety.py`, exportacions CSV — injecció de fórmules a les exportacions) (PR #76)
    - Tots els Excel generats desen com a text els valors que comencen per `=`: un text introduït per un usuari ja no s'executa com a fórmula en obrir el fitxer. No afecta les fórmules dels fitxers que es llegeixen.
    - Les exportacions CSV posen una `'` davant dels textos que Excel interpretaria com a fórmula (`=`, `+`, `-`, `@`), excepte els números. L'actualització massiva de comptadors treu aquesta `'` en importar un CSV exportat.

#### BILLING/SERVICE (`billing/utils/invoice_service.py`, `service/serializers/supply_point_serializer.py` — consum per comptador i avís de tall) (PR #52)
    - En un contracte amb diversos punts de subministrament i tarifa per punt, el consum de cada lectura és el del seu comptador: abans s'hi sumava el de les lectures anteriors i la segona línia facturava el consum acumulat.
    - L'avís de tall del punt de subministrament es mostra també per als talls planificats sense data de fi (p. ex. per impagament).
    - Proves actualitzades al comportament actual.

### MODIFIED
#### COREDATA/AUTH (`coredata/permissions.py`, `coredata/views/config_project_view.py`, `auth/views.py` — només l'usuari `customers` modifica les configuracions internes) (PR #61)
    - L'API `config-project` es pot continuar consultant amb qualsevol usuari autenticat, però crear, modificar, esborrar i `bulk-update-values` només ho pot fer l'usuari `customers`; la resta reben `403`.
    - `GET /auth/permission/my-permissions/` retorna `can_edit_config_project`.
    - Tests a `coredata/tests.py` (`ConfigProjectPermissionTests`). Cal desplegar-lo junt amb el frontend.

### CHORE
#### BILLING/COMMUNICATION/LECTURAPP (`lecturapp/*`, `billing/utils/payment_service.py`, `communication/utils/communication_service.py`, `billing/tasks.py` — dades sensibles als logs) (PR #76)
    - Els logs ja no escriuen contrasenyes ni tokens de l'app de lectures, ni IBAN, noms, adreces, correus, assumptes o números de factura de remeses, comunicacions i factures: només identificadors i recomptes.

#### GENERAL (`order/services/rabbit.py`, `order/management/commands/run_gmao_consumer.py`, vistes i serialitzadors diversos — dades personals als logs i codi sense ús) (PR #79)
    - Els esdeveniments enviats i rebuts del GMAO ja no escriuen el contingut del missatge (dades del client) al log, només la clau i la mida.
    - Esborrats els missatges de depuració amb formularis, pagaments i IBAN de diversos mòduls (facturació, contractes, preus, servei, estadístiques, OV).
    - Esborrats fitxers antics sense ús: `billing/utils/sepa_service_prev.py`, `billing/views/detailed_billing_document_generate_view_prev.py`, `billing/views/sepa_payment_document_generate_view_prev.py` i `communication/views/manage_communication_process_view_copy.py`.

### DOCS
#### INTEGRATIONS (`docs/integrations/odoo/` — OpenAPI del connector i contracte en castellà)
    - Nova especificació OpenAPI 3.0 (`docs/integrations/odoo/openapi.yaml`) dels `POST /invoices` i `POST /payments` que Aqua360 envia al connector Odoo. Descripcions i textos dels exemples en castellà. Autenticació documentada amb la capçalera `Aqua360-Api-Key` i resposta `{ "id", "aqua_id" }`.
    - El contracte narratiu en castellà és `data-contract.es.md` (mateixa estructura, literals dels JSON en castellà). El català (`data-contract.md`) continua sent la versió de treball i enllaça l'OpenAPI. La nota d'`amount` al pagament queda alineada amb v1.1: positiu en un cobrament, negatiu en una devolució, sense canviar `payment_type`.

## [16-10-2026]
### FEAT
#### CLAIMREQUEST (`claimrequest/tasks.py` — filtre per devolució de remesa SEPA a la cerca de pagaments per a gestions d'impagats)
    - `_build_claim_request_filters` accepta `payment_remittance_return_id`: limita els contractes, els pagaments i els recomptes als pagaments d'aquesta devolució SEPA. Es combina amb la resta de filtres (estats de pagament reclamables, explotació, pagaments ja en una gestió activa, etc.). Cal desplegar-lo junt amb el frontend.
    - Amb aquest filtre, a més de les factures vençudes, també compten les factures confirmades amb el pagament retornat: després d'una devolució la factura torna a «Confirmada» i no passa a «Vençuda» fins a la data de venciment, de manera que una devolució recent no tenia pagaments reclamables. La cerca general sense devolució continua demanant factures vençudes.

#### CONTRACT (`contract/utils/bail_service.py`, `contract/views/bail_view.py`, `billing/utils/invoice_service.py` — retorn manual d'una fiança) (PR #49)
    - Nou `POST bail/return-immediately/` (`bail_ids`): retorna una fiança no retornada igual que en una baixa (pre-factura de retorn, estat pendent i després retornada) i n'abona l'import al saldo del contracte que la inclou. `400` si la fiança no està pendent de retornar o el contracte no té forma de pagament ni saldo. Cal desplegar-lo junt amb el frontend.

### FIX
#### OV (`ov/views.py`, `docs/ov/openapi.yaml`, `ov/tests.py` — `GET /ov/contract-detail/` torna a respondre directament)
    - `GET /ov/contract-detail/?contract_token=<token>` torna a donar `200` amb el detall del contracte (mateix esquema `ContractFullDetail` que `/ov/contract/{token}/`) en lloc de redirigir amb `302`.
    - El token pot contenir barra (`/`), que una ruta `<str:token>` no pot resoldre: abans provocava `NoReverseMatch` (`500`). Ara el contracte es busca per consulta (`Contract.token`).
    - El `request` es passa al serialitzador perquè el paràmetre opcional `dni` continuï desenmascarant l'IBAN i determinant `is_account_holder`. `400` si falta el paràmetre; `404` si el contracte no existeix.
    - `docs/ov/openapi.yaml`: documenta `200` (`ContractFullDetail`) i `404` en comptes del `302`.
    - Tests a `ov/tests.py` (`ContractOVViewTests`): token amb barra, token senzill, token desconegut, paràmetre absent i processament de paràmetres extra sense redirect.

#### STATISTICS (`statistics/migrations/0046_vw_contract_debt_exclude_balance.py` — el deute del contracte no compta els pagaments «En saldo») (PR #58)
    - La vista `vw_contract_debt` ja no suma els pagaments en estat «En saldo», que estan cobrats amb el saldo del contracte i la resta de l'aplicació ja tracta com a pagats. En retornar fiances, les factures pagades dels contractes de baixa sortien amb deute.
    - Tests a `statistics/tests.py` (`ContractDebtViewTests`).

#### CONTRACT (`contract/serializers/contract_serializer.py` — punt de subministrament des dels contractes de la persona) (PR #55)
    - `ContractMinimalListSerializer` exposa `supply_point_default_id`, perquè la llista de contractes de la fitxa de persona pugui obrir el punt de subministrament del contracte. Cal desplegar-lo junt amb el frontend.

#### BILLING (`billing/views/billing_preinvoices_summary_view.py` — ordre dels totals al resum de pre-factures) (PR #50)
    - El resum de pre-factures mostra el subtotal abans del total.

## [15-10-2026]

### FEAT
#### STATISTICS (`report_billing_by_zone_service.py` — línia d'ensobrat a l'execució de padrons per zona)
    - L'informe «Execució de padrons per zona de tarificació» classificava l'ensobrat com a «Altres conceptes» (no és aigua, clavegueram ni cànon). Ara es detecta per token/nom `ENSOBRAT` i surt com a concepte propi a cada zona, amb el mateix desglossament per padró (núm. factures i euros) i un total `TOTAL ENSOBRAT` al peu.

#### BILLING (`billing/templatetags/billing_filters.py` — filtres per a les cartes d'impagats)
    - Nou filtre `invoice_period_month`: últim mes del període facturat en format `MM/AAAA` (p. ex. `03/2026`), per a columnes estretes com el detall del deute de les cartes d'impagats. Mateix criteri que `invoice_period` (lectura més recent o mes de facturació menys un) i retorna "Puntual" per a les factures que no són de consum.
    - Nou filtre `address_without_city`: `address_complete` d'una adreça serialitzada sense el ", MUNICIPI" final, per als blocs de destinatari on el municipi ja surt a la línia del codi postal.
    - Nou filtre `invoice_period_short`: període facturat amb abreviatures de mes de 3 lletres en l'idioma actiu (`ABR - JUN 2026`, `JUL 2026`, `NOV 2025 - GEN 2026`); "Puntual" per a les factures que no són de consum.
    - Nou filtre `mask_iban`: IBAN en blocs de 4 separats per guions amb l'últim bloc ocult (`ES00-0000-0000-0000-0000-****`).
    - Les plantilles de carta que els facin servir requereixen aquest backend desplegat.

#### BILLING (`billing/utils/charts_service.py` — gràfic de consum de la factura a partir de les factures)
    - Cada barra del gràfic és ara el consum facturat (`Invoice.consumption`) d'una factura del contracte, en lloc del recalculat a partir de les lectures. El gràfic coincideix amb el que s'ha cobrat en comptadors generals, comptadors compartits entre contractes i refacturacions.
    - Les factures es posicionen per la data de la seva última lectura, de manera que una refacturació ocupa el lloc de la factura original encara que s'emeti mesos després.
    - S'exclouen pressupostos, factures abonades o anul·lades, els seus abonaments (que copien el consum en positiu) i les factures sense lectures (derrames i similars, que tenen `consumption` desat amb un valor que no és consum d'aigua). Ja no surten barres de lectures intermèdies que no s'han facturat.
    - Si una factura de consum no té el consum desat, es calcula a partir de les seves lectures. Si el contracte no té prou factures (p. ex. contractes que abans es facturaven fora de l'aplicació), les barres que falten s'omplen amb l'historial de lectures anterior a la factura més antiga, com fins ara.
    - S'elimina la barra apilada "Subministrament adicional": el total de cada barra no canvia, però ja no es distingeix per subministrament.

#### SERVICE (`service/models.py`, `service/serializers/company_serializer.py`, plantilles de factura, pagament, contracte, baixa, cartes i correus — ACUSTOMERS-356, blocs de contacte i avaries configurables) (PR #22)
    - Camps nous a l'empresa (migració `service.0135`) per al bloc de contacte de les plantilles: títol i horari d'atenció al client i d'avaries, i interruptors per amagar cada bloc i cada horari (per defecte es mostren). Sense configurar, els documents surten igual que fins ara.
    - Les plantilles estàndard (factures normals i simplificades, sol·licitud de factura, justificant i document de pagament, dipòsit, carta i correu bàsics, contractes, baixa, recordatori de pagament i carta de tall) prenen el títol i l'horari de l'empresa si n'hi ha.
    - Corregit el bloc d'avaries de les plantilles de factura, que mostrava el telèfon d'atenció al client: ara mostra el segon telèfon i, si no n'hi ha, el principal.
    - En un `PUT` de l'empresa, els textos que no arriben es buiden. Tests a `service/tests_company_contact_texts.py`. Cal desplegar-lo junt amb el frontend.

#### CLAIMREQUEST/BILLING (`claimrequest/tasks.py`, `billing/views/reading_batch_template_view.py` — 97, filtre per plantilla de lot de lectura a la reclamació d'impagats) (PR #31)
    - La cerca de contractes de la reclamació d'impagats accepta `selectedReadingBatchTemplatesIds`: limita als contractes el punt de subministrament dels quals és en una ruta d'aquestes plantilles.
    - El llistat de plantilles de lot de lectura accepta `route_zone` (zones de ruta) i `has_routes=true` (només plantilles amb rutes).
    - Tests a `claimrequest/tests.py`. Cal desplegar-lo junt amb el frontend.

#### COREDATA/ORDER (`coredata/migrations/0138_*`, `coredata/migrations/0139_*`, `order/filters/order_filter.py` — PA-33, selector d'ordres de treball per motiu) (PR #34)
    - Noves configuracions del motiu d'ordre de cada flux: `order_reason_contract_termination`, `order_reason_contract_activation`, `order_reason_new_connection_request` i `order_reason_customer_supply_cut` (migracions `coredata.0138` i `coredata.0139`; no se sobreescriuen si ja tenen valor). La `0138` crea el motiu «Baixa de contracte» si no existeix.
    - Nou filtre `supply_point_ids` a les ordres de treball: abans el paràmetre s'ignorava i es retornaven ordres de tot el sistema. Cal desplegar-lo junt amb el frontend.

#### COMMUNICATION/DOCUMENTMANAGER (`communication/serializers/communication_process_serializer.py`, `communication/tasks.py`, `documentmanager/*` — D_004-369, documents de comunicació agrupats per persona) (PR #36)
    - Els documents d'un procés de comunicació s'agrupen per comunicació (persona): primer la carta o el document de comunicació i després les factures i els pagaments.
    - La descàrrega en un sol PDF respecta l'ordre dels documents demanats (també amb AWS i Azure), en lloc de l'ordre de la base de dades.
    - Impagats amb «Agrupar pagaments»: també s'adjunten les factures de cada contracte; el rebut continua sent el document agrupat.
    - Tests a `communication/tests.py` i `documentmanager/tests.py`.

#### CONTRACT (`contract/serializers/contract_request_serializer.py`, `contract/opscripts/0004_fill_empty_contract_request_person.py` — D_004-368, el titular fa de sol·licitant si la sol·licitud no en té) (PR #37)
    - En crear o desar una sol·licitud de contracte sense sol·licitant, s'hi assigna el titular. No es modifica un sol·licitant existent ni quan canvia el titular.
    - Opscript `contract/0004_fill_empty_contract_request_person`: omple el sol·licitant amb el titular a les sol·licituds existents que no en tenen.
    - Tests a `contract/tests/test_contract_request_default_person.py`.

### FIX
#### SERVICE (`service/serializers/meter_serializer.py` — adreça del comptador opcional)
    - `MeterSerializer.create()` fallava sense `address_street` (variables sense definir): ara crea el comptador sense carrer ni número.
    - `MeterSerializer.update()` amb `address_street` i `address_street_number` explícitament a `null` treu l'adreça del comptador; si les claus no hi són, es manté com abans.
    - `street_complete` retorna `null` en lloc de `"None"` quan el comptador no té carrer.
    - Tests a `service/tests.py` (`TestMeterOptionalAddress`). Cal desplegar-lo junt amb el frontend.

#### CONTRACT (`contract/serializers/contract_serializer.py` — factures d'una altra sol·licitud a la llista de factures del contracte)
    - `get_request_invoices` buscava les factures de la sol·licitud amb `contract_request__token=obj.token`, és a dir, comparava el token del contracte amb el de les sol·licituds. Si una sol·licitud aliena tenia el mateix token que el contracte, les seves factures sortien a la pestanya de factures del contracte. Ara es filtra per la FK `contract_request` del contracte (igual que `contract_pinned_serializer.py` i `get_invoices_count`), i els contractes sense sol·licitud no en retornen cap.

#### BILLING (`billing/utils/sepa_service.py` — 1906, lectura dels retorns SEPA amb data no estàndard) (PR #38)
    - L'informe de retorn (pain.002) identifica el banc pel BIC o, si no hi és, pel codi d'entitat de l'IBAN del creditor, i aplica el format de data de cada banc.
    - Algun banc envia la data de creació com a AAAA-DD-MM: abans no es podia llegir, es feia servir una data anterior al cobrament i tots els retorns es descartaven com a «data de pagament posterior a la de retorn». Per a la resta de bancs es manté l'ISO i, només si no és vàlida, es prova amb el dia i el mes intercanviats.
    - Tests a `billing/tests/test_sepa_return_report.py`.

#### SERVICE/COREDATA (`service/serializers/meter_serializer.py`, `coredata/opscripts/0003_recover_lost_street_numbers.py` — ACUSTOMERS-337, números de carrer perduts en actualitzar l'adreça dels comptadors) (PR #32)
    - `MeterSerializer.create()`, en reaprofitar un número de carrer existent, només actualitza els camps que arriben (com ja feia `update()`): el número pot ser el de l'adreça d'un punt de subministrament i quedava buit.
    - Opscript `coredata/0003_recover_lost_street_numbers`: torna a omplir els números sense número ni sufix amb el de l'adreça dels elements relacionats (comptador, escomesa, finca, bateria, posició de ruta), només si totes les fonts coincideixen i és el mateix carrer. La resta es llisten per revisar-los a mà.
    - Tests a `coredata/tests.py` i `service/tests.py`.

#### LECTURAPP (`lecturapp/serializers.py`, `lecturapp/tasks.py` — D_004-189, la Lecturapp no envia comptadors inactius) (PR #40)
    - Les dades que rep la Lecturapp (comptadors de la finca, posicions de la ruta i recomptes) exclouen tant els comptadors en aforament com els inactius. Una posició amb només comptadors inactius ja no s'envia.
    - Tests a `lecturapp/tests.py` (`TestLecturappExcludesInactiveMeters`).

#### STATISTICS (`statistics/utils/billing_amount_average.py` — 29, avís d'import alt comparant només factures d'aigua) (PR #42)
    - Les mitjanes de l'avís d'import alt (completa, del mateix període i la de reserva) només compten les factures de l'origen configurat a `origin_reading_token`; les d'alta i d'altres conceptes ja no hi entren.
    - Un contracte nou amb només la factura d'alta ja no té mitjana, i la primera factura d'aigua ja no rep l'avís. Tests a `statistics/tests.py`.

### CHORE
#### COREDATA (`coredata/opscripts/0004_fill_connection_street_numbers.py` — 47, número de carrer de les escomeses que no en tenen) (PR #39)
    - Opscript `coredata/0004_fill_connection_street_numbers`: les escomeses actives sense número (i no marcades S/N) prenen el carrer i el número de l'adreça de referència (la bateria si són de bateria, el punt de subministrament si són individuals), només quan totes les fonts coincideixen i sense modificar números compartits.
    - S'ha d'executar després del `0003`; llista les escomeses que canvien de carrer i les que no es poden resoldre. Tests a `coredata/tests.py`.

## [14-10-2026]

### FEAT
#### COREDATA (`coredata/views/person_bank_view.py`, `coredata/utils/person_bank_utils.py`, `coredata/serializers.py` — 1886, edició completa del compte bancari i DNI per defecte al titular)
    - `resolve` de `PersonBank`: amb el mateix IBAN es desen titular, DNI, càrrec, número de compte, SWIFT, país i banc (abans només el SWIFT). SWIFT i país buits no esborren el valor desat; la resposta retorna `updated`. Amb un IBAN nou es continua creant un compte i l'original queda intacte.
    - DNI buit: `99999999R` si el titular és una altra persona, o el document de la persona si n'és el titular. La regla s'aplica a `resolve`, `PersonBankSaveSerializer` i als comptes desats des de la fitxa de persona.
    - Tests a `coredata/tests.py`.

#### SERVICE (`service/utils/supply_cut_bulk_planner.py`, `service/views/supply_cut_view.py`, `coredata/views/street_view.py`, `communication/utils/communication_service.py` — D_004-367, planificació massiva de talls de subministrament)
    - Nou `supply_cut_bulk_planner`: resol una llista d'identificadors d'un sol tipus (`contract_token`, `supply_point_id`, `street_id`) a punts de subministrament, amb deduplicació, detecció de conflictes amb talls oberts i previsualització. Límit de 5.000 identificadors; per carrer només punts actius.
    - Noves accions `bulk-plan/preview/` i `bulk-plan/` a `SupplyCutViewSet`: el servidor torna a resoldre la llista, retorna `409` si hi ha conflictes sense `override_conflicts` i crea el tall en estat Planificat (`source=manual`), amb els punts vinculats però sense tallar fins a `date_start`. Permís `add_supplycut`.
    - Nova acció `resolve-ids` a `StreetViewSet` (id de carrer → etiqueta).
    - Noves variables de plantilla `%supplycut.*` a les comunicacions; `affected_addresses` només llista els punts on el destinatari és titular, propietari o llogater.
    - Tests: `service/tests_supply_cut_bulk_planner.py` i `communication/tests.py`. Cal desplegar-lo junt amb el frontend.

#### SERVICE/COMMUNICATION (`service/models.py`, `service/utils/smtp_password_crypto.py`, `service/serializers/value_objects_serializer.py`, `communication/utils/communication_service.py` — D_004-374, contrasenya SMTP pròpia per a cada correu de l'empresa)
    - Nou camp `CompanyConfigEmail.encrypted_password` (migració `service.0134`), xifrat amb Fernet amb la clau `SMTP_PASSWORD_ENCRYPTION_KEY` del `.env` (admet diverses claus separades per comes per rotar-la).
    - Enviament SMTP i `send_test_email`: la contrasenya s'agafa, per ordre, de la desada al correu, de la variable `EMAIL_PASSWORD_*` del correu, de la de la configuració i d'`EMAIL_HOST_PASSWORD`. Només es llegeixen variables d'entorn `EMAIL_PASSWORD_*`.
    - Corregit l'usuari SMTP quan no hi ha correu per defecte (es passava l'objecte en lloc de l'adreça).
    - API: la contrasenya és només d'escriptura (`password`, `clear_password`) i la resposta només inclou `has_password`. Sense clau configurada es rebutja amb `400`. El desat de la configuració és atòmic i deixa un sol correu per defecte.
    - Tests: `communication/tests_smtp_password.py`. Cal desplegar-lo junt amb el frontend.

#### CONTRACT (`contract/utils/contract_service.py`, `contract/views/close_contract_termination_request_view.py`, `billing/views/generate_invoice_budget_view.py` — ACUSTOMERS-344, finalitzar la baixa des de l'alta i el canvi de nom)
    - El tancament de la baixa accepta `ignore_invoice`: la baixa queda finalitzada «sense factura» tret que es facturi la lectura de tall o ja tingui factura o pressupost. Mantenint el número de contracte, la baixa també queda «sense factura».
    - Generar el pressupost d'una baixa treu la marca «sense factura».
    - Tests: `contract/tests/test_finalize_termination_from_request.py`.

#### BILLING (`billing/models.py`, `billing/utils/smart_metering_service.py`, `billing/views/reading_document_view.py`, `billing/serializers/reading_document_serializer.py` — D_004-217, càrrega de lectures de Smart Metering des d'Introduir lectures)
    - `ReadingDocument` té els camps nous `source` (`FILE` / `SMART_METERING`) i `reading_date` (migració `billing.0322`).
    - La previsualització i la importació de Smart Metering ja no depenen del lot: cobreixen tots els comptadors de Smart Metering i desen les lectures en un document de lectures, amb un Excel generat (fulls de lectures desades i de no carregades, amb el motiu).
    - No es modifiquen lectures ja assignades a un lot, facturades o d'un altre document, per evitar lectures estranyes en carregar des de lots diferents.
    - Una sola càrrega per data: es bloqueja si ja n'hi ha una, i només es pot substituir mentre les seves lectures no s'hagin fet servir.
    - API: accions noves `smart-metering/preview` i `smart-metering/import` a `reading-document`. S'eliminen les del lot (`reading-batch-summary`) i les seves tasques. Els documents de Smart Metering no es poden processar amb plantilla.
    - Cal desplegar-lo junt amb el frontend. Tests: `billing/tests/test_smart_metering_document.py`.

### CHORE
#### COMMUNICATION (`communication/serializers/message_template_serializer.py` — 1860)
    - `MessageTemplateListSerializer` exposa `is_active` perquè el selector de plantilles de l'enviament de factures descarti les inactives.

## [13-10-2026]

### FEAT
#### BILLING (`billing/utils/reading_service.py`, `billing/views/reading_view.py`, `billing/serializers/reading_serializer.py` — lectures enllaçades per `copied_from`)
    - Quan es modifica una lectura que és còpia d'una altra o que té còpies (`copied_from` / `copies`, p. ex. comptadors generals repartits entre contractes), la modificació s'aplica a totes les lectures del grup.
    - Nous helpers `get_reading_copy_group_root`, `get_reading_copy_group` (lectures actives i no de control del grup, sense la pròpia) i `get_copy_calculated_value`: cada còpia manté la seva lectura anterior, i el consum es recalcula contra aquesta més el mateix ajust manual que s'hagi fet a la lectura editada.
    - Edició directa (`PUT`/`PATCH` a `/billing/reading/<id>/`): `ReadingViewSet.perform_update` propaga `reading_date`, `reading_value`, `leak_value` i el consum recalculat a la resta del grup (via `ReadingSerializer`, dins la mateixa transacció). Només si algun d'aquests valors ha canviat (sense fuita i fuita 0 es consideren iguals), i a cada còpia només s'envien els camps que hi són diferents: una còpia que ja té els mateixos valors no es torna a desar (desar-la li trauria la marca d'estimada i el moviment de la bossa). Canviar només la nota d'alerta no toca les còpies.
    - Modificació de lectures del contracte (`modify_existing_readings`): quan una lectura del grup es substitueix per una de nova, les altres també (la vella passa a control, s'afegeix a `modified_readings`, es registra a `LogReadingChange` i es traspassa a les baixes). Les noves lectures queden enllaçades a la nova original per `copied_from`. Les còpies que no canvien de valor no es substitueixen, només es tornen a enllaçar.
    - `ReadingSerializer`, `ReadingByBatchSerializer` i `ReadingByBatchMinimalSerializer` exposen `copies_count` (nombre de lectures del grup que es modificaran juntament amb la lectura).
    - Tests: `billing/tests/test_reading_copy_group.py`.

#### BILLING/SERVICE (D_004-357 — compte de l'empresa per a les transferències de retorn)
    - `CompanyBankRouting` té un camp nou `operation` (`collection` / `transfer`): les remeses de cobrament (pain.008) i les transferències de retorn als clients (pain.001) tenen ara mapes d'encaminament independents. Permet, per exemple, cobrar els IBAN nacionals per un compte i els estrangers per un altre, i fer els retorns a l'inrevés.
    - Les restriccions úniques passen a ser per operació. La migració `service.0131` hi afegeix el camp i la `service.0132` copia les files existents com a `transfer`, de manera que els retorns continuen sortint pel mateix compte que abans fins que se'n canviï el mapa.
    - `resolve_payment_banks` rep `is_return` i aplica el mapa corresponent. La generació de remeses i el llistat de rebuts el passen segons el tipus de remesa.
    - API `company-bank-routing`: `bulk` i `set_special` accepten `operation` (per defecte `collection`, així que les peticions d'abans no canvien). `matrix` manté les claus d'abans per als cobraments i afegeix les de transferències a `transfer`, dins de cada fila i a l'arrel. El filtre accepta `operation`.
    - Tests a `billing/tests/test_remittance_routing.py`.

#### COMMUNICATION (`communication/views/communication_view.py`, `communication/views/communication_process_view.py`, `communication/permissions.py`, `communication/filters/*` — D_004-370, eliminació lògica de comunicacions i processos cancel·lats)
    - Noves accions `POST delete-cancelled` a `CommunicationViewSet` i `CommunicationProcessViewSet`: esborrat lògic (`is_active=False`) només si l'element està cancel·lat; si no, `400`. El `DELETE` actual continua cancel·lant.
    - Eliminar un procés cancel·lat desactiva també les seves comunicacions cancel·lades. Queda registrat a `LogCommunicationStatusChange` i `LogCommunicationProcessStatusChange` amb observació i usuari.
    - Nou permís `CommunicationDeletePermission`: les accions exigeixen `delete_communication` encara que vagin per `POST`. Constant `CANCELLED_STATUS_TOKEN` (`'-1'`) a `communication.models`.
    - Filtre `exclude_cancelled` a `CommunicationFilter` i `CommunicationProcessFilter` (s'ignora si hi ha un filtre d'estat explícit).
    - Els eliminats ja no compten al total de comunicacions de persona i contracte, als totals del procés ni a l'exportació CSV.
    - Sense migracions (`is_active` ja existia). Cal desplegar-lo junt amb el frontend. Tests a `communication/tests.py`.

#### OV/AUTH (`ov/views.py`, `ov/serializers.py`, `ov/urls.py`, `auth/urls.py`, `docs/ov/openapi.yaml` — cerca de contracte per NIC i descàrrega de factures en ZIP)
    - Nou `GET /ov/contract/by-nic/<nic>/` (NIC amb 1 o 2 barres, validat amb regex abans de consultar la BD).
    - Nou `POST /ov/invoices/download/`: genera un ZIP amb els PDF de les factures definitives del contracte indicat.
    - `POST /auth/login` accepta també la ruta sense barra final.
    - OpenAPI actualitzat amb els dos endpoints nous (exemples anonimitzats).

<!-- Entrades afegides el 09-10-2026 després de la release 1.133.01: es comptabilitzen en aquest dia. -->
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

### FIX
#### BILLING (`billing/utils/remittance_routing.py` — rebuts sense empresa en remeses d'una sola empresa)
    - Els rebuts sense factura ni contracte (p. ex. devolucions a una persona) s'atribuïen a l'única empresa seleccionada, però el mapa d'encaminament i el compte per defecte només es carregaven per a les empreses que sortien dels rebuts. Aquests rebuts acabaven sempre amb l'avís `company_without_bank` i fora de la remesa. Ara l'empresa s'atribueix abans de carregar els mapes.
#### CONTRACT (`contract/utils/aca_tram_service.py` — PA-49: nombre de persones i bonificació d'ampliació de trams de l'ACA)
    - Es podia aplicar la bonificació d'ampliació de trams a contractes que no arriben al mínim de persones: `create_aca_bonification_on_total_persons_increase` la creava amb qualsevol augment de `total_persons` (p. ex. d'1 a 2) i la variable de membres no tenia cap validació.
    - Nou `ConfigProject` `aca_tram_min_persons` (migració `coredata.0137`, valor `4`; si no existeix o no és un enter, també 4). Helper `watchdog.aca_config.aca_tram_min_persons()`.
    - La lògica passa de `contract/signals.py` a `contract/utils/aca_tram_service.py` (`sync_aca_tram_with_total_persons`, cridat pel nou receptor `sync_aca_tram_on_total_persons_change`):
        - Només es crea la bonificació si les persones augmenten i arriben al mínim.
        - Si el contracte ja la té, s'actualitza el nombre de membres també quan baixa (sempre per sobre del mínim); no es torna a encuar la sol·licitud ACA si el valor no canvia.
        - Si baixa per sota del mínim, la bonificació es desactiva (amb data de fi), `deactivate_bonification` en desactiva les variables i s'esborra la sol·licitud ACA encara no enviada.
    - `sync_contract_total_persons_from_aca_variable` ja no toca el contracte si la variable està inactiva, si la bonificació està desactivada o si el valor no arriba al mínim. Abans, en desactivar la bonificació, el contracte recuperava el nombre antic de membres. Quan sí que l'actualitza, ara ho registra a `LogContractTotalMembers`.
    - `VariableSaveSerializer.validate` rebutja la variable de membres per sota del mínim (excepte en desactivar-la).
    - `ContractDataChangeEditSerializer` exposa `aca_tram_min_persons` (només si el contracte té la bonificació activa) perquè el formulari avisi abans de desactivar-la.
    - Tot plegat només s'aplica amb `uses_aca` actiu; als projectes sense ACA no canvia res.
    - Tests: `contract/tests/test_aca_tram_service.py`.

#### BILLING (`billing/views/epayment_document_generate_view.py` — empresa emissora de la factura electrònica)
    - Amb múltiples empreses (`use_multiple_companies`), l'XML de la factura electrònica agafa l'empresa de la factura com a emissora (NIF i comptes). Sense múltiples empreses es manté la lògica anterior (empresa de l'explotació o `main_company_token`).

#### BILLING (`billing/views/billing_view.py` — D_004-373, contractes no facturables fora dels possibles no facturats)
    - `check_missing` comptava els contractes no facturables (`block_billing`) com a possibles no facturats. Ara s'exclouen de la llista, dels totals (`missing_contracts`, `missing_by_route`, `missing_by_exploitation`), dels llistats filtrats i de l'Excel.
    - El camp `block_billing` de la resposta passa a ser el nombre de contractes no facturables sense factura al període, comptats a part. Cal desplegar-lo junt amb el frontend.
    - Tests: `billing/tests/test_check_missing_block_billing.py`.

#### BILLING (`billing/serializers/reading_serializer.py` — 1876, lectures a 0 o facturades sobreescrites en entrar-ne una)
    - En crear una lectura manual, una lectura anterior amb valor 0 es tractava com a buida i es reaprofitava (data, lot i origen nous) encara que estigués facturada: desapareixia de l'històric i la nova no es podia entrar.
    - Ara només es reaprofita si no té valor (`reading_value` nul) i no té factura definitiva (`BILLED_READING_FILTER`); en la resta de casos es crea una lectura nova.
    - Tests: `billing/tests/test_reading_save_previous_reading.py`.

#### CONTRACT (`contract/utils/contract_request_service.py`, `contract/views/close_contract_termination_request_view.py` — D_004-278, estat del punt de subministrament després d'una baixa)
    - `check_and_deactivate_supply_point_and_meter` no feia res si la baixa no tenia lectures i saltava els punts sense comptador: el punt quedava «Actiu» sense cap contracte actiu. Ara es revisen sempre tots els punts del contracte.
    - Els punts sense altres contractes actius ni sol·licituds obertes reben l'estat triat a la pantalla (`supply_point_status`). Sense estat triat (baixa completada pel tancament de les ordres) es manté l'estat si ja és de baixa; si no, passa al predeterminat. El comptador passa a inactiu, excepte si és compartit (general) i encara és a altres punts.
    - Sense lectures de baixa no es desen `removal_at` ni `uninstallation_at`.
    - `CloseContractTerminationRequestViewSet` delega l'estat al servei (un punt amb un altre contracte actiu conserva el seu estat); el camp `status` és opcional. Afecta el tancament manual i el tancament per ordres (`contract_termination_check_orders`).
    - Tests: `contract/tests/test_termination_supply_point_status.py`.

#### SERVICE (`service/services/meter_change_service.py`, `service/views/supply_point_view.py` — E_25_164-28, dates d'instal·lació en el canvi de comptador)
    - El canvi de comptador no desava cap data: la data del canvi passa a ser la `installation_at` del comptador nou i la `uninstallation_at` del retirat, només si encara no en tenen. El vell només es marca com a desinstal·lat quan ja no és a cap punt de subministrament.
    - Nou helper `set_meter_change_dates`, cridat des de `MeterChangeService.apply` (ordres de treball i RabbitMQ/GMAO) i des de `SupplyPointViewSet.save_meter_change`. Les ordres de treball usen la data del dia.
    - Tests: `service/tests_meter_change_dates.py`.

#### SERVICE (`service/serializers/supply_point_serializer.py` — escomesa en editar un punt de subministrament)
    - Un `connection_id` buit o `NaN` en editar un punt de subministrament ja no esborra l'escomesa actual.

#### STATISTICS (`statistics/utils/report_billing_service.py` — resum ACA: volum consumit igual al facturat)
    - Al resum de l'informe ACA, el consum domèstic, industrial i municipal es calcula amb les unitats facturades (sense la part fixa), de manera que quadra amb el volum facturat.

#### PRICING (`pricing/models.py` — migracions fantasma de la categoria del concepte comptable)
    - `AccountingConcept.CATEGORY_CHOICES` era un `set`: l'ordre canviava a cada procés de Python i, segons l'execució, `makemigrations`/`migrate` detectaven un canvi inexistent a `pricing`. Passa a ser una llista amb el mateix ordre que la migració `0119`; no cal cap migració nova.

### CHORE
#### GENERAL (`.gitignore`, `backend/.gitignore` — fitxers que no han d'anar al repositori)
    - Les personalitzacions per client (`*_personalized.*`, `*_personalized_*`) deixen d'anar al repositori i s'ignoren: 8 plantilles HTML, `billing/utils/generate_serie_final_personalized.py` i `coredata/utils/name_utils_personalized.py`. El codi ja les carrega només si existeixen (`template_utils`, `try/except ImportError`); sense elles s'usa la versió per defecte.
    - Es recuperen les entrades del `.gitignore` del repositori antic que faltaven: exports reals d'Odoo (`integrations/outbound/odoo/exports/` i `exports-jsons.zip`), `dades_prod.json`, `deploy_info.json`, `DEPLOYS.md`, `celerybeat-schedule*`, `celerybeat.pid` i, a l'arrel, `.claude/settings.local.json`.
    - Es treuen del repositori `celerybeat-schedule` (si viatja amb la imatge, cada contenidor nou considera vençudes totes les tasques periòdiques) i els exports d'Odoo, que contenen dades de clients.
    - En fer pull, Git esborra aquests fitxers de la còpia de treball: qui els faci servir n'ha de fer una còpia abans. Celery torna a crear `celerybeat-schedule` sol.

#### CONTRACT (`contract/utils/bail_service.py`, `contract/views/bail_view.py`, `contract/tasks.py`, `contract/opscripts/0003_fix_pending_bails.py` — fiances en donar de baixa un contracte)
    - En donar de baixa un contracte, la fiança passa automàticament al saldo del contracte en comptes de quedar-se pendent.
    - Opscript `contract/0003_fix_pending_bails` per regularitzar les fiances que havien quedat pendents.

## [09-10-2026]

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
