"""
Tests de la construcció del payload de l'event RabbitMQ "order.created"
(order/services/rabbit.py).

Es centra en les dues dades noves per a la GMAO:
  - exploitation_token (camp arrel del payload)
  - last_reading_value / last_reading_date / last_reading_consumption (additional_info)

publish_event queda sempre patchejat: cap test ha d'arribar a un broker real.
"""
import datetime
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase

from billing.models import Reading
from contract.models import Contract
from coredata.models import ConfigProject
from order.models import Order
from order.services.rabbit import (
    _format_decimal,
    _get_last_reading_info,
    _resolve_exploitation_token,
    _resolve_order_supply_point,
    publish_order_created,
)
from service.models import Connection, ConnectionRequest, Exploitation, Meter, SupplyPoint


class RabbitPublishTestCase(TestCase):
    """
    Base dels tests d'aquest mòdul.

    El post_save de Contract (contract/signals.py) fa
    ConfigProject.objects.get(token='contract_terminated_status') de forma
    incondicional, així que sense aquesta fila no es pot crear cap Contract
    en un banc de proves buit. No és un problema del codi que es prova: és una
    dependència del senyal que la base de dades de proves no porta.
    """

    @classmethod
    def setUpTestData(cls):
        ConfigProject.objects.get_or_create(
            token="contract_terminated_status",
            defaults={
                "name": "Contract terminated status",
                "value": "contract_terminated",
            },
        )


def make_exploitation(token):
    return Exploitation.objects.create(token=token, name=token)


def make_connection(exploitation=None, token="CON-1"):
    return Connection.objects.create(token=token, exploitation=exploitation)


def make_meter(token="MET-1", code="MTR-1"):
    return Meter.objects.create(token=token, code=code)


def make_supply_point(connection=None, meter=None, token="SP-1"):
    return SupplyPoint.objects.create(token=token, connection=connection, meter=meter)


def make_contract(supply_point_default=None, token="CTR-1"):
    return Contract.objects.create(token=token, supply_point_default=supply_point_default)


def make_connection_request(exploitation=None, token="CR-1"):
    return ConnectionRequest.objects.create(token=token, exploitation=exploitation)


def make_order(**kwargs):
    kwargs.setdefault("token", "ORD-1")
    return Order.objects.create(**kwargs)


def make_reading(
    supply_point,
    meter,
    reading_date,
    reading_value=None,
    real_consumption=None,
    calculated_value=None,
    is_estimated=False,
    is_active=True,
    copied_from=None,
):
    return Reading.objects.create(
        supply_point=supply_point,
        meter=meter,
        reading_date=reading_date,
        reading_value=reading_value,
        real_consumption=real_consumption,
        calculated_value=calculated_value,
        is_estimated=is_estimated,
        is_active=is_active,
        copied_from=copied_from,
    )


def additional_info_of(payload, key):
    """Torna el 'text' de la entrada 'key' de l'array additional_info."""
    for entry in payload["additional_info"]:
        if entry["key"] == key:
            return entry["text"]
    raise AssertionError(f"'{key}' no existeix al additional_info del payload")


class FormatDecimalTest(RabbitPublishTestCase):
    def test_strips_trailing_zeros(self):
        self.assertEqual(_format_decimal(Decimal("1000.00")), "1000")
        self.assertEqual(_format_decimal(Decimal("25.50")), "25.5")
        self.assertEqual(_format_decimal(Decimal("0.00")), "0")

    def test_keeps_significant_decimals(self):
        self.assertEqual(_format_decimal(Decimal("1234.56")), "1234.56")

    def test_none_stays_none(self):
        self.assertIsNone(_format_decimal(None))

    def test_does_not_strip_zeros_of_whole_numbers(self):
        # El guard sobre "." evita que 1000 -> "1"
        self.assertEqual(_format_decimal(Decimal("1000")), "1000")
        self.assertEqual(_format_decimal(Decimal("200")), "200")


class ResolveOrderSupplyPointTest(RabbitPublishTestCase):
    def test_prefers_the_order_supply_point(self):
        order_sp = make_supply_point(token="SP-ORDER")
        contract_sp = make_supply_point(token="SP-CONTRACT")
        order = make_order(supply_point=order_sp, contract=make_contract(contract_sp))

        self.assertEqual(_resolve_order_supply_point(order), order_sp)

    def test_falls_back_to_the_contract_supply_point(self):
        contract_sp = make_supply_point(token="SP-CONTRACT")
        order = make_order(contract=make_contract(contract_sp))

        self.assertEqual(_resolve_order_supply_point(order), contract_sp)

    def test_returns_none_without_supply_point_or_contract(self):
        self.assertIsNone(_resolve_order_supply_point(make_order()))

    def test_returns_none_when_contract_has_no_supply_point(self):
        self.assertIsNone(_resolve_order_supply_point(make_order(contract=make_contract())))


