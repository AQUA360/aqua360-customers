"""Resum d'activitat diària per usuari.

Contesta la pregunta "què he fet avui": cobraments registrats, ordres de treball
noves, gestions de contracte, comunicacions, lectures... El sistema no té una taula
única d'auditoria, però sí que hi ha ~30 models de `logger` amb (`user`, `timestamp`)
i una vintena de models de domini amb un `user`/`created_by` propi. Aquest mòdul els
declara tots a `ACTIVITY_SOURCES` i els recorre un a un, de manera que afegir una
font nova és afegir una entrada a la llista i no tocar res més.

Dues sortides sobre el mateix càlcul (`build_daily_activity`):
  - el JSON que consumeix la pantalla (`views/daily_activity_view.py`),
  - l'Excel que genera la cua d'informes (`generate_daily_activity_summary_report`).
"""

import datetime
import traceback

from django.apps import apps
from django.conf import settings
from django.contrib.auth.models import User
from django.db.models import Count, Exists, OuterRef, Q, Sum
from django.utils import timezone
from django.utils.translation import gettext as _, ngettext

from billing.models import PaymentMovement

import openpyxl

from statistics.views.reports_views import add_row, adjust_column_widths, jump_row, save_report


# Nombre de moviments que es llegeixen per font per muntar la cronologia. La pantalla
# en demana pocs (només ha de pintar el dia) i l'Excel molts, perquè allà sí que
# s'espera el detall complet.
SCREEN_SOURCE_DETAIL_LIMIT = 200
SCREEN_TIMELINE_LIMIT = 500
REPORT_SOURCE_DETAIL_LIMIT = 5000
REPORT_TIMELINE_LIMIT = 50000

# Comptes tècnics: l'activitat que hi queda registrada no és de ningú en concret
# (processos automàtics, importacions, tasques programades) i, barrejada amb la de
# les persones, només fa soroll — `customers` pot acumular centenars de gestions
# de contracte en una setmana d'un sol procés. No es poden consultar ni pels
# administradors; l'única excepció és un mateix (veure `resolve_activity_users`),
# perquè a algunes instal·lacions aquest compte també és el login d'administració.
DEFAULT_EXCLUDED_ACTIVITY_USERNAMES = ['customers']

# `PaymentStatus.token` de "Pagat". És el criteri de "cobrat" de l'informe: un rebut
# remès compta com a cobrat quan ha quedat en aquest estat.
PAID_STATUS_TOKEN = '0'


def get_excluded_activity_usernames():
    """Usernames que no es poden consultar. Sobreescrivible per instal·lació amb
    `DAILY_ACTIVITY_EXCLUDED_USERNAMES` a settings."""
    return list(getattr(settings, 'DAILY_ACTIVITY_EXCLUDED_USERNAMES',
                        DEFAULT_EXCLUDED_ACTIVITY_USERNAMES))


def get_excluded_activity_user_ids():
    return set(
        User.objects.filter(username__in=get_excluded_activity_usernames())
        .values_list('id', flat=True)
    )


class ActivitySource:
    """Una font d'activitat: un model amb un camp d'usuari i un camp de data.

    `token_paths`, `contract_paths` i `detail_paths` són camins amb punts
    (`object.token`, `payment.invoice.contract.token`) que es proven en ordre fins
    que un dona valor; serveixen per omplir les columnes "Referència", "Contracte" i
    "Detall" de la cronologia sense haver d'escriure codi per model.
    """

    def __init__(self, key, category, label, model, user_field, date_field,
                 token_paths=(), contract_paths=(), detail_paths=(),
                 select_related=(), amount_aggregator=None, amount_resolver=None,
                 queryset_filter=None, detail_resolver=None):
        self.key = key
        self.category = category
        self.label = label
        self.model = model
        self.user_field = user_field
        self.date_field = date_field
        self.token_paths = token_paths
        self.contract_paths = contract_paths
        self.detail_paths = detail_paths
        self.select_related = select_related
        # Callable(queryset) -> dict amb els imports de la font (p. ex. cobrat/retornat).
        self.amount_aggregator = amount_aggregator
        # Callable(obj) -> Decimal|None per l'import d'una fila concreta de la cronologia.
        self.amount_resolver = amount_resolver
        # Callable(queryset) -> queryset, per acotar la font (p. ex. separar cobraments
        # de devolucions) o per treure'n duplicats d'una altra font.
        self.queryset_filter = queryset_filter
        # Callable(obj) -> str|None quan el detall no surt de camins (p. ex. "N rebuts").
        self.detail_resolver = detail_resolver

    def get_model(self):
        app_label, model_name = self.model.split('.')
        return apps.get_model(app_label, model_name)

    @property
    def date_lookup(self):
        """`camp__range` per als DateField i `camp__date__range` per als DateTimeField."""
        model = self.get_model()
        internal_type = model._meta.get_field(self.date_field).get_internal_type()
        if internal_type == 'DateTimeField':
            return f'{self.date_field}__date__range'
        return f'{self.date_field}__range'

    def queryset(self, user_ids, date_from, date_to):
        model = self.get_model()
        queryset = model.objects.filter(
            **{f'{self.user_field}__in': user_ids, self.date_lookup: (date_from, date_to)}
        )
        if self.queryset_filter:
            queryset = self.queryset_filter(queryset)
        return queryset


# ---------------------------------------------------------------------------
# Categories
# ---------------------------------------------------------------------------

CATEGORY_COLLECTIONS = 'collections'
CATEGORY_ORDERS = 'orders'
CATEGORY_CONTRACTS = 'contracts'
CATEGORY_BILLING = 'billing'
CATEGORY_READINGS = 'readings'
CATEGORY_COMMUNICATIONS = 'communications'
CATEGORY_CLAIMS = 'claims'
CATEGORY_SERVICE = 'service'
CATEGORY_PRICING = 'pricing'
CATEGORY_OTHER = 'other'


def get_category_labels():
    return {
        CATEGORY_COLLECTIONS: _("Cobraments i devolucions"),
        CATEGORY_ORDERS: _("Ordres de treball"),
        CATEGORY_CONTRACTS: _("Gestions de contracte"),
        CATEGORY_BILLING: _("Facturació"),
        CATEGORY_READINGS: _("Lectures i comptadors"),
        CATEGORY_COMMUNICATIONS: _("Comunicacions i atenció"),
        CATEGORY_CLAIMS: _("Impagats, incidències i fraus"),
        CATEGORY_SERVICE: _("Servei i infraestructura"),
        CATEGORY_PRICING: _("Productes i tarifes"),
        CATEGORY_OTHER: _("Altres"),
    }


