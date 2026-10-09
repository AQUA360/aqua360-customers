from django.test import TestCase

from coredata.models import ConfigProject
from pricing.models import PriceRate
from pricing.utils.return_fee_service import RETURN_FEE_CONFIG_TOKENS, sync_return_fee_config


class ReturnFeeConfigSyncTests(TestCase):
    """La tarifa de despeses de devolució ha de configurar-se sola en marcar-la."""

    def config_values(self):
        return {
            token: ConfigProject.objects.filter(token=token).values_list('value', flat=True).first()
            for token in RETURN_FEE_CONFIG_TOKENS
        }

    def test_marking_creates_and_fills_every_config(self):
        ConfigProject.objects.filter(token__in=RETURN_FEE_CONFIG_TOKENS).delete()
        price_rate = PriceRate.objects.create(token='DR', name='Despeses de devolució', is_return_fee=True)

        sync_return_fee_config(price_rate)

        self.assertEqual(self.config_values(), {token: 'DR' for token in RETURN_FEE_CONFIG_TOKENS})

    def test_marking_a_new_one_unmarks_the_previous(self):
        previous = PriceRate.objects.create(token='DR', name='Antiga', is_return_fee=True)
        sync_return_fee_config(previous)

        current = PriceRate.objects.create(token='DR2', name='Nova', is_return_fee=True)
        sync_return_fee_config(current)

        previous.refresh_from_db()
        self.assertFalse(previous.is_return_fee)
        self.assertEqual(self.config_values(), {token: 'DR2' for token in RETURN_FEE_CONFIG_TOKENS})

    def test_renaming_the_token_follows(self):
        price_rate = PriceRate.objects.create(token='DR', name='Despeses de devolució', is_return_fee=True)
        sync_return_fee_config(price_rate)

        price_rate.token = 'DEV'
        price_rate.save()
        sync_return_fee_config(price_rate)

        self.assertEqual(self.config_values(), {token: 'DEV' for token in RETURN_FEE_CONFIG_TOKENS})

    def test_unmarking_only_clears_its_own_configs(self):
        price_rate = PriceRate.objects.create(token='DR', name='Despeses de devolució', is_return_fee=True)
        sync_return_fee_config(price_rate)
        other_token = list(RETURN_FEE_CONFIG_TOKENS)[-1]
        ConfigProject.objects.filter(token=other_token).update(value='ALTRA')

        price_rate.is_return_fee = False
        price_rate.save()
        sync_return_fee_config(price_rate)

        values = self.config_values()
        self.assertIsNone(values['invoice_return_price_rate_token'])
        self.assertEqual(values[other_token], 'ALTRA')
