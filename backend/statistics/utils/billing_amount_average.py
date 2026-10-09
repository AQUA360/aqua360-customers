"""
Mitjanes de l'import facturat (BillingConsumption.total_amount) per a l'avís d'import alt.

L'avís compara cada factura amb la mitjana de TOTES les factures del contracte, de manera
que el rebut d'estiu (piscina, reg) saltava cada any. Ara, a més, es compara amb el mateix
període d'anys anteriors i l'avís només surt si l'import és alt respecte de les dues
mitjanes. Si el contracte no té històric d'aquest període, queda només la mitjana completa
(comportament anterior). Així el canvi només pot treure avisos de pics estacionals
recurrents, mai afegir-ne.

Per què no substituir directament la mitjana completa per la del període: amb facturació mensual el període inclou
la factura del mes anterior, i un pic tapa el del mes següent; i com que el període de
l'any anterior es va facturar amb tarifes més baixes, sortien més avisos que abans.

- Període: el mes de facturació (billing_period_month) amb un marge de PERIOD_WINDOW_MONTHS
  a cada banda, perquè una tanda trimestral no sempre s'emet el mateix mes.
- Només compten factures d'almenys MIN_MONTHS_AGO mesos enrere (anys anteriors) i amb
  import positiu (els abonaments negatius esbiaixen mitjanes de poques mostres).
"""
from django.db.models import Count, Sum

from billing.models import Invoice
from statistics.models import BillingConsumption

PERIOD_WINDOW_MONTHS = 1
MIN_MONTHS_AGO = 10
HIGH_AMOUNT_FACTOR = 1.5


def period_months(month):
    """Mesos (1-12) que es consideren el mateix període que `month`, de forma circular."""
    if not month:
        return None
    month = int(month)
    return sorted({(month - 1 + offset) % 12 + 1 for offset in range(-PERIOD_WINDOW_MONTHS, PERIOD_WINDOW_MONTHS + 1)})


def _month_index(year, month):
    return int(year) * 12 + int(month)


def _avg(total_sum, total_count):
    if not total_count or total_sum is None:
        return None
    return float(total_sum) / total_count


def seasonal_amounts(rows, year, month):
    """
    Imports del mateix període d'anys anteriors a partir de files (year, month, total_amount).
    Buit si la factura no té any/mes.
    """
    months = period_months(month)
    if not months or not year:
        return []
    limit = _month_index(year, month) - MIN_MONTHS_AGO
    return [
        float(amount) for y, m, amount in rows
        if amount is not None and amount > 0 and y and m in months and _month_index(y, m) <= limit
    ]


def is_high_amount(total_final, avg_total):
    return bool(avg_total) and float(total_final) > float(avg_total) * HIGH_AMOUNT_FACTOR


def get_total_amount_avg(contracts, exclude_invoice_id=None):
    """Mitjana completa de total_amount dels contractes; si no n'hi ha, la de les factures."""
    stats = BillingConsumption.objects.filter(contract__in=contracts)
    if exclude_invoice_id:
        stats = stats.exclude(invoice_id=exclude_invoice_id)
    agg = stats.aggregate(total_sum=Sum('total_amount'), total_count=Count('total_amount'))
    avg = _avg(agg['total_sum'], agg['total_count'])
    if avg is not None:
        return avg

    invoices = Invoice.objects.filter(contract__in=contracts, total_final__isnull=False)
    if exclude_invoice_id:
        invoices = invoices.exclude(id=exclude_invoice_id)
    agg = invoices.aggregate(total_sum=Sum('total_final'), total_count=Count('id'))
    return _avg(agg['total_sum'], agg['total_count'])


def get_seasonal_total_amount_avg(contracts, year, month, exclude_invoice_id=None):
    """
    Mitjana de total_amount del mateix període d'anys anteriors, o None si no n'hi ha
    (o si la factura no té any/mes).
    """
    months = period_months(month)
    if not months or not year:
        return None
    stats = BillingConsumption.objects.filter(contract__in=contracts, month__in=months)
    if exclude_invoice_id:
        stats = stats.exclude(invoice_id=exclude_invoice_id)
    values = seasonal_amounts(stats.values_list('year', 'month', 'total_amount'), year, month)
    return sum(values) / len(values) if values else None


def is_high_amount_for_period(total_final, contracts, year, month, exclude_invoice_id=None):
    if not is_high_amount(total_final, get_total_amount_avg(contracts, exclude_invoice_id)):
        return False
    seasonal_avg = get_seasonal_total_amount_avg(contracts, year, month, exclude_invoice_id)
    return seasonal_avg is None or is_high_amount(total_final, seasonal_avg)


class TotalAmountAvgCache:
    """
    Versió en bloc de is_high_amount_for_period per a la generació massiva de factures:
    dues consultes per a tots els contractes i després es resol cada contracte en memòria.
    """

    def __init__(self, contract_ids):
        self.by_month = {}
        rows = (
            BillingConsumption.objects.filter(contract_id__in=contract_ids)
            .values_list('contract_id', 'year', 'month', 'total_amount')
        )
        for contract_id, year, month, amount in rows:
            self.by_month.setdefault(contract_id, []).append((year, month, amount))

        self.invoices = {}
        rows = (
            Invoice.objects.filter(contract_id__in=contract_ids, total_final__isnull=False)
            .values('contract_id')
            .annotate(total_sum=Sum('total_final'), total_count=Count('id'))
        )
        for row in rows:
            self.invoices[row['contract_id']] = (row['total_sum'], int(row['total_count']))

    def total_avg(self, contract_id):
        amounts = [float(a) for _, _, a in self.by_month.get(contract_id, []) if a is not None]
        if amounts:
            return sum(amounts) / len(amounts)
        return _avg(*self.invoices.get(contract_id, (None, 0)))

    def seasonal_avg(self, contract_id, year, month):
        amounts = seasonal_amounts(self.by_month.get(contract_id, []), year, month)
        return sum(amounts) / len(amounts) if amounts else None

    def is_high_amount(self, total_final, contract_id, year, month):
        if not is_high_amount(total_final, self.total_avg(contract_id)):
            return False
        seasonal_avg = self.seasonal_avg(contract_id, year, month)
        return seasonal_avg is None or is_high_amount(total_final, seasonal_avg)
