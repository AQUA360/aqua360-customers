from django.core.management.base import BaseCommand
from service.models import Cluster

class Command(BaseCommand):
    help = 'Update nb_nozzles for all clusters to be the count of supply_points and ensure it is even'

    def handle(self, *args, **kwargs):
        clusters = Cluster.objects.all()
        for cluster in clusters:
            # Comptar el nombre de supply points associats al cluster
            nb_nozzles = cluster.nozzles.count()

            # Assegurar que el nombre és parell
            if nb_nozzles % 2 != 0:
                nb_nozzles += 1

            # Actualitzar el camp nb_nozzles
            cluster.nb_nozzles = nb_nozzles
            cluster.save()

            self.stdout.write(self.style.SUCCESS(f'Updated Cluster ID {cluster.id}: nb_nozzles set to {nb_nozzles}'))
