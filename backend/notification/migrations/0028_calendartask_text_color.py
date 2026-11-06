from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('notification', '0027_incident_sac_data'),
    ]

    operations = [
        migrations.AddField(
            model_name='calendartask',
            name='text_color',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='calendartaskrecurrence',
            name='text_color',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
    ]
