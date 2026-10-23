import re

from django.db import migrations

# Fórmules que són només un número escrit amb coma decimal (0,5). Amb l'eval eren una tupla
# (0, 5) i el nou avaluador de fórmules les rebutja. Les condicions no es toquen: allà la coma
# separa llistes de valors.
DECIMAL_COMMA_RE = re.compile(r'^\s*([-+]?\d+),(\d+)\s*$')


def fix_decimal_comma(apps, schema_editor):
    for model_name in ('Adjustment', 'AdjustmentIntervalStretch', 'LineItemType'):
        model = apps.get_model('pricing', model_name)
        for item in model.objects.filter(formula__contains=',').only('id', 'formula'):
            match = DECIMAL_COMMA_RE.match(item.formula)
            if match:
                item.formula = f'{match.group(1)}.{match.group(2)}'
                item.save(update_fields=['formula'])


class Migration(migrations.Migration):

    dependencies = [
        ('pricing', '0131_alter_accountingconcept_category'),
    ]

    operations = [
        migrations.RunPython(fix_decimal_comma, migrations.RunPython.noop),
    ]
