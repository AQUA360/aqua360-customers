import importlib

from django.test import TestCase

from service.models import ClusterDocumentationType

opscript = importlib.import_module('service.opscripts.0002_load_cluster_documentation_types')


class ClusterDocumentationTypesOpscriptTests(TestCase):
    """Tipus de document de bateria per defecte («Fotos»)."""

    def test_crea_el_tipus_fotos_per_defecte(self):
        opscript.run()

        photos = ClusterDocumentationType.objects.get(token='photos')
        self.assertEqual(photos.name, 'Fotos')
        self.assertTrue(photos.is_default)
        self.assertTrue(photos.is_active)

    def test_no_duplica_ni_modifica_el_que_ja_existeix(self):
        ClusterDocumentationType.objects.create(token='photos', name='Fotografies', is_default=False)

        opscript.run()

        self.assertEqual(ClusterDocumentationType.objects.filter(token='photos').count(), 1)
        self.assertEqual(ClusterDocumentationType.objects.get(token='photos').name, 'Fotografies')
