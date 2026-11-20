import base64
import matplotlib
matplotlib.use('Agg')  # Set backend before importing pyplot
import matplotlib.pyplot as plt
import contextlib
import contextvars
from collections import defaultdict

from billing.models import Reading, Invoice
from django.db.models import Max, Q
from io import BytesIO
import colorsys

from coredata.models import ConfigProject

def get_complementary_color(rgb_color):
    """
    Convert RGB color to tertiary color using color theory wheel.
    RGB values should be in 0-1 range.
    """
    # Convert RGB to HSV
    h, s, v = colorsys.rgb_to_hsv(rgb_color[0], rgb_color[1], rgb_color[2])
    
    # Shift hue by 120 degrees (tertiary color)
    h = (h + 0.75) % 1.0
    
    # Convert back to RGB
    r, g, b = colorsys.hsv_to_rgb(h, s, v)
    
    return (r, g, b)

def get_darker_color(rgb_color):
    return (rgb_color[0] * 0.85, rgb_color[1] * 0.85, rgb_color[2] * 0.85)

def rgb_from_hex(value):
    if not isinstance(value, str):
        return None
    hex_color = value.strip().lstrip('#')
    if len(hex_color) < 6:
        return None
    try:
        return tuple(int(hex_color[i:i + 2], 16) / 255.0 for i in (0, 2, 4))
    except ValueError:
        return None

MAX_BARS = 5

def resolve_reading(reading, seen=None):
    """A control reading can later be corrected; the correction is linked via
    modified_readings. Follow that link to the final, non-control value instead of
    keeping the superseded one (mirrors invoice_service.resolve_reading)."""
    if seen is None:
        seen = set()
    if reading.id in seen:
        return reading
    seen.add(reading.id)
    if reading.is_control:
        replacement = reading.modified_readings.filter(is_control=False).first()
        if replacement:
            return resolve_reading(replacement, seen)
    return reading

CHART_EXCLUDED_STATUS_CONFIG_TOKENS = ['invoice_status_cancelled_token', 'invoice_status_payoff_token', 'invoice_status_dropped_token']
CHART_CONFIG_TOKENS = CHART_EXCLUDED_STATUS_CONFIG_TOKENS + [
    'invoice_type_invoice_token', 'invoice_main_color', 'invoice_secondary_color',
    'invoice_chart_remove_background', 'invoice_chart_bar_color',
]

# Historial precarregat per a un tros de factures (veure `chart_history_scope`)
_chart_history = contextvars.ContextVar('chart_history', default=None)


def _chart_readings_queryset():
    return Reading.objects.select_related('previous_reading__previous_reading').order_by('id')


