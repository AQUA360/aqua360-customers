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


class PersonBankResolveTests(TestCase):
    """`resolve`: amb el mateix IBAN es desen totes les dades al compte; amb un IBAN nou se'n crea un altre."""

    IBAN = 'ES9121000418450200051332'
    OTHER_IBAN = 'ES7921000813610123456789'

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
            person=self.person, iban=self.IBAN, swift='CAIX', name='Titular', dni='P-RESOLVE', is_active=True
        )

    def _resolve(self, **extra):
        payload = {'person': self.person.id, 'iban': self.IBAN, 'current_id': self.account.id, **extra}
        return self.client.post('/coredata/person-bank/resolve/', payload, format='json')

    def test_mateix_iban_desa_totes_les_dades(self):
        response = self._resolve(
            swift='caixesbbxxx', name='Un altre nom', dni='12345678Z', role='AUTORITZAT', account_number='123'
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['reused'])
        self.assertTrue(response.data['updated'])
        self.account.refresh_from_db()
        self.assertEqual(self.account.swift, 'CAIXESBBXXX')
        self.assertEqual(self.account.name, 'Un altre nom')
        self.assertEqual(self.account.dni, '12345678Z')
        self.assertEqual(self.account.role, 'AUTORITZAT')
        self.assertEqual(self.account.account_number, '123')
        self.assertEqual(self.person.banks.count(), 1)

    def test_sense_canvis_no_marca_updated(self):
        response = self._resolve(name='Titular', dni='P-RESOLVE', swift='')
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data['updated'])

    def test_swift_i_pais_buits_no_esborren_el_desat(self):
        from coredata.models import Country

        country = Country.objects.create(name='Espanya', iso_code='ES')
        self.account.country = country
        self.account.save()
        response = self._resolve(swift='', country=None)
        self.assertFalse(response.data['updated'])
        self.account.refresh_from_db()
        self.assertEqual(self.account.swift, 'CAIX')
        self.assertEqual(self.account.country, country)

    def test_titular_diferent_sense_dni_posa_el_generic(self):
        from coredata.utils.person_bank_utils import DEFAULT_HOLDER_DNI

        self._resolve(name='Un altre titular', dni='')
        self.account.refresh_from_db()
        self.assertEqual(self.account.dni, DEFAULT_HOLDER_DNI)

    def test_iban_nou_crea_compte_i_deixa_l_original(self):
        from coredata.utils.person_bank_utils import DEFAULT_HOLDER_DNI

        response = self._resolve(iban=self.OTHER_IBAN, name='Un altre titular', dni='')
        self.assertEqual(response.status_code, 201)
        self.assertFalse(response.data['reused'])
        self.assertEqual(response.data['dni'], DEFAULT_HOLDER_DNI)
        self.account.refresh_from_db()
        self.assertEqual(self.account.iban, self.IBAN)
        self.assertEqual(self.account.name, 'Titular')
        self.assertEqual(self.person.banks.count(), 2)


class ResolveHolderDniTests(TestCase):
    """DNI per defecte del titular d'un compte quan arriba buit."""

    def setUp(self):
        from coredata.models import Person

        self.person = Person.objects.create(token='11111111H', name='Àngela', surname='Puig  Martí')

    def _resolve(self, dni, name, person=None):
        from coredata.utils.person_bank_utils import resolve_holder_dni

        return resolve_holder_dni(dni, name, person or self.person)

    def test_dni_informat_es_manté(self):
        self.assertEqual(self._resolve(' 12345678Z ', 'Una altra persona'), '12345678Z')

    def test_mateix_titular_fa_servir_el_document_de_la_persona(self):
        self.assertEqual(self._resolve('', 'angela puig marti'), '11111111H')
        self.assertEqual(self._resolve(None, ''), '11111111H')

    def test_titular_diferent_fa_servir_el_generic(self):
        from coredata.utils.person_bank_utils import DEFAULT_HOLDER_DNI

        self.assertEqual(self._resolve('', 'Una altra persona'), DEFAULT_HOLDER_DNI)

    def test_persona_sense_document_fa_servir_el_generic(self):
        from coredata.models import Person
        from coredata.utils.person_bank_utils import DEFAULT_HOLDER_DNI

        person = Person.objects.create(token='', name='Sense document')
        self.assertEqual(self._resolve('', 'Sense document', person), DEFAULT_HOLDER_DNI)


