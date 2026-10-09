import json

from django.core.management.base import BaseCommand

from coredata.models import ConfigProject
from service.models import SupplyCut, SupplyCutCause, SupplyCutStatus
from integrations.outbound.giswater.sync import (
    _load_mincut_config_maps,
    _resolve_catalog_with_map,
)

# Mapes CANÒNICS, explícits i per significat (els mateixos de la migració
# 0126). Mai s'han de derivar del catàleg: GIS i el PA tenen vocabularis
# independents i la coincidència de dígits no és una equivalència. Els motius
# de GIS (1=Accidental, 2=Planificada) es tradueixen a l'Accidental/Planificada
# del catàleg; «Sobre la planificació» (4) passa a ser la Planificada (0) i
# «En curs» == «Actiu». «Conflicte» (5) es manté com a estat propi (requereix
# revisió).
EXPLICIT_STATE_MAP = {
    "0": "0",
    "Planificada": "0",
    "4": "0",
    "Sobre la planificació": "0",
    "1": "1",
    "En curs": "1",
    "2": "2",
    "Acabat": "2",
    "3": "3",
    "Cancel·lat": "3",
    "5": "5",
    "Conflicte": "5",
}

EXPLICIT_CAUSE_MAP = {
    "1": "Accidental",
    "Accidental": "Accidental",
    "2": "Planificada",
    "Planificada": "Planificada",
}


def _write_maps():
    ConfigProject.objects.update_or_create(
        token="giswater_mincut_state_map",
        defaults={
            "name": "Mapa d'estat de Giswater -> token del catàleg d'estat del PA",
            "value": json.dumps(EXPLICIT_STATE_MAP, ensure_ascii=False),
        },
    )
    ConfigProject.objects.update_or_create(
        token="giswater_mincut_cause_map",
        defaults={
            "name": "Mapa de motiu de Giswater -> token del catàleg de motiu del PA",
            "value": json.dumps(EXPLICIT_CAUSE_MAP, ensure_ascii=False),
        },
    )


class Command(BaseCommand):
    help = (
        "Mostra els talls de forniment en quarantena (requires_review=True) i, "
        "amb --commit, els reintenta resoldre amb els mapes de ConfigProject. "
        "MAI es crea cap entrada de catàleg (mapa-first, zero minting); un valor "
        "no mapejat deixa el tall en quarantena i conserva els raws. Amb "
        "--refresh es restableixen els mapes CANÒNICS/explícits de ConfigProject "
        "abans de resoldre."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--commit",
            action="store_true",
            help="Aplica la re-resolució. Sense aquest flag només es llisten.",
        )
        parser.add_argument(
            "--refresh",
            action="store_true",
            help="Restableix els mapes CANÒNICS (estat/motiu) a ConfigProject; "
            "útil quan un --refresh anterior o una edició manual els ha corromput.",
        )

    def handle(self, *args, **options):
        commit = options["commit"]
        refresh = options["refresh"]

        if refresh:
            _write_maps()
            self.stdout.write(
                self.style.SUCCESS("Mapes canònics/explícits restablerts a ConfigProject.")
            )

        pending = SupplyCut.objects.filter(requires_review=True).order_by("created_at")
        total = pending.count()
        self.stdout.write(
            self.style.WARNING(f"{total} tall(s) en quarantena (requires_review=True).")
        )
        if not total:
            return

        if not commit:
            for cut in pending[:10]:
                self.stdout.write(
                    f"  - {cut.token} causa_raw={cut.cause_raw!r} state_raw={cut.state_raw!r}"
                )
            self.stdout.write("Usa --commit per reintentar-los resoldre.")
            return

        maps = _load_mincut_config_maps()
        resolved_count = 0
        for cut in pending:
            cause, cause_resolved = _resolve_catalog_with_map(
                maps["giswater_mincut_cause_map"], SupplyCutCause, cut.cause_raw
            )
            status, status_resolved = _resolve_catalog_with_map(
                maps["giswater_mincut_state_map"], SupplyCutStatus, cut.state_raw
            )
            resolved = cause_resolved and status_resolved
            if resolved:
                cut.cause = cause
                cut.status = status
                cut.mincut_cause_token = cause.token if cause else None
                cut.mincut_state_token = status.token if status else None
                cut.requires_review = False
                resolved_count += 1
            cut.save(
                update_fields=[
                    "cause",
                    "status",
                    "mincut_cause_token",
                    "mincut_state_token",
                    "requires_review",
                    "updated_at",
                ]
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"{resolved_count} resolt(s); "
                f"{SupplyCut.objects.filter(requires_review=True).count()} en revisió."
            )
        )