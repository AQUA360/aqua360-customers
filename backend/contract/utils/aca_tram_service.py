"""Ampliació de trams de l'ACA (bonificació configurada a `ConfigProject.aca_at_token`).

`Contract.total_persons` és la font de veritat del nombre de persones; la `Variable`
configurada a `ConfigProject.aca_tram_members_variable_token` (per defecte
`ACA-TRAM-MEMBRES`) de la `Bonification` n'és el reflex que s'envia a l'ACA. Aquest
servei manté les dues coses sincronitzades i aplica el mínim de persones
(`watchdog.aca_config.aca_tram_min_persons`).

Tot plegat només s'aplica als projectes amb l'ACA activa (`uses_aca`): fora de
Catalunya no hi ha ampliació de trams.
"""
from django.utils import timezone

from coredata.models import ConfigProject
from coredata.utils.name_utils import generate_token

from ..models import ACABonificationRequest, Bonification, BonificationType, Variable


def get_aca_tram_bonification_type():
    """BonificationType d'ampliació de trams ACA, segons `ConfigProject.aca_at_token`."""
    config = ConfigProject.objects.filter(token='aca_at_token').first()
    if not config or not config.value:
        return None
    return BonificationType.objects.filter(token__icontains=config.value).order_by('id').first()


def is_members_variable_type(variable_type):
    from watchdog.aca_config import is_aca_tram_members_variable_type
    return is_aca_tram_members_variable_type(variable_type)


def members_variable_type(bonification_type):
    """`VariableType` de persones d'aquest tipus de bonificació, segons la configuració."""
    if not bonification_type:
        return None
    for variable_type in bonification_type.variable_types.all():
        if is_members_variable_type(variable_type):
            return variable_type
    return None


def get_active_aca_tram_bonification(contract, bonification_type):
    return Bonification.objects.filter(
        contract=contract, bonification_type=bonification_type, is_active=True
    ).order_by('-id').first()


def aca_tram_min_persons_for_contract(contract):
    """Mínim de persones si el contracte té la bonificació d'ampliació de trams activa
    (per sota, `sync_aca_tram_with_total_persons` la desactivarà); None en cas contrari."""
    from watchdog.aca_config import aca_tram_min_persons, uses_aca_enabled

    if not uses_aca_enabled():
        return None
    bonification_type = get_aca_tram_bonification_type()
    if not bonification_type or not get_active_aca_tram_bonification(contract, bonification_type):
        return None
    return aca_tram_min_persons()


def aca_tram_members_error(variable_type, value):
    """Missatge d'error si `value` no arriba al mínim de persones per a la variable de
    membres de l'ampliació de trams; None si és vàlid o la variable no hi té res a veure."""
    from watchdog.aca_config import aca_tram_min_persons, uses_aca_enabled

    if not is_members_variable_type(variable_type) or not uses_aca_enabled():
        return None
    bonification_type = get_aca_tram_bonification_type()
    if not bonification_type or not bonification_type.variable_types.filter(pk=variable_type.pk).exists():
        return None

    min_persons = aca_tram_min_persons()
    try:
        num_persons = int(value)
    except (TypeError, ValueError):
        return f"El nombre de membres ha de ser un enter (mínim {min_persons})."
    if num_persons < min_persons:
        return (
            f"L'ampliació de trams de l'ACA només s'aplica a habitatges de {min_persons} "
            f"o més persones (s'han indicat {num_persons})."
        )
    return None


