from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.test import RequestFactory, TestCase

from contract.filters.contract_filter import ContractFilter
from contract.models import Contract, ContractStatus
from coredata.models import ConfigProject


class ContractIsCheckedFilterTest(TestCase):
    """Filtre is_checked (contractes en seguiment): cada usuari veu només els que segueix ell."""

    @classmethod
    def setUpTestData(cls):
        # El signal post_save de Contract la llegeix; un valor que no coincideix amb cap
        # estat de la prova evita el flux de fiances de baixa, que aquí no es prova.
        ConfigProject.objects.update_or_create(
            token='contract_terminated_status', defaults={'value': 'CHK_UNUSED_TERMINATED'}
        )
        active, _ = ContractStatus.objects.get_or_create(token='CHK_ACTIVE', defaults={'name': 'Actiu'})
        User = get_user_model()
        cls.user_a = User.objects.create_user('chk-user-a', 'chk-a@example.com', 'x')
        cls.user_b = User.objects.create_user('chk-user-b', 'chk-b@example.com', 'x')

        cls.only_a = Contract.objects.create(token='CHK-A', status=active, is_active=True)
        cls.only_b = Contract.objects.create(token='CHK-B', status=active, is_active=True)
        cls.both = Contract.objects.create(token='CHK-AB', status=active, is_active=True)
        cls.nobody = Contract.objects.create(token='CHK-NONE', status=active, is_active=True)

        cls.only_a.user_checked.add(cls.user_a)
        cls.only_b.user_checked.add(cls.user_b)
        cls.both.user_checked.add(cls.user_a, cls.user_b)

    def _ids(self, data, user):
        request = RequestFactory().get('/')
        request.user = user
        qs = ContractFilter(data=data, queryset=Contract.objects.all(), request=request).qs
        return list(qs.values_list('id', flat=True))

    def test_each_user_sees_only_their_checked_contracts(self):
        ids_a = self._ids({'is_checked': 'true'}, self.user_a)
        ids_b = self._ids({'is_checked': 'true'}, self.user_b)
        self.assertCountEqual(ids_a, [self.only_a.id, self.both.id])
        self.assertCountEqual(ids_b, [self.only_b.id, self.both.id])

    def test_contract_checked_by_several_users_is_not_duplicated(self):
        ids_a = self._ids({'is_checked': 'true'}, self.user_a)
        self.assertEqual(len(ids_a), len(set(ids_a)))

    def test_anonymous_user_gets_no_checked_contracts(self):
        self.assertEqual(self._ids({'is_checked': 'true'}, AnonymousUser()), [])

    def test_without_filter_returns_all_contracts(self):
        all_ids = {self.only_a.id, self.only_b.id, self.both.id, self.nobody.id}
        self.assertTrue(all_ids.issubset(set(self._ids({}, self.user_a))))
        self.assertTrue(all_ids.issubset(set(self._ids({'is_checked': 'false'}, self.user_a))))
