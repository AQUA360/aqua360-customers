import os
import matplotlib
matplotlib.use('Agg')  # Set backend before importing pyplot
import matplotlib.pyplot as plt
from billing.models import Reading, Invoice
from django.db.models import Max, Q
from io import BytesIO
from django.core.files.base import ContentFile
from django.conf import settings
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

def get_invoice_chart_readings(invoice):
    """Lectures que ha cobrat una factura. `invoice.readings` només conté la lectura final de cada
    comptador: en un canvi de comptador a mig període, la lectura de tancament del comptador substituït
    queda enllaçada via previous_reading i no a invoice.readings, i també s'ha de tenir en compte."""
    invoice_readings = list(invoice.readings.filter(is_active=True))
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

def generate_chart(invoice, title, hide_background_and_logos=False):
    # Validate invoice
    if invoice is None:
        print("Error: Invoice cannot be None")
        return None
    
    if not hasattr(invoice, 'id') or invoice.id is None:
        print("Error: Invoice must have a valid id")
        return None
    
    contract = None
    
    if hasattr(invoice, 'contract') and invoice.contract:
        contract = invoice.contract
    elif hasattr(invoice, 'contract_termination') and invoice.contract_termination:
        if hasattr(invoice.contract_termination, 'contract') and invoice.contract_termination.contract:
            contract = invoice.contract_termination.contract
    
    if contract is None:
        print("Error: Invoice has no contract")
        return None
    
    # Validate supply_point_default
    if not hasattr(contract, 'supply_point_default') or contract.supply_point_default is None:
        print("Error: Contract has no supply_point_default")
        return None

    # Cada barra és el consum facturat (`Invoice.consumption`) d'una factura del contracte, no el
    # recalculat a partir de les lectures: així el gràfic coincideix amb el que s'ha cobrat (comptadors
    # generals, canvis de comptador, fuites, refacturacions...). Cada factura es posiciona per la data
    # de la seva última lectura, que una refacturació comparteix amb la factura original; l'issue_date
    # i el billing_period passen a ser els de la refacturació i la mourien de lloc. Només compten factures
    # amb lectures: n'hi ha sense lectures (derrames...) que tenen `consumption` desat amb un valor que no
    # és consum d'aigua.
    dates = []
    values = []
    used_reading_ids = set()
    # Data de la lectura més antiga ja representada: l'historial de lectures només s'usa per sota
    readings_cutoff = None

    def add_invoice_bar(bar_invoice, bar_date):
        nonlocal readings_cutoff
        chart_readings = get_invoice_chart_readings(bar_invoice)
        if bar_invoice.consumption is not None:
            value = float(bar_invoice.consumption)
        else:
            # Factura de consum sense el consum desat: es calcula a partir de les seves lectures
            value = sum(float(reading.real_consumption or 0) for reading in chart_readings)
        dates.append(bar_date)
        values.append(value)
        used_reading_ids.update(reading.id for reading in chart_readings)
        readings_cutoff = min([reading.reading_date for reading in chart_readings if reading.reading_date] + [bar_date])

    current_bar_date = invoice.readings.filter(is_active=True).aggregate(m=Max('reading_date'))['m']
    if current_bar_date is None:
        print("Error: Invoice has no readings")
        return None
    add_invoice_bar(invoice, current_bar_date)

    # Barres anteriors: factures vàlides del contracte. S'exclouen pressupostos, factures abonades o
    # anul·lades (i els seus abonaments, que copien el consum en positiu) i factures sense lectures.
    excluded_statuses = list(ConfigProject.objects.filter(
        token__in=['invoice_status_cancelled_token', 'invoice_status_payoff_token', 'invoice_status_dropped_token']
    ).values_list('value', flat=True))
    invoice_type_token = ConfigProject.objects.filter(token='invoice_type_invoice_token').values_list('value', flat=True).first()

    # Ids per separat: un OR entre `contract` i `contract_termination__contract` impedeix fer servir
    # els índexs i la consulta passa de mil·lisegons a segons per factura.
    contract_invoice_ids = list(Invoice.objects.filter(contract=contract).values_list('id', flat=True))
    contract_invoice_ids += list(Invoice.objects.filter(contract_termination__contract=contract).values_list('id', flat=True))

    previous_invoices = Invoice.objects.filter(
        id__in=contract_invoice_ids,
        is_active=True,
        is_suppressed=False,
        type__token=invoice_type_token,
    ).filter(
        Q(return_token__isnull=True) | Q(return_token=''),
    ).exclude(
        status__token__in=excluded_statuses,
    ).exclude(
        id=invoice.id,
    ).annotate(
        period_date=Max('readings__reading_date', filter=Q(readings__is_active=True)),
    ).filter(
        period_date__lt=current_bar_date,
    ).order_by('-period_date', '-id')

    for previous_invoice in previous_invoices:
        if len(dates) >= MAX_BARS:
            break
        # Una sola barra per període si hi hagués més d'una factura vàlida amb la mateixa data
        if previous_invoice.period_date in dates:
            continue
        add_invoice_bar(previous_invoice, previous_invoice.period_date)

    # Si no hi ha prou factures (p.ex. contractes que abans es facturaven fora de l'aplicació), s'omplen
    # les barres que falten amb l'historial de lectures anterior a la factura més antiga: una lectura del
    # subministrament principal per barra, més les dels altres subministraments del contracte del mateix dia.
    while readings_cutoff and len(dates) < MAX_BARS:
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

        same_day_readings = list(Reading.objects.filter(
            contract=contract,
            reading_date=next_reading.reading_date,
            is_control=False,
            is_initial=False,
            is_active=True,
        ).exclude(id__in=used_reading_ids))

        dates.append(next_reading.reading_date)
        values.append(sum(float(reading.real_consumption or 0) for reading in same_day_readings))
        used_reading_ids.update(reading.id for reading in same_day_readings)
        readings_cutoff = next_reading.reading_date

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
            main_color_obj = ConfigProject.objects.get(token='invoice_main_color')
            if main_color_obj and hasattr(main_color_obj, 'value'):
                main_color = main_color_obj.value
    except (ConfigProject.DoesNotExist, AttributeError):
        main_color = None
    
    try:
        if invoice.company and invoice.company.invoice_secondary_color:
            secondary_color = invoice.company.invoice_secondary_color
        else:
            secondary_color_obj = ConfigProject.objects.get(token='invoice_secondary_color')
            if secondary_color_obj and hasattr(secondary_color_obj, 'value'):
                secondary_color = secondary_color_obj.value
    except (ConfigProject.DoesNotExist, AttributeError):
        secondary_color = None
    try:
        remove_bg_val = getattr(invoice.company, 'invoice_chart_remove_background', None) if invoice.company else None
        if remove_bg_val is not None:
            remove_background = bool(remove_bg_val)
        else:
            remove_bg_obj = ConfigProject.objects.get(token='invoice_chart_remove_background')
            remove_background = (remove_bg_obj and hasattr(remove_bg_obj, 'value') and remove_bg_obj.value.lower() == 'true')
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

    # Validate invoice.id and invoice.token
    if not hasattr(invoice, 'id') or invoice.id is None:
        print("Error: Invoice must have a valid id")
        plt.close(fig)
        return None
    
    invoice_token = getattr(invoice, 'token', None) or f'invoice_{invoice.id}'
    
    try:
        chart_dir = os.path.join(settings.MEDIA_ROOT, 'uploads', 'billing', 'invoices', str(invoice.id), 'charts')
        os.makedirs(chart_dir, exist_ok=True)
    except (OSError, AttributeError) as e:
        print(f"Error creating chart directory: {str(e)}")
        plt.close(fig)
        return None

    file_name = f"{invoice_token}_chart.png"
    file_path = os.path.join(chart_dir, file_name)

    buf = None
    try:
        buf = BytesIO()
        plt.savefig(buf, format='png', dpi=72, transparent=hide_background_and_logos)
        buf.seek(0)
        
        with open(file_path, 'wb') as f:
            f.write(buf.read())
    except Exception as e:
        print(f"Error saving chart: {str(e)}")
        if buf:
            buf.close()
        plt.close(fig)
        return None
    finally:
        if buf:
            buf.close()
        plt.close(fig)

    return file_path
