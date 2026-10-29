from __future__ import absolute_import, unicode_literals
import os
from celery import Celery
from celery.schedules import crontab
from celery.signals import before_task_publish, task_postrun, task_prerun, worker_ready
from django.conf import settings

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'customers.settings')

app = Celery('customers')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

# Les tasques porten l'usuari que les ha encuat: així els historials dels processos
# automàtics que llança algú queden a nom seu. Les del beat no en tenen.
CURRENT_USER_HEADER = 'current_user_id'


@before_task_publish.connect
def attach_current_user(headers=None, **kwargs):
    if headers is None or CURRENT_USER_HEADER in headers:
        return
    from contract.middleware import get_current_user
    user = get_current_user()
    headers[CURRENT_USER_HEADER] = user.pk if user else None


@task_prerun.connect
def restore_current_user(task=None, **kwargs):
    # En mode eager la tasca corre dins la petició, que ja té l'usuari
    if task is None or task.request.is_eager:
        return
    from django.contrib.auth import get_user_model
    from contract.middleware import set_current_user
    user_id = getattr(task.request, CURRENT_USER_HEADER, None)
    user = get_user_model().objects.filter(pk=user_id).first() if user_id else None
    set_current_user(user)


@task_postrun.connect
def clear_current_user(task=None, **kwargs):
    if task is None or task.request.is_eager:
        return
    from contract.middleware import set_current_user
    set_current_user(None)

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
    'generate-recurring-calendar-tasks': {
        'task': 'notification.tasks.generate_recurring_tasks',
        'schedule': crontab(minute=22, hour=0)
    },
    'check-today-tasks': {
        'task': 'notification.tasks.notify_today_tasks',
        'schedule': crontab(minute=25, hour=0)
    },
    'check-due-incidents': {
        'task': 'notification.tasks.notify_due_incidents',
        'schedule': crontab(minute=27, hour=0)
    },
    # Els terminis poden ser en hores: avisos i escalats cada 15 minuts
    'check-incident-deadlines': {
        'task': 'notification.tasks.check_incident_deadlines',
        'schedule': crontab(minute='*/15')
    },
    # El resum per correu surt a primera hora del matí, no de matinada.
    'send-daily-tasks-email': {
        'task': 'notification.tasks.send_daily_tasks_email',
        'schedule': crontab(minute=0, hour=7)
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