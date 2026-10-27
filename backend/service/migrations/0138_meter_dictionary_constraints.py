from django.db import migrations, models
from django.db.models.functions import Upper


class Migration(migrations.Migration):

    dependencies = [
        ('service', '0137_meter_dictionary_uniqueness'),
    ]

    operations = [
        migrations.AddConstraint(
            model_name='metermanufacturer',
            constraint=models.UniqueConstraint(Upper('name'), name='meter_manufacturer_name_ci_unique'),
        ),
        migrations.AddConstraint(
            model_name='metermodel',
            constraint=models.UniqueConstraint(Upper('name'), 'manufacturer', name='meter_model_name_manufacturer_ci_unique'),
        ),
        migrations.AddConstraint(
            model_name='metermodel',
            constraint=models.UniqueConstraint(
                Upper('name'),
                condition=models.Q(manufacturer__isnull=True),
                name='meter_model_name_no_manufacturer_ci_unique',
            ),
        ),
        migrations.AddConstraint(
            model_name='metercommtechnology',
            constraint=models.UniqueConstraint(Upper('name'), name='meter_comm_technology_name_ci_unique'),
        ),
    ]
