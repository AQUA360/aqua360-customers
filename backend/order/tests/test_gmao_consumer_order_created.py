"""
Tests del consumer GMAO per a l'event inbound "order.created" (ACUSTOMERS-357).

Cobreix l'enrutat de process_message, els tres nivells de vinculació
(parent -> adreça -> orfe), la idempotència, el mapeig d'estat/due date,
el processament de reports reutilitzat, el guard _skip_publish del senyal
post_save i la presència de description al llistat.

L'import de order.services.consumer es fa de forma diferida (setUp): el
mòdul executa una consulta a ConfigProject a nivell de mòdul, i la
descoberta de testos passa abans de crear la base de dades de test.
"""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from coredata.models import Address, City, ConfigProject, Street, StreetNumber
from contract.models import Contract
from order.models import (
    Order,
    OrderPriority,
    OrderReason,
    OrderReport,
    OrderStatus,
    OrderType,
)
from service.models import SupplyPoint, SupplyPointStatus

User = get_user_model()


def order_created_payload(**overrides):
    payload = {
        "key": "order.created",
        "order_token": "O-GMAO-202610-001",
        "order_title": "Reparació extra de fuita",
        "order_description": "Detectada fuita secundària durant la inspecció.",
        "scheduled_at": "2026-10-19T14:00:00Z",
        "due_date": "2026-10-20T14:00:00Z",
        "parent_order_token": "O2026020001",
        "address": "Carrer Major 12, 08500 Vic",
        "status_id": 1,
        "status_token": "GM-init",
        "status_name": "Pendent",
        "reports": [],
    }
    payload.update(overrides)
    return payload


class GmaoOrderCreatedBaseTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        # Dependència del senyal post_save de Contract
        ConfigProject.objects.get_or_create(
            token="contract_terminated_status",
            defaults={"name": "Contract terminated status", "value": "contract_terminated"},
        )
        # Mapping carregat a l'importar order.services.consumer
        ConfigProject.objects.get_or_create(
            token="gmao_integration_order_status_mapping",
            defaults={
                "name": "GMAO order status mapping",
                "value": (
                    '{"pending":"1","in_progress":"5","completed":"5",'
                    '"finalized":"2","cancelled":"-1"}'
                ),
            },
        )
        cls.mapped_status = OrderStatus.objects.create(token="1", name="Pendent")
        cls.default_status = OrderStatus.objects.create(
            token="99", name="Per defecte", is_default=True
        )
        # Token de baixa per al filtre loose de SupplyPoint (consumer)
        ConfigProject.objects.get_or_create(
            token="supply_point_status_deactivate_token",
            defaults={"name": "Supply point deactivate status token", "value": "-1"},
        )
        cls.sp_active_status = SupplyPointStatus.objects.create(
            token="1", name="Actiu"
        )
        cls.sp_baixa_status = SupplyPointStatus.objects.create(
            token="-1", name="Baixa"
        )

    def setUp(self):
        # Import diferit: veure el docstring del mòdul
        from order.services import consumer

        self.consumer = consumer

    def make_address_fixture(self, street_name="Major", number=12, postal="08500", city_name="Vic"):
        city, _ = City.objects.get_or_create(token=f"CITY-{city_name}", defaults={"name": city_name})
        street, _ = Street.objects.get_or_create(city=city, name=street_name)
        street_number, _ = StreetNumber.objects.get_or_create(street=street, number=number)
        address = Address.objects.create(
            street=street,
            street_number=street_number,
            postal_code=postal,
            city_name=city_name,
        )
        return address


class ProcessMessageRoutingTest(GmaoOrderCreatedBaseTestCase):
    def test_routes_order_created_key(self):
        # Ordre ja existent -> la ruta respon amb la branca idempotent
        Order.objects.create(token="O-GMAO-202610-001")
        result = self.consumer.process_message(order_created_payload())
        self.assertTrue(result["success"])
        self.assertFalse(result["created"])
        self.assertTrue(result["idempotent"])

    def test_unknown_key_still_raises(self):
        with self.assertRaises(ValueError):
            self.consumer.process_message({"key": "unknown.event"})


