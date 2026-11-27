import django.db.models.deletion
from django.db import migrations, models


# Text que deixava el procés de facturació a l'historial de la factura quan no la domiciliava
# perquè el contracte tenia factures pendents de cobrar (paràmetre `block_remittance_if_unpaid`).
# No té traduccions: sempre s'ha desat així.
REMITTANCE_BLOCKED_OBSERVATION = "No es domicilia: el contracte té factures pendents de cobrar"


def mark_remittance_blocked_logs(apps, schema_editor):
    """Les factures que ja s'havien deixat de domiciliar també han de mostrar l'avís."""
    LogInvoiceDataChange = apps.get_model('logger', 'LogInvoiceDataChange')
    LogInvoiceDataChange.objects.filter(
        observation=REMITTANCE_BLOCKED_OBSERVATION, auto_reason__isnull=True,
    ).update(auto_reason='remittance_blocked_unpaid')


class Migration(migrations.Migration):

    dependencies = [
        ('billing', '0354_insolvency_process_debt_management'),
        ('logger', '0055_logincidentchange'),
    ]

    operations = [
        migrations.AddField(
            model_name='loginvoicedatachange',
            name='auto_reason',
            field=models.CharField(blank=True, choices=[('invalid_account_return', 'Retorn SEPA per compte invàlid'), ('remittance_blocked_unpaid', 'No es domicilia: factures pendents de cobrar')], max_length=50, null=True),
        ),
        migrations.AddField(
            model_name='loginvoicedatachange',
            name='reject_motive',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='invoice_data_changes', to='billing.rejectmotive'),
        ),
        migrations.RunPython(mark_remittance_blocked_logs, migrations.RunPython.noop),
    ]
