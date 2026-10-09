# -*- coding: utf-8 -*-
"""Catàleg de tipus de via de l'Agència Catalana de l'Aigua (ACA).

Font única: `Llista de valors de tipus via` de l'ACA (document «Estructura del Fitxer.
Declaració facturació detallada EESS en alta»), 71 codis. Aquesta llista és la que ha
de tenir `coredata_streettype`: el fixture `initial_data/ca/coredata.StreetType.json` la
carrega a cada instal·lació nova i `manage.py sync_street_types` la torna a posar al dia
en una que ja existeix.

La taula NO està bloquejada a la base de dades (decisió de Raul, 14/09/2026): el que
impedeix que el catàleg torni a créixer sol és que cap camí del codi hi escriu. Tot el
que ha de resoldre un tipus de via (serializers, importadors) passa per
`coredata/street_types.py` i no per un `get_or_create`: un tipus que no és a la llista
no es crea, el carrer es queda sense tipus.
"""

# (pk, codi ACA, descripció ACA) — ordre alfabètic de la descripció, tal com el publica l'ACA.
ACA_STREET_TYPES = (
    (1, "AG", "Agregat"),
    (2, "AL", "Albareda"),
    (3, "AP", "Apartat de Correus"),
    (4, "AR", "Àrea, Raval"),
    (5, "AV", "Avinguda"),
    (6, "BD", "Baixada"),
    (7, "BR", "Barranc, Corregada"),
    (8, "BO", "Barri"),
    (9, "BL", "Bloc"),
    (10, "CM", "Camí"),
    (11, "CP", "Campa"),
    (12, "CR", "Carrer"),
    (13, "CO", "Carreró"),
    (14, "CA", "Carretera"),
    (15, "CS", "Cases"),
    (16, "CG", "Col·legi"),
    (17, "CL", "Colònia"),
    (18, "LD", "Costat, vessant"),
    (19, "DP", "Diputació"),
    (20, "DS", "Disseminats"),
    (21, "ED", "Edificis"),
    (22, "EN", "Entrada, eixample"),
    (23, "ES", "Escalinata, graonada"),
    (24, "EX", "Esplanada"),
    (25, "EM", "Extramurs"),
    (26, "ER", "Extraradi"),
    (27, "FC", "Ferrocarril"),
    (28, "GL", "Glorieta"),
    (29, "GV", "Gran Via"),
    (30, "GP", "Grup"),
    (31, "HT", "Hort"),
    (32, "MZ", "Illa de Cases"),
    (33, "JR", "Jardins"),
    (34, "LG", "Lloc"),
    (35, "AD", "Llogaret"),
    (36, "MS", "Masia"),
    (37, "MC", "Mercat"),
    (38, "ML", "Moll"),
    (39, "MN", "Municipi"),
    (40, "MT", "Muntanya"),
    (41, "PQ", "Parròquia"),
    (42, "PA", "Partida"),
    (43, "PT", "Passatge"),
    (44, "PG", "Passeig"),
    (45, "CT", "Pendent"),
    (46, "PR", "Perllongament, continuació"),
    (47, "PL", "Plaça"),
    (48, "PB", "Poblat"),
    (49, "PO", "Polígon"),
    (50, "PN", "Pont"),
    (51, "PD", "Pujada"),
    (52, "QT", "Quinta"),
    (53, "RC", "Racó, raconada"),
    (54, "RM", "Ramal"),
    (55, "RB", "Rambla"),
    (56, "RP", "Rampa"),
    (57, "RR", "Riera"),
    (58, "AY", "Rierol"),
    (59, "RD", "Ronda"),
    (60, "RU", "Rua, camí real"),
    (61, "SD", "Sender, caminol"),
    (62, "SL", "Solar"),
    (63, "SA", "Sortida"),
    (64, "TN", "Terrenys"),
    (65, "TO", "Torrent"),
    (66, "TR", "Travessera"),
    (67, "TV", "Travessia"),
    (68, "UB", "Urbanització"),
    (69, "VI", "Via"),
    (70, "VP", "Via Pública Indeterminada"),
    (71, "CH", "Xalet"),
)

