from django.test import TestCase

from contract.models import ACABonificationRequest, Bonification, BonificationType, Contract, Variable, VariableType
from contract.serializers.variable_serializer import VariableSaveSerializer
from coredata.models import ConfigProject
from logger.models import LogContractTotalMembers


class AcaTramServiceTest(TestCase):

    def setUp(self):
        for token, value in (
            ('uses_aca', 'True'),
            ('aca_notification_enabled', 'True'),
            ('aca_at_token', 'ACA-TRAM'),
            ('aca_tram_min_persons', '4'),
            ('aca_tram_members_variable_token', 'ACA-TRAM-MEMBRES'),
            ('contract_active_token', 'actiu'),
            ('contract_terminated_status', 'baixa'),
        ):
            ConfigProject.objects.update_or_create(token=token, defaults={'value': value})

        self.type_flag = VariableType.objects.create(token='ACA-TRAM', name='Ampliació', data_type='bool')
        self.type_members = VariableType.objects.create(token='ACA-TRAM-MEMBRES', name='Membres', data_type='int')
        self.bonification_type = BonificationType.objects.create(token='ACA-TRAM', name='Ampliació de trams')
        self.bonification_type.variable_types.set([self.type_flag, self.type_members])

        self.contract = Contract.objects.create(token='CT-TEST', total_persons=1)

    def set_total_persons(self, value):
        self.contract.refresh_from_db()
        self.contract.total_persons = value
        self.contract.save()

    def active_bonification(self):
        return Bonification.objects.filter(
            contract=self.contract, bonification_type=self.bonification_type, is_active=True
        ).first()

    def members_value(self, bonification):
        return bonification.variables.get(type=self.type_members).value

    def test_increase_below_min_does_not_create_bonification(self):
        self.set_total_persons(2)

        self.assertIsNone(self.active_bonification())

    def test_reaching_min_creates_bonification_and_aca_request(self):
        self.set_total_persons(3)
        self.set_total_persons(4)

        bonification = self.active_bonification()
        self.assertIsNotNone(bonification)
        self.assertEqual(self.members_value(bonification), '4')
        self.assertEqual(ACABonificationRequest.objects.get(bonification=bonification).num_persons_to_apply, 4)

    def test_change_above_min_updates_members(self):
        self.set_total_persons(5)
        self.set_total_persons(6)
        self.set_total_persons(5)

        self.assertEqual(Bonification.objects.filter(contract=self.contract).count(), 1)
        bonification = self.active_bonification()
        self.assertEqual(self.members_value(bonification), '5')
        self.assertEqual(ACABonificationRequest.objects.get(bonification=bonification).num_persons_to_apply, 5)

    def test_drop_below_min_deactivates_bonification_without_restoring_persons(self):
        self.set_total_persons(5)
        bonification = self.active_bonification()

        self.set_total_persons(2)

        bonification.refresh_from_db()
        self.contract.refresh_from_db()
        self.assertFalse(bonification.is_active)
        self.assertIsNotNone(bonification.end_at)
        self.assertEqual(self.contract.total_persons, 2)
        self.assertFalse(ACABonificationRequest.objects.filter(bonification=bonification).exists())

    def test_members_variable_updates_contract_and_logs(self):
        self.set_total_persons(4)
        variable = self.active_bonification().variables.get(type=self.type_members)

        variable.value = '6'
        variable.save()

        self.contract.refresh_from_db()
        self.assertEqual(self.contract.total_persons, 6)
        log = LogContractTotalMembers.objects.get(object=self.contract)
        self.assertEqual((log.previous_total_persons, log.current_total_persons), (4, 6))

    def test_members_variable_below_min_does_not_touch_contract(self):
        self.set_total_persons(4)
        Variable.objects.filter(bonification=self.active_bonification(), type=self.type_members).update(value='2')
        variable = Variable.objects.get(bonification=self.active_bonification(), type=self.type_members)

        variable.save()

        self.contract.refresh_from_db()
        self.assertEqual(self.contract.total_persons, 4)

    def test_serializer_rejects_members_below_min(self):
        serializer = VariableSaveSerializer(data={
            'contract': self.contract.id, 'type': self.type_members.id, 'value': '2', 'token': 'VR-TEST',
        })

        self.assertFalse(serializer.is_valid())
        self.assertIn('value', serializer.errors)

    def test_serializer_allows_deactivating_old_variable_below_min(self):
        variable = Variable.objects.create(
            contract=self.contract, type=self.type_members, value='2', token='VR-OLD', is_active=True,
        )

        serializer = VariableSaveSerializer(variable, data={'is_active': False}, partial=True)

        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_without_aca_nothing_is_created_or_validated(self):
        ConfigProject.objects.filter(token='uses_aca').update(value='False')

        self.set_total_persons(5)
        serializer = VariableSaveSerializer(data={
            'contract': self.contract.id, 'type': self.type_members.id, 'value': '2', 'token': 'VR-TEST',
        })

        self.assertIsNone(self.active_bonification())
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_configured_variable_token_replaces_membres_hint(self):
        ConfigProject.objects.filter(token='aca_tram_members_variable_token').update(value='HABITANTS')
        habitants = VariableType.objects.create(token='HABITANTS', name='Habitants', data_type='int')
        self.bonification_type.variable_types.add(habitants)

        self.set_total_persons(4)

        bonification = self.active_bonification()
        self.assertEqual(bonification.variables.get(type=habitants).value, '4')
        self.assertFalse(bonification.variables.filter(type=self.type_members).exists())

        self.set_total_persons(6)
        self.assertEqual(bonification.variables.get(type=habitants).value, '6')

        variable = bonification.variables.get(type=habitants)
        variable.value = '7'
        variable.save()
        self.contract.refresh_from_db()
        self.assertEqual(self.contract.total_persons, 7)

        rejected = VariableSaveSerializer(data={
            'contract': self.contract.id, 'type': habitants.id, 'value': '2', 'token': 'VR-HAB',
        })
        ignored = VariableSaveSerializer(data={
            'contract': self.contract.id, 'type': self.type_members.id, 'value': '2', 'token': 'VR-MEM',
        })
        self.assertFalse(rejected.is_valid())
        self.assertTrue(ignored.is_valid(), ignored.errors)

    def test_missing_members_config_falls_back_to_aca_tram_membres(self):
        ConfigProject.objects.filter(token='aca_tram_members_variable_token').delete()

        self.set_total_persons(4)

        self.assertEqual(self.members_value(self.active_bonification()), '4')

    def test_min_persons_for_contract_only_with_active_bonification(self):
        from contract.utils.aca_tram_service import aca_tram_min_persons_for_contract

        self.assertIsNone(aca_tram_min_persons_for_contract(self.contract))
        self.set_total_persons(5)
        self.assertEqual(aca_tram_min_persons_for_contract(self.contract), 4)
