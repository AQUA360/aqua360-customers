# Changelog Frontend

## [30-06-2026]

### FEAT
#### CLAIMREQUEST
    - Ara es permet seleccionar quins contractes es vol enviar la sol·licitud de vulnerabilitat
    - Es poden afegir documents (mínim) al pas de vulnerabilitat, exemple respostes de la sol·licitud o semblants
    - Fitxer vulnerables ara fa servir la funció de openAuthenticatedFile

### FIX
#### COREDATA / EMPRESES
- **AddCompanyBanks.vue**: Corregit que el checkbox "És SEPA?" no es marcava en carregar les dades del banc existent. Ara `is_sepa` s'inicialitza correctament des de `props.bank.is_sepa` a `getData()`.

### CHORE
#### SERVICE / GEOLOCALITZACIÓ
- **MapRegion.vue**: El component de mapa ara mostra, per sobre del mapa, l'adreça de l'escomesa i les coordenades (latitud i longitud) quan estan disponibles. S'ha afegit el prop `address` (String) al component.
- **ConnectionRegion.vue, SupplyPointRegion.vue, SupplyCutRegion.vue**: Actualitzats per passar el camp `address_complete` com a prop `:address` al component `MapRegion`.
- **locales/ca.ts i locales/es.ts**: Afegides les claus `address_block.latitude` i `address_block.longitude`.

### MODIFIED
#### READING / LECTURES
- **ReadingEdit.vue**: Afegit tooltip (atribut `title`) als tres botons d'acció de cada fila de lectura: "Enviar comunicació individual" (taronja), "Guardar" (blau fosc) i "Veure/Amagar detall" (blau clar, canvia dinàmicament segons l'estat). S'han afegit les claus de traducció `common.send_individual_communication`, `common.show_detail` i `common.hide_detail` a `locales/ca.ts` i `locales/es.ts`.

#### BILLING
    - Al entrar lectures per fitxer, es guarden les lectures que no s'han pogut trobar. També s'ha canviat el descarregar el fitxer entrat amb la funció openAuthenticatedFile

## [29-06-2026]

### FIX
#### COMPONENTS / PIGGY BANK
- **PiggyBankRegion.vue**: La subregió que mostra `AddPiggyBankBalance` i `ReturnPiggyBankRegion` ara sempre ocupa el 48% de l'amplada (`w-[48%]`), tant per a la vista de persona com per a la de contracte. Abans, en la vista de contracte s'usava `w-[95%]`, ocupant quasi tota la pantalla.
- **ReturnPiggyBankRegion.vue**: La subregió interna que mostra el selector d'IBAN (`PersonBankSelect`) passa de `w-[96%]` a `w-1/2` per evitar que ocupi quasi tota l'amplada de la pàgina.

