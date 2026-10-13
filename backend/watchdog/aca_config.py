from django.db.models import Q

from contract.models import Contract, ContractUseType, VariableType
from coredata.models import ConfigProject
from pricing.models import ArticleCode, LineItemType, PriceRate, Product

ACA_USES_CONFIG_TOKEN = 'uses_aca'
ACA_NOTIFICATION_CONFIG_TOKEN = 'aca_notification_enabled'
ACA_PRODUCT_CONFIG_TOKEN = 'token_product_aca'
ACA_DIR_VARIABLE_CONFIG_TOKEN = 'contract_use_aca_dir_variable_token'
ACA_KEEPER_USE_TYPE_CONFIG_TOKEN = 'contract_keeper_use_type_token'
ACA_RAMADER_ARTICLE_TOKEN = 'ramader_0'

REQUIRED_ACA_ARTICLE_CODE_SPECS = (
    ('part_fixa', 'Part fixa'),
    ('part_variable', 'Part variable'),
)

ACA_RATE_CONFIG_SPECS = (
    ('contract_use_aca_mun_tokens', ('MUNICIPAL',)),
    ('contract_use_aca_ind_tokens', ('INDUSTRIAL',)),
    ('contract_use_aca_dom_tokens', ('DOMESTIC', 'DOMÈSTIC')),
    ('contract_use_aca_gan_tokens', ('AGRICUL', 'RAMADE','AGRICO')),
)

DEFAULT_ACA_VARIABLE_TYPE = {
    'token': 'Factura-ACA',
    'name': 'Factura ACA',
    'data_type': 'int',
    'application': 'CT',
    'is_active': True,
    'is_vulnerable': False,
}


def uses_aca_enabled():
    try:
        value = ConfigProject.objects.get(token=ACA_USES_CONFIG_TOKEN).value
    except ConfigProject.DoesNotExist:
        return False
    if value is None:
        return False
    return str(value).strip().lower() in ('true', '1', 'yes', 't')


def aca_notification_enabled():
    """Activa l'enviament de notificacions a l'ACA (sol·licituds pendents d'enviar,
    exportació del fitxer d'ampliació de trams). La creació de la Bonification/Variable
    ACA-TRAM en augmentar `total_persons` NO depèn d'aquest flag, només de `uses_aca_enabled`
    (veure `contract.signals.create_aca_bonification_on_total_persons_increase`)."""
    if not uses_aca_enabled():
        return False
    try:
        value = ConfigProject.objects.get(token=ACA_NOTIFICATION_CONFIG_TOKEN).value
    except ConfigProject.DoesNotExist:
        return False
    if value is None:
        return False
    return str(value).strip().lower() in ('true', '1', 'yes', 't')


def get_config_value(token):
    try:
        return (ConfigProject.objects.get(token=token).value or '').strip()
    except ConfigProject.DoesNotExist:
        return None


def find_canon_product(preferred_token=None):
    if preferred_token:
        product = Product.objects.filter(token=preferred_token).first()
        if product:
            return product
    return Product.objects.filter(name__icontains='CANON').order_by('id').first()


def get_aca_price_rates(product):
    if not product:
        return PriceRate.objects.none()
    token_hint = product.token or ''
    if token_hint:
        return PriceRate.objects.filter(
            is_active=True,
        ).filter(
            Q(product=product) | Q(product__token__icontains=token_hint)
        ).distinct()
    return PriceRate.objects.filter(product=product, is_active=True)


def split_config_tokens(value):
    if not value:
        return []
    return [part.strip() for part in value.split('|') if part.strip()]


def price_rate_matches_pattern(price_rate, pattern):
    token = price_rate.token or ''
    name = price_rate.name or ''
    return pattern in token or pattern in name


def config_patterns_match_price_rates(patterns, price_rates):
    if not patterns:
        return False, patterns
    missing = []
    for pattern in patterns:
        if not any(price_rate_matches_pattern(rate, pattern) for rate in price_rates):
            missing.append(pattern)
    return len(missing) == 0, missing


def find_price_rates_for_name_patterns(product, patterns):
    if not product:
        return []
    rates = list(get_aca_price_rates(product))
    matched = []
    seen_ids = set()
    for pattern in patterns:
        pattern_upper = pattern.upper()
        for rate in rates:
            if rate.id in seen_ids:
                continue
            haystack = f'{rate.name or ""} {rate.token or ""}'.upper()
            if pattern_upper in haystack:
                matched.append(rate)
                seen_ids.add(rate.id)
    return matched


def build_config_value_from_price_rates(price_rates):
    tokens = sorted({rate.token for rate in price_rates if rate.token})
    return '|'.join(tokens)


def _append_aca_article_code_fix_recommendations(issues):
    issues.append('')
    issues.append('Recomanació (watchdog): crea ArticleCode i vincula LineItemType amb:')
    issues.append('  python manage.py watchdog_fix_aca_config --dry-run')
    issues.append('  python manage.py watchdog_fix_aca_config')
    issues.append('  python manage.py fix_aca_lineitemtype_articles --dry-run')
    issues.append('  python manage.py fix_aca_lineitemtype_articles')


