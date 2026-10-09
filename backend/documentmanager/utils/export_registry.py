"""
Registre entity -> ExportConfig per a la vista d'exportació genèrica
(documentmanager/views_export/generic_export_view.py) i la task genèrica
(documentmanager/tasks.py: generic_export_task).

Cada entrada reutilitza el FilterSet i els permission_classes que ja fa
servir el ViewSet CRUD d'aquell recurs, per no duplicar-los.
"""
from dataclasses import dataclass
from typing import Callable, Dict, List, Tuple

from django.db.models import Count
from django.utils.translation import gettext as _


@dataclass
class ExportConfig:
    queryset: Callable  # () -> QuerySet base
    filterset_class: type
    permission_classes: list
    # catàleg de columnes disponibles: {key: (header, lambda obj: value)}
    available_columns: Dict[str, Tuple[str, Callable]]
    # ordre/subconjunt per defecte quan el front no especifica `columns`
    default_columns: List[str]
    document_entity: str  # valor per al camp `entity` de documentmanager.Document
    default_ordering: str = None
    service_key: str = None  # key a settings.DOCUMENT_MANAGER_SERVICES; per defecte, l'entity

    def resolve_columns(self, requested_keys=None):
        """
        requested_keys: llista ordenada de keys demanades pel front (query param
        `columns=token,number,total_final`). Claus desconegudes s'ignoren.
        Si no se'n demana cap (o totes són desconegudes), fa servir default_columns.
        """
        from documentmanager.utils.generic_export_service import resolve_columns
        return resolve_columns(self.available_columns, self.default_columns, requested_keys)


def _invoice_config():
    from rest_framework.permissions import IsAuthenticated
    from billing.models import Invoice
    from billing.filter.invoice_filter import InvoiceFilter
    from documentmanager.utils.export_permissions import export_permission_class

    available_columns = {
        "token": (_("Token"), lambda i: i.token or ""),
        "number": (_("Número"), lambda i: i.number or ""),
        "contract": (_("Contracte"), lambda i: i.contract.token if i.contract else ""),
        "customer": (_("Client"), lambda i: i.customer_final or ""),
        "customer_token": (_("Token client"), lambda i: i.customer_token_final or ""),
        "status": (_("Estat"), lambda i: i.status.name if i.status else ""),
        "issue_date": (_("Data emissió"), lambda i: i.issue_date.strftime("%Y-%m-%d") if i.issue_date else ""),
        "due_date": (_("Data venciment"), lambda i: i.due_date.strftime("%Y-%m-%d") if i.due_date else ""),
        "total_final": (_("Total"), lambda i: i.total_final if i.total_final is not None else ""),
        "left_to_pay": (_("Pendent"), lambda i: i.left_to_pay if i.left_to_pay is not None else ""),
        "serie": (_("Sèrie"), lambda i: i.serie_final or ""),
        "payment_type": (_("Forma de pagament"), lambda i: i.payment_type.name if i.payment_type else ""),
        "payment_bank": (_("Banc de pagament"), lambda i: i.payment_bank_final or ""),
        "origin": (_("Origen"), lambda i: i.origin.name if i.origin else ""),
    }

    return ExportConfig(
        # select_related: sense ell, cada columna FK feia una consulta per fila
        # (unes 4 per factura amb totes les columnes; ~2 min per 73k factures).
        queryset=lambda: Invoice.objects.all().filter(is_active=True).select_related(
            "contract", "status", "payment_type", "origin",
        ),
        filterset_class=InvoiceFilter,
        permission_classes=[IsAuthenticated, export_permission_class('billing', 'invoice')],
        available_columns=available_columns,
        default_columns=[
            "token", "number", "contract", "customer", "status",
            "issue_date", "due_date", "total_final", "left_to_pay",
        ],
        document_entity="INVOICE",
        default_ordering="-issue_date",
        service_key="billing",
    )


def _property_config():
    from rest_framework.permissions import IsAuthenticated
    from service.models import Property
    from service.filters.property_filter import PropertyFilter
    from documentmanager.utils.export_permissions import export_permission_class

    def _route_position(p):
        rp = p.route_position
        if not rp:
            return ""
        return f"{rp.route.token if rp.route else ''} - {rp.position if rp.position is not None else ''}".strip(" -")

    available_columns = {
        "token": (_("Token"), lambda p: p.token or ""),
        "name": (_("Nom"), lambda p: p.name or ""),
        "city": (_("Municipi"), lambda p: p.address_city.name if p.address_city else ""),
        "cadastral": (_("Cadastral"), lambda p: p.cadastral or ""),
        "total_supply_points": (_("Núm. Punts de Subministrament"), lambda p: p.total_supply_points_export),
        "route_position": (_("Ruta - Posició"), _route_position),
    }

    return ExportConfig(
        queryset=lambda: Property.objects.filter(is_active=True).select_related(
            "address_city", "route_position", "route_position__route",
        ).annotate(total_supply_points_export=Count("supply_points", distinct=True)),
        filterset_class=PropertyFilter,
        permission_classes=[IsAuthenticated, export_permission_class('service', 'property')],
        available_columns=available_columns,
        default_columns=list(available_columns.keys()),
        document_entity="PROPERTY",
        default_ordering="token",
        service_key="connection",
    )


def _meter_config():
    from rest_framework.permissions import IsAuthenticated
    from service.models import Meter
    from service.filters.meter_filter import MeterFilter
    from documentmanager.utils.export_permissions import export_permission_class

    # `.first()` ordena per pk i ignora el prefetch (SupplyPoint no té Meta.ordering):
    # feia 2 consultes per comptador més les de connection/exploitation. Agafem el
    # de pk més baix de la llista ja precarregada, que és el mateix que tornava .first().
    def _first_sp(m):
        sps = list(m.supply_points.all())
        return min(sps, key=lambda sp: sp.pk) if sps else None

    def _first_supply_point(m):
        sp = _first_sp(m)
        return sp.token if sp else ""

    def _exploitation(m):
        sp = _first_sp(m)
        if sp and sp.connection and sp.connection.exploitation:
            return sp.connection.exploitation.name
        return ""

    available_columns = {
        "code": (_("Codi"), lambda m: m.code or ""),
        "supply_point": (_("Punt de Subministrament"), _first_supply_point),
        "exploitation": (_("Explotació"), _exploitation),
        "status": (_("Estat"), lambda m: m.status.name if m.status else ""),
        "installation_at": (_("Data instal·lació"), lambda m: m.installation_at.strftime("%Y-%m-%d") if m.installation_at else ""),
        "uninstallation_at": (_("Data desinstal·lació"), lambda m: m.uninstallation_at.strftime("%Y-%m-%d") if m.uninstallation_at else ""),
        "has_remote_reading": (_("Telelectura"), lambda m: "Sí" if m.has_remote_reading else "No"),
        "manufacturer": (_("Fabricant"), lambda m: m.manufacturer or ""),
        "manufacturing_year": (_("Any fabricació"), lambda m: m.manufacturing_year if m.manufacturing_year is not None else ""),
        "comm_technology": (_("Tecnologia comunicació"), lambda m: m.comm_technology or ""),
        "caliber": (_("Calibre"), lambda m: m.caliber.name if m.caliber else ""),
    }

    return ExportConfig(
        queryset=lambda: Meter.objects.filter(is_active=True).select_related(
            "status", "caliber",
        ).prefetch_related("supply_points__connection__exploitation"),
        filterset_class=MeterFilter,
        permission_classes=[IsAuthenticated, export_permission_class('service', 'meter')],
        available_columns=available_columns,
        default_columns=list(available_columns.keys()),
        document_entity="METER",
        default_ordering="code",
        service_key="connection",
    )