class ChartHistory:
    """
    Dades del gràfic de consum d'un tros de factures carregades amb poques consultes: les factures
    anteriors dels seus contractes, les lectures de cada factura i l'historial de lectures. El gràfic
    surt igual que consultant-ho factura a factura.
    """

    def __init__(self, invoices, bars_only=False):
        """Amb `bars_only`, només les lectures de `invoices` (per a `invoice_chart_bar`)."""
        self.loaded_invoice_ids = {invoice.id for invoice in invoices}
        self.invoice_ids_by_contract = defaultdict(set)
        self.previous_invoices = {}
        self.history_readings_by_contract = defaultdict(list)
        self.readings_by_invoice = defaultdict(list)
        if bars_only:
            self.config = {}
            self._load_readings(self.loaded_invoice_ids)
            return

        self.config = dict(ConfigProject.objects.filter(token__in=CHART_CONFIG_TOKENS).values_list('token', 'value'))
        excluded_statuses = [self.config[token] for token in CHART_EXCLUDED_STATUS_CONFIG_TOKENS if token in self.config]
        invoice_type_token = self.config.get('invoice_type_invoice_token')

        contract_ids = {contract.id for contract in (_chart_contract(invoice) for invoice in invoices) if contract}
        for invoice_id, contract_id in Invoice.objects.filter(contract_id__in=contract_ids).values_list('id', 'contract_id'):
            self.invoice_ids_by_contract[contract_id].add(invoice_id)
        for invoice_id, contract_id in Invoice.objects.filter(
            contract_termination__contract_id__in=contract_ids,
        ).values_list('id', 'contract_termination__contract_id'):
            self.invoice_ids_by_contract[contract_id].add(invoice_id)
        all_invoice_ids = set().union(*self.invoice_ids_by_contract.values()) if self.invoice_ids_by_contract else set()

        # Factures anteriors vàlides (mateixos criteris que `_previous_chart_invoices`)
        self.previous_invoices = {
            row['id']: row for row in _valid_chart_invoices(
                Invoice.objects.filter(id__in=all_invoice_ids), excluded_statuses, invoice_type_token,
            ).values('id', 'consumption', 'period_date')
        }

        # Lectures actives de les factures del tros i de les anteriors
        self._load_readings(set(self.previous_invoices) | self.loaded_invoice_ids)

        # Historial de lectures per omplir les barres que falten
        for row in Reading.objects.filter(
            contract_id__in=contract_ids, is_control=False, is_initial=False, is_active=True,
        ).values('id', 'contract_id', 'supply_point_id', 'reading_date', 'real_consumption'):
            self.history_readings_by_contract[row['contract_id']].append(row)

    def _load_readings(self, invoice_ids):
        reading_ids_by_invoice = defaultdict(list)
        for invoice_id, reading_id in Invoice.readings.through.objects.filter(
            invoice_id__in=invoice_ids, reading__is_active=True,
        ).values_list('invoice_id', 'reading_id'):
            reading_ids_by_invoice[invoice_id].append(reading_id)
        readings = {
            reading.id: reading for reading in _chart_readings_queryset().filter(
                id__in={reading_id for ids in reading_ids_by_invoice.values() for reading_id in ids},
            )
        }
        for invoice_id, reading_ids in reading_ids_by_invoice.items():
            self.readings_by_invoice[invoice_id] = [readings[reading_id] for reading_id in sorted(reading_ids)]

    def has(self, invoice):
        return invoice.id in self.loaded_invoice_ids


@contextlib.contextmanager
def chart_history_scope(invoices):
    """Precarrega l'historial del gràfic de `invoices` mentre dura el bloc."""
    token = _chart_history.set(ChartHistory(list(invoices)))
    try:
        yield
    finally:
        _chart_history.reset(token)


def _chart_config(token):
    history = _chart_history.get()
    if history is not None:
        return history.config.get(token)
    return ConfigProject.objects.filter(token=token).values_list('value', flat=True).first()


def _chart_contract(invoice):
    if getattr(invoice, 'contract', None):
        return invoice.contract
    termination = getattr(invoice, 'contract_termination', None)
    if termination and getattr(termination, 'contract', None):
        return termination.contract
    return None


def _valid_chart_invoices(queryset, excluded_statuses, invoice_type_token):
    """Factures que poden ser una barra: vàlides i amb la data de la seva última lectura activa."""
    return queryset.filter(
        is_active=True,
        is_suppressed=False,
        type__token=invoice_type_token,
    ).filter(
        Q(return_token__isnull=True) | Q(return_token=''),
    ).exclude(
        status__token__in=excluded_statuses,
    ).annotate(
        period_date=Max('readings__reading_date', filter=Q(readings__is_active=True)),
    )


def _chart_invoice_readings(invoice_id, history=None):
    if history is not None and invoice_id in history.readings_by_invoice:
        return history.readings_by_invoice[invoice_id]
    if history is not None and (invoice_id in history.previous_invoices or invoice_id in history.loaded_invoice_ids):
        return []
    return list(_chart_readings_queryset().filter(invoices__id=invoice_id, is_active=True))


