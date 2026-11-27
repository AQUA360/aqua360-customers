"""Informe de gestions per usuari i municipi.

Compta, per a cada municipi i usuari, gestions concretes de l'oficina: canvis de
titular, sol·licituds d'alta, canvis de compte i de forma de pagament, cobraments
(per forma de pagament), modificacions de factures i factures creades a mà.

A diferència del resum d'activitat diària, no compta files de log: cada mètrica
es defineix sobre el registre que representa la gestió i es treuen els canvis
automàtics (estat de factura, PDF...) i els processos dels comptes tècnics. El
municipi és el del punt de subministrament del contracte de la gestió.
"""

from django.utils.translation import gettext
import datetime
import logging
from collections import defaultdict

import openpyxl
from django.contrib.auth.models import User
from django.db.models import F, Q
from django.db.models.functions import Coalesce
from django.utils import timezone
from django.utils.translation import gettext as _
from rest_framework import status
from rest_framework.response import Response

from statistics.utils.daily_activity_service import (
    PAID_STATUS_TOKEN,
    get_excluded_activity_usernames,
    parse_activity_dates,
)
from statistics.views.reports_views import add_row, adjust_column_widths, save_report

logger = logging.getLogger(__name__)

METRIC_CHANGE_OF_NAME = 'change_of_name'
METRIC_NEW_CONTRACT_REQUEST = 'new_contract_request'
METRIC_BANK_ACCOUNT_CHANGE = 'bank_account_change'
METRIC_PAYMENT_TYPE_CHANGE = 'payment_type_change'
METRIC_MANUAL_COLLECTION = 'manual_collection'
METRIC_REMITTANCE_COLLECTION = 'remittance_collection'
METRIC_INVOICE_MODIFICATION = 'invoice_modification'
METRIC_INVOICE_MASS_MODIFICATION = 'invoice_mass_modification'
METRIC_INVOICE_CREATED = 'invoice_created'

METRICS = [
    METRIC_CHANGE_OF_NAME,
    METRIC_NEW_CONTRACT_REQUEST,
    METRIC_BANK_ACCOUNT_CHANGE,
    METRIC_PAYMENT_TYPE_CHANGE,
    METRIC_MANUAL_COLLECTION,
    METRIC_REMITTANCE_COLLECTION,
    METRIC_INVOICE_MODIFICATION,
    METRIC_INVOICE_MASS_MODIFICATION,
    METRIC_INVOICE_CREATED,
]

# Una mateixa persona que modifica aquestes factures o més dins del mateix minut
# ho ha fet amb una acció massiva (canvi de forma de pagament, recàlcul en bloc...).
MASS_MODIFICATION_THRESHOLD = 10

# Camps d'`InvoiceLog` que canvien sols (cobraments, devolucions, PDF, enviament):
# una operació que només toca aquests camps no és una modificació de la factura.
AUTOMATIC_INVOICE_FIELDS = {
    'status', 'invoice_file', 'invoice_file_template', 'pdf_page_count', 'return_token',
    'updated_at', 'reject', 'send_date', 'send_at', 'pdf_generated_at',
}
INVOICE_CREATED_FIELD = 'Created'
EMPTY_LOG_VALUES = ['', 'None']


def get_metric_labels():
    return {
        METRIC_CHANGE_OF_NAME: _("Canvis de titular"),
        METRIC_NEW_CONTRACT_REQUEST: _("Sol·licituds d'alta nova"),
        METRIC_BANK_ACCOUNT_CHANGE: _("Canvis de número de compte"),
        METRIC_PAYMENT_TYPE_CHANGE: _("Canvis de forma de pagament"),
        METRIC_MANUAL_COLLECTION: _("Cobraments manuals"),
        METRIC_REMITTANCE_COLLECTION: _("Rebuts de remesa marcats com a cobrats"),
        METRIC_INVOICE_MODIFICATION: _("Modificacions de factures"),
        METRIC_INVOICE_MASS_MODIFICATION: _("Factures modificades en accions massives"),
        METRIC_INVOICE_CREATED: _("Factures creades manualment"),
    }


