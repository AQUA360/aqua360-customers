from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('service', '0130_exploitation_incasol_num'),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name='companybankrouting',
            name='unique_company_payer_bank_routing',
        ),
        migrations.RemoveConstraint(
            model_name='companybankrouting',
            name='unique_company_special_routing',
        ),
        migrations.AddField(
            model_name='companybankrouting',
            name='operation',
            field=models.CharField(choices=[('collection', 'Cobrament (remesa)'), ('transfer', 'Transferència (retorn)')], default='collection', max_length=16),
        ),
        migrations.AddConstraint(
            model_name='companybankrouting',
            constraint=models.UniqueConstraint(condition=models.Q(('match_type', 'payer_bank')), fields=('company', 'operation', 'bank'), name='unique_company_payer_bank_routing'),
        ),
        migrations.AddConstraint(
            model_name='companybankrouting',
            constraint=models.UniqueConstraint(condition=models.Q(('match_type', 'payer_bank'), _negated=True), fields=('company', 'operation', 'match_type'), name='unique_company_special_routing'),
        ),
    ]
