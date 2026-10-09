from django.core.management.base import BaseCommand
from django.db.models import Exists, OuterRef

from service.models import SupplyCut, SupplyPoint
from service.utils import supply_cut_service


class Command(BaseCommand):
    help = (
        "Repara l'estat dels punts de subministrament que han quedat tallats "
        "per talls que ja estan en un estat terminal (tancat, acabat o cancel·lat). "
        "Per defecte només mostra quants punts es restablirien; cal --commit per aplicar-ho."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--commit',
            action='store_true',
            help="Aplica la reparació. Sense aquest flag només es mostra el recompte.",
        )

    def handle(self, *args, **options):
        commit = options['commit']
        closed_tokens = supply_cut_service.closed_status_tokens()
        # Points of a terminal cut that are still cut and belong to no other
        # open (non-terminal) cut: these are the ones the close should have
        # restored. Mirrors the guard of restore_supply_point.
        other_open_cut = SupplyCut.objects.filter(
            supply_points=OuterRef('pk'),
            is_active=True,
        ).exclude(status__token__in=closed_tokens)
        candidates = (
            SupplyPoint.objects
            .filter(
                status__token='tallat',
                supply_cuts__is_active=True,
                supply_cuts__status__token__in=closed_tokens,
            )
            .filter(~Exists(other_open_cut))
            .distinct()
        )
        total = candidates.count()
        self.stdout.write(self.style.WARNING(
            f"{total} punt(s) tallat(s) pendent(s) de restablir en talls terminals."
        ))
        if not total:
            return

        if not commit:
            self.stdout.write("Usa --commit per restablir-los.")
            return

        cut_ids = (
            SupplyCut.objects
            .filter(is_active=True, status__token__in=closed_tokens)
            .values_list('id', flat=True)
        )
        restored = 0
        for cut_id in cut_ids:
            supply_cut = SupplyCut.objects.filter(id=cut_id).first()
            if not supply_cut:
                continue
            restored += supply_cut_service.restore_supply_points(
                cut_id, user=None, observation="Reparació d'estats terminals de talls"
            )
        self.stdout.write(self.style.SUCCESS(
            f"Reparació aplicada: {restored} punt(s) restablert(s)."
        ))