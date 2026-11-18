import io
import shutil
import tempfile
from unittest import mock

from django.conf import settings
from django.contrib.auth.models import Permission, User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from PIL import Image
from rest_framework.test import APIClient

from fraud.models import Fraud, FraudImage, FraudReport
from fraud.views import fraud_image_view

STORAGE = tempfile.mkdtemp()
SERVICES = {**settings.DOCUMENT_MANAGER_SERVICES, 'fraud': 'hdd'}
URL = '/fraud/fraud-image/'


def image_file(fmt='JPEG', name='foto.jpg'):
    buffer = io.BytesIO()
    Image.new('RGB', (40, 30), 'green').save(buffer, fmt)
    return SimpleUploadedFile(name, buffer.getvalue(), content_type='image/jpeg')


@override_settings(DOCUMENT_STORAGE_PATH=STORAGE, DOCUMENT_MANAGER_SERVICES=SERVICES)
class FraudImageUploadTests(TestCase):
    """Pujada d'imatges a un informe de frau: només imatges JPEG/PNG reals i de mida limitada."""

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(STORAGE, ignore_errors=True)

    def setUp(self):
        user = User.objects.create_user(username='frau', password='x')
        user.user_permissions.add(Permission.objects.get(codename='add_fraud', content_type__app_label='fraud'))
        self.client = APIClient()
        self.client.force_authenticate(user)
        fraud = Fraud.objects.create(token='FR-1')
        self.report = FraudReport.objects.create(token='INF-1', fraud=fraud)

    def _upload(self, data):
        return self.client.post(URL, data, format='multipart')

    def test_puja_jpeg_i_png(self):
        for fmt, name in (('JPEG', 'foto.jpg'), ('PNG', 'foto.png')):
            response = self._upload({'id': self.report.id, 'file': image_file(fmt, name)})
            self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(FraudImage.objects.filter(fraud_report=self.report).count(), 2)

    def test_sense_id_retorna_400(self):
        response = self._upload({'file': image_file()})
        self.assertEqual(response.status_code, 400)

    def test_id_no_numeric_retorna_400(self):
        response = self._upload({'id': 'abc', 'file': image_file()})
        self.assertEqual(response.status_code, 400)

    def test_informe_inexistent_retorna_404(self):
        response = self._upload({'id': self.report.id + 999, 'file': image_file()})
        self.assertEqual(response.status_code, 404)

    def test_informe_sense_frau_retorna_404(self):
        report = FraudReport.objects.create(token='INF-2')
        response = self._upload({'id': report.id, 'file': image_file()})
        self.assertEqual(response.status_code, 404)

    def test_sense_fitxer_retorna_400(self):
        response = self._upload({'id': self.report.id})
        self.assertEqual(response.status_code, 400)

    def test_fitxer_que_no_es_imatge_retorna_400(self):
        fake = SimpleUploadedFile('foto.jpg', b'%PDF-1.4 no soc una imatge', content_type='image/jpeg')
        response = self._upload({'id': self.report.id, 'file': fake})
        self.assertEqual(response.status_code, 400)

    def test_format_no_permes_retorna_400(self):
        response = self._upload({'id': self.report.id, 'file': image_file('GIF', 'foto.jpg')})
        self.assertEqual(response.status_code, 400)

    def test_fitxer_massa_gran_retorna_413(self):
        with mock.patch.object(fraud_image_view, 'MAX_FRAUD_IMAGE_BYTES', 10):
            response = self._upload({'id': self.report.id, 'file': image_file()})
        self.assertEqual(response.status_code, 413)
        self.assertFalse(FraudImage.objects.exists())
