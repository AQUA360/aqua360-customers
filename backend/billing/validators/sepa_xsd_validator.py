from pathlib import Path

from lxml import etree

PAIN_008_XSD_PATH = Path(__file__).resolve().parent / 'pain.008.001.02.xsd'


def validate_sepa_xml(xml_content, xsd_path=None):
    """
    Valida un XML SEPA contra l'XSD pain.008.001.02.

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
        doc = etree.fromstring(xml_content)
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
