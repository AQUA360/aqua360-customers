from types import SimpleNamespace

from django.test import SimpleTestCase, TestCase

from billing.utils.sepa_file_service import (
    SEPA_USTRD_MAX_LENGTH,
    append_sepa_invoice_detail,
    build_payment_sepa_concept,
    build_sepa_concept,
    get_saved_concept_fields,
    normalize_concept_fields,
    save_concept_fields,
)


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

    def test_long_prefix_preserves_complete_omitted_invoice_count(self):
        for prefix_length in (133, 136, 140, 160):
            for invoice_count in (1, 12, 123):
                with self.subTest(prefix_length=prefix_length, invoice_count=invoice_count):
                    concept = build_sepa_concept(
                        "P" * prefix_length, ["A-0001"] * invoice_count
                    )

                    self.assertLessEqual(len(concept), SEPA_USTRD_MAX_LENGTH)
                    self.assertTrue(concept.endswith(f" +{invoice_count}"))


class AppendSepaInvoiceDetailTests(SimpleTestCase):
    PREFIX = "AIGUA CONTRACTE C1 FRA A-0001"

    def _invoice(self, street="Carrer Major", number=12, postal_code="25001", **kwargs):
        address = SimpleNamespace(
            street=street,
            street_number=number,
            postal_code=postal_code,
            floor=None,
            door=None,
            stair=None,
            building=None,
        )
        supply_point = SimpleNamespace(name="PS 1", token="SP1", address=address)
        data = dict(
            total_final=12.5,
            consumption=15.0,
            real_consumption=None,
            contract=SimpleNamespace(supply_point_default=supply_point),
        )
        data.update(kwargs)
        return SimpleNamespace(**data)

    def test_detail_has_amount_consumption_supply_point_and_postal_code(self):
        self.assertEqual(
            append_sepa_invoice_detail(self.PREFIX, self._invoice(), "ca"),
            f"{self.PREFIX} IMPORT 12.50EUR CONSUM 15m3 PUNT SUBM. Carrer Major, 12 25001",
        )

    def test_empty_fields_are_omitted(self):
        invoice = self._invoice(consumption=None, contract=None)
        self.assertEqual(
            append_sepa_invoice_detail(self.PREFIX, invoice, "en"),
            f"{self.PREFIX} AMOUNT 12.50EUR",
        )

    def test_postal_code_is_dropped_entirely_when_it_does_not_fit(self):
        head = f"{self.PREFIX} IMPORT 12.50EUR CONSUM 15m3 PUNT SUBM. "
        street = "X" * (SEPA_USTRD_MAX_LENGTH - len(head) - len(", 12") - 2)  # sobren 2: no hi cap " 25001"
        concept = append_sepa_invoice_detail(self.PREFIX, self._invoice(street=street), "ca")
        self.assertEqual(concept, f"{head}{street}, 12")

    def test_long_street_is_cut_with_ellipsis_keeping_the_number(self):
        concept = append_sepa_invoice_detail(self.PREFIX, self._invoice(street="Y" * 200, number=7), "ca")
        self.assertLessEqual(len(concept), SEPA_USTRD_MAX_LENGTH)
        self.assertTrue(concept.endswith("..., 7"))
        self.assertNotIn("25001", concept)

    def test_supply_point_without_address_falls_back_to_name(self):
        invoice = self._invoice()
        invoice.contract.supply_point_default.address = None
        self.assertTrue(append_sepa_invoice_detail(self.PREFIX, invoice, "ca").endswith("PUNT SUBM. PS 1"))

    def test_stair_floor_and_door_are_kept_without_double_spaces(self):
        invoice = self._invoice()
        address = invoice.contract.supply_point_default.address
        address.stair, address.floor, address.door = "B", "2", "1"
        self.assertTrue(
            append_sepa_invoice_detail(self.PREFIX, invoice, "ca").endswith("Carrer Major, 12 B 2-1 25001")
        )

    def test_long_street_keeps_number_stair_floor_and_door(self):
        invoice = self._invoice(street="Y" * 200, number=7)
        address = invoice.contract.supply_point_default.address
        address.stair, address.floor, address.door = "B", "2", "1"
        self.assertTrue(append_sepa_invoice_detail(self.PREFIX, invoice, "ca").endswith("..., 7 B 2-1"))

    def test_address_without_number_has_no_dangling_comma(self):
        invoice = self._invoice(number=None)
        self.assertTrue(
            append_sepa_invoice_detail(self.PREFIX, invoice, "ca").endswith("PUNT SUBM. Carrer Major 25001")
        )