CATEGORY_ORDER = [
    CATEGORY_COLLECTIONS,
    CATEGORY_ORDERS,
    CATEGORY_CONTRACTS,
    CATEGORY_BILLING,
    CATEGORY_READINGS,
    CATEGORY_COMMUNICATIONS,
    CATEGORY_CLAIMS,
    CATEGORY_SERVICE,
    CATEGORY_PRICING,
    CATEGORY_OTHER,
]


# ---------------------------------------------------------------------------
# Imports (només les fonts que en tenen)
# ---------------------------------------------------------------------------

def _collection_amounts(queryset):
    """Import dels moviments de cobrament (`is_positive=True`), normalment positiu."""
    total = queryset.aggregate(total=Sum('payment__amount'))['total'] or 0
    return {'charged': total, 'net': total}


def _return_amounts(queryset):
    """Import de les devolucions (`is_positive=False`), normalment negatiu.

    L'import real d'un moviment és `amount * (1 si is_positive else -1)`, el mateix
    `multiplier` que fa servir l'informe de cobraments de `report_billing_service.py`.
    No es dona per fet que les devolucions tinguin l'import positiu a la base de
    dades: n'hi ha amb `amount` ja negatiu (devolució d'un rebut negatiu, que per
    tant suma), i llavors la devolució surt en positiu.
    """
    total = -(queryset.aggregate(total=Sum('payment__amount'))['total'] or 0)
    return {'returned': total, 'net': total}


def _payment_movement_row_amount(obj):
    amount = getattr(getattr(obj, 'payment', None), 'amount', None)
    if amount is None:
        return None
    return amount if obj.is_positive else -amount


def _remittance_amounts(queryset):
    """Imports d'un conjunt de remeses de cobrament.

    Dues xifres, perquè responen preguntes diferents:
      - `charged`: els rebuts de la remesa que han quedat en estat Pagat. És el
        cobrament de debò, i és el que se suma a l'import cobrat del dia.
      - `remitted`: tot el que es va enviar al banc, cobrat o no.

    Un rebut remès dues vegades (reenviat després d'una devolució) compta a cada
    remesa: és el que s'ha enviat realment a cada enviament.

    L'import cobrat es calcula sobre l'**estat actual** del rebut, no sobre el que
    tenia el dia de l'enviament: si demà una part d'aquesta remesa torna com a
    devolució, el cobrat d'aquell dia baixarà. `remitted`, que no depèn de l'estat,
    es manté al costat justament per poder veure les dues coses.
    """
    totals = queryset.aggregate(
        remitted=Sum('payments__amount'),
        charged=Sum('payments__amount', filter=Q(payments__status__token=PAID_STATUS_TOKEN)),
    )
    return {
        'remitted': totals['remitted'] or 0,
        'charged': totals['charged'] or 0,
        'net': totals['charged'] or 0,
    }


def _remittance_row_amount(obj):
    """L'import cobrat de la remesa (els rebuts que han quedat en estat Pagat)."""
    return obj.payments.filter(status__token=PAID_STATUS_TOKEN).aggregate(total=Sum('amount'))['total']


def _remittance_row_detail(obj):
    total_count = obj.payments.count()
    paid_count = obj.payments.filter(status__token=PAID_STATUS_TOKEN).count()
    parts = [ngettext("%(count)d rebut", "%(count)d rebuts", total_count) % {'count': total_count}]
    if paid_count != total_count:
        parts.append(_("%(count)d cobrats") % {'count': paid_count})
    status = getattr(getattr(obj, 'status', None), 'name', None)
    if status:
        parts.append(str(status))
    return ' · '.join(parts)


def _exclude_movement_twins(queryset):
    """Treu els canvis d'estat de rebut que ja compta `PaymentMovement`.

    Cada `PaymentMovement` deixa també una fila a `LogPaymentStatusChange` amb el
    mateix rebut i el mateix estat, escrita en el mateix instant (amb centèsimes de
    diferència), de manera que comptar les dues fonts feia que una devolució SEPA
    sortís dues vegades. El moviment és el registre bo —porta remesa, motiu de
    devolució i import—, així que és el log el que se'n va.

    Les altres 13.000 files del log no tenen moviment (`Pendent → Processat` de
    l'enviament de remeses, anul·lacions, abonaments) i s'han de continuar comptant:
    per això no es descarta la font sencera.
    """
    movements = PaymentMovement.objects.filter(
        payment_id=OuterRef('object_id'),
        current_status_id=OuterRef('current_status_id'),
    )
    return queryset.annotate(has_movement=Exists(movements)).filter(has_movement=False)


def _simple_amount_aggregator(field, sign=1):
    def aggregator(queryset):
        total = queryset.aggregate(total=Sum(field))['total'] or 0
        return {'net': total * sign}
    return aggregator


def _simple_amount_resolver(attr, sign=1):
    def resolver(obj):
        value = getattr(obj, attr, None)
        return None if value is None else value * sign
    return resolver


# ---------------------------------------------------------------------------
# Registre de fonts
# ---------------------------------------------------------------------------