### CHORE
#### CONTRACT / SOL·LICITUD — DOCUMENTACIÓ
- **ContractDocumentsData.vue**: Afegit camp de text lliure (`doc_text`) al formulari d'afegir documentació. El botó "Afegir" s'activa si hi ha tipus seleccionat i almenys un dels dos camps omplerts (text o fitxer). Els labels indiquen que cada camp és alternatiu a l'altre (`o fitxer` / `o text`). El tipus de document es marca com a obligatori amb `*`.
- **ContractDocumentsData.vue**: El llistat de documents ara mostra tant el fitxer (botó de descàrrega) com el text en una mateixa entrada quan els dos camps estan presents. Les entrades sense fitxer mostren el text en cursiva. Les entrades sense text no mostren cap camp buit.
- **ContractDocumentsData.vue**: Afegit emit `refresh` perquè el component pugui notificar al pare de recarregar les dades quan la resposta de l'API no inclou el contracte complet (cas de text sense fitxer).
- **ContractRequestEdit.vue**: Afegida barra inferior desplegable de Documentació (fixa al fons, respectant l'amplada de la sidebar) que apareix a partir del pas 3 (`currentStep >= 2`). La barra mostra un comptador de documents actius i desplega el component `ContractDocumentsData` en clicar. Utilitza `useSidebarStore` per calcular el `left` dinàmic i afegeix `pb-14` al wrapper quan la barra és visible.
- **ContractRequestEdit.vue** i **ContractRequestDocumentationRegion.vue**: Connectat l'event `@refresh` de `ContractDocumentsData` per recarregar les dades del contracte des del servidor quan cal.
- **contract-request-api.js** i **contract-api.js**: `saveFile` ara té dos camins: si hi ha fitxer, fa `PUT save-file/` amb FormData (comportament existent); si no hi ha fitxer però hi ha text, fa `POST save-documentation/` amb JSON. En cap cas s'envia `file: null` al backend.
- **locales/ca.ts** i **locales/es.ts**: Afegides les claus `common.or_file`, `common.or_text` i `common.file_or_text_required`.

### MODIFIED
#### READINGS / SMART METERING
    - S'han modificat les columnes del quadre de diàleg de comptadors intel·ligents per controlar el titular d'un contracte i s'ha eliminat la ciutat d'adreça del punt de subministrament.

#### COMMUNICATION
    - Al fer una comunicació individual, si selecciones un contracte s'afegeix autom. el tipus de comunicació preferit
    - Al tab de comunicacions de contracte mostra el titol de la comunicació

#### CONTRACT / HISTORIAL DE CANVIS
- **ContractTabs.vue**: La pestanya "Modificacions" ara unifica els dos orígens d'historial de canvis del contracte. S'ha afegit el prop `contract_logs` i el computed `allHistoryEntries` que fusiona `allModifications` (ContractDataChange) amb els logs de camp (ContractLog), ordenats per data descendent. Les entrades de ContractDataChange es mostren amb les targetes existents (`DataChange.vue`), mentre que les entrades de ContractLog es mostren amb un article inline diferenciat (punt gris, `operation_token`, `field_name: old → new`, usuari i data).
- **ContractRegion.vue**: Ara crida `$ContractApiService.getLogs()` en paral·lel amb les altres crides de modificacions (`getMembersChange`). Els logs es passen a `ContractTabs` via el prop `contract_logs` i s'inclouen al comptador de la pestanya. Eliminat l'import de `ContractLogs` i la seva subregió.
- **ContractPinned.vue**: Mateixa adaptació que `ContractRegion.vue`: fetch en paral·lel de `getLogs`, prop `contract_logs` passat a `ContractTabs`, comptador actualitzat i `ContractLogs` eliminat.
- **ContractActionsDropdown.vue**: Eliminada l'opció "Historial de canvis" del menú d'accions, ja que el contingut ara es troba integrat al tab "Modificacions".

## [26-06-2026]

### FIX
#### READING / LOTS DE LECTURES
- **pages/reading/reading-batches/edit/[id].vue**: El títol de la pàgina de detall d'un lot de lectures ara mostra el nom del lot (`batchName`) a continuació del títol genèric (`reading_batch_detail - NOM`). S'ha afegit la variable reactiva `batchName` i s'assigna des del camp `name` de la resposta de `getSummary`.

#### COMPONENTS / FILTRES ADDICIONALS
- **pages/contract/contracts/index.vue, pages/contract/contract-terminations/index.vue, pages/contract/contract-requests/index.vue, pages/contract/follow-contracts/index.vue, pages/order/orders/index.vue, pages/service/connections/index.vue, pages/service/meters/index.vue, pages/service/supplypoints/index.vue, pages/billing/budgets/index.vue, pages/billing/claim-managements/index.vue, pages/billing/invoice/index.vue, pages/billing/joined-payments/index.vue, pages/billing/sepa/index.vue, pages/billing/wallet-managements/index.vue, pages/communication/communications/index.vue, pages/communication/process-communications/index.vue, pages/incident/incidents/index.vue, pages/pricing/price-rates/index.vue**: Eliminat el `mb-2` del `div` contenidor dels filtres addicionals (`v-if="isFilterOpen"`) a totes les pàgines afectades. Aquest marge inferior generava un espai extra tant vertical com horitzontal en activar els filtres avançats, provocant scroll no desitjat a la pàgina.

## [25-06-2026]

### FEAT
#### BILLING / FACTURACIÓ — DOCUMENTS FINALS
- **BillingDocumentsSummary.vue**: Afegit botó "Regenerar PDFs de factures" a la secció de documents finals. En clicar, llança un `POST /billing/billing/{id}/regenerate-pdfs` i inicia un polling cada 2,5 s a `GET /billing/billing/regenerate-pdfs/status/{task_id}/`. El botó mostra el percentatge de progrés en temps real amb el mateix efecte de barra de progrés d'esquerra a dreta que la resta de tasques Celery. En cas d'error canvia a fons vermell amb icona d'advertència.
- **billing-api.js**: Afegits els mètodes `regeneratePdfs(id)` i `checkRegeneratePdfsTask(taskId)` per als nous endpoints de regeneració de PDFs.
- **locales/ca.ts i locales/es.ts**: Afegides les claus `billing_block.regenerate_pdfs` i `billing_block.confirm_regenerate_pdfs`.

#### READING / LOTS DE LECTURES
- **ReadingBatchSummary.vue**: Afegida selecció de lectures per files (checkbox per cada fila) al panell de detall de lectures d'un lot. Les files seleccionades es destaquen amb fons `bg-amber-50`.
- **ReadingBatchSummary.vue**: Afegida barra d'accions per sobre de la capçalera de la taula de lectures. Mostra el comptador de files seleccionades i un botó taronja "Recalcular estimades" que **només apareix quan alguna de les lectures seleccionades és estimada** (`is_estimated = true`). Si hi ha seleccionades però cap és estimada, mostra un missatge explicatiu. Quan no hi ha res seleccionat, mostra un hint en gris *"Selecciona lectures per recalcular les estimades"*.
- **ReadingEdit.vue**: Afegida prop `selected` (Boolean) i emit `toggle-select` per integrar-se amb la selecció del pare. Fons de la fila `bg-amber-50` quan `selected = true`.
- **reading-api.js**: Afegit mètode `recalculateEstimatedReadings(reading_ids)` que crida `POST /billing/reading/recalculate-estimated/` amb `{ reading_ids: [...] }`. Retorna les lectures actualitzades que es fusionen localment a `showReadings` sense recarregar tota la pàgina.
- **locales/ca.ts i locales/es.ts**: Afegides les claus `billing_block.recalculate_estimated_readings`, `billing_block.correct_recalculate_estimated`, `billing_block.error_recalculate_estimated`, `billing_block.checkbox_recalculate_hint` i `billing_block.select_estimated_to_recalculate`.

### FIX
#### COMPONENTS / DOCUMENTS
- **DocumentList.vue**: Corregit un `ReferenceError: today_date_string is not defined` que petava en intentar descarregar documents en ZIP. La variable s'usava al nom del fitxer descarregat però no estava declarada al component (copy-paste incomplet). Ara s'inicialitza localment com la data ISO del dia en muntar el component.
- **DocumentList.vue**: Corregit que qualsevol clic dins del llistat de documents tancava la region pare. Causa: els botons sense `type="button"` actuaven com a `submit` si hi havia un `<form>` ancestre, i els events de clic pujaven cap al listener de tancament del pare. Solució: afegit `type="button"` als tres botons del component i `@click.stop` al contenidor arrel.
- **CommunicationRegion.vue**: Afegit `@click.stop` al `div` arrel de la region per evitar que qualsevol clic intern propagui cap al pare i tanqui la region inesperadament.

#### STATISTICS / ANALYSIS
- **pages/statistics/analysis/index.vue**: Els botons "Recàlcul de Consums Diaris" i "Backfill de Factures sense dades de consum" ara mostren el percentatge de progrés de la tasca Celery directament dins del botó mentre s'executa. El fons del botó es va omplint d'esquerra a dreta (efecte barra de progrés) amb una capa `bg-white/20` animada. El polling (cada 2 s) s'inicia en rebre el `task_id` i s'atura automàticament en navegar fora de la pàgina (`onUnmounted`). L'altre botó queda deshabilitat mentre una tasca és activa. En finalitzar, es refresca el resum de consums i es restaura l'estat normal dels botons.

### CHORE
#### COMPONENTS / OBSERVACIONS
- **InputTextarea.vue**: Redissenyat l'estil del camp de text d'observacions. El `textarea` ara té vores arrodonides, fons blanc, focus amb anell `sky-400` i més contrast visual. El botó "Enter" s'ha substituït per un botó "Registrar" amb icona de paper d'enviament, alineat a la dreta, amb estil prominent (`bg-sky-500`). S'ha afegit la clau de traducció `common.register` a `locales/ca.ts` i `locales/es.ts`.

#### BILLING / LLISTAT DE FACTURES (BillingSummary)
- **BillingSummary.vue + InvoiceEdit.vue**: Afegida la columna "Tipus d'ús" (`use_type_final`) a la taula de factures. Les columnes "Adreça de facturació" i "Localització" s'han eliminat de la vista principal i mogut a un popover informatiu accessible passant el cursor per sobre del nou botó (ℹ) a la columna d'accions. El popover usa `<Teleport to="body">` i posicionament `fixed` per evitar que quedi retallat pel contenidor `overflow-y-auto`.
- **InvoiceEdit.vue**: La columna d'accions s'ha ampliat a `260px` per encabir el nou botó d'informació. Tots els paddings de les cel·les uniformitzats a `p-3`.
- **BillingSummary.vue**: Capçalera de la taula actualitzada a 9 columnes (`grid-cols-[40px,1.5fr,1fr,1fr,1fr,1fr,1fr,100px,260px]`), sense `divide-x` i amb `items-center bg-slate-50` per alinear-se correctament amb les files.

## [23-06-2026]

### FEAT
#### SERVICE
    - Comptador al seleccionar telelectura es permet seleccionar tipus (smart metering o agbar)
    - Es permet filtrar comptador per telelectura o històric i per tipus de telelectura

#### SMART METERING
    - Fer el visalitzador de les dsdes obtngudes de l'smart matering des del lot de lectures + guardar les dades de l'smart metering al comptador corresponent

### FIX
#### SUPPLY POINT
- **SupplyPointEdit.vue**: En mode edició, els selects de tipus (`type`), origen (`source`), tipus de subministrament (`supply_type`) i emplaçament (`placement`) ara es preseleccionen automàticament amb el valor que retorna el backend. Si el backend retorna `null` o buit, el camp queda en blanc en lloc de seleccionar el primer element per defecte. El camp `placement` s'identifica per ID directe (no objecte), mentre que la resta es cerquen per `id` o `name` dins l'objecte retornat.

#### COMMUNICATION
    - Carregar un esborrany de fuites no s'havia canviat encara per celery i petav

### CHORE
#### REPORTS
- **add.vue / index.vue**: Integrat el front-end amb el nou sistema de cua de reports (`report_queue`) de back-end. S'ha afegit un mapa reactiu `activeReportsStatus` i un mecanisme de consulta periòdica (polling) a `/api/statistics/report-queue/<queue_item_id>/` cada 3 segons mentre s'estigui en estat `pending` o `running`.
- **add.vue / index.vue**: Afegit suport per descarregar fitxers generats mitjançant el document manager (`$DocumentManagerApiService.viewDocument`) en els casos en què `document_url` sigui null però es disposi de `document_id`.

### MODIFIED
#### SMART METERING/READINGS
    - Ocultar el boto de SmartMetering als clients que no tinguin token de Samrt Metering + modificar les columnes del quadre de dialeg de les lectures de l'smart metering i treure el holder

#### REPORTS
- **add.vue / GenericReportForm.vue / AcaReportForm.vue / RatesReportForm.vue**: Refactoritzada la visualització de càrrega i progrés perquè només es mostri de forma inline durant els estats `pending` i `running`. Un cop finalitzat o fallit, es restitueix el disseny i el comportament original dels botons de trigger de descàrrega/generació.
- **index.vue**: Actualitzada la columna "Data de creació" per a mostrar la data i l'hora utilitzant `formatDateTime`. Eliminat el valor de fallback `common.no_name` a la columna de nom de l'informe, deixant-la buida/en blanc quan no està definit.

#### ORDER
- **order-api.js**: Habilitat de nou el filtratge automàtic per explotació a la crida de cerca d'ordres (`&exploitation=...`).

#### CONTRACT / TERMINATIONS
- **ContractTerminationDetail.vue / ContractTerminationEdit.vue**: Corregida la visualització i càrrega de la lectura de baixa per a extreure correctament el valor reactiu (`reading?.value` / `reading_value`) en lloc de tractar-ho com a objecte de lectura complet.
- **locales/ca.ts i locales/es.ts**: Actualitzada la clau de traducció per a descriure la lectura de baixa com a "Lectura final / baixa".

## [22-06-2026]

### CHORE
#### READING / LOTS DE LECTURES
    - **ReadingBatchSummary.vue**: Afegit un bloc informatiu al pas 4 (Resum/Finalització) del wizard de lots de lectura que mostra la mateixa taula de comptadors que el pas 3 ("Lectures assignades"). La taula es mostra a la columna dreta, al costat del resum de lectures processades, i inclou: total lectures assignades, alertes del lector, alertes de telelectura, lectures sense valor, lectures sobrants, telelectures, lectures amb punt de subministrament inactiu, punts sense ruta i subministraments sense lectura.
    - **ReadingBatchSummary.vue**: Cada fila de la taula de "Lectures assignades" amb valor > 0 incorpora un eye icon (hover) que obre un panell lateral de només lectura amb el llistat de lectures corresponents filtrades per aquell grup. La taula de lectura mostra: Contracte, Titular, Punt de subministrament, Última lectura i Data última lectura. Sense opcions d'edició ni estimació.
    - **ReadingBatchEdit.vue**: Passa el prop `counters_pending` (dades del pas 3) al component `ReadingBatchSummary` per disposar de la informació de lectures al pas final.

### MODIFIED
#### COMMUNICATION
    - Cerca canviada a celery. Casos amb moltes factures peta igual

#### READING / LOTS DE LECTURES
    - **ReadingBatchSummary.vue**: Reestructurat el layout del pas 4 a dues columnes (`grid-cols-2`), igual que `BillingSummary.vue`. Columna esquerra: resum de lectures processades (com a `<ul>` unificada en lloc de bombolles separades). Columna dreta: botó d'exportació + bloc de lectures assignades del pas 3.
    - **ReadingBatchSummary.vue**: El total de "Lectures assignades" suma `assigned_readings + already_billed` per reflectir correctament el recompte un cop el lot ha estat processat (el backend mou les lectures de `assigned_readings` a `already_billed` en finalitzar el processament).
    - **ReadingBatchSummary.vue**: Si el prop `counters_pending` no arriba via pare (accés directe al pas 4), el component crida automàticament `GET /billing/reading-batch-summary?batch_id={id}` per carregar les dades de lectures assignades.
    - **ReadingBatchSummary.vue**: Augmentat el z-index de la sub-regió de detall (contracte, punt de subministrament, etc.) de `z-30` a `z-50` perquè es mostri per sobre del panell lateral de lectures assignades (`z-40`).

## [19-06-2026]

### FEAT
#### BILLING
    - **BillingSummary.vue**: Afegida una nova secció d'avís (banner ambre) a sobre del panell de "Possibles contractes no facturats". Si existeixen alertes de consum relacionades amb la facturació en curs, es mostra el recompte i, en clicar, s'obre un panell lateral intern amb el detall complet.
    - **ConsumptionAlertsDetail.vue** (nou component): Panell lateral que mostra les alertes de consum filtrades per `billing_batch`. Inclou la taula d'alertes (tipus, contracte, titular, punt de subministrament, consum, dates) amb scroll infinit, i permet obrir el detall del contracte en un sub-panell (`ContractRegion`).
    - **consumption-management/index.vue**: A la pestanya "Historial" s'ha afegit un filtre de facturació (desplegable amb totes les facturacions existents). En seleccionar una facturació, les dades es filtren per `billing_batch`. El filtre es carrega automàticament en canviar a la pestanya d'historial i es neteja en restablir filtres o canviar de pestanya.
    - **consumption-management-api.js**: Afegit el paràmetre `billingBatch` a `getAll()`. Si s'envia, afegeix `&billing_batch=ID` a la petició i omet el paràmetre `mode` (tal com indica el backend: els dos filtres s'exclouen mútuament).
    - **locales/ca.ts i locales/es.ts**: Afegida la clau `billing_block.consumption_alerts_warning` amb el text d'avís en català i castellà.

