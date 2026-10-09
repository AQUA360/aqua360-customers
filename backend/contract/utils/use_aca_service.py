import logging

from django.db.models import Q
from django.db.models.signals import post_save, pre_save

from contract.models import Contract
from contract.signals import contract_pre_save, terminate_contract_update_bail
from watchdog.aca_config import uses_aca_enabled

logger = logging.getLogger(__name__)


def get_active_contracts_queryset():
    return Contract.objects.filter(is_active=True)


def get_pending_use_aca_queryset():
    return get_active_contracts_queryset().filter(
        Q(use_aca__isnull=True) | Q(use_aca='')
    )


def get_use_aca_stats():
    active_contracts = get_active_contracts_queryset()
    pending_contracts = get_pending_use_aca_queryset()

    return {
        'uses_aca_enabled': uses_aca_enabled(),
        'active_contracts': active_contracts.count(),
        'pending_use_aca': pending_contracts.count(),
        'filled_use_aca': active_contracts.exclude(
            Q(use_aca__isnull=True) | Q(use_aca='')
        ).count(),
    }


def disconnect_contract_signals():
    try:
        post_save.disconnect(terminate_contract_update_bail, sender=Contract)
        pre_save.disconnect(contract_pre_save, sender=Contract)
    except Exception as exc:
        logger.warning("No s'han pogut desconnectar alguns signals: %s", exc)


def reconnect_contract_signals():
    try:
        post_save.connect(terminate_contract_update_bail, sender=Contract)
        pre_save.connect(contract_pre_save, sender=Contract)
    except Exception as exc:
        logger.warning("No s'han pogut reconnectar alguns signals: %s", exc)


def run_fill_contract_use_aca(update_all_contracts=False, dry_run=False):
    from contract.management.commands.fill_contract_use_aca import fill_contract_use_aca

    disconnect_contract_signals()
    try:
        return fill_contract_use_aca(
            update_all_contracts=update_all_contracts,
            dry_run=dry_run,
        )
    finally:
        reconnect_contract_signals()