def get_activity_sources():
    """Les fonts d'activitat, amb les etiquetes ja traduïdes.

    És una funció i no una constant de mòdul perquè les etiquetes passen per
    `gettext` i s'han de resoldre amb l'idioma actiu de la petició (o el de
    `settings.LANGUAGE_CODE` quan corre dins de la tasca de Celery).
    """
    return [
        # --- Cobraments -----------------------------------------------------
        # Cobraments i devolucions van separats: una devolució no és un cobrament, i
        # barrejar-los feia que un dia de devolucions SEPA es llegís com si s'hagués
        # cobrat en negatiu. El motiu de devolució i la remesa surten al detall.
        ActivitySource(
            key='payment_collections', category=CATEGORY_COLLECTIONS,
            label=_("Cobraments registrats"),
            model='billing.PaymentMovement', user_field='user', date_field='timestamp',
            token_paths=('token', 'payment.token'),
            contract_paths=('payment.contract.token', 'payment.invoice.contract.token'),
            detail_paths=('payment_type.name', 'payment_bank', 'current_status.name'),
            select_related=('payment', 'payment__contract', 'payment__invoice__contract',
                            'payment_type', 'current_status'),
            queryset_filter=lambda queryset: queryset.filter(is_positive=True),
            amount_aggregator=_collection_amounts,
            amount_resolver=_payment_movement_row_amount,
        ),
        ActivitySource(
            key='payment_returns', category=CATEGORY_COLLECTIONS,
            label=_("Devolucions de rebuts"),
            model='billing.PaymentMovement', user_field='user', date_field='timestamp',
            token_paths=('token', 'payment.token'),
            contract_paths=('payment.contract.token', 'payment.invoice.contract.token'),
            detail_paths=('reject_motive.name', 'payment_remittance.token', 'payment_type.name'),
            select_related=('payment', 'payment__contract', 'payment__invoice__contract',
                            'payment_type', 'current_status', 'reject_motive', 'payment_remittance'),
            queryset_filter=lambda queryset: queryset.filter(is_positive=False),
            amount_aggregator=_return_amounts,
            amount_resolver=_payment_movement_row_amount,
        ),
        # El cobrament massiu (la remesa SEPA) no deixa usuari a cada moviment de
        # rebut: els moviments de cobrament sense usuari els
        # escriu un procés automàtic. L'acció humana és enviar la remesa al banc, i
        # queda a `PaymentRemittance.sent_by`/`sent_at`: una fila per remesa amb el
        # nombre de rebuts i l'import, en lloc de milers de files sense amo.
        # L'import cobrat de la remesa (els rebuts en estat Pagat) suma a l'import
        # cobrat del dia: sense això, el cobrat només portava els cobraments manuals
        # de finestreta, una part ínfima del cobrat per remesa) i sortia absurdament baix.
        ActivitySource(
            key='remittances_sent', category=CATEGORY_COLLECTIONS,
            label=_("Remeses enviades a cobrament"),
            model='billing.PaymentRemittance', user_field='sent_by', date_field='sent_at',
            token_paths=('token',),
            select_related=('status', 'company_bank'),
            queryset_filter=lambda queryset: queryset.filter(is_return=False),
            amount_aggregator=_remittance_amounts,
            amount_resolver=_remittance_row_amount,
            detail_resolver=_remittance_row_detail,
        ),
        # Els fitxers de devolucions carregats. Sense import: les devolucions rebut a
        # rebut ja les compta `payment_returns` i sumar-hi també el total del fitxer
        # seria comptar dues vegades el mateix diner.
        ActivitySource(
            key='remittance_returns', category=CATEGORY_COLLECTIONS,
            label=_("Fitxers de devolucions carregats"),
            model='billing.PaymentRemittanceReturn', user_field='returned_by',
            date_field='created_at',
            token_paths=('token',),
            detail_resolver=_remittance_row_detail,
        ),
        ActivitySource(
            key='payment_status_changes', category=CATEGORY_COLLECTIONS,
            label=_("Altres canvis d'estat de rebuts"),
            model='logger.LogPaymentStatusChange', user_field='user', date_field='timestamp',
            token_paths=('object.token',),
            contract_paths=('object.contract.token', 'object.invoice.contract.token'),
            detail_paths=('current_status.name', 'observation'),
            select_related=('object', 'object__contract', 'object__invoice__contract', 'current_status'),
            queryset_filter=_exclude_movement_twins,
        ),
        ActivitySource(
            key='joined_payments', category=CATEGORY_COLLECTIONS,
            label=_("Pagaments agrupats creats"),
            model='billing.JoinedPayment', user_field='user', date_field='created_at',
            token_paths=('token',), contract_paths=('contract.token',),
            detail_paths=('status.name',),
            select_related=('contract', 'status'),
            amount_aggregator=_simple_amount_aggregator('amount'),
            amount_resolver=_simple_amount_resolver('amount'),
        ),
        ActivitySource(
            key='joined_payment_status_changes', category=CATEGORY_COLLECTIONS,
            label=_("Canvis d'estat de pagaments agrupats"),
            model='logger.LogJoinedPaymentStatusChange', user_field='user', date_field='timestamp',
            token_paths=('object.token',), contract_paths=('object.contract.token',),
            detail_paths=('current_status.name', 'observation'),
            select_related=('object', 'object__contract', 'current_status'),
        ),
        ActivitySource(
            key='commitment_deposit_movements', category=CATEGORY_COLLECTIONS,
            label=_("Moviments de compromís de pagament"),
            model='logger.LogCommitmentDepositMovement', user_field='user', date_field='timestamp',
            token_paths=('object.token',), contract_paths=('object.contract.token',),
            detail_paths=('current_status.name',),
            select_related=('object', 'object__contract', 'current_status'),
            amount_aggregator=_simple_amount_aggregator('used_remaining'),
            amount_resolver=_simple_amount_resolver('used_remaining'),
        ),
        ActivitySource(
            key='piggy_bank_movements', category=CATEGORY_COLLECTIONS,
            label=_("Moviments de guardiola"),
            model='contract.PiggyBankMovement', user_field='user', date_field='created_at',
            token_paths=('token',),
            detail_paths=('payment.token', 'bail.token'),
            select_related=('payment', 'bail'),
        ),
        ActivitySource(
            key='commitment_deposit_observations', category=CATEGORY_COLLECTIONS,
            label=_("Observacions de compromisos de pagament"),
            model='billing.CommitmentDepositObservation', user_field='user', date_field='created_at',
            token_paths=('commitment_deposit.token',),
            contract_paths=('commitment_deposit.contract.token',),
            detail_paths=('observation',),
            select_related=('commitment_deposit', 'commitment_deposit__contract'),
        ),
        ActivitySource(
            key='joined_payment_observations', category=CATEGORY_COLLECTIONS,
            label=_("Observacions de pagaments agrupats"),
            model='billing.JoinedPaymentObservation', user_field='user', date_field='created_at',
            token_paths=('joined_payment.token',),
            contract_paths=('joined_payment.contract.token',),
            detail_paths=('observation',),
            select_related=('joined_payment', 'joined_payment__contract'),
        ),

        # --- Ordres de treball ---------------------------------------------
        ActivitySource(
            key='orders_created', category=CATEGORY_ORDERS,
            label=_("Ordres de treball noves"),
            model='order.Order', user_field='created_by', date_field='created_at',
            token_paths=('token',), contract_paths=('contract.token',),
            detail_paths=('type.name', 'reason.name', 'status.name'),
            select_related=('contract', 'type', 'reason', 'status'),
        ),
        ActivitySource(
            key='order_status_changes', category=CATEGORY_ORDERS,
            label=_("Canvis d'estat d'ordres"),
            model='logger.LogOrderStatus', user_field='user', date_field='timestamp',
            token_paths=('object.token',), contract_paths=('object.contract.token',),
            detail_paths=('current_status.name', 'observation'),
            select_related=('object', 'object__contract', 'current_status'),
        ),
        ActivitySource(
            key='order_observations', category=CATEGORY_ORDERS,
            label=_("Observacions d'ordres"),
            model='order.OrderObservation', user_field='user', date_field='created_at',
            token_paths=('order.token',), contract_paths=('order.contract.token',),
            detail_paths=('observation',),
            select_related=('order', 'order__contract'),
        ),

        # --- Gestions de contracte -----------------------------------------
        ActivitySource(
            key='contract_request_status_changes', category=CATEGORY_CONTRACTS,
            label=_("Sol·licituds de contracte gestionades"),
            model='logger.LogContractRequestStatus', user_field='user', date_field='timestamp',
            token_paths=('object.token',),
            detail_paths=('current_status.name', 'observation'),
            select_related=('object', 'current_status'),
        ),
        ActivitySource(
            key='contract_data_changes', category=CATEGORY_CONTRACTS,
            label=_("Canvis de dades de contracte"),
            model='contract.ContractDataChange', user_field='user', date_field='created_at',
            token_paths=('token',), contract_paths=('contract.token',),
            detail_paths=('new_payment_type.name', 'new_language'),
            select_related=('contract', 'new_payment_type'),
        ),
        ActivitySource(
            key='contract_changes', category=CATEGORY_CONTRACTS,
            label=_("Altes, baixes i canvis de contracte"),
            model='logger.LogContractChange', user_field='user', date_field='timestamp',
            contract_paths=('contract.token',), token_paths=('contract.token',),
            detail_paths=('action', 'field_changed', 'observation'),
            select_related=('contract',),
        ),
        ActivitySource(
            key='contract_logs', category=CATEGORY_CONTRACTS,
            label=_("Modificacions de contracte"),
            model='contract.ContractLog', user_field='user', date_field='created_at',
            token_paths=('contract.token',), contract_paths=('contract.token',),
            detail_paths=('field_name',),
            select_related=('contract',),
        ),
        ActivitySource(
            key='contract_observations', category=CATEGORY_CONTRACTS,
            label=_("Observacions de contracte"),
            model='contract.ContractObservation', user_field='user', date_field='created_at',
            token_paths=('contract.token',), contract_paths=('contract.token',),
            detail_paths=('observation',),
            select_related=('contract',),
        ),
        ActivitySource(
            key='contract_request_observations', category=CATEGORY_CONTRACTS,
            label=_("Observacions de sol·licituds de contracte"),
            model='contract.ContractRequestObservation', user_field='user', date_field='created_at',
            token_paths=('contract_request.token',),
            detail_paths=('observation',),
            select_related=('contract_request',),
        ),
        ActivitySource(
            key='contract_termination_observations', category=CATEGORY_CONTRACTS,
            label=_("Observacions de baixes de contracte"),
            model='contract.ContractTerminationRequestObservation', user_field='user',
            date_field='created_at',
            token_paths=('contract_termination.token',),
            detail_paths=('observation',),
            select_related=('contract_termination',),
        ),
        ActivitySource(
            key='contract_members_changes', category=CATEGORY_CONTRACTS,
            label=_("Canvis de membres de convivència"),
            model='logger.LogContractTotalMembers', user_field='user', date_field='timestamp',
            token_paths=('object.token',), contract_paths=('object.token',),
            detail_paths=('observation',),
            select_related=('object',),
        ),
        ActivitySource(
            key='contract_phone_changes', category=CATEGORY_CONTRACTS,
            label=_("Canvis de telèfon de contracte"),
            model='logger.LogContractPhones', user_field='user', date_field='timestamp',
            token_paths=('object.token',), contract_paths=('object.token',),
            detail_paths=('current_phone',),
            select_related=('object',),
        ),
        ActivitySource(
            key='contract_bonification_changes', category=CATEGORY_CONTRACTS,
            label=_("Canvis de bonificacions i variables"),
            model='logger.LogContractBonificationsVariablesChange', user_field='user',
            date_field='timestamp',
            token_paths=('object.token',), contract_paths=('object.token',),
            detail_paths=('observation',),
            select_related=('object',),
        ),

        # --- Facturació -----------------------------------------------------
        ActivitySource(
            key='invoice_status_changes', category=CATEGORY_BILLING,
            label=_("Canvis d'estat de factures"),
            model='logger.LogInvoiceChangeStatus', user_field='user', date_field='timestamp',
            token_paths=('object.serie_final', 'object.token'),
            contract_paths=('object.contract.token',),
            detail_paths=('current_status.name', 'observation'),
            select_related=('object', 'object__contract', 'current_status'),
        ),
        ActivitySource(
            key='invoice_data_changes', category=CATEGORY_BILLING,
            label=_("Canvis de dades de factures"),
            model='logger.LogInvoiceDataChange', user_field='user', date_field='timestamp',
            token_paths=('object.serie_final', 'object.token'),
            contract_paths=('object.contract.token',),
            detail_paths=('observation',),
            select_related=('object', 'object__contract'),
        ),
        ActivitySource(
            key='invoice_logs', category=CATEGORY_BILLING,
            label=_("Modificacions de factures"),
            model='billing.InvoiceLog', user_field='user', date_field='created_at',
            token_paths=('invoice.serie_final', 'invoice.token'),
            contract_paths=('invoice.contract.token',),
            select_related=('invoice', 'invoice__contract'),
        ),
        ActivitySource(
            key='bail_status_changes', category=CATEGORY_BILLING,
            label=_("Canvis d'estat de fiances"),
            model='logger.LogBailStatus', user_field='user', date_field='timestamp',
            token_paths=('object.token',), contract_paths=('object.contract.token',),
            detail_paths=('current_status.name', 'observation'),
            select_related=('object', 'object__contract', 'current_status'),
        ),

        # --- Lectures -------------------------------------------------------
        ActivitySource(
            key='reading_changes', category=CATEGORY_READINGS,
            label=_("Canvis de lectura"),
            model='logger.LogReadingChange', user_field='user', date_field='timestamp',
            token_paths=('meter.code', 'contract.token'),
            contract_paths=('contract.token',),
            detail_paths=('observation',),
            select_related=('meter', 'contract'),
        ),
        ActivitySource(
            key='meter_logs', category=CATEGORY_READINGS,
            label=_("Modificacions de comptadors"),
            model='service.MeterLog', user_field='user', date_field='created_at',
            token_paths=('meter.code',),
            detail_paths=('field_name',),
            select_related=('meter',),
        ),

        # --- Comunicacions i atenció ---------------------------------------
        ActivitySource(
            key='call_registers', category=CATEGORY_COMMUNICATIONS,
            label=_("Trucades registrades"),
            model='coredata.CallRegister', user_field='user', date_field='created_at',
            token_paths=('token',), contract_paths=('contract.token',),
            detail_paths=('comment',),
            select_related=('contract',),
        ),
        ActivitySource(
            key='communications_created', category=CATEGORY_COMMUNICATIONS,
            label=_("Comunicacions creades"),
            model='communication.Communication', user_field='user', date_field='created_at',
            token_paths=('token',),
            detail_paths=('use_type.name', 'status.name'),
            select_related=('use_type', 'status'),
        ),
        ActivitySource(
            key='communication_processes', category=CATEGORY_COMMUNICATIONS,
            label=_("Processos de comunicació creats"),
            model='communication.CommunicationProcess', user_field='user', date_field='created_at',
            token_paths=('token',),
            detail_paths=('use_type.name', 'status.name'),
            select_related=('use_type', 'status'),
        ),
        ActivitySource(
            key='communication_status_changes', category=CATEGORY_COMMUNICATIONS,
            label=_("Canvis d'estat de comunicacions"),
            model='logger.LogCommunicationStatusChange', user_field='user', date_field='timestamp',
            token_paths=('object.token',),
            detail_paths=('current_status.name', 'observation'),
            select_related=('object', 'current_status'),
        ),
        ActivitySource(
            key='communication_process_status_changes', category=CATEGORY_COMMUNICATIONS,
            label=_("Canvis d'estat de processos de comunicació"),
            model='logger.LogCommunicationProcessStatusChange', user_field='user',
            date_field='timestamp',
            token_paths=('object.token',),
            detail_paths=('current_status.name', 'observation'),
            select_related=('object', 'current_status'),
        ),
        ActivitySource(
            key='communication_changes', category=CATEGORY_COMMUNICATIONS,
            label=_("Canvis de canal de comunicacions"),
            model='logger.LogCommunicationChange', user_field='user', date_field='timestamp',
            token_paths=('object.token',),
            detail_paths=('observation',),
            select_related=('object',),
        ),
        ActivitySource(
            key='communication_observations', category=CATEGORY_COMMUNICATIONS,
            label=_("Observacions de comunicacions"),
            model='communication.CommunicationObservation', user_field='user', date_field='created_at',
            token_paths=('communication.token',),
            detail_paths=('observation',),
            select_related=('communication',),
        ),
        ActivitySource(
            key='communication_process_observations', category=CATEGORY_COMMUNICATIONS,
            label=_("Observacions de processos de comunicació"),
            model='communication.CommunicationProcessObservation', user_field='user',
            date_field='created_at',
            token_paths=('process.token',),
            detail_paths=('observation',),
            select_related=('process',),
        ),

        # --- Impagats, incidències i fraus ---------------------------------
        ActivitySource(
            key='claim_requests', category=CATEGORY_CLAIMS,
            label=_("Gestions d'impagats creades"),
            model='claimrequest.ClaimRequest', user_field='user', date_field='created_at',
            token_paths=('token',),
            detail_paths=('status.name', 'current_step.name'),
            select_related=('status', 'current_step'),
        ),
        ActivitySource(
            key='claim_request_changes', category=CATEGORY_CLAIMS,
            label=_("Moviments de gestions d'impagats"),
            model='logger.LogClaimRequestContractChange', user_field='user', date_field='created_at',
            token_paths=('object.token',),
            contract_paths=('deleted_contract.token',),
            detail_paths=('current_status.name',),
            select_related=('object', 'deleted_contract', 'current_status'),
            amount_aggregator=_simple_amount_aggregator('amount_paid'),
            amount_resolver=_simple_amount_resolver('amount_paid'),
        ),
        ActivitySource(
            key='vulnerability_request_observations', category=CATEGORY_CLAIMS,
            label=_("Observacions de sol·licituds de vulnerabilitat"),
            model='claimrequest.VulnerabilityRequestObservation', user_field='user',
            date_field='created_at',
            token_paths=('vulnerability_request.token',),
            detail_paths=('observation',),
            select_related=('vulnerability_request',),
        ),
        ActivitySource(
            key='incident_status_changes', category=CATEGORY_CLAIMS,
            label=_("Canvis d'estat d'incidències"),
            model='logger.LogIncidentStatusChange', user_field='user', date_field='timestamp',
            token_paths=('object.token',),
            detail_paths=('current_status.name', 'observation'),
            select_related=('object', 'current_status'),
        ),
        ActivitySource(
            key='incident_reports', category=CATEGORY_CLAIMS,
            label=_("Informes d'incidència"),
            model='notification.IncidentReport', user_field='user', date_field='created_at',
            token_paths=('token', 'incident.token'),
            select_related=('incident',),
        ),
        ActivitySource(
            key='incident_observations', category=CATEGORY_CLAIMS,
            label=_("Observacions d'incidències"),
            model='notification.IncidentObservation', user_field='user', date_field='created_at',
            token_paths=('incident.token',),
            detail_paths=('observation',),
            select_related=('incident',),
        ),
        ActivitySource(
            key='fraud_status_changes', category=CATEGORY_CLAIMS,
            label=_("Canvis d'estat de fraus"),
            model='logger.LogFraudStatusChange', user_field='user', date_field='timestamp',
            token_paths=('object.token',),
            detail_paths=('current_status.name', 'observation'),
            select_related=('object', 'current_status'),
        ),
        ActivitySource(
            key='fraud_reports', category=CATEGORY_CLAIMS,
            label=_("Informes de frau"),
            model='fraud.FraudReport', user_field='user', date_field='created_at',
            token_paths=('token', 'fraud.token'),
            select_related=('fraud',),
        ),
        ActivitySource(
            key='fraud_observations', category=CATEGORY_CLAIMS,
            label=_("Observacions de fraus"),
            model='fraud.FraudObservation', user_field='user', date_field='created_at',
            token_paths=('fraud.token',),
            detail_paths=('observation',),
            select_related=('fraud',),
        ),

        # --- Servei i infraestructura --------------------------------------
        ActivitySource(
            key='supply_point_changes', category=CATEGORY_SERVICE,
            label=_("Canvis de punt de subministrament"),
            model='logger.LogSupplyPointChange', user_field='user', date_field='timestamp',
            token_paths=('supply_point.token',),
            detail_paths=('action', 'field_changed', 'observation'),
            select_related=('supply_point',),
        ),
        ActivitySource(
            key='supply_point_observations', category=CATEGORY_SERVICE,
            label=_("Observacions de punts de subministrament"),
            model='service.SupplyPointObservation', user_field='user', date_field='created_at',
            token_paths=('supply_point.token',),
            detail_paths=('observation',),
            select_related=('supply_point',),
        ),
        ActivitySource(
            key='connection_status_changes', category=CATEGORY_SERVICE,
            label=_("Canvis d'estat d'escomeses"),
            model='logger.LogConnectionStatus', user_field='user', date_field='timestamp',
            token_paths=('object.token',),
            detail_paths=('current_status.name', 'observation'),
            select_related=('object', 'current_status'),
        ),
        ActivitySource(
            key='connection_request_status_changes', category=CATEGORY_SERVICE,
            label=_("Canvis d'estat de sol·licituds d'escomesa"),
            model='logger.LogConnectionRequestStatus', user_field='user', date_field='timestamp',
            token_paths=('object.token',),
            detail_paths=('current_status.name', 'observation'),
            select_related=('object', 'current_status'),
        ),
        ActivitySource(
            key='connection_observations', category=CATEGORY_SERVICE,
            label=_("Observacions d'escomeses"),
            model='service.ConnectionObservation', user_field='user', date_field='created_at',
            token_paths=('connection.token',),
            detail_paths=('observation',),
            select_related=('connection',),
        ),
        ActivitySource(
            key='connection_request_observations', category=CATEGORY_SERVICE,
            label=_("Observacions de sol·licituds d'escomesa"),
            model='service.ConnectionRequestObservation', user_field='user', date_field='created_at',
            token_paths=('connection_request.token',),
            detail_paths=('observation',),
            select_related=('connection_request',),
        ),
        ActivitySource(
            key='cluster_status_changes', category=CATEGORY_SERVICE,
            label=_("Canvis d'estat de bateries"),
            model='logger.LogClusterStatus', user_field='user', date_field='timestamp',
            token_paths=('object.token',),
            detail_paths=('current_status.name', 'observation'),
            select_related=('object', 'current_status'),
        ),
        ActivitySource(
            key='cluster_nozzle_status_changes', category=CATEGORY_SERVICE,
            label=_("Canvis d'estat de boquilles"),
            model='logger.LogClusterNozzleStatus', user_field='user', date_field='timestamp',
            token_paths=('object.token',),
            detail_paths=('current_status.name', 'observation'),
            select_related=('object', 'current_status'),
        ),
        ActivitySource(
            key='cluster_observations', category=CATEGORY_SERVICE,
            label=_("Observacions de bateries"),
            model='service.ClusterObservation', user_field='user', date_field='created_at',
            token_paths=('cluster.token',),
            detail_paths=('observation',),
            select_related=('cluster',),
        ),
        ActivitySource(
            key='supply_cut_status_changes', category=CATEGORY_SERVICE,
            label=_("Canvis d'estat de talls de subministrament"),
            model='logger.LogSupplyCutStatus', user_field='user', date_field='timestamp',
            token_paths=('object.token',),
            detail_paths=('current_status.name', 'observation'),
            select_related=('object', 'current_status'),
        ),
        ActivitySource(
            key='supply_cut_observations', category=CATEGORY_SERVICE,
            label=_("Observacions de talls de subministrament"),
            model='service.SupplyCutObservation', user_field='user', date_field='created_at',
            token_paths=('supply_cut.token',),
            detail_paths=('observation',),
            select_related=('supply_cut',),
        ),

        # --- Productes i tarifes -------------------------------------------
        ActivitySource(
            key='product_changes', category=CATEGORY_PRICING,
            label=_("Canvis de productes"),
            model='logger.LogProductChange', user_field='user', date_field='timestamp',
            token_paths=('object.name',),
            detail_paths=('changed_field',),
            select_related=('object',),
        ),
        ActivitySource(
            key='price_rate_changes', category=CATEGORY_PRICING,
            label=_("Canvis de tarifes"),
            model='logger.LogPriceRateChange', user_field='user', date_field='timestamp',
            token_paths=('object.name',),
            detail_paths=('line_item_type_name', 'changed_field'),
            select_related=('object',),
        ),

        # --- Altres ---------------------------------------------------------
        ActivitySource(
            key='general_notes', category=CATEGORY_OTHER,
            label=_("Notes generals"),
            model='notification.GeneralNote', user_field='user', date_field='created_at',
            token_paths=('token',),
            detail_paths=('note',),
        ),
    ]


