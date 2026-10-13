# Changelog Frontend

## [09-10-2026]

### REFACTOR
#### DOWNLOADS (`plugins/api/documentmanager/export-job-api.js` — cua de descàrregues)
    - El plugin passa de `plugins/api/importexport/` a `plugins/api/documentmanager/` i crida `/documentmanager/export-job/`, la nova ubicació de l'`ExportJob` al backend. Cal desplegar-lo junt amb el backend.

## [08-10-2026]

### FEAT
#### BILLING (`BillingInvoicesSummary.vue` — padró de facturació a la cua de descàrregues)
    - Al pas final del lot, «Padró de facturació», «Padró de facturació reduït» i «Resum de contractes sense ACA» van a la cua de descàrregues amb el nom «<informe> – <lot>». El fitxer es descarrega sol quan està llest encara que s'hagi sortit del lot, i queda al menú Descàrregues.
    - Si el backend encara retorna només `task_id`, es manté el badge d'abans.

#### GENERAL (`stores/useExportJobs.ts`, `components/molecules/ExportJobsMenu.vue`, `NavTopPinned.vue`, `layouts/default.vue`, `useServerExport.ts`, `DownloadXlsxButton.vue`, `export-job-api.js`, `api-manager.js`, `reading-api.js`, `locales/*` — cua de descàrregues)
    - Nou menú **Descàrregues** a la barra superior (icona al costat dels avisos generals): llista les exportacions de l'usuari amb l'estat (en cua, generant, llest, error, cancel·lada), quan es van demanar i quant van tardar. Permet descarregar, cancel·lar, treure de la llista i netejar les acabades. Mostra un spinner mentre n'hi ha alguna en curs i un comptador de fitxers acabats que encara no s'han vist.
    - Les exportacions del servidor ja no depenen de la pàgina: en prémer el botó, la feina entra a la cua i es mostra un avís. Quan acaba, el fitxer es descarrega automàticament encara que s'hagi canviat de pàgina o refrescat, i sempre queda disponible al menú.
    - Funciona per als ~40 llistats amb `DownloadXlsxButton` i per a l'exportació de lectures. El nom de la descàrrega és el títol de la pàgina (o la nova prop `exportName`).
    - Els endpoints que encara només retornen `task_id` continuen amb el polling d'abans.
    - Claus noves `export_jobs.*` als quatre idiomes.

### FIX
#### CONTRACT (`BankDetail.vue` — botons del document SEPA al detall del contracte)
    - Els botons del SEPA (baixar/veure, pujar el signat i enviar per correu) estaven a la mateixa línia que l'IBAN i, en algunes pantalles, quedaven tapats.
    - Ara el SEPA té un camp propi amb l'etiqueta «SEPA», sota l'IBAN i el SWIFT, amb la icona d'estat (✓ signat / ✗ no signat) i els botons al costat. És el mateix format que el de la sol·licitud de contracte.

#### CONTRACT (`pages/contract/aca-documents/edit/[id].vue`, `plugins/api/contract/contract-api.js`, `locales/*` — validació de documents ACA)
    - La pantalla «Processar documents» d'un document ACA no trobava mai els contractes de l'abonat: llegia `contracts_holder`/`contracts_tenant`/`contracts_owner` del detall de la persona, que el backend ja no retorna (refactor de `PersonSerializer`, 31-03-2026). L'excepció es mostrava com «No existeix cap persona amb el document…». Ara es busquen amb el nou `ContractApiService.getByPerson(id)` (`/contract/contract/?persons=<id>`: titular, propietari o llogater).
    - Si el DNI de la línia no identifica una sola persona (DNI genèric com `99999999R`, que el backend ara respon amb 409, o inexistent), es busca pel nom que porta el fitxer. Si en surten diverses, s'agafa la que és titular, propietària o llogatera del contracte de la línia (nou `ContractApiService.getByToken`); si no, els resultats es mostren al cercador perquè l'usuari triï. En triar una persona del cercador es carrega per `id`, no pel DNI.
    - El bloc del contracte no es pintava (error de Vue `nextSibling`): llegia `contract.supply_point.address_complete`, camp que no existeix. Ara és `supply_point_default?.address_complete`, i `holder?.full_name` per als contractes sense titular.
    - Propietari i llogater es mostraven amb l'etiqueta «Tipus de client»; ara «Propietari» i «Llogater».
    - Textos: `check_changes`, `accepted_changes`, `finish`, `validate` i `reject` es demanaven a `contract_block.*` però són a `common.*`; «Nom» i «NIF/CIF» estaven escrits com a clau (ara `common.name` i `common.person_id`), i «Dades del document» té la clau nova `contract_block.aca_document_data` als quatre idiomes.

