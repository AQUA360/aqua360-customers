"""Duplicate communication process policy for supply cuts.

Single source of truth shared by the preflight endpoint and the process
creation serializer, so the warning shown before starting a process can never
disagree with the check that actually guards the write.

Tiers:
    ``block``  a process for the same cut is mid-flight. Starting a second one
               would duplicate communications to the same recipients, so the
               user has to cancel or wait first.
    ``warn``   processes exist but none is mid-flight (pending, draft,
               finished or cancelled). A new process is legitimate, but the user
               is told about the existing ones first.
    ``none``   nothing linked to those cuts; the caller proceeds silently.
"""

from communication.models import CommunicationProcess

# Processant, Coms. creades, En curs: these are the statuses where a Celery task
# is running or the communications are being delivered, so the process is still
# in flight.
BLOCKING_CONFIG_TOKENS = (
    'communication_process_status_processing_token',
    'communication_process_status_files_created_token',
    'communication_process_status_current_token',
)

# Used when the ConfigProject rows are missing, so a fresh install or a partial
# data load still blocks the three known mid-flight states.
FALLBACK_BLOCKING_TOKENS = frozenset({'-2', '1', '2'})

TIER_BLOCK = 'block'
TIER_WARN = 'warn'
TIER_NONE = 'none'


def blocking_tokens():
    """Blocking status tokens, resolved from config with a safe fallback."""
    from coredata.models import ConfigProject

    tokens = set()
    for config_token in BLOCKING_CONFIG_TOKENS:
        try:
            tokens.add(str(ConfigProject.objects.get(token=config_token).value))
        except ConfigProject.DoesNotExist:
            continue
    return tokens or set(FALLBACK_BLOCKING_TOKENS)


def processes_for_cuts(cut_ids, exclude_process_id=None, exclude_run_token=None):
    """Active processes linked to any of ``cut_ids``.

    Soft deleted processes (``is_active=False``) are ignored, otherwise a deleted
    process would keep blocking a cut forever. ``exclude_run_token`` lets a
    wizard that creates several batched processes of the same run ignore its own
    earlier batches, while still blocking a different user's run.
    """
    if not cut_ids:
        return CommunicationProcess.objects.none()

    queryset = (
        CommunicationProcess.objects
        .filter(is_active=True, supply_cuts__id__in=list(cut_ids))
        .exclude(id=exclude_process_id)
        .distinct()
    )
    if exclude_run_token:
        queryset = queryset.exclude(run_token=exclude_run_token)
    return queryset.select_related('status', 'user')


def classify(processes, blocking=None):
    """Return ``block``/``warn``/``none`` for an iterable of processes."""
    if blocking is None:
        blocking = blocking_tokens()

    tokens = [str(process.status.token) for process in processes if process.status_id]
    if any(token in blocking for token in tokens):
        return TIER_BLOCK
    if tokens:
        return TIER_WARN
    return TIER_NONE


def inspect(cut_ids, exclude_process_id=None, exclude_run_token=None):
    """Return ``(tier, processes)`` for the given cuts in one query."""
    processes = list(processes_for_cuts(cut_ids, exclude_process_id, exclude_run_token))
    return classify(processes), processes


def lock_cuts(cut_ids):
    """Take a row lock on every cut so concurrent saves serialise.

    Must be called inside an open transaction, otherwise Django raises
    ``TransactionManagementError``. Ids are locked in ascending order so two
    transactions covering the same cuts in a different order cannot deadlock.
    Returns the ids that actually exist.
    """
    from service.models import SupplyCut

    if not cut_ids:
        return []

    rows = SupplyCut.objects.select_for_update().filter(id__in=list(cut_ids)).order_by('id')
    return [row.id for row in rows]