class HandleOrderCreatedValidationTest(GmaoOrderCreatedBaseTestCase):
    def test_missing_order_token_raises(self):
        with self.assertRaises(ValueError):
            self.consumer.handle_order_created(order_created_payload(order_token=None))
        self.assertFalse(Order.objects.filter(token="O-GMAO-202610-001").exists())


class Tier1ParentLinkingTest(GmaoOrderCreatedBaseTestCase):
    def setUp(self):
        super().setUp()
        address = self.make_address_fixture()
        supply_point = SupplyPoint.objects.create(token="SP-PARENT", address=address)
        contract = Contract.objects.create(
            token="CTR-PARENT", supply_point_default=supply_point
        )
        self.parent = Order.objects.create(
            token="O2026020001",
            contract=contract,
            supply_point=supply_point,
            address=address,
            type=OrderType.objects.create(token="T-1", name="Tipus"),
            reason=OrderReason.objects.create(token="R-1", name="Motiu"),
            priority=OrderPriority.objects.create(token="PR-1", name="Alta"),
        )

    def test_links_and_inherits_from_parent(self):
        result = self.consumer.handle_order_created(order_created_payload())
        self.assertTrue(result["created"])
        self.assertEqual(result["linking_tier"], "parent")

        order = Order.objects.get(token="O-GMAO-202610-001")
        self.assertEqual(order.contract, self.parent.contract)
        self.assertEqual(order.supply_point, self.parent.supply_point)
        self.assertEqual(order.address, self.parent.address)
        self.assertEqual(order.type, self.parent.type)
        self.assertEqual(order.reason, self.parent.reason)
        self.assertEqual(order.priority, self.parent.priority)

    def test_field_mapping(self):
        self.consumer.handle_order_created(order_created_payload())
        order = Order.objects.get(token="O-GMAO-202610-001")

        # Token = identificador GMAO: els futurs order.status.changed hi mapen
        self.assertEqual(order.token, "O-GMAO-202610-001")
        self.assertEqual(order.dueDateAt.isoformat(), "2026-10-20")
        # status_token "GM-init" no està al mapping -> estat per defecte
        self.assertEqual(order.status, self.default_status)

        # Descripció: títol + cos + adreça crua de GMAO (sense flag)
        self.assertEqual(
            order.description,
            "Reparació extra de fuita\n\n"
            "Detectada fuita secundària durant la inspecció.\n\n"
            "Adreça GMAO: Carrer Major 12, 08500 Vic",
        )
        self.assertNotIn("[REVISIÓ MANUAL]", order.description)

    def test_mapped_status_token(self):
        self.consumer.handle_order_created(order_created_payload(status_token="pending"))
        order = Order.objects.get(token="O-GMAO-202610-001")
        self.assertEqual(order.status, self.mapped_status)

    def test_invalid_due_date_is_ignored(self):
        self.consumer.handle_order_created(
            order_created_payload(due_date="not-a-date")
        )
        order = Order.objects.get(token="O-GMAO-202610-001")
        self.assertIsNone(order.dueDateAt)


