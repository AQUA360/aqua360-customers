from types import SimpleNamespace

from django.test import SimpleTestCase

from pricing.utils.accounting_service import (
    _apply_declare_settings,
    _empty_iva_values,
    _line_has_negative_amount,
)


def _iva_line(*, tax_10=0.0, tax_21=0.0, base_10=0.0, base_21=0.0, total=None):
    iva = _empty_iva_values()
    iva['10.00'] = {'base': base_10, 'tax': tax_10}
    iva['21.00'] = {'base': base_21, 'tax': tax_21}
    if total is None:
        total = tax_10 + tax_21
    return {
        'total': total,
        'subtotal': 0.0,
        'iva': iva,
        'return_category': 'invoice',
        'is_invoice': False,
    }


def _pricing(*, declare_sign='positive', return_sign='negative', declare_as='debt', return_declare_as='debt'):
    return SimpleNamespace(
        declare_as=declare_as,
        declare_sign=declare_sign,
        return_declare_as=return_declare_as,
        return_declare_as_invoice=None,
        return_declare_as_payment=None,
        return_declare_as_lineitem=None,
        return_sign=return_sign,
        return_sign_invoice=None,
        return_sign_payment=None,
        return_sign_lineitem=None,
    )


class LineHasNegativeAmountTests(SimpleTestCase):
    def test_mixed_iva_rates_with_positive_net_is_not_return(self):
        line = _iva_line(tax_10=-16.58, tax_21=26.11, base_10=-165.77, base_21=124.32)
        self.assertFalse(_line_has_negative_amount(line))

    def test_negative_net_tax_is_return(self):
        line = _iva_line(tax_10=-16.58, tax_21=5.0)
        self.assertTrue(_line_has_negative_amount(line))

    def test_zero_total_uses_iva_net(self):
        line = _iva_line(tax_10=-16.58, tax_21=5.0, total=0.0)
        line['total'] = 0.0
        self.assertTrue(_line_has_negative_amount(line))


class ApplyDeclareSettingsMixedIvaTests(SimpleTestCase):
    def test_mixed_iva_keeps_declare_sign_for_positive_net(self):
        line = _iva_line(tax_10=-16.58, tax_21=26.11, base_10=-165.77, base_21=124.32)
        updated = _apply_declare_settings(line, _pricing())
        self.assertEqual(updated['declare_as'], 'debt')
        self.assertEqual(updated['total'], 9.53)
        self.assertEqual(updated['iva']['10.00']['tax'], -16.58)
        self.assertEqual(updated['iva']['21.00']['tax'], 26.11)

    def test_negative_net_uses_return_sign(self):
        line = _iva_line(tax_10=-26.11, tax_21=16.58)
        updated = _apply_declare_settings(line, _pricing())
        self.assertEqual(updated['declare_as'], 'debt')
        self.assertEqual(updated['total'], -9.53)
