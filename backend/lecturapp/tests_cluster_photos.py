import base64
import io
import json
import shutil
import tempfile

from django.conf import settings
from django.test import TestCase, override_settings
from PIL import Image

from lecturapp.models import ReadingOperator
from django.core.files.base import ContentFile

from documentmanager.utils.main_utils import upload_document
from service.models import Cluster, ClusterDocumentationFile, ClusterNozzle, Property, SupplyPoint

STORAGE = tempfile.mkdtemp()
SERVICES = {**settings.DOCUMENT_MANAGER_SERVICES, 'connection': 'hdd'}


def image_base64(size=(1200, 900), fmt='JPEG'):
    buffer = io.BytesIO()
    Image.new('RGB', size, 'green').save(buffer, fmt)
    return f'data:image/{fmt.lower()};base64,' + base64.b64encode(buffer.getvalue()).decode()


def jpeg_base64(size=(1200, 900)):
    return image_base64(size)


def decode_image(data_url):
    return Image.open(io.BytesIO(base64.b64decode(data_url.split(',', 1)[1])))


@override_settings(DOCUMENT_STORAGE_PATH=STORAGE, DOCUMENT_MANAGER_SERVICES=SERVICES)
class LecturappClusterPhotosTests(TestCase):
    """Apartat «Bateries» de la finca al Lecturapp: dades i fotos sota demanda."""

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(STORAGE, ignore_errors=True)

    def setUp(self):
        operator = ReadingOperator.objects.create(name='Op', surname='Test', username='op-bateries', password='x')
        self.headers = {'HTTP_X_APP_TOKEN': operator.generate_token().token}
        self.property = Property.objects.create(name='Finca')
        # Bateria lligada a la finca a través d'un punt de subministrament
        self.cluster = Cluster.objects.create(token='BAT-1', nb_nozzles=4)
        nozzle = ClusterNozzle.objects.create(cluster=self.cluster, token='B1', row=1, col=2)
        SupplyPoint.objects.create(token='SP-1', property=self.property, cluster_nozzle=nozzle)
        # Bateria lligada directament a la finca
        self.direct_cluster = Cluster.objects.create(token='BAT-2', property=self.property)
        # Bateries que no han de sortir
        Cluster.objects.create(token='BAT-INACTIVA', property=self.property, is_active=False)
        Cluster.objects.create(token='BAT-ALTRA', property=Property.objects.create(name='Altra'))

    def _upload(self, cluster, photo):
        return self.client.post(
            f'/lecturapp/clusters/{cluster.id}/photos/', json.dumps({'photo': photo}),
            content_type='application/json', **self.headers,
        )

    def test_llista_les_bateries_de_la_finca_sense_imatges(self):
        self.assertEqual(self._upload(self.cluster, jpeg_base64()).status_code, 201)

        response = self.client.get(f'/lecturapp/properties/{self.property.id}/clusters/', **self.headers)

        self.assertEqual(response.status_code, 200)
        results = response.json()['results']
        self.assertEqual([c['token'] for c in results], ['BAT-1', 'BAT-2'])
        self.assertEqual(results[0]['nozzles'][0]['token'], 'B1')
        self.assertEqual(len(results[0]['photos']), 1)
        self.assertNotIn('photo', results[0]['photos'][0])

    def test_puja_la_foto_i_la_dona_en_miniatura_o_original(self):
        photo_id = self._upload(self.cluster, jpeg_base64()).json()['id']
        self.assertTrue(ClusterDocumentationFile.objects.filter(id=photo_id, cluster=self.cluster).exists())

        url = f'/lecturapp/clusters/{self.cluster.id}/photos/{photo_id}/'
        thumbnail = self.client.get(url + '?size=thumbnail', **self.headers).json()['photo']
        original = self.client.get(url, **self.headers).json()['photo']

        self.assertLessEqual(max(decode_image(thumbnail).size), 300)
        self.assertEqual(decode_image(original).size, (1200, 900))

    def test_no_dona_la_foto_si_no_es_de_la_bateria(self):
        photo_id = self._upload(self.cluster, jpeg_base64()).json()['id']
        response = self.client.get(f'/lecturapp/clusters/{self.direct_cluster.id}/photos/{photo_id}/', **self.headers)
        self.assertEqual(response.status_code, 404)

    def test_rebutja_fitxers_que_no_son_imatges(self):
        response = self._upload(self.cluster, base64.b64encode(b'no soc una imatge').decode())
        self.assertEqual(response.status_code, 400)
        self.assertFalse(ClusterDocumentationFile.objects.exists())

    def test_cal_estar_autenticat(self):
        response = self.client.get(f'/lecturapp/properties/{self.property.id}/clusters/')
        self.assertEqual(response.status_code, 401)

    def test_no_dona_documents_que_no_son_imatges(self):
        document = upload_document(
            ContentFile(b'%PDF-1.4 informe', name='informe.pdf'), 'CLUSTER', 'CLUSTER',
            self.cluster.id, self.cluster.token, '', 'hdd', 'informe.pdf',
        )
        pdf = ClusterDocumentationFile.objects.create(cluster=self.cluster, file=document)
        response = self.client.get(f'/lecturapp/clusters/{self.cluster.id}/photos/{pdf.id}/', **self.headers)
        self.assertEqual(response.status_code, 404)

    def test_desa_les_fotos_sempre_en_jpeg(self):
        photo = self._upload(self.cluster, image_base64(fmt='PNG')).json()
        self.assertTrue(photo['name'].endswith('.jpg'))
        original = self.client.get(f'/lecturapp/clusters/{self.cluster.id}/photos/{photo["id"]}/', **self.headers).json()['photo']
        self.assertTrue(original.startswith('data:image/jpeg;base64,'))
        self.assertEqual(decode_image(original).format, 'JPEG')

    def test_rebutja_data_url_sense_contingut_i_fotos_massa_grans(self):
        self.assertEqual(self._upload(self.cluster, 'data:').status_code, 400)
        too_large = base64.b64encode(b'x' * (1600 * 1024)).decode()
        self.assertEqual(self._upload(self.cluster, too_large).status_code, 413)
        self.assertFalse(ClusterDocumentationFile.objects.exists())

    def test_cos_per_sobre_del_limit_de_django_respon_413(self):
        with self.settings(DATA_UPLOAD_MAX_MEMORY_SIZE=1000):
            response = self._upload(self.cluster, jpeg_base64())
        self.assertEqual(response.status_code, 413)
