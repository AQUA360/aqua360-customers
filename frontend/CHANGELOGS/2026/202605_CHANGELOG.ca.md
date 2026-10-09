# Changelog Frontend

## [29-05-2026]

### FEAT
#### COMMUNICATION

    - S'han afegit logs de canvis de comunicació
    - S'ha afegit un nou filtre de procés que permet fer una cerca per comunicacions ja creades que directament et mostra les comunicacions i crea el procés sense haver de passar per tots els passos
    - S?ha afegit l'opció d'afegir el tipus d'ús del procés de comunicació

### FIX
#### BILLING / INVOICES

    - AddInvoiceBudget.vue: Corregit el problema de visualització de pressupostos o factures generats per a sol·licituds d'escomesa (`connection_request`) i sol·licituds de contracte (`contract_request`). S'ha prioritzat l'ús dels serveis específics `$InvoiceApiService.getConnectionRequestInvoice` i `$InvoiceApiService.getContractInvoice` per carregar les factures, en comptes de dependre del camp `invoices` del detall de l'entitat, el qual no ve poblat des del backend per a aquests recursos. També s'han normalitzat les propietats `type_token` i `status_token` per garantir la consistència interna en cas que l'API utilitzi noms alternatius com `type_final` o `status_token`.

### CHORE
#### OTHER

    - S'ha afegit un atom component pels selectors al crear un procés de comunicació 'OptionSelectorGroup.vue'
    - Ara a configuració es pot consultar els codis de raons de retorn de pagaments sepa

### MODIFIED
#### COMMUNICATION

    - S'ha afegit l'opció d'afegir factures a les comunicacions fetes per un procés de comunicació sense necessitat de lligar una facturació directament
    - Ara es mostren les relacions d'una comunicació: Contractes, Factures i Lectures

#### OTHER

    - Ara es permet a DocumentList.vue descarregar tots els fitxers disponibles i poder filtrar per extensió (si només es vol descarregar els XML per exemple)

#### CONTRACTS / REFACTORING

    - Ara es mostren les comunicacions relacionades a contracte
    - Extracció de components compartits per evitar la dessincronització de codi entre les diferents vistes de contracte (`ContractPinned.vue`, `ContractRegion.vue`, `PinnedContractBasicInfo.vue` i `ContractDetail.vue`):
      - ContractActionsDropdown.vue: Nou component compartit per unificar les accions del menú desplegable de contractes.
      - ContractStatusBadges.vue: Nou component compartit per unificar el bloc de botons de capçalera amb informació de saldo, deute, deute compromès i persones.
      - ContractTabs.vue: Nou component compartit per unificar tota l'estructura de pestanyes inferiors (observacions, lectures, incidències, fiances, etc.) i els seus respectius panells de detall.
      - S'ha actualitzat ContractPinned.vue, ContractRegion.vue, ContractDetail.vue i PinnedContractBasicInfo.vue per utilitzar aquests nous components compartits.

#### SETTINGS

    - index.vue (pages/settings): Restablerta la visualització neta del títol de la pàgina a la capçalera.

## [28-05-2026]

### FIX
#### CONTRACT
    - ContractRequestEdit.vue i ContractRequestRegion.vue: Corregida la funció `mapErrorToStep` per a que els errors de titularitat del compte bancari es dirigeixin correctament al Pas 3 (Pagament) en lloc del Pas 2 (Persones). S'han afegit també les paraules clau en castellà per a la interpretació i mapeig dels missatges d'error en aquest idioma.

### CHORE
#### OTHER
    - S'ha afegit al index de configuració la taula de raons de devolució del SEPA

### MODIFIED
#### READINGS / CONTRACTS
    - S'ha implementat la identificació visual dels contractes i punts de subministrament de contra incendis mitjançant la icona de boca d'incendis/estintor (`fa6-solid:fire-extinguisher` en color vermell) a diverses vistes i visualitzacions del front-end.
    - ReadingEdit.vue: Afegida la icona al costat del contracte i bloquejat el control d'edició manual de lectures estimades per a incendis de manera que no es puguin modificar de 0.
    - ReadingListDetail.vue i ReadingDetail.vue: Mostrada la icona al costat dels valors de lectura quan el camp `is_fire` de la lectura és cert.
    - ReadingBatchReadingsSummary.vue i MissingReadingEdit.vue: Mostrada la icona de contra incendis al costat del token del contracte en els llistats de lectures pendents o descartades del lot de lectures.
    - ContractDetail.vue i InvoiceDetail.vue: S'ha estès la visualització per mostrar la icona de contra incendis al costat dels tokens de contracte (incloses les llistes de contractes generals) identificant-los a través del configurat `fire_usage_type_token` o del camp `is_fire`.

#### CUSTOMERS / BANK ACCOUNTS
    - PersonBankSelect.vue i AddBank.vue: Habilitada la capacitat d'editar comptes bancaris ja existents en lloc de només permetre la seva eliminació/desactivació. S'ha integrat un botó d'edició amb icona de llapis a la llista de bancs que obre el panell lateral amb les dades pre-emplenades. S'ha utilitzat clonació profunda (`_.cloneDeep`) per evitar la mutació de props de Vue, s'ha afegit una clau dinàmica per forçar la reinstanciació del formulari al canviar de banc, i s'ha actualitzat la sincronització en desar el banc per actualitzar-lo en la llista local de la persona.

#### BILLING / INVOICES
    - billing-api.js: Afegit el mètode `cancel` al servei `BillingApiService` per realitzar la petició PUT a `/api/billing/billing/<billing_id>/cancel/`.
    - BillingRegion.vue: Afegida l'opció "Cancel·lar lot de facturació" al menú desplegable d'accions (`OptionsDropdown`) per a lots no cancel·lats (estat amb token diferent de "-1").
    - pages/billing/billing/index.vue: Integrat el refresc automàtic de dades a través de `@changed="getData"` en rebre la notificació de canvis del panell lateral de facturació.
    - BillingEdit.vue: Integrat el botó "Cancel·lar facturació" a la barra de navegació inferior de la configuració de facturació pas a pas per facilitar la cancel·lació i redirecció cap a la llista de facturació.