# ---------------------------------------------------------------------------
# Resolució de camins
# ---------------------------------------------------------------------------

def _resolve_path(obj, path):
    """`obj.a.b.c` tolerant a nuls i a atributs inexistents (retorna None)."""
    current = obj
    for part in path.split('.'):
        if current is None:
            return None
        current = getattr(current, part, None)
    return current


def _resolve_first(obj, paths):
    for path in paths:
        value = _resolve_path(obj, path)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return None


def _resolve_detail(obj, paths, max_length=200):
    """Concatena els camins de detall que tenen valor, separats per ' · '."""
    parts = []
    for path in paths:
        value = _resolve_path(obj, path)
        if value is None:
            continue
        text = ' '.join(str(value).split())
        if text and text not in parts:
            parts.append(text)
    detail = ' · '.join(parts)
    if len(detail) > max_length:
        detail = detail[:max_length - 1] + '…'
    return detail or None


def _user_display(user):
    if user is None:
        return None
    full_name = f"{user.first_name or ''} {user.last_name or ''}".strip()
    return full_name or user.username


# ---------------------------------------------------------------------------
# Càlcul
# ---------------------------------------------------------------------------

def parse_activity_dates(date_from=None, date_to=None):
    """Normalitza el rang de dates. Sense res, el dia d'avui.

    Accepta 'YYYY-MM-DD' i també les cadenes ISO amb hora que envia el frontal
    (`2026-09-08T00:00:00.000Z`), de les quals només es queda la part de la data.
    """
    def to_date(value):
        if value in (None, ''):
            return None
        if isinstance(value, datetime.datetime):
            return value.date()
        if isinstance(value, datetime.date):
            return value
        text = str(value)[:10]
        try:
            return datetime.date.fromisoformat(text)
        except ValueError:
            return None

    start = to_date(date_from)
    end = to_date(date_to)
    today = timezone.localdate()
    if start is None and end is None:
        return today, today
    if start is None:
        start = end
    if end is None:
        end = start
    if start > end:
        start, end = end, start
    return start, end


