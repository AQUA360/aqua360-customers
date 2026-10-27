from django.core.management.base import BaseCommand

from documentmanager.utils.main_utils import delete_document
from notification.models import Incident
from notification.utils.incident_utils import retention_limit, retention_years


class Command(BaseCommand):
    help = (
        "Llista les incidències esborrades (lògicament) que ja han superat el període de "
        "retenció (ConfigProject incident_retention_years) i, amb --purge, les elimina "
        "definitivament amb els seus informes i documents vinculats."
    )

    def add_arguments(self, parser):
        parser.add_argument('--purge', action='store_true', help="Elimina definitivament les incidències llistades.")

    def handle(self, *args, **options):
        limit = retention_limit()
        incidents = Incident.objects.filter(is_active=False, created_at__lt=limit).order_by('created_at')
        self.stdout.write(f"Retenció: {retention_years()} anys (registrades abans del {limit:%d/%m/%Y})")
        self.stdout.write(f"Incidències esborrades fora del període de retenció: {incidents.count()}")
        for incident in incidents:
            self.stdout.write(f"  {incident.token} - {incident.created_at:%d/%m/%Y} - esborrada el "
                              f"{incident.deleted_at:%d/%m/%Y}" if incident.deleted_at else f"  {incident.token}")
        if options['purge']:
            purged = 0
            for incident in incidents:
                # El justificant no s'elimina amb la incidència (SET_NULL): s'esborra el fitxer i el registre
                document = incident.receipt_document
                incident.delete()
                if document:
                    if document.service == 'hdd':
                        delete_document(document)
                        document.delete()
                    else:
                        # Sense rutina d'esborrat per a aquest servei: es manté el registre per poder-lo localitzar
                        self.stderr.write(f"  Justificant de {incident.token} pendent d'esborrar manualment (document {document.id})")
                purged += 1
            self.stdout.write(self.style.SUCCESS(f"Eliminades: {purged}"))
