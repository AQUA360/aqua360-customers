# Changelog Backend

## [29-05-2026]

### FEAT
#### COMMUNICATION
    - S'ha afegit l'opció de fer cerca per comunicacions al procés de comunicació i crear un de nou amb comunicacions ja exitents sense encessitat de passar per tot el procés
    - S'han afegit logs dels canvis a comunicació (email, tlf, adreça)

### MODIFIED
#### COMMUNICATION
    - S'ha afegit l'opció d'afegir les factures per enviar sense necessitat de tenir una facturació lligada, només que s'hagi seleccionat cerca per factures
    - S'ha afegit el poder guardar el tipus d'ús a un procés de comunicació
    - S'ha canviat com mostrem el email a la comunicació un cop creada. Ara, en comptes de passar el html com a tal, s'envia una foto del que seria el correu
    

#### BILLING
    - Afegit a la funció de generar moviment de pagament, guardar el tipus de pagament (correus o taquilla) i guardat també en pagament (més fàcil de contorlar i lligar)
    - Al buscar contractes sense facturar en una facturació, mira per dates i rangs en comptes de fer comprovacions a la propia facturació

## [28-05-2026]

### FEAT
#### BILLING
    - **Cancel·lació de lot de facturació**: S'ha afegit l'endpoint `/api/billing/billing/<id>/cancel/` (mètode `PUT`) que permet cancel·lar un lot de facturació (`Billing`), canviant el seu estat a `Cancel·lat` (token `"-1"`), eliminant en cascada totes les seves pre-factures associades no confirmades, i alliberant les lectures perquè puguin ser facturades de nou.

### CHORE
#### COREDATA
    - **Configuració de consum inusual configurable**: S'ha afegit el paràmetre `reading_alert_unusual_consumption_min_value` a `ConfigProject` mitjançant la migració `0102_unusual_consumption_config.py` per definir el consum mínim necessari (per defecte 20) abans de comprovar o disparar una alerta de consum inusual.
    - **Token per a tipus d'ús de connexió contra incendis**: S'ha registrat la clau de configuració `fire_connection_use_type_token` (valor per defecte `'incendis'`) a `ConfigProject` mitjançant la migració `0103_add_fire_connection_use_type_config.py`.

#### BILLING
    - **Tag d'icona de reciclatge**: S'ha afegit el tag `get_recycle_icon_base64` a `billing/templatetags/svg_converter.py` per generar la icona de reciclatge en base64 per als PDFs de factures. Admet tant la càrrega d'un SVG personalitzat des de `config/assets/recycle.svg` amb tintat de color dinàmic (`fill="currentColor"`) com un fallback a una icona vectorial per defecte (tres fletxes amb fulla).

### MODIFIED
#### BILLING
    - El filtre que buscava contractes sense facturar teniem el següent problema:
        1. Quan una ruta es facturava en 2+ facturacions, agafava com no facturat els contractes de l'altre facturació tot i amb les factures confirmades. Exemple, facturació RUTA1 amb 500 contractes, es va deixar part de les lectures fora i es va fer facturació RUTA1/1 amb 150 contractes. A la primera facturació saltaràn 150 contractes com no facturats i a la segona 500 com no facturats
    - **Ordenació de pagaments per estat**: S'ha implementat el filtre d'ordenació personalitzat `PaymentOrderingFilter` al `PaymentViewSet` per garantir que, en ordenar pel camp `status`, es mostrin primer per defecte els pagaments en estat "Pendiente", seguits de la resta d'estats segons la seva posició configurada.
    - **Avisos dinàmics a la factura**: S'ha substituït l'avís de tarifes ACA a `invoice_template.html` per avisos dinàmics dins de la secció "AVÍS IMPORTANT":
        - Avís de manca de NIF per a persones/contractes amb token `99999999R` o `88888888Y`.
        - Invitació a sol·licitar la factura digital amb icona ecològica (tenyida en color blau corporatiu) per a usuaris amb factura no digital (`not is_digital`).
        - Enllaç i opció permanent de consulta de factures a l'oficina virtual.
    - **Control d'alertes de consum inusual**: 
        - S'ha actualitzat `check_unusual_consumption` a `billing/utils/reading_service.py` per descartar l'alerta si la diferència absoluta de consum respecte a la lectura anterior és menor al llindar mínim configurat (`min_val`), evitant alertes falses en consums baixos (ex. de 6 a 21 m³).
        - S'ha afegit un control per ometre l'alerta de consum inusual quan és la segona lectura del contracte i el valor d'aquesta lectura és superior a la primera lectura registrada.
    - **Creació de lectures des del Serializer**: S'ha actualitzat el mètode `create` de `ReadingSaveSerializer` a `billing/serializers/reading_serializer.py` per invocar correctament `reading_update(...)` en la creació de lectures noves autònomes (sense `supply_id`), garantint l'actualització del sac d'estimacions i de les lectures futures.
    - **Estimació a zero i is_fire per a contra incendis**: S'ha implementat que les estimacions per a contractes o connexions de contra incendis es forcin a `0` a `billing/utils/reading_service.py`. A més, s'ha afegit la propietat `is_fire` a `Reading` (`billing/models.py`) i s'ha exposat en els diferents serialitzadors de lectures (`ReadingSerializer`, `ReadingByBatchSerializer` i `ReadingByBatchMinimalSerializer` de `billing/serializers/reading_serializer.py`).
#### CONTRACT
    - **Propietat is_fire i serialitzadors de contracte**: S'ha afegit la propietat `is_fire` a `Contract` (`contract/models.py`) i s'ha exposat als serialitzadors de contracte (`ContractSerializer`, `ContractListSerializer`, `ContractMinimalListSerializer` i `ContractMinimalSerializer` de `contract/serializers/contract_serializer.py` i `contract/serializers/contract_minimal_serializer.py`).

## [27-05-2026]

### FEAT
#### COMMUNICATION
    - S'ha afegit 'use_type' a les communicacions per poder filtrar més endavant per nous processos de comunicacions 'sueltas'
    - S'ha afegit la relació de lectures amb comunicacions i processos de comunicació
    - Generar la plantilla de email en png i enviar-la en base64 al front per evitar treballar directament amb html

### MODIFIED
    - Ara al crear una comunicació, si li relaciones una factura o és una factura electrònica genera i assigna automàticament els documents.
    - Afegit ConfigProject's de loaddata que faltaven.
    - L'script de create_superuser_and_token.py ara accepta username
#### COMMUNICATION
    - **Soft delete i log de cancel·lació de comunicacions**: S'ha implementat el mètode `destroy` a `CommunicationViewSet` i `CommunicationProcessViewSet`. En lloc d'eliminar físicament els registres de la base de dades, ara es canvien a l'estat de cancel·lat (estat amb token `'-1'`) i es registra el canvi a l'historial mitjançant `LogCommunicationStatusChange` i `LogCommunicationProcessStatusChange` respectivament. A més, en cancel·lar un procés de comunicació, es cancel·len automàticament totes les seves comunicacions internes associades de manera atòmica.
#### BILLING
    - **Redisseny del PDF de Reconeixement de Deute**: S'ha adaptat completament la plantilla `commitment_deposit_template.html` i la vista `CommitmentDepositPDFDownloadViewSet` a `commitment_deposit_pdf_view.py` per fer-la coincidir amb el model visual exigit pel client. Inclou tipografia Helvetica/Arial, capçalera amb logos dinàmics de l'empresa/explotació, venciments de quotes maquetats a doble columna, data de signatura en català enllaçada dinàmicament des de backend (`now_date_ca`), i peus de pàgina dinàmics enllaçant els nous tags d'imatges base64 (`user_icon` i `hydrant_icon`) de la llibreria `svg_converter`.
