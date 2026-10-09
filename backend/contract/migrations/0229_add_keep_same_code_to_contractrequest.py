from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('contract', '0228_add_is_change_of_name_to_contractrequest'),
    ]

    operations = [
        migrations.AddField(
            model_name='contractrequest',
            name='keep_same_code',
            field=models.BooleanField(default=False, verbose_name='Keep Same Code'),
        ),
    ]
