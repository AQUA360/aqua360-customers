from django.db import migrations

OLD_TOKEN = "canvi_titular"
NEW_TOKEN = "change_of_owner"

TERMINATION_TOKEN = "contract_termination"
TERMINATION_REMOVE_TYPES = ["restore_meter", "restore_supply"]
TERMINATION_ADD_TYPES = ["remove_meter"]


def forwards(apps, schema_editor):
    OrderReason = apps.get_model("order", "OrderReason")
    OrderType = apps.get_model("order", "OrderType")

    # Token en català -> anglès (només si el nou no existeix ja).
    if not OrderReason.objects.filter(token=NEW_TOKEN).exists():
        OrderReason.objects.filter(token=OLD_TOKEN).update(token=NEW_TOKEN)

    # La baixa de contracte retira, no reposa.
    for reason in OrderReason.objects.filter(token=TERMINATION_TOKEN):
        reason.type.remove(*OrderType.objects.filter(token__in=TERMINATION_REMOVE_TYPES))
        reason.type.add(*OrderType.objects.filter(token__in=TERMINATION_ADD_TYPES))


def backwards(apps, schema_editor):
    OrderReason = apps.get_model("order", "OrderReason")
    if not OrderReason.objects.filter(token=OLD_TOKEN).exists():
        OrderReason.objects.filter(token=NEW_TOKEN).update(token=OLD_TOKEN)


class Migration(migrations.Migration):

    dependencies = [
        ("order", "0036_order_change_meter_applied_at_and_more"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
