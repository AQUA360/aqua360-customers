# Importar els mòduls registra les cards (decorador @register).
from . import general, orders, readings, billing, tasks  # noqa: F401
from .base import all_cards, available_cards, get_card  # noqa: F401
