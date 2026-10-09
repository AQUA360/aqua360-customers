from __future__ import absolute_import, unicode_literals
import os
from celery import Celery
from celery.schedules import crontab
from celery.signals import worker_ready
from django.conf import settings

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'customers.settings')

app = Celery('customers')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

# Les tasques periòdiques van amb `crontab`, no amb `timedelta`: un interval es
# compta des de l'arrencada del beat, i com que cada desplegament recrea el
# contenidor, les diàries acabaven executant-se a l'hora del deploy (i, si es
# desplegava sovint, cada vegada). Amb crontab tenen una hora fixa de matinada.
# Els minuts van escalonats per no engegar-les totes al mateix instant.
beat_schedule = {
    'deactivate-expired-bonifications-every-24-hours': {
        'task': 'contract.tasks.deactivate_expired_bonifications_variables',
        'schedule': crontab(minute=5, hour=0),  
    },
    'check-payments-due-date-every-24-hours': {
        'task': 'billing.tasks.check_payments_due_date',
        'schedule': crontab(minute=10, hour=0),  
    },
    'activate-supply-cut-every-24-hours': {
        'task': 'service.tasks.activate_supply_cut',
        'schedule': crontab(minute=15, hour=0),  
    },
    'deactivate-supply-cut-every-24-hours': {
        'task': 'service.tasks.deactivate_supply_cut',
        'schedule': crontab(minute=20, hour=0),  
    },
    'generate-daily-documents': {
        'task': 'statistics.tasks.generate_daily_documents',
        'schedule': crontab(minute=30, hour=22),  
    },
    # 'create-billings': {
    #     'task': 'billing.tasks.create_billings',
    #     'schedule': crontab(minute=0, hour=0, day_of_month=1)
    # },
    'calculate-median-consumption': {
        'task': 'statistics.tasks.calculate_median_consumption',
        'schedule': crontab(minute=0, hour=0, day_of_month=1)
    },
    'check-today-tasks': {
        'task': 'billing.tasks.check_today_tasks',
        'schedule': crontab(minute=25, hour=0)
    },
    'expire-vulnerability-requests': {
        'task': 'claimrequest.tasks.set_expired_vulnerability_request', 
        'schedule': crontab(minute=30, hour=0)
    },
    'notify-claim-request-step-due-date': {
        'task': 'claimrequest.tasks.notify_claim_request_step_due_date', 
        'schedule': crontab(minute=0, hour=0, day_of_month=1)
    },
    # COMENTED SINCE THIS IS SUPPOSEDLY ALREADY HANDLED BY A SIGNAL
    # 'return-bails-termination-requests': {
    #     'task': 'contract.tasks.return_bails_termination_requests',
    #     'schedule': crontab(minute=0, hour=0, day_of_month=1)
    # },
    'cleam-tmp-dir': {
        'task': 'coredata.tasks.clean_tmp_dir',
        'schedule': crontab(minute=0, hour=0, day_of_month=1)
    },
    'update-missing-periods-for-invoices': {
        'task': 'billing.tasks.update_missing_periods_for_invoices',
        'schedule': crontab(minute=0, hour=0, day_of_month=1)
    },
    'fill-contract-use-aca': {
        'task': 'contract.tasks.fill_contract_use_aca_task',
        'schedule': crontab(minute=35, hour=0), 
    },
    'check-daily-documents-due-date-every-24-hours': {
        'task': 'statistics.tasks.check_daily_documents_due_date',
        'schedule': crontab(minute=40, hour=0),  
    },
    'cleanup-export-jobs': {
        'task': 'documentmanager.tasks.cleanup_export_jobs',
        'schedule': crontab(minute=45, hour=0),
    },
    'backfill-billing-consumption-monthly': {
        'task': 'statistics.tasks.backfill_billing_consumption',
        'schedule': crontab(minute=15, hour=2, day_of_month='1'),
        'options': {
            'queue': 'celery',       
            'expires': 60 * 60 * 6,  
        },
    },
}

if getattr(settings, "GISWATER_SYNC_CONNECS_ENABLED", False):
    beat_schedule["sync-giswater-connections"] = {
        "task": "integrations.tasks.sync_giswater_connections_task",
        "schedule": crontab(
            minute=settings.GISWATER_SYNC_CONNECS_MINUTE,
            hour=settings.GISWATER_SYNC_CONNECS_HOUR,
        ),
    }

if getattr(settings, "SIGNING_POLL_ENABLED", False):
    # Aquesta sí que ha d'anar sovint, però continua sent un crontab (i no un
    # timedelta) pel motiu explicat a dalt: així no depèn de l'hora del deploy.
    beat_schedule["poll-signing-sessions"] = {
        "task": "integrations.tasks.poll_signing_sessions_task",
        "schedule": crontab(minute=f"*/{settings.SIGNING_POLL_MINUTES}"),
    }

app.conf.beat_schedule = beat_schedule
""" 'check-send-date': {
    'task': 'communication.tasks.check_send_date',
    'schedule': crontab(minute=0, hour=0, day_of_month=1)
} """

# @worker_ready.connect
# def run_on_start(sender, **kwargs):
#     # from billing.tasks import create_billings
#     from statistics.tasks import calculate_median_consumption
#     # create_billings.delay()
#     calculate_median_consumption.delay()