"""
Analitza les factures d'un lot (batch) per title_final i detecta les que,
respecte a la mitjana de facturació del contracte, superen un percentatge
configurable. Útil per detectar factures possiblement mal calculades o
d'una naturalesa diferent.

Ús:
    python manage.py batch_invoice_anomaly_total_report --title "Fact. M12/1 - TRIMESTRAL - 12026"
    python manage.py batch_invoice_anomaly_total_report --title "Fact. M12/1 - TRIMESTRAL - 12026" --threshold 50
    python manage.py batch_invoice_anomaly_total_report --title "Fact. M12/1 - TRIMESTRAL - 12026" --csv resultats.csv
"""

import csv
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db.models import Avg, Count

from billing.models import Invoice


class Command(BaseCommand):
    help = (
        "Reporta factures d'un lot (per title_final) que són anomalies per total: per cada contracte, "
        "compara el total_final de la factura del lot amb la mitjana de les altres factures "
        "del contracte i llista les que superen el percentatge configurat (per defecte 50%%)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--title",
            type=str,
            required=True,
            help='title_final del lot (ex: "Fact. M12/1 - TRIMESTRAL - 12026")',
        )
        parser.add_argument(
            "--threshold",
            type=float,
            default=50.0,
            help=(
                "Percentatge per sobre de la mitjana a partir del qual es considera alerta "
                "(ex: 50 = total_final > mitjana * 1.5). Per defecte: 50"
            ),
        )
        parser.add_argument(
            "--csv",
            type=str,
            default="",
            help="Ruta del fitxer CSV on exportar les alertes (ex: resultats.csv)",
        )

    def _contract_token(self, inv):
        return (inv.contract.token or "") if inv.contract_id and inv.contract else ""

    @staticmethod
    def _decimal_comma(value, decimals=2):
        """Formata un nombre amb coma decimal (compatible amb Excel)."""
        if value is None:
            return ""
        s = f"{float(value):.{decimals}f}"
        return s.replace(".", ",")

    def handle(self, *args, **options):
        title = (options.get("title") or "").strip()
        threshold_percent = options.get("threshold", 50.0)
        csv_path = (options.get("csv") or "").strip()

        if not title:
            self.stderr.write(self.style.ERROR("Has de proporcionar --title."))
            return

        # Factures del lot amb aquest title_final (una per contracte)
        batch_invoices = (
            Invoice.objects.filter(title_final=title)
            .select_related("contract")
            .order_by("contract_id", "id")
        )

        if not batch_invoices.exists():
            self.stdout.write(
                self.style.WARNING(f"No s'han trobat factures amb title_final = {title!r}")
            )
            return

        self.stdout.write(
            self.style.SUCCESS(
                f"Factures del lot (title_final = {title!r}): {batch_invoices.count()}"
            )
        )
        self.stdout.write("")

        # Base queryset per “altres factures” del contracte (excloem la del lot)
        def other_invoices_queryset(contract_id, exclude_invoice_id):
            return Invoice.objects.filter(
                is_active=True,
                batch__isnull=False,
                type_final="F",
                type_id=2,
                contract_id=contract_id,
            ).exclude(id=exclude_invoice_id)

        alerts = []
        no_comparison = []

        for inv in batch_invoices:
            contract_id = inv.contract_id
            if not contract_id:
                no_comparison.append((inv, "contracte sense contract_id"))
                continue

            others = other_invoices_queryset(contract_id, inv.id)
            agg = others.aggregate(avg_total=Avg("total_final"), n=Count("id"))

            avg_total = agg["avg_total"]
            n_others = agg["n"] or 0

            if n_others == 0:
                no_comparison.append((inv, "cap altra factura per calcular mitjana"))
                continue

            total_final = inv.total_final or Decimal("0")
            if avg_total is None or avg_total == 0:
                no_comparison.append((inv, "mitjana de les altres factures nul·la o zero"))
                continue

            # total_final > mitjana * (1 + threshold/100) => alerta
            limit = Decimal(str(avg_total)) * (1 + Decimal(str(threshold_percent)) / 100)
            if total_final > limit:
                alerts.append(
                    {
                        "invoice": inv,
                        "total_final": total_final,
                        "avg_others": Decimal(str(avg_total)),
                        "n_others": n_others,
                        "limit": limit,
                        "pct_above": float((total_final - avg_total) / avg_total * 100),
                    }
                )

        # Sortida: factures sense comparació
        if no_comparison:
            self.stdout.write(self.style.WARNING("Sense comparació (no es pot calcular mitjana):"))
            for inv, reason in no_comparison:
                ct = self._contract_token(inv)
                self.stdout.write(
                    f"  contract_id={inv.contract_id} contract.token={ct!r} "
                    f"invoice id={inv.id} serie_final={inv.serie_final!r} "
                    f"total_final={inv.total_final} — {reason}"
                )
            self.stdout.write("")

        if not alerts:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Cap factura del lot supera el {threshold_percent}% per sobre de la mitjana."
                )
            )
            return

        alerts.sort(key=lambda a: a["pct_above"], reverse=True)

        self.stdout.write(
            self.style.ERROR(
                f"Alertes: {len(alerts)} factura(s) amb total_final > {threshold_percent}% de la mitjana:"
            )
        )
        for a in alerts:
            inv = a["invoice"]
            ct = self._contract_token(inv)
            self.stdout.write(
                f"  contract_id={inv.contract_id} contract.token={ct!r} "
                f"invoice id={inv.id} serie_final={inv.serie_final!r} "
                f"total_final={a['total_final']} | "
                f"mitjana altres ({a['n_others']} factures) = {a['avg_others']} | "
                f"llindar = {a['limit']} | "
                f"+{a['pct_above']:.1f}% sobre la mitjana"
            )

        if csv_path:
            self._write_csv(csv_path, title, threshold_percent, alerts)

    def _write_csv(self, csv_path, title, threshold_percent, alerts):
        """Exporta les alertes a un fitxer CSV."""
        fieldnames = [
            "contract_id",
            "contract_token",
            "invoice_id",
            "serie_final",
            "total_final",
            "mitjana_altres",
            "n_others",
            "llindar",
            "pct_sobre_mitjana",
            "title_final",
            "threshold_percent",
        ]
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=";")
            writer.writeheader()
            for a in alerts:
                inv = a["invoice"]
                writer.writerow({
                    "contract_id": inv.contract_id or "",
                    "contract_token": self._contract_token(inv),
                    "invoice_id": inv.id,
                    "serie_final": inv.serie_final or "",
                    "total_final": self._decimal_comma(a["total_final"]),
                    "mitjana_altres": self._decimal_comma(a["avg_others"]),
                    "n_others": a["n_others"],
                    "llindar": self._decimal_comma(a["limit"]),
                    "pct_sobre_mitjana": self._decimal_comma(a["pct_above"]),
                    "title_final": inv.title_final or "",
                    "threshold_percent": self._decimal_comma(threshold_percent),
                })
        self.stdout.write(self.style.SUCCESS(f"Exportat {len(alerts)} alerta(s) a {csv_path!r}."))
