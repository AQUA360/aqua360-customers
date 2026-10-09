
# Changelog Backend

## [31-07-2026]

### FEAT
#### INTEGRATIONS GISWATER (HTTP Basic Auth com a fallback)

    - Si`GISWATER_KEYCLOAK_URL` està buit, el client outbound (`integrations/outbound/giswater`) autentica amb HTTP Basic Auth (`GISWATER_USERNAME` / `GISWATER_PASSWORD`) en lloc d'OAuth Keycloak.
    - Noves variables a `.env` / `customers/settings.py`. `validate_giswater_auth` valida els dos modes.

### FIX
#### COMMUNICATION (`send_electronic_mail` — `sent_at` amb datetime naïve)

    -`send_electronic_mail` (`communication/utils/communication_service.py`), cridat des de la task Celery `send_communications_task`: en marcar l'enviament assignava `Communication.sent_at = datetime.now()`, generant un `RuntimeWarning` de Django (`DateTimeField received a naive datetime while time zone support is active`). Ara usa `timezone.now()`.

#### BILLING (`GET /billing/billing/<id>/check-missing/` — no detectava contractes sense factura del seu període real)

    -`BillingViewSet.check_missing` (`billing/views/billing_view.py`): el rang de dates que delimitava quins contractes eren "no facturats" es calculava a partir del `Min`/`Max` de `reading_date` de les lectures ja associades al propi `Billing`. Un contracte sense cap lectura vinculada a aquest `Billing` quedava fora del rang de cerca i no apareixia ni a facturats ni a la llista de "no facturats".
    - Ara el rang (`first_start_reading`/`last_end_reading`) es calcula com el període calendari real que factura aquest `Billing`, segons la periodicitat del facturador (`Biller.period_type` → nombre de mesos: trimestral=3, mensual=1, etc.). El mes/any de referència s'obté parsejant el sufix `-{mes}{any}` que `create_billings` (`billing/tasks.py`) grava al `token`/`name` en crear el lot pel període corresponent — **no** de `billing.created_at`, ja que un `Billing` es pot crear amb retard respecte al període que factura (p. ex. període 1, gener-març, creat al maig). Si no es pot parsejar (Billing creat per un altre flux), cau a `created_at`.
    - `route_contracts`/`exploitation_contracts` es filtren per `created_at__date__lte` del final del període, i un contracte es considera "missing" si **no té cap factura que cobreixi aquest període** (per lectures dins del rang, o per `issue_date` dins del rang si no en té) a **qualsevol** `Billing`, no només l'actual — així es detecten contractes ja exclosos erròniament pel `Billing` concret però encara pendents pel període.
    - `last_end_reading` (i l'`end_date` retornat a la resposta) es capa a `min(..., avui)`, ja que no es poden generar factures amb dates futures.

#### BILLING (`GET /billing/reading/` — el llistat de lectures mostrava també les de control)

    -`ReadingViewSet` (`billing/views/reading_view.py`): el llistat general (p. ex. `GET /billing/reading/?contract=4&ordering=-reading_date`) no filtrava per `Reading.is_control`, tot i que el `ReadingFilter` ja permetia fer-ho explícitament amb `?is_control=`. Les lectures de control (no facturables) sortien barrejades amb la resta.
    - Nou `get_queryset()`: a l'acció `list`, si no s'informa `?is_control=` a la petició, s'exclouen per defecte les lectures amb `is_control=True`, de manera que només es mostren les realment facturables. Si es passa `?is_control=` explícitament, es respecta el valor demanat (no es duplica el filtre).

#### SERVICE (`GET /service/supply-point/<id>/` — el deute mostrat no coincidia amb la suma de deute dels contractes)

    -`get_contract_debt`/`to_representation` (`SupplyPointSerializer`, `service/serializers/supply_point_serializer.py`): el deute del punt de subministrament es calculava sumant `Payment.amount` filtrant només per `Payment.status`, sense tenir en compte que `Invoice` té el seu propi camp `status` (FK a `InvoiceStatus`, independent del `PaymentStatus` del pagament). Una factura sense estat assignat (`Invoice.status IS NULL`) amb algun pagament associat es comptava igualment com a deute, encara que cap dels `total_debt` per contracte de la mateixa resposta la reflectís (aquests ja filtraven per estats de pagament més restrictius).
    - Afegit `invoice__status__isnull=False` a les dues consultes (`get_contract_debt` i el `total_debt` per contracte dins `to_representation`), de manera que els pagaments de factures sense estat ja no es compten com a deute.

## [30-07-2026]

### FEAT
#### STATISTICS (Exports CSV de contractes — columnes Route i RoutePosition)

    - Als exports`POST /statistics/contracts/export/`, `POST /statistics/contracts/pricerates/export/` i `POST /statistics/contracts/invoice-reading-summary/export/`, s'afegeixen les columnes `Route` i `RoutePosition` a partir de la `Property` del `SupplyPoint` per defecte del contracte (`supply_point_default → property → route_position → route`).
    - `Route`: token de la ruta (fallback `name` / `id`). `RoutePosition`: `position` (fallback `token`).
    - A l'export general i de pricerates (`contract/utils/contract_csv_export.py`, reutilitzat per `contract_tariffs_export.py`): columnes just després de `Punt subministrament (adreça)`, amb `select_related` ampliat.
    - A l'export invoice-reading-summary (`contract/utils/contract_invoice_reading_summary_export.py`): columnes just després de `Nom ruta` i abans del bloc de comptador.

#### BILLING (Revert protegit d'un lot de lectures ja finalitzat)

    - Nou`POST /billing/reading-batch/<id>/revert/` (`ReadingBatchRevertView`, `billing/views/reading_batch_generate_view.py`): permet tornar un `ReadingBatch` de `finish` a `processing` per reprocessar-lo, sense l'esborrat total i sense proteccions de l'antiga `ReadingBatchRegenerateView`.
    - Bloqueja el revert amb `409` (`blocked_reading_ids`) si alguna `Reading` del lot té una `Invoice` amb `type_final='F'` (factura definitiva) vinculada; cal gestionar-la manualment abans.
    - Desvincula (`invoice.readings.remove()`) les factures esborrany (`type_final='P'`) de les lectures del lot abans de reencuar `process_reading_batch`, i ho reporta a `unlinked_draft_invoice_ids`, ja que el seu valor pot canviar en el reprocés.
    - Ja no esborra cap `Reading`: reseteja `processed_at`/`is_processed` i deixa que `process_reading_batch` recalculi in-place.

### FIX
#### BILLING (`ReadingBatchSaveSerializer` — es podia reobrir un lot amb factura definitiva ja emesa)

    -`ReadingBatchSaveSerializer.update()` (`billing/serializers/reading_batch_serializer.py`): el canvi d'estat via `status_token` (`PATCH`/`PUT /billing/reading-batch/<id>/`) s'acceptava sempre, sense validar la transició. Un lot en estat `finish` amb lectures ja facturades en definitiva (`Invoice.type_final='F'`) es podia tornar a `processing` sense cap avís, deixant via lliure a un reprocés/esborrat de lectures ja facturades.
    - Ara `_validate_status_transition()` rebutja (`400`, error al camp `status_token`) qualsevol canvi d'estat que surti de `finish` si detecta `Reading` del lot amb factura definitiva vinculada.

#### BILLING (`get_reading_minimal_object` — el reprocés de lectures sobreescrivia sempre tota la fila i no actualitzava la bossa d'estimades)

    -`billing/utils/reading_service.py`: cada crida feia `reading.save()` complet (tots els camps), independentment de si algun valor havia canviat, i mai tocava `EstimatedBag`/`EstimatedBagMovement` encara que el `calculated_value` d'una lectura estimada canviés durant el reprocés d'un lot (`process_reading_batch`).
    - Ara només es persisteixen (`save(update_fields=[...])`) els camps que realment difereixen del valor previ. Si el `calculated_value` d'una `Reading` estimada canvia, s'aplica el diferencial a `EstimatedBag.total_consumption` (suma, no sobreescriptura) i s'actualitza l'`EstimatedBagMovement` existent en lloc de recrear-lo — mateix patró ja usat a `recalculate_estimated_readings_batch.py`.

#### SERVICE (`SupplyPointSerializer.create` — resolució del codi postal al crear finca)

    -`POST /service/supply-point/` (`SupplyPointSerializer.create`, `service/serializers/supply_point_serializer.py`): en crear un punt de subministrament sense `property_id`, el backend creava una `Property` amb `PostalCode.objects.get(id=address_data['postal_code'])`. El frontend envia el **codi postal com text** (p. ex. `"08349"`, via `address_postal_code.code` de la connexió), no l'ID de `PostalCode`, i el endpoint petava amb `PostalCode matching query does not exist`. Ara `_resolve_postal_code()` resol el valor per **ID** (si és numéric) o per **codi**; si no existe a la BD, `address_postal_code` queda `null` en lloc d'un 500. També s'aplica a `RoutePosition.address_postal_code` en la mateixa creació (abans s'assignava el `CharField` de l'`Address` en un `ForeignKey`).

#### BILLING (`GET /billing/billing/<id>/invoices` — l'ordenació per `consumption_days` no funcionava)

    -`BillingInvoicesViewSet` (`billing/views/billing_invoices_view.py`): `consumption_days` és un camp real del model `Invoice`, però no estava a la whitelist `ordering_fields` de l'`OrderingFilter` de DRF, que ignora silenciosament qualsevol `?ordering=` no inclòs a la llista i cau a l'ordre per defecte (`-created_at`). Afegit `'consumption_days'` a `ordering_fields`.

### CHORE
#### DEPLOY (Runbook i script per unificar el deploy de tots els clients, backend + frontend, amb registre de versions)

    - Nou`docs/DEPLOY_RUNBOOK.md`: guia pas a pas del procés de deploy amb Mina (identificació de client directe/Docker, checklist previ, comandes per tipus de client, rollback, verificació post-deploy), documentant el mètode ja existent sense canviar `config/deploy.rb`/`config/deploy_docker.rb`.
    - Nou `config/deploy_all.sh`: detecta automàticament tots els clients a `config/private/*.rb` (directe vs Docker, segons si defineixen `backend_docker_path`) i permet desplegar-los tots o un subconjunt en una sola comanda (`--direct`/`--docker`/`--test`/`--production`/`--only`/`--skip`/`--dry-run`/`--continue-on-error`). Per als clients directes, unifica backend + frontend: si el mateix client existeix a `../avsis-customers-frontend/config/private/<client>.rb`, encadena `mina <client> deploy` a totes dues carpetes sense haver de fer `cd` manual (els clients Docker ja ho fan junts via `deploy_docker`).
    - Cada execució real deixa un registre a `logs/deploy_log.md` (taula Markdown, ignorada per git, llegible directament amb `cat`/editor): data, client, tier, tipus, branca+versió (SHA remot via `git ls-remote`, sense necessitat d'entrar als servidors) de backend/frontend, i estat `ok`/`error` de cada component amb el missatge d'error. Consultable amb `config/deploy_all.sh --show-log`.

## [29-07-2026]

### FEAT
#### BILLING (Devolució de factura — opció devolució de saldo i recalcul de left_to_pay)

    -`PUT /billing/invoice/<id>/pass-to-pending/` (`InvoiceViewSet.pass_to_pending`, `billing/views/invoice_view.py`): la devolució manual pot aplicar-se **només al pagament SEPA** o **també al pagament per saldo (BALANCE)** segons l’opció seleccionada al modal. En conseqüència, `left_to_pay` i els moviments/estats de pagament es recalculen segons l’import real retornat (ex.: si només es retorna SEPA, `left_to_pay` reflecteix la part SEPA; si també es retorna el saldo, `left_to_pay` torna a ser `total_final`). El modal de devolució del frontend ara inclou el checkbox per decidir si el saldo (hucha) s’ha de reintegrar.

#### GENERAL (Base per a factures multi-idioma — `gl` afegit, camp `language` a contracte i selecció de plantilla per idioma)

    -`LANGUAGES` (`customers/settings.py`): afegit `'gl'` (Galego) al costat de `ca`/`es`/`en`.
    - Nou camp `language` (`CharField`, choices `settings.LANGUAGES`, per defecte `settings.LANGUAGE`) a `Contract` i `ContractRequest` (`contract/models.py`, migració `contract/migrations/0234_add_language_field.py`). `contract_create()` (`contract/utils/contract_service.py`) el propaga de la `ContractRequest` al `Contract` en finalitzar l'alta (fallback a `settings.LANGUAGE` si no n'hi ha).
    - `resolve_template_path()` (`coredata/utils/template_utils.py`) accepta ara un paràmetre opcional `lang`: cerca, per ordre de prioritat, `_personalized_{lang}` → `_{lang}` → `_personalized` → la plantilla per defecte, sense necessitat de tocar cap `TEMPLATE_LOADER`. Les plantilles per idioma es gestionen a l'altre projecte (no es dupliquen en aquest repo).
    - `invoice_pdf.py` (generació del PDF de factura): la resolució de `invoice_template.html`/`invoice_request_template.html` passa ara `lang=contract.language` (o `settings.LANGUAGE_CODE` si la factura no té contracte associat), de manera que l'idioma de la factura ve sempre del contracte, no d'una selecció puntual de l'usuari.
    - `locale/gl/LC_MESSAGES/django.po`: generat i traduïdes 454 de les ~464 cadenes reals de l'aplicació (la resta són cadenes de llibreries de tercers capturades per error per `makemessages`, ja presents igual a `ca`/`es`, sense traduir intencionadament).
    - `Product`, `PriceRate`, `LineItemType` (`pricing/models.py`): nou camp `name_translations` (`JSONField`, `{idioma: text}`), migració `pricing/migrations/0101_add_name_translations.py`. Validat als `Save Serializer` corresponents (`pricing/serializers/{product,price_rate,line_item_type}_serializer.py`): comprova que sigui un objecte i que les claus siguin idiomes vàlids de `settings.LANGUAGES`.
    - Estès el mateix mecanisme de plantilla per idioma a `contract_template.html`: `contract_pdf_service.py` (generació principal del contracte) i `contract_process_aca_document_view.py` (`ProcessACADocumentViewSet`) construeixen ara la llista `[contract_template_personalized_{lang}.html, contract_template_{lang}.html, contract_template_personalized.html, contract_template.html]` (amb `lang = instance.language`/`contract_request.language`, fallback `settings.LANGUAGE_CODE`) i la passen a `render_to_string`, seguint exactament el mateix ordre de prioritat que `resolve_template_path` per a les factures, sense tocar cap plantilla `.html` ni el `TEMPLATE_LOADER`.
    - `ContractDataChange` (`contract/models.py`, migració `contract/migrations/0235_contractdatachange_new_language_and_more.py`): nous camps `new_language`/`previous_language`. `ContractDataChangeSerializer.create()` (`contract/serializers/contract_data_change_serializer.py`) aplica ara de debò el canvi (`contract.language = new_language; contract.save()`) quan `new_language` ve informat i difereix de l'actual, i apareix a l'historial de canvis del contracte (`contract/views/contract_view.py`, `field_name: 'language'`). Afegit també `'language'` als `fields` de `ContractDataChangeEditSerializer` (`contract/serializers/contract_data_change_edit_serializer.py`), perquè aparegui al formulari de modificació de dades (`GET`/`PUT .../data-change/`).
    - `create_line_item_data`/`create_from_lineitemtype`/`create_from_lineitemtype_connection` (`billing/utils/invoice_line_item_service.py`): el `name`/`product_name`/`price_rate_name` de cada `InvoiceLineItem` (inclosos els trams de consum) es resol ara amb l'idioma del contracte (`_translated_name()`), en lloc de fer servir sempre el `name` en català. Limitació: `tram.name_stretch` no té traducció, així que la part del nom que ve del tram sempre surt en l'idioma en què es va definir la tarifa.
    - **Rearquitectura de `name_translations`**: substituït el `JSONField` de `Product`/`PriceRate`/`LineItemType` per taules dedicades `ProductI18n`/`PriceRateI18n`/`LineItemTypeI18n` (`pricing/models.py`, `related_name='translations'`, `unique_together(parent, language)`), migració `pricing/migrations/0102_remove_lineitemtype_name_translations_and_more.py` (amb `RunPython` que migra les dades existents del JSON abans d'eliminar el camp). Nou `TranslatableFieldMixin` (`pricing/serializers/translatable_mixin.py`) manté el mateix contracte API (`{idioma: text}` al body) sobre les 4 taules noves. **Nou**: `PriceIntervalStretchI18n` afegeix per primer cop traducció als trams (`name_stretch_translations`, mateix `PUT /pricing/price-interval-stretch/<id>/` ja existent) — abans no n'hi havia cap.

### FIX
#### COMMUNICATION (`mark-as-sent` — comunicacions postals individuals i `sent_at`)

    -`POST /communication/communication/mark-as-sent/` (`CommunicationViewSet.mark_as_sent`, `communication/views/communication_view.py`): ara accepta `communication_ids` (a més de `process_id`) per poder marcar com a enviades les cartes d'una comunicació individual (abans només funcionava amb procés massiu). En marcar, s'assigna també `sent_at` (abans només es canviava l'`status`, i el llistat de comunicacions —que mostra `sent_at`— continuava sense data d'enviament). Es registra el canvi a `LogCommunicationStatusChange`.

#### CONTRACT (`contract_create` — consulta innecessària de `MeterStatus` "sense comptador")

    -`contract_create()` (`contract/utils/contract_service.py`): la resolució de `meter_no_meter_status` (via `ConfigProject.token_meter_status_no_meter` → `MeterStatus`) es feia sempre a l'inici de la funció, encara que el `supply_point` ja tingués comptador assignat i mai calgués aquest estat. Si aquesta configuració estava trencada (p. ex. `ConfigProject` apuntant a un token sense cap `MeterStatus` corresponent), `finalize-in-place`/`contract_create` petava amb un 500 per a **tots** els contractes, també els que ja tenien comptador actiu. Ara la consulta només es fa dins de la branca `else` (`supply_point` sense comptador), just abans de crear el comptador fictici.

#### COMMUNICATION (Generació de comunicacions — contractes del mateix titular amb emails diferents es fusionaven en una sola comunicació)

    - Detectat en un cas real: dos contractes del mateix titular, cadascun amb un`Contract.person_contact_email` diferent, van acabar enviant les seves factures dins la mateixa `Communication`, amb un únic `used_email` per a tots dos, descartant l'email configurat a un dels dos contractes.
    - Arrel: `filter_by_contract`/`filter_by_contract_request`/`filter_by_draft` (`communication/views/manage_communication_process_view.py`) agrupaven contractes/lectures del mateix titular usant només `person.token` com a clau d'agrupació (`group_key`), ignorant `Contract.person_contact_email`. `filter_by_billing` ja incloïa l'email a la clau des d'abans i no es veia afectada.
    - Ara `filter_by_contract`, `filter_by_contract_request` i `filter_by_draft` calculen també `contract.person_contact_email.email` i l'afegeixen a `group_key` (`token|email`), de manera que dos contractes del mateix titular amb emails diferents ja no es fusionen en una única `Communication`. `filter_by_address` i `filter_by_person` (branca `contract`) hereten el fix en delegar a `filter_by_contract`.

#### BILLING (`generate_report_invoice_pdf` — no respectava l'idioma del contracte en regenerar el PDF de factura)

    - En regenerar una factura des de`InvoiceReportPDFDownloadViewSet`, sempre sortia amb la plantilla base (`invoice_template.html`) independentment de l'idioma configurat al contracte, tot i existir la plantilla traduïda corresponent (p. ex. `invoice_template_es.html`).
    - Arrel: `generate_report_invoice_pdf` (`billing/views/invoice_pdf_view.py`) és una implementació duplicada i independent de la generació del PDF de factura, diferent de `billing/utils/invoice_pdf.py::generate()` (que sí resol la plantilla amb `resolve_template_path(..., lang=contract.language)`). Aquí el nom de fitxer estava hardcoded (`'invoice_template.html' if invoice.readings.exists() else 'invoice_request_template.html'`), sense cap referència a l'idioma del contracte.
    - Nou helper `resolve_invoice_template_name()` (`billing/views/invoice_pdf_view.py`), que reaprofita `build_template_candidates()` (`coredata/utils/template_utils.py`) provant `_personalized_{lang}` → `_{lang}` → `_personalized` → la plantilla base, comprovant existència real a `billing/templates/`. `invoice_lang` es calcula ara a partir de `contract.language` (fallback `settings.LANGUAGE_CODE`), mateix criteri que a `invoice_pdf.py`.

## [28-07-2026]

### FEAT
#### BILLING (`CommitmentDepositFilter` — consultar el compromís de dipòsit d'una factura)

    -`CommitmentDeposit.invoices` és un `ManyToManyField` cap a `Invoice` (`related_name='payment_commitments'`), però no hi havia cap manera de filtrar el llistat de `/billing/commitment-deposit/` per factura des del frontend (necessari per mostrar, dins d'`InvoiceRegion`, a quin compromís de dipòsit pertany una factura ja en estat de compromís). Afegit nou filtre `invoice` a `billing/filter/commitment_deposit_filter.py` (`filters.NumberFilter(field_name='invoices__id', lookup_expr='exact')`), mateix patró que el `contract` ja existent al mateix `FilterSet`. Sense migració (no toca el model).

#### BILLING (Retorn manual de factura — data de devolució i estat com SEPA)

    -`PUT /billing/invoice/<id>/pass-to-pending/` (`InvoiceViewSet.pass_to_pending`, `billing/views/invoice_view.py`): nou paràmetre opcional `return_date` (YYYY-MM-DD; per defecte avui) quan es registra una devolució amb `return_reason`.
    - En devolució manual, el pagament passa sempre a **Retornat** (amb `reject`, `reject_date`, `LogPaymentStatusChange` i `PaymentMovement` amb la data triada), sense passar a **Vençut** encara que la factura ja hagi vençut.
    - La factura segueix el mateix criteri que el retorn SEPA (`payment_view.py`): **Confirmada** si `due_date > avui`, **Vençuda** si ja ha vençut.
    - Els fluxos sense motiu de devolució (passar a pendent / vençut) es mantenen com abans.

#### BILLING (Enviaments de factures per email)

    - Nou endpoint`POST billing/invoice-send-email/` (`billing/views/invoice_send_email_view.py`), que accepta la factura a enviar (`invoice_id`) i la companyia (`company_config_id` opcional, per defecte la companyia de la factura).
    - Genera la plantilla d'email amb `create_email_template` (`communication/utils/communication_service.py`) i envia el correu amb `send_electronic_mail` (`communication/utils/communication_service.py`).
    - Adjunta el PDF de la factura a la comunicació.
    - Retorna el resultat de l'enviament.

#### STATISTICS (Nou informe "Liquidació de Fiances INCASOL" — TXT d'amplada fixa)

    - Nou generador`generate_incasol_liquidation_report` (`statistics/utils/report_incasol_liquidation_service.py`), registrat com a `incasol_liquidation_report` a `statistics/tasks.py` (`generator_funcs`), nova vista `ReportIncasolLiquidation` (`statistics/views/reports_views.py`) i ruta `POST billing/incasol-liquidation-report` (`statistics/urls.py`), seguint el mateix contracte asíncron (`task_id` → progrés → `document_id`) que la resta d'informes. Donat d'alta a `AvailableReport` via migració `statistics/migrations/0035_add_incasol_liquidation_report.py` (`function_name='incasol_liquidation_report'`, secció `billing`, botó "Descarregar TXT").
    - Genera un fitxer de text pla d'amplada fixa (no XLSX): una línia de capçalera (58 caràcters: Nº Concert, trimestre, any, nº d'altes/baixes i els seus imports en cèntims amb signe) seguida d'una línia de 403 caràcters per cada moviment de fiança (alta `FI` / baixa `BA`), amb referència de contracte, data, import, adreça desglossada (tipus/nom de carrer, número, escala, pis, porta, codi postal, municipi), NIF i nom del titular. Format deduït d'una mostra real del fitxer oficial d'Incasol.
    - Les fiances "alta" es filtren per `Bail.created_at` dins del `date_range` rebut i les "baixa" per `Bail.return_date`; el filtre opcional de persona/contracte (`person_ids`/`contract_ids`) s'aplica com a restricció addicional sobre `contract_id`.
    - L'identificador de contracte de cada línia de detall es normalitza amb el token base (`re.sub(r'/\d+$', '', token)`, mateixa regex que `_rename_old_contract_and_get_reused_token` a `contract/utils/contract_service.py`), per evitar mostrar el token intern amb sufix `/NNNN` que queda a la fila de `Contract` un cop aquest ha tingut un canvi de nom posterior a la creació de la fiança.
    - Depèn de tres `ConfigProject` nous per tenant (no sembrats per migració, cal donar-los d'alta manualment a cada instal·lació): `incasol_num` (p. ex. `5090`, per compondre `Nº Concert = S{incasol_num}`), `incasol_titular` i `incasol_percentage` (per defecte `90` si no existeix).

#### CONTRACT (Backfill de fiances per contractes existents segons taula de preus històrica)

    - Nou management command`python manage.py backfill_bails_from_price_table` (`contract/management/commands/backfill_bails_from_price_table.py`, `--dry-run`/`--limit`): agrupa tots els `Contract` per token base (traient el sufix `/NNNN` dels canvis de nom) per reconstruir cada contracte físic com una única cadena, calcula la data d'alta original (`registration_date` o `created_at` del membre més antic de la cadena) i li aplica la taula de preus de fiances (0€ abans del 28/06/1988, 6,01€ fins 13/01/1998, 12,02€ fins 31/12/2008, 20€ fins 14/01/2011, 21€ fins 31/12/2016, 0€ des de l'01/01/2017).
    - Crea una única `Bail` per cadena (evitant duplicats si ja n'existeix cap a qualsevol membre), vinculada al contracte "actual" (el que conserva el token base sense sufix, és a dir el titular vigent) amb estat `bail_status_unreturned_token`. Les cadenes amb import 0€ segons la taula no generen fiança. El `created_at` de la fiança es força (via `.update()` posterior al `.create()`, ja que el camp és `auto_now_add`) a la data d'alta original del contracte, no a la data d'execució de l'script.

#### WATCHDOG (Última lectura vs comptador del contracte)

    - Nou check`check_active_contracts_last_reading_meter_mismatch` (`watchdog/services.py`), registrat a `run_all_checks` com a "Contractes Actius: última Lectura amb Meter no vinculat": per cada contracte actiu (`contract_active_token`), agafa l'última `Reading` i comprova que el seu `Meter` estigui vinculat a un `SupplyPoint` del contracte (`Meter → SupplyPoint → Contract.supply_points`). Si el meter no hi està relacionat (o la lectura no en té), reporta `Contract.id`/`token`, `Meter.id`/`code` i dades de la lectura (id, data, valor, `supply_point_id`).

### FIX
#### STATISTICS (Informe "Liquidació de Fiances INCASOL")

    -`cannot import name 'StreetType' from 'contract.models'`: `StreetType` viu a `coredata.models`, no a `contract.models`; corregit l'import a `report_incasol_liquidation_service.py`.
    - L'informe sortia sempre buit: es filtraven primer els `Contract` creats dins del `date_range` i després les fiances vinculades a aquests, però `Contract.created_at` és la data d'inserció real a BD (no la data històrica de la fiança), de manera que mai coincidia amb el trimestre consultat. Ara es filtra directament per les dates pròpies de `Bail` (`created_at` per a altes, `return_date` per a baixes).

#### SERVICE (`save-meter-change` — 500 en assignar comptador a un punt de subministrament sense comptador previ)

    -`_create_meter_reading()` (`service/views/supply_point_view.py`): quan el `SupplyPoint` no tenia cap comptador assignat prèviament (sense `Reading` anterior pel contracte), `contract_prev_reading` és `None`, però el condicional que decideix si cal consolidar la lectura de control anterior accedia directament a `contract_prev_reading.invoices.count()` sense comprovar-ho abans, llançant `AttributeError: 'NoneType' object has no attribute 'invoices'`. Això avortava la petició amb un 500 abans d'arribar a `Reading.objects.create(...)`: el comptador nou (`supply_point.meter`) quedava assignat, però la lectura (`new_reading`) mai es creava. Afegida la comprovació `contract_prev_reading and ...` al condicional.

## [27-07-2026]

### FIX
#### GENERAL (Exportació XLSX/CSV genèrica — patró `{entity}/export/` unificat per a tot el backend)

    - Nova infraestructura compartida a`importexport/utils/` (`export_registry.py`, `generic_export_service.py`, `permissions.py`) i `importexport/views/generic_export_view.py`: un únic contracte per a qualsevol entitat, `POST {app}/{entity}/export/` → `202 {task_id}` → `GET /task-progress/{task_id}/` → `result: {document_id, document_name}`. Cada entitat només aporta una `ExportConfig` (queryset, `FilterSet` ja existent, columnes disponibles).
    - `export_permission_class()` exigeix `view_<model>` en lloc de `add_<model>` (el que exigiria `DjangoModelPermissions` en un `POST`), per no bloquejar rols de només lectura. Aplicat també a `Communication` (migrat de `GET export/csv` a `POST export`).
    - 41 endpoints `{entity}/export/` implementats seguint aquest patró (Auth: group/user; Billing: invoice/biller/billing/commitment-deposit/invoice-template/joined-payment/message/payment/reading-batch/reading-batch-template/payment-remittance/payment-remittance-return; Claimrequest; Verifactu; Communication: communication/communication-process/message-template; Contract: bail/contract-request/contract-termination-request; Coredata: person/street; Order: order/order-type; Pricing: billing-range/line-item-type/price-rate/product; Service: supply-point/property/meter/cluster/connection/connection-request/exploitation), cada ruta muntada abans d'`include(router.urls)` per no col·lidir amb el `pk` del router.
    - `Reading` (`export-readings`) migrat de síncron (`{"file_url"}`) a asíncron amb el mateix contracte; `ReadingBatch.download` ara puja el document via `upload_document` en lloc de `default_storage`.
    - Bug corregit al servei compartit: `build_export_csv_bytes()` petava amb `prefetch_related` per manca de `chunk_size` a `iterator()`.
    - Pendents (no implementats): `contract/consumption-management/export/` (ViewSet sense queryset/FilterSet) i `service/supply-point-request/export/` (model ja no existeix).

#### BILLING (Plantilla SEPA — titular del deutor)

    -`coredata/templates/sepa_template.html`: el nom i NIF/NIE del deutor passen a mostrar `person_fullname` i `person_token` (dades del `PersonBank` seleccionat) en lloc de `holder.full_name` i `holder.token`, perquè el PDF reflecteixi el titular del compte bancari i no el titular del contracte/sol·licitud quan són persones diferents.

#### BILLING (`Reading` — índex per a la cerca de "lectura anterior" durant la facturació)

    - Auditoria del pipeline de facturació (`billing/tasks.py`, `billing/utils/invoice_service.py::generate_consumption_invoice_multiple`, `billing/utils/invoice_line_item_service.py`) buscant el mateix patró que l'ordenació per deute. La resta de punts revisats ja seguien un patró correcte (agregats en bloc com `avg_total_cache`/`bc_aggs`/`inv_aggs`) o tenen un volum massa petit per justificar cap canvi (`BillingRange`/`ContractPriceRate`, 57 files); no s'ha trobat cap cas addicional on calgui una `VIEW` nova (el guany de `vw_contract_debt` ve de compartir un mateix agregat entre molts contractes, cosa que aquí no passa: cada lectura és una fila única).
    - Sí s'ha trobat un problema real: la cerca de la "lectura anterior" (`Reading.objects.filter(supply_point=..., meter=..., contract=..., reading_date__lt=..., is_control=False).order_by('-reading_date').first()`, cridada per cada lectura x tarifa dins del lot de facturació) feia sempre `Seq Scan` sobre `billing_reading` (~1M files, ~150ms per crida) perquè no hi havia cap índex compost, només el de la PK.
    - Nous índexs a `Reading` (`billing/models.py`, migració `billing/migrations/0306_reading_reading_prev_contract_idx_and_more.py`): `reading_prev_contract_idx` (`supply_point, meter, contract, -reading_date`) i `reading_prev_no_contract_idx` (`supply_point, meter, -reading_date`, pel fallback sense contracte). Creats amb `CREATE INDEX CONCURRENTLY` (migració `atomic=False` + `SeparateDatabaseAndState`) per no bloquejar escriptures durant el desplegament, donat el volum de la taula.

#### COREDATA (`Bank` — codis SWIFT/BIC incorrectes o truncats a la llista de bancs)

    - Detectat que`Bank.bic` (`coredata/models.py`) conté sistemàticament el BIC truncat a només els 4 primers caràcters (codi d'institució, p. ex. `DEUTSCHE BANK, S.A.E.` amb `bic='DEUT'` en lloc de `DEUTESBB`) i, en un subconjunt de registres, un valor directament incorrecte (p. ex. token `96` "PROBANCA SERVICIOS FINANCIEROS" amb `bic='BBVA'` en lloc de `PROAESMM`). Confirmat que l'endpoint `GET /coredata/bank/get-swift/?iban_prefix=...` no llegeix d'aquesta taula (calcula el BIC amb la llibreria `schwifty` a partir del prefix IBAN, i per tant ja retorna el valor correcte); l'error només afecta el llistat de bancs servit per `BankViewSet` (camp `bic`), d'on el consumeix el front.
    - Nou management command `python manage.py fix_bank_bic` (`coredata/management/commands/fix_bank_bic.py`): creua `Bank.token` (zero-paddejat a 4 dígits) amb el registre BIC oficial ES de `schwifty` i mostra/aplica la correcció de `bic`. Per defecte fa `--dry-run` (només informa); `--apply` escriu els canvis; `--fill-empty-only` limita l'actualització als bancs amb `bic` buit sense tocar els que ja en tenen un valor.
    - Arrel del problema: `prometeo/banks.py` (script que genera la fixture `prometeo/data/banks.json` a partir de `prometeo/banks.csv`, carregada via `loaddata prometeo/data/*.json` a `prometeo/reset_db.sh`) copiava directament la columna `Bic` del CSV, que ja porta el BIC truncat a 4 caràcters o, en alguns casos, un valor erroni. Ara `make_json()` creua `Token` (zero-paddejat a 4 dígits) amb el mateix registre BIC oficial ES de `schwifty`; si hi ha correspondència, substitueix el `Bic` del CSV pel BIC oficial complet, evitant que el problema es reintrodueixi en cada importació/reset de demo. Si el token no té entrada al registre (entitat absorbida/inexistent), es manté el valor del CSV com a fallback. Regenerat `prometeo/data/banks.json` amb el fix aplicat (365 dels 561 bancs corregits).

#### CONTRACT (Ordenació per deute — de subquery correlacionat a JOIN normal contra `vw_contract_debt`)

    -`statistics/migrations/0033_create_vw_contract_debt.py`: revertida (altre cop) a `VIEW` normal — es va provar de tornar-la `MATERIALIZED VIEW` amb índex únic per tenir un `Index Scan` real, però requeria refrescar-la (Celery/manual) i s'ha descartat per mantenir-la sempre actualitzada sense cap procés de refresc. Eliminats en conseqüència `billing/tasks.py::refresh_contract_debt_view_task` (tasca Celery amb `REFRESH MATERIALIZED VIEW CONCURRENTLY`), `billing/signals.py::refresh_contract_debt_view_on_invoice_change` (signal que la disparava en crear/pagar/anul·lar factures) i el comandament `contract/management/commands/refresh_contract_debt_view.py`, tots ja innecessaris amb una vista normal.
    - Nou camp `Contract.debt_view` (`contract/models.py`): `ForeignKey` a `ContractDebtView` reaprofitant la columna `token` ja existent (`db_column='token'`, `db_constraint=False`, `editable=False`, `on_delete=DO_NOTHING`), afegit només a l'estat de Django via `SeparateDatabaseAndState` (`contract/migrations/0232_contract_debt_view_relation.py`, no toca la BD ja que la columna ja existeix). `Contract.check()` silencia expressament `models.E007` (columna compartida entre `token` i `debt_view`) només per aquest model, ja que és intencional.
    - `annotate_contract_list_debt_amount` ara fa `select_related('debt_view')` en lloc del `Subquery`, generant un `LEFT OUTER JOIN "vw_contract_debt" ON (token = contract_token)` normal (un únic `Hash Left Join`, com qualsevol altra relació de l'aplicatiu).

### FEAT
#### STATISTICS (`GET /statistics/summary-consumption-by-use` i `GET /statistics/summary-billing-by-use` — filtres `active`/`is_billable`)

    - Tots dos endpoints (`ConsumptionSummaryByUseType`/`BillingSummaryByUseType`, `statistics/views/summary_statistics_view.py`) accepten ara els paràmetres opcionals `active` i `is_billable` (booleans, `?active=true&is_billable=true`), que filtren els contractes agregats a cada resum (tant el desglossat per `ContractUseType` com els totals globals) per `Contract.is_active` i pel mateix criteri de "facturable" ja usat a la resta de l'aplicació (`Contract.block_billing=False`).
    - Si no s'envia cap dels dos paràmetres, es manté exactament el comportament actual (sense filtrar el desglossat; el total de contractes global continua limitat a `is_active=True` com fins ara). Nous helpers `_parse_bool_param()`/`_contract_filter_q()`.

#### WATCHDOG (Pagaments i abonaments)

    - Nou check`check_payments_without_movements` (`watchdog/services.py`), registrat com a "Pagaments sense Moviments": detecta pagaments actius en estat Pagat, Retornat o En saldo (`payment_status_piggy_token`) sense cap `PaymentMovement` actiu.
    - Nou check `check_payoff_invoices_missing_negative_balance_movement`, registrat com a "Abonaments sense Moviment de Pagament Negatiu": si la factura abonada té un pagament amb moviment de saldo positiu (`PiggyBankMovement` / `PersonPiggyBankMovement`) i la factura d'abonament no té `PaymentMovement` negatiu al seu pagament, ho reporta.

## [26-07-2026]

### FEAT
#### BILLING (Fan-out de lectures de comptador general a facturació)

    -**Problema**: la captura de lectures crea **una sola** `Reading` per comptador (sovint amb `contract`/`supply_point` null). La facturació, en canvi, només processa lectures amb `contract` omplert i agrupa per contracte. Resultat: un `Meter.is_general=True` compartit per N punts de subministrament no generava factura a cap contracte (o només a un, si la lectura ja duia contracte), tot i que la divisió de consum (`consum / nº SupplyPoint actius`) ja existia a `recalc_consumption_general_meter_no_submeters`.
    - **Solució**: es manté **1 lectura física** a la captura i, en facturar, es fa un *fan-out* a N lectures fill (`copied_from` = canònica), una per cada parell `(supply_point, contract)` actiu del meter general **sense subcomptadors**. Les còpies conserven el `calculated_value` total (p.ex. 500); la factura continua dividint amb la lògica existent.
    - Els contractes amb `block_billing=True` (no facturables) s’exclouen del fan-out i del divisor del consum (`count_general_meter_billable_targets` / `_get_general_meter_fanout_targets`): només compten destins amb contracte actiu i `block_billing=False`.
    - Nou helper `fanout_general_meter_readings()` / `find_canonical_general_meter_reading()` a `billing/utils/reading_service.py` (idempotent; no duplica si ja existeix còpia per `billing+meter+contract`; ignora lectures que només són `previous_reading` d’una altra del mateix billing).
    - Cablejat abans de generar factures a `process_billing_batch`, `process_selected_contracts_task` (`billing/tasks.py`) i `BillingViewSet.process_contract` (`billing/views/billing_view.py`).
    - Assignació al lot/billing: `BillingPreInvoicesAssignReadingsViewSet` i `assign_readings_task` també accepten la lectura canònica del meter general (per `meter`, no només per `supply_point`/`contract`), perquè arribi al billing i el fan-out tingui què expandir.
    - Tests: `billing/tests/test_general_meter_fanout.py` (fan-out, idempotència, exclusió `block_billing`, comptadors del lot amb `copied_from__isnull=True`, 3 factures amb consum dividit).
    - Documentació del comportament: `docs/meter_general.md`.

## [24-07-2026]

### FEAT
#### SUPPLY POINT

    - Mostrar el deute dels contractes al punt de subm.

#### WATCHDOG

    - Nou check`check_incidents_exist` (`watchdog/services.py`), registrat a `run_all_checks` com a "Incidències a la BD": si no existeix cap `Incident`, mostra el missatge "No hi ha cap incidència a la base de dades"; si n'hi ha, el check passa OK.
    - Nou check `check_invoices_without_contract_or_person` (`watchdog/services.py`), registrat a `run_all_checks` com a "Factures sense Contracte o Persona": detecta factures actives amb `serie_final` (numerades) sense `person`. Exclou pressupostos (`serie_final` que comença per `P`). Si també falta el contracte, ho indica; si en té, mostra el token del contracte.
    - Nou check `check_invoice_sequence_sync` (`watchdog/services.py`), registrat com a "InvoiceSequence desfasada (serie_final)": compara `InvoiceSequence.last_number` amb el màxim numèric ja assignat a `Invoice.serie_final` per al mateix prefix (p. ex. `FC/1826`). Si el comptador queda per sota, avisa (evita `IntegrityError` de duplicate `serie_final` en confirmar factures). Fix: `python manage.py watchdog_fix_invoice_sequences` (`--dry-run`, `--prefix FC/1826`).

#### BILLING

    -`ContractSepaPDFView` (`billing/views/contract_sepa_pdf_view.py`) accepta ara `bank_id`/`person_bank_id` al body: si s'informa i correspon a un `PersonBank` existent, es genera el document amb aquest compte (IBAN/SWIFT/nom/DNI) en lloc del compte per defecte del pagament del contracte (`contract.payment.IBAN`); si no s'envia, o l'id no existeix, es manté el comportament actual (fallback al compte per defecte). Nou helper `_resolve_person_bank()`.
    - De pas, `iban`/`swift` (fins ara sempre placeholders fixos `" - "`, ja que l'helper `_iban_and_swift()` estava definit però no s'arribava a cridar mai) ara es calculen realment a partir del compte bancari resolt (per defecte o triat), imprescindible perquè seleccionar un compte diferent tingui cap efecte visible al PDF.
    - `SepaPDFDownloadViewSet` (`billing/views/sepa_pdf_view.py`) accepta ara `bank_id`/`person_bank_id` al body: si s'informa i correspon a un `PersonBank` existent, substitueix el compte ja persistit al `GeneralPayment` (`general_payment.IBAN`, o el de `contract_request.payment` si aplica) per generar el document (IBAN/SWIFT/`person_fullname`/`person_token`); si no s'envia, o l'id no existeix, es manté el comportament actual (el compte ja guardat).
    - Nou model `InvoiceCategory` (`billing/models.py`, migració `billing/migrations/0304_invoicecategory_invoice_category.py`, només schema — sense sembrar dades) i camp `Invoice.category` (FK, `null=True`/`blank=True`). CRUD via `InvoiceCategoryViewSet` (`billing/views/invoice_category_view.py`, registrat a `/invoice-category/`, calcat d'`InvoiceTypeViewSet`), amb `update-positions`/`update-default`. No es sembra cap fila per defecte: cal crear-les manualment (via l'endpoint) només a les instal·lacions on calgui, amb els tokens que reconeix `generate_serie_final_personalized.py` (`consum`, `pressupost`, `canvi_nom`, `alta`, `alta_escomesa`, `reconnexio`, `contra_incendis`, `recarrec`).
    - `billing/utils/generate_serie_final_personalized.py` (`get_category_digit`): quan `invoice.category` té token, el dígit de la sèrie final surt directament d'una taula `CATEGORY_TOKEN_TO_DIGIT` (`token → (dígit AV, dígit MV)`), permetent per primer cop generar explícitament les categories "Reconnexió" (AV=4/MV=8) i "Alta d'escomesa", que fins ara sempre queien al valor per defecte (Consum). Si `invoice.category` és `None` (fluxos automàtics existents: lectures massives, terminacions de contracte, pressupostos estàndard), es manté l'heurística anterior sense cap regressió. El dígit ja no és una taula fixa al codi (`CATEGORY_TOKEN_TO_DIGIT`, eliminada), sinó configurable per categoria: nous camps `InvoiceCategory.serie_digit_av`/`serie_digit_mv` (migració `billing/migrations/0305_invoicecategory_serie_digit_av_and_more.py`, editables via `/invoice-category/`, com qualsevol altre camp del CRUD). `get_category_digit()` només aplica aquest dígit configurat a factures normals (`is_budget=False`) i quan la categoria té el camp corresponent informat; un pressupost (`is_budget=True`) manté sempre la seva pròpia lògica de dígit encara que tingui una `category` assignada, i si el camp no està configurat es manté l'heurística de fallback com fins ara.
    - Nou camp `Exploitation.companies` (M2M a `Company`, `service/models.py`, migració `service/migrations/0116_exploitation_companies.py` amb backfill automàtic de l'empresa actual de cada explotació). `Exploitation.company` es manté com a empresa per defecte. Exposat a `ExploitationSerializer` (`service/serializers/exploitation_serializer.py`).
    - Nou helper `resolve_selected_company()` (`billing/utils/invoice_service.py`): valida que l'empresa triada per l'usuari pertany a `exploitation.companies` abans d'assignar-la a la factura; si no, cau a l'empresa per defecte. Cablejat a `invoice_contract_generate`/`generate_empty_invoice` (nous paràmetres opcionals `company_id`/`category_id`), i a les vistes `GenerateInvoiceBudgetView` (`billing/views/generate_invoice_budget_view.py`, `payment_data.company_id`/`category_id` i `selected_custom.company`/`category`) i `InvoiceContractGenerateView` (`billing/views/invoice_contract_generate_view.py`, `company_id`/`category_id` al body). Aplicable als fluxos de factura Personalitzada, Alta, Alta d'escomesa i Pressupost de baixa.

#### BILLING (Categories de factura més enllà de "Personalitzat"/"Lectures" + selecció d'empresa per explotació)

    - Nou model`InvoiceCategory` (`billing/models.py`, migració `billing/migrations/0304_invoicecategory_invoice_category.py`, només schema — sense sembrar dades) i camp `Invoice.category` (FK, `null=True`/`blank=True`). CRUD via `InvoiceCategoryViewSet` (`billing/views/invoice_category_view.py`, registrat a `/invoice-category/`, calcat d'`InvoiceTypeViewSet`), amb `update-positions`/`update-default`. No es sembra cap fila per defecte: cal crear-les manualment (via l'endpoint) només a les instal·lacions on calgui, amb els tokens que reconeix `generate_serie_final_personalized.py` (`consum`, `pressupost`, `canvi_nom`, `alta`, `alta_escomesa`, `reconnexio`, `contra_incendis`, `recarrec`).
    - `billing/utils/generate_serie_final_personalized.py` (`get_category_digit`): quan `invoice.category` té token, el dígit de la sèrie final surt directament d'una taula `CATEGORY_TOKEN_TO_DIGIT` (`token → (dígit AV, dígit MV)`), permetent per primer cop generar explícitament les categories "Reconnexió" (AV=4/MV=8) i "Alta d'escomesa", que fins ara sempre queien al valor per defecte (Consum). Si `invoice.category` és `None` (fluxos automàtics existents: lectures massives, terminacions de contracte, pressupostos estàndard), es manté l'heurística anterior sense cap regressió. El dígit ja no és una taula fixa al codi (`CATEGORY_TOKEN_TO_DIGIT`, eliminada), sinó configurable per categoria: nous camps `InvoiceCategory.serie_digit_av`/`serie_digit_mv` (migració `billing/migrations/0305_invoicecategory_serie_digit_av_and_more.py`, editables via `/invoice-category/`, com qualsevol altre camp del CRUD). `get_category_digit()` només aplica aquest dígit configurat a factures normals (`is_budget=False`) i quan la categoria té el camp corresponent informat; un pressupost (`is_budget=True`) manté sempre la seva pròpia lògica de dígit encara que tingui una `category` assignada, i si el camp no està configurat es manté l'heurística de fallback com fins ara.
    - Nou camp `Exploitation.companies` (M2M a `Company`, `service/models.py`, migració `service/migrations/0116_exploitation_companies.py` amb backfill automàtic de l'empresa actual de cada explotació). `Exploitation.company` es manté com a empresa per defecte. Exposat a `ExploitationSerializer` (`service/serializers/exploitation_serializer.py`).
    - Nou helper `resolve_selected_company()` (`billing/utils/invoice_service.py`): valida que l'empresa triada per l'usuari pertany a `exploitation.companies` abans d'assignar-la a la factura; si no, cau a l'empresa per defecte. Cablejat a `invoice_contract_generate`/`generate_empty_invoice` (nous paràmetres opcionals `company_id`/`category_id`), i a les vistes `GenerateInvoiceBudgetView` (`billing/views/generate_invoice_budget_view.py`, `payment_data.company_id`/`category_id` i `selected_custom.company`/`category`) i `InvoiceContractGenerateView` (`billing/views/invoice_contract_generate_view.py`, `company_id`/`category_id` al body). Aplicable als fluxos de factura Personalitzada, Alta, Alta d'escomesa i Pressupost de baixa.

#### STATISTICS (Filtres aplicats visibles a la cua d'informes i a l'informe finalitzat)

    -`ReportQueue.payload` (`statistics/models.py`) ja desava el payload complet rebut a `POST /statistics/available-reports/<id>/trigger/`, però `GET /statistics/report-queue/` i `GET /statistics/report-queue/<id>/` no el retornaven (`ReportQueueListView`/`ReportQueueStatusView`, `statistics/views/available_report_view.py`, són `APIView` amb diccionaris construïts a mà). Ara tots dos exposen `filters` (el `payload` cru) i el nou `filters_display`.
    - Nou `filters_display` (JSONField) a `ReportQueue`, i nous `filters`/`filters_display` (JSONField) a `GeneralReport` (l'"informe finalitzat" de `GET /statistics/general-report/`; migració `statistics/migrations/0034_generalreport_filters_generalreport_filters_display_and_more.py`). `GeneralReportSerializer` ja usa `fields='__all__'`, així que els exposa sense cap canvi addicional.
    - Nova funció `resolve_filter_labels(payload)` (`statistics/utils/report_filters.py`): converteix el payload cru (`date_range`/`start_date`/`end_date`, `exploitation_id`, `billing_id(s)`, `remittance_id(s)`, `person_ids`, `contract_ids`, `report_type_id`, `product_ids`, `taxes_ids`, `payment_type_ids`, `include_preinvoices`, `include_tax_free_lines`, `model_347_year`/`year`, `version`, `account_type`/`accounting_type`) en una llista `[{label, value}]` amb noms/tokens resolts (no ids crus), perquè el frontend no hagi de fer cap crida addicional per mostrar els filtres aplicats. Calculat a `AvailableReportViewSet.trigger()` en crear l'item de cua.
    - Com que `GeneralReport` i `ReportQueue` no tenen cap FK entre ells (només comparteixen el mateix `document_id` un cop generat l'informe, via `save_report()` a `statistics/views/reports_views.py`), `run_report_task` (`statistics/tasks.py`) copia `filters`/`filters_display` del `ReportQueue` al `GeneralReport` corresponent en finalitzar amb èxit (`GeneralReport.objects.filter(document_id=document_id).update(...)`), sense recalcular-los ni tocar cap dels ~30 generadors d'informes existents.

#### STATISTICS (Informe invoice-reading-summary — columnes NoFacturable / Comptador)

    - L'export`POST /statistics/contracts/invoice-reading-summary/export/` (`contract/utils/contract_invoice_reading_summary_export.py`) afegeix les columnes `NoFacturable` (`Contract.block_billing`), `Comptador` (`supply_point_default.meter.code`, abans "Codi comptador"), `ComptadorGeneral` (`Meter.is_general`) i `ComptadorPare` (`Meter.meter_general.code`). Actualitzada també la vista de referència `docs/sql/vw_contract_invoice_reading_summary.sql`.

### MODIFIED
#### BILLING

    - S'ha canviat el nom de 'Anul·lat' a 'Abonat' per ser més proper a l'acció real
    - billing>utils>invoice_line_item_service.py`create_from_lineitemtype`, les unitats sempre es fa un arrodoniment abans de calcular el preu de la línia per evitar tenir unitats amb més de dos decimals

### FIX
#### BILLING (SEPA — l'IBAN/SWIFT tornava a agafar el compte personal del titular en lloc del vinculat al contracte)

    -`SepaPDFDownloadViewSet` (`billing/views/sepa_pdf_view.py`): el fix del 22-07-2026 va introduir que, si el titular tenia algun `PersonBank` amb `is_default=True`, aquest substituïa `general_payment.IBAN` (el compte vinculat al contracte) a l'hora de generar el PDF. Això feia que el document mostrés l'IBAN/SWIFT del compte personal "actual" del titular, encara que no fos el que realment té associat el contracte (p. ex. si el titular té diversos comptes i en marca un altre com a per defecte per a altres usos). Eliminat aquest bloc: `personBank` torna a ser sempre `general_payment.IBAN` (el pagament vinculat al contracte). `person_fullname`/`person_token` (mostrats al PDF) mantenen exactament la mateixa fórmula de fallback que fins ara (`personBank.name`/`.dni` si n'hi ha, si no `holder.full_name`/`.token`) — només canvia la font de `personBank`, no la lògica de com es mostra el nom.
    - Mateixa vista: el "titular" (`holder`/`holder_person`, usat per a nom/adreça del deutor quan no hi ha `person_id` explícit a la petició) sempre es prenia de `contract_request.holder`, encara que el `GeneralPayment` (`payment_id`) del contracte tingués un IBAN vinculat a una persona diferent (detectat al contracte 9732: `Contract.payment_id` amb un `PersonBank` d'una altra persona que el `holder`). Ara, si `general_payment.IBAN.person` existeix, aquesta persona té prioritat sobre `contract_request.holder` per determinar el titular a mostrar; si el pagament no té cap persona vinculada, es manté el comportament anterior (`contract_request.holder`).
    - Mateixa vista: `general_payment` (i per tant `PersonBank`/IBAN) es resolia únicament a partir de l'`id` rebut a la URL (`/sepa/download/<id>/`), sense verificar que coincidís amb el pagament realment vinculat al contracte/sol·licitud. Ara, un cop resolt `contract_request` (`Contract` o `ContractRequest` segons `value`), si aquest té `payment` informat, es fa servir sempre aquest (`contract_request.payment`) en lloc del rebut per URL — l'`id` de la URL només actua com a fallback si el contracte no té cap `payment` vinculat. Això garanteix que el `PersonBank` mostrat i el `GeneralPaymentSepaDocument` generat corresponguin sempre al pagament real del contracte, encara que el crider passi un `id` desactualitzat.
    - `coredata/templates/sepa_template.html` i `billing/templates/sepa_template.html`: "Nom del deutor" i "NIF-NIE del deutor" imprimien `{{ holder.full_name }}`/`{{ holder.token }}` (el nom/token de la `Person` vinculada, `PersonBank.person`), ignorant les variables `person_fullname`/`person_token` que les vistes (`sepa_pdf_view.py`, `contract_sepa_pdf_view.py`) ja calculaven amb la prioritat correcta (`PersonBank.name`/`.dni` si n'hi ha, si no `holder`). Ara els dos templates imprimeixen `{{ person_fullname }}`/`{{ person_token }}`, que ja prioritzen el nom/DNI propis del compte bancari.

#### CONTRACT (Ordenació per deute — encara lenta amb la vista `vw_contract_debt`)

    -`statistics/migrations/0033_create_vw_contract_debt.py`: la vista `vw_contract_debt` (deute per contracte, mateixa definició que `ContractSerializer.get_debt_amount`) es va crear com a `VIEW` normal. Comprovat amb `EXPLAIN ANALYZE` que això no resolia la lentitud en ordenar contractes per deute: una vista normal no precalcula res, Postgres n'infla la definició a cada consulta, de manera que un `Subquery` correlacionat hi torna a recalcular tota l'agregació `SUM`/`JOIN` per cada contracte (cost estimat ~11,5 mil milions).
    - Descartada l'alternativa amb `MATERIALIZED VIEW` (Index Scan immediat, però requeria refrescar-la manualment/via signal, amb risc de dades desactualitzades i de disparar-se centenars de cops en un lot de facturació). Es manté `vw_contract_debt` com a `VIEW` normal (sempre actualitzada, sense cap procés de refresc) i s'afegeix un `CREATE INDEX` sobre `contract_contract(token)` — l'únic camp de la consulta sense índex, ja que els FK (`contract_id`, `invoice_id`, `status_id`) ja en porten un automàticament per Django — per accelerar el lookup a la vista subjacent.
    - `contract/models.py` (`ContractDebtView`, `managed=False`, `db_table='vw_contract_debt'`), `contract/utils/contract_list_queryset.py` (`annotate_contract_list_debt_amount`) i `ContractSerializer.get_debt_amount` (`contract/serializers/contract_serializer.py`) llegeixen d'aquesta vista en lloc de recalcular l'agregació amb `Payment.objects.filter(...)`/`Subquery` correlacionat directe sobre `billing_payment`.

## [23-07-2026]

### FIX
#### SERVICE (epayment_document_generate_view.py -> `generate_xml`)

    - Si el total de cada línia no dona EXACTE al multiplicar les unitats amb el preu unitari, afegim un preu unitari modificat per passar validacions. Exemple: unitats 2.03, preu unitari 10 i preu final 20.33. Al treballar les unitats a 2.0333... però guardar 2.03, el total té 3 cèntims més i no quadra, de manera que farem que el preu unitari a declarar sigui 10.0148.

#### BILLING (`invoice_return_charge` — senyal per identificar recàrrecs de retorn a `generate_serie_final`)

    -`invoice_return_charge()` (`billing/utils/invoice_service.py`): abans de confirmar la factura de recàrrec (`confirm_invoice(surcharge)`), es marca la instància amb un atribut transitori (no persistit) `surcharge._is_return_surcharge = True`. Això permet que una implementació personalitzada de `generate_serie_final` (via `billing/utils/generate_serie_final_personalized.py`) pugui distingir aquestes factures de recàrrec de retorn de la resta i assignar-los una sèrie pròpia, sense necessitat d'inspeccionar `title`/`token`/`reject`, camps que no són prou fiables per a aquesta detecció.

#### SERVICE (`Meter` — el número i sufix de l'adreça es guardaven bé però es mostrava "S/N")

    -`MeterSerializer.create()` (`service/serializers/meter_serializer.py`): en crear un comptador nou reutilitzant un `StreetNumber` ja existent (`street_number_id`, p. ex. l'adreça original del punt de subministrament, sense número), el mètode només llegia una clau `type` que mai arriba al payload real (el camp és `number_type_type`, segons com el serialitza `StreetNumberSerializer` a `coredata/serializers.py`). Com a conseqüència, `number`/`number_suffix` s'actualitzaven correctament a BD però `number_type` sempre queia al valor per defecte (`ConfigProject('address_street_no_number_type_token')` = "SN"), fent que l'adreça es mostrés com "C. DEL BARATO, S/N" en lloc de "C. DEL BARATO, 20 A". `update()` ja tenia la cadena de fallback correcta (`type` → `number_type` (dict) → `number_type_type` → per defecte); ara `create()` fa el mateix.

### FEAT
#### SERVICE (Update massiva de Meter — preview + confirm)

    - Nous endpoints`POST /service/meter/bulk-update/preview/` i `POST /service/meter/bulk-update/confirm/` (`MeterViewSet`): pujada multipart de CSV/Excel (1a columna = `meter.code`, resta = camps a actualitzar). El preview no escriu a BD i retorna `updates` (canvis old/new), `unchanged`, `not_found` i `errors`; el confirm torna a pujar el mateix fitxer i aplica només les files vàlides (parcial). Cel·les buides no toquen el camp. Si un `code` es repeteix al fitxer, el processament és seqüencial (preview alineat amb confirm) i es retorna `duplicate_codes_in_file`.
    - Camps actualitzables: escalars principals (`code2`, booleans operatius, manufacturer/model, dates, digits, lat/long, remote reading…) + `status`/`caliber` per token o name. Sense `is_active` (baixa lògica), adreces ni `meter_general`; no crea comptadors nous. Lògica a `service/utils/meter_bulk_update_service.py`. Permís `service.change_meter`. Doc: `docs/meter-bulk-update.md`.

#### BILLING (Mostrar tots els trams de consum a la factura, encara que no tinguin consum)

    - Nou`ConfigProject` (token `SHOW_ALL_CONSUMPTION_TRAMS`, per defecte `'false'`, migració `coredata/migrations/0118_add_show_all_consumption_trams_config.py`) i helper `should_show_all_consumption_trams()` (`coredata/utils/invoice_tram_config.py`).
    - `create_from_lineitemtype` (`billing/utils/invoice_line_item_service.py`, branca `line_item_type.price_interval`): fins ara, un cop exhaurit el consum d'un tram, el bucle tallava (`break`) i com a molt es mostrava un únic tram addicional sense consum (via `LineItemType.always_show`, i només en un cas vora impossible d'assolir: `previous_stretch_end <= 0`). Amb el nou flag actiu, el bucle ja no talla: continua generant una `InvoiceLineItem` amb `units=0` per a cada tram restant de la tarifa, perquè el client pugui veure tots els trams (amb o sense consum) a la factura.

#### CONTRACT / BILLING (Facturar període complert a una alta)

    - Nou camp`bill_full_period` (booleà, per defecte `False`) a `Contract` i `ContractRequest` (migració `contract/migrations/0230_contract_bill_full_period_and_more.py`), verbose name "Facturar Període Complert". `contract_create()` (`contract/utils/contract_service.py`) el copia de la `ContractRequest` al `Contract` en finalitzar l'alta.
    - `create_from_lineitemtype` (`billing/utils/invoice_line_item_service.py`): quan el contracte té `bill_full_period=True`, es força `is_first_invoice=False` encara que la detecció habitual (sense lectura anterior, `is_initial`, `is_close`, canvi de contracte, etc.) l'hagués marcat com a primera factura. Efecte: als conceptes amb `active_choice='DAYS'`, la primera factura de l'alta ja no es prorrateja per dies consumits i es factura el període complert des del primer dia.

## [22-07-2026]

### FEAT
#### IMPORTEXPORT (`import_contracts_tokens` — IdentSEPA)

    - L'import`python manage.py import_contracts_tokens` mapa la columna CSV `IdentSEPA` al camp `Contract.mandate_id` (`importexport/utils/contracts_tokens_service.py`). Si la columna arriba buida, es desa `None`.

### FIX
#### CONTRACT (Filtre i ordenació per deute al llistat)

    -`GET /contract/contract/` (`ContractFilter`, `contract/filters/contract_filter.py`): nou filtre `has_debt` (`true`/`false` o `1`/`0`) que deixa només els contractes amb (o sense) deute, amb el mateix criteri que `debt_amount` del llistat: suma d'`amount` dels `Payment` en estats de deute (vençut/retornat/irrecuperable/dotació) o pendents amb factura confirmada, via `_contract_debt_status_context()`.
    - Ordenació per `debt_amount` / `-debt_amount` (`ContractOrderingFilter` a `contract/views/contract_view.py`): anota el queryset només quan es demana aquesta ordenació (`annotate_contract_list_debt_amount` a `contract/utils/contract_list_queryset.py`), per no penalitzar el llistat normal.

#### BILLING

    -`update_payment` (`billing/signals.py`): el fix del 16-07-2026 que marcava la factura "Pagada" per import cobrat també recalculava `left_to_pay` a cada pagament (`manual_payment`, remeses, etc.), deixant-lo a `0` quan la factura quedava liquidada. `left_to_pay` només s'ha de definir a la creació/confirmació de la factura: igual a `total_final`, o `total_final` menys saldo/moneder quan es generen 2 payments (un de BALANCE i un del pendent). Ara el signal manté la lògica d'estat "Pagada" per suma d'`amount` dels payments pagats/moneder vs `total_final`, però **ja no modifica** `left_to_pay`. Alineat també a `fix_sent_remittance_effects`.
    - `BankRNDDocumentView._match_invoice_by_barcode_contract()` (`billing/views/bank_rnd_view.py`): la referència dels pagaments per taquilla/correus del fitxer de retorns bancaris no porta el `token` de factura amb el prefix `01`/`02`/`03`/`05` que la branca principal espera, així que sempre queia en aquest mètode de reserva (que reconstrueix el contracte a partir de la referència del codi de barres). Aquest mètode filtrava les factures candidates només per l'estat "Confirmada" (`InvoiceStatus.token=2`), excloent les factures ja en estat "Enviada" (`3`) o "Vençuda" (`-1`) — l'estat habitual d'una factura quan el client la paga per aquest canal —, de manera que el pagament mai es vinculava. Ara el filtre accepta els tres estats (`Confirmada`, `Enviada`, `Vençuda`).
    - `POST /billing/sepa/download/<id>/` (`SepaPDFDownloadViewSet`, `billing/views/sepa_pdf_view.py`): els camps "Nom del deutor" i "NIF-NIE del deutor" del PDF (`billing/templates/sepa_template.html`, `coredata/templates/sepa_template.html`) mostraven `holder.full_name`/`holder.token` (el titular del contracte) en lloc del titular del compte bancari/IBAN. Ara mostren `person_fullname`/`person_token`, ja calculats a la vista prioritzant `personBank.name`/`personBank.dni` sobre el titular del contracte.
    - La mateixa vista resolia el compte bancari del deutor únicament a partir de `general_payment.IBAN`, un `ForeignKey` fix que no s'actualitza en marcar un altre `PersonBank` com a per defecte. Ara, si el titular té algun `PersonBank` amb `is_default=True`, aquest substitueix `general_payment.IBAN` a l'hora de generar el PDF, de manera que el document sempre reflecteix el compte marcat com a actual.

#### COREDATA (`PersonBank` — `is_default` no desmarcava la resta de comptes)

    -`PersonBankSaveSerializer.update()` i `PersonBankSerializer.update()` (`coredata/serializers.py`): en marcar un `PersonBank` com a per defecte (`PATCH /coredata/person-bank/<id>/` amb `is_default: true`), no es desmarcaven la resta de comptes bancaris de la mateixa persona, podent quedar més d'un compte marcat com a per defecte alhora. Ara, quan `is_default` es marca a `True`, es posa `is_default=False` a la resta de `PersonBank` de la mateixa `person`.

## [21-07-2026]

### FEAT
#### BILLING (PaymentRemittance + is_return)

    - S'ha afegit l'opció de que una remesa sigui de retorn per transferència. El procés és gaire bé el mateix amb alguna diferència (sobre tot al generar el fitxer xml (`sepa_file_service.py`) degut a blocs amb un nom diferent o que no es mostren si són retorns)

#### BILLING (Exportació CSV de SupplyPoints d'un ReadingBatch)

    - Nou endpoint`GET /billing/reading/by-batch/supply-points/csv-export/?batch=<id>` (`ReadingBatchSupplyPointsCSVExportView`): llança la tasca Celery `export_reading_batch_supply_points_csv_task` i retorna `{task_id}` (`202`), mateix contracte que `reading/by-batch/csv-export/`.
    - El CSV (UTF-8 amb BOM, delimitador `;`) inclou tots els `SupplyPoint` de les `Route` del lot (respectant `include_telecontrol` / `include_manual`), amb `Route[Token]`/`Route[Name]`, `RoutePosition[Token]`/`RoutePosition[Position]`, `Property[Token]`, `SupplyPoint[Token]`, `SupplyPoint[Status]`, `Meter[Code]`, `HasReading`, `Reading[ReadingDate]`, `Reading[ReadingValue]`, `Reading[Consumption]` (`calculated_value`) i columnes dinàmiques `Contract[n][Token]` / `Contract[n][Status]` / `Contract[n][Facturable]` (`not block_billing`) segons el màxim de contractes. Lògica compartida a `service/utils/supply_points_route_csv_export.py` (usada també per l'export per Route).

#### SERVICE (Exportació CSV de SupplyPoints d'una Route)

    - Nou endpoint`POST /service/route/<id>/export-supply-points/` (`RouteViewSet.export_supply_points`): llança `export_route_supply_points_csv_task` i retorna `{task_id}` (`202`), mateix patró que `export-positions`. Mateixes columnes que l'export per ReadingBatch (sense lot: `HasReading=No` i lectures buides). Desat via `upload_document` (`entity="ROUTE"`, `field="EXPORT_SUPPLY_POINTS"`).

#### SERVICE (Lookup de comptadors per llista de codes)

    - Nous endpoints`POST /service/meter/lookup-by-codes/` (JSON síncron) i `POST /service/meter/lookup-by-codes/csv/` (Celery, `{task_id}`): body `{ "codes": ["…"] }`, match exacte per `Meter.code`. Retorna `found` (info de comptador + SP + contractes + última lectura no-control) i `not_found`. CSV amb `Found` Sí/No i columnes alineades. Lògica a `service/utils/meter_lookup_service.py`, vista `MeterLookupViewSet`, tasca `lookup_meters_by_codes_csv_task`.

#### SERVICE (Tab paginada de SupplyPoints d'una Route)

    - Nou endpoint`GET /service/route/<id>/supply-points/` (`RouteViewSet.supply_points`): llistat paginat (`page` / `page_size`, default 20) amb la mateixa informació que l'export CSV (`route`, `route_position`, `property`, `token`, `status`, `meter`, `has_reading`/`reading`, `contracts` amb `facturable`). Filtres `status` i `contract_status` (ids separats per coma); ordenació `ordering=property__token|token|status__name|status__token|contracts__status__name|contracts__status__token` (prefix `-` per descendent). Serializer `RouteSupplyPointTabSerializer`, filtre `RouteSupplyPointTabFilter`.

#### BILLING (Detall de ReadingBatch — agregats `num_routes` / `num_supplies` / `num_readings`)

    -`GET /billing/reading-batch/<id>/` (`ReadingBatchSerializer`): afegeix a la resposta els camps `num_routes`, `num_supplies`, `num_active_supplies` i `num_readings`, amb el mateix criteri que el llistat (`ReadingBatchMinimalSerializer`) per als totals, i `num_active_supplies` filtrant només SupplyPoints actius (`is_active=True` + `supply_point_status_activate_token`), sense treure ni canviar cap camp existent. Així el detall del lot pot mostrar el resum d’anàlisi i l’export de SupplyPoints també quan encara no hi ha lectures.

#### SERVICE (Contractes inactius als SupplyPoints)

    - Els serializers de`SupplyPoint` (`SupplyPointListSerializer`, `SupplyPointSerializer`, `SupplyPointMinimalSerializer`, `SupplyPointContractsSerializer`, `SupplyPointMinimalContractsSerializer` a `service/serializers/supply_point_serializer.py`) només retornen contractes amb `is_active=True`, alineat amb el mateix criteri del llistat de contractes.

### CHORE
#### COREDATA (Adreça — camp d'informació extra)

    - Nou camp`Address.address_extra` (`TextField`, `null=True`, `blank=True`, migració `coredata/migrations/0117_address_address_extra.py`) per informar dades addicionals lliures a una adreça (p. ex. "Dutxa", "Font"), a diferència de `building` que és estructural (nom d'edifici/bloc) i s'usa a la composició de la línia d'adreça i als filtres. Exposat automàticament a `AddressSerializer`/`AddressSerializerReduced` (`fields = '__all__'`) i editable via `AddressViewSet` (GET/POST/PUT/PATCH) sense cap canvi addicional.

#### WATCHDOG (Escomeses amb múltiples PS sense bateria)

    - Nova comprovació d'integritat`Escomeses amb múltiples PS sense Bateria` (`check_connections_multiple_supply_points_without_cluster` a `watchdog/services.py`): detecta `Connection` actives amb més d'un `SupplyPoint` actiu i sense cap `Cluster` (bateria) vinculat. A la sortida de `python manage.py watchdog sniff` apareix com a línia pròpia (`✔ Escomeses amb múltiples PS sense Bateria: OK` o `✘ ...: FALLAT`), entre `SupplyPoints Multiple Contracts` i `Persons Duplicate Tokens`; en cas d'incidències, detalla cada escomesa (p. ex. `Connection ID 904 (1/13880) té 2 SupplyPoints actius i cap Cluster (bateria) vinculat`).

## [20-07-2026]

### FIX
#### CONTRACT

    - Les lectures amb baixa lògica (`Reading.is_active=False`) ja no es mostren a la informació de consum: serialitzadors de supply points (`last_readings_by_contract`, `last_reading`), gestió de consums (`GET /contract/consumption-management/`), consum OV (`GET /billing/contract-consumption-ov/<contract_token>/`), lectures recents del contracte (`ContractMinimalSerializer`) i `pending_billing` (`ContractSerializer`). La gestió de consums també exclou contractes amb baixa lògica (`contract__is_active=True`).
    - El llistat de contractes (`GET /contract/contract/`) i l'exportació CSV associada ara exclouen per defecte els contractes amb `is_active=False` (`ContractFilter` i `ContractViewSet.get_queryset()` en acció `list`). El detall per ID (`retrieve`) segueix accessible.

#### BILLING (reading_service.py -> `modify_existing_readings`)

    - Ordena la modificació de lectures primer pel comptadors actual, pel cas de modificar una lectura de tancament (canvi de comptador) gestioni en l'ordre correcte les lectures i la relació que tenen amb el seu previous reading.

#### BILLING (estimat suppy_point_view.py - `save-meter-change` - invoice_service.py)

    - Al fer un canvi de comptador, si tenim una bossa d'estimats positiva i un consum positiu al fer el canvi, calcula i resta en aquest consum per fer el càlcul en aquest mateix moment i no deixar-ho per més endavant.

#### BILLING (models.py `INVOICE`)

    - Canviat 'consumption_bag' per 'real_consumption' ja que el nou NO indicava correctament el que contenia. Això implica canvis als fitxers amb aquest consumption_bag involucrat.

### FEAT
#### CONTRACT (Canvi de nom mantenint el mateix codi de contracte)

    - Nou camp`ContractRequest.keep_same_code` (booleà, per defecte `False`, migració `contract/migrations/0229_add_keep_same_code_to_contractrequest.py`). Quan una sol·licitud de "Canvi de nom" (`is_change_of_name=True`) el marca a `True`, `contract_create()` (`contract/utils/contract_service.py`) ja no genera un token nou pel `Contract`: reutilitza el codi del contracte donat de baixa i, en comptes, és aquest darrer qui es renombra amb un sufix incremental `{codi}/000N` (`_rename_old_contract_and_get_reused_token`), on `N` compta les baixes històriques ja aprovades amb el mateix codi base. Requereix que la sol·licitud tingui exactament una `ContractTerminationRequest` vinculada; si no, llança un error de validació explícit.
    - En aquest mateix flux, `ContractTerminationRequest.bill_cut_reading` es força a `False` (la lectura de tall ja no es factura d'immediat) i les seves lectures actives es revinculen al nou `Contract` (`batch=None`), perquè es reculli junt amb la resta de lectures pendents al proper cicle de facturació (trimestral) en lloc de facturar-se soles. Si aquesta lectura de tall coincideix amb una lectura "inicial" ja introduïda per a l'alta (mateix comptador), es fusionen en una de sola per no duplicar-la a la factura.
    - `billing/utils/invoice_service.py` (`generate_consumption_invoice_multiple`): la guarda que bloquejava la generació de factura quan la lectura és anterior a la data d'alta del contracte ara s'ignora específicament quan el contracte prové d'un canvi de nom amb `keep_same_code=True`, ja que en aquest cas és intencionat arrossegar lectures anteriors a la nova alta.
    - Nou endpoint `PUT /contract/contract-request/finalize-in-place/<contract_request_id>/` (`FinalizeContractRequestInPlaceView`, `contract/utils/contract_request_service.py`: `contract_request_finalize_in_place`): com el `finalize` existent (valida dades, genera les `Order` pendents de la sol·licitud i de la baixa vinculada per traçabilitat), però sense esperar que es completin: finalitza la `ContractRequest` i crea el `Contract` immediatament. Pensat per a fluxos sense intervenció física, com el canvi de nom.

#### BILLING (READING — data i fuita a la lectura inicial)

    -`POST /billing/request-reading/` (`ReadingViewSet.save_initial_reading`, `billing/views/reading_view.py`) accepta ara els camps opcionals `reading_date` i `leak_value`. Fins ara la lectura inicial es creava sempre sense data (quedava `null` fins que `contract_create` l'omplia amb la data d'alta), sense possibilitat d'indicar una data real anterior (p. ex. la d'una lectura de tall) ni un valor de fuita. Compatible amb les crides existents que no envien aquests camps.
    - `contract_create()` (`contract/utils/contract_service.py`) ja no sobreescriu `reading.reading_date` si la lectura ja en porta una d'informada; només aplica el fallback a la data d'alta quan la lectura no en té cap.

#### BILLING (Smart Metering — lectura puntual per comptador)

    - Nou endpoint`GET /billing/smart-metering/meter-reading/` (`SmartMeteringMeterReadingView`, `billing/views/smart_metering_meter_reading_view.py`): consulta **síncrona** (sense Celery) la lectura d'un sol comptador per data via la 3rd party Smart Metering. Paràmetres: `meter` o `meter_id`, `date` (opcional, per defecte avui), `margin` (opcional). Resposta: `{ found, reading_value, reading_date, origin: "SMART METERING", ... }`.
    - `SmartMeteringClient` (`billing/utils/smart_metering_service.py`): nou endpoint intern `/meter-readings-by-date/` (`SINGLE_READINGS_ENDPOINT`) i mètode `fetch_meter_reading()`. Refactor de la crida HTTP compartida a `_get()`.
    - Nova funció `fetch_smart_metering_meter_reading()`: resol el codi de comptador (directe o via `meter_id`), consulta l'API externa i normalitza la resposta per al front (inclou suport per respostes d'un sol comptador a `_extract_api_rows()`).
    - Permisos: `IsAuthenticated` + `ReadingPermission` (mateixos que lectures). Registrat a `billing/urls.py`.

### CHORE
#### COREDATA (Mode de generació del codi de contracte)

    - Nova clau`CONTRACT_TOKEN_GENERATION_INCREMENTAL_ENABLED` a `ConfigProject` (migració `coredata/migrations/0116_add_contract_token_generation_incremental_enabled_config.py`, valor per defecte `'false'`). Nou helper `generate_contract_request_token()` (`contract/utils/contract_token_service.py`), usat ara per `ContractRequestViewSet.create()` (`contract/views/contract_request_view.py`) en lloc de cridar `generate_token` directament: amb el flag desactivat, el comportament és idèntic a l'actual (codi basat en data); activat, continua la numeració a partir del token numèric del darrer `Contract` (el més nou), ignorant la data.

## [17-07-2026]

### FEAT
#### DOCUMENTMANAGER (Model, API i cicle de vida de `DocumentSign` — firma OTP de documents)

    - Nou model`DocumentSign` (`documentmanager/models.py`, migració `0016_documentsign`) per gestionar la firma OTP de documents externa: `token`, `contract` (FK a `Contract`), `contract_request` (FK a `ContractRequest`, per poder firmar durant una sol·licitud abans que existeixi el contracte definitiu), `contract_file`/`contract_file_signed`, `signed_at`, `status` (`1`=Pending, `2`=Sended, `3`=Signed, `-1`=Error) amb `error_report`, i dades del signant `otp_name`/`otp_email`/`otp_phone`. Registrat a l'admin (`DocumentSignAdmin`)
    - Nou `DocumentSignSerializer` (`documentmanager/serializers.py`) amb `status_display`, `contract_token`, `contract_request_token` i URLs absolutes (`contract_file_url`/`contract_file_signed_url`)
    - Nou `DocumentSignViewSet` (`documentmanager/views.py`), amb `DjangoModelPermissions` a més de l'autenticació, i CRUD complet i accions:
        - `by_contract` (`GET /documentmanager/document-signs-by-contract/?contract_id=` o `?contract_request_id=`) per relacionar un contracte (o una sol·licitud d'alta encara sense contracte) amb els seus documents de firma
        - `all_documents` (`GET /documentmanager/document-signs-all/?status=`) per llistar tots els documents registrats amb el seu estat
        - `download` (`GET /documentmanager/document-sign-download/<pk>/`) per descarregar el document firmat (o el pendent si encara no hi ha firma)
        - `send` (`POST /documentmanager/document-sign/<pk>/send/`) per enviar el document a firmar
    - `contract_create()` (`contract/utils/contract_service.py`): en finalitzar una sol·licitud i crear el `Contract` definitiu, els `DocumentSign` que s'havien enviat a firmar durant la sol·licitud (vinculats només a `contract_request`) es vinculen automàticament també al nou `Contract`, seguint el mateix patró que ja s'aplicava a `Invoice`

#### INTEGRATIONS (Integració amb Aqua360 Sign per a `DocumentSign`)

    - Aprofitada la integració existent amb Aqua360 Sign (`integrations/outbound/signing`, `integrations/inbound/signing`) per donar suport a la firma OTP de `DocumentSign`, sense duplicar client ni webhook:
        - `create_document_sign_session()` (`integrations/outbound/signing/services.py`): envia el `contract_file` d'un `DocumentSign` mitjançant el `SigningClient` ja existent, actualitzant `token`/`status` (`Sended` en èxit, `Error` + `error_report` en fallada)
        - `handle_signing_callback()` (`integrations/inbound/signing/services.py`) distingeix, a partir de l'`external_reference` del callback, entre una `ContractRequest` (comportament original) i un `DocumentSign`; en aquest darrer cas desa el document firmat a `contract_file_signed` i marca `status=Signed`/`signed_at` (`save_signed_document_sign_file()`)
        - El webhook `/signing/callback/` (`SigningCallbackView`) i la seva autenticació per `X-API-Key` es reutilitzen sense canvis
    - `_ensure_document_sign_contract_file()` (`integrations/outbound/signing/services.py`): si el `DocumentSign` encara no té `contract_file`, backend el genera automàticament abans d'enviar-lo a firmar, en comptes d'exigir que front l'hagi generat prèviament. Reutilitza el `contract_file` del `Contract`/`ContractRequest` si ja existeix (p. ex. generat via `contract/download/<id>/?is_contract=false`); si no existeix, genera el PDF amb `generate_contract_pdf_bytes()` (la mateixa funció que usa aquell endpoint), el desa com a `Document` i el deixa vinculat tant al `Contract`/`ContractRequest` com al `DocumentSign`, per no regenerar-lo en properes crides

#### DOCUMENTMANAGER / INTEGRATIONS (Estat `Expired` per a sessions de signatura caducades)

    - Nou estat`STATUS_EXPIRED` (`4`) a `DocumentSign` (migració `documentmanager/migrations/0017_alter_documentsign_status.py`), i suport per l'event `session.expired` del webhook d'Aqua360 Sign (abans es rebutjava amb un 400 sense actualitzar res): `SigningCallbackView` (`integrations/inbound/signing/views.py`) ara accepta `session.signed` i `session.expired`; `handle_signing_callback()` (`integrations/inbound/signing/services.py`) hi afegeix `_handle_contract_request_expired()`/`_handle_document_sign_expired()`, que marquen `ContractSigningSession.STATUS_EXPIRED`/`DocumentSign.STATUS_EXPIRED` respectivament (sense tocar sessions ja firmades).

### CHORE
#### DOCUMENTMANAGER (Interruptor de la funcionalitat DocumentSign)

    - Nova clau`DOCUMENT_SIGN_ENABLED` a `ConfigProject` (migració `coredata/migrations/0113_add_document_sign_enabled_config.py`, valor per defecte `'false'`), consultable pel front via l'endpoint ja existent `GET /config-project/DOCUMENT_SIGN_ENABLED/value/` sense necessitat de cap endpoint nou.
    - Nou helper `is_document_sign_enabled()` (`documentmanager/utils/document_sign_config.py`), usat per bloquejar l'enviament a firmar quan la funcionalitat està desactivada: a `DocumentSignViewSet.perform_create`/`send` (`documentmanager/views.py`) i a `create_contract_request_signing_session()`/`create_document_sign_session()` (`integrations/outbound/signing/services.py`).

### FIX
#### READING (DOCUMENT — CSV ISO-8859-1 / Windows-1252)

    - L'importació de documents de lectures (`_iter_reading_document_csv_rows` a `billing/tasks.py`) només acceptava UTF-8 i fallava amb fitxers ISO (`'utf-8' codec can't decode byte 0xe7...`). Ara es detecta l'encoding: UTF-8 (amb BOM), i si falla es fa fallback a `cp1252` / `iso-8859-1`.

#### INTEGRATIONS (El PDF firmat no arribava incrustat al webhook)

    -`handle_signing_callback()` assumia que el document firmat venia en base64 dins del propi callback (`signed_document`/`document`/`documents[].content`) o com a URL (`signed_document_url`), quan segons la documentació d'Aqua360 Sign (`customers-webhook-example.md`) el webhook `session.signed` només notifica l'esdeveniment: el PDF firmat cal descarregar-lo a part. Nou mètode `SigningClient.download_signed_document(session_id, document_id)` (`integrations/outbound/signing/client.py`, `GET /api/sessions/<session_id>/documents/<document_id>/signed/`), usat per la nova `_download_signed_pdf()` (`integrations/inbound/signing/services.py`) que substitueix l'antiga `_extract_signed_pdf_bytes()`.

#### INTEGRATIONS (`external_reference` inestable en reenviaments de `DocumentSign`)

    -`create_document_sign_session()` (`integrations/outbound/signing/services.py`) reutilitzava `document_sign.token` com a `external_reference` del següent enviament, però aquest camp guarda l'id de sessió remot d'Aqua360 (sobreescrit a cada enviament), no una referència pròpia estable. Resultat: en reenviar un document (`force=True`), la nova sessió quedava registrada a Aqua360 amb una referència que ja no coincidia amb res resoluble al nostre sistema, i el callback corresponent es perdia silenciosament (404 intern). Ara `external_reference` és sempre `docsign-<document_sign.id>` (vegeu també el següent punt).

#### INTEGRATIONS (Col·lisió d'id entre `DocumentSign` i `ContractRequest` al resoldre el callback)

    -`_resolve_document_sign()`/`_resolve_contract_request()` (`integrations/inbound/signing/services.py`) usaven l'id numèric nu com a `external_reference` de fallback per a `DocumentSign`, ambigu amb l'id (també numèric) de `ContractRequest`. Detectat en producció/proves: un `DocumentSign` amb el mateix id que un `ContractRequest` existent va rebre el callback resolt erròniament contra el `ContractRequest`, desant-hi el PDF firmat equivocat i deixant el `DocumentSign` real sense actualitzar. Ara `create_document_sign_session()` genera sempre la referència amb prefix `docsign-<id>` (constant `DOCUMENT_SIGN_REFERENCE_PREFIX`, `documentmanager/utils/document_sign_config.py`), i `handle_signing_callback()` la resol directament com a `DocumentSign` sense passar per `ContractRequest`; es manté compatibilitat amb sessions ja enviades abans d'aquest canvi (referència sense prefix).

#### INTEGRATIONS (Autenticació del callback sempre obligatòria, contradient la documentació)

    -`SigningCallbackView` (`integrations/inbound/signing/views.py`) rebutjava sempre el callback amb 403 quan `SIGN_CALLBACK_API_KEY` no estava configurat, tot i que la documentació (`customers-webhook-example.md`) especifica que l'autenticació per `X-API-Key` és opcional (només si es configura als dos costats). Ara només es valida la clau quan `SIGN_CALLBACK_API_KEY` té un valor.

#### INTEGRATIONS (Migració `0001_initial` d'`integrations` mai aplicada en bases de dades noves)

    -`integrations/migrations/0001_initial.py` (squash de les migracions `0001`/`0002`/`0003`) s'incloïa a si mateixa (`("integrations", "0001_initial")`) dins la seva pròpia llista `replaces`, fent que Django l'eliminés del graf de migracions sense substituir-la per res. Efecte: en qualsevol base de dades nova (p. ex. la de tests), les taules `integrations_integrationrequestlog`/`integrations_contractsigningsession` mai es creaven (`relation does not exist`), tot i que `manage.py check`/`showmigrations` no ho detectaven com a error. Eliminada l'auto-referència de `replaces`.

#### SERVICE (`ClusterNozzle` — vincle amb `SupplyPoint` existent)

    -`ClusterNozzleSaveSerializer.create()`/`update()` (`service/serializers/cluster_nozzle_serializer.py`): quan es passa `supply_point_id` (vincular un `SupplyPoint` ja existent a la boquilla, en comptes de crear-ne un de nou via `supplyPoint`), ara es desvincula primer qualsevol altre `SupplyPoint` que ja estigués assignat a aquest `ClusterNozzle` (`exclude(id=supply_point_id).update(cluster_nozzle=None)`) abans d'assignar-hi el nou, evitant que una boquilla acabi amb més d'un punt de subministrament vinculat. A `update()`, aquest camí (`supply_point_id` sense `supplyPoint`) no existia abans i no feia res.
    - `ClusterNozzleViewSet.create()` (`service/views/cluster_nozzle_view.py`): `request.data.get('supplyPoint')['placement']` petava amb `TypeError` quan el payload no incloïa `supplyPoint` (cas de vincular un `SupplyPoint` existent per `supply_point_id`). Ara es comprova que `supplyPoint` existeixi abans de llegir-ne el `placement`.

#### SERVICE (`SupplyPointSaveNozzleSerializer` — camps d'adreça `null` trencaven la deduplicació)

    -`_create_address()` (`service/serializers/supply_point_serializer.py`): quan `street`/`street_number` arribaven com `null` (en lloc d'absents), `address_data.get('street', {})` retornava `None` i no el `{}` per defecte, petant en accedir-hi. Mateix problema amb `postal_code`/`building`/`floor`/`door`/`stair`: `get(..., '')` només aplica el valor per defecte si la clau no existeix, no si val `None`, de manera que dues adreces idèntiques enviades amb aquests camps a `null` en comptes d'absents no es detectaven com a duplicades (`Address.objects.filter(...).exists()` no coincidia mai amb la fila ja creada amb `''`). Ara tots aquests camps normalitzen `None` a `{}`/`''` abans d'usar-los.

#### MIGRATIONS

    - S'han actualitzat els migrates per funcionar correctament.
    - En diversos servidors,`coredata.0114_update_contract_keeper_use_type_name` constava aplicada a `django_migrations` sense que la seva dependència `coredata.0113_add_document_sign_enabled_config` s'hagués arribat a registrar mai (i per tant sense que la seva `ConfigProject(token='DOCUMENT_SIGN_ENABLED')` s'hagués creat), fent fallar `migrate` amb `InconsistentMigrationHistory` en corregir la dependència de `0114` al commit anterior. Nova comanda de gestió `fix_document_sign_migration_history` (`coredata/management/commands/`), idempotent, que detecta aquest cas concret, crea la `ConfigProject` que faltava i registra `0113` com a aplicada abans de `0114`; s'executa automàticament a `docker-entrypoint.sh` abans de `migrate --noinput` a cada arrencada del contenidor, sense necessitat de corregir cada base de dades manualment.

## [16-07-2026]

### FEAT
#### READING (DOCUMENT — validació prèvia i reprocessament)

    - Flux en dos passos:`POST /billing/reading-document/` amb `auto_process=false` → `GET|POST .../validate/` (preview) → `POST .../process/` (Celery). `PATCH` + `POST .../reprocess/` per corregir i tornar a entrar. Compatibilitat: sense `auto_process=false` es processa immediatament com abans.
    - `ReadingDocument`: camps `status`, `task_id`, `processed_at`, `last_preview` (migració `0301`). Servei `billing/utils/reading_document_import_service.py` amb filtre/paginació al preview (`action`, `reason`, `offset`/`max_rows` o `page`/`page_size`, `filtered_total`, cache a `last_preview`, `refresh=true`).

#### IMPORTEXPORT / PRICING (`merge_pricing_product`)

    - Nova comanda`python manage.py merge_pricing_product <pricing.json> --product-token <TOKEN>` per fer merge selectiu d'un sol `Product` (i tot l'arbre: PriceRate, BillingRange, LineItemType, Adjustment, conditions, stretches) des d'un dumpdata de pricing d'un altre projecte, sense carregar tot el fixture.

#### SERVICE (Exportació CSV de posicions d'una ruta)

    - Nou endpoint`POST /service/route/<id>/export-positions/` (`RouteViewSet.export_positions`, `service/views/route_view.py`): llança la tasca Celery `export_route_positions_csv_task` (`service/tasks.py`) i retorna `{task_id}` (`202`), seguint el mateix contracte que `contract-use-aca`/`export_contracts_csv_task` (`contract/tasks.py`) — cal fer polling a `GET /task-progress/<task_id>/` (endpoint ja existent, `billing/views/reading_batch_generate_view.py:TaskProgressView`), que quan l'estat és `SUCCESS` inclou dins `result` el `document_id`/`filename` retornats per la tasca.

### CHORE
#### READING (DOCUMENT — validació prèvia i reprocessament)

    - Cada fila del preview exposa els valors efectius (`origin`, `is_control`, `leak_value`, `observation`, `raw_reading_value`, etc.). Doc: `docs/reading-document-import.md`.

#### IMPORTEXPORT / PRICING (`merge_pricing_product`)

    - Dry-run per defecte; cal`--apply` per persistir. Upsert per token (no força els pk del dump); els BillingRange es poden reassignar a la tarifa del dump; no elimina tarifes/line items locals que no surten al dump. Models globals (Tax, BillingPeriod, Publication, PriceInterval, etc.) es resolen per token o pk.

#### SERVICE (Exportació CSV de posicions d'una ruta)

    - La tasca genera un CSV (UTF-8 amb BOM, delimitador`;`) amb columnes `Ordre, Codi de posició, Finques, Punts de subministrament, Observació` (`service/utils/route_export_csv.py`), recorrent `Route.positions` ordenades per `position`, i per cadascuna les seves `Property` (Finques) i els `SupplyPoint` de cada finca (Punts de subministrament); `Observació` és `RoutePosition.reader_observation`. Desat via `documentmanager.utils.main_utils.upload_document` (`entity="ROUTE"`, `field="EXPORT_POSITIONS"`).

### MODIFIED
#### CONTRACT (ContractRequestType "Canvi de nom" → camp persistent `is_change_of_name`)

    - Nou camp`ContractRequest.is_change_of_name` (booleà, migració `contract/migrations/0228_add_is_change_of_name_to_contractrequest.py`, amb backfill de dades per a les sol·licituds existents amb `type__token='canvi_nom'`). Fins ara l'única manera de detectar que una `ContractRequest` era un "Canvi de nom" era comparant `type.token == 'canvi_nom'` contra el catàleg `ContractRequestType`, que la mostrava barrejada al mateix llistat que "Agrícola", "Domèstic", etc. Exposat com a camp editable a `ContractRequestSerializer` (`contract_request_base_serializer.py`, via `fields = '__all__'`): el frontend ja pot enviar `is_change_of_name: true` directament al crear/editar la sol·licitud. El `pre_save` de `ContractRequest` (`contract/signals.py`) només **força** el valor a `True` quan `type.token == 'canvi_nom'` (per compatibilitat amb dades antigues); mai el sobreescriu a `False`, de manera que no trepitja el valor enviat explícitament pel client.
    - `ContractRequestTypeViewSet.get_queryset()` (`contract/views/contract_request_type_view.py`): l'acció `list` exclou ara `token='canvi_nom'`, de manera que ja no apareix al desplegable de tipus de contractació.
    - `report_advanced_billing_service.py` (informe "Canvis de nom / Titular"): substituït el filtre `type__token__in=[..., 'canvi_nom']` per `Q(is_change_of_name=True)` combinat amb la resta de tokens.
    - Eliminada la fila `ContractRequestType(token='canvi_nom')` del catàleg amb la comanda de gestió ja existent `python manage.py delete_contractrequesttype --id <id>` (posa `ContractRequest.type` a `NULL` via `SET_NULL` sense afectar `is_change_of_name`, que es manté com a senyal independent i persistent).

### FIX
#### READING (DOCUMENT)

    - Mapping buit (`mapped_name=""`) ja no llegeix columnes sense capçalera del CSV (evita valors spurious a origen/fuga/observació). `Decimal` de lectures anteriors es serialitza correctament al `last_preview`. `process`/`reprocess` desbloquegen documents atrapats a `processing` si la tasca Celery ja ha fallat.

#### BILLING (Recalcular un lot o una factura individual esborrava factures ja finalitzades per via externa)

    -`BillingBatchRegenerateView` (`billing/views/billing_batch_regenerate_view.py`, endpoint `POST /billing/billing/<id>/recalculate`): en recalcular/regenerar un lot de facturació esborrava **totes** les `Invoice` del lot (`Invoice.objects.filter(billing=id).delete()`) sense mirar si alguna ja s'havia finalitzat per via externa a la facturació en lot (p. ex. confirmada/pagada manualment abans que el lot acabés de processar-se). Un cop esborrada, `process_billing_batch` (`billing/tasks.py:1759-1761`) tornava a generar una factura nova per a les mateixes lectures, ja que el seu filtre de protecció (excloure lectures que ja tenen una `Invoice` amb `type_final='F'`) només funciona si la factura encara existeix a BD. Ara només s'esborren les factures que encara estan en estat "Pre-factura" (`invoice_status_pending_token`); les ja finalitzades es conserven intactes (i, si pertanyien a un sub-lot d'exclusió, es reassignen al lot principal abans d'esborrar-lo) de manera que les seves lectures queden protegides pel filtre existent i no es tornen a facturar.
    - Mateix problema a nivell individual: `recalculate_invoice`/`recalculate_invoice_smart` (`billing/utils/recalculate_invoice_service.py`, endpoint `POST /billing/invoice/<id>/recalculate-smart/`) esborraven la factura original i en regeneraven una nova independentment del seu estat. Nova guarda `_assert_invoice_is_recalculable()` que bloqueja amb `ValueError` (retornat com a `400`) si la factura ja no és "Pre-factura". Verificat amb la factura real 67814 (estat "Pagada"): abans es regenerava perdent el pagament, ara queda bloquejada i intacta; una pre-factura normal es continua recalculant amb normalitat.

#### BILLING (Pagament d'una factura amb intents de cobrament antics no la marcava "Pagada")

    -`update_payment` (signal `post_save` de `Payment`, `billing/signals.py`): quan una factura tenia més d'un `Payment` associat (p. ex. un intent de cobrament anterior ja "Vençut"/"Retornat" abans d'un nou pagament via `BankRNDDocumentView` — fitxer de retorns bancaris "N19"/wallet management, o `manual_payment`), el signal només marcava `Invoice.status = "Pagada"` si **tots** els `Payment` històrics de la factura tenien estat `paid`/`piggy`. Com que un intent antic fallit mai passa a "pagat", la factura quedava bloquejada per sempre en el seu estat previ (p. ex. "Vençuda") encara que el `Payment`/`PaymentMovement` vigent ja constés correctament com a pagat. Ara la condició es basa en l'import realment pendent: se suma l'`amount` de tots els `Payment` en estat pagat/moneder de la factura i, si cobreix el `total_final` (`left_to_pay <= 0`), es marca "Pagada" i es recalcula `left_to_pay`, independentment de l'estat d'intents de cobrament antics ja superats.
    - Importació de lectures: només es vincula **un** contracte **actiu** (`ConfigProject.contract_active_token` + `is_active=True`), prioritzant `supply_point_default`. Ja no s'iteren contractes de baixa ni es creen N lectures per N contractes del mateix punt.

## [15-07-2026]

### FEAT
#### DOCS (API Oficina Virtual)

    - Nova documentació OpenAPI de la API OV a`docs/ov/openapi.yaml` (en castellà), amb resum d'endpoints, autenticació per token, esquemes de petició/resposta i tot l'abast de `/ov/` (contracte, dades de facturació, factures, consums i lectures) per a integracions de tercers (Oficines Virtuals).

#### STATISTICS (Informes generats amb extensió `.xls` però contingut `.xlsx`)

    - Diversos generadors d'informes creaven el`Workbook` amb `openpyxl` (format modern `.xlsx`) però anomenaven el fitxer resultant amb extensió `.xls` antiga, fent que alguns lectors/visors interpretessin malament el fitxer i el mostressin buit tot i que les dades s'havien calculat i desat correctament (detectat arran de l'informe "Resum de facturació", `AvailableReport` pk=1, que retornava un `.xls` visualment buit malgrat tenir 175 factures i totals correctes al full de càlcul real). Corregida l'extensió a `.xlsx` a: `get_report_billing_summary` (`report_billing_service.py`), `generate_aqua_remittance_report` i les funcions de `report_service.py` que generaven `INCASOL_*.xls`/`puntual_*.xls`, i dues funcions de `report_wallet_service.py` (`wallet_*.xls` i `{name}_*.xls`). No afecta la lògica de generació de dades, només el nom/extensió del fitxer desat.

### CHORE
#### CONTRACT (ContractRequestType "Canvi de nom")

    - Nova migració de dades`coredata/migrations/0115_add_canvi_nom_contract_request_type_config.py`: crea/actualitza el `ContractRequestType(token='canvi_nom', name='Canvi de nom')` i la clau `ConfigProject(token='contract_request_type_change_name_token')` (guarda l'`id` del tipus). Permet que el frontend enviï aquest `type` a la creació del `ContractRequest` per diferenciar explícitament un "Canvi de nom" (alta+baixa amb `ContractTerminationRequest.type.token` de "Baixa per canvi de titular" i `holder`/`owner` de nou/antic titular) d'una alta normal, sense necessitat de cap altre canvi de lògica al backend: el flux de finalització (`contract_request_finalize`/`contract_create`) i de baixa segueixen sent els mateixos per a qualsevol tipus de sol·licitud.

#### STATISTICS (Filtratge multi-selecció als informes)

    - Nou helper`statistics/utils/report_filters.py` (`get_multi_ids`, `invoice_multi_filter_q`, `payment_multi_filter_q`, `contract_multi_filter_q`) per acceptar `billing_ids`/`remittance_ids`/`person_ids`/`contract_ids` (llistes o CSV) al payload de `POST /statistics/available-reports/{pk}/trigger/` i aplicar-los com a filtres `__in` combinats: `person_ids` es resol contra els tres rols de `Contract` (`owner`/`tenant`/`holder`), `contract_ids`/`billing_ids` de forma directa, i `remittance_ids` via `Payment.remittances`. Aplicat a la majoria de generadors de `report_service.py`, `report_billing_service.py`, `report_wallet_service.py`, `report_advanced_billing_service.py` i `report_contract_termination_export_service.py` (contract_ids/person_ids), mantenint intacte el comportament existent amb `billing_id`/`remittance_id` singulars per als informes personalitzats encara no migrats a multi-selecció al front.
    - **Nota**: `report_wincen_service.py` i `generate_management_volume_report` (`report_advanced_billing_service.py`) queden fora d'abast: el primer delega a un servei extern amb un `billing_id` simple, i el segon itera sobre models massa heterogenis per aplicar el filtre sense risc de trencar els comptadors.

## [14-07-2026]

### FIX
#### READING (DOCUMENT)

    -`billing/tasks.py` (`process_reading_document_file`): corregits dos bugs que impedien importar fitxers de lectures (p. ex. CSV de telelectura amb `;`).
        - Quan una fila no trobava el comptador, la tasca Celery petava amb `UnboundLocalError` perquè `reading_date` s'usava al token de `ReadingDocumentNotFound` abans de parsejar-la; a més, el bloc `not_found` feia servir un format de data fix (`%d/%m/%Y`) incompatible amb valors com `1/7/26 9:47`. Ara la data es parseja abans de resoldre el comptador (amb `parse_reading_document_date`) i s'usa `Meter address` com a identificador quan no hi ha columna `meter`.
        - En CSV amb delimitador `;`, `csv.Sniffer` sovint no el detectava i el codi feia fallback a `,`, de manera que totes les columnes del mapping (`Receive time`, `Meter address`, etc.) quedaven buides i les 319 files es saltaven silenciosament (`num_readings: 0`). Afegida detecció de delimitador per nombre d'aparicions a la capçalera i logs `[reading-doc]` per traçar cada fila (data, `comm_module`, comptador trobat/no trobat, contractes, creació de lectura).

#### BILLING (`check-missing` — contractes en Aforament marcats erròniament com `no_meter`)

    -`BillingViewSet.check_missing` (`billing/views/billing_view.py`): els contractes amb un comptador en estat "Aforament" (token `token_meter_status_no_meter`) es marcaven amb el motiu `no_meter`, tot i tenir un comptador assignat i ser facturables per estimació amb normalitat (mateix tractament que ja aplica `reading_service.py` via `is_gauge`). Ara `contract_ids_with_meters` només comprova que el contracte tingui algun comptador assignat (`supply_points__meter__isnull=False`), independentment del seu estat, de manera que l'Aforament ja no compta com a `no_meter`. Un contracte sense cap comptador assignat continua marcant-se `no_meter` com fins ara. Com a conseqüència, el recompte agregat `no_meter` que mostra `BillingSummary.vue` (que prové directament d'aquest endpoint) deixa d'inflar-se amb contractes en Aforament, sense necessitat de cap canvi al frontend.

### CHORE
#### BILLING (`serie_final` de pressupostos — hook de personalització per client)

    -`billing/utils/invoice_service.py`: afegit el mòdul opcional de personalització `generate_budget_serie_final_personalized` (importat amb `try/except ImportError`, mateix patró ja existent al fitxer per a altres mòduls personalitzats). Quan `is_budget=True` i el client té definit `generate_budget_serie_final_personalized.generate_budget_serie_final(serie, invoice)`, aquesta funció s'usa per calcular el `serie_final` del pressupost en lloc de la lògica per defecte (`f"{serie.token}/{invoice.id}"`). Aplicat a `generate_consumption_invoice`, `generate_consumption_invoice_multiple`, `invoice_contract_generate`, `invoice_generate_return_bail` i `invoice_contract_termination_generate`. Si el client no té el mòdul personalitzat, el comportament es manté idèntic a l'actual.

### MODIFIED
#### COREDATA (`ConfigProject` — nom més entenedor del token `contract_keeper_use_type_token`)

    - Canviat el`name` del `ConfigProject` amb `token='contract_keeper_use_type_token'` de "Token Contract Keeper Use Type" a "Token Contracte Ús Agrícola", ja que "Keeper" no s'entenia bé en aquest context agrícola. Actualitzat als fixtures (`prometeo/data/config_project/local/ConfigProject.json`, `prometeo/data_es/config_project/local/ConfigProject.json`, `prometeo/data/config_project/aquacis/ConfigProject_AquaCIS.json`) i afegida la migració de dades `coredata/migrations/0114_update_contract_keeper_use_type_name.py` per aplicar el canvi també a bases de dades ja existents.

## [13-07-2026]

### FEAT
#### CONTRACT (use_aca ACA)

    - Nou endpoint`GET /contract/contract-use-aca/` per consultar quants contractes actius tenen `use_aca` null o buit.
    - Nou endpoint `POST /contract/contract-use-aca/` per executar `fill_contract_use_aca` (dry-run síncron o execució real en segon pla via Celery).

### CHORE
#### COREDATA (ConfigProject)

    - Nou endpoint`POST /coredata/config-project/bulk-update-values/` per actualitzar en bloc el `value` de diversos `ConfigProject` mitjançant una llista `{token, value}` (normalitza booleans com `uses_aca` a string).

#### WATCHDOG (Validació ACA)

    - Ampliada la comprovació`ArticleCode per informes ACA` quan `ConfigProject.uses_aca=True`: valida l'existència dels `ArticleCode` `part_fixa` i `part_variable`, que hi hagi `LineItemType` vinculats a cadascun, i que si existeix `ArticleCode` `ramader_0` el `ConfigProject.contract_keeper_use_type_token` coincideixi amb algun `ContractUseType.token`. Recomana `fix_aca_lineitemtype_articles` per corregir els vincles de `LineItemType`.

#### IMPORTEXPORT (Correcció de comptadors i lectures en canvis de comptador històrics)

    - Nova comanda de gestió`fix_meter_changes_from_cambios` (`python manage.py fix_meter_changes_from_cambios <csv_dir> --from-year <any>`): per a explotacions ja importades on `CambiosContador.csv` no s'havia tingut en compte, crea els `Meter` "vell"/"nou" que faltin i reassigna `Reading.meter` segons la data del canvi.

### FIX
#### IMPORTEXPORT (`fix_meter_changes_from_cambios`)

    - El camp`Observaciones` de `CambiosContador.csv` només reconeixia el format `VELL x NOU y`. Ara reconeix variants.

## [10-07-2026]

### FEAT
#### INTEGRATIONS GISWATER

    - feat(integrations): filtres`connection_token` i `connection_code_gis` a `GET /giswater/v1/contracts/`

### FIX
#### REPORT BILLING (INFORME ACA)

    - fix(report_billing_aca): consumption_bag com a consum real + ramaders agafi el use_aca "Q"

#### INTEGRATIONS GISWATER

    - fix(integrations): simplificació de serialitzador de resposta per giswater
    - fix(integrations): rutes inbound versionades sota`/giswater/v1/` (contractes i lectures)

## [09-07-2026]

### FEAT
#### BILLING / STATISTICS (Gestió manual de tasques de cua penjades)

    - 'billing/models.py' (`BillingQueue`), 'statistics/models.py' (`ReportQueue`): afegit el nou estat `skipped` a `STATUS_CHOICES` (migracions `billing/migrations/0300_alter_billingqueue_status.py` i `statistics/migrations/0032_alter_reportqueue_status.py`), per distingir un item saltat manualment d'un que ha fallat de veritat.
    - Nou endpoint `POST /billing/billing-queue/<queue_item_id>/action/` (`BillingQueueActionView`, `billing/views/billing_batch_generate_view.py`) i `POST /statistics/report-queue/<queue_item_id>/action/` (`ReportQueueActionView`, `statistics/views/available_report_view.py`), amb body `{"action": "kill" | "skip" | "restart"}`.

### CHORE
#### BILLING / STATISTICS (Gestió manual de tasques de cua penjades)

    - 'billing/tasks.py': nova funció`apply_billing_queue_action(queue_item, action)` amb les tres accions `kill` (revoca la tasca de Celery via `celery_app.control.revoke(task_id, terminate=True, signal='SIGKILL')` i marca l'item com a `failed`), `skip` (revoca i marca com a `skipped`) i `restart` (revoca, neteja `task_id`/`error_message`/`started_at`/`completed_at` i el torna a `pending`). Totes tres criden `process_next_queue_item()` en acabar per desbloquejar la cua FIFO, ja que aquesta només avança quan no hi ha cap item en `running`.
    - 'statistics/tasks.py': mateixa lògica amb `apply_report_queue_action(queue_item, action)`, cridant `process_next_report_queue_item()`.
    - **Nota**: cap dels dos models no tenia fins ara cap ús de `celery_app.control.revoke`; depenent de la configuració del pool de workers (`prefork` vs `solo`), el `revoke(terminate=True)` pot no interrompre immediatament una crida bloquejant ja en curs (p. ex. una consulta llarga a BD), però sí evita que la tasca continuï un cop hagi comprovat el senyal, i en qualsevol cas allibera la cua per a la següent tasca en marcar l'item com a `failed`/`skipped`/`pending`.

#### IMPORTEXPORT (Comanda de gestió per a correcció de titulars històrics)

    - Nova comanda de gestió`fix_historic_invoice_holder` (`python manage.py fix_historic_invoice_holder`): Identifica i corregeix factures històriques importades on el titular final (`customer_final` / `customer_token_final`) s'havia assignat erròniament amb el titular del compte bancari (`contract.payment.IBAN.person`) en lloc de l'actual titular del contracte (`contract.holder`). També corregeix els pagaments actius associats. Admet `--dry-run`, `--new-format-regex` i `--limit`.

### FIX
#### REPORT BILLING (INFORME ACA)

    - Agafava malament el volums de PART VARIABLE Tarifa Social. No hi havia cap tarifa social però en canvi mostrava volum al primer tram de tarifa social 50%. Era perquè en comptes de mirar només el concepte variable, mirava tots els conceptes de la factura buscant si s'havia una condició on impliques la variable de tarifa social, però sense tenir en compte que la condició podia ser negada (tarifa-social is null). PART FIXA SENSE CONSUM tenia condició negada (is_null) i es pensava que era tarifa social. S'ha corregit: 1. que per fer els volums socials només agafi correctors aplicats en conceptes de tarifa variable (no a qualsevol concepte) i 2. vigilar que no hi hi ha la variable, no s'estigui negant (operator is_null).

#### IMPORTEXPORT (Importació de pagaments)

    -`PaymentImportService` (`importexport/utils/payment_import_service.py`): Corregida la priorització del titular final (`customer_final` / `customer_token_final`) en la importació de pagaments. Ara s'assigna sempre el titular del contracte (`contract.holder`) en lloc del titular del compte bancari (`contract.payment.IBAN.person`), el qual només s'ha d'utilitzar per al pagador final (`payer_final`) en els rebuts SEPA.

#### CONTRACT

    -`contract_create()` (`contract/utils/contract_service.py`): les `Order` (ordres de treball) creades mentre encara existia només la `ContractRequest` (`Order.contract_request`) no es vinculaven mai al `Contract` definitiu en finalitzar la sol·licitud. Ara, en el mateix punt on ja es vinculaven les `Invoice` pendents, també es vinculen les `Order` pendents (`Order.objects.filter(contract_request=contract_request, contract__isnull=True).update(contract=contract)`)

#### BILLING (`GET /billing/billing-queue/` — item failed no visible / refresc continu al front)

    - 'billing/views/billing_batch_generate_view.py' (`BillingQueueListView`): l'endpoint només retornava els últims 10 items `completed`/`failed` de **tot el sistema** (`[:10]` sense filtrar per lot) i no incloïa el nou estat `skipped`. Si hi havia més de 10 lots amb tasques finalitzades recentment, l'item concret d'un lot podia quedar fora d'aquesta finestra, fent-lo invisible pel frontend (que interpretava "no trobat" com "acabat amb èxit" i entrava en un bucle de refresc cada 2 segons, ja que `Billing.status` mai s'actualitza en fallar la cua). Ara accepta el paràmetre opcional `?billing_id=<id>` per retornar tots els items d'aquell lot sense el límit dels 10 globals, i el filtre inclou `skipped`.
    - Mateixa vista: gestionat l'estat `REVOKED` de la tasca de Celery (resultant de matar-la manualment) a l'autoreparació de l'estat `running`; abans no queia en cap de les branques `PROGRESS`/`SUCCESS`/`FAILURE` i l'item es quedava indefinidament en `running`.

#### BILLING

    -`generate_xml` corregit el càlcul i la validació del camp Quantity perquè sigui fidel al PDF (2 decimals) i compleixi la regla 6a (Ordre HAP/1650/2015): ara es valida TotalCost = RedondeigA2(Quantity * UnitPriceWithoutTax) sense arrodonir prèviament el preu unitari, evitant rebutjos RCF6a
    - Nova comanda de gestió regenerate_einvoice (python3 manage.py regenerate_einvoice <serie_final...>) per regenerar l’XML de factura electrònica i sobrescriure el document EFACTURA desat per a factures ja emeses.

#### STATISTICS

    - Informe ACA. S'ha restat el invoice.estimated_bag del calcul del total de consum de les factures.

## [08-07-2026]

### FIX
#### BILLING

    - Avís`warning_date_range` (rang de dates de facturació): `ReadingViewSet.list_by_batch`/`list_by_batch_minimal`, `BillingInvoicesViewSet.list` i `BillingInvoicesSummaryViewSet` (`billing/views/reading_view.py`, `billing/views/billing_invoices_view.py`) només comptaven i filtraven com a "avís" les lectures/factures amb un període de facturació (`consumption_days`) superior a `mediana * 1.25`. Ara `date_range_above_margin_count` i el filtre `?alert=warning_date_range` també inclouen les que tenen un període inferior a `mediana * 0.75` (marge simètric al de dalt), ja que un rang massa curt també és un indicador d'un període de facturació incorrecte

#### STATISTICS

    -`generate_detailed_billing_summary` i `generate_aca_summary_report` (`report_billing_service.py`): en la ruta per rang de dates s'excloïen **totes** les factures anul·lades, de manera que una factura anul·lada que tenia un abonament/refactura lligat (`return_token`) desapareixia de l'informe tot i que el seu abonament sí que hi apareixia (i a l'informe ACA sí que hi sortia). Ara només s'exclouen les anul·lades **sense** `return_token`; les anul·lades amb refactura lligada es mantenen, alineant tots dos informes amb el criteri que ja apliquen `report_service.py` i `report_wallet_service.py`
    - `generate_billing_taxes_summary` (`report_billing_service.py`, informe "Resum IVA"): els imports de base i IVA dels abonaments (factures en estat payoff `-2`) es comptabilitzaven en positiu. Ara, per a les factures en estat abonament, la base i l'IVA es sumen en negatiu (via `-Abs(...)`), tant al resum agrupat per producte/tarifa (hoja "RESUM IVA") com al detall per factura (hoja "FACTURES"), per reflectir correctament els abonaments

### MODIFIED
#### GEODATA

    -`import_geo_data_pgeocode` (comanda de gestió): la resolució de municipis es feia només pel nom (`City.objects.filter(token=NOM)`), sense tenir en compte la província. Com que `City.token` és únic a la BD, un municipi amb el mateix nom en dues províncies diferents (p. ex. "Cervera" a Lleida i a Astúries) només es creava a la primera província trobada; la segona quedava silenciada (`try/except: pass`) i els seus codis postals s'acabaven vinculant erròniament a la ciutat de la primera província. Ara els municipis es resolen per `(nom, província)` reutilitzant `resolve_city()` (`importexport/utils/location_utils.py`), que genera un token únic incorporant la província quan cal crear-ne un de nou
    - `clean_duplicate_cities` (comanda de gestió): els duplicats es detectaven només pel nom, fusionant municipis reals de províncies diferents que coincidien de nom. Ara l'agrupació es fa per `(nom, província)`
    - `gen_exploitation_sp_service.py` i `CitySerializer.validate_city` (`coredata/serializers.py`): substituïda la generació manual de token de ciutat (nom en majúscules, sense província) per `resolve_city()`, evitant el mateix risc de col·lisió/fusió incorrecta
    - `import_geo_data_pgeocode` (comanda de gestió): en mode `--dry-run` ara es mostra el llistat de províncies noves que es crearien i el llistat de municipis nous amb la província a la qual pertanyen, en comptes de mostrar només els comptadors totals
    - `import_geo_data_pgeocode` (comanda de gestió): la comparació per detectar si una província ja existia es feia amb el nom original de pgeocode (castellà, p. ex. "Asturias") normalitzat, mentre que a la BD el nom ja estava desat traduït al català (p. ex. "ASTÚRIES"). Com que `normalize_name` només elimina accents/majúscules i no tradueix, "ASTURIAS" i "ASTURIES" no coincidien mai i es creava una província duplicada per cada província amb traducció catalana diferent del castellà, arrossegant tots els seus municipis i codis postals cap a la duplicada. Ara la comparació es fa sempre sobre el nom ja traduït (`get_display_name`)
    - Nova comanda de gestió `merge_translated_duplicate_provinces` (execució puntual) per fusionar les províncies que ja havien quedat duplicades per l'error anterior (p. ex. "Asturias" / "ASTÚRIES"): manté la província amb l'ID més baix i hi mou els municipis, adreces i codis postals de les duplicades abans d'eliminar-les. Admet `--dry-run`
    - `resolve_city()` (`importexport/utils/location_utils.py`): quan un municipi arribava com a "orfe" (sense província, arrossegat del bug de duplicació de províncies) i n'hi havia un altre amb el mateix nom en una província diferent (p. ex. "Cervera" a Lleida i a Astúries), la primera província que el processava es quedava aquesta fila òrfena sencera, incloent-hi els codis postals que ja tenia vinculats d'una altra província. Resultat: es mostrava el codi postal de "Cervera" (Lleida) al municipi "Cervera" (Astúries) o viceversa, per compartir la mateixa fila de `City`. Ara només es reutilitza l'orfe si no té cap codi postal vinculat a una província diferent de la que es vol assignar
    - Nova comanda de gestió `fix_city_postal_code_province_mismatch` (execució puntual) per corregir els municipis que ja havien quedat amb codis postals d'una altra província vinculats per l'error anterior: mou cada codi postal mal vinculat cap al municipi correcte (creant-lo si cal amb `resolve_city()`) i corregeix també les `Address` que apuntaven al municipi equivocat a partir del seu propi `postal_code`. Admet `--dry-run`

#### CONTRACT

    -`contract_create()` (`contract/utils/contract_service.py`): quan una sol·licitud de contracte (alta) factura la lectura de tall d'una baixa (`bill_cut_reading=True`), la factura es generava vinculada a la `ContractRequest` (`Invoice.contract_request`) perquè el `Contract` definitiu encara no existia en aquell moment, i mai s'arribava a vincular `Invoice.contract` un cop la sol·licitud es finalitzava. Ara, en finalitzar la sol·licitud i crear el contracte definitiu, es vinculen automàticament les factures pendents (`Invoice.objects.filter(contract_request=contract_request, contract__isnull=True)`) al nou `Contract`
    - Nova comanda de gestió `fix_missing_invoice_contract_link` (execució puntual) per corregir les factures que ja havien quedat en aquest estat (sol·licitud ja finalitzada amb contracte creat, però factura encara sense `contract` assignat) abans d'afegir el vincle automàtic anterior. Admet `--dry-run`

#### BILLING

    -`process_invoice_documents` (`tasks.py`, generació per lots de factures/PDFs): el progrés de `BillingQueue` es calculava sumant els passos de les dues fases (confirmació de factures + generació de PDF), fent que `total_items` es doblés respecte al nombre real de factures i que el percentatge avancés de forma esbiaixada. Ara `total_items` correspon al nombre real de factures i el percentatge combina les dues fases ponderant-les al 50% cadascuna. Afegits els camps `invoices_processed` i `documents_generated` al model `BillingQueue` (migració `0299`) i exposats a `BillingQueueListView`/`BillingQueueStatusView`, per distingir quantes factures s'han confirmat i quants PDFs s'han generat. El progrés ara s'actualitza cada 10 factures/documents en comptes de cada un, per reduir escriptures a la base de dades

## [07-07-2026]

### FIX
#### ORDERS

    - 'order_filter' : aplicar filtre per ciutat quan les comandes estan vinculades a una adreça i no a un contracte o punt de subministrament.

### CHORE
#### REMITTENCE RETURN

    - 'sepa_service' i 'payment_service': Afegir que es passi el color de l'estat anterior

### MODIFIED
#### PROMETEUS / PRICING ARTICLE CODE

    - 'princing.ArticleCode':  Elimnar i afegir els article code que s'estan usant actualment a totes les instal·lacions i eliminar les que hi havia en el fitxer perquè no s'estàn usant.

#### BILLING

    -`BillingPreInvoicesSummaryViewSet` (`billing_preinvoices_summary_view.py`, endpoint `/billing/billing/pre-invoices/<id>/summary`): el bloc `line_items` del resum ara agrupa només per Nom del producte i Nom de la tarifa (p. ex. "CANON AIGUA (ACA) - DOMESTICA"), en comptes de creuar-ho també amb el tipus de concepte i el tram, que multiplicava innecessàriament el nombre de línies. Afegit `subtotal_consumption` (consum total en m³) sota `responsible_consumption`. Els valors nuls o buits (tipus de pagament, tipus d'ús, producte, tarifa, percentatge d'IVA, bonificació, variable, missatge) ara es mostren com a "Altres" en comptes de quedar com `None`/omesos silenciosament
    - Corregit el recompte de `line_items`, `taxes`, `bonifications`, `variables` i `messages` a `BillingPreInvoicesSummaryViewSet`: com que aquests blocs es calculen fent un `JOIN` amb una relació u-a-molts/molts-a-molts de la factura (línies de factura, bonificacions, variables, missatges), `Count('id')` comptava files del `JOIN` (una per cada línia/tram/bonificació coincident) en lloc de factures reals, inflant molt el recompte (p. ex. "CANON AIGUA (ACA) - DOMESTICA" mostrava 4261 quan en realitat eren 906 factures). Ara s'usa `Count('id', distinct=True)` per comptar factures úniques
    - `get_report_billing_summary()` (`report_billing_service.py`, informe "Resum de facturació"): la columna "Num. Factures" del bloc per producte/IVA comptava files de `InvoiceLineItem` (`Count('id')`) en lloc de factures úniques, ja que cada factura pot tenir diverses línies actives amb el mateix producte i IVA (p. ex. trams). Corregit amb `Count('invoice', distinct=True)`
    - Informe WinCen (`wincen_service.py`): ampliada la columna de codi de contracte de 8 a 10 caràcters, ja que hi ha tokens de contracte que es truncaven silenciosament (es perdia l'últim dígit) quan superaven l'ample anterior. La línia exportada passa de 154 a 156 caràcters

#### STATISTICS

    - Informe global d'impagats (`generate_wallet_all_unpaid_summary`, `report_wallet_service.py`): el filtre de rang de dates deixava fora impagats no domiciliats (SEPA) marcats manualment com a "returned"/"endowment" (targeta rebutjada, transferència no rebuda, etc.), ja que en aquests casos el camp `reject_date` no s'assigna (només ho fa el procés automàtic de venciment o el flux de retorns SEPA). Afegida una quarta condició al filtre que els captura per `updated_at` quan `reject_date` és nul
    - `generate_accounting_values_report` (`report_service_personalized.py`, informes "Resum comptable" de Factures/Compromisos): les condicions comprovaven `accounting_type == "INVOICES"`/`"COMMITMENTDEPOSIT"`, però `statistics/tasks.py` sempre normalitza aquest valor a `"INVOICE"`/`"COMMITMENT"` (singular) abans de cridar la funció. Com que mai coincidien, no s'executava cap branca i es generava un fitxer Excel completament en blanc. Corregit perquè comprovi els valors singulars, i afegida la mateixa normalització/valor per defecte que ja tenia la versió base per robustesa. Aplicat al fitxer `report_service_personalized.py` per a la instal·lació C
    - `ReportQueue` (endpoint `/statistics/report-queue/`): el percentatge de progrés es quedava sempre a `0%` fins que l'informe acabava de cop, perquè `run_report_task` mai cridava `self.update_state(state='PROGRESS', ...)` durant l'execució (només ho feia `generate_register_billing_summary`). Afegit `task.update_state(...)` cada 50 iteracions al bucle principal de la resta de generadors d'informes (`report_service.py`, `report_billing_service.py`, `report_wallet_service.py`, `report_advanced_billing_service.py`, `report_contract_termination_export_service.py`, `report_wincen_service.py` i `report_service_personalized.py`), aprofitant que `run_report_task` ja detecta automàticament si la funció generadora accepta un paràmetre `task` i li passa la pròpia tasca de Celery

## [03-07-2026]

### FEAT
#### SERVICE

    - Nou endpoint`GET /service/route-position/check_position/?route=<id>&position=<n>` (`RoutePositionViewSet.check_position`) que retorna `{position, occupied}` comprovant amb un simple `.exists()` si una posició concreta ja està ocupada dins una ruta, sense haver de carregar ni paginar totes les posicions de la ruta (necessari per a rutes amb centenars de milers/milions de posicions). Alimenta el nou input numèric de "Ordre de ruta" al frontend.

### CHORE
#### BILLING

    - Al afegir/modificar lectures, ara deixa seleccionar el estimated used o bé bloquejar el seu ús i canviar el origin a mà

#### SERVICE

    - Afegit índex compost`(route, position)` al model `RoutePosition` (migració `0115_routeposition_route_position_index`) perquè la comprovació anterior sigui eficient a gran escala.

### MODIFIED
#### BILLING

    -`create_from_lineitemtype()` (`invoice_line_item_service.py`): el càlcul de `is_first_invoice` ara també considera com a "primera factura" la que ve just després d'una lectura de tall d'una baixa reassignada a un contracte diferent del que es dona de baixa (alta amb `bill_cut_reading` facturant la lectura de la baixa sobre el contracte nou). Abans, en aquest cas, la factura amb la primera lectura real del contracte nou no es prorratejava perquè `previous_reading` pertanyia formalment al mateix contracte. La comprovació exclou explícitament les baixes on el contracte de la `ContractTerminationRequest` coincideix amb el de la lectura, per no afectar baixes pendents/esborrany que continuen facturant amb normalitat sobre el mateix contracte

## [02-07-2026]

### MODIFIED
#### BILLING

    - Corregida la gràfica de consum de la factura (`charts_service.py`): abans es pintava una barra per cada lectura trobada, provocant barres duplicades o mal agrupades quan una facturació tenia més d'una lectura (p. ex. canvi de comptador dins el mateix període). Ara la barra de la factura actual suma totes les seves lectures actives (resolent les lectures de control cap a la seva versió final corregida), i les barres anteriors continuen mostrant l'històric de lectures excloent les ja comptades, per no duplicar-les
    - Afegit un resum superior a l'informe de padró de facturació reduït (`generate_mini_register_billing_summary`) amb el TOTAL M3 de la facturació i el desglossament per tipus d'ús del contracte (DOMESTIC, INDUSTRIAL, MUNICIPAL, AGRICOLA i ALTRES per a la resta de tipus), amb l'etiqueta i el valor en columnes separades
    - Informe WinCen (`wincen_service.py`) convertit en un informe específic de la instal·lació A: desactivat per defecte (`AvailableReport.is_active=False`, cal activar-lo manualment), filtrat perquè només inclogui factures emeses a un únic destinatari (per NIF), excloent pressupostos i pre-factures (només factures finals confirmades), i s'elimina el prefix `FC`/`FF` del número de factura exportat

#### CLAIMREQUEST

    -`VulnerabilityRequestSaveSerializer.update()`: en acceptar una sol·licitud de vulnerabilitat amb un `VulnerabilityRequestType` seleccionat, ara s'apliquen automàticament al contracte les variables i bonificacions configurades al tipus (`variable_types`/`bonification_types`), fent merge amb qualsevol selecció manual sense duplicar-les. Abans, si no es marcaven manualment a la UI, el contracte quedava només com a "vulnerable" sense les bonificacions/variables associades
    - El nivell de vulnerabilitat (`vulnerability_level`) ara es deriva automàticament del `VulnerabilityRequestType` seleccionat quan no s'indica explícitament
    - El camp `duration` del `VulnerabilityRequestType` (fins ara no utilitzat) ara es fa servir per calcular automàticament la data de finalització (`end_at`) quan no s'indica explícitament
    - S'evita duplicar bonificacions/variables ja actives al contracte del mateix tipus en tornar a acceptar una sol·licitud

### FEAT
#### ORDER

    - Nou endpoint`GET /order/order/filter-cities/` (`OrderViewSet.filter_cities`) que retorna el llistat de municipis (id, nom) que realment tenen ordres de treball, aplicant els mateixos filtres que la llista d'ordres (estat, tipus, creador, etc.), per poder alimentar el filtre de "Municipi" del frontend

## [01-07-2026]

### CHORE
#### CONTRACT

    -**Comanda `contract_create_empty_payment`**: Nova comanda de gestió (`python manage.py contract_create_empty_payment`) que recorre els contractes sense `GeneralPayment` (`payment_id IS NULL`) i els hi crea un pagament buit del tipus indicat (`--payment-type`, per defecte id=2 del `contract_paymenttype`). Admet `--dry-run`.

#### DOCS

    - Vista Smart Metering documentada a docs/sql/vw_abonats_aqua360.sql

#### CONTRACT REQUEST

    - Afegit el camp`meter_mode` (real/fictional/none) a ContractRequest per suportar els fluxos de "Comptador fictici" i "Sense comptador"
    - L'endpoint `set-requested-meter-caliber` accepta i desa ara també el `meter_mode`
    - La validació de finalització de la sol·licitud de contracte permet completar sense comptador assignat quan `meter_mode = 'none'`
    - L'endpoint `request-reading` crea el comptador fictici al vol si encara no existeix i el `meter_mode` de la sol·licitud és `fictional`, evitant l'error 404 "Meter not found"

### MODIFIED
#### CLAIMREQUEST

    - S'ha afegit un nom per la gestió de impagats
    - Els filtres de gestió de impagats va millor a com es tracta actualment la vulnerabilitat als contractes. També s'ha afegit una manera de seleccionar contractes en comptes de seleccionar tots individualment
    - Excel sol·licitud de vulnerabilitat s'ha afegit la columna de tipus d'ús i s'ha forçat a fer servir el llenguatge aplicat, no el del navegador

#### READING/SMART METERING

    - Canviar el mètode en fer matech amb els comptadors, de quals a contains, ens podriem trobar que hi ha algún comptador que no té tot el codi complet i li falti alguna lletra (per davant o per darrera)

#### ROUTES

    - Corregit l'assignació de posicions a les rutes (route_serializer.py) per evitar col·lisions amb la restricció unique_together(route, position), processant les posicions en ordre descendent
    - Afegit l'endpoint`move` a RoutePositionViewSet per moure una posició existent dins d'una ruta, desplaçant atòmicament les posicions intermèdies