class RecoverLostStreetNumbersTests(TestCase):
    """Opscript 0003: omple els StreetNumber N/R/S buits amb el número del punt de subministrament."""

    def setUp(self):
        from coredata.models import Street, StreetNumberType

        self.types = {t: StreetNumberType.objects.get_or_create(type=t, defaults={'description': t})[0]
                      for t in ('N', 'S', 'SN', 'R')}
        self.street = Street.objects.create(name='Carrer de Prova')

    def _run(self):
        import importlib

        importlib.import_module('coredata.opscripts.0003_recover_lost_street_numbers').run()

    def _street_number(self, number_type, street=None, **fields):
        from coredata.models import StreetNumber

        return StreetNumber.objects.create(street=street or self.street, number_type=self.types[number_type], **fields)

    def _meter_with_supply_point(self, meter_street_number, supply_point_street_number):
        from coredata.models import Address
        from service.models import Meter, SupplyPoint

        meter = Meter.objects.create(code='M1', address_street=meter_street_number.street,
                                     address_street_number=meter_street_number)
        address = Address.objects.create(street=supply_point_street_number.street,
                                         street_number=supply_point_street_number)
        SupplyPoint.objects.create(meter=meter, address=address)
        return meter

    def test_recupera_el_numero_i_el_tipus_del_punt(self):
        lost = self._street_number('N')
        self._meter_with_supply_point(lost, self._street_number('S', number=13, number_suffix='B'))

        self._run()

        lost.refresh_from_db()
        self.assertEqual(lost.number_type.type, 'S')
        self.assertEqual(str(lost), '13-B')

    def test_carrer_duplicat_amb_una_altra_grafia(self):
        from coredata.models import Street

        lost = self._street_number('N', street=Street.objects.create(name='CARRER DE PROVA'))
        self._meter_with_supply_point(lost, self._street_number('N', number=8))

        self._run()

        lost.refresh_from_db()
        self.assertEqual(lost.number, 8)

    def test_no_toca_si_el_carrer_es_diferent(self):
        from coredata.models import Street

        lost = self._street_number('N', street=Street.objects.create(name='Avinguda Llunyana'))
        self._meter_with_supply_point(lost, self._street_number('N', number=8))

        self._run()

        lost.refresh_from_db()
        self.assertIsNone(lost.number)

    def test_no_toca_si_la_font_es_sense_numero_o_hi_ha_discrepancies(self):
        from coredata.models import Address
        from service.models import SupplyPoint

        from_sn = self._street_number('N')
        self._meter_with_supply_point(from_sn, self._street_number('SN'))

        conflict = self._street_number('N')
        meter = self._meter_with_supply_point(conflict, self._street_number('N', number=1))
        SupplyPoint.objects.create(meter=meter, address=Address.objects.create(
            street=self.street, street_number=self._street_number('N', number=2)))

        self._run()

        from_sn.refresh_from_db()
        conflict.refresh_from_db()
        self.assertIsNone(from_sn.number)
        self.assertIsNone(conflict.number)

    def test_no_toca_numeros_correctes_ni_sense_numero(self):
        ok = self._street_number('S', number_suffix='LOCAL')
        sn = self._street_number('SN')
        self._meter_with_supply_point(ok, self._street_number('N', number=5))
        self._meter_with_supply_point(sn, self._street_number('N', number=5))

        self._run()

        ok.refresh_from_db()
        sn.refresh_from_db()
        self.assertEqual(str(ok), 'LOCAL')
        self.assertEqual(sn.number_type.type, 'SN')
        self.assertIsNone(sn.number)


