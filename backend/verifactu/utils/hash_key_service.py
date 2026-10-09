import base64
import json
import qrcode
import io
import hashlib
from datetime import datetime, timezone
from decimal import Decimal
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives import serialization
from decouple import config

from billing.models import Invoice
from verifactu.utils.qr_service import generate_qr_base64
from verifactu.utils.notify_verifactu_service import build_invoices_data_body

def sha256_hex_bytes(data: bytes) -> str:
    """Generate SHA256 hash from bytes."""
    h = hashlib.sha256()
    h.update(data)
    return h.hexdigest().upper()

# ----------------------------
# Verifactu Hash Generation
# ----------------------------

def _normalize_numeric_value(value: str) -> str:
    """
    Format numeric values according to Verifactu specification.
    
    According to Verifactu spec, numeric values should be formatted with exactly 2 decimal places.
    This ensures consistency in hash calculation.
    Example: '123.1' -> '123.10', '123' -> '123.00', '123.456' -> '123.46' (rounded)
    """
    if not value:
        return value
    
    value = value.strip()
    if not value:
        return value
    
    try:
        # Parse as decimal
        decimal_val = Decimal(value)
        
        # Format with exactly 2 decimal places
        # This ensures consistent formatting for hash calculation
        formatted = decimal_val.quantize(Decimal('0.01'))
        
        # Convert to string with 2 decimal places
        return f"{formatted:.2f}"
    except (ValueError, TypeError):
        # If not a valid number, return as is (after trimming)
        return value.strip()


def _format_field_value(value, is_numeric: bool = False) -> str:
    """
    Format field value according to Verifactu rules:
    - Remove leading and trailing spaces
    - For numeric fields, normalize decimal places (remove trailing zeros)
    - If value is None or empty, return empty string
    """
    if value is None:
        return ''
    
    value_str = str(value).strip()
    
    if not value_str:
        return ''
    
    if is_numeric:
        return _normalize_numeric_value(value_str)
    
    return value_str


def _build_hash_string(
    id_emisor_factura: str,
    num_serie_factura: str,
    fecha_expedicion_factura: str,
    tipo_factura: str,
    cuota_total: str,
    importe_total: str,
    huella: str = None,
    fecha_hora_huso_gen_registro: str = None
) -> str:
    """
    Build the hash string from individual fields according to Verifactu specification.
    Format: nombreCampo1=valorCampo1&nombreCampo2=valorCampo2&...
    """
    parts = []
    
    # 1. IDEmisorFactura
    id_emisor = _format_field_value(id_emisor_factura)
    parts.append(f"IDEmisorFactura={id_emisor}")
    
    # 2. NumSerieFactura
    num_serie = _format_field_value(num_serie_factura)
    parts.append(f"NumSerieFactura={num_serie}")
    
    # 3. FechaExpedicionFactura
    fecha_exp = _format_field_value(fecha_expedicion_factura)
    parts.append(f"FechaExpedicionFactura={fecha_exp}")
    
    # 4. TipoFactura
    tipo_factura_val = _format_field_value(tipo_factura)
    parts.append(f"TipoFactura={tipo_factura_val}")
    
    # 5. CuotaTotal (numeric)
    cuota_total_val = _format_field_value(cuota_total, is_numeric=True)
    parts.append(f"CuotaTotal={cuota_total_val}")
    
    # 6. ImporteTotal (numeric)
    importe_total_val = _format_field_value(importe_total, is_numeric=True)
    parts.append(f"ImporteTotal={importe_total_val}")
    
    # 7. Huella (from previous invoice)
    huella_val = _format_field_value(huella)
    parts.append(f"Huella={huella_val}")
    
    # 8. FechaHoraHusoGenRegistro
    fecha_hora = _format_field_value(fecha_hora_huso_gen_registro)
    parts.append(f"FechaHoraHusoGenRegistro={fecha_hora}")
    
    return '&'.join(parts)


def sha256_hex(
    id_emisor_factura: str,
    num_serie_factura: str,
    fecha_expedicion_factura: str,
    tipo_factura: str,
    cuota_total: str,
    importe_total: str,
    huella: str = None,
    fecha_hora_huso_gen_registro: str = None,
    debug: bool = False
) -> str:
    """
    Generate SHA256 hash for Verifactu invoice according to AEAT specification.
    
    The hash is generated from a concatenated string of specific fields,
    following the format: nombreCampo1=valorCampo1&nombreCampo2=valorCampo2&...
    
    Output format (according to AEAT specification):
    - Hexadecimal format
    - Uppercase
    - 64 alphanumeric characters
    
    Args:
        id_emisor_factura: IDEmisorFactura (NIF del emisor)
        num_serie_factura: NumSerieFactura (número de serie de la factura)
        fecha_expedicion_factura: FechaExpedicionFactura (formato DD-MM-YYYY)
        tipo_factura: TipoFactura (ej: 'F1')
        cuota_total: CuotaTotal (valor numérico como string)
        importe_total: ImporteTotal (valor numérico como string)
        huella: Huella del registro anterior (opcional)
        fecha_hora_huso_gen_registro: FechaHoraHusoGenRegistro (formato ISO 8601 con timezone, opcional)
        debug: If True, print the hash string before hashing (for debugging)
    
    Fields used (in order):
    1. IDEmisorFactura
    2. NumSerieFactura
    3. FechaExpedicionFactura
    4. TipoFactura
    5. CuotaTotal
    6. ImporteTotal
    7. Huella (from previous invoice)
    8. FechaHoraHusoGenRegistro
    
    Rules:
    - Remove leading and trailing spaces from all values
    - For numeric fields (CuotaTotal, ImporteTotal), format with exactly 2 decimal places
    - If a field is missing or empty, use nombreCampo= (field name and equals sign, no value)
    """
    # Build the hash string
    hash_string = _build_hash_string(
        id_emisor_factura=id_emisor_factura,
        num_serie_factura=num_serie_factura,
        fecha_expedicion_factura=fecha_expedicion_factura,
        tipo_factura=tipo_factura,
        cuota_total=cuota_total,
        importe_total=importe_total,
        huella=huella,
        fecha_hora_huso_gen_registro=fecha_hora_huso_gen_registro
    )
    
    if debug:
        print(f"DEBUG Hash string: {hash_string}")
        print(f"DEBUG Hash string bytes: {hash_string.encode('utf-8')}")
    
    # Generate SHA256 hash
    return sha256_hex_bytes(hash_string.encode('utf-8'))
