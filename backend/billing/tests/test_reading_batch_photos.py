import base64
import io
import shutil
import tempfile
from datetime import date

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from PIL import Image
from rest_framework.test import APIRequestFactory, force_authenticate

from billing.models import Reading, ReadingBatch
from billing.utils.reading_batch_service import get_photo_readings_queryset
from billing.views.reading_batch_setup_view import ReadingBatchSetupViewSet
from service.models import SupplyPoint

MEDIA_ROOT = tempfile.mkdtemp()


def jpeg_bytes(size=(1200, 900)):
    buffer = io.BytesIO()
    Image.new('RGB', size, 'blue').save(buffer, 'JPEG')
    return buffer.getvalue()


def decode_image(data_url):
    return Image.open(io.BytesIO(base64.b64decode(data_url.split(',', 1)[1])))


@override_settings(MEDIA_ROOT=MEDIA_ROOT)
class ReadingBatchPhotosTests(TestCase):
    """Apartat «Lectures amb foto» del resum del lot de lectures."""

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA_ROOT, ignore_errors=True)

    def setUp(self):
        self.photo_bytes = jpeg_bytes()
        self.batch = ReadingBatch.objects.create(name='Lot amb fotos')
        self.with_photo = SupplyPoint.objects.create(token='SP-FOTO')
        self.without_photo = SupplyPoint.objects.create(token='SP-SENSE')
        self.reading = self._reading(self.with_photo, photo=True)
        self.second_reading = self._reading(self.with_photo, photo=True)
        self._reading(self.without_photo)
        self.user = get_user_model().objects.create_superuser('admin-fotos', 'a@example.com', 'x')
        self.factory = APIRequestFactory()

    def _reading(self, supply_point, photo=False, batch=None):
        return Reading.objects.create(
            batch=batch or self.batch, supply_point=supply_point, is_control=False,
            reading_date=date(2026, 10, 1), reading_value=10,
            photo=SimpleUploadedFile('foto.jpg', self.photo_bytes, content_type='image/jpeg') if photo else None,
        )

    def _get(self, view_action, path, **kwargs):
        request = self.factory.get(path)
        force_authenticate(request, user=self.user)
        return ReadingBatchSetupViewSet.as_view({'get': view_action})(request, **kwargs)

    def test_compta_lectures_amb_foto_i_no_les_de_control(self):
        # Dues lectures amb foto del mateix punt compten dues vegades
        self.assertEqual(get_photo_readings_queryset(self.batch).count(), 2)
        self.second_reading.is_control = True
        self.second_reading.save(update_fields=['is_control'])
        self.assertEqual(get_photo_readings_queryset(self.batch).count(), 1)

    def test_la_galeria_pagina_per_lectures_i_retorna_miniatures(self):
        response = self._get('retrieve', '/?readings=photo', id=self.batch.id)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['count'], 2)
        self.assertEqual([r['id'] for r in response.data['results']], [self.reading.id, self.second_reading.id])
        thumbnail = decode_image(response.data['results'][0]['thumbnail'])
        self.assertLessEqual(max(thumbnail.size), 400)
        self.assertNotIn('photo', response.data['results'][0])

    def test_la_foto_original_nomes_es_dona_per_lectures_de_la_galeria_del_lot(self):
        response = self._get('photo', '/', id=self.batch.id, reading_id=self.reading.id)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(decode_image(response.data['photo']).size, (1200, 900))

        other_batch = ReadingBatch.objects.create(name='Un altre lot')
        response = self._get('photo', '/', id=other_batch.id, reading_id=self.reading.id)
        self.assertEqual(response.status_code, 404)