def _supply_point_config():
    from rest_framework.permissions import IsAuthenticated
    from service.models import SupplyPoint
    from service.filters.supply_point_filter import SupplyPointFilter
    from documentmanager.utils.export_permissions import export_permission_class

    def _route_position(sp):
        rp = sp.property.route_position if sp.property else None
        if not rp:
            return ""
        return f"{rp.route.token if rp.route else ''} - {rp.position if rp.position is not None else ''}".strip(" -")

    def _cluster_nozzle(sp):
        return sp.cluster_nozzle.token if sp.cluster_nozzle else ""

    available_columns = {
        "token": (_("Token"), lambda sp: sp.token or ""),
        "address_complete": (_("Adreça"), lambda sp: str(sp.address) if sp.address else ""),
        "address_city": (_("Municipi"), lambda sp: sp.address.city.name if sp.address and sp.address.city else ""),
        "type": (_("Tipus"), lambda sp: sp.type.name if sp.type else ""),
        "status": (_("Estat"), lambda sp: sp.status.name if sp.status else ""),
        "is_potable": (_("Potable"), lambda sp: "Sí" if sp.is_potable else "No"),
        "property_route_position": (_("Ruta - Posició"), _route_position),
        "meter": (_("Comptador"), lambda sp: sp.meter.code if sp.meter else ""),
        "cluster_nozzle": (_("Broquet"), _cluster_nozzle),
        "connection": (_("Escomesa"), lambda sp: sp.connection.token if sp.connection else ""),
        "connection_exploitation": (_("Explotació"), lambda sp: sp.connection.exploitation.name if sp.connection and sp.connection.exploitation else ""),
    }

    return ExportConfig(
        # Tota la cadena que llegeix str(Address): sense ella eren 5 consultes per fila.
        queryset=lambda: SupplyPoint.objects.filter(is_active=True).select_related(
            "address", "address__city", "address__country",
            "address__street", "address__street__type",
            "address__street_number", "address__street_number__number_type",
            "type", "status", "meter",
            "cluster_nozzle", "connection", "connection__exploitation",
            "property", "property__route_position", "property__route_position__route",
        ),
        filterset_class=SupplyPointFilter,
        permission_classes=[IsAuthenticated, export_permission_class('service', 'supplypoint')],
        available_columns=available_columns,
        default_columns=list(available_columns.keys()),
        document_entity="SUPPLY_POINT",
        default_ordering="token",
        service_key="connection",  # mateixa clau que la resta de docs de Connection/Cluster
    )


def _group_config():
    from rest_framework.permissions import IsAuthenticated
    from django.contrib.auth.models import Group
    from auth.filters import GroupFilter
    from documentmanager.utils.export_permissions import export_permission_class

    available_columns = {
        "id": (_("ID"), lambda g: g.id),
        "name": (_("Nom"), lambda g: g.name or ""),
        "permissions_count": (_("Núm. permisos"), lambda g: g.permissions.count()),
    }

    return ExportConfig(
        queryset=lambda: Group.objects.all().order_by('name'),
        filterset_class=GroupFilter,
        permission_classes=[IsAuthenticated, export_permission_class('auth', 'group')],
        available_columns=available_columns,
        default_columns=list(available_columns.keys()),
        document_entity="GROUP",
        default_ordering="name",
    )


def _user_config():
    from rest_framework.permissions import IsAuthenticated
    from django.contrib.auth.models import User
    from auth.filters import UserFilter
    from documentmanager.utils.export_permissions import export_permission_class

    # NO exposar mai `password` ni cap altre camp sensible.
    available_columns = {
        "username": (_("Usuari"), lambda u: u.username or ""),
        "first_name": (_("Nom"), lambda u: u.first_name or ""),
        "last_name": (_("Cognoms"), lambda u: u.last_name or ""),
        "email": (_("Email"), lambda u: u.email or ""),
        "is_active": (_("Actiu"), lambda u: "Sí" if u.is_active else "No"),
        "is_superuser": (_("Superusuari"), lambda u: "Sí" if u.is_superuser else "No"),
        "groups": (_("Grups"), lambda u: ", ".join(u.groups.values_list('name', flat=True))),
        "date_joined": (_("Data alta"), lambda u: u.date_joined.strftime("%Y-%m-%d") if u.date_joined else ""),
        "last_login": (_("Últim accés"), lambda u: u.last_login.strftime("%Y-%m-%d %H:%M:%S") if u.last_login else ""),
    }

    return ExportConfig(
        queryset=lambda: User.objects.all().prefetch_related("groups").order_by('-date_joined'),
        filterset_class=UserFilter,
        permission_classes=[IsAuthenticated, export_permission_class('auth', 'user')],
        available_columns=available_columns,
        default_columns=list(available_columns.keys()),
        document_entity="USER",
        default_ordering="-date_joined",
    )


def _biller_config():
    from rest_framework.permissions import IsAuthenticated
    from django_filters import rest_framework as filters
    from billing.models import Biller
    from documentmanager.utils.export_permissions import export_permission_class

    class BillerFilter(filters.FilterSet):
        search = filters.CharFilter(method='filter_search')

        class Meta:
            model = Biller
            fields = ['search']

        def filter_search(self, queryset, name, value):
            from django.db.models import Q
            return queryset.filter(Q(token__icontains=value) | Q(name__icontains=value))

    available_columns = {
        "token": (_("Token"), lambda b: b.token or ""),
        "name": (_("Nom"), lambda b: b.name or ""),
        "period_type": (_("Periodicitat"), lambda b: b.get_period_type_display() if b.period_type else ""),
        "initial_month": (_("Mes inicial"), lambda b: b.get_initial_month_display() if b.initial_month else ""),
        "is_active": (_("Actiu"), lambda b: "Sí" if b.is_active else "No"),
    }

    return ExportConfig(
        queryset=lambda: Biller.objects.all(),
        filterset_class=BillerFilter,
        permission_classes=[IsAuthenticated, export_permission_class('billing', 'biller')],
        available_columns=available_columns,
        default_columns=list(available_columns.keys()),
        document_entity="BILLER",
        default_ordering="name",
        service_key="billing",
    )


