-- Equivalent API (no depèn d'aquesta vista): GET /smartmetering/v1/contracts/
-- Documentació: docs/integrations/smartmetering/data-contract.md
CREATE OR REPLACE VIEW "external_views"."vw_abonats_aqua360" AS
SELECT
  c.token::text AS policy,
  m.code::text AS meter,
  pr.name::text AS rate,
  a.address_search::text AS service_point,
  m.installation_at AS inst_date,
  m.comm_module::text AS comm_module,
  m.comm_technology::text AS comm_technology,
  m.manufacturer::text AS manufacturer,
  m.model::text AS model,
  m.network_provider::text AS network_provider,
  cn.exploitation_id::integer AS expl_id,
  cn.dma_id::integer AS dma_id,
  c.status_id = 2 AS contract_active,
  concat_ws(' '::text, p.name, p.surname) AS customer,
  sp.cadastral::text AS cadastral_ref,
  cn.id::text AS connect_id
FROM
  contract_contract c
  LEFT JOIN coredata_person p ON p.id = c.holder_id
  LEFT JOIN service_supplypoint sp ON sp.id = c.supply_point_default_id
  LEFT JOIN service_meter m ON m.id = sp.meter_id
  LEFT JOIN coredata_address a ON a.id = sp.address_id
  LEFT JOIN service_connection cn ON cn.id = sp.connection_id
  LEFT JOIN LATERAL (
    SELECT
      ppr.name
    FROM
      contract_contract_price_rates ccpr
      JOIN contract_contractpricerate cpr ON cpr.id = ccpr.contractpricerate_id
      JOIN pricing_pricerate ppr ON ppr.id = cpr.price_rate_id
    WHERE
      ccpr.contract_id = c.id
      AND cpr.is_active = true
      AND (
        cpr.supply_point_id = sp.id
        OR cpr.supply_point_id IS NULL
      )
    ORDER BY
      cpr.id DESC
    LIMIT
      1
  ) pr ON true
WHERE
  c.is_active = true;
  