#### BILLING (`InvoiceMiniDetail.vue` — llistat compacte de factures: columna «Títol» i alineació)
    - La columna «Títol» (mode `is_info`, p. ex. a `AffectedClaimContracts`) passa de 120px a 200px. Un títol massa llarg, encara que no tingui espais, es retalla amb punts suspensius en lloc de trepitjar la columna del costat, i es veu sencer en passar-hi el ratolí.
    - Capçalera i files alineades: les columnes `1fr` passen a `minmax(0, 1fr)`. Abans creixien segons el contingut i cada fila (que és una graella independent) podia quedar diferent de la capçalera.
    - La plantilla de columnes es construeix a partir de les columnes que es mostren realment (pagaments, titular i enviar només quan toquen). En mode `is_info` hi sobrava una columna, perquè no es mostra «Titular».
    - El número de factura es mostra sencer i en una sola línia, amb una amplada mínima de 170px (`minmax(170px, 1fr)`) perquè no es solapi amb «Pagament». Si el panell és massa estret, la taula fa scroll horitzontal.

## [07-10-2026]

### FIX
#### BILLING (`InvoiceRegionModals.vue` — opcions excloents en abonar una factura pagada)
    - En generar l'abonament d'una factura pagada es podien marcar alhora «Guardar total pagat a saldo» i «Retornar el saldo automàticament». Ara són excloents: en marcar-ne una es desmarca l'altra (també es poden deixar totes dues sense marcar, com abans).
    - «Retornar el saldo» ja no depèn de tenir marcat «Guardar a saldo» i el selector del mètode de devolució només es mostra quan està marcat.
    - La crida al backend no canvia: retornar el saldo continua enviant `return_paid_total: true` + `return_paid_total_balance: true`, perquè el backend fa l'entrada i la sortida del saldo.
#### BILLING (`CommitmentDepositPayments.vue`, `locales/*` — cèntims del fraccionament d'un compromís de pagament)
    - En fraccionar un compromís, cada pagament s'arrodonia per separat amb `toFixed(2)` i la suma podia quedar un o més cèntims per sota (100 € / 3 → 99,99 €) o per sobre (200 € / 3 → 200,01 €) del total. Aleshores apareixia «Diferència a completar» i no es podia continuar sense corregir els imports a mà.
    - Ara el repartiment es fa en cèntims: tots els pagaments tenen el mateix import base i els cèntims sobrants s'afegeixen automàticament al **primer pagament** (100 € / 3 → 33,34 + 33,33 + 33,33).
    - Quan hi ha ajust es mostra un avís que explica que s'han afegit X € al primer pagament perquè la divisió no és exacta. L'avís desapareix si es modifiquen els imports a mà.
    - Clau nova `claim_block.rounding_adjustment_info` als quatre idiomes.
#### COREDATA (`call-register-api.js`, `AddNewCall.vue`, `ContractTabs.vue` — registre de trucades)
    - En reescriure `CallRegisterApiService` (commit `4887991f`) es van perdre els mètodes `save` i `getDetail`. En prémer «Finalitzar», `$CallRegisterApiService.save` no existia, l'error s'empassava en silenci i el modal es tancava sense guardar res (ni la trucada ni les anotacions). Es restauren tots dos mètodes.
    - El modal de registre de trucada té un botó **«Cancel·lar»** per sortir sense guardar.
    - En tancar el modal després de guardar, la pestanya «Registre de trucada» del contracte (fitxa i contracte fixat) es recarrega i hi apareix la trucada nova. La llista de `ContractTabs` es manté muntada amb `v-show` i no rebia el `reload` del pare; ara `ContractTabs` accepta la prop `reload` i la passa a `CallRegisterList`. A la fitxa de persona ja es recarregava.
    - Si el guardat falla, el modal ja no es tanca i es conserven les anotacions; els botons es desactiven mentre es desa.
#### CONTRACT (`ContractRequestDetail.vue` — descarregar la factura de la sol·licitud)
    - El botó de descàrrega de la factura cridava `downloadInvoice`, que no existia al component (`_ctx.downloadInvoice is not a function`). Ara baixa el PDF temporal si la factura encara no té fitxer, o obre el document si ja en té, amb el mateix comportament que al resum de la sol·licitud.

### FEAT
#### GENERAL (`layouts/default.vue`, `pages/index.vue`, `ContractDetail.vue`, `ContractRequestTermination.vue`, `StreetPicker.vue` — tancar regions amb ESC)
    - La tecla ESC tanca la regió oberta. Si n'hi ha diverses (una sub-regió dins d'una altra), tanca primer la de més a la dreta.
    - Abans ja hi havia un handler, però agafava la primera regió del DOM (sovint una de tancada, que queda fora de pantalla) i no feia res. Ara només té en compte les regions visibles i clica el botó de tancar de la seva pròpia barra (`#region_nav`).
    - Si el cercador (Ctrl+K) està obert, ESC només tanca el cercador.
    - Els components que ja fan servir ESC (desplegable de factures de `ContractDetail`, confirmació de lectura de `ContractRequestTermination`, desplegable de `StreetPicker`) en fan `preventDefault()`, i llavors la regió de sota no es tanca. S'ha tret el `preventDefault()` incondicional de `pages/index.vue`, que ho bloquejava a l'inici.
