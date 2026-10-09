from django.db import migrations


def create_variablecalculation_units(apps, schema_editor):
    VariableCalculation = apps.get_model("pricing", "VariableCalculation")
    obj, _ = VariableCalculation.objects.get_or_create(
        token="units",
        defaults={"name": "Unitats"},
    )
    if obj.name != "Unitats":
        obj.name = "Unitats"
        obj.save(update_fields=["name"])


def remove_variablecalculation_units(apps, schema_editor):
    VariableCalculation = apps.get_model("pricing", "VariableCalculation")
    VariableCalculation.objects.filter(token="units", name="Unitats").delete()


class Migration(migrations.Migration):

    dependencies = [
        ("pricing", "0098_backfill_lineitemtype_is_prorated_from_active_choice"),
    ]

    operations = [
        migrations.RunPython(
            create_variablecalculation_units,
            remove_variablecalculation_units,
        ),
    ]

