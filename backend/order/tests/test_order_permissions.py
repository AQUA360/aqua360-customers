"""Permisos de lectura de les ordres, els operadors i el PDF d'una ordre (#2653).

Abans, `DjangoModelPermissions` no exigia cap permís per GET: qualsevol usuari
autenticat llegia ordres i operadors i generava (i desava) el PDF d'una ordre.
Ara:
- Ordres: `view_order`, o bé el permís de la fitxa (incidència, contracte...)
  quan es llisten filtrades per aquella fitxa o es consulta una ordre lligada
  a una fitxa que l'usuari pot veure (mateix criteri que les reclamacions).
- Operadors: `view_operator`.
- PDF: POST amb `view_order`.
- `by-token` d'un codi inexistent: 404.
"""
from unittest.mock import patch

from django.contrib.auth.models import Permission, User
from django.test import TestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from contract.models import Contract
from coredata.models import Address, ConfigProject
from notification.models import Incident
from service.models import SupplyPoint
from order.models import Operator, Order, OrderStatus
from order.permissions import OrderViewSetPermission
from order.views.operator_view import OperatorViewSet
from order.views.order_pdf_view import OrderReportPDFDownloadViewSet
from order.views.order_view import OrderViewSet


def _perm(label):
    app_label, codename = label.split('.')
    return Permission.objects.get(content_type__app_label=app_label, codename=codename)


class OrderPermissionsTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        status = OrderStatus.objects.create(token="2653-default", name="Pendent (test)", is_default=True)
        cls.incident = Incident.objects.create()
        cls.other_incident = Incident.objects.create()
        cls.order = Order.objects.create(status=status, token="2653-A", incident=cls.incident)
        cls.other_order = Order.objects.create(status=status, token="2653-B", incident=cls.other_incident)
        cls.loose_order = Order.objects.create(status=status, token="2653-C")
        # El senyal de desar un contracte llegeix aquesta configuració
        ConfigProject.objects.get_or_create(token="contract_terminated_status", defaults={"value": "2653-terminated"})
        # El llistat d'ordres mostra l'adreça del punt de subministrament
        cls.supply_point = SupplyPoint.objects.create(token="2653-SP", address=Address.objects.create())
        cls.contract = Contract.objects.create(supply_point_default=cls.supply_point)
        cls.supply_point_order = Order.objects.create(status=status, token="2653-D", supply_point=cls.supply_point)
        cls.operator = Operator.objects.create(token="2653-OP", name="Operari", surname="Test")

        cls.no_perms = User.objects.create_user("no-perms-2653", "no-perms-2653@example.com", "x")
        cls.order_viewer = User.objects.create_user("order-viewer-2653", "order-viewer-2653@example.com", "x")
        cls.order_viewer.user_permissions.add(_perm("order.view_order"), _perm("order.view_operator"))
        cls.incident_viewer = User.objects.create_user("incident-viewer-2653", "incident-viewer-2653@example.com", "x")
        cls.incident_viewer.user_permissions.add(_perm("notification.view_incident"))

        cls.contract_viewer = User.objects.create_user("contract-viewer-2653", "contract-viewer-2653@example.com", "x")
        cls.contract_viewer.user_permissions.add(_perm("contract.view_contract"))

        cls.factory = APIRequestFactory()

    def _get(self, view, path, user, **kwargs):
        request = self.factory.get(path)
        force_authenticate(request, user=User.objects.get(pk=user.pk))
        return view(request, **kwargs)

    def _list(self, user, query=""):
        return self._get(OrderViewSet.as_view({"get": "list"}), f"/order/{query}", user)

    def _retrieve(self, user, order):
        return self._get(OrderViewSet.as_view({"get": "retrieve"}), f"/order/{order.pk}/", user, pk=order.pk)

    def _by_token(self, user, token):
        return self._get(OrderViewSet.as_view({"get": "by_token"}), f"/order/by-token/{token}/", user, token=token)

    def _ids(self, response):
        data = response.data
        results = data["results"] if isinstance(data, dict) and "results" in data else data
        return {row["id"] for row in results}

    # Ordres

    def test_order_list_requires_permission(self):
        self.assertEqual(self._list(self.no_perms).status_code, 403)
        self.assertEqual(self._list(self.no_perms, f"?incident={self.incident.pk}").status_code, 403)
        self.assertEqual(self._list(self.order_viewer).status_code, 200)

    def test_order_detail_and_by_token_require_permission(self):
        self.assertEqual(self._retrieve(self.no_perms, self.order).status_code, 403)
        self.assertEqual(self._by_token(self.no_perms, self.order.token).status_code, 403)
        self.assertEqual(self._retrieve(self.order_viewer, self.order).status_code, 200)
        self.assertEqual(self._by_token(self.order_viewer, self.order.token).status_code, 200)

    def test_by_token_not_found_returns_404(self):
        self.assertEqual(self._by_token(self.order_viewer, "2653-NO-EXISTEIX").status_code, 404)

    def test_related_viewer_lists_only_orders_of_filtered_record(self):
        response = self._list(self.incident_viewer, f"?incident={self.incident.pk}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self._ids(response), {self.order.pk})

    def test_related_viewer_cannot_list_without_valid_filter(self):
        for query in ("", "?incident=", "?incident=abc", f"?contract={self.incident.pk}"):
            with self.subTest(query=query):
                self.assertEqual(self._list(self.incident_viewer, query).status_code, 403)

    def test_related_viewer_detail_only_for_linked_orders(self):
        self.assertEqual(self._retrieve(self.incident_viewer, self.order).status_code, 200)
        self.assertEqual(self._retrieve(self.incident_viewer, self.loose_order).status_code, 403)

    def test_related_viewer_cannot_use_other_order_actions(self):
        self.assertEqual(self._by_token(self.incident_viewer, self.order.token).status_code, 403)

    def test_contract_viewer_same_criteria_in_list_and_detail(self):
        # L'ordre és del contracte a través del punt de subministrament: surt al
        # llistat filtrat pel contracte i, per tant, també se'n pot obrir el detall.
        response = self._list(self.contract_viewer, f"?contract={self.contract.pk}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self._ids(response), {self.supply_point_order.pk})
        # Detall: es comprova el permís sobre l'objecte (el serializer del detall
        # carrega tota la fitxa del punt de subministrament).
        request = self.factory.get(f"/order/{self.supply_point_order.pk}/")
        request.user = User.objects.get(pk=self.contract_viewer.pk)
        permission = OrderViewSetPermission()
        self.assertTrue(permission.has_object_permission(request, None, self.supply_point_order))
        self.assertFalse(permission.has_object_permission(request, None, self.loose_order))

    # Operadors

    def test_operator_read_requires_permission(self):
        list_view = OperatorViewSet.as_view({"get": "list"})
        detail_view = OperatorViewSet.as_view({"get": "retrieve"})
        for user, expected in ((self.no_perms, 403), (self.incident_viewer, 403), (self.order_viewer, 200)):
            with self.subTest(user=user.username):
                self.assertEqual(self._get(list_view, "/operator/", user).status_code, expected)
                self.assertEqual(
                    self._get(detail_view, f"/operator/{self.operator.pk}/", user, pk=self.operator.pk).status_code,
                    expected,
                )

    def test_operator_head_and_options(self):
        list_view = OperatorViewSet.as_view({"get": "list"})
        for user, head_expected in ((self.no_perms, 403), (self.order_viewer, 200)):
            with self.subTest(user=user.username):
                for method, expected in (("head", head_expected), ("options", 200)):
                    request = getattr(self.factory, method)("/operator/")
                    force_authenticate(request, user=User.objects.get(pk=user.pk))
                    self.assertEqual(list_view(request).status_code, expected, method)

    # PDF

    def _pdf(self, method, user):
        request = getattr(self.factory, method)(f"/order/download-order/{self.order.pk}/")
        force_authenticate(request, user=User.objects.get(pk=user.pk))
        view = OrderReportPDFDownloadViewSet.as_view(http_method_names=["post"])
        return view(request, id=self.order.pk)

    @patch("order.views.order_pdf_view.generate_order_pdf", return_value=("/media/test.pdf", 1, None))
    def test_pdf_requires_post_and_view_permission(self, generate):
        self.assertEqual(self._pdf("post", self.no_perms).status_code, 403)
        self.assertEqual(self._pdf("post", self.incident_viewer).status_code, 403)
        self.assertEqual(self._pdf("get", self.order_viewer).status_code, 405)
        generate.assert_not_called()

        response = self._pdf("post", self.order_viewer)
        self.assertEqual(response.status_code, 200)
        generate.assert_called_once()