ACA_CODES = frozenset(code for _pk, code, _name in ACA_STREET_TYPES)
ACA_NAME_BY_CODE = {code: name for _pk, code, name in ACA_STREET_TYPES}
ACA_CODE_BY_NAME = {name.upper(): code for _pk, code, name in ACA_STREET_TYPES}

# Grafies històriques (ERP d'origen, imports antics, brossa de `get_or_create`) → codi ACA.
# NOMÉS s'usa per rescatar dades que ja són a la base de dades; no és una llista de valors
# vàlids. ⚠️ `CL` NO hi és a posta: a l'ACA `CL` és Colònia, però molts ERP l'escriuen per
# «calle» (= Carrer). És una ambigüitat que s'ha de resoldre client per client amb l'origen,
# no aquí.
LEGACY_ALIASES = {
    "C": "CR", "C/": "CR", "C.": "CR", "CARRER": "CR", "CALLE": "CR", "CRR": "CR",
    "AV": "AV", "AV/": "AV", "AVDA": "AV", "AVINGUDA": "AV", "AVENIDA": "AV",
    "CTRA": "CA", "CARRETERA": "CA", "CRTA": "CA",
    "CM": "CM", "CAM": "CM", "CAMI": "CM", "CAMÍ": "CM", "CAMINO": "CM",
    "PZ": "PL", "PÇA": "PL", "PLAÇA": "PL", "PLACA": "PL", "PLAZA": "PL", "PÇ": "PL", "PZA": "PL",
    "PS": "PG", "PG": "PG", "PASSEIG": "PG", "PASEO": "PG",
    "PTGE": "PT", "PASSATGE": "PT", "PASAJE": "PT",
    "BJ": "BD", "BX": "BD", "BAIXADA": "BD", "BAJADA": "BD",
    "BO": "BO", "BARRI": "BO", "BARRIO": "BO",
    "DS": "DS", "DISSEMINAT": "DS", "DISSEMINATS": "DS", "DISEMINADO": "DS",
    "CJ": "CO", "CARRERÓ": "CO", "CARRERO": "CO", "CALLEJON": "CO", "CALLEJÓN": "CO",
    "PJ": "PT",
    "UR": "UB", "URB": "UB", "URBANITZACIO": "UB", "URBANITZACIÓ": "UB",
    "URBANIZACION": "UB", "URBANIZACIÓN": "UB",
    "POL": "PO", "POLI": "PO", "P.I": "PO", "P.I.": "PO", "POLIGON": "PO", "POLÍGON": "PO", "POLIGONO": "PO",
    "RBLA": "RB", "RMBLA": "RB", "RAMBLA": "RB",
    "RDA": "RD", "RONDA": "RD",
    "TRAV": "TR", "TRAVESSERA": "TR", "TRAVESERA": "TR",
    "TRAVESSIA": "TV", "TRAVESIA": "TV",
    "GR": "GP", "GRUP": "GP", "GRUPO": "GP",
    "GV": "GV", "G.V": "GV", "G.V.": "GV", "GRAN VIA": "GV", "GRAN VÍA": "GV",
    "RIERA": "RR",
    "PDA": "PD", "PUJADA": "PD", "SUBIDA": "PD",
    "RVL": "AR", "RAVAL": "AR", "AREA": "AR", "ÀREA": "AR",
    "MASIA": "MS", "MASÍA": "MS",
    "MOLL": "ML", "MUELLE": "ML",
    "PONT": "PN", "PUENTE": "PN",
    "GLORIETA": "GL", "GTA": "GL",
    "PART": "PA", "PARTIDA": "PA",
    "VIA": "VI", "VÍA": "VI",
    "LLOC": "LG",
    "HORT": "HT", "HUERTA": "HT",
    "TORRENT": "TO",
    "SOLAR": "SL",
    "MERCAT": "MC", "MERCADO": "MC",
    "MUNICIPI": "MN", "MUNICIPIO": "MN",
    "MUNTANYA": "MT", "MONTAÑA": "MT",
    "XALET": "CH", "CHALET": "CH",
    "EDIFICI": "ED", "EDIFICIS": "ED", "EDIFICIO": "ED",
    "CASES": "CS", "CASAS": "CS",
    "ESPLANADA": "EX", "EXPLANADA": "EX",
    "FERROCARRIL": "FC",
    "RAMAL": "RM",
    "RAMPA": "RP",
    "RIEROL": "AY",
    "SORTIDA": "SA", "SALIDA": "SA",
    "TERRENYS": "TN", "TERRENOS": "TN",
    "COLONIA": "CL", "COLÒNIA": "CL",
    "JARDINS": "JR", "JARDINES": "JR", "JDNS": "JR",
    "PARROQUIA": "PQ", "PARRÒQUIA": "PQ",
    "POBLAT": "PB", "POBLADO": "PB",
}


