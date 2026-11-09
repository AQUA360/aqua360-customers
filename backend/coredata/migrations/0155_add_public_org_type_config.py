from django.db import migrations

PUBLIC_ORG_TYPE_TOKEN = 'public_org_type'
USES_ACA_TOKEN = 'uses_aca'
ACA_ORG_TYPE = 'aca'
PUBLIC_ORG_TYPE_NAME = (
    "Organisme públic al qual pertany el projecte ('aca' = Agència Catalana de l'Aigua; "
    "buit = explotació fora de Catalunya)"
)
# Informes que només tenen sentit per als projectes de l'ACA.
ACA_REPORT_FUNCTION_NAMES = ('aca_summary_report', 'factdeta_report')


def _is_legacy_aca(value):
    return str(value or '').strip().lower() in ('true', '1', 'yes', 't')


def _is_aca_org(value):
    return str(value or '').strip().lower() == ACA_ORG_TYPE


def add_public_org_type_config(apps, schema_editor):
    ConfigProject = apps.get_model('coredata', 'ConfigProject')
    AvailableReport = apps.get_model('statistics', 'AvailableReport')

    uses_aca = ConfigProject.objects.filter(token=USES_ACA_TOKEN).first()
    legacy_aca = _is_legacy_aca(uses_aca.value if uses_aca else None)

    org = ConfigProject.objects.filter(token=PUBLIC_ORG_TYPE_TOKEN).first()
    if org is None:
        ConfigProject.objects.create(
            token=PUBLIC_ORG_TYPE_TOKEN,
            name=PUBLIC_ORG_TYPE_NAME,
            value=ACA_ORG_TYPE if legacy_aca else '',
            file='ACA',
        )
    # Si ja existia (creat manualment o per loaddata) es respecta el seu valor.

    ConfigProject.objects.filter(token=USES_ACA_TOKEN).delete()

    org_value = ConfigProject.objects.filter(
        token=PUBLIC_ORG_TYPE_TOKEN
    ).values_list('value', flat=True).first()
    AvailableReport.objects.filter(
        function_name__in=ACA_REPORT_FUNCTION_NAMES
    ).update(is_active=_is_aca_org(org_value))


def remove_public_org_type_config(apps, schema_editor):
    ConfigProject = apps.get_model('coredata', 'ConfigProject')
    AvailableReport = apps.get_model('statistics', 'AvailableReport')

    org_value = ConfigProject.objects.filter(
        token=PUBLIC_ORG_TYPE_TOKEN
    ).values_list('value', flat=True).first()
    legacy_aca = _is_aca_org(org_value)

    ConfigProject.objects.filter(token=USES_ACA_TOKEN).delete()
    ConfigProject.objects.create(
        token=USES_ACA_TOKEN,
        name='Bool fa servir use_aca',
        value='True' if legacy_aca else 'False',
    )
    ConfigProject.objects.filter(token=PUBLIC_ORG_TYPE_TOKEN).delete()

    AvailableReport.objects.filter(
        function_name__in=ACA_REPORT_FUNCTION_NAMES
    ).update(is_active=legacy_aca)


class Migration(migrations.Migration):

    dependencies = [
        ('coredata', '0154_add_send_batch_status_lifecycle_tokens'),
        ('statistics', '0051_add_factdeta_report'),
    ]

    operations = [
        migrations.RunPython(add_public_org_type_config, remove_public_org_type_config),
    ]
