"""
QR URL Helper for Verifactu

Generates properly URL-encoded validation URLs for Verifactu invoices.
Complies with Spanish government requirements:
- URL encoding (percent encoding) for all parameters
- UTF-8 encoding
- Proper handling of special characters
"""

from django.conf import settings
from decouple import config
from urllib.parse import urlencode
from typing import Optional
from datetime import datetime
import re


def format_fecha_to_dd_mm_aaaa(fecha) -> str:
    """
    Formats a date to DD-MM-AAAA format as required by Verifactu.
    
    Accepts:
    - datetime objects
    - date objects
    - strings in various formats (YYYY-MM-DD, DD/MM/YYYY, DD-MM-YYYY, etc.)
    
    Returns:
    - String in DD-MM-AAAA format (e.g., "01-01-2024")
    """
    # If it's already a datetime or date object
    if isinstance(fecha, datetime):
        return fecha.strftime("%d-%m-%Y")
    elif hasattr(fecha, 'strftime'):  # date objects
        return fecha.strftime("%d-%m-%Y")
    
    # If it's a string, try to parse it
    if isinstance(fecha, str):
        fecha = fecha.strip()
        
        # Check if it's already in DD-MM-AAAA format
        if re.match(r'^\d{2}-\d{2}-\d{4}$', fecha):
            return fecha
        
        # Try to parse common date formats
        date_formats = [
            "%Y-%m-%d",      # 2024-01-01
            "%d/%m/%Y",      # 01/01/2024
            "%d-%m-%Y",      # 01-01-2024
            "%Y/%m/%d",      # 2024/01/01
            "%d.%m.%Y",      # 01.01.2024
        ]
        
        for fmt in date_formats:
            try:
                parsed_date = datetime.strptime(fecha, fmt)
                return parsed_date.strftime("%d-%m-%Y")
            except ValueError:
                continue
        
        # If we can't parse it, try to extract date parts from various formats
        # This is a fallback for edge cases
        date_match = re.search(r'(\d{1,2})[-\/\.](\d{1,2})[-\/\.](\d{4})', fecha)
        if date_match:
            day, month, year = date_match.groups()
            try:
                parsed_date = datetime(int(year), int(month), int(day))
                return parsed_date.strftime("%d-%m-%Y")
            except ValueError:
                pass
    
    # If all else fails, raise an error
    raise ValueError(f"Unable to parse fecha '{fecha}' to DD-MM-AAAA format")


def generate_verifactu_url(numserie: str, fecha, importe: str) -> Optional[str]:
    """
    Segons la documentació de Verifactu:
        A fin de asegurar que todos sus caracteres sean leídos e interpretados correctamente,
        la «URL» de cotejo o remisión de información de la factura contenida en el código «QR»
        que debe aparecer en la factura, concretamente el contenido de los parámetros, deberán
        ser codificados de forma adecuada siguiendo los estándares generales de las
        aplicaciones en entorno web («URL encoding») y utilizando la codificación UTF-8.
        Con el fin de especificar el uso del «URL encoding», se muestra un ejemplo de factura
        con el siguiente conjunto de parámetros, para el entorno de Pruebas Externas:
         URL base: https://prewww2.aeat.es/wlpl/TIKE-CONT/ValidarQR?
         Parámetro nif: 89890001K
         Parámetro numserie: 12345678&G33
         Parámetro fecha: 01-01-2024 (format DD-MM-AAAA)
         Parámetro importe: 241.4
    
    Args:
        nif: NIF del emisor
        numserie: Número de serie de la factura
        fecha: Fecha (datetime, date, o string en varios formatos) - se formateará a DD-MM-AAAA
        importe: Importe de la factura
    
    Example:
        generate_url("89890001K", "12345678&G33", "01-01-2024", "241.4")
        Returns: "https://prewww2.aeat.es/wlpl/TIKE-CONT/ValidarQR?nif=89890001K&numserie=12345678%26G33&fecha=01-01-2024&importe=241.4"
    """
    base_url = getattr(settings, 'VERIFACTU_URL_VALIDATOR', None) or config('VERIFACTU_URL_VALIDATOR', default=None)
    
    if not base_url:
        return None
    
    # Ensure base URL doesn't end with '?' (we'll add query parameters)
    base_url = base_url.rstrip('?')
    
    # Format fecha to DD-MM-AAAA format as required by Verifactu
    fecha_formatted = format_fecha_to_dd_mm_aaaa(fecha)
    
    nif = config('VERIFACTU_NIF')
    if not nif:
        return None
    
    # Prepare parameters as a dictionary
    # All values will be properly URL-encoded by urlencode
    params = {
        'nif': nif,
        'numserie': numserie,
        'fecha': fecha_formatted,
        'importe': importe
    }
    
    # Use urlencode to properly URL-encode all parameters
    # urlencode automatically:
    # - URL-encodes (percent-encodes) all parameter values
    # - Uses UTF-8 encoding (default in Python 3 for string encoding)
    # - Handles special characters like &, =, spaces, etc.
    # 
    # Example: "12345678&G33" becomes "12345678%26G33"
    # 
    # Note: In Python 3, urlencode works with Unicode strings and automatically
    # encodes them as UTF-8 when converting to percent-encoded format
    query_string = urlencode(params)
    
    # Construct the full URL
    full_url = f"{base_url}?{query_string}"
    
    return full_url
  