def get_invoice_chart_readings(invoice, history=None):
    """Lectures que ha cobrat una factura. `invoice.readings` només conté la lectura final de cada
    comptador: en un canvi de comptador a mig període, la lectura de tancament del comptador substituït
    queda enllaçada via previous_reading i no a invoice.readings, i també s'ha de tenir en compte."""
    invoice_id = invoice if isinstance(invoice, int) else invoice.id
    invoice_readings = _chart_invoice_readings(invoice_id, history)
    invoice_reading_ids = {reading.id for reading in invoice_readings}
    chart_readings = []
    for reading in invoice_readings:
        chart_readings.append(reading)
        prev = reading.previous_reading
        if prev and prev.is_close and prev.id not in invoice_reading_ids:
            chart_readings.append(prev)
        prev_prev = prev.previous_reading if prev else None
        if prev_prev and prev_prev.is_close and prev_prev.id not in invoice_reading_ids:
            chart_readings.append(prev_prev)
    return [resolve_reading(reading) for reading in chart_readings]


def invoice_chart_bar(invoice, history=None):
    """
    Barra del gràfic d'una factura: (data, consum). La data és la de la seva última lectura activa
    i el consum, el facturat (`Invoice.consumption`) o, si no en té, el de les seves lectures.
    Sense lectures, (None, None).
    """
    invoice_readings = _chart_invoice_readings(invoice.id, history)
    bar_date = max((reading.reading_date for reading in invoice_readings if reading.reading_date), default=None)
    if bar_date is None:
        return None, None
    return bar_date, _chart_bar_value(invoice.consumption, get_invoice_chart_readings(invoice, history))


def _chart_bar_value(consumption, chart_readings):
    if consumption is not None:
        return float(consumption)
    # Factura de consum sense el consum desat: es calcula a partir de les seves lectures
    return sum(float(reading.real_consumption or 0) for reading in chart_readings)