class FillConnectionStreetNumbersTests(TestCase):
    """Opscript 0004: omple el número de les escomeses amb l'adreça del punt o de la bateria."""

    def setUp(self):
        from coredata.models import Street, StreetNumberType
        from service.models import ConnectionInstallationType

        self.types = {t: StreetNumberType.objects.get_or_create(type=t, defaults={'description': t})[0]
                      for t in ('', 'N', 'SN')}
        self.installation_types = {t: ConnectionInstallationType.objects.get_or_create(token=t)[0]
                                   for t in ('cluster', 'individual')}
        self.street = Street.objects.create(name='Carrer de Prova')

    def _run(self):
        import importlib

        importlib.import_module('coredata.opscripts.0004_fill_connection_street_numbers').run()

    def _street_number(self, number_type, street=None, **fields):
        from coredata.models import StreetNumber

        return StreetNumber.objects.create(street=street or self.street, number_type=self.types[number_type], **fields)

    def _connection(self, installation_type, number_type=''):
        from coredata.models import Street
        from service.models import Connection

        # les escomeses importades tenen un carrer propi (duplicat) i un número buit
        street = Street.objects.create(name=self.street.name)
        return Connection.objects.create(
            installation_type=self.installation_types[installation_type], address_street=street,
            address_street_number=self._street_number(number_type, street=street),
        )

    def _supply_point(self, connection, street_number, **fields):
        from coredata.models import Address
        from service.models import SupplyPoint

        address = Address.objects.create(street=street_number.street, street_number=street_number)
        return SupplyPoint.objects.create(connection=connection, address=address, **fields)

    def test_individual_agafa_l_adreca_del_punt(self):
        connection = self._connection('individual')
        source = self._street_number('N', number=7)
        self._supply_point(connection, source)

        self._run()

        connection.refresh_from_db()
        self.assertEqual(connection.address_street_number, source)
        self.assertEqual(connection.address_street, self.street)

    def test_individual_amb_un_altre_carrer_agafa_tota_l_adreca_del_punt(self):
        from coredata.models import Street

        connection = self._connection('individual')
        source = self._street_number('N', street=Street.objects.create(name='Avinguda Completa'), number=3)
        self._supply_point(connection, source)

        self._run()

        connection.refresh_from_db()
        self.assertEqual(connection.address_street.name, 'Avinguda Completa')
        self.assertEqual(connection.address_street_number, source)

    def test_bateria_agafa_l_adreca_de_la_bateria(self):
        from service.models import Cluster, ClusterNozzle

        connection = self._connection('cluster')
        cluster_number = self._street_number('N', number=10)
        cluster = Cluster.objects.create(connection=connection, address_street=self.street,
                                         address_street_number=cluster_number)
        nozzle = ClusterNozzle.objects.create(cluster=cluster, token='1')
        # els punts de les boques tenen números diferents: mana la bateria
        self._supply_point(connection, self._street_number('N', number=1), cluster_nozzle=nozzle)
        self._supply_point(connection, self._street_number('N', number=2), cluster_nozzle=nozzle)

        self._run()

        connection.refresh_from_db()
        self.assertEqual(connection.address_street_number, cluster_number)

    def test_bateria_sense_bateries_agafa_l_adreca_dels_punts(self):
        connection = self._connection('cluster')
        source = self._street_number('N', number=4)
        self._supply_point(connection, source)

        self._run()

        connection.refresh_from_db()
        self.assertEqual(connection.address_street_number, source)

    def test_no_toca_sn_explicit_font_sense_numero_ni_discrepancies(self):
        explicit_sn = self._connection('individual', number_type='SN')
        self._supply_point(explicit_sn, self._street_number('N', number=1))
        from_sn = self._connection('individual')
        self._supply_point(from_sn, self._street_number('SN'))
        conflict = self._connection('individual')
        self._supply_point(conflict, self._street_number('N', number=1))
        self._supply_point(conflict, self._street_number('N', number=2))
        originals = {c.id: c.address_street_number_id for c in (explicit_sn, from_sn, conflict)}

        self._run()

        for connection in (explicit_sn, from_sn, conflict):
            connection.refresh_from_db()
            self.assertEqual(connection.address_street_number_id, originals[connection.id])


class ConfigProjectPermissionTests(TestCase):
    """Qualsevol usuari autenticat llegeix els ConfigProject; només `customers` els modifica."""

    def setUp(self):
        from django.contrib.auth import get_user_model
        from rest_framework.test import APIClient
        from coredata.models import ConfigProject

        User = get_user_model()
        self.customers = User.objects.create_user('customers', 'customers@example.com', 'x')
        self.admin = User.objects.create_superuser('admin', 'admin@example.com', 'x')
        self.config = ConfigProject.objects.create(token='some_token', name='Some token', value='old')
        self.client = APIClient()

    def _bulk_update(self, user):
        self.client.force_authenticate(user)
        return self.client.post(
            '/coredata/config-project/bulk-update-values/',
            [{'token': 'some_token', 'value': 'new'}],
            format='json',
        )

    def test_any_authenticated_user_can_read(self):
        self.client.force_authenticate(self.admin)
        self.assertEqual(self.client.get('/coredata/config-project/').status_code, 200)
        response = self.client.get('/coredata/config-project/some_token/value/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['value'], 'old')

    def test_anonymous_user_cannot_read(self):
        self.assertIn(self.client.get('/coredata/config-project/').status_code, (401, 403))

    def test_customers_can_bulk_update(self):
        response = self._bulk_update(self.customers)
        self.assertEqual(response.status_code, 200)
        self.config.refresh_from_db()
        self.assertEqual(self.config.value, 'new')

    def test_other_users_cannot_bulk_update(self):
        response = self._bulk_update(self.admin)
        self.assertEqual(response.status_code, 403)
        self.config.refresh_from_db()
        self.assertEqual(self.config.value, 'old')

    def test_other_users_cannot_write_through_the_model_endpoints(self):
        self.client.force_authenticate(self.admin)
        url = '/coredata/config-project/some_token/'
        self.assertEqual(self.client.patch(url, {'value': 'new'}, format='json').status_code, 403)
        self.assertEqual(self.client.put(url, {'token': 'some_token', 'value': 'new'}, format='json').status_code, 403)
        self.assertEqual(self.client.delete(url).status_code, 403)
        self.assertEqual(
            self.client.post('/coredata/config-project/', {'token': 'other', 'value': 'x'}, format='json').status_code,
            403,
        )
        self.config.refresh_from_db()
        self.assertEqual(self.config.value, 'old')

    def test_my_permissions_exposes_the_flag(self):
        self.client.force_authenticate(self.customers)
        self.assertTrue(self.client.get('/auth/permission/my-permissions/').data['can_edit_config_project'])
        self.client.force_authenticate(self.admin)
        self.assertFalse(self.client.get('/auth/permission/my-permissions/').data['can_edit_config_project'])
