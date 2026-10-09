# Resum dels scripts Django (management commands)

Aquest document llista tots els mòduls del projecte que tenen l’estructura `management/commands/` i una breu explicació (dues línies) del que fa cada script.

**Ús:** `python manage.py <nom_command> [opcions]`

---

## billing

| Command | Descripció |
|--------|-------------|
| **backfill_estimated_bags** | Crea `EstimatedBag` per a totes les parelles (contracte, punt de subministrament) que en manquen. Permet dry-run, límit i incloure contractes inactius. |
| **batch_invoice_anomaly_total_report** | Analitza les factures d’un lot (per `title_final`) i detecta les que superen un percentatge configurable respecte a la mitjana de facturació del contracte. Exportable a CSV. |
| **delete_and_recalculate_invoice** | Esborra una prefactura i en genera una de nova (id diferent). Només accepta prefactures: `python manage.py delete_and_recalculate_invoice <invoice_id>`. |
| **reading_add_estimated_days** | Afegeix (crea o actualitza) una lectura estimada a +N dies per a un seguit de contractes. |
| **recalculate_invoice** | Recalcula una factura conservant el mateix id, `serie_final` i data d'emissió (línies, consums, dies i imports, i les dades estàtiques de client, pagador i adreça; actualitza el pagament si canvia el total). `python manage.py recalculate_invoice --invoice-id 123 [--regenerate-pdf] [--dry-run]`. |
| **recalculate_billing_invoices** | Recalcula les factures d'un Billing conservant id, `serie_final` i data d'emissió, incloses les dades estàtiques de client, pagador i adreça (mateixa lògica que `recalculate_invoice`). `python manage.py recalculate_billing_invoices --billing-id 42 [--invoice-ids 10,11,12] [--regenerate-pdf] [--dry-run] [--list-invoices]`. |
| **test_average_consumption** | Prova la funció `get_average_consumption` per un contracte i opcionalment un mes. Útil per depuració. |
| **test_estimated_reading** | Prova la funció `get_estimated_reading_minimal_object` per un contracte i supply point (i opcionalment data i batch). |

---

## claimrequest

| Command | Descripció |
|--------|-------------|
| **create_vulnerability_requests** | Crea `VulnerabilityRequest` per als contractes que tenen la variable ACA-CANON i afegeix la variable vulnerability. Admet dry-run i filtre per contract-token. |

---

## communication

| Command | Descripció |
|--------|-------------|
| **send_test_email** | Envia un correu de prova amb la configuració actual (SMTP o Microsoft Graph). Requereix `--to`; opcionalment subject, body, from. |

---

## contract

| Command | Descripció |
|--------|-------------|
| **backfill_piggy_banks** | Crea `PiggyBank` per a tots els contractes que no en tenen i enllaça la relació. Admet dry-run, límit i batch size. |
| **fill_contract_use_aca** | Omple el camp use_aca dels contractes segons les tarifes del producte CANON (id=6). |

---

## coredata

| Command | Descripció |
|--------|-------------|
| **create_superuser_and_token** | Crea un superusuari i genera un token d’API. |

---

## importexport

### Anàlisi i comprovacions (check / analyze)

| Command | Descripció |
|--------|-------------|
| **analyze_supply_points_multiple_contracts** | Analitza quants punts de subministrament tenen més d’un contracte actiu (status_id=2). |
| **check_contract_addresses_person** | Assigna el PersonAddress del holder (mateixa adreça que supply_point_default) quan sigui possible. Admet dry-run. |
| **check_contract_addressess** | Arregla contractes sense adreça de facturació utilitzant l'adreça del titular o punt de subministrament, i mostra comptadors de consistència. |
| **check_contract_billing_person** | Comprova la persona de facturació dels contractes; mostra què es faria sense desar (dry-run). |
| **check_contract_digital_comm** | Analitza punts de subministrament amb més d’un contracte actiu en context de comunicació digital. |
| **check_person_address_duplicate_tokens** | Llegeix un CSV (person_address) i imprimeix les files on un mateix Address[Token] apareix més d’una vegada amb diferent Person[Token]. |
| **find_supply_points_without_active_contracts** | Troba punts de subministrament sense cap contracte actiu i els pot marcar com a inactius. |

### Neteja i correccions (clean / fix)