def get_chart_bars(invoice):
    """Dates i valors de les barres del gràfic d'una factura, de la més recent a la més antiga.
    Fa servir l'historial precarregat si n'hi ha (`chart_history_scope`). Sense dades, (None, None)."""
    history = _chart_history.get()
    if history is not None and not history.has(invoice):
        history = None

    # Cada barra és el consum facturat (`Invoice.consumption`) d'una factura del contracte, no el
    # recalculat a partir de les lectures: així el gràfic coincideix amb el que s'ha cobrat (comptadors
    # generals, canvis de comptador, fuites, refacturacions...). Cada factura es posiciona per la data
    # de la seva última lectura, que una refacturació comparteix amb la factura original; l'issue_date
    # i el billing_period passen a ser els de la refacturació i la mourien de lloc. Només compten factures
    # amb lectures: n'hi ha sense lectures (derrames...) que tenen `consumption` desat amb un valor que no
    # és consum d'aigua.
    contract = _chart_contract(invoice)
    dates = []
    values = []
    used_reading_ids = set()
    # Data de la lectura més antiga ja representada: l'historial de lectures només s'usa per sota
    readings_cutoff = None

    def add_invoice_bar(bar_invoice_id, consumption, bar_date):
        nonlocal readings_cutoff
        chart_readings = get_invoice_chart_readings(bar_invoice_id, history)
        dates.append(bar_date)
        values.append(_chart_bar_value(consumption, chart_readings))
        used_reading_ids.update(reading.id for reading in chart_readings)
        readings_cutoff = min([reading.reading_date for reading in chart_readings if reading.reading_date] + [bar_date])

    current_bar_date = max(
        (reading.reading_date for reading in _chart_invoice_readings(invoice.id, history) if reading.reading_date),
        default=None,
    )
    if current_bar_date is None:
        print("Error: Invoice has no readings")
        return None, None
    add_invoice_bar(invoice.id, invoice.consumption, current_bar_date)

    # Barres anteriors: factures vàlides del contracte. S'exclouen pressupostos, factures abonades o
    # anul·lades (i els seus abonaments, que copien el consum en positiu) i factures sense lectures.
    for previous_id, consumption, period_date in _previous_chart_invoices(invoice, contract, current_bar_date, history):
        if len(dates) >= MAX_BARS:
            break
        # Una sola barra per període si hi hagués més d'una factura vàlida amb la mateixa data
        if period_date in dates:
            continue
        add_invoice_bar(previous_id, consumption, period_date)

    # Si no hi ha prou factures (p.ex. contractes que abans es facturaven fora de l'aplicació), s'omplen
    # les barres que falten amb l'historial de lectures anterior a la factura més antiga: una lectura del
    # subministrament principal per barra, més les dels altres subministraments del contracte del mateix dia.
    history_readings = history.history_readings_by_contract.get(contract.id, []) if history is not None else None
    while readings_cutoff and len(dates) < MAX_BARS:
        if history_readings is not None:
            candidates = [
                row for row in history_readings
                if row['supply_point_id'] == contract.supply_point_default_id and row['reading_date'] is not None
                and row['reading_date'] < readings_cutoff and row['id'] not in used_reading_ids
            ]
            next_date = max((row['reading_date'] for row in candidates), default=None)
            if next_date is None:
                break
            same_day_readings = [
                row for row in history_readings
                if row['reading_date'] == next_date and row['id'] not in used_reading_ids
            ]
            same_day_values = [row['real_consumption'] for row in same_day_readings]
            same_day_ids = [row['id'] for row in same_day_readings]
        else:
            next_reading = Reading.objects.filter(
                contract=contract,
                supply_point=contract.supply_point_default,
                is_control=False,
                is_initial=False,
                is_active=True,
                reading_date__lt=readings_cutoff,
            ).exclude(id__in=used_reading_ids).order_by('-reading_date').first()

            if next_reading is None or next_reading.reading_date is None:
                break
            next_date = next_reading.reading_date
            same_day_readings = list(Reading.objects.filter(
                contract=contract,
                reading_date=next_date,
                is_control=False,
                is_initial=False,
                is_active=True,
            ).exclude(id__in=used_reading_ids))
            same_day_values = [reading.real_consumption for reading in same_day_readings]
            same_day_ids = [reading.id for reading in same_day_readings]

        dates.append(next_date)
        values.append(sum(float(value or 0) for value in same_day_values))
        used_reading_ids.update(same_day_ids)
        readings_cutoff = next_date

    return dates, values


def _previous_chart_invoices(invoice, contract, current_bar_date, history=None):
    """(id, consum, data) de les factures anteriors del contracte, de la més recent a la més antiga."""
    if history is not None:
        rows = [
            history.previous_invoices[invoice_id]
            for invoice_id in history.invoice_ids_by_contract.get(contract.id, ())
            if invoice_id in history.previous_invoices and invoice_id != invoice.id
        ]
        rows = [row for row in rows if row['period_date'] is not None and row['period_date'] < current_bar_date]
        rows.sort(key=lambda row: (row['period_date'], row['id']), reverse=True)
        return [(row['id'], row['consumption'], row['period_date']) for row in rows]

    excluded_statuses = [value for value in (
        _chart_config(token) for token in CHART_EXCLUDED_STATUS_CONFIG_TOKENS
    ) if value is not None]
    # Ids per separat: un OR entre `contract` i `contract_termination__contract` impedeix fer servir
    # els índexs i la consulta passa de mil·lisegons a segons per factura.
    contract_invoice_ids = list(Invoice.objects.filter(contract=contract).values_list('id', flat=True))
    contract_invoice_ids += list(Invoice.objects.filter(contract_termination__contract=contract).values_list('id', flat=True))
    previous_invoices = _valid_chart_invoices(
        Invoice.objects.filter(id__in=contract_invoice_ids), excluded_statuses, _chart_config('invoice_type_invoice_token'),
    ).exclude(
        id=invoice.id,
    ).filter(
        period_date__lt=current_bar_date,
    ).order_by('-period_date', '-id')
    return [(row['id'], row['consumption'], row['period_date']) for row in previous_invoices.values('id', 'consumption', 'period_date')]


