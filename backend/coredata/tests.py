import json
from pathlib import Path

from django.test import TestCase

from coredata.aca_street_types import (
    ACA_CODES,
    ACA_STREET_TYPES,
    LEGACY_ALIASES,
    code_from_street_name,
    code_from_token,
)
from coredata.models import StreetType
from coredata.serializers import StreetSerializer, StreetTypeSerializer
from coredata.street_types import resolve_street_type


class AcaStreetTypeListTests(TestCase):
    """La llista de l'ACA és una constant: si algú la toca, aquests tests ho han de dir."""

    def test_te_71_codis_unics(self):
        self.assertEqual(len(ACA_STREET_TYPES), 71)
        self.assertEqual(len(ACA_CODES), 71)
        self.assertEqual(len({name for _pk, _c, name in ACA_STREET_TYPES}), 71)
        self.assertEqual([pk for pk, _c, _n in ACA_STREET_TYPES], list(range(1, 72)))

    def test_cap_alies_apunta_fora_de_la_llista(self):
        fora = sorted({code for code in LEGACY_ALIASES.values() if code not in ACA_CODES})
        self.assertEqual(fora, [])

    def test_codis_coneguts(self):
        self.assertEqual(code_from_token("CR"), "CR")       # carrer
        self.assertEqual(code_from_token("Ctra."), "CA")    # carretera
        self.assertEqual(code_from_token("PZ"), "PL")       # plaça, grafia castellana
        self.assertEqual(code_from_token("Carrer"), "CR")   # pel nom
        self.assertIsNone(code_from_token("VEI"))           # veïnat no és tipus de via de l'ACA
        self.assertIsNone(code_from_token(""))

    def test_prefix_del_nom(self):
        self.assertEqual(code_from_street_name("PLAÇA MAJOR, 12"), ("PL", "MAJOR, 12"))
        self.assertEqual(code_from_street_name("C/ MAJOR"), ("CR", "MAJOR"))
        self.assertEqual(code_from_street_name("Ctra. de Manresa"), ("CA", "de Manresa"))
        self.assertEqual(code_from_street_name("SERRA DE PUIGFRED"), (None, "SERRA DE PUIGFRED"))

    def test_prefix_mal_escrit(self):
        # grafies reals trobades en dades importades
        self.assertEqual(code_from_street_name("C: Torras i Bages"), ("CR", "Torras i Bages"))
        self.assertEqual(code_from_street_name("C, Montseny"), ("CR", "Montseny"))
        self.assertEqual(code_from_street_name("Pça C. St. C.Nicaragua"), ("PL", "C. St. C.Nicaragua"))
        self.assertEqual(code_from_street_name("G.V. Corts Catalanes, 1180"), ("GV", "Corts Catalanes, 1180"))
        self.assertEqual(code_from_street_name("P.I. Can Forns"), ("PO", "Can Forns"))

    def test_dos_prefixos_seguits(self):
        # Hi ha un carrer que l'ERP va escriure «CR CL AFORES»: mana el primer tipus i
        # el segon nomes s'ha de treure del nom.
        self.assertEqual(code_from_street_name("CR CL AFORES"), ("CR", "AFORES"))

    def test_descripcio_sencera_de_l_aca_al_davant(self):
        self.assertEqual(code_from_street_name("Apartat de Correus 341"), ("AP", "341"))
        self.assertEqual(code_from_street_name("Gran Via de les Corts"), ("GV", "de les Corts"))

    def test_el_nom_sencer_es_un_tipus(self):
        # Hi ha un carrer que es diu, literalment, «CARRETERA».
        self.assertEqual(code_from_street_name("CARRETERA"), ("CA", ""))
        self.assertEqual(code_from_street_name("Ctra."), ("CA", ""))

    def test_el_que_no_es_un_tipus_no_s_hi_forca(self):
        # «PI DE LES TRES BRANQUES» es un nom de carrer, no el tipus «PI».
        self.assertEqual(
            code_from_street_name("PI DE LES TRES BRANQUES"), (None, "PI DE LES TRES BRANQUES")
        )
        self.assertEqual(code_from_street_name("SORTIDOR 38264001"), (None, "SORTIDOR 38264001"))
        self.assertEqual(code_from_street_name("Jacint Verdaguer"), (None, "Jacint Verdaguer"))


