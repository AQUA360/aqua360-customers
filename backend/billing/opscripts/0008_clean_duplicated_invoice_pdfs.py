"""Esborra les còpies dels PDF de factura que ja són al gestor documental.

Abans el PDF definitiu es desava dues vegades: a uploads/billing/invoices
(invoice_file_template) i al gestor documental (invoice_file). Ara només es desa
al gestor documental; aquest script treu les còpies que hi havien quedat.
"""
from django.core.management import call_command


def run():
    call_command('clean_duplicated_invoice_pdfs')
