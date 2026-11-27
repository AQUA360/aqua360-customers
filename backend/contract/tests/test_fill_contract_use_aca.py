from django.test import TestCase

from contract.management.commands.fill_contract_use_aca import fill_contract_use_aca
from contract.models import Contract, ContractPriceRate, ContractUseType
from coredata.models import ConfigProject
from pricing.models import PriceRate, Product


class FillContractUseAcaAgriculturalTests(TestCase):
    """Els contractes agrícoles sense tarifa de cànon queden amb l'ús ACA «G» si el seu tipus d'ús és
    a la configuració; la resta de contractes sense cànon no es toquen."""

    def setUp(self):
        for token, value in (
            ('public_org_type', 'aca'),
            ('contract_use_aca_mun_tokens', 'MUNICIPAL'),
            ('contract_use_aca_dom_tokens', 'DOMESTIC'),
            ('contract_use_aca_ind_tokens', 'INDUSTRIAL'),
            ('contract_use_aca_gan_tokens', 'RAMADE'),
            ('contract_use_aca_alta_tokens', 'ALTA'),
            ('contract_use_aca_dir_variable_token', 'ACA-DIR'),
            ('token_product_aca', 'ACA'),
            ('contract_use_aca_agr_use_type_tokens', 'AGRICOLA|REG'),
            ('contract_terminated_status', 'BAIXA'),
        ):
            # public_org_type ja el crea una migració
            ConfigProject.objects.update_or_create(token=token, defaults={'value': value})
        self.water_rate = PriceRate.objects.create(token='AIGUA_REG', product=Product.objects.create(token='AIGUA'))
        self.canon_rate = PriceRate.objects.create(token='ACA_DOMESTIC', product=Product.objects.create(token='ACA'))

    def contract(self, token, use_type_token, *price_rates):
        contract = Contract.objects.create(
            token=token, use_type=ContractUseType.objects.create(token=use_type_token, name=use_type_token),
        )
        contract.price_rates.set([ContractPriceRate.objects.create(price_rate=rate) for rate in price_rates])
        return contract

    def test_agricultural_use_type_without_canon_is_g(self):
        self.contract('C-AGR', 'AGRICOLA', self.water_rate)
        self.contract('C-DOM', 'DOMESTIC', self.water_rate)
        # Amb tarifa de cànon mana la tarifa, encara que el tipus d'ús sigui agrícola
        self.contract('C-AGR-ACA', 'REG', self.water_rate, self.canon_rate)

        fill_contract_use_aca()

        uses = dict(Contract.objects.values_list('token', 'use_aca'))
        self.assertEqual(uses, {'C-AGR': 'G', 'C-DOM': None, 'C-AGR-ACA': 'D'})

    def test_agricultural_use_type_without_any_price_rate_is_g(self):
        self.contract('C-AGR', 'AGRICOLA')
        self.contract('C-DOM', 'DOMESTIC')

        fill_contract_use_aca()

        uses = dict(Contract.objects.values_list('token', 'use_aca'))
        self.assertEqual(uses, {'C-AGR': 'G', 'C-DOM': None})


class FillContractUseAcaAltaTests(TestCase):
    """Les tarifes d'ALTA es distingeixen de les industrials encara que hi casin."""

    def setUp(self):
        for token, value in (
            ('public_org_type', 'aca'),
            ('contract_use_aca_mun_tokens', 'MUNICIPAL'),
            ('contract_use_aca_dom_tokens', 'DOMESTIC'),
            ('contract_use_aca_ind_tokens', 'CAN-IND|CAN'),
            ('contract_use_aca_gan_tokens', 'RAMADE'),
            ('contract_use_aca_alta_tokens', 'CAN-ALTA'),
            ('contract_use_aca_dir_variable_token', 'ACA-DIR'),
            ('token_product_aca', 'ACA'),
            ('contract_use_aca_agr_use_type_tokens', ''),
            ('contract_terminated_status', 'BAIXA'),
        ):
            ConfigProject.objects.update_or_create(token=token, defaults={'value': value})
        self.product = Product.objects.create(token='ACA')

    def contract(self, token, rate_token):
        contract = Contract.objects.create(token=token)
        rate = PriceRate.objects.create(token=rate_token, product=self.product)
        contract.price_rates.set([ContractPriceRate.objects.create(price_rate=rate)])
        return contract

    def test_alta_rate_matching_industrial_token_is_alta(self):
        self.contract('C-ALTA', 'CAN-ALTA')
        self.contract('C-ALTA-2', 'CAN-ALTA-2')
        self.contract('C-IND', 'CAN-IND')

        fill_contract_use_aca()

        uses = dict(Contract.objects.values_list('token', 'use_aca'))
        self.assertEqual(uses, {'C-ALTA': 'L', 'C-ALTA-2': 'L', 'C-IND': 'I'})

    def test_exact_token_wins_over_contained_one(self):
        # 'CAN-ALTA' és dins de 'CAN-ALTA-IND', però el token industrial és el de la tarifa
        ConfigProject.objects.filter(token='contract_use_aca_ind_tokens').update(value='CAN-ALTA-IND')
        self.contract('C-IND', 'CAN-ALTA-IND')

        fill_contract_use_aca()

        self.assertEqual(Contract.objects.get(token='C-IND').use_aca, 'I')
