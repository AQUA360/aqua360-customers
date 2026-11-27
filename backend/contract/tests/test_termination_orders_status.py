"""Les ordres d'una baixa no tornen a Pendent si ja estan en marxa (#2936).

- Quan la baixa passa a Pendent, només les ordres en Esborrany passen a Pendent,
  i l'historial ho apunta a nom de la baixa, no de l'usuari.
- Desar o cancel·lar la baixa no toca les ordres en marxa.
- Cada canvi d'estat fet per l'app s'envia al GMAO; els que arriben del GMAO, no.
"""
from unittest.mock import patch

from django.test import TestCase, override_settings

from contract.models import Contract, ContractStatus, ContractTerminationRequest, ContractTerminationStatus
from coredata.models import ConfigProject
from logger.models import LogOrderStatus
from order.models import Order, OrderStatus


@override_settings(RABBITMQ_ENABLED=False)
class TerminationOrdersStatusTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        for token, value in (
            ('contract_active_token', 'ACTIVE'),
            ('contract_terminated_status', 'TERMINATED'),
            ('contract_termination_pending_token', 'CT_PENDING'),
            ('contract_termination_completed_token', 'CT_COMPLETED'),
            ('contract_termination_cancelled_token', 'CT_CANCELLED'),
            ('contract_termination_draft', 'CT_DRAFT'),
            ('order_status_pending_token', 'OS_PENDING'),
            ('order_status_draft_token', 'OS_DRAFT'),
            ('order_status_completed_token', 'OS_COMPLETED'),
        ):
            ConfigProject.objects.update_or_create(token=token, defaults={'value': value})
        cls.ct_draft = ContractTerminationStatus.objects.create(token='CT_DRAFT', name='Esborrany')
        cls.ct_pending = ContractTerminationStatus.objects.create(token='CT_PENDING', name='Pendent')
        cls.ct_cancelled = ContractTerminationStatus.objects.create(token='CT_CANCELLED', name='Cancel·lat')
        cls.os_draft = OrderStatus.objects.create(token='OS_DRAFT', name='Esborrany')
        cls.os_pending = OrderStatus.objects.create(token='OS_PENDING', name='Pendent')
        cls.os_in_progress = OrderStatus.objects.create(token='OS_IN_PROGRESS', name='En Curs')
        cls.active = ContractStatus.objects.create(token='ACTIVE', name='Actiu')

    def _termination(self, token, status):
        contract = Contract.objects.create(token=f'CON-{token}', status=self.active, is_active=True)
        return ContractTerminationRequest.objects.create(token=f'BX-{token}', contract=contract, status=status)

    def _order(self, token, status, termination):
        return Order.objects.create(token=token, status=status, contract_termination_request=termination)

    def test_pending_termination_releases_only_draft_orders(self):
        termination = self._termination('1', self.ct_draft)
        draft = self._order('ORD-1A', self.os_draft, termination)
        in_progress = self._order('ORD-1B', self.os_in_progress, termination)

        termination.status = self.ct_pending
        termination.save()

        draft.refresh_from_db()
        in_progress.refresh_from_db()
        self.assertEqual(draft.status, self.os_pending)
        self.assertEqual(in_progress.status, self.os_in_progress)
        log = LogOrderStatus.objects.get(object=draft)
        self.assertIsNone(log.user)
        self.assertEqual(log.observation, 'Canvi automàtic per la baixa BX-1')
        self.assertFalse(LogOrderStatus.objects.filter(object=in_progress).exists())

    def test_saving_pending_termination_does_not_touch_orders(self):
        termination = self._termination('2', self.ct_pending)
        in_progress = self._order('ORD-2', self.os_in_progress, termination)

        termination.ignore_invoice = True
        termination.save()

        in_progress.refresh_from_db()
        self.assertEqual(in_progress.status, self.os_in_progress)

    def test_cancelled_termination_does_not_touch_orders(self):
        termination = self._termination('3', self.ct_pending)
        in_progress = self._order('ORD-3A', self.os_in_progress, termination)
        draft = self._order('ORD-3B', self.os_draft, termination)

        termination.status = self.ct_cancelled
        termination.save()

        in_progress.refresh_from_db()
        draft.refresh_from_db()
        self.assertEqual(in_progress.status, self.os_in_progress)
        self.assertEqual(draft.status, self.os_draft)

    @override_settings(RABBITMQ_ENABLED=True)
    def test_status_change_is_published_to_gmao(self):
        with patch('order.services.rabbit.publish_order_created'):
            termination = self._termination('4', self.ct_draft)
            draft = self._order('ORD-4', self.os_draft, termination)

        with patch('order.services.rabbit.publish_order_status_changed') as publish, \
                self.captureOnCommitCallbacks(execute=True):
            termination.status = self.ct_pending
            termination.save()

        publish.assert_called_once()
        order, previous_status, reason = publish.call_args.args
        self.assertEqual(order.pk, draft.pk)
        self.assertEqual(order.status, self.os_pending)
        self.assertEqual(previous_status, self.os_draft)
        self.assertEqual(reason, 'Canvi automàtic per la baixa BX-4')

    @override_settings(RABBITMQ_ENABLED=True)
    def test_status_change_from_gmao_is_not_published_back(self):
        with patch('order.services.rabbit.publish_order_created'):
            order = self._order('ORD-5', self.os_pending, None)

        with patch('order.services.rabbit.publish_order_status_changed') as publish, \
                self.captureOnCommitCallbacks(execute=True):
            order.status = self.os_in_progress
            order._from_gmao = True
            order.save()

        publish.assert_not_called()

    @override_settings(RABBITMQ_ENABLED=True)
    def test_save_without_status_change_is_not_published(self):
        with patch('order.services.rabbit.publish_order_created'):
            order = self._order('ORD-6', self.os_pending, None)

        with patch('order.services.rabbit.publish_order_status_changed') as publish, \
                self.captureOnCommitCallbacks(execute=True):
            order.description = 'canvi'
            order.save()

        publish.assert_not_called()
