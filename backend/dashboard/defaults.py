import uuid

# Disposició inicial per a qui encara no ha personalitzat la pàgina d'inici. Les
# cards per a les quals l'usuari no té permís es descarten en servir-la.
DEFAULT_LAYOUT = [
    {'key': 'daily_activity', 'size': 'lg'},
    {'key': 'tasks_today', 'size': 'md'},
    {'key': 'orders_to_validate', 'size': 'md'},
    {'key': 'reading_batches_in_progress', 'size': 'lg'},
    {'key': 'invoices_issued', 'size': 'sm'},
    {'key': 'invoice_cancellations', 'size': 'sm'},
    {'key': 'rebillings', 'size': 'sm'},
    {'key': 'recent_searches', 'size': 'lg'},
    {'key': 'calendar', 'size': 'lg'},
    {'key': 'quick_access', 'size': 'lg'},
]


def default_layout():
    return [{'id': str(uuid.uuid4()), 'config': {}, **item} for item in DEFAULT_LAYOUT]