def _billing_config():
    from rest_framework.permissions import IsAuthenticated
    from billing.models import Billing
    from billing.filter.billing_filter import BillingFilter
    from documentmanager.utils.export_permissions import export_permission_class

    available_columns = {
        "token": (_("Token"), lambda b: b.token or ""),
        "name": (_("Nom"), lambda b: b.name or ""),
        "biller": (_("Facturador"), lambda b: b.biller.name if b.biller else ""),
        "status": (_("Estat"), lambda b: b.status.name if b.status else ""),
        "send_at": (_("Data enviament"), lambda b: b.send_at.strftime("%Y-%m-%d %H:%M:%S") if b.send_at else ""),
        "is_excluded": (_("Exclosa"), lambda b: "Sí" if b.is_excluded else "No"),
        "created_at": (_("Data creació"), lambda b: b.created_at.strftime("%Y-%m-%d") if b.created_at else ""),
    }

    return ExportConfig(
        queryset=lambda: Billing.objects.filter(is_active=True).select_related("biller", "status"),
        filterset_class=BillingFilter,
        permission_classes=[IsAuthenticated, export_permission_class('billing', 'billing')],
        available_columns=available_columns,
        default_columns=list(available_columns.keys()),
        document_entity="BILLING",
        default_ordering="-created_at",
        service_key="billing",
    )


def _claim_request_config():
    from rest_framework.permissions import IsAuthenticated
    from claimrequest.models import ClaimRequest
    from claimrequest.filter.claim_request_filter import ClaimRequestFilter
    from documentmanager.utils.export_permissions import export_permission_class

    available_columns = {
        "token": (_("Token"), lambda c: c.token or ""),
        "name": (_("Nom"), lambda c: c.name or ""),
        "status": (_("Estat"), lambda c: c.status.name if c.status else ""),
        "template": (_("Plantilla"), lambda c: c.template.name if c.template else ""),
        "current_step": (_("Pas actual"), lambda c: c.current_step.token if c.current_step else ""),
        "due_date": (_("Data límit"), lambda c: c.due_date.strftime("%Y-%m-%d") if c.due_date else ""),
        "user": (_("Usuari"), lambda c: c.user.username if c.user else ""),
        "created_at": (_("Data creació"), lambda c: c.created_at.strftime("%Y-%m-%d") if c.created_at else ""),
    }

    return ExportConfig(
        queryset=lambda: ClaimRequest.objects.all().select_related("status", "template", "current_step", "user"),
        filterset_class=ClaimRequestFilter,
        permission_classes=[IsAuthenticated, export_permission_class('claimrequest', 'claimrequest')],
        available_columns=available_columns,
        default_columns=list(available_columns.keys()),
        document_entity="CLAIM_REQUEST",
        default_ordering="-created_at",
    )


def _commitment_deposit_config():
    from rest_framework.permissions import IsAuthenticated
    from billing.models import CommitmentDeposit
    from billing.filter.commitment_deposit_filter import CommitmentDepositFilter
    from documentmanager.utils.export_permissions import export_permission_class

    available_columns = {
        "token": (_("Token"), lambda cd: cd.token or ""),
        "status": (_("Estat"), lambda cd: cd.status.name if cd.status else ""),
        "contract": (_("Contracte"), lambda cd: cd.contract.token if cd.contract else ""),
        "total": (_("Total"), lambda cd: cd.total if cd.total is not None else ""),
        "remaining": (_("Pendent"), lambda cd: cd.remaining if cd.remaining is not None else ""),
        "due_date": (_("Data límit"), lambda cd: cd.due_date.strftime("%Y-%m-%d") if cd.due_date else ""),
        "customer": (_("Client"), lambda cd: cd.customer_final or ""),
    }

    return ExportConfig(
        queryset=lambda: CommitmentDeposit.objects.all().select_related("status", "contract"),
        filterset_class=CommitmentDepositFilter,
        permission_classes=[IsAuthenticated, export_permission_class('billing', 'commitmentdeposit')],
        available_columns=available_columns,
        default_columns=list(available_columns.keys()),
        document_entity="COMMITMENT_DEPOSIT",
        default_ordering="-due_date",
        service_key="billing",
    )


def _invoice_template_config():
    from rest_framework.permissions import IsAuthenticated
    from django_filters import rest_framework as filters
    from billing.models import InvoiceTemplate
    from documentmanager.utils.export_permissions import export_permission_class

    class InvoiceTemplateFilter(filters.FilterSet):
        search = filters.CharFilter(method='filter_search')

        class Meta:
            model = InvoiceTemplate
            fields = ['search']

        def filter_search(self, queryset, name, value):
            from django.db.models import Q
            return queryset.filter(Q(token__icontains=value) | Q(name__icontains=value))

    available_columns = {
        "token": (_("Token"), lambda t: t.token or ""),
        "name": (_("Nom"), lambda t: t.name or ""),
        "origin": (_("Origen"), lambda t: t.origin.name if t.origin else ""),
        "position": (_("Posició"), lambda t: t.position if t.position is not None else ""),
        "is_default": (_("Per defecte"), lambda t: "Sí" if t.is_default else "No"),
    }

    return ExportConfig(
        queryset=lambda: InvoiceTemplate.objects.all().select_related("origin"),
        filterset_class=InvoiceTemplateFilter,
        permission_classes=[IsAuthenticated, export_permission_class('billing', 'invoicetemplate')],
        available_columns=available_columns,
        default_columns=list(available_columns.keys()),
        document_entity="INVOICE_TEMPLATE",
        default_ordering="position",
        service_key="billing",
    )


def _joined_payment_config():
    from rest_framework.permissions import IsAuthenticated
    from billing.models import JoinedPayment
    from billing.filter.joined_payment_filter import JoinedPaymentFilter
    from documentmanager.utils.export_permissions import export_permission_class

    available_columns = {
        "token": (_("Token"), lambda jp: jp.token or ""),
        "number": (_("Número"), lambda jp: jp.number or ""),
        "status": (_("Estat"), lambda jp: jp.status.name if jp.status else ""),
        "contract": (_("Contracte"), lambda jp: jp.contract.token if jp.contract else ""),
        "customer": (_("Client"), lambda jp: jp.customer_final or ""),
        "payment_type": (_("Forma de pagament"), lambda jp: jp.payment_type_name or ""),
        "payment_date": (_("Data pagament"), lambda jp: jp.payment_date.strftime("%Y-%m-%d") if jp.payment_date else ""),
        "due_date": (_("Data venciment"), lambda jp: jp.due_date.strftime("%Y-%m-%d") if jp.due_date else ""),
        "total_final": (_("Total"), lambda jp: jp.total_final if jp.total_final is not None else ""),
    }

    return ExportConfig(
        queryset=lambda: JoinedPayment.objects.filter(is_active=True).select_related("status", "contract", "payment_type"),
        filterset_class=JoinedPaymentFilter,
        permission_classes=[IsAuthenticated, export_permission_class('billing', 'joinedpayment')],
        available_columns=available_columns,
        default_columns=list(available_columns.keys()),
        document_entity="JOINED_PAYMENT",
        default_ordering="-created_at",
        service_key="billing",
    )


