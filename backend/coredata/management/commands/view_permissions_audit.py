"""Llista les vistes DRF obertes per a qualsevol usuari autenticat, agrupades per app.

    python manage.py view_permissions_audit             # resum per app i vistes
    python manage.py view_permissions_audit --write-baseline

Vegeu customers/view_permissions_audit.py i customers/tests_view_permissions_routes.py.
"""

from collections import defaultdict

from django.core.management.base import BaseCommand

from customers.view_permissions_audit import (
    BASELINE_PATH,
    collect_open_views,
    load_baseline,
    write_baseline,
)


class Command(BaseCommand):
    help = 'Vistes DRF sense permís de lectura propi (i baseline del test de rutes).'

    def add_arguments(self, parser):
        parser.add_argument(
            '--write-baseline',
            action='store_true',
            help=f'Reescriu {BASELINE_PATH.name} amb les vistes obertes actuals.',
        )

    def handle(self, *args, **options):
        open_views = collect_open_views()
        by_app = defaultdict(list)
        for name in sorted(open_views):
            by_app[name.split('.', 1)[0]].append(name)

        for app, names in sorted(by_app.items(), key=lambda item: (-len(item[1]), item[0])):
            self.stdout.write(f'{app}: {len(names)}')
            for name in names:
                entry = open_views[name]
                note = f"  [{', '.join(sorted(entry['notes']))}]" if entry['notes'] else ''
                self.stdout.write(f"    {name}  ({', '.join(sorted(entry['methods']))}){note}")
        self.stdout.write(f'Total: {len(open_views)}')

        if options['write_baseline']:
            write_baseline(open_views)
            self.stdout.write(self.style.SUCCESS(f'Baseline escrita: {BASELINE_PATH}'))
        else:
            baseline = set(load_baseline()) if BASELINE_PATH.exists() else set()
            new = sorted(set(open_views) - baseline)
            if new:
                self.stdout.write(self.style.WARNING('Obertes i no a la baseline: ' + ', '.join(new)))