#### SERVICE
    - **Ampliació de telèfons a Company**: S'ha incrementat la longitud màxima (`max_length=255`) dels camps `phone`, `phone2` i `contact_phone` del model `Company` a `service/models.py` i s'ha generat/aplicat la migració de base de dades corresponent. Això permet guardar configuracions de contacte complexes o múltiples telèfons separats per barres o altres delimitadors.
#### CONTRACT
    - S'han afegit valors al serializer de contract per poder treballar amb aquest al crear i gestionar noves comunicacions
    - **Habilitats camps de canvis i subrogacions**: S'han tornat a activar els camps `data_changes`, `surrogations` i `tenant_changes` al `ContractSerializer` per a exposar la informació d'històrics de dades, subrogacions i canvis de llogater.
    - **Filtre de sol·licituds de baixa per adreça**: Es permet buscar per address_search a baixes de contracte.

### FIX
#### BILLING
    - **Retorn de saldo en cancel·lació de factures**: S'ha corregit el comportament en el retorn/abonament de factures per assegurar que els pagaments realitzats mitjançant el mètode de pagament per saldo (`BALANCE`) es retornin sempre a la bossa de saldo (piggy bank) de l'abonat (contracte o persona) fins i tot quan es realitza la devolució amb el paràmetre `return_paid_total` desactivat (per evitar la pèrdua de crèdit en refacturacions errònies).

## [26-05-2026]

### FEAT
#### LOGGER
    - **Nou endpoint de logs de contracte**: S'ha creat l'endpoint `/api/logger/contract-data/` per retornar l'historial de modificacions de dades de facturació i fiscals d'un contracte (adreça de facturació, mètode de pagament i IBAN) mitjançant la serialització de `ContractDataChange`.

#### STATISTICS
    - **Pestanya de Resum per Empresa a l'Informe de Recaptació**: S'ha afegit a la nova pestanya anomenada "Resum per Empresa" a l'informe Excel de recaptació per conceptes (`generate_recaptacio_conceptes_excel`). Aquest nou full detalla de manera resumida la facturació per a cadascuna de les empreses facturadores (`Company`) dins del període seleccionat, mostrant de forma agregada el total **Facturat**, el total **Cobrat** (calculat com a diferència) i el total **Pendent** (imports de factures amb `left_to_pay` actiu). S'inclouen files de totalització global al peu de la taula i s'aplica el format de moneda adequat a tots els valors numèrics.

#### COREDATA
    - **Sistema de personalització de plantilles HTML**: S'ha creat `coredata/utils/template_utils.py` amb carregadors personalitzats (`PersonalizedFilesystemLoader` i `PersonalizedAppDirectoriesLoader`) per a cercar plantilles amb el sufix `_personalized.html` de manera prioritària i transparent al motor de Django. També s'inclou el helper `resolve_template_path()` per a redireccionar la lectura directa via `open()` de Python.
    - **Mandate_id configurable**: S'ha afegit el camp `mandate_id` al model `Contract` i `ContractRequest` per guardar el codi de la domiciliació bancària.

### MODIFIED
#### LOGGER
    - **Logs de dades de factura amb IBAN**: S'han afegit els camps `previous_iban` i `current_iban` al model `LogInvoiceDataChange` i al seu serialitzador per guardar i exposar els canvis del compte bancari a l'endpoint `/logger/invoice-data/`. Inclou la migració de base de dades `0049_loginvoicedatachange_current_iban_and_more.py`.

#### BILLING
    - **Registre de canvis de mètode de pagament**: S'ha actualitzat l'acció `change_payment_method_invoice` a `InvoiceViewSet` i la funció utilitària `log_invoice_data_change` per recollir i guardar els canvis d'IBAN quan es modifica el mètode de pagament d'una factura.