class MultipleSupplyPointsTests(SimpleTestCase):
    PREFIX = "AIGUA CONTRACTE C1 FRA A-0001"

    def _point(self, street, number, pk, postal_code="25001", **unit):
        address = SimpleNamespace(
            street=street, street_number=number, postal_code=postal_code,
            floor=unit.get("floor"), door=unit.get("door"), stair=unit.get("stair"), building=None,
        )
        return SimpleNamespace(pk=pk, name=f"PS{pk}", token=f"SP{pk}", address=address)

    def _invoice(self, *points):
        readings = [SimpleNamespace(supply_point=p) for p in points]
        return SimpleNamespace(
            total_final=12.5, consumption=15.0, real_consumption=None, contract=None,
            readings=SimpleNamespace(all=lambda: readings),
        )

    def _detail(self, *points, language="ca"):
        return append_sepa_invoice_detail(self.PREFIX, self._invoice(*points), language).split("PUNT SUBM. ")[-1]

    def test_same_street_numbers_are_joined_with_commas(self):
        points = [self._point("AV PAISOS CATALANS", n, i) for i, n in enumerate((24, 26))]
        self.assertEqual(self._detail(*points), "AV PAISOS CATALANS 24, 26 25001")

    def test_numbers_are_sorted(self):
        points = [self._point("AV X", n, i) for i, n in enumerate((28, 24, 26))]
        self.assertEqual(self._detail(*points), "AV X 24, 26, 28 25001")

    def test_same_number_groups_units_in_brackets(self):
        points = [
            self._point("AV X", 1, 1, stair="B", floor="1", door="1"),
            self._point("AV X", 1, 2, stair="B", floor="2", door="1"),
        ]
        self.assertEqual(self._detail(*points), "AV X 1 (B 1-1,B 2-1) 25001")

    def test_duplicated_points_count_once(self):
        point = self._point("AV X", 5, 1)
        self.assertEqual(self._detail(point, point), "AV X, 5 25001")

    def test_too_many_points_are_summarised_with_plus_n(self):
        points = [self._point("AVINGUDA DELS PAISOS CATALANS", n, n) for n in range(1, 60)]
        concept = append_sepa_invoice_detail(self.PREFIX, self._invoice(*points), "ca")
        self.assertLessEqual(len(concept), SEPA_USTRD_MAX_LENGTH)
        self.assertRegex(concept, r"PUNT SUBM\. AVINGUDA DELS PAISOS CATALANS 1, 2, 3.* \(\+\d+\)$")


class ConceptFieldsTests(SimpleTestCase):
    def _payment(self):
        water = SimpleNamespace()
        address = SimpleNamespace(
            street="CARRER MAJOR", street_number=12, postal_code="25001",
            floor=None, door=None, stair=None, building=None,
        )
        point = SimpleNamespace(pk=1, name="PS1", token="PS1", address=address)
        invoice = SimpleNamespace(
            serie_final="FC/1", origin=water, total_final=10.0, consumption=5.0, real_consumption=None,
            contract=SimpleNamespace(token="C-1", supply_point_default=point),
            readings=SimpleNamespace(all=lambda: []),
        )
        return SimpleNamespace(token="P1", commitment_deposit=None, invoice=invoice), water

    def _concept(self, fields):
        payment, water = self._payment()
        return build_payment_sepa_concept(payment, "ca", water, False, fields)

    def test_all_fields_by_default(self):
        self.assertEqual(
            self._concept(None),
            "AIGUA CONTRACTE C-1 FRA FC/1 IMPORT 10.00EUR CONSUM 5m3 PUNT SUBM. CARRER MAJOR, 12 25001",
        )

    def test_only_selected_fields_are_shown(self):
        self.assertEqual(self._concept(["contract", "amount"]), "AIGUA CONTRACTE C-1 IMPORT 10.00EUR")
        self.assertEqual(self._concept(["invoice", "consumption"]), "AIGUA FRA FC/1 CONSUM 5m3")

    def test_no_fields_leaves_only_the_base_text(self):
        self.assertEqual(self._concept([]), "AIGUA")

    def test_unknown_fields_are_ignored(self):
        self.assertEqual(normalize_concept_fields(["amount", "foo"]), {"amount"})


class SavedConceptFieldsTests(TestCase):
    def test_nothing_saved_means_all_fields(self):
        self.assertIsNone(get_saved_concept_fields())

    def test_saved_selection_is_global_and_keeps_concept_order(self):
        self.assertEqual(save_concept_fields(["amount", "contract", "foo"]), ["contract", "amount"])
        self.assertEqual(get_saved_concept_fields(), ["contract", "amount"])

    def test_saving_again_replaces_and_empty_selection_is_kept(self):
        save_concept_fields(["contract"])
        save_concept_fields([])
        self.assertEqual(get_saved_concept_fields(), [])
