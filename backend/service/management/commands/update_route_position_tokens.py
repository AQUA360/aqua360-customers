from django.core.management.base import BaseCommand
from service.models import Route, RoutePosition
from service.utils.route_positions_service import build_route_position_token


class Command(BaseCommand):
    help = (
        "Regenera l'Ident. (token) de les posicions de ruta a partir del "
        "disseny token_ruta + '_' + ordre (p.ex. 888_1), per deixar-los "
        "consistents amb el patró que ara es manté automàticament en "
        "reordenar. Opcionalment sincronitza també l'Ident. de les finques "
        "vinculades a cada posició (--sync-properties)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--route-id",
            type=int,
            default=None,
            help="Limita l'actualització a una sola ruta (per id).",
        )
        parser.add_argument(
            "--sync-properties",
            action="store_true",
            help="Un cop actualitzat l'Ident. de la posició, també l'aplica a les finques vinculades.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Mostra els canvis sense escriure'ls a la base de dades.",
        )

    def handle(self, *args, **options):
        route_id = options.get("route_id")
        sync_properties = options.get("sync_properties")
        dry_run = options.get("dry_run")

        route_positions = RoutePosition.objects.select_related("route").filter(route__isnull=False)
        if route_id:
            route_positions = route_positions.filter(route_id=route_id)

        total = route_positions.count()
        updated = 0
        skipped = 0

        self.stdout.write(f"Processant {total} posicions de ruta...")

        for route_position in route_positions:
            new_token = build_route_position_token(route_position)

            if not new_token or new_token == route_position.token:
                skipped += 1
                continue

            old_token = route_position.token
            self.stdout.write(f"  RoutePosition {route_position.id}: '{old_token}' -> '{new_token}'")

            if not dry_run:
                route_position.token = new_token
                route_position.save(update_fields=["token"])

                if sync_properties:
                    for prop in route_position.properties.all():
                        if prop.token != new_token:
                            prop.token = new_token
                            prop.save(update_fields=["token"])

            updated += 1

        prefix = "[DRY-RUN] " if dry_run else ""
        self.stdout.write(self.style.SUCCESS(
            f"{prefix}Fet. {updated} posicions actualitzades, {skipped} ja tenien l'Ident. correcte."
        ))