#### SERVICE / CONNECTIONS
    - **ConnectionRegion.vue**: Afegida pestanya "Docs" al costat d'Observacions al detall d'una escomesa. Mostra un comptador de documents actius i permet pujar, visualitzar i eliminar fitxers associats a l'escomesa.
    - **ConnectionDocumentsData.vue** (nou component): Component de gestió de documents de connexions, equivalent al `ContractDocumentsData.vue`. Permet seleccionar el tipus de document (des de l'endpoint `GET /api/service/connection-documentation-type/`), pujar un fitxer via `PUT /api/service/connection/{id}/save-file/`, descarregar documents existents i eliminar-los. El llistat de documents prové del camp `documentation_files` del serialitzador complet de `Connection`.
    - **connection-api.js**: Afegit mètode `saveFile()` que crida `PUT /api/service/connection/{id}/save-file/` amb `multipart/form-data` (camps: `file`, `id`, `connection_type`).

#### SERVICE / CLUSTERS (BATERIES)
    - **ClusterRegion.vue**: Afegida pestanya "Docs" al costat d'Observacions al detall d'una bateria. Mostra un comptador de documents actius i permet pujar, visualitzar i eliminar fitxers associats a la bateria.
    - **ClusterDocumentsData.vue** (nou component): Component de gestió de documents de bateries, equivalent al `ConnectionDocumentsData.vue`. Utilitza `service/cluster-documentation-type` per als tipus i `PUT /api/service/cluster/{id}/save-file/` per pujar fitxers.
    - **cluster-api.js**: Afegit mètode `saveFile()` que crida `PUT /api/service/cluster/{id}/save-file/` amb `multipart/form-data` (camps: `file`, `id`, `cluster_type`).

### CHORE
#### SETTINGS
    - **settings/index.vue**: Afegides dues entrades noves a la secció de Servei: "Escomeses: Documentació" (`service/connection-documentation-type`) i "Bateries: Documentació" (`service/cluster-documentation-type`).

### MODIFIED
    - ClaimRequestEdit, paginat, millorat i amb cerca manual per evitar trepitjar-se mentre s'agafen els contractes que toquen. Cerca passada a celery

## [18-06-2026]

### FEAT
#### CONSUMPTION MANAGEMENT
    - **Pestanyes d'alertes actuals i historial**: S'han afegit dues pestanyes ("Alertes actuals" i "Historial") a la vista de gestió d'alertes de consum per alternar entre els dos modes. En canviar de mode es reinicien els filtres, cerca i paginació automàticament.
    - S'han afegit les traduccions de les noves pestanyes (`tab_current` i `tab_history`) en català i castellà.

### MODIFIED
#### SERVICE / ROUTES
    - **RouteEdit.vue**: Optimitzada la gestió de posicions després de desar. Eliminades les crides a `findPositionPage` (que recorria totes les pàgines del backend fins trobar la posició guardada, provocant una recàrrega lenta de tot el llistat). Ara, si la posició editada o nova cau dins del rang ja carregat, s'insereix localment i s'ordena sense cap petició addicional; si queda fora del rang visible, s'ignorar i apareixerà de forma natural quan l'usuari faci scroll fins aquella posició.
    - **RouteEdit.vue**: El scroll automàtic cap a la posició guardada ara comprova si l'element ja és visible al viewport del contenidor abans de fer `scrollIntoView`, evitant desplaçaments innecessaris. L'efecte de ressaltat groc es continua aplicant sempre independentment del scroll.
    - **AddRoutePosition.vue, AddProperties.vue**: Corregits els scrollbars dobles a la subregió de finques. El contenidor de la subregió ja no genera el seu propi scroll; `AddProperties` accepta la nova prop `fitContainer` que, quan és `true`, adapta l'alçada i l'amplada del llistat al contenidor pare en lloc d'usar alçades fixes basades en `100vh`.

#### BILLING
    - **AddInvoiceBudget.vue**: Afegida la reactivitat de `paymentTypeOptionsById` al `watch` per actualitzar correctament l'objecte `paymentData` en generar un pressupost.

#### CONSUMPTION MANAGEMENT
    - **Renombrat a "Alertes de consums"**: S'ha canviat el títol i l'etiqueta del menú lateral de "Gestió de consums" a "Alertes de consums" a `ca.ts` i `es.ts`.
    - **consumption-management-api.js**: S'ha adaptat el mètode `getAll` per passar el paràmetre `mode` (`current` o `history`) a la petició de l'API.

## [17-06-2026]

### FEAT
#### CONSUMPTION MANAGEMENT
    - **Nova secció "Gestió de consums"**: S'ha creat una nova pàgina (`pages/consumption-management/index.vue`) accessible des del menú lateral sota "Gestió de fraus". Mostra una taula paginada amb tres tipus d'anomalies de consum identificades amb un badge de color: boques d'incendi amb consum (`fire_hydrant`, vermell), contractes de baixa amb consum (`inactive_consumption`, taronja) i contractes amb lectures duplicades en el mateix període (`duplicate_readings`, groc). Inclou cerca de text, filtre per tipus (checkboxes), ordenació per columnes i obertura del detall del contracte en un panell lateral (`ContractRegion`) sense abandonar la pàgina.
    - **consumption-management-api.js**: Nou servei d'API (`$ConsumptionManagementApiService`) per a l'endpoint `GET /contract/consumption-management/`, amb suport de cerca, filtre per `type`, paginació, ordenació i filtre per explotació del `localStorage`. Registrat a `nuxt.config.ts`.
    - **NavSidebar.vue**: Afegida l'entrada "Gestió de consums" (icona `fa6-solid:droplet`) al menú de servei, a sota de "Gestió de fraus".
    - **locales/ca.ts i locales/es.ts**: Afegida la clau `consumption_mngs` al namespace `common` i el bloc `consumption_management` amb el títol de la pàgina, les etiquetes de columna i les traduccions dels tres tipus d'anomalia.

### FIX
#### CONTRACT / ADDRESS
    - **ContractRequestAddressPayment.vue**: Corregit un error on es creava un registre `PersonAddress` duplicat quan l'adreça del punt de subministrament ja estava associada al titular. Ara es verifica si l'adreça ja existeix i, en cas afirmatiu, es reutilitza l'ID existent sense crear un nou registre. A més, s'ha eliminat la condició `addressOptionsAreEmpty` del criteri d'auto-assignació d'adreça perquè l'assignació es pugui produir tot i que ja hi hagi adreces disponibles.

#### ORDER
    - **order-api.js**: Deshabilitat temporalment el filtratge automàtic per explotació a la crida de cerca (el paràmetre `&exploitation=...` s'ha comentat).

### CHORE
#### ADDRESS / STREETS
    - **pages/service/streets/index.vue**: S'ha afegit un filtre per municipi a la pàgina de carrers. El llistat de municipis es carrega filtrant els que tenen carrers associats (`has_streets`), ordenant primer els del municipi de l'explotació activa i la resta alfabèticament. El filtre s'integra amb el paginador i el buscador de text, i es reinicia al restablir els filtres. S'ha afegit el component `FilterSelect` per al selector de municipi i un `watch` sobre `selectedCity` per recarregar el llistat automàticament.
    - **locales/ca.ts i locales/es.ts**: Afegida la clau de traducció `select_city` (`Selecciona ciutat` / `Selecciona ciudad`) per al filtre de municipis.

### MODIFIED
#### ADDRESS / STREETS
    - **AddAddress.vue, AddPartialAddress.vue, LocationSearch.vue**: La cerca de carrers ara passa el codi/ID del municipi seleccionat com a paràmetre a `$StreetApiService.getAll`, filtrant els resultats per la població triada.
    - **plugins/api/coredata/address-api.js**: Afegit el paràmetre opcional `hasStreets` a la funció `getCities()` per poder filtrar municipis que tinguin carrers associats (`&has_streets=true/false`).

## [16-06-2026]

### FEAT
#### BILLING
    - **Cua seqüencial de facturació**: S'ha implementat un panell d'estat de la cua a `BillingEdit.vue` dividit en dues seccions desplegables: una per als processos actius/pendents amb barra de progrés real, i una altra per a l'historial d'últims processos finalitzats (amb estat de la tasca, data de finalització i possibles errors del backend).
    - S'han definit traduccions específiques (`ca.ts` i `es.ts`) per a tots els estats, títols i botons desplegables de la cua.

### MODIFIED
#### BILLING
    - **Optimització de polling i bloquejos**: S'ha adaptat `BillingSummary.vue` i `BillingDocumentsSummary.vue` per aturar el polling a l'endpoint de detall `/billing/billing-queue/<queue_item_id>/` de forma immediata en assolir el $100\%$ de progrés o completar-se el procés, allargant l'interval de consultes a 5 segons.
    - S'ha corregit el bloqueig de la interfície de facturació perquè el botó de següent del Pas 0 no es bloquegi mai i es puguin encolar noves tasques, i perquè els bloquejos de botons dels passos següents només s'apliquin quan hi hagi un procés actiu corresponent al lot seleccionat (evitant el bloqueig creuat per tasques d'altres lots).

#### NAVIGATION / SIDEBAR
    - **NavSidebar.vue**: S'ha eliminat la selecció i assignació automàtica de l'explotació al `localStorage` quan l'usuari només té accés a una única explotació. Això permet que l'explotació es mantingui correctament deseleccionada al `localStorage` si l'usuari decideix deseleccionar-la, tot i que se'n segueixin mostrant els detalls visuals a la barra lateral.

#### ORDER
    - **order-api.js**: S'ha adaptat la crida a l'endpoint de cerca d'ordres perquè, si no hi ha cap explotació seleccionada al `localStorage`, la petició es realitzi correctament sense incloure el paràmetre d'explotació a la URL.

## [15-06-2026]

### FIX
#### BILLING
    - **AddBillingRange.vue**: Corregit l'error que impedia desar un nou interval de facturació quan es clicava "Guardar" a causa d'un error d'accés a `props.br_id.value` (canviat a `props.br_id`). S'han fet opcionals els camps de data de fi (`endDate`) i publicació (`selectedPublication`), i s'ha implementat un avís toast (`common.required_fields`) quan algun dels camps obligatoris no s'omple.

### CHORE
#### BILLING
    - S'ha afegit un comentari/observació pel pressupost

### MODIFIED
#### CLAIMREQUEST
    - Vulnerabilitat ara s'assigna només al titular (o llogater en cas d'haver-hi i tenir un titular juridic) i les variables i bonificacions s'assignen automàticament amb un tipus que es pot configurar

## [12-06-2026]

### FIX
#### CONTRACT
    - data-change.vue: Corregit un error on la llista de representants seleccionats no es mostrava correctament en carregar la pàgina de modificació de dades. S'ha afegit la càrrega inicial dels tipus de representants (`fetchRepresentativeType()`) al hook `onMounted` i s'ha assegurat l'assignació de la referència correcta de l'objecte tipus trobat per enllaçar-se adequadament amb el selector del formulari.

#### PERSON
    - PersonAddressSelect.vue, PersonContactSelect.vue, BankSelect.vue: S'ha corregit un error on no es mostrava el nom de la persona als blocs de selecció (mostrant "—" o quedant buit). S'ha implementat la funció `getPersonDisplayName` per resoldre correctament el nom combinant `name` i `surname` o usant el nom de l'entitat jurídica/token quan la propietat `full_name` no està definida directament.

### CHORE
#### SERVICE
    - ConnectionEdit.vue: S'ha obligat a seleccionar una explotació per a noves escomeses (mostrant un avís en format toast en cas contrari), a més d'auto-seleccionar l'explotació activa de la sessió. S'ha implementat també una alerta visual quan el municipi de la localització triada no coincideix amb els de l'explotació. S'han afegit les claus de traducció associades a `ca.ts` i `es.ts`.

### MODIFIED
#### BILLING
    - **Gestió de remeses SEPA**: S'ha adaptat la llista de pagaments (`SEPAPaymentsList.vue`) perquè en excloure es demani confirmació amb `confirm()`, però en incloure s'afegeixi directament sense avís. S'han afegit els botons "Incloure tots" i "Excloure tots" per interactuar amb la nova api d'exclusió/inclusió massiva segons els filtres del cercador per a totes les pàgines. A `SEPAManagementEdit.vue` i `SEPAManagementSummary.vue` s'ha corregit un error de concatenació de cadenes de text (`parseFloat`) al total de l'import i s'ha assegurat que la barra de resum mantingui el total de factures seleccionades intacte, actualitzant només el total d'exclosos i l'import sumat. S'ha definit la funció `bulkExcludeSEPAInvoices` a `payment-api.js` i afegit la traducció `include_all` a `ca.ts` i `es.ts`.

## [11-06-2026]

### FEAT
#### BILLING
    - MissingContractsDetail.vue: S'han afegit botons d'acció dinàmics per a cada contracte sense facturar segons el seu estat de lectura o lots ("Afegir lectura estimada", "Afegir al lot", i "Processar").
    - MissingContractsDetail.vue: S'ha afegit un botó a la part superior per poder processar massivament tots els contractes seleccionats de forma asíncrona a través d'una tasca de Celery de back-end.
    - S'ha implementat una pantalla de bloqueig visual amb una barra de progrés que immobilitza el panell lateral i mostra el percentatge de progrés de la tasca en segon pla (Celery) fent servir `$apiManager.checkTask` fins que finalitza correctament.
    - locales/ca.ts i locales/es.ts: S'han afegit les traduccions corresponents per als nous botons, missatges de confirmació d'èxit i el motiu de manca de comptador (`cause_no_meter`).

### FIX
#### COMMUNICATION
    - CommunicationDetail.vue i CommunicationRegion.vue: S'ha corregit un error on no s'actualitzava o no desapareixia el missatge d'error de rebuig de la comunicació quan aquesta fallava i després es tornava a llançar/enviar correctament. S'ha implementat un observador (`watch`) per propagar els canvis del prop `data` cap a la variable reactiva local `localData` de detall, i s'ha configurat la recàrrega automàtica de dades amb `getData(false)` i l'emissió de l'esdeveniment `changed` en completar amb èxit l'enviament des de `sendComm`.

### MODIFIED
#### BILLING
    - BillingSummary.vue: S'ha adaptat la funció de recàrrega perquè actualitzi els llistats de factures, els comptadors generals i la llista de contractes no facturats directament sense tancar el panell lateral en completar una acció de modificació.
    - MissingContractsDetail.vue: S'ha afegit la desestructuració del servei `$apiManager` de `useNuxtApp()` per admetre el sondeig periòdic de les tasques Celery.
    - MissingContractsDetail.vue: S'ha configurat la detecció de la manca de comptador (`no_meter`) a la llista de motius pendents, desactivant els botons d'acció individuals i la selecció en els checkboxes de processament massiu.

#### CONTRACT
    - ContractActionsDropdown.vue: S'ha afegit que si el contracte no té punt de subministrament per defecte (`supply_point_default`) i/o no té comptador associat, no es permeti modificar les lectures (deshabilitant l'opció "Modificar lectures" al menú d'accions).

## [10-06-2026]

### FIX
#### CONTRACT
    - ContractRequestEdit.vue i ContractRequestTermination.vue: S'han assignat claus (`key`) úniques a les seccions i pestanyes de renderitzat condicional dels passos per evitar errors de Virtual DOM (`TypeError: Cannot set properties of null (setting '__vnode')`) al tancar la regió lateral d'edició.

### CHORE
#### CONTRACT
    - S'ha afegit una validació al pas 7 (Finalització) per bloquejar la finalització d'una sol·licitud de contracte si algun dels punts de subministrament amb comptador existent no té registrada la lectura inicial (en cas de comptador nou, es mostra només un avís de warning sense bloquejar la finalització). Qualsevol error o avís de validació relacionat amb lectures redirigeix correctament a l'usuari cap al pas 6 ("Situació actual").
    - S'han afegit les traduccions corresponents a la manca de lectura inicial del nou contracte (`warning_missing_initial_reading`).
    - S'ha afegit el filtre de "Contracte no facturable" (`block_billing`) com a opció de filtre addicional, integrant-se amb la persistència del `sessionStorage` i les peticions d'exportació de dades.

#### COMMUNICATION
    - S'ha afegit un botó d'exportació a CSV que propaga els filtres actius del llistat de comunicacions a través de l'endpoint de xarxa dedicat.
    - S'ha afegit el filtre de rang de dates ("Data") a la secció de filtres opcionals (`filtersExtra`) de la graella de comunicacions.

### MODIFIED
#### CONTRACT
    - ContractRequestTermination.vue: S'ha mogut el bloc de la lectura inicial fora del panell plegable (detalls) per fer-lo directament visible i s'ha embolicat en un disseny de targeta (card) més clar, retolant-lo de forma explícita com a "Lectura inicial del nou contracte" (`initial_reading_new_contract`).
    - MissingReadingEdit.vue: S'ha adaptat el mètode d'estimació perquè utilitzi la data de lectura seleccionada a la casella de calendari reactiva en lloc d'utilitzar sempre la data per defecte del lot.

#### COMMUNICATION
    - index.vue (communications): S'ha adaptat l'estructura de dades de la selecció de data amb `selectedDateRangeArr` i `date_range` per ser coherent amb el format utilitzat a la resta d'apartats de l'aplicació.
    - FilterSelect.vue: S'ha implementat el reset automàtic del valor de rang de dates en el botó quan es reinicien o es buiden els filtres.

## [09-06-2026]

### FIX
#### NAVIGATION / DETAILS
    - contract/contracts, billing/invoice, service/properties, service/supplypoints, billing/billing: S'ha corregit un error que provocava la pèrdua de l'ID a la URL del navegador quan es clicava de nou sobre el mateix element per a forçar la recàrrega de la regió lateral. S'ha introduït el paràmetre `isReload` a la funció `toggleRegion` per evitar que s'executi l'eliminació del paràmetre de consulta (`id`) en realitzar aquesta acció de recàrrega temporal.

### MODIFIED
#### BILLING
    - S'ha afegit l'opció de deixar seleccionar entre titular, propietari o llogater per pagar un compromís de pagament

#### COREDATA
    - Persona ara modifica el expedient de l'any actual i permet consultar els expedients d'anys anteriors

#### SERVICE
    - Ara a empresa es pot afegir X correus per diferents tipus de comunicacions.

#### COMMUNICATION
    - Obligatori seleccionar ara el correu electronic amb la configuració de l'empresa al crear comunicaicons

## [08-06-2026]

### FEAT
#### BILLING
    - S'ha afegit una pàgina nova per les devolucions SEPA, a on podrem consultar els pagaments retornats, el fitxer i el total
    - S'ha afegit l'opció de descarregar massivament factures des de contracte (person en procés per falta de dades)

### FIX
#### BILLING
    - components/molecules/AddInvoiceBudget.vue: En fer una refactura, s'assegura que el pressupost generat inclogui el token de la factura original (clau `invoice_token` dins de `redoOption`) perquè s'estableixi correctament la vinculació i s'assigni la sèrie de refactura amb el prefix "FF". A més, es realitza una crida asíncrona dedicada (`getInvoicesFromContract`) per obtenir les factures en lloc de rely on `data.invoices` del contracte, evitant penalitzacions de rendiment a l'endpoint general del detall de contracte.

#### ADDRESS
    - components/molecules/AddAddress.vue: S'ha forçat la crida asíncrona a `getCities` en assignar valors i en establir la població per defecte de l'explotació, assegurant que el llistat de municipis es carregui sempre correctament i es mostri el municipi seleccionat.

#### CONTRACT
    - components/organisms/ContractTerminationEdit.vue: S'ha corregit un error de tipus (`TypeError: Cannot read properties of undefined (reading 'contract')`) en el formulari de baixa de contractes. S'ha implementat encadenament opcional (`request?.contract?.token`, `request?.connection` i `props.request?.id`) a la plantilla i s'ha afegit una comprovació de seguretat al mètode `getSupplyPoint` perquè no s'executi quan el component es troba en mode de creació (sense un objecte `request` definit).

### CHORE
#### PERSON
    - S'ha afegit factures a la region de persona i poder descarregar massivament factures

#### LINE ITEM TYPE:
    - S'ha afegit que es pugui veure el token a la component LineItemTypeEdit

#### INCIDENTS
    - index.vue (incidents): S'ha afegit el botó d'exportació d'incidències per a descarregar l'estat actual en format Excel a través d'una tasca asíncrona amb polling.

### MODIFIED
#### ADDRESS / CITIES
    - components/molecules/AddCities.vue: S'han ajustat les amplades de les columnes de la llista de poblacions (`120px` per a la identificació/token, `3fr` per al nom, `1.5fr` per a la província i `1fr` per al país) per millorar la visualització. A més, s'ha aplicat truncat de text (`truncate`) i s'ha afegit l'atribut `title` per mostrar el text complet en fer hover.

#### REPORTS
    - add.vue (reports): S'ha actualitzat `customFuncs` amb `'incident_response_time'` i `'incident_response_time_report'` per a donar suport correcte al configurador de filtres en l'informe "Temps de resposta a reclamacions".

#### INCIDENTS API
    - incident-api.js: Afegit el mètode `exportExcel` per a fer la petició de trigger d'exportació d'incidències asíncrona al backend.

## [05-06-2026]

### FIX
#### NAVIGATION
    - contract/contracts, billing/invoice, service/properties, service/supplypoints: S'ha implementat la sincronització bidireccional del paràmetre `id` de la URL al consultar el detall de contractes, factures, propietats i punts de subministrament. Quan s'accedeix via URL directa (`?id=xxx`) s'obre automàticament el detall corresponent. En clicar un altre element de la taula s'actualitza la query conservant la ruta exacta (`path: route.path`), i en tancar la regió s'elimina el paràmetre de manera neta amb `nextTick`. S'han corregit les fallades de tipus (estricte `===` entre string i number) que impedien el correcte funcionament de les condicions de guarda, i s'han reordenat les variables reactives (`selectedItemId` i `isSubRegionOpen`) a l'inici dels scripts setup per evitar errors de referència i accessos abans de la seva inicialització (Error 500 en SSR).
    - ContractRequestSetup.vue: S'ha resolt el problema de vinculació (objecte vs ID) al desplegable de "Tipus de contractació" (`selectedType`) i s'ha forçat l'espera asíncrona de la llista de tipus a `onMounted` perquè s'actualitzi correctament en seleccionar el punt de subministrament.
    - ContractRequestEdit.vue: S'ha evitat l'error del backend (crash 500 de Django per assignar una llista de diccionaris al set del ManyToMany de `price_rates_ids` en la creació) separant el desat de les tarifes en un `PUT` posterior una vegada obtingut l'ID.

#### CONTRACT
    - contractDataChangeDisplay: Verificar que no es null el nom del payment anterior, petava al generar els pressupostos.

### CHORE
#### CONTRACT
    - ContractRequestSetup.vue, ContractRequestEdit.vue: Implementada la càrrega de dades per defecte de l'últim contracte (actiu o de baixa) en seleccionar un punt de subministrament (tipus de contractació, tipus d'ús, categoria, tipus de client, tipus de deute i tarifes de preus).

#### BILLING / INVOICES
    - invoice/index.vue, invoice-api.js: S'ha afegit l'opció de filtratge per línies de factura (lineitem) a la barra de cerca de la llista de factures. S'ha integrat un nou camp de text amb la icona de document amb línies (`fa6-solid:file-lines`) que propaga el terme de cerca asíncron cap al paràmetre `line_item` del backend.
    - locales/ca.ts, locales/es.ts: Afegides les traduccions del placeholder de cerca de línia de factura en català i castellà.

### MODIFIED
#### SERVICE / METERS
    - pages/service/meters/index.vue: S'han adaptat i ajustat les amplades de les columnes de la graella de comptadors per evitar la superposició de la columna d'estat amb la de data d'instal·lació, comprimint la columna d'explotació i la de l'adreça (punt de subministrament). En aquesta última, s'ha aplicat truncat de text amb punts suspensius i visualització completa del text en passar el cursor per sobre (tooltip/title).
    - components/organisms/MeterRegion.vue: S'ha habilitat i posat en funcionament la pestanya d'historial de modificacions (historial de canvis) del comptador integrant el component `ModelLogs` amb el servei `$MeterApiService`.

#### COMPONENTS / PAGES
    - components/atoms/DelinquencyLevel.vue: S'ha eliminat el semàfor i ara es mostra el valor del deute de la persona.
    - components/molecules/ContractRequestSetup.vue: S'ha canviat el nom "Morositat" per "Deute" a la taula de sol·licitants.
    - pages/contract/persons/index.vue: S'ha canviat el nom "Morós" per "Deute" i ara es mostra el valor del deute de la persona.

## [04-06-2026]

### CHORE
#### BILLING
    - S'ha afegit justificant de pagament al pagament agrupat

### FEAT
#### COREDATA
    - Afegit a person el 'expedient' per factura electrònica

### MODIFIED
#### BILLING
    - ReadingBatchRegion.vue: Migrada l'exportació de lectures del lot (CSV) cap a un procés asíncron amb polling. Ara el frontal rep el `task_id`, consulta periòdicament el progrés (cada 2 segons) mitjançant `$apiManager.checkTask` mostrant el percentatge de càrrega sobre el botó d'exportació, i descarrega automàticament el fitxer un cop l'estat passa a ser exitós (`SUCCESS`).

#### OTHERS/AUTH FILE
    - S'ha modificat open-authenticated-file per permetre descarregar directament fitxers amb url que no són pdf (un -zip per exemple)

#### PRICING
    - BillingRangeEdit.vue: S'ha afegit el camp `id` a les dades passades al mètode `save` per a la modificació d'intervals de facturació. D'aquesta manera, el servei d'API realitza correctament una petició `PUT` a `/pricing/billing-range/{id}/` en comptes d'una petició `POST` (la qual creava un duplicat de l'interval).

