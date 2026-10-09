# Changelog Frontend

## [31-07-2026]

### FIX
#### BILLING (`ReadingBatchEdit.vue` — bloqueig d'avanç al pas 2 massa restrictiu)
    - `nextStep()` bloquejava l'avanç del pas 2 (Configuració) sempre que `countersSetup.assigned_readings` fos 0/buit, encara que el lot tingués lectures reals comptabilitzades sota altres claus (remotes, amb alerta, etc.), impedint avançar en casos vàlids. Nou computed `hasSetupReadings`: només bloqueja l'avanç (mostrant `reading_block.no_readings_detected_warning`) quan TOTS els comptadors del pas són 0 excepte `missing_readings` ("Lectures pendents"), és a dir, quan realment no s'ha detectat cap lectura de cap tipus.
#### CONTRACT (`pages/contract/contracts/[id]/data-change.vue` — guardar sense canvis ja no modifica el contracte)
    - `save()` ja no fa `ContractApiService.save` si no hi ha cap canvi real (adreces, pagament, telèfons, idioma, etc.): només torna enrere sense tocar la BD.
    - Només s'envien al backend els camps que han canviat; `communication_type` només si l'usuari el modifica (o la correcció automàtica).
    - Si el tipus és DIGITAL/BOTH i no hi ha email, en desar es força a PAPER (no es pot comunicar digitalment sense mail).
    - Si el tipus és DIGITAL/BOTH i sí hi ha email, el `person_contact_email_id` s'envia en els saves del contracte perquè el backend no el buidi; si és PAPER, no s'envia el mail (tenir-ne un no passa la comunicació a digital).
#### BILLING (`ReadingBatchEdit.vue` — bloqueig d'avanç al pas 2 (Configuració) massa restrictiu quan el lot es carrega per data)
    - `nextStep()` bloquejava sempre l'avanç del pas 2 quan `hasSetupReadings` era fals (cap comptador amb lectures detectades), fins i tot quan el lot s'havia carregat "per data" (`setupData.reading_date` informat, mateixa comprovació ja usada a `needsAssignReadingsFromSetup`), cas en què encara no hi ha comptadors previs a mostrar però sí que es pot continuar. Ara el bloqueig només s'aplica quan no hi ha lectures detectades **i** tampoc s'ha carregat per data.
#### GENERAL (scroll doble a les regions laterals fixes — `ContractRegion.vue`, `InvoiceRegion.vue` i la resta de regions amb el patró `#right_page`/`#region_nav`)
    - Causa arrel identificada en tres punts alhora: (1) `assets/styles/global.css` afegia `overflow-y: auto` directament al contenidor `#right_page`, que ja conté un altre `overflow-y-auto` intern (el de la pròpia regió), duplicant el scroll; (2) el contenidor `#right_page` no era `flex`, així que l'alçada pròpia d'`#region_nav` (el botó de tancar) no es descomptava del `h-full` del contingut germà, sobrepassant l'alçada del panell; (3) `layouts/default.vue` (`<main id="page">`) no tenia alçada ni `overflow` fixats, permetent que el document/`body` sencer fes scroll per darrere del panell fix.
    - `assets/styles/global.css`: `#right_page` passa a `display: flex; flex-direction: column; overflow: hidden` (el panell ja no fa scroll ell mateix); `#region_nav` amb `flex-shrink: 0`; el(s) div(s) de contingut després d'`#region_nav` passen a `flex: 1 1 auto; min-height: 0; overflow-y: auto`, únic contenidor amb scroll. Aplicat automàticament (selector per `id`) a totes les regions que segueixen aquest patró, sense haver de tocar cada pàgina/component individualment.
    - `layouts/default.vue`: `.wrapper` ara és `h-screen overflow-hidden` (el `body` ja no pot fer scroll mai); el contenidor de contingut passa a `flex flex-col h-full`; `<main id="page">` passa a `flex-1 min-h-0 overflow-y-auto`, essent ara l'únic contenidor de scroll per a tot el contingut normal de pàgina.
    - `components/organisms/ContractRegion.vue`: afegit `overflow-hidden` al contenidor arrel (`region__content`), per contenir l'excés d'alçada (`calc(100%+45px)`) de la subregió quan aquesta es mostra en mode `grid grid-cols-2` (vista principal, no subregió apilada).

