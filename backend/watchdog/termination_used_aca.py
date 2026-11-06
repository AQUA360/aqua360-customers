"""Factures i pressupostos de baixa amb un `used_aca` que no és el del contracte donat de baixa.

Entre la creació de `Invoice.used_aca` i la correcció d'`invoice_contract_termination_generate`
(agost-setembre de 2026), les baixes facturades des de la pantalla de la baixa guardaven el
`use_aca` d'un altre contracte: sense alta vinculada, el del contracte amb l'id més baix sense
sol·licitud d'alta; amb alta vinculada, el del contracte nou. Els informes de l'ACA (FACTDETA i
Declaració ACA) prioritzen `used_aca` sobre el contracte, de manera que aquestes factures es
declaren amb un ús equivocat. Els pressupostos afectats encara sense facturar l'arrosseguen a la
factura en passar-los (`pass_budget_to_invoice`).

Si el `use_aca` del contracte s'ha canviat després de facturar la baixa, també surt aquí: cal
revisar el llistat amb --dry-run abans de corregir.
"""
from django.db.models import Exists, F, OuterRef, Q

from billing.models import Invoice
from coredata.models import ConfigProject

TERMINATION_USED_ACA_CHECK_NAME = "Factures de baixa amb used_aca erroni"

WATCHDOG_FIX_TERMINATION_USED_ACA_COMMANDS = (
    "python manage.py watchdog_fix_termination_used_aca --dry-run",
    "python manage.py watchdog_fix_termination_used_aca --ids=ID1,ID2  (o --all un cop revisat el llistat)",
)

MAX_LISTED_ISSUES = 200


def _config_value(token):
    """Valor d'un ConfigProject, o None si no existeix."""
    config = ConfigProject.objects.filter(token=token).first()
    return config.value if config else None


def get_termination_used_aca_mismatches():
    """Factures i pressupostos de baixa amb `used_aca` informat i diferent del `use_aca` actual del
    contracte de la baixa (un contracte sense `use_aca` també compta: hauria de quedar buit)."""
    expected = F('contract_termination__contract__use_aca')
    return (
        Invoice.objects
        .filter(contract_termination__isnull=False, contract_termination__contract__isnull=False)
        .exclude(used_aca__isnull=True)
        .exclude(used_aca='')
        .filter(
            Q(contract_termination__contract__use_aca__isnull=True)
            | Q(contract_termination__contract__use_aca='')
            | ~Q(used_aca=expected)
        )
    )


def _with_pending_budget_flag(queryset):
    """Anota si la baixa ja té una factura; un pressupost sense factura encara es pot passar a factura."""
    budget_token = _config_value('invoice_type_budget_token')
    invoiced = Invoice.objects.filter(
        contract_termination=OuterRef('contract_termination'),
        type__token=_config_value('invoice_type_invoice_token'),
    )
    return queryset.annotate(termination_invoiced=Exists(invoiced)), budget_token


def check_termination_used_aca_issues():
    """Incidències del watchdog: una línia per factura o pressupost de baixa amb used_aca erroni."""
    queryset, budget_token = _with_pending_budget_flag(get_termination_used_aca_mismatches())
    rows = list(
        queryset.order_by('created_at', 'id').values(
            'id', 'serie_final', 'type__token', 'type__name', 'status__name', 'issue_date', 'created_at',
            'used_aca', 'contract_termination_id', 'contract_termination__contract__token',
            'contract_termination__contract__use_aca', 'termination_invoiced',
        )
    )
    if not rows:
        return []

    issues = []
    for row in rows[:MAX_LISTED_ISSUES]:
        is_pending_budget = row['type__token'] == budget_token and not row['termination_invoiced']
        created = row['created_at'].date() if row['created_at'] else None
        issues.append(
            f"Factura ID {row['id']} ({row['type__name'] or row['type__token'] or '-'} "
            f"{row['serie_final'] or '-'}, estat {row['status__name'] or '-'}, emesa {row['issue_date']}, "
            f"creada {created}): used_aca '{row['used_aca']}' però el contracte de la baixa "
            f"{row['contract_termination__contract__token']} (baixa ID {row['contract_termination_id']}) "
            f"té use_aca '{row['contract_termination__contract__use_aca'] or ''}'"
            + (" — PRESSUPOST PENDENT DE FACTURAR: la factura heretarà el valor erroni" if is_pending_budget else "")
        )
    if len(rows) > MAX_LISTED_ISSUES:
        issues.append(f"... i {len(rows) - MAX_LISTED_ISSUES} més (total {len(rows)})")
    issues.append(
        "Si el trimestre ja s'ha presentat a l'ACA, cal valorar una declaració complementària "
        "per a les factures corregides."
    )
    return issues