def check_aca_article_code_issues():
    """ArticleCode, LineItemType i contract_keeper_use_type_token per exports ACA."""
    if not uses_aca_enabled():
        return []

    issues = []
    existing_article_tokens = []

    for article_token, article_name in REQUIRED_ACA_ARTICLE_CODE_SPECS:
        if not ArticleCode.objects.filter(token=article_token).exists():
            issues.append(
                f"ArticleCode amb token '{article_token}' ({article_name}) no existeix; "
                "necessari per a l'informe Declaració ACA i altres exports ACA"
            )
        else:
            existing_article_tokens.append(article_token)

    for article_token in existing_article_tokens:
        if not LineItemType.objects.filter(article__token=article_token).exists():
            issues.append(
                f"No hi ha cap LineItemType amb article vinculat a ArticleCode '{article_token}'"
            )

    if ArticleCode.objects.filter(token=ACA_RAMADER_ARTICLE_TOKEN).exists():
        keeper_value = get_config_value(ACA_KEEPER_USE_TYPE_CONFIG_TOKEN)
        if keeper_value is None:
            issues.append(
                f"ConfigProject '{ACA_KEEPER_USE_TYPE_CONFIG_TOKEN}' no existeix "
                f"(requerit perquè existeix ArticleCode '{ACA_RAMADER_ARTICLE_TOKEN}')"
            )
        elif not keeper_value:
            issues.append(
                f"ConfigProject '{ACA_KEEPER_USE_TYPE_CONFIG_TOKEN}' té el valor buit "
                f"(requerit perquè existeix ArticleCode '{ACA_RAMADER_ARTICLE_TOKEN}')"
            )
        elif not ContractUseType.objects.filter(token=keeper_value).exists():
            issues.append(
                f"ConfigProject '{ACA_KEEPER_USE_TYPE_CONFIG_TOKEN}' té valor '{keeper_value}' "
                "però no coincideix amb cap ContractUseType.token"
            )

    if issues:
        _append_aca_article_code_fix_recommendations(issues)

    return issues


def check_aca_configuration_issues():
    """
    Retorna la llista d'incidències de configuració ACA.
    Buit si uses_aca no està activat o tot és correcte.
    """
    if not uses_aca_enabled():
        return []

    issues = []

    product_token_value = get_config_value(ACA_PRODUCT_CONFIG_TOKEN)
    canon_product = find_canon_product(product_token_value)

    if not product_token_value:
        issues.append(
            f"ConfigProject '{ACA_PRODUCT_CONFIG_TOKEN}' no existeix o té el valor buit"
        )
    elif not Product.objects.filter(token=product_token_value).exists():
        fallback = Product.objects.filter(name__icontains='CANON').order_by('id').first()
        if fallback:
            issues.append(
                f"ConfigProject '{ACA_PRODUCT_CONFIG_TOKEN}' té valor '{product_token_value}' "
                f"però no coincideix amb cap Product.token; es pot usar '{fallback.token}' "
                f"(Product ID {fallback.id}, name={fallback.name!r})"
            )
        else:
            issues.append(
                f"ConfigProject '{ACA_PRODUCT_CONFIG_TOKEN}' té valor '{product_token_value}' "
                "però no coincideix amb cap Product.token i no s'ha trobat cap producte CANON"
            )
            canon_product = None
    else:
        canon_product = Product.objects.filter(token=product_token_value).first()

    aca_price_rates = list(get_aca_price_rates(canon_product)) if canon_product else []

    for config_token, search_patterns in ACA_RATE_CONFIG_SPECS:
        config_value = get_config_value(config_token)
        if config_value is None:
            issues.append(f"ConfigProject '{config_token}' no existeix")
            continue
        if not config_value:
            issues.append(f"ConfigProject '{config_token}' té el valor buit")
            continue

        patterns = split_config_tokens(config_value)
        ok, missing = config_patterns_match_price_rates(patterns, aca_price_rates)
        if not ok:
            issues.append(
                f"ConfigProject '{config_token}' té patrons sense PriceRate ACA coincident: "
                f"{', '.join(missing)} (valor actual: {config_value!r})"
            )

    dir_variable_value = get_config_value(ACA_DIR_VARIABLE_CONFIG_TOKEN)
    if dir_variable_value is None:
        issues.append(f"ConfigProject '{ACA_DIR_VARIABLE_CONFIG_TOKEN}' no existeix")
    else:
        for variable_token in split_config_tokens(dir_variable_value):
            if not VariableType.objects.filter(token=variable_token).exists():
                issues.append(
                    f"ConfigProject '{ACA_DIR_VARIABLE_CONFIG_TOKEN}' referencia "
                    f"VariableType.token '{variable_token}' però no existeix a la base de dades"
                )

    # Contractes actius amb tarifa ACA però sense use_aca
    if canon_product and product_token_value:
        contracts_missing_use_aca = Contract.objects.filter(
            is_active=True,
            use_aca__isnull=True,
            price_rates__price_rate__product=canon_product,
        ).distinct()
        total_missing = contracts_missing_use_aca.count()
        if total_missing:
            examples = list(
                contracts_missing_use_aca.values_list('token', flat=True)[:5]
            )
            examples_text = ', '.join(examples)
            suffix = (
                f" (exemples: {examples_text})"
                if examples_text
                else ''
            )
            issues.append(
                f"{total_missing} contracte(s) actiu(s) amb tarifa ACA però use_aca buit{suffix}"
            )

    if issues:
        issues.append('')
        issues.append('Recomanació (watchdog): configura ACA i use_aca amb:')
        issues.append('  python manage.py watchdog_fix_aca_config --dry-run')
        issues.append('  python manage.py watchdog_fix_aca_config')
        issues.append('  python manage.py fill_contract_use_aca --dry-run')
        issues.append('  python manage.py fill_contract_use_aca')

    return issues
