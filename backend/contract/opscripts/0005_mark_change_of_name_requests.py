from contract.models import ContractTerminationType
from coredata.models import ConfigProject


def run():
    # El tipus de baixa per canvi de titular és el que l'aplicació fa servir en donar de baixa
    # el contracte anterior d'una sol·licitud: les sol·licituds vinculades són canvis de nom
    config = ConfigProject.objects.filter(token='termination_type_holder_change').first()
    termination_type = ContractTerminationType.objects.filter(token=config.value).first() if config and config.value else None
    if termination_type is None:
        print("No termination type for holder change configured")
        return

    if not termination_type.is_change_of_name:
        termination_type.is_change_of_name = True
        termination_type.save(update_fields=['is_change_of_name'])
    updated = termination_type.mark_linked_requests_as_change_of_name()
    print(f"Contract requests marked as change of name: {updated}")
