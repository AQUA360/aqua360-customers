from django.db import migrations

def create_confirmed_status(apps, schema_editor):
    try:
        PaymentCommitmentStatus = apps.get_model('billing', 'PaymentCommitmentStatus')
        ConfigProject = apps.get_model('coredata', 'ConfigProject')
    except LookupError:
        # If models have been renamed/deleted in future migrations
        return
    
    # Create the status record for PaymentCommitment (Confirmed)
    # Token 3, Name Confirmat, Position 6
    PaymentCommitmentStatus.objects.get_or_create(
        token='3',
        defaults={
            'name': 'Confirmat',
            'position': 6,
            'description': 'Compromís de pagament confirmat i a l’espera de liquidar-se',
            'color': 'blue'
        }
    )
    
    # Create the config project record
    ConfigProject.objects.get_or_create(
        token='payment_commitment_status_confirmed_token',
        defaults={
            'value': '3',
            'name': 'Payment Commitment Status Confirmed Token',
        }
    )

def remove_confirmed_status(apps, schema_editor):
    try:
        PaymentCommitmentStatus = apps.get_model('billing', 'PaymentCommitmentStatus')
        ConfigProject = apps.get_model('coredata', 'ConfigProject')
        
        PaymentCommitmentStatus.objects.filter(token='3').delete()
        ConfigProject.objects.filter(token='payment_commitment_status_confirmed_token').delete()
    except LookupError:
        pass

class Migration(migrations.Migration):
    dependencies = [
        ('billing', '0267_paymentremittance_task_id'),
        ('coredata', '0001_initial'), # Minimum dependency for ConfigProject
    ]

    operations = [
        migrations.RunPython(create_confirmed_status, remove_confirmed_status),
    ]
