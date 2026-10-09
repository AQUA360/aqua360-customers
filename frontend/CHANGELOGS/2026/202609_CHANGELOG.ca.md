

## [30-09-2026]

### CHORE
#### SERVICE (`AddCompany.vue`, `CompanyDetail.vue`, `ExploitationEdit.vue`, `ExploitationDetail.vue` — el codi d'entitat subministradora passa a l'empresa)
    - El `supply_code` (codi d'entitat subministradora de l'ACA) es mou de l'explotació a l'empresa, com al backend (`service/migrations/0126_move_supply_code_to_company.py`). Ara s'edita al formulari d'empresa, al costat del NIF, i es mostra al detall de l'empresa.
    - Es treu el camp del formulari d'explotació. El detall de l'explotació el continua mostrant, llegit de l'empresa de l'explotació.
    - Requereix desplegar **backend i frontend alhora**: amb el backend antic el formulari d'empresa no desa el codi, i el d'explotació deixa d'enviar-lo.
    - **No s'ha provat en un navegador**.

#### CONTRACT (`docs/document-sign/` — documentació de la signatura OTP)
    - `frontend-flow.md`: on surt el widget, botons per estat i endpoints que el front crida.
    - `backend-endpoints.md`: contracte d'API confirmat amb backend.

#### CONTRACT (backend confirma el contracte de Signatura OTP)
    - `POST document-sign/{id}/retrieve/`: consulta Aqua360 i no retorna binari. Si ja està signat, desa el PDF, passa a `3` i 200 amb `contract_file_signed_url` i `signed_at`. Si encara no, 200 amb l'estat que ja tenia (`2` o `4`); el front mira `status === 3`. Si Aqua360 el dóna per caducat, estat `4` i 200. Si Aqua360 falla, estat `-1`, `error_report` i **502**. `/send/` només envia la petició OTP.
    - `contract_file_signed_url` només ve informat amb estat `3` i apunta a la mateixa descàrrega (cal `Authorization`). `contract_file_url` continua sent el PDF original.
    - Un reenviament correcte desvincula el PDF signat de la sessió anterior: no queda descarregable fins que la nova signatura es tanqui.
    - El `DELETE` esborra el registre local en qualsevol estat, inclòs `3`. Aqua360 Sign no documenta cancel·lar la sessió: l'enllaç OTP pot seguir viu fins que caduqui. Un callback posterior d'aquella referència respondrà 404.
    - En finalitzar l'alta, el `DocumentSign` de la sol·licitud ja es vincula al contracte i es conserva `contract_request`. El llistat per `contract_id` el troba. El webhook d'Aqua360 ja fa la mateixa feina que `retrieve` quan el signant acaba; el front no en depèn.