#### CONTRACT
    - ContractRequestEdit.vue, ContractTerminationEdit.vue: S'ha integrat el token de la sol·licitud o contracte al títol del propi formulari.
    - contract-requests/edit/[id].vue, contract-terminations/add.vue, contract-terminations/edit/[id].vue: S'han eliminat els H1 duplicats d'aquestes pàgines per evitar títols redundants.

#### READINGS
    - reading-batches/add.vue: S'ha eliminat el títol H1 duplicat per no redundar amb el del component fill.

#### SERVICE
    - pages/service/properties/index.vue: S'ha ajustat la graella (grid) de la llista de propietats per encabir i mostrar correctament la ruta (`route?.name`) i la posició de la ruta (`route_position_token`) en lloc de duplicar el camp de punts de subministrament.

## [03-06-2026]

### FIX
#### INVOICE
    - InvoiceRegion.vue: Add import deleted before InvoicePaymentDetail.

### MODIFIED
#### NAVIGATION / SIDEBAR
    - NavSidebar.vue: S'ha actualitzat la selecció de l'empresa per defecte per utilitzar la propietat `is_default` de la resposta de l'API d'empreses, prescindint de la crida a `configProject` per al token `main_company_token`.

#### BILLING / INVOICES
    - ReadingsChange ara es pot seleccionar si es vol manternir la lectura estimada (no es podran fer canvis sobre la lectura) i si es vol fer servir la bossa d'estimades a lectures modificades
    - ConnectionRequestDetail.vue, ContractRequestSummary.vue i ContractTerminationDetail.vue: S'ha corregit la descàrrega/visualització del PDF de les factures temporals (`getTemporaryPDF`) per utilitzar la utilitat d'autenticació `openAuthenticatedFileUrl` en lloc d'obrir la URL directament.

