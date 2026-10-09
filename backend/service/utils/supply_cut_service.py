from django.db.models import Q
from django.utils import timezone

from coredata.models import ConfigProject
from logger.models import LogSupplyPointChange

from ..models import SupplyCut, SupplyPointStatus


# Tokens CANÒNICS del catàleg d'estats de tall (migració 0126). El catàleg és
# fix: 0=Planificat, 1=Actiu, 2=Acabat, 3=Cancel·lat, 5=Conflicte
# (requires_review). «Acabat» és l'estat de tancament per defecte de les
# tasques/vistes; «Planificat» el de naixement dels talls manuals.
PLANNED_STATUS_TOKEN = '0'
ACTIVE_STATUS_TOKEN = '1'
FINISHED_STATUS_TOKEN = '2'
CANCELLED_STATUS_TOKEN = '3'
CONFLICTE_STATUS_TOKEN = '5'

# Transicions PERMESES entre estats (token origen -> tokens destí). És l'única
# font de veritat: els valida el serializer, les accions start/finish i els
# tests. «Conflicte» NO es pot triar manualment (ni sortir-ne): és una
# sentinella que es resol amb resolve-review. La sync de Giswater assigna
# estats directament segons l'estado sense passar per aquesta màquina, i un
# tall mai registra «Acabat» si no ha passat per «Actiu» (un pla cancel·lat
# és «Cancel·lat»).
ALLOWED_TRANSITIONS = {
    PLANNED_STATUS_TOKEN: {ACTIVE_STATUS_TOKEN, CANCELLED_STATUS_TOKEN},
    ACTIVE_STATUS_TOKEN: {FINISHED_STATUS_TOKEN, CANCELLED_STATUS_TOKEN},
    FINISHED_STATUS_TOKEN: set(),
    CANCELLED_STATUS_TOKEN: set(),
    CONFLICTE_STATUS_TOKEN: set(),
}


def validate_transition(from_token, to_token):
    """Verdader si la transició d'estat és permesa (token antic -> token nou)."""
    if from_token == to_token:
        return True
    allowed = ALLOWED_TRANSITIONS.get(from_token)
    return allowed is not None and to_token in allowed


def is_temporary_cause(supply_cut):
    """El tall és PUNTUAL (previst amb dates o accidental): no altera l'estat
    del punt de subministrament ni genera avís. Fals = tall indefinit."""
    return bool(supply_cut.cause and supply_cut.cause.is_temporary)


def affects_sp_status(supply_cut):
    """Verdader NOMÉS quan el tall manté el PP tallat: ACTIU, indefinit i fora
    de quarantena. Els temporals i els que estan en revisió mai toquen els PP."""
    if supply_cut.requires_review or is_temporary_cause(supply_cut):
        return False
    return bool(supply_cut.status and supply_cut.status.token == ACTIVE_STATUS_TOKEN)


def effective_start(supply_cut):
    """Inici efectiu del tall per a durades/mètriques: exec_start real, o la
    previsió (date_start), o bé la creació/notificació del tall (created_at).
    Tot tall acabat té una durada mesurable per construcció."""
    return supply_cut.exec_start or supply_cut.date_start or supply_cut.created_at


def planned_cut_is_stale(supply_cut):
    """Un tall Planificat és OBSOLET quan la seva fi PREVISTA (forecast end,
    `date_end`) ja ha passat sense que el tall s'hagi arribat a activar. Cap
    altra data (inici previst o execució real) el fa obsolet."""
    if not supply_cut.date_end:
        return True # Si no té data de fi, caduca directament
    return supply_cut.date_end < timezone.now()


def _open_cut_affecting_sp(supply_point):
    """Talls oberts que MANTENEN el PP tallat: ACTIU, indefinit i sense
    quarantena. Un tall temporal o en conflicte no té cap efecte sobre el PP."""
    return supply_point.supply_cuts.filter(
        is_active=True,
        requires_review=False,
        status__token=ACTIVE_STATUS_TOKEN,
        cause__is_temporary=False,
    )