def _billing_message_config():
    from rest_framework.permissions import IsAuthenticated
    from billing.models import Message
    from billing.filter.message_filter import MessageFilter
    from documentmanager.utils.export_permissions import export_permission_class

    available_columns = {
        "token": (_("Token"), lambda m: m.token or ""),
        "title": (_("Títol"), lambda m: m.title or ""),
        "message_type": (_("Tipus"), lambda m: m.get_message_type_display() if m.message_type else ""),
        "template": (_("Plantilla"), lambda m: m.template.name if m.template else ""),
        "start_at": (_("Data inici"), lambda m: m.start_at.strftime("%Y-%m-%d") if m.start_at else ""),
        "end_at": (_("Data fi"), lambda m: m.end_at.strftime("%Y-%m-%d") if m.end_at else ""),
        "is_active": (_("Actiu"), lambda m: "Sí" if m.is_active else "No"),
    }

    return ExportConfig(
        queryset=lambda: Message.objects.filter(is_active=True).select_related("template"),
        filterset_class=MessageFilter,
        permission_classes=[IsAuthenticated, export_permission_class('billing', 'message')],
        available_columns=available_columns,
        default_columns=list(available_columns.keys()),
        document_entity="BILLING_MESSAGE",
        default_ordering="token",
        service_key="billing",
    )


def _payment_config():
    from rest_framework.permissions import IsAuthenticated
    from billing.models import Payment
    from billing.filter.payment_filter import PaymentFilter
    from documentmanager.utils.export_permissions import export_permission_class

    available_columns = {
        "token": (_("Token"), lambda p: p.token or ""),
        "invoice": (_("Factura"), lambda p: p.invoice.token if p.invoice else ""),
        "contract": (_("Contracte"), lambda p: p.contract.token if p.contract else ""),
        "status": (_("Estat"), lambda p: p.status.name if p.status else ""),
        "amount": (_("Import"), lambda p: p.amount if p.amount is not None else ""),
        "payment_date": (_("Data pagament"), lambda p: p.payment_date.strftime("%Y-%m-%d") if p.payment_date else ""),
        "due_date": (_("Data venciment"), lambda p: p.due_date.strftime("%Y-%m-%d") if p.due_date else ""),
        "payment_type": (_("Forma de pagament"), lambda p: p.payment_type or ""),
        "customer": (_("Client"), lambda p: p.customer_final or ""),
    }

    return ExportConfig(
        queryset=lambda: Payment.objects.filter(is_active=True).select_related("invoice", "contract", "status"),
        filterset_class=PaymentFilter,
        permission_classes=[IsAuthenticated, export_permission_class('billing', 'payment')],
        available_columns=available_columns,
        default_columns=list(available_columns.keys()),
        document_entity="PAYMENT",
        default_ordering="-payment_date",
        service_key="billing",
    )


def _reading_batch_config():
    from rest_framework.permissions import IsAuthenticated
    from billing.models import ReadingBatch
    from billing.filter.reading_batch_filter import ReadingBatchFilter
    from documentmanager.utils.export_permissions import export_permission_class

    available_columns = {
        "token": (_("Token"), lambda rb: rb.token or ""),
        "name": (_("Nom"), lambda rb: rb.name or ""),
        "status": (_("Estat"), lambda rb: rb.status.name if rb.status else ""),
        "type": (_("Tipus"), lambda rb: rb.get_type_display() if rb.type else ""),
        "is_processed": (_("Processat"), lambda rb: "Sí" if rb.is_processed else "No"),
        "processed_at": (_("Data procés"), lambda rb: rb.processed_at.strftime("%Y-%m-%d %H:%M:%S") if rb.processed_at else ""),
    }

    return ExportConfig(
        queryset=lambda: ReadingBatch.objects.filter(is_active=True).select_related("status"),
        filterset_class=ReadingBatchFilter,
        permission_classes=[IsAuthenticated, export_permission_class('billing', 'readingbatch')],
        available_columns=available_columns,
        default_columns=list(available_columns.keys()),
        document_entity="READING_BATCH",
        default_ordering="id",
        service_key="billing",
    )


def _reading_batch_template_config():
    from rest_framework.permissions import IsAuthenticated
    from django_filters import rest_framework as filters
    from billing.models import ReadingBatchTemplate
    from documentmanager.utils.export_permissions import export_permission_class

    class ReadingBatchTemplateFilter(filters.FilterSet):
        search = filters.CharFilter(method='filter_search')

        class Meta:
            model = ReadingBatchTemplate
            fields = ['search']

        def filter_search(self, queryset, name, value):
            from django.db.models import Q
            return queryset.filter(Q(token__icontains=value) | Q(name__icontains=value))

    available_columns = {
        "token": (_("Token"), lambda t: t.token or ""),
        "name": (_("Nom"), lambda t: t.name or ""),
        "is_active": (_("Actiu"), lambda t: "Sí" if t.is_active else "No"),
    }

    return ExportConfig(
        queryset=lambda: ReadingBatchTemplate.objects.all(),
        filterset_class=ReadingBatchTemplateFilter,
        permission_classes=[IsAuthenticated, export_permission_class('billing', 'readingbatchtemplate')],
        available_columns=available_columns,
        default_columns=list(available_columns.keys()),
        document_entity="READING_BATCH_TEMPLATE",
        default_ordering="name",
        service_key="billing",
    )


def _payment_remittance_config():
    from rest_framework.permissions import IsAuthenticated
    from billing.models import PaymentRemittance
    from billing.filter.payment_remittance_filter import PaymentRemittanceFilter
    from documentmanager.utils.export_permissions import export_permission_class

    available_columns = {
        "token": (_("Token"), lambda pr: pr.token or ""),
        "status": (_("Estat"), lambda pr: pr.status.name if pr.status else ""),
        "company_bank": (_("Compte bancari"), lambda pr: str(pr.company_bank) if pr.company_bank else ""),
        "payments_count": (_("Núm. pagaments"), lambda pr: pr.payments.count()),
        "desired_send_at": (_("Data prevista"), lambda pr: pr.desired_send_at.strftime("%Y-%m-%d") if pr.desired_send_at else ""),
        "sent_at": (_("Data enviament"), lambda pr: pr.sent_at.strftime("%Y-%m-%d") if pr.sent_at else ""),
        "sent_by": (_("Enviat per"), lambda pr: pr.sent_by.username if pr.sent_by else ""),
        "is_return": (_("És devolució"), lambda pr: "Sí" if pr.is_return else "No"),
    }

    return ExportConfig(
        queryset=lambda: PaymentRemittance.objects.all().select_related("status", "company_bank", "sent_by"),
        filterset_class=PaymentRemittanceFilter,
        permission_classes=[IsAuthenticated, export_permission_class('billing', 'paymentremittance')],
        available_columns=available_columns,
        default_columns=list(available_columns.keys()),
        document_entity="PAYMENT_REMITTANCE",
        default_ordering="-created_at",
        service_key="billing",
    )


