from django.core.management.base import BaseCommand
from watchdog.persons_without_contact import (
    WARNING_CHECK_NAMES,
    ZOMBIE_PERSONS_CHECK_NAME,
)
from watchdog.services import DataIntegrityService
import json
import time
import sys
import threading
import os
import re
from datetime import datetime


class Command(BaseCommand):
    help = "Comprova la integritat de les dades a la base de dades"

    def add_arguments(self, parser):
        parser.add_argument(
            "command", nargs="?", type=str, help="Comanda a executar (p.ex., sniff)"
        )
        parser.add_argument(
            "--json",
            action="store_true",
            help="Sortida en format JSON",
        )
        parser.add_argument(
            "--save",
            action="store_true",
            help="Desa els resultats a la carpeta logs (.json si --json, .log si no)",
        )

    def save_results_to_file(self, results, as_json=False):
        """Desa els resultats en un fitxer a la carpeta logs."""
        # Get the watchdog app directory
        app_dir = os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        )
        logs_dir = os.path.join(app_dir, "logs")

        # Create logs directory if it doesn't exist
        os.makedirs(logs_dir, exist_ok=True)

        # Generate filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        extension = "json" if as_json else "log"
        filename = f"WatchdogCheck-{timestamp}.{extension}"
        filepath = os.path.join(logs_dir, filename)

        # Save results
        with open(filepath, "w", encoding="utf-8") as f:
            if as_json:
                json.dump(results, f, indent=4, ensure_ascii=False)
            else:
                f.write("📋 Resultats de la comprovació d'integritat:\n\n")
                for check_name, issues in results.items():
                    if not issues:
                        f.write(f"✔ {check_name}: OK\n")
                    elif self._is_warning(check_name, issues):
                        f.write(f"⚠ {check_name}: AVÍS\n")
                        for issue in issues:
                            f.write(f"  - {issue}\n")
                    else:
                        f.write(f"✘ {check_name}: FALLAT\n")
                        for issue in issues:
                            f.write(f"  - {issue}\n")
                        
                        # Afegir comanda de fix per errors d'Exploitation Integrity
                        if check_name == "Exploitations Integrity":
                            f.write("\n💡 Per arreglar aquests errors, pots usar:\n")
                            for issue in issues:
                                match = re.search(r"Exploitation ID (\d+)", issue)
                                if match:
                                    exploitation_id = match.group(1)
                                    f.write(
                                        f"  python manage.py fix_exploitation_cities {exploitation_id} "
                                        "--city 'NOM_CIUTAT' --postalcode 'CODI_POSTAL'\n"
                                    )
                            f.write("\n")
                        # Afegir comanda de fix per Active SupplyPoints sharing ClusterNozzle
                        if check_name == "Active SupplyPoints sharing ClusterNozzle":
                            cluster_ids = sorted(
                                set(
                                    m.group(1)
                                    for issue in issues
                                    for m in [
                                        re.search(r"Cluster ID (\d+)", issue)
                                    ]
                                    if m
                                )
                            )
                            if cluster_ids:
                                ids_arg = ",".join(cluster_ids)
                                f.write(
                                    "\n💡 Per arreglar aquests errors, pots usar:\n"
                                )
                                f.write(
                                    f"  python manage.py watchdog_fix_nozzle_positions --id {ids_arg}\n"
                                )
                                f.write("\n")
                        if check_name == "PersonBank i CompanyBank IBANs vàlids":
                            f.write(
                                "\n💡 Per arreglar aquests errors, pots usar:\n"
                            )
                            f.write(
                                "  python manage.py watchdog_fix_empty_bank_ibans --dry-run\n"
                            )
                            f.write(
                                "  python manage.py watchdog_fix_empty_bank_ibans\n"
                            )
                            f.write("\n")
                        if check_name == "Contracts without Piggybanks":
                            f.write(
                                "\n💡 Per arreglar aquests errors, pots usar:\n"
                            )
                            f.write(
                                "  python manage.py watchdog_fix_contract_piggy_banks --dry-run\n"
                            )
                            f.write(
                                "  python manage.py watchdog_fix_contract_piggy_banks\n"
                            )
                            f.write("\n")
                        if check_name == "Factures amb Estat Inconsistent (Pagaments Pagats)":
                            f.write(
                                "\n💡 Per arreglar aquests errors, pots usar:\n"
                            )
                            f.write(
                                "  python manage.py watchdog_fix_invoice_status_from_payments --dry-run\n"
                            )
                            f.write(
                                "  python manage.py watchdog_fix_invoice_status_from_payments\n"
                            )
                            f.write("\n")
                        if check_name == "Factures sense Pagament Actiu":
                            f.write(
                                "\n💡 Per arreglar aquests errors, pots usar:\n"
                            )
                            f.write(
                                "  python manage.py create_payments_from_invoices --dry-run\n"
                            )
                            f.write(
                                "  python manage.py create_payments_from_invoices\n"
                            )
                            f.write(
                                "  python manage.py create_payments_from_invoices --billing-id N\n"
                            )
                            f.write("\n")
                        if check_name == "Lectures sense Comptador (meter_id)":
                            f.write(
                                "\n💡 Per arreglar aquests errors, pots usar:\n"
                            )
                            f.write(
                                "  python manage.py watchdog_fix_readings_without_meter --dry-run\n"
                            )
                            f.write(
                                "  python manage.py watchdog_fix_readings_without_meter\n"
                            )
                            f.write("\n")
                        if check_name == "Configuració ACA i use_aca":
                            f.write(
                                "\n💡 Per arreglar aquests errors, pots usar:\n"
                            )
                            f.write(
                                "  python manage.py watchdog_fix_aca_config --dry-run\n"
                            )
                            f.write(
                                "  python manage.py watchdog_fix_aca_config\n"
                            )
                            f.write(
                                "  python manage.py fill_contract_use_aca --dry-run\n"
                            )
                            f.write(
                                "  python manage.py fill_contract_use_aca\n"
                            )
                            f.write("\n")
                        if check_name == "ArticleCode per informes ACA":
                            f.write(
                                "\n💡 Per arreglar aquests errors, pots usar:\n"
                            )
                            f.write(
                                "  python manage.py watchdog_fix_aca_config --dry-run\n"
                            )
                            f.write(
                                "  python manage.py watchdog_fix_aca_config\n"
                            )
                            f.write(
                                "  python manage.py fix_aca_lineitemtype_articles --dry-run\n"
                            )
                            f.write(
                                "  python manage.py fix_aca_lineitemtype_articles\n"
                            )
                            f.write("\n")
                        if check_name == "ConfigProject JSON carregat correctament":
                            f.write(
                                "\n💡 Per arreglar aquests errors, pots usar:\n"
                            )
                            f.write(
                                "  python manage.py watchdog_fix_config_project --dry-run\n"
                            )
                            f.write(
                                "  python manage.py watchdog_fix_config_project\n"
                            )
                            f.write("\n")
                        if check_name == "Adreces Orfes":
                            f.write(
                                "\n💡 Per arreglar aquests errors, pots usar:\n"
                            )
                            f.write(
                                "  python manage.py watchdog_fix_orphaned_addresses --dry-run\n"
                            )
                            f.write(
                                "  python manage.py watchdog_fix_orphaned_addresses\n"
                            )
                            f.write("\n")
                        if check_name == ZOMBIE_PERSONS_CHECK_NAME:
                            f.write(
                                "\n💡 Per arreglar aquests errors, pots usar:\n"
                            )
                            f.write(
                                "  python manage.py watchdog_fix_delete_zombie_persons --dry-run\n"
                            )
                            f.write(
                                "  python manage.py watchdog_fix_delete_zombie_persons\n"
                            )
                            f.write("\n")
                        if check_name == "InvoiceSequence desfasada (serie_final)":
                            f.write(
                                "\n💡 Per arreglar aquests errors, pots usar:\n"
                            )
                            f.write(
                                "  python manage.py watchdog_fix_invoice_sequences --dry-run\n"
                            )
                            f.write(
                                "  python manage.py watchdog_fix_invoice_sequences\n"
                            )
                            f.write("\n")

        return filepath

    def start_dog_loading(self):
        """Inicia l'animació de càrrega en un thread separat."""

        dog_frames = [
            "🐕 Bup!              ",
            "🐕 Bup! Bup!         ",
            "🐕 Bup! Bup! Bup!    ",
            "🐶 Ensumo...         ",
            "🐕‍🦺 Detectant...      ",
            "🦮 Gairebé acabat... ",
        ]

        spinner_frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

        stop_event = threading.Event()

        def animation_thread():
            spinner_idx = 0
            dog_idx = 0
            while not stop_event.is_set():
                dog_text = dog_frames[dog_idx]
                sys.stdout.write(f"\r  {spinner_frames[spinner_idx]} {dog_text}")
                sys.stdout.flush()
                spinner_idx = (spinner_idx + 1) % len(spinner_frames)
                # Change dog frame every 20 spinner iterations (2seconds)
                if spinner_idx % 20 == 0:
                    dog_idx = (dog_idx + 1) % len(dog_frames)
                time.sleep(0.1)

        sys.stdout.write("\n🐾 El Watchdog està ensumant problemes de dades...\n\n")
        sys.stdout.flush()

        # Start animation in separate thread
        thread = threading.Thread(target=animation_thread)
        thread.start()

        return stop_event, thread

    def stop_dog_loading(self, stop_event, thread):
        """Atura l'animació de càrrega."""
        stop_event.set()
        thread.join()
        sys.stdout.write("\r  ✅ Comprovació completada!      \n\n")
        sys.stdout.flush()

    def handle(self, *args, **options):
        if options["command"] == "sniff":
            service = DataIntegrityService()

            stop_event, thread = None, None
            if not options["json"] and not options["save"]:
                stop_event, thread = self.start_dog_loading()

            try:
                results = service.run_all_checks()
            finally:
                if stop_event and thread:
                    self.stop_dog_loading(stop_event, thread)
            # Save results if --save is specified
            if options["save"]:
                filepath = self.save_results_to_file(results, as_json=options["json"])
                self.stdout.write(
                    self.style.SUCCESS(f"💾 Resultats desats a: {filepath}")
                )

            if options["json"]:
                self.stdout.write(json.dumps(results, indent=4))
            else:
                self.stdout.write(
                    self.style.HTTP_INFO(
                        "📋 Resultats de la comprovació d'integritat:\n"
                    )
                )

                has_issues = False
                has_warnings = False
                for check_name, issues in results.items():
                    if not issues:
                        self.stdout.write(self.style.SUCCESS(f"✔ {check_name}: OK"))
                    elif self._is_warning(check_name, issues):
                        has_warnings = True
                        self.stdout.write(self.style.WARNING(f"⚠ {check_name}: AVÍS"))
                        for issue in issues:
                            self.stdout.write(f"  - {issue}")
                    else:
                        has_issues = True
                        self.stdout.write(self.style.ERROR(f"✘ {check_name}: FALLAT"))
                        for issue in issues:
                            self.stdout.write(f"  - {issue}")
                        
                        # Mostrar comanda de fix per errors d'Exploitation Integrity
                        if check_name == "Exploitations Integrity":
                            self.stdout.write("")
                            self.stdout.write(
                                self.style.WARNING(
                                    "💡 Per arreglar aquests errors, pots usar:"
                                )
                            )
                            for issue in issues:
                                # Extreure l'ID de l'Exploitation del missatge
                                # Format: "Exploitation ID 1 (LLUÇA) has no cities OR no code"
                                match = re.search(r"Exploitation ID (\d+)", issue)
                                if match:
                                    exploitation_id = match.group(1)
                                    self.stdout.write(
                                        f"  python manage.py fix_exploitation_cities {exploitation_id} "
                                        "--city 'NOM_CIUTAT' --postalcode 'CODI_POSTAL'"
                                    )
                            self.stdout.write("")
                        # Mostrar comanda de fix per Active SupplyPoints sharing ClusterNozzle
                        if check_name == "Active SupplyPoints sharing ClusterNozzle":
                            cluster_ids = sorted(
                                set(
                                    m.group(1)
                                    for issue in issues
                                    for m in [
                                        re.search(r"Cluster ID (\d+)", issue)
                                    ]
                                    if m
                                )
                            )
                            if cluster_ids:
                                ids_arg = ",".join(cluster_ids)
                                self.stdout.write("")
                                self.stdout.write(
                                    self.style.WARNING(
                                        "💡 Per arreglar aquests errors, pots usar:"
                                    )
                                )
                                self.stdout.write(
                                    f"  python manage.py watchdog_fix_nozzle_positions --id {ids_arg}"
                                )
                                self.stdout.write("")
                        if check_name == "PersonBank i CompanyBank IBANs vàlids":
                            self.stdout.write("")
                            self.stdout.write(
                                self.style.WARNING(
                                    "💡 Per arreglar aquests errors, pots usar:"
                                )
                            )
                            self.stdout.write(
                                "  python manage.py watchdog_fix_empty_bank_ibans --dry-run"
                            )
                            self.stdout.write(
                                "  python manage.py watchdog_fix_empty_bank_ibans"
                            )
                            self.stdout.write("")
                        if check_name == "Contracts without Piggybanks":
                            self.stdout.write("")
                            self.stdout.write(
                                self.style.WARNING(
                                    "💡 Per arreglar aquests errors, pots usar:"
                                )
                            )
                            self.stdout.write(
                                "  python manage.py watchdog_fix_contract_piggy_banks --dry-run"
                            )
                            self.stdout.write(
                                "  python manage.py watchdog_fix_contract_piggy_banks"
                            )
                            self.stdout.write("")
                        if check_name == "Factures amb Estat Inconsistent (Pagaments Pagats)":
                            self.stdout.write("")
                            self.stdout.write(
                                self.style.WARNING(
                                    "💡 Per arreglar aquests errors, pots usar:"
                                )
                            )
                            self.stdout.write(
                                "  python manage.py watchdog_fix_invoice_status_from_payments --dry-run"
                            )
                            self.stdout.write(
                                "  python manage.py watchdog_fix_invoice_status_from_payments"
                            )
                            self.stdout.write("")
                        if check_name == "Factures sense Pagament Actiu":
                            self.stdout.write("")
                            self.stdout.write(
                                self.style.WARNING(
                                    "💡 Per arreglar aquests errors, pots usar:"
                                )
                            )
                            self.stdout.write(
                                "  python manage.py create_payments_from_invoices --dry-run"
                            )
                            self.stdout.write(
                                "  python manage.py create_payments_from_invoices"
                            )
                            self.stdout.write(
                                "  python manage.py create_payments_from_invoices --billing-id N"
                            )
                            self.stdout.write("")
                        if check_name == "Lectures sense Comptador (meter_id)":
                            self.stdout.write("")
                            self.stdout.write(
                                self.style.WARNING(
                                    "💡 Per arreglar aquests errors, pots usar:"
                                )
                            )
                            self.stdout.write(
                                "  python manage.py watchdog_fix_readings_without_meter --dry-run"
                            )
                            self.stdout.write(
                                "  python manage.py watchdog_fix_readings_without_meter"
                            )
                            self.stdout.write("")
                        if check_name == "Configuració ACA i use_aca":
                            self.stdout.write("")
                            self.stdout.write(
                                self.style.WARNING(
                                    "💡 Per arreglar aquests errors, pots usar:"
                                )
                            )
                            self.stdout.write(
                                "  python manage.py watchdog_fix_aca_config --dry-run"
                            )
                            self.stdout.write(
                                "  python manage.py watchdog_fix_aca_config"
                            )
                            self.stdout.write(
                                "  python manage.py fill_contract_use_aca --dry-run"
                            )
                            self.stdout.write(
                                "  python manage.py fill_contract_use_aca"
                            )
                            self.stdout.write("")
                        if check_name == "ArticleCode per informes ACA":
                            self.stdout.write("")
                            self.stdout.write(
                                self.style.WARNING(
                                    "💡 Per arreglar aquests errors, pots usar:"
                                )
                            )
                            self.stdout.write(
                                "  python manage.py watchdog_fix_aca_config --dry-run"
                            )
                            self.stdout.write(
                                "  python manage.py watchdog_fix_aca_config"
                            )
                            self.stdout.write(
                                "  python manage.py fix_aca_lineitemtype_articles --dry-run"
                            )
                            self.stdout.write(
                                "  python manage.py fix_aca_lineitemtype_articles"
                            )
                            self.stdout.write("")
                        if check_name == "ConfigProject JSON carregat correctament":
                            self.stdout.write("")
                            self.stdout.write(
                                self.style.WARNING(
                                    "💡 Per arreglar aquests errors, pots usar:"
                                )
                            )
                            self.stdout.write(
                                "  python manage.py watchdog_fix_config_project --dry-run"
                            )
                            self.stdout.write(
                                "  python manage.py watchdog_fix_config_project"
                            )
                            self.stdout.write("")
                        if check_name == "Adreces Orfes":
                            self.stdout.write("")
                            self.stdout.write(
                                self.style.WARNING(
                                    "💡 Per arreglar aquests errors, pots usar:"
                                )
                            )
                            self.stdout.write(
                                "  python manage.py watchdog_fix_orphaned_addresses --dry-run"
                            )
                            self.stdout.write(
                                "  python manage.py watchdog_fix_orphaned_addresses"
                            )
                            self.stdout.write("")
                        if check_name == ZOMBIE_PERSONS_CHECK_NAME:
                            self.stdout.write("")
                            self.stdout.write(
                                self.style.WARNING(
                                    "💡 Per arreglar aquests errors, pots usar:"
                                )
                            )
                            self.stdout.write(
                                "  python manage.py watchdog_fix_delete_zombie_persons --dry-run"
                            )
                            self.stdout.write(
                                "  python manage.py watchdog_fix_delete_zombie_persons"
                            )
                            self.stdout.write("")
                        if check_name == "InvoiceSequence desfasada (serie_final)":
                            self.stdout.write("")
                            self.stdout.write(
                                self.style.WARNING(
                                    "💡 Per arreglar aquests errors, pots usar:"
                                )
                            )
                            self.stdout.write(
                                "  python manage.py watchdog_fix_invoice_sequences --dry-run"
                            )
                            self.stdout.write(
                                "  python manage.py watchdog_fix_invoice_sequences"
                            )
                            self.stdout.write("")

                if not has_issues and not has_warnings:
                    self.stdout.write(
                        self.style.SUCCESS(
                            "\n🎉 Totes les comprovacions han passat! Bon gos! 🐕"
                        )
                    )
                elif not has_issues:
                    self.stdout.write(
                        self.style.WARNING(
                            "\nLes comprovacions greus han passat. Revisa els avisos. 🐕"
                        )
                    )
                else:
                    self.stdout.write(
                        self.style.ERROR(
                            "\n⚠️ Algunes comprovacions han fallat. Bup! 🐕"
                        )
                    )
        else:
            self.stdout.write(
                self.style.ERROR(
                    "Si us plau, proporcioneu una comanda vàlida. Comandes disponibles: sniff"
                )
            )

    def _is_warning(self, check_name, issues):
        if check_name not in WARNING_CHECK_NAMES:
            return False
        return not any(str(issue).startswith("Error de configuració") for issue in issues)