def _supply_point_status(config_token):
    value = ConfigProject.objects.get(token=config_token).value
    return SupplyPointStatus.objects.get(token=value)


def closed_status_token():
    """Token of the cut status meaning "finished" (`Acabat`, 2).

    The canonical status assigned when a cut is auto-closed (done cuts, cuts
    left without supply points). The old `supply_cut_status_innactive_token`
    config row no longer exists; the terminal family is {2, 3}.
    """
    return FINISHED_STATUS_TOKEN


def closed_status_tokens():
    """Tokens treated as "closed/finished" (`supply_cut_status_closed_tokens`, comma list).

    The terminal family is {2, 3} (Acabat, Cancel·lat). Falling back to the
    single finished token keeps the old behavior on environments where the
    config row does not exist yet.
    """
    config = ConfigProject.objects.filter(token='supply_cut_status_closed_tokens').first()
    if config is None:
        return {closed_status_token()}
    value = config.value
    return {token.strip() for token in value.split(',') if token.strip()}


def is_supply_cut_closed(supply_cut):
    if not supply_cut.is_active:
        return True
    return bool(supply_cut.status and supply_cut.status.token in closed_status_tokens())


def _log_status_change(supply_point, new_status, action, user=None, observation=None):
    LogSupplyPointChange.objects.create(
        supply_point=supply_point,
        user=user,
        action=action,
        field_changed='status',
        previous_value=supply_point.status.name if supply_point.status else None,
        current_value=new_status.name,
        previous_related_id=supply_point.status_id,
        current_related_id=new_status.id,
        observation=observation,
    )


def _apply_status(supply_point, new_status, action, user=None, observation=None):
    if supply_point.status_id == new_status.id:
        return False
    _log_status_change(supply_point, new_status, action, user, observation)
    supply_point.status = new_status
    supply_point.save()
    return True


def cut_supply_points(supply_cut_id, user=None, observation=None):
    """Marks all supply points of the cut as cut.

    No-op for PUNTUAL/temporal cuts (never alter the supply point status) and
    for cuts in quarantine (requires_review): they are resolved and then
    started manually.
    """
    supply_cut = SupplyCut.objects.filter(id=supply_cut_id).first()
    if not supply_cut:
        return 0
    if is_temporary_cause(supply_cut) or supply_cut.requires_review:
        return 0

    cut_status = _supply_point_status('supply_point_status_cut_token')
    changed = 0
    for supply_point in supply_cut.supply_points.all():
        if _apply_status(supply_point, cut_status, 'deactivate', user, observation):
            changed += 1
    return changed


def restore_supply_point(supply_point, ignore_cut_id=None, user=None, observation=None):
    """Restores a supply point to the active state.

    Does nothing if the point still belongs to another open INDEFINITE ACTIVE
    cut: the same point can sit in more than one cut and removing it from one
    must not restore supply that another one keeps cut. Temporary cuts and
    quarantined ones never hold a point cut, so they do not block the restore.
    `ignore_cut_id` is the cut being closed or removed from, so it does not
    count.
    """
    other_open_cuts = _open_cut_affecting_sp(supply_point)
    if ignore_cut_id:
        other_open_cuts = other_open_cuts.exclude(id=ignore_cut_id)
    if other_open_cuts.exists():
        return False

    active_status = _supply_point_status('supply_point_status_activate_token')
    return _apply_status(supply_point, active_status, 'activate', user, observation)


def restore_supply_points(supply_cut_id, supply_points=None, user=None, observation=None):
    """Restores the supply points of a cut being closed to the active state.

    With `supply_points` the restoration can be limited to a subset (e.g. the
    points just removed from the cut and no longer present in it).
    """
    supply_cut = SupplyCut.objects.filter(id=supply_cut_id).first()
    if not supply_cut:
        return 0

    if supply_points is None:
        supply_points = supply_cut.supply_points.all()

    changed = 0
    for supply_point in supply_points:
        if restore_supply_point(supply_point, supply_cut.id, user, observation):
            changed += 1
    return changed


