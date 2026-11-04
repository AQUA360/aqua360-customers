import os
import zipfile

from django.core.management.base import BaseCommand, CommandError

from billing.utils.factdeta_reader import build_factdeta_workbook, read_factdeta, summarize_factdeta

# Un FACTDETA té 664 caràcters per factura: 500 MB són unes 750.000 factures
MAX_TXT_SIZE = 500 * 1024 * 1024


class Command(BaseCommand):
    help = (
        "Llegeix fitxers FACTDETA (.txt, o .zip amb .txt a dins), en mostra els totals i les validacions "
        "i en desa l'anàlisi en un Excel per fitxer (RESUM_<fitxer>.xlsx)."
    )

    def add_arguments(self, parser):
        parser.add_argument('paths', nargs='+', help="Fitxers .txt o .zip")
        parser.add_argument('-o', '--output-dir', help="Carpeta dels Excel (per defecte, la del fitxer)")
        parser.add_argument('--no-excel', action='store_true', help="Només mostra el resum per pantalla")

    def handle(self, *args, **options):
        self.used_outputs = set()
        for path in options['paths']:
            if not os.path.isfile(path):
                raise CommandError(f"No existeix el fitxer {path}")
            output_dir = options['output_dir'] or os.path.dirname(os.path.abspath(path))
            if zipfile.is_zipfile(path):
                with zipfile.ZipFile(path) as zip_file:
                    for name in zip_file.namelist():
                        if name.lower().endswith('.txt') and os.path.basename(name).upper().startswith('FD'):
                            if zip_file.getinfo(name).file_size > MAX_TXT_SIZE:
                                self.stderr.write(self.style.ERROR(f"{name}: massa gran per analitzar-lo"))
                                continue
                            self._analyze(zip_file.read(name), os.path.basename(name), output_dir, options)
            else:
                with open(path, 'rb') as file:
                    self._analyze(file.read(), os.path.basename(path), output_dir, options)

    def _analyze(self, content, file_name, output_dir, options):
        factdeta = read_factdeta(content, file_name)
        total = summarize_factdeta(factdeta)['total']
        self.stdout.write(self.style.MIGRATE_HEADING(file_name))
        self.stdout.write(
            f"  Registres {total['count']}  |  Volum consumit {total['consumed_volume']}  |  "
            f"Volum facturat {total['billed_volume']}"
        )
        self.stdout.write(
            f"  Part variable {total['variable_amount']:.2f}  |  Part fixa {total['fixed_amount']:.2f}  |  "
            f"Total {total['total_amount']:.2f}"
        )
        warnings = len(factdeta.issues) - len(factdeta.incidences)
        style = self.style.ERROR if factdeta.incidences else self.style.SUCCESS
        self.stdout.write(style(f"  Incidències {len(factdeta.incidences)}  |  Avisos {warnings}"))
        if not options['no_excel']:
            os.makedirs(output_dir, exist_ok=True)
            # Dins d'un zip hi pot haver dos fitxers amb el mateix nom en carpetes diferents
            base = os.path.join(output_dir, f"RESUM_{os.path.splitext(file_name)[0]}")
            output, number = f"{base}.xlsx", 1
            while output in self.used_outputs:
                number += 1
                output = f"{base}_{number}.xlsx"
            self.used_outputs.add(output)
            build_factdeta_workbook(factdeta).save(output)
            self.stdout.write(f"  Excel: {output}")
