from django.core.management.base import BaseCommand
from django.db.models import Count
from django.db.models.functions import Upper

from documentmanager.entity_permissions import ENTITY_PERMISSIONS, FIELD_PERMISSIONS
from documentmanager.models import Document


class Command(BaseCommand):
    help = (
        "Llista els tipus de document (entity/field) d'aquesta instal·lació i si "
        "documentmanager.entity_permissions els cobreix. Els que no, només els veuen els superusuaris."
    )

    def add_arguments(self, parser):
        parser.add_argument('--fail', action='store_true', help='Surt amb error si hi ha algun tipus sense cobrir.')

    def handle(self, *args, **options):
        rows = (
            Document.objects.filter(is_active=True)
            .annotate(entity_upper=Upper('entity'), field_upper=Upper('field'))
            .values('entity_upper', 'field_upper')
            .annotate(total=Count('id'))
            .order_by('-total')
        )
        covered, uncovered = {}, {}
        for row in rows:
            entity, field = row['entity_upper'], row['field_upper']
            if entity in ENTITY_PERMISSIONS:
                covered[entity] = covered.get(entity, 0) + row['total']
            elif field in FIELD_PERMISSIONS:
                covered[f'{field} (per field)'] = covered.get(f'{field} (per field)', 0) + row['total']
            else:
                key = f'entity={entity!r} field={field!r}'
                uncovered[key] = uncovered.get(key, 0) + row['total']

        self.stdout.write(self.style.SUCCESS(f'Cobertes: {len(covered)} tipus, {sum(covered.values())} documents'))
        for key, total in sorted(covered.items(), key=lambda item: -item[1]):
            self.stdout.write(f'  {total:>8}  {key}')
        if uncovered:
            self.stdout.write(self.style.WARNING(
                f'SENSE COBRIR: {len(uncovered)} tipus, {sum(uncovered.values())} documents (només superusuaris)'
            ))
            for key, total in sorted(uncovered.items(), key=lambda item: -item[1]):
                self.stdout.write(f'  {total:>8}  {key}')
            if options['fail']:
                raise SystemExit(1)
        else:
            self.stdout.write(self.style.SUCCESS('Tots els tipus de document estan cobertes.'))
