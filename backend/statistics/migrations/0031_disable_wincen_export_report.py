from django.db import migrations


def disable_wincen_report(apps, schema_editor):
    AvailableReport = apps.get_model('statistics', 'AvailableReport')
    AvailableReport.objects.filter(function_name='wincen_export_report').update(is_active=False)


def enable_wincen_report(apps, schema_editor):
    AvailableReport = apps.get_model('statistics', 'AvailableReport')
    AvailableReport.objects.filter(function_name='wincen_export_report').update(is_active=True)


class Migration(migrations.Migration):

    dependencies = [
        ('statistics', '0030_add_wincen_export_report'),
    ]

    operations = [
        migrations.RunPython(disable_wincen_report, enable_wincen_report),
    ]
