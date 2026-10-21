from django.conf import settings
from django.db import migrations
from django.db.models import Max

ORIGIN_TOKEN = 'supplycut'
TEMPLATE_TOKEN = 'supplycut_notice'

# Plantilla genèrica d'avís de tall: les adreces i les dates surten de les
# variables %supplycut.*, de manera que serveix per a qualsevol tall. Es crea
# en l'idioma de la instal·lació (settings.LANGUAGE), com els catàlegs de
# initial_data/ca i initial_data/es.
TEXTS = {
    'ca': {
        'origin': 'Tall de subministrament',
        'template': 'Avís de tall de subministrament',
        'types': {
            'message_type_sms_token': {
                'subject': "Avís de tall de subministrament",
                'body': (
                    "%company.name: tall d'aigua previst del %supplycut.date_start a les %supplycut.time_start "
                    "al %supplycut.date_end a les %supplycut.time_end a %supplycut.affected_addresses. "
                    "Disculpeu les molèsties."
                ),
            },
            'message_type_email_token': {
                'subject': "Avís de tall de subministrament d'aigua",
                'body': (
                    "Benvolgut/da %person.name,\n\n"
                    "Li comuniquem que està previst un tall en el subministrament d'aigua que afecta "
                    "les adreces següents:\n- %supplycut.affected_addresses\n\n"
                    "Inici previst: %supplycut.date_start a les %supplycut.time_start\n"
                    "Fi prevista: %supplycut.date_end a les %supplycut.time_end\n"
                    "Motiu: %supplycut.cause_name\n\n"
                    "Disculpi les molèsties.\n\n"
                    "Atentament,\n%company.name"
                ),
            },
            'message_type_letter_token': {
                'subject': "Avís de tall de subministrament d'aigua",
                'body': (
                    "Benvolgut/da %person.name,\n\n"
                    "Ens posem en contacte amb vostè per comunicar-li que està previst un tall en el "
                    "subministrament d'aigua que afecta les adreces següents:\n- %supplycut.affected_addresses\n\n"
                    "Inici previst: %supplycut.date_start a les %supplycut.time_start\n"
                    "Fi prevista: %supplycut.date_end a les %supplycut.time_end\n"
                    "Motiu: %supplycut.cause_name\n\n"
                    "Disculpi les molèsties.\n\n"
                    "Atentament,\n\n%company.name"
                ),
            },
        },
    },
    'es': {
        'origin': 'Corte de suministro',
        'template': 'Aviso de corte de suministro',
        'types': {
            'message_type_sms_token': {
                'subject': "Aviso de corte de suministro",
                'body': (
                    "%company.name: corte de agua previsto del %supplycut.date_start a las %supplycut.time_start "
                    "al %supplycut.date_end a las %supplycut.time_end en %supplycut.affected_addresses. "
                    "Disculpen las molestias."
                ),
            },
            'message_type_email_token': {
                'subject': "Aviso de corte de suministro de agua",
                'body': (
                    "Estimado/a %person.name,\n\n"
                    "Le comunicamos que está previsto un corte en el suministro de agua que afecta "
                    "a las siguientes direcciones:\n- %supplycut.affected_addresses\n\n"
                    "Inicio previsto: %supplycut.date_start a las %supplycut.time_start\n"
                    "Fin previsto: %supplycut.date_end a las %supplycut.time_end\n"
                    "Motivo: %supplycut.cause_name\n\n"
                    "Disculpe las molestias.\n\n"
                    "Atentamente,\n%company.name"
                ),
            },
            'message_type_letter_token': {
                'subject': "Aviso de corte de suministro de agua",
                'body': (
                    "Estimado/a %person.name,\n\n"
                    "Nos ponemos en contacto con usted para comunicarle que está previsto un corte en el "
                    "suministro de agua que afecta a las siguientes direcciones:\n- %supplycut.affected_addresses\n\n"
                    "Inicio previsto: %supplycut.date_start a las %supplycut.time_start\n"
                    "Fin previsto: %supplycut.date_end a las %supplycut.time_end\n"
                    "Motivo: %supplycut.cause_name\n\n"
                    "Disculpe las molestias.\n\n"
                    "Atentamente,\n\n%company.name"
                ),
            },
        },
    },
}


def installation_language():
    """'es' per a les instal·lacions en castellà; la resta, 'ca'."""
    language = getattr(settings, 'LANGUAGE', None) or getattr(settings, 'LANGUAGE_CODE', None) or 'ca'
    language = str(language).lower().replace('_', '-')
    return 'es' if language == 'es' or language.startswith('es-') else 'ca'


def create_supplycut_origin_and_template(apps, schema_editor):
    MessageOrigin = apps.get_model('communication', 'MessageOrigin')
    MessageTemplate = apps.get_model('communication', 'MessageTemplate')
    MessageTypeTemplate = apps.get_model('communication', 'MessageTypeTemplate')
    MessageType = apps.get_model('communication', 'MessageType')
    ConfigProject = apps.get_model('coredata', 'ConfigProject')

    # BD nova: els catàlegs encara no hi són i l'origen arriba amb initial_data
    # (amb pk fixa). Crear-lo aquí xocaria amb les pk d'aquella càrrega.
    if not MessageOrigin.objects.exists():
        return

    texts = TEXTS[installation_language()]

    # Aggregate i no order_by('-position'): a Postgres els NULL van primer en ordre descendent.
    last_position = MessageOrigin.objects.aggregate(Max('position'))['position__max']
    origin, _ = MessageOrigin.objects.get_or_create(
        token=ORIGIN_TOKEN,
        defaults={
            'name': texts['origin'],
            'position': (last_position or 0) + 1,
        },
    )

    if MessageTemplate.objects.filter(token=TEMPLATE_TOKEN).exists():
        return

    type_templates = []
    for config_token, content in texts['types'].items():
        type_token = ConfigProject.objects.filter(token=config_token).values_list('value', flat=True).first()
        message_type = MessageType.objects.filter(token=type_token).first() if type_token else None
        if message_type is None:
            # Instal·lació sense aquest canal (p. ex. sense SMS): no se'n crea la plantilla.
            continue
        type_templates.append(MessageTypeTemplate.objects.create(
            token=f'{TEMPLATE_TOKEN}_{message_type.token}',
            type=message_type,
            subject=content['subject'],
            body=content['body'],
        ))

    if not type_templates:
        return
    template = MessageTemplate.objects.create(
        token=TEMPLATE_TOKEN,
        name=texts['template'],
        origin=origin,
    )
    template.templates.set(type_templates)


def remove_supplycut_origin_and_template(apps, schema_editor):
    MessageOrigin = apps.get_model('communication', 'MessageOrigin')
    MessageTemplate = apps.get_model('communication', 'MessageTemplate')
    MessageTypeTemplate = apps.get_model('communication', 'MessageTypeTemplate')

    MessageTypeTemplate.objects.filter(token__startswith=f'{TEMPLATE_TOKEN}_').delete()
    MessageTemplate.objects.filter(token=TEMPLATE_TOKEN).delete()
    MessageOrigin.objects.filter(token=ORIGIN_TOKEN, messagetemplate__isnull=True).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('communication', '0033_communicationprocessexclusion'),
    ]

    operations = [
        migrations.RunPython(create_supplycut_origin_and_template, remove_supplycut_origin_and_template),
    ]
