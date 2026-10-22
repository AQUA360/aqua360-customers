import os
import posixpath

from django.core.files.storage import default_storage
from django.core.management.base import BaseCommand

from billing.models import Invoice

INVOICES_UPLOAD_DIR = 'uploads/billing/invoices'


class Command(BaseCommand):
    help = (
        "Esborra les còpies dels PDF de factura a uploads/billing/invoices que ja "
        "són al gestor documental (invoice_file), i els PDF d'aquesta carpeta "
        "que cap factura referencia. Les previsualitzacions de factures sense "
        "document definitiu i els altres fitxers (gràfiques) es mantenen."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help="No esborra res; només mostra què s'esborraria.",
        )
        parser.add_argument(
            '--skip-orphans',
            action='store_true',
            help="No esborra els PDF de la carpeta que cap factura referencia.",
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        prefix = '[DRY-RUN] ' if dry_run else ''

        cleared_names, skipped, duplicated_bytes = self._clean_duplicated(dry_run)
        self.stdout.write(
            f"{prefix}Còpies duplicades esborrades: {len(cleared_names)} "
            f"({self._format_size(duplicated_bytes)})"
        )
        if skipped:
            self.stdout.write(self.style.WARNING(
                f"{prefix}Factures saltades perquè el document del gestor documental "
                f"no és al disc: {len(skipped)} (ids: {', '.join(map(str, skipped[:50]))}"
                f"{'...' if len(skipped) > 50 else ''})"
            ))

        if not options['skip_orphans']:
            orphans, orphan_bytes = self._clean_orphans(cleared_names, dry_run)
            self.stdout.write(
                f"{prefix}Fitxers sense cap factura esborrats: {orphans} "
                f"({self._format_size(orphan_bytes)})"
            )

        self.stdout.write(self.style.SUCCESS(f"{prefix}Neteja acabada."))

    def _clean_duplicated(self, dry_run):
        invoices = (
            Invoice.objects
            .filter(invoice_file__isnull=False)
            .exclude(invoice_file_template='')
            .exclude(invoice_file_template__isnull=True)
            .select_related('invoice_file')
            .only('id', 'invoice_file_template', 'invoice_file__service', 'invoice_file__location')
        )

        cleared_names = set()
        skipped = []
        total_bytes = 0
        for invoice in invoices.iterator(chunk_size=500):
            document = invoice.invoice_file
            # Al disc local es pot comprovar que el document existeix; a la resta
            # de serveis (azure, aws...) es dona per bo.
            if document.service == 'hdd' and not (document.location and os.path.exists(document.location)):
                skipped.append(invoice.id)
                continue

            name = invoice.invoice_file_template.name
            total_bytes += self._size(name)
            cleared_names.add(name)
            if not dry_run:
                if default_storage.exists(name):
                    default_storage.delete(name)
                Invoice.objects.filter(id=invoice.id).update(invoice_file_template='')

        return cleared_names, skipped, total_bytes

    def _clean_orphans(self, cleared_names, dry_run):
        if not default_storage.exists(INVOICES_UPLOAD_DIR):
            return 0, 0

        referenced = set(
            Invoice.objects
            .exclude(invoice_file_template='')
            .exclude(invoice_file_template__isnull=True)
            .values_list('invoice_file_template', flat=True)
        ) - cleared_names

        count = 0
        total_bytes = 0
        for name in self._walk(INVOICES_UPLOAD_DIR):
            # A la mateixa carpeta hi ha altres fitxers de la factura (p. ex. les
            # gràfiques de charts/): només es tracten els PDF.
            if not name.lower().endswith('.pdf'):
                continue
            if name in referenced or name in cleared_names:
                continue
            count += 1
            total_bytes += self._size(name)
            if not dry_run:
                default_storage.delete(name)

        if not dry_run:
            self._remove_empty_dirs(INVOICES_UPLOAD_DIR)
        return count, total_bytes

    def _walk(self, path):
        dirs, files = default_storage.listdir(path)
        for file_name in files:
            yield posixpath.join(path, file_name)
        for dir_name in dirs:
            yield from self._walk(posixpath.join(path, dir_name))

    def _remove_empty_dirs(self, path):
        # Les carpetes buides només es poden treure amb emmagatzematge local.
        try:
            root = default_storage.path(path)
        except NotImplementedError:
            return
        for dir_path, _dirs, _files in os.walk(root, topdown=False):
            if dir_path != root and not os.listdir(dir_path):
                os.rmdir(dir_path)

    def _size(self, name):
        try:
            return default_storage.size(name)
        except (OSError, NotImplementedError):
            return 0

    def _format_size(self, size):
        for unit in ('B', 'KB', 'MB', 'GB'):
            if size < 1024 or unit == 'GB':
                return f"{size:.1f} {unit}"
            size /= 1024
