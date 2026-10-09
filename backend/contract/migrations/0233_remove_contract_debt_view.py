from django.db import migrations


class Migration(migrations.Migration):
    """Elimina Contract.debt_view només de l'estat de Django.

    El camp reutilitzava db_column='token' i feia que Django inclogués la columna
    dues vegades en INSERT/UPDATE (token + debt_view).
    """

    dependencies = [
        ('contract', '0232_contract_debt_view_relation'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.RemoveField(
                    model_name='contract',
                    name='debt_view',
                ),
            ],
        ),
    ]
