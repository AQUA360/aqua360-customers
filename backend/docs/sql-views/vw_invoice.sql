-- Vista d’anàlisi sobre billing_invoice (factures actives, no suprimides, type_final = 'F', status_id != 1).
-- Inclou tots els camps escalars i foreign keys del model Invoice (billing.models.Invoice), excepte:
--   - ManyToMany: general_contracts, readings (calen taules intermèdies / agregacions).
--   - Fitxers: invoice_file_template és la ruta emmagatzemada pel FileField.
-- contract_token: LEFT JOIN contract_contract (contract opcional a la factura).

CREATE OR REPLACE VIEW vw_invoice AS
SELECT
  -- Identificadors
  i.id                              AS invoice_id,
  i.token                           AS invoice_token,
  i.created_at                      AS created_at,
  i.updated_at                      AS updated_at,
  -- Contracte (opcional)
  i.contract_id                     AS contract_id,
  c.token                           AS contract_token,
  -- Foreign keys (relacions simples)
  i.connection_id                   AS connection_id,
  i.connection_request_id           AS connection_request_id,
  i.exploitation_id                 AS exploitation_id,
  i.company_id                      AS company_id,
  i.batch_id                        AS batch_id,
  i.billing_id                      AS billing_id,
  i.template_id                     AS template_id,
  i.invoice_file_id                 AS invoice_file_id,
  i.contract_request_id             AS contract_request_id,
  i.contract_termination_id         AS contract_termination_id,
  i.piggy_bank_id                   AS piggy_bank_id,
  i.payment_type_id                 AS payment_type_id,
  i.payment_bank_id                 AS payment_bank_id,
  i.payment_company_bank_id         AS payment_company_bank_id,
  i.serie_id                        AS serie_id,
  i.invoice_class_id                AS invoice_class_id,
  i.type_id                         AS invoice_type_id,
  i.reject_id                       AS reject_id,
  i.status_id                       AS status_id,
  i.suppression_reason_id           AS suppression_reason_id,
  i.suppressed_by_id                AS suppressed_by_id,
  i.parent_invoice_id               AS parent_invoice_id,
  i.origin_id                       AS origin_id,
  i.warning_id                      AS warning_id,
  i.verifactu_notification_id       AS verifactu_notification_id,
  -- Administració / numeració
  i.number                          AS number,
  i.dir3_final                      AS dir3_final,
  i.accounting_office_final         AS accounting_office_final,
  i.managing_body_final             AS managing_body_final,
  i.processing_unit_final           AS processing_unit_final,
  i.command_final                   AS command_final,
  i.record_final                    AS record_final,
  i.type_final                      AS type_final,
  i.serie_final                     AS serie_final,
  i.serie_token_final               AS serie_token_final,
  i.invoice_class_token_final       AS invoice_class_token_final,
  i.title_final                     AS title_final,
  i.issue_date                      AS issue_date,
  i.due_date                        AS due_date,
  COALESCE(i.title_final, i.number, i.token) AS invoice_code,
  -- Client / domicili (snapshot a la factura)
  i.is_confirmed                    AS is_confirmed,
  i.customer_final                  AS customer_final,
  i.customer_token_final            AS customer_token_final,
  i.payer_final                     AS payer_final,
  i.payer_token_final               AS payer_token_final,
  i.customer_is_juridic             AS customer_is_juridic,
  i.customer_tlf_final              AS customer_tlf_final,
  i.customer_email_final            AS customer_email_final,
  i.address_final                   AS address_final,
  i.postal_code_final               AS postal_code_final,
  i.city_final                      AS city_final,
  i.province_final                  AS province_final,
  i.location_final                  AS location_final,
  i.country_final                   AS country_final,
  -- Imports
  i.subtotal_final                  AS subtotal_final,
  i.total_final                     AS total_final,
  i.left_to_pay                     AS left_to_pay,
  -- Pagament (text snapshot)
  i.payment_type_final              AS payment_type_final,
  i.payment_type_token_final        AS payment_type_token_final,
  i.payment_bank_final              AS payment_bank_final,
  i.payment_swift_final             AS payment_swift_final,
  i.payment_iban_final              AS payment_iban_final,
  i.persons_final                   AS persons_final,
  i.responsible_consumption         AS responsible_consumption,
  -- Estat factura (join)
  st.token                          AS status_token,
  st.name                           AS status_name,
  i.reason                          AS reason,
  i.return_token                    AS return_token,
  -- Supressió / enviament
  i.is_suppressed                   AS is_suppressed,
  i.suppressed_at                   AS suppressed_at,
  i.is_general                      AS is_general,
  i.simplified                      AS simplified,
  i.is_sent                         AS is_sent,
  i.send_at                         AS send_at,
  -- Consum / període
  i.real_consumption                 AS real_consumption,
  i.consumption                     AS consumption,
  i.consumption_days                AS consumption_days,
  i.is_registration                 AS is_registration,
  i.billing_period_year             AS billing_period_year,
  i.billing_period_month            AS billing_period_month,
  i.billing_period_days             AS billing_period_days,
  i.budget_token                    AS budget_token,
  i.refactored_token                AS refactored_token,
  i.manually_modified               AS manually_modified,
  i.is_active                       AS is_active,
  -- Plantilla PDF emmagatzemada (path)
  i.invoice_file_template           AS invoice_file_template
FROM billing_invoice i
LEFT JOIN contract_contract c
  ON c.id = i.contract_id
LEFT JOIN billing_invoicestatus st
  ON st.id = i.status_id
WHERE i.is_active = true
  AND i.is_suppressed = false
  AND i.type_final = 'F'
  AND i.status_id != 1 -- NO és prefactura
;