def _payment_remittance_return_config():
    from rest_framework.permissions import IsAuthenticated
    from billing.models import PaymentRemittanceReturn
    from billing.filter.payment_remittance_return_filter import PaymentRemittanceReturnFilter
    from documentmanager.utils.export_permissions import export_permission_class

    available_columns = {
        "token": (_("Token"), lambda pr: pr.token or ""),
        "return_date": (_("Data devolució"), lambda pr: pr.return_date.strftime("%Y-%m-%d") if pr.return_date else ""),
        "returned_by": (_("Retornat per"), lambda pr: pr.returned_by.username if pr.returned_by else ""),
        "payments_count": (_("Núm. pagaments"), lambda pr: pr.payments.count()),
    }

    return ExportConfig(
        queryset=lambda: PaymentRemittanceReturn.objects.all().select_related("returned_by"),
        filterset_class=PaymentRemittanceReturnFilter,
        permission_classes=[IsAuthenticated, export_permission_class('billing', 'paymentremittancereturn')],
        available_columns=available_columns,
        default_columns=list(available_columns.keys()),
        document_entity="PAYMENT_REMITTANCE_RETURN",
        default_ordering="-return_date",
        service_key="billing",
    )


def _verifactu_invoice_config():
    from rest_framework.permissions import IsAuthenticated
    from verifactu.models import VerifactuNotification
    from verifactu.filters.verifactu_notification_filter import VerifactuNotificationFilter
    from documentmanager.utils.export_permissions import export_permission_class

    available_columns = {
        "token": (_("Token"), lambda n: n.token or ""),
        "response_status": (_("Estat resposta"), lambda n: n.response_status or ""),
        "message_type": (_("Tipus missatge"), lambda n: n.message_type or ""),
        "batch": (_("Lot"), lambda n: n.batch.token if n.batch else ""),
        "verifactu_hash": (_("Hash"), lambda n: n.verifactu_hash or ""),
        "created_at": (_("Data creació"), lambda n: n.created_at.strftime("%Y-%m-%d %H:%M:%S") if n.created_at else ""),
    }

    return ExportConfig(
        queryset=lambda: VerifactuNotification.objects.all().select_related("batch"),
        filterset_class=VerifactuNotificationFilter,
        permission_classes=[IsAuthenticated, export_permission_class('verifactu', 'verifactunotification')],
        available_columns=available_columns,
        default_columns=list(available_columns.keys()),
        document_entity="VERIFACTU_NOTIFICATION",
        default_ordering="-created_at",
    )


def _communication_process_config():
    from rest_framework.permissions import IsAuthenticated
    from communication.models import CommunicationProcess
    from communication.filters.communication_process_filter import CommunicationProcessFilter
    from documentmanager.utils.export_permissions import export_permission_class

    available_columns = {
        "token": (_("Token"), lambda c: c.token or ""),
        "status": (_("Estat"), lambda c: c.status.name if c.status else ""),
        "use_type": (_("Tipus d'ús"), lambda c: c.use_type.name if c.use_type else ""),
        "template": (_("Plantilla"), lambda c: c.template.name if c.template else ""),
        "type_names": (_("Tipus"), lambda c: c.type_names or ""),
        "due_date": (_("Data límit"), lambda c: c.due_date.strftime("%Y-%m-%d") if c.due_date else ""),
        "user": (_("Usuari"), lambda c: c.user.username if c.user else ""),
        "created_at": (_("Data creació"), lambda c: c.created_at.strftime("%Y-%m-%d") if c.created_at else ""),
    }

    return ExportConfig(
        queryset=lambda: CommunicationProcess.objects.filter(is_active=True).select_related("status", "use_type", "template", "user"),
        filterset_class=CommunicationProcessFilter,
        permission_classes=[IsAuthenticated, export_permission_class('communication', 'communicationprocess')],
        available_columns=available_columns,
        default_columns=list(available_columns.keys()),
        document_entity="COMMUNICATION_PROCESS",
        default_ordering="-created_at",
        service_key="communication",
    )


def _message_template_config():
    from rest_framework.permissions import IsAuthenticated
    from communication.models import MessageTemplate
    from communication.filters.message_template_filter import MessageTemplateFilter
    from documentmanager.utils.export_permissions import export_permission_class

    available_columns = {
        "token": (_("Token"), lambda m: m.token or ""),
        "name": (_("Nom"), lambda m: m.name or ""),
        "origin": (_("Origen"), lambda m: m.origin.name if m.origin else ""),
        "is_active": (_("Actiu"), lambda m: "Sí" if m.is_active else "No"),
    }

    return ExportConfig(
        queryset=lambda: MessageTemplate.objects.all().select_related("origin"),
        filterset_class=MessageTemplateFilter,
        permission_classes=[IsAuthenticated, export_permission_class('communication', 'messagetemplate')],
        available_columns=available_columns,
        default_columns=list(available_columns.keys()),
        document_entity="MESSAGE_TEMPLATE",
        default_ordering="name",
        service_key="communication",
    )


def _bail_config():
    from rest_framework.permissions import IsAuthenticated
    from contract.models import Bail
    from contract.filters.bail_filter import BailFilter
    from documentmanager.utils.export_permissions import export_permission_class

    available_columns = {
        "token": (_("Token"), lambda b: b.token or ""),
        "contract": (_("Contracte"), lambda b: b.contract.token if b.contract else ""),
        "status": (_("Estat"), lambda b: b.status.name if b.status else ""),
        "product": (_("Producte"), lambda b: b.product.name if b.product else ""),
        "amount": (_("Import"), lambda b: b.amount if b.amount is not None else ""),
        "payment_date": (_("Data pagament"), lambda b: b.payment_date.strftime("%Y-%m-%d") if b.payment_date else ""),
        "return_date": (_("Data devolució"), lambda b: b.return_date.strftime("%Y-%m-%d") if b.return_date else ""),
        "is_billing": (_("Facturada"), lambda b: "Sí" if b.is_billing else "No"),
    }

    return ExportConfig(
        queryset=lambda: Bail.objects.filter(is_active=True).select_related("contract", "status", "product"),
        filterset_class=BailFilter,
        permission_classes=[IsAuthenticated, export_permission_class('contract', 'bail')],
        available_columns=available_columns,
        default_columns=list(available_columns.keys()),
        document_entity="BAIL",
        default_ordering="-payment_date",
    )


