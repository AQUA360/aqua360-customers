from django.db import migrations


def add_incident_compliance_report(apps, schema_editor):
    AvailableReport = apps.get_model('statistics', 'AvailableReport')
    ReportType = apps.get_model('statistics', 'ReportType')

    # Mateixa secció que l'informe de temps de resposta a reclamacions
    claim_report = AvailableReport.objects.filter(function_name='claim_response_time_report').first()
    section = claim_report.section if claim_report else ReportType.objects.filter(token='statistics').first()

    AvailableReport.objects.get_or_create(
        function_name='incident_compliance_report',
        defaults={
            'name': "Compliment del servei d'atenció",
            'description': (
                "Incidències per tipus i canal: compliment de terminis, temps de primera resposta i de "
                "resolució en dies hàbils, reobertures i indicadors d'atenció telefònica."
            ),
            'is_active': True,
            'section': section,
            'download_button_name': 'Descarregar Excel',
            'has_custom_config': False,
            'required_fields': ['date_range', 'exploitation_id'],
            'position': 7,
        }
    )


def remove_incident_compliance_report(apps, schema_editor):
    AvailableReport = apps.get_model('statistics', 'AvailableReport')
    AvailableReport.objects.filter(function_name='incident_compliance_report').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('statistics', '0049_dailydocument_no_data_found'),
    ]

    operations = [
        migrations.RunPython(add_incident_compliance_report, remove_incident_compliance_report),
    ]
