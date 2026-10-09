from django.core.management.base import BaseCommand
from django.db import transaction

from contract.models import VariableType
from coredata.models import ConfigProject
from pricing.models import ArticleCode

from watchdog.aca_config import (
    ACA_DIR_VARIABLE_CONFIG_TOKEN,
    ACA_PRODUCT_CONFIG_TOKEN,
    ACA_RATE_CONFIG_SPECS,
    DEFAULT_ACA_VARIABLE_TYPE,
    REQUIRED_ACA_ARTICLE_CODE_SPECS,
    build_config_value_from_price_rates,
    find_canon_product,
    find_price_rates_for_name_patterns,
    get_config_value,
    split_config_tokens,
    uses_aca_enabled,
)


class Command(BaseCommand):
    help = (
        "Corregeix la configuració ACA (ConfigProject i VariableType) quan el projecte "
        "té uses_aca=True. Recomanat quan el watchdog detecta 'Configuració ACA i use_aca'. "
        "Per omplir use_aca als contractes, executa després fill_contract_use_aca."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Mostra què es faria sense desar canvis',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']

        article_codes_to_create = []
        for article_token, article_name in REQUIRED_ACA_ARTICLE_CODE_SPECS:
            if ArticleCode.objects.filter(token=article_token).exists():
                continue
            article_codes_to_create.append({
                'token': article_token,
                'name': article_name,
                'is_active': True,
            })

        if not uses_aca_enabled():
            if not article_codes_to_create:
                self.stdout.write(
                    self.style.WARNING(
                        "ConfigProject 'uses_aca' no està activat; no s'apliquen canvis ACA."
                    )
                )
                return
            self.stdout.write(
                self.style.WARNING(
                    "ConfigProject 'uses_aca' no està activat; només es crearan ArticleCode."
                )
            )
            updates = []
            variable_types_to_create = []
        else:
            product_token_value = get_config_value(ACA_PRODUCT_CONFIG_TOKEN)
            canon_product = find_canon_product(product_token_value)

            if not canon_product and not article_codes_to_create:
                self.stdout.write(
                    self.style.ERROR(
                        "No s'ha trobat cap Product amb name like 'CANON' per configurar ACA."
                    )
                )
                return

            updates = []
            variable_types_to_create = []

            if canon_product:
                if product_token_value != canon_product.token:
                    updates.append(
                        (
                            ACA_PRODUCT_CONFIG_TOKEN,
                            product_token_value or '(buit)',
                            canon_product.token,
                        )
                    )

                for config_token, search_patterns in ACA_RATE_CONFIG_SPECS:
                    matched_rates = find_price_rates_for_name_patterns(canon_product, search_patterns)
                    if not matched_rates:
                        self.stdout.write(
                            self.style.WARNING(
                                f"No s'han trobat PriceRate ACA per '{config_token}' "
                                f"(patrons: {', '.join(search_patterns)})"
                            )
                        )
                        continue

                    new_value = build_config_value_from_price_rates(matched_rates)
                    current_value = get_config_value(config_token) or ''
                    if current_value != new_value:
                        updates.append((config_token, current_value or '(buit)', new_value))

                dir_tokens = split_config_tokens(get_config_value(ACA_DIR_VARIABLE_CONFIG_TOKEN) or '')
                if not dir_tokens:
                    dir_tokens = [DEFAULT_ACA_VARIABLE_TYPE['token']]

                for variable_token in dir_tokens:
                    if VariableType.objects.filter(token=variable_token).exists():
                        continue
                    if variable_token == DEFAULT_ACA_VARIABLE_TYPE['token']:
                        variable_types_to_create.append(DEFAULT_ACA_VARIABLE_TYPE)
                    else:
                        variable_types_to_create.append({
                            'token': variable_token,
                            'name': variable_token,
                            'data_type': 'int',
                            'application': 'CT',
                            'is_active': True,
                            'is_vulnerable': False,
                        })

        if not updates and not variable_types_to_create and not article_codes_to_create:
            self.stdout.write(self.style.SUCCESS('La configuració ACA ja és coherent.'))
            return

        prefix = '[DRY RUN] ' if dry_run else ''

        with transaction.atomic():
            for config_token, old_value, new_value in updates:
                message = (
                    f"{prefix}ConfigProject '{config_token}': "
                    f"{old_value!r} -> {new_value!r}"
                )
                if dry_run:
                    self.stdout.write(message)
                else:
                    config, _created = ConfigProject.objects.get_or_create(
                        token=config_token,
                        defaults={'name': config_token, 'value': new_value},
                    )
                    config.value = new_value
                    config.save(update_fields=['value', 'updated_at'])
                    self.stdout.write(self.style.SUCCESS(message))

            for variable_data in variable_types_to_create:
                message = (
                    f"{prefix}Crear VariableType token={variable_data['token']!r} "
                    f"name={variable_data['name']!r}"
                )
                if dry_run:
                    self.stdout.write(message)
                else:
                    VariableType.objects.create(**variable_data)
                    self.stdout.write(self.style.SUCCESS(message))

            for article_data in article_codes_to_create:
                message = (
                    f"{prefix}Crear ArticleCode token={article_data['token']!r} "
                    f"name={article_data['name']!r}"
                )
                if dry_run:
                    self.stdout.write(message)
                else:
                    ArticleCode.objects.create(**article_data)
                    self.stdout.write(self.style.SUCCESS(message))

            if dry_run:
                transaction.set_rollback(True)

        self.stdout.write('')
        self.stdout.write(
            self.style.SUCCESS(
                f"{prefix}Configuracions actualitzades: {len(updates)}; "
                f"VariableType creats: {len(variable_types_to_create)}; "
                f"ArticleCode creats: {len(article_codes_to_create)}"
            )
        )
        self.stdout.write(
            self.style.WARNING(
                'Recorda executar fill_contract_use_aca per omplir use_aca als contractes:'
            )
        )
        self.stdout.write('  python manage.py fill_contract_use_aca --dry-run')
        self.stdout.write('  python manage.py fill_contract_use_aca')