def _contract_request_config():
    from rest_framework.permissions import IsAuthenticated
    from contract.models import ContractRequest
    from contract.filters.contract_request_filter import ContractRequestFilter
    from documentmanager.utils.export_permissions import export_permission_class

    available_columns = {
        "token": (_("Token"), lambda cr: cr.token or ""),
        "holder": (_("Titular"), lambda cr: str(cr.holder) if cr.holder else ""),
        "supply_point": (_("Punt de subministrament"), lambda cr: cr.supply_point_default.token if cr.supply_point_default else ""),
        "status": (_("Estat"), lambda cr: cr.status.name if cr.status else ""),
        "type": (_("Tipus"), lambda cr: cr.type.name if cr.type else ""),
        "use_type": (_("Tipus d'ús"), lambda cr: cr.use_type.name if cr.use_type else ""),
        "requested_at": (_("Data sol·licitud"), lambda cr: cr.requested_at.strftime("%Y-%m-%d") if cr.requested_at else ""),
        "approved_at": (_("Data aprovació"), lambda cr: cr.approved_at.strftime("%Y-%m-%d") if cr.approved_at else ""),
    }

    return ExportConfig(
        queryset=lambda: ContractRequest.objects.filter(is_active=True).select_related(
            "holder", "supply_point_default", "status", "type", "use_type",
        ),
        filterset_class=ContractRequestFilter,
        permission_classes=[IsAuthenticated, export_permission_class('contract', 'contractrequest')],
        available_columns=available_columns,
        default_columns=list(available_columns.keys()),
        document_entity="CONTRACT_REQUEST",
        default_ordering="-requested_at",
    )


def _contract_termination_request_config():
    from rest_framework.permissions import IsAuthenticated
    from contract.models import ContractTerminationRequest
    from contract.filters.contract_termination_request_filter import ContractTerminationRequestFilter
    from documentmanager.utils.export_permissions import export_permission_class

    available_columns = {
        "token": (_("Token"), lambda ct: ct.token or ""),
        "contract": (_("Contracte"), lambda ct: ct.contract.token if ct.contract else ""),
        "person": (_("Persona"), lambda ct: str(ct.person) if ct.person else ""),
        "type": (_("Tipus"), lambda ct: ct.type.name if ct.type else ""),
        "status": (_("Estat"), lambda ct: ct.status.name if ct.status else ""),
        "requested_at": (_("Data sol·licitud"), lambda ct: ct.requested_at.strftime("%Y-%m-%d") if ct.requested_at else ""),
        "approved_at": (_("Data aprovació"), lambda ct: ct.approved_at.strftime("%Y-%m-%d") if ct.approved_at else ""),
    }

    return ExportConfig(
        queryset=lambda: ContractTerminationRequest.objects.filter(is_active=True).select_related(
            "contract", "person", "type", "status",
        ),
        filterset_class=ContractTerminationRequestFilter,
        permission_classes=[IsAuthenticated, export_permission_class('contract', 'contractterminationrequest')],
        available_columns=available_columns,
        default_columns=list(available_columns.keys()),
        document_entity="CONTRACT_TERMINATION_REQUEST",
        default_ordering="-requested_at",
    )


def _person_config():
    from rest_framework.permissions import IsAuthenticated
    from coredata.models import Person
    from coredata.filters.person_filter import PersonFilter
    from documentmanager.utils.export_permissions import export_permission_class

    # NO exposar mai dades bancàries (PersonBank: iban/account_number/swift) ni altres camps sensibles.
    available_columns = {
        "token": (_("Token"), lambda p: p.token or ""),
        "name": (_("Nom"), lambda p: p.name or ""),
        "surname": (_("Cognoms"), lambda p: p.surname or ""),
        "is_juridic": (_("Jurídica"), lambda p: "Sí" if p.is_juridic else "No"),
        "identification_type": (_("Tipus identificació"), lambda p: p.identification_type.name if p.identification_type else ""),
        "vulnerability_level": (_("Nivell vulnerabilitat"), lambda p: p.vulnerability_level),
    }

    return ExportConfig(
        queryset=lambda: Person.objects.all().select_related("identification_type", "deliquency"),
        filterset_class=PersonFilter,
        permission_classes=[IsAuthenticated, export_permission_class('coredata', 'person')],
        available_columns=available_columns,
        default_columns=list(available_columns.keys()),
        document_entity="PERSON",
        default_ordering="surname",
    )


def _street_config():
    from rest_framework.permissions import IsAuthenticated
    from coredata.models import Street
    from coredata.filters.street_filter import StreetFilter
    from documentmanager.utils.export_permissions import export_permission_class

    available_columns = {
        "token": (_("Token"), lambda s: s.token or ""),
        "name": (_("Nom"), lambda s: s.name or ""),
        "name_2": (_("Nom 2"), lambda s: s.name_2 or ""),
        "type": (_("Tipus"), lambda s: s.type.name if s.type else ""),
        "city": (_("Municipi"), lambda s: s.city.name if s.city else ""),
    }

    return ExportConfig(
        queryset=lambda: Street.objects.all().select_related("city", "type"),
        filterset_class=StreetFilter,
        permission_classes=[IsAuthenticated, export_permission_class('coredata', 'street')],
        available_columns=available_columns,
        default_columns=list(available_columns.keys()),
        document_entity="STREET",
        default_ordering="name",
    )


def _order_config():
    from rest_framework.permissions import IsAuthenticated
    from order.models import Order
    from order.filters.order_filter import OrderFilter
    from documentmanager.utils.export_permissions import export_permission_class

    available_columns = {
        "token": (_("Token"), lambda o: o.token or ""),
        "contract": (_("Contracte"), lambda o: o.contract.token if o.contract else ""),
        "type": (_("Tipus"), lambda o: o.type.name if o.type else ""),
        "reason": (_("Motiu"), lambda o: o.reason.name if o.reason else ""),
        "status": (_("Estat"), lambda o: o.status.name if o.status else ""),
        "priority": (_("Prioritat"), lambda o: o.priority.name if o.priority else ""),
        "dueDateAt": (_("Data límit"), lambda o: o.dueDateAt.strftime("%Y-%m-%d") if o.dueDateAt else ""),
        "completed_at": (_("Data completat"), lambda o: o.completed_at.strftime("%Y-%m-%d %H:%M:%S") if o.completed_at else ""),
        "created_by": (_("Creat per"), lambda o: o.created_by.username if o.created_by else ""),
    }

    return ExportConfig(
        queryset=lambda: Order.objects.filter(is_active=True).select_related(
            "contract", "type", "reason", "status", "priority", "created_by",
        ),
        filterset_class=OrderFilter,
        permission_classes=[IsAuthenticated, export_permission_class('order', 'order')],
        available_columns=available_columns,
        default_columns=list(available_columns.keys()),
        document_entity="ORDER",
        default_ordering="-created_at",
        service_key="order",
    )