### FEAT
#### BILLING (`ReadingBatchEdit.vue` — botó "Estimar lectures" al pas 2, per poder avançar el wizard fent estimacions)
    - Nou botó al peu del pas 2 (Configuració) que obre `EstimateReadingsDialog.vue` (el mateix popup ja usat al pas 3) i, en confirmar, crida `$ReadingBatchApiService.estimateReadings(id, {supply_points: 'all', ...params})`; en completar-se la tasca (`waitForAssignTask`, mateix mecanisme de polling que l'assignació de rutes) es refresquen els comptadors del lot, permetent desbloquejar `hasSetupReadings` i avançar sense necessitat de lectures reals.
#### BILLING (`ReadingBatchEdit.vue`/`ReadingBatchCreate.vue` — tornar al pas 1 (Creació/selecció de rutes) des del pas 2 per modificar dades inicials)
    - Nou botó "Anterior" al pas 2 (`backToCreation`): purament local (no crida l'endpoint de revert de backend, ja que el pas 1 i el pas 2 comparteixen el mateix estat inicial del lot), torna `currentStep` a 0 i, quan el lot ja existeix, en carrega les dades actuals (`$ReadingBatchApiService.getDetail(id)`) per precarregar el formulari de creació.
    - `ReadingBatchCreate.vue`: nova prop `initialData`, amb precàrrega best-effort de `name`/`token`/`include_telecontrol`/`include_manual`/rutes (intentant fer coincidir amb una plantilla ja existent, o mostrant directament la llista de rutes si no n'hi ha cap que coincideixi exactament); si el backend no retorna algun d'aquests camps, simplement no es precarrega aquell camp (sense trencar el formulari).
    - `save()` al pas 0 de `ReadingBatchEdit.vue`: si `props.id` ja existeix (s'està reeditant un lot ja creat), ara crida `$ReadingBatchApiService.update(data)` (PUT) en lloc de `create()` (POST), i es queda a la mateixa pàgina (`nextStep()` avança automàticament al pas 2) en lloc de navegar a una nova URL d'edició.
#### CONTRACT/COREDATA (gestió de múltiples correus electrònics als contactes de persona)
    - `components/molecules/AddContact.vue`: el camp de correu electrònic passa de mostrar-ne un de sol a permetre afegir-ne fins a 5 (inputs individuals amb papereres per esborrar cadascun, inclòs el primer), guardant-los concatenats amb `;` (`join(';')`) i separant-los en carregar un contacte existent. Reorganitzats els camps del formulari. Nou botó Esborrar al costat de Guardar.
    - `components/molecules/PersonContactSelect.vue`: afegit botó d'editar a cada contacte de la llista, que obre `AddContact` amb les dades precarregades. L'esborrat es gestiona ara des d'`AddContact`, amb confirmació prèvia abans de trucar `$PersonContactApiService.remove`. Corregida una condició de carrera que feia que editar un contacte es dupliqués com un de nou fins que es recarregava la pàgina. Nous events `contact-updated`/`contact-removed`, i `defineExpose({ close })` per permetre tancar el panell des del component pare.
    - `components/molecules/ContractRequestAddressPayment.vue`: `closeAllRegions()` ara també tanca `PersonContactSelect`, evitant que quedessin dues finestres laterals obertes simultàniament en tancar/reobrir des de diferents punts d'entrada (telèfon/SMS/email digital). Afegits handlers per sincronitzar immediatament `selectedPhones`, `selectedSMSPhones` i `selectedDigitalPersonContact` quan un contacte s'edita o s'esborra des de qualsevol de les tres finestres de selecció.
    - `plugins/services/coredata/person-address-api.js`: afegit el mètode `remove(id)` a `PersonContactApiService`.
#### READING (`pages/reading/readings/estimation.vue` — taula "Historial de lectures" més llegible i amb dades de consum diari)
    - Mida de text de la taula d'historial (dins de les files expandibles de les dues seccions, "Pendents d'estimar" i "Amb lectura recent") augmentada de `text-[10px]` a `text-[12px]`.
    - Noves columnes "Dies de consum" (`rh.consumption_days`) i "Consum diari mig" (`calculated_value / consumption_days`, en m³, amb 2 decimals), per poder comparar consums entre lectures de diferent durada sense haver de calcular-ho a mà. Reutilitzades les claus i18n ja existents `billing_block.consumption_days` i `billing_block.consumption_daily_avg`.
#### CONTRACT (`components/molecules/ContractDetail.vue` — dades bàsiques del contracte en 3 columnes i comptador del punt de subministrament)
    - La primera graella de dades bàsiques passa de 2 a 3 columnes (`grid-cols-2` → `grid-cols-3`): 1a fila amb Identificació + Data d'alta + Idioma. La Data de baixa (`termination_date`, condicional) es mostra ara en una fila pròpia per no desplaçar l'Idioma fora de la 1a fila quan hi és present.
    - Fila Titular + Punt de subministrament: es manté a `grid-cols-2`, sense canvis.
    - Fila Tipus de client + Tipus d'ús + Categoria: també passa a `grid-cols-3` (abans 2 files de `grid-cols-2`).
    - Nou camp "Comptador" (`localData.supply_point_default.meter_code`/`meter_id`), en una fila pròpia just a sota de Tipus de client/Tipus d'ús/Categoria, amb el mateix patró d'enllaç que la resta de camps d'aquest component (obre `MeterRegion` apilada amb `showDetail`, més `AtomsRedirectButton` cap a `/service/meters/`). Només es mostra si el punt de subministrament per defecte té comptador assignat (`v-if` sobre tota la fila, sense deixar cap buit visual quan no en té).

## [30-07-2026]

### FEAT
#### BILLING (`ReadingBatchEdit.vue` — revertir lot des del pas 4 mitjançant el nou endpoint `/revert/`)
    - El botó "Anterior" del pas 4 (Resum/Validació) ja no fa un `PUT status_token` genèric: `previousStep()` ara crida el nou endpoint `POST billing/reading-batch/<id>/revert/` (nou mètode `revert(id)` a `plugins/api/billing/reading-batch-api.js`), que substitueix l'anterior canvi d'estat manual i ja s'encarrega al backend de recalcular in-place les lectures i desvincular factures esborrany, resolent el punt pendent de backend anotat anteriorment en aquest mateix changelog.
    - Resposta **202**: es mostra el badge de progrés (`AtomsProcessColorBadge`, mateix mecanisme de polling ja usat per `estimateReadingsTaskId`/`assignReadingsTaskId`) amb el `task_id` retornat; en acabar, torna al pas 3 (Gestió de Lectures). Si `unlinked_draft_invoice_ids` no és buit, es mostra un toast d'avís amb el nombre de factures esborrany desvinculades (`billing_block.revert_unlinked_draft_invoices`).
    - Resposta **409** (lectures amb factura definitiva vinculada): nou modal d'error (`showBlockedRevertModal`) amb el missatge del backend i la llista de `blocked_reading_ids`, en lloc d'un toast genèric.
    - Resposta **404**/**500**: toast d'error amb el missatge (`billing_block.reading_batch_not_found` / detall del backend).
    - 'locales/ca.ts', 'locales/es.ts', 'locales/gl.ts', 'locales/en.ts': noves claus `billing_block.reverting_reading_batch`, `billing_block.revert_blocked_title`, `billing_block.revert_blocked_final_invoice`, `billing_block.reading_batch_not_found`, `billing_block.blocked_reading_ids`, `billing_block.revert_unlinked_draft_invoices`.
    - Pas 2 (Configuració/Assignació de rutes): `nextStep()` ara bloqueja l'avanç si `countersSetup.assigned_readings` és 0/buit (mostra `reading_block.no_readings_detected_warning` i no avança), evitant arribar al pas 3 amb 0 lectures detectades (p. ex. per una data incorrecta).
    - 'locales/ca.ts', 'locales/es.ts', 'locales/gl.ts', 'locales/en.ts': noves claus `reading_block.no_readings_detected_warning` i `confirmation_text_block.confirm_revert_reading_batch`.
#### READING (selectors de "Període de referència" i "Estadístic" en estimar lectures)
    - Backend exposa un nou catàleg de valors compartits (`period_choices`: `last_reading`/`last_year`/`same_period_previous_year`/`historic`; `statistic_choices`: `mean`/`median`) al `GET /billing/contract-estimation/` (`settings`), reutilitzat als 3 punts on es genera una estimació, sense necessitat de tornar-lo a demanar per GET des dels altres dos formularis.
    - `pages/reading/readings/estimation.vue` (`POST /billing/contract-estimation/`): nous selectors "Període de referència" i "Estadístic" al panell de paràmetres d'estimació, llegint `settings.period_choices`/`settings.statistic_choices`/`settings.default_period`/`settings.default_statistic` del GET; només s'envien `period`/`statistic` al POST si l'usuari els selecciona.
    - `components/molecules/EstimateReadingsDialog.vue` (`PUT billing/reading-batch/estimate-readings/<id>/`): mateixos 2 selectors afegits dins del popup ja existent, per defecte sense seleccionar.
    - Nou component `components/molecules/EstimateSingleReadingDialog.vue`, que substitueix el `confirm()` de navegador de l'estimació d'una lectura individual a `AddReading.vue` (`POST billing/reading/estimate/`) per un popup amb els mateixos 2 selectors.
    - En cap dels 3 casos es trenca el comportament actual si l'usuari no toca els selectors: `period`/`statistic` només s'afegeixen al body quan tenen un valor seleccionat.
    - 'locales/ca.ts', 'locales/es.ts', 'locales/gl.ts', 'locales/en.ts': noves claus `reading_block.estimation_period`, `reading_block.estimation_period_*` (una per opció), `reading_block.estimation_statistic`, `reading_block.estimation_statistic_*` (una per opció).
#### READING (`pages/reading/readings/estimation.vue` — columna de comparació en lloc de regió emergent)
    - En generar una simulació (`dry_run`) o una estimació real, en lloc d'obrir automàticament la regió lateral de resultats, ara s'afegeix una nova columna a la dreta de les dues taules (`needs_estimation` i `has_recent`) amb fons i vora diferenciats (`bg-emerald-50 border-2 border-dashed border-emerald-400`), mostrant data/valor/consum de la nova estimació (`getEstimationResultForContract`, mapejat per `token` contra `executionResult.details`) per poder comparar-la directament amb l'última i penúltima lectura de la mateixa fila. La regió de detalls es manté disponible manualment amb el botó "Veure detalls".
    - 'locales/ca.ts', 'locales/es.ts', 'locales/gl.ts', 'locales/en.ts': nova clau `reading_block.new_estimation`.

### FIX
#### BILLING (`pages/billing/invoice/index.vue` — cercar una factura des de `SideBarSearch.vue` no obria bé la regió)
    - `checkRouteQuery()` tenia dos `if` independents (no `if/else if`): quan la navegació arribava amb `query.action=showDetail` **i** `query.id` alhora (exactament el cas de `SideBarSearch.vue`), `showDetail(id, 'InvoiceRegion')` s'executava dues vegades consecutives. La segona crida entrava a la branca de "recàrrega" (mateix id, regió ja oberta), que neteja `detail`/`selectedItemId`/`regionComponent` de forma síncrona i només els restaura dins un `nextTick()` posterior, deixant una finestra en què la regió es podia renderitzar sense `id`. Canviat a `if / else if` (mateix patró que la resta de pàgines de l'aplicació), eliminant la crida duplicada i la condició de carrera.
#### READING (`components/molecules/ReadingListDetail.vue` — dependència del text lliure d'`origin` en comptes de `is_estimated`)
    - Backend ha advertit que `Reading.origin` és text lliure (sense choices) i que, amb les noves opcions d'estimació (període/estadístic), el contingut ja no és sempre exactament `"Estimada"` (p. ex. `"Estimada (última lectura / mediana)"`), a més de dependre de l'idioma actiu del backend en el moment de crear la lectura. Revisat tot el frontend cercant lògica condicional sobre `origin`/`last_reading_origin` (no només visualització): `last_reading_origin` no es fa servir enlloc; l'única comparació de negoci trobada era `element.origin == 'estimated'` a `ReadingListDetail.vue`, redundant amb `element.is_estimated` i ja pràcticament morta (comparava amb el literal anglès `'estimated'`, que mai coincidia amb el text real en català). Eliminada la dependència d'`origin`: la condició ara és únicament `element.is_estimated`.

## [29-07-2026]

### FEAT
#### COMMUNICATION (`MessagesVisualization.vue` — descarregar carta individual i marcar com a enviada)
    - Mateix flux que el procés massiu: el botó **Descarregar carta** de la pestanya Mensaje (ja existent) ara demana confirmació (`confirm_sent_postal`) si la comunicació encara no té `sent_at`, crida `POST communication/communication/mark-as-sent/` amb `communication_ids` i descarrega el PDF. Així les comunicacions postals individuals queden amb `status` enviada i `sent_at` informat.
#### BILLING (`InvoiceRegionModals.vue` — devolució manual i opció de retornar el saldo)
    - Modal **Generar devolució** (`openReturnReason`): nou checkbox "Devolució també del saldo a la hucha" (`return_all`), visible només quan la factura té pagaments de tipus BALANCE (`has_payments_piggy_bank`). En marcar-lo, s'envia `return_all=true` a `PUT billing/invoice/<id>/pass-to-pending/` perquè el backend reintegri també l'import cobrat amb saldo (a més del pagament SEPA). Per defecte queda desmarcat; si la factura té saldo, s'obre amb el checkbox actiu.
    - `locales/ca.ts`, `locales/es.ts`, `locales/en.ts`, `locales/gl.ts`: nova clau `common.return_all_piggy_bank`.
#### GENERAL (suport de nous idiomes Gallec i Anglès, i idioma del contracte)
    - Afegits els idiomes `gl` (Gallec) i `en` (Anglès) a tota l'aplicació: `nuxt.config.ts` (`locales`), `i18n.config.ts` (missatges), `plugins/i18n-init.client.js` (`validLocales`), i nous fitxers `locales/en.ts`/`locales/gl.ts` (traducció completa de tots els blocs existents). Fins ara només hi havia Català/Castellà.
    - Nova constant compartida `utils/languages.js` (`AVAILABLE_LANGUAGES`), amb els 4 idiomes disponibles; `LanguageSwitcher.vue`, `NavSidebar.vue` i `SendInvoiceModal.vue` (llistes duplicades de `languages` fins ara) l'importen en lloc de mantenir cadascun la seva pròpia còpia.
    - `NavSidebar.vue`: el selector d'idioma del menú lateral passa de dos botons fixes (Català/Español) a un `<select>` amb les 4 opcions disponibles.
    - Nou camp "Idioma" a `ContractRequestSetup.vue` (alta de contracte/sol·licitud), desat al camp `language` de la sol·licitud/contracte (`ContractRequestEdit.vue` — `saveStep`). Valor per defecte l'idioma configurat a `LANGUAGE` de l'`.env` (`config.public.defaultLocale`).
    - Nou camp "Idioma" a `pages/contract/contracts/[id]/data-change.vue` (modificació de dades d'un contracte ja existent, que encara no el tenia): es carrega l'idioma ja guardat al contracte (o l'`.env` per defecte si no en té), i en canviar-lo es registra com a canvi auditat (`new_language`/`previous_language` via `$ContractApiService.changeData`, mateix patró que la resta de camps d'aquest formulari) i es persisteix a `$ContractApiService.save`.
    - Idioma mostrat en mode lectura a `ContractDetail.vue` i `ContractRequestDetail.vue` (fins ara es guardava però no es mostrava enlloc un cop desat).
    - Noves claus de traducció (`ca`/`es`/`gl`/`en`): `galician`, `common.translations`, `common.add_translation`.
#### PRICING/BILLING (`TranslatableNameField.vue` — noms traduïbles de productes, tarifes i conceptes de línia)
    - Nou component `components/molecules/TranslatableNameField.vue`: llista d'idioma+nom afegibles/eliminables, evitant repetir el mateix idioma dues vegades.
    - Integrat a `ProductEdit.vue`, `PriceRateEdit.vue` i `LineItemTypeEdit.vue`: nou camp `name_translations` (objecte `{idioma: nom}`) desat al costat del `name` principal, carregat/desat com a llista de files editables.
#### BILLING (`pages/billing/invoice-budgets/index.vue` — botó "Nou pressupost" al llistat de pressupostos)
    - Afegit a la pàgina de pressupostos el mateix botó de crear un nou registre que ja existia a la pàgina de factures (`showDetail(null, 'AddInvoiceBudget')`), col·locat al costat del botó de Descarregar XLSX dins el `div class="flex items-center gap-2"` de la capçalera.
    - 'locales/ca.ts', 'locales/es.ts': nova clau `billing_block.new_budget` ("Nou pressupost"/"Nuevo presupuesto").

### FIX
#### CONTRACT (`ContractRequestEdit.vue`/`ContractRequestTermination.vue` — sol·licituds de "Canvi de nom")
    - El banner informatiu del pas "Finalització" ("Aquesta sol·licitud és un Canvi de nom...") es mostrava sempre que la sol·licitud era de tipus canvi de nom (`isChangeOfNameRequest`), independentment de si s'havia triat "Mantenir número de contracte" o "Nou número de contracte". Com que en aquesta segona opció sí que es crea un contracte nou (el missatge és fals en aquest cas), ara només es mostra quan `isChangeOfNameRequest && canKeepSameCode && keepSameCode`.
    - A `ContractRequestTermination.vue`, l'opció "Facturar la lectura de tall a la baixa"/"Passar el consum al nou contracte d'alta" (`billCutReading`) partia per defecte de `false` (Passar el consum al nou contracte), quan el comportament esperat per defecte és "Facturar la lectura de tall a la baixa". Canviat el valor inicial a `true`. No afecta sol·licituds amb una `ContractTerminationRequest` ja desada, que continuen carregant el valor persistit.

## [28-07-2026]

### FEAT
#### BILLING (`PaymentRegion.vue`/`PaymentDetail.vue` — vincular el pagament amb el contracte, la factura, el compromís de dipòsit i el fraccionament)
    - El contracte associat a un pagament ("Contracte" a `PaymentDetail.vue`) només es mostrava quan `data.contract` venia informat directament al pagament; en pagaments d'una factura o d'un compromís de dipòsit (on el contracte penja de forma anidada de `data.invoice.contract`/`data.commitment_deposit.contract`, mateix camp ja usat a `CommitmentDepositDetail.vue`) el camp no apareixia mai. Nou computed `contractLink` amb aquest fallback (`data.contract || data.invoice?.contract || data.commitment_deposit?.contract`).
    - Afegit `AtomsRedirectButton` (obre en una pestanya nova via `/ruta/?id=`, mateix patró ja usat per a remeses i pagaments agrupats en aquest mateix component) al costat del botó d'obrir en subregió, tant per al Contracte com per a la Factura i el Compromís de dipòsit, per poder-hi accedir directament sense haver d'obrir-los apilats dins del pagament.
    - Nou camp "Fraccionaments" a `PaymentDetail.vue`: quan el pagament prové d'un compromís de dipòsit, identifica i mostra a quin fraccionament (`PaymentCommitment`, `is_guide=True`) concret correspon (data de venciment o token), amb accés directe al compromís de dipòsit corresponent.
    - `PaymentRegion.vue`: en carregar el pagament, si té `commitment_deposit`, cerca el fraccionament corresponent amb `$PaymentCommitmentApiService.getByDeposit(commitment_deposit_id, true)` i fent coincidir el `due_date`. **`PaymentCommitment` no té cap FK cap a `Payment`** (verificat a `billing/models.py` del repo backend): quan es genera el pagament d'un fraccionament, `add_wallet_payment` (`billing/utils/commitment_deposit_service.py`) copia el `due_date` del fraccionament (`is_guide=True`) al pagament, així que es poden fer coincidir per `commitment_deposit` + `due_date` — mateix filtre `deposit` ja usat i confirmat a `PaymentCommitmentFilter`. (Una primera versió assumia erròniament un filtre `?payment_id=` al llistat que no existeix — hauria retornat sempre el primer registre de tota la taula; corregit sense necessitat de tocar backend.)
#### BILLING (`InvoiceRegion.vue`/`InvoiceDetail.vue` — mostrar el compromís de pagament d'una factura)
    - Nou camp "Compromís de dipòsit" a `InvoiceDetail.vue` (sempre visible a la factura, no només a la pestanya de pagaments) quan la factura pertany a un compromís de dipòsit: nom clicable que obre `CommitmentDepositRegion` apilada, més `AtomsRedirectButton` per obrir-lo directament en una pestanya nova (`/billing/commitment-deposits/?id=`), mateix patró que la resta de relacions d'aquest component.
    - **Verificat contra el repo `avsis-customers-backend`**: `CommitmentDeposit.invoices` és un `ManyToManyField` (no hi ha cap FK/camp `commitment_deposit` a `Invoice`, ni exposat mai a `billing/serializers/invoice_serializer.py`) i no hi havia cap filtre per consultar-ho des d'una factura. Afegit filtre `invoice` a `billing/filter/commitment_deposit_filter.py` (backend, mateix patró que el `contract` ja existent: `filters.NumberFilter(field_name='invoices__id', lookup_expr='exact')`), sense migració (no toca el model). Nou mètode `getByInvoice(invoice_id)` a `plugins/api/billing/commitment-deposit-api.js` (`GET /billing/commitment-deposit/?invoice=<id>`).
    - `InvoiceRegion.vue`: en carregar la factura, si l'estat és `invoice_status_commitment_token`, consulta `getByInvoice` i passa el resultat a `InvoiceDetail` com a nova prop `commitmentDeposit` (abans s'assumia erròniament un camp `localData.commitment_deposit` inexistent al payload de la factura, que mai s'hauria mostrat).
    - `InvoiceRegion.vue` no tenia registrada `CommitmentDepositRegion` entre les subregions obribles (només ho feia `PaymentRegion.vue`); afegit l'import i el bloc corresponent perquè el nou enllaç de la factura pugui obrir-la apilada.
#### BILLING (`InvoiceRegionModals.vue` — data de devolució al generar retorn)
    - Modal **Generar devolució** (`openReturnReason`): nou camp `AtomsInputDate` ("Data devolució") i enviament de `return_date` a `PUT billing/invoice/<id>/pass-to-pending/`.
    - El botó Confirmar queda deshabilitat si no hi ha tipus de devolució ni data.
    - El flux **Devolver factura** (`openLiquidate`) no canvia.
#### BILLING (Enviaments de factures per email)
    - Permet enviaments de factures per email des de la pestanya "Factures" de `ContractRegion.vue` (i també a `InvoiceRegion.vue`), en el mateix botó d'acció principal (Operacions/Nou registre).
    - `SendInvoiceModal.vue`: nou component modal que permet seleccionar el targeta de correu electrònic (contrat/persona) i la plantilla d'email (o bé la plantilla per defecte de la companyia, o bé la plantilla personalitzada de la factura), i enviar la factura per email.
#### PRICING (`BillingRangeEdit.vue` — mantenir la tarifa d'origen activa en modificar un rang de facturació)
    - En modificar un rang de facturació des de `PriceRateRegion.vue` (via la subregió `BillingRangeRegion.vue`), l'edició obria una pàgina completa (`/pricing/billing-ranges/edit/<id>`) que en desar redirigia sempre al llistat general de rangs (`/pricing/billing-ranges/`), perdent el context de la tarifa d'origen i obligant a tornar-la a cercar. `BillingRangeRegion.vue` (`edit()`) ara hi afegeix `?price_rate_id=<id>`; `BillingRangeEdit.vue` rep aquest id com a nova prop `returnPriceRateId` i, en desar (o clicar el nou botó "Tornar"), torna a `/pricing/price-rates/?id=<price_rate_id>`, reobrint `PriceRateRegion` amb la mateixa tarifa activa (mateix patró d'`?id=` a la URL ja usat a `ContractRegion.vue`/`pages/contract/contracts/index.vue`), en lloc del llistat.
    - Nou botó "Tornar" a `BillingRangeEdit.vue`, al costat de "Guardar", per poder sortir del formulari sense desar sense dependre del botó "enrere" del navegador.
    - `pages/pricing/billing-ranges/edit/[id].vue` i `pages/pricing/billing-ranges/add.vue`: llegeixen `route.query.price_rate_id` i el passen a `BillingRangeEdit`.
    - 'locales/ca.ts', 'locales/es.ts': nova clau `common.go_back` ("Tornar"/"Volver").
#### CONTRACT (`ContractRegion.vue` — accions del contracte agrupades per categoria i disponibles des de cada pestanya)
    - `ContractActionsDropdown.vue`: les opcions del desplegable d'accions del contracte, fins ara totes seguides sense cap ordre, ara estan agrupades per categoria (Contractació, Facturació, Lectures, Servei, Atenció al client, Ordres de treball), seguint el mateix criteri de separació que el menú lateral (`NavSidebar.vue`). Cada grup se separa amb una línia divisòria amb el nom de la categoria incrustat al mig, en lloc d'un títol de secció a part.
    - `OptionsDropdown.vue`: la llista d'opcions del desplegable ara té una alçada màxima (`max-h-[70vh]`) amb scroll vertical intern i una barra d'scroll fina i discreta (mateix patró ja usat a `NavSidebar.vue`), per poder navegar-hi quan el contingut no cap en pantalla.
    - `ContractTabs.vue`: cada pestanya rellevant incorpora ara el botó (o botons) de l'acció directament relacionada, sense haver d'obrir el desplegable general: "Modificar lectures" a Lectures; "Factures generals", "Descàrrega massiva" i "Factura personalitzada" a Factures; "Modificar bonificacions"/"Modificar variables" a Bonificacions/Variables; "Modificar tarifes" a Tarifes; "Modificar" a Modificacions; "Nova subrogació" a Subrogacions; "Canvi d'inquilí" a Canvis d'inquilí; "Nova ordre" a Ordres; "Nova incidència" a Incidències; "Nou procés de comunicació" a Comunicació; "Afegir tasca" a Tasques; "Nova reclamació" a Gestió de deute. Botons visibles només amb permís de modificació (`canChange`, nova prop passada des de `ContractRegion.vue`), estil `button-primary` (blau) en mida reduïda (`text-xs`), agrupats en una mateixa fila quan n'hi ha més d'un per pestanya (p. ex. Factures), amb marge superior i inferior respecte al contingut de la pestanya.

### FIX
#### CONTRACT (`AdjustmentList.vue` — clic sobre un corrector dins de `ContractRegion.vue` saltava a dalt de la pàgina)
    - L'enllaç del nom del corrector (`<a href="#">`, mostrat quan `isContractSubregion`) no feia `preventDefault` en clicar-lo: a més d'emetre `show-detail` (que ja obria correctament la subregió `AdjustmentRegion` via la cadena `AdjustmentList` → `LineItemTypeDetail` → `PriceRateListItem` → `ContractTabs` → `ContractRegion`), el navegador seguia l'`href="#"` i saltava al principi de la pàgina, donant la sensació que es reiniciava tota la vista. Afegit `.prevent` al `@click`.

#### BILLING (`pages/billing/invoice/index.vue` — ajust d'amplades de columnes del llistat)
    - Reajustades les amplades de les columnes de la graella del llistat de factures (capçalera i files): "Identificació" de 150px a 120px, "Data" de 80px a 90px, "..." (3a columna) de 200px a 220px, i l'última columna de 80px a 90px, per millorar l'encaix del contingut.

## [27-07-2026]

### FEAT
#### GENERAL (exportació a XLSX de tots els llistats principals)
    - Nou botó "Descarregar XLSX" (`components/atoms/DownloadXlsxButton.vue`) afegit a la capçalera d'unes 40 pàgines de llistat (billing, order, service, contract, pricing, reading, communication, user, verifactu) i a diverses mini-llistes de detall (`ContractMiniDetail.vue`, `FraudMiniDetail.vue`, `PaymentCommitmentList.vue`, entre d'altres).
    - Exportació híbrida (`composables/useServerExport.ts`): si els resultats filtrats caben en una sola pàgina, es genera el fitxer client-side (`utils/xlsx-export.ts`, llibreria `xlsx`) exactament amb les files/columnes visibles; si n'hi ha més d'una, es delega al backend, que genera el fitxer complet (totes les pàgines, respectant filtres/cerca/ordre actius) com a tasca en segon pla, seguida amb el mateix mecanisme de `task-progress` ja usat en altres exports. Timeout de polling afegit (5 minuts) per no quedar-se esperant indefinidament si la tasca no respon.
    - `plugins/api/api-manager.js`: nou mètode genèric `exportTable(entity, {...})`, que construeix els paràmetres comuns (`search`, `status`, `ordering`, `columns`) més els filtres propis de cada entitat, i fa `POST {apiHost}{entity}export/`. Cada plugin d'entitat (`billing/*`, `order/*`, `service/*`, `contract/*`, `pricing/*`, `reading/*`, `communication/*`, `auth/*`, `coredata/*`) exposa ara un mètode `exportData` que hi crida a sobre.
    - Nova dependència `xlsx@^0.18.5` (`package.json`/`package-lock.json`).
    - `pages/billing/invoice/index.vue`, `pages/billing/wallet-managements/index.vue`, `pages/service/properties/index.vue` i 20 pàgines més: el botó de Descarregar i el botó d'acció principal (Operacions/Nou registre) eren germans solts dins un `flex justify-between`, que els escampava per tot l'ample de la capçalera en lloc d'agrupar-los; ara van junts dins un `div class="flex items-center gap-2"` a la dreta (Descarregar a l'esquerra del botó principal).
#### BILLING (`InvoiceConsumptionDetail.vue` — consum de la factura com a informació principal)
    - A la pestanya "Informació de consum" d'`InvoiceRegion.vue` (i també a `InvoiceView.vue`), abans només es mostrava l'historial de lectures del contracte (`ReadingDetail`), sense prioritzar les dades de consum de la pròpia factura. Ara `InvoiceConsumptionDetail.vue` mostra com a informació principal el consum de la factura (`consumption`, `real_consumption`, `consumption_days`), després les lectures utilitzades a la factura (`data.readings` via `ReadingMiniDetail`) i, a `InvoiceRegion`, l'historial del contracte com a secció secundària clarament diferenciada (`showContractReadings`; desactivat a `InvoiceView`).
    - `FieldDetail.vue`: contrast de les etiquetes per defecte de `text-slate-400` a `text-slate-600`.
    - 'locales/ca.ts', 'locales/es.ts': noves claus `billing_block.invoice_readings`, `billing_block.contract_readings` i `billing_block.contract_readings_help`.
#### BILLING (`InvoicePaymentDetail.vue` — obrir un pagament com a subregió apilada des de la pestanya "Pagaments" d'una factura)
    - Al tab "Pagaments" d'`InvoiceRegion.vue`, clicar un pagament només obria `PaymentRegion` (mateixa lògica ja existent a `showDetail`/`SubRegion`) quan la factura es mostrava com a pantalla principal (`!isSubRegion`); si `InvoiceRegion` ja estava oberta com a subregió (p. ex. des de la pestanya "Factures" de `ContractRegion.vue`), el token del pagament només era un enllaç de redirecció (`AtomsRedirectButton`) sense possibilitat d'obrir-lo. Eliminada la condició `v-if="!isSubRegion"`: ara el botó del pagament sempre emet `showDetail('PaymentRegion', element.id)`, i `InvoiceRegion.vue` (ja preparat, mateix patró que `PiggyBankRegion.vue`/`AddPiggyBankBalance.vue`) l'obre apilada per sobre de la regió de factura (`fixed ... z-50` quan `isSubRegion`).
#### STATISTICS (`pages/statistics/analysis/index.vue` — filtre "contractes actius i facturables" als resums per tipus d'ús)
    - A les taules "Resum de Consum per Tipus d'Ús" i "Resum de Facturació per Tipus d'Ús", nou checkbox "Només contractes actius i facturables" al costat del botó "Actualitzar" de cada taula, activat per defecte (es pot desmarcar per veure el resum sense aquesta restricció). Cada taula té el seu propi estat (`consumptionActiveBillableOnly`/`billingActiveBillableOnly`), independent l'una de l'altra, i recarrega automàticament en canviar-lo.
    - `plugins/api/statistics/general-statistics-api.js`: `getSummaryConsumptionByUse`/`getSummaryBillingByUse` ara accepten un objecte `params` opcional, afegit com a query string (`URLSearchParams`, mateix patró ja usat a `billing-consumption-api.js`). Quan el filtre està actiu s'envia `?active=true&is_billable=true`; quan es desmarca, no s'envia cap paràmetre.
    - 'locales/ca.ts', 'locales/es.ts': nova clau `statistics_block.filter_active_billable_contracts`.

## [24-07-2026]

### FIX
#### CONTRACT (`InputSepa.vue` — no es veia el deutor/compte seleccionat en canviar l'IBAN abans de guardar)
    - En canviar el compte de domiciliació (`onPersonBankSelected`, `ContractRequestAddressPayment.vue`) i obrir tot seguit "Generar SEPA" sense haver clicat encara el botó "Guardar" de la pàgina, `InputSepa.vue` no mostrava ni el deutor ni el número de compte seleccionats. El component només renderitzava aquesta informació (`AtomsFieldDetail` amb `item.name`/`person?.full_name`) dins del `<fieldset v-if="props.sepa">`, és a dir, únicament quan ja existia un document SEPA generat prèviament; a més, `ContractRequestAddressPayment.vue` no li passava mai el prop `person`, així que ni tan sols en aquest cas es podia resoldre el nom del titular a partir del compte triat.
    - Afegit un nou `<fieldset v-if="item?.IBAN">` (sempre visible, independent de si ja hi ha SEPA generat) que mostra el compte seleccionat (`item.IBAN`, l'objecte complet de banc ja seleccionat) reutilitzant `BankDetail.vue`, igual que a la resta de pantalles.
    - `ContractRequestAddressPayment.vue`: `<InputSepa>` ara rep també `:person="selectedBankDebitPerson"`, perquè es pugui mostrar el nom del titular quan el compte no en porta un (`item.name`) associat directament.
    - `generateDocument()` (`InputSepa.vue`) identificava sobre quin registre generar el document només per l'`id` del `GeneralPayment` ja persistit a backend (`props.item.id`), sense enviar mai el compte acabat de seleccionar a pantalla; només s'enviava `person_id`. Si l'usuari canviava l'IBAN i generava el document abans de clicar "Guardar" a la pàgina, el PDF es generava igualment amb el compte antic (l'únic que el backend coneixia). Ara `save_data` inclou també `bank_id`/`person_bank_id` amb l'id del compte seleccionat (`item.IBAN.id`).

#### CONTRACT (`ContractRequestTypeRegion.vue` — filtre de tarifes de sol·licitud inconsistent)
    - El botó "Afegir tarifes" de "Tarifes de sol·licitud" (quan la llista és buida) filtrava per `[origin_contract_token, origin_supply_token]`, mentre que l'opció "Modificar tarifes de sol·licitud" del menú d'accions només filtrava per `origin_contract_token`, mostrant conjunts diferents segons des d'on s'obria el mateix selector. Igualat el botó "Afegir" perquè filtri només per `origin_contract_token`, com l'opció "Modificar".

#### BILLING (`AddInvoiceBudget.vue`/`IndividualInvoiceForm.vue` — selector d'empresa sense control per `ConfigProject`)
    - El selector d'empresa en crear factura/pressupost es mostrava sempre que l'explotació tingués més d'una empresa vinculada (`companies.length > 1`), sense possibilitat de desactivar-lo per projecte. Afegit el flag `use_multiple_companies` (`$ConfigProjectApiService.get`, mateix patró ja usat a `ContractDetail.vue`/`ContractRequestEdit.vue`) a totes dues pantalles; el selector ara només es mostra quan el flag és cert i hi ha més d'una empresa.
    - En triar "Domiciliació Bancària (SEPA)" i clicar "Seleccionar IBAN", s'obria per error `CompanyBankSelect` (comptes de l'empresa) en lloc dels comptes del titular/persona; i a l'inrevés amb "Transferència bancària". Invertida la condició d'`openPersonBankSelect()` perquè SEPA mostri sempre els comptes del titular del contracte/persona i la transferència bancària els de l'empresa de l'explotació.

### FEAT
#### CONTRACT (`ContractRequestAddressPayment.vue` — selecció de compte en generar document sense domiciliació)
    - Al bloc de pagament, quan el mètode seleccionat NO és domiciliació bancària (`!isDirectDebitSelected`), abans no hi havia cap manera de triar un compte; ara es mostra el mateix selector de compte (`PersonBankSelect`, reutilitzant `selectedBankDebit`/`openPersonBankSelect` ja existents) sobre el botó "Generar Document".
    - `generateDocumentNoSepa()` crida `emitChange()` abans de generar el document, perquè el compte seleccionat quedi persistit al `payment` de la sol·licitud (`payment.IBAN`/`payment.person_bank`) igual que a la resta de fluxos.
    - La crida a `$ContractApiService.generateSepaDocumentNoDirect` (`POST /billing/contract/<id>/sepa/`) ara envia també `bank_id`/`person_bank_id` amb l'id del compte seleccionat, a més del `person_id` que ja s'enviava.

#### BILLING (`pages/billing/reports/index.vue` — mostrar filtres usats en generar un informe)
    - Al llistat d'informes generats, nova columna "Filtres" (5a columna de la graella) amb una icona `(i)`; als tres blocs de la cua (actius, pendents i historial de finalitzats) el mateix botó `(i)` al costat de l'estat/progrés. En passar el ratolí per sobre, mostra un popover flotant (`Teleport` a `body`, mateix patró que `InvoiceEdit.vue`) amb tots els filtres ben estructurats en columnes etiqueta/valor, sense limitar-ne la quantitat ni trencar la graella de la taula.
    - Filtres possibles a mostrar (un per cada camp del payload que ja s'envia avui a `triggerReport`, veure `pages/billing/reports/add.vue`): rang de dates / data inici / data fi, explotació, facturacions seleccionades, remeses seleccionades, persones seleccionades, contractes seleccionats, tipus d'informe, inclou pre-factures, inclou línies exemptes d'impostos, any (model 347), productes i formes de pagament. Es llegeixen de `item.filters_display` (array `{label, value}` ja resolt pel backend) amb fallback a `item.filters` (payload cru) si el primer no existeix; només es mostren els camps amb valor.
    - 'locales/ca.ts', 'locales/es.ts': noves claus `reports_block.show_filters` i `reports_block.filter_*` (una per cada camp del payload ja enviat avui a `triggerReport`, veure `pages/billing/reports/add.vue`).

#### BILLING (categoria de factura i empresa emissora en generar factures/pressupostos)
    - `EditFieldDialog.vue`: nova prop `maxlength` (opcional), aplicada a l'`<input>` intern.
    - `ConfigList.vue`: nova prop `hasSerieDigits`. Quan està activada, afegeix dues columnes editables inline (`EditFieldDialog`, `maxlength="1"`) sobre les propietats `serie_digit_av`/`serie_digit_mv` de cada element, seguint el mateix patró ja usat per `position`/`is_default` (sense obrir cada registre per separat).
    - `pages/settings/index.vue`: `showConfigList()` accepta un nou paràmetre `hasSerieDigits` (default `false`); només l'entrada "Factures: Categories" (`billing/invoice-category`) l'activa. La resta d'entrades que ja usen `ConfigList.vue` queden inalterades.
    - Camps merament informatius per a la configuració de la categoria (dígit que encapçala la sèrie final segons empresa — empresa 1 / empresa 2); si es deixen buits el backend cau a la lògica anterior. No afecta el formulari de creació de factures (que ja envia `category_id`/`company_id` i deixa que el backend resolgui el dígit) ni s'aplica en pressupostos.
    - 'locales/ca.ts', 'locales/es.ts': noves claus `billing_block.serie_digit_av`/`serie_digit_mv`.
    - Nou component `components/molecules/SelectInvoiceCategory.vue` (calcat de `SelectPaymentType.vue`), que carrega el nou catàleg `billing/invoice-category` via `$ConfiglistApiService`.
    - `IndividualInvoiceForm.vue` (factura individual/personalitzada, `entity: 'custom'`): nou selector opcional de "Categoria", que escriu a `selected_custom.category`; i nou selector d'empresa (prop `companies`), visible només si l'explotació té més d'una empresa vinculada, que escriu a `selected_custom.company`.
    - `AddInvoiceBudget.vue` (flux `contract_request`/`is_budget: true`): carrega `companies` a partir de `exploitation.companies` (`loadCompanies()`), i mostra al fieldset de mètode de pagament el mateix selector d'empresa (només si `companies.length > 1`, inclòs a `payment_data.company_id`) i el de categoria (`payment_data.category_id`), reutilitzats també al payload de sub-factures del flux de baixa/finalització (`entity: 'contract_termination_request'`).
    - Ambdós selectors de categoria/empresa no es mostren mai duplicats: quan `individual: true` només apareix el d'`IndividualInvoiceForm`; el del fieldset de pagament queda amagat en aquest cas.
    - El selector de categoria (component i etiqueta) queda completament amagat quan el catàleg `billing/invoice-category` no retorna cap resultat.
    - `pages/settings/index.vue`: nova secció pròpia "Factures: Categories" (independent de la resta d'entrades de facturació) que obre `ConfigList.vue` (ja genèric, sense servei API nou) sobre `billing/invoice-category`, permetent crear/editar/eliminar/reordenar i marcar la categoria per defecte.
    - 'locales/ca.ts', 'locales/es.ts': noves claus `billing_block.category`/`categories`.
    - No requereix cap canvi de backend addicional: reutilitza exactament el contracte CRUD + `update-positions/` + `update-default/` de `/billing/invoice-category/` (i el camp `exploitation.companies`) ja confirmat com a desplegat.

## [23-07-2026]

### FEAT
#### SERVICE (Actualització massiva de comptadors)
    - 'pages/service/meters/index.vue': nou botó d'importació (visible amb `can_change`) que obre el modal d'actualització massiva al costat del lookup i de l'export CSV.
    - 'components/molecules/MeterBulkUpdateModal.vue': flux upload → preview → confirm. Previsualitza canvis (`old` → `new`), stats, no trobats, errors, sense canvis i codis duplicats al fitxer (`duplicate_codes_in_file`). Confirm parcial reenviant el mateix fitxer; toast amb `stats.updated` i refresca el llistat.
    - Plantilla Excel descarregable (`public/templates/meter_bulk_update_template.xlsx`) amb les columnes actualitzables (sense `is_active`) i fulla `status` de referència amb els tokens `1`, `-1` i `0`.
    - 'plugins/api/service/meter-api.js': nous mètodes `bulkUpdatePreview` (`POST /service/meter/bulk-update/preview/`) i `bulkUpdateConfirm` (`POST /service/meter/bulk-update/confirm/`) via `FormData`.
    - 'locales/ca.ts', 'locales/es.ts': claus `service_block.meter_bulk_*` (incloent avís de duplicats i `reason` `already_updated_earlier_in_file`).

#### CONTRACT (`ContractRequestEdit.vue` — facturar període complert)
    - Nou checkbox "Facturar període complert" al pas "Situació actual" (pas 6) d'una sol·licitud d'alta, vinculat al nou camp `bill_full_period` de `ContractRequest` (ja acceptat pel serializer, `fields = '__all__'`). Es desa immediatament en canviar-lo (`$ContractRequestApiService.save`) i també s'inclou al payload del `saveStep` d'aquest pas. Es carrega des del `GET` de la sol·licitud (`loadData`) per pintar el formulari en edicions posteriors. Valor per defecte `false` (comportament actual amb prorrateig); marcant-lo, la primera factura de l'abonat es factura com un període complert.
    - 'locales/ca.ts', 'locales/es.ts': nova clau `contract_block.bill_full_period`.

### FIX
#### SERVICE (`MeterEdit.vue` — número i sufix de l'adreça no es vinculaven bé en crear un comptador nou)
    - Es reenvia `street_number_id` en crear un comptador des d'un punt de subministrament amb adreça existent, evitant registres d'adreça duplicats/orfes.

#### SERVICE (`ClusterEdit.vue` — boquilles sense punt de subministrament en desar la bateria)
    - Si una boquilla no té punt de subministrament, ara se'n crea un automàticament en desar la bateria (abans es descartava silenciosament).
    - Corregit `placement` a `newNozzle()`: s'enviava l'objecte sencer del selector en lloc de l'id, provocant error de backend en desar.
    - El pis/porta/escala/edifici d'una boquilla ja existent ara es recullen correctament (amb fallback a l'adreça prèvia) en crear-hi un punt de subministrament nou, i el vincle amb la bateria es persisteix immediatament en tots els fluxos (crear ràpid, seleccionar existent, editar via `FastSupplyPointEdit.vue`).
    - `FastSupplyPointEdit.vue` no incloïa mai pis/porta/escala/edifici en desar l'adreça; ara rep la destinació de la boquilla i la inclou.
    - `InputSupplyDestination.vue` ara emet els canvis a cada tecla (`@input`) en lloc de només en perdre el focus, evitant pèrdua de dades en clicar "Guardar" immediatament.

#### SERVICE (`ClusterEdit.vue` — spinner en desar la bateria)
    - Nou overlay de càrrega (`AppLoading`) que bloqueja el formulari mentre es desa, i el botó "Guardar" mostra l'estat "Desant...", seguint el mateix patró que la resta de l'aplicació.

## [22-07-2026]

### FEAT

#### SERVICE (`ClusterEdit.vue` — camp "Ampliació")
    - Nou camp de text "Ampliació" (`address_extra`) a nivell de bateria (`ClusterEdit.vue`, al costat de "Cadastral"), desat al payload de `saveCluster()` amb el mateix nom de camp que ja fan servir `AddAddress.vue`/`SupplyPointDetail.vue`.
    - Nou camp "Ampliació" a l'adreça de cada boquilla, al costat d'"Edifici": 'components/atoms/InputSupplyDestination.vue' (usat des de `ClusterNozzleEdit.vue`) afegeix una 5a columna `address_extra`, que es carrega/emet igual que `floor`/`door`/`stair`/`building`. 'ClusterEdit.vue' inclou `address_extra` en construir `nozzle.supplyPoint.address` tant a `saveCluster()` com a `createNewLocalSupplyPoint()` (branca de connexió i branca d'adreça manual), perquè es persisteixi correctament.
#### CONTRACT (`ContractRequestAddressPayment.vue` — compte bancari per defecte)
    - Nou botó "Guardar com a forma de pagament per defecte" a la targeta del compte de domiciliació seleccionat: crida `$PersonBankApiService.save({ id, is_default: true })` sobre el compte actual i actualitza l'estat local (`selectedBankDebit` i els bancs de la persona titular) perquè es reflecteixi a l'instant. Quan el compte ja és el per defecte, es mostra un indicador en lloc del botó.
    - Nou avís (icona d'atenció) al costat del botó "Generar SEPA" quan el compte de domiciliació seleccionat no és el per defecte de la persona, indicant que cal guardar-lo com a tal perquè el canvi s'apliqui al PDF generat (l'endpoint `billing/sepa/download/<id>/` identifica el compte pel registre `GeneralPayment` ja persistit, no pel compte triat a pantalla).
    - 'locales/ca.ts', 'locales/es.ts': noves claus `common.save_as_default_payment`, `common.default_payment`, `common.default_payment_needed_for_sepa`.

### FIX
#### CONTRACT (`ContractRequestTermination.vue` — pas 6, botons de comptador amagats)
    - Al pas "Situació actual" (pas 6) d'una sol·licitud de contracte, el bloc de botons "Comptador fictici" / "Sense comptador" / "Nou comptador" / "Seleccionar comptador" només es mostrava quan el punt de subministrament encara no tenia cap comptador assignat (`v-if="!selectedMeter"`). Com que el flux de "Canvi de nom" reutilitza sempre el punt de subministrament del contracte actiu (que ja té un comptador), aquest bloc quedava sempre amagat i no hi havia manera de canviar-lo, afegir-ne un de fictici, etc. Eliminada la condició perquè el bloc es mostri sempre; quan ja hi ha un comptador assignat, el botó "Seleccionar comptador" passa a mostrar el text "Canviar comptador" (`billing_block.change_meter`, ja existent).
    - En activar "Comptador fictici" o "Sense comptador", el bloc "Comptador seleccionat/actual" (`MeterDetail`) es continuava mostrant per sota, encara que ja no apliqués. Ara aquest `fieldset` només es mostra quan hi ha `selectedMeter` i cap dels dos modes (`continueWithoutMeter`/`withoutMeter`) està actiu.
#### CONTRACT
    - En canviar el compte de domiciliació SEPA d'una sol·licitud/contracte, `onPersonBankSelected` només actualitzava `selectedBankDebit`, però no l'objecte (`localPayment`) que es passa a `InputSepa` per generar el document. En clicar "Generar SEPA" tot seguit, el PDF es continuava vinculant al compte bancari i titular anteriors en lloc dels acabats de seleccionar. Ara `onPersonBankSelected` també actualitza `localPayment.IBAN` (i reinicialitza `sepa_document`) amb el nou compte seleccionat.

    - Filtre avançat "Deute" (`has_debt`): Deutor / No deutor a `pages/contract/contracts/index.vue`, enviat via `contract-api.js` (`getAll` i export Excel) com a `has_debt=true|false`. Requereix el filtre backend ja desplegat.
    - Columna "Deute acumulat": ampliada de 70px a 130px perquè es vegin les fletxes d'ordenació (`ordering=debt_amount` / `-debt_amount`), ja cablejades amb `TableHeader`.
    - `TableHeader.vue`: el text es trunca i la icona d'ordenació no es comprimeix (`shrink-0`), perquè la fletxa es vegi també en columnes estretes.

## [21-07-2026]

### FEAT
#### BILLING (billing/sepa & billing/transfer)
    - S'ha afegit l'opció de generar una remesa de retorn per transferència, que acaba passant pel mateix recorregut que una remesa normal però amb diferents filtres. S'ha separat al menú i a les urls per major facilitat a l'hora de mostrar un o l'altre.
    
#### SERVICE (Lookup de comptadors per codes en massa)
    - 'pages/service/meters/index.vue': botó amb lupa al costat de l'export CSV que obre el modal de cerca en massa.
    - 'components/molecules/MeterLookupModal.vue': modal amb textarea per enganxar codis de comptador (un per línia, estil columna Excel) i botó cercar.
    - 'pages/service/meters/lookup.vue': pantalla d'avaluació amb pestanyes Trobats / No trobats, botó per copiar els no trobats (un per línia) al porta-retalls i export CSV async amb polling.
    - 'plugins/api/service/meter-api.js': nous mètodes `lookupByCodes` (`POST /service/meter/lookup-by-codes/`) i `lookupByCodesCsv` (`POST /service/meter/lookup-by-codes/csv/`).
    - 'locales/ca.ts', 'locales/es.ts': claus `service_block.meter_lookup_*`.
#### SERVICE (Adreça — nou camp "Ampliació")
    - 'components/molecules/AddAddress.vue': nou camp de text "Ampliació" (`address_extra`) al formulari de creació/edició d'adreça, al costat d'"Edifici". Es reinicia, es carrega (`assignValues`) i es desa (`save`) igual que la resta de camps d'adreça (`floor`/`door`/`stair`/`building`).
    - 'components/molecules/SupplyPointDetail.vue': mostrat el nou camp "Ampliació" a la fitxa de detall del punt de subministrament, al costat d'"Edifici", només quan té valor.
    - 'locales/ca.ts', 'locales/es.ts': nova clau `address_block.address_extra` ("Ampliació"/"Ampliación").
#### BILLING (`ReadingBatchRegion.vue` — anàlisi del lot i export CSV de SupplyPoints)
    - Export async de punts de subministrament del lot (`GET /billing/reading/by-batch/supply-points/csv-export/`) amb el mateix patró de polling que l'export de lectures; botó secundari al costat de l'export CSV existent.
    - Resum d'anàlisi al detall del lot: nº de rutes, punts de subministrament totals/actius i lectures entrades (amb fallback si el backend encara no envia `num_routes` / `num_supplies` / `num_active_supplies` / `num_readings` al detall).
    - El resum i l'export de SupplyPoints es mostren també quan el lot encara no té lectures; l'export de lectures queda deshabilitat si no n'hi ha.
    - Edició inline de metadades del lot (`token`, `name`, `created_at`) amb llapis/desar/cancel·lar (si `can_change`), via `PUT /billing/reading-batch/<id>/`; el wizard “Modificar” es manté per al flux de lectures.
    - `reading-batch-api.js`: nou mètode `exportSupplyPointsCsv`. Claus i18n `common.export_supply_points_csv`, `common.num_routes`, `common.active_supply_points` (ca/es).

### FIX
#### ORDER (`OrderMiniDetail.vue`)
    - Accés segur a `item.type?.name` quan `type` és null.

#### CONTRACT (Firma OTP duplicada al pas 7 de la sol·licitud de contracte)
    - 'components/molecules/ContractRequestSummary.vue': el widget de firma OTP (`MoleculesDocumentSignStatus`) es renderitzava dues vegades seguides al pas de resum/finalització: un primer bloc correctament condicionat per `documentSignEnabled` i un segon bloc idèntic sense cap condició, que sempre es mostrava encara que el flag `DOCUMENT_SIGN_ENABLED` estigués desactivat. Eliminat el bloc duplicat, de manera que ara es comporta igual que la pestanya "Documents" de `ContractRegion.vue`/`ContractDocumentsData.vue`.

## [20-07-2026]

### FIX
#### BILLING (`ReadingChange.vue`)
    - Controlar que la lectura anterior sigui o del mateix comptador o del mateix dia

#### CONTRACT (sol·licitud "Canvi de nom" — dades de Titular/Propietari/Inquilí precarregades incorrectament)
    - 'components/molecules/ContractRequestSetup.vue': en iniciar un "Canvi de nom", es precarregava el titular anterior del contracte (`contract.holder`) com a "Propietari" de la nova sol·licitud, i el llogater anterior (`contract.tenant`) com a "Inquilí". Eliminat tot el mecanisme `prefill_owner`/`prefill_tenant` (refs, payload d'`emitChange` i el segon `save()` a `ContractRequestEdit.vue` que assignava `owner`/`tenant` en crear la sol·licitud): ara el pas "Persones" (Titular, Propietari, Inquilí) queda sempre buit en un "Canvi de nom", perquè l'usuari hi introdueixi les dades noves des de zero.
    - `nuxt.config.ts`: afegit el plugin `smart-metering-api.js` a la llista explícita de plugins; sense això `$SmartMeteringApiService` era `undefined` i el botó de lectura de tall petava abans d'arribar al backend.
    - `FieldDetail.vue`: el prop `value` accepta ara boolean/number/object (no només String), evitant warnings de Vue quan es mostren camps com telelectura.

### FEAT
#### CONTRACT (sol·licitud "Canvi de nom" — mantenir número de contracte i facturació de la lectura de tall)
    - 'components/organisms/ContractRequestEdit.vue', 'components/molecules/ContractRequestTermination.vue': els radiobuttons de "Codi de contracte" (Mantenir/Crear número nou) i "Facturació de la lectura de tall" (a la baixa/al nou contracte) ja no són `<input type="radio">` clàssics, sinó dues caixetes clicables (`role="radio"`) amb vora i fons ressaltats en blau i icona de check quan estan seleccionades, seguint el mateix patró visual per a totes dues.
    - 'components/molecules/ContractRequestTermination.vue': el bloc de "Facturació de la lectura de tall" ara només es mostra amb la mateixa condició que el de "Codi de contracte" (`is_change_of_name` de la sol·licitud, nou prop `isChangeOfNameRequest` passat des de `ContractRequestEdit.vue`), en lloc de mostrar-se sempre que hi hagués un contracte actiu i una baixa ja creada (independentment de si es tractava d'un "Canvi de nom").
    - 'components/organisms/ContractRequestEdit.vue': nou radiobutton horitzontal "Mantenir número de contracte" / "Crear número de contracte nou" al pas "Situació actual", visible només quan la sol·licitud és de tipus "Canvi de nom" (`is_change_of_name`). Nou camp `keep_same_code`, desat immediatament en canviar la selecció (`$ContractRequestApiService.save`) i també inclòs al `save()` del pas de baixes. Només es pot activar quan hi ha exactament una `ContractTerminationRequest` vinculada (`terminationData.value.length === 1`); en cas contrari l'opció queda deshabilitada amb un text explicatiu, i el frontend força `keep_same_code: false` en desar per no contradir la validació del backend (que rebutja `keep_same_code=True` si no hi ha exactament una baixa vinculada).
    - 'components/molecules/ContractRequestTermination.vue': nou radiobutton horitzontal "Facturar la lectura de tall a la baixa" / "Passar el consum al nou contracte d'alta" (camp `bill_cut_reading` de la `ContractTerminationRequest`, que fins ara no tenia cap control d'UI, només es desava programàticament). Ambdues opcions es poden seleccionar independentment del radiobutton "Codi de contracte"; quan `keep_same_code=true` es manté només un avís informatiu (el backend ignora aquesta selecció i força `bill_cut_reading=False`, facturant-se al proper trimestre), sense bloquejar-ne la interacció.
    - 'components/molecules/ContractRequestTermination.vue': quan es combina "Mantenir número de contracte" amb "Passar el consum al nou contracte d'alta", en prémer "Guardar Lectura manual" la mateixa lectura (valor, data, fuita, comptador) que es desa a la baixa es reenvia també com a lectura inicial del nou `ContractRequest` (`$ReadingApiService.saveRequestReading`), evitant haver d'introduir-la dues vegades.
    - Noves claus de traducció (`ca`/`es`): `contract_block.keep_same_code_title`, `keep_same_code_option`, `new_code_option`, `keep_same_code_disabled_info`, `keep_same_code_bill_cut_forced_info`, `bill_cut_reading_choice_title`, `bill_cut_reading_to_termination`, `bill_cut_reading_to_new_contract`.
    - Requereix canvis de backend (ja aplicats segons indicació): `ContractRequest.keep_same_code` exposat pel serializer (`fields = '__all__'`), validat contra el nombre de `ContractTerminationRequest` vinculades, i forçant `bill_cut_reading=False` a la baixa quan `keep_same_code=True`.
    - **Pendent de confirmar amb backend**: l'endpoint `POST /billing/reading/request-reading/` (`$ReadingApiService.saveRequestReading`) només accepta `contract_request_id`, `meter_id`, `reading_value` i `meter_mode` (sense data). Ara el frontend hi envia també `reading_date` i `leak_value` per transferir la lectura real de la baixa (no la d'avui) com a lectura inicial del nou contracte; cal que el backend accepti aquests dos camps opcionals i, si `reading_date` ve informat, creï la lectura inicial amb aquesta data en lloc de `now()`.
#### CONTRACT (Sol·licitud de contracte — lectura de tall via Smart Metering)
    - `ContractRequestTermination.vue`: nou botó **"Obtenir lectura de tall (Smart Metering)"** a la secció d'última lectura (canvi de comptador), visible quan el punt de subministrament té telelectura (`is_telecontrol`) i codi de comptador. En clicar, consulta l'endpoint nou del backend amb la data seleccionada, omple automàticament valor i data als camps de lectura manual, i mostra feedback visual (trobat / no trobat / error).
    - Nou plugin `plugins/api/billing/smart-metering-api.js` (`$SmartMeteringApiService`) amb `getMeterReading()`, `previewBatchReadings()` i `assignBatchReadings()`. Registrat a `nuxt.config.ts` (aquest projecte no autodescobreix plugins).
    - `locales/ca.ts`, `locales/es.ts`: noves claus `fetch_cut_reading_smart_metering`, `smart_metering_reading_found`, `smart_metering_reading_not_found`, `smart_metering_fetch_error`.

### CHORE
#### GENERAL (`locales/ca.ts`, `locales/es.ts`)
    - Eliminades diverses propietats duplicades dins l'objecte `contract_block` (`change_of_name`, `new_holder`, `apply_change_of_name`, `change_of_name_finalize_info`, `document_signs` i la resta de claus `document_sign_*`, `signed_at`), que provocaven l'error de TypeScript "An object literal cannot have multiple properties with the same name."
#### BILLING (Smart Metering — centralització del servei API al front)
    - `ReadingBatchEdit.vue`: el flux de preview/assignació de lectures Smart Metering del lot passa de `$ReadingBatchApiService` a `$SmartMeteringApiService`.
    - `reading-batch-api.js`: eliminats `previewSmartMetering`/`assignSmartMetering` (ara viuen al plugin dedicat).

## [17-07-2026]

### FEAT
#### SERVICE (`ClusterEdit.vue` — gestió de punts de subministrament per boquilla)
    - A cada boquilla ('ClusterNozzleEdit.vue') d'una bateria, ara es pot vincular/editar/desvincular directament el seu punt de subministrament sense sortir de la pantalla d'edició, mitjançant una nova regió lateral ("Seleccionar", "Crear nou", "Editar", "Desvincular") oberta amb els nous botons de llapis/més que apareixen al costat de cada punt de subministrament de la llista.
    - 'ClusterEdit.vue': en seleccionar un punt de subministrament ja existent (`MoleculesAddSupplyPoints`) o crear-ne un de nou, el vincle amb la `ClusterNozzle` es desa immediatament contra el backend (`$ClusterNozzleApiService.save`/`$SupplyPointApiService.save`), en lloc de quedar només en memòria fins prémer "Guardar" a tota la bateria.
    - 'FastSupplyPointEdit.vue': `loadFromDetail` ara sí rep i aplica les dades del punt de subministrament (`props.supply_point`) en obrir el formulari d'edició; abans es cridava sense paràmetre i el formulari sortia sempre buit.

### FIX
#### SERVICE (`ClusterEdit.vue`/`cluster-nozzle` — vinculació de punts de subministrament a una boquilla)
    - 'service/views/cluster_nozzle_view.py' (`ClusterNozzleViewSet.create`, backend): petava amb `TypeError: 'NoneType' object is not subscriptable` en crear/actualitzar una boquilla sense punt de subministrament nou (`request.data.get('supplyPoint')['placement']` quan `supplyPoint` no venia al payload, cas habitual des que `ClusterEdit.vue` esborra aquest camp abans d'enviar). Ara es comprova que `supplyPoint` existeixi abans d'accedir-hi.
    - 'service/serializers/cluster_nozzle_serializer.py' (`ClusterNozzleSaveSerializer.create`, backend): petava amb `TypeError: ClusterNozzle() got unexpected keyword arguments: 'supply_point_id'` en crear una boquilla nova amb un punt de subministrament ja existent vinculat (`supply_point_id`), ja que aquest camp no és del model `ClusterNozzle` i només es descartava a `update()`, no a `create()`. Ara `create()` també l'extreu abans de construir l'objecte.
    - 'service/serializers/cluster_nozzle_serializer.py': tant `create()` com `update()` rebien `supply_point_id` (vincle a un punt de subministrament ja existent, sense dades noves de `supplyPoint`) però el descartaven sense fer res, de manera que el punt de subministrament mai quedava vinculat a la boquilla. Ara ambdós mètodes assignen `SupplyPoint.cluster_nozzle` a la boquilla corresponent quan reben `supply_point_id`.
    - 'service/serializers/cluster_nozzle_serializer.py': en reassignar un punt de subministrament diferent a una boquilla que ja en tenia un altre vinculat, el nou quedava afegit sense desvincular l'anterior (una `ClusterNozzle` pot tenir diversos `SupplyPoint` per FK inversa), acumulant-se tots els punts assignats en sessions successives. Ara, abans de vincular `supply_point_id`, es desvincula (`cluster_nozzle=None`) qualsevol altre punt de subministrament que ja pengés d'aquella boquilla.
    - 'ClusterEdit.vue' (`onSupplyPointSelected`): en seleccionar per una boquilla un punt de subministrament que localment ja estava assignat a una altra posició de la mateixa bateria, ambdues boquilles competien per reclamar-lo en desar tota la bateria (condició de carrera segons quina petició arribava última). Ara es neteja localment el `supplyPoint` de l'altra boquilla abans d'assignar-lo a la nova.
    - 'plugins/api/service/cluster-nozzle-api.js' (`doDelete`): una resposta buida (204, habitual en un `DELETE`) es tractava com a error i llançava `Error estructura 'results' no trobat`, provocant un `Unhandled promise rejection` en eliminar boquilles sobrants en desar la bateria. Ara simplement es retorna la resposta del `DELETE` tal qual.
    - 'ClusterEdit.vue': el toast d'èxit en vincular/crear un punt de subministrament feia servir la clau inexistent `common.saved` (amb text fallback embegut). Substituïda per `common.saved_successfully`, ja existent a `locales/ca.ts`/`locales/es.ts`; substituïts també altres textos amb fallback embegut (`common.error` → `common.error_save`, `common.back` → `common.previous`, `common.unlink`, `common.select`, `common.new_register`) per les claus de traducció ja existents.


#### CONTRACT (Firma OTP de documents — Aqua360 Sign)
    - Nou plugin `plugins/api/documentmanager/document-sign-api.js` (`$DocumentSignApiService`), amb els mètodes CRUD estàndard i els endpoints específics `getByContract`, `getAllSummary`, `send` i `getDownloadUrl`, seguint el model `DocumentSign` de backend (status 1=Pending, 2=Sended, 3=Signed, -1=Error).
    - Nou component `DocumentSignStatus.vue`: mostra la caixa d'estat de la firma OTP d'un contracte (badge d'estat, missatge d'error si `status=-1`, botó de descàrrega quan hi ha document firmat) i el formulari/botó per iniciar-la (nom/email/tlf de l'signant) quan encara no s'ha demanat. Integrat dins `ContractDocumentsData.vue`, per la qual cosa apareix automàticament a totes les pantalles que ja usaven aquest component: la pestanya "Documents" de `ContractRegion.vue` i la barra de documentació de `ContractRequestEdit.vue` (sol·licitud de contracte).
    - 'ContractTabs.vue': moguda la pestanya "Documents" entre "Incidències" i "Comunicacions".
    - 'ContractDocumentsData.vue': el formulari de firma OTP (nom/email/telèfon del signant) es preomple automàticament amb les dades ja disponibles al contracte/sol·licitud: nom del titular (`holder.full_name`), email (contacte digital seleccionat o primer contacte amb email) i telèfon (primer contacte amb telèfon).
    - Nova pàgina `pages/contract/document-signs/index.vue` amb el llistat de tots els documents amb firma OTP (filtre per estat, descàrrega del document firmat/pendent) i nova entrada al menú lateral (`NavSidebar.vue`) "Documents firmats" dins la secció de Contractació.
    - Noves claus de traducció (`ca`/`es`): `contract_block.document_signs`, `document_sign_otp`, `document_sign_not_requested`, `document_sign_needs_contract`, `document_sign_sent`, `signed_at`, i `common.retry`/`common.refresh`.
    - Backend ara accepta crear el `DocumentSign` amb el camp `contract_request` (id de la ContractRequest) en lloc de `contract` durant el flux d'alta (abans que existeixi contracte). `DocumentSignStatus.vue` i `ContractDocumentsData.vue` (nou prop/computed `contractRequestId`/`signContractRequestId`) usen aquest camp com a fallback quan la sol·licitud encara no té `request.contract`, permetent iniciar la firma OTP també en altes noves. S'ha afegit `getByContractRequest` a `$DocumentSignApiService` (assumeix el mateix endpoint `document-signs-by-contract/` amb paràmetre `contract_request_id` — **pendent de confirmar amb backend** si cal un paràmetre/endpoint diferent).
    - 'ContractRequestSummary.vue': afegida la caixa de firma OTP dins el bloc "Doc" (substituint el botó comentat "signar contracte"), amb la mateixa lògica de `signContractId`/`signContractRequestId` i autoemplenat de nom/email/telèfon a partir del `holder` i els contactes de la sol·licitud, consistent amb `ContractDocumentsData.vue`.
    - 'pages/contract/document-signs/index.vue': la columna de contracte ara és clicable. Si el `DocumentSign` té `item.contract`, obre `ContractRegion` amb aquest id; si encara no en té i té `item.contract_request`, obre `ContractRequestRegion`. S'ha afegit la regió lateral (`right_page`) amb tots dos components, seguint el patró de la resta de pàgines de llistat.
    - Tota la funcionalitat de "Firma OTP de documents" es pot activar/desactivar sense desplegament, mitjançant el nou flag `DOCUMENT_SIGN_ENABLED` de `config-project` (consultat via `$ConfigProjectApiService.get('DOCUMENT_SIGN_ENABLED')`, sense endpoint nou; el valor es modifica des de `/admin/` o el CRUD de `config-project`). Nova acció `fetchDocumentSignEnabled`/estat `documentSignEnabled` a `stores/useConfigStore.ts`, seguint el mateix patró ja existent per `OV_ENABLED`. Amb el flag desactivat: s'amaga l'enllaç "Documents firmats" del menú lateral (`NavSidebar.vue`), es redirigeix a `/` en accedir directament a `/contract/document-signs/`, i s'amaga el widget `DocumentSignStatus` dins `ContractRequestSummary.vue` i `ContractDocumentsData.vue`.

#### CONTRACT (Firma OTP de documents)
    - El nou plugin `document-sign-api.js` no s'havia afegit a la llista de plugins de `nuxt.config.ts` (aquest projecte registra cada servei API manualment en lloc d'autodescobrir-los), per la qual cosa `$DocumentSignApiService` era `undefined` i petava tant a `DocumentSignStatus.vue` com a la pàgina de llistat. Afegit `~/plugins/api/documentmanager/document-sign-api.js` al bloc de plugins.
    - 'pages/contract/document-signs/index.vue': refeta perquè segueixi exactament l'estètica i estructura de `pages/billing/invoice/index.vue` (capçalera amb `TableHeader`, formulari de filtres amb el mateix `FilterSelect :plain="true"` per l'estat, botons de mostrar/reiniciar filtres). Afegides les claus de traducció `document_sign_status_pending/sended/signed/error`.
    - 'stores/useConfigStore.ts': `$ConfigProjectApiService` es desestructurava de `useNuxtApp()` a nivell de mòdul (una sola vegada, en carregar l'arxiu) en lloc de dins de cada acció. Si el context de Nuxt encara no estava llest en aquell moment, el servei quedava `undefined` per sempre en aquell tancament i totes les crides a `fetchOvEnabled`/`fetchDocumentSignEnabled` fallaven silenciosament (capturades pel `try/catch`, sense arribar mai a fer la petició HTTP), deixant `ovEnabled`/`documentSignEnabled` sempre a `false` encara que el valor a backend fos `true`. Ara `useNuxtApp()` es crida dins de cada acció, en el moment en què s'executa.
    - 'pages/contract/document-signs/index.vue', 'DocumentSignStatus.vue': el botó de descàrrega del document firmat era un `<a :href target="_blank">` apuntant directament a un endpoint autenticat (`IsAuthenticated`, Token auth de DRF); el navegador no hi afegeix el header d'autenticació, per la qual cosa la descàrrega fallava. Substituït per un `<button>` que crida la utilitat ja existent `openAuthenticatedFileUrl(url, false)` (`utils/open-authenticated-file.ts`), que fa el `fetch` amb el header `Authorization` i dispara la descàrrega a partir del blob rebut, igual que ja fa `ContractRequestSummary.vue`/`InvoiceView.vue`/`PaymentRegion.vue` per a altres documents.

#### BILLING (comptador de factures processades congelat a 0)
    - 'components/molecules/BillingSummary.vue': el comptador "Factures processades" es quedava a 0 encara que la cua anés avançant. Es llegia amb `queueRes.invoices_processed ?? queueRes.processed_items`, però per alguns `task_type` el backend envia sempre `invoices_processed` present i fixat a `0` (no `null`/`undefined`), de manera que `??` mai queia cap a `processed_items` (el camp que sí que anava pujant). Canviat a `||` i actualitzat a cada tick del polling independentment de l'`status` concret.

#### BILLING (factures ja processades — botons d'eliminar/recalcular actius)
    - 'components/atoms/InvoiceEdit.vue': una factura amb `type_final === 'F'` (ja definitiva/processada) permetia igualment clicar "Eliminar" i "Recalcular", accions que no té sentit aplicar-hi. Afegit `computed isInvoiceProcessed` i desactivats (`:disabled`) ambdós botons amb tooltip explicatiu quan la factura ja està processada.
    - 'locales/ca.ts', 'locales/es.ts': nova clau `billing_block.invoice_already_processed`.

## [16-07-2026]

### FEAT
#### READINGS (Importació de documents amb validació prèvia)
    - Nou flux d'entrada de lectures amb **validació abans de processar**: pujar amb `auto_process=false`, preview (`validate`), confirmar (`process`) amb polling Celery.
    - `AddReadings.vue`: pantalles d'upload (fitxer + plantilla + panell de mapping) i de preview (stats filtrables, taula amb camps efectius, paginació via API).
    - Entrada a **pantalla completa** (`/reading/readings/add`) en lloc de la region lateral; el lot de lectures hi redirigeix i recupera el document en tornar.
    - `reading-document-api.js`: mètodes `update`, `validate`, `process`, `reprocess`; gestió del `409` (tasca ja en curs) enganxant-se al `task_id` existent.
    - Docs d'API al `docs/` i traduccions `ca`/`es` del nou flux.

#### SERVICE (`RouteRegion.vue` — exportació de posicions de ruta)
    - Nou botó "Descarregar CSV" a la pestanya de posicions d'una ruta, que genera un fitxer amb totes les posicions de la ruta (no només la pàgina visible), incloent finques i punts de subministrament de cadascuna, amb columnes separades per `;`.
    - 'plugins/api/service/route-api.js': nou mètode `exportRoutePositions(routeId)`, que llança la generació en segon pla (Celery) i es controla amb el mateix mecanisme de `task-progress` ja usat en altres exportacions (`use_aca`, informes).
    - Requereix un canvi de backend (endpoint que llanci la tasca i generi el CSV amb `;` com a separador) — pendent de confirmar amb l'equip de backend.

### FIX
#### CONTRACT (sol·licitud "Canvi de nom" — tipus de contractació incorrecte/bloquejat)
    - 'components/molecules/ContractRequestSetup.vue': eliminat el fallback que precarregava dades (tipus, categoria, ús...) del primer contracte del punt de subministrament quan cap coincidia amb el contracte actiu, cosa que podia copiar per error el tipus d'un contracte no relacionat (p. ex. "Agrícola").
    - 'components/molecules/ContractRequestSetup.vue': el selector de "Tipus de contractació" ja no es bloqueja mai; sempre és editable.
    - 'components/molecules/ContractRequestSetup.vue': en el flux de "Canvi de nom" ja no es preselecciona cap "Tipus de contractació"; queda buit per defecte.
    - 'plugins/api/contract/contract-request-type-api.js' (`getByToken`): corregit perquè cerqui explícitament l'element pel seu `token` en lloc d'assumir que el primer resultat retornat ja és el correcte.

#### BILLING (descàrrega de PDF de factura en producció)
    - 'utils/open-authenticated-file.ts': la descàrrega/visualització de fitxers autenticats (PDF de factura, entre d'altres) fallava en producció quan el backend retornava una URL relativa (p. ex. `/media/uploads/billing/invoices/...`), ja que es resolia contra el domini del frontend en lloc del backend. Ara es prefixa amb `apiHost` qualsevol URL que no porti ja un esquema (`http(s)://`, `blob:`, `data:`...).

#### GENERAL (error `Cannot access 'X' before initialization` en 37 pàgines de llistat)
    - En obrir directament una pàgina de llistat amb `?action=showDetail&id=...` a la URL, saltava un `ReferenceError` de TDZ i la regió lateral no s'obria. Totes aquestes pàgines segueixen el mateix patró (`toggleRegion`/`checkRouteQuery`/`showDetail` + `watch(route.query, {immediate:true})`), i en 37 d'elles les variables `detail`/`selectedItemId`/`isSubRegionOpen` es declaraven DESPRÉS de `toggleRegion`, que ja les feia servir: com que el `watch` amb `immediate:true` crida aquesta cadena de funcions de manera síncrona durant el `setup()`, es podia accedir a la variable abans que s'inicialitzés. Mateixa causa i mateix fix ja aplicat abans a `contract-requests/index.vue` (10-07-2026), ara generalitzat a la resta de llistats afectats: moure aquestes declaracions abans de `toggleRegion`.

## [15-07-2026]

### FEAT
#### CONTRACT (nova sol·licitud "Canvi de nom")
    - 'components/molecules/ContractActionsDropdown.vue': nova opció "Canvi de nom" al menú d'accions del contracte, que redirigeix a `/contract/contract-requests/add?contract_id=<id>` (mateix patró que "Nova ordre de treball").
    - 'components/molecules/ContractRequestSetup.vue': nou prop `prefillContractId`. Quan es crea una sol·licitud nova amb aquest prop (i encara no hi ha `request`), es carrega automàticament el contracte indicat, es preselecciona/bloqueja el mateix punt de subministrament (i els addicionals) reaprofitant la lògica ja existent de `onSupplyPointSelected` (que ja copiava categoria/ús/tarifa/gestió de deute del contracte actiu), es bloqueja el selector de tipus de sol·licitud i es preselecciona el tipus "Canvi de nom" (buscat via el nou token de configuració `contract_request_type_change_name_token`), i s'emeten `prefill_owner`/`prefill_tenant` amb el propietari/inquilí del contracte actual. El camp "Sol·licitant" es renombra a "Nou titular" en aquest mode.
    - 'components/organisms/ContractRequestEdit.vue': passa `prefill-contract-id` (des de `route.query.contract_id`, només quan encara no existeix `request`) a `ContractRequestSetup`. En crear la sol·licitud (`saveStep(0)`), si venen `prefill_owner`/`prefill_tenant`, es fa un segon `save()` (mateix patró ja usat per `price_rates_ids` en creació) per fixar `owner`/`tenant` al nou `ContractRequest`, de manera que el pas "Persones" ja els mostra precarregats i només cal seleccionar un titular nou.
    - Requereix als canvis de backend indicats al xat: un nou registre a `contract/contract-request-type` (p. ex. token `CANVI_NOM`) i una nova clau `contract_request_type_change_name_token` a `coredata/config-project` que apunti al seu id.
    - 'locales/ca.ts', 'locales/es.ts': noves claus `contract_block.change_of_name` i `contract_block.new_holder`.
    - FIX: el tipus de contractació i el punt de subministrament no es precarregaven mai. `ContractRequestEdit.vue` passa sempre un `request` inicialitzat a `{}` (mai `null`) a `ContractRequestSetup`, de manera que la comprovació `!props.request` a l'`onMounted` d'aquest últim era sempre falsa. Canviat a `!props.request?.id` (un objecte buit no té `id`, una sol·licitud real sí).
    - FIX: com que la clau `contract_request_type_change_name_token` encara no existeix a `coredata/config-project` (pendent de crear-se a backend), la consulta directa `$ConfigProjectApiService.get(token)` (endpoint de detall `.../config-project/<token>/value/`) retornava 404 amb el missatge "No ConfigProject matches the given query." i mostrava un toast d'error, i com que el selector de "Tipus de contractació" es bloquejava incondicionalment en mode "Canvi de nom" (encara que no s'hagués trobat cap tipus), l'usuari es quedava sense poder-hi seleccionar res. Ara es fa servir `$ConfigProjectApiService.getAll(token)` (llistat filtrat per `?token=`, que no peta si no hi ha cap resultat) i el selector només es bloqueja (`isTypeLocked`) quan el tipus "Canvi de nom" s'ha trobat i preseleccionat correctament; si la configuració encara no existeix, el selector queda actiu perquè l'usuari pugui triar el tipus manualment.
    - CANVI DE COMPORTAMENT EN FINALITZAR: com que un "Canvi de nom" és conceptualment idèntic a una `ContractSurrogation` (només canvia el titular sobre el mateix contracte, sense donar-lo de baixa ni crear-ne un de nou), el botó de finalitzar ja no crida sempre `$ContractRequestApiService.finalize()` (que crea un `Contract` nou). `ContractRequestEdit.vue` detecta ara si la sol·licitud és de tipus "Canvi de nom" i, en aquest cas, crida un nou mètode `$ContractRequestApiService.finalizeInPlace()` (`plugins/api/contract/contract-request-api.js`, `PUT /contract/contract-request/finalize-in-place/<id>/` — **endpoint pendent de crear a backend**, veure més avall). També es mostren un banner informatiu i un text de confirmació/botó diferents ("Aplicar canvi de nom") quan la sol·licitud és d'aquest tipus.
    - REFACTOR (seguint indicació de backend): substituïda tota la resolució via `coredata/config-project` (`contract_request_type_change_name_token`) per una identificació directa i explícita pel `token='canvi_nom'` del `ContractRequestType`, ja existent a BD (sense dependre d'ids fixos que varien entre entorns):
      - 'plugins/api/contract/contract-request-type-api.js': `getAll()` accepta ara un paràmetre `token` opcional (`&token=<token>`), i s'afegeix `getByToken(token)` com a drecera.
      - 'components/molecules/ContractRequestSetup.vue' (`applyChangeOfNamePrefill`): ara resol i preselecciona el tipus amb `$ContractRequestTypeApiService.getByToken('canvi_nom')` en lloc de consultar `coredata/config-project`.
      - 'components/organisms/ContractRequestEdit.vue': `isChangeOfNameRequest` ara compara directament `request.type.token === 'canvi_nom'` (amb `getDetail` puntual de fallback si `type` arriba com a simple id sense `token` niat), en lloc de comparar ids resolts via config-project.
      - Ja NO cal crear la clau `contract_request_type_change_name_token` a `coredata/config-project` (esmena a la indicació anterior); només cal el registre `ContractRequestType` amb `token='canvi_nom'` (ja existent, `id=7` a l'entorn de referència, però el frontend no en depèn).
      - `applyChangeOfNamePrefill` també corregeix la semántica del camp `owner`: ara es preomple amb el **titular anterior** (`contract.holder`) en lloc del rol real de propietari (`contract.owner`), per obtenir la traçabilitat "de qui a qui" indicada per backend (`ContractRequest.holder` = nou titular, `ContractRequest.owner` = titular anterior).
      - Es confirma que la baixa vinculada (pas "Situació actual", `ContractRequestTermination.vue::terminate()`) ja envia sempre el `ContractTerminationRequest.type` resolt pel token de configuració `termination_type_holder_change` (mecanisme genèric preexistent, reutilitzat sense canvis per aquest flux).

### CHORE
#### BILLING (`pages/billing/reports/add.vue`)
    - Ampliats els filtres globals de la pàgina de generació d'informes: ara es pot filtrar per persona i per contracte, a més de facturació i remesa, i tots quatre admeten selecció múltiple. S'han afegit els nous botons "Selecciona persona"/"Selecciona contracte" al panell de filtres globals, seguint exactament el mateix patró visual i d'interacció que ja existia per a "Selecciona facturació"/"Selecciona remesa": obren el panell lateral (`#right_page`) amb un llistat paginat/cercable, cada clic sobre una fila marca/desmarca l'element (fons groc) sense tancar el panell, i els elements triats es mostren com a caixes verdes amb botó per eliminar-los individualment.
    - 'components/molecules/AddPersons.vue': nou component, calcat de `AddBillings.vue`/`AddContracts.vue` (mateix contracte `selected_items`/`multiple`/`item-clicked`), amb cerca (`$PersonApiService.getAll`), taula (identificador, tipus físic/jurídic, nom) i paginació.
    - Reutilitzat `components/molecules/AddContracts.vue` (ja existent, mateix patró que `AddBillings.vue`) per a la selecció múltiple de contractes.
    - 'components/organisms/SEPARemittanceList.vue': nous props `multiple` i `selected_items` (array), seguint el mateix patró que `AddBillings.vue`, per permetre marcar/desmarcar diverses remeses en mode `allow_select` sense tancar el panell després de cada clic.
    - El payload enviat a `POST /statistics/report-queue/<id>/trigger/` (via `triggerReport`) inclou ara `billing_ids`, `remittance_ids`, `person_ids` i `contract_ids` (llistes d'ids separades per comes), mantenint `billing_id`/`remittance_id` (primer element seleccionat) per compatibilitat amb els informes personalitzats (`AcaReportForm.vue`, `RatesReportForm.vue`, `GenericReportForm.vue`) que encara treballen amb una única facturació/remesa.

### MODIFIED
#### ORDER
    - 'components/molecules/OrderMiniDetail.vue': el llistat d'ordres de treball d'un contracte (`ContractTabs.vue`) només mostrava les ordres vinculades directament al `contract_id` de la sol·licitud, no les vinculades al punt de subministrament del contracte (mode "Punt de subministrament" d'`OrderEdit.vue`, ja usat des de la incidència/contracte). Afegit el nou prop `supply_point_ids` (array), passat des de `ContractTabs.vue` amb els ids de `contract.supply_points`, i nou paràmetre `supply_point_ids` a `plugins/api/order/order-api.js` (`getAll`), que s'envia com a `&supply_point_ids=<id1>,<id2>,...` a `GET /order/order/`.
    - 'components/molecules/OrderMiniDetail.vue': afegida una nova columna "Contracte" al llistat d'ordres, que mostra `related_contract_token` quan l'ordre pertany al contracte (o a un altre contracte relacionat) i el deixa buit (`-`) quan l'ordre només prové del punt de subministrament, per poder-les diferenciar visualment.
    - 'locales/ca.ts', 'locales/es.ts': afegida la traducció de la nova clau `common.contract` (`Contracte`/`Contrato`), reaprofitant l'entrada ja existent al bloc `common` (junt amb `contracts`).

#### BILLING (`pages/billing/reports/add.vue`)
    - 'pages/billing/reports/add.vue': en finalitzar la generació d'un informe estàndard des de la cua (`startPollingReport`), si el backend només retornava `document_id` (sense `document_url`), el fitxer no es descarregava automàticament i calia esperar que l'usuari anés a l'historial de "Processos Finalitzats" i cliqués manualment "Descarregar". Ara, quan l'estat passa a `completed` i hi ha `document_id` però no `document_url`, es crida directament `downloadQueueDocument` (mateix mètode ja usat des de l'historial) per descarregar el document sense intervenció de l'usuari.
    - 'pages/billing/reports/add.vue': el toast que apareix en finalitzar la descàrrega d'un informe estàndard no estava traduït (mostrava la clau `reports_block.report_completed_success` literal, ja que no existia al fitxer de traduccions) i no identificava l'informe. Afegides les claus `reports_block.report_completed_success`/`report_generation_failed` a `locales/ca.ts` i `locales/es.ts`, amb interpolació `{name}`, i `startPollingReport` ara rep i mostra el `report.name` (en lloc del token/id) en el missatge d'èxit i d'error.

## [14-07-2026]

### FIX
#### SUPPLYPOINT
    - 'SupplyPointEdit.vue': canviar que no sigui obligatori el paràmetre de guardar el source del supplypoint ja que no sempre hi és i el del placement.

#### COMMUNICATION
    - 'CommunicationProcessRegion.vue': en seleccionar una extensió de fitxer al desplegable de `DocumentList.vue` (dins la pestanya "Documents" d'una `CommunicationRegion` oberta com a subregió d'un procés de comunicació), es tancava tota la regió lateral. El `<CommunicationRegion>` no declara l'event `'change'` (només `'changed'`), de manera que el `@change="refresh(false)"` que hi havia lligat es convertia en un listener natiu de DOM sobre l'arrel del component; l'event nadiu `change` del `<select>` de `DocumentList.vue` hi feia bombolla i disparava `refresh(false)`, que sempre emet `'changed'` independentment del paràmetre `close`, provocant el tancament de la regió des de la pàgina. Eliminat el binding `@change` sobrant, mantenint només `@changed="refresh(false)"`.

## [13-07-2026]

### FEAT
#### SETTINGS (Configuració ACA)
    - 'pages/settings/config_aca/index.vue': nova pàgina de configuració ACA (`/settings/config_aca/`) accessible des de Configuració. Toggle principal `uses_aca` per activar/desactivar la integració; taula de paràmetres ConfigProject amb selectors en cascada (VariableType, ContractUseType, Product, PriceRate); desat en bloc via `bulk-update-values`. Inclou el paràmetre `contract_keeper_use_type_token` (selector de `ContractUseType`, desant només el token). Secció de codis comptables per concepte: recorregut Product → PriceRate → BillingRange → LineItemType, amb indicació visual de l'interval actiu (`billing_range_active`) per tarifa.
    - 'plugins/api/coredata/config-project-api.js': nou mètode `bulkUpdateValues()` (`POST /coredata/config-project/bulk-update-values/`) i correcció de `get()` per acceptar valors booleans `false`.
    - 'plugins/api/pricing/article-code-api.js': nou plugin CRUD per `ArticleCode` (`/pricing/article-code/`). Registrat a `nuxt.config.ts`.
    - 'pages/settings/index.vue': enllaç a la configuració ACA sota el bloc Configuracions.
    - Noves claus de traducció (`ca`/`es`) a `settings_block`: `config_aca`, `aca_enable`, `aca_enable_help`, `aca_disabled_hint`, `aca_line_items`, `aca_line_items_help`, `aca_select_article_code`.
    - 'plugins/api/contract/contract-use-aca-api.js': nou plugin per consultar estadístiques (`GET /contract/contract-use-aca/`) i executar l'ompliment de `Contract.use_aca` (`POST /contract/contract-use-aca/`, dry-run, async i `update_all_contracts`). Registrat a `nuxt.config.ts`.
    - 'pages/settings/config_aca/index.vue': nova secció **Contractes use_aca** amb comptadors (`active_contracts`, `filled_use_aca`, `pending_use_aca`), simulació d'ompliment, execució real en segon pla amb seguiment via `task-progress`, opció de reprocessar tots els contractes actius i desglossament de motius d'omissió.

### FIX
#### SETTINGS (Configuració ACA)
    - 'pages/settings/config_aca/index.vue': corregit fals positiu de toast "Error" en omplir `use_aca` quan el backend retornava la tasca correctament. El polling ara normalitza estats de `task-progress` (`SUCCESS`/`COMPLETED`/etc.), accepta resultats d'ompliment sense wrapper `state`, evita toasts genèrics si la resposta inclou estadístiques de negoci, i consulta el progrés sense passar per `checkTask` (que podia mostrar errors paral·lels). Deixat d'enviar `update_all_contracts` al POST async mentre la tasca Celery del backend no accepta aquest paràmetre; el toast d'error mostra ara el missatge real de `task-progress.error`.

## [10-07-2026]

### FIX
#### GENERAL
    - 'IncidentRegion.vue': quan s'obria com a subregió d'una altra regió (p. ex. des de `ContractRegion.vue`) i s'hi obria alhora una subregió pròpia (p. ex. "Afegir tasca"), aquesta no es sobreposava com a overlay al mateix nivell que la regió germana, sinó que quedava incrustada al layout de graella intern, fent inaccessible/invisible el botó de tancar (que ja existia al codi). El `<div id="subregion">` no tenia la lògica condicional segons `isSubRegion` (`fixed top-0 right-0 w-[48vw] z-50` + `translate-x-0`/`translate-x-full`) que ja fa servir `ContractRegion.vue` per aquest mateix cas. Aplicat el mateix patró, tant al `<div id="subregion">` com al contenidor arrel (`grid-cols-2` només quan `SubRegion && !isSubRegion`).

#### CONTRACT
    - 'pages/contract/contract-requests/index.vue': en accedir amb un `?id=` a la URL, saltava l'error `Cannot access 'isSubRegionOpen' before initialization` dins `toggleRegion`. El `watch(() => route.query, ..., { immediate: true })` crida `checkRouteQuery()` → `showDetail()` → `toggleRegion()` de manera síncrona durant el `setup()`, però `isSubRegionOpen`, `detail` i `selectedItemId` (usats dins `toggleRegion`) es declaraven més avall al fitxer, provocant un error de TDZ (Temporal Dead Zone) amb `const`. Mogudes les tres declaracions abans de `toggleRegion`, eliminant els `const` duplicats que hi havia més avall.

## [09-07-2026]

### FEAT
#### BILLING / REPORTS (Gestió manual de tasques de cua penjades)

    - 'plugins/api/statistics/reports-api.js': nou mètode `sendReportsQueueAction(queueItemId, action)` que crida `POST /statistics/report-queue/<id>/action/`.
    - 'plugins/api/billing/billing-api.js': nous mètodes `sendBillingQueueAction(queueItemId, action)` (`POST /billing/billing-queue/<id>/action/`) i `getBillingQueue(billingId = null)` (accepta un `billingId` opcional per filtrar la consulta).
    - 'pages/billing/reports/index.vue': al bloc "Processos Actius" de la cua d'informes, afegits els botons "Reiniciar", "Saltar" i "Matar tasca" (amb confirmació prèvia) per gestionar una tasca de Celery penjada de `ReportQueue`.
    - 'components/organisms/BillingEdit.vue': mateixos botons al bloc "Processos Actius" de la cua de facturació (`BillingQueue`).
    - Ambdues pàgines inclouen ara `skipped` al filtre i al badge del bloc "Historial de Processos Finalitzats", ja que backend ha afegit aquest nou estat.
    - Noves claus de traducció (`ca`/`es`): `common.restart`, `common.skip`, `common.kill_task`, `billing_block.error_queue_action`, `reports_block.error_queue_action`, `confirmation_text_block.confirm_kill_queue_task`/`confirm_skip_queue_task`/`confirm_restart_queue_task`.

### FIX
#### CONTRACT

    - 'ContractTerminationDetail.vue': en obrir `ContractTerminationRegion.vue` es produïa l'error `Cannot access 'loadPreviousReadings' before initialization`. La funció `loadPreviousReadings` (i el ref `previousReadings`) es declaraven al final del `<script setup>`, però `getData()`, que la crida, s'executava síncronament durant el `setup()` per culpa del `watch(() => props.termination, ..., { immediate: true })`, abans que la `const loadPreviousReadings` s'hagués inicialitzat (error de TDZ). Moguda la declaració abans de `getData`/`fetchData`.

#### BILLING (cua de facturació — estat "Processant" incorrecte, refresc continu i falta de botó de reintent)

    - 'billing/views/billing_batch_generate_view.py' (`BillingQueueListView`, backend): `GET /billing/billing-queue/` només retornava els últims 10 items `completed`/`failed` **de tot el sistema** (`[:10]`, sense filtrar per lot), ni tenia en compte el nou estat `skipped`. Si hi havia més de 10 lots amb tasques finalitzades recentment a qualsevol banda de l'app, l'item `failed`/`skipped` d'un lot concret podia quedar fora d'aquesta finestra. Ara l'endpoint accepta `?billing_id=<id>` per retornar tots els items d'aquell lot sense el límit dels 10 globals, i el filtre inclou `skipped`. També es gestiona l'estat `REVOKED` de la tasca de Celery a l'autoreparació d'items `running` (abans queia pel forat entre `PROGRESS`/`SUCCESS`/`FAILURE` i l'item es quedava penjat indefinidament).
    - 'components/atoms/ProcessColorBadge.vue' (usat a `pages/billing/billing/index.vue` i `BillingEdit.vue`): com que el frontend no trobava l'item (per la limitació anterior de l'endpoint), interpretava "no trobat" com "acabat amb èxit" i emetia `refresh`; com que `Billing.status` mai canvia quan la cua falla, la pàgina tornava a mostrar "Processant" i repetia el cicle cada 2 segons indefinidament. Ara consulta `/billing/billing-queue/?billing_id=<id>` i n'agafa l'item més recent per `created_at`, detectant de manera fiable un `failed`/`skipped` i mostrant un badge vermell "Failed" amb botó de rellançar (`action=restart`) en lloc d'entrar en bucle. A més, s'ha eliminat la crida redundant a `GET /task-progress/<task_id>/` a cada tick (2s): l'endpoint de `billing-queue` ja retorna `percent`/`status` calculats, així que `checkTask` només es manté com a fallback pel cas (no usat en aquesta pàgina) en què el component només rep `taskId` sense `billingId`.
    - 'components/molecules/BillingSummary.vue' (usat a `pages/billing/billing/edit/[id].vue` via `BillingEdit.vue`): consolidats diversos problemes relacionats amb el mateix polling de cua:
      - El badge/botó "Reiniciar" no reconeixia l'estat `skipped`, i en el flux on el component només rep `task_id` (sense `queue_item_id`, com passa des d'aquesta pàgina) la branca `FAILURE` no marcava `queueStatus.value = 'failed'`, per la qual cosa ni el badge "Failed" ni el botó de reiniciar es mostraven mai. Ara sí es marca l'estat, i s'ha afegit el botó "Reiniciar" també dins la caixa vermella d'estat (no només a la fila de botons superior).
      - Com que `billing_id` és sempre conegut en aquest component, el polling prova primer `/billing/billing-queue/?billing_id=<id>` (evitant repetir cada 5s la crida a `GET /task-progress/<uuid>/`); aquesta última només es manté com a últim recurs quan no hi ha ni `billing_id` ni `queue_item_id` disponibles.
      - Fins i tot amb aquest fallback, si el lot no té cap `BillingQueue` associat (p. ex. proves manuals sobre un lot antic), la crida a `checkTask` es repetia indefinidament sense parar mai perquè només gestionava `SUCCESS`/`FAILURE` i ignorava `REVOKED` (tasca matada manualment). Ara també es gestiona `REVOKED` i s'ha afegit un límit de 90 intents (com a `ProcessColorBadge.vue`) abans de marcar-lo com a `failed`.
      - `restartQueueTask` resol l'id de l'item a rellançar (`resolveFailedQueueItemId`, filtrant per `billing_id` sense el límit dels 10 globals) i, quan no en troba cap (lot sense entrada a la cua), fa un recàlcul complet (`regenerate()`, la mateixa acció que el botó "Recalcular factures") en lloc de fallar silenciosament.
    - 'components/organisms/PaymentRegion.vue': `regeneratePaymentDocument` obria el PDF amb `window.open(file.pdf_url, '_blank')` directament, sense passar el token d'autenticació, fent fallar la descàrrega/visualització. Ara usa `openAuthenticatedFileUrl` (mateixa utilitat que `InvoiceView.vue`), que fa el `fetch` autenticat i obre el blob resultant.

#### SERVICE

    - 'SupplyPointDetail.vue': en canviar la selecció de punt de subministrament des de `ContractRequestSetup.vue`, el bloc "Contracte" no s'actualitzava i es quedava amb les dades del primer punt de subministrament carregat. La llista de contractes (`contracts`) es calculava una única vegada dins `onMounted`, sense recalcular-se quan el `watch` de `props.id` tornava a executar `fetchData()` en canviar de selecció. Ara `contracts` és un `computed` reactiu a `localData` i `activeContractToken`.

#### CONTRACT

    - 'ContractRequestTermination.vue': en clicar "Donar de baixa" a una sol·licitud de contracte es produïa l'error `Cannot read properties of undefined (reading 'value')`. La lògica que inicialitza `last_reading_values` (una entrada per cada punt de subministrament del contracte, necessària pels `v-model` de valor/fuita/data de lectura) només s'executava dins `loadData()`, però `terminate()`, `clickGuardarLectura()` i el `watch` de `billCutReading` assignaven `termination_request.value` directament des de l'API sense recalcular-la, deixant `last_reading_values` buit i el `.find(...)` del template retornant `undefined`. Extreta la lògica a una funció `syncLastReadingValues()` i cridada després de cada assignació de `termination_request.value`.
    - 'ContractRequestSummary.vue': en tancar el formulari de pressupost/factura (`closeInvoiceData`) es produïa l'error `fetchTerminationInvoices is not defined`, una crida a una funció que no existeix (residu d'una refactorització anterior). La funció `fetchInvoiceData()`, ja cridada a la mateixa funció, recorre `contract_termination_requests` i en carrega les factures, per la qual cosa el bucle mort s'ha eliminat.

### MODIFIED
#### CONTRACT

    - 'ContractRequestAddressPayment.vue': en afegir un telèfon de contacte (`onPhoneSelected`), ara s'habilita automàticament l'opció d'SMS per aquell telèfon (s'afegeix també a `selectedSMSPhones`) sense necessitat de marcar-la manualment amb el botó de l'icona SMS.

#### BILLING

    - 'BillingDocumentsSummary.vue': la capçalera de la taula de factures tenia només 8 columnes amb etiquetes obsoletes (nom, DNI, adreça, ubicació) que no corresponien a les 9 columnes/dades reals que mostra cada fila (`InvoiceEdit.vue`). S'ha alineat la capçalera amb les columnes reals (client, contracte, tipus d'ús, pagament, total factura, total a pagar, dies), igual que ja estava fet a `BillingSummary.vue`. A més, s'ha eliminat l'ordenació de tots els camps excepte "Total factura" i "Total a pagar", que passen a mostrar-se com a etiquetes estàtiques sense icona ni acció de clic.

## [08-07-2026]

### FIX
#### CONTRACT
    - 'ContractRequestEdit.vue', 'ContractRequestTermination.vue': en una sol·licitud de contracte (alta), un cop desada la lectura inicial del comptador al pas "Situació actual", el pas de finalització seguia bloquejant el botó "Finalitzar" amb "Falta la lectura inicial del nou contracte" encara que la lectura s'hagués desat correctament. Calien tres correccions conjuntes:
      - El nom del camp que lliga la lectura amb la sol·licitud varia segons l'endpoint: `contract_request` en crear-la (`POST /billing/reading/request-reading/`) i `contract_request_id` quan ve niada dins `supply_point.last_meter_reading` del detall/guardat de la sol·licitud. La validació (`runValidation`, `ContractRequestTermination.vue`) només comprovava un dels dos noms. Ara es comproven ambdós.
      - `saveRequestReading()` no notificava el component pare en desar la lectura, de manera que `request.supply_points` quedava desactualitzat. Ara emet `change-sp` amb la lectura actualitzada, i `handleSupplyPointChanged` torna a executar `runValidation()` sempre (abans només si `currentStep.value === 5`, condició que no es complia editant "Situació actual" des del panell lateral d'una sol·licitud ja existent, amb `editingStepIndex` en lloc de `currentStep`).
      - En avançar del pas "Situació actual" al de "Finalització" (`nextStep` → `saveStep(5)`), es tornava a cridar `$ContractRequestApiService.save()` i el `last_meter_reading` que retorna aquest guardat reflecteix la darrera lectura activa del comptador a nivell global (pot pertànyer a una altra sol·licitud/contracte si el comptador es reutilitza), no la d'aquesta sol·licitud concreta, sobreescrivint la lectura correcta ja coneguda al frontend per una d'incorrecta. Ara es preserva la lectura local sempre que estigui marcada com a inicial i lligada a l'id d'aquesta sol·licitud.

#### BILLING
    - 'BillingDocumentsSummary.vue': el comptador "Documents generats" no es refrescava amb l'últim valor retornat pel backend en finalitzar el procés del `BillingQueue` (només s'actualitzava mentre l'estat era `running`). Ara també s'actualitza `documents_generated`/`total_items` en detectar la finalització (`percent >= 100` o `status === 'completed'`).
    - 'BillingDocumentsSummary.vue': en accedir a la pàgina d'una facturació ja completada (sense `task_id`/`queue_item_id` actiu), el comptador "Documents generats" no es mostrava. Ara, igual que "Factures processades", es mostra amb el total de factures quan `counters` ja està disponible.

#### ORDER
    - 'OrderRegion.vue' (usat des de `pages/order/orders/index.vue`): aplicada la mateixa correcció feta a `ClusterRegion.vue`, la pestanya "Observacions" es mostrava amb un espai en altura molt més petit que la resta de pestanyes. Ara la secció té la mateixa alçada mínima/màxima (`calc(100vh - 320px)`) i scroll intern, i el contenidor arrel del component sempre porta `h-full` per evitar que es col·lapsi quan s'obre com a subregió.
    - 'pages/order/orders/index.vue': en recarregar la pàgina amb un filtre d'estat desat de la sessió anterior, es feia una petició amb `status=[object Object]` (error 500 al backend) perquè `handlePageChange`, `handleSort`, `onChangeRegion` i la càrrega inicial passaven `selectedFilters` (array d'objectes `{id, name}` usat per la UI del desplegable) a `$OrderApiService.getAll` en lloc de `statuses` (array d'ids). A més, `statuses` no es desava ni es restaurava de `sessionStorage`, per la qual cosa es perdia igualment en recarregar. Ara totes les crides usen `statuses.value` i aquest s'inclou a l'estat persistit.

### CHORE
#### CONTRACT
    - 'ContractDetail.vue': eliminat el camp "Gestió del deute" (`debt_management`) del detall del contracte.
    - 'ContractRequestPriceRate.vue': eliminat el selector "Tipus de gestió del deute" (`debt_management_type`) del pas de tarifes de la sol·licitud de contracte, junt amb la càrrega de `contract/contract-debt-management` (`loadDebtManagements`) i l'enviament de `debt_management` a `emitChange`.
    - 'ContractRequestEdit.vue': eliminada la referència morta a `priceRateAndCategoryData.value.debt_management` (pas 4, "Documents, Tarifa i Variables") ja que aquest camp ja no s'emet des de `ContractRequestPriceRate.vue`.

#### GENERAL (`GeneralNoteList.vue`)
    - 'plugins/api/notification/general-note-api.js', 'layouts/default.vue', 'GeneralNoteList.vue': en crear-se un nou avís general, es mostra ara a tots els usuaris (connectats en aquell moment, o en fer login/accedir a la web) com a Toast informatiu blau (`toast.info`), amb el nom d'usuari remitent en una línia petita i el text de l'avís a sota, incloent el propi usuari que l'envia. Un cop mostrat, l'avís es marca automàticament com a llegit (`$GeneralNoteApiService.save({id})`) i no es torna a mostrar en properes comprovacions ni sessions. `layouts/default.vue` comprova els avisos pendents en accedir a qualsevol pàgina autenticada i cada 60 segons mentre l'usuari està connectat (nou mètode `getUnseen()` a l'API), mantenint sincronitzat el comptador del badge (`sideBarStore.newGeneralNotes`).

### MODIFIED
#### ORDER
    - 'OrderEdit.vue': quan l'ordre es crea des d'una incidència (`IncidentRegion.vue`) o des del contracte (`ContractActionsDropdown.vue`, botó "Nova ordre de treball"), ja no es vincula directament el contracte (mode "Contracte") sinó el seu punt de subministrament per defecte (mode "Punt de subministrament"), per evitar exposar dades sensibles del contracte. El contracte obtingut es guarda en un nou ref intern `linkedContract` per si l'usuari canvia manualment el radiobutton a "Contracte", cas en què es precarrega automàticament sense tornar-lo a demanar.
    - 'OrderEdit.vue': en canviar entre els radiobuttons de tipus d'ubicació (punt de subministrament, adreça, connexió, contracte) ja no s'esborren les seleccions prèvies dels altres tipus; es mantenen en memòria per si l'usuari hi torna.
    - 'IncidentRegion.vue': l'obertura d'`OrderEdit` des del menú "Afegir ordre de treball" ara passa també `contract_id` (derivat del contracte de la incidència), a més de l'`incident_id` que ja s'enviava.

#### GENERAL (component `FilterSelect`)
    - 'FilterSelect.vue': afegit el nou prop `plain`, que aplica l'estil neutre dels botons d'acció (com `filterShow`) en lloc de l'estil blau habitual, sense afectar la resta d'usos del component.

#### ORDER
    - 'pages/order/orders/index.vue': el filtre d'"Estat" es mostra ara directament a la barra principal de cerca (abans del botó de filtres avançats), fent servir el mateix `FilterSelect` que abans només apareixia dins de "Filtres addicionals" (amb `:plain="true"` perquè no es mostri en blau). S'ha eliminat l'opció "Estat" del desplegable de filtres addicionals per evitar-ne la duplicació.

#### BILLING
    - 'pages/billing/invoice/index.vue': aplicat el mateix canvi que a `orders/index.vue`: el filtre d'"Estat" es mostra directament a la barra principal (amb `:plain="true"`) en lloc de dins de "Filtres addicionals", eliminant-ne la duplicació.

## [07-07-2026]

### FEAT
#### CONTRACT

    - 'ContractActionsDropdown.vue': nova opció "Nova ordre de treball" al menú d'accions del contracte, que redirigeix a `/order/orders/add?contract_id=<id>`. 'OrderEdit.vue' i 'pages/order/orders/add.vue': afegit el nou prop `contract_id`, que si es rep preselecciona el contracte (carregant-lo via `$ContractApiService.getDetail`) i el subministrament per defecte, deixant l'ordre ja vinculada al contracte en crear-la.
    - 'locales/ca.ts', 'locales/es.ts': afegida la traducció de la nova clau `documents_generated`.

### FIX
#### SERVICE

    - 'ClusterRegion.vue': la pestanya "Observacions" es mostrava amb un espai en altura molt més petit que la resta de pestanyes, dificultant escriure una nova observació. Ara la secció té la mateixa alçada mínima/màxima (`calc(100vh - 320px)`) i scroll intern que la pestanya de subministraments, i el contenidor arrel del component sempre porta `h-full` (igual que `ConnectionRegion.vue`) per evitar que es col·lapsi quan s'obre com a subregió.

### CHORE
#### BILLING

    - 'locales/ca.ts', 'locales/es.ts': afegida la traducció del nou camp `subtotal_consumption` retornat per l'endpoint `/billing/billing/pre-invoices/<id>/summary`, mostrat a `InvoiceSummaryDetail.vue` dins del resum de facturació.


#### REMITTANCE RETURN

    - S'ha afegit que es pinti del color que li pertoca (ex: verd --> pagat, lila --> vençut, gris --> pendent,...) a l'estat anterior del pagament de retorn que es mostra.

### MODIFIED
#### BILLING

    - 'BillingDocumentsSummary.vue', 'BillingSummary.vue': adaptats als nous camps de l'endpoint `/billing/billing-queue/<id>/` per a `DEFINITIVE_INVOICE` (`total_items` ja no és el doble de les factures del lot, sinó el nombre real; s'hi afegeixen `invoices_processed` i `documents_generated`). El comptador de "Factures processades" ara llegeix `invoices_processed` (amb fallback a `processed_items` per als altres `task_type` que no l'envien) i es mostra com a `X / total_items`. S'afegeix un nou comptador "Documents generats" (`documents_generated / total_items`) per distingir la fase de confirmació de factures de la de generació de PDFs.

## [03-07-2026]

### FIX
#### BILLING
    - 'InvoiceDetail.vue', 'InvoiceDetailEdit.vue', 'InvoiceListDetail.vue', 'InvoiceTemplateRegion.vue': error potencial en accedir a `origin.name` quan `origin` és `null`. Afegit encadenament opcional (`?.`).
    - 'SupplyPointDetail.vue': error potencial en accedir a `status.name`/`status.color`, `meter.code`, `property.route_position.route.route_zone.token` i `connection.token` quan algun dels objectes intermedis és `null`. Afegit encadenament opcional (`?.`).
    - 'SupplyCutDetail.vue': error potencial en accedir a `supply_point.meter.code` i `supply_point.connection.token`. Afegit encadenament opcional (`?.`).
    - 'BailDetail.vue': error potencial en accedir a `contract.status_name`/`status_color` quan `contract` és `null`. Afegit encadenament opcional (`?.`).
    - 'ClusterDetail.vue': error potencial en accedir a `property.route_position.token`. Afegit encadenament opcional (`?.`).
    - 'CommunicationProcessDetail.vue', 'JoinedPaymentDetail.vue', 'PaymentDetail.vue': error potencial en accedir a `status.name`/`status.color`. Afegit encadenament opcional (`?.`).

#### GENERAL (component `AtomsColorBadge`/`ColorBadge`)
    - Diversos components que renderitzen un `AtomsColorBadge`/`ColorBadge` a partir de `X.status.name`/`X.status.color` petaven quan `status` era `null`: 'PaymentCommitmentList.vue', 'SEPARemittanceReturnDetail.vue', 'PaymentsList.vue', 'SEPARemittanceDetail.vue', 'PayCommitmentInvoice.vue', 'OrderMiniDetail.vue', 'OrderTypeDetail.vue', 'ReturnCommimentPayment.vue', 'AddWalletCommitmentPayment.vue', 'PaymentCommitmentWalletList.vue', 'InvoiceMiniDetail.vue', 'SEPAAnomalyPaymentsList.vue', 'SEPAPaymentsList.vue', 'ClaimRequestOrdersRegion.vue', 'ClaimRequestContractSelectionRegion.vue', 'ClaimRequestEdit.vue', 'ClaimRequestContractListRegion.vue', 'JoinedPaymentRegion.vue', 'wallet-managements/index.vue', 'billing/messages/index.vue', 'contract/aca-documents/edit/[id].vue'. Afegit encadenament opcional (`?.`) a totes les crides.

### CHORE
#### GENERAL
    - 'plugins/global-error-handler.client.js': nou handler global que captura errors no controlats de Vue (`vue:error`, `app:error`) i promeses rebutjades sense gestionar (`unhandledrejection`), els registra amb context i mostra un toast genèric a l'usuari.
    - 'utils/log-error.ts': nova funció `logError(context, error, extra)` que centralitza el format del `console.error` (missatge, status, dades de resposta i error complet) perquè qualsevol error es pugui depurar amb context suficient.

### MODIFIED
#### BILLING
    - 'SepaReturnSetup.vue': Ara sempre es poden modificar lectures, bloquejant la lectura que es trobi en una facturació pendent de confirmar i limitant l'anterior a aquesta. També es permet modificar directament el ús estimat, origen i bloquejar ús estimat si no es vol mirar la bossa i mantenir el consum que toca sense restar res.

#### SERVICE (`AddNewRoutePosition.vue`, `AddRoutePosition.vue`)
    - 'AddNewRoutePosition.vue': el desplegable de "Ordre de ruta" es saturava en rutes amb milions de posicions. Substituït per un input numèric simple. Sota el camp es mostra ara un missatge en verd ("La posició està lliure") o vermell ("La posició ja està ocupada") comprovant-ho puntualment contra el backend (nou endpoint `check_position`, amb debounce de 300ms), sense carregar cap llista de posicions.
    - 'AddRoutePosition.vue': eliminat el radio "La posició està al sistema?" (Sí/No), ja que amb l'input numèric i la comprovació en temps real ha quedat sense utilitat. El botó d'acció mostra ara sempre el mateix text ("Assignar posició"/"Desar").
    - 'RouteEdit.vue': eliminada la lògica `insertConflict`/`defaultExistingPosition` associada al radio eliminat.

#### GENERAL
    - 'plugins/api/api-manager.js': totes les crides que fallen (`fetch`, `checkTask`, `submitMassiveCancelContract`, `getUserPermissions`) ara registren l'error a la consola amb `logError` (endpoint, mètode i dades) abans de mostrar el toast a l'usuari.

## [02-07-2026]

### FEAT
#### READING

    - 'ReadingBatchReadingsSummary.vue': afegit el botó "Nou lot de subs. sense lectures" dins de la regió de "Subministraments sense lectura" (al costat del botó "Estimar tots"), que demana el nom del lot, hi anteposa el prefix "Sub. sense lectura - " i crea directament un nou lot de lectures amb els comptadors dels subministraments actualment sense lectura, saltant-se el pas de creació/selecció de rutes i portant l'usuari directament al pas de configuració del nou lot

### FIX
#### ORDER

    - 'pages/order/orders/index.vue': el filtre de "Municipi" mostrava tots els municipis de la província en lloc dels municipis que realment tenen ordres de treball. Ara es demana al backend el llistat de municipis amb ordres (respectant la resta de filtres actius) mitjançant el nou endpoint `getFilterCities`.

#### BILLING

    - 'InvoiceSelectionRegion.vue': error `Cannot read properties of null (reading 'name')` en carregar factures amb `status` a `null`. Afegit encadenament opcional (`?.`) a l'accés a `invoice.status.name`/`invoice.status.color`.

### MODIFIED
#### BILLING

    - 'BillingSummary.vue': afegida la causa "Sense comptador" (`cause_no_meter`) a la taula de "Causes possibles" dins de "Possibles contractes no facturats", mostrant `infoMissingContracts.no_meter` (dada ja retornada pel backend però no mostrada al frontend).

## [01-07-2026]

### FIX
#### READING
    - 'ReadingBatchEdit.vue': fer que al passar del pas 2 al pas 3 de processar un lot, en cargar pendents de facturar, agafi les lectures pertinents en el mateix fluxe que l'smart metering

### MODIFIED
#### CLAIM MANAGEMENT
    - 'ClaimRequestContractSelectionRegion.vue' Ara al pas dos de vulnerabilitat, es poden seleccionar contractes filtrant o afegint un csv igual al descarregat per enviar el informe. També es pot consultar el contracte i veure el import total a pagar pendent dintre de la sol·licitud
    - 'ClaimRequestEdit.vue' Ara al filtrar els contractes a afegir a una gestió de impagats es pot filtrar per la vulnerabilitat real que es fa servir (0, 1, 2) i afegir un nom a la gestió

#### Mode de comptador en sol·licituds de finalització de contracte (`ContractRequestTermination`)

- **Nova funcionalitat**: el botó "Seguir sense comptador" s'ha substituït per dos botons diferenciats:
  - **"Comptador fictici (Aforament / Incendis)"**: per a casos que requereixen un comptador fictici amb calibre (comportament equivalent a l'anterior opció). Desa `meter_mode: fictional` al backend.
  - **"Sense comptador"**: permet finalitzar la sol·licitud sense assignar cap comptador. Desa `meter_mode: none` al backend.
- **Millora**: el botó "Finalitzar" s'habilita quan qualsevol dels dos modes alternatius està actiu, sense necessitat de tenir un comptador assignat.
- **Millora**: el mode seleccionat es restaura automàticament en tornar a obrir la sol·licitud gràcies al camp `meter_mode` retornat pel backend.

#### Gestió de posicions de ruta (`RouteEdit`, `AddRoutePosition`, `AddNewRoutePosition`)

- **Correcció**: en afegir una posició nova o editar-ne una existent amb una posició inferior a la mínima carregada, ara es mostra correctament a la llista en lloc de desaparèixer.
- **Correcció**: en editar una posició existent i canviar-la a una posició ja ocupada per una altra, el bloc contigu a partir d'aquella posició es desplaça +1 (igual que ja es feia per a posicions noves).
- **Correcció**: en eliminar una posició que s'havia afegit i modificat durant la mateixa sessió, ja no s'envia simultàniament com a addició i eliminació al backend.
- **Millora**: quan el panell lateral té "Sí, seleccionar posició" actiu i l'usuari tria un número de posició, la llista principal fa scroll fins a aquella posició i la remarca en blau durant 2 segons.
- **Correcció**: en clicar el botó "+" entre dues posicions ocupades, el formulari ara pre-selecciona correctament la posició del conflicte en lloc de l'última posició disponible (condició de carrera resolta amb watcher reactiu).
