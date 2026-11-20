from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('pricing', '0140_accountingpricing_concept_token_rules'),
    ]

    operations = [
        migrations.AddField(
            model_name='accountingpricing',
            name='covers_undeclared',
            field=models.BooleanField(default=False),
        ),
    ]
