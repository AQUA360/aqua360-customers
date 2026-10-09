from datetime import date
from decimal import Decimal

from django.contrib.auth.models import Group, User
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from billing.models import Reading
from contract.models import Contract
from coredata.models import Address, City, Person, Street
from integrations.models import IntegrationRequestLog
from service.models import Connection, ConnectionDiameter, DMA, Exploitation, Meter, SupplyPoint


class GiswaterInboundAuthMixin:
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username="giswater-client", password="secret")
        self.giswater_group, _ = Group.objects.get_or_create(name="giswater")
        self.user.groups.add(self.giswater_group)
        self.token = Token.objects.create(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")


class GiswaterInboundContractsViewTest(GiswaterInboundAuthMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.url = reverse("giswater-inbound-contracts")

        self.holder = Person.objects.create(
            token="12345678A",
            name="Anna",
            surname="Garcia",
        )
        self.exploitation = Exploitation.objects.create(token="EXP-01", name="Exploitation 1")
        self.dma = DMA.objects.create(token="DMA-01", name="DMA 1")
        self.diameter = ConnectionDiameter.objects.create(token="D20", name="20mm")
        self.connection = Connection.objects.create(
            token="CONN-001",
            code_gis="12547",
            exploitation=self.exploitation,
            diameter=self.diameter,
            dma=self.dma,
            latitude=Decimal("41.480614"),
            longitude=Decimal("2.323578"),
        )
        self.street = Street.objects.create(name="Barcelona")
        self.city = City.objects.create(token="CITY-TEST", name="Població")
        self.address = Address.objects.create(
            street=self.street,
            city=self.city,
            postal_code="08110",
        )
        self.meter = Meter.objects.create(code="MTR-001")
        self.supply_point = SupplyPoint.objects.create(
            token="SP-001",
            connection=self.connection,
            address=self.address,
            meter=self.meter,
        )
        self.contract = Contract.objects.create(
            token="CTR-001",
            holder=self.holder,
            supply_point_default=self.supply_point,
        )

    def test_contracts_rejects_unauthenticated(self):
        client = APIClient()
        response = client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_contracts_returns_export_payload(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

        item = response.data[0]
        self.assertEqual(item["connection"]["token"], "CONN-001")
        self.assertEqual(item["connection"]["code_gis"], "12547")
        self.assertEqual(item["connection"]["exploitation_token"], "EXP-01")
        self.assertEqual(item["connection"]["diameter"], "D20")
        self.assertEqual(item["connection"]["dma_token"], "DMA-01")
        self.assertEqual(item["connection"]["latitude"], 41.480614)
        self.assertEqual(item["supply_point"]["token"], "SP-001")
        self.address.refresh_from_db()
        self.assertEqual(item["supply_point"]["address"], self.address.address_search)
        self.assertEqual(item["supply_point"]["meter_code"], "MTR-001")
        self.assertEqual(item["contract"]["token"], "CTR-001")
        self.assertEqual(item["contract"]["holder"]["name"], "Anna")
        self.assertEqual(item["contract"]["holder"]["surname"], "Garcia")
        self.assertEqual(item["contract"]["holder_full_name"], "Anna Garcia")

        log = IntegrationRequestLog.objects.get(
            provider="giswater", direction="inbound", endpoint="/giswater/v1/contracts/"
        )
        self.assertTrue(log.success)

    def test_contracts_handles_missing_relations(self):
        Contract.objects.create(token="CTR-EMPTY")

        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        empty_item = next(item for item in response.data if item["contract"]["token"] == "CTR-EMPTY")
        self.assertIsNone(empty_item["connection"])
        self.assertIsNone(empty_item["supply_point"])

    def test_contracts_filters_by_connection_token(self):
        other_connection = Connection.objects.create(token="CONN-002", code_gis="99999")
        other_supply_point = SupplyPoint.objects.create(
            token="SP-002",
            connection=other_connection,
        )
        Contract.objects.create(
            token="CTR-002",
            holder=self.holder,
            supply_point_default=other_supply_point,
        )

        response = self.client.get(self.url, {"connection_token": "CONN-001"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["contract"]["token"], "CTR-001")

    def test_contracts_filters_by_connection_code_gis(self):
        other_connection = Connection.objects.create(token="CONN-002", code_gis="99999")
        other_supply_point = SupplyPoint.objects.create(
            token="SP-002",
            connection=other_connection,
        )
        Contract.objects.create(
            token="CTR-002",
            holder=self.holder,
            supply_point_default=other_supply_point,
        )

        response = self.client.get(self.url, {"connection_code_gis": "12547"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["contract"]["token"], "CTR-001")

    def test_contracts_filter_returns_empty_when_no_match(self):
        response = self.client.get(self.url, {"connection_token": "UNKNOWN"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 0)


class GiswaterInboundReadingsViewTest(GiswaterInboundAuthMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.contract = Contract.objects.create(token="CTR-READ")
        self.supply_point = SupplyPoint.objects.create(token="SP-READ")
        self.meter = Meter.objects.create(code="MTR-READ")
        self.url = reverse(
            "giswater-inbound-contract-readings",
            kwargs={"contract_token": self.contract.token},
        )

        Reading.objects.create(
            contract=self.contract,
            supply_point=self.supply_point,
            meter=self.meter,
            reading_date=date(2026, 1, 15),
            reading_value=Decimal("100.50"),
            calculated_value=Decimal("12.00"),
            real_consumption=Decimal("11.50"),
            consumption_days=30,
            is_control=False,
            is_estimated=False,
            origin="manual",
            is_active=True,
        )
        Reading.objects.create(
            contract=self.contract,
            reading_date=date(2026, 2, 15),
            reading_value=Decimal("112.50"),
            calculated_value=Decimal("12.00"),
            is_active=False,
        )

    def test_readings_rejects_unauthenticated(self):
        client = APIClient()
        response = client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_readings_returns_active_readings_ordered_desc(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

        reading = response.data[0]
        self.assertEqual(reading["reading_date"], "2026-01-15")
        self.assertEqual(reading["reading_value"], 100.5)
        self.assertEqual(reading["consumption"], 12.0)
        self.assertEqual(reading["billing_consumption"], 11.5)
        self.assertEqual(reading["meter_code"], "MTR-READ")
        self.assertEqual(reading["supply_point_token"], "SP-READ")
        self.assertEqual(reading["origin"], "manual")

    def test_readings_unknown_contract_returns_404(self):
        url = reverse(
            "giswater-inbound-contract-readings",
            kwargs={"contract_token": "UNKNOWN"},
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class GiswaterGroupRestrictionTest(GiswaterInboundAuthMixin, TestCase):
    def test_giswater_group_can_access_giswater_routes(self):
        url = reverse("giswater-inbound-contracts")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_giswater_group_forbidden_outside_giswater(self):
        response = self.client.get("/coredata/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.json(), {"detail": "Forbidden"})

    def test_ov_group_forbidden_on_giswater(self):
        ov_user = User.objects.create_user(username="ov-client", password="secret")
        ov_group, _ = Group.objects.get_or_create(name="ov")
        ov_user.groups.add(ov_group)
        token = Token.objects.create(user=ov_user)

        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
        response = client.get(reverse("giswater-inbound-contracts"))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
