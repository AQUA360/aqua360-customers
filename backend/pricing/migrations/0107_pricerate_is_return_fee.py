from django.db import migrations, models


RETURN_FEE_CONFIG_TOKENS = [
    "invoice_return_price_rate_token",
    "claim_letter_return_fee_price_rate_token",
]


def mark_existing_return_fee_price_rate(apps, schema_editor):
    # La tarifa que ja estigués configurada com a despeses de devolució queda
    # marcada, perquè el formulari mostri l'estat real i no en calgui tornar a
    # marcar cap.
    ConfigProject = apps.get_model("coredata", "ConfigProject")
    PriceRate = apps.get_model("pricing", "PriceRate")

    tokens = [
        value
        for value in ConfigProject.objects.filter(
            token__in=RETURN_FEE_CONFIG_TOKENS
        ).values_list("value", flat=True)
        if value
    ]
    if not tokens:
        return
    PriceRate.objects.filter(token__in=tokens).update(is_return_fee=True)


def unmark_return_fee_price_rate(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("pricing", "0106_rename_code_accountingconcept_token_and_more"),
        ("coredata", "0133_add_invoice_return_price_rate_config"),
    ]

    operations = [
        migrations.AddField(
            model_name="pricerate",
            name="is_return_fee",
            field=models.BooleanField(default=False),
        ),
        migrations.RunPython(
            mark_existing_return_fee_price_rate,
            unmark_return_fee_price_rate,
        ),
    ]
