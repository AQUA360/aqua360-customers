"""
Utilitats per gestionar dates i temps en el mòdul de facturació.
"""

from datetime import datetime, timedelta, date
from django.utils import timezone


def convert_date_with_timezone(date_value, date_formats=None):
    """
    Converteix un valor de data a datetime amb timezone.
    
    Args:
        date_value: Pot ser str, datetime, date o None
        date_formats: Llista opcional de formats de data per provar (per defecte usa formats comuns)
        
    Returns:
        datetime amb timezone o None si no es pot convertir
    """
    if not date_value:
        return None
    
    # Formats de data per defecte si no s'especifiquen
    if date_formats is None:
        date_formats = [
            '%Y-%m-%d',           # 2023-12-25
            '%Y-%m-%d %H:%M:%S',  # 2023-12-25 14:30:00
            '%d-%m-%Y',           # 25-12-2023
            '%d/%m/%Y',           # 25/12/2023
            '%Y-%m-%d %H:%M',     # 2023-12-25 14:30
            '%d-%m-%Y %H:%M:%S',  # 25-12-2023 14:30:00
            '%d/%m/%Y %H:%M:%S',  # 25/12/2023 14:30:00
        ]
    
    aware_datetime = None
    
    if isinstance(date_value, str):
        # Si és una string, intentar parsejar-la amb diferents formats
        for fmt in date_formats:
            try:
                naive_datetime = datetime.strptime(date_value, fmt)
                aware_datetime = timezone.make_aware(naive_datetime)
                break
            except (ValueError, TypeError):
                continue
    elif isinstance(date_value, datetime):
        # Si ja és un datetime, comprovar si té timezone
        if timezone.is_naive(date_value):
            aware_datetime = timezone.make_aware(date_value)
        else:
            aware_datetime = date_value
    elif isinstance(date_value, date):
        # Si és un objecte date, convertir-lo a datetime
        naive_datetime = datetime.combine(date_value, datetime.min.time())
        aware_datetime = timezone.make_aware(naive_datetime)
    
    return aware_datetime


def convert_send_at_to_aware_datetime(send_at):
    """
    Converteix un valor send_at a datetime amb timezone.
    Aquesta funció manté la compatibilitat amb codi existent.
    
    Args:
        send_at: Pot ser str, datetime, date o None
        
    Returns:
        datetime amb timezone o None si no es pot convertir
    """
    return convert_date_with_timezone(send_at)