class Tier2AddressLinkingTest(GmaoOrderCreatedBaseTestCase):
    def test_links_by_address_when_parent_unknown(self):
        address = self.make_address_fixture()
        supply_point = SupplyPoint.objects.create(token="SP-ADDR", address=address)
        contract = Contract.objects.create(
            token="CTR-ADDR", supply_point_default=supply_point
        )

        result = self.consumer.handle_order_created(
            order_created_payload(parent_order_token="PARENT-THAT-DOES-NOT-EXIST")
        )
        self.assertTrue(result["created"])
        self.assertEqual(result["linking_tier"], "address")

        order = Order.objects.get(token="O-GMAO-202610-001")
        self.assertEqual(order.supply_point, supply_point)
        self.assertEqual(order.address, address)
        self.assertEqual(order.contract, contract)
        self.assertNotIn("[REVISIÓ MANUAL]", order.description)

    def test_ambiguous_address_creates_orphan(self):
        # Dues adreces idèntiques (mateix carrer/numero/codi) -> SP ambigu
        first = self.make_address_fixture()
        second = self.make_address_fixture()
        SupplyPoint.objects.create(token="SP-AMB-1", address=first)
        SupplyPoint.objects.create(token="SP-AMB-2", address=second)

        result = self.consumer.handle_order_created(
            order_created_payload(parent_order_token=None)
        )
        self.assertTrue(result["created"])
        self.assertEqual(result["linking_tier"], "orphan")
        # Dues adreces coincidents -> l'adreça també és ambiguïtat
        order = Order.objects.get(token="O-GMAO-202610-001")
        self.assertIsNone(order.address)

    def test_deactivated_supply_point_is_excluded(self):
        address = self.make_address_fixture()
        SupplyPoint.objects.create(
            token="SP-BAIXA", address=address, status=self.sp_baixa_status
        )
        active_sp = SupplyPoint.objects.create(
            token="SP-ACTIVA", address=address, status=self.sp_active_status
        )

        result = self.consumer.handle_order_created(
            order_created_payload(parent_order_token=None)
        )
        self.assertEqual(result["linking_tier"], "address")

        order = Order.objects.get(token="O-GMAO-202610-001")
        self.assertEqual(order.supply_point, active_sp)
        self.assertEqual(order.address, address)

    def test_strict_number_excludes_other_numbers_on_same_street(self):
        addr12 = self.make_address_fixture(street_name="Major", number=12)
        addr13 = self.make_address_fixture(street_name="Major", number=13)
        sp12 = SupplyPoint.objects.create(
            token="SP-12", address=addr12, status=self.sp_active_status
        )
        SupplyPoint.objects.create(
            token="SP-13", address=addr13, status=self.sp_active_status
        )

        result = self.consumer.handle_order_created(
            order_created_payload(parent_order_token=None)
        )
        self.assertEqual(result["linking_tier"], "address")

        order = Order.objects.get(token="O-GMAO-202610-001")
        self.assertEqual(order.supply_point, sp12)
        self.assertEqual(order.address, addr12)