| Command | Descripció |
|--------|-------------|
| **clean_duplicate_cities** | Neteja les ciutats duplicades a la base de dades. |
| **clusters_error** | Troba els Clusters i elimina els nozzles amb SupplyPoint inactiu (status id=3); si queda un sol nozzle, elimina el cluster. Admet `--dry-run`. |
| **clusters_reset_positions** | Reordena els nozzles de cada Cluster amb posicions 1, 2, 3… (segons l’ordre actual de `position`). Admet `--dry-run`. |
| **create_clusters_from_properties** | Crea un Cluster (token = Property) i un nozzle per SP quan la finca té ≥2 punts de subministrament; copia adreça i `ClusterStatus` per defecte de la Property. Admet `--dry-run`, `--property-token`, `--min-supply-points`, `--fix-existing`. |
| **commitment_fix_service** | Arregla el camp `remaining_to_share` dels commitment deposits amb status token "1". |
| **contract_add_reading_cut** | Afegeix una lectura de tall quan un contracte nou comença a mig període (vegeu [Lectures de tall (comparativa)](#lectures-de-tall-comparativa)). |
| **reading_cut_long_period** | Insereix lectura de tall a +90 dies (període llarg entre 2 darreres lectures no control); `--contract` o `--csv` (vegeu la mateixa secció). |
| **contract_fix_service** | Arregla lectures (relacions, consum, etc.) dels contractes. |
| **fix_address_duplicates** | Identifica i fusiona adreces duplicades a la base de dades. |
| **fix_billed_readings** | Importa o corregeix lectures facturades des d’un CSV. |
| **fix_clusters** | Corregeix la configuració de clusters i nozzles. |
| **fix_contract_pricerate_supply_point** | Corregeix el supply point dels `ContractPriceRate` quan no coincideix amb el defecte del contracte. |
| **fix_contract_reading_previous_readings** | Arregla les relacions previous_reading de les lectures dels contractes. Admet dry-run. |
| **fix_duplicate_payments** | Corregir pagaments duplicats. |
| **fix_estimated_bags** | Corregir/actualitzar estimated bags; admet mode només informe (no escriu a BD). |
| **fix_meters** | Actualitza els codis dels comptadors amb lletres d’inici/fi mal entrades. |
| **fix_meters_wrong_share** | Actualitza codis de comptadors segons un CSV amb els codis correctes. |
| **fix_OV_readings** | Analitza les lectures amb origin 'OV', recompta per contracte i detecta inconsistències (el help diu "logs de pagament"; el codi treballa amb lectures OV). |
| **fix_payment_status_missing_log** | Arregla logs de pagament que falten. |
| **fix_sync_contract_reading_date** | Arregla contractes actius amb Readings amb reading_date més antiga que Contract.created_at; actualitza created_at. |
| **fix_readings_consumption** | Recalcula el consum de les lectures basant-se en els valors anterior i actual. |
| **fix_readings_wrong_prev_relation** | Arregla relacions de previous_reading incorrectes entre lectures. |
| **fix_routepositions** | Corregeix problemes en les posicions de ruta dels supply points. |
| **fix_sync_contract_reading_date** | Arregla contractes actius amb Readings amb reading_date més antiga que Contract.created_at; actualitza created_at. |
| **invoice_fix_service** | Arregla el consum (o dades relacionades) de les factures des d’un fitxer. |
| **invoice_lines_fix_service** | Corregir línies de factura transferint-les des d’altres factures segons un CSV. |
| **invoice_payment_fix_service** | Arregla dades de pagament/consum de factures. |
| **invoice_status_fix_service** | Verifica i corregeix l’estat de les factures. |
| **invoice_suppression_fix** | Valida les supressions de factures des d’un fitxer CSV. |
| **payment_fix_service** | Valida o corregeix pagaments des d’un fitxer. |
| **quick_fix_service** | Conjunt d’arreglos ràpids (múltiples correccions). |
| **reading_fix_service** | Arregla lectures: lots, relacions amb punts de subministrament, relacions entre lectures, consum. |
| **restore_person_data** | Recupera dades de persones (adreces, bancs) després d'una pèrdua de dades. |
| **rollback_aca_ranges** | Reverteix els canvis fets per `duplicate_aca_ranges`. |
| **update_reading_relationships** | Actualitza les relacions entre lectures i els valors calculats. |

### Creació i generació

| Command | Descripció |
|--------|-------------|
| **create_contract_estimated_readings** | Crea lectures estimades per a contractes que no en tenen en un període determinat. |
| **contract_create_empty_payment** | Crea un GeneralPayment buit (sense IBAN) per als contractes amb `payment_id` NULL i l'assigna al contracte. Tipus configurable amb `--payment-type` (per defecte id=2). Admet dry-run. |
| **create_meter_reading_cut** | Permet crear lectures de tall per canvis de comptador o contracte. |
| **create_multiple_einvoice** | Genera XMLs de factura electrònica per múltiples factures (per serie_final). |
| **create_payments_from_invoices** | Crea pagaments per a factures sense cap pagament actiu (excepte pre-factura), via `confirm_invoice`. Filtres: `--billing-id`. Admet `--dry-run` i `--batch-size`. |
| **duplicate_aca_ranges** | Genera nous intervals de facturació per a productes ACA amb un increment de preu del 6%. |
| **fix_invoice_generate_csv** | Genera un fitxer CSV amb factures que presenten errors per a la seva revisió. |
| **generate_payment_movements** | Genera o arregla moviments/logs de pagament. |

### Eliminació (delete)

| Command | Descripció |
|--------|-------------|
| **delete_billingrange** | Elimina un o més BillingRange (per token) i els registres relacionats en cascada. Admet dry-run. |
| **delete_billingrange_with_end** | Elimina tots els BillingRange que tenen data de fi (end). |
| **delete_communication_process** | Elimina un procés de comunicació (per token) i tots els registres relacionats en cascada. Admet dry-run. |
| **delete_contract_pricerates** | Elimina les assignacions de tarifes (`ContractPriceRate`) d'una llista de contractes (per token o CSV). Esborra `ContractPriceRate` orfes per defecte. Admet dry-run. Útil abans de `import_contract_pricerates`. |
| **delete_contractrequesttype** | Elimina un o més `ContractRequestType` per ID (`--id 1,2,3`), neteja relacions M2M i elimina `ContractRequestDocumentationType` associats. Admet `--dry-run`. |
| **delete_invoice** | Elimina una factura i els seus registres relacionats en cascada. |
| **delete_order** | Elimina una ordre de treball i els registres relacionats en cascada. |
| **delete_pricerate** | Elimina un PriceRate i els registres relacionats en cascada. |
| **delete_pricerate_inactive** | Elimina tots els PriceRate amb is_active=False i els relacionats. Admet dry-run i límit. |
| **delete_product** | Elimina un producte i els registres relacionats en cascada. |
| **delete_product_inactive** | Elimina tots els productes amb is_active=False i els relacionats. |

### Duplicat i export

| Command | Descripció |
|--------|-------------|
| **duplicate_supply_point** | Duplica el punt de subministrament per defecte d’un contracte; opcionalment assigna un nou comptador (per token). |
| **meter_export** | Exporta comptadors en CSV amb la seva última lectura. Es pot redirigir a fitxer. |

### Omplir / completar (fill)

| Command | Descripció |
|--------|-------------|
| **backfill_billing_consumption** | Omple els registres buits de `BillingConsumption` aplicant el format de `fill_address`. |
| **calculate_daily_consumption** | Adapta els registres de `ContractConsumption` per utilitzar any i consum diari. |
| **fill_address_search** | Omple el camp address_search utilitzant el format de __str__() de l’adreça. |
| **fill_connection_address_from_property** | Omple l’adreça de Connection des de la Property vinculada (Cluster o SupplyPoint). Admet `--dry-run`, `--connection-token`, `--force`. |
| **fill_contract_pricerate_from_invoices** | Omple el pricerate del contracte a partir de les factures. Admet dry-run. |
| **fill_invoice_readings** | Enllaça **`Reading` → `Invoice.readings`** omplint la M2M **`billing_invoice_readings`**. |
| **init_billing_configs** | Inicialitza les configuracions de facturació al `ConfigProject`. |

### Import (CSV/Excel, genèrics i Aquacis)

| Command | Descripció |
|--------|-------------|
| **import_accounting_values** | Importa valors comptables des d’un fitxer CSV. |
| **import_addresses** | Importa adreces des d’un fitxer CSV. |
| **import_adjustments** | Importa correctors des d’un fitxer CSV. |
| **import_adjustments_conditions** | Importa les condicions dels correctors des d’un CSV. |
| **import_adjustments_intervals** | Importa intervals dels correctors des d’un CSV. |
| **import_bails** | Importa fianços (bails) des d’un CSV. |
| **import_bails_aquacis** | Importa Bail des d’un fitxer CSV (Aquacis). |
| **import_banks** | Importa bancs des d’un CSV. |
| **import_billers** | Importa facturadors (billers) des d’un CSV. |
| **import_billing_batches_aquacis** | Importa BillingBatch des d’un CSV (Aquacis). |
| **import_billing_ranges** | Importa intervals d’aplicació des d’un CSV. |
| **import_billing_ranges_aquacis** | Importa BillingRange des d’un CSV (Aquacis). |
| **import_billings_aquacis** | Importa Billing des d’un CSV (Aquacis). |
| **import_bonifications** | Importa bonificacions des d’un CSV. |
| **import_cities** | Importa ciutats des d’un CSV. |
| **import_client_types** | Importa tipus de client des d’un CSV. |
| **import_cluster_nozzles_aquacis** | Importa ClusterNozzles des d’un CSV (Aquacis). |
| **import_clusters** | Importa clusters des d’un CSV. |
| **import_clusters_aquacis** | Importa Clusters des d’un CSV (Aquacis). |
| **import_cnae** | Importa CNAE des d’un CSV. |
| **import_commitments** | Importa compromisos de pagament des d’un CSV. |
| **import_commitments_invoices** | Relaciona factures de compromisos des d’un CSV. |
| **import_commitments_payments** | Importa pagaments de compromisos des d’un CSV. |
| **import_communication_templates** | Importa plantilles de comunicació des d’un CSV. |
| **import_companies** | Importa empreses des d’un CSV. |
| **import_companies_aquacis** | Importa dades d’empreses/SupplyPoint des d’un CSV (Aquacis). |
| **import_connection_diamater_aquacis** | Importa ConnectionDiameter des d’un CSV (Aquacis). |
| **import_connection_dmas** | Importa DMA de connexió des d’un CSV. |
| **import_connection_geos** | Importa dades geogràfiques de connexions des d’un CSV. |
| **import_connection_installation_types_aquacis** | Importa ConnectionInstallationType des d’un CSV (Aquacis). |
| **import_connection_materials** | Importa ConnectionMaterial des d’un CSV. |
| **import_connection_request_statuses_aquacis** | Importa ConnectionRequestStatus des d’un CSV (Aquacis). |
| **import_connection_requests_aquacis** | Importa ConnectionRequest des d’un CSV (Aquacis). |
| **import_connection_statuses_aquacis** | Importa ConnectionStatus des d’un CSV (Aquacis). |
| **import_connection_types_aquacis** | Importa ConnectionType des d’un CSV (Aquacis). |
| **import_connection_use_types** | Importa ConnectionUseType des d’un CSV. |
| **import_connection_valve_types** | Importa ConnectionValveType des d’un CSV. |
| **import_connections** | Importa connexions des d’un CSV. |
| **import_connections_aquacis** | Importa Connection des d’un CSV (Aquacis). |
| **import_contract_categories** | Importa ContractCategory des d’un CSV. |
| **import_contract_cnaes** | Importa CNAE de contractes des d’un CSV. |
| **import_contract_invoice_pricerates** | Importa tarifes de contractes des d’un CSV i esquema JSON. Admet dry-run. |
| **import_contract_observations** | Importa observacions de contractes des d’un CSV. |
| **import_contract_payments** | Importa pagaments de contractes des d’un CSV. |
| **import_contract_persons** | Importa persones vinculades als contractes des d’un CSV. |
| **import_contract_pricerates** | Importa tarifes de contractes des d’un CSV (una fila per contracte; columnes `PriceRate[Token][0]`, `[1]`, …). |
| **import_contract_request_statuses_aquacis** | Importa estat de peticions de contracte des d’un CSV (Aquacis). |
| **import_contract_requests** | Importa peticions de contracte des d’un CSV. |
| **import_contract_requests_aquacis** | Importa ContractRequest des d’un CSV (Aquacis). |
| **import_contract_status_aquacis** | Importa ContractStatus des d’un CSV (Aquacis). |
| **import_contract_surrogation_types_aquacis** | Importa tipus de subrogació des d’un CSV (Aquacis). |
| **import_contract_surrogations_aquacis** | Importa subrogacions de contractes des d’un CSV (Aquacis). |
| **import_contract_termination_request_last_readings** | Importa últimes lectures de peticions de baixa des d’un CSV. |
| **import_contract_termination_request_statuses_aquacis** | Importa estats de petició de baixa des d’un CSV (Aquacis). |
| **import_contract_termination_requests_aquacis** | Importa peticions de baixa de contracte des d’un CSV (Aquacis). |
| **import_contract_termination_types_aquacis** | Importa tipus de baixa de contracte des d’un CSV (Aquacis). |
| **import_contract_use_types** | Importa tipus d’ús de contracte des d’un CSV. |
| **import_contract_variable_types** | Importa tipus de variables de contracte des d’un CSV. |
| **import_contract_variables** | Importa variables de contracte des d’un CSV. |
| **import_contracts** | Importa contractes des d’un CSV. |
| **import_contracts_aquacis** | Importa contractes des d’un CSV (Aquacis). |
| **import_contracts_from_supplypoints** | Crea contractes a partir dels punts de subministrament des d’un CSV. |
| **import_contracts_tokens** | Importa o actualitza tokens de contractes des d’un CSV. |
| **import_dma_gis** | Importa DMA (GIS) des d’un fitxer. |
| **import_exploitations** | Importa explotacions des d’un CSV. |
| **import_gen_companies** | Importa empreses (genèric) des d’un CSV. |
| **import_gen_exploitations** | Importa explotacions (genèric) des d’un CSV. |
| **import_gen_exploitations_sp** | Importa explotacions i/o supply points (genèric) des d’un CSV. |
| **import_gen_supply_points** | Importa punts de subministrament (genèric) des d’un CSV. |
| **import_geo_data_pgeocode** | Importa coordenades (lat/long) utilitzant `pgeocode` segons el codi postal. |
| **export_invoice_lines** | Exporta línies de factures de la BD a un CSV compatible amb `import_invoice_lines`. Filtres: `--billing-id`, `--contract-token`, `--contract-id`. |
| **export_invoices** | Exporta factures de la BD a un CSV compatible amb `import_invoices`. Filtres: `--billing-id`, `--contract-token`, `--contract-id`. |
| **export_payments** | Exporta pagaments de la BD a un CSV compatible amb `import_payments`. Filtres: `--billing-id`, `--contract-token`, `--contract-id`. Per defecte només pagaments actius i sense compromís de pagament. |
| **import_invoice_claims** | Importa reclamacions de factures des d’un CSV. |
| **import_invoice_lines** | Importa línies de factures des d’un CSV. |
| **import_invoice_series_aquacis** | Importa InvoiceSerie des d’un CSV (Aquacis). |
| **import_invoices** | Importa factures des d’un CSV. |
| **import_line_item_types** | Importa tipus de línia de factura des d’un CSV. |
| **import_line_item_types_aquacis** | Importa LineItemType des d’un CSV (Aquacis). |
| **import_meter_calibers_aquacis** | Importa MeterCaliber des d’un CSV (Aquacis). |
| **import_meter_statuses_aquacis** | Importa MeterStatus des d’un CSV (Aquacis). |
| **import_meters** | Importa comptadors des d’un CSV. |
| **import_meters_aquacis** | Importa comptadors des d’un CSV (Aquacis). |
| **import_observations** | Importa observacions de contractes des d’un CSV. |
| **import_operators_aquacis** | Importa operadors des d’un CSV (Aquacis). |
| **import_order_operator** | Importa operadors d’ordres des d’un CSV. |
| **import_order_status** | Importa estats d’ordres des d’un CSV. |
| **import_order_types** | Importa tipus d’ordres des d’un CSV. |
| **import_payments** | Importa pagaments des d’un CSV. |
| **import_person_address** | Importa adreces de persones des d’un CSV. |
| **import_person_address_aquacis** | Importa PersonAddress des d’un CSV (Aquacis). |
| **import_person_banks** | Importa dades bancàries de persones des d’un CSV. |
| **import_person_banks_aquacis** | Importa PersonBank des d’un CSV (Aquacis). |
| **import_person_contact** | Importa dades de contacte de persones des d’un CSV. |
| **import_person_emails_aquacis** | Importa emails de persones des d’un CSV (Aquacis). |
| **import_person_phones_aquacis** | Importa telèfons de persones des d’un CSV (Aquacis). |
| **import_persons** | Importa persones des d’un CSV. |
| **import_persons_aquacis** | Importa Person des d’un CSV (Aquacis). |
| **import_postal_codes_aquacis** | Importa codis postals des d’un CSV (Aquacis). |
| **import_price_interval_items** | Importa intervals de preu des d’un CSV. |
| **import_price_rates** | Importa PriceRate des d’un CSV. |
| **import_price_rates_aquacis** | Importa PriceRate des d’un CSV (Aquacis). |
| **import_pricing_csv** | Importa preus des de fitxers CSV per a cada explotació (versió CSV). |
| **import_products** | Importa productes des d’un CSV. |
| **import_products_aquacis** | Importa productes des d’un CSV (Aquacis). |
| **import_properties_aquacis** | Importa Property des d’un CSV (Aquacis). |
| **import_provinces_aquacis** | Importa províncies des d’un CSV (Aquacis). |
| **import_publications** | Importa publicacions/productes des d’un CSV. |
| **import_publications_aquacis** | Importa Publication des d’un CSV (Aquacis). |
| **import_reading** | Importa una lectura des d’un fitxer. |
| **import_reading_batch** | Importa lots de lectures des d’un CSV. |
| **import_reading_batches_aquacis** | Importa ReadingBatch des d’un CSV (Aquacis). Opció --delete per esborrar abans. |
| **import_readings** | Importa lectures des d’un CSV. |
| **import_readings_aquacis** | Importa Reading des d’un CSV (Aquacis). |
| **import_readings_no_invoice** | Importa lectures sense factura des d’un CSV. |
| **import_route_positions_aquacis** | Importa RoutePosition des d’un CSV (Aquacis). |
| **import_route_zones_aquacis** | Importa RouteZone des d’un CSV (Aquacis). |
| **import_routes_aquacis** | Importa rutes des d’un CSV (Aquacis). |
| **import_street_numbers** | Importa números de carrer (StreetNumber) des d’un CSV. |
| **import_street_types** | Importa tipus de carrer des d’un CSV. |
| **import_streets** | Importa carrers des d’un CSV. |
| **import_supply_cut_causes** | Importa causes de tall de subministrament des d’un CSV. |
| **import_supply_cut_statuses** | Importa estats de tall de subministrament des d’un CSV. |
| **import_supply_cut_types** | Importa tipus de tall (SupplyCutCause) des d’un CSV. |
| **import_supply_cuts** | Importa talls de subministrament des d’un CSV. |
| **import_supply_point_placement_aquacis** | Importa SupplyPointPlacement des d’un CSV (Aquacis). |
| **import_supply_point_sources** | Importa SupplyPointSource des d’un CSV. |
| **import_supply_point_statuses** | Importa SupplyPointStatus des d’un CSV. |
| **import_supply_point_types** | Importa SupplyPointType des d’un CSV. |
| **import_supply_points** | Importa punts de subministrament des d’un CSV. |
| **import_supply_points_aquacis** | Importa SupplyPoint des d’un CSV (Aquacis). |
| **import_supply_types** | Importa tipus de subministrament des d’un CSV. |
| **import_tank** | Importa dipòsits (tank) des d’un CSV. |
| **import_taxes_aquacis** | Importa impostos des d’un CSV (Aquacis). |
| **prometeo_import_contract_request_type** | Importa relacions ContractRequestType ↔ PriceRate des d'un JSON de Prometeo. |

### Càrrega i actualitzacions

| Command | Descripció |
|--------|-------------|
| **process_ov_users_with_contracts** | Processa el fitxer ov_users.csv i genera un CSV amb informació de contractes. |
| **regenerate_invoices** | Regenera els PDFs de les factures, sense recalcular imports. Amb `--billing-id` processa totes les factures d'aquell Billing; sense, les de status confirmat/expirat. Opcions: `--exclude-direct-debit-and-transfer` per excloure domiciliació i transferència, `--dry-run` per només mostrar què es faria, `--list-invoices` (amb dry-run) per llistar cada factura. Mostra resums per tipus de pagament i status. |
| **rerun_invoices** | Torna a executar la generació de factures (arreglos/recàlcul). |
| **truncate_config_contract_types** | Fa TRUNCATE de les taules contract_contractcategory, contract_contractusetype i contract_contractclienttype. |
| **truncate_order** | Elimina TOTS els registres d’Order i els relacionats (TRUNCATE). |
| **set_comm_process_statuses** | Estableix l’estat correcte per als processos de comunicació ja processats. |
| **sync_street_types** | Posa `coredata_streettype` als **71 tipus de via oficials de l'ACA** (llista a `coredata/aca_street_types.py`) i reassigna els carrers que apuntaven a un tipus que ja no existeix. El catàleg no està bloquejat a la base de dades: el que el manté net és que cap camí del codi hi crea files (tot passa per `coredata/street_types.py`). Amb `--dry-run` no desa res. |
| **update_aca_contracts** | Actualitza contractes ACA des d’un fitxer Excel (.xlsx). |
| **update_invoices_payoff** | Actualitza les factures a estat PayOff (Abonat). |
| **update_meter_telecontrol** | Actualitza dades de telecontrol dels comptadors. |
| **validate_einvoices** | Valida fitxers XML de factura electrònica (per exemple amb xmllint i esquema). |

### Watchdog (comprovacions d’integritat)

| Command | Descripció |
|--------|-------------|
| **watchdog_address_data** | Identifica dades d’adreça duplicades (carrers, números i adreces). |
| **watchdog_adjustment_variables** | Analitza AdjustmentCondition i comprova que les referències a variables existeixin. |
| **watchdog_billingrange** | Comprova la coherència dels BillingRange (intervals, referències). |
| **watchdog_meter** | Analitza els comptadors i comprova que tinguin un Calibre vàlid. |
| **watchdog_person** | Analitza persones i comprova que tinguin PersonBank i CompanyBank amb IBANs vàlids. |
| **watchdog_readings** | Identifica lectures amb dies de consum o valors calculats incorrectes respecte a la lectura anterior. |
| **watchdog_supplypoint_norouteposition** | Comprova punts de subministrament sense posició de ruta (route position). |

---

## integrations

Integració outbound amb **Giswater** (connecs, OAuth Keycloak, sincronització amb `Connection`).

**Documentació:** `integrations/outbound/giswater/README.md` i `docs/integrations.md`.

### Usuari inbound Giswater

| Command | Descripció |
|--------|-------------|
| **get_or_create_giswater_user** | Obté o crea l’usuari inbound Giswater i l’assigna al grup `giswater` (només pot accedir a `/giswater/`). Requereix `GISWATER_USER_USERNAME`, `GISWATER_USER_PASSWORD` i `GISWATER_USER_EMAIL` al `.env`. |

### Usuari inbound Smartmetering

| Command | Descripció |
|--------|-------------|
| **get_or_create_smartmetering_user** | Obté o crea l’usuari inbound Smartmetering i l’assigna al grup `smartmetering` (només pot accedir a `/smartmetering/`). Requereix `SMARTMETERING_USER_USERNAME`, `SMARTMETERING_USER_PASSWORD` i `SMARTMETERING_USER_EMAIL` al `.env`. |

### Validació i prova de connexió

| Command | Descripció |
|--------|-------------|
| **validate_giswater_auth** | Valida l'autenticació OAuth via Keycloak (`client_credentials`). Obté un `access_token` i mostra la longitud i una versió enmascarada. Útil abans de qualsevol altra crida. |
| **fetch_giswater_connecs** | Crida l'API Giswater `GET /basic/getlist?schema=ws&tableName=ve_connec`, mostra una previsualització de la resposta i la registra a `IntegrationRequestLog`. Opcions: `--save-json RUTA` (JSON complet), `--preview-chars N` (mida de la previsualització, default 500). |

### Sincronització Giswater → Connection

| Command | Descripció |
|--------|-------------|
| **sync_giswater_connections** | Sincronitza `Connection` amb connecs Giswater (`connec_type=ESCO`): `code_gis` ← `connec_id`, `latitude` ← `lat`, `longitude` ← `long`, cerca per `Connection.token == customer_code`. Mostra estadístiques (`updated`, `not_found`, `unchanged`, etc.) i detall de `not_found`. Opcions: `--only-not-found` (només llista sense resum), `--csv RUTA` (exporta not_found a CSV amb separador `;`; `-` = stdout). |

### Flux recomanat per consola

```bash
python manage.py validate_giswater_auth
python manage.py fetch_giswater_connecs --save-json /tmp/giswater_connecs.json
python manage.py sync_giswater_connections
python manage.py sync_giswater_connections --only-not-found --csv /tmp/giswater_not_found.csv
```

### Celery (background)

Les tasques `fetch_giswater_connecs_task` i `sync_giswater_connections_task` estan a `integrations.tasks`. La sync programada s'activa amb `GISWATER_SYNC_CONNECS_ENABLED=True` al `.env` (Celery Beat, per defecte cada dia a les 3:00).

### Aqua360 Sign

| Command | Descripció |
|--------|-------------|
| **check_signing_connection** | Comprova que Aqua360 Sign respon i accepta `SIGNING_API_KEY`. Fa `GET` d'una sessió inexistent: un `404` JSON és èxit. No crea cap sessió ni envia cap correu. |
| **send_contract_request_for_signing** | Genera el PDF d'una sol·licitud (`ContractRequest`) i l'envia a Aqua360 Sign. Opcions: `--contract-request-id ID` (obligatori), `--recipient-name`, `--recipient-email`, `--recipient-phone`, `--callback-url`, `--force`. |
| **poll_signing_sessions** | Consulta a Sign les sessions encara obertes i, si ja estan firmades, en desa el PDF. Opcions: `--document-sign ID` (repetible), `--session UUID` (repetible), `--skip-contract-requests`, `--limit N`, `--dry-run`. |

```bash
python manage.py check_signing_connection
python manage.py send_contract_request_for_signing --contract-request-id 55
python manage.py send_contract_request_for_signing --contract-request-id 780 --recipient-email signant@example.com
python manage.py poll_signing_sessions --dry-run
```

---

## lecturapp

| Command | Descripció |
|--------|-------------|
| **createsuperoperator** | Crea un super operador per a l’aplicació Lecturapp. |

---

## order

| Command | Descripció |
|--------|-------------|
| **run_gmao_consumer** | Consumeix missatges de la cua RabbitMQ gmao-event (integració GMAO). |

---

## ov

| Command | Descripció |
|--------|-------------|
| **get_or_create_ov_user** | Obté o crea l’usuari OV i l’assigna al grup OV. |

---

## service

| Command | Descripció |
|--------|-------------|
| **update_nb_nozzles** | Actualitza nb_nozzles de tots els clusters amb el recompte de supply_points i assegura que sigui parell. |

---

## verifactu

| Command | Descripció |
|--------|-------------|
| **test_verifactu_soap** | Prova l’enviament d’un missatge SOAP XML d’exemple al servei Verifactu. |

---

## watchdog

| Command | Descripció |
|--------|-------------|
| **fix_exploitation_cities** | Arregla errors d’Exploitation sense city o sense code (per ID, ciutat, codi postal, província, país). |
| **watchdog** | Comprova la integritat de les dades a la base de dades (diverses comprovacions). |
| **watchdog_fix_connection_exploitation** | Per a totes les `Connection` amb `exploitation = NULL`, assigna la primera `Exploitation` del sistema (id ASC). Ús després del watchdog si hi ha connexions sense explotació. |
| **watchdog_fix_empty_bank_ibans** | Elimina `PersonBank` i `CompanyBank` amb IBAN buit o invàlid; les FK referenciades queden NULL (`SET_NULL`). Admet `--dry-run`; `--skip-in-use` per no esborrar referenciats. Recomanat quan el watchdog detecta «PersonBank i CompanyBank IBANs vàlids». |
| **watchdog_fix_nozzle_positions** | Rep tokens o IDs de Clusters i redistribueix SupplyPoints que comparteixen el mateix ClusterNozzle en nozzles nous, reordenant posicions. Recomanat quan el watchdog detecta “Active SupplyPoints sharing ClusterNozzle”. |
| **watchdog_fix_orphaned_addresses** | Elimina `Address` orfes (sense relació amb Person, SupplyPoint, Order ni Company). Admet `--dry-run` i `--id`. |
| **watchdog_fix_readings_without_meter** | Corrigeix lectures actives sense `meter_id`: assigna el comptador del punt de subministrament (`supply_point` o `contract.supply_point_default`) o marca la lectura com a control si el SP no té comptador. Admet `--dry-run` i `--reading-id`. |
| **watchdog_fix_aca_config** | Corrigeix ConfigProject ACA (`token_product_aca`, tokens de tarifes ACA, `VariableType` de declaració directa) i crea `ArticleCode` requerits (`part_fixa`, `part_variable`) quan `uses_aca=True`. Després cal `fill_contract_use_aca` per als contractes. Admet `--dry-run`. |
| **watchdog_fix_config_project** | Crea els `ConfigProject` que falten segons el JSON mestre (`initial_data/ca/config_project/local/ConfigProject.json`). No usa els IDs del JSON. Admet `--dry-run` i `--token`. |
| **watchdog_fix_contract_registration_date_from_readings** | Per contractes actius amb lectures anteriors a `registration_date` (o `created_at` si és buida), assigna `registration_date` i `created_at` a la data de la lectura més antiga en conflicte. Només si la diferència en dies és ≤ `--max`. Admet `--dry-run` i `--contract-id`. |

---

## Lectures de tall (comparativa)

Dos comandaments de l’app **`importexport`** insereixen una **lectura intermèdia** i **reencadenen** la lectura més recent, però corresponen a **situacions de negoci diferents**. No són intercanviables.

### `importexport`: `reading_cut_long_period`

**Problema:** entre les dues últimes lectures **no de control** (mateix contracte, mateix punt i comptador) hi ha un **període molt llarg** (per defecte ≥ 150 dies), cosa que complica facturació o alertes.

**Criteri de lectures:** per cada `supply_point` del contracte es determina el **comptador vigent** com el de la **lectura més recent** (data, id) d’aquelles punt; només per aquest `(sp, meter)` s’agafen les **2 lectures més recents** (exclou `is_control`; per defecte també exclou `is_close`). Això evita usar un comptador antic després d’un **canvi de comptador** (on les «dues últimes» del vell serien del 2025 mentre la UI mostra el nou). Amb **`--all-meters`** es recupera el comportament anterior (totes les parelles `(sp, meter)` distintes).

**Tall:**

- **Data:** data de la lectura **antiga** (la segona en ordre DESC) **+ N dies** (per defecte 90, configurable amb `--days`).
- **Consum del tall:** `ceil(N × consum_total / dies_totals)` (enters); si el consum total entre les dues lectures és **0**, el tall té consum **0** i **mateix `reading_value`** que la lectura antiga (per poder facturar períodes ~trimestrals amb canon/impostos encara sense m³).
- **Valor de lectura del comptador:** `ceil(lectura_antiga + consum_tall)` si hi ha consum positiu; si el consum és zero, es conserva el valor de la lectura antiga.
- **`consumption_days`** del tall: **N** (valor de `--days`).
- **`calculated_value`** i **`real_consumption`** del tall: igual al consum del tall.
- **`origin`:** `LECTURA_TALL_PERIODE`.
- La lectura **més recent** passa a tenir com a `previous_reading` la nova lectura; es recalculen consum i dies fins a la nova anterior.

**Ús:**

```text
python manage.py reading_cut_long_period --contract <id_o_token_o_llista>
python manage.py reading_cut_long_period --contract 123,456,ABC
python manage.py reading_cut_long_period --days 60 --contract 123
python manage.py reading_cut_long_period --csv ruta.csv [--skip-header] [--dry-run]
python manage.py reading_cut_long_period --csv ruta.csv --min-period-days 150
python manage.py reading_cut_long_period --csv ruta.csv --include-close
python manage.py reading_cut_long_period --csv ruta.csv --all-meters
```

Opcions rellevants: `--min-period-days` (per defecte 150), `--dry-run`, `--include-close`, `--hide-short-period-detail`, **`--all-meters`** (processa tots els comptadors per SP, no només el de la darrera lectura).

### `importexport`: `contract_add_reading_cut`

**Problema:** un **contracte nou** comença a **mig període** respecte a la lectura que ve del **contracte anterior** (canvi de titularitat / alta amb lectura pendent del període antic).

**Criteri de lectures:** la **última lectura** del contracte nou ha de tenir `previous_reading` en un **altre contracte**; la data d’alta del contracte nou (`created_at`) ha d’estar **després** de la data d’aquesta lectura anterior.

**Tall:**

- **Data del tall:** **`created_at` del contracte nou** (no +90 dies fixos).
- **`consumption_days`:** dies entre la lectura anterior (contracte vell) i la data d’alta del nou.
- **Consum del tall:** `round(dies × consum_per_dia)` respecte al tram entre previous i última lectura del nou contracte.
- **Contracte de la nova lectura:** el del **`previous_reading`** (contracte antic), no el que es passa com a argument (que és el contracte nou).
- **`origin`:** `Calculat`.
- Actualitza l’**última lectura del contracte nou** (`last_reading`): nou `previous_reading`, consum restant amb `round`, nous `consumption_days`.

**Ús:**

```text
python manage.py contract_add_reading_cut --contracts TOKEN1,TOKEN2,TOKEN3
```

Només **tokens** de contractes **actius**; no admet CSV ni ID numèric ni dry-run al codi actual.

### Resum de diferències

| | `reading_cut_long_period` | `contract_add_reading_cut` |
|--|---------------------------|----------------------------|
| **Cas** | Mateix contracte, forat temporal gran entre 2 lectures reals | Contracte nou enllaçat a lectura d’un contracte anterior |
| **Quines lectures** | 2 darreres no control per (SP + meter) | Última del nou + `previous` d’**altre** contracte |
| **Data del tall** | Antiga + **N dies** (`--days`) | **Data d’alta** del contracte nou |
| **Durada del tall (`consumption_days`)** | **N** (`--days`) | Fins a `created_at` del nou |
| **Arrodoniment consum** | **`ceil`** | **`round`** |
| **`real_consumption` (tall)** | Igual que `calculated_value` | No es defineix explícitament al `create` |
| **Entrada** | `--contract` o `--csv` (id o token), dry-run, llindar de dies | Llista de tokens separats per comes |
| **Comprovacions** | Període mínim, no duplicat mateixa data, etc. | Mateix contracte a previous = error; `created_at` vs dates |

Si el dubte és “**canvi de titular amb lectura del titular vell**”, useu **`contract_add_reading_cut`**. Si és “**dues lectures del mateix contracte massa separades**”, useu **`reading_cut_long_period`**.