def generate_chart(invoice, title, hide_background_and_logos=False):
    # Validate invoice
    if invoice is None:
        print("Error: Invoice cannot be None")
        return None
    
    if not hasattr(invoice, 'id') or invoice.id is None:
        print("Error: Invoice must have a valid id")
        return None
    
    contract = _chart_contract(invoice)
    if contract is None:
        print("Error: Invoice has no contract")
        return None
    
    # Validate supply_point_default
    if not hasattr(contract, 'supply_point_default') or contract.supply_point_default is None:
        print("Error: Contract has no supply_point_default")
        return None

    dates, values = get_chart_bars(invoice)
    if dates is None:
        return None

    # Validate we have data to plot
    if not dates or not values or len(dates) != len(values):
        print(f"Error: Insufficient data to generate chart: dates and values must be non-empty and equal length (dates: {len(dates)}, values: {len(values)})")
        return None
    
    plt.clf()
    # plt.figure(figsize=(7, 6))  # Removed unnecessary figure creation
    main_color = None
    secondary_color = None
    
    try:
        if invoice.company and invoice.company.invoice_main_color:
            main_color = invoice.company.invoice_main_color
        else:
            main_color = _chart_config('invoice_main_color')
    except (ConfigProject.DoesNotExist, AttributeError):
        main_color = None
    
    try:
        if invoice.company and invoice.company.invoice_secondary_color:
            secondary_color = invoice.company.invoice_secondary_color
        else:
            secondary_color = _chart_config('invoice_secondary_color')
    except (ConfigProject.DoesNotExist, AttributeError):
        secondary_color = None
    try:
        remove_bg_val = getattr(invoice.company, 'invoice_chart_remove_background', None) if invoice.company else None
        if remove_bg_val is not None:
            remove_background = bool(remove_bg_val)
        else:
            remove_bg_value = _chart_config('invoice_chart_remove_background')
            remove_background = bool(remove_bg_value and remove_bg_value.lower() == 'true')
    except (ConfigProject.DoesNotExist, AttributeError):
        remove_background = False

    # Use main_color if available, otherwise use default
    bg_color = None
    additional_color = None
    
    if main_color and isinstance(main_color, str) and len(main_color.lstrip('#')) >= 6:
        try:
            # Convert hex color to RGB tuple (0-1 range for matplotlib)
            hex_color = main_color.lstrip('#')
            if len(hex_color) >= 6:
                base_color = tuple(int(hex_color[i:i+2], 16) / 255.0 for i in (0, 2, 4))
                if secondary_color and isinstance(secondary_color, str) and len(secondary_color.lstrip('#')) >= 6:
                    secondary_hex_color = secondary_color.lstrip('#')
                    if len(secondary_hex_color) >= 6:
                        base_color = tuple(int(secondary_hex_color[i:i+2], 16) / 255.0 for i in (0, 2, 4))
                        bg_color = tuple(int(hex_color[i:i+2], 16) / 255.0 for i in (0, 2, 4))
                        # Set additional color to complementary color of bg_color
                        additional_color = get_darker_color(base_color)
                    else:
                        additional_color = get_darker_color(base_color)
                else:
                    additional_color = get_darker_color(base_color)
            else:
                base_color = (0.2, 0.4, 0.8)
                additional_color = (0.4, 0.6, 0.95)
        except (ValueError, IndexError):
            # Invalid hex color, use defaults
            base_color = (0.2, 0.4, 0.8)
            bg_color = None
            additional_color = (0.4, 0.6, 0.95)
    else:
        base_color = (0.2, 0.4, 0.8)
        bg_color = None
        additional_color = (0.4, 0.6, 0.95)

    # Color de barres propi del projecte. Buit: es fan servir els colors de la factura.
    chart_bar_color = rgb_from_hex(_chart_config('invoice_chart_bar_color'))
    if chart_bar_color:
        base_color = chart_bar_color
        bg_color = None
        additional_color = get_darker_color(base_color)

    fig, ax = plt.subplots(figsize=(7, 6))  # Create figure and axis

    # Use equally spaced positions instead of dates for x-axis
    x_positions = list(range(len(dates)))[::-1]
    MAX_BAR_WIDTH = 0.4  # Cap width so a single bar doesn't span the full chart
    bar_width = MAX_BAR_WIDTH if len(dates) == 1 else 0.6

    try:
        ax.bar(x=x_positions, 
            height=values,
            width=bar_width,
            align='center',
            color=base_color,
            label='Subministrament principal')
    except (ValueError, TypeError) as e:
        print(f"Error creating bar chart: {str(e)}")
        plt.close(fig)
        return None

    # Add value labels on top of each bar
    for i in range(len(dates)):
        try:
            if i < len(values):
                total = float(values[i])
                ax.text(x=x_positions[i],
                        y=total + 0.5,
                        s=f'{total:.0f}',
                        ha='center',
                        va='bottom',
                        fontsize=20)
        except (IndexError, ValueError, TypeError) as e:
            # Skip this label if there's an error
            continue

    # Adjust ylim to account for total height
    try:
        total_height = [float(v) for v in values if v is not None]
        if total_height:
            ax.set_ylim(0, max(total_height) + 5)
        else:
            ax.set_ylim(0, 10)  # Default range if no valid heights
    except (ValueError, TypeError):
        ax.set_ylim(0, 10)  # Default range on error

    try:
        # Set x-axis ticks to equally spaced positions, but label them with dates
        ax.set_xticks(x_positions)
        ax.set_xticklabels([d.strftime('%m/%y') if hasattr(d, 'strftime') else str(d) for d in dates], fontsize=24, ha='center')
        ax.tick_params(axis='y', labelsize=24)
        # Fix x-axis range so a single bar doesn't fill the whole chart
        if len(dates) == 1:
            ax.set_xlim(-0.75, 0.75)
        else:
            ax.set_xlim(min(x_positions) - 0.5, max(x_positions) + 0.5)
    except (ValueError, AttributeError) as e:
        print(f"Warning: Error setting x-axis labels: {str(e)}")

    # Hide the top and right spines (borders)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    
    if bg_color and not hide_background_and_logos and not remove_background:
        ax.set_facecolor(bg_color)
        fig.patch.set_facecolor(bg_color)
        
        ax.yaxis.label.set_color(base_color)
        ax.xaxis.label.set_color(base_color)
        ax.tick_params(axis='both', colors=base_color)
        ax.spines['left'].set_color(base_color)
        ax.spines['bottom'].set_color(base_color)
        for text in ax.texts:
            text.set_color(base_color)
    
    else:
        fig.patch.set_facecolor('none')
        ax.set_facecolor('none')

    try:
        plt.tight_layout()
    except Exception as e:
        print(f"Warning: Error in tight_layout: {str(e)}")

    # El gràfic va incrustat al PDF com a data URI: no es desa a MEDIA_ROOT, perquè allà
    # quedaria accessible per URL (/media/...) amb un camí fàcil d'endevinar.
    buf = BytesIO()
    try:
        plt.savefig(buf, format='png', dpi=72, transparent=hide_background_and_logos)
        encoded = base64.b64encode(buf.getvalue()).decode('ascii')
    except Exception as e:
        print(f"Error rendering chart: {str(e)}")
        return None
    finally:
        buf.close()
        plt.close(fig)

    return f"data:image/png;base64,{encoded}"
