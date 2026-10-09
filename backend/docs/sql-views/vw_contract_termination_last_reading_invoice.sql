-- Vista d'anàlisi de sol·licituds de baixa de contracte amb:
--   - contracte associat
--   - darrera lectura del contracte
--   - darrera factura vàlida del contracte
-- Regles factura: activa, no suprimida, definitiva (type_final='F') i no esborrany (status_id != 1).

CREATE OR REPLACE VIEW vw_contract_termination_last_reading_invoice AS
SELECT
  c.id AS contract_id,
  c.token AS contract_token,
  r.id AS termination_request_id,
  DATE(r.created_at) AS termination_created_at,
  lr.id AS reading_id,
  lr.reading_date,
  lr.origin,
  li.id AS invoice_id,
  li.serie_final AS invoice_token,
  li.issue_date AS last_invoice_date
FROM contract_contractterminationrequest r
LEFT JOIN contract_contract c
  ON c.id = r.contract_id
LEFT JOIN (
  SELECT DISTINCT ON (br.contract_id)
    br.id, br.contract_id, br.reading_date, br.origin
  FROM billing_reading br
  ORDER BY br.contract_id, br.reading_date DESC, br.id DESC
) lr
  ON lr.contract_id = c.id
LEFT JOIN (
  SELECT DISTINCT ON (bi.contract_id)
    bi.id, bi.contract_id, bi.issue_date, bi.serie_final
  FROM billing_invoice bi
  WHERE bi.is_active = true
    AND bi.is_suppressed = false
    AND bi.type_final = 'F'
    AND bi.status_id != 1
  ORDER BY bi.contract_id, bi.issue_date DESC NULLS LAST, bi.id DESC
) li
  ON li.contract_id = c.id
WHERE r.status_id NOT IN (2, 4)
  AND r.is_active = true
ORDER BY r.created_at ASC
;
