from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('coredata', '0158_mainpermission_change_requires_superuser'),
    ]

    operations = [
        migrations.AddField(
            model_name='personbank',
            name='origin',
            field=models.CharField(
                choices=[('OV', 'Oficina Virtual'), ('MANUAL', 'Manual'), ('HIST', 'Històric')],
                default='HIST',
                max_length=10,
            ),
        ),
    ]
