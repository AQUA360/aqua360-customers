import re
import unicodedata

from django.conf import settings
from django.db import migrations
from django.db.models import Max

ORIGIN_TOKEN = 'sepa_return'
CLAIM_ORIGIN_TOKEN = 'claim'
ORIGIN_NAMES = {
    'ca': 'Retorn SEPA',
    'es': 'Devolución SEPA',
}
# Plantilles d'avís de devolució que fins ara s'enviaven des d'una gestió d'impagats
# creada en fer el retorn: ara es llancen des del retorn SEPA.
RETURN_TEMPLATE_NAME = re.compile(r'devoluci')


def installation_language():
    language = getattr(settings, 'LANGUAGE', None) or getattr(settings, 'LANGUAGE_CODE', None) or 'ca'
    language = str(language).lower().replace('_', '-')
    return 'es' if language == 'es' or language.startswith('es-') else 'ca'


def normalize(text):
    text = unicodedata.normalize('NFKD', text or '')
    return ''.join(char for char in text if not unicodedata.combining(char)).lower()


def create_sepa_return_origin(apps, schema_editor):
    MessageOrigin = apps.get_model('communication', 'MessageOrigin')
    MessageTemplate = apps.get_model('communication', 'MessageTemplate')

    # BD nova: l'origen arriba amb initial_data (amb pk fixa).
    if not MessageOrigin.objects.exists():
        return

    # Aggregate i no order_by('-position'): a Postgres els NULL van primer en ordre descendent.
    last_position = MessageOrigin.objects.aggregate(Max('position'))['position__max']
    origin, _ = MessageOrigin.objects.get_or_create(
        token=ORIGIN_TOKEN,
        defaults={
            'name': ORIGIN_NAMES[installation_language()],
            'position': (last_position or 0) + 1,
        },
    )

    for template in MessageTemplate.objects.filter(origin__token=CLAIM_ORIGIN_TOKEN):
        if RETURN_TEMPLATE_NAME.search(normalize(template.name)):
            template.origin = origin
            template.save(update_fields=['origin'])


def remove_sepa_return_origin(apps, schema_editor):
    MessageOrigin = apps.get_model('communication', 'MessageOrigin')
    MessageTemplate = apps.get_model('communication', 'MessageTemplate')

    claim_origin = MessageOrigin.objects.filter(token=CLAIM_ORIGIN_TOKEN).first()
    if claim_origin:
        MessageTemplate.objects.filter(origin__token=ORIGIN_TOKEN).update(origin=claim_origin)
    MessageOrigin.objects.filter(token=ORIGIN_TOKEN, messagetemplate__isnull=True).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('communication', '0038_messagetemplate_invoice_email_delivery'),
    ]

    operations = [
        migrations.RunPython(create_sepa_return_origin, remove_sepa_return_origin),
    ]
