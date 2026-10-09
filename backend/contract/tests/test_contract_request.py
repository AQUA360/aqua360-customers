from django.db import connection
from django.core.management import call_command
from django.test import TestCase
from django.contrib.auth.models import User

# Models necessaris
from coredata.models import Person, PersonAddress, PersonCNAE, PersonBank, PersonContact, ConfigProject
from contract.models import (
    ContractStatus, ContractRequestStatus,
    ContractRequest, Contract, SupplyPoint,
    ContractTerminationRequest, BonificationType,
    Bonification, Variable, ACADocument
)
from order.models import Order, OrderType, OrderStatus
from logger.models import LogContractChange

# Utils necessaris
from contract.utils.contract_service import contract_create
from contract.utils.contract_request_service import contract_request_finalize

class ContractRequestFinalizeUnitTest(TestCase):
    @classmethod
    def load_fixtures(cls):
        # Deshabilitar tots els signals
        from django.db.models.signals import post_save
        from django.dispatch import receiver
        from contract.signals import (
            update_termination_status,
            deactivate_bonification_type,
            deactivate_bonification,
            modified_variables_bonifications,
            added_end_at_variable,
            assign_variables
        )
        
        # Desconnectar tots els signals
        post_save.disconnect(update_termination_status, sender=ContractTerminationRequest)
        post_save.disconnect(deactivate_bonification_type, sender=BonificationType)
        post_save.disconnect(deactivate_bonification, sender=Bonification)
        post_save.disconnect(modified_variables_bonifications, sender=Variable)
        post_save.disconnect(added_end_at_variable, sender=Variable)
        post_save.disconnect(assign_variables, sender=ACADocument)
        
        # Disable debug cursor
        connection.force_debug_cursor = False

        try:
            # Load your fixtures
            call_command('loaddata', 'coredata/fixtures/tests/all_data.json')
            
        finally:
            # Reconnectar tots els signals
            post_save.connect(update_termination_status, sender=ContractTerminationRequest)
            post_save.connect(deactivate_bonification_type, sender=BonificationType)
            post_save.connect(deactivate_bonification, sender=Bonification)
            post_save.connect(modified_variables_bonifications, sender=Variable)
            post_save.connect(added_end_at_variable, sender=Variable)
            post_save.connect(assign_variables, sender=ACADocument)
            
            # Re-enable debug cursor
            connection.force_debug_cursor = True
    
    @classmethod
    def setUp(self):
        self.load_fixtures()
        self.user, created = User.objects.get_or_create(username='customers', defaults={'password': 'customers'})
        
        self.borrador_status = ContractRequestStatus.objects.get(token='1')
        
        pending_token_config = ConfigProject.objects.get(token='contract_request_pending_token')
        pending_token = pending_token_config.value
        self.pending_status = ContractRequestStatus.objects.get(token=pending_token)
        # Crear OrderStatus 'PENDING'
        self.pending_order_status = OrderStatus.objects.get(is_default=True)
        # Crear OrderTypes
        self.order_type1 = OrderType.objects.get(token='read_meter')
        self.order_type2 = OrderType.objects.get(token='Install_meter')
        # Crear SupplyPoint
        self.supply_point = SupplyPoint.objects.create(token='SP1', name='SupplyPoint1')
        # Crear ContractRequest
        self.contract_request = ContractRequest.objects.create(
            token='CR1',
            status=self.borrador_status
            # Assigna altres camps necessaris...
        )
        self.contract_request.order_types.add(self.order_type1, self.order_type2)
    
    def test_finalize_contract_request_success(self):
        # Finalitzar el ContractRequest
        updated_contract_request = contract_request_finalize(self.user,self.contract_request.id)
        # Comprovar que el status s'ha actualitzat
        self.assertEqual(updated_contract_request.status.token, self.pending_status.token)
        # Comprovar que les Orders s'han creat
        orders = Order.objects.filter(contract_request=self.contract_request)
        self.assertEqual(orders.count(), 2)
        self.assertTrue(orders.filter(type=self.order_type1).exists())
        self.assertTrue(orders.filter(type=self.order_type2).exists()) 