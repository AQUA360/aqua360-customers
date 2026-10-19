"""
Protecció global contra la injecció de fórmules als Excel que genera l'aplicació.

OpenPyXL desa com a fórmula qualsevol text que comenci per `=`. Si aquest text
ve de dades que escriuen els usuaris (noms, adreces, observacions...), Excel
l'executa en obrir el fitxer. L'aplicació no escriu fórmules expressament, així
que tots els textos es desen com a text.

Només afecta els valors assignats des del codi (`cell.value = ...`,
`ws.append(...)`): en llegir un fitxer amb `load_workbook`, les fórmules que ja
té es conserven. Les fórmules explícites (`ArrayFormula`, `DataTableFormula`)
tampoc es veuen afectades, perquè no són text.
"""
from openpyxl.cell.cell import Cell

_original_bind_value = Cell._bind_value


def _bind_value_as_text(self, value):
    _original_bind_value(self, value)
    if self.data_type == "f" and isinstance(self._value, str):
        self.data_type = "s"


def disable_string_formulas():
    """S'executa en arrencar Django (DocumentmanagerConfig.ready), també als workers de Celery."""
    Cell._bind_value = _bind_value_as_text
