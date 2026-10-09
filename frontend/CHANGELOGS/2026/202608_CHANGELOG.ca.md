# Changelog Frontend

## [31-08-2026]

### FEAT
#### SERVICE/CONTRACT (`ContractDetail.vue` — icona de tall de subministrament actiu al costat del token del contracte)
    - Fins ara, l'única manera de saber si el punt de subministrament d'un contracte tenia un tall de subministrament actiu era obrir-ne el detall; no hi havia cap indicador visual al llistat/fitxa del contracte, a diferència del que ja existia per a les boquilles d'un clúster (`ClusterRegion.vue`/`ClusterEdit.vue`).
    - Nou composable `composables/useSupplyPointCutStatusToken.js` (mateix patró que `useFireUsageTypeTokens.js`): resol el token de configuració `supply_point_status_cut_token` via `$ConfigProjectApiService` i exposa `isSupplyPointCut(contract)`, comparant-lo amb `status_token` de `supply_point_default`/`supply_points[0]`.
    - `ContractDetail.vue` mostra ara una icona `fa6-solid:scissors` (vermella) al costat del token del contracte quan hi ha un tall actiu, amb tooltip `service_block.active_supply_cut_warning` (clau ja existent, reutilitzada del patró de `ClusterRegion.vue`).
    - Pendent de confirmar en real que el backend inclou `status_token` dins de `supply_point_default` en la resposta de l'API del contracte; si no hi és, la icona no apareixerà mai encara que hi hagi un tall actiu.

### FIX
#### GENERAL (icona de "contra incendis": extintor → boca d'incendis, a tota l'aplicació)
    - La icona que marca un contracte/lectura com a relacionat amb un ús contra incendis (`fa6-solid:fire-extinguisher`) no coincidia amb el seu propi tooltip, que ja deia "Boca d'incendis" (`common.fire_hydrant`).
    - El paquet d'icones existent (`fa6-solid`, i també `fa6-regular`/`healthicons`/`heroicons`) no conté cap icona de boca d'incendis; s'afegeix el paquet `@iconify-json/mdi` (Material Design Icons) i es registra `'mdi'` a `icon.serverBundle.collections` (`nuxt.config.ts`).
    - Substituïda la icona `fa6-solid:fire-extinguisher` per `mdi:fire-hydrant` a tots els punts on apareixia: `ContractDetail.vue`, `InvoiceDetail.vue`, `ReadingDetail.vue`, `ReadingListDetail.vue`, `ReadingBatchReadingsSummary.vue`, `ReadingEdit.vue`, `MissingReadingEdit.vue`, `pages/contract/contracts/index.vue` i `pages/reading/readings/estimation.vue`.

#### CONTRACT (`ContractRequestEdit.vue`/`locales/*` — text del pas 6 de "Canvi de nom" poc clar sobre el manteniment del número de contracte)
    - El banner informatiu del pas 6 (clau `contract_block.change_of_name_finalize_info`) deia "sobre el mateix contracte existent, sense crear-ne cap de nou", una formulació que no deixava prou clar que el número de contracte no canvia.
    - Reescrit a `ca`/`es`/`gl`/`en`: "...mantenint el mateix número de contracte existent" (i equivalents), sense tocar la condició de visibilitat existent (`isChangeOfNameRequest && canKeepSameCode && keepSameCode`).

#### SERVICE (`SupplyCutEdit.vue` — data de fi del tall opcional, i validació que no sigui anterior a la d'inici)
    - Les dates d'inici i fi d'un tall de subministrament es tractaven igual, sense deixar clar que la data de fi es pot deixar en blanc perquè el tall quedi obert. S'afegeix l'etiqueta corresponent a cada camp (`common.start_date`/`common.end_date`) i un text d'ajuda sota la data de fi (`service_block.supply_cut_open_hint`).
    - `AtomsInputDateTime.vue`: nova prop `invalid` (marca el `<input>` amb una vora vermella) i nova prop `startDate`, que ara s'usa alhora com a `min` de l'input i com a llindar de validació a l'`onBlur`: si el valor introduït és anterior a `startDate`, es reverteix al propi `startDate` i s'emet el nou event `date-interval-error` amb el missatge `warning_block.date_warning`, gestionat per `SupplyCutEdit.vue::dateIntervalError()`.
    - `getAffectedSupplyPoints()` i `onContractSelected()` de `SupplyCutEdit.vue` ara toleren `supply_point_ids`/`contract_ids` `null`/`undefined` (p. ex. un contracte sense punts de subministrament associats), evitant un error en accedir a `.length`.
    - Noves claus de traducció (`ca`/`es`/`en`/`gl`) a `service_block`: `supply_cut_open_hint`.

#### GENERAL (`ColorBadge.vue` — el valor mostrat no es capitalitzava)
    - El text del badge (traduït o cru) es mostrava tal qual vingués del backend/traducció, sense capitalitzar la primera lletra, cosa que donava un aspecte inconsistent amb la resta d'etiquetes de la interfície.
    - Ara es capitalitza sempre el primer caràcter del valor mostrat, tant si prové de `billing_block.<value>`, de `<value>` directament, com si es mostra el valor cru sense traducció.

#### ROUTE (`RouteEdit.vue` — netejada la icona d'arrossegar (no funcional) del llistat de posicions)
    - Cada posició del llistat mostrava dues icones `fa6-solid:ellipsis-vertical` (aspecte de "nansa" per arrossegar) que no tenien cap comportament associat; s'eliminen per no confondre l'usuari.

## [28-08-2026]

### FEAT
#### COMMUNICATION
    - S'ha actualitzat la barra de navegació fixa del footer als fitxers `ClaimRequestEdit`, `ElectronicInvoiceManage`, `ClaimRequestManage`, `AddNewCommunication`, `SEPAManagementEdit` i `CommunicationProcessCreation`, canviant el color de fons de fucsia a `#FAE2DA`.
    - S'han ajustat els desplegables i l'espai vertical de la pàgina per evitar que els selectors quedin tapats pel footer i millorar-ne l'ús quan hi ha opcions llargues.
    - S'ha reorganitzat l'estructura de `ElectronicInvoiceManage`, `SEPAManagementEdit` i `CommunicationProcessCreation` per millorar la distribució dels continguts i l'espai disponible.

#### READING (`ReadingBatchRegion.vue` — informació del lot original als lots d'excloses)
    - Quan es visualitza un lot d'excloses (`is_excluded`), ara mostra un nou camp "Lot original" amb el nom/token del lot original (`excluded_from`), i permet navegar-hi directament (nou event `select-batch`)..
    - Els agregats (rutes, punts de subministrament totals/actius) d'un lot d'excloses ara s'hereten del lot original en lloc de comptar únicament les lectures pròpies del lot d'excloses, evitant que es mostrés el total de subministraments exclosos en lloc del total real del lot original.

## [27-08-2026]

### FEAT
#### BILLING
    - Ara al llistat de factures i prefactures es mostra i es poden filtrar aquelles lectures que han sigut comunicades a un procés de comunicació. Alt percentatge que aquesta comunicació significa un avís de fuita.