def _order_type_config():
    from rest_framework.permissions import IsAuthenticated
    from django_filters import rest_framework as filters
    from order.models import OrderType
    from documentmanager.utils.export_permissions import export_permission_class

    class OrderTypeFilter(filters.FilterSet):
        search = filters.CharFilter(method='filter_search')

        class Meta:
            model = OrderType
            fields = ['search']

        def filter_search(self, queryset, name, value):
            from django.db.models import Q
            return queryset.filter(Q(token__icontains=value) | Q(name__icontains=value))

    available_columns = {
        "token": (_("Token"), lambda t: t.token or ""),
        "name": (_("Nom"), lambda t: t.name or ""),
        "position": (_("Posició"), lambda t: t.position if t.position is not None else ""),
        "is_default": (_("Per defecte"), lambda t: "Sí" if t.is_default else "No"),
    }

    return ExportConfig(
        queryset=lambda: OrderType.objects.all(),
        filterset_class=OrderTypeFilter,
        permission_classes=[IsAuthenticated, export_permission_class('order', 'ordertype')],
        available_columns=available_columns,
        default_columns=list(available_columns.keys()),
        document_entity="ORDER_TYPE",
        default_ordering="token",
        service_key="order",
    )


def _billing_range_config():
    from rest_framework.permissions import IsAuthenticated
    from pricing.models import BillingRange
    from pricing.filters.billing_range_filter import BillingRangeFilter
    from documentmanager.utils.export_permissions import export_permission_class

    available_columns = {
        "token": (_("Token"), lambda br: br.token or ""),
        "name": (_("Nom"), lambda br: br.name or ""),
        "price_rate": (_("Tarifa"), lambda br: br.price_rate.name if br.price_rate else ""),
        "publication": (_("Publicació"), lambda br: br.publication.name if br.publication else ""),
        "start": (_("Data inici"), lambda br: br.start.strftime("%Y-%m-%d") if br.start else ""),
        "end": (_("Data fi"), lambda br: br.end.strftime("%Y-%m-%d") if br.end else ""),
        "is_active": (_("Actiu"), lambda br: "Sí" if br.is_active else "No"),
    }

    return ExportConfig(
        queryset=lambda: BillingRange.objects.all().select_related("price_rate", "publication"),
        filterset_class=BillingRangeFilter,
        permission_classes=[IsAuthenticated, export_permission_class('pricing', 'billingrange')],
        available_columns=available_columns,
        default_columns=list(available_columns.keys()),
        document_entity="BILLING_RANGE",
        default_ordering="-start",
    )


def _line_item_type_config():
    from rest_framework.permissions import IsAuthenticated
    from pricing.models import LineItemType
    from pricing.filters.line_item_type_filter import LineItemTypeFilter
    from documentmanager.utils.export_permissions import export_permission_class

    available_columns = {
        "token": (_("Token"), lambda li: li.token or ""),
        "name": (_("Nom"), lambda li: li.name or ""),
        "code": (_("Codi"), lambda li: li.code or ""),
        "billing_range": (_("Tram de facturació"), lambda li: li.billing_range.name if li.billing_range else ""),
        "tax": (_("Impost"), lambda li: li.tax.name if li.tax else ""),
        "price": (_("Preu"), lambda li: li.price if li.price is not None else ""),
        "is_positive": (_("Positiu"), lambda li: "Sí" if li.is_positive else "No"),
    }

    return ExportConfig(
        queryset=lambda: LineItemType.objects.all().select_related("billing_range", "tax", "article", "billing_period"),
        filterset_class=LineItemTypeFilter,
        permission_classes=[IsAuthenticated, export_permission_class('pricing', 'lineitemtype')],
        available_columns=available_columns,
        default_columns=list(available_columns.keys()),
        document_entity="LINE_ITEM_TYPE",
        default_ordering="name",
    )


def _price_rate_config():
    from rest_framework.permissions import IsAuthenticated
    from pricing.models import PriceRate
    from pricing.filters.price_rate_filter import PriceRateFilter
    from documentmanager.utils.export_permissions import export_permission_class

    available_columns = {
        "token": (_("Token"), lambda pr: pr.token or ""),
        "name": (_("Nom"), lambda pr: pr.name or ""),
        "product": (_("Producte"), lambda pr: pr.product.name if pr.product else ""),
        "billing_range_active": (_("Tram actiu"), lambda pr: pr.billing_range_active.name if pr.billing_range_active else ""),
        "is_bail": (_("És fiança"), lambda pr: "Sí" if pr.is_bail else "No"),
        "is_return_fee": (_("És despeses de devolució"), lambda pr: "Sí" if pr.is_return_fee else "No"),
        "is_active": (_("Actiu"), lambda pr: "Sí" if pr.is_active else "No"),
    }

    return ExportConfig(
        queryset=lambda: PriceRate.objects.filter(is_active=True).select_related("product", "billing_range_active"),
        filterset_class=PriceRateFilter,
        permission_classes=[IsAuthenticated, export_permission_class('pricing', 'pricerate')],
        available_columns=available_columns,
        default_columns=list(available_columns.keys()),
        document_entity="PRICE_RATE",
        default_ordering="name",
    )


def _product_config():
    from rest_framework.permissions import IsAuthenticated
    from pricing.models import Product
    from pricing.filters.product_filter import ProductFilter
    from documentmanager.utils.export_permissions import export_permission_class

    available_columns = {
        "token": (_("Token"), lambda p: p.token or ""),
        "name": (_("Nom"), lambda p: p.name or ""),
        "origin": (_("Origen"), lambda p: p.origin.name if p.origin else ""),
        "exploitation": (_("Explotació"), lambda p: p.exploitation.name if p.exploitation else ""),
        "position": (_("Posició"), lambda p: p.position if p.position is not None else ""),
        "is_active": (_("Actiu"), lambda p: "Sí" if p.is_active else "No"),
    }

    return ExportConfig(
        queryset=lambda: Product.objects.filter(is_active=True).select_related("origin", "exploitation", "company"),
        filterset_class=ProductFilter,
        permission_classes=[IsAuthenticated, export_permission_class('pricing', 'product')],
        available_columns=available_columns,
        default_columns=list(available_columns.keys()),
        document_entity="PRODUCT",
        default_ordering="position",
    )


