import datetime
from django.db.models.signals import post_save
from django.dispatch import receiver
from claimrequest.serializers.claim_request_save_serializer import add_working_days
from contract.models import Contract
from .models import ClaimRequest, ClaimRequestPayment
from coredata.models import ConfigProject
from .utils.claim_request_template_service import create_claim_request_steps_from_template

@receiver(post_save, sender=ClaimRequest)
def create_claim_request_steps(sender, instance, created, **kwargs):
    """
    Signal que s'executa després de guardar una reclamació.
    Si la reclamació té un template assignat:
    - Si no té passos, crea els passos corresponents
    - Si té passos i ha canviat de template, elimina els passos anteriors i crea els nous
    """
    if instance.template:
        # Si ha canviat de template o no té passos
        if not instance.steps.exists() or instance.steps.first().step_template.template != instance.template:
            # Eliminem els passos existents si n'hi ha
            instance.steps.all().delete()
            # Creem els nous passos
            create_claim_request_steps_from_template(instance, instance.template)
            #get today
            today = datetime.datetime.now()
            day_type = instance.current_step.duration_type
            if day_type == 'WORK':
                due_date = add_working_days(today, instance.current_step.duration or 0)
            else:
                due_date = today + datetime.timedelta(days=instance.current_step.duration or 0)
            instance.due_date = due_date.date()
            instance.save()
