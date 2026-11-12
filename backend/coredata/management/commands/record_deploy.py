from django.core.management.base import BaseCommand

from customers.deploy_info import get_deploy_info, record_deploy


class Command(BaseCommand):
    help = "Desa a l'historial la versió del backend si és nova (s'executa en arrencar el contenidor)."

    def handle(self, *args, **options):
        info = get_deploy_info(refresh=True)
        deployed_at = record_deploy("backend", info)
        if deployed_at is None:
            self.stdout.write("Sense versió per registrar.")
        else:
            self.stdout.write(f"Backend {info.get('release') or info.get('commit')} desplegat el {deployed_at:%Y-%m-%d %H:%M}.")