def build_daily_activity(user_ids, date_from=None, date_to=None, include_details=True,
                         source_detail_limit=SCREEN_SOURCE_DETAIL_LIMIT,
                         timeline_limit=SCREEN_TIMELINE_LIMIT, progress_callback=None):
    """Resum d'activitat de `user_ids` entre dues dates (incloses).

    Retorna un diccionari amb les claus `date_from`, `date_to`, `users`, `totals`,
    `categories` (amb les fonts a dins), `by_user` i `timeline`. Els comptadors
    surten d'un `values(user).annotate(Count)` per font — una consulta per font,
    no per usuari — i la cronologia només es munta si `include_details`.
    """
    date_from, date_to = parse_activity_dates(date_from, date_to)
    user_ids = [int(uid) for uid in user_ids]
    users = list(User.objects.filter(id__in=user_ids).order_by('username'))
    users_by_id = {user.id: user for user in users}

    category_labels = get_category_labels()
    sources = get_activity_sources()

    # {category: {'count': n, 'sources': {source_key: {...}}}}
    category_data = {
        key: {'key': key, 'label': category_labels[key], 'count': 0, 'amounts': {}, 'sources': []}
        for key in CATEGORY_ORDER
    }
    per_user_counts = {user_id: {'total': 0, 'categories': {}} for user_id in user_ids}
    timeline = []
    totals = {'total_actions': 0}

    total_sources = len(sources)
    for index, source in enumerate(sources, start=1):
        if progress_callback:
            progress_callback(index, total_sources)

        queryset = source.queryset(user_ids, date_from, date_to)

        counts_by_user = {
            row[source.user_field]: row['activity_count']
            for row in queryset.values(source.user_field).annotate(activity_count=Count('id'))
        }
        source_count = sum(counts_by_user.values())
        if source_count == 0:
            continue

        source_entry = {
            'key': source.key,
            'label': source.label,
            'category': source.category,
            'count': source_count,
            'amounts': {},
            'counts_by_user': {int(uid): count for uid, count in counts_by_user.items() if uid},
        }

        if source.amount_aggregator:
            amounts = source.amount_aggregator(queryset)
            source_entry['amounts'] = amounts
            for amount_key, amount_value in amounts.items():
                category_data[source.category]['amounts'][amount_key] = (
                    category_data[source.category]['amounts'].get(amount_key, 0) + amount_value
                )

        category_data[source.category]['count'] += source_count
        category_data[source.category]['sources'].append(source_entry)
        totals['total_actions'] += source_count

        for user_id, count in counts_by_user.items():
            if not user_id:
                continue
            bucket = per_user_counts.setdefault(user_id, {'total': 0, 'categories': {}})
            bucket['total'] += count
            bucket['categories'][source.category] = bucket['categories'].get(source.category, 0) + count

        if not include_details:
            continue

        detail_queryset = queryset.order_by(f'-{source.date_field}')
        if source.select_related:
            detail_queryset = detail_queryset.select_related(*source.select_related)
        for obj in detail_queryset[:source_detail_limit]:
            occurred_at = getattr(obj, source.date_field, None)
            user = getattr(obj, source.user_field, None)
            amount = source.amount_resolver(obj) if source.amount_resolver else None
            timeline.append({
                'occurred_at': occurred_at,
                'category': source.category,
                'category_label': category_labels[source.category],
                'source': source.key,
                'source_label': source.label,
                'user_id': getattr(user, 'id', None),
                'user': _user_display(user),
                'reference': _resolve_first(obj, source.token_paths),
                'contract': _resolve_first(obj, source.contract_paths),
                'detail': (source.detail_resolver(obj) if source.detail_resolver
                           else _resolve_detail(obj, source.detail_paths)),
                'amount': amount,
            })

    # Els cobraments són el que més es mira del dia: es pugen als totals generals.
    # `collections_count` compta només els cobraments i `returns_count` només les
    # devolucions: sumar-los en un únic comptador "Cobraments" feia que un dia de
    # devolucions SEPA semblés un dia de molta caixa.
    collections = category_data[CATEGORY_COLLECTIONS]
    source_counts = {source['key']: source['count'] for source in collections['sources']}
    totals['collections_count'] = source_counts.get('payment_collections', 0)
    totals['returns_count'] = source_counts.get('payment_returns', 0)
    totals['remittances_sent_count'] = source_counts.get('remittances_sent', 0)
    totals['remittance_returns_count'] = source_counts.get('remittance_returns', 0)
    totals['collections_remitted'] = collections['amounts'].get('remitted', 0)
    # Les dues parts de l'import cobrat, perquè la pantalla pugui ensenyar d'on surt:
    # el cobrat NO és el remès (part d'una remesa acaba retornada, abonada o en
    # compromís de pagament i no s'ha cobrat mai) més els manuals, sinó la part de
    # la remesa que ha quedat en estat Pagat més els manuals.
    source_amounts = {source['key']: source['amounts'] for source in collections['sources']}
    totals['collections_charged_remittances'] = source_amounts.get('remittances_sent', {}).get('charged', 0)
    totals['collections_charged_manual'] = source_amounts.get('payment_collections', {}).get('charged', 0)
    totals['collections_charged'] = collections['amounts'].get('charged', 0)
    totals['collections_returned'] = collections['amounts'].get('returned', 0)
    totals['collections_net'] = collections['amounts'].get('net', 0)
    totals['orders_count'] = category_data[CATEGORY_ORDERS]['count']
    totals['contracts_count'] = category_data[CATEGORY_CONTRACTS]['count']

    # Ordenem la cronologia de més recent a més antic. Les dates poden ser `date`
    # (PaymentMovement.movement_date) o `datetime`, i no es poden comparar entre
    # elles: la clau normalitza a datetime amb zona.
    def sort_key(entry):
        occurred_at = entry['occurred_at']
        if isinstance(occurred_at, datetime.datetime):
            if timezone.is_naive(occurred_at):
                return timezone.make_aware(occurred_at)
            return occurred_at
        if isinstance(occurred_at, datetime.date):
            return timezone.make_aware(datetime.datetime.combine(occurred_at, datetime.time.min))
        return timezone.make_aware(datetime.datetime.min)

    timeline.sort(key=sort_key, reverse=True)
    timeline_truncated = len(timeline) > timeline_limit
    timeline = timeline[:timeline_limit]

    categories = [
        category_data[key] for key in CATEGORY_ORDER if category_data[key]['count'] > 0
    ]
    for category in categories:
        category['sources'].sort(key=lambda source: source['count'], reverse=True)

    by_user = []
    for user in users:
        bucket = per_user_counts.get(user.id, {'total': 0, 'categories': {}})
        by_user.append({
            'id': user.id,
            'username': user.username,
            'name': _user_display(user),
            'total': bucket['total'],
            'categories': bucket['categories'],
        })
    by_user.sort(key=lambda item: item['total'], reverse=True)

    return {
        'date_from': date_from,
        'date_to': date_to,
        'users': [
            {'id': user.id, 'username': user.username, 'name': _user_display(user)}
            for user in users
        ],
        'missing_user_ids': [uid for uid in user_ids if uid not in users_by_id],
        'totals': totals,
        'categories': categories,
        'by_user': by_user,
        'timeline': timeline,
        'timeline_truncated': timeline_truncated,
    }