class Tier3OrphanOrderTest(GmaoOrderCreatedBaseTestCase):
    def test_creates_orphan_without_raising(self):
        result = self.consumer.handle_order_created(
            order_created_payload(parent_order_token=None, address="Sense adreça interpretable")
        )
        self.assertTrue(result["created"])
        self.assertEqual(result["linking_tier"], "orphan")

        order = Order.objects.get(token="O-GMAO-202610-001")
        self.assertIsNone(order.contract)
        self.assertIsNone(order.supply_point)
        self.assertIsNone(order.address)
        self.assertIsNone(order.type)
        self.assertEqual(order.status, self.default_status)

    def test_description_carries_manual_review_flags(self):
        self.consumer.handle_order_created(
            order_created_payload(parent_order_token=None)
        )
        order = Order.objects.get(token="O-GMAO-202610-001")

        # 1) Flag al títol, primera línia
        self.assertTrue(
            order.description.startswith(
                "[REVISIÓ MANUAL] Reparació extra de fuita"
            ),
            order.description,
        )
        # 2) Nota amb l'adreça crua del GMAO
        self.assertIn(
            "ATENCIÓ: Ordre òrfena pendent de vincular a un Punt de Subministrament "
            "o Contracte. Adreça proporcionada pel GMAO: Carrer Major 12, 08500 Vic",
            order.description,
        )
        # Cos de l'ordre present
        self.assertIn("Detectada fuita secundària durant la inspecció.", order.description)

    def test_orphan_note_without_address_shows_cap(self):
        self.consumer.handle_order_created(
            order_created_payload(parent_order_token=None, address="")
        )
        order = Order.objects.get(token="O-GMAO-202610-001")
        self.assertIn("Adreça proporcionada pel GMAO: cap", order.description)

    def test_titleless_orphan_still_flagged(self):
        self.consumer.handle_order_created(
            order_created_payload(parent_order_token=None, order_title="")
        )
        order = Order.objects.get(token="O-GMAO-202610-001")
        self.assertTrue(order.description.startswith("[REVISIÓ MANUAL]\nATENCIÓ:"))

    def test_orphan_keeps_unique_address_when_supply_points_ambiguous(self):
        # Única adreça amb dos SP actius -> orfe però amb adreça vinculada
        address = self.make_address_fixture()
        SupplyPoint.objects.create(
            token="SP-DUP-1", address=address, status=self.sp_active_status
        )
        SupplyPoint.objects.create(
            token="SP-DUP-2", address=address, status=self.sp_active_status
        )

        result = self.consumer.handle_order_created(
            order_created_payload(parent_order_token=None)
        )
        self.assertEqual(result["linking_tier"], "orphan")

        order = Order.objects.get(token="O-GMAO-202610-001")
        self.assertIsNone(order.supply_point)
        self.assertIsNone(order.contract)
        self.assertEqual(order.address, address)
        self.assertTrue(
            order.description.startswith("[REVISIÓ MANUAL]"), order.description
        )

    def test_orphan_without_address_match_creates_no_address(self):
        before = Address.objects.count()

        result = self.consumer.handle_order_created(
            order_created_payload(parent_order_token=None, address="Via Inexistent 99")
        )
        self.assertEqual(result["linking_tier"], "orphan")

        order = Order.objects.get(token="O-GMAO-202610-001")
        self.assertIsNone(order.supply_point)
        self.assertIsNone(order.address)
        self.assertEqual(Address.objects.count(), before)


class IdempotencyTest(GmaoOrderCreatedBaseTestCase):
    def test_redelivery_does_not_duplicate(self):
        first = self.consumer.handle_order_created(order_created_payload())
        second = self.consumer.handle_order_created(order_created_payload())

        self.assertTrue(first["created"])
        self.assertFalse(second["created"])
        self.assertTrue(second["idempotent"])
        self.assertEqual(
            Order.objects.filter(token="O-GMAO-202610-001").count(), 1
        )

    def test_redelivery_skips_reports(self):
        report = {
            "start_at": "2026-02-09T11:10:41.638000+00:00",
            "end_at": "2026-02-09T13:10:00+00:00",
            "description": "Intervenció",
            "username": "operator1",
            "user_first_name": "John",
            "user_last_name": "Doe",
            "photos": [],
            "form_submission": [],
        }
        self.consumer.handle_order_created(order_created_payload(reports=[report]))
        self.consumer.handle_order_created(order_created_payload(reports=[report]))
        self.assertEqual(OrderReport.objects.count(), 1)


class ReportsProcessingTest(GmaoOrderCreatedBaseTestCase):
    def test_reports_reuse_existing_parser(self):
        report = {
            "start_at": "2026-02-09T11:10:41.638000+00:00",
            "end_at": "2026-02-09T13:10:00+00:00",
            "description": "Intervenció",
            "username": "operator1",
            "user_first_name": "John",
            "user_last_name": "Doe",
            "photos": [],
            "form_submission": [],
        }
        result = self.consumer.handle_order_created(order_created_payload(reports=[report]))
        self.assertEqual(result["reports_processed"], 1)

        order = Order.objects.get(token="O-GMAO-202610-001")
        report_obj = OrderReport.objects.get()
        self.assertEqual(report_obj.order, order)