## [27-05-2026]

### FIX
#### CONTRACT
    - ContractRegion.vue: Es corregeix el bucle del template de canvis de llogater (tenant_changes) i de subrogacions (surrogations) per fer servir les variables reactives en lloc de les dades del contracte original no reactives/no invertides.
    - ContractRegion.vue: Inicialitzat el comptador de modificacions de contracte (`contractChangeNumber`) a la càrrega inicial a partir de la longitud de `data_changes` per evitar que es mostri com a `0` abans de fer clic a la pestanya de modificacions.

#### PROPERTY
    - AddProperties.vue: Fer que el focus del buscador només es faci en cas que no s'hagi seleccionat el filtre del carrer, sinó cada cop que buscavem pel cercador d'adreça (get_data), feia focus al cercador general.

### CHORE
#### BILLING
    - S'han eliminat els components anteriors de gestió de factura electrònica

#### COMMUNICATION
    - S'ha eliminat la region de IndividualCommunicationEdit

#### OTHER
    - S'ha agafat el codi repetit del nou 'StatusNav' i s'ha afegit a un nou component atoms/WizardStatusNav.vue
    - S'ha afegit a 'DocumentList.vue' l'opció de descarregar arxius en massa per extensió

### MODIFIED
#### COMMUNICATION
    - Nou component i pàgina per crear una comunicació. Millor separat i organitzat. Al crear-la s'ha esborrat 'IndividualCommunicationEdit.vue'
    - Al mostrar els missatges de les communicacions, ja no es fa amb v-html amb el valor html directe de la comunicació, sino que per back es genera un png en base64

#### GOT
    - summary/index.vue: Estandarditzat el disseny de la targeta en vista mòbil per coincidir exactament amb orders/index.vue, agrupant operaris i data de venciment a la mateixa línia, alineant horitzontalment els desplegables de filtre, reubicant els botons d'acció a sota de la capçalera, i integrant el botó "Anar a les meves ordres".
    - orders/index.vue: Substituït el filtre d'operari pel filtre d'explotació i agrupat els camps d'operaris i data a la mateixa línia flexible de la targeta.
    - got.vue (layouts): Reestructurat el disseny del top bar mòbil amb logo/títol centrat, botó de tirar enrere "<" a l'esquerra (dinàmic segons l'origen), i menú hamburguesa a la dreta que agrupa ordres, resum, perfil d'operari actiu i tancament de sessió.
    - OrderHeader.vue i profile.vue: Eliminats els botons de tirar enrere locals, unificant la navegació enrere des del header global.
    - OrderSupplyPoint.vue: Redissenyat l'indicador de telecontrol per mostrar una placa destacada amb "Telelectura" (icona d'antena) o "Lectura manual" (icona de mà) directament, traient l'etiqueta descriptiva superior en majúscules.

#### LOCALES
    - ca.ts i es.ts: Afegits els literals de traducció per a `telereading` ("Telelectura") i `manual_reading` ("Lectura manual") sota l'espai de noms `GOT`.

## [26-05-2026]

### FEAT
#### COMMUNICATION
    - CommunicationRegion.vue: Afegida l'opció de cancel·lar una comunicació si encara no ha estat enviada (estat pendent, token "0").
    - CommunicationProcessRegion.vue: Afegida l'opció de cancel·lar un procés de comunicació si està en estat pendent (token "0") o en estat de comunicacions creades (token "1").

### FIX
#### SERVICE / ROUTES
    - RouteEdit.vue i AddRoutePosition.vue: Solucionat el problema de visualització del botó per plegar la subregió quan s'obre la selecció de punts de subministrament (AddSupplyPoints.vue) o finques. S'ha separat l'scroll del panell lateral dret en dues columnes independents (h-full overflow-y-auto), alineant l'estètica amb la de PropertyRegion.vue per evitar que la capçalera de la subregió quedi retallada pel contenidor d'scroll superior de la pàgina principal de rutes.

#### READINGS
    - ContractReadingChange.vue: Netejat el camp `previous_reading_option_key` abans d'enviar les modificacions a l'API perquè contingui exclusivament la cadena de la data (format `YYYY-MM-DD`), evitant errors de parseig al backend.
    - ReadingsChange.vue: Adaptat el mètode `formatDate` al detall de la lectura anterior per extreure la data correctament de claus concatenades amb canonades (`|`) i evitar errors de data invàlida.
    - ReadingsChange.vue: Es corregeix un error on s'enllaçaven com a lectures anteriors (`previous_reading`) les lectures originals que s'estaven passant a control. S'ha modificat `findClosestPreviousReading` i `findClosestNextReading` per utilitzar l'estat actualitzat (amb `is_control: true` o noves dates) mapejant amb les dades modificades locals.

### CHORE
#### CONTRACT
    - ContractDataLog.vue: Nou component que obté i mostra l'historial de modificacions d'un contracte des del servei de logs del back-end.
    - ContractRequestAddressPayment.vue: Afegida funcionalitat de guardar un Mandate_id per contracte.

### MODIFIED
#### COMMUNICATION
    - S'ha implementat la propagació de l'esdeveniment `@changed` per refrescar dinàmicament els llistats i estats quan es cancel·la una comunicació o procés (afegit a les pàgines de llistats, així com a ContractRegion, PersonRegion i dins del propi procés).

#### DOCKERFILE
    - Per seguretat s'ha passat el Dockefile de npm a pnpm.

