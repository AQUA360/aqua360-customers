from django.db import migrations

NEW_TOKEN = 'claim_attached_documents'
OLD_INVOICES_TOKEN = 'attach_invoices_in_claims'
OLD_EXTRA_DOCS_TOKEN = 'attach_extra_docs_in_claims'
ALL_DOCUMENTS = 'invoices,payment_slips'
NAME = (
    "Documents adjunts a les comunicacions d'impagats (a més del document del pas, que es tria "
    "a la plantilla): invoices (factures), payment_slips (fulls de pagament), separats per "
    "comes. Buit: cap"
)


def _is_false(config):
    return bool(config and (config.value or '').strip().lower() != 'true')


def merge_claim_attachment_configs(apps, schema_editor):
    """Passa els dos configProject d'adjunts d'impagats a un de sol.

    Abans, amb `attach_invoices_in_claims` diferent de 'true' o `attach_extra_docs_in_claims`
    a 'false', no s'adjuntava ni la factura ni el full de pagament: es manté igual (valor buit).
    Sense cap dels dos (la tasca creava el primer a 'true'), s'adjunten tots dos.
    """
    ConfigProject = apps.get_model('coredata', 'ConfigProject')
    invoices = ConfigProject.objects.filter(token=OLD_INVOICES_TOKEN).first()
    extra_docs = ConfigProject.objects.filter(token=OLD_EXTRA_DOCS_TOKEN).first()
    extra_docs_off = bool(extra_docs and (extra_docs.value or '').strip().lower() == 'false')
    value = '' if _is_false(invoices) or extra_docs_off else ALL_DOCUMENTS
    if not ConfigProject.objects.filter(token=NEW_TOKEN).exists():
        ConfigProject.objects.create(token=NEW_TOKEN, name=NAME, value=value, file='COMMUNICATION')
    ConfigProject.objects.filter(token__in=[OLD_INVOICES_TOKEN, OLD_EXTRA_DOCS_TOKEN]).delete()


def split_claim_attachment_configs(apps, schema_editor):
    ConfigProject = apps.get_model('coredata', 'ConfigProject')
    config = ConfigProject.objects.filter(token=NEW_TOKEN).first()
    documents = {v.strip() for v in ((config.value if config else ALL_DOCUMENTS) or '').split(',') if v.strip()}
    ConfigProject.objects.get_or_create(
        token=OLD_INVOICES_TOKEN, defaults={'name': 'Attach invoices in claims', 'value': 'true'},
    )
    ConfigProject.objects.get_or_create(
        token=OLD_EXTRA_DOCS_TOKEN,
        defaults={
            'name': "Adjuntar factures i rebuts (o document agrupat) a les comunicacions d'impagats",
            'value': 'true' if documents else 'false',
            'file': 'COMMUNICATION',
        },
    )
    ConfigProject.objects.filter(token=NEW_TOKEN).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('coredata', '0161_auth_session_token'),
    ]

    operations = [
        migrations.RunPython(merge_claim_attachment_configs, split_claim_attachment_configs),
    ]
