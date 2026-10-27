from django.core.management.base import BaseCommand

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
                incident.delete()
                purged += 1
            self.stdout.write(self.style.SUCCESS(f"Eliminades: {purged}"))
