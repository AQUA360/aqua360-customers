# contract/migrations/0232_contract_debt_view_relation.py
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    """Afegeix Contract.debt_view (contract/models.py) nomes a l'estat de Django,
    sense tocar la BD: reutilitza la columna 'token' ja existent (db_column='token')
    per permetre un LEFT JOIN normal contra vw_contract_debt via select_related,
    en lloc d'un Subquery(OuterRef(...)) correlacionat (molt mes lent per llistes
    grans de contractes, veure contract/utils/contract_list_queryset.py)."""

    dependencies = [
        ('contract', '0231_contractdebtview'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.AddField(
                    model_name='contract',
                    name='debt_view',
                    field=models.ForeignKey(
                        blank=True,
                        db_constraint=False,
                        editable=False,
                        null=True,
                        on_delete=django.db.models.deletion.DO_NOTHING,
                        related_name='contracts',
                        to='contract.contractdebtview',
                        db_column='token',
                    ),
                ),
            ],
        ),
    ]
