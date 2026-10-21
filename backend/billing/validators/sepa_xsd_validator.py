from pathlib import Path

from lxml import etree

PAIN_008_XSD_PATH = Path(__file__).resolve().parent / 'pain.008.001.02.xsd'
# Fitxers de transferència (TRF). Com el de rebuts, és l'XSD de la Deutsche
# Kreditwirtschaft (DFÜ-Abkommen Anlage 3 v3.0), que afegeix les restriccions SEPA a l'ISO.
PAIN_001_XSD_PATH = Path(__file__).resolve().parent / 'pain.001.001.03.xsd'

XSD_PATHS_BY_TYPE = {
    'sepa': PAIN_008_XSD_PATH,
    'trf': PAIN_001_XSD_PATH,
}

# El fitxer el puja l'usuari: no es resolen entitats ni es carreguen DTD ni res
# de la xarxa, per no dependre dels valors per defecte de lxml davant d'un XXE.
SAFE_XML_PARSER = etree.XMLParser(
    resolve_entities=False,
    no_network=True,
    load_dtd=False,
    huge_tree=False,
)


def validate_sepa_xml(xml_content, xsd_path=None):
    """
    Valida un XML SEPA contra l'XSD pain.008.001.02 (o el que es passi a `xsd_path`).

    Retorna un dict:
      - valid (bool)
      - errors (list[dict]): line, column, message (buit si valid)
      - error (str|None): error de parseig / lectura (si el fitxer no és XML vàlid)
    """
    xsd_path = Path(xsd_path) if xsd_path else PAIN_008_XSD_PATH
    if not xsd_path.is_file():
        return {
            'valid': False,
            'errors': [],
            'error': f'XSD not found: {xsd_path}',
        }

    if isinstance(xml_content, str):
        xml_content = xml_content.encode('utf-8')

    try:
        schema = etree.XMLSchema(etree.parse(str(xsd_path)))
    except etree.XMLSchemaParseError as exc:
        return {
            'valid': False,
            'errors': [],
            'error': f'Invalid XSD schema: {exc}',
        }

    try:
        doc = etree.fromstring(xml_content, SAFE_XML_PARSER)
    except etree.XMLSyntaxError as exc:
        return {
            'valid': False,
            'errors': [{
                'line': exc.lineno,
                'column': exc.offset,
                'message': exc.msg,
            }],
            'error': 'XML syntax error',
        }

    # Un fitxer SEPA/TRF no porta mai DOCTYPE: si n'hi ha, es rebutja sense
    # validar-lo, ja que només serveix per declarar entitats.
    docinfo = doc.getroottree().docinfo
    if docinfo.doctype or docinfo.internalDTD is not None:
        return {
            'valid': False,
            'errors': [],
            'error': 'DTD not allowed',
        }

    if schema.validate(doc):
        return {'valid': True, 'errors': [], 'error': None}

    errors = [
        {
            'line': e.line,
            'column': e.column,
            'message': e.message,
            'domain': e.domain_name,
            'type': e.type_name,
        }
        for e in schema.error_log
    ]
    return {'valid': False, 'errors': errors, 'error': None}
