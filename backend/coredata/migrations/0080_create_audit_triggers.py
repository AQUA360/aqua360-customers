# coredata/migrations/0080_create_audit_triggers.py
from django.db import migrations

class Migration(migrations.Migration):

    dependencies = [
        ('coredata', '0079_alter_streettype_abbreviation'),
        ('billing', '0233_invoice_verifactu_invoice'),
        ('verifactu', '0001_initial'),
    ]

    operations = [

        # -----------------------------
        # 1️⃣ Create audit table for billing_invoice
        # -----------------------------
        migrations.RunSQL("""
        CREATE TABLE IF NOT EXISTS billing_invoice_audit (
            id SERIAL PRIMARY KEY,
            operation CHAR(1) NOT NULL,
            changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            db_user TEXT DEFAULT current_user,
            app_user TEXT,
            old_data JSONB,
            new_data JSONB
        );
        """),

        # -----------------------------
        # 2️⃣ Create audit table for verifactu_verifactunotification
        # -----------------------------
        migrations.RunSQL("""
        CREATE TABLE IF NOT EXISTS verifactu_verifactunotification_audit (
            id SERIAL PRIMARY KEY,
            operation CHAR(1) NOT NULL,
            changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            db_user TEXT DEFAULT current_user,
            app_user TEXT,
            old_data JSONB,
            new_data JSONB
        );
        """),

        # # -----------------------------
        # # 3️⃣ Create trigger function (shared)
        # # -----------------------------
        # migrations.RunSQL("""
        # CREATE OR REPLACE FUNCTION audit_table_changes()
        # RETURNS trigger AS $$
        # DECLARE
        #     app_user TEXT := current_setting('myapp.user_id', true);
        # BEGIN
        #     IF TG_OP = 'INSERT' THEN
        #         IF TG_TABLE_NAME = 'billing_invoice' THEN
        #             INSERT INTO billing_invoice_audit(operation, new_data, app_user)
        #             VALUES ('I', row_to_json(NEW), app_user);
        #         ELSIF TG_TABLE_NAME = 'verifactu_verifactuinvoice' THEN
        #             INSERT INTO verifactu_verifactuinvoice_audit(operation, new_data, app_user)
        #             VALUES ('I', row_to_json(NEW), app_user);
        #         END IF;
        #         RETURN NEW;

        #     ELSIF TG_OP = 'UPDATE' THEN
        #         IF TG_TABLE_NAME = 'billing_invoice' THEN
        #             INSERT INTO billing_invoice_audit(operation, old_data, new_data, app_user)
        #             VALUES ('U', row_to_json(OLD), row_to_json(NEW), app_user);
        #         ELSIF TG_TABLE_NAME = 'verifactu_verifactuinvoice' THEN
        #             INSERT INTO verifactu_verifactuinvoice_audit(operation, old_data, new_data, app_user)
        #             VALUES ('U', row_to_json(OLD), row_to_json(NEW), app_user);
        #         END IF;
        #         RETURN NEW;

        #     ELSIF TG_OP = 'DELETE' THEN
        #         IF TG_TABLE_NAME = 'billing_invoice' THEN
        #             INSERT INTO billing_invoice_audit(operation, old_data, app_user)
        #             VALUES ('D', row_to_json(OLD), app_user);
        #         ELSIF TG_TABLE_NAME = 'verifactu_verifactuinvoice' THEN
        #             INSERT INTO verifactu_verifactuinvoice_audit(operation, old_data, app_user)
        #             VALUES ('D', row_to_json(OLD), app_user);
        #         END IF;
        #         RETURN OLD;
        #     END IF;
        # END;
        # $$ LANGUAGE plpgsql;
        # """),

        # # -----------------------------
        # # 4️⃣ Create trigger for billing_invoice
        # # -----------------------------
        # migrations.RunSQL("""
        # CREATE TRIGGER billing_invoice_audit_trigger
        # AFTER INSERT OR UPDATE OR DELETE ON billing_invoice
        # FOR EACH ROW EXECUTE FUNCTION audit_table_changes();
        # """),

        # # -----------------------------
        # # 5️⃣ Create trigger for verifactu_verifactuinvoice
        # # -----------------------------
        # migrations.RunSQL("""
        # CREATE TRIGGER verifactu_verifactuinvoice_audit_trigger
        # AFTER INSERT OR UPDATE OR DELETE ON verifactu_verifactuinvoice
        # FOR EACH ROW EXECUTE FUNCTION audit_table_changes();
        # """),
    ]