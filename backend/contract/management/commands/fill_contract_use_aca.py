import logging
from django.core.management.base import BaseCommand
from django.db.models import Q
from contract.models import Contract
from contract.utils.use_aca_service import run_fill_contract_use_aca
from coredata.models import ConfigProject
from watchdog.aca_config import split_config_tokens, uses_aca_enabled

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Omple el camp use_aca dels contractes segons les tarifes del producte CANON (id=6)'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Executa el script sense fer canvis a la base de dades',
        )

    def handle(self, *args, **options):
        dry_run = options.get('dry_run', False)
        result = run_fill_contract_use_aca(update_all_contracts=False, dry_run=dry_run)
        self.stdout.write(self.style.SUCCESS(str(result)))

def _build_fill_result(
    *,
    dry_run=False,
    update_all_contracts=False,
    skipped=False,
    reason=None,
    total_contracts=0,
    updated_count=0,
    error_count=0,
    skipped_reasons=None,
    skipped_examples=None,
):
    skipped_reasons = skipped_reasons or {}
    skipped_examples = skipped_examples or {}
    total_skipped = sum(skipped_reasons.values())

    return {
        'skipped': skipped,
        'reason': reason,
        'dry_run': dry_run,
        'update_all_contracts': update_all_contracts,
        'total_contracts': total_contracts,
        'updated_count': updated_count,
        'skipped_count': total_skipped,
        'error_count': error_count,
        'skipped_reasons': skipped_reasons,
        'skipped_examples': skipped_examples,
    }