#### CONTRACT (`ContractActionsDropdown.vue` — compromís de pagament des del menú del contracte)
    - Nova opció **«Nou compromís de pagament»** a la secció de facturació del menú dels tres punts del contracte (fitxa i contracte fixat). Obre la creació del compromís amb el contracte ja seleccionat (`/billing/commitment-deposits/add?contract_id=<id>`).
    - Només apareix si el contracte té deute (`debt_amount > 0`, el mateix valor que el badge «Deute»).
#### CONTRACT (`useStandaloneVariableTypes.js`, `AddVariable.vue`, `bonifications.vue`, `ContractRequestPriceRate.vue` — variables només via bonificacions)
    - Una variable vinculada a un tipus de bonificació (`variable_types` del tipus) ja no es pot afegir sola: només s'afegeix des de la bonificació. Les úniques que es poden afegir individualment són les personalitzades (no vinculades a cap tipus de bonificació, actiu o no).
    - Nou composable `useStandaloneVariableTypes` que calcula aquests tipus personalitzats (recorre totes les pàgines de tipus de bonificació).
    - `AddVariable` només ofereix els tipus personalitzats en crear una variable nova, amb una nota explicativa; si no n'hi ha cap, mostra un avís i amaga el botó de desar. Editar una variable existent (també les d'una bonificació) funciona com abans.
    - El botó «Nova variable» de la pàgina de bonificacions del contracte i del pas de tarifes de la sol·licitud només es mostra si hi ha tipus personalitzats.
    - Claus `contract_block.no_standalone_variable_types` / `standalone_variable_types_info` als quatre idiomes.
    - La restricció és només al frontal: el backend continua acceptant qualsevol tipus de variable.
#### DASHBOARD (`CalendarTaskEdit.vue` — visibilitat de les tasques del calendari)
    - La casella «Mostrar a tots els usuaris», que en desmarcar-la canviava el text a «Mostrar només a mi» però quedava desmarcada, passa a ser un selector «Visibilitat de la tasca» amb dues opcions: **Tots els usuaris** o **Només l'usuari assignat**, amb un text d'ajuda per a cada cas.
    - En triar «Només l'usuari assignat» apareix el camp «Usuari assignat», preseleccionat amb l'usuari actual; no es pot desar sense usuari.
    - Claus noves `dashboard.task_visibility`, `show_all_info`, `show_only_assigned`, `show_only_assigned_info` i `assigned_user`; s'elimina `show_only_me`.
#### CONTRACT (`SendSepaEmailModal.vue`, `SepaQuickActions.vue`, `InputSepa.vue`, `ContractRequestAddressPayment.vue`, `general-payment-api.js`, `locales/*` — enviar el document SEPA per correu)
    - Fins ara el document SEPA (autorització de domiciliació) només es podia descarregar en PDF. Ara també es pot enviar directament per correu al client.
    - Botó **«Enviar SEPA per correu»** a la icona de sobre al costat de descarregar/pujar el SEPA (fitxa del contracte i alta), al panell «Document SEPA» (alta, modificació de dades i subrogació) i al costat de «Generar document SEPA (no domiciliat)».
    - El botó torna a generar el document perquè reflecteixi les dades actuals i obre el modal nou `SendSepaEmailModal`: remitent (per defecte, el de la companyia del contracte), correu del client (contactes del contracte i del titular, o un altre a mà), idioma, assumpte i cos.
    - Nou mètode `sendSepaEmail` a `GeneralPaymentApiService` i claus `contract_block.sepa_send_email` / `sepa_email_*` als quatre idiomes.
    - Va amb l'endpoint nou `POST /billing/sepa-document/<id>/send-email/` del backend.
#### INCIDENT (`IncidentEdit.vue`, `IncidentDetail.vue`, `IncidentRegion.vue`, `locales/*` — vincular una incidència a una bateria)
    - Nou cercador «Cerca una bateria específica» a la creació d'incidències, al costat dels de contracte, factura, ordre, compromís i punt de subministrament. En triar-ne una, se'n carrega el detall i es mostra amb `ClusterDetail`, amb el botó per treure-la.
    - Una incidència es pot guardar només amb una bateria vinculada. S'envia el camp `cluster` i el component accepta la prop `cluster_id` per obrir-lo des d'una bateria.
    - El detall de la incidència mostra la bateria amb enllaç a la regió lateral (`ClusterRegion`) i a la pàgina de bateries.
    - Nova clau `search_block.search_cluster` als quatre idiomes.
    - Va amb el camp nou `Incident.cluster` del backend.
#### CONTRACT REQUEST (`SepaQuickActions.vue`, `BankDetail.vue`, `ContractRequestAddressPayment.vue`, `ContractDetail.vue`, `locales/*` — signar el mandat SEPA des de l'indicador)
    - Al costat de la X / check del document SEPA hi ha dos botons: **descarregar** el document per signar (genera el SEPA i l'obre; si ja està signat, el botó passa a ser un ull per veure'l) i **pujar el document signat**, que el desa i el marca com a revisat en un sol pas.
    - El mateix a la fitxa del contracte (`ContractDetail.vue`), només quan es pot modificar i no és una subregió.
    - A la sol·licitud, el botó «Generar SEPA» se substitueix per un text que explica els botons nous.