class ResolveStreetTypeTests(TestCase):
    """El catàleg ja no l'omple cap migració: el porta el fixture de `initial_data/ca/`.
    Aquí es munta des de la mateixa llista de l'ACA, i `StreetTypeCatalogFixtureTests`
    comprova a part que el fixture que es distribueix hi coincideix codi a codi."""

    @classmethod
    def setUpTestData(cls):
        StreetType.objects.bulk_create([
            StreetType(id=pk, abbreviation=code, aca_abbreviation=code, name=name)
            for pk, code, name in ACA_STREET_TYPES
        ])

    def test_resol_contra_el_cataleg_i_no_crea_res(self):
        abans = StreetType.objects.count()
        self.assertEqual(resolve_street_type("PZ").aca_abbreviation, "PL")
        self.assertEqual(resolve_street_type(None, "Carretera").aca_abbreviation, "CA")
        self.assertEqual(resolve_street_type(None, "C/ MAJOR").aca_abbreviation, "CR")
        self.assertIsNone(resolve_street_type("VEI", "Veïnat"))
        self.assertIsNone(resolve_street_type(None, None))
        self.assertEqual(StreetType.objects.count(), abans)


class StreetTypeSerializerTests(ResolveStreetTypeTests):
    """Un tipus que no es reconeix ha de quedar en None, no en un 500.

    DRF afirma que Serializer.validate() no retorni None. `to_internal_value` sí que
    pot tornar None (catàleg tancat): run_validation ho ha de tractar abans d'aquesta
    afirmació, que és el que petava a POST /service/meter/.
    """

    def test_tipus_reconegut(self):
        serializer = StreetTypeSerializer(data={"abbreviation": "PZ", "name": "Plaça"})
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data.aca_abbreviation, "PL")

    def test_tipus_no_reconegut_al_recurs_arrel_es_un_400(self):
        serializer = StreetTypeSerializer(data={"abbreviation": "VEI", "name": "Veïnat"})
        self.assertFalse(serializer.is_valid())

    def test_tipus_no_reconegut_anidat_no_peta(self):
        abans = StreetType.objects.count()
        serializer = StreetSerializer(data={
            "name": "Major",
            "type": {"abbreviation": "VEI", "name": "Veïnat"},
        })
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertIsNone(serializer.validated_data["type"])
        self.assertEqual(StreetType.objects.count(), abans)

    def test_reenvia_la_fila_per_id_si_l_abreviacio_no_resol(self):
        carrer = StreetType.objects.get(aca_abbreviation="CR")
        serializer = StreetSerializer(data={
            "name": "Major",
            "type": {"id": carrer.id, "abbreviation": "VEI", "name": "Veïnat"},
        })
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data["type"].id, carrer.id)


class StreetTypeCatalogFixtureTests(TestCase):
    """El catàleg que es distribueix ha de ser EXACTAMENT la llista de l'ACA.

    La taula no està bloquejada a la base de dades (decisió de Raul, 14/09/2026): el que la
    manté neta és que cap camí del codi hi escriu i que el fixture que es carrega a cada
    instal·lació porta els 71 codis i cap més. Si el fixture i la llista es separen, aquest
    test salta.
    """

    FIXTURE = Path(__file__).resolve().parent.parent / "initial_data" / "ca" / "coredata.StreetType.json"

    def _fixture(self):
        return json.loads(self.FIXTURE.read_text(encoding="utf-8"))

    def test_el_fixture_porta_els_71_codis(self):
        rows = self._fixture()
        self.assertEqual(len(rows), len(ACA_STREET_TYPES))
        self.assertEqual(
            {r["fields"]["aca_abbreviation"] for r in rows}, set(ACA_CODES)
        )

    def test_el_fixture_coincideix_codi_a_codi(self):
        rows = {r["pk"]: r["fields"] for r in self._fixture()}
        for pk, code, name in ACA_STREET_TYPES:
            self.assertIn(pk, rows, "falta el pk {} ({})".format(pk, code))
            self.assertEqual(rows[pk]["aca_abbreviation"], code)
            self.assertEqual(rows[pk]["name"], name)

    def test_cap_pk_repetida_al_fixture(self):
        pks = [r["pk"] for r in self._fixture()]
        self.assertEqual(len(pks), len(set(pks)))


