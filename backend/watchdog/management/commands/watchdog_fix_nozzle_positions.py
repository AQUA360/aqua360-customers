# watchdog/management/commands/watchdog_fix_nozzle_positions.py
# Fix recomanat quan el watchdog detecta "Active SupplyPoints sharing ClusterNozzle".

from django.core.management.base import BaseCommand
from django.db import transaction

from service.models import (
    Cluster,
    ClusterNozzle,
    ClusterNozzleStatus,
    ClusterNozzleType,
    SupplyPoint,
)


class Command(BaseCommand):
    help = (
        "Rep --token (TOKEN1,TOKEN2,...) i/o --id (1,2,3,...) de bateries (Cluster) i revisa els seus ClusterNozzle. "
        "Si algun té més d'un punt de subministrament (SupplyPoint), distribueix cada "
        "SupplyPoint en el seu propi ClusterNozzle, creant nozzles nous i reordenant posicions. "
        "Recomanat quan el watchdog detecta 'Active SupplyPoints sharing ClusterNozzle'."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--token",
            type=str,
            default="",
            help="Token(s) del(s) Cluster(s) a processar, separats per comes (ex: TOKEN1,TOKEN2,TOKEN3)",
        )
        parser.add_argument(
            "--id",
            type=str,
            default="",
            help="ID(s) del(s) Cluster(s) a processar, separats per comes (ex: 1,2,3)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Mostra què es faria sense desar canvis",
        )

    def get_clusters_from_options(self, tokens_raw, ids_raw):
        """
        Retorna la llista de clusters (sense duplicats) i els identificadors no trobats.
        """
        clusters_by_id = {}
        not_found = []

        if tokens_raw:
            token_list = [s.strip() for s in tokens_raw.split(",") if s.strip()]
            for token in token_list:
                cluster = Cluster.objects.filter(token=token).first()
                if cluster:
                    clusters_by_id[cluster.id] = cluster
                else:
                    not_found.append(f"token:{token}")

        if ids_raw:
            id_list = [s.strip() for s in ids_raw.split(",") if s.strip()]
            for raw_id in id_list:
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
            self.stderr.write(
                self.style.ERROR(
                    "Has de proporcionar almenys --token o --id "
                    "(ex: --token TOKEN1,TOKEN2 o --id 1,2,3)."
                )
            )
            return

        if dry_run:
            self.stdout.write(self.style.WARNING("Mode dry-run: no es desaran canvis."))

        clusters, not_found = self.get_clusters_from_options(tokens_raw, ids_raw)

        if not_found:
            for ref in not_found:
                self.stderr.write(
                    self.style.ERROR(f"No s'ha trobat cap Cluster amb {ref}")
                )

        for cluster in clusters:
            self.process_cluster(cluster, dry_run)

        self.stdout.write(self.style.SUCCESS("[Fi] Clusters processats."))

    def process_cluster(self, cluster, dry_run):
        """Processa un sol cluster: distribueix SupplyPoints en un ClusterNozzle cada un."""
        self.stdout.write(f"Processant Cluster: {cluster} (id={cluster.id})")

        nozzles = list(
            ClusterNozzle.objects.filter(cluster=cluster).order_by("position", "id")
        )
        if not nozzles:
            self.stdout.write(
                self.style.WARNING("Aquest cluster no té cap ClusterNozzle.")
            )
            return

        # Construir llista ordenada de SupplyPoints: per ordre de nozzle (position) i dins del nozzle per id
        supply_points_ordered = []
        nozzles_with_multiple = []

        for nozzle in nozzles:
            sps = list(SupplyPoint.objects.filter(cluster_nozzle=nozzle).order_by("id"))
            if len(sps) > 1:
                nozzles_with_multiple.append((nozzle, len(sps)))
            supply_points_ordered.extend(sps)

        if not nozzles_with_multiple:
            self.stdout.write(
                self.style.SUCCESS(
                    "Cap ClusterNozzle té més d'un SupplyPoint. No cal fer canvis."
                )
            )
            return

        self.stdout.write(
            f"ClusterNozzles amb més d'un SupplyPoint: "
            f'{", ".join(f"nozzle id={n.id} (position={n.position}, count={c})" for n, c in nozzles_with_multiple)}'
        )
        self.stdout.write(f"Total SupplyPoints a distribuir: {len(supply_points_ordered)}")

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f"En mode real es crearien {max(0, len(supply_points_ordered) - len(nozzles))} "
                    "ClusterNozzle(s) nous i es reassignarien els SupplyPoints."
                )
            )
            return

        with transaction.atomic():
            default_status = ClusterNozzleStatus.objects.filter(is_default=True).first()
            default_type = ClusterNozzleType.objects.filter(is_default=True).first()

            n = len(supply_points_ordered)
            for i, sp in enumerate(supply_points_ordered):
                position = i + 1
                if i < len(nozzles):
                    nozzle = nozzles[i]
                    nozzle.position = position
                    nozzle.save()
                else:
                    token = (
                        f"{cluster.token}/{position}"
                        if cluster.token
                        else f"cluster-{cluster.id}-{position}"
                    )
                    nozzle = ClusterNozzle.objects.create(
                        cluster=cluster,
                        token=token,
                        status=default_status,
                        type=default_type,
                        position=position,
                        col=None,
                        row=None,
                    )
                    nozzles.append(nozzle)
                    self.stdout.write(
                        f"  Creat ClusterNozzle id={nozzle.id} token={nozzle.token} position={position}"
                    )

                if sp.cluster_nozzle_id != nozzle.id:
                    sp.cluster_nozzle = nozzle
                    sp.save()
                    self.stdout.write(
                        f"  Assignat SupplyPoint id={sp.id} -> ClusterNozzle id={nozzle.id} (position={position})"
                    )

            # Reordenar la resta de nozzles existents (els que queden per sobre de n)
            for j, nozzle in enumerate(nozzles[n:], start=1):
                new_position = n + j
                if nozzle.position != new_position:
                    nozzle.position = new_position
                    nozzle.save()
                    self.stdout.write(
                        f"  Reordenat ClusterNozzle id={nozzle.id} -> position={new_position}"
                    )

        self.stdout.write(self.style.SUCCESS("Cluster processat correctament."))
