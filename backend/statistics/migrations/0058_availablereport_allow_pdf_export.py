from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('statistics', '0057_merge_20261112_0844'),
    ]

    operations = [
        migrations.AddField(
            model_name='availablereport',
            name='allow_pdf_export',
            field=models.BooleanField(default=False, help_text="Si està actiu, el front-end mostra un botó per descarregar l'informe en PDF a més de l'Excel.", verbose_name='Permet descarregar en PDF'),
        ),
    ]