def _cluster_config():
    from rest_framework.permissions import IsAuthenticated
    from service.models import Cluster
    from service.filters.cluster_filter import ClusterFilter
    from documentmanager.utils.export_permissions import export_permission_class

    available_columns = {
        "token": (_("Token"), lambda c: c.token or ""),
        "status": (_("Estat"), lambda c: c.status.name if c.status else ""),
        "connection": (_("Escomesa"), lambda c: c.connection.token if c.connection else ""),
        "nb_nozzles": (_("Núm. broquets"), lambda c: c.nb_nozzles if c.nb_nozzles is not None else ""),
        "installation_at": (_("Data instal·lació"), lambda c: c.installation_at.strftime("%Y-%m-%d") if c.installation_at else ""),
        "address_city": (_("Municipi"), lambda c: c.address_city.name if c.address_city else ""),
    }

    return ExportConfig(
        queryset=lambda: Cluster.objects.filter(is_active=True).select_related("status", "connection", "address_city"),
        filterset_class=ClusterFilter,
        permission_classes=[IsAuthenticated, export_permission_class('service', 'cluster')],
        available_columns=available_columns,
        default_columns=list(available_columns.keys()),
        document_entity="CLUSTER",
        default_ordering="token",
        service_key="connection",
    )


def _connection_config():
    from rest_framework.permissions import IsAuthenticated
    from service.models import Connection
    from service.filters.connection_filter import ConnectionFilter
    from documentmanager.utils.export_permissions import export_permission_class

    available_columns = {
        "token": (_("Token"), lambda c: c.token or ""),
        "exploitation": (_("Explotació"), lambda c: c.exploitation.name if c.exploitation else ""),
        "status": (_("Estat"), lambda c: c.status.name if c.status else ""),
        "type": (_("Tipus"), lambda c: c.type.name if c.type else ""),
        "use_type": (_("Tipus d'ús"), lambda c: c.use_type.name if c.use_type else ""),
        "diameter": (_("Diàmetre"), lambda c: c.diameter.name if c.diameter else ""),
        "installation_at": (_("Data instal·lació"), lambda c: c.installation_at.strftime("%Y-%m-%d") if c.installation_at else ""),
        "address_city": (_("Municipi"), lambda c: c.address_city.name if c.address_city else ""),
    }

    return ExportConfig(
        queryset=lambda: Connection.objects.filter(is_active=True).select_related(
            "exploitation", "status", "type", "use_type", "diameter", "address_city",
        ),
        filterset_class=ConnectionFilter,
        permission_classes=[IsAuthenticated, export_permission_class('service', 'connection')],
        available_columns=available_columns,
        default_columns=list(available_columns.keys()),
        document_entity="CONNECTION",
        default_ordering="token",
        service_key="connection",
    )


def _connection_request_config():
    from rest_framework.permissions import IsAuthenticated
    from service.models import ConnectionRequest
    from service.filters.connection_request_filter import ConnectionRequestFilter
    from documentmanager.utils.export_permissions import export_permission_class

    available_columns = {
        "token": (_("Token"), lambda cr: cr.token or ""),
        "person": (_("Persona"), lambda cr: str(cr.person) if cr.person else ""),
        "exploitation": (_("Explotació"), lambda cr: cr.exploitation.name if cr.exploitation else ""),
        "status": (_("Estat"), lambda cr: cr.status.name if cr.status else ""),
        "type": (_("Tipus"), lambda cr: cr.type.name if cr.type else ""),
        "requested_at": (_("Data sol·licitud"), lambda cr: cr.requested_at.strftime("%Y-%m-%d") if cr.requested_at else ""),
        "address_city": (_("Municipi"), lambda cr: cr.address_city.name if cr.address_city else ""),
    }

    return ExportConfig(
        queryset=lambda: ConnectionRequest.objects.filter(is_active=True).select_related(
            "person", "exploitation", "status", "type", "address_city",
        ),
        filterset_class=ConnectionRequestFilter,
        permission_classes=[IsAuthenticated, export_permission_class('service', 'connectionrequest')],
        available_columns=available_columns,
        default_columns=list(available_columns.keys()),
        document_entity="CONNECTION_REQUEST",
        default_ordering="-requested_at",
        service_key="connection",
    )


def _exploitation_config():
    from rest_framework.permissions import IsAuthenticated
    from service.models import Exploitation
    from service.filters.exploitation_filter import ExploitationFilter
    from documentmanager.utils.export_permissions import export_permission_class

    available_columns = {
        "token": (_("Token"), lambda e: e.token or ""),
        "name": (_("Nom"), lambda e: e.name or ""),
        "company": (_("Empresa"), lambda e: e.company.name if e.company else ""),
        "code": (_("Codi"), lambda e: e.code or ""),
        "supply_code": (_("Codi subministrament"), lambda e: e.company.supply_code if e.company and e.company.supply_code else ""),
        "is_active": (_("Actiu"), lambda e: "Sí" if e.is_active else "No"),
    }

    return ExportConfig(
        queryset=lambda: Exploitation.objects.all().select_related("company"),
        filterset_class=ExploitationFilter,
        permission_classes=[IsAuthenticated, export_permission_class('service', 'exploitation')],
        available_columns=available_columns,
        default_columns=list(available_columns.keys()),
        document_entity="EXPLOITATION",
        default_ordering="name",
        service_key="connection",
    )


# Registre construït de forma diferida (via callables `_xxx_config()`) perquè
# els imports de models/filters no s'executin a l'import time d'aquest mòdul.
_CONFIG_FACTORIES = {
    "invoice": _invoice_config,
    "supply_point": _supply_point_config,
    "property": _property_config,
    "meter": _meter_config,
    "group": _group_config,
    "user": _user_config,
    "biller": _biller_config,
    "billing": _billing_config,
    "claim_request": _claim_request_config,
    "commitment_deposit": _commitment_deposit_config,
    "invoice_template": _invoice_template_config,
    "joined_payment": _joined_payment_config,
    "billing_message": _billing_message_config,
    "payment": _payment_config,
    "reading_batch": _reading_batch_config,
    "reading_batch_template": _reading_batch_template_config,
    "payment_remittance": _payment_remittance_config,
    "payment_remittance_return": _payment_remittance_return_config,
    "verifactu_invoice": _verifactu_invoice_config,
    "communication_process": _communication_process_config,
    "message_template": _message_template_config,
    "bail": _bail_config,
    "contract_request": _contract_request_config,
    "contract_termination_request": _contract_termination_request_config,
    "person": _person_config,
    "street": _street_config,
    "order": _order_config,
    "order_type": _order_type_config,
    "billing_range": _billing_range_config,
    "line_item_type": _line_item_type_config,
    "price_rate": _price_rate_config,
    "product": _product_config,
    "cluster": _cluster_config,
    "connection": _connection_config,
    "connection_request": _connection_request_config,
    "exploitation": _exploitation_config,
}


def get_export_config(entity: str) -> ExportConfig:
    factory = _CONFIG_FACTORIES.get(entity)
    if factory is None:
        return None
    return factory()