#### STATISTICS
    - **Informe de pagaments en efectiu**: Canviat el filtre de data per pagaments.
    - **Ajustos al filtre de factures al Resum per Empresa**: S'ha actualitzat la consulta del nou full "Resum per Empresa" per no utilitzar `filter_pending_invoices` (que filtrava de forma restrictiva per a pagaments actius i descartava factures vàlides), evitant així discrepàncies de totals amb la interfície d'usuari. Ara també inclou per defecte factures amb explotació a NULL (com fa l'API), exclou correctament esborranys i factures cancel·lades, i força el pendent a zero si l'estat de la factura és "Pagada" o "Compensada" (evitant problemes quan el camp `left_to_pay` del model a la base de dades no s'ha sincronitzat correctament).

#### CONFIG / DEPLOY
    - **Ignorat a Git**: Afegit `*_personalized.html` al fitxer `.gitignore` per a evitar conflictes en entorns de producció.
    - **Configuració de Django**: Modificat `TEMPLATES` a `settings.py` per a registrar els nous carregadors de plantilles personalitzats.
    - **Scripts de deploy amb Mina**: Actualitzats `pull_templates.rb` i `pull_templates_docker.rb` per a comprovar si existeixen plantilles personalitzades a `customers-clients-data` i copiar-les prioritàriament amb el sufix `_personalized.html` a la carpeta original de l'app, fent un fallback al comportament estàndard només si no existeixen.

### FIX
#### STATISTICS
    - **Informe resum ACA (V1 i V2)**: Controlat el cas on no hi ha factures per al període o lot seleccionat per tal de generar l'informe mostrant igualment les línies de càlcul de les explotacions amb els valors a 0/buits en lloc de llançar un error no controlat de tipus `NoneType` al processar els atributs de la data d'emissió de factura. A més, s'ha configurat perquè els camps de les dates de referència facin fallback a les dates dels filtres especificats en lloc de mostrar-se buits.

#### BILLING
    - **Reversió de la lògica de previous_reading**: S'ha revertit la lògica de resolució i enllaç de la variable `previous_reading` a com funcionava abans del canvi del 13 de maig de 2026 (cerca simple per data), per garantir la independència i evitar conflictes de dades/relacions amb el nou sistema de logs de lectures (`LogReadingChange`).

## [22-05-2026]

### FEAT
#### STATISTICS
    - **Informe de clavegueram facturat**: Nou informe Excel (`generate_clavegueram_invoices_excel`) accessible des de `/api/statistics/billing/clavegueram-invoices-summary`. Creua directament factures (`Invoice`) en lloc de moviments de cartera, amb les columnes: Contracte, Titular, NIF, Adreça, Núm. Factura, Data, Període (trimestral), Consum m³ (des de la variable de contracte `Consum anual`), Tipologia, Quota Fixa i Quota Variable (ambdues amb IVA inclòs). Inclou pestanya de resum i migració `0028_add_clavegueram_invoices_report.py`.

### MODIFIED
#### DOCUMENTMANAGER
    - **CORS Content-Disposition**: S'ha exposat la capçalera `Content-Disposition` afegint `Access-Control-Expose-Headers = Content-Disposition` a les respostes de descàrrega (`view_document`, `download_documents` i `download_single_pdf_document`) a `documentmanager/views.py` per tal que el frontend (Axios/AJAX) pugui recuperar el nom real dels fitxers.
    - **Estandardització de capçaleres**: S'han afegit cometes dobles al voltant del nom de fitxer a la capçalera `Content-Disposition: attachment; filename="..."` a tots els serveis d'emmagatzematge (`hdd_service.py`, `azure_service.py`, `ftp_service.py` i `cloud_service.py`) per evitar truncaments del nom en navegadors en presència d'espais o caràcters especials.

#### STATISTICS
    - **Normalització de noms de fitxer**:
      - S'ha canviat el prefix fix de l'informe de fiances a `fiances_incasol_` amb marca de temps dinàmica per evitar duplicats.
      - S'ha implementat normalització a minúscules i neteja d'accents a `generate_aqua_remittance_report` i `generate_pending_invoices_person_summary` utilitzant `unicodedata` per prevenir problemes de descàrrega en sistemes client.
      - S'ha afegit un fallback a la tasca de Celery `run_report_task` a `statistics/tasks.py` perquè si el generador retorna un nom nul, es recuperi el nom real des de l'objecte `Document` associat.
      - S'ha afegit control de nuls de seguretat a `statistics/views/reports_views.py` per quan el tipus de l'informe general és indefinit.
    - **Informe de Recaptació per Conceptes**:
      - Millorat el prefetch_related a `generate_recaptacio_conceptes_excel` a `statistics/utils/report_billing_service.py` per incloure el producte a través de les tarifes (`price_rate__product`), i actualitzat el processament de línies de factura per cercar-lo en ambdós llocs.
      - Implementada la sincronització de signes d'IVA i bases a nivell de línia i globals en el mateix informe per garantir consistència numèrica.
    - **Neteja de reports obsolets**: 
      - Actualitzada la migració de dades `0027_move_recaptacio_to_wallet.py` per comprovar l'existència de l'informe successor (`recaptacio_excel_report`) i eliminar l'històric de clavegueram (`clavegueram_excel_report`) de la taula `AvailableReport`.

#### BILLING
    - **Sincronització de signes i totals a línies de factura**: 
      - S'ha sobreescrit el mètode `save()` del model `InvoiceLineItem` a `billing/models.py` per forçar que el signe de `tax_price` (IVA) coincideixi amb el del preu base (`price`), automatitzar el càlcul del camp `total` i limitar el decimal segons restriccions del camp.
      - Actualitzada la funció `create_line_item_data` a `billing/utils/invoice_line_item_service.py` per assignar correctament el signe negatiu a l'IVA si el tipus de concepte no és positiu.

#### CONTRACT
    - **Optimització d'exportació a CSV**: Ampliat el `.select_related()` dins de `prepare_contract_export_queryset` a `contract/utils/contract_csv_export.py` per incloure les relacions imbricades de carrer, tipus de número, ciutat i país, evitant consultes N+1 massives i accelerant notablement el rendiment de l'exportació de contractes.

## [21-05-2026]

### FIX
#### SERVICE
    - **bulk-update-property**: S'ha corregit el comportament de l'endpoint d'actualització massiva de finques. Ara, quan s'envia una llista de punts de subministrament (`supply_points`) per a una finca (`property_id`), els punts de subministrament que prèviament estaven vinculats a aquesta finca però que no es troben a la llista s'eliminen/desvinculen correctament (establint el seu camp `property` a `None`). A més, s'ha optimitzat el procés perquè només es modifiquin i es registrin en l'historial de canvis (`LogSupplyPointChange`) els punts de subministrament que realment han canviat de finca o que han estat desvinculats.

### MODIFIED
#### STATISTICS
    - tasks.py: S'ha acotat la normalització de `remittance_id` a `id` perquè només s'apliqui als informes `aqua_remittance_report`, `wallet_unpaid_summary` i `wallet_all_unpaid_summary`. Això evita que en altres informes s'utilitzi un ID de remesa com a ID de facturació quan no hi ha cap facturació seleccionada peró sí una remesa global.
    - tasks.py: S'ha afegit un mapeig independent per als tres nous noms de funcions d'informes de comptabilitat (`accounting_values_invoice_report`, `accounting_values_payment_report` i `accounting_values_commitment_report`) per configurar automàticament `accounting_type` a `INVOICE`, `PAYMENT` o `COMMITMENT` abans d'executar el generador, normalitzant posteriorment el nom de la funció cap a `accounting_values_report`.
    - report_wallet_service.py: S'ha adaptat la generació de l'informe de retorn SEPA (`wallet_unpaid_summary` / `wallet_all_unpaid_summary`) perquè accepti `remittance_id` com a filtre alternatiu a `date_range`. En cas d'especificar-se, s'obtenen els pagaments associats directament a la remesa indicada, i les dates d'inici i fi de l'informe es calculen automàticament a partir de la data de la remesa.
    - report_service.py: Corregits els atributs de `CommitmentDeposit` a la generació de l'informe comptable per utilitzar els camps reals del model: `com.total` (import total) i `com.remaining` (pendent/restant) en lloc de `com.amount` i `com.current_remaining`, solucionant així un error de tipus `AttributeError` en generar l'informe de compromisos.
    - Migracions: Nova migració de dades `0026_update_accounting_reports.py` per registrar els nous noms de funció únics, noms en català i l'activació dels tres informes de comptabilitat a la base de dades.
#### BILLING
    - Facturació NO agafa lectures si ja estàn facturades

## [20-05-2026]

### MODIFIED
#### STATISTICS
    - Modificar el nom de l'arxiu de l'ACA per a que coincidèixi amb el període de facturació que estem declarant

#### BILLING
    - Billing tasks. Ara tant al assignar lectures a un lot de lectures com mirar les lectures per processar un lot de facturació, mirarà que només estigui la última lectura per contracte i comptador
    - CommitmentDeposit s'han reduït tots 2 digits. Els pagaments actuals es mantenen igual però els propers sortiràn correctament amb 11 digits per afegir al codi de barres
    - ReadingBatchMinimalSerializer: S'han afegit els camps de mètrica `num_contracts`, `num_read_contracts` i `num_supplies` calculats mitjançant agregacions eficients a nivell de base de dades per al llistat de lots de lectura.

### CHORE
#### IMPORTEXPORT
    - Afegit fitxer per eliminar explotacions i els seus models relacionats (supplypoints, properties ...)
    - Afegit fitxer per eliminar les persones sense contracte d'una explotació
    - **Comanda `delete_route`**: Nova comanda `python manage.py delete_route --id <id>` per eliminar una `Route` i les `RoutePosition` associades (les propietats queden amb `route_position` a NULL); desvincula billings i lots de lectura (M2M). Admet `--dry-run` i múltiples IDs separats per comes.

### FIX
#### STATISTICS
    - **Ajustos al fitxer de declaració ACA (V2 - CSV)**:
      - S'ha corregit el valor de `aca_code` perquè utilitzi `exploitations.first().code` en lloc de `supply_code`.
      - S'ha afegit la constant `"DMC"` a la línia de capçalera (`header_line`).
      - S'ha corregit l'ordre dels camps del registre `"20"` a `new_line`, col·locant primer `aca_code` i després `exploitation_instance.supply_code`.
      - S'ha restaurat l'ordre original de camps (nom, codi, codi de subministrament) a l'informe Excel (V1) de l'ACA.
    - **Informe d'Ingrés detallat per tipologia i periodicitat**:
      - S'ha afegit la columna `"Data Moviment Cartera"` al full `"Detall Registres"` de l'informe Excel per mostrar de forma informativa la data o dates del moviment de cartera associats a cada factura detallada.
    - **Informe de facturació resumida (Mini Register Billing Summary)**:
      - S'ha implementat l'agrupació de les línies de l'informe per producte (`product_name`) i tram (`interval`) consolidant tots els consums i conceptes sota una única llista global per explotació.
      - S'ha resolt la duplicació en la suma de m³ sumant només el producte de consum d'aigua principal per a les tarifes que el contenen.
      - S'ha afegit la detecció robusta del producte d'aigua de consum per nom i prefix del token.
      - S'han afegit noves files de desglossament per detallar la composició de la facturació: `TOTAL M3 (Consum Brut)`, `TOTAL M3 FACTURAT ALS TRAMS (AIGUA)`, `TOTAL ESTIMAT RESTAT M3` i `TOTAL M3 POU PROPI / SENSE PRODUCTE AIGUA`, de manera que quadrin exactament tots els m³ facturats amb el total de capçalera.
      - S'ha corregit l'etiqueta de les línies corresponents a l'interval 0: es mostren com a `M3` si és un producte volumètric (Aigua, Cànon ACA, Clavegueram) i com a `QUOTES/UNITATS` per a quotes fixes o conceptes de manteniment/conservació.

## [19-05-2026]

### FEAT
#### STATISTICS
    - **Nova pestanya a l'Informe de Tipologia**: S'ha afegit el nou full "Consum i Quotes per Ruta" a l'informe d'Ingrés detallat per tipologia i periodicitat (`generate_detailed_typology_periodicity_report`). Aquest full creua la informació per les rutes de subministrament i mostra columnes agrupades amb subcolumnes específiques per a **Aigua** (núm. factures, m³ facturats, quota servei, consum €) i **Clavegueram** (núm. factures, m³ facturats, quota servei, consum €). A més, s'inclouen dinàmicament els grups de **Recaptació/Rec**, **Escomeses** i **Comptadors** només si s'han facturat conceptes d'aquest tipus en el període seleccionat, per tal d'evitar mostrar columnes totalment buides.

### CHORE
#### WATCHDOG
    - **main_company_token vs Company.vat**: Nova comprovació que `ConfigProject` amb token `main_company_token` tingui un valor no buit i que coincideixi amb algun `Company.vat`. En cas d'error, el sniff recomana `python manage.py watchdog_fix_main_company_token`, que assigna el NIF de la primera `Company` (id ASC).
    - **Country, Province i City per defecte**: Nova comprovació que a `Coredata.Country`, `Coredata.Province` i `Coredata.City` hi hagi almenys un registre amb `is_default=True`. En cas d'error, recomana `python manage.py watchdog_fix_default_geo_from_company`, que marca per defecte el país, província i ciutat de l'adreça de la primera `Company` (id ASC).

#### IMPORTEXPORT
    - **Comanda `delete_billing`**: Nova comanda de gestió `python manage.py delete_billing --id <id>` per eliminar un `Billing` per ID. Esborra les factures associades (incloent les de billings exclosos fills) amb la mateixa cascada que `delete_invoice`; la resta de relacions (`BillingBatch`, `Reading`, `ReadingBatch`, rutes i billings exclosos) es desvinculen abans d'eliminar el registre. Admet `--dry-run` i múltiples IDs separats per comes.
    - **Comanda `delete_readingbatch`**: Nova comanda de gestió `python manage.py delete_readingbatch --id <id>` per eliminar un `ReadingBatch` per ID. Desvincula lectures, documents de lectura, rutes, comptadors (`fix_meters`) i lots exclosos fills abans d'eliminar el registre. Admet `--dry-run` i múltiples IDs separats per comes.

#### TRANSLATIONS
    - S'han afegit les traduccions oficials per al nou "Informe de Recaptació" (i la seva descripció) i per als valors de `payment_origin` ("Box Office" -> "Oficina", "Post Office" -> "Correus") en català, castellà i anglès als fitxers `.po`, i s'han compilat correctament.

### MODIFIED
#### WATCHDOG
    - **Contractes Actius amb Lectures Anteriors a Creació**: La comprovació usa `registration_date` i, si és buida, `created_at`; el missatge d'error inclou la diferència en dies i el camp de referència. Recomana `python manage.py watchdog_fix_contract_registration_date_from_readings --max N` (amb `--dry-run` opcional), que assigna `registration_date` a la lectura més antiga en conflicte només si la diferència és ≤ `--max`.

#### BILLING
    - Generar i obtenir factures electròniques per un procés apart ara es fa des d'un view de Invoice: get-e-invoice. I l'obtenció de document es fa per celery

### FIX
#### BILLING
    - send_payment_remittances() en tasks, sent_at que SEMPRE sigui la data que li estem passant. No té sentit una altra
    - **PAYMENT_ORIGIN_CHOICES**: S'ha actualitzat el model `PaymentMovement` a `billing/models.py` per utilitzar `gettext_lazy` (`_`) a les opcions de `PAYMENT_ORIGIN_CHOICES`, permetent la seva traducció dinàmica al backend.
    - **Gestió massiva de factures**: S'han exclòs les factures ja pagades i s'ha limitat la cerca per filtrar exclusivament les modalitats de pagament en efectiu (`CASH`) o domiciliació bancària (`DIRECT_DEBIT`) a `InvoiceManageMassivelyViewSet`.
    - **IVA negatiu a factures rectificatives**: Es corregeix la funció `return_invoice` a `billing/utils/invoice_service.py` per negar correctament el camp `tax_price` (IVA) quan es genera la factura rectificativa/d'abonament, de manera que es desi com a valor negatiu a la base de dades.
    - **Filtre de lectures de control**: S'ha afegit el filtre `is_control=False` a diverses consultes i llistats de lots de lectura (incloent l'exportació a CSV i el càlcul de mitjanes/alertes a `reading_view.py` i `reading_by_batch_csv_export_view.py`), assegurant que les lectures de control no interfereixin en els llistats generals ni s'exportin de forma errònia.

#### STATISTICS
    - **Adaptació de la versió de l'informe ACA**: S'ha actualitzat la tasca de Celery `run_report_task` a `statistics/tasks.py` perquè, quan es crida a l'informe ACA (`aca_summary_report`) des de l'endpoint genèric de trigger d'informes disponibles i es rep el paràmetre `"version": 2`, es redirigeixi automàticament cap a la funció de la segona versió (`aca_summary_report_second_ver`), permetent que el frontal generi de forma autònoma l'informe en format CSV per a la seva pujada directa.
    - S'ha canviat el nom del fitxer per presentar a l'ACA de manera automàtica (fitxer .csv) per tal d'adapta-nos al nou format 
    - **Enforce default language & Fallback**: S'ha forçat l'ús del settings.LANGUAGE_CODE en els camps traduïts de `AvailableReportSerializer` i tasques de Celery. Per evitar que es mostri en català quan al fitxer `.env` s'ha definit `LANGUAGE=es` en lloc de `LANGUAGE_CODE=es`, s'ha actualitzat `customers/settings.py` perquè `LANGUAGE_CODE` agafi com a fallback el valor de la variable `LANGUAGE`.
    - **Millora classificació de Riego (Rec)**: S'ha estès la cerca de línies de factura classificades com a reg ("Rec") per cercar la presència de `"RIEGO"` o `"REG"` tant en el nom del producte com en el nom de la tarifa (`price_rate_name` i `price_rate__name`), garantint la compatibilitat amb el nom de tarifa RIEGO configurat pel client.
    - **Informe de Recaptació (ex-Clavegueram)**: S'ha rebatejat l'informe de clavegueram a la base de dades i a les tasques com a "Informe de Recaptació" (`recaptacio_excel_report`), actualitzant tant els endpoints de l'API (`/api/statistics/billing/recaptacio-summary`), el seed de la base de dades a la migració `0024`, com els enrutaments de Celery. S'ha realitzat un rollback i posterior migració de dades per a reflectir aquest canvi de manera consistent.

## [18-05-2026]

### FEAT
#### CONTRACT
    - S'ha afegit un checkbox a ContractTermination per si es vol finalitzar la baixa sense Factura, que no surti tota l'estona l'avís de que li falta
    - Dissenyat i implementat un sistema complet de validació de dades per a les sol·licituds d'alta de contracte (`ContractRequest`) abans de finalitzar-les o de crear el contracte.
    - Creat el nou endpoint `GET /api/contract-requests/{id}/validate-data/` per a validació activa en temps real, que comprova la integritat del titular, punt de subministrament per defecte, adreça de facturació completa (amb suport per a les regles de carrerer d'AGENTS.md) i dades bancàries SEPA obligatòries.
    - S'han protegit els endpoints de finalització (`FinalizeContractRequestView`) i de creació de contractes (`ContractRequestCreateContractView`) per llançar un error `400 Bad Request` amb el llistat detallat de dades mancants si la validació de dades no és satisfactòria.

#### STATISTICS
    - Dissenyat i implementat el nou model d'informes dinàmics `AvailableReport` a [models.py] per a la gestió directa dels informes actius per part dels administradors.
    - Dissenyat el ViewSet `AvailableReportViewSet` a [available_report_view.py] que ofereix operacions CRUD, l'endpoint `active-list` i l'endpoint genèric de llançament asíncron `trigger` a través de Celery (`run_report_task`).
    - Registrades les noves rutes a [urls.py] sota el prefix `/api/statistics/available-reports/`.
    - Registrat el model `AvailableReport` al Django Admin de [admin.py] per a la gestió directa dels informes actius per part dels administradors.

#### BILLING
    - Afegit nou model 'JoinedPayment'. Semblant a com funciona una remesa SEPA. Agafa pagaments pendent i els agrupa, deixant pagar en conjunt amb transferència o per codi de barres. Tot això implica:
        - Nou model, serializer, view, filter i url
        - Nou estat 'JoinedPaymentStatus' amb nou .json i valors a ConfigProject
        - Nou logger per guardar canvis d'estat
        - Nous pull templates
        - Canvis al serializers de Invoice, Payment i CommitmentDeposit per limitar canvis i modificacions mentre aquest pagament agrupat està actiu.
        - Al filtrar pagaments per una remesa, evita els pagaments que estàn a un 'JoinedPayment' actiu
        - Nou template 'grouped_payment_template' per aquests pagaments    

### CHORE
#### STATISTICS
    - Creat el nou serialitzador `AvailableReportSerializer` a [serializers.py] que permet la traducció automàtica de qualsevol d'aquests camps a l'idioma sol·licitat pel frontal utilitzant directament els diccionaris `.po` del backend.
    - Generada la migració d'estructura `0023_availablereport.py` i la migració de dades consolidada `0024_seed_available_reports.py`. Aquesta darrera unifica tota la pre-població, configuració i classificació de dades del sistema. A més, s'han refós i unificat directament en aquesta migració totes les millores posteriors (definició del component de dates unificat `date_range`, configuració personalitzada de `remittance_id` a l'informe de remeses i l'ordenació seqüencial contigua dels resums comptables actius i inactius), optimitzant i reduint l'historial a només dues migracions per a futurs desplegaments en servidors de producció o equips de treball.
    - Implementada una capa de retrocompatibilitat robusta a [report_service.py] per normalitzar els valors de payload històrics del frontal (`INVOICES` i `COMMITMENTDEPOSIT`) cap als valors requerits pel motor de generació del back-end (`INVOICE` i `COMMITMENT`).
    - Incorporada una capa de normalització bidireccional i completament robusta de paràmetres a la tasca de Celery `run_report_task` a [tasks.py] per a traduir automàticament i bidireccionalment entre el format de llista `date_range` i els camps de dades individuals `start_date` / `end_date`, a més de resoldre silenciosament fallbacks entre `id`, `billing_id` i `remittance_id` i **assegurar un formatat ISO-8601 estricte (`YYYY-MM-DDTHH:MM:SS.fffZ`)** per a tots els elements de dades temporals, evitant qualsevol error de sintaxi amb els motors Excel legacy.
    - El fitxer d'entrada de lectures ara és configurable

### FIX
#### STATISTICS
    - **Remeses Aqua (ID 77)**: Corregida la configuració de dades a la base de dades a través de la nova migració `0026_fix_available_reports_config.py` perquè demani estrictament el filtre `remittance_id` i s'activi `has_custom_config = True`. Això fa que el frontal pinti immediatament el botó "Selecciona Remesa" enlloc del seleccionador de dates, evitant així l'error `"remittance id is required."`.
    - **Resum comptable (ID 76)**: Corregit l'error `"Report not implemented"` implementant un fallback automàtic tant al motor de generació de `report_service.py` com a la tasca de Celery de `tasks.py` perquè s'assigni per defecte `"INVOICE"` (el comportament esperat per al resum d'assentaments actiu) si no es rep cap paràmetre `accounting_type`. A més, s'actualitza el resolutor del frontal a `add.vue` perquè reconegui `accounting_values_report` de la mateixa manera que `getAccountSummary`. **Corregit també l'error d'abast de variables en què `row` només s'inicialitzava dins de la branca `PAYMENT`, fent que fallés amb `UnboundLocalError` per a qualsevol altre tipus (INVOICE / COMMITMENT). Ara s'inicialitza globalment a l'inici de la funció.**

#### SERVICE
    - s'ha esborrat field='token' del generate_token a cluster_nozzle_serializer i supply_point_serializer

#### BILLING
    - S'han canviat les cometes dobles per cometes simples del fitxer `joined_payment_services.py` perquè sinó al llençar el `python manage.py loaddata prometeo/data/billing.JoinedPaymentStatus.json`, generava un error a la terminal.
    - `reading_batch_generate_view.py`: S'ha millorat la precisió i el filtratge en el sumatori de lots de lectura (`ReadingBatchSummaryView`). Ara es filtren els punts de subministrament sense ruta per incloure només aquells amb comptador actiu, contracte actiu i estat de subministrament actiu o tallat (`supply_point_status_activate_token` / `supply_point_status_cut_token`). També s'han corregit les sumes de `num_supplies`, `num_contracts` i `num_no_meter` per evitar duplicats i comportaments inesperats de concatenació/suma.

#### COREDATA
    - Sistema de creació de finques (`Property`): Es corregeix l'error d'intercanvi de dades on el camp `token` guardava l'adreça i el camp `name` quedava buit en la creació de finques des dels serializers de Punts de Subministrament (`SupplyPointSerializer`) i Bateries (`ClusterSaveSerializer`).
    - Ara, les finques es creen correctament generant un token únic a través de `generate_token` (amb codi de control `PROPN`) i comprovant-ne la unicitat amb `check_token_exists`, i emmagatzemant l'adreça descriptiva de la finca al camp `name`.
    - S'ha afegit un fallback de seguretat equivalent directament al serialitzador base de finques (`PropertySerializer`) en cas que no s'enviïn `name` o `token` en peticions directes de l'API.
    - S'ha automatitzat la vinculació de les noves finques creades a una ruta utilitzant `auto_assign_route_to_property` quan no es rep una posició de ruta explícita, exactament igual que en la creació autònoma.

## [15-05-2026]

### FIX


### CONTRACT
    - general_payment_sepa_document_view.py -> Hi han 'GeneralPayment' que guarden sense titular. En aquest cas peta al intentar guardar el document de SEPA. Ara si no té 'name' agafa el seu 'dni'

#### COREDATA
    - Sistema de Carrerer i Adreces (`partial_address_view.py` i `serializers.py`): S'ha refet la lògica de gestió d'adreces per evitar la modificació accidental de registres compartits. Ara el sistema utilitza sempre un patró de "cerca o creació" en lloc d'actualitzar registres en calent, garantint que si dos abonats comparteixen adreça i un d'ells la canvia, l'altre no es vegi afectat.
    - Normalització de dades: S'ha implementat la neteja automàtica d'espais (`strip`) i la conversió de valors nuls a cadenes buides per als camps `name`, `name_2`, `number_suffix` i `number_end_suffix`. Això resol el problema de duplicats al carrerer causats per discrepàncies entre `NULL` i `''` o espais accidentals.
    - Millora en la cerca de carrers: S'han inclòs els camps `name_2` i `type` (tipus de carrer) en totes les consultes de validació, assegurant una identificació unívoca i evitant col·lisions entre carrers amb noms similars.

#### STATISTICS
    - report_billing_service.py: Creat el nou informe de recaptació per conceptes dinàmic (`generate_recaptacio_conceptes_excel`) accessible des de l'endpoint `/statistics/billing/recaptacio-conceptes-summary`.
    - report_wallet_service.py: Analitzat el funcionament dels fraccionaments en l'informe d'impagats globals, verificant que cada quota impagada es mostra de forma individual vinculada al seu "compromís de pagament".
    - report_wallet_service.py: S'ha implementat un filtre als informes d'impagats per ometre automàticament aquells compromisos de pagament que hagin estat anul·lats (`token='-1'`), assegurant que no es comptabilitzin deutes de fraccionaments cancel·lats.

#### BILLING
    - Reordenació manual d'elements de pressupostos i factures personalitzades: S'ha afegit el camp `custom_order` al model `InvoiceLineItem` i s'ha creat la migració `0278_invoicelineitem_custom_order.py`. S'ha actualitzat `InvoiceLineItemSerializer` i la injecció al document PDF (`invoice_pdf.py`) per respectar l'ordre definit per l'usuari. A nivell de plantilles PDF s'ha eliminat la reordenació alfabètica de productes (`dictsort:"product_name"`) a `invoice_request_template.html`, s'ha incorporat a `InvoiceViewEdit.vue` una interfície amb botons de pujar i baixar per gestionar l'ordenació i desar-la de forma persistent, i s'ha substituït el filtre de reordenació alfabètica hardcoded a `InvoiceView.vue` pel criteri de `custom_order` per assolir una concordança absoluta a tot el sistema.
    - general_payment_sepa_document_view.py: S'ha corregit un `AttributeError` i un `NameError` en la càrrega de documents SEPA. Ara es gestiona correctament quan el compte bancari no té nom assignat o és un compte d'empresa, assegurant una resolució segura del nom de la carpeta de destinació (`folder_name`).

## [14-05-2026]

### CHORE
    - Watchdog per avisar que el main_company_token no coordina amb cap empresa del sistema.
    - Watchdog per avisar que un contracte no té cap tarifa assignada.

#### LECTURAPP
    - tasks.py: Ordenació de comptadors per posició en bateria.

### MODIFIED
#### STATISTICS
    - Informes de cartera i impagats (`report_wallet_service.py`): S'han unificat els informes de resum d'impagats (`wallet-unpaid-summary` i `wallet-unpaid-detailed-summary`) en un únic fitxer Excel amb dues pestanyes diferenciades ("Resumen recibos" i "Detalle recibos"), optimitzant la càrrega de relacions i canviant el prefix del fitxer generat a `retorn_sepa_`. Addicionalment s'ha creat un nou informe global d'impagats (`wallet-all-unpaid-summary`) que inclou tots els rebuts en estat vençut, retornat o morositat independentment de si la seva modalitat de pagament és domiciliació bancària o qualsevol altra.

#### COREDATA
    - models.py: S'ha canviat el camp `email` del model `PersonContact` d'un camp `EmailField` a un camp `CharField(max_length=255)` i s'ha generat la migració corresponent (`0101_alter_personcontact_email.py`). Això permet guardar diverses adreces de correu a la base de dades sense que les peticions `PATCH` de modificació de dades fallin per validacions estrictes de format en el serialitzador.

#### BILLING
    - report_billing_service ara el report del aca, la part de detall de factures, mostra per separat la part variable i la part fixa
    - Reversió de noms d'estats i classes de factura: S'ha revertit la conversió a tokens de les taules `InvoiceStatus` i `InvoiceClass` implementada ahir, restaurant els seus noms en text literal (ex. "Pre-factura", "Pagada", "Original", etc.) mitjançant la migració de dades `0277` i actualitzant els fitxers de llavors (`prometeo/data/` i `prometeo/data_es/`). Es mantenen en format tokenitzat exclusivament les alertes de lectura (`ReadingAlert` i la nova alerta de consum inusualment baix).
    - Renderització de PDFs (Factures i Compromisos): S'han actualitzat `invoice_pdf.py` i `payment_pdf_service.py` perquè injectin de manera prioritària el compte bancari de l'empresa seleccionat (`payment_company_bank`) al document generat. En cas de no haver-n'hi cap d'explícit, es fa un fallback automàtic al compte bancari actiu per defecte de l'empresa (`company_bank`). Addicionalment, s'han enriquit les plantilles d'exemple (`payment_doc_template.html` i `invoice_request_template.html`) mostrant el nom de l'entitat dinàmicament (`{{ company_bank.bank.name }}`) a les seccions de transferència bancària, mantenint intencionadament fixa l'opció de `CAIXABANK` per al pagament de codis de barres als caixers automàtics.

### FIX
#### BILLING
    - payment_pdf_service.py: S'ha corregit la cascada de resolució del compte bancari en generar documents de compromís de pagament per transferència per prioritzar el compte específic seleccionat i guardat a `payment.payment_bank`, evitant que el PDF continuï mostrant sempre l'IBAN predeterminat del contracte o l'explotació.
    - invoice_serializer.py: S'ha afegit una validació de seguretat per comprovar l'existència de l'objecte `status` abans d'accedir a les seves propietats a `InvoiceMinimalSerializer` i altres mètodes, resolent un `AttributeError` en llistats de factures.
    - commitment_deposit_service.py: S'ha eliminat la injecció de la clau inexistent `payment_company_bank` en la creació del model `Payment`, evitant un `TypeError` fatal en processar pagaments de compromisos.
    - generate_invoice_budget_view.py: S'han inicialitzat prèviament les variables `company_bank`, `payment_type`, `payment_bank` i `electronic_data` a `None` per prevenir l'excepció `UnboundLocalError` quan les peticions no inclouen `payment_data`.

## [13-05-2026]

### FEAT
#### BILLING
    - reading_service.py: Implementar nova alerta de consum inusualment baix (`reading_alert_low_consumption`) simètrica a la de consum alt (caiguda de més del 50% de la mitjana/històric).
    - reading_service.py: Crear i integrar el model `LogReadingChange` per registrar automàticament l'històric d'auditoria tant de les modificacions de lectures existents com de les noves creacions enviades des del front (`readings_data`), traçant els valors anteriors/actuals, contracte, comptador, observació/origen i l'usuari responsable.

#### CONTRACT
    - bail_view.py: Crear nou endpoint per a la cancel·lació de fiances via `POST` a `/contract/bail/cancel/`, passant un llistat d'identificadors o tokens (ex. `"05604974/001"`) dins `bail_ids` per canviar el seu estat a `"Cancelled"`, desactivar-les (`is_active = False`) i conservar la traça al `LogBailStatus`.
    - Linked contract directly to company to allow having two companies working at the same time.

### MODIFIED
#### BILLING
    - reading_service.py: Neteja automàtica d'alertes prèvies en les lectures si en re-processar el lot ja no es detecten anomalies (es fa `reading.alert = alert` directament).
    - Internacionalització i Refacció d'estats/alertes: S'ha creat la migració de dades `0276` per convertir tots els valors literals emmagatzemats als camps `name` de les taules `ReadingAlert`, `InvoiceStatus` i `InvoiceClass` en claus d'internacionalització unívoques (`reading_alert_*`, `invoice_status_*`, `invoice_class_*`). S'han actualitzat els fitxers de càrrega inicial (`prometeo/data/` i `prometeo/data_es/`) i s'ha eliminat la traducció via `gettext` al backend per retornar directament les claus al frontend, delegant tota la responsabilitat de localització visual a l'aplicació client.
#### STATISTICS
    - Normalització de noms de fitxers d'informes: Modificats `report_service.py`, `report_wallet_service.py` i `report_billing_service.py` per generar tots els informes i llistats amb un sufix de marca de temps dinàmica completa (`%Y%m%d_%H%M%S`), evitant sobreescriure fitxers generats anteriorment en el mateix mes i preservant l'històric complet de documents.
    - report_billing_service.py: Afegida la columna d'origen de pagament (`origen de pagament`) a l'Informe de cobraments per permetre la traçabilitat del canal pel qual s'ha efectuat l'ingrés o devolució.
    - report_billing_service.py: Modificat l'Informe de clavegueram per calcular sempre la columna "Període Liquidat" en format trimestral (`<T>T <Any>`) a partir de la data del moviment de cartera, eliminant el càlcul condicional segons la periodicitat del client.

### FIX
#### BILLING
    - reading_service.py: Corregit el parseig del camp `previous_reading_option_key` en afegir o modificar lectures, extreient directament la lectura anterior a partir del `previous_reading_id` o processant l'estructura separada per barres (`|`), evitant que el valor anterior quedi a `None` en el registre de `LogReadingChange`.
#### STATISTICS
    - report_billing_service.py: Corregida la pauta de suma al "Resum de facturació" per sumar directament els valors ja calculats i guardats a la base de dades (`sum_tax=Sum('line_items__tax_price')`) en lloc d'aplicar el càlcul matemàtic de l'IVA sobre les bases agregades en memòria. Això elimina qualsevol distorsió per re-arrodoniment intern i blinda la precisiòn comptable.
    - report_billing_service.py: Afegit el filtre estricte `is_active=True` sobre les línies de detall per evitar incloure al sumatori global de facturació imports provinents de línies de factura cancel·lades o re-calculades.
    - report_advanced_billing_service.py: Netejada la visualització de l'informe de "Tipologia i Periodicitat" descartant la fila d'ajustos i fent que el TOTAL FACTURACIÓ correspongui mil·limètricament a la suma real de totes les línies de detall mostrades a la taula.

## [12-05-2026]

### FEAT
#### BILLING
    - Afegida la funcionalitat de configuració de columnes per a la exportació de lots de lectura.

### CHORE
    - Prometeo. Afegit parametre de language per fer `ca` o `es` i fer demos amb espanyol. s'ha renombrat la carpeta data_spanish per data_es per fer-ho més equivalent al paràmetre.

### MODIFIED
#### BILLING
    - bank_rnd_view.py: Garantit que l'origen de pagament (`payment_origin`) es registri sempre en el darrer moviment associat al pagament en processar la càrrega definitiva d'un fitxer de retorn bancari (`is_saving=True`), tant per a pagaments ja pagats prèviament com per als que es marquen com a pagats durant aquest procés.
#### STATISTICS
    - report_service.py: Implementació d'un sistema de personalització que permet sobreescriure funcions del mòdul base mitjançant un fitxer `report_service_personalized` per client, seguint el mateix patró que a report_billing_service.py.

### FIX
#### OV
    - create_reading_serialized.py quan calcula el calculated value peta per float i decimal
#### STATISTICS
    - report_billing_service.py: Millorat el tractament dels compromisos de pagament vinculats a factures a l'informe de cobraments, generant files independents per a cada factura i prorratejant els imports cobrats segons el pes proporcional de cada factura sobre el total del compromís.
    - report_advanced_billing_service.py: Refet l'informe "Ingrés detallat per tipologia i periodicitat" per extreure les columnes de Producte i Tarifa segons l'estructura de dades de l'API (`price_rate__product__name` i `price_rate__name`).

## [11-05-2026]

### CHORE
    - send_test_email.py: Nou paràmetre `--config-token` per carregar la configuració SMTP des de `CompanyConfig` (amb password des de `.env`).
    - Deploy: exemples de private amb mina amb Dockers i sense dockers.

### FIX
#### BILLING
    - payment_view.py i invoice_view.py al retornar/abonar una factura, si és una sol. de contracte o no té pas un contracte assignat i està pagat per saldo, només tractar amb el saldo de la persona, no el del contracte
    - report_billing_service.py, fitxer aca calcula pels industrial només el concepte general, no pas el específic. 
    - payment/invoice serializer, mostra el total del saldo de persona en cas de no tenir un contracte associat per permetre pagar factures, també afegit retorn a bossa quan s'abona (invoice view 'return')
    - reading_batch_estimate_view.py: Adaptada la vista `ReadingBatchEstimateViewSet` per acceptar paràmetres de configuració de data d'estimació (`estimation_type`, `reading_date`, `days_from_last`).
    - tasks.py: Actualitzada la tasca `estimate_readings_task` per utilitzar la data d'estimació calculada de forma dinàmica.
    - reports_views.py: Solucionat `IndentationError` per duplicitat de definició de la classe `ReportCobramentsSummary`.
    - manage_commitment_deposit_request_view.py: Solucionat `UnboundLocalError` al processar factures sense contracte associat i permesa la creació de compromisos de pagament per a factures d'altres orígens.
    - commitment_deposit_serializer.py: Corregit `AttributeError` en accedir a dades del contracte inexistents. Ara es proporciona una estructura d'objecte segura i dades de fallback (nom i document del client) per al frontend.
    - commitment_deposit_pdf_view.py: Solucionat `AttributeError` en la generació de PDFs per a dipòsits sense contracte, utilitzant les dades de client i adreça registrades en el propi dipòsit.
    - reading_filter.py: Solucionat `AttributeError` en el filtratge de lectures sense factura associada. Ara es retorna un queryset buit en lloc d'un error.
#### CORE
    - partial_address_view.py: Solucionat l'error `MultipleObjectsReturned` en la creació de carrers i tipus de carrer. Implementada lògica per garantir la creació de nous carrers quan la ciutat és diferent, evitant col·lisions amb registres existents que tenen la ciutat buida.
#### STATISTICS
    - report_billing_service.py: Nou informe de cobraments i devolucions (`generate_cobraments_report`) amb prorrateig de costos (Aigua, Clavegueram, Cànon) i suport per a valors negatius en devolucions.
    - report_billing_service.py: Corregit error de `select_related` en l'accés al camp `payment_type` dins de l'informe de cobraments.
    - report_advanced_billing_service.py: Nous informes avançats: Ingrés per tipologia i periodicitat, Ingrés detallat per concepte, Ingressos no tarifaris, Evolució d'abonats, Evolució de tarifa social, Temps de resposta de reclamacions i Volum de gestions.
    - report_wallet_service.py: Millores en els informes de cartera, llistats de bancs i resum de cobraments.
    - reports_views.py: Nova vista `ReportCobramentsSummary` i endpoint `/api/statistics/billing/cobraments-summary` per a la generació de l'informe de cobraments.
    - tasks.py: Registrada la tasca `cobraments_excel_report` per a la generació asíncrona de l'informe.

## [08-05-2026]

### MODIFIED
CORE
***
    - other_utils.py -> round_ceil added option to round 0 up to 1 in case 0 is decimal
    - 0099_add_incident_closed_status_config.py: Nova configuració `incident_status_closed_token` per identificar dinàmicament l'estat tancat dels incidents.
STATISTICS
***
    - report_billing_service.py: Implementació d'un sistema de personalització que permet sobreescriure funcions del mòdul base mitjançant un fitxer `personalized` per client.
    - report_billing_service_personalized.py (customers-clients-data): Neteja del fitxer personalitzat per deixar només les funcions amb lògica específica, garantint que les noves funcionalitats (com el report de Clavegueram) s'heretin correctament del fitxer base.
BILLING
***
    - generate_invoice_budget_view.py: Permesa la vinculació de factures de pressupost o consum manual a un `Billing` o `BillingBatch` existent mitjançant els nous paràmetres `billing_id` i `billing_batch_id`.
    - invoice_service.py: Actualitzada la generació de factures de lectura de tall per permetre el flag `bill_termination_requester`, permetent decidir si es factura al titular que marxa o al que entra.
    - invoice_service.py: Garantida la visibilitat de les factures de lectura de tall des de la sol·licitud de baixa, mantenint la vinculació amb `contract_termination` fins i tot en altes vinculades.
    - generate_invoice_budget_view.py: Afegit suport per al paràmetre `bill_termination_requester` en la generació manual de factures i pressupostos.
    - Millora de la plantilla genèrica perquè es vegi millor en noves implantacions
CONTRACT
***
    - contract_service.py: Eliminada la generació automàtica de factures de lectura de tall en activar un contracte per passar a un flux totalment manual i controlat.
    - contract_request_service.py: Eliminada la generació automàtica de factures de lectura de tall en finalitzar una sol·licitud de baixa.
    - comentat linies 242-253 a contracte_create() NO hauria de crear una factura automàticament
    - ContractTerminationRequestFilter: Afegit filtratge per nif i cognoms de la persona en la cerca de sol·licituds de baixa de contracte.
#### NOTIFICATION
    - IncidentViewSet: Implementat `perform_update` per tancar automàticament totes les ordres associades a un incident quan es marca el flag `close_associated_orders`.
    - IncidentSerializer: Afegit camp `orders` i millorada la resolució del token de l'ordre vinculada (`order_token`) quan s'utilitza la relació inversa.

## [07-05-2026]

### CHORE
CORE
***
    - fix_inactive_supply_points: Nou script de gestió per actualitzar l'estat dels supply points de contractes de baixa.
    - fix_inactive_meters: Nou script de gestió per actualitzar l'estat dels meters associats a contractes de baixa.

### FIX
BILLING
***
    - invoice_service.py: Correcció d'UnboundLocalError per a la variable prev_reading i prevenció de TypeError en comparacions de dates.
    - generate_invoice_budget_view.py: Millora de robustesa en la gestió de factures i lectures vinculades.
    - invoice_service.py: En factures de baixa vinculades a una alta amb lectura de tall, la factura es vincula ara al nou contracte/sol·licitud d'alta i es desvincula de la baixa. Per les baixes sense lectura de tall marcada segueix facturant al contracte de baixa.
    - recalculate_invoice_service.py.py: Solucionat un bug que no permetia recalcular factures.
    - invoice_line_item_service.py: Solucionat un bug que no permetia facturar el tram 1 quan tenia consum 0 tot i tenir preu fix.

## [06-05-2026]

### FEAT
CONTRACT
***
    - termination_date: Implementació del camp al model Contract per registrar la data de baixa efectiva, incloent automatització en el tancament de contractes.

BILLING
***
    - Suport per a facturació de comunitats: D'habitatges mitjançant la variable de contracte "General" per definir el nombre d'unitats residencials.

### CHORE
ORDER
***
    - OrderSaveSerializer.create: Millora de la inferència automàtica de l'adreça i el motiu (reason) a partir d'objectes relacionats (com connection_request, supply_point o contract) quan aquests no es reben en la petició POST.
    - Sincronització de coordenades: (latitude, longitude) a les ordres des de connection_request en el moment de la creació.

CONTRACT
***
    - fill_contract_termination_date: Nou script de gestió per a la càrrega retroactiva de dates de baixa a partir de l'historial de logs i sol·licituds.
    - 0218_contract_termination_date.py: Integració de l'script de càrrega de dades directament en la migració.

### MODIFIED
CONTRACT
***
    - ContractTerminationRequestSerializer: invoices filtre les abonades.
    - contract/models.py: Afegit camp termination_date i exposat en els serialitzadors de l'API.
    - CloseContractTerminationRequestViewSet: Registre automàtic de la data de baixa en confirmar el tancament.
    - ContractTerminationRequestViewSet: Gestió de la neteja del camp termination_date en cancel·lar sol·licituds.
ORDER
***
    - OrderListSerializer: Inclusió dels camps reason_token, reason_name i address_complete per garantir que la informació de motiu i adreça es mostri correctament en els llistats d'ordres (vistes simple_list).
BILLING
***
    - invoice_service.py: Millora de pre_check_readings per forçar el recàlcul de dies de consum i valors calculats, garantint la integritat de les dades durant la generació i recàlcul de factures.
    - billing_invoices_view.py: Sincronització dels comptadors de resum de facturació (BillingInvoicesSummaryViewSet) i la llista filtrada de factures, excloent les factures marcades com a excloses (is_excluded) en el càlcul de mitjanes i alertes.
    - billing/tasks.py: estimate_readings_task() s'ha mogut obtenció de target_date a més adalt per arreglar error de valor no declarat.
    - invoice_service.py: Al generar una factura d'aigua, ara només mira 1 únic contracte (fora funcionalitat d'una gran factura per molts contractes). Això afecta a generate_invoice_budget_view.py, billing/tasks.py -> process_billing_batch() i al agafar la plantilla a invoice_pdf(_view).py.
    - contract/GeneralInvoice: Ara tracta 2 adreces al igual que factura.
    - billing_filters.py: Actualització de la lògica de generació de blocs per multiplicar els límits de consum pel nombre d'habitatges quan l'agrupament avançat està actiu, mantenint la descripció base per a millor llegibilitat.
    - billing_filters.py: Ajust automàtic de les unitats i el preu unitari de la "QUOTA DE SERVEI" per reflectir el nombre d'habitatges mantenint l'import total correcte.
    - invoice_pdf_view.py: Injecció de la variable num_habitatges al context de renderització dels PDFs per a l'ús en plantilles.
    - Adaptació de les plantilles de factura: Per mostrar "Núm. Habitatges" en lloc de "Núm. Persones" de forma dinàmica quan s'utilitza la variable "General".
    - Refinament de la lògica de generació de PDF: De factures per gestionar correctament les sol·licituds d'escomesa (connection_request) i les seves adreces.
GEO
***
    - import_geo_data_pgeocode.py: S'ha afegit --default-province per marcar la província predeterminada.
SUPPLY POINT
***
    - supply_point_view.py: S'ha modificat el canvi de comptador per gestionar tant el canvi com les lectures de tall en una mateixa funció. Necessari last_reading tot just afegit a MeterSerializer per la gestió i nova funció per això: save_meter_change().
STATISTICS
***
    - generate_management_volume_report: Actualització de l'informe de volum de gestió per prioritzar el token del contracte en el detall de registres, facilitant la identificació de les accions.

### FIX
BILLING
***
    - reading_view.py: contract_created_at now grabs registration_date before created_at if it exists.
    - invoice_service.py: funció de factura de baixa es passa el linked_contract_request filtrat només per bill_cut_reading True, ara sempre facturava la baixa el nou titular.
    - recalculate_invoice_service.py: Correcció de NameError per models Reading i Billing i assegurada l'actualització explícita de warnings en el recàlcul smart d'invoices.
    - warning_date_range: Resolta la discrepància en els comptadors d'alertes de rang de dates en ignorar les factures excloses.
IMPORT
***
    - Prometeo: importava els Country's buits i arreglat country Escòcia.

### REMOVED
BILLING
***
    - GeneralInvoice: S'ha esborrat gran part de la funcionalitat relacionada a factures amb el 'GeneralInvoice' degut a refactor.

## [05-05-2026]

### FEAT
BILLING
***
    - reading_view.py: Poder estimar sense crear una lectura a estimate_reading() -> get_estimated_reading_minimal_object(), només es fa servir de moment per estimar una lectura al modificar lectures.
    - reading_service.py: Al modificar lectures (modify_existing_readings()), poder afegir una nova lectura estimada i repartir aquests consums en EstimatedBagMovements per tenir-ho a vista de cada lectura.

### CHORE
STATISTICS
***
    - report_advanced_billing_service.py: Helper de parseig de dates per normalitzar entrades i evitar fallades silencioses.

CORE
***
    - CHANGELOG.md: Afegir el fitxer de CHANGELOG.md pel control de canvis.

### MODIFIED
STATISTICS
***
    - Optimització d'informes avançats: Amb traçabilitat de logs i format numèric Excel (#,##0.00).
BILLING
***
    - Filtre global de factures excloses: (is_excluded=False) en tots els informes estadístics per coherència amb el frontend.
    - Refinament de la lògica d'adreces: En PDF per mantenir sincronització amb sol·licituds d'escomesa.

### FIX
BILLING
***
    - file_template i connection_address: NameError en la generació de PDF de factures.
    - reading_view.py: Al estimar una lectura, mirar període de facturació.
    - SEPA: gestiona correctament retorn de pagaments (payment_view.py -> manage_rejection_payments) de compromisos de pagament. Fins ara només mirava de factures.
STATISTICS
***
    - openpyxl: FieldError i TypeError (timezones) en la generació d'informes Excel amb openpyxl.
    - Informes d'evolució i tarifa social: Discrepàncies en comptadors de contractes actius.
CONTRACT
***
    - contract_request_service.py: imports faltants.
