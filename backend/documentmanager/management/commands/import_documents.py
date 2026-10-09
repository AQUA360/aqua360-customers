"""Importa els documents escanejats de l'ERP d'origen al gestor documental.

Llegeix `documents.csv` (`;`, UTF-8 BOM) i la carpeta de fitxers que el generador de l'ETL ha
tret de l'ERP, i crea una fila de `documentmanager.Document` per document, copiant el fitxer al
magatzem de la instal·lació (`settings.DOCUMENT_STORAGE_PATH`).

    python3 manage.py import_documents <csv> [--files-dir DIR] [--dry-run]

Per què no fa servir `documentmanager.utils.upload_document`: aquell camí està pensat per a un
fitxer que puja un usuari des de la interfície i **no escriu** `entity_token`, `folder` ni `date`
a la fila, a més de desar-ho tot a la carpeta del mes EN QUÈ S'IMPORTA. En una migració això
deixaria 3.000 documents amb la fila coixa i tots dins de la carpeta del mateix mes. Aquí la fila
s'escriu sencera i la carpeta es fa amb la data REAL del document.

És idempotent: un document que ja hi és (mateixa entitat, mateix id i mateix nom) no es torna a
crear. Els documents que els usuaris hagin creat des de l'app no es toquen mai.
"""
import csv
import shutil
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from contract.models import (Contract, ContractDocumentationType,
                            ContractRequestDocumentation)
from documentmanager.models import Document
from coredata.models import Person

#: entitat del CSV → com es troba la fila del nostre model a partir del token
RESOLVERS = {
    "CONTRACT": lambda token: Contract.objects.filter(token=token).order_by("id").first(),
    "PERSON": lambda token: Person.objects.filter(token=token).order_by("id").first(),
}


