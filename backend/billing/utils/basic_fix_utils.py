from django.db.models.functions import Length
from billing.models import CommitmentDeposit, Invoice, Payment, PaymentStatus
from communication.models import Communication
from coredata.models import ConfigProject


def cancel_payments_in_cancelled_commitments(apps, schema_editor):
    # Models històrics (no els actuals): si no, en una BD nova la consulta inclou
    # columnes afegides per migracions posteriors (p. ex. CommitmentDeposit.start_date).
    CommitmentDeposit = apps.get_model('billing', 'CommitmentDeposit')
    Payment = apps.get_model('billing', 'Payment')
    PaymentStatus = apps.get_model('billing', 'PaymentStatus')
    ConfigProject = apps.get_model('coredata', 'ConfigProject')
    try:
        cancelled_commitment_status_token = ConfigProject.objects.get(token='commitment_deposit_status_cancelled_token').value
        payment_paid_status_token = ConfigProject.objects.get(token='payment_status_paid_token').value
        payment_cancelled_status = PaymentStatus.objects.get(token=ConfigProject.objects.get(token='payment_status_cancelled_token').value)
    except (ConfigProject.DoesNotExist, PaymentStatus.DoesNotExist):
        return
    
    commitment_deposits = CommitmentDeposit.objects.filter(status__token=cancelled_commitment_status_token)
    commitment_payments = Payment.objects.filter(
        commitment_deposit__in=commitment_deposits).exclude(
            status__token=payment_paid_status_token).distinct()
    for payment in commitment_payments:
        payment.status = payment_cancelled_status
        payment.save()


def fix_commitment_deposit_tokens(apps, schema_editor):
    CommitmentDeposit = apps.get_model('billing', 'CommitmentDeposit')
    commitment_deposits = CommitmentDeposit.objects.annotate(token_length=Length('token')).filter(token_length=11)
    for commitment in commitment_deposits:
        commitment.token = f"03{commitment.token[4:]}"
        commitment.save()


def fix_communications_no_use_type():
    try:
        from communication.models import CommunicationUseType
        communication_use_type = CommunicationUseType.objects.get(is_default=True)
    except:
        print("COMMUNICATION USE TYPE MISSING")
        return
    
    communications = Communication.objects.filter(use_type__isnull=True)
    communications.update(use_type=communication_use_type)
    
    print(f"FIXED {communications.count()} COMMUNICATIONS")


def fix_invoices_persons():
    # UPDATE INVOICES IN BATCHES MOVED TO TASK
    from billing.tasks import fix_invoices_persons_task
    fix_invoices_persons_task.delay()