from django.core.management.base import BaseCommand
from django.db import connection
from django.db.migrations.recorder import MigrationRecorder

class Command(BaseCommand):
    help = "Elimina el registre de les migracions de logo (0100, 0101) que causaven duplicats per rutes absolutes a la taula django_migrations."

    def handle(self, *args, **options):
        migrations_to_cleanup = ['0100_alter_exploitation_logo', '0101_alter_exploitation_logo']
        
        recorder = MigrationRecorder(connection)
        
        # Filtrem les migracions que volem esborrar
        problematic_migrations = recorder.migration_qs.filter(
            app='service', 
            name__in=migrations_to_cleanup
        )
        
        count = problematic_migrations.count()
        
        if count == 0:
            self.stdout.write(self.style.SUCCESS("No s'han trobat migracions de logo amb rutes absolutes per netejar (0100 o 0101)."))
            return

        self.stdout.write(f"S'han trobat {count} registres de migracions problemàtiques: {list(problematic_migrations.values_list('name', flat=True))}")
        
        problematic_migrations.delete()
        
        self.stdout.write(self.style.SUCCESS(f"Neteja completada. S'han eliminat els {count} registres."))