### FIX
#### CONTRACT (`DocumentSignStatus.vue`, `ContractRequestDetail.vue`, `document-signs/index.vue`, `document-sign-api.js`, locales — flux de signatura OTP)
    - Un cop enviat a signar no hi havia manera de tornar a començar: la caixa d'estat mostra ara un botó **Reiniciar** (amb confirmació) que esborra la petició actual i deixa tornar a enviar.
    - El botó **Descarregar** sortia així que s'enviava, perquè feia servir l'URL del contracte original (encara no signat). Ara **Descarregar** només surt quan l'estat és *Signat*. Mentre està *Enviat a signar* (o *Caducat*) el botó és **Sol·licitar document signat**: `POST document-sign/{id}/retrieve/` (consulta Aqua360, sense binari) i refresca l'estat; si encara no hi ha document, avisa i no descarrega res.
    - El mateix component passa a ser operable des de `ContractRequestRegion` (bloc Contracte de `ContractRequestDetail`), no només des del pas de resum de l'alta ni de la pestanya Documents.
    - En català, les etiquetes del flux passen de «firma/firmar» a «signatura/signar».
    - **Sol·licitar document signat** no reutilitza `/send/` (això només és l'Enviar inicial). Crida `POST document-sign/{id}/retrieve/`. Després d'un enviament correcte ja no es torna a mostrar Enviar, encara que l'estat trigui a passar a *Sended*.
    - **No s'ha provat en un navegador**; els components compilen.

## [29-09-2026]

### FEAT
#### BILLING (`SEPAManagementEdit.vue` — remeses amb selector de banc manual)
    - Amb el ConfigProject `use_manual_bank_remittance` a `true`, la pantalla de remeses SEPA torna al funcionament d'abans: selector d'un sol compte (els de l'empresa de l'explotació, amb el SEPA preseleccionat) i s'envia `selected_bank` en lloc de `selected_companies`/`bank_assignments`. S'amaguen el selector d'empreses, el botó de revisar l'encaminament i la columna Banc del llistat de rebuts.
    - Amb `false` (per defecte) no canvia res.
    - **No s'ha provat en un navegador**; el component compila.

### FIX
#### SERVICE (`SupplyPointDetail.vue`, `locales/*` — el bloc d'observacions del lector es confonia amb la pestanya Observacions)
    - El bloc del detall del punt de subministrament que edita `reader_observation` es titulava «Observacions», la mateixa etiqueta que la pestanya d'observacions. Ara fa servir la clau `common.reader_observation`, també al placeholder del camp.
    - El text de la clau passa de «Observació del lector» a «Observacions per al lector / operaris» (i l'equivalent a castellà, anglès i gallec). La ruta i la posició de ruta, que ja feien servir aquesta clau, mostren el mateix text.
    - **No s'ha provat en un navegador**.

## [28-09-2026]

### FIX
#### SERVICE (`ClusterEdit.vue`, `AddPartialAddress.vue`, `locales/*` — no es podia desar una bateria amb un carrer nou: error `errors.address_street_id_required`)
    - Causa: `ClusterEdit.vue` exigeix `address_street_id` abans de desar, però un carrer nou encara no té id (`AddPartialAddress` només n'envia el nom i el tipus), així que el desat es bloquejava. A més, la clau `errors.*` no existia a cap idioma i l'usuari veia la clau crua.
    - `AddPartialAddress.vue` exposa `persistAddress()`, que desa el carrer i el número a `coredata/partial-address/` (l'endpoint busca abans de crear: no genera duplicats ni modifica carrers existents) i deixa el carrer creat com a seleccionat. `ClusterEdit.vue` la crida abans de desar la bateria i abans de crear el punt de subministrament d'una boquilla, quan no es fa servir l'adreça de la connexió.
    - Corregit: en passar a "crear carrer" s'enviava l'id del carrer seleccionat abans (i es reutilitzava aquell carrer, ignorant el nom nou); i en canviar el carrer o el número s'enviava l'id del número carregat inicialment (la bateria es quedava amb el número del carrer antic).
    - Corregit: "Cercar per cadastre" feia servir una variable `province` inexistent i petava.
    - Els missatges de validació de `ClusterEdit.vue` passen a les claus existents `address_block.error_required_*` (+ nova `address_block.error_required_street_type`).
#### BILLING
    - Al generar el pdf de factura personalitzada, es guardava cada línia amb els decimals máx 2 i sense arrodonir. Ara es passa 4 decimals i s'arrodoneix al back

### FEAT
#### SERVICE (nou `StreetPicker.vue`, `AddPartialAddress.vue`, `AddAddress.vue` — selector de carrer més usable i comú a tots els formularis d'adreça)
    - El selector de carrer passa a un component compartit, `components/molecules/StreetPicker.vue` (v-model `{ street, creating, name, type }`), que fan servir tant `AddPartialAddress.vue` com `AddAddress.vue`. Abans cada un tenia la seva còpia.
    - Un sol camp de cerca amb desplegable (indicador de càrrega, navegació amb ↑/↓/Enter/Esc). L'última opció és sempre "Crear el carrer «…»" amb el text escrit, si no hi ha cap carrer amb el mateix nom.
    - El carrer triat es mostra com a confirmació amb un botó per canviar-lo. En mode creació, el nom ve prefixat amb el text cercat, el tipus de via és editable, s'indica que el carrer es crearà en desar i es mostren carrers existents amb un nom semblant per poder triar-ne un i no duplicar-lo.
    - El bloc de número només apareix quan ja hi ha un carrer triat o s'està creant.
    - Mateixes props, event `valueChanged` i forma de l'objecte emès: `PropertyEdit`, `MeterEdit`, `ConnectionEdit` i `ConnectionRequestPerson` no canvien.
    - `AddAddress.vue`: mateix comportament, amb les seves particularitats. Per a adreces estrangeres o províncies 98/99 (municipi manual) només es pot crear el carrer, sense cerca. El cadastre només surt per a adreces d'Espanya. El tipus de via admet text lliure. En triar un carrer amb codi postal, s'omple el codi postal. Ara també exigeix el tipus de via en crear un carrer. Les dades que envia a `createAddress`/`updateAddress` no canvien, de manera que els seus usos (persones, empreses, punts de subministrament, sol·licituds, ordres...) no s'han de tocar.
    - Els estils globals `#street_type_select` i `.create-street` es mouen al component compartit (`.street-picker-type`, `.street-picker-name`); no els feia servir cap altre component.
    - Claus noves als quatre idiomes (`address_block.*`).
    - **No s'ha provat en un navegador**; els components compilen.

#### CONTRACT (`ContractRequestTermination.vue`, `ContractRequestEdit.vue`, `reading-api.js`, `locales/*` — "Facturar període complert": avís de lectura no facturada del contracte anterior)
    - Amb "Facturar període complert" marcat, el bloc "Lectura inicial" del pas 6 consulta el nou endpoint `request-transferable-reading/`. Si el contracte anterior té una lectura encara no facturada, es mostra un avís amb el valor, la data i el contracte, i un botó "Utilitzar com a lectura inicial".
    - El botó demana confirmació i crida `request-transfer-reading/`, que traspassa la lectura a l'alta com a lectura inicial (`is_initial`). Després el bloc es comporta igual que si s'hagués desat una lectura inicial manual (s'emet `change-sp` perquè el pas 7 revalidi).
    - `ContractRequestEdit.vue` passa `billFullPeriod` a `ContractRequestTermination` (prop nova `billFullPeriod`).
    - Claus noves als quatre idiomes: `contract_block.transferable_reading_warning`, `contract_block.use_as_initial_reading`, `confirmation_text_block.confirm_use_transferable_reading`.
    - **No s'ha provat en un navegador**; els components compilen.

#### CONTRACT (`ContractTerminationDetail.vue`, `ContractStatusBadges.vue` — bloc de contracte compacte al detall de la baixa)
    - Els blocs «Contracte» (amb el `ContractDetail` sencer) i «Punt de subministrament» ocupaven massa espai. Es fusionen en un sol bloc «Contracte» amb: identificació (enllaç a `ContractRegion`), data d'alta (`registration_date` o, si no n'hi ha, `created_at`), titular (`PersonBadge`) i subministrament (adreça del punt per defecte, enllaç a `SupplyPointRegion`).
    - A sota, les quatre etiquetes d'estat del contracte: estat, saldo, deute i nombre de persones. Es reutilitza `ContractStatusBadges.vue`, que té una prop nova `showExtra` (per defecte `true`) per amagar les etiquetes de bossa de consum i de dipòsits en compromís. La resta d'usos (`ContractDetail.vue`, `PinnedContractBasicInfo.vue`) no canvien.
    - Ja no es llisten els punts de subministrament addicionals del contracte; només el per defecte.

#### CONTRACT (`ContractTerminationDetail.vue`, `ContractTerminationRegion.vue`, `ContractTerminationEdit.vue`, `locales/*` — botó per finalitzar la baixa directament)
    - Si el consum ja està facturat, el bloc «Factura final» del detall de la baixa mostra un botó «Finalitzar baixa» que la tanca directament, sense entrar al procés i anar fins al pas 3.
    - Es considera facturat quan hi ha factura final, o quan la darrera lectura de tots els punts de subministrament ja està facturada (el mateix cas que mostra l'avís «L'última lectura ja està facturada»).
    - El botó només surt si la baixa és en esborrany o pendent (els mateixos tokens `contract_termination_draft` / `contract_termination_pending_status` que el botó «Finalitzar» del procés), no té connexió vinculada i l'usuari pot modificar baixes. Dins del procés (`ContractTerminationEdit.vue`, pas 3) s'amaga amb la prop nova `showQuickFinalize`, perquè allà ja hi ha el botó «Finalitzar».
    - Demana la mateixa confirmació que el procés i crida el mateix endpoint `close`. A diferència del procés, on l'estat del punt de subministrament es tria al pas 2, aquí sempre es passa a «no contractable» (`supply_point_status_not_contractable_token`). Després es recarrega el detall i `ContractTerminationRegion.vue` es refresca (event nou `finalized`).
    - Clau nova als quatre idiomes: `contract_block.finalize_termination`.
    - **No s'ha provat en un navegador**; els components compilen.

#### CONTRACT (`ContractTerminationEdit.vue`, `ContractRequestTermination.vue`, `locales/*` — la lectura que es demana a la baixa s'identifica com a «Lectura de tall»)
    - Els camps de valor, fuita i data de la lectura del pas 2 de la baixa, i els de la baixa del contracte anterior dins de `ContractRequestEdit.vue`, no deixaven clar quina lectura es demanava. Ara són dins d'un requadre taronja titulat «Lectura de tall» (icona de tisores), separat del requadre blau de la darrera lectura registrada, amb el text d'ajuda «Introdueix la lectura del comptador en el moment de la baixa. És la lectura amb què es tancarà el contracte.»
    - El botó de desar passa de «Desar Lectura manual» a «Desar lectura de tall». A `ContractRequestTermination.vue`, el botó d'obtenir la lectura de Smart Metering i els seus missatges queden dins del mateix requadre.
    - Claus noves als quatre idiomes: `billing_block.cut_reading`, `cut_reading_info` i `save_cut_reading`.

#### CONTRACT (`ContractRequestTermination.vue` — es treu el bloc «Sol·licitant» de la baixa dins la sol·licitud de contracte)
    - Dins de `ContractRequestEdit.vue` la persona que sol·licita la baixa no aporta res. Es treu el bloc; el detall de la baixa i el seu procés el continuen mostrant.

### CHORE
#### READING
    - ReadingsChange es torna a mostrar el botó per mostrar/amagar les lectures de control.

## [25-09-2026]

### FEAT
#### CONTRACT (`pages/contract/clause-templates/index.vue`, `ClauseTemplateEditRegion.vue`, `pages/settings/index.vue`, `locales/*` — gestió de plantilles de clàusules)
    - Fins ara les plantilles de clàusules només es podien seleccionar i assignar; crear-les o canviar-ne el text només es podia fer des de l'admin de Django. Nova pàgina `/contract/clause-templates/`, enllaçada des de Configuració → Contractació («Clàusules: Plantilles de clàusules»), amb el llistat (identificador, títol i inici del text), cerca, ordenació per identificador i títol i paginació.
    - Nova regió `ClauseTemplateEditRegion.vue` per crear i editar una plantilla (identificador, títol i text; títol i text obligatoris). En editar es mostra un avís: els canvis només s'apliquen a les clàusules que s'assignin a partir d'ara, perquè cada clàusula de sol·licitud o contracte en guarda una còpia del text.
    - Els permisos són els de sol·licituds de contracte (`$ContractRequestApiService`), els mateixos que comprova el backend (`ContractRequestPermission`).
    - Botó «Eliminar» a la regió d'edició: esborrat lògic (`is_active = false`) amb confirmació. Les clàusules ja copiades a sol·licituds i contractes es conserven.
    - La pàgina i els dos selectors de plantilles (`AddClauseTemplate.vue`, `ClauseTemplateSelectMultiple.vue`) només demanen plantilles actives (`?is_active=true`). No hi ha manera de reactivar una plantilla des del front; de moment es fa des de l'admin.
    - `AddClauseTemplate.vue` (afegir clàusula a una sol·licitud) mostra «No hi ha clàusules configurades» quan no hi ha cap plantilla activa, en lloc d'una llista buida.
    - Claus noves als quatre idiomes: `contract_block.clause_template`, `new_clause_template`, `clause_template_edit_notice`, `confirm_delete_clause_template` i `no_clauses_configured`.
    - Requereix els canvis corresponents al backend (cerca, ordenació i filtre `is_active` a `clause-template`).
    - **No s'ha provat en un navegador**; els components compilen.

#### COMMUNICATION (`CommunicationProcessCreation.vue`, `CommunicationProcessCreationSetup.vue`, `CommunicationProcessCreationManage.vue`, `CommunicationProcessCreationData.vue`, `locales/*` — selector d'empresa al pas 1 del wizard de nou procés de comunicació)
    - Si el configProject `use_multiple_companies` és cert, el pas 1 mostra un selector «Empresa dels contractes» (empreses proveïdores, carregades com a `ContractRequestSetup.vue`). Surt tant a la cerca per filtres com a la cerca fixada (facturació / gestió d'impagats / remesa SEPA).
    - L'empresa triada s'envia a la cerca com a `filters.company` i el backend exclou els contractes assignats a una altra empresa. El selector és opcional: si es deixa buit, no es filtra res.
    - **Pas 3:** `CommunicationProcessCreationData.vue` rep `defaultCompanyId` i preselecciona la configuració d'empresa (`service/company-config`) d'aquella empresa. Si només n'hi ha una es continua triant sola, i si ja n'hi ha una de desada es respecta.
    - Canviar l'empresa del pas 1 buida el resultat de la cerca i l'empresa i el remitent del pas 3, perquè cal tornar a cercar i el pas 3 torni a preseleccionar la de la nova empresa.
    - Clau nova als quatre idiomes: `customer_service_block.select_contracts_company`.
    - Requereix els canvis corresponents al backend (filtre `company` a la cerca de destinataris).
    - **No s'ha provat en un navegador**.
#### SERVICE (`components/organisms/SupplyCutRegion.vue`, `SupplyCutEdit.vue`, `ContractRegion.vue`, `components/molecules/SupplyPointDetail.vue`, `pages/service/supply-cut/index.vue`, `locales/*` — edició del motiu i avís de revisió manual dels talls de subministrament)
    - Nova targeta àmbar «Requereix revisió manual» al detall del tall en quarantena (backend `requires_review`), amb el motiu exacte: estat «Conflicte», o el valor `cause_raw`/`state_raw` rebut de Giswater sense mapeig al catàleg, indicant quina configuració falla (`giswater_mincut_cause_map`/`giswater_mincut_state_map`), una línia «què cal fer» (`review_reason_action`) i l'acció «Resoldre revisió» (també al menú) que obre el panell per assignar l'estat real i treure el tall de la cua.
    - Nova acció «Canviar motiu» (amagada en quarantena): edita el motiu, la data de fi prevista (obligatòria per als motius puntuals quan no n'hi ha) i una observació, des d'un formulari compacte. Exclou les causes d'origen Giswater («Accidental (giswater)»/«Planificada (giswater)») i mostra una confirmació quan el canvi passa de puntual a indefinit (o a l'inrevés), explicant l'efecte sobre els punts de subministrament.
    - L'avís àmbar de tall vigent (punt de subministrament i contracte) només surt quan hi ha un tall realment vigent i mostra la data de fi prevista formatejada (`formatDate`, en lloc de la data/hora crua de l'API); la llista de talls es refresca reactivament (`changed`/re-clau del detall) després d'iniciar/acabar/canviar motiu.
    - Cal tenir el backend del mateix dia (quarantena, `requires_review`, edició de motiu, alerta per fi prevista).

### FIX
#### SERVICE (`components/organisms/SupplyCutRegion.vue`, `components/molecules/SupplyPointDetail.vue` — l'avís de tall vigent es quedava penjat i no era reactiu)
    - El banner/tisores de tall del punt de subministrament no desapareixia quan el tall deixava de ser vigent (acabat, cancel·lat, en quarantena, temporal passat o pla amb la fi prevista superada) fins a una càrrega completa de pàgina. Ara el detall es re-munta (`spDetailKey`) i la llista es refecta (`@changed`) després de cada acció, i el contracte mostra el mateix avís amb la mateixa regla.
#### SERVICE (`plugins/api/api-manager.js`, `pages/service/supply-cut/index.vue` — cap pàgina no es queda en estat «Loading» / encallada davant d'un 401)
    - `handleUnauthorized`: el redireccionament a `/auth/login` passa a ser no bloquejant (`router.push('/auth/login')` sense `await` i amb `.catch(() => {})`), de manera que el `finally` dels components s'executa sempre, es reseteja el `pending` i cap pàgina es queda en càrrega infinita quan la sessió caduca.
    - Cerca de talls de subministrament: es treu el disparador redundant `@input` de la caixa de cerca (ara la cerca la dispara únicament el `watch` de `searchInput`/`selectedFilters`, amb `@submit` per a l'Enter), failsafe `pending = false` a la sortida per manca de permís (`can_view`) i token de seqüència (`requestSeq`) perquè una resposta antiga o desendreçada no pugui deixar la taula penjada ni assignar dades/errors fora d'ordre.
#### SERVICE (`components/organisms/SupplyCutRegion.vue` — el panell de resolució de revisió no es tancava en confirmar)
    - `saveResolveReview` crida ara `closeSubRegion()` en completar-se, així el panell lateral dret desapareix després de resoldre la revisió, igual que amb la resta d'accions del panell.
#### GENERAL (enduriment davant de 401 a tota l'aplicació — `plugins/api/api-manager.js`, `middleware/permission.js`, `SideBarSearch.vue`, `RouteEdit.vue`, `UserEdit.vue`, `pages/billing/billing/edit/[id].vue`, `pages/billing/reports/edit/[id].vue`, `ManageContractsRegion.vue`, `meter-api.js`, `contract-api.js`, `sepa-remittance-api.js`, `config_aca/index.vue`, `config_aca/index_prev.vue`)
    - `api-manager.js`: `handleUnauthorized` s'exposa com a `$apiManager.handleUnauthorized`, tanca també els panells oberts de cerca/notificacions/contracte fixat i limita els toasts de sessió caducada a un per període.
    - `middleware/permission.js`: es reescriu la càrrega de permisos amb `$apiManager.fetch`; s'elimina el bloc 401 duplicat que llançava `ReferenceError` (`last401ToastTime`/`nuxtApp`) i impedia la redirecció a login.
    - Càrregues que podien quedar-se en estat de càrrega: tots els `loading`/`pending` es resetejen en `finally` a la cerca (`SideBarSearch`), a `RouteEdit.findPositionPage`, a `UserEdit`, a `billing/edit`, a `billing/reports/edit` i als 6 selectors de `ManageContractsRegion`.
    - Exports (`meter-api`, `contract-api`, `sepa-remittance-api`): davant d'un 401 es crida `$apiManager.handleUnauthorized` per netejar la sessió i redirigir, en lloc de deixar l'error sol.
    - Sondes periòdiques de `config_aca` (`index.vue`/`index_prev.vue`): en rebre un 401 s'aturen l'`interval` i la `runningFill` per no continuar disparant peticions amb la sessió caducada.
#### SERVICE (reducció de crides i re-renders en desar un tall/detall — `components/organisms/SupplyCutRegion.vue`, `components/molecules/SupplyCutDetail.vue`, `components/molecules/ChangeStatus.vue`)
    - Cada acció de desar del tall (canvi de causa, canvi d'estat, resolució de revisió, finalitzar/cancel·lar o treure un punt de subministrament) disparava una cascada de peticions i re-muntatges que podia arribar a 3 crides a l'endpoint de detall (`213/`), 5 a `general-note/?is_seen=false` i un pic de ~35 MB de transferència.
    - El detall ja no es torna a baixar de zero després de desar: la resposta del PUT serveix per actualitzar l'estat local de `SupplyCutRegion` (i per al canvi d'estat, `ChangeStatus` emet la resposta via l'event `changed`). Es manté la recàrrega lleugera de l'ordre de treball (`getOrder()`), el `notifyChanged()` (re-munt del `SupplyPointDetail` + refresc de la llista pare) i el `closeSubRegion()`.
    - `SupplyCutDetail.vue` accepta una prop nova `data` i es renderitza a partir d'ella sense fer cap petició quan el pare ja en té; perd el watch per clau (`props.key`) que disparava una recàrrega redundant, i el watch d'`id` només recarrega quan no hi ha `data`.
    - `ChangeStatus.vue`: el watch de `props.status` ja no torna a demanar els estats (`fetchStatuses`) en cada canvi, només actualitza la selecció.
#### GENERAL (deduplicació de `general-note/?is_seen=false` — `layouts/default.vue`, `components/molecules/Breadcrumb.vue`, `plugins/api/notification/general-note-api.js`)
    - `layouts/default.vue` feia dues crides a la mateixa URL (`?is_seen=false`) en cada comprovació (una per a les notes no vistes i una altra per al recompte de pendents); ara una sola crida alimenta tots dos.
    - `Breadcrumb.vue` demanava les notes generals a l'arrencada i a cada canvi de ruta; ara el recompte de notes generals el gestiona únicament el layout (propietari únic de la sonda periòdica). El breadcrumb conserva les actualitzacions de notificacions i documents diaris.
    - `general-note-api.js`: `getUnseen` i `checkNewGeneralNotes` dedupeixen les crides concurrents en vol (`in-flight`), compartint una sola petició.

## [24-09-2026]

### FEAT
#### SERVICE (`plugins/api/service/supply-point-api.js` — filtre per zona de tarificació / placement)
    - `getList` i l'export Excel accepten `placement_id` (array d'ids) i l'envien com a `&placement_id=...`, el mateix paràmetre que ja filtra el backend.
    - Al front el selector mostrarà el nom de la zona (`Zona 1`, `Zona 2`, etc. des de `service/supply-point-placement`) i enviarà l'`id` de cada placement.
#### SERVICE (`pages/service/supplypoints/index.vue` — columnes configurables al llistat + columna de zona)
    - El llistat de punts de subministrament passa al mateix patró de `DataTable` que els contractes (`table-key="supply-points"`): l'usuari pot mostrar/amagar, reordenar i redimensionar columnes; la preferència es guarda a `localStorage` per usuari (`useTableColumns`).
    - Nova columna "Zona" (`placement_name`) al final; el text ve del backend. Requereix el camp `placement_name` al `SupplyPointListSerializer` del backend.
    - La icona de frau es mou dins de la columna d'identificació (com als contractes) per evitar l'espai buit entre identificació i adreça.
    - La regió lateral usa `z-20` (igual que contractes) perquè el botó de columnes visibles no quedi per sobre quan s'obre un punt de subministrament.

#### COMMUNICATION (`CommunicationProcessCreation.vue`, `CommunicationProcessCreationData.vue`, `CommunicationProcessCreationMessage.vue` — preseleccions al wizard de nou procés de comunicació segons el pas 1)
    - El wizard dedueix el context de la comunicació del que s'ha triat al pas 1: una facturació fixada (`billing_id` o Gestions → facturació) o la cerca per tipus «Facturació» donen `billing`; una gestió d'impagats (`claim_request_id`) dona `claim`. Aquest token es passa als passos 3 i 4.
    - **Pas 3:** el «Tipus d'ús» es preselecciona pel token del context (p. ex. Facturació) i, si no n'hi ha cap que coincideixi, pel marcat com a `is_default` (Altres). El «Remitent» passa al correu de l'empresa configurat per a aquell tipus d'ús, si n'hi ha, també quan l'usuari canvia el tipus d'ús a mà.
    - Si es canvia el context al pas 1 després d'haver passat pel pas 3, s'oblida el tipus d'ús desat perquè torni a preseleccionar el del nou context.
    - **Pas 4:** l'«Origen» es preselecciona pel mateix token (Facturació / Gestió d'impagats). La «Plantilla» només es tria sola si l'origen en té exactament una (també en canviar l'origen a mà); si n'hi ha més, no s'endevina. En triar plantilla es marca per defecte «Predefinit al contracte», sempre que totes les persones tinguin contractes (si no, l'opció està deshabilitada i es manté el comportament anterior: si la plantilla té un sol canal, es marca aquest).
    - Tornant enrere als passos 3 i 4 es respecten les dades ja desades i no es tornen a aplicar les preseleccions.
    - Per a les cerques per contracte no es preselecciona res: filtrar per contracte no vol dir que la comunicació sigui de contractes.
    - **No s'ha provat en un navegador**; els components compilen.

#### COMMUNICATION (`CommunicationProcessCreationMessage.vue`, `CommunicationProcessCreationFinalMessage.vue`, `locales/*` — es treu l'opció «Comunicació digital» del pas 4)
    - L'opció virtual `digital` («Comunicació digital (Adreça electrònica)») es confonia amb el canal real «Adreça electrònica» de la plantilla. A la pràctica forçava el correu a tothom ignorant la preferència del contracte, i a les persones sense correu els creava la comunicació de correu amb l'adreça buida, mentre que «Adreça electrònica» només envia a qui en té i no té el contracte en paper.
    - Al pas 4 queden «Predefinit al contracte» i els canals reals de la plantilla. Es treuen també les branques `'digital'` del pas 5 i la clau `customer_service_block.digital_comm` dels quatre idiomes (la de `contract_block.digital_comm` de les fitxes de contracte no es toca).
    - El backend encara accepta `digital` (`message_service.py`, `communication_serializer.py`) perquè els processos existents continuïn funcionant; es pot treure més endavant.

### FIX
#### SERVICE (`pages/service/supplypoints/index.vue` — ordenar per zona no feia res)
    - El `sortKey` de la columna Zona enviava `placement__name`, que el backend no té a `ordering_fields`. Es canvia a `placement_name`, el mateix alias anotat que ja fan servir tipus, estat i la resta de columnes relacionades. Requereix el fix corresponent al backend.

#### COMMUNICATION (`CommunicationProcessCreationData.vue` — el tipus d'ús i l'empresa del pas 3 no es preseleccionaven mai)
    - `loadData()` sobreescrivia el tipus d'ús preseleccionat amb `props.data.use_type || null` i l'empresa amb `... || null`: com que en entrar al pas 3 per primer cop no hi ha res desat, el tipus d'ús per defecte i l'empresa única que s'havien triat just abans quedaven buits. Ara només se sobreescriuen si hi ha un valor desat.
    - El `map` dels tipus d'ús no copiava `is_default`, de manera que la cerca del tipus per defecte no trobava mai res.
    - `changeCompanyConf()` feia servir `selectedCommunicationUseType`, una variable que no existeix: hauria petat tan bon punt hi hagués un tipus d'ús seleccionat. Ara fa servir `selectedUseType`.

## [21-09-2026]

### FEAT
#### SERVICE (`SupplyCutDetail.vue`, `SupplyCutMiniDetail.vue`, `SupplyCutEdit.vue`, `pages/service/supply-cut/index.vue` — distinció clara entre dates previstes i reals als talls, ara amb hora)
    - Els quatre camps de dates de la llista i de les fitxes de tall es mostraven amb `common.start_date` / `common.end_date`, amb un sufix «(Exec)» per a les reals. Ara tenen noms propis i traduïts als quatre idiomes (`service_block.cut_date_expected_start`, `cut_date_expected_end`, `cut_date_real_start`, `cut_date_real_end`): «Data prevista (inici/fi)» i «Data real (inici/fi)». S'apliquen a la llista, als detalls, a l'editor i a la matriu i l'exportació XLSX del detall miniaturitzat.
    - La llista mostra les dates amb `formatDateTime` en lloc de `formatDate`, perquè a un tall l'hora informa (el detall ja les pintava amb hora). Les columnes s'amplien perquè hi càpiga el text nou (155 px).

### FIX
#### BILLING (`pages/billing/reports/add.vue`, `pages/billing/reports/index.vue` — la cua d'informes reconeix l'estat `warning`)
    - El backend pot tancar una tasca amb `warning` (informe generat amb avisos). El front només tractava `completed` i `failed`, així que aquestes tasques no entraven a «finalitzades», el sondeig no s'aturava i el distintiu les pintava com a error.
    - `warning` passa a ser un estat acabat: s'atura el polling, es mostra un toast d'avís amb el `error_message` i a la cua surt un distintiu ambre (`common.warning`) amb el missatge en itàlica, separat del vermell de `failed`.

#### ORDER (`OrderRegion.vue`, `OrderDetail.vue`, `OrderEdit.vue` — la fitxa d'ordre petava si `externalGot` no era un string)
    - `config.public.externalGot.toLowerCase()` petava al setup amb `is not a function`: Nuxt pot exposar `NUXT_EXTERNAL_GOT` com a booleà, no com a string. Es veia a la instal·lació E.
    - Es converteix amb `String(...)` abans de comparar, el mateix patró que ja feia `pages/settings/index.vue`.

#### DATA-TABLE (`components/organisms/DataTable.vue` — el template gestionat amb tracks `minmax()` no col·lapsava la graella)
    - El `grid-template` heretat ve separat per comes i es tornava espais amb un simple `split(',')`. Un template gestionat (`isColumnMode`) porta tracks del tipus `minmax(40px, 1fr)`, que contenen comes pròpies: separar-les invalidava el valor i la graella sencera queia a una sola columna.
    - `splitGridTemplate()` separa només per les comes de primer nivell —esquivant les que queden dins de parèntesis— i deixa els tracks `minmax()` intactes.

#### AUTH (`plugins/api/api-manager.js` — un 401 neteja la sessió i torna al login sense deixar pantalles mig carregades)
    - Els tres punts de sortida (`fetch`, poll de `task-progress` i `my-permissions`) tenien cadascun la seva redirecció a `/auth/login`, sense netejar la sessió. Si el middleware d'autenticació seguia veient el token com a vàlid, la pàgina es quedava en estat de càrrega.
    - Tot es unifica en un únic `handleUnauthorized`: mostra un toast (limitat a un cada 2 s), neteja `auth_token`, `user_username` i `exploitation` del `localStorage` i fa `nuxtApp.$router.push('/auth/login')`, el mateix camí que ja feia `NavSidebar.logout()`. A `fetch` es conserva l'excepció de les rutes GOT, que es queden al seu propi login.

#### DATE-UTILS (`utils/date.ts`, `SupplyCutDetail.vue` — les dates buides o invàlides ja no surten com a 01/01/1970)
    - `formatDate`, `formatDateTime`, `formatTime` i `formatDateVerbose` rebien un `string` i cridaven `new Date(...)` sense mirar-lo: quan el valor era `null`, `undefined` o una cadena buida sortien dates absurdes (com el `01/01/1970` del detall del tall quan no hi havia data prevista), i amb una cadena malformada un `Invalid Date` que no es traduïa.
    - Els quatre formatejadors accepten ara també `null`/`undefined` i tornen `-` per a valors buits o no parsejables; se n'aplica el mateix tractament a les dates prevista i real d'inici del detall del tall.

## [18-09-2026]

### FEAT
#### BILLING (`InvoiceView.vue` — veure i descarregar el PDF sempre disponibles a la fitxa de la factura)
    - Els dos botons rodons flotants només sortien quan la factura ja tenia el document definitiu generat (`invoice_file`). Si no en tenia —pre-factures, pressupostos, o qualsevol factura sense PDF generat— el contenidor es pintava buit, de 0×0, i des de fora semblava que els botons haguessin desaparegut.
    - Ara **hi són sempre**: un obre el PDF en una **pestanya nova** i l'altre el **descarrega**. Quan no hi ha document definitiu, totes dues accions treballen amb el **PDF provisional**, que el backend genera sota demanda a `temporary-pdf/{id}/` per a qualsevol factura sense mirar-ne l'estat. El títol del primer botó ho diu, perquè se sàpiga què s'està obrint.
    - Les tres funcions que hi havia (`invoicePDF`, `showDocument`, `downloadDocument`) es refonen en una de sola amb la cascada «document definitiu, si no provisional». Cada botó té el seu indicador de càrrega: abans en compartien un de sol que en algunes branques no es reiniciava mai i deixava els dos botons inservibles.
    - El `URL.revokeObjectURL` de la pestanya nova ja no s'executa als 250 ms —cosa que la podia deixar en blanc— sinó quan l'usuari la tanca.
    - **No s'ha provat en un navegador**; el component compila i les icones arriben al bundle.

#### SETTINGS
    - S'ha afegit un nou apartat per configurar els codis comptables separats per tipus factura (mira tota la factura), conceptes (mira les línies i productes de la factura per calcular valors) i cobrament (mira els moviments de pagament)

### FIX
#### BILLING (`pages/billing/budgets/index.vue` — el botó de nou pressupost sortia sense icona)
    - Demanava `fa-solid:file-budget`, i hi havia dos problemes: **`file-budget` no existeix** a Font Awesome (ni a la 5 ni a la 6), i el prefix `fa-solid` (Font Awesome 5) no és a les col·leccions que empaqueta `nuxt.config.ts`, de manera que s'hauria d'haver baixat per xarxa.
    - Passa a `fa6-solid:file-circle-plus`, que existeix, encaixa amb l'acció i ve de la col·lecció ja empaquetada.
    - Queda pendent: hi ha una cinquantena d'usos més del prefix `fa-solid:` repartits pel projecte. Aquests noms sí que existeixen i es veuen, però es baixen sota demanda en comptes de venir del paquet local.

## [17-09-2026]

### FEAT
#### CONTRACT (`PersonEdit.vue`, `utils/dni.js` — avís (no bloquejant) si el DNI introduït no és vàlid)
    - Nou `utils/dni.js` amb `isValidDNI()`: valida el format (8 dígits + lletra) i la lletra de control (mòdul 23 sobre la taula `TRWAGMYFPDXBNJZSQVHLCKE`), sense llançar cap excepció.
    - Quan el tipus de document seleccionat és DNI (`identification_type.token === 'dni'`) i el camp d'identificador no és vàlid, apareix un avís sota l'input (No impedeix guardar en cap cas): la funció `isValid()` que bloqueja el botó de desar no s'ha tocat, i el DNI queda igualment desat encara que sigui invàlid.
    - L'avís no surt si el tipus de document no és DNI o si el camp encara està buit.

#### CONTRACT (`change-tenant.vue`, locales — canviar llogater, titular i propietari des de la mateixa pantalla)
    - El **canvi de llogater** d'un contracte només deixava tocar el llogater. Si a més calia treure el propietari perquè no sortís a la factura, o canviar el titular, s'havia de passar per la subrogació (que mou pagament, adreces i contactes) o per una sol·licitud de canvi de nom. Ara el primer pas de la pantalla presenta els **tres rols** —titular, propietari i llogater— amb el mateix aspecte que el pas 2 de l'edició de sol·licituds (`ContractRequestPersons.vue`): targeta verda per persona, llapis per canviar-la, paperera per desvincular els opcionals, i asterisc rosa al titular, que continua sent obligatori.
    - Els canvis es **preparen, no es desen a l'instant**. Cada rol tocat queda marcat amb el distintiu «Modificat», mostra a sota qui hi havia abans i té un enllaç per desfer-ho. Això canvia la paperera del llogater, que abans desvinculava i desava de cop: ara tot es desa junt al botó final del segon pas, un cop revisades adreces i pagament.
    - El pas 2 (`ContractRequestAddressPayment`) rep el contracte amb les persones ja triades, de manera que ofereix les adreces, comptes i contactes de les noves. Com a `previous-tenant` hi va **la persona que marxa** —el llogater si ha canviat i, si no, el titular antic—, que és la que el component fa servir per netejar IBAN, mandat, adreces i contactes que només eren seus.
    - En desar, el titular i el propietari viatgen **dins del mateix PUT del contracte** que ja hi havia (`holder_id` / `owner_id`, només els rols que canvien), i tot seguit es fa el `ContractTenantChange` amb la seva documentació, que continua sent exclusiva del canvi de llogater i es descarta si el canvi es desfà. Si el PUT falla, la pantalla **s'atura i mostra el missatge del backend** en comptes d'empassar-se l'error i tirar endavant amb el canvi de llogater, com feia abans; el desat del pagament també tolera ara els contractes sense `payment`.
    - El títol de la pantalla i l'opció del menú continuen dient **«Canvi de llogater»**; la molla de pa, que fins ara ensenyava el segment de la ruta sense traduir («Change Tenant»), també, amb la clau nova `breadcrumb.change_tenant` als quatre idiomes.
    - Va acompanyat del canvi de backend del mateix dia (`holder_id` / `owner_id` a `ContractSerializer`, que reassignen la persona del rol amb traça a l'historial i **sense** tocar pagament ni adreces: la subrogació formal continua sent l'única que ho fa). **No s'ha provat en un navegador**: el component compila amb `@vue/compiler-sfc` i els quatre fitxers d'idioma parsegen correctament.

### FIX
#### CONTRACT (`BankDetail.vue` — el nom del titular es mostra en lloc del DNI)
    - A la fitxa de contracte ara es prioritza mostrar el titular del compte bancari, no sempre es veia bé.

#### SERVICE / BILLING (`StatusesNav.vue`, `AddBonification.vue`, `ContractRequestSummary.vue`, `NavSidebar.vue`, `layouts/got.vue`, `pages/got/login.vue` — errors preexistents que Vite 8 destapa)
    - **Quatre rutes a `public/` mal escrites.** A Nuxt, `public/` se serveix des de l'arrel. Tres apuntaven a `/public/favicon-32x32.png` i **donaven 404 al navegador** (icona trencada a la barra lateral i al layout GOT); la quarta, sense barra inicial, Vite la interpretava com un import i petava el build. Totes a `/favicon-32x32.png`.
    - **Dues expressions regulars que Tailwind confonia amb classes CSS.** `replace(/[-:.TZ]/g, '')` i `/[-:T.]/g` les escanejava com a propietats arbitràries i generava CSS invàlid (`.\[-\:\.TZ\]{-:.TZ}`). Eren els dos avisos d'esbuild que s'arrossegaven de sempre, i amb lightningcss passen a ser error fatal. Substituïdes per `/\D/g`, que sobre un ISO string dona exactament el mateix resultat.
    - **`.clip-right::after.opacity-50`** a `StatusesNav.vue`: una classe no pot anar darrere d'un pseudoelement, i el navegador descartava la regla sencera, de manera que **mai no ha fet res**. Esborrada. No calia cap alternativa: `opacity` s'aplica a l'element i als seus pseudoelements, així que n'hi ha prou amb posar `opacity-50` al `<span>`.

#### COMMON (`plugins/npm/vue-datepicker.js` — el calendari sortia tot en anglès)
    - Al plugin no se li passava mai res i `@vuepic/vue-datepicker` té els textos en anglès per defecte: `locale` val `'en-Us'` (mesos i dies) i els botons són cadenes a part que el locale **no** tradueix (`selectText: 'Select'`, `cancelText: 'Cancel'`).
    - El component global `Datepicker` passa a ser un embolcall que omple `locale`, `selectText` (`common.select`) i `cancelText` (`common.cancel`) amb l'idioma actiu d'i18n. Es llegeix dins del render, de manera que no depèn de l'ordre de càrrega dels plugins i **es refà en calent** en canviar d'idioma. Qui necessiti altres valors els pot seguir passant per prop.
    - Afecta els informes (`reports/add`, `GenericReportForm`, `RatesReportForm`). `components/atoms/DatePicker.vue` ja passava el locale a mà i usa `auto-apply`, que amaga els botons. Queden en anglès el `nowButtonLabel` (el `now-button` no s'usa enlloc) i les `ariaLabels`.

#### BILLING (`ChangeStatus.vue`, `AddInvoiceBudget.vue`, `useFinalInvoiceTokens.js` — la paperera de factura torna a deixar triar, però només el que toca)
    - El panell d'anul·lar factura de la sol·licitud ensenyava l'estat com un badge fix («Abonada») en comptes del desplegable, de manera que no es podia decidir entre **abonar** i **anul·lar**. El camí alternatiu (quan el token de ConfigProject no arribava) era encara pitjor: oferia **els dotze** estats de factura, Pagada i Pre-factura incloses.
    - Ara el desplegable s'acota als dos únics estats d'eliminació —**Abonada (-6)** i **Anul·lada (-7)**— i ve amb l'opció bona ja triada segons el cas: si la factura ha cobrat alguna cosa, **només** s'ofereix abonar-la; si no ha cobrat res (Confirmada, Enviada…), es pot **anul·lar o abonar**, amb Anul·lada per defecte. El criteri és el mateix que el backend aplica a `PUT /billing/invoice/{id}/return/` (`payments.filter(movements__gt=0)`), aproximat al front amb `left_to_pay` vs `total_final` del detall de la factura, que es demana en obrir el panell.
    - Atenció, aquest botó **no** passa per `return/`: fa un canvi d'estat pelat, sense generar l'abonament ni retornar pagaments. Per això s'hi tanca la porta a estampar «Anul·lada» a una factura amb cobraments. El flux complet continua sent el de la fitxa de la factura (`InvoiceRegionModals.vue`).
    - El motiu obligatori d'ahir es manté i ara va lligat als dos estats: `reasonToken` de `ChangeStatus` accepta una llista de tokens. `ChangeStatus` guanya també `allowedTokens` (filtra i ordena les opcions del desplegable; la primera és la preseleccionada) i `useFinalInvoiceTokens` exposa `paidStatusToken`.
    - De passada, `statusSelectedToken` es resol en carregar el component: el `watch` de `statusSelected` saltava abans que arribessin els estats i el token quedava indefinit fins al primer canvi, cosa que amagava el camp de motiu.
    - **No s'ha provat en un navegador**; els components compilen. En instal·lacions sense `invoice_status_dropped_token` configurat (no hi és a les dades base, l'afegeix la migració `0307`), el desplegable queda només amb Abonada.

#### CONTRACT (`ContractRequestSetup.vue`, `ContractRequestEdit.vue`, `data-change.vue`, locales — no es pot desar un contracte amb 0 persones a l'habitatge)
    - El camp *Persones a l'habitatge* era un `<input type="number">` sense cap límit ni validació ni al canvi de dades del contracte ni al primer pas de la sol·licitud. Un 0 desat des d'aquí va aturar tot un lot de facturació a la instal·lació D (`float division by zero`): el càlcul del consum responsable divideix pel nombre de persones. El backend del mateix dia corregeix la divisió i rebutja el valor; això és la meitat de frontal, perquè l'usuari ho vegi abans d'enviar-ho i sàpiga què fer-ne.
    - Els dos camps porten ara `min="1"` i, amb 0 o negatiu, es marquen amb la classe **`invalid`** del projecte (vora vermella, la mateixa que fan servir `AddOrderType`, `AddCompany` i companyia) més un `ring` vermell, l'etiqueta del camp també en vermell i un bloc d'avís amb icona i fons vermell clar amb el motiu i la sortida: **«El nombre de persones a l'habitatge ha de ser com a mínim 1. Si cal reflectir un cas especial, afegiu-ho com a variable del contracte.»** La clau `contract_block.total_persons_min` és als quatre idiomes.
    - **I no deixa desar**: al canvi de dades el botó de desar queda deshabilitat i `save()` talla amb un toast si s'hi arriba igualment; a la sol·licitud, `ContractRequestSetup` emet `total_persons_valid` i `ContractRequestEdit` bloqueja tant el pas següent (`nextStep`) com el desat del pas 0 (`saveStep`), amb el mateix toast i seguint el patró que ja hi havia per a `company_required`. A la sol·licitud només s'aplica quan el tipus té `has_persons`.
    - **No s'ha provat en un navegador**: els tres components compilen amb `@vue/compiler-sfc` i els quatre fitxers d'idioma parsegen correctament.

### CHORE
#### BUILD (`package.json`, `.nvmrc`, `config/deploy.rb` — el deploy demana Node 22.19+)
    - El primer desplegament a l'entorn de test va petar amb `TypeError: trustedFunctions.difference is not a function`. Ve de `postcss-merge-longhand` (per `nuxt` -> `@nuxt/vite-builder` -> `cssnano`), que fa servir `Set.prototype.difference()`: un mètode que **no existeix abans de Node 22**. El paquet ho declara (`engines: ^22.11.0 || ^24.11.0`) però `npm install` només avisa, no atura, i el build moria molt més tard amb un error que no diu res del problema real.
    - El `Dockerfile` ja s'havia pujat a `node:22`, però **el desplegament no passa per Docker**: va per mina i pm2 contra el Node que hi hagi instal·lat al servidor. Calia declarar-ho i comprovar-ho.
    - `package.json` declara `engines: ^22.19.0 || ^24.11.0 || >=26.0.0` (el rang que demana Nuxt 4.5.2, més estricte que el de cssnano) i s'afegeix un `.nvmrc`.
    - `config/deploy.rb` comprova la versió de Node **abans** d'instal·lar res i atura el desplegament amb un missatge clar si no serveix, en comptes de fallar a mig build. També hi afegeix `NODE_OPTIONS=--max-old-space-size=4096`, perquè amb Vite 7+ el build passa dels ~2,2 GB de heap que Node dona per defecte.
    - **Cal actualitzar el Node dels servidors de desplegament**, tant per compilar com per executar: `.output/server/index.mjs` també s'executa amb el Node del sistema via pm2.

#### BUILD (`package.json`, `nuxt.config.ts`, `Dockerfile`, `i18n/` — Nuxt 3.15.1 -> 4.5.2 i neteja de dependències)
    - **Nuxt 3.15.1 -> 4.5.2.** Tanca tots els avisos de seguretat del framework (DoS per enverinament de cache, bypass de middleware de rutes, XSS reflectit a `navigateTo()`). Per sota: Vite 6 -> 8, unhead 1 -> 2, vue-router 4.5 -> 4.6. **No ha calgut moure els 944 fitxers a `app/`**: Nuxt 4 detecta la disposició antiga i la respecta. `@pinia/nuxt`, `@nuxt/icon`, `@nuxtjs/tailwindcss` i `@vesp/nuxt-fontawesome` funcionen sense tocar-los, i el `tsconfig.json` tampoc s'ha hagut de canviar.
    - **`@nuxtjs/i18n` 8.5.6 -> 10.6.0** (vue-i18n 9 -> 11). Obligat: Nuxt 3.21+ porta unhead v2 i la v8 del mòdul crida `getActiveHead()`, que ja no s'exporta. Cap ús de les API que vue-i18n 11 elimina (`$tc`, `tc`, `$te`, `tm`, mode legacy).
    - **`i18n.config.ts` i `locales/` s'han mogut dins d'`i18n/`.** La v10 fa obligatori el `restructureDir` i busca la configuració a `i18n/`; en no trobar-la **no avisa de res**, arrenca sense cap missatge i tota l'aplicació mostra les claus crues (`common.save`, `billing_block.…`) en comptes dels textos. Fora l'opció `lazy`, que la v10 ha eliminat, i afegit `bundle.optimizeTranslationDirective: false`, que el mòdul mateix recomana desactivar i que a més disparava la memòria del build.
    - **`vue3-openlayers` 11.5.0 -> 12.2.2.** A la v12 el component `OlSourceOsm` es diu `OlSourceOSM`: amb el nom antic la capa de teules no es muntava i el mapa sortia en blanc amb només el marcador. Corregit a `MapRegion.vue`. La resta de components del fitxer s'han verificat un per un contra els que registra la v12.
    - **Fora 42 dependències de producció que no s'usaven**: `@tinymce/tinymce-vue`, `@tiptap/*` (27), `@tiptap/react`, `@vueup/vue-quill`, `dompurify`, `html2pdf.js`, `jsdom`, `tinymce`, `vue-datepicker-next`, `vue-meta`, `vue-tinymce`, `@nuxt/ui`, `@nuxtjs/axios`, `@nuxtjs/fontawesome`, `trix`, `axios`, `nuxt-tiptap-editor`, `@samk-dev/nuxt-vcalendar`. El manifest passa de 69 a 26 dependències.
    - **Tot el tiptap era codi mort.** A `invoice-templates/edit/[id].vue` l'editor tiptap estava comentat i el que s'usa és `InvoiceTemplateHTMLModify`. Esborrats `InvoiceTemplateModify.vue`, `TiptapToolbar.vue`, `TiptapTableDialog.vue`, `TipTapEditorHelper.vue` i les 8 extensions de `plugins/tiptap-extensions/`.
    - **Tres imports no declarats** que entraven de gorra per paquets que s'han tret: `react` a `DragHandleExtension.js` (sense fer-se servir dins del fitxer), `@vueuse/core` a set components (`useDebounceFn`, ara declarat com a dependència) i `axios` a `reports/add.vue` (importat i mai cridat).
    - `Dockerfile`: `node:20` -> `node:22` (Nuxt 4 demana `^22.19.0` i Node 20 és fora de manteniment) i `NODE_OPTIONS=--max-old-space-size=4096` al pas de construcció, perquè amb Vite 7+ el build passa dels ~2,2 GB de heap que Node dona per defecte i moria amb `heap out of memory`.
    - **`npm audit`: de 115 paquets vulnerables i 276 avisos a 2 i 3.** Les 7 crítiques desapareixen, inclosa l'execució de comandes arbitràries a la màquina del desenvolupador via l'RPC de Nuxt DevTools. Queden dues altes d'`xlsx` (totes dues al parser, i `utils/xlsx-export.ts` només escriu) i una baixa de `quill`; cap de les tres té correcció disponible.
    - **No s'ha provat en un navegador**: `npm run build` i el servidor de desenvolupament passen, i s'ha verificat que els quatre idiomes arriben al bundle.

## [16-09-2026]

### FIX
#### CONTRACT (`ContractTerminationEdit.vue` — fora el commutador «Facturar lectura de tall» de les baixes de contracte)
    - Al primer pas de l'alta/edició d'una **baixa de contracte** hi havia un commutador *Facturar lectura de tall* que es desava al camp `bill_cut_reading` de la baixa i que **no llegia ningú en aquest flux**. Quan es factura des de la baixa (`ContractTerminationRegion.vue` -> `AddInvoiceBudget.vue`), l'entitat és `contract_termination_request` i el camp s'envia sempre a `false` (`bill_cut_reading: props.entity === 'contract_request' ? ... : false`), amb `bill_termination_requester` a cert: la lectura de tall es factura al titular que es dona de baixa, estigués el commutador com estigués.
    - El camp només té sentit com a **disjuntiva** —facturar la lectura de tall al titular de la baixa *o* passar el consum al nou contracte d'alta— i aquesta disjuntiva només existeix quan hi ha una alta simultània. Per això a `ContractRequestTermination.vue` el bloc de tria està darrere de `v-if="isChangeOfNameRequest"`, i allà sí que decideix si la lectura de tall es reaprofita com a lectura inicial del nou contracte. En una baixa aïllada no hi ha cap contracte nou on passar el consum.
    - A més, el commutador podia **desfer la decisió presa al canvi de nom**: una baixa creada des d'una sol·licitud d'alta es pot obrir després a `/contract/contract-terminations/edit/:id`, i el desat dels passos 1 i 2 hi reenviava `bill_cut_reading` amb el valor del commutador, que arrencava a `false`.
    - Es treuen el commutador, el `ref` i les dues assignacions de càrrega, i el camp deixa d'anar al `payload` del desat. **El camp del backend es manté**: el continua omplint el flux d'alta (`ContractRequestTermination.vue`, `ContractRequestSummary.vue`) i el continua llegint la generació de factures/pressupostos; el que deixa de ser és editable des d'on no significava res.
    - **No s'ha provat en un navegador**: només s'han tret referències a una variable que no tenia cap altre consumidor dins el component.

#### SERVICE (`InputImage.vue`, `ExploitationDetail.vue`, `CompanyDetail.vue`, `LogoField.vue` — canviar el logo semblava que no es desés i les fitxes no el mostraven)
    - Al selector d'imatge, esborrar el logo amb la paperera i tornar a triar **el mateix fitxer** no feia res: el valor de l'`<input type="file">` no es buidava mai, així que el navegador no disparava cap event, el component no emetia `update` i el formulari desava sense logo tot i que semblava que se n'hagués triat un. Ara el valor es buida després de llegir el fitxer i en esborrar la imatge, i s'escolta `@change` en comptes de `@input`.
    - L'`<input>` viu dins del `div` que obre el selector en fer-hi clic, de manera que el clic sintètic de `fileInput.click()` tornava a pujar fins al `div` i re-entrava al mateix gestor; ara el clic de l'input s'atura amb `@click.stop`. El botó de la paperera porta `type="button"` i, sense imatge, el `div` ja no demana `url(null)` com a fons.
    - A les fitxes d'**explotació** i d'**empresa**, el logo es pintava amb `background-image`: si el fitxer no existia (BD copiada d'un altre entorn sense el directori `media`) quedava un requadre buit **i es perdia el camp amb el nom**, perquè el `v-else` amb el `FieldDetail` no s'activa mentre el camp `logo` tingui valor. El bloc, que estava duplicat literalment als dos components i barrejava `grid` i `flex` a la mateixa classe, passa a un àtom nou `LogoField` que pinta un `<img>` i, si la càrrega falla, cau al camp normal amb l'etiqueta i el nom.
    - Va acompanyat del canvi de backend del mateix dia: el logo d'explotació es desava sempre a `uploads/exploitation/<id>.jpg` i, com que la URL no canviava mai, el navegador servia la imatge cachejada i el canvi semblava perdut encara que el fitxer sí que s'havia escrit. **No s'ha provat en un navegador**; els components compilen i el camí del fitxer s'ha verificat contra la instal·lació local.

#### CONTRACT (`document-sign.ts`, `DocumentSignStatus.vue`, `document-signs/index.vue`, locales — els estats de la firma OTP sortien en anglès)
    - El badge d'estat pintava `status_display`, que és l'etiqueta de les `STATUS_CHOICES` de Django i arriba **sempre en anglès**: es veia «Sended» encara que la interfície estigués en català. Les claus `document_sign_status_*` ja existien, però només les feia servir el desplegable de filtres, i per això el filtre sortia traduït i el badge del costat no.
    - Faltava del tot l'estat **EXPIRED (4)**: existeix al model des del principi i el sondeig nou del backend ara el pot escriure, però no tenia clau a cap idioma, ni entrada al filtre, ni color.
    - Nou `utils/document-sign.ts` amb els codis, el mapa codi → clau i18n i els colors, en la línia de `utils/origin-type.ts`. Passa a ser l'única font de veritat dels cinc estats: el filtre del llistat es genera del mapa (ja no cal mantenir la llista a mà) i els dos badges resolen l'etiqueta pel codi numèric.
    - `document_sign_status_expired` afegit a `ca`, `es`, `en` i `gl`, i color ambre per a caducat a la caixa i la icona de `DocumentSignStatus.vue`, que només contemplava quatre estats.
    - **No s'ha provat en un navegador.**

#### SERVICE / CONTRACT (`useFinalInvoiceTokens.js`, `ConnectionRequestDetail.vue`, `ConnectionRequestPayment.vue`, `ContractRequestDetail.vue`, `ContractRequestSummary.vue`, `ContractTerminationDetail.vue`, `AddInvoiceBudget.vue` — la sol·licitud marcava com a anul·lada una factura viva)
    - A la sol·licitud d'escomesa, una factura **Pagada** sortia etiquetada com a **Factura anul·lada**. Cap dada del backend era incorrecta: la pantalla triava el document equivocat i després deduïa l'etiqueta de la tria.
    - Els abonaments hereten el `type` de la factura original (`return_invoice()`), així que arriben al front amb `type_token: 'F'` igual que les factures. Com que el llistat ve ordenat per `-issue_date, -created_at`, l'abonament era el primer de la llista i el `find()` se'l quedava com a "factura final", deixant la factura bona com a "no escollida".
    - Tampoc n'hi havia prou amb comparar contra `invoice_status_cancelled_token` (-6, Abonada): anul·lar una factura sense moviments de cobrament li estampa `invoice_status_dropped_token` (-7, Anul·lada), de manera que una factura realment anul·lada no es detectava mai com a tal.
    - Nou composable `useFinalInvoiceTokens` que centralitza el criteri: `findFinalInvoice()` retorna la primera de tipus factura que no estigui anul·lada (-7), abonada (-6) ni sigui un abonament (-2), i `isInvoice()` / `isVoidedInvoice()` toleren les tres formes en què arriba el token segons l'endpoint. Els quatre tokens es llegeixen de ConfigProject amb try/catch independent perquè un token no configurat en un client no en tombi els altres.
    - Cada fila passa a dir **què és** (Factura / Pressupost) i a mostrar **l'estat real** en un `ColorBadge` (`status_name` / `status_color`, que el backend ja enviava), en comptes de deduir "Factura anul·lada" de "no és la que he triat". Aplicat també a sol·licituds de contracte, resum de sol·licitud i baixes, que tenien el mateix patró.
    - A `AddInvoiceBudget` la mateixa comparació errònia afectava el gris de les files anul·lades i els botons d'esborrar pressupost i anul·lar factura, que sobre una factura ja anul·lada (-7) encara s'oferien. S'hi ha descomentat el badge d'estat que hi havia mort a la plantilla.
    - **No s'ha provat en un navegador**; els sis components compilen i el criteri de selecció s'ha verificat contra les dades reals de la sol·licitud d'escomesa afectada.

#### CONTRACT (`pages/contract/follow-contracts/index.vue` — les files de la taula no quadraven amb la capçalera)
    - A **Seguiment de contractes**, les dades sortien desplaçades una columna respecte de la capçalera: sota "Data" hi havia l'identificador, sota "Identificació" el punt de subministrament, i així fins al final. No passava a totes les files: les fixades (taronges) quadraven, i per això el símptoma semblava aleatori.
    - Causa: la pàgina feia servir `DataTable` en mode antic (`grid-template` + slots `#header`/`#default`) amb `pin-column`. La capçalera pinta sempre la cel·la del pin, però la fila la pintava només si el contracte estava fixat (`<span v-if="item.is_pinned">`). En una graella CSS una cel·la que no existeix no deixa el forat: totes les següents pugen una posició. Hi sumava que la capçalera i les files no compartien ni el `gap` ni el `padding` horitzontal.
    - La pàgina passa al **mode de columnes** de `DataTable` (el mateix de `contract/contracts/`, `table-key="follow-contracts"`): el pin va pel slot `#pin`, que el component renderitza sempre amb la icona condicionada a dins, i cada columna té el seu slot `cell-<clau>`, de manera que capçalera i cel·la comparteixen per definició la mateixa pista i la graella ja no es pot desincronitzar.
    - De passada hereta tot el que dona aquest mode: selector de columnes visibles, redimensionar arrossegant, reordenar, i ocultació automàtica de les menys prioritàries en pantalles estretes, tot desat per usuari a `localStorage`. L'espai sobrant es reparteix cap al punt de subministrament, el titular i l'observació; l'última porta `data-table-no-truncate` perquè ocupa dues línies (data + text) i el retall el fa l'`abbr` de dins.
    - No hi ha cap canvi de dades ni de crides: els mateixos camps, els mateixos `sortKey` i el mateix `handleSort`. **No s'ha provat en un navegador**; el component compila sense errors de plantilla.

### FEAT
#### SERVICE (`ExploitationDetail.vue` — el logo de l'explotació encapçala la seva fitxa)
    - El logo que es puja al formulari d'edició d'una explotació no es veia enlloc de l'aplicació: la fitxa de l'explotació ensenya el logo de l'**empresa**, no el seu. Ara surt a dalt de tot de la regió, per sobre del codi i el nom.
    - Si el fitxer no es pot carregar, el bloc s'amaga en comptes de deixar una imatge trencada. **No s'ha provat en un navegador.**

#### BILLING (`ChangeStatus.vue`, `AddInvoiceBudget.vue`, `InvoiceDetail.vue`, locales — motiu obligatori en anul·lar una factura)
    - En anul·lar una factura no quedava enlloc **per què** s'havia anul·lat. Passat un temps, ni el mateix historial de la factura ho aclaria: només s'hi veia el salt d'estat. Ara el panell d'anul·lació demana el motiu i no deixa desar sense omplir-lo, amb un exemple al placeholder (*anul·lada per duplicat amb la fac. F-2026/00123*).
    - No ha calgut tocar el backend. El model `Invoice` ja tenia el camp `reason` —fins ara només l'omplia el marcatge d'incobrable— i el senyal `invoice_pre_save` registra a `InvoiceLog` qualsevol camp que canviï. El motiu viatja dins el mateix PUT que canvia l'estat, així que queda desat i **registrat a l'historial de canvis de la factura** amb usuari, data i el mateix `operation_token` que el canvi d'estat, sense cap model ni endpoint nou.
    - `ChangeStatus` guanya `reasonLabel`, `reasonPlaceholder` i `reasonRequired` perquè el camp de motiu que ja hi havia es pugui reetiquetar segons el context: des d'ara diu «Motiu de l'anul·lació» al panell d'anul·lar i continua dient «Motiu» a la resta. També deixa d'enviar el `reason` quan està buit, que abans esborrava el motiu que la factura ja tingués.
    - A la fitxa de la factura el motiu ja es mostrava, però sempre etiquetat «Raó irrecuperable». Ara l'etiqueta depèn de l'estat: «Motiu de l'anul·lació» si la factura està anul·lada o abonada (via `isVoidedInvoice` de `useFinalInvoiceTokens`), i «Raó irrecuperable» en la resta de casos.
    - Textos a `ca`, `es`, `en` i `gl`. **No s'ha provat en un navegador**; els quatre fitxers de traducció s'han validat i els components compilen. Recordatori: l'únic punt viu per anul·lar una factura continua sent la paperera taronja del llistat de documents d'una sol·licitud (`AddInvoiceBudget`); l'opció del menú ⋮ de la fitxa de la factura segueix comentada a `InvoiceRegion.vue`.

#### BILLING (`pages/billing/bails/index.vue`, `bail-api.js` — filtre per estat del contracte al llistat de fiances)
    - El llistat de fiances només es podia filtrar per l'estat de la fiança, tot i que ja ensenyava l'estat del contracte com a columna. Nou desplegable de multi-selecció **Estat del contracte** (`FilterSelect`, el mateix patró que a `billing/invoice`), amb les opcions de `/contract/contract-status/`.
    - Els estats triats es propaguen a totes les crides: cerca, canvi de filtres, paginació, ordenació, refresc en tancar la fitxa de detall i **exportació XLSX** (`contract_status` com a `extraParams`). `getAll()` i `exportData()` de `$BailApiService` accepten el paràmetre nou i l'envien com a llista d'ids separada per comes.
    - El botó de reinicialitzar filtres ara buida també els estats seleccionats (de fiança i de contracte); abans només netejava el text de cerca i les dades quedaven descoordinades amb els checkboxes marcats. `pagination.isFiltered` també té en compte els filtres actius, no només el text de cerca.
    - Va acompanyat de la correcció de backend del mateix dia: `BailFilter` comparava `contract_status` contra el **token** i amb un sol valor, de manera que el filtre no feia efecte.

#### PRICING (`PriceRateEdit.vue`, `PriceRateRegionDetail.vue`, locales — marcar una tarifa com a despeses de devolució)
    - Nova casella **Despeses de devolució** al formulari de tarifes, al costat de la de fiança i amb la mateixa ajuda emergent, i distintiu al detall de la tarifa quan està marcada.
    - Marcant-la, el backend deixa configurada tota sola la tarifa que el sistema farà servir per als càrrecs per devolució de rebut i per a l'import de despeses de la carta de suspensió: fins ara calia entrar el token als ConfigProject a mà. Només hi pot haver una tarifa marcada; en marcar-ne una de nova es desmarca l'anterior, i l'ajuda emergent ho adverteix.
    - Textos a `ca`, `es`, `en` i `gl`. Va acompanyada del canvi de backend del mateix dia (`PriceRate.is_return_fee`).

### CHORE
#### BUILD (`package.json`, `package-lock.json`, `nuxt.config.ts`, `Dockerfile` — Nuxt 3.15.1 -> 3.21.11)
    - Puja de Nuxt per tancar els avisos de seguretat del framework: DoS per enverinament de cache amb renderitzat de payload, bypass de middleware de rutes per diferència de majúscules entre `vue-router` i el router de rutes, i XSS reflectit a `navigateTo()`. Amb `ssr: false` bona part d'aquests camins no s'executen aquí, però `nuxt` desapareix del tot de la llista de `npm audit`.
    - **`@nuxtjs/i18n` ha hagut de passar de la 8.5.6 a la 9.5.6.** Nuxt 3.21 porta unhead v2 i la v8 del mòdul crida `getActiveHead()`, que ja no s'exporta: el build petava amb un `RollupError`. La 9.5.6 és la que es desenvolupa contra Nuxt 3.17+; la 10.x ja apunta a Nuxt 4. Arrossega `vue-i18n` de la 9.14.2 a la 10.0.8. La configuració d'aquí no se'n ressent: els missatges vénen inline d'`i18n.config.ts` amb `legacy: false`, i el plugin `i18n-init.client.js` continua fent `$i18n.locale.value`.
    - Nou `i18n.bundle.optimizeTranslationDirective: false`. El mòdul l'activa per defecte i ell mateix avisa que el desactivis perquè causa problemes i queda obsolet a la v10; a sobre dispara la memòria del build.
    - **El build ara demana més heap del que Node dona per defecte.** Amb 3.15 no s'hi arribava; amb 3.21 (Vite 6 -> 7) el build mor amb `heap out of memory` als ~2,2 GB. El `Dockerfile` fixa `NODE_OPTIONS=--max-old-space-size=4096` a l'etapa de construcció. Qui compili en local i topi amb l'error, el mateix.
    - `Dockerfile` passa de `node:20-bookworm-slim` a `node:22`: Nuxt 3.21 demana `^20.19.0 || >=22.12.0`, i Node 20 ja és fora de manteniment.
    - `npm audit` baixa de 110 a **71** paquets vulnerables (271 -> **152** avisos a l'estil Dependabot). Les crítiques passen de 7 a 3: se'n van `@nuxt/devtools`, `simple-git`, `shell-quote` i `tar`, és a dir **l'execució de comandes arbitràries a la màquina del desenvolupador via l'RPC de DevTools**, que era l'única crítica amb un camí d'atac realista. Queden `form-data` (via axios), `jspdf` (via `vue3-openlayers`) i `koa` (via `tailwind-config-viewer`).
    - `npm run build` passa, amb els mateixos dos avisos de CSS que ja hi havia i la mateixa mida de `.output/public` (12M). El servidor de dev arrenca net i serveix 200, sense cap avís d'i18n. **No s'ha provat en un navegador**: cal repassar com a mínim el canvi d'idioma, el mapa, l'editor tiptap de plantilles de factura i el calendari.

#### BUILD (`package.json`, `package-lock.json`, `DragHandleExtension.js` — fora deu dependències de producció que no s'usen)
    - Cap d'aquests deu paquets s'importa enlloc del codi: `@tinymce/tinymce-vue`, `@tiptap/react`, `@vueup/vue-quill`, `dompurify`, `html2pdf.js`, `jsdom`, `tinymce`, `vue-datepicker-next`, `vue-meta` i `vue-tinymce`. L'editor real és tiptap (quill encara s'usa en quatre fitxers), el datepicker actiu és `@vuepic/vue-datepicker`, i `vue-meta` és de l'època de Nuxt 2.
    - `DragHandleExtension.js` importava `React`, `useEffect` i `useRef` sense fer-los servir enlloc del fitxer: còpia-enganxa d'un exemple de tiptap per a React. Amb `@tiptap/react` fora, `react` ja no es resolia i el build petava. Treta la línia, que a més feia entrar React al bundle d'una aplicació Vue. El fitxer es continua fent servir des d'`InvoiceTemplateModify.vue`.
    - `npm audit` passa de 115 a 110 paquets vulnerables (276 -> 271 avisos a l'estil Dependabot): se'n van les tres altes de `tinymce` i l'alta d'`html2pdf.js`. **Les set crítiques no es mouen**: `jspdf` continua entrant per `vue3-openlayers`, que sí que fem servir a `MapRegion.vue`, i totes les altres són de la cadena d'eines de desenvolupament (`@nuxt/devtools`, `simple-git`, `shell-quote`, `tar`, `koa`, `form-data`).
    - Avís per a qui faci pull: cal un `npm install`, o `node_modules` queda desquadrat amb el manifest.
    - Queda pendent: `trix`, `@nuxtjs/axios`, `@nuxtjs/fontawesome` i `@nuxt/ui` tampoc s'usen. `dompurify` passa a estar disponible només per coincidència (el porten `trix` i `jspdf`), de manera que un import nou funcionaria fins que es tregui `trix`.
    - `npm run build` passa, amb els mateixos dos avisos de CSS que ja hi havia i la mateixa mida de bundle. **No s'ha provat en un navegador**; l'editor de plantilles de factura no s'ha obert.

## [15-09-2026]

### CHORE
#### SERVICE (`SupplyCutRegion.vue`, `SupplyCutDetail.vue`, `ClusterEdit.vue`, `ClusterRegion.vue` — estandardització de comentaris a l'anglès i neteja)
    - Els comentaris afegits a la línia de treball del supply-cut estaven en català, mentre que la convenció del codi (sobretot al backend) tendeix a l'anglès. Es tradueixen els comentaris nous de `SupplyCutRegion.vue` (ordre de treball, treure un punt del tall i el token provisional de `OrderSaveSerializer.validate()`), el comentari HTML de `SupplyCutDetail.vue` sobre els `fieldset` morts, i els comentaris de `ClusterEdit.vue`/`ClusterRegion.vue` sobre el marcatge del punt amb `supply_point_status_cut_token`. Els comentaris preexistents no es toquen.
    - `SupplyCutDetail.vue`: s'elimina codi mort (`fetchConnectionStatuses()`/`supplyPointRequestStatuses` i la crida a `$ConfiglistApiService` a `onMounted`), que no s'utilitza en cap plantilla després de la retirada dels `fieldset` del dia [02-09-2026].

#### SERVICE (`SupplyCutRegion.vue`, `SupplyCutDetail.vue`, `ClusterEdit.vue`, `ClusterRegion.vue` — estandardització de comentaris a l'anglès i neteja)
    - Els comentaris afegits a la línia de treball del supply-cut estaven en català, mentre que la convenció del codi (sobretot al backend) tendeix a l'anglès. Es tradueixen els comentaris nous de `SupplyCutRegion.vue` (ordre de treball, treure un punt del tall i el token provisional de `OrderSaveSerializer.validate()`), el comentari HTML de `SupplyCutDetail.vue` sobre els `fieldset` morts, i els comentaris de `ClusterEdit.vue`/`ClusterRegion.vue` sobre el marcatge del punt amb `supply_point_status_cut_token`. Els comentaris preexistents no es toquen.
    - `SupplyCutDetail.vue`: s'elimina codi mort (`fetchConnectionStatuses()`/`supplyPointRequestStatuses` i la crida a `$ConfiglistApiService` a `onMounted`), que no s'utilitza en cap plantilla després de la retirada dels `fieldset` del dia [02-09-2026].

### FIX
#### COMMUNICATION
    - S'ha corregit el botó d'acceptació de la pantalla de selecció de pagaments SEPA per a la gestió de remeses.

### FEAT
#### BILLING / SERVICE (`SEPAManagementEdit.vue`, `SEPAPaymentsList.vue`, `CompanyBankRouting.vue`, `AddCompany.vue`, `CompanyRegion.vue` — remeses per empresa emissora i encaminament per entitat del pagador)
    - A la pantalla de remeses SEPA, el selector de compte bancari passa a ser de **empresa emissora** (multi-selecció). Els comptes on va cada rebut els decideix el mapa d'encaminament de l'empresa, i es genera un fitxer per cada compte que hi acabi tenint rebuts. Seleccionar una empresa també **filtra** els rebuts: una remesa de l'empresa 1 ja no pot arrossegar factures de l'empresa 2.
    - El llistat de rebuts guanya una columna **Banc** (només quan hi ha més d'un compte on triar) amb el compte que ha decidit el mapa, i permet canviar-lo rebut a rebut com a excepció. Les files canviades a mà es marquen amb vora blava; tornar-les al compte del mapa esborra l'excepció, de manera que no queda obsoleta si després es canvia la configuració.
    - Bloc d'avisos sobre els filtres amb el que ha passat en encaminar: rebuts sense IBAN, empreses sense compte per defecte, rebuts d'una altra empresa. Són informatius i no impedeixen generar.
    - La previsualització de fitxers ensenya l'empresa, el banc i els últims dígits de l'IBAN de cada fitxer.
    - **Pestanya nova a la fitxa d'empresa: «Encaminament de remeses»**. Taula amb totes les entitats bancàries del sistema, el nombre de clients que hi paga i el compte de l'empresa on s'encamina cadascuna. Ve filtrada a les entitats en ús (de 572 del catàleg, a la instal·lació B només 70 les fa servir algú) amb commutador per veure-les totes, cercador per codi/nom/BIC, selecció múltiple amb assignació en bloc, les dues files especials a dalt (IBAN estranger i Per defecte) i una estimació de clients per compte. El nom de l'entitat és **editable des d'aquí**: el catàleg ve d'una importació i en té de molt usades sense nom (0182 BBVA, amb 1.320 clients).
    - L'encaminament només s'ofereix quan l'empresa té **més d'un compte actiu**: amb un de sol tot hi va igualment i no hi ha res a repartir. També es pot obrir des de la pantalla de remeses, per repassar-lo o retocar-lo just abans de generar; en tancar-lo es refà la cerca perquè els comptadors reflecteixin el canvi. Va en una region pròpia, per sobre del contingut i sense estrènyer la pàgina de sota.
    - **El compte per defecte ara es desa.** El selector de la fitxa d'empresa només canviava l'estat local i `is_default` no arribava mai al servidor. També es veu molt més clar: capçalera a la llista de comptes, fila destacada, etiqueta «PER DEFECTE» i una nota que explica que és on van els rebuts que l'encaminament no assigni a cap altre compte (en ambre si no n'hi ha cap de marcat). A `CompanyRegion` el compte per defecte surt primer, amb vora destacada i capçalera pròpia.

## [14-09-2026]

### FEAT
#### BILLING
    - Si la raó de refacturació és **canvi de titular**, es pot seleccionar un nou titular. Aquest nou titular s'envia a `generateInvoiceBudget` dins de `redo_option.new_holder` en generar pressupost o factura. Si la raó és canvi de titular i no n'hi ha cap de seleccionat, es mostra un avís i no es genera.

#### STATISTICS
    - S'ha creat un nou model i funció pels informes que s'han de generar de manera diaria. S'agafa una plantilla amb un informe existent relacionat i se li passa com a dades data d'aquell dia, generant un informe relacionat amb totes les factures, cobraments o el que sigui de cada dia.
    Des de 'statistics/daily-document-templates' es pot configurar un nom, descripció, cada quants dies caduca... 
    Des de 'statistics/daily-documents' podem consultar els fitxers i podem realitzar accions com ara descarregar el document, marcar com a enviat, cancel·lar amb un motiu, regenerar document i mostrar si ha fallat la generació de fitxer. També mostrem els informes pendents des del navsidebar.

### FIX
#### BILLING (`SEPAReturnSetup.vue` — la selecció de pagaments no es buidava en carregar un fitxer de devolucions nou)
    - A **producció de la instal·lació A**, carregar quatre fitxers de devolucions seguits sense recarregar la pàgina va generar gestions d'impagats de 6, 13, 23 i 31 pagaments quan els fitxers en portaven 6, 7, 10 i 8: cada gestió nova arrossegava els pagaments de les anteriors.
    - Causa: `getRejections()` buidava `rejections` en carregar el fitxer nou, però **no** `selectedClaimPayments` ni `selectedReturnPayments`, i tot seguit els emetia cap amunt tal com havien quedat. Si els pagaments es marcaven un per un (`addOrRemoveClaimPayment` fa `push`), la selecció del fitxer anterior hi continuava; amb el botó de seleccionar-ho tot (`selectAllForClaims`, que reassigna la llista) sortia neta, i per això el mateix procés a l'entorn de test va fallar només a la segona càrrega.
    - `getRejections()` ara buida les dues seleccions en carregar un fitxer, i el `watch` de `save_response` també les buida (i n'avisa el component pare) un cop desat, perquè tornar a prémer Desar no creï una segona gestió amb els mateixos pagaments.
    - Acompanya la correcció de backend del mateix dia, que retalla la llista rebuda als pagaments d'aquella devolució i en descarta els que ja siguin en una gestió oberta. **No s'ha provat en un navegador**; la reproducció i la verificació s'han fet sobre les dades reals de producció i de test.

#### BILLING (`SEPAManagementEdit.vue`, `AddInvoices.vue`, `AddContracts.vue` — els panells de seleccionar factures i contractes quedaven per sota de la barra de totals)
    - A la pantalla de remeses SEPA, el panell lateral de seleccionar factures (i el de contractes) s'allargava per sota del bloc fix de càlcul de totals: la paginació quedava tapada i no es podia canviar de pàgina.
    - Causa principal: `SEPAManagementEdit.vue` mesura el footer fix amb un `ResizeObserver` per reservar-ne l'espai, però ho feia amb `entry.contentRect.height`, que **no** inclou el `py-4` ni la vora del bloc. La `#right_page` es calculava uns 35 px més alta que l'espai lliure real i se sortia per sota. Ara es mesura amb `footerRef.offsetHeight`.
    - `AddInvoices.vue` i `AddContracts.vue` tenien l'alçada del llistat clavada a `calc(100vh - 200px)`, sense saber res de les pantalles amb barra fixa inferior. Nova prop `height_offset` (per defecte `200`, el comportament actual per a la resta de pantalles); la de remeses hi passa `260 + footerHeight`, de manera que l'espai descomptat inclou l'alçada real de la barra.
    - També hi tenien l'amplada clavada a `calc(100vw - 295px)`, un valor que no depenia del contenidor i deixava un espai en blanc a la dreta del panell. Ara és `width: 100%`; les columnes del grid són de píxels fixos i el contingut no es deforma.
    - Només canvia la geometria: cap canvi de dades ni de comportament dels llistats. **Comprovat visualment a la pantalla de remeses SEPA.**

## [10-09-2026]

### FIX
#### CONTRACT (`data-change.vue`, `change-tenant.vue` — vincular el contracte al GeneralPayment que retorna el backend)
    - Acompanya la correcció de backend del mateix dia: canviar la domiciliació d'un contracte la canviava també als altres contractes del mateix titular, perquè diversos contractes podien penjar de la mateixa fila de `GeneralPayment` i el desat la modificava in-place. Ara el backend fa copy-on-write i, si la fila estava compartida, retorna una fila **nova** que el contracte ha de passar a apuntar.
    - `data-change.vue`: `payment_id` només s'enviava al desar el contracte si havia canviat el tipus o l'IBAN. Ara s'envia **sempre que s'ha desat el payment** (`needsPaymentSave`), de manera que el contracte queda vinculat a la fila retornada en qualsevol cas i no depèn de quines condicions disparen el vincle.
    - `change-tenant.vue`: la resposta de `$GeneralPaymentApiService.save()` es descartava i el contracte no es tornava a vincular; amb copy-on-write això hauria deixat la fila nova òrfena i el contracte amb la domiciliació antiga. Ara es recull la resposta i s'envia `payment_id` amb el desat del contracte.
    - Sense canvis a `surrogate.vue`, `general-invoices.vue`, `ContractRequestEdit.vue` ni `ConnectionRequestEdit.vue`: tots ja vinculaven l'`id` de la fila retornada.

## [09-09-2026]

### FEAT
#### STATISTICS (`daily-activity-summary.vue`, `DailyActivitySummary.vue`, `daily-activity-api.js` — informe de resum diari i widget al dashboard)
    - Nova pantalla `/billing/reports/daily-activity-summary` amb tot el que un usuari ha fet en un dia o en un rang: cinc comptadors (accions, cobraments, devolucions, ordres noves i gestions de contracte), el desglossament de les 10 categories i la cronologia amb hora, acció, referència, contracte, detall i import. Clicant una categoria es filtra la cronologia; botons ràpids Avui / Ahir / Últims 7 dies.
    - Segueix el patró de `general-billing-summary.vue`: pantalla pròpia amb els seus filtres i Excel amb `task_id` + `AtomsProcessColorBadge`. No està registrat a `AvailableReport`; s'hi arriba pel botó nou de `billing/reports/index.vue` i pel widget.
    - **Selector d'usuari**: per defecte "La meva activitat"; amb permís, "Tots els usuaris" i el llistat nominal (i llavors surten la columna Usuari a la cronologia i la taula usuari × categoria). Els comptes tècnics no hi surten, i la llista la decideix el backend (`excluded_usernames`).
    - **Cobraments i devolucions en dos blocs separats**, amb l'import com a xifra gran i no el comptador de moviments (el cobrament massiu es fa per remesa: una acció, milers de rebuts). Cada part porta el seu import —"Remeses: 10 · 488.543,89 €" amb el remès i el no cobrat a sota, "Cobraments manuals: 20 · 1.290,80 €"— perquè la suma del total es pugui seguir.
    - **Widget "La meva activitat d'avui"** a dalt de `pages/index.vue`, amb els mateixos comptadors i enllaç a l'informe. Demana el resum amb `includeDetails: false`; si la crida falla no es pinta, perquè al dashboard no hi ha d'haver un bloc d'error per una dada informativa.
    - Nou `$DailyActivityApiService` (`getSummary()`, `generateReport()`), registrat a `nuxt.config.ts`. Les dates es formen amb `toLocaleDateString('sv-SE')` per no agafar el dia de demà a partir de les 22 h.
    - 39 claus noves sota `daily_activity_block`, més `breadcrumb.daily_activity_summary`, a ca/es/en/gl.
    - Requereix el canvi de backend del mateix dia. Comprovat amb `npm run build` i amb les dues pàgines renderitzant al dev server; **no s'ha provat amb dades reals en un navegador**.

#### CONTRACT (`DataTable.vue`, `useTableColumns.js`, `contracts/index.vue` — taula de contractes configurable per usuari, columna i filtre de comptador)
    - La taula de contractes tenia les columnes clavades a una cadena fixa (`80px,120px,2fr,1fr,75px,120px,150px,150px,130px`): no s'adaptava a la mida de la pantalla, no es podia canviar l'amplada ni triar què es veia, i en pantalles estretes el contingut es tallava sense criteri. Ara `DataTable` accepta un **mode de columnes** (prop `columns` amb un descriptor per columna) que en gestiona l'amplada, la visibilitat i l'ordre. El mode antic (prop `gridTemplate`) es manté intacte per a la trentena de pantalles que el fan servir; només la de contractes s'ha migrat.
    - **L'amplada es reparteix en píxels des de JS, no amb pistes `fr`.** `minmax(min, width)` tapa una columna a la seva amplada preferida per sempre: en una pantalla gran tot el sobrant se l'enduien les dues columnes flexibles i la resta continuava truncada. Ara, si sobra espai es reparteix segons el pes `grow` de cada columna, i si en falta es retalla proporcionalment a la folgança que cadascuna té per sobre del seu mínim (cedeixen primer les més amples). La taula ocupa l'amplada exacta de la finestra a qualsevol mida; la deriva d'arrodoniment en repartir decimals entre deu columnes s'absorbeix a la columna flexible més ampla perquè no dispari la barra de scroll horitzontal.
    - **Es recalcula sol** en canviar la mida de la finestra, la pantalla o la barra lateral (`ResizeObserver` sobre el contenidor, diferit a `requestAnimationFrame` perquè la remesura no dispari l'avís `ResizeObserver loop completed`), amb un listener de `window.resize` de reserva. En estrènyer, les columnes cauen per ordre de `priority` (1 no cau mai); en eixamplar, tornen soles.
    - **Redimensionar, reordenar i triar columnes.** Nansa a la vora dreta de cada capçalera per arrossegar-ne l'amplada (doble clic la restaura); arrossegar la capçalera la canvia de posició; i el botó ⊞ obre un selector amb totes les columnes, on es marquen les visibles i es reordenen amb la nansa o amb fletxes. Una amplada posada a mà és una **línia de base, no una congelació**: la columna manté la mida en estrènyer però continua rebent la seva part quan hi ha espai de sobres. Res del creixement no es desa, o sigui que es recalcula sempre des de la base i no s'acumula.
    - **La configuració es desa per usuari i per taula** a `localStorage` (`dataTableColumns:<taula>:<usuari>`), amb la visibilitat, les amplades i l'ordre. Es va valorar desar-ho al servidor: al backend no hi ha cap model de preferències d'usuari, o sigui que caldria taula, migració i endpoint nous; a canvi, la configuració viatjaria entre navegadors i dispositius. S'ha deixat a `localStorage` amb l'estat aïllat a `loadState`/`saveState`, de manera que migrar-ho a API és tocar un sol fitxer. Si el codi hi afegeix una columna nova, els usuaris amb un ordre desat la reben al final en lloc de perdre-la.
    - **Nova columna "Comptador"** amb el codi del comptador del punt de subministrament, ordenable. Requereix el canvi de backend del mateix dia (`meter_code`); els contractes sense comptador hi mostren un guionet.
    - **Nou filtre de cerca per comptador**, al costat dels d'adreça, correu i IBAN. Busca a tots els punts de subministrament del contracte i pels dos codis del comptador, i el filtre s'aplica també a l'exportació a CSV. Requereix el canvi de backend del mateix dia (`search_meter`).
    - **Corregit de passada**: `handleChange()` —la recàrrega del llistat en tancar la fitxa d'un contracte— no passava els filtres de text, de manera que els de correu i IBAN es perdien en silenci i el llistat tornava amb més resultats dels filtrats. Ara els tres filtres de text es passen a tots els punts de càrrega.
    - També s'ha corregit la icona de contracte fixat, que era de 16 px dins d'una columna de 12 px amb `overflow: hidden` i sortia retallada.
    - Vuit claus noves a `common` (`configure_columns`, `visible_columns`, `columns_hidden_by_width`, `restore_default_columns`, `resize_column`, `drag_to_reorder`, `move_up`, `move_down`) i una a `contract_block` (`search_meter_info`), a ca/es/en/gl.
    - Comprovat amb `npm run build` i amb la pàgina renderitzant al dev server, i la lògica de repartiment, reordenació i llindars responsive simulada aïlladament. **No s'ha provat el filtre de comptador contra dades reals.**

#### CONTRACT (`ContractTabs.vue`, `InvoiceMiniDetail.vue`, `SendInvoiceModal.vue` — enviaments agrupats de factures)
    - Nou botó "Enviaments agrupats" al llistat de factures del contracte, que activa un mode de selecció múltiple per preparar l'enviament de diverses factures.
    - En aquest mode, les factures amb document disponible es poden seleccionar mitjançant un selector; les factures sense `invoice_file_template` queden deshabilitades.
    - El botó "Enviar" mostra el nombre de factures seleccionades i obre el modal d'enviament amb navegació entre les factures seleccionades.
    - Les seleccions es mantenen encara que es canviï de pàgina del llistat, i es netegen en sortir del mode d'enviaments agrupats.
    - Noves claus `contract_block.grouped_sends` i `contract_block.cancel_grouped_sends` a ca/es/en/gl.

## [08-09-2026]

### FEAT
#### ORDER (`OrderEdit.vue`, `GotOrderLocation.vue` — ordres de treball ubicades només per coordenades)
    - El bloc "Ubicació" de l'editor d'ordres només deixava triar entre punt de subministrament, adreça, escomesa i contracte: sempre calia lligar l'ordre a una entitat, tot i que el model del backend (`order.Order`) ja té `supply_point`, `connection`, `address` i `contract` opcionals i camps `latitude`/`longitude` propis. Ara hi ha una cinquena opció, "Només coordenades", que desa l'ordre amb les quatre relacions a `null` i la ubicació únicament al mapa.
    - Amb "Només coordenades" seleccionat, la geolocalització deixa de ser opcional: `isValid()` exigeix latitud i longitud i, si falten, surt el missatge sota el mapa en comptes de desar una ordre sense cap ubicació. Les caselles d'actualitzar la geolocalització de la finca o de l'escomesa continuen sortint només amb punt de subministrament o escomesa triats, perquè aquí no hi ha cap entitat a actualitzar.
    - En obrir una ordre existent que no té cap relació però sí coordenades, el radiobutton es restaura a "Només coordenades" (abans queia al valor per defecte "Punt de subministrament" i semblava que faltava per omplir).
    - Al minigot, el detall de l'ordre (`pages/got/orders/[id].vue`) no mostrava mai les coordenades de l'ordre, de manera que una ordre ubicada només al mapa arribava a l'operari sense cap dada d'on anar. Nou component `components/got/OrderLocation.vue` amb latitud, longitud, un mapa Leaflet amb el marcador (mateix patró que `AtomsInputGeolocation`, però només de lectura) i un enllaç per obrir la ubicació a Google Maps. Surt sempre que l'ordre porti coordenades, també si a més va lligada a un punt de subministrament o una adreça. No calen canvis de backend: `OrderGotSerializer` ja fa `fields = '__all__'` i retorna `latitude`/`longitude`.
    - Cinc claus noves a ca/es/en/gl: `order_block.only_coordinates`, `order_block.only_coordinates_hint`, `order_block.only_coordinates_required`, `GOT.location` i `GOT.open_in_maps`.
#### CLAIM REQUEST
    - Permet crear una despesa per factura relacionada a la gestió de impagats, creant un pagament agrupat si es configura. Això actua a sobre del procés de comunicació, fent que en comptes de lligar la factura i nous pagaments, es pugui afeigr el pagament agrupat com a codi de barres a les cartes generades.
#### SERVICE/CLUSTER (`ClusterRegion.vue`, `ClusterNozzleEdit.vue`, `ClusterEdit.vue` — número de comptador a les boquilles i fitxa del punt de subministrament sense sortir de la pantalla)
    - Ni el llistat de boquilles de la fitxa de la bateria ni l'editor mostraven el comptador del punt de subministrament: per saber quin comptador hi havia a cada boquilla calia obrir el punt de subministrament un per un. Nova columna "Comptador" a `ClusterRegion.vue` (files de boquilla i de boquilla partida) i el codi del comptador sota el punt de subministrament a `ClusterNozzleEdit.vue`.
    - El codi del comptador és clicable i obre `MeterRegion` al panell lateral (`showDetail('MeterRegion', …)` a `ClusterRegion.vue`; nou event `show-meter-region` a `ClusterNozzleEdit.vue` que `ClusterEdit.vue` resol amb `OrganismsMeterRegion`), el mateix patró que ja fa `SupplyPointDetail.vue`. Dins d'una subregion es mostra com a text, com la resta d'enllaços del component.
    - A l'editor de boquilles, el punt de subministrament només es podia obrir en una pestanya nova (`AtomsRedirectButton`), cosa que feia perdre l'edició en curs. Ara l'Ident. del punt obre la seva fitxa (`OrganismsSupplyPointRegion`) al panell lateral de `ClusterEdit.vue` mitjançant el nou event `show-supply-point-region`, i la icona d'obrir en pestanya nova es manté al costat per a qui la vulgui. Els dos panells nous es netegen a `closeAllRegions()`, igual que la resta de regions de la pantalla.
    - Requereix el canvi de backend del mateix dia: `ClusterNozzleSerializer` no retornava cap dada del comptador. No calen claus de traducció noves (`meter`, `common.show_detail`).


#### COREDATA (`CallRegisterList.vue`, `call-register-api.js`, `call_register_filter.py` — la pestanya "Registre de trucada" no mostrava els registres tot i comptar-ne)
    - `call-register-api.js` exposava la funció `getAll()` però mai s'havia posat com a plugin de Nuxt (`defineNuxtPlugin` + `nuxtApp.provide('CallRegisterApiService', ...)`). `CallRegisterList.vue` desestructurava `$CallRegisterApiService` d'`useNuxtApp()`, que sempre era `undefined`, i petava.
    - Ara `call-register-api.js` es registra correctament com a plugin sota `plugins/services/coredata/`, amb el mateix patró (`entity`, `apiHost`, `provideName`) que la resta de serveis d'aquest mòdul.

### MODIFIED
#### CONTRACT
    - En retornar saldo, el pagament es genera com a pagat excepte si el mètode és `BANK_TRANSFER`, que queda pendent. Ara, només per transferència, hi ha un checkbox per decidir si el pagament s'ha de generar com a pagat; s'envia com a `mark_as_paid` a `return-money`. La resta de mètodes segueixen desant-se sempre com a pagats i no envien el camp.

## [07-09-2026]

### FEAT
#### BILLING (`pages/billing/reports/add.vue` — filtre per rang de número de factura al bloc "Filtres extra")
    - El bloc "Filtres extra" incorpora el mateix filtre que `billing/reports/general-billing-summary`: prefix de sèrie opcional i número de factura "des de" i "fins a". Es comporta com els altres filtres globals de la pantalla (`include_preinvoices`): val per a qualsevol informe que es generi des d'aquí. La casella "Excloure les factures ja revisades" **no** hi surt: és del flux de revisió per rangs, no un filtre d'informes, i aquí exclouria factures de l'informe sense que ningú ho hagi demanat.
    - S'envien al trigger com `serie_final_from`, `serie_final_to` i `prefix`, les mateixes claus que ja fa servir la pantalla de rangs, de manera que el backend les aplica a tots els informes basats en factures.
    - Es pot deixar un dels dos extrems buit per no acotar aquell costat, i el prefix tot sol també filtra (tota la sèrie: p. ex. `FC/AAAAMM/` són les factures d'un mes). Si el "des de" és més gran que el "fins a", el missatge surt sota els camps i `isValid()` no deixa generar l'informe.
    - **El rang ja compta com a selecció**: amb el rang (o només el prefix) omplert, `isValid()` deixa generar l'informe sense triar lot de facturació, període, remesa, persona ni contracte, perquè el rang identifica les factures per si sol i el backend ja no exigeix lot ni període.
    - Reutilitza les claus de traducció que ja existien (`serie_final_prefix`, `serie_final_from`, `serie_final_to`, `exclude_already_reviewed_invoices`) i n'afegeix cinc a ca/es/en/gl: `serie_final_range_group`, `serie_final_range_hint`, `serie_final_range_invalid`, `serie_final_range_format` i `serie_final_range_mixed`.
#### COMMUNICATION (`CommunicationProcessCreation.vue` — resum del resultat de la cerca a la barra inferior)
    - No hi havia manera de saber quants registres havia tornat la cerca de destinataris abans d'anar avançant passos: la capçalera del wizard només tenia dos comptadors petits (persones seleccionades i factures) lluny del botó "Cerca", i el de factures sortia sempre, encara que la cerca fos de remeses o d'impagats i no en tornés cap. El resum passa a la barra inferior fixa, al costat del botó "Cerca", amb el mateix patró que `SEPAManagementEdit.vue`: número gran i etiqueta, i el flaix `jquery-highlight` sobre el footer quan els comptadors canvien, perquè el footer és fix i queda fora de la vista on l'usuari està treballant.
    - Comptadors de persones, persones excloses, contractes, factures i lectures. Els que són a zero no es pinten, perquè cada tipus de cerca (facturació, impagats, remeses…) només omple algunes d'aquestes dades i un "Factures: 0" permanent només feia soroll. El de persones sí que hi surt sempre, com a referència.
    - Es compten els registres de les persones **no excloses**, aplicant les dues exclusions del wizard (el flag `exclude` que ja arriba de la cerca i les persones tretes a mà al pas 2, `excludedPersons`), que és el mateix criteri de `save()`. Abans el comptador de factures sumava també les de les persones excloses, de manera que no quadrava amb el que s'acabava enviant.
    - Els comptadors surten d'una única llista (`searchSummary`) en lloc d'estar escrits a mà al template, i les insígnies antigues de la capçalera s'han tret per no duplicar la mateixa informació en dos llocs.
    - Dues claus noves a ca/es/en/gl: `customer_service_block.search_summary` (títol del grup, com a `title` del bloc) i `customer_service_block.excluded_persons`.
#### CONTRACT (`pages/contract/contracts/[id]/surrogate.vue` — decidir què passa amb el llogater durant una subrogació)
    - La subrogació només movia el titular: `ContractSurrogationSerializer.create()` canvia `holder`, la persona de la guardiola, el pagament i les adreces, i buida els contactes de l'antic titular perquè són dades personals seves — però `contract.tenant` no hi sortia, així que el llogater de l'antic titular es quedava enganxat al contracte en silenci. Incoherent amb el criteri del propi flux, que sí que neteja el contacte. Treure'l només es podia fer des de "Canvi de llogater", en una segona passada: a les dues úniques subrogacions de la instal·lació B sobre contractes amb llogater, el llogater es va assignar a mà 10 i 3 minuts després de subrogar, passant per l'altra pantalla.
    - Nou bloc "Llogater actual" sota "Nou titular", amb el mateix patró que `change-tenant.vue`: paperera per desvincular-lo (amb confirmació) i llapis per substituir-lo per una altra persona. Si el contracte no en té, hi surt `contract_block.no_tenant` i un botó per assignar-ne un.
    - Les dues accions passen per `POST /contract/contract-tenant-change/` (`changeTenant`), no per `tenant = null` a pèl, de manera que el backend deixa la `ContractObservation` ("Canvi de llogater: X → Cap") i el `ContractLog` corresponents. S'apliquen a l'instant i no esperen a desar la subrogació, igual que la desvinculació de `change-tenant.vue`.
    - `PersonSearch` es reutilitza per als dos camps: `openPersonForm('holder' | 'tenant')` decideix on va la persona seleccionada i quines etiquetes es mostren al panell.
    - No cal cap canvi de backend: `ContractTenantChangeSerializer` ja accepta `new_tenant` i `previous_tenant` a null i ho reflecteix als textos com a "Cap".
    - Nova clau `contract_block.tenant_changed_success` a ca/es/en/gl.

#### READING (`ReadingBatchRegion.vue` — alertes de lector al llistat de lectures)
    - S'ha afegit una columna amb l'alerta del lector al llistat de lectures dins de lot.

#### COREDATA (`ClusterDetail.vue`, `PersonChangeHistory.vue` — pestanya de modificacions a la fitxa de persona)
    - Nou component `PersonChangeHistory.vue`, igual que el tab `dataChange` de `ContractBlock.vue`, consumint el nou endpoint `GET /coredata/person/{id}/logs/` via `$PersonApiService.getLogs()`.
    - Inclou el mateix botó "Modificar" que la resta de pestanyes d'acció ràpida, que porta a l'edició de la persona.
    - Nova pestanya "Modificacions" a `PersonRegion.vue`, amb comptador que s'actualitza en carregar l'historial.

#### DEPLOY (`NavSidebar.vue`, `composables/useDeployInfo.ts`, `scripts/record_deploy.sh` — data del deploy i commits desplegats al desplegable del NavSidebar)
    - Al desplegable de l'explotació, just sota el botó "Ajuda", hi surt la data de l'últim desplegament i, en passar-hi el ratolí, el commit (branca@sha) de frontend i el de backend que s'estan executant. Serveix per saber, des de la mateixa aplicació, quina versió té davant un client quan reporta alguna cosa.
    - `scripts/record_deploy.sh` (bessó del del repo backend) s'executa al deploy abans del build de Nuxt i escriu `public/deploy-info.json` — que Nuxt copia a l'output i serveix a `/deploy-info.json` — i una fila nova a l'històric `DEPLOYS.md` del servidor. Tots dos fitxers estan ignorats per git.
    - El commit desplegat es llegeix del `.mina_git_revision` de la release (Mina esborra el `.git` amb `remove_git_dir`) i la data i el títol del commit del repo bare `<deploy_to>/scm`; la branca la passa `config/deploy.rb` amb `--branch`. Si el registre falla, el deploy continua amb un avís al log.
    - `useDeployInfo()` demana el JSON propi i `GET /coredata/deploy-info/` del backend un únic cop, i només quan s'obre el desplegable; les dues crides són tolerants a error (sense toast) perquè un problema aquí no ha d'interrompre res. La data mostrada és la més recent de les dues, ja que frontend i backend es despleguen per separat.
    - En desenvolupament no hi ha cap dels dos fitxers: es mostra "Sense informació del desplegament" en comptes d'una data falsa. Noves claus `common.deploy`, `deploy_frontend`, `deploy_backend` i `deploy_unknown` a ca/es/en/gl.

## [04-09-2026]

### FIX
#### BILLING (`InvoiceRegionModals.vue` — el botó "Retornar" no donava cap senyal mentre es retornava la factura)
    - `returnInvoice()` triga (crea el retorn, i opcionalment el moviment de saldo o la transferència), però el botó es limitava a quedar-se desactivat per `returningInvoice`: sense text ni icona que ho indiqués, semblava que el clic no hagués fet res i convidava a tornar-hi.
    - Ara, mentre dura la crida, el botó mostra un spinner i el text "Processant" (`common.processing`), el mateix patró que ja fan servir la resta d'accions llargues del projecte. No canvia cap comportament: la protecció contra el doble clic ja hi era via `:disabled`.

#### CONTRACT (`PersonBankSelect.vue`, `person-bank-api.js` — l'IBAN editat des d'un contracte es canviava a la resta de contractes de la persona)
    - El llapis de cada compte obria `AddBank` en mode edició i `AddBank.save()` retorna `{ ...props.selectedBank }`, conservant l'`id`; `onNewBank` cridava `$PersonBankApiService.save()`, que amb `id` fa `PUT` i reescriu la fila. Com que un `PersonBank` penja de la persona i el comparteixen tots els contractes que l'han triat, posar l'IBAN 2 al contracte 2 el canviava també al contracte 1.
    - `PersonBankSelect` no fa mai més `PUT`: crida el nou `resolve()`, que reaprofita el compte de la persona si l'IBAN ja existeix (i el deixa exactament com estava) o en crea un de nou i l'assigna només aquí. Els 9 llocs que munten aquest selector són contextos de contracte, factura o compromís; la fitxa de la persona (`PersonEdit.vue`) fa servir `AddBank` directament i conserva l'edició en lloc.
    - Tres avisos segons el que ha passat: compte existent reaprofitat, compte nou creat sense tocar l'original, i —quan s'edita sense canviar l'IBAN però sí les dades del titular— que aquestes dades es modifiquen des de la fitxa de la persona. Noves claus `informative_block.person_bank_reused`, `person_bank_copied_on_edit` i `person_bank_edit_not_applied` a ca/es/en/gl.
    - Si la crida falla, el formulari es queda obert per poder reintentar-ho, en comptes de tancar-se com abans.

## [03-09-2026]

### FIX
#### READING (`ReadingBatchReadingsSummary.vue`, `reading-batch-api.js` — el botó "Nou lot de subs. sense lectures" creava un lot amb tots els subministraments)
    - El botó (afegit a `111ac273`) paginava tot el llistat de subministraments sense lectura per acumular-ne els `meter_id` i els enviava com a `meter_ids` a `POST /billing/reading-batch/`. Aquest camp no existeix al serialitzador del backend i s'ignorava en silenci, de manera que el lot es creava amb totes les rutes actives: exactament el contrari del que promet el botó. Es veia mirant `num_routes`/`num_supplies` del lot resultant.
    - Ara crida el nou `POST /billing/reading-batch/{id}/create-missing-batch/` (`createMissingBatch()` a `reading-batch-api.js`), que calcula la llista al servidor amb el mateix criteri que el llistat de la pantalla i crea el lot fixat pels comptadors d'aquells subministraments. De passada s'estalvien les N/20 crides encadenades que feia el bucle de paginació (100 peticions per a 2.000 subministraments) i el lot nou hereta `include_telecontrol`/`include_manual` del lot origen.
    - El `toast` d'error el mostra ja `$apiManager` amb el `detail` del backend (p. ex. quan no queda cap subministrament sense lectura), així que el component ja no en duplica cap. En crear-se el lot es confirma amb el nombre de subministraments inclosos abans de saltar al pas de configuració.

### CHORE
#### READING (`ReadingBatchReadingsSummary.vue` — context del botó "Nou lot de subs. sense lectures")
    - El botó no explicava enlloc què fa i era fàcil confondre'l amb "Afegir subms. sense lectura a lot manual", que actua sobre un lot existent. S'hi ha afegit una nota sota el botó (i el mateix text com a `title`) que diu que crea un lot NOU només amb els N subministraments sense lectura d'aquest lot, sense haver de triar rutes, i que el lot actual no es modifica.
    - El botó es desactiva si no hi ha cap subministrament sense lectura, i el `window.prompt` del nom explica ara que s'hi afegirà el prefix "Sub. sense lectura - ". Noves claus `billing_block.new_missing_readings_batch_prompt`, `new_missing_readings_batch_info` i `missing_readings_batch_created` a ca/es/en/gl.

## [02-09-2026]

### FIX
#### CONTRACT (`ContractActionsDropdown.vue` — "Generar contracte" restava desactivat amb fitxer esborrat/`is_active: false`)
    - En eliminar el fitxer del contracte, el backend el pot tornar amb `is_active: false` en lloc de `null`. El menú d'accions desactivava "Generar contracte" amb `:disabled="contract?.contract_file"`, així que qualsevol objecte (fins i tot inactiu) bloquejava l'opció.
    - Ara només es desactiva si hi ha `contract_file` actiu (`is_active !== false`), el mateix criteri que ja usava `ContractDocumentsData.vue`.
    - Alineat també el comptador de documents a `ContractTabs.vue`/`ContractRequestRegion.vue` i l'avís de contracte no signat a `ContractRequestDetail.vue`, filtrant fitxers inactius.
    
#### SERVICE/SUPPLY-CUT (`SupplyCutRegion.vue` — el botó "Generar ordre de treball" d'un tall de subministrament no feia res)
    - `generateWorkOrder()` era un stub buit (`// TODO`): el botó hi era des del principi però no creava cap ordre ni mostrava cap error, així que la pantalla semblava acabada. Ara crea l'ordre seguint el mateix patró que `ConnectionRequestData.vue` i `ContractTerminationEdit.vue`.
    - Nou `getOrderConfig()`: resol el tipus d'ordre a partir del `ConfigProject` `order_type_supply_cut_token` i carrega els tipus i estats d'ordre (`order/order-type`, `order/order-status`).
    - L'ordre es crea amb `supply_point`, `contract` (si el punt de subministrament en té), `type`, l'estat per defecte, `dueDateAt` (data d'inici del tall) i una `description` amb el tall, la ubicació, el punt de subministrament, l'escomesa, el comptador i la causa. S'hi envia també un `token` provisional perquè `OrderSaveSerializer.validate()` l'exigeix en crear, tot i que el backend el sobreescriu amb el token definitiu dins de `create()` — el mateix que fan la resta de crides del projecte.
    - Nou `getOrder()`: en carregar el tall i en canviar de punt de subministrament es comprova si ja existeix una ordre d'aquest tipus per a aquell punt. Si n'hi ha, el botó se substitueix per la fitxa de l'ordre (`MoleculesOrderTypeDetail`, clicable → obre `OrderRegion` al panell lateral) amb botó d'eliminar-la, de manera que no es poden generar ordres duplicades.
    - Quan `order_type_supply_cut_token` apunta a un token que no existeix al catàleg de tipus d'ordre del client, el botó ja no apareix: es mostra un avís que anomena el token buscat i la clau de configuració. Abans això només es descobria en clicar, amb un toast que no deia quina clau calia revisar.
    - `showDetail()` i `handleClickChangeStatus()` es netegen mútuament, perquè el formulari de canvi d'estat i el detall d'una ordre no se solapin al panell lateral.
    - Configuració per client: `order_type_supply_cut_token` ve amb el valor de plantilla `cut_supply`, que no existeix als clients amb catàleg propi de tipus d'ordre (i que feia fallar el botó amb "No s'ha trobat el tipus d'ordre"). Per a la instal·lació B s'ha fixat a `YA` (TREURE COMPTADOR: MOROSITAT), determinat analitzant l'ús històric de les taules `Feina`/`OrdreServei` de la BD original del client.
    - Pendent, no inclòs aquí: `ClaimRequestManageCutSupply.vue` crida `postClaimRequestOrder('cut_supply', …)` amb el token literal en comptes del configurat, així que aquest flux continua fallant als clients amb catàleg propi de tipus d'ordre.

#### SERVICE/SUPPLY-CUT (`SupplyCutDetail.vue` — codi mort que semblava funcionalitat pendent)
    - El component tenia dos `fieldset` (dades del punt de subministrament, i "Generar ordre de treball" amb un `generateWorkOrder()` buit) protegits per `v-if="data.supply_point"`. `SupplyCut` no té cap camp `supply_point` — només la M2M `supply_points` —, així que no s'han mostrat mai: era una segona còpia morta, i desactualitzada, de la pantalla real. S'han tret, amb un comentari que remet a `SupplyCutRegion.vue`, que és qui serveix aquesta informació i les accions reals (ordre de treball i canvi d'estat) per al punt seleccionat i amb comprovació de permisos.

#### BILLING (`AddInvoices.vue`, `invoice-api.js`, `money.js` — el filtre per import no trobava res i el cursor saltava sol a la primera casella)
    - El camp "Cerca un total específic" s'enviava com a `left_to_pay` en comptes de `total_final`: filtrava per l'import PENDENT, així que cercar el total d'una factura ja cobrada (pendent = 0) no la trobava mai. El backend té tots dos filtres; ara s'hi envia el que promet l'etiqueta. Comprovat amb una factura ja cobrada: filtrant per `left_to_pay` no surt, i per `total_final` sí.
    - Segona causa: `total_final.replace(',', '.')` només substituïa la PRIMERA coma, així que escrivint `1.234,56` s'enviava `1.234.56`, que no és un número i feia que el `NumberFilter` del backend respongués 400. Nova `parseAmountInput()` a `utils/money.js`, que normalitza les formes amb què s'escriu un import (`1.234,56`, `1234,56`, `1234.56`, `1234`) i retorna `null` si no en surt un número, de manera que el filtre no s'envia en comptes de trencar la petició. Amb un sol separador la xifra és ambigua i, com que en un import no existeixen tres decimals, `1.234` es llegeix com a milers i `12,34` com a decimals. La normalització s'aplica també al filtre de rang (`start`/`end_total_final_range`), que tenia el mateix problema.
    - Aquest arranjament és a la capa d'API compartida, així que afecta també el camp equivalent del llistat general de factures (`pages/billing/invoice/index.vue`), que tenia exactament el mateix error.
    - `getData()` acabava sempre amb `document.getElementById('searchInput').focus()`. Com que es crida en escriure a qualsevol filtre, en canviar de pàgina i en ordenar, el cursor tornava constantment a la primera casella. Ara el focus es posa només quan s'obre el panell (en muntar i quan `props.show` passa a cert), que era la intenció útil.
    - `resetFilters()` no netejava el total, els mètodes de pagament ni el tipus de factura: en reiniciar desapareixien els xips de la interfície però la cerca seguia aplicant-los. També s'ha afegit a `checkInAdvacedFilters()` el cas dels mètodes de pagament i del tipus, que hi faltava, de manera que treure'ls dels filtres avançats també els desaplica. L'indicador `isFiltered` compta ara aquests tres filtres.

### FEAT
#### CONTRACT (`pages/contract/contracts/[id]/change-tenant.vue` — desvincular llogater del contracte)
    - Fins ara, el flux de "Canvi de llogater" només permetia substituir el llogater per un de nou; no hi havia manera de deixar el contracte sense llogater (`tenant_id = null`) sense eliminar la persona.
    - Al bloc "Llogater actual" s'afegeix una paperera sempre visible que, amb confirmació, crida `changeTenant` amb `new_tenant: null` i `previous_tenant` = llogater actual, desvincula el llogater del contracte i torna al detall.
    - Si el contracte no té llogater, es mostra el text informatiu `contract_block.no_tenant`.
    - Noves claus i18n (`ca`/`es`/`en`/`gl`): `contract_block.no_tenant`, `contract_block.tenant_unlinked_success`, `confirmation_text_block.confirm_unlink_tenant`.
    - Requereix que el backend accepti `new_tenant: null` a `POST /contract/contract-tenant-change/` i deixi `tenant_id` a null amb log.

#### BILLING (`SEPAManagementEdit.vue`, `SEPAPaymentsList.vue` — marcar com a exclosos de la remesa els contractes amb factures pendents de pagar, i poder revisar-los)
    - En preparar una remesa SEPA no hi havia manera de deixar fora els rebuts dels contractes que arrosseguen deute: es remesaven factures noves de contractes que ja tenen factures vençudes/impagades. Tampoc es podia revisar què quedava fora, perquè el panell del llistat barrejava rebuts inclosos i exclosos.
    - Nou interruptor "Marca exclosos els contractes amb impagats" als filtres generals (`SEPAManagementEdit.vue`, just sota el selector Factura / Compromisos de pagament), amb icona d'informació que explica el criteri. No redueix el llistat: en cercar, marca aquests rebuts com a exclosos (crida `bulkExcludeSEPAInvoices` amb `only_contracts_with_pending_invoices`), de manera que compten al comptador d'exclosos, es veuen a la pestanya "Exclosos" i es poden tornar a incloure un a un. La remesa ja els salta pel mecanisme existent d'`include_excluded`, així que `clickFinalize()` no necessita cap filtre addicional. Només ho fa la cerca que demana l'usuari: `search()` accepta `applyPendingInvoicesExclusion`, i els refrescos que demana el llistat (`@change`) el passen a `false` — si no, tornar a incloure un rebut seria impossible perquè el refresc posterior el tornaria a excloure.
    - Nou botó "Excloure els de contractes amb impagats" al llistat de pagaments (`SEPAPaymentsList.vue`, al costat d'"Excloure tots"): la mateixa acció a demanda, sense haver de tornar a cercar. Força `exclude_contracts_with_pending_invoices: false` al payload perquè el backend dona prioritat a l'exclusió i, si arribés activa, marcaria justament la resta de rebuts.
    - Noves pestanyes "A remesar" / "Exclosos" al panell del llistat de pagaments (`SEPAManagementEdit.vue`), amb el recompte a cada pestanya: la primera mostra el que es processarà (`include_excluded: false`) i la segona exactament el que no (`only_excluded: true`, paràmetre nou del backend). Abans el panell barrejava els dos casos i no hi havia manera de revisar què s'havia deixat fora. El comptador vermell d'exclosos de la capçalera ara és clicable i obre el panell directament a la pestanya d'exclosos.
    - Requereix el canvi de backend del mateix dia: el criteri de "factura pendent de pagar" és l'estat Vençuda/Impagada, no hi compten les factures de despeses d'impagats i no hi compta la factura del propi rebut que s'està remesant.
    - Noves claus de traducció (`billing_block`) a `ca`/`es`/`en`/`gl`: `exclude_contracts_with_pending_invoices`, `exclude_contracts_with_pending_invoices_action`, `info_exclude_contracts_with_pending_invoices` i `payments_to_remit`.

#### CONTRACT (`contracts/index.vue`, `useSupplyPointCutStatusToken.js` — icona de tisores a la llista de contractes amb el subministrament tallat)
    - El detall del contracte (`ContractDetail.vue`) ja marcava amb una icona de tisores els contractes amb un tall de subministrament actiu, però la llista de contractes no ho mostrava: calia obrir cada contracte per saber-ho.
    - Nova icona `fa6-solid:scissors` al costat de l'Ident. del contracte, amb el mateix `title` (`service_block.active_supply_cut_warning`) que al detall i al costat de la de boca d'incendi.
    - `useSupplyPointCutStatusToken().isSupplyPointCut()` accepta ara també el camp pla `supply_point_default_status_token` que retorna el serializer de llista, a més de les formes imbricades que ja tractava, de manera que el detall i la llista comparteixen la mateixa lògica. Requereix el canvi de backend del mateix dia.

#### SERVICE/SUPPLY-CUT (`SupplyCutRegion.vue`, `supply-cut-api.js` — treure un punt de subministrament d'un tall perquè deixi d'afectar el seu contracte)
    - Un tall marca com a tallats tots els seus punts de subministrament, i és l'estat del punt el que fa que el contracte consti com a tallat. Fins ara l'única sortida era tancar el tall sencer: no hi havia cap manera d'excloure'n un contracte concret. De fet no hi ha cap pantalla d'edició d'un tall existent (`SupplyCutEdit.vue` només està muntat a `pages/service/supply-cut/add.vue`) i el llistat de punts de la regió era només de lectura.
    - Nova columna d'accions al llistat de punts del tall, amb un botó "Treure del tall" (`fa6-solid:link-slash`) per fila: confirmació explícita, spinner mentre desa, `@click.stop` perquè no canviï el punt seleccionat, i visible només amb `objectPermissions.can_change`. En acabar recarrega el tall i, si el punt tret era el seleccionat, neteja la selecció.
    - Nou `removeSupplyPoint(id, supply_point_id, observation)` a `plugins/api/service/supply-cut-api.js`, que crida l'endpoint nou del backend del mateix dia. Si el tall es queda sense punts, el backend el tanca automàticament.
    - Noves claus de traducció (`service_block`) a `ca`/`es`/`en`/`gl`: `remove_supply_point_from_cut` i `confirm_remove_supply_point_from_cut`.
    - Requereix el canvi de backend del mateix dia: sense ell, tancar un tall o treure'n un punt no tenia cap efecte sobre l'estat del punt de subministrament.
    - Pendent, no inclòs aquí: des del contracte i del punt de subministrament només hi ha enllaç per CREAR un tall (`/service/supply-cut/add`), no per anar al tall que l'està afectant, de manera que per desfer-ho cal passar pel llistat de talls. L'API ja accepta el filtre `supply_point` a `/service/supply-cut/list/`.

#### BILLING (`AddInvoices.vue` — filtre per tipus de factura per identificar despeses d'impagats, altes i consum)
    - En seleccionar factures per a una remesa (`SEPAManagementEdit.vue`) no hi havia manera de distingir per tipus: calia anar factura per factura per saber si una era de consum, d'alta o de despeses d'impagats.
    - Nou multi-select "Tipus de factura" als filtres avançats, amb Consum, Altes, Despeses d'impagats, Escomeses, Subministrament i Altres. Envia el nou paràmetre `invoice_kinds` del backend del mateix dia, que resol el mapatge a partir dels `ConfigProject` d'origen i, per a les despeses d'impagats, de la `PriceRate` de la línia — la classificació depèn de la configuració de cada client i per això no es replica aquí.
    - Els tipus surten disjunts: demanar "Altres" no hi inclou les despeses d'impagats, tot i que tècnicament tenen aquest origen.
    - Noves claus de traducció (`billing_block`) a `ca`/`es`/`en`/`gl`: `invoice_kind`, `invoice_kind_consumption`, `invoice_kind_registration`, `invoice_kind_unpaid_fee`, `invoice_kind_connection`, `invoice_kind_supply` i `invoice_kind_other`.
    - Pendent, no inclòs aquí: la branca `payment_bank_final` de `getData()` va per `getInvoiceByCustomerToken()` i ignora el total, els mètodes de pagament i el tipus. I el llistat general de factures no ofereix el selector de tipus, tot i que el backend ja l'admet.

## [01-09-2026]

### CHORE
#### BILLING
    - S'ha afegit una mica més d'informació i s'ha retocat una mica visualment el component de 'BilledInvoicesDetail'

#### SERVICE/ROUTE (`PropertyEdit.vue`, `RouteEdit.vue`, `AddRoutePosition.vue`, `AddNewRoutePosition.vue` — gestionar la posició de ruta d'una finca des de la seva pròpia fitxa, i reordenar/canviar de ruta amb més facilitat)
    - Fins ara, l'única manera d'afegir o modificar la posició de ruta d'una finca era des de la pàgina de la ruta (`RouteEdit.vue`); no hi havia cap manera de fer-ho des de la fitxa de la finca. `PropertyEdit.vue` mostra ara un botó "Afegir ruta" quan la finca no en té cap assignada, que obre un selector de rutes (`MoleculesAddRoute`) i crea la posició de ruta corresponent.
    - Quan la finca ja té una posició de ruta assignada, es mostren ara també l'ordre (`route_position.position`) i l'Ident. de la pròpia posició (`route_position.token`), no només l'Ident./nom de la ruta.
    - El botó de llapis al costat de la ruta ja no navega a la pàgina completa de la ruta (`RouteEdit.vue`): obre directament, en un panell lateral, el formulari d'edició d'aquella posició concreta (`OrganismsAddRoutePosition`/`AddNewRoutePosition.vue`), sense necessitat de carregar ni mostrar la resta de posicions de la ruta.
    - Nou camp "Ruta" dins del propi formulari d'edició d'una posició (`AddNewRoutePosition.vue`), amb un botó que obre un selector de rutes i permet **moure la posició a una ruta diferent** (el backend ja ho admetia, però no hi havia manera d'activar-ho des del frontend). En canviar de ruta es recalcula la primera posició lliure disponible i es regenera l'Ident. amb el patró de la nova ruta.
    - `AddRoutePosition.vue` (organisme pare) manté ara l'estat de la ruta seleccionada de forma independent de la prop original, de manera que aquest mateix flux de canvi de ruta funciona tant des de `RouteEdit.vue` com des de `PropertyEdit.vue`; la comprovació de token duplicat (pensada per a la ruta original) se salta quan l'usuari ha canviat de ruta.
    - A `RouteEdit.vue`, el llistat de posicions es pot arrossegar (drag&drop, amb `vuedraggable`, ja usat en altres pantalles) per reordenar-les quan estan ordenades per "Ordre" — desactivat automàticament si s'ordena per Identificació o Nom. En deixar anar, es crida el nou endpoint `/route-position/{id}/move/` del backend, que desplaça en cadena (+1/-1) les posicions intermèdies fins trobar un espai lliure. Requereix el canvi de backend del mateix dia.
    - L'Ident. (token) d'una posició de ruta ja no es genera amb zeros a l'esquerra (`888_00001`); ara segueix sempre el patró `{token_ruta}_{ordre}` (p. ex. `888_1`), coherent amb el que el backend recalcula automàticament en reordenar.
    - Noves claus de traducció (`ca`/`es`/`en`/`gl`) a `common`: `reorder`.

#### BILLING/CLAIMREQUEST (`ClaimRequestEdit.vue` — nou checkbox per no comptabilitzar les factures de despeses de devolució com a "vençudes")
    - En crear una gestió d'impagats, les factures de recàrrec/despeses de devolució (generades automàticament quan un rebut torna) es comptaven igual que qualsevol altra factura vençuda, inflant el nombre de factures i l'import total del deute mostrat.
    - Nou checkbox "No comptabilitzar les factures de despeses de devolució" al Pas 1 del formulari, enviat com a `exclude_return_fee_invoices` a `getClaimData()`. Requereix el canvi de backend del mateix dia (`_build_claim_request_filters`/`ContractWithPaymentsSerializer.get_expired_invoices`).
    - Nova clau de traducció (`ca`/`es`/`en`/`gl`) a `billing_block`: `exclude_return_fee_invoices`.
#### BILLING
    - Quan la facturació està finalitzada (`isFinished`), les factures amb `contract_in_billing` mostren una etiqueta ("Aquest contracte ja té una factura a la facturació") i queden bloquejades per accions com moure a facturació o confirmar pressupost (perquè afegirien un altre document al mateix contracte). Si no els queda cap acció disponible, el checkbox de selecció també es desactiva.

    - S'ha afegit un nou apartat a la facturació per mostrar les factures creades que entren dins del mateix període, tant si estàn a dins de la facturació com si no i formen part d'una altra gestió. Aquestes es poden gestionar, generant pressupostos, afegint a la facturació i altres opcions segons es requereixi. Amb això, la part de possibles contractes sense facturar s'ha separat en un nou component per compartir a les dues parts de facturació que ho necessita i formant un grid de 3