class SpanishBicTests(TestCase):
    """El catàleg `Bank.bic` només porta el codi de 4 lletres: el BIC bo surt del registre de schwifty."""

    def test_bic_complet_amb_o_sense_zeros(self):
        from coredata.utils.iban_validator_utils import get_spanish_bic
        self.assertEqual(get_spanish_bic('0081'), 'BSABESBB')
        self.assertEqual(get_spanish_bic('81'), 'BSABESBB')

    def test_codi_desconegut_o_invalid(self):
        from coredata.utils.iban_validator_utils import get_spanish_bic
        self.assertIsNone(get_spanish_bic('9999'))
        self.assertIsNone(get_spanish_bic('ABCD'))
        self.assertIsNone(get_spanish_bic(''))

    def test_bic_del_compte_per_documents(self):
        from coredata.utils.iban_validator_utils import resolve_account_bic
        iban = 'ES97 0081 0000 0000 0000 0000'
        # El SWIFT propi del compte mana i es completa a 11 caràcters
        self.assertEqual(resolve_account_bic(iban, 'caixesbb', 'BSAB'), 'CAIXESBBXXX')
        # El codi de 4 lletres del catàleg no és un BIC: es passa al registre oficial
        self.assertEqual(resolve_account_bic(iban, '', 'BSAB'), 'BSABESBBXXX')
        self.assertEqual(resolve_account_bic(iban, None, 'BSABESBB'), 'BSABESBBXXX')
        # IBAN estranger sense SWIFT: no s'endevina res
        self.assertIsNone(resolve_account_bic('DE89370400440532013000', None, None))
        self.assertEqual(resolve_account_bic('DE89370400440532013000', 'COBADEFFXXX'), 'COBADEFFXXX')


class PersonBankResolveSwiftTests(TestCase):
    """`resolve` amb el mateix IBAN: s'aplica el SWIFT nou al compte, sense duplicar-lo ni tocar el titular."""

    IBAN = 'ES9121000418450200051332'

    def setUp(self):
        from django.contrib.auth import get_user_model
        from rest_framework.test import APIClient
        from billing.models import CommitmentDepositStatus
        from coredata.models import ConfigProject, Person, PersonBank

        # La resposta serialitza la persona, que compta els dipòsits pendents
        CommitmentDepositStatus.objects.create(token='PAID')
        ConfigProject.objects.create(token='commitment_deposit_status_paid_token', value='PAID')

        user = get_user_model().objects.create_superuser('resolve', 'resolve@example.com', 'x')
        self.client = APIClient()
        self.client.force_authenticate(user)
        self.person = Person.objects.create(token='P-RESOLVE', name='Titular')
        self.account = PersonBank.objects.create(
            person=self.person, iban=self.IBAN, swift='CAIX', name='Titular', is_active=True
        )

    def _resolve(self, **extra):
        payload = {'person': self.person.id, 'iban': self.IBAN, 'current_id': self.account.id, **extra}
        return self.client.post('/coredata/person-bank/resolve/', payload, format='json')

    def test_nomes_canvia_el_swift(self):
        response = self._resolve(swift='caixesbbxxx', name='Un altre nom')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['reused'])
        self.assertTrue(response.data['swift_updated'])
        self.account.refresh_from_db()
        self.assertEqual(self.account.swift, 'CAIXESBBXXX')
        self.assertEqual(self.account.name, 'Titular')
        self.assertEqual(self.person.banks.count(), 1)

    def test_swift_buit_no_esborra_el_desat(self):
        response = self._resolve(swift='')
        self.assertFalse(response.data['swift_updated'])
        self.account.refresh_from_db()
        self.assertEqual(self.account.swift, 'CAIX')
