from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('pricing', '0128_remove_accountingpricing_is_additional_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='accountingpricing',
            name='payment_origin',
            field=models.CharField(
                blank=True,
                choices=[('box_office', 'Box Office'), ('post_office', 'Post Office')],
                max_length=20,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name='accountingpricing',
            name='separate_by_payment_origin',
            field=models.BooleanField(default=False),
        ),
    ]
