"""Actualitza l'informe de deute i saldo a data: formulari propi i textos revisats.

Amb `has_custom_config` el llistat d'informes mostra el formulari propi (selector d'una sola
data) en lloc del botó de descàrrega directa, que depèn del període global. També es
reaplica la descripció, que ja no parla de "data de tall".
"""


def run():
    from importlib import import_module

    from statistics.models import AvailableReport

    defaults = import_module(
        'statistics.opscripts.0005_add_wallet_debt_balance_at_date_report'
    ).REPORT_DEFAULTS
    AvailableReport.objects.filter(
        function_name='wallet_debt_balance_at_date_report',
    ).update(
        has_custom_config=True,
        name=defaults['name'],
        description=defaults['description'],
        download_button_name=defaults['download_button_name'],
    )