def get_metric_criteria():
    return {
        METRIC_CHANGE_OF_NAME: _(
            "Sol·licituds de contracte de canvi de nom (marcades com a canvi de nom o amb la baixa "
            "per canvi de titular vinculada) creades per l'usuari, més les edicions directes del "
            "titular d'un contracte."
        ),
        METRIC_NEW_CONTRACT_REQUEST: _(
            "Sol·licituds de contracte creades per l'usuari que no són canvis de nom."
        ),
        METRIC_BANK_ACCOUNT_CHANGE: _(
            "Canvis de dades de contracte amb un compte bancari nou i diferent de l'anterior, més les "
            "edicions directes de l'IBAN del contracte. Un mateix contracte i dia compta una vegada."
        ),
        METRIC_PAYMENT_TYPE_CHANGE: _(
            "Canvis de dades de contracte en què canvia la forma de pagament."
        ),
        METRIC_MANUAL_COLLECTION: _(
            "Rebuts que l'usuari ha passat a Pagat fora de remesa. El detall per forma de pagament "
            "és a la taula de sota de cada municipi."
        ),
        METRIC_REMITTANCE_COLLECTION: _(
            "Rebuts d'una remesa bancària que l'usuari ha marcat com a cobrats."
        ),
        METRIC_INVOICE_MODIFICATION: _(
            "Edicions manuals de dades d'una factura (imports, venciment, forma de pagament, compte, "
            "sèrie, adreça...). No compten els canvis d'estat, el PDF ni la plantilla. Diverses "
            "modificacions de la mateixa factura dins del mateix minut compten com una."
        ),
        METRIC_INVOICE_MASS_MODIFICATION: _(
            "Factures modificades en una acció massiva: l'usuari n'ha modificat %(n)s o més dins "
            "del mateix minut."
        ) % {'n': MASS_MODIFICATION_THRESHOLD},
        METRIC_INVOICE_CREATED: _(
            "Factures creades per l'usuari (no les de la facturació periòdica)."
        ),
    }


def _city(prefix=''):
    """Municipi del punt de subministrament per defecte d'un contracte o sol·licitud."""
    path = f'{prefix}__' if prefix else ''
    return Coalesce(
        f'{path}supply_point_default__address__city__name',
        f'{path}supply_point_default__address__street__city__name',
        f'{path}supply_point_default__address__city_name',
    )


def _period_bounds(date_from, date_to):
    """Límits amb zona [inici, fi) perquè els filtres de data puguin fer servir l'índex."""
    start = timezone.make_aware(datetime.datetime.combine(date_from, datetime.time.min))
    end = timezone.make_aware(
        datetime.datetime.combine(date_to + datetime.timedelta(days=1), datetime.time.min)
    )
    return start, end


def _in_period(field, start, end):
    return {f'{field}__gte': start, f'{field}__lt': end}


def _to_minute(value):
    return value.replace(second=0, microsecond=0) if value else value


