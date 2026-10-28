from django.db import migrations
from django.db.models.functions import Upper


def merge_duplicate_dictionary_values(apps, schema_editor):
    database = schema_editor.connection.alias
    manufacturer_model = apps.get_model('service', 'MeterManufacturer')
    meter_model = apps.get_model('service', 'MeterModel')
    technology_model = apps.get_model('service', 'MeterCommTechnology')

    manufacturers = {}
    for value in manufacturer_model.objects.using(database).annotate(
        normalized_name=Upper('name'),
    ).order_by('id').iterator():
        if value.normalized_name is None:
            continue
        existing_id = manufacturers.setdefault(value.normalized_name, value.pk)
        if existing_id != value.pk:
            meter_model.objects.using(database).filter(manufacturer_id=value.pk).update(
                manufacturer_id=existing_id,
            )
            manufacturer_model.objects.using(database).filter(pk=value.pk).delete()

    for model in (meter_model, technology_model):
        values = {}
        for value in model.objects.using(database).annotate(
            normalized_name=Upper('name'),
        ).order_by('id').iterator():
            if value.normalized_name is None:
                continue
            key = (value.manufacturer_id, value.normalized_name) if model == meter_model else value.normalized_name
            existing_id = values.setdefault(key, value.pk)
            if existing_id != value.pk:
                model.objects.using(database).filter(pk=value.pk).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('service', '0136_metercommtechnology'),
    ]

    operations = [
        migrations.RunPython(merge_duplicate_dictionary_values, migrations.RunPython.noop),
    ]
