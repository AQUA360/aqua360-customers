from io import BytesIO
import os
import re
import barcode
from barcode.writer import SVGWriter, ImageWriter
from coredata.models import ConfigProject

class BarcodeResponse(list):
    """
    Clase para mantener compatibilidad con llamadas que esperan una lista [rv, string]
    pero permitiendo acceder a los valores extraídos y al método getvalue() directamente.
    """
    def __init__(self, rv, barcode_string, barcode_values):
        super().__init__([rv, barcode_string])
        self.barcode_values = barcode_values
    
    def getvalue(self):
        return self[0].getvalue()

def get_reference_suffix():
    config = ConfigProject.objects.filter(token='reference_suffix_barcode_token').first()
    suffix = str(config.value).strip() if config and config.value else '501'
    if not suffix.isdigit():
        suffix = '501'
    return suffix

def get_barcode_values(barcode_data):
    """
    Calcula y retorna los valores individuales que componen el código de barras.
    """
    company = barcode_data.get('company')
    if not company:
        raise Exception("Company not found")
    
    app_id = '90'
    format_type = '507'
    after_format = '00'
    
    vat = company.vat
    
    if company.company_banks.count() > 0:
        if company.company_banks.count() == 1:
            bank_account = company.company_banks.first()
        else:
            bank_account = company.company_banks.filter(is_default=True, is_active=True).first()
        if bank_account:
            vat = bank_account.barcode_cif if bank_account.barcode_cif else company.vat
    
    transmitter_numeric = re.sub(r'[^0-9]', '', vat or '')
    if not transmitter_numeric:
        raise Exception("Company VAT does not contain any digits")
    transmitter = str(int(transmitter_numeric)).zfill(8)
    
    reference = barcode_data.get('reference')
    if not reference:
        raise Exception("Reference not found")
    
    reference = str(reference).zfill(11)
        
    ident = barcode_data.get('ident')
    if not ident:
        raise Exception("Ident not found")                   
    
    total_final = barcode_data.get('total_final')
    if total_final == None:
        raise Exception("Total final not found")
        
    total_decimals = str(total_final)[str(total_final).find('.'):].replace('.','')
    total_whole = int(total_final) 
    total_str = repeat_to_at_least_length('0', 8 - len(str(total_whole))) + str(total_whole) + str(total_decimals) + repeat_to_at_least_length('0', 2 - len(str(total_decimals))) 
    
    final_digit = '0'                   # to check
    reference_suffix = get_reference_suffix()
    
    # Cálculo del dígito de control para la referencia
    sum_all = int(transmitter) + int(reference_suffix) + int(reference) + int(ident) + int(str(total_final).replace('.',''))
    divided = sum_all / 97
    decimal_part = str(divided).split('.')[-1]
    
    control_digit = 100 - int(decimal_part[:2])
    if control_digit == 100:
        control_digit = 0
    
    reference_with_control = f"{reference}{repeat_to_at_least_length('0', 2 - len(str(control_digit)))}{control_digit}"
    
    return {
        'app_id': app_id,
        'format_type': format_type,
        'transmitter': transmitter,
        'suffix': reference_suffix,
        'display_reference': reference_with_control,
        'reference': f"{reference_suffix}{reference_with_control}",
        'ident': ident,
        'total': f'{total_str}{final_digit}',
    }

def generate_barcode(barcode_data, show_string=True):
    """ 
    https://www.caixabank.es/deployedfiles/empresas/Estaticos/pdf/Transferenciasyficheros/Cuaderno64_Junio_2016.pdf
    """
    barcode_values = get_barcode_values(barcode_data)
    
    final_barcode_string = (
        f"{barcode_values['app_id']}"
        f"{barcode_values['format_type']}"
        f"{barcode_values['transmitter']}"
        f"{barcode_values['reference']}"
        f"{barcode_values['ident']}"
        f"{barcode_values['total']}"
    )
    
    code128 = barcode.get_barcode_class('code128')
    barcode_instance = code128(final_barcode_string, writer=ImageWriter())
        
    options = {
        'module_width': 0.3,  
        'module_height': 9.0,  
        'font_size': 9.0,
        'write_text': show_string,
    }
    
    rv = BytesIO()
    barcode_instance.write(rv, options)
    return rv
    
def repeat_to_at_least_length(s, wanted):
    if wanted >= 0:
        return s * (wanted//len(s))
    return ''