class ResolveExploitationTokenTest(RabbitPublishTestCase):
    def test_via_order_supply_point_connection(self):
        exploitation = make_exploitation("EXP-SP")
        order = make_order(
            supply_point=make_supply_point(connection=make_connection(exploitation))
        )

        self.assertEqual(_resolve_exploitation_token(order), "EXP-SP")

    def test_via_contract_supply_point_when_order_has_none(self):
        exploitation = make_exploitation("EXP-CTR")
        contract_sp = make_supply_point(connection=make_connection(exploitation))
        order = make_order(contract=make_contract(contract_sp))

        self.assertEqual(_resolve_exploitation_token(order), "EXP-CTR")

    def test_contract_is_used_even_when_order_supply_point_has_no_connection(self):
        # L'SP de l'ordre existeix però no té Connection: ha de provar el del contracte.
        exploitation = make_exploitation("EXP-CTR")
        contract_sp = make_supply_point(connection=make_connection(exploitation))
        order = make_order(
            supply_point=make_supply_point(connection=None),
            contract=make_contract(contract_sp),
        )

        self.assertEqual(_resolve_exploitation_token(order), "EXP-CTR")

    def test_via_order_connection(self):
        exploitation = make_exploitation("EXP-CON")
        order = make_order(connection=make_connection(exploitation))

        self.assertEqual(_resolve_exploitation_token(order), "EXP-CON")

    def test_via_connection_request(self):
        exploitation = make_exploitation("EXP-CR")
        order = make_order(connection_request=make_connection_request(exploitation))

        self.assertEqual(_resolve_exploitation_token(order), "EXP-CR")

    def test_order_supply_point_wins_over_contract(self):
        order_sp_exploitation = make_exploitation("EXP-ORDER-SP")
        order = make_order(
            supply_point=make_supply_point(
                connection=make_connection(order_sp_exploitation, token="CON-A")
            ),
            contract=make_contract(
                make_supply_point(
                    connection=make_connection(make_exploitation("EXP-CTR-SP"), token="CON-B")
                )
            ),
        )

        self.assertEqual(_resolve_exploitation_token(order), "EXP-ORDER-SP")

    def test_order_connection_wins_over_connection_request(self):
        order = make_order(
            connection=make_connection(make_exploitation("EXP-CON")),
            connection_request=make_connection_request(
                make_exploitation("EXP-CR"), token="CR-2"
            ),
        )

        self.assertEqual(_resolve_exploitation_token(order), "EXP-CON")

    def test_blank_token_falls_through_to_the_next_candidate(self):
        exploitation = make_exploitation(None)
        exploitation.token = ""
        exploitation.save()
        order = make_order(
            connection=make_connection(exploitation, token="CON-BLANK"),
            connection_request=make_connection_request(
                make_exploitation("EXP-CR"), token="CR-BLANK-FALLBACK"
            ),
        )

        self.assertEqual(_resolve_exploitation_token(order), "EXP-CR")

    def test_returns_none_when_nothing_resolves(self):
        self.assertIsNone(_resolve_exploitation_token(make_order()))

    def test_returns_none_without_address_or_coordinates_path(self):
        # Un order només amb address/coordenades no es pot resoldre: no s'ha de fer
        # cap consulta geoespacial.
        order = make_order(latitude=Decimal("41.12345678901234"),
                           longitude=Decimal("2.12345678901234"))
        self.assertIsNone(_resolve_exploitation_token(order))

    def test_query_count_is_bounded_on_a_freshly_fetched_order(self):
        # Els FK es comproven abans de travessar-los, de manera que una relació
        # nul·la no genera cap consulta i el recorregut queda acotat i conegut.
        exploitation = make_exploitation("EXP-Q")
        supply_point = make_supply_point(
            connection=make_connection(exploitation, token="CON-Q")
        )
        order = make_order(supply_point=supply_point)

        # Es torna a carregar l'ordre perquè quedi sense cap relació a la cache,
        # igual que quan arriba des del post_save.
        fresh_order = Order.objects.filter(pk=order.pk).first()

        with self.assertNumQueries(3):  # SupplyPoint + Connection + Exploitation
            self.assertEqual(_resolve_exploitation_token(fresh_order), "EXP-Q")

    def test_query_count_is_zero_when_relations_are_already_cached(self):
        exploitation = make_exploitation("EXP-QC")
        supply_point = make_supply_point(
            connection=make_connection(exploitation, token="CON-QC")
        )
        order = make_order(supply_point=supply_point)

        with self.assertNumQueries(0):
            self.assertEqual(_resolve_exploitation_token(order), "EXP-QC")

    def test_query_count_is_zero_when_nothing_is_set(self):
        order = Order.objects.filter(pk=make_order().pk).first()

        with self.assertNumQueries(0):
            self.assertIsNone(_resolve_exploitation_token(order))