def compute_user_city_management(date_from, date_to):
    """Recompte de gestions entre dues dates (incloses).

    Retorna `(users, metrics, payments)`:
      - `users`: {user_id: nom per mostrar}
      - `metrics`: {municipi: {user_id: {mètrica: n}}}
      - `payments`: {municipi: {user_id: {forma de pagament: n}}} (cobraments manuals)
    Les gestions sense contracte (o sense municipi) queden amb municipi `None`.
    """
    from billing.models import InvoiceLog, PaymentMovement
    from contract.models import ContractDataChange, ContractLog, ContractRequest
    from logger.models import LogContractRequestStatus, LogInvoiceDataChange

    start, end = _period_bounds(date_from, date_to)
    users = {
        user.id: (f"{user.first_name or ''} {user.last_name or ''}".strip() or user.username)
        for user in User.objects.exclude(username__in=get_excluded_activity_usernames())
    }
    user_ids = list(users)

    metrics = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))
    payments = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))

    def add(city, user_id, metric):
        metrics[city][user_id][metric] += 1

    # --- Sol·licituds de contracte -------------------------------------------
    # La sol·licitud no desa qui la crea: és l'usuari del seu primer canvi d'estat.
    creators = {}
    for request_id, user_id in (
        LogContractRequestStatus.objects
        .filter(previous_status__isnull=True, object__isnull=False)
        .filter(object__created_at__gte=start, object__created_at__lt=end)
        .order_by('timestamp', 'id')
        .values_list('object_id', 'user_id')
    ):
        creators.setdefault(request_id, user_id)
    creators = {request_id: user_id for request_id, user_id in creators.items() if user_id in users}

    period_requests = ContractRequest.objects.filter(id__in=list(creators))
    change_of_name_ids = set(
        period_requests
        .filter(Q(is_change_of_name=True)
                | Q(contract_termination_requests__type__is_change_of_name=True))
        .values_list('id', flat=True)
    )
    for request_id, city in period_requests.annotate(city=_city()).values_list('id', 'city'):
        metric = (METRIC_CHANGE_OF_NAME if request_id in change_of_name_ids
                  else METRIC_NEW_CONTRACT_REQUEST)
        add(city, creators[request_id], metric)

    # Edicions directes del titular d'un contracte que ja en tenia.
    for city, user_id in (
        ContractLog.objects
        .filter(field_name='holder', user_id__in=user_ids, **_in_period('created_at', start, end))
        .exclude(Q(old_value__isnull=True) | Q(old_value__in=EMPTY_LOG_VALUES))
        .annotate(city=_city('contract'))
        .values_list('city', 'user_id')
    ):
        add(city, user_id, METRIC_CHANGE_OF_NAME)

    # --- Canvis de compte i de forma de pagament ----------------------------
    data_changes = ContractDataChange.objects.filter(
        user_id__in=user_ids, is_active=True, **_in_period('created_at', start, end),
    )
    bank_events = set()
    for city, user_id, contract_id, created_at in (
        data_changes
        .filter(new_payment__isnull=False)
        .filter(Q(previous_payment__isnull=True)
                | ~Q(new_payment__iban=F('previous_payment__iban')))
        .annotate(city=_city('contract'))
        .values_list('city', 'user_id', 'contract_id', 'created_at')
    ):
        bank_events.add((city, user_id, contract_id, timezone.localdate(created_at)))
    for city, user_id, contract_id, created_at in (
        ContractLog.objects
        .filter(field_name='payment_IBAN', user_id__in=user_ids,
                **_in_period('created_at', start, end))
        .annotate(city=_city('contract'))
        .values_list('city', 'user_id', 'contract_id', 'created_at')
    ):
        bank_events.add((city, user_id, contract_id, timezone.localdate(created_at)))
    for city, user_id, _contract_id, _day in bank_events:
        add(city, user_id, METRIC_BANK_ACCOUNT_CHANGE)

    for city, user_id in (
        data_changes
        .filter(new_payment_type__isnull=False)
        .filter(Q(previous_payment_type__isnull=True)
                | ~Q(new_payment_type=F('previous_payment_type')))
        .annotate(city=_city('contract'))
        .values_list('city', 'user_id')
    ):
        add(city, user_id, METRIC_PAYMENT_TYPE_CHANGE)

    # --- Cobraments -----------------------------------------------------------
    no_payment_type = _("Sense forma de pagament")
    for city, user_id, payment_type, remittance_id in (
        PaymentMovement.objects
        .filter(user_id__in=user_ids, is_active=True, is_positive=True,
                current_status__token=PAID_STATUS_TOKEN,
                **_in_period('timestamp', start, end))
        .annotate(city=Coalesce(_city('payment__contract'), _city('payment__invoice__contract')))
        .values_list('city', 'user_id', 'payment_type__name', 'payment_remittance_id')
    ):
        if remittance_id:
            add(city, user_id, METRIC_REMITTANCE_COLLECTION)
            continue
        add(city, user_id, METRIC_MANUAL_COLLECTION)
        payments[city][user_id][payment_type or no_payment_type] += 1

    # --- Factures ---------------------------------------------------------------
    # `InvoiceLog` desa una fila per camp modificat: s'agrupen per operació.
    operations = {}
    for token, field, invoice_id, user_id, created_at, city in (
        InvoiceLog.objects
        .filter(user_id__in=user_ids, **_in_period('created_at', start, end))
        .annotate(city=_city('invoice__contract'))
        .values_list('operation_token', 'field_name', 'invoice_id', 'user_id', 'created_at', 'city')
    ):
        # Alguns camins fan servir un token fix (p. ex. "change_due_date") per a
        # totes les factures: la factura sempre forma part de la clau.
        key = (token, invoice_id) if token else (invoice_id, user_id, created_at)
        operation = operations.setdefault(key, {
            'fields': set(), 'invoice_id': invoice_id, 'user_id': user_id,
            'created_at': created_at, 'city': city,
        })
        operation['fields'].add(field)

    modifications = set()  # (factura, usuari, minut, municipi)
    for operation in operations.values():
        if INVOICE_CREATED_FIELD in operation['fields']:
            add(operation['city'], operation['user_id'], METRIC_INVOICE_CREATED)
        elif operation['fields'] - AUTOMATIC_INVOICE_FIELDS:
            modifications.add((operation['invoice_id'], operation['user_id'],
                               _to_minute(operation['created_at']), operation['city']))
    for invoice_id, user_id, timestamp, city in (
        LogInvoiceDataChange.objects
        .filter(user_id__in=user_ids, object__isnull=False, **_in_period('timestamp', start, end))
        .annotate(city=_city('object__contract'))
        .values_list('object_id', 'user_id', 'timestamp', 'city')
    ):
        modifications.add((invoice_id, user_id, _to_minute(timestamp), city))

    invoices_per_minute = defaultdict(set)
    for invoice_id, user_id, minute, _city_name in modifications:
        invoices_per_minute[(user_id, minute)].add(invoice_id)
    for invoice_id, user_id, minute, city in modifications:
        is_mass = len(invoices_per_minute[(user_id, minute)]) >= MASS_MODIFICATION_THRESHOLD
        add(city, user_id, METRIC_INVOICE_MASS_MODIFICATION if is_mass else METRIC_INVOICE_MODIFICATION)

    return users, metrics, payments


