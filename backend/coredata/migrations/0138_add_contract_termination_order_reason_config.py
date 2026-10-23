from django.db import migrations
from django.db.models import Count

CONFIG_TOKEN = "order_reason_contract_termination"
CONFIG_NAME = "Motiu ordre Baixa de contracte"
REASON_TOKEN = "contract_termination"
REASON_NAME = "Baixa de contracte"


def add_contract_termination_order_reason(apps, schema_editor):
    OrderReason = apps.get_model("order", "OrderReason")
    OrderType = apps.get_model("order", "OrderType")
    ConfigProject = apps.get_model("coredata", "ConfigProject")

    reason = OrderReason.objects.filter(token=REASON_TOKEN).first()
    if not reason:
        reason = OrderReason.objects.filter(name__iexact=REASON_NAME).first()

    created_reason = False
    if not reason:
        reason = OrderReason.objects.create(token=REASON_TOKEN, name=REASON_NAME)
        created_reason = True

    if created_reason:
        safe_types = OrderType.objects.annotate(num_reasons=Count("reasons")).filter(
            num_reasons__gte=2
        )
        for order_type in safe_types:
            order_type.reasons.add(reason)

    config, created = ConfigProject.objects.get_or_create(
        token=CONFIG_TOKEN,
        defaults={"name": CONFIG_NAME, "value": reason.token},
    )
    if not created and not config.value:
        config.value = reason.token
        config.save()


def remove_contract_termination_order_reason(apps, schema_editor):
    OrderReason = apps.get_model("order", "OrderReason")
    ConfigProject = apps.get_model("coredata", "ConfigProject")

    ConfigProject.objects.filter(token=CONFIG_TOKEN).delete()

    reason = OrderReason.objects.filter(token=REASON_TOKEN).first()
    if reason and not reason.order_set.exists():
        reason.delete()


class Migration(migrations.Migration):

    dependencies = [
        ("coredata", "0137_add_aca_tram_min_persons_config"),
        ("order", "0013_orderreason"),
    ]

    operations = [
        migrations.RunPython(
            add_contract_termination_order_reason,
            remove_contract_termination_order_reason,
        ),
    ]