class Command(BaseCommand):
    help = "Importa els documents escanejats de l'ERP al gestor documental."

    def add_arguments(self, parser):
        parser.add_argument("csv_path")
        parser.add_argument(
            "--files-dir",
            help="Carpeta amb els fitxers (per defecte, «documents/» al costat del CSV).")
        parser.add_argument(
            "--types-csv",
            help="catàleg de tipus de document de l'ERP (per defecte, «document_types.csv» al "
                 "costat del CSV). Sense ell, els documents de contracte queden sense tipus i "
                 "la fitxa del contracte no en mostra cap.")
        parser.add_argument("--dry-run", action="store_true")

    def _load_types(self, types_path, dry_run):
        """Catàleg de tipus de document de l'ERP → `ContractDocumentationType`.

        Retorna {(entitat, codi de l'ERP): ContractDocumentationType}. Els tipus que l'app ja
        té amb un altre nom venen marcats al CSV (`App[Token]`) i es reaprofiten: el catàleg
        del destí mana quan és el mateix concepte amb un altre nom. La resta es creen amb el
        nom de l'ERP i un token derivat del seu codi.
        """
        if not types_path.is_file():
            self.stdout.write(self.style.WARNING(
                f"  no hi ha {types_path}: els documents quedaran sense tipus i la fitxa del "
                f"contracte no en mostrarà cap"))
            return {}

        with open(types_path, encoding="utf-8-sig", newline="") as fh:
            rows = list(csv.DictReader(fh, delimiter=";"))

        out, made = {}, 0
        for row in rows:
            entity = (row.get("Entity") or "").strip()
            code = (row.get("Code") or "").strip()
            name = (row.get("Name") or "").strip()
            app_token = (row.get("App[Token]") or "").strip()
            if entity != "CONTRACT" or not code:
                continue

            if app_token:
                doc_type = ContractDocumentationType.objects.filter(token=app_token).first()
                if doc_type is None:
                    raise CommandError(
                        f"el tipus «{app_token}» no és al catàleg de l'app: el CSV el dona per "
                        f"existent i no hi és")
            else:
                token = f"erp_{code.replace('-', 'm')}"
                doc_type = ContractDocumentationType.objects.filter(token=token).first()
                if doc_type is None and not dry_run:
                    doc_type = ContractDocumentationType.objects.create(
                        token=token, name=name or token, is_default=False, is_active=True)
                    made += 1
            if doc_type is not None:
                out[(entity, code)] = doc_type

        if made:
            self.stdout.write(self.style.SUCCESS(f"  {made} tipus de document creats"))
        return out

    def handle(self, *args, **options):
        csv_path = Path(options["csv_path"])
        if not csv_path.is_file():
            raise CommandError(f"No hi ha el CSV: {csv_path}")
        files_dir = Path(options["files_dir"]) if options["files_dir"] else csv_path.parent / "documents"
        if not files_dir.is_dir():
            raise CommandError(f"No hi ha la carpeta de fitxers: {files_dir}")
        dry_run = options["dry_run"]

        types_path = (Path(options["types_csv"]) if options["types_csv"]
                      else csv_path.parent / "document_types.csv")

        with open(csv_path, encoding="utf-8-sig", newline="") as fh:
            rows = list(csv.DictReader(fh, delimiter=";"))

        created = skipped_existing = 0
        missing_entity, missing_file, errors = [], [], []
        linked = 0

        with transaction.atomic():
            # El catàleg de tipus PRIMER: l'app no llegeix `Document` a la fitxa del contracte,
            # sinó la fila que enllaça el document amb el contracte i li dona un tipus. Sense
            # tipus, els documents hi són però no es veuen (§5 trampa 82).
            doc_types = self._load_types(types_path, dry_run)
            for i, row in enumerate(rows, start=2):
                entity = (row.get("Entity") or "").strip()
                token = (row.get("Entity[Token]") or "").strip()
                name = (row.get("Document[Name]") or "").strip()
                location = (row.get("Location") or "").strip()

                resolver = RESOLVERS.get(entity)
                if resolver is None:
                    errors.append(f"línia {i}: entitat «{entity}» desconeguda")
                    continue
                target = resolver(token)
                if target is None:
                    missing_entity.append(f"{entity} {token}")
                    continue

                source = files_dir / location
                if not source.is_file():
                    missing_file.append(location)
                    continue

                if Document.objects.filter(entity=entity, entity_id=target.id,
                                           document_name=name).exists():
                    skipped_existing += 1
                    continue

                date = (row.get("Date") or "").strip() or None
                # la carpeta de destí surt de la data del DOCUMENT, no de la d'avui
                year = date[:4] if date else "sense_data"
                month = date[5:7] if date else "00"
                dest = (Path(settings.DOCUMENT_STORAGE_PATH) / entity / year / month
                        / f"{token}_{name}")

                if not dry_run:
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(source, dest)
                    document = Document.objects.create(
                        entity=entity,
                        field=(row.get("Field") or entity).strip(),
                        entity_id=target.id,
                        entity_token=token,
                        document_name=name,
                        date=date,
                        folder=(row.get("Folder") or "").strip() or None,
                        service=(row.get("Service") or "hdd").strip(),
                        location=str(dest),
                        location_url=None,
                        version=int(row.get("Version") or 1),
                        is_active=(row.get("IsActive") or "1").strip() == "1",
                    )
                    if entity == "CONTRACT":
                        link = ContractRequestDocumentation.objects.create(
                            contract=target,
                            contract_type=doc_types.get(
                                (entity, (row.get("Folder") or "").strip())),
                            file=document,
                        )
                        # `created_at` és `auto_now_add`: sense això, l'enllaç de tots els
                        # documents queda amb la data de la IMPORTACIÓ i és la que es veu a la
                        # fitxa del contracte. Ha de ser la data REAL del document.
                        if date:
                            ContractRequestDocumentation.objects.filter(pk=link.pk).update(
                                created_at=date, updated_at=date)
                        linked += 1
                created += 1

            if dry_run:
                transaction.set_rollback(True)

        self.stdout.write(self.style.SUCCESS(
            f"{'[dry-run] ' if dry_run else ''}documents creats: {created} de {len(rows)} "
            f"(ja hi eren: {skipped_existing})"))
        if linked:
            self.stdout.write(self.style.SUCCESS(
                f"  {linked} enllaçats a la fitxa del seu contracte"))
        if missing_entity:
            self.stdout.write(self.style.WARNING(
                f"  {len(missing_entity)} sense l'entitat al destí, p.ex. {missing_entity[:5]}"))
        if missing_file:
            self.stdout.write(self.style.WARNING(
                f"  {len(missing_file)} sense el fitxer a la carpeta, p.ex. {missing_file[:3]}"))
        if errors:
            for e in errors[:10]:
                self.stdout.write(self.style.ERROR(f"  {e}"))
            raise CommandError(f"{len(errors)} files amb error: no s'ha desat res.")
