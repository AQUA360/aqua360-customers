"""Eliminar una sol·licitud d'escomesa: només en esborrany o pendent i sense registres lligats."""
from django.contrib.auth.models import Permission, User
from django.test import TestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from billing.models import Invoice
from coredata.models import ConfigProject
from documentmanager.models import Document
from logger.models import LogConnectionRequestStatus
from order.models import Order
from service.models import (
    Connection,
    ConnectionRequest,
    ConnectionRequestDocumentationFile,
    ConnectionRequestObservation,
    ConnectionRequestStatus,
)
from service.views.connection_request_view import ConnectionRequestViewSet


class ConnectionRequestDeleteTest(TestCase):
    def setUp(self):
        ConfigProject.objects.create(token='invoice_status_cancelled_token', value='cancelled')
        self.user = User.objects.create(username='deleter')
        self.user.user_permissions.add(Permission.objects.get(codename='delete_connectionrequest'))
        self.user = User.objects.get(pk=self.user.pk)
        self.statuses = {
            token: ConnectionRequestStatus.objects.create(token=token, name=token)
            for token in ('draft', 'pending', 'approved', '1', '-1')
        }

    def _request(self, status_token='draft', **kwargs):
        return ConnectionRequest.objects.create(
            token=f'REQ-{ConnectionRequest.objects.count() + 1}',
            status=self.statuses[status_token],
            **kwargs,
        )

    def _delete(self, obj, user=None):
        request = APIRequestFactory().delete(f'/service/connection-request/{obj.pk}/')
        force_authenticate(request, user=user or self.user)
        return ConnectionRequestViewSet.as_view({'delete': 'destroy'})(request, pk=obj.pk)

    def test_draft_and_pending_can_be_deleted(self):
        for token in ('draft', 'pending'):
            obj = self._request(token)
            ConnectionRequestObservation.objects.create(connection_request=obj)
            LogConnectionRequestStatus.objects.create(object=obj, current_status=obj.status)
            response = self._delete(obj)
            self.assertEqual(response.status_code, 204, token)
            self.assertFalse(ConnectionRequest.objects.filter(pk=obj.pk).exists())
            self.assertFalse(ConnectionRequestObservation.objects.filter(connection_request_id=obj.pk).exists())
        self.assertFalse(LogConnectionRequestStatus.objects.exists())

    def test_other_statuses_cannot_be_deleted(self):
        for token in ('approved', '1', '-1'):
            obj = self._request(token)
            response = self._delete(obj)
            self.assertEqual(response.status_code, 400, token)
            self.assertEqual(response.data['error'], 'not_deletable_status')
            self.assertTrue(ConnectionRequest.objects.filter(pk=obj.pk).exists())

    def test_without_status_cannot_be_deleted(self):
        obj = ConnectionRequest.objects.create(token='REQ-NO-STATUS')
        self.assertEqual(self._delete(obj).status_code, 400)

    def test_with_related_records_cannot_be_deleted(self):
        with_connection = self._request(connection=Connection.objects.create(token='CON-1'))
        with_invoice = self._request()
        Invoice.objects.create(connection_request=with_invoice)
        with_order = self._request()
        Order.objects.create(connection_request=with_order)
        for obj in (with_connection, with_invoice, with_order):
            response = self._delete(obj)
            self.assertEqual(response.status_code, 400)
            self.assertEqual(response.data['error'], 'has_related_records')
            self.assertTrue(ConnectionRequest.objects.filter(pk=obj.pk).exists())

    def test_inactive_related_records_do_not_block(self):
        obj = self._request()
        Invoice.objects.create(connection_request=obj, is_active=False)
        Order.objects.create(connection_request=obj, is_active=False)
        self.assertEqual(self._delete(obj).status_code, 204)

    def test_inactive_connection_does_not_block(self):
        obj = self._request(connection=Connection.objects.create(token='CON-OFF', is_active=False))
        self.assertEqual(self._delete(obj).status_code, 204)

    def test_requires_delete_permission(self):
        obj = self._request()
        response = self._delete(obj, user=User.objects.create(username='viewer'))
        self.assertEqual(response.status_code, 403)
        self.assertTrue(ConnectionRequest.objects.filter(pk=obj.pk).exists())

    def test_documents_are_deactivated(self):
        obj = self._request()
        document = Document.objects.create(entity='CONNECTION_REQUEST', entity_id=obj.pk, service='hdd')
        ConnectionRequestDocumentationFile.objects.create(connection_request=obj, file=document)
        other = Document.objects.create(entity='CONNECTION_REQUEST', entity_id=obj.pk + 1000, service='hdd')
        self.assertEqual(self._delete(obj).status_code, 204)
        document.refresh_from_db()
        other.refresh_from_db()
        self.assertFalse(document.is_active)
        self.assertTrue(other.is_active)
