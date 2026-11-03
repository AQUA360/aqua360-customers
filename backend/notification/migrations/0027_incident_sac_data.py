from django.conf import settings
from django.db import migrations

# Paràmetres de la gestió SAC que configura cada client
CONFIGS = [
    ('incident_retention_years', 'Incidències: anys de retenció', '5'),
    ('incident_channel_app_token', "Incidències: token del canal de l'app de lectures", 'app'),
]

# Canals d'entrada per defecte (cada client els pot canviar, ordenar o esborrar)
CHANNELS = [
    ('telefon', {'ca': 'Telèfon', 'es': 'Teléfono'}, True),
    ('email', {'ca': 'Correu electrònic', 'es': 'Correo electrónico'}, False),
    ('ov', {'ca': 'Oficina virtual', 'es': 'Oficina virtual'}, False),
    ('presencial', {'ca': 'Presencial', 'es': 'Presencial'}, False),
    ('postal', {'ca': 'Correu postal', 'es': 'Correo postal'}, False),
    ('app', {'ca': 'App de lectures', 'es': 'App de lecturas'}, False),
]


def forwards(apps, schema_editor):
    """
    Paràmetres de configuració i, per a les incidències existents, el creador i la
    data de tancament a partir de l'historial d'estats: el creador és l'usuari del
    primer registre i la data de tancament, la de l'últim pas a l'estat tancat.
    """
    Incident = apps.get_model('notification', 'Incident')
    IncidentChannel = apps.get_model('notification', 'IncidentChannel')
    LogIncidentStatusChange = apps.get_model('logger', 'LogIncidentStatusChange')
    ConfigProject = apps.get_model('coredata', 'ConfigProject')

    for token, name, value in CONFIGS:
        ConfigProject.objects.get_or_create(token=token, defaults={'name': name, 'value': value})

    language = 'es' if settings.LANGUAGE_CODE.startswith('es') else 'ca'
    for position, (token, names, is_default) in enumerate(CHANNELS):
        IncidentChannel.objects.get_or_create(
            token=token, defaults={'name': names[language], 'position': position, 'is_default': is_default},
        )

    config = ConfigProject.objects.filter(token='incident_status_closed_token').first()
    closed_token = config.value if config else '2'

    for incident in Incident.objects.filter(created_by__isnull=True).iterator():
        first_log = LogIncidentStatusChange.objects.filter(object_id=incident.id).order_by('timestamp').first()
        if first_log and first_log.user_id:
            Incident.objects.filter(id=incident.id).update(created_by_id=first_log.user_id)

    for incident in Incident.objects.filter(closed_at__isnull=True, status__token=closed_token).iterator():
        last_close = LogIncidentStatusChange.objects.filter(
            object_id=incident.id, current_status__token=closed_token,
        ).order_by('-timestamp').first()
        # update() per no tocar updated_at
        Incident.objects.filter(id=incident.id).update(
            closed_at=last_close.timestamp if last_close else incident.updated_at
        )


def backwards(apps, schema_editor):
    ConfigProject = apps.get_model('coredata', 'ConfigProject')
    IncidentChannel = apps.get_model('notification', 'IncidentChannel')
    ConfigProject.objects.filter(token__in=[token for token, _, _ in CONFIGS]).delete()
    IncidentChannel.objects.filter(token__in=[token for token, _, _ in CHANNELS]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('notification', '0026_incident_sac_management'),
        ('logger', '0040_rename_logincidentstatus_logincidentstatuschange'),
        ('coredata', '0099_add_incident_closed_status_config'),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
