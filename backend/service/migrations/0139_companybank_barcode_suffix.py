from django.db import migrations, models


def copy_global_suffix(apps, schema_editor):
    """El sufix era global: els comptes existents hereten el valor que tenien en ús."""
    ConfigProject = apps.get_model('coredata', 'ConfigProject')
    CompanyBank = apps.get_model('service', 'CompanyBank')
    config = ConfigProject.objects.filter(token='reference_suffix_barcode_token').first()
    suffix = str(config.value) if config and config.value else ''
    # Els valors no vàlids no es copien; la generació del codi farà servir '501'.
    if len(suffix) == 3 and suffix.isascii() and suffix.isdigit():
        CompanyBank.objects.filter(barcode_suffix__isnull=True).update(barcode_suffix=suffix)


class Migration(migrations.Migration):

    dependencies = [
        ('coredata', '0151_callregister_incident_keep_calls'),
        ('service', '0138_meter_dictionary_constraints'),
    ]

    operations = [
        migrations.AddField(
            model_name='companybank',
            name='barcode_suffix',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.RunPython(copy_global_suffix, migrations.RunPython.noop),
    ]