def remove_supply_points_from_cut(supply_cut, supply_point_ids, user=None, observation=None):
    """Removes supply points from a cut and restores them.

    This is how a cut stops affecting a single contract without closing the
    whole cut: the contract hangs off the supply point, and it is the supply
    point status that marks it as cut.
    """
    supply_points = list(supply_cut.supply_points.filter(id__in=supply_point_ids))
    if not supply_points:
        return 0

    supply_cut.supply_points.remove(*supply_points)
    return restore_supply_points(
        supply_cut.id, supply_points=supply_points, user=user, observation=observation
    )


def close_supply_cut(supply_cut, user=None, observation=None):
    """Closes the cut: sets the end date if missing and reactivates the affected points.

    `date_end` is the forecast: it is only filled when empty, so a Giswater
    `forecast_end` is not overwritten. `exec_end` is the real execution and is
    set whenever none is present yet.
    """
    now = timezone.now()
    update_fields = []
    if not supply_cut.date_end:
        supply_cut.date_end = now
        update_fields.append('date_end')
    if not supply_cut.exec_end:
        supply_cut.exec_end = now
        update_fields.append('exec_end')
    if update_fields:
        update_fields.append('updated_at')
        supply_cut.save(update_fields=update_fields)
    return restore_supply_points(supply_cut.id, user=user, observation=observation)


def supply_cuts_due_to_activate(as_of=None):
    """Cuts that should already be active: Giswater by `exec_start`, manual ones by `date_start`."""
    as_of = as_of or timezone.now().date()
    closed_tokens = closed_status_tokens()
    active_token = ConfigProject.objects.get(token='supply_cut_status_active_token').value
    return (
        SupplyCut.objects
        .filter(is_active=True)
        .filter(
            Q(source=SupplyCut.SOURCE_GISWATER, exec_start__date__lte=as_of)
            | Q(source=SupplyCut.SOURCE_MANUAL, date_start__date__lte=as_of)
        )
        .exclude(status__token__in=[active_token, *closed_tokens]).exclude(requires_review=True)
    )


def supply_cuts_due_to_deactivate(as_of=None):
    """Cuts that should already be closed: Giswater by `exec_end`, manual ones by `date_end`."""
    as_of = as_of or timezone.now().date()
    closed_tokens = closed_status_tokens()
    return (
        SupplyCut.objects
        .filter(is_active=True)
        .filter(
            Q(source=SupplyCut.SOURCE_GISWATER, exec_end__date__lt=as_of)
            | Q(source=SupplyCut.SOURCE_MANUAL, date_end__date__lt=as_of)
        )
        .exclude(status__token__in=closed_tokens).exclude(requires_review=True)
    )