#### CONTRACT
    - ContractRegion.vue: S'ha substituït l'anterior llistat local de canvis de dades pel nou component de log unificat de modificacions `ContractDataLog` i s'ha integrat el seu comptador de forma reactiva a la pestanya.
    - ContractTerminationEdit.vue: Redissenyat el llistat d'accions de punts de subministrament per mostrar la darrera lectura realitzada amb el seu valor, data i indicació dels dies transcorreguts (avui, ahir o fa X dies) dins d'un requadre destacat amb estil d'alerta. S'ha integrat el botó de visualització d'historial dins d'aquest requadre.
    - ContractRequestTermination.vue: Aplicat el mateix disseny de requadre destacat per a la darrera lectura d'accions de baixa de contracte, integrant-hi la càrrega dinàmica de la darrera lectura i eliminant el botó duplicat de consulta d'historial de lectures.

#### BILLING / INVOICES
    - InvoiceDataLog.vue: S'ha integrat la visualització del canvi de compte bancari (`previous_iban` -> `current_iban`) utilitzant el component `<AtomsIBAN>` amb botó de visibilitat (ull).

#### LOCALES
    - ca.ts i es.ts: Afegides les traduccions de `today` i `yesterday` a la secció `common` (`common.today` i `common.yesterday`).

## [21-05-2026]

### MODIFIED
#### CONTRACT
    - Permet sempre guardar lectura manual. Encara que sigui telelectura (al menys de moment)

#### BILLING / REPORTS
    - add.vue (pages/billing/reports): Permet generar informes quan només es selecciona una remesa (sense necessitat de seleccionar dates o facturació). S'ha modificat el bloqueig de validació (`isValid`) i s'ha afegit la sincronització de `billing_id` i `remittance_id` en el formulari global en el mètode `handleReportDownload`.
    - add.vue / Formularis: S'ha separat la descàrrega i estat de càrrega dels informes de comptabilitat controlant l'estat `downloading` a través del seu identificador únic (`report.id`) en lloc del nom del mètode compartit, evitant descàrregues simultànies accidentals. S'ha actualitzat el tipus del prop `downloading` dels components `RatesReportForm.vue`, `AcaReportForm.vue` i `GenericReportForm.vue` per admetre valors numèrics i cadenes, i s'ha ajustat la propietat computada `isCurrentDownloading` per verificar per ID.

#### ORDERS
    - index.vue (pages/order/orders): Reestructurat el flux d'inicialització (`onMounted`) perquè carregui primer les ordres sense filtres per poblar el desplegable de municipis complet. S'ha introduït `accumulatedCities` (un `Map` persistent) per acumular els municipis obtinguts en les diferents consultes. Un cop carregat el desplegable, s'apliquen els filtres desats a `sessionStorage` (si n'hi ha d'actius), garantint que es mostrin la resta de municipis i no només el seleccionat.

## [20-05-2026]

### MODIFIED
#### READINGS
    - S'han augmeentat els dies de tolerància per poder introduir les lectures dins el mateix període

#### CONTRACT
    - ContractRequestEdit.vue: S'ha habilitat la modificació directa de dades d'altres passos (Setup, Persones, Direcció/Pagament, Tarifes i Ordres) des de la llista de punts pendents de validació. Les dades s'editen en un panell lateral adaptat (amb ampliació dinàmica del visualitzador a `w-2/3`) per no perdre el pas actual de l'usuari, i la llista de punts a validar es recalcula automàticament en desar i tancar el panell.

#### BILLING
    - index.vue (pages/reading/reading-batches): S'ha dividit la columna de lectures del llistat de lots de lectura en tres columnes amb noves mètriques (contractes llegits/totals, lectures totals i punts de subministrament totals). S'han ajustat les amplades de la graella de la taula, s'ha aplicat el truncatge de text (`truncate`) amb `title` per evitar desquadraments i s'ha configurat les capçaleres perquè puguin ocupar dues línies.

#### LOCALES
    - locales (ca.ts, es.ts): S'han afegit les noves claus de traducció per a les capçaleres de les mètriques dels lots de lectura.

## [19-05-2026]

### CHORE
#### STATISTICS/REPORT
    - S'han esborrat les pàgines de informes de billing i order que anaven per separat del base

#### BILLING
    - CommitmentDeposit s'ha afegit un filtre d'estat i només es poden seleccionar les pendents per treure pagaments
    - Si un commitment no té fraccionaments a treure, ni deixar sol·licitar ni entrar pagaments

#### STATISTICS/REPORT
    - Afegit 'getIndividualReport' a ReportApiService per quan es vol cridar un informe específic fora de la part de 'Informes'

### MODIFIED
#### CONTRACT
    - ContractRegion.vue block modificar lectures si el contracte es troba a una facturació en prefactura
    - ContractTerminationEdit.vue: Redissenyat completament el pas a pas de la Baixa de contracte a la mateixa línia de temps horitzontal Premium, adaptant la visualització dels passos ("Dades de la Baixa", "Accions" i "Finalització") amb descripcions i estat de progrés impecable.

#### BILLING
    - ReadingBatchEdit.vue: Habilitada i redissenyada la visualització del pas a pas en la configuració de Lots de Lectura a una línia de temps Premium de 4 passos ("Creació", "Configuració", "Lectures" i "Resum"), alineant la seva estètica amb la resta de wizards avançats del projecte.
    - ElectronicInvoiceEdit.vue: Redissenyat el pas a pas de la Generació de Facturació Electrònica a la línia de temps Premium, cobrint la "Selecció" i el "Resum" amb descripcions i indicadors totalment alineats.
    - add.vue (pages/billing/reports): Substituïts els textos estàtics hardcodificats de la vista i avisos de toast per variables dinàmiques de traducció localitzada, donant compatibilitat total per a idiomes.

#### LOCALES
    - locales (ca.ts, es.ts): Afegides les claus de traducció per als passos i títols dels wizards de baixa de contracte, lots de lectura i factures-e. S'ha millorat la descripció del pagament massiu de factures (`bulk_pay_description`) per indicar que els filtres s'apliquen a la llista de factures. S'han afegit nous literals i missatges de toast dinàmics per a la pàgina de creació d'informes.

## [18-05-2026]

