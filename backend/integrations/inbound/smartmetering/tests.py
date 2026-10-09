from datetime import date

from django.contrib.auth.models import Group, User
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from contract.models import Contract, ContractStatus, ContractUseType
from coredata.models import Address, City, ConfigProject, Person, Street
from integrations.models import IntegrationRequestLog
from service.models import Connection, DMA, Exploitation, Meter, SupplyPoint


class SmartMeteringInboundAuthMixin:
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username="smartmetering-client", password="secret")
        self.smartmetering_group, _ = Group.objects.get_or_create(name="smartmetering")
        self.user.groups.add(self.smartmetering_group)
        self.token = Token.objects.create(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")


class SmartMeteringInboundContractsViewTest(SmartMeteringInboundAuthMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.url = reverse("smartmetering-inbound-contracts")

        self.active_status = ContractStatus.objects.create(token="1", name="Actiu")
        ConfigProject.objects.create(token="contract_active_token", value="1")
        ConfigProject.objects.create(token="contract_terminated_status", value="-1")

        self.holder = Person.objects.create(
            token="12345678A",
            name="Anna",
            surname="Garcia",
        )
        self.exploitation = Exploitation.objects.create(token="EXP-01", name="Exploitation 1")
        self.dma = DMA.objects.create(token="DMA-01", name="DMA 1")
        self.connection = Connection.objects.create(
            token="CONN-001",
            exploitation=self.exploitation,
            dma=self.dma,
        )
        self.street = Street.objects.create(name="Barcelona")
        self.city = City.objects.create(token="CITY-TEST", name="Població")
        self.address = Address.objects.create(
            street=self.street,
            city=self.city,
            postal_code="08110",
        )
        self.meter = Meter.objects.create(
            code="MTR-001",
            installation_at=date(2024, 3, 15),
            comm_module="MOD-99",
            comm_technology="NB-IoT",
            manufacturer="Elster",
            model="A1700",
            network_provider="Vodafone",
        )
        self.supply_point = SupplyPoint.objects.create(
            token="SP-001",
            connection=self.connection,
            address=self.address,
            meter=self.meter,
            cadastral="08001A00010001",
        )
        self.use_type = ContractUseType.objects.create(token="DOM", name="Domèstica")
        self.contract = Contract.objects.create(
            token="CTR-001",
            holder=self.holder,
            supply_point_default=self.supply_point,
            status=self.active_status,
            use_type=self.use_type,
        )

    def test_contracts_rejects_unauthenticated(self):
        client = APIClient()
        response = client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_contracts_returns_view_shaped_payload(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

        item = response.data[0]
        self.address.refresh_from_db()
        self.assertEqual(item["policy"], "CTR-001")
        self.assertEqual(item["meter"], "MTR-001")
        self.assertEqual(item["rate"], "Domèstica")
        self.assertEqual(item["service_point"], self.address.address_search)
        self.assertEqual(item["inst_date"], "2024-03-15")
        self.assertEqual(item["comm_module"], "MOD-99")
        self.assertEqual(item["comm_technology"], "NB-IoT")
        self.assertEqual(item["manufacturer"], "Elster")
        self.assertEqual(item["model"], "A1700")
        self.assertEqual(item["network_provider"], "Vodafone")
        self.assertEqual(item["expl_id"], self.exploitation.token)
        self.assertEqual(item["dma_id"], self.dma.token)
        self.assertTrue(item["contract_active"])
        self.assertEqual(item["customer"], "Anna Garcia")
        self.assertEqual(item["cadastral_ref"], "08001A00010001")
        self.assertEqual(item["connect_id"], str(self.connection.id))

        log = IntegrationRequestLog.objects.get(
            provider="smartmetering",
            direction="inbound",
            endpoint="/smartmetering/v1/contracts/",
        )
        self.assertTrue(log.success)

    def test_contracts_handles_missing_relations(self):
        Contract.objects.create(token="CTR-EMPTY")

        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        empty_item = next(item for item in response.data if item["policy"] == "CTR-EMPTY")
        self.assertIsNone(empty_item["meter"])
        self.assertIsNone(empty_item["rate"])
        self.assertIsNone(empty_item["service_point"])
        self.assertIsNone(empty_item["inst_date"])
        self.assertIsNone(empty_item["expl_id"])
        self.assertIsNone(empty_item["dma_id"])
        self.assertFalse(empty_item["contract_active"])
        self.assertIsNone(empty_item["customer"])
        self.assertIsNone(empty_item["cadastral_ref"])
        self.assertIsNone(empty_item["connect_id"])

    def test_contracts_excludes_inactive_contracts(self):
        Contract.objects.create(
            token="CTR-INACTIVE",
            holder=self.holder,
            supply_point_default=self.supply_point,
            status=self.active_status,
            is_active=False,
        )

        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        policies = [item["policy"] for item in response.data]
        self.assertEqual(policies, ["CTR-001"])

    def test_contracts_filters_by_policy(self):
        Contract.objects.create(token="CTR-002", holder=self.holder, status=self.active_status)

        response = self.client.get(self.url, {"policy": "CTR-001"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["policy"], "CTR-001")

    def test_contracts_filters_by_meter(self):
        other_meter = Meter.objects.create(code="MTR-002")
        other_supply_point = SupplyPoint.objects.create(token="SP-002", meter=other_meter)
        Contract.objects.create(
            token="CTR-002",
            holder=self.holder,
            supply_point_default=other_supply_point,
            status=self.active_status,
        )

        response = self.client.get(self.url, {"meter": "MTR-001"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["policy"], "CTR-001")

    def test_contracts_filter_returns_empty_when_no_match(self):
        response = self.client.get(self.url, {"policy": "UNKNOWN"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 0)

    def test_rate_comes_from_contract_use_type(self):
        commercial = ContractUseType.objects.create(token="COM", name="Comercial")
        Contract.objects.create(
            token="CTR-002",
            holder=self.holder,
            supply_point_default=self.supply_point,
            status=self.active_status,
            use_type=commercial,
        )

        response = self.client.get(self.url, {"policy": "CTR-002"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data[0]["rate"], "Comercial")


class SmartMeteringGroupRestrictionTest(SmartMeteringInboundAuthMixin, TestCase):
    def test_smartmetering_group_can_access_smartmetering_routes(self):
        url = reverse("smartmetering-inbound-contracts")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_smartmetering_group_forbidden_outside_smartmetering(self):
        response = self.client.get("/coredata/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.json(), {"detail": "Forbidden"})

    def test_giswater_group_forbidden_on_smartmetering(self):
        giswater_user = User.objects.create_user(username="giswater-client", password="secret")
        giswater_group, _ = Group.objects.get_or_create(name="giswater")
        giswater_user.groups.add(giswater_group)
        token = Token.objects.create(user=giswater_user)

        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
        response = client.get(reverse("smartmetering-inbound-contracts"))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_smartmetering_group_forbidden_on_giswater(self):
        response = self.client.get(reverse("giswater-inbound-contracts"))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_ov_group_forbidden_on_smartmetering(self):
        ov_user = User.objects.create_user(username="ov-client", password="secret")
        ov_group, _ = Group.objects.get_or_create(name="ov")
        ov_user.groups.add(ov_group)
        token = Token.objects.create(user=ov_user)

        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
        response = client.get(reverse("smartmetering-inbound-contracts"))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
