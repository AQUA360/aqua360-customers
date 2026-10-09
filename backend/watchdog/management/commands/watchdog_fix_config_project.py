from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from watchdog.config_project_fixture import (
    create_missing_config_projects,
    get_config_project_fixture_path,
    get_missing_config_project_entries,
    load_config_project_fixture_entries,
)


class Command(BaseCommand):
    help = (
        "Crea els ConfigProject que falten a la base de dades segons el JSON mestre "
        "(initial_data/ca/config_project/local/ConfigProject.json). "
        "Recomanat quan el watchdog detecta 'ConfigProject JSON carregat correctament'."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Mostra què es crearia sense desar canvis',
        )
        parser.add_argument(
            '--token',
            type=str,
            default=None,
            help='Només crea aquests tokens si falten (separats per comes)',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        tokens = self._parse_tokens(options['token'])
        fixture_path = get_config_project_fixture_path()

        self.stdout.write(f"JSON mestre: {fixture_path}")

        try:
            load_config_project_fixture_entries(fixture_path=fixture_path)
        except (FileNotFoundError, ValueError) as exc:
            raise CommandError(str(exc)) from exc

        missing_entries = get_missing_config_project_entries(
            tokens=tokens,
            fixture_path=fixture_path,
        )

        if tokens:
            unknown_tokens = sorted(
                token for token in tokens
                if token not in {
                    entry["token"]
                    for entry in load_config_project_fixture_entries(fixture_path=fixture_path)
                }
            )
            if unknown_tokens:
                self.stdout.write(
                    self.style.WARNING(
                        "Tokens no trobats al JSON mestre: "
                        + ", ".join(unknown_tokens)
                    )
                )

        if not missing_entries:
            self.stdout.write(
                self.style.SUCCESS('No falta cap ConfigProject del JSON mestre.')
            )
            return

        prefix = '[DRY RUN] ' if dry_run else ''
        self.stdout.write(
            f"\n{prefix}Es crearien {len(missing_entries)} ConfigProject(s):\n"
        )

        for entry in missing_entries:
            self.stdout.write(
                f"  - token={entry['token']!r}, name={entry['name']!r}, "
                f"value={entry['value']!r}, file={entry['file']!r}"
            )

        with transaction.atomic():
            created_entries = create_missing_config_projects(
                missing_entries,
                dry_run=dry_run,
            )
            if dry_run:
                transaction.set_rollback(True)

        self.stdout.write('')
        if dry_run:
            self.stdout.write(
                self.style.SUCCESS(
                    f"{prefix}{len(created_entries)} ConfigProject(s) pendents de crear."
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Creats {len(created_entries)} ConfigProject(s) correctament."
                )
            )

    def _parse_tokens(self, tokens_input):
        if not tokens_input:
            return None
        tokens = [token.strip() for token in tokens_input.split(',') if token.strip()]
        if not tokens:
            raise CommandError("No s'han proporcionat tokens vàlids")
        return tokens