### FEAT
#### BILLING
    - S'ha afegit una nova pàgina 'billing/joined-payments' amb les seves regions i 'add'. S'encarrega de mostrar els pagaments agrupats per poder pagar varies factures alhora.
    Al 'add' joined payments podem seleccionar per persona o contracte, ens mostrarà el total pendents i podrem escollir entre aquests pagaments pendents, un mètode de pagament fora de SEPA, TVP online i Saldo (son mètodes que ja funcionen bé de manera individual) i una data de venciment. També podrem fer una ullada al pdf de manera temporal.

    A la region podrem: Pagar, cancel·lar, modificar mètode de pagament i venciment i treure el pdf un altre cop. Podrem veure observacions, logs simples de estatus i els pagaments implicats.

    Això implica bloqueig a: PaymentRegion i InvoiceRegion en cas de tenir els pagaments en un agrupament pendent. Nova secció de pagaments entrant per pagament bancari/visa

    EL fitxer d'entrada de lectures ara és configurable

### FIX
#### BILLING
    - S'ha recuperat l'obtenció de factures electròniques a un nou component més simple o ràpid. Les factures s'obtenen per celery

### CHORE
#### CONTRACT
    - S'ha afegit un checkbox a ContractTermination per si es vol finalitzar la baixa sense Factura, que no surti tota l'estona l'avís de que li falta
    - S'ha afegit la integració amb l'endpoint de validació de dades (`validate-data`) de sol·licituds de contracte per bloquejar i controlar finalitzacions incorrectes d'alta.
    - S'han afegit noves claus de traducció localitzada per als títols dels passos i capçalera del wizard d'alta de contracte a `ca.ts`.

#### PLUGINS
    - contract-request-api.js: Afegit el mètode `validateData` per consultar dinàmicament les validacions de dades sobre les sol·licituds de contracte.

#### OTHER
    - S'ha afegit el component 'SelectPaymentType' per substituir codi repetit a l'hora de selecciona un tipus de pagament. S'ha aplicat a diferents components/ o potser no s'ha aplicat a tots.
    - S'ha afegit un component de confirmació per accions més importants a on obliga al usuari a escriure 'accepto' per continuar

#### BILLING / REPORTS
    - GenericReportForm.vue: Creat un nou formulari genèric modular que dibuixa automàticament controls de dates, desplegables d'explotació, selecció de facturacions o remeses, tipus d'informes, i llistats de productes o tipus de pagaments a partir del llistat de `required_fields` enviat pel Back-end.
    - AcaReportForm.vue: Creat un component a mida per a l'informe ACA que ofereix botons duals de descàrrega (Manual CSV versió 1 i Fitxer Automàtic versió 2).
    - RatesReportForm.vue: Creat un component personalitzat per l'informe desglossat de tarifes de facturació.

#### LOCALES
    - ca.ts i es.ts: Afegit el literal de traducció per a remeses (`remittance`) i les traduccions localitzades completes per a cadascun dels tipus de pagaments del llistat de cobraments.

### MODIFIED
#### CONTRACT
    - ContractRequestEdit.vue: Redissenyat el pas a pas superior (stepper) del wizard d'alta a una línia de temps horitzontal Premium amb indicadors circulars animats de procés actiu (amb ombrejat i pols d'atenció), passos completats (amb checkmarks directes), passos bloquejats, i textos descriptius de títols i subtítols completament alineats.
    - ContractRequestEdit.vue i ContractRequestRegion.vue: Implementada la validació asíncrona automatitzada al Pas 7, banner visual de llista de comprovació (checklist) reactiu que inhabilita el botó de finalitzar, modal elegant de Teleport per capturar errors 400 Bad Request en crear el contracte, i botons intel·ligents de redirecció que porten a l'usuari de manera instantània al pas precís per corregir cadascuna de les dades pendents.
    - ContractRequestTermination.vue: Corregida la visualització de les dades de comptador i estat a la línia de resum tancada de Baixes de contracte. S'ha integrat un watch reactiu a `selectedMeter` per demanar dinàmicament els detalls a l'API amb el nom de propietat real (`meter_code`) i d'estat, protegint la renderització amb operadors d'encadenament segur (`?.`).

#### SERVICE / ROUTES
    - supply-point-api.js: S'ha actualitzat la funció `getByProperty` per recollir iterativament totes les pàgines de punts de subministrament d'una propietat des del backend, assegurant que no es perdi cap element en desar o llistar.
    - AddNewRoutePosition.vue: Implementada la paginació client dels punts de subministrament associats a les finques/propietats de la posició, afegint el component `<Pagination>` per mantenir la vista lateral d'edició compacta i estilitzada quan es llisten molts punts.

