from django.db import migrations


def add_claim_letter_return_fee_price_rate_config(apps, schema_editor):
    ConfigProject = apps.get_model("coredata", "ConfigProject")
    ConfigProject.objects.get_or_create(
        token="claim_letter_return_fee_price_rate_token",
        defaults={
            "name": "Token de la tarifa (PriceRate) de despeses de devolució a la carta de suspensió",
            "value": None,
        },
    )


def remove_claim_letter_return_fee_price_rate_config(apps, schema_editor):
    ConfigProject = apps.get_model("coredata", "ConfigProject")
    ConfigProject.objects.filter(token="claim_letter_return_fee_price_rate_token").delete()


class Migration(migrations.Migration):

    dependencies = [
        ("coredata", "0122_add_executed_script"),
    ]

    operations = [
        migrations.RunPython(
            add_claim_letter_return_fee_price_rate_config,
            remove_claim_letter_return_fee_price_rate_config,
        ),
    ]
