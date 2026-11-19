"""Esborra les gràfiques de factura que es desaven a MEDIA_ROOT.

Les gràfiques del consum de les factures es desaven com a PNG a
uploads/billing/invoices/<id>/charts/, accessibles per URL amb un camí fàcil
d'endevinar. Ara van incrustades al PDF i no es desen; els PDF ja generats porten
la imatge dins, així que els fitxers ja no fan falta.
"""
import os

from django.conf import settings


def run():
    invoices_dir = os.path.join(settings.MEDIA_ROOT, 'uploads', 'billing', 'invoices')
    if not os.path.isdir(invoices_dir):
        return

    removed = 0
    for entry in os.scandir(invoices_dir):
        charts_dir = os.path.join(entry.path, 'charts')
        if not entry.is_dir() or not os.path.isdir(charts_dir):
            continue
        for chart in os.scandir(charts_dir):
            if chart.is_file() and chart.name.endswith('_chart.png'):
                os.remove(chart.path)
                removed += 1
        for path in (charts_dir, entry.path):
            try:
                os.rmdir(path)  # només si ha quedat buida
            except OSError:
                break

    print(f"Gràfiques de factura esborrades: {removed}")