def _sorted_cities(*groups):
    cities = set()
    for group in groups:
        cities.update(group)
    named = sorted(city for city in cities if city)
    return named + ([None] if None in cities else [])


def build_workbook(date_from, date_to, users, metrics, payments, black_fill=None, white_bold_font=None):
    labels = get_metric_labels()
    no_city = _("Sense municipi")
    cities = _sorted_cities(metrics, payments)
    payment_types = sorted({
        payment_type
        for by_user in payments.values() for counts in by_user.values() for payment_type in counts
    })
    period = f"{date_from.strftime('%d/%m/%Y')} - {date_to.strftime('%d/%m/%Y')}"

    def user_name(user_id):
        return users.get(user_id, '-')

    def by_activity(counts_by_user):
        return sorted(counts_by_user,
                      key=lambda uid: (-sum(counts_by_user[uid].values()), user_name(uid)))

    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = _("Per municipi")
    row = 0
    row = add_row(sheet, row, [_("Gestions per usuari i municipi")], fill=black_fill, font=white_bold_font)
    row = add_row(sheet, row, [_("Període"), period])
    row += 1

    for city in cities:
        row = add_row(sheet, row, [city or no_city], fill=black_fill, font=white_bold_font)
        row = add_row(sheet, row, [_("Usuari")] + [labels[m] for m in METRICS])
        totals = defaultdict(int)
        by_user = metrics.get(city, {})
        for user_id in by_activity(by_user):
            values = [by_user[user_id].get(metric, 0) for metric in METRICS]
            row = add_row(sheet, row, [user_name(user_id)] + values)
            for metric, value in zip(METRICS, values):
                totals[metric] += value
        row = add_row(sheet, row, [_("Total")] + [totals[m] for m in METRICS])

        city_payments = payments.get(city, {})
        if city_payments:
            row += 1
            row = add_row(sheet, row, [_("Cobraments manuals per forma de pagament")])
            row = add_row(sheet, row, [_("Usuari")] + payment_types + [_("Total")])
            payment_totals = defaultdict(int)
            for user_id in by_activity(city_payments):
                values = [city_payments[user_id].get(ptype, 0) for ptype in payment_types]
                row = add_row(sheet, row, [user_name(user_id)] + values + [sum(values)])
                for ptype, value in zip(payment_types, values):
                    payment_totals[ptype] += value
            row = add_row(sheet, row, [_("Total")] + [payment_totals[p] for p in payment_types]
                          + [sum(payment_totals.values())])
        row += 2

    summary = workbook.create_sheet(title=_("Resum"))
    row = 0
    row = add_row(summary, row, [_("Municipi")] + [labels[m] for m in METRICS],
                  fill=black_fill, font=white_bold_font)
    grand_totals = defaultdict(int)
    for city in cities:
        by_user = metrics.get(city, {})
        values = [sum(counts.get(metric, 0) for counts in by_user.values()) for metric in METRICS]
        row = add_row(summary, row, [city or no_city] + values)
        for metric, value in zip(METRICS, values):
            grand_totals[metric] += value
    row = add_row(summary, row, [_("Total")] + [grand_totals[m] for m in METRICS])
    row += 2
    row = add_row(summary, row, [_("Cobraments manuals per forma de pagament")],
                  fill=black_fill, font=white_bold_font)
    row = add_row(summary, row, [_("Municipi")] + payment_types + [_("Total")])
    payment_grand_totals = defaultdict(int)
    for city in cities:
        by_user = payments.get(city, {})
        values = [sum(counts.get(ptype, 0) for counts in by_user.values()) for ptype in payment_types]
        row = add_row(summary, row, [city or no_city] + values + [sum(values)])
        for ptype, value in zip(payment_types, values):
            payment_grand_totals[ptype] += value
    add_row(summary, row, [_("Total")] + [payment_grand_totals[p] for p in payment_types]
            + [sum(payment_grand_totals.values())])

    criteria_sheet = workbook.create_sheet(title=_("Criteris"))
    row = 0
    row = add_row(criteria_sheet, row, [_("Concepte"), _("Com es calcula")],
                  fill=black_fill, font=white_bold_font)
    row = add_row(criteria_sheet, row, [_("Municipi"), _(
        "El del punt de subministrament del contracte de la gestió (en les sol·licituds, el del "
        "seu punt de subministrament). Les gestions sense contracte surten a \"Sense municipi\"."
    )])
    row = add_row(criteria_sheet, row, [_("Usuari"), _(
        "Qui ha fet la gestió. No s'hi inclouen els processos automàtics dels comptes tècnics."
    )])
    criteria = get_metric_criteria()
    for metric in METRICS:
        row = add_row(criteria_sheet, row, [labels[metric], criteria[metric]])

    for each in (sheet, summary):
        adjust_column_widths(each)
    criteria_sheet.column_dimensions['A'].width = 40
    criteria_sheet.column_dimensions['B'].width = 120
    return workbook


