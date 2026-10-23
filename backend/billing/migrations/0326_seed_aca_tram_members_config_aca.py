from django.db import migrations

CONFIG_TOKEN = 'aca_tram_members_variable_token'


def seed_aca_tram_members_config_aca(apps, schema_editor):
    ConfigProject = apps.get_model('coredata', 'ConfigProject')
    ConfigAca = apps.get_model('billing', 'ConfigAca')
    Exploitation = apps.get_model('service', 'Exploitation')
    VariableType = apps.get_model('contract', 'VariableType')

    config = ConfigProject.objects.filter(token=CONFIG_TOKEN).first()
    if not config:
        return

    tokens = [part.strip() for part in (config.value or '').split('|') if part.strip()]
    variable_types = list(VariableType.objects.filter(token__in=tokens))

    for exploitation in Exploitation.objects.all():
        config_aca = ConfigAca.objects.filter(
            exploitation=exploitation,
            config_project=config,
        ).first()
        if not config_aca:
            config_aca = ConfigAca.objects.create(
                exploitation=exploitation,
                config_project=config,
                token=config.token,
                token_type='VariableType',
                is_active=True,
            )
        else:
            config_aca.token = config.token
            config_aca.token_type = 'VariableType'
            config_aca.is_active = True
            config_aca.save(update_fields=['token', 'token_type', 'is_active'])
        if variable_types:
            config_aca.variable_types.set(variable_types)


def unseed_aca_tram_members_config_aca(apps, schema_editor):
    ConfigAca = apps.get_model('billing', 'ConfigAca')
    ConfigAca.objects.filter(token=CONFIG_TOKEN).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('billing', '0325_merge_20261021_1042'),
        ('coredata', '0143_add_aca_tram_members_variable_config'),
        ('service', '0135_company_contact_texts'),
        ('contract', '0244_aca_document_change_exchange_file'),
    ]

    operations = [
        migrations.RunPython(
            seed_aca_tram_members_config_aca,
            unseed_aca_tram_members_config_aca,
        ),
    ]
