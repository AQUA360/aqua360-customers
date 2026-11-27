from django.db import migrations
from django.db.models import Q

ALTA_CONFIG_TOKEN = 'contract_use_aca_alta_tokens'


def add_config_aca_alta_rows(apps, schema_editor):
    """Fila de tarifes d'ALTA a la pantalla de Config ACA de cada explotació que encara no la té,
    amb les tarifes de cànon que casen amb el valor actual (com fa update_config_aca_service)."""
    ConfigProject = apps.get_model('coredata', 'ConfigProject')
    ConfigAca = apps.get_model('billing', 'ConfigAca')
    Exploitation = apps.get_model('service', 'Exploitation')
    PriceRate = apps.get_model('pricing', 'PriceRate')

    config_project = ConfigProject.objects.filter(token=ALTA_CONFIG_TOKEN).first()
    if not config_project:
        return
    tokens = [part.strip() for part in (config_project.value or '').split('|') if part.strip()]
    token_q = Q()
    for token in tokens:
        token_q |= Q(token__icontains=token)

    # Només on la Config ACA ja està creada: on no, la crea sencera update_config_aca_service
    configured_ids = ConfigAca.objects.exclude(exploitation__isnull=True).values('exploitation_id')
    for exploitation in Exploitation.objects.filter(id__in=configured_ids):
        if ConfigAca.objects.filter(exploitation=exploitation, config_project=config_project).exists():
            continue
        config_aca = ConfigAca.objects.create(
            exploitation=exploitation,
            config_project=config_project,
            token=config_project.token,
            token_type='PriceRate',
            is_active=True,
        )
        if tokens:
            config_aca.price_rates.set(PriceRate.objects.filter(
                token_q, product__exploitation=exploitation, is_active=True,
            ).distinct())


class Migration(migrations.Migration):

    dependencies = [
        ('billing', '0354_insolvency_process_debt_management'),
    ]

    operations = [
        migrations.RunPython(add_config_aca_alta_rows, migrations.RunPython.noop),
    ]
