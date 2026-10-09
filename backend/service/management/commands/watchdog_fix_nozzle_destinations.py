# service/management/commands/watchdog_fix_nozzle_destinations.py
# Corregeix el camp `destination` (Us/desti) d'un ClusterNozzle perque coincideixi amb
# el pis/porta reals de l'unic SupplyPoint que hi ha vinculat.
#
# Detectat en una bateria on els nozzles tenien el `destination` "desplacat" respecte al SupplyPoint que hi ha
# realment connectat (p.ex. nozzle amb destination="AT-1" connectat a un SupplyPoint de
# planta baixa local -LOC- porta DRETA, en lloc d'un atic porta 1). Revisant tota la BD
# amb el mateix criteri s'ha trobat que es un problema molt mes ampli (~200 bateries),
# no nomes d'aquest cluster -- aquest command nomes toca els clusters que se li indiquin.

from django.core.management.base import BaseCommand
from django.db import transaction

from service.models import Cluster, ClusterNozzle


def expected_destination(supply_point):
    """Retorna el `destination` que li correspondria a un nozzle segons l'adreca
    (pis/porta) del SupplyPoint que hi te vinculat, seguint la mateixa convencio ja
    usada a la resta de bateries de la BD ("<pis>-<porta>", "LOC-<porta>", o nomes
    "<pis>" quan no hi ha porta, p.ex. "SOT", "P.O")."""
    if not supply_point or not supply_point.address:
        return None
    address = supply_point.address
    floor = (address.floor or "").strip()
    door = (address.door or "").strip()
    if not floor:
        return None
    if floor.upper() == "LOC":
        return f"LOC-{door}" if door else "LOC"
    if door:
        return f"{floor}-{door}"
    return floor


class Command(BaseCommand):
    help = (
        "Rep --token (TOKEN1,TOKEN2,...) i/o --id (1,2,3,...) de bateries (Cluster) i "
        "recalcula el `destination` de cada ClusterNozzle a partir del pis/porta del "
        "SupplyPoint que hi ha vinculat. Nomes toca nozzles amb exactament un "
        "SupplyPoint connectat i adreca amb pis informat; els altres es reporten pero "
        "no es toquen (cal resoldre'ls primer, p.ex. amb watchdog_fix_nozzle_positions)."
    )

    def add_arguments(self, parser):
        parser.add_argument("--token", type=str, default="",
                             help="Token(s) del(s) Cluster(s), separats per comes")
        parser.add_argument("--id", type=str, default="",
                             help="ID(s) del(s) Cluster(s), separats per comes")
        parser.add_argument("--dry-run", action="store_true",
                             help="Mostra que es faria sense desar canvis")

    def get_clusters_from_options(self, tokens_raw, ids_raw):
        clusters_by_id = {}
        not_found = []

        if tokens_raw:
            for token in (s.strip() for s in tokens_raw.split(",") if s.strip()):
                cluster = Cluster.objects.filter(token=token).first()
                if cluster:
                    clusters_by_id[cluster.id] = cluster
                else:
                    not_found.append(f"token:{token}")

        if ids_raw:
            for raw_id in (s.strip() for s in ids_raw.split(",") if s.strip()):
                if not raw_id.isdigit():
                    not_found.append(f"id:{raw_id}")
                    continue
                cluster = Cluster.objects.filter(id=int(raw_id)).first()
                if cluster:
                    clusters_by_id[cluster.id] = cluster
                else:
                    not_found.append(f"id:{raw_id}")

        return list(clusters_by_id.values()), not_found

    def handle(self, *args, **options):
        tokens_raw = (options.get("token") or "").strip()
        ids_raw = (options.get("id") or "").strip()
        dry_run = options.get("dry_run", False)

        if not tokens_raw and not ids_raw:
            self.stderr.write(self.style.ERROR(
                "Has de proporcionar almenys --token o --id (ex: --token TOKEN1,TOKEN2 o --id 1,2,3)."
            ))
            return

        if dry_run:
            self.stdout.write(self.style.WARNING("Mode dry-run: no es desaran canvis."))

        clusters, not_found = self.get_clusters_from_options(tokens_raw, ids_raw)
        for ref in not_found:
            self.stderr.write(self.style.ERROR(f"No s'ha trobat cap Cluster amb {ref}"))

        for cluster in clusters:
            self.process_cluster(cluster, dry_run)

        self.stdout.write(self.style.SUCCESS("[Fi] Clusters processats."))

    def process_cluster(self, cluster, dry_run):
        self.stdout.write(f"Processant Cluster: {cluster} (id={cluster.id})")
        nozzles = (
            ClusterNozzle.objects.filter(cluster=cluster)
            .prefetch_related("supply_points__address")
            .order_by("position", "id")
        )
        changes = []
        skipped = []
        for nozzle in nozzles:
            sps = list(nozzle.supply_points.all())
            if len(sps) != 1:
                skipped.append((nozzle, len(sps)))
                continue
            expected = expected_destination(sps[0])
            if expected is None:
                skipped.append((nozzle, "sense pis a l'adreca"))
                continue
            current = (nozzle.destination or "").strip()
            if current.upper() != expected.upper():
                changes.append((nozzle, current, expected))

        if skipped:
            for nozzle, reason in skipped:
                self.stdout.write(self.style.WARNING(
                    f"  Nozzle id={nozzle.id} ({nozzle.token}) ignorat: {reason}"
                ))

        if not changes:
            self.stdout.write(self.style.SUCCESS("  Cap canvi necessari."))
            return

        for nozzle, current, expected in changes:
            self.stdout.write(
                f"  Nozzle id={nozzle.id} ({nozzle.token}): destination '{current}' -> '{expected}'"
            )

        if dry_run:
            return

        with transaction.atomic():
            for nozzle, current, expected in changes:
                nozzle.destination = expected
                nozzle.save(update_fields=["destination"])

        self.stdout.write(self.style.SUCCESS(f"  Actualitzats {len(changes)} nozzle(s)."))
