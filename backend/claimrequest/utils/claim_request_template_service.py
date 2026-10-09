from django.db import transaction
from ..models import ClaimRequest, ClaimRequestStep, ClaimRequestStepTemplate, ClaimRequestTemplate
from django.utils import timezone
import datetime

def create_claim_request_steps_from_template(claim_request: ClaimRequest, template: ClaimRequestTemplate, current_position: int = 0):
    """
    Crea els passos d'una reclamació a partir d'un template.
    
    Args:
        claim_request (ClaimRequest): La reclamació per la qual crear els passos
        template (ClaimRequestTemplate): El template a partir del qual crear els passos
    
    Returns:
        list: Llista de passos creats
    """
    with transaction.atomic():
        # Obtenim tots els passos del template ordenats per posició
        step_templates = ClaimRequestStepTemplate.objects.filter(
            template=template
        ).order_by('position')
        
        created_steps = []
        previous_step = None
        
        if current_position > 0:
            step_templates = step_templates.filter(position__gte=current_position).distinct()
        
        for step_template in step_templates:
            # Creem el pas copiant tots els camps del template
            step = ClaimRequestStep.objects.create(
                claim_request=claim_request,
                step_template=step_template,
                token=step_template.token,
                name=step_template.name,
                description=step_template.description,
                position=step_template.position,
                duration=step_template.duration,
                duration_type=step_template.duration_type,
                document_type=step_template.document_type,
                order_type=step_template.order_type
            )
            
            # Si hi ha un pas anterior, l'establim com a next_step
            if previous_step:
                previous_step.next_step = step
                previous_step.save()
            
            if step_template.price_rates.count() > 0:
                step.price_rates.set(step_template.price_rates.all())
                step.save()
            
            created_steps.append(step)
            
            # Si és el primer pas, l'establim com a pas actual
            if not previous_step:
                claim_request.current_step = step
                claim_request.save()
            
            previous_step = step
        
        return created_steps 