#### BILLING / REPORTS
    - GenericReportForm.vue: Actualitzades les flags reactives (`showProducts`, `showTaxFree`, `showModelYear`) per forçar la visualització de camps configurables fixos de forma estàtica per als 8 informes històrics personalitzats en base al seu `function_name`. Corregida la detecció de `model_347` (abans amb una clau errònia `report_billing_347`) i de `billing_cobraments_summary` per a la càrrega dels seus selectors de configuració específics (any, línies exemptes i llistat de mètodes de pagament). Afegits nous `props` (`globalDateRange`, `globalExploitationId`, `globalIncludePreinvoices`) amb els seus corresponents `watchers` per propagar i sincronitzar automàticament els valors configurats a la barra lateral o camps globals cap al formulari de l'informe expandit. Ocultat completament el selector local de dates (`showDateRange = false`) per evitar duplicacions i recollir sempre la informació del rang genèric global. Afegit el mapeig dinàmic `getPaymentTypeName` per renderitzar de forma totalment traduïda el llistat dels 7 mètodes de pagament del resum de pagaments cobrats.
    - AcaReportForm.vue: Simplificat completament per eliminar qualsevol control o selector intern, mostrant únicament els dos botons de descàrrega asíncrona directes (Manual CSV i Fitxer Automàtic) i consumint de forma neta els filtres i l'explotació globals via props.
    - add.vue: Reinstaurada la visualització en acordió (Cas B) per als 8 informes històrics amb camps personalitzats ("Declaració ACA", "Padró de facturació", "Padró de facturació reduït", "Resum de facturació per integració NAVISION", "Model 347", "Resum de pagaments cobrats", "Resum de facturació detallat" i "Resum de facturació per tipus de punt de subministrament") associant directament el seu estat d'acordió mitjançant el comprovador `isCustomReport` i resolent dinàmicament cap a `OrganismsGenericReportForm` com a component de fallback amb els nous `props` globals sincronitzats. Corregida l'asincronia en el muntatge (`onMounted`) esperant deterministament a que finalitzi `getExploitations` (que recupera l'explotació activa de `localStorage`) abans de llançar `getProducts`, garantint que la llista de productes es filtri correctament per a l'explotació activa  des del primer instant. Actualitzat el formatador de l'objecte payload a `handleReportDownload` per empaquetar els llistats de productes, impostos (`taxes_ids`) i mètodes de pagament en cadenes de text separades per comes (`comma-separated strings`) i afegida la compatibilitat doble per a resums comptables enviant tant `account_type` com `accounting_type` per alimentar l'auto-normalització del Back-end.
    - reports-api.js: Eliminades totes les crides estàtiques repetitives a informes infants i simplificat el servei a una sola crida dinàmica `triggerReport` que fa POST a `/api/statistics/available-reports/<report_id>/trigger/`.

## [15-05-2026]

### MODIFIED
#### BILLING / REPORTS
    - reports-api.js i add.vue: Unificat l'antic informe de clavegueram amb el nou informe genèric de recaptació per conceptes. S'ha creat el nou endpoint `recaptacio-conceptes-summary` (via `getRecaptacioConceptesSummary`) i s'ha actualitzat la interfície per permetre el filtratge per explotació (`exploitation_id`) i rang de dates, canviant el nom visual a "Informe de Recaptació per Conceptes".

## [14-05-2026]

### FIX
#### SERVICE / COMPANIES
    - exploitation-api.js: Corregida la serialització de camps de tipus array (com `company_banks_ids`) a les funcions `createCompany` i `updateCompany` en construir el `FormData`, evitant que s'enviessin com a cadenes de text separades per comes i resolent l'error 400 (Bad Request) del Back-end.

#### BILLING / INVOICES & WALLET
    - AddInvoiceBudget.vue i AddWalletCommitmentPayment.vue: Solucionat un error on no es carregava el llistat d'IBANs de l'empresa quan l'objecte pare retornava una estructura de llistat/cerca (`results`) o quan la propietat de l'empresa era un enter pla en lloc d'un objecte niat, afegint el desempaquetat automàtic del primer resultat i comprovació de tipus. També s'ha implementat i millorat la funció `onSelectPaymentMethod` per esborrar automàticament els bancs previs en canviar de mètode, autoseleccionar l'IBAN si només n'hi ha un, i obrir directament el panell lateral amb el llistat d'IBANs si n'hi ha diversos, i s'ha configurat la recuperació automàtica de l'objecte complet de l'empresa a través de `$ExploitationApiService.getCompany` per alimentar les dades locals (`localCompany`) quan no es rep per `props`. A més, s'ha desacoblat tota la lògica d'identificació i obtenció de bancs respecte al bloc `if (props.object_id)` per garantir que es recuperin i sincronitzin automàticament tant en la càrrega inicial com en rebre canvis en l'explotació o els contractes seleccionats lliurement. Per a `AddWalletCommitmentPayment.vue`, s'ha afegit una resolució multinivell extrema: si el contracte només conté l'ID pla de l'explotació, consulta `$ExploitationApiService.getDetail` per extreure'n l'empresa; i com a darrer garant absolut per evitar que `compId` sigui `undefined`, consulta automàticament `$ExploitationApiService.getCompanies()` i pren la primera empresa disponible del sistema.
    - general-invoices.vue i general-payment-api.js: Implementada l'opció de seleccionar el compte bancari d'empresa (via `CompanyBankSelect`) quan el mètode de pagament agrupat configurat és transferència bancària i l'empresa en té diversos d'actius. S'ha definit correctament el gestor d'esdeveniments `onSelectPaymentMethod` per netejar i obrir dinàmicament el llistat de comptes pertinents i s'ha enriquit el procés de desat per enviar el camp `company_iban` cap al servei `$GeneralPaymentApiService`. Així mateix, s'ha estès el mecanisme de resolució multinivell extrem (desempaquetant contractes complets, explotacions o fent fallbacks a nivell de sistema) per assegurar que els comptes de la companyia es carreguin sempre satisfactòriament. A nivell de servei (`general-payment-api.js`), s'ha afegit un pretractament defensiu al payload per extreure dinàmicament l'ID sencer si `company_iban` o `IBAN` arriben com a objectes complets en lloc d'enters plans.

### CHORE
#### BILLING / INVOICES
    - Revertits els textos i la commutació automàtica corresponents als estats i classes de Factures per mantenir exclusivament les funcionalitats de traducció automàtica referents a les alertes de lectura i consums inusualment baixos.

### MODIFIED
#### BILLING / REPORTS
    - reports-api.js i add.vue: Unificats els antics informes d'impagats (resum i detallat) en un únic informe anomenat "Informe retorn SEPA" que genera l'Excel complet amb les dues pestanyes, eliminant l'opció redundant a la interfície i afegint el paràmetre `exploitation_id` per suportar el filtratge per explotació. També s'ha creat un nou botó per a l'"Informe de tots els impagats (Global)" que crida al nou endpoint `wallet-all-unpaid-summary` (via `getAllUnpaidPaymentsSummary`) per incloure totes les modalitats de pagament amb deute pendent.

#### LOCALES
    - locales (ca.ts, es.ts): Actualitzades les etiquetes de traducció per reflectir la unificació ("Informe retorn SEPA" / "Informe devolución SEPA") i afegits els literals corresponents al nou informe global de tots els impagats.

#### SERVICE / PROPERTIES & SUPPLY POINTS
    - PropertyRegion.vue: Afegida l'opció d'afegir i desvincular punts de subministrament a una finca mitjançant un nou botó que desplega la subregió lateral amb el component `AddSupplyPoints.vue`, permetent assignar i desassignar punts al vol utilitzant la mateixa lògica de peticions al Back-end que a les rutes (`bulkUpdateProperty`). També s'ha inclòs l'acció directa d'esborrat (icona d'escombraries) a cada fila del llistat existent.
    - SupplyPointRegion.vue i SupplyPointDetail.vue: Integrada l'opció "Modificar finca" dins del menú d'accions principals per assignar o canviar la finca d'un punt de subministrament desplegant la subregió de selecció (`AddProperties.vue`), preservant automàticament la resta de punts de la finca de destí mitjançant `bulkUpdateProperty`. S'ha afegit també un nou camp de detall visualitzant la finca assignada per permetre la navegació directa cap a la seva vista.

