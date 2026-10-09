from django.core.management.base import BaseCommand
from django.db.models import Q

from billing.models import ConfigAca
from contract.models import ContractUseType, VariableType
from coredata.models import ConfigProject
from pricing.models import PriceRate, Product
from service.models import Exploitation

ACA_CONFIG_SPECS = (
    ('contract_use_aca_mun_tokens', 'PriceRate', 'price_rates', 'price_rates'),
    ('contract_use_aca_dom_tokens', 'PriceRate', 'price_rates', 'price_rates'),
    ('contract_use_aca_ind_tokens', 'PriceRate', 'price_rates', 'price_rates'),
    ('contract_use_aca_gan_tokens', 'PriceRate', 'price_rates', 'price_rates'),
    ('contract_use_aca_alta_tokens', 'PriceRate', 'price_rates', 'price_rates'),
    ('contract_use_aca_dir_variable_token', 'VariableType', 'variable_types', 'variable_types'),
    ('tarifa_social', 'VariableType', 'variable_types', 'variable_types'),
    ('token_product_aca', 'Product', 'products', 'products'),
    ('contract_keeper_use_type_token', 'ContractUseType', 'contract_use_types', 'contract_use_types'),
)


def _split_tokens(value):
    if not value:
        return []
    return [part.strip() for part in value.split('|') if part.strip()]


def _resolve_related(resolver_name, exploitation, tokens):
    if not tokens:
        empty = {
            'price_rates': PriceRate.objects.none(),
            'products': Product.objects.none(),
            'variable_types': VariableType.objects.none(),
            'contract_use_types': ContractUseType.objects.none(),
        }
        return empty[resolver_name]

    if resolver_name == 'price_rates':
        token_q = Q()
        for token in tokens:
            token_q |= Q(token__icontains=token)
        return PriceRate.objects.filter(
            product__exploitation=exploitation,
            is_active=True,
        ).filter(token_q).distinct()

    if resolver_name == 'products':
        token_q = Q()
        for token in tokens:
            token_q |= Q(token__icontains=token)
        return Product.objects.filter(
            exploitation=exploitation,
            is_active=True
        ).filter(token_q).distinct()

    if resolver_name == 'variable_types':
        return VariableType.objects.filter(token__in=tokens)

    if resolver_name == 'contract_use_types':
        return ContractUseType.objects.filter(token__in=tokens)

    raise ValueError(f'Unknown resolver: {resolver_name}')


def update_config_aca_service():
    config_projects = {}
    for token, _, _, _ in ACA_CONFIG_SPECS:
        try:
            config_projects[token] = ConfigProject.objects.get(token=token)
        except ConfigProject.DoesNotExist:
            print(f'ConfigProject not found for token: {token}')

    created_count = 0
    updated_count = 0

    for exploitation in Exploitation.objects.all():
        for token, token_type, m2m_field, resolver_name in ACA_CONFIG_SPECS:
            if token not in config_projects:
                continue
            config_project = config_projects[token]
            related_qs = _resolve_related(
                resolver_name,
                exploitation,
                _split_tokens(config_project.value),
            )
            result = _upsert_config_aca(
                exploitation=exploitation,
                config_project=config_project,
                token_type=token_type,
                m2m_field=m2m_field,
                related_qs=related_qs,
            )
            if result == 'created':
                created_count += 1
            else:
                updated_count += 1

    print(f'Created/updated: created={created_count}, updated={updated_count} ')
    
    for config in config_projects.values():
        config_acas = ConfigAca.objects.filter(config_project=config)
        new_value_tokens = set()
        for config_aca in config_acas:
            if config_aca.token_type == 'Product':
                tokens = config_aca.products.values_list('token', flat=True)
            elif config_aca.token_type == 'PriceRate':
                tokens = config_aca.price_rates.values_list('token', flat=True)
            elif config_aca.token_type == 'VariableType':
                tokens = config_aca.variable_types.values_list('token', flat=True)
            elif config_aca.token_type == 'ContractUseType':
                tokens = config_aca.contract_use_types.values_list('token', flat=True)
            else:
                continue
            for token in tokens:
                if token not in new_value_tokens:
                    new_value_tokens.add(token)
        config.value = '|'.join(new_value_tokens)
        config.save()



def _upsert_config_aca(
    *,
    exploitation,
    config_project,
    token_type,
    m2m_field,
    related_qs,
):
    related_count = related_qs.count()
    existing = ConfigAca.objects.filter(
        exploitation=exploitation,
        config_project=config_project,
    ).first()

    label = (
        f'exploitation={exploitation.id} config={config_project.token} '
        f'type={token_type} related={related_count}'
    )

    if existing:
        existing.token = config_project.token
        existing.token_type = token_type
        existing.is_active = True
        existing.save(update_fields=['token', 'token_type', 'is_active', 'updated_at'])
        getattr(existing, m2m_field).set(related_qs)
        print(f'Updated ConfigAca ({label})')
        return 'updated'

    config_aca = ConfigAca.objects.create(
        exploitation=exploitation,
        config_project=config_project,
        token=config_project.token,
        token_type=token_type,
        is_active=True,
    )
    getattr(config_aca, m2m_field).set(related_qs)
    print(f'Created ConfigAca ({label})')
    return 'created'