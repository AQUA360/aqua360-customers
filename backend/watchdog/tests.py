from django.core.management import call_command
from django.test import TestCase
from io import StringIO

from billing.models import GeneralPayment
from contract.models import Contract, ContractRepresentative, ContractStatus
from coredata.models import ConfigProject, Person, PersonAddress, PersonBank, PersonContact
from service.models import Meter, SupplyPoint
from watchdog.services import DataIntegrityService
from watchdog.persons_without_contact import (
    check_active_contract_person_issues,
    check_zombie_person_issues,
    get_zombie_persons_queryset,
)


class PersonsWithoutContactWatchdogTests(TestCase):
    def setUp(self):
        self.active = ContractStatus.objects.create(token="1", name="Alta")
        self.inactive = ContractStatus.objects.create(token="0", name="Baixa")
        ConfigProject.objects.update_or_create(
            token="contract_active_token",
            defaults={"value": "1"},
        )
        ConfigProject.objects.update_or_create(
            token="contract_terminated_status",
            defaults={"value": "-1"},
        )

    def _person(self, name):
        return Person.objects.create(name=name, surname="Test", token=name)

    def test_zombie_is_a_failure_and_active_contract_is_only_a_warning(self):
        zombie = self._person("Zombi")
        with_contact = self._person("AmbContacte")
        PersonContact.objects.create(person=with_contact, phone="600000000")
        with_address = self._person("AmbAdreca")
        PersonAddress.objects.create(person=with_address)
        inactive_holder = self._person("Baixa")
        Contract.objects.create(
            token="BAIXA-1",
            status=self.inactive,
            holder=inactive_holder,
        )
        active_owner = self._person("Actiu")
        Contract.objects.create(
            token="ALTA-9",
            status=self.active,
            owner=active_owner,
        )

        zombie_issues = check_zombie_person_issues()
        self.assertTrue(any(f"Persona ID {zombie.id}" in issue for issue in zombie_issues))
        self.assertFalse(any("AmbContacte" in issue for issue in zombie_issues))
        self.assertFalse(any("AmbAdreca" in issue for issue in zombie_issues))
        self.assertFalse(any("Baixa" in issue for issue in zombie_issues))
        self.assertFalse(any("Actiu" in issue for issue in zombie_issues))

        warning_issues = check_active_contract_person_issues()
        self.assertTrue(
            any("ALTA-9 (propietari)" in issue and f"Persona ID {active_owner.id}" in issue for issue in warning_issues)
        )
        self.assertFalse(any(f"Persona ID {zombie.id}" in issue for issue in warning_issues))
        self.assertFalse(any("BAIXA-1" in issue for issue in warning_issues))

    def test_representative_of_active_contract_is_a_warning(self):
        person = self._person("Rep")
        contract = Contract.objects.create(token="ALTA-REP", status=self.active)
        ContractRepresentative.objects.create(person=person, contract=contract)

        self.assertFalse(get_zombie_persons_queryset().filter(id=person.id).exists())
        issues = check_active_contract_person_issues()
        self.assertTrue(any("ALTA-REP (representant)" in issue for issue in issues))

    def test_delete_command_removes_only_zombies(self):
        zombie = self._person("Esborrar")
        kept = self._person("Guardar")
        Contract.objects.create(token="ALTA-KEEP", status=self.active, holder=kept)

        dry_run = StringIO()
        call_command("watchdog_fix_delete_zombie_persons", "--dry-run", stdout=dry_run)
        self.assertIn(str(zombie.id), dry_run.getvalue())
        self.assertTrue(Person.objects.filter(id=zombie.id).exists())

        call_command("watchdog_fix_delete_zombie_persons", stdout=StringIO())
        self.assertFalse(Person.objects.filter(id=zombie.id).exists())
        self.assertTrue(Person.objects.filter(id=kept.id).exists())

    def test_delete_command_skips_person_whose_bank_is_in_use(self):
        zombie = self._person("Banc")
        bank = PersonBank.objects.create(person=zombie, iban="ES0000000000000000000000")
        other = self._person("Altre")
        PersonContact.objects.create(person=other, email="a@example.com")
        payment = GeneralPayment.objects.create(IBAN=bank)
        Contract.objects.create(
            token="ALTA-BANC",
            status=self.active,
            holder=other,
            payment=payment,
        )

        output = StringIO()
        call_command("watchdog_fix_delete_zombie_persons", stdout=output)
        self.assertTrue(Person.objects.filter(id=zombie.id).exists())
        self.assertIn("compte bancari", output.getvalue())


class ActiveContractsSupplyPointMeterTests(TestCase):
    def setUp(self):
        self.active = ContractStatus.objects.create(token="1", name="Alta")
        self.inactive = ContractStatus.objects.create(token="0", name="Baixa")
        ConfigProject.objects.update_or_create(
            token="contract_active_token",
            defaults={"value": "1"},
        )
        ConfigProject.objects.update_or_create(
            token="contract_terminated_status",
            defaults={"value": "-1"},
        )
        self.service = DataIntegrityService()

    def test_only_active_contracts_without_meter_fail(self):
        active_without = Contract.objects.create(token="ALTA-SENSE", status=self.active)
        active_without.supply_points.add(SupplyPoint.objects.create(token="SP-SENSE"))

        inactive_without = Contract.objects.create(token="BAIXA-SENSE", status=self.inactive)
        inactive_without.supply_points.add(SupplyPoint.objects.create(token="SP-BAIXA"))

        active_with = Contract.objects.create(token="ALTA-AMB", status=self.active)
        active_with.supply_points.add(
            SupplyPoint.objects.create(token="SP-AMB", meter=Meter.objects.create(token="M1"))
        )

        issues = self.service.check_contracts_with_supply_points_no_meter()
        self.assertTrue(any("ALTA-SENSE" in issue for issue in issues))
        self.assertFalse(any("BAIXA-SENSE" in issue for issue in issues))
        self.assertFalse(any("ALTA-AMB" in issue for issue in issues))
