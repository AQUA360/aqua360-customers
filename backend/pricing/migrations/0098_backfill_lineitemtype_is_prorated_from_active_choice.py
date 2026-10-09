from django.db import migrations


def backfill_lineitemtype_is_prorated(apps, schema_editor):
    LineItemType = apps.get_model('pricing', 'LineItemType')
    LineItemType.objects.filter(active_choice='DAYS').update(is_prorated=True)
    LineItemType.objects.exclude(active_choice='DAYS').update(is_prorated=False)


class Migration(migrations.Migration):

    dependencies = [
        ('pricing', '0097_alter_variablecalculation_token'),
    ]

    operations = [
        migrations.RunPython(backfill_lineitemtype_is_prorated, migrations.RunPython.noop),
    ]