## [02-06-2026]

### FEAT
#### COMMUNICATION
	- S'ha afegit un procés de comunicació en 'Esborrany' el qual entrarà a editar-se i lligarà les lectures afegides a les comunicacions que es creïn. 
	- S'ha afegit l'opció de formatar els textos a afegir a les comunicacions, com ara 'BOLD', 'ITALIC', 'UNDERLINE' i 'ALIGNMENT'

#### BILLING
	- Ara tenim l'opció d'afegir lectures a un lot de lectures cap a un procés de comunicació en 'Esborrany' que es podrà editar més endavant

### FIX
#### CONTRACT
    - ContractRegion.vue i ContractPinned.vue: Corregida la duplicació de factures de `request_invoices` a la llista de factures de la pestanya realitzant un filtratge de desduplicació per ID.

### MODIFIED
#### COMMUNICATION
	- S'han afegit variables amb les que treballar als textos de comunicacions.

#### CONTRACT
    - ContractStatusBadges.vue: Afegit el botó/caixeta de la bossa de consum (bossa d'estimades) que mostra els m3 totals del contracte quan és superior a 0, el qual enllaça a la regió de la bossa d'estimades (`EstimatedBagRegion`). S'ha amagat també la caixeta de "Pendent a compromís" quan el seu valor és 0.
    - ContractDetail.vue: S'han amagat/eliminat les icones de gota (`fa6-solid:droplet`) de la bossa de consum dels punts de subministrament (tant el principal com els addicionals).
    - ContractRequestSummary.vue i ContractRequestDetail.vue: S'ha corregit l'obertura del PDF del contracte (`generateContract`) per utilitzar la utilitat d'autenticació `openAuthenticatedFileUrl`.
    - ContractDocumentsData.vue: Afegit control per evitar mostrar fitxers de documentació (`documentation_files`) i el document del contracte (`contract_file`) quan arriben amb la propietat `is_active` igual a `false`.
    - ContractRegion.vue i ContractPinned.vue: Afegit el paràmetre `is_invoice=true` a la crida de factures del contracte (`getInvoicesFromContract`) per obtenir només factures/pre-factures i excloure els pressupostos. Corregida l'obertura del PDF del contracte (`generateContract`) per utilitzar la utilitat d'autenticació `openAuthenticatedFileUrl`.
    - ContractTabs.vue: Actualitzat el comptador de la pestanya "Factures" per utilitzar directament la longitud de la llista processada al frontal (`invoices?.length || 0`) en lloc del valor estàtic del backend.

#### BILLING / INVOICES
    - invoice-api.js: Actualitzada la funció `getInvoicesFromContract` per admetre el paràmetre `is_invoice` a la URL de l'API.

#### NAVIGATION / SIDEBAR
    - NavSidebar.vue: S'ha canviat el comportament del botó d'ajuda per utilitzar directament la llengua del frontend en lloc de la llengua de l'usuari.

#### READINGS
    - AddReadings.vue: S'ha implementat la descàrrega de plantilles de càrrega de lectures a través d'una petició autenticada amb token a les capçaleres per evitar errors de fitxers protegits.

## [01-06-2026]

### FEAT
#### PERMISSIONS / PIGGY BANK
    - GroupPermissionsEdit.vue, PiggyBankRegion.vue, ca.ts, es.ts, piggy-bank-api.js, person-piggy-bank-api.js: Afegit el control de permisos per a la Bossa de Saldo (Piggy Bank) de contractes i persones. S'ha introduït el mètode `getPermissions` als respectius serveis de l'API per validar els permisos específics del recurs. S'ha adaptat el component `PiggyBankRegion.vue` per ocultar/inhabilitar les opcions de modificació de saldo si l'usuari no té el permís `change_piggy_bank` (o `can_change` de l'API), així com per mostrar un avís de manca de permisos i bloquejar la vista si no disposa del permís de lectura (`can_view`). S'han afegit les clau de traducció `piggy_bank` i `person_piggy_bank` a nivell d'arrel de traduccions per al correcte renderitzat de la categoria en el panell d'edició de permisos de grups, i s'ha fet robust el component `GroupPermissionsEdit.vue` davant de permisos sense dades afectades (`affected_data` nul/buit) per evitar errors de renderitzat.

### FIX
#### CONTRACT / MODIFICACIÓ DE DADES
    - Corregida la detecció i el guardat de **múltiples telèfons** del contracte (abans només es reflectia bé el principal o es perdien canvis per desincronització pare/fill).
    - Corregit que en carregar el formulari s'assignessin adreces automàticament des del punt de subministrament quan el titular ja tenia adreces disponibles.
    - Corregit el comptador i la visualització de la pestanya Modificacions després de la resolució de conflictes amb `ContractTabs` (develop).

### CHORE
#### CONTRACT / MODIFICACIÓ DE DADES
    - ContractDataLog.vue: Eliminat (duplicava `data_changes` del contracte amb una segona crida a `logger/contract-data`; els canvis es mostren via `DataChange` + `mergeContractModifications`).
    - ContractMembersChange.vue: Eliminat (el log de persones al contracte es llegeix des de `contract-total-members` i es fusiona al mateix llistat).
    - logger-api.js: Eliminat el mètode `create` (no s'utilitzava; el registre de telèfons es fa al backend en guardar el contracte amb `phone_ids`).

#### CONTRACT
    - contractDataChangeDisplay.js: Nou util amb la lògica compartida per detectar i mostrar canvis de dades del contracte (pagament, adreces, email, persones i **llista de telèfons**), normalització d'IDs i fusió d'historials (`mergeContractModifications`).
    - contract-api.js: Afegit `getDataChangeDetail` (`GET …/contracts/{id}/data-change/`) i suport a `save(..., { dataChangeEdit: true })` (`PUT …?edit=data-change`) per reduir el pes de les peticions de càrrega i guardat del formulari de modificació de dades.
    - DataChange.vue: Refactoritzat per mostrar cada tipus de canvi de forma consistent (inclosos telèfons amb text `anterior → nou` quan hi ha diversos números).

### MODIFIED
#### NAVIGATION / SIDEBAR
    - NavSidebar.vue: Reestructurada la barra de navegació lateral per mantenir fixa la part superior amb els primers 3 ítems (amb línia separadora) i la part central scrollable. La part inferior esdevé un botó fix de l'explotació que, en ser clicat, obre un desplegable superior elegant on s'integren la selecció d'idioma (Català / Español), l'enllaç de configuració, el nom de l'usuari logejat, un botó d'ajuda (enllaçat a la documentació externa) i la sortida del sistema, eliminant així aquestes opcions dels espais principals i optimitzant l'espai i neteja de la barra lateral. S'ha afegit també un comportament de tancament automàtic en fer clic a fora del desplegable. A més, si no hi ha cap explotació seleccionada, se selecciona per defecte en cas de ser l'única de la llista; altrament, es recuperen i mostren les dades de la primera empresa disponible al sistema.

#### EXPORTS / CSV & EXCEL
    - meter-api.js i contract-api.js: Eliminada la propietat `parseResponse: txt => txt` dels mètodes `exportCsv` i `exportExcel` per processar correctament la resposta JSON de 202 ACCEPTED que conté el `task_id` de la tasca de generació asíncrona.
    - index.vue (meters) i index.vue (contracts): Migrada la descàrrega de fitxers d'exportació cap a un flux de processament asíncron amb polling. Agora el frontal rep el `task_id` de l'exportació, consulta periòdicament el progrés (cada 2 segons) mitjançant `$apiManager.checkTask` mostrant el percentatge de càrrega sobre el propi botó d'exportació, i descarrega automàticament el document obtingut amb `$DocumentManagerApiService.viewDocument` un cop l'estat passa a ser exitós (`SUCCESS`). En cas d'error (`FAILURE`), s'atura el polling i es mostra un missatge d'error detallat obtingut de la clau `error` de la resposta.

#### INVOICES
    - InvoiceDetail.vue: Migrada la visualització del document de factura. Ara, en lloc d'obrir directament el document en una nova pestanya, es carrega i mostra el document en una finestra emergent en un context autenticat.
    - Es fa servir la util `open-authenticated-file.ts` per accedir a fitxers dins de /media.

#### USER / GROUP
    - UserEdit.vue: Afegida la possibilitat de triar a quin grup pertany un usuari durant la seva creació o modificació. Es carrega la llista de grups de l'endpoint de grups i es renderitza un selector dropdown. En desar, s'envia el camp `group_id` seleccionat (o `null` si s'ha buidat). Addicionalment, s'ha protegit l'enviament de la contrasenya en edició, evitant enviar el camp `new_pwd` si no s'ha introduït cap valor als camps de contrasenya (es manté així l'anterior). El checkbox d'Administrador està vinculat correctament al camp `is_superuser`.

#### CONTRACT
    - Corregit que guardi el canvi del mètode de pagament o el canvi de diferents domiciliacions bancàries.
    - pages/contract/contracts/[id]/data-change.vue: Detecció fiable de canvis de telèfons via l'estat del component fill (`getContactsState`); guardat només dels camps que han canviat; càrrega amb endpoint lleuger; sense guardat fantasma de pagament en cada `emitChange`; representants només si han canviat; retorn amb `router.back()` quan és possible.
    - ContractRequestAddressPayment.vue: Còpia de contactes per no mutar `contract.contacts`; `resolveId` en emitir canvis; ús de dades de persona embebides del contracte (sense `getFullDetail` redundant); `autoAssignSupplyAddress` per no crear adreces des del punt de subministrament en editar contracte; només crida `setSupplyAddresses` si no hi ha cap adreça disponible.
    - ContractTabs.vue: Pestanya Modificacions unificada amb `allModifications` i `DataChange` (substitueix `ContractDataLog` + `ContractMembersChange` dins del component compartit de pestanyes).
    - ContractRegion.vue i ContractPinned.vue: Càrrega paral·lela de logs `contract-total-members` i `contract-phones`; historial fusionat a la pestanya Modificacions; integració amb `ContractTabs` després del refactor de pestanyes compartides.
    - ContractPinned.vue: Càrrega diferida dels logs de modificacions en obrir la pestanya per primera vegada.
