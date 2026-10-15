import importlib

from django.test import TestCase

from contract.models import ContractRequest
from contract.serializers.contract_request_serializer import ContractRequestSaveSerializer
from coredata.models import Person


class ContractRequestDefaultPersonTest(TestCase):
    """Sense sol·licitant, el titular de la sol·licitud fa de sol·licitant."""

    def setUp(self):
        self.holder = Person.objects.create(name="Titular", surname="Prova")
        self.applicant = Person.objects.create(name="Sol·licitant", surname="Prova")

    def _save(self, data, instance=None):
        if instance is None:
            data = {"token": "REQ-TEST", **data}
        serializer = ContractRequestSaveSerializer(instance, data=data, partial=instance is not None)
        serializer.is_valid(raise_exception=True)
        return serializer.save()

    def test_create_without_person_uses_holder(self):
        request = self._save({"holder": self.holder.id})
        self.assertEqual(request.person, self.holder)

    def test_update_holder_fills_empty_person(self):
        request = self._save({})
        self.assertIsNone(request.person)

        request = self._save({"holder": self.holder.id}, instance=request)
        self.assertEqual(request.person, self.holder)

    def test_existing_person_is_kept(self):
        request = self._save({"person": self.applicant.id})
        request = self._save({"holder": self.holder.id}, instance=request)
        self.assertEqual(request.person, self.applicant)

    def test_changing_holder_does_not_change_person(self):
        request = self._save({"holder": self.holder.id})
        other_holder = Person.objects.create(name="Altre", surname="Titular")
        request = self._save({"holder": other_holder.id}, instance=request)
        self.assertEqual(request.person, self.holder)

    def test_opscript_fills_only_empty_person_with_holder(self):
        without_person = ContractRequest.objects.create(holder=self.holder)
        with_person = ContractRequest.objects.create(holder=self.holder, person=self.applicant)
        without_holder = ContractRequest.objects.create()

        importlib.import_module("contract.opscripts.0004_fill_empty_contract_request_person").run()

        without_person.refresh_from_db()
        with_person.refresh_from_db()
        without_holder.refresh_from_db()
        self.assertEqual(without_person.person, self.holder)
        self.assertEqual(with_person.person, self.applicant)
        self.assertIsNone(without_holder.person)
