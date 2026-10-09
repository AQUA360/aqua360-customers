from django.db import migrations

# Correccio de codis segons la llista de valors "5.2 Tipus de via" del document
# de l'ACA "04_estructura_fitxer_registre_ampliacio.pdf" (Ampliació de trams).
# Alguns valors existents eren directament incorrectes o xocaven amb el codi
# real d'un altre tipus de via (p.ex. "Carrer" tenia aca_abbreviation="C" en
# lloc de "CR", i "Carretera" tenia aca_abbreviation="CR", que en realitat és
# el codi ACA de "Carrer").
ACA_ABBREVIATION_FIXES = {
    'Carrer': 'CR',
    'Plaça': 'PL',
    'Passeig': 'PG',
    'Passatge': 'PT',
    'Carretera': 'CA',
    'Baixada': 'BD',
    'Jardins': 'JR',
    'Urbanització': 'UB',
    'Riera': 'RR',
    'Raval': 'AR',
    'Masia': 'MS',
    'Pujada': 'PD',
    'Carreró': 'CO',
    'Pont': 'PN',
    'Disseminat': 'DS',
    'Grup': 'GP',
    'Partida': 'PA',
    'Colònia': 'CL',
}

# Tipus de via sense equivalent real a la llista de l'ACA: es buida el camp
# perquè el codi de generació del fitxer apliqui el valor per defecte "VP"
# (Via Pública Indeterminada) en lloc d'un codi inventat/incorrecte.
ACA_ABBREVIATION_CLEAR = ['Finca', 'Autovia', 'Parc']


def fix_aca_abbreviations(apps, schema_editor):
    StreetType = apps.get_model('coredata', 'StreetType')
    for name, aca_abbreviation in ACA_ABBREVIATION_FIXES.items():
        StreetType.objects.filter(name=name).update(aca_abbreviation=aca_abbreviation)
    StreetType.objects.filter(name__in=ACA_ABBREVIATION_CLEAR).update(aca_abbreviation=None)


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('coredata', '0123_add_claim_letter_return_fee_amount_config'),
    ]

    operations = [
        migrations.RunPython(fix_aca_abbreviations, noop_reverse),
    ]