def generate_user_city_management_report(request, black_fill=None, white_bold_font=None, task=None):
    """Excel de gestions per usuari i municipi. Payload: `start_date`/`end_date` o `date_range`."""
    try:
        data = request.data or {}
        start_value = data.get('start_date')
        end_value = data.get('end_date')
        date_range = data.get('date_range')
        if not (start_value and end_value) and isinstance(date_range, (list, tuple)) and len(date_range) >= 2:
            start_value, end_value = date_range[0], date_range[1]
        date_from, date_to = parse_activity_dates(start_value, end_value)

        users, metrics, payments = compute_user_city_management(date_from, date_to)
        if not metrics:
            # Sense fitxer i sense error: la cua i els informes diaris ho tracten com
            # "sense dades" (l'informe diari respecta `create_without_data`).
            return None, None, None
        workbook = build_workbook(date_from, date_to, users, metrics, payments,
                                  black_fill=black_fill, white_bold_font=white_bold_font)

        filename = f"gestions_usuari_municipi_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        document_id = save_report(
            content=workbook, filename=filename,
            name=data.get('name') or _("Gestions per usuari i municipi"),
            type_id=data.get('type_id'), start_date=date_from, end_date=date_to,
        )
        return None, document_id, filename
    except Exception:
        logger.exception("Error generant l'informe de gestions per usuari i municipi")
        # Un error no es pot confondre amb "sense dades": l'informe diari el desa com a error.
        return Response(
            {'error': gettext("An unexpected error has occurred.")},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        ), None, None
