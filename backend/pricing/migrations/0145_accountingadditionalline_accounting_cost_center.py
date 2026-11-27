from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('pricing', '0144_accountingpricing_separate_by_sign'),
    ]

    operations = [
        migrations.AddField(
            model_name='accountingadditionalline',
            name='accounting_cost_center',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='additional_lines',
                to='pricing.accountingcostcenter',
            ),
        ),
    ]