## [13-05-2026]

### FEAT
#### BILLING / BAILS

    - bail-api.js: Afegit el mètode `cancel` al servei de fiances per permetre cridar l'endpoint de cancel·lació al Back-end.
    - BailRegion.vue: Afegida l'opció "Cancel·lar fiança" al menú d'accions per a fiances pendents.


#### READINGS / LOGS

    - logger-api.js: Afegit el mètode `getReadingChanges` al servei de logger per recuperar l'històric de modificacions de lectures filtrat per contracte i comptador.
    - ContractReadingChange.vue: Afegida la visualització de l'històric de modificacions de lectura (amb usuari, data, valor anterior i actual, i observacions) amb un disseny premium i suport de paginació en un panell lateral (region) accessible mitjançant un botó a la capçalera.

### FIX
#### BILLING / INVOICES

    - AddInvoiceBudget.vue: Eliminada l'alerta de confirmació innecessària en la creació inicial de pressupostos per evitar confusió amb l'emissió de factures definitives.
    - AddInvoiceBudget.vue i BudgetEdit.vue: Solucionat l'error on el botó de "Generar pressupost" quedava deshabilitat o no s'actualitzava la llista en fer "Tornar a generar pressupost", passant correctament el nou pressupost al pare i preservant la reactivitat de les opcions de facturació seleccionades (`selectedCustom`).

### CHORE
#### BILLING / SUMMARY

    - BillingSummary.vue i BillingDocumentsSummary.vue: Solucionat un error de visualització on el recompte de lectures i l'etiqueta d'estat apareixien buits als apartats de "Lots de lectura", afegint suport de resolució dual per a objectes plans i niats (`num_total_readings` i `status_name` / `status_color`).

### MODIFIED
#### CORE DATA / CONTRACT

    - Added functionality for multiple operating companies.

#### CORE DATA / CALL REGISTER

    - AddNewCall.vue: Corregida la funció de guardat per enviar sempre el registre de trucada cap al Back-end en finalitzar, independentment de si s'ha fet clic en el botó de trucar prèviament, i s'ha solucionat el tancament prematur en cancel·lar el diàleg de confirmació.

#### SERVICE / SUPPLY POINTS

    - supply-point-api.js: Afegit el mètode `patch` per permetre l'actualització parcial d'atributs d'un punt de subministrament mitjançant la petició HTTP PATCH.
    - SupplyPointDetail.vue: Implementada la capacitat de modificar les observacions del lector (`reader_observation`) directament des de la vista de detall amb un formulari integrat i s'ha millorat la seva visualització general amb una targeta premium i dinàmica.

#### READINGS / OBSERVATIONS

    - ReadingsChange.vue: Millorat el registre de canvis en les observacions per detallar si es marca com a lectura de control (incloent valors anterior i nou), l'addició de fuites, la modificació de la data i la creació de noves lectures (estimades, manuals o de control). També s'ha corregit un error de sincronització que impedia propagar i registrar correctament el log i l'estat d'emmagatzematge en afegir una lectura nova sense modificar-ne d'existents.
    - ContractReadingChange.vue: Implementat el mapeig i la traducció automàtica de les observacions del Back-end corresponents a consums inusualment baixos ("Unusually low consumption") o alts ("Unusually high consumption").
    - ReadingBatchSummary.vue: Afegida la traducció automàtica de les etiquetes dinàmiques dels comptadors de resum d'alertes i incidències (tals com "Lectura 0", "Lectura Negativa", "Lectura inusual" i "Unusually low consumption") i adaptat el títol dinàmic del llistat lateral per suportar en temps real la resolució i traducció de les noves claus del Back-end (`reading_alert_*`).
    - Adaptadors Globals: Implementada la traducció nativa dinàmica a `ColorBadge.vue`, `StatusesNav.vue` i `FilterSelect.vue` per suportar nativament i commutar automàticament al vol les noves claus proporcionades pel Back-end relacionades amb tipus d'alertes de lectura (`reading_alert_*`).

#### LOCALES

    - locales (ca.ts, es.ts): Afegits els literals globals `common.saving` i `common.saved_successfully` per donar suport a l'estat d'emmagatzematge en les edicions en línia, així com els mapes exhaustius de claus normalitzades de Back-end per a alertes de lectura (`reading_alert_*`).

## [12-05-2026]

### FIX
#### BILLING
    - InvoiceRegion.vue: Corregida la pèrdua de la propietat `in_invoice` en obrir el diàleg de refacturació, la qual cosa impedia seleccionar el tipus o opció de refactura (RedoOptions).

### CHORE
#### BILLING
    - Afegida la funcionalitat de configuració de columnes per a la exportació de lots de lectura.

## [11-05-2026]

