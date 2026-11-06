# Changelog Backend

## [05-11-2026]
### MODIFIED
#### BILLING (`billing/filter/invoice_filter.py` — llista de factures més ràpida)
    - Els filtres de la llista de factures ja no demanen `DISTINCT` quan no poden repetir cap factura (camps propis i claus foranes: tipus, estat, sèrie, cerca, etc.). Amb `DISTINCT`, la base comparava totes les factures abans de tornar-ne una pàgina: en una explotació de 34.000 factures, obrir la pantalla passava 2,5 s a la consulta; sense, 0,75 s. El mateix nombre de factures.
    - Els filtres que sí poden repetir-ne (línies de factura i contractes generals) el mantenen. Tests a `billing/tests/test_invoice_list_filter_distinct.py`.
    - Índex nou `invoice_list_order_idx` (data d'emissió i de creació, migració `billing.0336`) per a l'ordre de la llista: la base ja no ordena totes les factures per tornar-ne una pàgina. Mateixa còpia: de 0,5 s a 0,04 s.

## [04-11-2026]
### FIX
#### BILLING (`billing/views/payment_view.py` — segona devolució d'un rebut tornat a presentar el mateix dia de la primera)
    - En carregar un fitxer de devolucions, un retorn ja registrat només impedeix el nou si és POSTERIOR al cobrament per domiciliació que es retorna (per data i, el mateix dia, per ordre de registre). Abans es comparava només la data: si el rebut s'havia tornat a presentar el mateix dia de la primera devolució i tornava amb el mateix motiu, la segona devolució es descartava sense cap avís i el rebut quedava pagat.
    - Tornar a carregar el mateix fitxer continua sense duplicar la devolució. Tests a `billing/tests/test_return_after_payment_method_change.py`.
#### PRICING (`initial_data/ca/optional/pricing.ACA.json` — condició «FACTURA ACA» del cànon domèstic L2-2023)
    - La condició 9003001 del corrector `ACA/D/PV/FACTURA-ACA-DIRECTAMENT/L2-2023` deia «Variable: Factura ACA (char)» però avaluava `variable.ACA-TRAM` (ampliació de trams per família nombrosa): un contracte amb ampliació de trams refacturat en un període 2023–2025 quedava amb el cànon a 0 (i el mínim el pujava a 18 m³). Ara avalua `variable.Factura-ACA` ≥ 1, igual que totes les altres condicions «factura ACA directament» del paquet.
    - Les instal·lacions que ja tenien el paquet carregat s'han corregit a part, a la base de dades (mateixa condició, mateix valor).

