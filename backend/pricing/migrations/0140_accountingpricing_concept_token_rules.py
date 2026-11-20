from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('pricing', '0139_accounting_declared_as_return'),
    ]

    operations = [
        migrations.AddField(
            model_name='accountingpricing',
            name='concept_token_rules',
            field=models.JSONField(blank=True, default=list),
        ),
    ]
