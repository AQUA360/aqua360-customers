from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('service', '0135_company_contact_texts'),
    ]

    operations = [
        migrations.CreateModel(
            name='MeterCommTechnology',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, null=True)),
                ('name', models.CharField(blank=True, max_length=255, null=True)),
            ],
        ),
    ]