# Caracters que un ERP deixa davant o darrere d'un prefix i no volen dir res
# (`C: Torras i Bages`, `.. Santuari`, `CL DE LA CREU,`).
_ESCOMBRARIES = " .,:;-/"


def _clean(value):
    return (value or "").strip().strip(_ESCOMBRARIES).upper()


def code_from_token(value):
    """Retorna el codi ACA d'una grafia solta (`CL`, `Ctra.`, `PLAÇA`, `CR`) o None."""
    token = _clean(value)
    if not token:
        return None
    if token in ACA_CODES:
        return token
    if token in ACA_CODE_BY_NAME:
        return ACA_CODE_BY_NAME[token]
    return LEGACY_ALIASES.get(token)


# Descripcions de l'ACA de mes d'una paraula, de la mes llarga a la mes curta, per poder
# reconeixer «Apartat de Correus 341» o «Gran Via de les Corts».
_NOMS_LLARGS = tuple(sorted(
    (name.upper() for _pk, _c, name in ACA_STREET_TYPES if " " in name),
    key=len, reverse=True,
))


def code_from_street_name(name):
    """Endevina el codi ACA a partir del PREFIX del nom del carrer (`PLAÇA MAJOR` → PL,
    `C: Torras i Bages` → CR). Retorna (codi, nom_sense_prefix) o (None, nom original)."""
    raw = (name or "").strip().lstrip(_ESCOMBRARIES)
    if not raw:
        return None, (name or "").strip()

    # 1) descripcio sencera de l'ACA al davant («Apartat de Correus 341»).
    amunt = raw.upper()
    for descripcio in _NOMS_LLARGS:
        if amunt.startswith(descripcio):
            resta = raw[len(descripcio):].strip(_ESCOMBRARIES)
            if resta or amunt == descripcio:
                return ACA_CODE_BY_NAME[descripcio], resta

    # 2) el nom SENCER es un tipus de via («CARRETERA», «Ctra.»): via sense nom.
    code = code_from_token(raw)
    if code:
        return code, ""

    # 3) prefix curt, separat per espai o per un signe de puntuacio.
    for sep in (" ", "/", ".", ":", ","):
        head, _, tail = raw.partition(sep)
        if not tail.strip(_ESCOMBRARIES):
            continue
        code = code_from_token(head if sep == " " else head + sep)
        if code:
            return code, _treu_prefixos_repetits(tail.strip(_ESCOMBRARIES))
    return None, raw


def _treu_prefixos_repetits(nom, maxim=2):
    """Alguns ERP escriuen DOS tipus seguits (`CR CL AFORES`). El tipus el mana el primer, que
    ja s'ha resolt; aqui nomes es neteja el que queda dins del nom.

    Nomes es treu un codi de DUES lletres, sense cap signe: `CL`, `PZ`, `DS`. Aixi no es menja
    una paraula del nom que nomes S'ASSEMBLA a un tipus (`Pça C. St. C.Nicaragua`, on `C.` es
    «Ciutat», o `CL VIA AUGUSTA`, on `VIA` es part del nom)."""
    for _ in range(maxim):
        cap, _sep, resta = nom.partition(" ")
        resta = resta.strip(_ESCOMBRARIES)
        if not resta or len(cap) != 2 or not cap.isalpha() or not code_from_token(cap):
            return nom
        nom = resta
    return nom