#### COMMUNICATION
    - Semblant al que es comenta abaix, permet adjuntar factures als lots de communicacions a on hi han lectures lligades (només en cas d'existir)
    - Permet seleccionar i afegir les lectures de les factures seleccionades a una comunicació individual. També permet adjuntar lectures a tipus de filtre facturació al procés de comunicació
    
#### CONTRACT (`ContractRequestAddressPayment.vue`, `change-tenant.vue` — neteja de dades de l'antic llogater en canviar-lo)
    - En canviar de llogater, es netegen (IBAN, mandat, adreces, correu, telèfons) totes les dades que fossin de l'antic llogater, mantenint les de qui segueix vinculat al contracte (titular, nou llogater, propietari).
    - Als selectors d'IBAN, adreça i contacte, cada persona es mostra ara amb el seu rol entre parèntesis (Titular, Propietari, Llogater).

#### BILLING (`pages/billing/reports/general-billing-summary.vue` — filtre per excloure les factures ja revisades, i actualització en viu de la columna "Revisades")
    - Fins ara, marcar un rang com a "revisades" no evitava que es tornessin a incloure ni a la previsualització (`to_generate`) ni a l'informe generat en una segona execució sobre el mateix rang — es mostraven igualment, només duplicades també a la pestanya "Ja revisades" a mode informatiu. Requereix el canvi de backend del mateix dia (nou paràmetre `exclude_reviewed`, per defecte `true`, a `invoice/reviewed-range-preview/` i als serveis de generació dels dos informes).
    - Nou checkbox "Excloure les factures ja revisades" (marcat per defecte, un per pestanya de Resum general/Padró de facturació), enviat com a `exclude_reviewed` tant a `previewReviewedRange` com a `generateReport`. Canviar-lo marca la previsualització com a obsoleta (afegit a `currentRangeKey`, igual que el prefix i el rang), exigint tornar a cercar.
    - En clicar "Marcar com a revisades"/"Desmarcar", un cop confirmat pel backend, ja no cal tornar a cercar per veure el canvi: s'actualitza en viu el camp `reviewed` de totes les factures ja carregades a la previsualització (a totes les pestanyes), canviant a l'instant la insígnia de la columna "Revisades" sense recalcular comptadors ni recategoritzar files entre pestanyes.

#### BILLING
    - Ara al llistat de factures i prefactures es mostra i es poden filtrar aquelles lectures que han sigut comunicades a un procés de comunicació. Alt percentatge que aquesta comunicació significa un avís de fuita.

#### COMMUNICATION
    - Semblant al que es comenta abaix, permet adjuntar factures als lots de communicacions a on hi han lectures lligades (només en cas d'existir)
    - Permet seleccionar i afegir les lectures de les factures seleccionades a una comunicació individual. També permet adjuntar lectures a tipus de filtre facturació al procés de comunicació
    
#### CONTRACT (`ContractRequestAddressPayment.vue`, `change-tenant.vue` — neteja de dades de l'antic llogater en canviar-lo)
    - En canviar de llogater, es netegen (IBAN, mandat, adreces, correu, telèfons) totes les dades que fossin de l'antic llogater, mantenint les de qui segueix vinculat al contracte (titular, nou llogater, propietari).
    - Als selectors d'IBAN, adreça i contacte, cada persona es mostra ara amb el seu rol entre parèntesis (Titular, Propietari, Llogater).

### FIX
#### CONTRACT (`ContractRequestEdit.vue` — l'alerta de "Aplicar canvi de nom" deia sempre que no es crearia cap contracte nou)
    - Al pas 7 (Finalització) d'una sol·licitud de "Canvi de nom", el `confirm()` en clicar "Aplicar canvi de nom" mostrava sempre el mateix text (`confirm_change_of_name_finalize`, "No es crearà cap contracte nou"), fins i tot quan l'usuari havia triat crear un número de contracte nou en lloc de mantenir l'existent.
    - `clickFinalize()` ara tria el text segons `canKeepSameCode && keepSameCode`: si és cert, manté el missatge existent; si no, mostra la nova clau `confirm_change_of_name_finalize_new_code`, que indica que es generarà un nou número de contracte.
    - Nova clau de traducció (`ca`/`es`/`en`/`gl`) a `confirmation_text_block`: `confirm_change_of_name_finalize_new_code`.

#### ROUTE (`AddRoutePosition.vue` — no es podia inserir una posició de ruta al mig d'un tram sense forats)
    - Els codis de posició es generen automàticament com `<token_ruta>_<posició>` (p. ex. `13_00101`). En inserir una posició nova entre dues d'existents sense cap forat (p. ex. crear-ne una entre les posicions 100 i 101 de la ruta 13), el codi generat per a la nova posició coincidia exactament amb el de la posició 101 (encara sense desplaçar), i `save()` ho detectava com a "codi duplicat", mostrant un `alert()` bloquejant que impedia crear el registre — encara que el desplaçament automàtic de la resta de posicions (ja implementat a `RouteEdit.vue::newPosition()`) hauria resolt la col·lisió igualment.
    - Ara, en lloc de bloquejar la petició, si el codi generat ja existeix a la ruta s'hi afegeix un sufix numèric incremental fins trobar-ne un de lliure (`10_00101` → `10_001011` → `10_001012`...) i es continua amb la creació/edició amb aquest nou codi. Es notifica el canvi amb un `toast.warning`, sense bloquejar l'acció.
    - Nova clau de traducció (`ca`/`es`/`en`/`gl`) a `service_block`: `duplicate_token_auto_renamed`.

#### CONTRACT (`ContractRequestEdit.vue` — l'alerta de "Aplicar canvi de nom" deia sempre que no es crearia cap contracte nou)
    - Al pas 7 (Finalització) d'una sol·licitud de "Canvi de nom", el `confirm()` en clicar "Aplicar canvi de nom" mostrava sempre el mateix text (`confirm_change_of_name_finalize`, "No es crearà cap contracte nou"), fins i tot quan l'usuari havia triat crear un número de contracte nou en lloc de mantenir l'existent.
    - `clickFinalize()` ara tria el text segons `canKeepSameCode && keepSameCode`: si és cert, manté el missatge existent; si no, mostra la nova clau `confirm_change_of_name_finalize_new_code`, que indica que es generarà un nou número de contracte.
    - Nova clau de traducció (`ca`/`es`/`en`/`gl`) a `confirmation_text_block`: `confirm_change_of_name_finalize_new_code`.

## [26-08-2026]

### FEAT
#### BILLING (`pages/billing/reports/general-billing-summary.vue`, `plugins/api/billing/invoice-api.js` — nou informe "Resum de la facturació general" + marcar factures com a revisades per rang)
    - Requereix el canvi de backend del mateix dia (nous endpoints `invoice/mark-reviewed-range/`, `invoice/reviewed-range-preview/`, `statistics/billing/general-billing-summary` i el `ConfigProject` `general_billing_summary_preview_enabled`). Substitueix, per a aquest cas, l'antic informe en PDF que generava el sistema Kais ("Del núm. de factura X a la Y").
    - Nova pàgina `/billing/reports/general-billing-summary` (enllaçada des de `/billing/reports`), amb camps "Prefix de sèrie" (opcional) i "Núm. de factura des de/fins a" — el `serie_final` d'aquest sistema incrusta el dígit de categoria/sèrie i l'any a l'inici, així que el prefix evita barrejar sèries diferents amb magnituds numèriques coincidents.
    - Dos mètodes nous a `invoice-api.js`: `markReviewedRange(data)` (`POST invoice/mark-reviewed-range/`) i `previewReviewedRange(data)` (`POST invoice/reviewed-range-preview/`).
    - Quan el `ConfigProject` `general_billing_summary_preview_enabled` està actiu, la pàgina exigeix una cerca (dry-run) abans de poder generar l'informe o marcar el rang: barra de navegació fixada al footer (mateix patró `fixed right-0 bottom-0 ... style="width: calc(100% - 250px)"` que `ClaimRequestEdit.vue`) amb els comptadors en viu (factures que es generaran / excloses / perdudes des de l'última revisió / ja revisades dins el rang) i els botons "Cercar", "Generar informe" i "Marcar com a revisades" — aquests dos últims deshabilitats fins que hi ha una cerca vàlida per al rang actual; si es canvia el rang després de cercar, es torna a exigir una nova cerca.
    - Resultat de la cerca mostrat en una taula amb pestanyes (Es generaran / Excloses / Perdudes / Ja revisades), amb número de factura, data, titular, import i una columna "Revisada"/"No revisada" per cada factura.
    - Quan el `ConfigProject` està desactivat, la pàgina manté un flux simple sense cerca (botons "Generar informe" i "Marcar/Desmarcar com a revisades" directes).
    - La comprovació d'aquest `ConfigProject` fa servir `$ConfigProjectApiService.getAll()` en lloc de `get()`, perquè `get()` cacheja el valor a `localStorage` sense caducitat: si el navegador ja havia consultat aquesta config abans que existís al backend, es quedava amb `false` indefinidament encara que es canviés el valor a la base de dades.
    - Afegida una segona pestanya "Padró de facturació" a la mateixa pàgina, que genera l'informe `register_billing_summary` ja existent (mateix format que abans generava Kais) reutilitzant exactament el mateix filtre (prefix + rang de `serie_final`), previsualització, marcar/desmarcar com a revisades i footer amb el cercador que la pestanya "Resum de la facturació general" — únicament canvia l'informe que es genera en prémer "Generar informe". Requereix el canvi de backend del mateix dia (`generate_register_billing_summary` ara accepta `serie_final_from`/`serie_final_to`/`prefix`, a més del `id`/`date_range` que ja acceptava).
    - Lògica compartida extreta a la funció `useBillingSummaryRange()`, instanciada un cop per pestanya, per no duplicar tot el flux de previsualització/revisió/generació entre les dues.
    - El botó "Resum de la facturació general" a `/billing/reports` ara només es mostra quan el `ConfigProject` `general_billing_summary_preview_enabled` està actiu (abans sempre era visible, independentment del valor del config).
    - Paginació per scroll a la taula de previsualització: es mostren 50 factures inicialment i se'n carreguen 50 més en apropar-se al final del scroll, per no penjar el navegador quan la cerca retorna molts resultats. Es reinicia a 50 en canviar de pestanya (Es generaran/Excloses/Perdudes/Ja revisades) o en tornar a cercar.
    - Fix visual: la insígnia "No revisada" es sobreposava a la capçalera de la columna "Revisada" en fer scroll (capçalera fixada sense `z-index` per sobre de les files). Augmentada també l'alçada màxima de la taula.
#### CLAIM REQUEST
    - S'ha recuperat el poder modificar els passos de la gestió de impagats. Amb això, s'ha afegit poder lligar unes tarifes a cada pas de la gestió
    - A la gestió de impagats, si al pas es detecten tarifes relacionades, es podrà generar factures de despeses relacionades

### CHORE
#### CLAIM REQUEST
    - Si no et trobes al pas ACTUAL de la gestió (no has finalitzat el pas) no podràs tocar res dels altres passos: Generar informes, factures, processos, ordres...

## [25-08-2026]

### FIX
#### CONTRACT (`ContractDetail.vue`, `PinnedContractBasicInfo.vue` — el dia de remesa no desapareixia en esborrar-lo)
    - Requereix el canvi de backend del mateix dia (`ContractSerializer.update()`). En esborrar el millor dia de remesa es veia el valor vell fins que recarregava tota la fitxa.
    - El valor s'amaga abans del `confirm()` i es desa sense recarregar el contracte. Si es cancel·la, es restaura.

## [24-08-2026]

### FEAT
#### COMMUNICATION (`CommunicationProcessCreation.vue`, `useConfigStore.ts` — valor per defecte del checkbox "Adjuntar el document de reclamació al correu electrònic" configurable per client)
    - El checkbox afegit el 20-08-2026 al pas 6 (Resum) del procés de comunicacions sortia sempre marcat per defecte (`ref(true)`), sense cap manera de configurar-ho per client. Requereix el canvi de backend del mateix dia (nou `ConfigProject` `ATTACH_CLAIM_DOCUMENTS_ENABLED`, migració `0127_add_attach_claim_documents_enabled_config.py`).
    - Nou estat `attachClaimDocumentsEnabled` i acció `fetchAttachClaimDocumentsEnabled()` a `useConfigStore.ts`, seguint el mateix patró (i mateixa caché a `localStorage` via `$ConfigProjectApiService`) que `ovEnabled`/`documentSignEnabled`/`acaNotificationEnabled`.
    - `CommunicationProcessCreation.vue` crida `fetchAttachClaimDocumentsEnabled()` en muntar-se i, amb un `watch` sobre `attachClaimDocumentsEnabled` (`immediate: true`), assigna aquest valor a `attachClaimDocuments` un cop resolt. El checkbox segueix sempre visible per a processos de gestió d'impagats i l'usuari pot canviar-ne el valor manualment abans de desar; només canvia l'estat inicial amb què es mostra.
#### COMMUNICATION (CommunicationRegion.vue, communication-api.js, index.vue — nova opció "Retornar Carta")
- No existia la opció de marcar una comunicació com a "Retornada" quan una carta postal no arriba a recollir-se
- Nova opció "Retornar Carta" al desplegable d'opcions de `CommunicationRegion.vue` visible només quan la comunicació té el canal "Adreça postal".
- Confirmació amb el `confirm()` del navegador. En confirmar, crida el nou mètode `returnLetter()` de `communication-api.js` (`POST .../return-letter/`, requereix el canvi de backend del mateix dia).

## [21-08-2026]

### FIX
#### GENERAL (`SupplyPointRegion.vue`, `PriceRateRegion.vue`, `ProductRegion.vue` — el contingut de la regió quedava tapat en obrir una subregió)
    - El fix del 20-08-2026 va convertir el panell `#subregion` en `fixed top-0 right-0 w-[48vw]` (overlay) i, a canvi, cada regió ha d'aplicar `mr-[48vw]` al seu contenidor principal quan la subregió és oberta perquè el contingut es reflueixi a la meitat esquerra en lloc de quedar-hi a sota. Aquestes tres regions es van quedar sense la contrapartida: el panell s'obria correctament però el detall de sota conservava l'amplada sencera i quedava mig amagat rere l'overlay.
    - Afegit `transition-all duration-500 ease` + `:class="{ ..., 'mr-[48vw]': SubRegion }"` al `div` principal, exactament el mateix patró que ja tenien `ContractRegion.vue` i `InvoiceRegion.vue`.
    - Repassats tots els components amb `id="subregion"` i `w-[48vw]`: aquests tres eren els únics que no aplicaven cap marge.
#### CONTRACT (`price-rates.vue`, `locales/*` — la "tarifa BOP" mostrava la data del BOE en lloc del número)
    - La secció de tarifa BOP afegida el 19-08-2026 mostrava `Publication.boe_date`, però el valor identificatiu que es vol veure (i que surt al PDF del contracte) és el número de BOE. Requereix el canvi de backend del mateix dia a `get_contract_tarifa_bop()` (`contract/utils/contract_service.py`), que ara prioritza `Publication.boe_number` i cau a `boe_date` només quan no està informat; el fallback és necessari perquè bona part de les publicacions existents encara no tenen el número entrat i, sense ell, el camp quedaria buit a tots els contractes.
    - `pages/contract/contracts/[id]/price-rates.vue`: `getBopDate()` passa a `getBopValue()` i aplica el mateix criteri que el backend sobre `price_rate.billing_range_active.publication` (`boe_number` net d'espais, i si és buit o nul, la data). No calia cap canvi de serialitzador: `PublicationMinimalSerializer` ja exposa `boe_number` i `boe_date`, i la cadena `ContractPriceRateSerializer` → `PriceRateSerializer` → `BillingRangeSerializer` → `publication` ja els feia arribar al front.
    - La data del fallback es formata amb `formatDate` (`utils/date.ts`, `dd/mm/aaaa`). Abans es pintava el valor cru de DRF (`aaaa-mm-dd`), de manera que la línia superior "Valor BOE aplicat actualment" (que ve de `contract.tarifa_bop`, ja formatada pel backend amb `%d/%m/%Y`) i la línia de cada tarifa mostraven la mateixa data amb dos formats diferents.
    - `ContractTabs.vue` (pestanya de tarifes, només lectura) no necessita cap canvi: pinta directament `contract.tarifa_bop`, que ja arriba calculat amb el criteri nou.
    - Traduccions (`ca`/`es`/`en`/`gl`) a `contract_block`: `bop_tariff_current` passa de "Data BOE aplicada actualment" a "Valor BOE aplicat actualment" i `bop_tariff_no_date` de "Sense data BOE" a "Sense dada BOE", perquè el que es mostra ja no és necessàriament una data. Els noms de les claus es mantenen per no tocar-ne els usos.

### CHORE
#### BILLING
    - A les possible factures no facturades s'ha afegit un buscador
#### SETTINGS
    - S'han bloquejat canvis a molts dels config importants

## [20-08-2026]

### FEAT
#### COMMUNICATION (`CommunicationProcessCreation.vue`, `CommunicationRegion.vue` — opció per no adjuntar el document de reclamació al correu d'impagats)
    - Requereix el canvi de backend del mateix dia (nou camp `CommunicationFile.attach_to_email` i nou camp write-only `attach_claim_documents` al procés). Fins ara els tres documents que genera el flux d'impagats (factura impagada, full de pagament i document del pas) s'adjuntaven sempre al correu, sense cap control des de la interfície.
    - Nou checkbox "Adjuntar el document de reclamació al correu electrònic" al **pas 6 (Resum)**, visible només quan el procés és de gestió d'impagats (`objectSearchData.entity === 'claimrequest'`), just abans de prémer "Enviar". Envia `attach_claim_documents` a la crida de creació del procés.
    - Implementat com a `ref` del pare (mateix patró que `attachInvoices`) i no dins `finalData`: `CommunicationProcessCreationFinalMessage.vue` (pas 5) reconstrueix `finalData` a partir d'una llista blanca de camps, de manera que qualsevol camp nou que hi viatgés quedaria esborrat en passar pel pas 5. `save()` llegeix el valor directament del `ref`, així que no depèn de cap pas intermedi.
    - `CommunicationRegion.vue`: el tab de documents d'una comunicació llistava tots els fitxers actius sense distingir-ne cap, de manera que el document exclòs hi apareixia igualment i feia pensar que s'enviaria. Ara es filtren els fitxers amb `attach_to_email === false`, en l'únic punt on s'assigna `documents` (la resta d'accions del tab hi passen per `getData`). Comparació estricta a posta: si el camp no arribés al payload, els fitxers es continuarien mostrant en lloc de desaparèixer tots. No calia cap canvi de backend perquè `CommunicationFileSerializer` ja fa servir `fields = '__all__'`. Si tots els fitxers quedessin exclosos, el tab ja té estat buit propi (`common.no_records`).
    - Noves claus de traducció (`ca`/`es`/`en`/`gl`): `common.attach_claim_documents_to_email` i `informative_block.info_attach_claim_documents`.

#### CONTRACT (`useConfigStore.ts`, `pages/contract/aca-documents/index.vue` — amagar el botó "Bonificacions pendents d'enviar" si l'ACA no té l'enviament de notificacions activat)
    - El botó de la pàgina de documents ACA que obre `ACABonificationsPendingRegion` només depenia dels permisos de l'usuari (`permissions?.can_view`), sense cap relació amb si l'entitat té activat l'enviament de notificacions a l'ACA. Requereix el canvi de backend del mateix dia (nou `ConfigProject` `aca_notification_enabled`).
    - Nou estat `acaNotificationEnabled` i acció `fetchAcaNotificationEnabled()` a `useConfigStore.ts`, seguint el mateix patró (i mateixa caché a `localStorage` via `$ConfigProjectApiService`) que `ovEnabled`/`documentSignEnabled`.
    - `pages/contract/aca-documents/index.vue` crida `fetchAcaNotificationEnabled()` en muntar-se, un cop confirmats els permisos, i el botó ara és `v-if="permissions?.can_view && configStore.acaNotificationEnabled"`.
#### ROUTE (`AddNewRoutePosition.vue` — camp "Observació del lector" a la visualització/edició d'una posició de ruta)
    - No hi havia cap manera de veure, d'un cop d'ull, quines observacions del lector (si n'hi ha) s'havien registrat en cada posició de ruta.
    - Ara es mostra un camp de text a la visualització/edició d'una posició de ruta, amb el títol "Observació del lector" `reader_observation` del `RoutePosition` corresponent.
    - Noves claus de traducció (`ca`/`es`/`en`/`gl`): `common.reader_observation`.
#### BILLING
    - S'ha afegit un informe en prefactura per mostrar els contractes sense ACA amb el seu consum facturat

## [19-08-2026]

### FEAT
#### CONTRACT
    - 'change-tenant' & 'surrogate' Al fer un canvi de llogater ara permet afegir tipus de documentació des de configuració i, al detectar valors, al propi component del canvi de llogater permet seleccionar la documentació que es vol afegir i més tard, un cop guardat els canvis, afegeix aquesta documentació al tab de contract documentation amb un petit 'chivato' d'on arribar aquest document. Els mateixos canvis s'han aplicat a subrogació tot i que el tema de la documentació ja estava mig fet.

#### BILLING (`ClaimRequestEdit.vue` — moure el resum de contractes/pagaments/import seleccionats a la barra inferior)
    - El resum (nombre de contractes, pagaments i import) del filtratge de reclamacions es mostrava en una caixa pròpia a la part superior del formulari, separada de la barra rosada fixada al peu on ja hi ha els botons de navegació ("Anterior"/"Següent"/"Cercar"/"Desar"), a diferència del procés similar de `SEPAManagementEdit.vue`, on el resum de la cerca (import total, pagaments seleccionats, anomalies, fitxers SEPA) ja viu dins la pròpia barra inferior.
    - S'elimina la caixa superior (`bg-white border border-sky-300 ...`) i el seu contingut (`activeContractsSummary`, `totalSelectedPayments`) es mou dins la barra `bg-fuchsia-100` del peu, en un bloc `grid auto-cols-max grid-flow-col` a l'esquerra dels botons d'acció, seguint el mateix patró visual que `SEPAManagementEdit.vue`.
    - L'animació `animate-stats-box-ping` (ja existent, disparada pel `watch` sobre `activeContractsSummary`) s'aplica ara a tota la barra inferior en lloc de la caixa superior desapareguda.

#### SERVICE (`ClusterRegion.vue`, `ClusterEdit.vue` — marcar en vermell les boquilles amb el punt de subministrament tallat)
    - Ni a la visualització ni a l'edició d'una bateria hi havia manera de veure, d'un cop d'ull, quines boquilles tenien el subministrament tallat sense obrir cada punt de subministrament un a un.
    - El senyal real d'un tall és l'`status` del propi `SupplyPoint` (el backend el canvia automàticament al crear un `SupplyCut`, vegeu canvi de backend del mateix dia); es descarta un primer intent basat en `SupplyCutApiService` (consulta N+1 per boquilla contra `/service/supply-cut/list/`) perquè aquest endpoint fa servir `SupplyCutMinimalSerializer`, que no exposa cap `status.token` comparable.
    - Ara es carrega un únic cop el token `supply_point_status_cut_token` (= `tallat`) via `$ConfigProjectApiService.get(...)` (mateix patró ja usat a `ConnectionDetail.vue` amb `activeToken`) i es compara de forma síncrona amb `nozzle.supply_points[0].status_token`, sense cap crida addicional per boquilla.
    - Les boquilles afectades (incloses les dividides) es ressalten amb fons vermell i una icona `fa6-solid:droplet-slash` amb tooltip.
    - Requereix el canvi de backend del mateix dia (`service/serializers/cluster_nozzle_serializer.py`): fins ara `ClusterNozzleSerializer.get_supply_points` no retornava `status_token`/`status_name`/`status_color` del punt de subministrament.
    - Noves claus de traducció (`ca`/`es`/`en`/`gl`): `service_block.active_supply_cut_warning`.

#### CONTRACT (`ContractTabs.vue`, `price-rates.vue`, `PublicationDetail.vue` — mostrar i modificar la "tarifa BOP" del contracte, i habilitar l'edició de `Publication`)
    - No hi havia cap manera, des del front, de veure quina data BOE es faria servir com a "tarifa BOP" al PDF del contracte, ni de saber quina tarifa de consum n'era la referència, ni de canviar-ho. Requereix el canvi de backend del mateix dia (`ContractPriceRate.is_bop_reference`, camp calculat `tarifa_bop` a `ContractSerializer`, endpoint `set-bop-price-rate`).
    - `pages/contract/contracts/[id]/price-rates.vue`: nova secció que mostra `contract.tarifa_bop` i llista cada tarifa de consum del contracte amb un botó "Marcar com a referència BOP" (o una insígnia si ja ho és); crida el nou mètode `$ContractApiService.setBopPriceRate(id, contractPriceRateId)` (`PUT .../set-bop-price-rate/`).
    - `ContractTabs.vue`, pestanya de tarifes (`activeTab === 'price_rate'`): mateixa informació en mode només lectura — data BOE actual del contracte i insígnia "Referència BOP actual" a la tarifa corresponent; l'edició es manté centralitzada a `price-rates.vue` per no duplicar la lògica d'escriptura.
    - Noves claus de traducció (`ca`/`es`/`en`/`gl`) a `contract_block`: `bop_tariff`, `bop_tariff_current`, `bop_tariff_set_reference`, `bop_tariff_reference`, `bop_tariff_no_date`, `bop_tariff_updated`, `bop_tariff_update_error`.
    - Detectat en revisar un contracte que la seva referència BOP apuntava a una `Publication` sense `boe_date` informat, i que **no hi havia cap opció al front per editar una `Publication`** un cop creada: `AddPublication.vue` només servia per crear-ne (el suport d'edició que hi havia era codi mort — el prop `object` no es feia servir enlloc del formulari, `getData()` no arribava a omplir cap camp). Ara accepta un prop `id`: si té valor, carrega les dades reals i el `save()` fa `PUT` en lloc de `POST`.
    - `PublicationDetail.vue` (ja s'obria com a subregió en clicar el nom d'una publicació des del detall d'un `BillingRange`) incorpora un nou botó "Modificar" que substitueix la vista de lectura per aquest mateix formulari amb l'`id` actual, i torna a la vista de lectura en desar. Nova clau `pricing_block.edit_publication`.
    - Abast deliberadament mínim: no s'ha afegit cap llistat/pàgina propi de `Publication` (`/pricing/publications`); només s'hi arriba des d'un `BillingRange` que la faci servir.

#### CONTRACT (`ACABonificationsPendingRegion.vue` — valors per defecte als camps de revisió abans d'exportar a l'ACA)
    - Els 4 camps de revisió interna de cada sol·licitud pendent ("Autoritza revisar dades CENS", "Resultat tràmit", "Censat a l'adreça" i "Persones censades") es mostraven sempre buits/sense marcar fins que l'usuari els omplia un a un, encara que la majoria de vegades el valor esperat és previsible.
    - Ara es precarrega un valor per defecte, només visual (no es desa res fins que l'usuari interactua amb el camp en qüestió): "Autoritza revisar dades CENS" marcat; "Resultat tràmit" i "Censat a l'adreça" amb la primera opció real de cada llista; "Persones censades" amb el mateix valor que "Nombre de persones a aplicar".

### FIX
#### CONTRACT (`ACABonificationsPendingRegion.vue` — botó "Seleccionar tots" visible sense cap sentit)
    - El botó no tenia cap condició de visibilitat: apareixia igual mentre la llista encara carregava i quan no hi havia cap sol·licitud pendent (`items.length === 0`), sense cap efecte útil en cap dels dos casos.
    - Ara només es mostra quan ja ha acabat de carregar i hi ha almenys un registre (`v-if="!pending && items.length > 0"`).

#### PRICING (`AddPublication.vue` — 500 en modificar una `Publication` amb el camp "Referència" buit)
    - En habilitar l'edició (canvi anterior d'aquest mateix dia), modificar la `Publication` `id=1` petava amb `IntegrityError: duplicate key value violates unique constraint "pricing_publication_reference_key"`.
    - Causa: `Publication.reference` és `unique=True` però `null=True`; aquesta publicació en concret tenia `reference=NULL`, i `getData()` la carregava al formulari amb `response.reference ?? ''` — convertint el `null` en un string buit. En desar, s'enviava `reference: ''`, que xocava amb una altra `Publication` (`id=3`) que ja tenia `reference=''` guardat (Postgres tracta `''` com un valor real als índexs únics, no com `NULL`).
    - Corregit a `save()`: `reference` (i `boe_number`, mateix risc encara que sense constraint únic) s'envien com `null` quan són buits, no com a string buit, evitant la col·lisió i permetent que múltiples `Publication` sense referència coexisteixin (Postgres sí permet diversos `NULL` en una columna `unique`).

## [18-08-2026]

### FIX
#### BILLING/CONTRACT
    - Deixar modificar la ultima lectura del contracte tot i que estigui trepitjant un període, ja que aquesta lectura quedaria fora dels límits d'una facturació normal

### FEAT
#### CONTRACT (`pages/contract/aca-documents/index.vue` — nova regió "Bonificacions pendents d'enviar" a l'ACA)
    - A la pàgina "Bonificacions ACA" (existent, gestió de `ACADocument`) no hi havia cap manera de veure quines bonificacions d'ampliació de trams s'havien afegit a un contracte i encara no s'havien notificat a l'ACA, ni de generar el fitxer normatiu de sol·licitud. Requereix el canvi de backend del mateix dia (nou model `ACABonificationRequest` i endpoints `contract/aca-bonification-request/`).
    - Nou botó "Bonificacions pendents d'enviar" al costat de "Pujar document", que obre la mateixa regió lateral amb el nou component `components/organisms/ACABonificationsPendingRegion.vue`.
    - `ACABonificationsPendingRegion.vue`: llistat de sol·licituds pendents (contracte, titular, nombre de persones —de només lectura, ve de la variable de la bonificació, no editable aquí—, "Autoritza revisar CENS", i tres camps de revisió interna abans d'enviar: "Resultat tràmit" (desplegable, llista de valors 5.3/5.4 de l'ACA), "Censat a l'adreça" (desplegable, llista 5.5) i "Persones censades" (numèric, llista 5.6)), amb selecció individual/"Seleccionar tots".
    - En lloc de generar i descarregar el fitxer directament, el botó ara obre un modal de **previsualització** (`$ACABonificationApiService.previewExport`, `POST .../preview-export/`, no persisteix res al backend) que mostra el nom i el contingut exacte del fitxer (línies de 350 caràcters) abans de confirmar, amb un avís explícit: *"En generar el fitxer, les bonificacions seleccionades es marcaran com a notificades a l'ACA i no es podran tornar a incloure en un altre enviament"*. Només en confirmar des del modal es crida `generateExport` (`POST .../generate-export/`), que sí descarrega el fitxer i marca les sol·licituds com enviades.
    - Nou `plugins/api/contract/aca-bonification-api.js` (cal registrar-lo explícitament a `nuxt.config.ts`, els plugins d'aquest projecte no s'autodescobreixen — oblit inicial que provocava `$ACABonificationApiService is not defined` fins que es va afegir a la llista).
    - Noves claus de traducció (`ca`/`es`/`en`/`gl`): `common.aca_bonifications_pending`, `num_persons_to_apply`, `authorizes_census_review`, `generate_export_file`, `preview_export_file`, `aca_generate_warning`, `aca_result`, `censat_adreca`, `num_persons_censats`, `no_pending_aca_bonifications`.

#### CONTRACT (`BonificationDetail.vue` — indicador d'estat "Enviat/Pendent d'enviar a ACA" a la pestanya Bonificacions del contracte)
    - Fins ara, un cop afegida una bonificació d'ampliació de trams a un contracte, no hi havia cap manera de saber des de la pròpia fitxa del contracte si ja s'havia notificat a l'ACA o encara estava pendent.
    - `BonificationDetail.vue` (reutilitzat tant a `ContractTabs.vue` com des de la pàgina de bonificacions): quan `item.is_aca_bonification` és cert (nou camp del `BonificationSerializer`, backend), es mostra una etiqueta al costat del nom de la bonificació — groga "Pendent d'enviar a ACA" o verda "Enviat a ACA" segons `item.sent_to_aca`.
    - Ajustat el `padding` de l'etiqueta (`px-3 py-1`, abans `px-2 py-0.5`) i afegit `whitespace-nowrap`: amb el padding original el text sortia de la rodona.
#### BILLING
    - S'ha afegit un nou botó que permet trobar nous configs en cas d'haver-ho modificacions al use aca

#### READING (`ReadingBatchCreate.vue` — codi i nom amb any/mes en triar plantilla)
    - En triar una plantilla al pas de creació del lot de lectures, el codi i el nom es copiaven tal qual de la plantilla, sense indicar el període al qual pertanyien.
    - Ara s'hi afegeix automàticament l'any i el mes actuals, calculats a partir de la data d'actual. Els camps segueixen sent editables abans de continuar.

## [17-08-2026]

### FEAT
#### BILLING (`PaymentDetail.vue`, `PaymentRegion.vue` — relació amb el compromís de dipòsit quan el pagament ve d'una factura, i alineació del camp "Venciment")
    - A `PaymentDetail.vue` el camp "Compromís de dipòsit" només es mostrava (`v-else-if`) quan el pagament NO tenia factura i tenia `commitment_deposit` informat directament (FK); un pagament que ve d'una factura (`data.invoice`) pertanyent a un compromís de dipòsit via relació M2M `CommitmentDeposit.invoices` (sense FK directa al pagament), no el mostrava mai, a diferència d'`InvoiceDetail.vue`, que ja resol aquest cas amb `$CommitmentDepositApiService.getByInvoice` de forma independent del camp factura.
    - A `PaymentRegion.vue`, dins `getData()`, s'afegeix una nova resolució `commitmentDeposit` (ref, objecte complet): usa `data.commitment_deposit` si existeix, i si no però hi ha `data.invoice`, el cerca amb `getByInvoice(invoice.id)` (mateix patró que `InvoiceRegion.vue`). Es passa a `PaymentDetail.vue` com a nova prop `commitmentDeposit`, mostrada com a camp independent (no lligat a l'`v-else-if` de factura), igual que a `InvoiceDetail.vue`.
    - El càlcul del fraccionament concret (`paymentCommitment`, camp "Fraccionament") ara reutilitza aquest `commitmentDeposit` ja resolt en lloc de dependre només de `data.commitment_deposit`; si el pagament no prové d'un fraccionament generat via `add_wallet_payment` (el `due_date` no coincideix exactament amb cap `PaymentCommitment.due_date`), aquest camp es manté ocult però ara sí es mostra la relació amb el compromís de dipòsit.
    - El botó/enllaç del camp "Fraccionament" a `PaymentDetail.vue` ara navega amb `paymentCommitment.commitment_deposit.id` (ja ve dins la resposta de `PaymentCommitmentSerializer`) en lloc de `data.commitment_deposit.id`, ja que aquest últim pot no existir en el cas anterior.
    - Es corregeix l'alineació del text "Venciment" a `PaymentDetail.vue`: la fila editable (input de data) feia servir una graella pròpia (`grid-cols-[107px,1fr]`, `mt-4`) diferent de la resta de camps (`FieldDetail`, `grid-cols-[120px,1fr]`), fent que l'etiqueta no quedés alineada amb "Estat" (que usa `FieldDetail` amb `mt-3`); s'iguala l'amplada de columna (`120px`) i el marge superior (`mt-3`, en lloc de `mt-4`) al de la cel·la d'"Estat".
    - El camp de data en si (`AtomsInputDate`) també quedava desalineat respecte al valor d'"Estat" (`AtomsColorBadge`, `py-0.5`), ja que l'input fa servir per defecte `py-2` (classe global `.input`) i el seu contenidor `mb-4`, fent-lo molt més alt. S'afegeix una nova classe modificadora `compact-date` a `InputDate.vue` (`margin-bottom: 0`, `padding-top/bottom: 0.125rem` igual que `ColorBadge`) i s'aplica al costat de `no-border` a `PaymentDetail.vue`, amb el contenidor de la fila fixat a `h-[25px] items-center` com el d'"Estat".
    - El camp "Fraccionament" (compromís de pagament) a `PaymentDetail.vue` no era clicable quan `isSubRegion` és cert (és a dir, quan ja hi ha 2 regions obertes i no se'n pot anidar una tercera): es mostrava com a text pla. Ara, en aquest cas, es mostra amb `AtomsRedirectButton` per obrir el compromís de dipòsit en una pestanya nova, en lloc de deixar-lo sense cap enllaç.

#### CONTRACT (`pages/contract/contracts/index.vue` — cerca de contractes per email i per IBAN del titular)
    - Al llistat de contractes, dins els filtres avançats, no hi havia manera de cercar per email ni per IBAN relacionats amb el contracte; només existia la cerca per adreça (`search_by_address`/`search_all_address`).
    - S'afegeixen dos nous botons a la barra de filtres (mateix comportament que el botó de cerca per adreça amb la icona de casa + "+"): un amb icona "@" (`fa6-solid:at`) i un altre amb icona de banc (`fa6-solid:building-columns`), que mostren/amaguen sengles camps de text (`showEmailSearch`/`showIbanSearch`) dins l'àrea de filtres oberta, en lloc del component estructurat `AtomsInputAddressSearch` (no té sentit per un valor de cerca simple).
    - Els nous valors (`searchEmailInput`/`searchIbanInput`) es connecten a tot el flux ja existent: cerca amb `debounce`, paginació, ordenació, `resetFilters`, marcador `isFiltered`, exportació a Excel i persistència de l'estat de cerca a `sessionStorage`.
    - `ContractApiService.getAll`/`exportExcel` (`plugins/api/contract/contract-api.js`) accepten ara `search_email`/`search_iban`, afegits al final de la llista de paràmetres (per no trencar les altres crides existents que els passen posicionalment: `PersonContractsList.vue`, `AddContracts.vue`, etc.) i enviats com a query params `search_email`/`search_iban` a `GET /contract/contract/`.
    - Noves claus de traducció `contract_block.search_email_info`/`contract_block.search_iban_info` (ca/es/en/gl).
    - Requereix el canvi de backend del mateix dia (`contract/filters/contract_filter.py`) que interpreta aquests dos nous query params; sense ell la cerca no filtra res.
    
#### BILLING (nou `ReaderAlertRegion.vue` — veure les alertes de lector pendents d'un lot de lectures, i els contractes afectats)
    - Als passos "Configuració" (`ReadingBatchSetup.vue`) i "Lectures" (`ReadingBatchReadingsSummary.vue`) de l'edició d'un lot de lectures, no hi havia cap manera de veure quines lectures tenien una alerta de lector (`Reading.reader_alert`: "Absent", "Comptador parat", "Frau"...) sense obrir-les una a una; l'únic comptador existent (`readings_with_reader_alerts`) era agregat i no permetia distingir-les ni consultar-ne el detall.
    - Als dos passos s'afegeix una fila "Alertes de lector" amb el total (suma del nou `counters.reader_alert_breakdown`, vegeu canvi de backend del mateix dia) i una icona d'alerta (`fa6-solid:triangle-exclamation`, vermella) clicable, que emet `show-subregion` amb `{ type: 'reader-alerts' }`.
    - `ReadingBatchEdit.vue` escolta aquest event i obre el panell lateral dret ja existent al component (fins ara només usat, comentat, per `ChangeStatus`), ara mostrant `reader_alert_breakdown` a través del nou component `components/molecules/ReaderAlertRegion.vue`. El panell passa de `w-1/2` a `w-[90%]` mentre es mostra aquesta regió (com la resta de regions de detall de l'aplicació), per deixar espai al llistat de contractes.
    - `ReaderAlertRegion.vue` (nou): primer nivell amb la llista d'alertes per separat (nom + comptador, tal com ve de la BBDD, sense traduir — a diferència dels tokens `reading_alert_*`, aquests noms ja són text introduït per l'operador/lector); en clicar-ne una es demanen les lectures d'aquell tipus concret (`$ReadingApiService.getReadingsByBatchMinimal(batch_id, page, 'reader_alert=<nom>')`, paginat amb `Pagination.vue`) i es reutilitza `AtomsReadingEdit`/`ReadingListDetail` (ja permeten obrir el contracte/titular/punt de subministrament) per obrir el contracte de cada lectura en una subregió apilada (`OrganismsContractRegion`, mateix patró de tres nivells ja usat a `ReadingBatchSummary.vue`).
    - Descartat un primer disseny (una fila per cada tipus d'alerta directament al llistat de comptadors, sense pas intermedi) a petició, en favor d'aquest de fila única + regió amb desglossament + subregió de contractes.

#### CONTRACT (`ContractRequestTermination.vue` — avís d'alerta de lector a la lectura inicial/de tall del pas "Situació actual")
    - Al pas 6 de la sol·licitud de contractació ("Situació actual"), ni la targeta de "Lectura inicial del nou contracte" ni el bloc de "Lectura de tall" (baixa) avisaven quan l'última lectura del comptador tenia una alerta de lector (lectura 0, negativa, inusual, consum baix...) associada a la BBDD.
    - S'afegeix una icona d'alerta (`fa6-solid:triangle-exclamation`, vermella) al costat del valor de la lectura a totes dues seccions, visible quan `last_reading.alert`/`previous_readings[sp].alert` és cert. En passar-hi el cursor es mostra un tooltip personalitzat (no l'atribut `title` natiu, poc fiable entre navegadors) amb el missatge concret (`alert_notes` si n'hi ha, si no el nom de l'alerta).
    - Nova funció `translateReadingAlert()`: quan el valor rebut és el token intern (`reading_alert_zero`, `reading_alert_unusual`...) en lloc d'un nom ja llegible, es tradueix via `t('billing_block.' + token)` (claus ja existents a `ca.ts`/`es.ts`), amb el mateix patró que ja fa servir `StatusesNav.vue`; si la clau no existeix, es mostra el text tal qual.
    - Requereix el canvi de backend del mateix dia (`supply_point_serializer.py`, `meter_serializer.py`, `reading_serializer.py`): fins ara aquests endpoints no retornaven el camp `alert`/`alert_notes` de la lectura, de manera que la icona no es podia mostrar encara que la lectura tingués l'alerta a la BBDD.
#### CONTRACT
    - S'ha afegit l'opció de canviar el tipus d'ús i tipus tarifari d'un contracte. Tot això implica nous camps a actualitzar al contracte i una nova funció que genera un nou template de comunicació de canvi de dades al contracte.

### FIX
#### BILLING (`ReadingBatchReadingsSummary.vue` — el llistat de "Lectures sense valor" (i alerta de lector/inactius) es quedava sempre a la 1a/2a pàgina)
    - El `count` que retorna `GET billing/reading-batch/setup/<id>/?readings=no_reading_value` (i `reader_alert`/`inactive_sp`) és el total real de punts de subministrament (p. ex. 90), però el backend pagina de 20 en 20 mentre que el component calculava `totalPages` amb un `perPage` fix de 50 (`Math.ceil(count / 50)`), de manera que els botons de pàgina només arribaven a mostrar 2 de les 5 pàgines reals i el botó "següent" es desactivava abans d'hora — l'usuari només podia veure 40 de les 90 files.
    - `getData()` accepta ara un mode `append`: en lloc de dependre d'un `perPage` fixe, el llistat de "sense valor"/"alerta de lector"/"inactius" passa a carregar-se per scroll infinit: en arribar prop del final del contenidor (`loadMoreOnScroll`) es demana la pàgina següent i s'afegeix als resultats ja mostrats, guiant-se únicament per `result.next` (sense assumir cap mida de pàgina concreta).
    - S'elimina el component `Pagination.vue` d'aquest bloc concret (es manté sense canvis a la resta: assignades, descartades, telecomandament/alerta remota, sense lectura assignar), afegint en el seu lloc un indicador "carregant..." al final del llistat mentre es demana la pàgina següent.
#### BILLING (`MissingReadingEdit.vue`, `ReadingBatchReadingsSummary.vue` — columna de contracte massa estreta)
    - La primera columna de les files de lectures (token del contracte + icona de boca d'incendi + data d'alta) quedava tallada (`truncate`) per manca d'espai.
    - S'eixampla la primera columna de `1.2fr` a `1.8fr` a `MissingReadingEdit.vue` (ambdues variants del grid) i a les 3 capçaleres `sticky` corresponents de `ReadingBatchReadingsSummary.vue`, i es treu el `truncate` de la cel·la per no tallar el contingut.
#### SERVICE (`MeterChangeAdd.vue` — botó "Guardar" bloquejat en canvi de comptador)
    - Corregit un bug pel qual, si es clicava "Guardar" sense haver seleccionat el nou comptador, el botó es quedava carregant.
    - `saveNewMeter()`: ara `saving.value` només es posa a `true` un cop superades les validacions (`isValid()`) i la confirmació, de manera que sempre es restableix a `false` en acabar.
#### BILLING (`PaymentRegion.vue`, `InvoiceRegion.vue` — subregió de Pagament mal renderitzada en obrir-la dins d'una subregió de Factura oberta, al seu torn, des d'un altre Pagament)
    - Mateixa causa arrel que el fix del 12-08-2026 a `SEPARemittanceDetail.vue`: el panell `#subregion` combina `position: fixed` amb l'animació `transform` (`translate-x-0`/`translate-x-full`), i qualsevol element amb `transform` esdevé el *containing block* dels seus descendents `fixed`. Amb tres nivells d'imbricació (`PaymentRegion` → subregió `InvoiceRegion` → subregió `PaymentRegion`), el panell del tercer nivell deixava d'ancorar-se al viewport real i quedava atrapat/mal dimensionat dins del panell del primer nivell.
    - En lloc de canviar l'animació a `right` (com al fix del 12-08-2026), aquí s'embolica el panell `#subregion` (i el panell `#right_page`/`PersonBankSelect` d'`InvoiceRegion`) amb `<Teleport to="body">`: així es renderitzen directament sota `<body>`, fora de qualsevol ancestre amb `transform`, independentment del nivell d'imbricació. L'ordre de muntatge (pare abans que fill) manté el panell més intern per sobre visualment.
    - Nomès s'ha aplicat a `PaymentRegion.vue`/`InvoiceRegion.vue` (el cas reportat); la resta de ~63 components amb el mateix patró `#subregion` es mantenen sense tocar.

## [14-08-2026]

### FEAT
#### BILLING (`SepaValidateModal.vue` — validació de fitxers SEPA)
    - S'ha afegit un nou component `SepaValidateModal.vue` (`components/molecules/SepaValidateModal.vue`) per validar fitxers SEPA.
    - S'ha afegit un nou endpoint `/billing/sepa-validate/` (`$SepaRemittanceApiService.validateFile`) per validar fitxers SEPA.
    - S'ha afegit un nou mètode `validateFile` (`$SepaRemittanceApiService.validateFile`) per validar fitxers SEPA.
#### CONTRACT/ORDER (`ContractRegion.vue`, `OrderRegion.vue` — obrir els informes d'una ordre de treball en una "doble regió" per sobre de la subregió)
    - En visualitzar les ordres de treball des de la pestanya corresponent d'un contracte (`OrderRegion` obert com a subregió dins `ContractRegion`), no es podia obrir el detall d'un informe: `OrderReportList.vue` desactivava el clic sobre el token de l'informe quan `isSubRegion` era cert, i `OrderRegion.showDetail()` feia un no-op en aquest mateix cas.
    - `OrderReportList.vue`: el token de l'informe ara sempre és clicable, independentment de si `OrderRegion` s'està mostrant com a subregió.
    - `OrderRegion.vue`: quan ja s'obre com a subregió, `showDetail()` ja no bloqueja l'obertura d'un detall niat — ara obre una nova "doble regió" (`doubleSubRegion`/`doubleRegionDetailComponent`/`doubleRegionDetailId`), un segon panell fixe (`#double-subregion`, `z-[90]`) que es mostra **per sobre** de la subregió actual amb `OrderReportEdit`, sense tancar la vista de l'ordre.
    - `ContractRegion.vue`: el seu panell `#subregion` es converteix del patró antic `translate-x` (`transform`) al patró `right-0`/`right-[-48vw]` (mateix fix ja aplicat el 12-08-2026 a `SEPARemittanceDetail.vue`), necessari perquè el nou panell `fixed` de la doble regió d'`OrderRegion` no quedi atrapat dins seu (un ancestre amb `transform` esdevé el *containing block* dels seus descendents `fixed`) i s'ancori correctament al viewport.
#### BILLING (`ReadingBatchSummary.vue`, `ReadingBatchEdit.vue` — avís i correcció d'errors parcials en processar/assignar/estimar un lot de lectures)
    - Nou component `components/atoms/PartialErrorsBanner.vue`: banner groc amb comptador i llistat desplegable dels errors retornats pel backend (`last_task_status`/`last_task_errors` del lot, o `status`/`errors` del resultat de la tasca Celery via `$apiManager.checkTask`), amb missatge en català i, quan l'error és corregible (`fixable` + `fix_field`), un botó "Corregeix".
    - `ReadingBatchSummary.vue`: nova region lliscant "Fix Reading Error" (mateix patró visual `role="region"`/`translate-x` que la resta de regions del component) que obre en clicar "Corregeix", carrega el detall de la lectura (`$ReadingApiService.getDetail`) i permet editar-ne la data (`$ReadingApiService.save` → `PUT /billing/reading/{id}/`); en desar, elimina l'error de la llista i refresca tant la llista de lectures (`getData()`) com els comptadors principals ("Total lectures" i desglossament d'avisos) i els pendents (`loadPendingCounters()`).
    - `ReadingBatchEdit.vue`: el mateix banner es mostra també als passos "Configuració" i "Lectures" (tasques `assign_readings_task`/`estimate_readings_task`), llegint `status`/`errors` del resultat del polling a `waitForAssignTask()`.
    - Corregit un bug pel qual, en tornar al pas de resum d'un lot ja processat (`counters_pending` ja rebut per props des del pare), mai s'arribava a consultar `last_task_status`/`last_task_errors` perquè `loadPendingCounters()` (l'única via per obtenir-los) no es cridava en aquest cas.
    - Noves claus d'i18n (`billing_block.partial_processing_errors_*`, `billing_block.reading_id`) a `ca.ts`/`es.ts`/`en.ts`/`gl.ts`.

### CHORE
#### BILLING
    - Reorganitzat el resum de facturació a les prefactures i canviat una mica l'estil.
#### SERVICE (`ConnectionRegion.vue` — nova pestanya "Ordres de treball")
    - S'afegeix una nova pestanya "Ordres de treball", sempre visible, al detall de connexió, que mostra les ordres vinculades a la connexió.
    - `components/molecules/OrderMiniDetail.vue`: nou prop `connection_id`; quan es passa, el llistat es carrega amb `$OrderApiService.getFilterConnection(id)` (mètode ja existent al servei, `GET /order/order/?connection=<id>`, sense usar-se encara des del costat de connexió) en lloc del `getAll` genèric.
    - `ConnectionRegion.vue`: en clicar una ordre del llistat s'obre el seu detall (`OrderRegion`) a la subregió, mateix patró que la resta de pestanyes/entitats vinculades (contracte, factura, etc.).

### FIX
#### CALENDAR (`CalendarTaskEdit.vue` — no es podia assignar una tasca a un usuari concret)
    - Causa arrel: la càrrega d'usuaris (`getUsers()`) estava comentada i `selectedUser` s'inicialitzava filtrant per un codi `'null'` inexistent a la llista (sempre buida), de manera que el selector d'usuari no mostrava mai cap opció; a més, en desar, `user_id` es calculava a partir d'aquest mateix `selectedUser.value.code` trencat.
    - Ara `getUsers()` es crida a `onMounted()` i omple el selector amb `$UserApiService.getAll()`; en editar una tasca ja assignada, `selectedUser` es preompli amb l'usuari real (`detail.user`); en desar, `user_id` s'envia com `null` si `all_users` és cert, o el codi de l'usuari seleccionat en cas contrari.
    - En reiniciar el formulari (nou `id` a `null`) es torna a l'estat "Tots els usuaris" (`all_users = true`, `selectedUser = null`) en lloc de l'assignació trencada anterior.

## [13-08-2026]

### CHORE
#### CONTRACT
    - Al canviar les tarifes d'un contracte o sol. només t'avisava si hi havien tarifes que no coincidien amb les que venien amb el contract type. Ara també avisa si en falta alguna

### FEAT
#### BILLING/READING
    - S'ha afegit una nova opció de moure els subm. sense lectura que siguin de telelectura a un lot manual al cas que estiguin separats.
#### REPORTS (`reports/add.vue` — nous filtres per informes de facturació)
    - S'afegeixen nous filtres per a informes de facturació:
        - `Serie`: selector de series de facturació per a informes de facturació.
        - `Excloure facturació`: selector de facturació per a excloure-la dels informes de facturació.
#### BILLING (`billing/index.vue`, `BillingDetail.vue` — codi i nom editables en iniciar i en post-creació)
    - Ara, un cop seleccionat el facturador, el model mostra els camps `Identificador` i `Nom` precalculats automàticament a partir del `period_type` del facturador (trimestral, semestral, mensual, etc.) i el mes/any actuals (p. ex. `T3/2026`, `S1/2026`, `M8/2026`), editables abans de confirmar.
    - `plugins/services/coredata/config-project-api.js` (`BillingApiService.start()`): ara accepta `token` i `name` opcionals, enviats com a query params junt amb `biller_id`.
    - `components/molecules/BillingDetail.vue`: s'afegeix un botó d'edició (llapis) al costat del nom, al detall de la facturació, que permet editar `Identificador` i `Nom` un cop ja creat el registre, desant amb `PATCH` (`$BillingApiService.patch`).
    - `components/organisms/BillingRegion.vue`: s'ajusta l'espaiat del bloc de botons "Cancel·lar"/"Guardar" i del botó "Consulta Facturació", que quedaven massa junts.

#### BILLING (`MissingReadingEdit.vue`, `ReadingBatchReadingsSummary.vue` — columna "Consum" en estimar lectures i regió de lectures assignades)
    - `MissingReadingEdit.vue`: nova columna "Consum" (`calculated_value`) als llistats de lectures sense assignar, alertes de lector i alertes remotes; en clicar "Estimar" es mostra el valor de consum que ha calculat l'estimació (`response.readings[0].calculated_value`, ja retornat per l'endpoint però abans no es llegia).
    - `ReadingBatchReadingsSummary.vue`: el bloc "Total lectures assignades" ara es pot obrir com la resta de regions (icona d'ull en passar-hi el cursor), mostrant un llistat cercable i paginat de les lectures ja vinculades al lot (contracte, data, lectura, fuita, consum, estimada), reutilitzant l'endpoint existent `$ReadingApiService.getReadingsByBatchMinimal` (el mateix que `ReadingBatchSummary.vue`), sense requerir cap filtre nou al backend.

### MODIFIED
#### BILLING (`ReadingBatchSummary.vue`, `ReadingBatchReadingsSummary.vue` — estandardització visual dels llistats de lectures i pas de scroll infinit a paginació)
    - Totes les llistes de lectures d'aquests dos components (assignades, sense lectura, descartades, telecomandament/alerta remota, alerta de lector/sense valor/inactius) passen de scroll infinit (`@scroll`/`loadMore`) a paginació estàndard amb `Pagination.vue`, com a la resta de llistats de l'aplicació.
    - Capçaleres adaptades a l'estil visual de `DataTable.vue` (`text-xs font-medium uppercase tracking-wider text-gray-400`, amb `truncate`/`min-w-0` per evitar que un text llarg de capçalera eixample la columna) sense arribar a fer-hi servir el component `DataTable.vue`: als llistats amb `AtomsReadingEdit`/`AtomsMissingReadingEdit` (files amb graella pròpia interna) la capçalera manté el mateix `grid-cols`/`gap-2`/`px-4` que l'àtom, ja que `DataTable.vue` porta un `gap`/`padding` fixos (`gap-3 px-1 py-1`) que no hi quadren pixel a pixel; als llistats de cel·les simples (descartades, assignades) sí que s'utilitza `DataTable.vue`.

### FIX
#### BILLING (`ReadingBatchSummary.vue` — capçalera de columnes desalineada de les files un cop apareixia la barra de scroll)
    - Causa arrel: la capçalera del llistat de lectures era germana del contenidor `overflow-y-auto` de les files, en lloc d'estar-hi a dins; quan la llista tenia prou files per mostrar la barra de desplaçament vertical, aquesta consumia amplada només al contenidor de files (no al de la capçalera), desquadrant progressivament totes les columnes cap a la dreta (efecte més visible a les últimes columnes).
    - Es mou la capçalera dins del mateix contenidor `overflow-y-auto` que les files (primer element), amb `sticky top-0 z-10 bg-white` perquè es mantingui fixa visualment en fer scroll — mateix patró que ja fa servir `DataTable.vue` internament (capçalera i files al mateix contenidor). Aplicat també a les tres seccions equivalents de `ReadingBatchReadingsSummary.vue` que compartien el mateix patró.
#### BILLING (`ReadingEdit.vue` — columna "Tipus" eixamplava la resta de columnes amb valors llargs)
    - Una cel·la de graella CSS no s'encongeix per sota de l'amplada del seu contingut per defecte (`min-width: auto`); un valor llarg a `reading.origin` (p. ex. "TELECONTROL") podia forçar l'eixamplament de tota la columna i descol·locar les següents. S'afegeix `min-w-0` a la cel·la i `truncate` (amb `title` per veure el valor complet en passar el cursor) a l'`span`.
#### BILLING (`ReadingBatchSummary.vue` — error en obrir "Lectures amb punt subm. inactiu": `Cannot read properties of undefined (reading 'token')`)
    - La regió de lectures pendents (`showPendingReadings`) accedia directament a `supply.contracts[0].token`/`.id` sense comprovar que el punt de subministrament tingués cap contracte; alguns punts de subministrament inactius no en tenen, provocant l'error en renderitzar. Ara es mostra `-` quan no hi ha cap contracte, igual que ja es feia per al titular a la mateixa columna.

## [12-08-2026]

### FIX
#### BILLING (Pressupost de baixa — SelectPaymentType sense mètode/IBAN)
    - En generar el pressupost des d'una sol·licitud de baixa (`contract_termination_request`), `AddInvoiceBudget.getData()` només llegia `data.payment`. La sol·licitud de baixa no té `payment` propi (el té el contracte), a diferència de l'alta (`contract_request`), així que el selector de pagament i l'IBAN SEPA quedaven buits tot i tenir-los el contracte.
    - Ara, si `entity === 'contract_termination_request'`, es fa servir `data.contract.payment` (fallback a `data.payment`). Mateix comportament de preompliment que a l'alta.

### CHORE
#### GENERAL (`InputTextarea.vue` — alçada configurable del textarea)
    - Nou prop `rows` (per defecte `1.5`, accepta decimals per l'alçada mínima). La resta d'usos sense `rows` es mantenen ~com abans (una línia i mig), no a 2 files fixes.
    - L'auto-resize ja no col·lapsa el camp buit a una sola línia: respecta `Math.max(scrollHeight, alçada mínima per rows)`.
    - `ObservationList.vue`: passa `:rows="1.25"` al camp d'afegir observacions.
#### CONTRACT (`data-change.vue` — no es persistia el mètode de pagament si el contracte no en tenia)
    - En editar un contracte sense `payment` (o amb `GeneralPayment` sense `type`), el canvi de mètode es detectava i es creava el `GeneralPayment`, però no es vinculava al contracte (`payment_id`), perquè `needsContractSave` només es disparava amb canvi d'IBAN.
    - A més es podia fer un doble save del payment (`paymentToUpdate` + `payment_options`).
    - Ara: snapshot buit si no hi ha payment, un sol save, i vincle al contracte quan no n'hi havia o canvia tipus/IBAN.

#### BILLING CONFIG ACA
    - S'ha modificat el index de modificació aca per permetre modificar els tokens per explotació (per casos de clients amb multiexplotació) i poder seleccionar multiples tokens
    - Les pestanyes d'explotació amb canvis sense desar mostren la icona en vermell i un ping quan s'està a una altra pestanya, per avisar que cal tornar-hi a desar

#### CONTRACT (`ContractTabs` / `ContractRegion` — historial de modificacions triplicat)
    - La pestanya de modificacions barrejava `data_changes` del contracte amb `/logs/`, que ja inclou els mateixos data-changes → es veia "Mètode de pagament", `payment_type` i `payment` (GeneralPayment ID) a l'hora.
    - Ara només es mostren logs amb `source !== 'data_change'`, i s'oculta el log tècnic `payment` si ja hi ha un data-change de mètode/IBAN al mateix guardat.

## [11-08-2026]

### MODIFIED
#### GENERAL (`DataTable.vue` — estandardització dels llistats de taules a totes les vistes)
    - Es crea el nou component orgànic `DataTable.vue` (`components/organisms/DataTable.vue`), que unifica i estandarditza la capçalera (amb suport per a capçalera fixa `sticky top-0`), el desplegament dels estats de càrrega (`pending`/`loading`), error i llista buida (`isEmpty`), i el càlcul dinàmic d'alçada i amplada adaptat al `sidebarStore.sidebarWidth`.
    - S'aplica l'estil CSS per al truncat automàtic de text amb punts suspensius (`text-overflow: ellipsis`) a totes les cel·les de capçalera i contingut, amb opció per ometre'l mitjançant la classe `data-table-no-truncate`.
    - Es refactoritzen 57 llistats de pàgines de tots els mòduls de l'aplicació (`billing`, `communication`, `consumption-management`, `contract`, `fraud`, `incident`, `order`, `pricing`, `reading`, `service`, `user`, `verifactu`) per utilitzar el nou component `DataTable`.
#### PRICING (`pages/pricing/products/index.vue` — ampliada columna "Nom" i truncat amb "...")
    - S'amplia la proporció de la columna "Nom" a `gridTemplate` (`2.5fr`) per donar-li més espai i evitar que trepitgi la columna d'explotació.
    - S'afegeixen les propietats de truncat (`truncate`, `min-w-0`, `block`) i l'atribut `title` als camps per substituir el text llarg per "..." i mostrar el valor complet en passar el cursor per sobre.
#### CONTRACT (`ContractDocumentsData.vue` — data de pujada de la documentació a la pestanya Documents)
    - S'afegeix una columna/badge amb la data de pujada (`formatDate`) a cada element del llistat de documentació del contracte.
    - S'ordena la llista de documents per data de creació descendent per localitzar ràpidament la documentació afegida més recentment.

### CHORE
#### READING
    - Afegir lectures per document s'ha canviat de manera que sempre es tracta per celery. Documents grans peta amb timeout

## [10-08-2026]

### CHORE
#### COMMUNCATION
    - Allow to download files without invoices

### FIX
#### PRICING (`EditFieldDialog.vue` — no es podia buidar un camp d'una taula de preus, p. ex. a `PriceIntervalStretchesEdit.vue`)
    - Causa arrel: `onDialogClose()` interceptava el cas de valor buit **abans** de saber si la fila era nova o ja existent, i sempre feia `emits('refreshList')` sense arribar a cridar l'API — això recarrega la llista amb les dades del servidor (valor antic intacte), donant la sensació que no es podia deixar el camp buit. `$apiService.updateValue()` (`plugins/api/api.js`) ja convertia `''` a `null` correctament; mai arribava a cridar-se.
    - Ara només s'omet la crida quan es tracta d'una fila **nova** (`id == 0`) amb el valor buit (no té sentit crear-la sense valor); per a una fila **existent**, encara que el camp quedi buit, es crida `updateValue(...)` igualment, que persisteix `null`.
    - `EditFieldDialog.vue` és un component compartit (13 usos: `PriceIntervalStretchesEdit.vue`, `PriceVariableStretchesEdit.vue`, `AddPriceInterval.vue`, `AddPriceVariable.vue`, `ConfigList.vue`, etc.), així que el fix aplica per igual a tots els llistats de configuració que l'usen.
#### BILLING (`invoice-api.js` — es reverteix el canvi de paginació del 07-08-2026, arrel dels llistats de factures buits)
    - Causa arrel: el canvi de backend del 07-08-2026 (`OptionalPageNumberPagination` a `InvoiceViewSet`) fa que `GET /billing/invoice/` sense el paràmetre `page` retorni un array pla en lloc de l'objecte `{count, next, previous, results}` habitual. Aquell dia només es va normalitzar `getAll()` (usat per `MassiveInvoiceDownload.vue`); la resta de crides a l'endpoint sense `page` (`getInvoicesFromContract`, `getGeneralInvoicesFromContract`, `getContractInvoice`, `getConnectionRequestInvoice`) es van quedar llegint `response.results`, que passava a ser `undefined`, deixant buits els llistats de factures a `ContractRegion.vue`, `ContractPinned.vue`, `AddInvoiceBudget.vue`, `ContractRequestDetail.vue` i `ConnectionRequestDetail.vue`.
    - En lloc de pegar cada crida perquè accepti tots dos formats (pas intermedi d'avui, ja revertit), es reverteix directament l'arrel: el backend torna a paginar sempre `billing/invoice/` (vegeu canvi de backend). `getAll()` torna a afegir sempre `&page=...` (com abans del 07-08-2026); la resta de mètodes de `invoice-api.js` tornen a la seva forma original, sense cap normalització d'array (ja no cal, mai poden rebre'n).
    - S'extreu la construcció de la query de filtres (`search`, `contract`, `is_invoice`, dates, `person`...) a un helper compartit `buildInvoiceFilterQuery()` dins `invoice-api.js`, reutilitzat per `getAll()` i pel nou `massiveDownload()` (FEAT més avall), evitant duplicar-la.
#### BILLING (`SEPARemittanceDetail.vue` — subregió de Pagament mal renderitzada dins la subregió de Factura)
    - Causa arrel: el panell `#subregion` combinava `position: fixed` amb una animació d'obertura/tancament basada en `transform` (`translate-x-0`/`translate-x-full`). Per l'espec CSS, qualsevol element amb `transform` esdevé el *containing block* de tots els seus descendents `position: fixed`; així, quan des de la subregió de Factura (`InvoiceRegion`, oberta dins d'aquest panell) s'obria la seva pròpia subregió de Pagament (també `fixed`), aquesta deixava d'ancorar-se al viewport real i quedava atrapada dins del contenidor `overflow-hidden` de `SEPARemittanceDetail.vue`: es perdia el `padding-left` (`pl-10`) del panell i la fletxa de tancar (`#region_nav`) quedava mal posicionada/invisible.
    - Es substitueix l'animació `translate-x-*` (`transform`) del `#subregion` per una transició sobre `right` (`right-0` ↔ `right-[-48%]`), evitant crear aquest *containing block* espuri. Els panells `fixed` niats (p. ex. Pagament dins de Factura) tornen a ancorar-se correctament al viewport, mostrant la fletxa de tancar i el padding interior com a la resta de l'aplicació.
#### CONTRACT (`pages/contract/contracts/index.vue` — mateix problema de `transform`/`fixed` niats al panell de detall de contracte)
    - El panell `#right_page` (llista+detall de contractes) pateix el mateix problema de fons que `SEPARemittanceDetail.vue` (FIX anterior): combinava `position: fixed` amb una animació `transform` (`translate-x-0`/`translate-x-[2000px]`), i dins seu es renderitza `ContractRegion`, que obre les seves pròpies subregions niades (persona, factura...) també amb `position: fixed`. Es substitueix per una transició sobre `right` (`right-0` ↔ `right-[-2000px]`), evitant el *containing block* espuri per als panells niats.
#### SERVICE (`SupplyPointRegion.vue` — subregions niades (contracte, factura) mal renderitzades)
    - La subregió pròpia de `SupplyPointRegion.vue` (contracte, comptador, connexió, etc., obertes des del detall de punt de subministrament) usava `w-full` en lloc de `w-[48vw]` (com la resta de l'aplicació): en obrir, per exemple, un contracte des de la pestanya "Contractes", el panell ocupava tota l'amplada de la pantalla en lloc de mostrar-se com a panell lateral.
    - A més, `SupplyPointRegion.vue` no tenia registrat el component `InvoiceRegion` al seu bloc de subregions, tot i que `ReadingDetail.vue` (pestanya "Lectures") ja emetia `show-detail('InvoiceRegion', ...)` en clicar una factura des d'una lectura: el panell s'obria (a tota amplada) però no hi carregava mai la factura. S'afegeix l'import i el bloc `<InvoiceRegion v-if="showRegionDetailComponent === 'InvoiceRegion'" ...>`.

### FEAT
#### BILLING (`ReadingListDetail.vue` — paginació incremental (scroll infinit) de l'històric de lectures, 5 en 5)
    - L'històric de lectures (dins del detall d'una lectura, taula amb data/lectura/consum/origen...) carregava sempre totes les lectures anteriors del mateix contracte/punt de subministrament d'una sola vegada.
    - `$ReadingApiService.getReadingDetail(id, page)` (`plugins/api/billing/reading-api.js`) afegeix `?page=` a la URL; `reading_history` al backend ha passat de ser un array pla a `{count, results}` (vegeu FEAT backend, 5 resultats per pàgina).
    - En lloc de botons de pàgina, la llista creix incrementalment en fer scroll: mateix patró que `ConsumptionAlertsDetail.vue` (`onScroll` al `div` amb `overflow-y-auto`, detecta quan s'arriba a prop del final — `scrollTop + clientHeight >= scrollHeight - 20` — i crida `loadMoreHistory()`, que demana la pàgina següent i fa `data.value = [...data.value, ...newResults]` en lloc de reemplaçar-la). Nous estats `historyPage`, `historyTotal`, `historyHasMore`, `loadingMore` (bloqueja crides simultànies i s'atura quan ja s'ha carregat tot); petit indicador "Carregant..." al peu de la llista mentre es demana la següent pàgina.
    - Com que cada pàgina torna a demanar tot el detall de la lectura (`getReadingDetail`), `detail.value` (contracte, punt de subministrament, foto...) es reassigna a cada scroll però amb les mateixes dades — acceptable perquè és el mateix comportament que ja tenia `getData()` en general, no una regressió d'aquest canvi.
    - Amb una mida de pàgina de 5, les primeres files no sempre omplen els `260px` (`max-h-[260px]`) del contenidor amb scroll; per evitar que l'usuari es quedi sense manera de disparar `onHistoryScroll` en aquest cas, `fillContainer()` comprova després de cada càrrega si el contingut ja desborda el contenidor (`scrollHeight > clientHeight`) i, si no, demana la pàgina següent i torna a comprovar, recursivament, fins que hi hagi prou files per fer scroll o s'acabin les dades. Nou `ref="scrollContainer"` al `div` amb `overflow-y-auto` per poder mesurar-lo.
    - Per evitar files duplicades entre pàgines: al backend, `previous_readings` s'ordena per `-reading_date` seguit de `-id` com a desempat (moltes lectures comparteixen exactament la mateixa data, típic d'un lot de lectura, i sense una clau secundària estable la paginació per `offset` no té garantit el mateix ordre entre peticions successives — vegeu FEAT backend). Al frontend, nou `requestToken` (incrementat a cada `getData()` i a cada tancament del detall): `getData()`, `fillContainer()` i `loadMoreHistory()` comproven, després de cada `await`, que la seva petició encara sigui la vigent abans d'escriure `data.value`, per si l'usuari tanca i torna a obrir el detall abans que una càrrega incremental anterior hagi acabat — en aquest cas la resposta tardana es descarta en lloc d'afegir-se sobre una llista ja renovada.
    - El botó "Descarregar XLSX" (`AtomsDownloadXlsxButton`) exporta només les files ja carregades (les que s'han vist fent scroll), no tot l'històric si encara no s'ha arribat al final — coherent amb el seu comentari original ("exports exactly the rows/columns shown"), però és un canvi de comportament respecte abans (quan no hi havia paginació i exportava tot l'històric sempre).
#### BILLING (`PersonRegion.vue`, `ContractRegion.vue` — paginació a la pestanya de Factures)
    - La pestanya de Factures del detall de persona i de la llista principal de factures del detall de contracte carregaven sempre la primera pàgina de `billing/invoice/` (50 factures) sense cap manera de veure la resta.
    - `PersonRegion.vue`: la càrrega d'invoices s'extreu a `getInvoices(page)`, amb un nou estat `invoicesPagination` (`page`, `perPage`, `total`, `totalPages`) i `onInvoicesPageChange()`; s'afegeix el component `Pagination` (`components/molecules/Pagination.vue`) sota `InvoiceMiniDetail`, mateix patró que `MassiveInvoiceDownload.vue`. El comptador de la pestanya passa a mostrar el total real (`invoicesPagination.total`) en lloc de la mida de la pàgina carregada.
    - `ContractRegion.vue`/`ContractTabs.vue`: `getInvoices(page)` passa el nou paràmetre a `getInvoicesFromContract`; l'estat `invoicesPagination` es calcula a `ContractRegion.vue` i es passa com a prop a `ContractTabs.vue`, que hi renderitza `Pagination` sota la llista de factures individuals (subtab "Factures") i emet `update-invoices-page` cap amunt en canviar de pàgina. No s'ha tocat la subtab de factures generals (`getGeneralInvoicesFromContract`), que es manté sense paginar.
    - `plugins/api/billing/invoice-api.js` (`getInvoicesFromContract`): accepta ara un quart paràmetre `page` (per defecte `1`) i l'afegeix a la URL, en lloc de demanar sempre la primera pàgina implícita del backend.
#### BILLING (`MassiveInvoiceDownload.vue` — la descàrrega massiva de factures passa a gestionar-la el backend)
    - Amb `billing/invoice/` tornant a paginar (50/pàgina), `MassiveInvoiceDownload.vue` ja no pot mantenir tot el llistat filtrat carregat al navegador per construir-se els `ids` a descarregar (l'enfocament del 07-08-2026). `searchData()` torna a demanar només la pàgina visible i mostra `data.count` (el total real de factures que compleixen el filtre, no la mida de la pàgina) al bloc "Total Filtrat"; s'afegeix el component `Pagination` (`components/molecules/Pagination.vue`) per navegar-hi, igual que a la resta de llistats de l'app.
    - El checkbox d'excloure factura es manté igual (per `id`, a `excludedInvoices`), ara funcionant a través de pàgines en lloc de sobre tot el llistat carregat de cop.
    - `downloadInvoices()` ja no fa `getDocuments`/`downloadDocuments` amb els ids carregats al navegador: crida el nou `$InvoiceApiService.massiveDownload(excludedInvoices, inZip, ...filtres)` (POST `billing/invoice/massive-download/`, vegeu backend), que envia els mateixos filtres del llistat + els exclosos, i el backend genera el zip/pdf de **totes** les factures que compleixen el filtre com a tasca Celery. El component en fa seguiment amb `AtomsProcessColorBadge`/`task-progress` (mateix patró que ja s'usava per a la descàrrega massiva d'e-factures a `CommunicationProcessRegion.vue`) i, en acabar, obre/descarrega el fitxer amb `openAuthenticatedFileUrl(result.file_url, !inZip)`.
#### SERVICE (`AddCompany.vue` — traduccions per idioma al "Text del peu de factura" i la "Llei de protecció de dades", igual que Producte/Tarifa)
    - Aquests dos camps de configuració d'empresa eren únicament textos plans, sense cap manera d'especificar-hi un text diferent per idioma, a diferència del `name` de Producte/Tarifa/Concepte, que ja tenia aquesta opció via `TranslatableNameField.vue`.
    - `components/molecules/TranslatableNameField.vue`: noves props opcionals `label` (per defecte manté `common.translations`, com fins ara) i `multiline` (renderitza `<textarea>` en lloc d'`<input type="text">`); sense canvis de comportament pels usos existents (`ProductEdit.vue`, `PriceRateEdit.vue`, `LineItemTypeEdit.vue`), que no passen cap de les dues.
    - `AddCompany.vue`: nous estats `invoice_footer_text_translations`/`data_protection_law_text_translations` (array `{language, name}`, mateixa forma que `translations` a Producte/Tarifa), carregats/desats des de/cap als nous camps `invoice_footer_text_translations`/`data_protection_law_text_translations` del backend (vegeu FEAT backend), amb un `<TranslatableNameField ... multiline />` sota cada `<textarea>` corresponent, etiquetat per distingir a quin camp pertany (aquest component és compartit i mostra el mateix `label` si se n'usen dues instàncies a la mateixa pantalla sense diferenciar-lo).
    - Al bucle de `createCompany()`/`updateCompany()`, qualsevol valor que sigui un objecte pla (no array, no `File`/`Blob`) es serialitza amb `JSON.stringify()` abans d'afegir-lo al `FormData` (necessari perquè aquest endpoint envia les dades com a `multipart/form-data` pel `logo`), mateix patró que ja s'usava a `manageRejectionPayments()` (`plugins/api/billing/payment-api.js`). Al backend, `MultiTranslatableFieldMixin` declara aquests camps com `serializers.JSONField` (no `DictField`) perquè sap desxifrar una cadena JSON quan l'input és multipart (vegeu FEAT backend).

## [07-08-2026]

### FIX
#### CONTRACT (`ContractRequestTermination.vue`, `ContractRequestEdit.vue` — finalitzar sol·licitud d'alta amb "Sense comptador")
    - Causa arrel: en triar "Sense comptador" (pas 6 de la sol·licitud d'alta) el `meter_id` del punt de subministrament no s'esborrava, així que tant la targeta de "lectura inicial" com la validació de finalització (`runValidation()`) el seguien tractant com si hi hagués un comptador pendent de lectura, bloquejant l'alta amb l'avís "Falta assignar un comptador al punt de subministrament de la sol·licitud".
    - `ContractRequestTermination.vue`: la targeta de lectura inicial ja no es mostra quan `withoutMeter` és cert.
    - `ContractRequestEdit.vue` (`runValidation()`): s'omet l'exigència de lectura inicial per supply point quan `request.value.meter_mode === 'none'`, i es filtren de `res.errors` (backend) els avisos que contenen "comptador" en aquest mateix cas, permetent finalitzar la sol·licitud d'alta sense comptador.

### FEAT
#### BILLING (`MassiveInvoiceDownload.vue` — descarregar tot el llistat de factures d'una persona, no només les primeres 50)
    - El backend ara permet demanar `GET /billing/invoice/` sense el paràmetre `page` per rebre el llistat complet sense paginar (vegeu canvi de backend); fins ara `MassiveInvoiceDownload.vue` sempre demanava la pàgina 1, així que només es podien seleccionar/descarregar les primeres 50 factures d'una persona.
    - `plugins/api/billing/invoice-api.js` (`getAll()`): només afegeix `&page=...` a la URL si es passa un valor de `page` (abans sempre l'afegia, per defecte `1`). `MassiveInvoiceDownload.vue` (`searchData()`) crida ara `getAll(..., page=null, ...)` per obtenir el llistat sencer.
    - Sense `page`, el backend (DRF) retorna un array pla en lloc de l'objecte `{count, next, previous, results}` habitual. `getAll()` només acceptava aquest segon format i llençava `Error estructura 'results' no trobat` davant l'array, fent que el llistat de `MassiveInvoiceDownload.vue` es quedés buit tot i que el backend sí retornava les factures. Ara `getAll()` detecta l'array i el normalitza a `{ count: response.length, next: null, previous: null, results: response }`.

## [06-08-2026]

### FIX
#### BILLING (`ReadingBatchSetup.vue`, `ReadingBatchEdit.vue` — validació d'origen de lectures al pas 1 del lot)
    - Causa arrel: `selectedOriginType` s'inicialitzava sempre a `'FILE'`, encara que l'usuari no hagués triat cap origen, i el pas 1 (`nextStep`) validava únicament `hasSetupReadings`/`reading_date` sense mirar quin origen estava seleccionat; això aplicava la mateixa exigència (lectures assignades o data de lectura) a tots els orígens (fitxer, data, no facturat, facturació pendent), encara que només l'origen Lecturapp (`APP`) depèn realment d'això.
    - `ReadingBatchSetup.vue`: `selectedOriginType` comença a `null` en lloc de `'FILE'`; `emitChange()` emet `{ origin_type: null }` si encara no s'ha triat cap origen, i inclou `origin_type` a la resta de dades emeses. En aplicar un document de lectura pendent (`applyPendingReadingDocument`), es fixa `selectedOriginType = 'FILE'` explícitament.
    - `ReadingBatchEdit.vue`: `nextStep()` bloqueja el pas 1 amb avís si no s'ha seleccionat cap origen (`setupData.origin_type`); la validació de lectures assignades/data de lectura només s'aplica quan l'origen és `'APP'`, la resta d'orígens ja poden avançar un cop seleccionats.
#### BILLING (Smart metering preview — duplicat per contracte i falsos matches)
    - El preview generava **una fila per cada contracte** del supply point (actiu + baixa recent), així que amb ~2000 comptadors de telelectura es veien ~4000 files i semblava tot el lot, no només telelectura.
    - Ara només hi ha **una fila per comptador/SP** (contracte actiu preferent).
    - El match API↔DB per `contains` ignorava fragments curts (`"12"`, `"20"`…) que encaixaven en gairebé tots els codis i marcaven lectures falses com a telelectura. Ara cal coincidència exacta o `contains` amb mínim 5 caràcters, preferint el codi API més llarg.
    - Si el lot té `include_telecontrol=False`, el preview torna buit.
    - Backend: el preview només demana meters amb tipus `SMART_METERING` (no qualsevol telelectura `OTHER`), i respecta `include_telecontrol`/`include_manual` del lot (no tots els de la mateixa ruta si el lot és només manuals).
#### BILLING (`InvoiceViewEdit.vue`, `BudgetEdit.vue`, `AddInvoiceBudget.vue` — el botó "Generar factura" des del detall tornava a mostrar el mateix pressupost)
    - Causa arrel: en convertir un pressupost a factura (`is_budget: false` sobre l'id del pressupost), el backend crea una **factura nova amb un id diferent** (`pass_budget_to_invoice`) i deixa el pressupost original intacte. `convertBudgetToInvoice()` a `InvoiceViewEdit.vue` ignorava la factura retornada (`response.invoice`) i tornava a carregar amb el mateix `props.id`, així que sempre reapareixia el pressupost sense canvis; la factura nova no es propagava mai cap a `AddInvoiceBudget.vue`, que per tant tampoc actualitzava la seva llista.
    - `InvoiceViewEdit.vue`: `convertBudgetToInvoice()` ja no torna a fer `getInvoice()`; propaga la factura retornada per l'API via `handleChanged(false, response.invoice)` (nou segon paràmetre `invoiceData` a `handleChanged`/event `changed`).
    - `BudgetEdit.vue`: `handleChanged(close, newInvoice)` fa servir directament la factura nova rebuda quan el seu id difereix de l'actual, en lloc de refer la consulta amb l'id (antic) del pressupost.
    - `AddInvoiceBudget.vue`: `refresh()` detecta que la factura resultant és final i té un id diferent del que s'estava mostrant, i navega la subregió cap a la factura nova (`showDetail('InvoiceEdit', invoice.id)`), igual que ja feia `generateInvoice()`; això força el remuntatge de `BudgetEdit` amb l'id correcte i actualitza la llista de factures/pressupostos de la regió.
#### BILLING (Smart metering preview async — barra de progrés)
    - El preview de Smart Metering al lot de lectures passa a ser asíncron (Celery): `previewBatchReadings()` a `plugins/api/billing/smart-metering-api.js` adapta al nou contracte del backend (`task_id`) i manté compatibilitat amb la resposta síncrona antiga si encara arriba `readings`.
    - `ReadingBatchEdit.vue`: desa `smartMeteringPreviewTaskId`, fa el seguiment amb `AtomsProcessColorBadge` / `task-progress` (`onSmartMeteringPreviewTaskRefresh`) i obre el diàleg quan la tasca acaba amb èxit. Nou computed `isSmartMeteringBusy` per bloquejar Següent/Estimar mentre corre el preview o el guardat.
    - `ReadingBatchSetup.vue`: mentre corre el preview, el botó Smart Metering es substitueix per `AtomsProcessColorBadge` al mateix lloc (prop `smartMeteringTaskId` + event `smart-metering-preview-refresh`); la data queda deshabilitada durant la tasca.
    - 'locales/ca.ts', 'locales/es.ts', 'locales/gl.ts', 'locales/en.ts': nova clau `billing_block.smart_metering_loading_preview`.

### FEAT
#### BILLING (`SendInvoiceModal.vue` — idioma per defecte i previsualització de la informació afegida al correu)
    - L'idioma del cos del correu (`selectedLang`), fins ara sempre inicialitzat a la locale de la interfície, ara es preselecciona amb `contract.language` (el mateix camp ISO que ja usa `ContractDetail.vue`/`data-change.vue`), amb fallback a la locale si el contracte no en té.
    - El backend afegeix automàticament al cos del correu la informació de factura/contracte enviats (vegeu backend); per evitar sorpreses, sota el textarea es mostra ara una previsualització de només lectura (`sentInfoLines`, nou `computed`) amb `Factura: <serie_final>` i, si n'hi ha, `Contracte: <token>`, sense afegir aquest text al `body` editable que s'envia.
    - Nova clau de traducció `billing_block.email_body_included_info` als quatre idiomes (`ca`, `es`, `en`, `gl`).
#### GENERAL (`app.vue`, `NavSidebar.vue`, `NavTopPinned.vue`, nou `stores/useExploitationStore.ts` — nom de l'explotació a la pestanya i al menú lateral)
    - Fins ara la pestanya del navegador (`<title>`) i el text del menú lateral mostraven sempre el literal "Customers", sense cap referència a l'explotació activa: amb diverses pestanyes obertes (una per instal·lació/client) no hi havia manera de distingir-les a cop d'ull.
    - Nou store `useExploitationStore` (Pinia), amb l'única finalitat de compartir l'explotació actual (`current`) entre components que ja la carregaven cadascun pel seu compte (`NavSidebar.vue` i `NavTopPinned.vue` fan cadascun el seu `$ExploitationApiService.getDetail(...)`; no s'ha tocat aquesta doble crida, només s'hi ha afegit la publicació al store un cop rebuda la resposta).
    - `app.vue`: el `<title>` ara és reactiu (`useHead({ title: () => ... })`) i mostra `Customers - <nom explotació>` quan n'hi ha una seleccionada, o `Customers` si no.
    - `NavSidebar.vue`: el mateix patró `Customers - <nom explotació>` substitueix el literal "Customers" tant al text visible del logo com al `title` de l'enllaç quan el menú està col·lapsat a icones.
#### COMMUNICATION (`CommunicationProcessRegion.vue`, `communication_process_serializer.py` — descarregar documents enviats per correu electrònic)
    - Al desplegable d'opcions del detall d'un procés de comunicació, la descàrrega de documents només oferia "Tots" / "Cartes" / "E-factures", sense cap opció equivalent a "Cartes" per als documents enviats per adreça electrònica (diferent de les e-factures, que són un canal/procés a part).
    - `downloadLetters(postal, email)` (abans només acceptava `postal`): amb `email=true` filtra `com_files` per `item.is_email` (nou camp, vegeu backend) en lloc de `item.is_postal`. El nom del fitxer descarregat reflecteix ara el canal (`common.email_long` en lloc de `customer_service_block.letters` quan `email=true`).
    - Nova opció al desplegable "Descarregar Docs (Correu electrònic)", activa només quan `data.has_email` és cert (nou camp, vegeu backend); reutilitza els mateixos `$DocumentManagerApiService.downloadDocuments`/`downloadSinglePdfDocument` que ja s'usaven per a "Cartes", sense cap crida nova.

## [05-08-2026]

### FEAT
#### EXPLOITATION (`CurrentExploitationSelect.vue`, `exploitation-api.js` — saltar a les instal·lacions germanes)
    - Les instal·lacions amb una base de dades per explotació (instal·lació O: 6 poblacions, 6 bases de dades, 6 adreces) només podien canviar d'instal·lació editant la barra d'adreces. El selector d'explotació llista ara també aquestes instal·lacions i navega a la que es tria, marcant l'actual com a tal i deixant-la desactivada.
    - La llista ve del nou endpoint `GET /service/exploitation-site/` (model `ExploitationSite` del backend), amb `$ExploitationApiService.getSites()`. Cap adreça no queda escrita al codi: cada base de dades declara les seves germanes.
    - **Fallback als desplegaments anteriors a `ExploitationSite`**: si l'endpoint no existeix o no retorna cap instal·lació, es llegeix `NUXT_PUBLIC_EXPLOITATION_SITES` (JSON `[{name, url}]`) via `runtimeConfig.public.exploitationSites`, com fins ara. Això permet desplegar el frontend nou sobre un backend que encara no té la taula, sense finestra de tall.
    - La crida a l'endpoint es fa amb `suppressToast`, perquè un backend antic (404) o amb la migració encara sense aplicar (500) no tregui un toast d'error a l'usuari cada vegada que obre el selector: el fallback ja cobreix el cas silenciosament.
    - Quan no hi ha cap instal·lació germana (ni a la taula ni a la variable d'entorn) el bloc no es renderitza i el selector es comporta exactament com abans, de manera que els clients amb una sola instal·lació no noten cap canvi.
    - **Clic al nom: s'hi va des de la mateixa pestanya. Clic a la fletxa: s'obre una pestanya nova** (amb `noopener`), per poder treballar amb dues poblacions a l'hora. Cada instal·lació són dos botons germans, no un dins de l'altre.
    - En canviar d'instal·lació s'hi arrossega la pàgina on s'era (`/contract/contracts`); es descarten les rutes amb identificador (`/billing/billing/edit/42`), perquè aquells números són d'una altra base de dades i allà apunten a un altre registre o a cap.
    - **El retorn a la ruta després del login (`middleware/auth.global.ts`) només s'activa si l'adreça porta el marcador `from_site`**, que posa únicament aquesta graella. Aquest middleware corre abans de tenir sessió i no pot consultar la taula, així que el marcador és la porta: a la resta de desplegaments la branca no es pot activar mai i el login continua deixant l'usuari a la pàgina principal. Si a la instal·lació de destí ja hi ha sessió oberta, no es passa pel formulari.
    - **Autoselecció d'explotació** (`NavTopPinned.vue`): només a les instal·lacions que declaren germanes **i** que tenen una sola explotació, on triar-la a mà no aporta res. Amb diverses explotacions a la mateixa base de dades no se'n selecciona cap, perquè l'aplicació no ha de filtrar les dades sense que l'usuari ho hagi decidit. La consulta de germanes es fa un sol cop per sessió del navegador.
    - Els canvis de disposició del panell (alçada repartida amb `flex` per encabir-hi la graella) van darrere la mateixa porta: sense files a `ExploitationSite`, el panell es renderitza amb les mateixes classes i el mateix `style` que abans.
    - Noves claus de traducció `common.current_installation` i `common.open_in_new_tab` als quatre idiomes (`ca`, `es`, `en`, `gl`).

### FIX
#### EXPLOITATION (`CurrentExploitationSelect.vue` — paginació i ordenació del panell d'explotacions)
    - El panell cridava `$ExploitationApiService.getData` amb 5 arguments (`searchQuery, filters, page, sort, desc`) contra una signatura de 4 (`searchQuery, page, sort, desc`): la llista de filtres queia al lloc del número de pàgina i el número de pàgina al del nom de la columna, així que l'adreça que sortia cap al servidor era `?search=&page=&ordering=-1`.
    - Efecte: **la paginació retornava sempre la primera pàgina i ordenar per una columna no feia res**, sense cap error visible (DRF converteix un `page` buit en pàgina 1 i descarta en silenci una columna que no és a `ordering_fields`). La cerca sí que funcionava, perquè el primer argument era correcte. Es nota a les instal·lacions amb més de 50 explotacions a la mateixa base de dades.

## [04-08-2026]

### FEAT
#### BILLING (MANDATE ID)
    - S'ha preparat el front a les parts de modificar contracte, sol. de contracte i sol. d'escomesa per la generació automàtica per darrera del mandate id i permetre modificar-ho de manera personalitzada. També es mostra ara al detall de contracte el mandate id associat al contracte amb un petit log de canvis

#### INCIDENT (`IncidentEdit.vue`, `IncidentDetail.vue`, `IncidentRegion.vue` — vincular incidència amb punt de subministrament)
    - `IncidentEdit.vue`: nova opció per vincular una incidència a un punt de subministrament (nou prop `supply_point_id`, cercador amb `$SupplyPointApiService` i bloc de detall `SupplyPointDetail`), a més de contracte/factura/comanda/dipòsit ja existents. En desar, s'envia el camp `supply_point`.
    - La creació d'una incidència ja no queda bloquejada si només s'ha vinculat un punt de subministrament (abans calia obligatòriament contracte, factura, comanda o dipòsit de compromís).
    - `IncidentDetail.vue`: els vincles (contracte, punt de subministrament, factura, comanda, dipòsit de compromís) ara es mostren tots de manera dinàmica, només si la incidència els retorna; abans el contracte es mostrava sempre encara que no n'hi hagués.
    - `IncidentRegion.vue`: s'afegeix la subregió `SupplyPointRegion` perquè es pugui obrir el detall del punt de subministrament vinculat des de la incidència.
    - **Pendent backend**: afegir el camp `supply_point` (FK, nullable) al model/serializer de `notification/incident/` (lectura i escriptura), i relaxar la validació de negoci que actualment exigeix contracte/factura/comanda/dipòsit obligatoris perquè el punt de subministrament també sigui suficient.
#### PRICING (Nous logs)
    - S'han afegit logs de producte i tarifa per saber quan hi ha canvis tenir traçabilitat

### FIX
#### READING (`pages/reading/readings/estimation.vue` — historial de lectures incloïa lectures de control)
    - En obrir l'historial de lectures d'un contracte (crida a `billing/reading/`), ara s'envia `is_control=False` perquè no es mostrin lectures de control.
#### GENERAL (botó de tancar invisible a les subregions laterals — `ContractRegion.vue`, `SupplyPointRegion.vue`, `InvoiceRegion.vue` i ~85 components més amb el patró `#subregion`)
    - Causa arrel: el panell `#subregion` (detall niat que s'obre des d'una regió, p. ex. obrir un punt de subministrament des d'un contracte) es desplaçava `margin-top: -45px` i s'alçava `h-[calc(100%+45px)]` per alinear el seu botó de tancar (`#region_nav`) per sobre de la caixa del contenidor, i només esdevenia un panell `fixed` quan el component s'usava niat (`isSubRegion`). Quan es mostrava en mode "vista principal" (dins del `#right_page` de la pàgina llista+detall), aquesta franja de 45px per sobre quedava tallada per l'`overflow` del `#right_page`/`#page` (introduït al fix del scroll doble), deixant el botó de tancar inaccessible; a més, en mode niat el contingut principal es comprimia a `grid-cols-2` encara que el panell ja es mostrava com a overlay fixed.
    - Fix aplicat de manera uniforme: el panell `#subregion` ara és sempre `fixed top-0 right-0` (independentment de si el component és o no una subregió niada), amb `translate-x-0`/`translate-x-full` només segons si està obert; s'elimina completament el truc `margin-top: -45px` / `h-[calc(100%+45px)]`. El contenidor principal aplica `mr-[amplada]` amb transició quan la subregió és oberta, per no quedar tapat per l'overlay, en lloc de dependre d'una graella `grid-cols-2`.
    - Aplicat a tots els components `organisms`/`molecules` que seguien aquest patró (`#subregion` + `margin-top: -45px`), excepte `AddRoutePosition.vue` (mai s'usa com a subregió niada, no té prop `isSubRegion`).
#### CONTRACT (Saving data)
    - Al intentar guardat la forma de pagamament o el sepa donava error.

## [03-08-2026]

### FEAT
#### CONTRACT (`ContractRequestAddressPayment.vue` — opció "Sense comunicació")
    - Nova opció "Sense comunicació" (`communication_type = 'NONE'`) a l'apartat de Comunicació de la sol·licitud de contracte, al costat de Paper/Digital/Ambdues. En seleccionar-la, es desvinculen automàticament l'email digital (`selectedDigitalPersonContact`) i l'adreça de contacte (`selectedContactAddress`), i no es mostra cap dels dos blocs (paper/digital) per sota.
    - `ContractRequestDetail.vue`/`ContractDetail.vue`: mostren la nova etiqueta "Sense comunicació" quan `communication_type == 'NONE'`.
    - 'locales/ca.ts', 'locales/es.ts', 'locales/en.ts', 'locales/gl.ts': nova clau `contract_block.no_comm`.
#### BILLING (Abonar factura amb saldo cap a contracte)
    - Donar l'opció de, un cop entrat el saldo a contracte, retornar automàticament aquest saldo cap a un pagament amb un mètode de pagament X, que ja es gestionarà si surt autom. com a pagat o com a pendent per genenerar un TRF
#### BILLING (`InvoiceLineItemDetailInvoice.vue` — agrupació de conceptes per Producte)
    - Els conceptes d'una factura, fins ara agrupats només per Concepte (`line_item_type`), ara s'agrupen primer per Producte i, dins de cada producte, per Tarifa + Concepte, tant a la vista normal com a la vista `by_company`.
#### CONTRACT/BILLING (`MassiveInvoiceDownload.vue` — reorganització dels blocs de Filtres i Total Filtrat)
    - Els blocs "Filtres" i "Total Filtrat", fins ara en columnes una al costat de l'altra, ara es mostren un sota l'altre (Filtres a sobre, Total Filtrat a sota).
    - Dins de Filtres, el bloc "Import total" ara es pot plegar/desplegar (amagat per defecte).
    - El filtre de "Data d'emissió" (Des de/Fins a) passa a una fila pròpia amb els inputs alineats horitzontalment amb les etiquetes; a la fila següent es mostren junts el selector "Separat en zip"/"Tot en un document" i el botó "Descarregar".

### FIX
#### BILLING (`pages/billing/reports/index.vue` — columnes del llistat massa amples i popover de filtres inaccessible)
    - Graella del llistat (capçalera i files): proporcions de columnes ajustades de `1fr,1fr,1fr,1fr,1.4fr` a `1.2fr,1.2fr,0.7fr,1fr,0.6fr`, reduint sobretot la columna "Doc". Data, nom, document i tipus ara amb `truncate`/`min-w-0` i `title` amb el text complet, en lloc d'eixamplar la columna quan el contingut és llarg.
    - Popover flotant de filtres (`showFiltersPopover`/`hideFiltersPopover`): era `pointer-events-none`, impedint posar el cursor a sobre (es tancava en sortir del botó (i) abans de poder-hi interactuar). Ara accepta el cursor, amb `@mouseenter`/`@mouseleave` propis i un tancament amb retard de 150ms (cancel·lable) perquè es pugui moure el cursor des del botó fins a la finestra sense que es tanqui; també apropada lleugerament al botó (`rect.bottom + 1` en lloc de `+ 6`).
#### CONTRACT (`pages/contract/contracts/[id]/price-rates.vue` — modificar tarifes ja no esborra la forma de comunicació)
    - En desar tarifes, si el contracte té comunicació DIGITAL o BOTH s'envia de nou el `person_contact_email_id` existent, perquè el backend no el buidi i forci el tipus a PAPER.