class GetLastReadingInfoTest(RabbitPublishTestCase):
    def setUp(self):
        self.meter = make_meter()
        self.supply_point = make_supply_point(meter=self.meter)

    def test_returns_the_latest_real_reading(self):
        make_reading(
            self.supply_point, self.meter, datetime.date(2026, 9, 1),
            reading_value=Decimal("900"), real_consumption=Decimal("20"), calculated_value=Decimal("20"),
        )
        make_reading(
            self.supply_point, self.meter, datetime.date(2026, 10, 1),
            reading_value=Decimal("1000.00"), real_consumption=Decimal("25.00"), calculated_value=Decimal("25.00"),
        )

        info = _get_last_reading_info(self.supply_point)

        self.assertEqual(info["value"], "1000")
        self.assertEqual(info["date"], "2026-10-01")
        self.assertEqual(info["consumption"], "25m3")

    def test_skips_estimated_readings(self):
        make_reading(
            self.supply_point, self.meter, datetime.date(2026, 9, 1),
            reading_value=Decimal("900"), real_consumption=Decimal("20"), calculated_value=Decimal("20"),
        )
        # Més recent però estimada: s'ha d'ometre.
        make_reading(
            self.supply_point, self.meter, datetime.date(2026, 10, 1),
            reading_value=Decimal("1000"), real_consumption=Decimal("25"), calculated_value=Decimal("25"),
            is_estimated=True,
        )

        info = _get_last_reading_info(self.supply_point)

        self.assertEqual(info["value"], "900")
        self.assertEqual(info["date"], "2026-09-01")
        self.assertEqual(info["consumption"], "20m3")

    def test_ignores_inactive_readings(self):
        make_reading(
            self.supply_point, self.meter, datetime.date(2026, 9, 1),
            reading_value=Decimal("900"), real_consumption=Decimal("20"), calculated_value=Decimal("20"),
        )
        make_reading(
            self.supply_point, self.meter, datetime.date(2026, 10, 1),
            reading_value=Decimal("1000"), real_consumption=Decimal("25"), calculated_value=Decimal("25"),
            is_active=False,
        )

        info = _get_last_reading_info(self.supply_point)

        self.assertEqual(info["date"], "2026-09-01")

    def test_ignores_readings_of_another_meter(self):
        other_meter = make_meter(token="MET-2", code="MTR-2")
        make_reading(
            self.supply_point, other_meter, datetime.date(2026, 10, 1),
            reading_value=Decimal("1000"), real_consumption=Decimal("25"), calculated_value=Decimal("25"),
        )

        info = _get_last_reading_info(self.supply_point)

        self.assertEqual(info["value"], None)
        self.assertEqual(info["date"], None)
        self.assertEqual(info["consumption"], None)

    def test_ignores_copied_readings(self):
        # El fanout de comptadors generals crea còopies de la lectura física
        # (copied_from). Al camp ens interessa la física, no la còpia.
        physical = make_reading(
            self.supply_point, self.meter, datetime.date(2026, 10, 1),
            reading_value=Decimal("1000"), real_consumption=Decimal("25"), calculated_value=Decimal("25"),
        )
        make_reading(
            self.supply_point, self.meter, datetime.date(2026, 10, 1),
            reading_value=Decimal("999"), real_consumption=Decimal("99"), calculated_value=Decimal("99"),
            copied_from=physical,
        )

        info = _get_last_reading_info(self.supply_point)

        self.assertEqual(info["value"], "1000")
        self.assertEqual(info["consumption"], "25m3")

    def test_returns_the_physical_reading_when_only_a_copy_exists(self):
        physical = make_reading(
            self.supply_point, self.meter, datetime.date(2026, 10, 1),
            reading_value=Decimal("1000"), real_consumption=Decimal("25"), calculated_value=Decimal("25"),
        )
        # La còpia té data posterior: si no es filtrés, guanyaria ella.
        make_reading(
            self.supply_point, self.meter, datetime.date(2026, 11, 1),
            reading_value=Decimal("1500"), real_consumption=Decimal("500"), calculated_value=Decimal("500"),
            copied_from=physical,
        )

        info = _get_last_reading_info(self.supply_point)

        self.assertEqual(info["value"], "1000")
        self.assertEqual(info["date"], "2026-10-01")
        self.assertEqual(info["consumption"], "25m3")

    def test_tiebreaks_on_same_date_with_the_newest_record(self):
        # Sense el desempata -id, dues lectures amb la mateixa data es quedaven
        # amb una fila arbitrària.
        make_reading(
            self.supply_point, self.meter, datetime.date(2026, 10, 1),
            reading_value=Decimal("900"), real_consumption=Decimal("20"), calculated_value=Decimal("20"),
        )
        make_reading(
            self.supply_point, self.meter, datetime.date(2026, 10, 1),
            reading_value=Decimal("1000"), real_consumption=Decimal("25"), calculated_value=Decimal("25"),
        )

        info = _get_last_reading_info(self.supply_point)

        self.assertEqual(info["value"], "1000")
        self.assertEqual(info["date"], "2026-10-01")
        self.assertEqual(info["consumption"], "25m3")

    def test_consumption_uses_calculated_value_not_real_consumption(self):
        # Els dos camps es posen a valors diferents a propòsit: si algú torna a
        # posar real_consumption, aquest test falla.
        make_reading(
            self.supply_point, self.meter, datetime.date(2026, 10, 1),
            reading_value=Decimal("1000"),
            real_consumption=Decimal("99"),
            calculated_value=Decimal("25.00"),
        )

        info = _get_last_reading_info(self.supply_point)

        self.assertEqual(info["value"], "1000")
        self.assertEqual(info["date"], "2026-10-01")
        self.assertEqual(info["consumption"], "25m3")

    def test_consumption_is_none_but_value_and_date_are_kept(self):
        # Les tres claus no són atòmiques: sense calculated_value, el consum és
        # null malgrat que hi hagi valor i data. Tampoc no es cau a
        # real_consumption.
        make_reading(
            self.supply_point, self.meter, datetime.date(2026, 10, 1),
            reading_value=Decimal("1000"),
            real_consumption=Decimal("99"),
            calculated_value=None,
        )

        info = _get_last_reading_info(self.supply_point)

        self.assertEqual(info["value"], "1000")
        self.assertEqual(info["date"], "2026-10-01")
        self.assertIsNone(info["consumption"])

    def test_zero_calculated_value_is_reported_as_zero_not_null(self):
        # Una lectura inicial sense previous_reading es crea amb calculated_value=0
        # (billing/tasks.py), de manera que la GMAO rep "0m3" i no null. Cal
        # distingir "zero consum" de "consum desconegut".
        make_reading(
            self.supply_point, self.meter, datetime.date(2026, 10, 1),
            reading_value=Decimal("1000"),
            calculated_value=Decimal("0"),
        )

        info = _get_last_reading_info(self.supply_point)

        self.assertEqual(info["consumption"], "0m3")

    def test_returns_none_without_meter(self):
        supply_point_without_meter = make_supply_point(token="SP-NO-METER")
        make_reading(
            supply_point_without_meter, self.meter, datetime.date(2026, 10, 1),
            reading_value=Decimal("1000"), real_consumption=Decimal("25"), calculated_value=Decimal("25"),
        )

        info = _get_last_reading_info(supply_point_without_meter)

        self.assertEqual(info, {"value": None, "date": None, "consumption": None})

    def test_returns_none_without_supply_point(self):
        self.assertEqual(
            _get_last_reading_info(None),
            {"value": None, "date": None, "consumption": None},
        )

    def test_returns_none_without_any_reading(self):
        info = _get_last_reading_info(self.supply_point)

        self.assertEqual(info, {"value": None, "date": None, "consumption": None})

    def test_date_is_formatted_as_iso_day(self):
        make_reading(
            self.supply_point, self.meter, datetime.date(2026, 1, 5),
            reading_value=Decimal("10"), real_consumption=Decimal("1"),
        )

        info = _get_last_reading_info(self.supply_point)

        self.assertEqual(info["date"], "2026-01-05")
        self.assertNotIn("T", info["date"])
        self.assertNotIn("+", info["date"])

    def test_database_error_is_swallowed(self):
        from django.db import DatabaseError

        with patch(
            "order.services.rabbit.Reading.objects.filter",
            side_effect=DatabaseError("connection dropped"),
        ):
            info = _get_last_reading_info(self.supply_point)

        self.assertEqual(info, {"value": None, "date": None, "consumption": None})

    def test_programming_errors_are_not_swallowed(self):
        from django.core.exceptions import FieldError

        with patch(
            "order.services.rabbit.Reading.objects.filter",
            side_effect=FieldError("Unknown field"),
        ):
            with self.assertRaises(FieldError):
                _get_last_reading_info(self.supply_point)

    def test_uses_a_single_query(self):
        # Una sola consulta de lectures: el filtre per supply_point i meter
        # resol l'última lectura directament de l'index
        # reading_prev_no_contract_idx, sense lectures per lloatre.
        make_reading(
            self.supply_point, self.meter, datetime.date(2026, 10, 1),
            reading_value=Decimal("1000"), real_consumption=Decimal("25"), calculated_value=Decimal("25"),
        )
        # Es torna a carregar el SP i el comptador sense cache, com a l'event real.
        supply_point = SupplyPoint.objects.filter(pk=self.supply_point.pk).first()

        with self.assertNumQueries(2):  # meter + lectura
            info = _get_last_reading_info(supply_point)

        self.assertEqual(info["date"], "2026-10-01")

    def test_uses_no_query_without_meter(self):
        supply_point_without_meter = SupplyPoint.objects.filter(
            pk=make_supply_point(token="SP-NO-METER-Q").pk
        ).first()

        with self.assertNumQueries(0):
            self.assertEqual(
                _get_last_reading_info(supply_point_without_meter),
                {"value": None, "date": None, "consumption": None},
            )


