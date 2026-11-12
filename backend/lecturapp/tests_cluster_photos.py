import base64
import io
import json
import shutil
import tempfile

from django.conf import settings
from django.test import TestCase, override_settings
from PIL import Image

from lecturapp.models import ReadingOperator
from service.models import Cluster, ClusterDocumentationFile, ClusterNozzle, Property, SupplyPoint

STORAGE = tempfile.mkdtemp()
SERVICES = {**settings.DOCUMENT_MANAGER_SERVICES, 'connection': 'hdd'}


def jpeg_base64(size=(1200, 900)):
    buffer = io.BytesIO()
    Image.new('RGB', size, 'green').save(buffer, 'JPEG')
    return 'data:image/jpeg;base64,' + base64.b64encode(buffer.getvalue()).decode()


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