### MODIFIED
#### BILLING
    - Permetre obtenir el saldo de persona en cas de ser més que 0 i no tenir saldo de contracte disponible
    - payment-api.js: Actualitzada la funció `returnBank` per incloure el paràmetre `payment_origin` en la petició al Back-end, assegurant-ne la persistència.
    - BankReturnSetup.vue: Implementada la tramesa de l'origen del pagament en processar fitxers de devolució bancària (RND/N57), garantint que es guardi independentment de si es marca l'opció de "Guardar saldo".
    - BankReturnSetup.vue: Refinada la validació de selecció de pagaments per evitar missatges d'error innecessaris quan es processa un fitxer sense seleccions individuals de saldo.
    - BankReturnSetup.vue: Millorada la robustesa del procés de càrrega mitjançant la sincronització d'operacions per evitar condicions de carrera en actualitzar les dades.
    - EstimateReadingsDialog.vue: Creat un nou component modal per a l'estimació massiva de lectures que permet triar entre data específica, dies des de l'última lectura o estimació per defecte, amb una estètica integrada amb la resta del sistema.
    - ReadingBatchReadingsSummary.vue: Integrat el nou diàleg d'estimació, substituint el `confirm` natiu del navegador i permetent una configuració avançada de l'estimació.
    - reports-api.js: Afegit el mètode `getCobramentsSummary` per gestionar la generació asíncrona de l'informe de resum de cobraments.
    - add.vue: Implementada la integració de l'informe de resum de cobraments, incloent la petició a l'API, el monitoratge de la tasca asíncrona (Celery) i la descàrrega automàtica del fitxer generat.
    - locales (ca.ts, es.ts): Afegits literals per al nou diàleg d'estimació de lectures i l'informe de cobraments.

#### CORE DATA / STREETS
    - street-api.js: Afegit el mètode `create` al servei de carrers per permetre la creació estàndard mitjançant POST.
    - AddPartialAddress.vue: Actualitzada l'estructura de la crida a `partial-address` per incloure `address_city` a l'arrel, assegurant la correcta vinculació del carrer amb la ciutat.
    - AddAddress.vue: Inclòs el camp `city` dins de l'objecte de carrer en crear un carrer nou per mantenir la integritat de les dades.

#### SERVICE / CONNECTIONS
    - ConnectionEdit.vue: Implementada la selecció automàtica de l'explotació activa (des de localStorage) en crear una nova escomesa.
    - ConnectionEdit.vue: Assegurat que el camp `exploitation` s'enviï sempre en el payload de guardat, tant en creació com en edició.
    - ConnectionEdit.vue: Habilitat el selector d'explotació durant la creació d'escomeses per permetre la revisió de l'explotació assignada.

## [08-05-2026]

### CHORE
#### PRICING
    - ProductDetail.vue: Afegida informació d'empresa

### MODIFIED
#### CONTRACT
    - ContractRequestSummary.vue: Millorada la claredat en la facturació de lectura de tall mitjançant alertes informatives i etiquetes visuals que identifiquen el sol·licitant com a pagador.
    - ContractRequestSummary.vue: Implementada l'eliminació automàtica (amb confirmació) de pressupostos i factures de tancament en desactivar l'opció de lectura de tall per mantenir la coherència de dades.
    - ContractRequestSummary.vue: Optimitzada la visualització de factures de tancament realitzant cerques explícites per a cada sol·licitud de baixa vinculada.
    - ContractTerminationRegion.vue: Vinculada la generació de factures de tancament al sol·licitant de la baixa, enviant la informació necessària al Back-end per a la seva correcta identificació.

#### INCIDENT / ORDERS
    - ChangeStatus.vue: Implementada la detecció d'ordres pendents en tancar una incidència, amb un diàleg de confirmació per permetre el tancament automàtic de les ordres associades.
    - order-api.js: Afegit el filtre per `incident_id` a la funció `getAll` per permetre la recuperació d'ordres vinculades a una incidència específica.

#### BILLING
    - index.vue (wallet-managements): Afegir el filtre per filtrar per dates, la data de pagament dels pagaments de cartera.
    - IndividualInvoiceForm.vue: Implementada la selecció dual de Facturacions i Lots en la generació de factures personalitzades, assegurant l'enviament correcte de `billing_id` o `billing_batch_id` segons el tipus seleccionat.
    - AddInvoiceBudget.vue: Afegit suport per al paràmetre `bill_termination_requester` en la generació de pressupostos i factures.

#### LOCALES
    - locales (ca.ts, es.ts): Afegits literals informatius i de confirmació per a la gestió de la facturació de lectura de tall i el canvi de responsabilitat en les baixes.
    - locales (ca.ts, es.ts): Afegits literals `incident_block` per a la confirmació del tancament d'ordres associades a incidències.

## [07-05-2026]

### FIX
#### READINGS
    - SupplyMeterChange.vue: No mirava si existia la lectura anterior, ara si.

#### CONTRACT
    - ContractRequestEdit.vue: Corregida la inicialització de `terminationData` en `loadData()` per evitar la pèrdua d'estat al refrescar o navegar.
    - ContractRequestEdit.vue: Convertit `onContractTerminated` a asíncron per garantir que el guardat finalitzi correctament abans de permetre l'avanç de pas.

### CHORE
#### LOCALES
    - locales (ca.ts, es.ts): Afegit el literal `common.no_options` per a una millor experiència d'usuari en els selectors sense dades.

### MODIFIED
#### CONTRACT
    - ContractRegion.vue: Destacat visual en vermell de la pestanya de gestió de deute quan el contracte té deute pendent.
    - ContractDetail.vue: Marcador d'import de deute ressaltat en vermell per millorar-ne la visibilitat.
    - ContractRequestEdit.vue: Refactorització del mètode `save()` al pas 6 (Baixa de contracte) per consolidar crides a l'API i evitar bloquejos de la interfície (spinner).
    - ContractRequestEdit.vue: Corregit l'índex del pas 7 (Resum) a la funció de guardat per permetre la persistència correcta de les dades finals.