class PublishOrderCreatedPayloadTest(RabbitPublishTestCase):
    def setUp(self):
        self.exploitation = make_exploitation("EXP-1")
        self.meter = make_meter()
        self.supply_point = make_supply_point(
            connection=make_connection(self.exploitation), meter=self.meter
        )

    def _publish(self, order):
        with patch("order.services.rabbit.publish_event") as publish_event:
            publish_order_created(order)
        publish_event.assert_called_once()
        key, payload = publish_event.call_args[0]
        self.assertEqual(key, "order.created")
        return payload

    def test_payload_has_exploitation_token_at_root_level(self):
        order = make_order(supply_point=self.supply_point)

        payload = self._publish(order)

        self.assertEqual(payload["exploitation_token"], "EXP-1")

    def test_payload_exploitation_token_is_none_when_unresolvable(self):
        order = make_order()

        payload = self._publish(order)

        self.assertIn("exploitation_token", payload)
        self.assertIsNone(payload["exploitation_token"])

    def test_payload_contains_the_three_last_reading_entries(self):
        make_reading(
            self.supply_point, self.meter, datetime.date(2026, 10, 1),
            reading_value=Decimal("1000.00"), real_consumption=Decimal("25.00"), calculated_value=Decimal("25.00"),
        )
        order = make_order(supply_point=self.supply_point)

        payload = self._publish(order)

        self.assertEqual(additional_info_of(payload, "last_reading_value"), "1000")
        self.assertEqual(additional_info_of(payload, "last_reading_date"), "2026-10-01")
        self.assertEqual(additional_info_of(payload, "last_reading_consumption"), "25m3")

    def test_payload_last_reading_keys_always_present_with_none(self):
        order = make_order(supply_point=self.supply_point)

        payload = self._publish(order)

        for key in (
            "last_reading_value",
            "last_reading_date",
            "last_reading_consumption",
        ):
            self.assertIsNone(additional_info_of(payload, key))

    def test_payload_is_json_serializable(self):
        import json

        make_reading(
            self.supply_point, self.meter, datetime.date(2026, 10, 1),
            reading_value=Decimal("1000.00"), real_consumption=Decimal("25.00"), calculated_value=Decimal("25.00"),
        )
        order = make_order(supply_point=self.supply_point)

        payload = self._publish(order)

        # default=str és el que fa servir publish_event
        json.dumps(payload, ensure_ascii=False, indent=2, default=str)

    def test_payload_reading_uses_the_contract_supply_point(self):
        contract_sp = make_supply_point(
            connection=make_connection(self.exploitation, token="CON-CTR"),
            meter=make_meter(token="MET-CTR", code="MTR-CTR"),
            token="SP-CTR",
        )
        make_reading(
            contract_sp, contract_sp.meter, datetime.date(2026, 9, 15),
            reading_value=Decimal("500"), real_consumption=Decimal("12"), calculated_value=Decimal("12"),
        )
        order = make_order(contract=make_contract(contract_sp))

        payload = self._publish(order)

        self.assertEqual(payload["exploitation_token"], "EXP-1")
        self.assertEqual(additional_info_of(payload, "last_reading_value"), "500")
        self.assertEqual(additional_info_of(payload, "last_reading_date"), "2026-09-15")
        self.assertEqual(additional_info_of(payload, "last_reading_consumption"), "12m3")