#### CONTRACT REQUEST (`ContractRequestTermination.vue`, `ReadingDetail.vue`, `locales/*` — pas 6 «Situació actual» en cards i lectura inicial)
    - El pas 6 es mostra amb tres cards verticals una al costat de l'altra (**Comptador**, **Lectura inicial** i **Contracte actiu**) amb la informació resumida i un botó «+ informació» que obre el detall en una regió lateral. El formulari de la lectura de tall i les ordres queda a sota de les cards.
    - S'ha retallat l'espai de dalt de les regions laterals del component.
    - Es pot **marcar com a inicial una lectura ja entrada al comptador**: botó per a la darrera lectura i «Triar una altra lectura del comptador», que obre un llistat on les lectures es poden seleccionar (només en aquest cas). Es crea una còpia com a lectura inicial de la sol·licitud; l'original no es toca.
    - Només es pot triar la **darrera lectura facturada o una de posterior** (les anteriors surten atenuades). Si es tria una lectura facturada, se'n duplica el valor i l'original es queda al contracte anterior. Fa servir el camp nou `is_billed` del backend.
    - La lectura inicial desada es pot **modificar** (camp amb Desar/Cancel·lar) o substituir triant-ne una altra.
    - La confirmació és una caixa flotant al mig de la pantalla (no un `confirm()` del navegador) amb la lectura triada i, si n'hi ha, la llista de **lectures posteriors pendents de facturar que passaran al contracte nou** en finalitzar l'alta. En passar el ratolí per sobre d'una lectura del llistat es ressalten les que es mourien.
    - Va amb el canvi del backend que mou aquestes lectures a `contract_create()`.