def update_aca_tram_members(bonification, total_persons, notification_enabled):
    """El contracte ja té una Bonification ACA-TRAM activa: actualitza el valor de la
    seva Variable de membres en lloc de crear-ne una de nova (i una altra
    ACABonificationRequest duplicada) cada cop que canvia `total_persons`.

    Si l'enviament de notificacions ACA està activat (`aca_notification_enabled`), la
    sol·licitud (ja enviada o no) torna a quedar pendent d'enviar amb el nou valor —
    l'ACA necessita rebre l'ampliació de trams actualitzada, no la primera que es va
    enviar."""
    variable_type = members_variable_type(bonification.bonification_type)
    if not variable_type:
        return

    variable, variable_created = Variable.objects.get_or_create(
        bonification=bonification, type=variable_type,
        defaults={
            'contract': bonification.contract,
            'value': str(total_persons),
            'name': variable_type.name,
            'token': generate_token(Variable),
        },
    )
    if not variable_created:
        if variable.value == str(total_persons):
            return
        variable.value = str(total_persons)
        variable.save()

    if not notification_enabled:
        return

    aca_request, _ = ACABonificationRequest.objects.get_or_create(bonification=bonification)
    aca_request.num_persons_to_apply = total_persons
    aca_request.sent_at = None
    aca_request.aca_document = None
    aca_request.save()


def create_aca_tram_bonification(contract, bonification_type):
    """Crea la `Bonification` "Ampliació de trams" i una `Variable` per cada
    `VariableType` del tipus (la booleana "Amplicació de tram (ACA)" i la de membres,
    amb `total_persons`), mateix comportament que `AddBonification.vue`
    (`VariableSaveSerializer.create` fixa "True" per als tipus booleans).
    `track_aca_bonification_request`/`sync_aca_bonification_num_persons`
    (`contract/signals.py`) en generen la corresponent `ACABonificationRequest` pendent."""
    variable_types = list(bonification_type.variable_types.all())
    if not variable_types:
        return None

    bonification = Bonification.objects.create(
        person=contract.holder,
        contract=contract,
        bonification_type=bonification_type,
        requested_at=timezone.now(),
        is_active=True,
        token=generate_token(Bonification),
    )
    for variable_type in variable_types:
        if variable_type.data_type == 'bool':
            value = 'True'
        elif is_members_variable_type(variable_type):
            value = str(contract.total_persons)
        else:
            continue
        Variable.objects.create(
            contract=contract,
            bonification=bonification,
            type=variable_type,
            value=value,
            name=variable_type.name,
            token=generate_token(Variable),
        )
    return bonification


def deactivate_aca_tram_bonification(bonification):
    """El contracte ja no arriba al mínim de persones: es dona de baixa la bonificació.
    `deactivate_bonification` (`contract/signals.py`) en desactiva les variables i ho
    deixa al log. La sol·licitud ACA encara no enviada s'esborra aquí: aquell mateix
    senyal marca la instància amb `_skip_signal` i `track_aca_bonification_request` ja
    no hi arriba."""
    bonification.is_active = False
    if not bonification.end_at:
        bonification.end_at = timezone.now().date()
    bonification.save()
    ACABonificationRequest.objects.filter(bonification=bonification, sent_at__isnull=True).delete()


def sync_aca_tram_with_total_persons(contract, old_total_persons):
    """Ha canviat `total_persons` del contracte: ajusta la bonificació d'ampliació de trams.

    - Per sota del mínim: es desactiva la bonificació activa, si n'hi ha.
    - Amb bonificació activa: s'actualitza el nombre de membres.
    - Sense bonificació, només si les persones augmenten i arriben al mínim: es crea."""
    from watchdog.aca_config import aca_notification_enabled, aca_tram_min_persons, uses_aca_enabled

    new_total_persons = contract.total_persons
    if old_total_persons is None or new_total_persons is None or new_total_persons == old_total_persons:
        return
    if not uses_aca_enabled():
        return

    bonification_type = get_aca_tram_bonification_type()
    if not bonification_type:
        return

    bonification = get_active_aca_tram_bonification(contract, bonification_type)
    if new_total_persons < aca_tram_min_persons():
        if bonification:
            deactivate_aca_tram_bonification(bonification)
        return

    if bonification:
        update_aca_tram_members(bonification, new_total_persons, aca_notification_enabled())
    elif new_total_persons > old_total_persons:
        create_aca_tram_bonification(contract, bonification_type)
