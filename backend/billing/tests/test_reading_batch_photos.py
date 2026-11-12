import base64
import shutil
import tempfile
from datetime import date

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings

from billing.models import Reading, ReadingBatch
from billing.utils.reading_batch_service import SETUP_FILTERS, get_setup_filter_supply_point_ids
from billing.views.reading_batch_setup_view import get_photo_readings
from service.models import SupplyPoint

MEDIA_ROOT = tempfile.mkdtemp()
PHOTO_BYTES = b'\xff\xd8\xff\xe0 foto de prova'


@override_settings(MEDIA_ROOT=MEDIA_ROOT)
class ReadingBatchPhotosTests(TestCase):
    """Apartat «Lectures amb foto» del resum del lot de lectures."""

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA_ROOT, ignore_errors=True)

    def setUp(self):
        self.batch = ReadingBatch.objects.create(name='Lot amb fotos')
        self.with_photo = SupplyPoint.objects.create(token='SP-FOTO')
        self.without_photo = SupplyPoint.objects.create(token='SP-SENSE')
        self.reading = Reading.objects.create(
            batch=self.batch, supply_point=self.with_photo, is_control=False,
            reading_date=date(2026, 10, 1), reading_value=10,
            photo=SimpleUploadedFile('foto.jpg', PHOTO_BYTES, content_type='image/jpeg'),
        )
        Reading.objects.create(
            batch=self.batch, supply_point=self.without_photo, is_control=False,
            reading_date=date(2026, 10, 1), reading_value=20,
        )

    def test_el_filtre_nomes_inclou_les_lectures_amb_foto(self):
        self.assertIn('photo', SETUP_FILTERS)
        ids = get_setup_filter_supply_point_ids(self.batch, 'photo')
        self.assertEqual(ids, {self.with_photo.id})

    def test_no_compta_les_lectures_de_control(self):
        self.reading.is_control = True
        self.reading.save(update_fields=['is_control'])
        self.assertEqual(get_setup_filter_supply_point_ids(self.batch, 'photo'), set())

    def test_la_galeria_retorna_la_foto_de_cada_lectura(self):
        supply_points = SupplyPoint.objects.filter(id__in=[self.with_photo.id, self.without_photo.id])
        result = get_photo_readings(self.batch, supply_points)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['id'], self.reading.id)
        self.assertEqual(result[0]['supply_point_token'], 'SP-FOTO')
        self.assertEqual(
            result[0]['photo'],
            'data:image/jpeg;base64,' + base64.b64encode(PHOTO_BYTES).decode('utf-8'),
        )
