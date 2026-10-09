-- SELECT per taula vista: contracte, NoFacturable (block_billing), tipus d'ús, explotació, zona (RouteZone/Route),
-- comptador (Comptador / ComptadorGeneral / ComptadorPare), última factura, última lectura,
-- lectura previa, previous_previous_reading i previous_previous_previous_reading.
-- Només contractes actius (ContractStatus.token = '1').
-- Factures definitives: billing_invoice.type_final = 'F' i exclou estat esborrany (status_id != 1).
-- Lectures: exclou lectures de control (billing_reading.is_control = false).
-- Relacions: Contract -> SupplyPoint (default) -> Property -> RoutePosition -> Route -> RouteZone
--            Exploitation: SupplyPoint (supply_point_default) -> Connection -> Exploitation
--            Contract -> Invoice (última per issue_date)
--            Contract -> Reading (última per reading_date), Reading.previous_reading_id -> cadena de lectures previes
-- Noms de taules Django: contract_contract, billing_invoice, billing_reading, service_routezone, service_route, etc.

CREATE OR REPLACE VIEW vw_contract_invoice_reading_summary AS
-- (el mateix SELECT del fitxer, sense ORDER BY si no ho permet el motor dins de VIEW)

WITH last_invoice AS (
  SELECT DISTINCT ON (contract_id)
    contract_id,
    id AS invoice_id,
    COALESCE(title_final, number, token) AS invoice_code,
    issue_date AS invoice_issue_date
  FROM billing_invoice
  WHERE contract_id IS NOT NULL
    AND is_active = true
    AND is_suppressed = false
    AND type_final = 'F'
    AND status_id != 1
  ORDER BY contract_id, issue_date DESC NULLS LAST, id DESC
),
last_reading AS (
  SELECT DISTINCT ON (contract_id)
    contract_id,
    id AS reading_id,
    reading_date AS last_reading_date,
    reading_value AS last_reading_value,
    previous_reading_id
  FROM billing_reading
  WHERE contract_id IS NOT NULL
    AND is_active = true
    AND is_control = false
  ORDER BY contract_id, reading_date DESC NULLS LAST, id DESC
)
SELECT
  c.id                    AS contract_id,
  c.token                 AS contract_token,
  DATE(c.created_at)            AS contract_created_at,
  c.block_billing         AS "NoFacturable",
  c.holder_id             AS holder_id,
  p.token                 AS holder_token,
  TRIM(COALESCE(p.name, '') || ' ' || COALESCE(p.surname, '')) AS holder_name,
  c.use_type_id           AS use_type_id,
  ut.token                AS use_type_token,
  ut.name                 AS use_type_name,
  expl.id                 AS exploitation_id,
  expl.token              AS exploitation_token,
  expl.name               AS exploitation_name,
  rz.id                   AS route_zone_id,
  rz.token                AS route_zone_token,
  rz.name                 AS route_zone_name,
  r.id                    AS route_id,
  r.token                 AS route_token,
  r.name                  AS route_name,
  m.id                    AS meter_id,
  m.code                  AS "Comptador",
  m.is_general            AS "ComptadorGeneral",
  mg.code                 AS "ComptadorPare",
  li.invoice_id           AS last_invoice_id,
  li.invoice_code         AS last_invoice_code,
  li.invoice_issue_date   AS last_invoice_date,
  lr.reading_id           AS last_reading_id,
  lr.last_reading_date    AS last_reading_date,
  lr.last_reading_value   AS last_reading_value,
  lr.previous_reading_id  AS previous_reading_id,
  pr.reading_date         AS previous_reading_date,
  pr.reading_value        AS previous_reading_value,
  pr.previous_reading_id  AS previous_previous_reading_id,
  ppr.reading_date        AS previous_previous_reading_date,
  ppr.reading_value       AS previous_previous_reading_value,
  ppr.previous_reading_id AS previous_previous_previous_reading_id,
  pppr.reading_date       AS previous_previous_previous_reading_date,
  pppr.reading_value      AS previous_previous_previous_reading_value
FROM contract_contract c
INNER JOIN contract_contractstatus cs
  ON cs.id = c.status_id AND cs.token = '1'
LEFT JOIN coredata_person p
  ON p.id = c.holder_id
LEFT JOIN contract_contractusetype ut
  ON ut.id = c.use_type_id
-- Exploitation: supply_point_default -> connection -> exploitation
LEFT JOIN service_supplypoint sp
  ON sp.id = c.supply_point_default_id
LEFT JOIN service_connection conn
  ON conn.id = sp.connection_id
LEFT JOIN service_exploitation expl
  ON expl.id = conn.exploitation_id
-- Zona via supply_point_default -> property -> route_position -> route -> route_zone
LEFT JOIN service_property prop
  ON prop.id = sp.property_id
LEFT JOIN service_routeposition rp
  ON rp.id = prop.route_position_id
LEFT JOIN service_route r
  ON r.id = rp.route_id
LEFT JOIN service_routezone rz
  ON rz.id = r.route_zone_id
-- Comptador del punt de subministrament (+ comptador general pare)
LEFT JOIN service_meter m
  ON m.id = sp.meter_id
LEFT JOIN service_meter mg
  ON mg.id = m.meter_general_id
-- Última factura
LEFT JOIN last_invoice li
  ON li.contract_id = c.id
-- Última lectura
LEFT JOIN last_reading lr
  ON lr.contract_id = c.id
-- Lectura previa (relacionada per previous_reading_id)
LEFT JOIN billing_reading pr
  ON pr.id = lr.previous_reading_id
  AND pr.is_control = false
-- Lectura previous_previous (anterior de la lectura previa)
LEFT JOIN billing_reading ppr
  ON ppr.id = pr.previous_reading_id
  AND ppr.is_control = false
-- Lectura previous_previous_previous (anterior de la previous_previous)
LEFT JOIN billing_reading pppr
  ON pppr.id = ppr.previous_reading_id
  AND pppr.is_control = false
WHERE c.is_active = true
;

-- ORDER BY c.id;


