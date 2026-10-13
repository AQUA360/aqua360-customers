from django.db import transaction

from contract.tasks import fix_pending_bails_task


def run():
    # Enqueue after commit: run_pending_scripts wraps run() in transaction.atomic().
    transaction.on_commit(lambda: fix_pending_bails_task.delay())