def sync_supply_points_status(supply_cut, previous_status=None, previous_temporary=None, *, user=None, observation=None):
    """Propaga el canvi d'estat d'un tall als seus punts (state-driven).

    És l'única font de veritat per propagació, reutilitzada pel serializer,
    per l'acció de resolució de conflictes i per les accions start/finish:
    entrar a ACTIU talla els PP (si és indefinit); entrar a un estat terminal
    els restaura (amb dates d'execució només si abans era Actiu). Conflicte és
    inert. La decidida de si el tall toca els PP es delega a les funcions
    gated (temporal/quarantena mai).

    `previous_temporary` desactiva el retorn precoç quan SOLS el motiu canvia:
    un tall ACTIU que passa de puntual a indefinit comença a mantenir els PP
    tallats (i a l'inrevés els deixa de mantenir), sense canviar d'estat.
    """
    new_status = supply_cut.status
    new_temporary = is_temporary_cause(supply_cut)

    if previous_status == new_status:
        # Sols el motiu ha canviat: només importa si el tall continua ACTIU
        # (els estats Planificat/terminal/Conflicte mai toquen els PP).
        prev_tok = previous_status.token if previous_status else None
        new_tok = new_status.token if new_status else None
        if (
            prev_tok == new_tok == ACTIVE_STATUS_TOKEN
            and previous_temporary is not None
            and new_temporary != previous_temporary
        ):
            if new_temporary:
                # Indefinit -> puntual: el tall deixa de mantenir el PP tallat.
                restore_supply_points(supply_cut.id, user=user, observation=observation)
            else:
                # Puntual -> indefinit: ara és un tall ACTIU indefinit: talla.
                cut_supply_points(supply_cut.id, user=user, observation=observation)
        return

    new_token = new_status.token if new_status else None
    prev_token = previous_status.token if previous_status else None

    if new_token == ACTIVE_STATUS_TOKEN:
        cut_supply_points(supply_cut.id, user=user, observation=observation)
    elif new_token in closed_status_tokens():
        if prev_token == ACTIVE_STATUS_TOKEN:
            # Un tall executat que tanca: dates de fi + restauració.
            close_supply_cut(supply_cut, user=user, observation=observation)
        else:
            # Cancel·lat/acabat sense haver estat mai Actiu: només es
            # restauren punts (no-op si mai s'havien tallat), sense marcar
            # dates d'execució.
            restore_supply_points(supply_cut.id, user=user, observation=observation)
    # Conflicte (5): inert, mai toca els PP.


def stamp_exec_start(supply_cut, when=None):
    """Stamps the real start if none is present yet (manual cuts when activated)."""
    if supply_cut.exec_start:
        return False
    supply_cut.exec_start = when or timezone.now()
    supply_cut.save(update_fields=['exec_start', 'updated_at'])
    return True


def stamp_exec_end(supply_cut, when=None):
    """Stamps the real end if none is present yet (manual cuts when closed)."""
    if supply_cut.exec_end:
        return False
    supply_cut.exec_end = when or timezone.now()
    supply_cut.save(update_fields=['exec_end', 'updated_at'])
    return True


def _cut_status(token):
    from ..models import SupplyCutStatus
    return SupplyCutStatus.objects.get(token=token)


def start_cut(supply_cut, user=None, observation=None):
    """Converteix un tall PLANIFICAT en ACTIU: stampa l'execució real i talla
    els PP si el tall altera el seu estat (indefinit; els temporals no).

    És l'única via legítima d'entrar a Actiu des d'un pla. Qualsevol altre
    estat d'origen (terminal, Conflicte) es rebutja.
    """
    if supply_cut.status is None or supply_cut.status.token != PLANNED_STATUS_TOKEN:
        raise ValueError("Només un tall Planificat es pot iniciar.")

    supply_cut.status = _cut_status(ACTIVE_STATUS_TOKEN)
    supply_cut.save(update_fields=['status', 'updated_at'])
    stamp_exec_start(supply_cut)
    cut_supply_points(supply_cut.id, user=user, observation=observation)
    return supply_cut


def finish_cut(supply_cut, user=None, observation=None):
    """Acaba un tall ACTIU: passa a Acabat, stampa la fi real i restaura els PP.

    Un tall que mai ha estat Actiu NO es registra com a Acabat (esbiaixaria
    mètriques d'execució): un pla es CANCEL·LA (Planificat -> Cancel·lat), no
    s'acaba.
    """
    if supply_cut.status is None or supply_cut.status.token != ACTIVE_STATUS_TOKEN:
        raise ValueError("Només un tall Actiu es pot finalitzar; els plans es cancel·len.")

    supply_cut.status = _cut_status(FINISHED_STATUS_TOKEN)
    supply_cut.save(update_fields=['status', 'updated_at'])
    close_supply_cut(supply_cut, user=user, observation=observation)
    return supply_cut