#### CONTRACT REQUEST (`ContractRequestEdit.vue`, `ContractRequestTermination.vue`, `locales/*` — «Mantenir número de contracte» sempre clicable)
    - En un canvi de nom, «Mantenir número de contracte» ja no està deshabilitat quan falta la baixa: en clicar-lo surt una caixa flotant que indica que cal donar de baixa el contracte vigent, amb un botó per fer-ho allà mateix. Si es fa la baixa, queda seleccionat «Mantenir»; si es cancel·la, es torna a «Crear número de contracte nou».
    - Si encara no es pot fer la baixa (no s'ha triat comptador) el botó surt desactivat amb l'explicació. Amb més d'una baixa vinculada, només es mostra l'avís de sempre.
    - `ContractRequestTermination` exposa `terminate({ skipConfirm })`, `canTerminate` i `activeContract`; `terminate()` ara gestiona els errors amb un toast.
#### CONTRACT (`ContractClausesEdit.vue`, `ContractTabs.vue`, `ContractActionsDropdown.vue`, `ContractRegion.vue`, `ContractPinned.vue`, `locales/*` — modificar les clàusules d'un contracte actiu)
    - Fins ara les clàusules només es podien afegir o treure a la sol·licitud de contracte: un cop el contracte era actiu, la pestanya **Clàusules** era només de lectura.
    - Botó «Modificar Clàusules» a la pestanya **Clàusules** (només amb permís de modificar el contracte) i opció nova al desplegable d'accions de dalt a la dreta, sota «Generar contracte». Tots dos obren el mateix panell lateral, tant a la fitxa del contracte com al contracte fixat.
    - El panell mostra les clàusules actuals del contracte, amb botó per treure-les, i les plantilles de clàusules actives per afegir-ne. Les plantilles que el contracte ja té no es tornen a oferir.
    - Una clàusula afegida es crea vinculada al contracte (`contract`). En treure una clàusula que venia de la sol·licitud no s'esborra: només es desvincula del contracte, i la sol·licitud original la conserva. Si es va afegir directament al contracte, s'esborra.
    - «Generar contracte» ja inclou les clàusules del contracte al PDF (`instance.clauses` al backend), així que els canvis surten al document quan es torna a generar. No cal cap canvi al backend.
    - Noves claus `confirm_remove_clause` i `contract_clauses_regenerate_notice` als quatre idiomes.
    - Va amb el canvi de la plantilla `contract_template_personalized.html` de la instal·lació L (`customers-clients-data`): amb més d'una clàusula, el text del contracte passava per sota del footer.

## [06-10-2026]

### CHORE
#### INVOICE
    - Permet afegir price unit negatiu

### FIX
#### BILLING (`InvoiceEdit.vue`, `BillingSummary.vue`, `locales/*` — warning when excluding a pre-invoice from the batch)
    - When excluding a pre-invoice (one or more), a warning appears stating that it will be deleted, the readings will be moved to the "excluded" batch, and they will not be billed with the current batch. Upon acceptance, the list refreshes.
    - This accompanies the backend change that deletes the pre-invoice and moves the readings.
    - **Not tested in a browser**.
#### READING (`ReadingBatchSummary.vue`, `locales/*` — resum del lot de lectures: textos tallats i totals que no quadraven)
    - "Comptadors amb:" a la fila de telelectures: el commit `a700be0b` va deixar `remote_readings` tallat en català. Ara és "Telelectures", com a la resta d'idiomes.
    - El "Total" de la fila de lectures assignades estava escrit al component: nova clau `total_assigned_readings` als quatre idiomes.
    - "Avisos" i "Correctes" agafen `total_warnings` i `total_correct` del backend, que es calculen igual que els llistats `alert=any` i `alert=null`. Si no hi són, es calcula com abans.
    - L'avís de rang de dates (`warning_date_range`) continua sortint com a fila però ja no se suma al total d'avisos, perquè aquestes lectures poden tenir també una altra alerta.
    - Va amb el canvi del backend que fa que els comptadors i els llistats del resum surtin de la mateixa consulta.
    - **No s'ha provat en un navegador**.

#### BILLING (`SEPAReturnSetup.vue`, `SEPAReturnManagementEdit.vue`, `payment-api.js` — retorns SEPA sense data de retorn)
    - En carregar el fitxer s'enviaven els pagaments amb `rjt_dt`, `skip_return`, motiu i `og_msg_id` (`mapRejections`, des de `a5dbe640`), però els quatre gestors de selecció (seleccionar tots per a retorn/reclamació i els interruptors de cada pagament) els reemplaçaven per una llista amb només `id` i `motive_id`, sense `og_msg_id`. Com que per desar cal marcar algun pagament, al backend no li arribava mai cap data de retorn: petava (500) i, abans, cada pagament agafava una data de rebuig equivocada (data de pagament o avui).
    - Nou `emitSelectionChanged()` que fa servir `mapRejections` i envia `og_msg_id`; manté el filtre de treure els pagaments `skip_return`.
    - `manageRejectionPayments` envia `return_date` (no s'havia enviat mai) i `SEPAReturnManagementEdit` hi posa la primera `rjt_dt` informada dels pagaments.
    - **No s'ha provat en un navegador**.

### FEAT
#### READING (`pages/reading/lecturapp.vue`, `LecturappHelpLink.vue`, `public/images/lecturapp/`, `locales/*` — pantalla d'ajuda per configurar la Lecturapp)
    - Pàgina nova `/reading/lecturapp` amb la **URL que cal posar a la configuració inicial de la Lecturapp** ben destacada i botó de copiar. És dinàmica per client: és l'`apiHost` de la instal·lació (la Lecturapp hi afegeix `/lecturapp/...`), així que cada client veu la seva.
    - En obrir la pàgina es comprova que l'endpoint `lecturapp/auth/validate-token/` respon (i es pot tornar a comprovar), per saber si la URL és bona.
    - Manual pas a pas: configurar l'app al mòbil, crear l'usuari Lecturapp de l'operari, crear el lot amb origen «Carregar per Lecturapp», prendre lectures amb l'app (assignar-se el lot, finca, lectura, incidències, sincronització automàtica) i problemes habituals. Inclou 8 captures de l'app que s'amplien en fer-hi clic.
    - Enllaç d'ajuda a la llista d'**Operaris**, a l'apartat «Usuari Lecturapp» de la fitxa de l'operari, a **Introduir lectures** i al costat de l'opció «Carregar per Lecturapp» de **Nou lot de lectures** (s'obre en una pestanya nova).
    - Primera versió: falten captures de la part web (usuari Lecturapp, creació del lot) i d'alguns passos de l'app.
    - **No s'ha provat en un navegador**.

#### BILLING (`CommitmentDepositPayments.vue`, `CommitmentDepositEdit.vue`, `CommitmentDepositFinalSummary.vue`, `PaymentCommitmentList.vue` — data d'inici del compromís de pagament i interval de cada termini)
    - Al pas 3 del compromís de pagament hi ha un camp nou **Data inici** del compromís (per defecte, avui). Els venciments es calculen a partir d'aquesta data: el termini *n* venç a data d'inici + *n* × periodicitat. Abans es calculaven sempre des d'avui.
    - Cada termini mostra el seu interval (`inici → venciment`): el primer comença a la data d'inici i la resta el dia després del venciment de l'anterior. És només informatiu: un termini es pot cobrar abans del seu inici.
    - Canviar la data d'inici o la periodicitat recalcula les dates sense tocar els imports (abans, canviar la periodicitat regenerava els terminis i es perdien els imports editats). El venciment de cada termini continua sent editable i, si es canvia, l'interval del següent s'ajusta. El venciment del compromís passa a ser el de l'últim termini.
    - La data d'inici s'envia al pas 4 (`start_date_commitment`) i cada termini envia el seu `start_date`. El resum final mostra l'interval de cada termini i `PaymentCommitmentList` (terminis guia) té la columna **Data inici**, també a l'exportació XLSX.
    - Requereix la migració `billing/0321_commitment_start_date` del backend.
    - **No s'ha provat en un navegador**.

## [05-10-2026]

### FIX
#### PERSON (`InputIban.vue`, `AddBank.vue`, `AddCompanyBanks.vue`, `PersonBankSelect.vue`, `BankDetail.vue` — banc fora de catàleg, canvi només del SWIFT i un sol camp SWIFT/BIC)
    - Si l'IBAN és correcte però el banc no és al catàleg, el camp ja no ho marca com a error: surt un avís («no és al catàleg, es pot desar igualment»), amb el nom de l'entitat segons el registre oficial quan es coneix.
    - El SWIFT automàtic (registre oficial o catàleg) ja no trepitja el que hi ha desat o el que ha escrit l'usuari: només es recalcula quan l'IBAN canvia de debò, no a cada focus/blur del camp. Abans, en obrir l'edició d'un compte el SWIFT desat es substituïa per la detecció (o es buidava si no se'n detectava cap). Del catàleg només s'agafen BIC complets (8/11 caràcters), no el codi de 4 lletres.
    - Des d'un contracte/factura/compromís, modificar només el SWIFT amb el mateix IBAN ara es desa al compte (el backend respon `swift_updated` i surt un avís que el canvi val per a tots els contractes del compte). Abans es deia que no s'havia aplicat res.
    - Un sol camp **SWIFT/BIC** editable, amb l'etiqueta «deduït de l'IBAN» quan el valor és automàtic. Abans el mateix valor sortia tres cops (caixeta «BIC (info)» sota l'IBAN, quadre «BIC» de només lectura i camp «SWIFT»), i el quadre desapareixia en escriure, de manera que la pantalla saltava. No hi ha cap camp BIC separat a les dades: tot és `swift`.
    - `BankDetail.vue` (targeta del compte a contractes, factures, compromisos…) mostra el nom del banc i el SWIFT sempre que n'hi hagi; abans el SWIFT només sortia si el compte no tenia IBAN i el banc estava comentat.
    - `AddBank.save()` llegia `country.iso_code` sense `.value`: no avisava mai de banc no seleccionat i sempre enviava `bank: ''`. Corregit; ara envia l'entitat seleccionada (o `null`).
    - **No s'ha provat en un navegador**.
#### CONTRACT REQUEST
    - S'ha arreglat a la configuració del tipus de contractació els títols per evitar ser confús

#### PERSON (`InputIban.vue` — «Banc no trobat» amb un IBAN correcte)
    - En entrar un IBAN espanyol, el camp buscava el banc comparant el codi d'entitat SENSE zeros («81») amb el token del catàleg tal com és. Des que `prometeo/data/coredata.Banks.json` porta 71 codis amb zeros a l'esquerra («0081» Sabadell, «0049» Santander, «0075», «0128» Bankinter…), aquests bancs no es trobaven mai i el formulari no deixava desar. Ara es comparen tots dos sense zeros, igual que el backend (`get_spanish_bank_code_candidates`).
    - **No s'ha provat en un navegador**.
#### SETTINGS (`pages/settings/index.vue` — llista de configuracions desquadrada i seccions duplicades)
    - Les seccions **Adreces** i **Contractació** sortien sagnades i enmig de la llista de *Servei*, i tornaven a sortir ben col·locades més avall. El `<ul>` de Servei (línia 141) tenia a dins un `<h3>` + `<ul>` de cada secció: un `<ul>` només admet `<li>`, així que el navegador els deixava com a fills directes de la llista i hi sumava la sagnia del pare. Ve del merge `08280280` (02-10-2026), que en resoldre el conflicte va conservar les dues versions del bloc: la de la branca sense reformatar, encastada dins del `<ul>` obert, i la correcta. S'esborren les 32 línies duplicades.
    - L'enllaç «Clàusules: Plantilles de clàusules» només existia al bloc duplicat; es mou a la llista de *Contractació* bona perquè no es perdi.
    - La secció **Documents** sortia dues vegades seguides, idèntica byte a byte, des del reformat de `d8abd0af` (18-09-2026). S'esborra la còpia.
    - Verificat que els 14 `<ul>` queden balancejats, que no hi ha cap `<h2>`/`<h3>` dins de cap llista, que les 12 seccions són úniques i que no es perd ni s'afegeix cap enllaç respecte d'abans.

#### CONTRACT (`VariableDetail.vue`, `ContractTabs.vue`, `bonifications.vue`, `ContractRequestPriceRate.vue` — el llapis de les variables no editava)
    - A la pestanya **Variables** de la fitxa del contracte sortia un llapis d'edició que no feia res: `VariableDetail` l'emetia (`@edit`) però ningú l'escoltava, i només es podia editar entrant a «Modificar variables». Ara el llapis porta a la mateixa pantalla de bonificacions/variables amb el formulari d'aquella variable ja obert (`?variable=<id>`, que `bonifications.vue` consumeix i neteja de la URL).
    - El llapis de `VariableDetail` passa a ser **opt-in** (`editButton` per defecte `false`): abans sortia per defecte a tot arreu i quedava mort a les pantalles que no tenen formulari d'edició (fitxa ACA, variables caducades). L'activen explícitament les pantalles que sí editen. També s'alinea bé quan no hi ha botó d'esborrar, i `edit` queda declarat a `defineEmits`.
    - A la sol·licitud de contracte (`ContractRequestPriceRate.vue`) el llapis ja obre el formulari lateral amb la variable carregada.
    - **No s'ha provat en un navegador**.
#### CONTRACT (`AddVariable.vue` — editar una variable la trencava)
    - El desat d'una variable existent és un `PUT` i només enviava un grapat de camps: la variable perdia el vincle amb la bonificació d'on penjava i el `token`. A més, `type: variable.type.id` era `undefined` en edició (l'API retorna `type` com a id, no com a objecte), així que el tipus també s'esborrava. Ara el formulari arrossega la variable original i resol el tipus des del selector.
    - En obrir el formulari per editar, el `watch` del selector de tipus podia buidar el valor que s'estava editant, i `onMounted` + el `watch` de `props.variable` disparaven dues càrregues concurrents que es trepitjaven. Es deixa una sola càrrega i el `watch` no toca el valor quan el tipus no l'ha canviat l'usuari.
    - `AddVariable` carregava el tipus abans que la variable, de manera que `VariableEdit` es podia pintar amb `item = null` i petava (`Cannot read properties of null (reading 'value')`, i després `instance.update is not a function`). S'inverteix l'ordre, el formulari només es pinta quan hi ha tipus **i** variable, i `VariableEdit` accepta un `item` buit sense petar.
    - **No s'ha provat en un navegador**.

### FEAT
#### SETTINGS (`pages/settings/index.vue` — editar els valors de «Configuracions internes»)
    - El desplegable **Configuracions internes** de la pàgina de configuració només llistava els `ConfigProject` (token + valor) en mode lectura: per canviar-ne cap calia anar a l'admin de Django o a la BBDD. Ara cada línia té un llapis (visible només amb permís `change_user`) que converteix el valor en un camp editable amb Guardar/Cancel·lar (també amb `Enter`/`Esc`).
    - El desat fa servir l'endpoint existent `config-project/bulk-update-values/`, que a més refresca la còpia del valor a `localStorage` (`config_<token>`), de manera que la resta de l'aplicació no es queda amb el valor antic.
    - Això permet, per exemple, modificar `incasol_num` («Núm concert INCASOL»), que ara fa de valor per defecte quan una explotació no té número propi.
    - **No s'ha provat en un navegador**.

#### SERVICE (`ExploitationEdit.vue`, `ExploitationDetail.vue`, `exploitation-api.js`, `locales/*` — núm. de concert INCASOL per explotació)
    - El formulari d'edició de l'explotació incorpora **Núm. concert INCASOL** (camp nou `incasol_num` del model `Exploitation` al back), amb l'ajuda que indica que va sense el prefix «S» i que, si es deixa buit, s'agafa el valor general de configuracions internes. La fitxa de detall de l'explotació també el mostra.
    - El camp es precarrega amb el valor general de `ConfigProject` (`incasol_num`) quan l'explotació encara no en té de propi, de manera que el formulari mostra sempre el número que faran servir realment els informes. En desar, el valor s'escriu als **dos** llocs: a l'explotació i a la configuració general. Si el projecte no té la fila `incasol_num` a `ConfigProject` no s'intenta sincronitzar (l'endpoint de desat només actualitza files existents, no en crea), i si la sincronització falla es desa igualment l'explotació i només s'avisa.
    - `updateExploitation` descartava qualsevol valor buit del `FormData`, de manera que un camp opcional mai es podia esborrar un cop desat; ara hi ha una llista explícita de camps que sí que s'envien buits (`CLEARABLE_FIELDS`), de moment només `incasol_num`, perquè es pugui tornar a delegar al valor general.
    - **No s'ha provat en un navegador**.

## [02-10-2026]

### FEAT
#### ACCOUNTING
    - La pàgina de settings s'ha reorganitzar i millorat amb `AccountingPricingsBox` i `AccountingReferenceCard`.
    - Nova region i valors per centres de cost, assignables a conceptes tarifaris.
    - El formulari d'edició de tarifes comptables amplia el model:
        - Factures noves categories: Normal / Dotació morositat / Irrecuperable amb opció de desdeclarar anterior.
        - Cobraments: filtres per IBAN nacional o estranger i de moviment si és client or són devolucions d'empresa.
        - Opció de declarar valors agrupats o per fila de manera individual.

#### ORDER (`OrderRegion.vue`, `ChangeMeterStatus.vue`, `ChangeMeterPreview.vue`, `OrderReportList.vue`, `OrderReportEdit.vue`, `order-api.js`, `locales/*` — flux de canvi de comptador des de l'ordre de treball)
    - Per a ordres de tipus `change_meter`/`install_meter`, un requadre sobre les pestanyes (`ChangeMeterStatus.vue`) valida si l'informe té totes les dades necessàries i mostra quins camps falten, o un botó «Previsualitzar» quan ja és possible aplicar el canvi.
    - Nova pantalla de previsualització (`ChangeMeterPreview.vue`, oberta com a subregió): mostra el comptador sortint (codi i lectura de l'informe vs. codi registrat al sistema, amb avís si no coincideixen) i el comptador entrant (si ja existeix al sistema o no). Si el comptador entrant no existeix, un botó obre el formulari de creació de comptador (`MeterEdit.vue`) amb el codi precarregat i editable; en guardar-lo, la previsualització es refresca sola.
    - Quan tot quadra, un botó «Fer el canvi» a la previsualització aplica el canvi (crida `apply-change-meter`); el requadre d'estat passa a mostrar «Canvi realitzat al programa d'abonats» de forma permanent per a aquesta ordre.
    - A «Dades del formulari» de l'informe, cada camp mostra una icona d'ajuda amb el seu token intern (el mateix que es parametritza al `ConfigProject` del back), per facilitar-ne el manteniment.
    - Un cop aplicat el canvi, l'informe mostra un bloc nou amb qui i quan s'ha aplicat.
    - Nous mètodes a `order-api.js`: `validateChangeMeter`, `previewChangeMeter`, `applyChangeMeter`.

### FIX
#### SERVICE (`MeterEdit.vue` — adreça no es precarregava i es podia desar un comptador sense adreça)
    - `isValid()` havia deixat de comprovar l'adreça (condició comentada); es podia desar un comptador sense cap adreça assignada i petava al back amb `UnboundLocalError`. Es torna a exigir.
    - En crear un comptador des del flux de canvi de comptador, la cerca del codi postal podia llençar una excepció silenciosa (`.find()` sense coincidència) que avortava tota la precàrrega de l'adreça; ara es protegeix i es registra l'error si n'hi ha.
    - El panell lateral («Nou comptador») no ocupava tota l'alçada quan `MeterEdit` s'obria com a subregió niada (quedava tallat); ara hereta correctament l'alçada del contenidor.
#### SERVICE (`AddPartialAddress.vue` — Municipi i Codi postal més estrets que l'opció seleccionada)
    - El `v-select` de Municipi/Codi postal podia quedar més estret que el text de l'opció triada. Ara l'amplada mínima es calcula a partir de l'opció més llarga de cada llista.
#### ORDER (`OrderRegion.vue`, `OrderReportList.vue` — alineació de panells niats i espaiat del botó XLSX)
    - Diversos panells de subregió (`#subregion`, `#double-subregion`, fletxa de tancament) feien servir `%` en lloc de `vw`, o els hi faltava el `py-2` que sí tenia la pàgina d'ordres, i quedaven descol·locats respecte als altres nivells de subregió un cop niats dos o tres cops.
    - El botó «Descarregar XLSX» d'Informes quedava enganxat a la línia de les pestanyes per falta de marge superior.

## [01-10-2026]

### FEAT
#### BILLING (`MissingContractsDetail.vue` — titular a "Possibles contractes no facturats")
    - Al costat del token de cada contracte es mostra el nom del titular (`contract_holder_name`, que el backend ja retornava a `check-missing`). Si és llarg es retalla i el nom complet surt al passar-hi el ratolí.
    - **No s'ha provat en un navegador**.
#### BILLING (`InvoiceEdit.vue`, `BillingSummary.vue`, `BillingDocumentsSummary.vue` — columna de consum a la llista de pre-factures)
    - Nova columna **Consum** (`invoice.consumption`, en m3) entre "Total a pagar" i el nombre de dies, a la llista de pre-factures d'una facturació i també a la de factures d'una facturació finalitzada (comparteixen la fila `InvoiceEdit`).
    - La columna es pot ordenar (`ordering=consumption`); cal el backend amb `consumption` a `ordering_fields`.
    - Capçalera i files alineades: les columnes passen a `minmax(0,…fr)` (abans `1fr` creixia segons el contingut i cada fila quedava diferent de la capçalera) i la capçalera reserva l'espai de la barra de desplaçament (`scrollbar-gutter: stable`). Els textos massa llargs es retallen i es veuen sencers al passar-hi el ratolí.
    - **No s'ha provat en un navegador**.

#### INCIDENT (`incident-api.js` — sense filtre d'explotació)
    - El llistat d'incidències i la seva exportació ja no envien `exploitation`: es mostren les incidències de totes les explotacions, sigui quina sigui l'explotació seleccionada. També afecta les incidències dins de contracte, factura, fiança i ordre (ja filtrades per la seva entitat).
    - El filtre `exploitation` continua existint al backend (`notification/filters/incident_filter.py`), però el frontend ja no el fa servir.

### FIX
#### CORE (`ProcessColorBadge.vue` — el seguiment de tasques llargues ja no es talla als 3 minuts)
    - Abans, qualsevol tasca no acabada (PENDING, STARTED o PROGRESS) comptava cap a un límit de 90 consultes (3 min) i després es mostrava error i es deixava de consultar, encara que la tasca seguís avançant (p. ex. el Padró de facturació d'una facturació gran).
    - Ara el límit de 3 min només s'aplica a tasques que no arrenquen (PENDING). Una tasca en marxa només es dona per encallada si el percentatge no puja durant 10 min (300 consultes); cada avanç reinicia el compte.
    - Afecta tots els usos del badge amb `taskId` (informes, exportacions). No canvia el seguiment per `billingId` (cua de facturació), que no tenia límit.
    - **No s'ha provat en un navegador**.