@override_settings(RABBITMQ_ENABLED=True)
class SkipPublishSignalTest(GmaoOrderCreatedBaseTestCase):
    def test_gmao_created_order_is_not_echoed(self):
        with patch("order.services.rabbit.publish_order_created") as mock_publish:
            with self.captureOnCommitCallbacks(execute=True):
                self.consumer.handle_order_created(order_created_payload())
        mock_publish.assert_not_called()

    def test_normal_creation_still_publishes(self):
        with patch("order.services.rabbit.publish_order_created") as mock_publish:
            with self.captureOnCommitCallbacks(execute=True):
                Order.objects.create(token="ORD-NORMAL")
        mock_publish.assert_called_once()


class OrderListSerializerDescriptionTest(GmaoOrderCreatedBaseTestCase):
    def test_list_serializer_includes_description(self):
        from order.serializers.order_serializer import OrderListSerializer

        order = Order.objects.create(
            token="ORD-LIST", description="Descripció de llistat"
        )
        data = OrderListSerializer(order).data
        self.assertEqual(data["description"], "Descripció de llistat")


class AddressParsingTest(TestCase):
    def parse(self, raw):
        from order.services import consumer

        return consumer._parse_address_text(raw)

    def test_parses_gmao_sample_address(self):
        parsed = self.parse("Carrer Major 12, 08500 Vic")
        self.assertEqual(parsed["street_name"], "Major")
        self.assertEqual(parsed["number"], 12)
        self.assertEqual(parsed["postal_code"], "08500")
        self.assertEqual(parsed["city_name"], "Vic")

    def test_parses_without_postal_code(self):
        parsed = self.parse("Carrer Major 12")
        self.assertEqual(parsed["street_name"], "Major")
        self.assertEqual(parsed["number"], 12)
        self.assertIsNone(parsed["postal_code"])
        self.assertIsNone(parsed["city_name"])

    def test_parses_street_name_only(self):
        parsed = self.parse("Avinguda Pau Casals")
        self.assertEqual(parsed["street_name"], "Pau Casals")
        self.assertIsNone(parsed["number"])

    def test_parses_number_after_comma(self):
        # Cas real GMAO: el número va en un segment posterior a la coma
        parsed = self.parse("C. MAJOR, 75")
        self.assertEqual(parsed["street_name"], "MAJOR")
        self.assertEqual(parsed["number"], 75)
        self.assertIsNone(parsed["postal_code"])
        self.assertIsNone(parsed["city_name"])

    def test_parses_number_and_postal_after_comma(self):
        parsed = self.parse("C. MAJOR, 75, 08500 Vic")
        self.assertEqual(parsed["street_name"], "MAJOR")
        self.assertEqual(parsed["number"], 75)
        self.assertEqual(parsed["postal_code"], "08500")
        self.assertEqual(parsed["city_name"], "Vic")

    def test_empty_address(self):
        parsed = self.parse("")
        self.assertIsNone(parsed["street_name"])
        self.assertIsNone(parsed["number"])
        self.assertIsNone(parsed["postal_code"])
        self.assertIsNone(parsed["city_name"])


class CreatorSystemUserTest(GmaoOrderCreatedBaseTestCase):
    def test_created_by_gmao_system_user(self):
        self.consumer.handle_order_created(order_created_payload())
        order = Order.objects.get(token="O-GMAO-202610-001")

        user = order.created_by
        self.assertIsNotNone(user)
        self.assertEqual(user.username, "GMAO")
        self.assertFalse(user.has_usable_password())
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)

    def test_gmao_user_is_reused_across_orders(self):
        self.consumer.handle_order_created(order_created_payload())
        self.consumer.handle_order_created(
            order_created_payload(order_token="O-GMAO-202610-002")
        )

        self.assertEqual(User.objects.filter(username="GMAO").count(), 1)
        first = Order.objects.get(token="O-GMAO-202610-001")
        second = Order.objects.get(token="O-GMAO-202610-002")
        self.assertEqual(first.created_by, second.created_by)
