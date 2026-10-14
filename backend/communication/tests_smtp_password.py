import os
from unittest.mock import patch

from cryptography.fernet import Fernet
from django.test import TestCase, override_settings

from communication.models import CommunicationUseType
from communication.serializers.communication_serializer import CommunicationSerializer
from communication.utils.communication_service import _send_via_smtp, get_smtp_password
from service.models import Company, CompanyConfig, CompanyConfigEmail
from service.serializers.value_objects_serializer import CompanyConfigEmailSerializer, CompanyConfigSerializer

TEST_KEY = Fernet.generate_key().decode()
ENV = {
    'EMAIL_PASSWORD_TEST_CONFIG': 'config-password',
    'EMAIL_PASSWORD_TEST_BILLING': 'billing-env-password',
}


@override_settings(EMAIL_HOST_PASSWORD='host-password', SMTP_PASSWORD_ENCRYPTION_KEY=TEST_KEY)
@patch.dict(os.environ, ENV)
class SmtpPasswordPerEmailTest(TestCase):
    """Cada correu de la configuració d'empresa pot tenir la seva contrasenya SMTP."""

    @classmethod
    def setUpTestData(cls):
        cls.config = CompanyConfig.objects.create(
            token='EMAIL_PASSWORD_TEST_CONFIG', mail_send_smtp_server='smtp.example.com', mail_send_smtp_port=587,
        )
        Company.objects.create(name='Company SMTP test', config=cls.config)
        cls.use_type = CommunicationUseType.objects.create(name='SMTP test', token='smtp-test')
        cls.default_email = CompanyConfigEmail.objects.create(
            company_config=cls.config, mail_send_mail='info@example.com', is_default=True, use_type=cls.use_type,
        )
        cls.billing_email = CompanyConfigEmail.objects.create(
            company_config=cls.config, mail_send_mail='billing@example.com', token='EMAIL_PASSWORD_TEST_BILLING',
            use_type=cls.use_type,
        )

    def _send(self, config_email):
        with patch('django.core.mail.backends.smtp.EmailBackend') as backend, \
                patch('communication.utils.communication_service.EmailMultiAlternatives'):
            _send_via_smtp(['to@example.com'], 'Assumpte', '', 'from@example.com', [], self.config, config_email)
        return backend.call_args.kwargs['username'], backend.call_args.kwargs['password']

    # --- Ordre de cerca de la contrasenya

    def test_stored_password_has_priority(self):
        self.billing_email.set_password('billing-stored-password')
        self.billing_email.save()
        self.assertEqual(self._send(self.billing_email), ('billing@example.com', 'billing-stored-password'))

    def test_env_token_of_the_email(self):
        self.assertEqual(self._send(self.billing_email), ('billing@example.com', 'billing-env-password'))

    def test_config_token_and_default_email(self):
        self.assertEqual(self._send(None), ('info@example.com', 'config-password'))

    def test_falls_back_to_host_password(self):
        self.assertEqual(get_smtp_password('EMAIL_PASSWORD_TEST_MISSING', None), 'host-password')
        self.assertEqual(get_smtp_password(None, None), 'host-password')

    def test_only_prefixed_env_variables_are_read(self):
        # El token es configura des de la pantalla: no pot apuntar a altres secrets.
        with patch.dict(os.environ, {'SOME_OTHER_SECRET': 'secret'}):
            self.assertEqual(get_smtp_password('SOME_OTHER_SECRET', None), 'host-password')
        self.assertEqual(get_smtp_password('SECRET_KEY', None), 'host-password')
        self.assertEqual(get_smtp_password('SMTP_PASSWORD_ENCRYPTION_KEY', None), 'host-password')

    def test_without_default_email_uses_first_address(self):
        CompanyConfigEmail.objects.filter(id=self.default_email.id).update(is_default=False)
        username, _ = self._send(None)
        self.assertIsInstance(username, str)

    # --- Xifratge

    def test_password_is_stored_encrypted(self):
        self.billing_email.set_password('billing-stored-password')
        self.billing_email.save()
        self.billing_email.refresh_from_db()
        self.assertNotIn('billing-stored-password', self.billing_email.encrypted_password)
        self.assertEqual(self.billing_email.get_password(), 'billing-stored-password')

    def test_undecryptable_password_falls_back(self):
        self.billing_email.set_password('billing-stored-password')
        self.billing_email.save()
        with override_settings(SMTP_PASSWORD_ENCRYPTION_KEY=Fernet.generate_key().decode()):
            self.assertIsNone(self.billing_email.get_password())
            self.assertEqual(self._send(self.billing_email), ('billing@example.com', 'billing-env-password'))

    def test_key_rotation(self):
        self.billing_email.set_password('billing-stored-password')
        self.billing_email.save()
        with override_settings(SMTP_PASSWORD_ENCRYPTION_KEY=f'{Fernet.generate_key().decode()},{TEST_KEY}'):
            self.assertEqual(self.billing_email.get_password(), 'billing-stored-password')

    # --- API

    def _payload(self, **billing_changes):
        emails = [
            {'id': self.default_email.id, 'mail_send_mail': 'info@example.com', 'mail_send_user': 'info@example.com',
             'is_default': True, 'use_type': {'value': self.use_type.id}},
            {'id': self.billing_email.id, 'mail_send_mail': 'billing@example.com', 'mail_send_user': 'billing@example.com',
             'is_default': False, 'use_type': {'value': self.use_type.id}, **billing_changes},
        ]
        return {'config_emails_data': emails}

    def _save_config(self, payload):
        serializer = CompanyConfigSerializer(self.config, data=payload, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        self.billing_email.refresh_from_db()

    def test_api_saves_keeps_and_clears_password(self):
        self._save_config(self._payload(password='new-password'))
        self.assertEqual(self.billing_email.get_password(), 'new-password')

        self._save_config(self._payload(password=''))
        self.assertEqual(self.billing_email.get_password(), 'new-password')

        self._save_config(self._payload(clear_password=True))
        self.assertFalse(self.billing_email.has_password)

    def test_api_never_returns_password(self):
        self.billing_email.set_password('billing-stored-password')
        self.billing_email.save()
        data = CompanyConfigEmailSerializer(self.billing_email).data
        self.assertTrue(data['has_password'])
        self.assertNotIn('encrypted_password', data)
        self.assertNotIn('password', data)
        self.assertNotIn('billing-stored-password', str(CompanyConfigSerializer(self.config).data))
        self.assertNotIn('encrypted_password', CommunicationSerializer().fields['company_config_email'].to_representation(self.billing_email))

    def test_api_without_key_rejects_password(self):
        with override_settings(SMTP_PASSWORD_ENCRYPTION_KEY=''):
            serializer = CompanyConfigSerializer(self.config, data=self._payload(password='new-password'), partial=True)
            serializer.is_valid(raise_exception=True)
            with self.assertRaisesMessage(Exception, 'SMTP_PASSWORD_ENCRYPTION_KEY'):
                serializer.save()

    def test_api_keeps_a_single_default_email(self):
        payload = self._payload(is_default=True)
        payload['config_emails_data'].append(
            {'id': None, 'mail_send_mail': 'new@example.com', 'mail_send_user': 'new@example.com',
             'is_default': True, 'use_type': {'value': self.use_type.id}}
        )
        self._save_config(payload)
        defaults = list(self.config.company_config_emails.filter(is_default=True).values_list('mail_send_mail', flat=True))
        self.assertEqual(defaults, ['info@example.com'])
