import os
import shutil
import tempfile
import time
from io import StringIO

import fitz
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.management import call_command
from django.test import TestCase, override_settings

from billing.models import Invoice
from billing.utils.invoice_pdf import prepare_invoice_pdf_filename
from coredata.utils.pdf_utils import merge_pdfs
from documentmanager.models import Document

MEDIA_ROOT = tempfile.mkdtemp()
DOCUMENTS_ROOT = tempfile.mkdtemp()


def make_old(name):
    # Els PDF recents es consideren en curs de generació i la neteja no els toca.
    path = default_storage.path(name)
    old_time = time.time() - 2 * 3600
    os.utime(path, (old_time, old_time))
    return name


def pdf_bytes(pages=1):
    pdf = fitz.open()
    for _ in range(pages):
        pdf.new_page()
    content = pdf.tobytes()
    pdf.close()
    return content


@override_settings(MEDIA_ROOT=MEDIA_ROOT)
class TestInvoicePdfStorage(TestCase):
    """
    El PDF definitiu de la factura només es desa al gestor documental
    (invoice_file); invoice_file_template només guarda la previsualització.
    """

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA_ROOT, ignore_errors=True)
        shutil.rmtree(DOCUMENTS_ROOT, ignore_errors=True)

    def _document(self, invoice, content=None, exists=True):
        location = os.path.join(DOCUMENTS_ROOT, f'FACTURA_{invoice.id}.pdf')
        if exists:
            with open(location, 'wb') as f:
                f.write(content or pdf_bytes())
        return Document.objects.create(
            entity='FACTURES', field='FACTURA', entity_id=invoice.id,
            document_name=f'FACTURA_{invoice.id}.pdf', service='hdd', location=location,
        )

    def _invoice(self, with_document=False, with_template=False, document_exists=True):
        # bulk_create: els signals de la factura no intervenen en el que es prova.
        number = Invoice.objects.count()
        Invoice.objects.bulk_create([Invoice(token=f'F-{number}', serie_final=f'FC/{number}')])
        invoice = Invoice.objects.get(token=f'F-{number}')
        if with_template:
            invoice.invoice_file_template.save('preview.pdf', ContentFile(pdf_bytes()), save=False)
        if with_document:
            invoice.invoice_file = self._document(invoice, exists=document_exists)
        Invoice.objects.filter(id=invoice.id).update(
            invoice_file_template=invoice.invoice_file_template.name or '',
            invoice_file=invoice.invoice_file,
        )
        return Invoice.objects.get(id=invoice.id)

    def test_prepare_filename_removes_previous_preview(self):
        invoice = self._invoice(with_template=True)
        preview_name = invoice.invoice_file_template.name

        filename = prepare_invoice_pdf_filename(invoice)

        self.assertEqual(filename, f"{invoice.serie_final.replace('/', '')}_{invoice.id}.pdf")
        self.assertFalse(default_storage.exists(preview_name))
        self.assertFalse(invoice.invoice_file_template)

    def test_merge_pdfs_reads_document_manager_file(self):
        first = self._invoice(with_document=True)
        second = self._invoice(with_document=True)
        without_pdf = self._invoice()

        only_template = self._invoice(with_template=True)

        merged = merge_pdfs(first, second, without_pdf, only_template)
        try:
            with fitz.open(merged.name) as pdf:
                self.assertEqual(pdf.page_count, 3)
        finally:
            os.remove(merged.name)

    def test_clean_command_removes_duplicates_and_orphans(self):
        duplicated = self._invoice(with_document=True, with_template=True)
        duplicated_name = duplicated.invoice_file_template.name
        preview_only = self._invoice(with_template=True)
        preview_name = preview_only.invoice_file_template.name
        missing_document = self._invoice(with_document=True, with_template=True, document_exists=False)
        missing_name = missing_document.invoice_file_template.name
        orphan_name = make_old(default_storage.save('uploads/billing/invoices/999999/old.pdf', ContentFile(pdf_bytes())))
        recent_name = default_storage.save('uploads/billing/invoices/999997/new.pdf', ContentFile(pdf_bytes()))
        chart_name = default_storage.save(
            f'uploads/billing/invoices/{duplicated.id}/charts/chart.png', ContentFile(b'png')
        )

        call_command('clean_duplicated_invoice_pdfs', stdout=StringIO())

        self.assertFalse(default_storage.exists(duplicated_name))
        self.assertFalse(Invoice.objects.get(id=duplicated.id).invoice_file_template)
        self.assertTrue(Invoice.objects.get(id=duplicated.id).invoice_file_id)
        # Sense document definitiu (o sense fitxer al disc), la còpia es manté.
        self.assertTrue(default_storage.exists(preview_name))
        self.assertTrue(default_storage.exists(missing_name))
        self.assertEqual(Invoice.objects.get(id=missing_document.id).invoice_file_template.name, missing_name)
        self.assertFalse(default_storage.exists(orphan_name))
        self.assertFalse(os.path.exists(os.path.join(MEDIA_ROOT, 'uploads/billing/invoices/999999')))
        # Les gràfiques de la factura es desen a la mateixa carpeta i no s'han de tocar.
        self.assertTrue(default_storage.exists(chart_name))
        self.assertTrue(default_storage.exists(recent_name))

    def test_clean_command_dry_run_keeps_files(self):
        duplicated = self._invoice(with_document=True, with_template=True)
        duplicated_name = duplicated.invoice_file_template.name
        orphan_name = make_old(default_storage.save('uploads/billing/invoices/999998/old.pdf', ContentFile(pdf_bytes())))

        call_command('clean_duplicated_invoice_pdfs', '--dry-run', stdout=StringIO())

        self.assertTrue(default_storage.exists(duplicated_name))
        self.assertEqual(Invoice.objects.get(id=duplicated.id).invoice_file_template.name, duplicated_name)
        self.assertTrue(default_storage.exists(orphan_name))

    def test_opscript_runs_cleanup_on_deploy(self):
        import importlib

        duplicated = self._invoice(with_document=True, with_template=True)
        duplicated_name = duplicated.invoice_file_template.name

        importlib.import_module('billing.opscripts.0008_clean_duplicated_invoice_pdfs').run()

        self.assertFalse(default_storage.exists(duplicated_name))
        self.assertFalse(Invoice.objects.get(id=duplicated.id).invoice_file_template)
