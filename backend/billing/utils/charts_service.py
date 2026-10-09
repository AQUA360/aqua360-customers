import os
import matplotlib
matplotlib.use('Agg')  # Set backend before importing pyplot
import matplotlib.pyplot as plt
from billing.models import Reading, Invoice
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
    
    dates = []
    values = []
    extra_values = []
    used_reading_ids = set()

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

    # Current invoice bar: aggregate every reading attached to this invoice (resolving any
    # control reading to its corrected value), summed per supply point, instead of one bar
    # per reading - this is what makes a meter change within the same billing show as a
    # single bar with the combined consumption.
    main_total = 0.0
    extra_total = 0.0
    has_main = False
    bar_date = None

    # `invoice.readings` només conté la lectura final de cada comptador facturat: en un
    # canvi de comptador a mig període, `reading.real_consumption` es queda amb el consum
    # propi d'aquesta lectura (p.ex. 14) i el total combinat (p.ex. 14+45=59) només viu a
    # `invoice.consumption` -- la lectura de tancament del comptador substituït (real_consumption
    # ja correcte, no cal recalcular-lo) queda enllaçada via previous_reading pero mai
    # s'afegeix a invoice.readings.set(...). Sense això la barra només reflectia el consum
    # del comptador nou (mateix bug que a les taules "Dades de consum" del PDF, corregit
    # amb `meter_change_readings`). Sumar-hi aquesta
    # lectura addicional no duplica res: real_consumption de la lectura final mai inclou ja
    # el consum del comptador substituït.
    chart_readings = []
    if hasattr(invoice, 'readings'):
        invoice_reading_ids = set(invoice.readings.filter(is_active=True).values_list('id', flat=True))
        for reading in invoice.readings.filter(is_active=True):
            chart_readings.append(reading)
            prev = reading.previous_reading
            if prev and prev.is_close and prev.id not in invoice_reading_ids:
                chart_readings.append(prev)
            prev_prev = prev.previous_reading if prev else None
            if prev_prev and prev_prev.is_close and prev_prev.id not in invoice_reading_ids:
                chart_readings.append(prev_prev)

    for reading in chart_readings:
        resolved = resolve_reading(reading)
        used_reading_ids.add(resolved.id)

        if resolved.reading_date and (bar_date is None or resolved.reading_date > bar_date):
            bar_date = resolved.reading_date

        value = float(resolved.real_consumption) if resolved.real_consumption is not None else 0.0
        if resolved.supply_point_id == contract.supply_point_default_id:
            main_total += value
            has_main = True
        else:
            extra_total += value

    if not has_main or bar_date is None:
        print("Error: No readings found for contract")
        return None

    dates.append(bar_date)
    values.append(main_total)
    extra_values.append(extra_total)

    # Earlier bars: walk the reading history backwards (one final reading per bar), the same
    # way previous billings were charted before, but skip any reading already folded into a
    # more recent bar so it isn't double counted.
    cutoff_date = min(
        (r.reading_date for r in Reading.objects.filter(id__in=used_reading_ids) if r.reading_date),
        default=bar_date,
    )

    for i in range(4):
        try:
            next_reading = Reading.objects.filter(
                contract=contract,
                supply_point=contract.supply_point_default,
                is_control=False,
                is_initial=False,
                is_active=True,
                reading_date__lt=cutoff_date,
            ).exclude(id__in=used_reading_ids).order_by('-reading_date').first()

            if next_reading is None or next_reading.reading_date is None:
                break

            extra_readings = Reading.objects.filter(
                contract=contract,
                reading_date=next_reading.reading_date,
                is_control=False,
                is_initial=False,
                is_active=True,
            ).exclude(supply_point=next_reading.supply_point).exclude(id__in=used_reading_ids)

            dates.append(next_reading.reading_date)
            values.append(float(next_reading.real_consumption) if next_reading.real_consumption is not None else 0.0)
            extra_values.append(sum(
                float(reading.real_consumption) if reading.real_consumption is not None else 0.0
                for reading in extra_readings
            ))

            used_reading_ids.add(next_reading.id)
            used_reading_ids.update(extra_readings.values_list('id', flat=True))
            cutoff_date = next_reading.reading_date
        except (AttributeError, ValueError) as e:
            break
        except Exception as e:
            # Log unexpected errors but continue
            print(f"Error processing reading {i}: {str(e)}")
            break

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

    # Ensure extra_values matches dates length
    while len(extra_values) < len(dates):
        extra_values.append(0)
    
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

    if any(extra_value != 0 for extra_value in extra_values):
        try:
            ax.bar(x=x_positions,
                height=extra_values,
                width=bar_width,
                align='center',
                color=additional_color,
                bottom=values,
                label='Subministrament adicional')
        except (ValueError, TypeError) as e:
            # Continue without extra bars if there's an error
            print(f"Warning: Could not add extra bars: {str(e)}")

    # Add value labels on top of each bar
    for i in range(len(dates)):
        try:
            if i < len(values) and i < len(extra_values):
                total = float(values[i]) + float(extra_values[i])
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
        total_height = [float(v1) + float(v2) for v1, v2 in zip(values, extra_values) if v1 is not None and v2 is not None]
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
