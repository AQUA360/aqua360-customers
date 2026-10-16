# statistics/migrations/0046_vw_contract_debt_exclude_balance.py
from django.db import migrations


DROP_VIEW = """
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_class WHERE relname = 'vw_contract_debt' AND relkind = 'm') THEN
        EXECUTE 'DROP MATERIALIZED VIEW vw_contract_debt CASCADE';
    ELSIF EXISTS (SELECT 1 FROM pg_class WHERE relname = 'vw_contract_debt' AND relkind = 'v') THEN
        EXECUTE 'DROP VIEW vw_contract_debt CASCADE';
    END IF;
END $$;
"""


class Migration(migrations.Migration):

    dependencies = [
        ('statistics', '0045_merge_20260922_0857'),
    ]

    operations = [

        # -----------------------------
        # vw_contract_debt: els pagaments "En saldo" (payment_status_piggy_token,
        # token '5') no són deute. Estan cobrats amb el saldo del contracte i la
        # resta de l'aplicatiu ja els tracta com a pagats (signal update_payment,
        # informe de cartera), però la vista els sumava: en retornar fiances, les
        # factures pagades dels contractes de baixa apareixien amb deute.
        # -----------------------------
        migrations.RunSQL(
            DROP_VIEW + """
            CREATE VIEW vw_contract_debt AS
            SELECT c.token AS contract_token,
                   COALESCE(SUM(GREATEST(p.amount, 0)), 0) AS debt_amount
            FROM contract_contract c
            JOIN billing_invoice i ON i.contract_id = c.id
            JOIN billing_payment p ON p.invoice_id = i.id
            JOIN billing_paymentstatus ps ON ps.id = p.status_id
            WHERE ps.token NOT IN ('0', '5', '-4', '-6', '-7', '-99')
            GROUP BY c.token;
            """,
            reverse_sql=DROP_VIEW + """
            CREATE VIEW vw_contract_debt AS
            SELECT c.token AS contract_token,
                   COALESCE(SUM(GREATEST(p.amount, 0)), 0) AS debt_amount
            FROM contract_contract c
            JOIN billing_invoice i ON i.contract_id = c.id
            JOIN billing_payment p ON p.invoice_id = i.id
            JOIN billing_paymentstatus ps ON ps.id = p.status_id
            WHERE ps.token NOT IN ('0','-4','-6', '-7', '-99')
            GROUP BY c.token;
            """,
        ),
    ]