#### BILLING
    - InvoiceRegion.vue: Estabilitzada la visualització de les sub-regions mitjançant un overlay lateral fixat amb ombra destacada i transicions millorades.
    - InvoiceRegion.vue: S'ha afegit el pas de la propietat `isSubRegion` al component `InvoiceViewEdit` per mantenir la consistència del disseny.
    - AddInvoiceBudget.vue: Millorat el disseny de l'overlay lateral fixat a la dreta amb ombra (`shadow-2xl`) i una transició més fluida.
    - AddInvoiceBudget.vue: Eliminat l'interruptor de "Facturar lectura de tall" per redundància amb el resum de la sollicitud.
    - IndividualInvoiceForm.vue: Implementada la plantilla `#no-options` en tots els `v-select` per millorar el feedback visual quan no hi ha resultats.

#### READINGS
    - ReadingsChange.vue: Millorada la selecció de lectura prèvia permetent distingir entre múltiples lectures realitzades el mateix dia mitjançant una identificació granular (ID, valor, comptador, etc.).

## [06-05-2026]

### FEAT
#### ORDERS
    - Gestió d'adjunts al formulari d'informes: Ara es poden eliminar fotos incorrectes i pujar-ne de noves directament des del detall de l'informe (OrderReportEdit.vue).

### FIX
#### CONTRACT
    - ConnectionRequestData.vue i ConnectionRequestDetail.vue: Corregit l'error de validació en crear ordres des de sollicituds d'escomesa (address i reason) movent la informació a la descripció per complir amb les restriccions de claus foranes del Back-end.
    - ContractDetail.vue: S'ha afegit un fallback a `created_at` quan `registration_date` és `null` per garantir que sempre es mostri la data de registre al detall del contracte.

#### BILLING
    - InvoiceEdit.vue: Corregida la compressió lateral de l'icones d'acció que deformava la seva forma circular.

### CHORE
#### BILLING
    - Eliminat opció de generar pressupost per factura agrupada.

#### COMPONENTS
    - InputTime.vue: Nou component per a l'entrada estandarditzada d'hores (HH:MM).

### MODIFIED
#### ORDERS
    - OrderReportEdit.vue: Habilitada l'edició de dates, hores i camps del formulari (text i numèrics) que abans eren de només lectura.
    - OrderReportEdit.vue: Millorada la robustesa en la càrrega i enviament de l'operari per evitar errors de validació del Back-end (operator_id).

#### BILLING
    - BillingSummary.vue: Millora en la detecció i visualització de lots de lectura vinculats (`reading_batches` i `missing_batch`).
    - BillingSummary.vue: Integració de la navegació directa cap a `ReadingBatchRegion` per modificar lectures des de la mateixa pantalla.
    - BillingSummary.vue: Redisseny dels botons de control ("Re-calcular" i "Modificar lectures") per ser més visuals i compactes, situats sota el títol de pre-factures.
    - BillingDocumentsSummary.vue: Si no hi han contractes sense facturar, no mostra possibles causes. Si n'hi ha, només mostra les possibles causes > 0.
    - general-invoices.vue: Ara fa servir dos adreces com una factura normal. S'ha modificat també la posició del botó 'Guardar'.
    - InvoiceEdit.vue: Ampliació de la columna d'accions a 200px i ús de `flex-shrink-0` per evitar la compressió dels botons circulars. S'han afegit *tooltips* a totes les accions.

#### CONTRACT
    - ContractDetail.vue: S'ha afegit la visualització de la data de baixa (`termination_date`) per als contractes que hagin finalitzat.

#### READINGS
    - SupplyMeterChange.vue: S'ha canviat el component per poder gestionar tant el comptador com les lectures alhora, de manera que no guardem lectures sense fer el canvi o la inversa. Ara tot es guarda junt al final un cop pressionem 'Guardar'. També, a SupplyPointRegion.vue ara el '@save' del component mencionat només tanca i recarrega la pàgina.
    - ReadingsChange.vue: S'ha canviat el 'Deseleccionar' de lloc amb només una icona de reset. També s'ha afegit una mica d'informació dient què fa cada botó de les lectures (quina canvia a control i quina l'esborra).

## [05-05-2026]

### FEAT
#### READINGS
    - Afegir opció a nova lectura estimada (ReadingsChange.vue). Es pot estimar manualment o cridant estimateReading(). NO es poden afegir estimades entre lectures ja existents i un cop afegit una estimada només es podran afegir estimades. Raonament -> Si tens una lectura real recent no té sentit estimar altres.

#### BILLING
    - Funcionalitat d'exclusió de factures: Permet excloure factures d'una remesa (tant individualment com en massa) i gestionar-les en una remesa d'excloses (BillingSummary.vue i InvoiceEdit.vue).
    - Selecció múltiple de factures a la vista de resum de remesa per a accions en bloc.

### FIX
#### READINGS
    - ReadingsChange.vue: Controlar estimar amb diferents períodes de facturació. Si son aforaments entrar una lectura normal, no pas estimada.
    - ReadingsChange.vue: Al estimar, si la lectura entrava en conflicte amb un període amb lectura i no retornava un objecte, es quedava xafat. Arreglat, ara mostrar warning de que no s'ha pogut estimar i com a molt s'ha de fer a mà.
    - ReadingsChange.vue: Al seleccionar lectures existents per esborrar, ja no es mostraven a la llista. Ara tornen a sortir. També deixar deseleccionar lots de lectura a les lectura. Correcció amb afegir lectures estimades, deixar modificar estimated_bag, abans es recalculava constantment.
    - ContractReadingChange.vue: Només controlava que hi haguessin lectures per modificar/crear per fer la crida dels canvis sense mirar si hi havien per eliminar. Ara mirar tots dos casos.

### CHORE
#### GENERAL
    - Afegir el fitxer de CHANGELOG.md pel control de canvis.

### MODIFIED
#### PERSON
    - PersonRegion ja no mostra TAB de Saldos ja que ara té la bossa de saldo pròpia.
