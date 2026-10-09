from django.db import migrations, models


def sync_attach_to_letter(apps, schema_editor):
    """Els documents ja creats amb `attach_to_email=False` venien d'un
    `attach_claim_documents=False`, que aleshores nomes podia expressar-se sobre el
    correu. Han de quedar igualment fora del paquet postal."""
    CommunicationFile = apps.get_model('communication', 'CommunicationFile')
    CommunicationFile.objects.filter(attach_to_email=False).update(attach_to_letter=False)


class Migration(migrations.Migration):

    dependencies = [
        ('communication', '0030_add_returned_status'),
    ]

    operations = [
        migrations.AddField(
            model_name='communicationfile',
            name='attach_to_letter',
            field=models.BooleanField(default=True),
        ),
        migrations.RunPython(sync_attach_to_letter, migrations.RunPython.noop),
    ]
