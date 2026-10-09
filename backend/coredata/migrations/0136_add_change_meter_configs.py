import json

from django.db import migrations

CONFIGS = (
    {
        "token": "change_meter_field_mapping",
        "name": "Change Meter Field Mapping",
        "value": json.dumps(
            [
                {"customers_field": "meter_old", "form_field": "codi_comptador_anterior"},
                {"customers_field": "reading_old", "form_field": "lectura_anterior"},
                {"customers_field": "meter_new", "form_field": "codi_comptador_instal_lat"},
                {"customers_field": "reading_new", "form_field": "lectura_actual"},
            ]
        ),
    },
    {
        "token": "change_meter_quick_fields",
        "name": "Change Meter Quick Fields",
        "value": json.dumps(
            [
                {"name": "Tipus d'instal·lació", "type": "options", "token": "tipus_dinstallacio", "required": True},
                {"name": "Material del comptador", "type": "options", "token": "material_del_comptador", "required": True},
                {"name": "Tipus lectura", "type": "options", "token": "tipus_lectura", "required": True},
                {"name": "Diàmetre comptador (mm)", "type": "options", "token": "diametre_comptador_mm", "required": True},
                {"name": "Número de comptador (sortint)", "type": "text", "token": "numero_de_comptador_sortint", "required": True},
                {"name": "Lectura comptador (sortint)", "type": "text", "token": "lectura_de_comptador_sortint", "required": True},
                {"name": "Foto comptador (sortint)", "type": "photo", "token": "foto_de_comptador_sortint", "required": False},
                {"name": "Número de comptador", "type": "text", "token": "numero_de_comptador", "required": True},
                {"name": "Lectura inicial", "type": "numeric", "token": "lectura_inicial", "required": True},
                {"name": "Foto del comptador", "type": "photo", "token": "foto_de_comptador", "required": False},
            ],
            ensure_ascii=False,
        ),
    },
)


def add_change_meter_configs(apps, schema_editor):
    ConfigProject = apps.get_model("coredata", "ConfigProject")
    for config in CONFIGS:
        ConfigProject.objects.get_or_create(
            token=config["token"],
            defaults={
                "name": config["name"],
                "value": config["value"],
                "file": None,
            },
        )


def remove_change_meter_configs(apps, schema_editor):
    ConfigProject = apps.get_model("coredata", "ConfigProject")
    ConfigProject.objects.filter(
        token__in=[config["token"] for config in CONFIGS]
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("coredata", "0135_add_use_manual_bank_remittance_config"),
    ]

    operations = [
        migrations.RunPython(add_change_meter_configs, remove_change_meter_configs),
    ]
