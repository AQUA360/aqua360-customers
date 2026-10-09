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

class ContractUnitTest(TestCase):
    
    @classmethod
    def load_fixtures(cls):
        # Deshabilitar tots els signals
        from django.db.models.signals import post_save, pre_save
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
    def setUpTestData(cls):
        cls.load_fixtures()
        # Load or create the test user
        cls.user, created = User.objects.get_or_create(username='customers', defaults={'password': 'customers'})
        # Load necessary statuses
        cls.active_status = ContractStatus.objects.get(token='1')
        cls.inactive_status = ContractStatus.objects.get(token='-1')
        # Create or fetch a ContractRequestStatus
        cls.contract_request_status_finalized = ContractRequestStatus.objects.get(token='3')
        
        # Get an existing SupplyPoint from fixtures
        cls.supply_point = SupplyPoint.objects.get(token='29001')
        
        # Create a ContractRequest object with the supply point
        cls.contract_request = ContractRequest.objects.create(
            token='20241107120228',
            status=cls.contract_request_status_finalized,
            supply_point_default=cls.supply_point
        )

    def test_contract_creation_creates_log_entry(self):
        # Create a contract using the test data
        contract_request = self.contract_request
        contract = contract_create(self.user, contract_request.id)
        contract.refresh_from_db()

        # Assertions to verify the contract was created correctly
        self.assertEqual(contract.token, '20241107120228')
        self.assertEqual(contract.supply_point_default, contract_request.supply_point_default)
        self.assertEqual(contract.holder, contract_request.holder)

        # Verify a log entry was created
        log = LogContractChange.objects.get(contract=contract, action='create')
        self.assertEqual(log.user, self.user) 