def fill_contract_use_aca(update_all_contracts=False, dry_run=False, single_contract_id=None):
    if not uses_aca_enabled():
        logger.warning('No s\'actualitzarà use_aca')
        return _build_fill_result(
            dry_run=dry_run,
            update_all_contracts=update_all_contracts,
            skipped=True,
            reason='uses_aca_disabled',
        )

    contract_use_aca_mun_tokens = split_config_tokens(ConfigProject.objects.get(token="contract_use_aca_mun_tokens").value)
    contract_use_aca_dom_tokens = split_config_tokens(ConfigProject.objects.get(token="contract_use_aca_dom_tokens").value)
    contract_use_aca_ind_tokens = split_config_tokens(ConfigProject.objects.get(token="contract_use_aca_ind_tokens").value)
    contract_use_aca_gan_tokens = split_config_tokens(ConfigProject.objects.get(token="contract_use_aca_gan_tokens").value)
    contract_use_aca_alta_tokens = split_config_tokens(ConfigProject.objects.get(token="contract_use_aca_alta_tokens").value)
    contract_use_aca_dir_variable_token = split_config_tokens(ConfigProject.objects.get(token="contract_use_aca_dir_variable_token").value)
    token_product_aca_parts = split_config_tokens(
        ConfigProject.objects.get(token="token_product_aca").value
    )
    # Diccionari de mapeig de tokens a valors use_aca. Els tokens buits es descarten:
    # un "" coincideix amb qualsevol tarifa (`"" in token`) i marcava tots els contractes.
    token_to_use_aca = {
        **{token: 'A' for token in contract_use_aca_mun_tokens},
        **{token: 'D' for token in contract_use_aca_dom_tokens},
        **{token: 'I' for token in contract_use_aca_ind_tokens},
        **{token: 'Q' for token in contract_use_aca_gan_tokens},
        **{token: 'L' for token in contract_use_aca_alta_tokens},
    }
    
    # Obtenir tots els contractes actius
    contracts = Contract.objects.filter(is_active=True)
    if not update_all_contracts:
        contracts = contracts.filter(Q(use_aca__isnull=True) | Q(use_aca=''))
    if single_contract_id:
        contracts = Contract.objects.filter(id=single_contract_id)
    total_contracts = contracts.count()
    
    logger.info(f'Processant {total_contracts} contractes...')
    
    updated_count = 0
    skipped_reasons = {
        'no_canon_price_rate': 0,  # No té cap tarifa del producte CANON
        'token_no_match': 0,  # Té tarifa CANON però el token no coincideix
        'already_correct': 0,  # El valor use_aca ja és correcte
        'no_price_rates': 0,  # No té cap tarifa assignada
    }
    error_count = 0
    skipped_examples = {
        'no_canon_price_rate': [],
        'token_no_match': [],
        'already_correct': [],
        'no_price_rates': [],
    }

    for contract in contracts:
        try:
            # Obtenir tots els ContractPriceRate del contracte
            contract_price_rates = contract.price_rates.all()
            
            # Si no té cap tarifa
            if not contract_price_rates.exists():
                skipped_reasons['no_price_rates'] += 1
                if len(skipped_examples['no_price_rates']) < 5:
                    skipped_examples['no_price_rates'].append(contract.token)
                continue
            
            # Buscar tarifes del producte CANON
            use_aca_value = None
            canon_price_rate_found = False
            canon_token = None
            
            for contract_price_rate in contract_price_rates:
                if not contract_price_rate.price_rate:
                    continue
                
                price_rate = contract_price_rate.price_rate
                
                # Comprovar si la tarifa pertany al producte CANON
                # token_product_aca may be "970" or "970_1|00_970|AC_970_001"
                product_token = price_rate.product.token if price_rate.product else None
                if product_token and any(part in product_token for part in token_product_aca_parts):
                    canon_price_rate_found = True
                    # Obtenir el token de la tarifa
                    token = price_rate.token
                    canon_token = token
                    
                    if token:
                        # Buscar el valor use_aca corresponent
                        for token_key, use_aca in token_to_use_aca.items():
                            if token_key in token:
                                use_aca_value = use_aca
                                break
                        
                        # Si hem trobat un valor, sortir del bucle
                        if use_aca_value:
                            break
            if any(var.type.token in contract_use_aca_dir_variable_token for var in contract.variables.all()):
                use_aca_value = "M"
            
            # Si no té cap tarifa CANON
            if not canon_price_rate_found:
                skipped_reasons['no_canon_price_rate'] += 1
                if len(skipped_examples['no_canon_price_rate']) < 5:
                    skipped_examples['no_canon_price_rate'].append(contract.token)
                continue
            
            # Si té tarifa CANON però el token no coincideix
            if not use_aca_value:
                skipped_reasons['token_no_match'] += 1
                if len(skipped_examples['token_no_match']) < 5:
                    skipped_examples['token_no_match'].append(f"{contract.token} (token: {canon_token})")
                continue
            
            # Si hem trobat un valor use_aca i és diferent del que té el contracte
            if contract.use_aca != use_aca_value:
                old_value = contract.use_aca
                if not dry_run:
                    contract.use_aca = use_aca_value
                    contract.save(update_fields=['use_aca'])
                
                updated_count += 1
                logger.info(
                    f'Contracte {contract.token}: use_aca actualitzat de "{old_value}" a "{use_aca_value}"'
                )
            else:
                # El valor ja és correcte
                skipped_reasons['already_correct'] += 1
                if len(skipped_examples['already_correct']) < 5:
                    skipped_examples['already_correct'].append(f"{contract.token} (ja té '{use_aca_value}')")
                
        except Exception as e:
            error_count += 1
            logger.error(f'Error processant contracte {contract.token}: {str(e)}')
            logger.error(f'Error processant contracte {contract.token}: {str(e)}', exc_info=True)
    
    # Resum
    total_skipped = sum(skipped_reasons.values())
    
    logger.info('')
    logger.info('=' * 50)
    logger.info('RESUM')
    logger.info('=' * 50)
    logger.info(f'Total contractes processats: {total_contracts}')
    logger.info(f'Contractes actualitzats: {updated_count}')
    logger.info(f'Contractes saltats: {total_skipped}')
    logger.info(f'Errors: {error_count}')
    
    # Detall de contractes saltats
    if total_skipped > 0:
        logger.info('')
        logger.warning('DETALL DE CONTRACTES SALTATS:')
        logger.info(f'  - Sense tarifes assignades: {skipped_reasons["no_price_rates"]}')
        if skipped_examples['no_price_rates']:
            logger.info(f'    Exemples: {", ".join(skipped_examples["no_price_rates"])}')
        
        logger.info(f'  - Sense tarifa del producte CANON (id=6): {skipped_reasons["no_canon_price_rate"]}')
        if skipped_examples['no_canon_price_rate']:
            logger.info(f'    Exemples: {", ".join(skipped_examples["no_canon_price_rate"])}')
        
        logger.info(f'  - Token CANON no coincideix amb cap patró conegut: {skipped_reasons["token_no_match"]}')
        if skipped_examples['token_no_match']:
            logger.info(f'    Exemples: {", ".join(skipped_examples["token_no_match"])}')
        
        logger.info(f'  - Valor use_aca ja és correcte: {skipped_reasons["already_correct"]}')
        if skipped_examples['already_correct']:
            logger.info(f'    Exemples: {", ".join(skipped_examples["already_correct"])}')
    
    if dry_run:
        logger.warning('\n⚠️  MODO DRY-RUN: No s\'han fet canvis a la base de dades')

    return _build_fill_result(
        dry_run=dry_run,
        update_all_contracts=update_all_contracts,
        total_contracts=total_contracts,
        updated_count=updated_count,
        error_count=error_count,
        skipped_reasons=skipped_reasons,
        skipped_examples=skipped_examples,
    )