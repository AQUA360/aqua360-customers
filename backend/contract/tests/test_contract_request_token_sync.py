from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase

from contract.utils import contract_token_service as service


def _instance(token='01234', **overrides):
    data = dict(
        pk=1,
        token=token,
        status=SimpleNamespace(token='1'),
        is_change_of_name=False,
        keep_same_code=False,
        save=mock.Mock(),
    )
    data.update(overrides)
    return SimpleNamespace(**data)


KWARGS = {'company_id': 1, 'use_type_id': 2, 'client_type_id': 3}


@mock.patch.object(service, 'contract_request_token_kwargs', return_value=KWARGS)
@mock.patch.object(service, '_is_contract_request_closed', return_value=False)
@mock.patch.object(service, 'next_contract_request_token', return_value='60001')
class SyncContractRequestTokenTests(SimpleTestCase):

    def test_without_personalized_hook_token_is_untouched(self, next_token, *_):
        instance = _instance()
        with mock.patch.object(service.name_utils, 'contract_request_token_matches', None):
            self.assertEqual(service.sync_contract_request_token(instance), ('01234', False))
        next_token.assert_not_called()
        instance.save.assert_not_called()

    def test_token_kept_when_still_matching(self, next_token, *_):
        instance = _instance()
        matches = mock.Mock(return_value=True)
        with mock.patch.object(service.name_utils, 'contract_request_token_matches', matches):
            self.assertEqual(service.sync_contract_request_token(instance), ('01234', False))
        matches.assert_called_once_with('01234', **KWARGS)
        next_token.assert_not_called()
        instance.save.assert_not_called()

    def test_token_regenerated_when_no_longer_matching(self, next_token, *_):
        instance = _instance()
        with mock.patch.object(service.name_utils, 'contract_request_token_matches', mock.Mock(return_value=False)):
            self.assertEqual(service.sync_contract_request_token(instance), ('60001', True))
        self.assertEqual(instance.token, '60001')
        instance.save.assert_called_once_with(update_fields=['token'])

    def test_closed_request_is_untouched(self, next_token, closed, _):
        closed.return_value = True
        instance = _instance()
        with mock.patch.object(service.name_utils, 'contract_request_token_matches', mock.Mock(return_value=False)):
            self.assertEqual(service.sync_contract_request_token(instance), ('01234', False))
        instance.save.assert_not_called()

    def test_change_of_name_keeping_code_is_untouched(self, next_token, *_):
        instance = _instance(is_change_of_name=True, keep_same_code=True)
        with mock.patch.object(service.name_utils, 'contract_request_token_matches', mock.Mock(return_value=False)):
            self.assertEqual(service.sync_contract_request_token(instance), ('01234', False))
        instance.save.assert_not_called()
