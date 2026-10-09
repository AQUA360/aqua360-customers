# statistics/migrations/0039_vw_contract_debt_no_negative.py
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
        ('statistics', '0038_new_available_report'),
    ]

    operations = [

        # -----------------------------
        # vw_contract_debt: el deute d'un contracte no pot ser mai negatiu.
        # Els pagaments d'import negatiu (factures rectificatives i liquidacions
        # a favor del client que es queden en estat Pendent, Vençut o En saldo)
        # es descomptaven del deute: un contracte podia sortir amb -24,04 EUR i,
        # en entrar-li una factura de 30 EUR, mostrar-ne 5,96 en lloc de 30.
        # Ara cada pagament hi suma GREATEST(amount, 0): els negatius no hi
        # resten i el total no pot baixar de zero.
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
            WHERE ps.token NOT IN ('0','-4','-6', '-7', '-99')
            GROUP BY c.token;
            """,
            reverse_sql=DROP_VIEW + """
            CREATE VIEW vw_contract_debt AS
            SELECT c.token AS contract_token, COALESCE(SUM(p.amount), 0) AS debt_amount
            FROM contract_contract c
            JOIN billing_invoice i ON i.contract_id = c.id
            JOIN billing_payment p ON p.invoice_id = i.id
            JOIN billing_paymentstatus ps ON ps.id = p.status_id
            WHERE ps.token NOT IN ('0','-4','-6', '-7', '-99')
            GROUP BY c.token;
            """,
        ),
    ]
