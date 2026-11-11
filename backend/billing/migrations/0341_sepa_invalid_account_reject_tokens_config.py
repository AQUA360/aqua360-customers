from django.db import migrations


TOKEN = 'sepa_invalid_account_reject_tokens'
# Motius ISO 20022 pels quals no té sentit tornar a domiciliar al mateix compte
# (vegeu billing/utils/sepa_invalid_account_service.py)
VALUE = 'AC01,AC04,AC06,AC13,AG01,BE06,MD07'
NAME = (
    "Retorn SEPA → Pagament Bancari: AC01 IBAN incorrecte, AC04 compte tancat, AC06 compte bloquejat, "
    "AC13 tipus compte invàlid, AG01 compte no admet rebuts, BE06 deutor desconegut, MD07 titular difunt"
)


def create_config(apps, schema_editor):
    """Crea el paràmetre amb els motius per defecte si encara no existeix."""
    ConfigProject = apps.get_model('coredata', 'ConfigProject')
    ConfigProject.objects.get_or_create(
        token=TOKEN,
        defaults={
            'name': NAME,
            'value': VALUE,
        },
    )


def delete_config(apps, schema_editor):
    """Desfà la migració esborrant el paràmetre."""
    ConfigProject = apps.get_model('coredata', 'ConfigProject')
    ConfigProject.objects.filter(token=TOKEN).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('billing', '0340_unpaid_fee_run'),
    ]

    operations = [
        migrations.RunPython(create_config, delete_config),
    ]