# ---------------------------------------------------------------------------
# Excel
# ---------------------------------------------------------------------------

def _format_moment(value):
    """Data i hora sense zona, tal com espera openpyxl per escriure-ho com a data."""
    if isinstance(value, datetime.datetime):
        if timezone.is_aware(value):
            value = timezone.localtime(value)
        return value.replace(tzinfo=None)
    return value


def generate_daily_activity_summary_report(request, black_fill=None, white_bold_font=None, task=None):
    """Excel del resum d'activitat diària.

    Payload: `user_ids` (o `user_id`), `date_from`/`date_to` (o `date_range`, o `date`),
    `name` i `type_id`. Els usuaris els resol i els valida la vista abans d'encolar la
    tasca: aquí ja arriben decidits, perquè dins de Celery no hi ha `request.user`.
    """
    try:
        data = request.data or {}
        name = data.get('name') or _("Resum d'activitat diària")
        type_id = data.get('type_id')

        user_ids = data.get('user_ids') or ([data.get('user_id')] if data.get('user_id') else [])
        user_ids = [int(uid) for uid in user_ids if uid]
        if not user_ids:
            return None, None, None

        date_range = data.get('date_range')
        if date_range and isinstance(date_range, (list, tuple)) and len(date_range) >= 2:
            date_from, date_to = date_range[0], date_range[1]
        else:
            date_from = data.get('date_from') or data.get('date')
            date_to = data.get('date_to') or data.get('date')

        def report_progress(current, total):
            if task:
                task.update_state(state='PROGRESS', meta={
                    'current': current,
                    'total': total,
                    'percent': round((current / total) * 100, 2) if total else 0.0,
                })

        activity = build_daily_activity(
            user_ids, date_from, date_to,
            include_details=True,
            source_detail_limit=REPORT_SOURCE_DETAIL_LIMIT,
            timeline_limit=REPORT_TIMELINE_LIMIT,
            progress_callback=report_progress,
        )

        workbook = openpyxl.Workbook()
        summary_sheet = workbook.active
        summary_sheet.title = _("Resum")

        row = 0
        row = add_row(summary_sheet, row, [_("Resum d'activitat diària")], fill=black_fill, font=white_bold_font)
        row = add_row(summary_sheet, row, [
            _("Període"),
            activity['date_from'].strftime('%d/%m/%Y'),
            activity['date_to'].strftime('%d/%m/%Y'),
        ])
        row = add_row(summary_sheet, row, [
            _("Usuaris"),
            ', '.join(user['name'] or user['username'] for user in activity['users']) or '-',
        ])
        row = jump_row(row)

        totals = activity['totals']
        row = add_row(summary_sheet, row, [_("Totals")], fill=black_fill, font=white_bold_font)
        row = add_row(summary_sheet, row, [_("Accions registrades"), totals['total_actions']])
        row = add_row(summary_sheet, row, [_("Cobraments manuals"), totals['collections_count']])
        row = add_row(summary_sheet, row, [_("Devolucions"), totals['returns_count']])
        row = add_row(summary_sheet, row, [_("Remeses enviades a cobrament"), totals['remittances_sent_count']])
        row = add_row(summary_sheet, row, [_("Fitxers de devolucions carregats"), totals['remittance_returns_count']])
        row = add_row(summary_sheet, row, [_("Import remès al banc"), totals['collections_remitted']])
        row = add_row(summary_sheet, row, [_("Import cobrat (manual + remesa)"), totals['collections_charged']])
        row = add_row(summary_sheet, row, [_("  del qual, cobrat per remesa"), totals['collections_charged_remittances']])
        row = add_row(summary_sheet, row, [_("  del qual, cobrat manualment"), totals['collections_charged_manual']])
        row = add_row(summary_sheet, row, [_("Import retornat"), totals['collections_returned']])
        row = add_row(summary_sheet, row, [_("Import net (cobrat + retornat)"), totals['collections_net']])
        row = add_row(summary_sheet, row, [_("Ordres de treball"), totals['orders_count']])
        row = add_row(summary_sheet, row, [_("Gestions de contracte"), totals['contracts_count']])
        row = jump_row(row)

        row = add_row(summary_sheet, row, [
            _("Categoria"), _("Acció"), _("Nombre"), _("Import"),
        ], fill=black_fill, font=white_bold_font)
        for category in activity['categories']:
            row = add_row(summary_sheet, row, [
                category['label'], '', category['count'],
                category['amounts'].get('net', ''),
            ], font=white_bold_font, fill=black_fill)
            for source in category['sources']:
                row = add_row(summary_sheet, row, [
                    '', source['label'], source['count'],
                    source['amounts'].get('net', ''),
                ])

        # Matriu per usuari: només té sentit quan l'informe agrupa més d'un usuari.
        if len(activity['users']) > 1:
            row = jump_row(row)
            category_labels = get_category_labels()
            visible_categories = [category['key'] for category in activity['categories']]
            row = add_row(summary_sheet, row, [_("Usuari"), _("Total")] + [
                category_labels[key] for key in visible_categories
            ], fill=black_fill, font=white_bold_font)
            for user in activity['by_user']:
                row = add_row(summary_sheet, row, [
                    user['name'] or user['username'], user['total'],
                ] + [user['categories'].get(key, 0) for key in visible_categories])

        detail_sheet = workbook.create_sheet(title=_("Detall"))
        add_row(detail_sheet, 0, [
            _("Data i hora"), _("Usuari"), _("Categoria"), _("Acció"),
            _("Referència"), _("Contracte"), _("Detall"), _("Import"),
        ], fill=black_fill, font=white_bold_font)
        detail_row = 1
        for entry in activity['timeline']:
            add_row(detail_sheet, detail_row, [
                _format_moment(entry['occurred_at']),
                entry['user'] or '',
                entry['category_label'],
                entry['source_label'],
                entry['reference'] or '',
                entry['contract'] or '',
                entry['detail'] or '',
                entry['amount'] if entry['amount'] is not None else '',
            ])
            detail_row += 1

        adjust_column_widths(summary_sheet)
        adjust_column_widths(detail_sheet)

        filename = (
            f"report_activitat_diaria_"
            f"{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        )
        document_id = save_report(
            content=workbook, filename=filename, name=name, type_id=type_id,
            start_date=activity['date_from'], end_date=activity['date_to'],
        )
        return None, document_id, filename
    except Exception as error:
        print(f"Error in generate_daily_activity_summary_report: {error}")
        traceback.print_exc()
        return None, None, None
