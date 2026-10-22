from django.test import SimpleTestCase

from billing.utils.sepa_file_service import SEPA_USTRD_MAX_LENGTH, build_sepa_concept


class BuildSepaConceptTests(SimpleTestCase):
    def test_single_invoice_is_appended_to_prefix(self):
        self.assertEqual(
            build_sepa_concept("AIGUA CONTRACTE C1", ["A-0001"]),
            "AIGUA CONTRACTE C1 FRA A-0001",
        )

    def test_without_invoice_numbers_keeps_prefix(self):
        self.assertEqual(build_sepa_concept("AIGUA CONTRACTE C1", [None, ""]), "AIGUA CONTRACTE C1")

    def test_grouped_payment_lists_all_invoices(self):
        self.assertEqual(
            build_sepa_concept("COMPROMÍS DE PAGAMENT CP1", ["A-0001", "A-0002"]),
            "COMPROMÍS DE PAGAMENT CP1 FRA A-0001 A-0002",
        )

    def test_custom_invoice_label(self):
        self.assertEqual(
            build_sepa_concept("WATER CONTRACT C1", ["A-0001"], "INV"),
            "WATER CONTRACT C1 INV A-0001",
        )

    def test_too_many_invoices_are_summarised_within_limit(self):
        numbers = [f"A-{i:010d}" for i in range(30)]
        concept = build_sepa_concept("COMPROMÍS DE PAGAMENT CP1", numbers)

        self.assertLessEqual(len(concept), SEPA_USTRD_MAX_LENGTH)
        listed = concept.split(" FRA ")[1].split(" ")
        hidden = int(listed[-1].lstrip("+"))
        self.assertEqual(len(listed) - 1 + hidden, len(numbers))
        self.assertEqual(listed[0], numbers[0])

    def test_invoices_that_fit_exactly_have_no_summary(self):
        prefix = "P"
        number = "X" * (SEPA_USTRD_MAX_LENGTH - len("P FRA "))
        self.assertEqual(build_sepa_concept(prefix, [number]), f"P FRA {number}")
