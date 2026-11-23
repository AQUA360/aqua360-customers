from rest_framework import status
from rest_framework.exceptions import APIException, ParseError
from rest_framework.parsers import BaseParser, get_encoding
from rest_framework.renderers import JSONRenderer
from rest_framework.settings import api_settings
from rest_framework.utils import json


class RequestBodyTooLarge(APIException):
    status_code = status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
    default_detail = "Request body too large"
    default_code = "request_body_too_large"


class LimitedJSONParser(BaseParser):
    """JSON amb un límit de mida propi en lloc de `DATA_UPLOAD_MAX_MEMORY_SIZE`.

    El `JSONParser` de DRF llegeix el cos amb `request.body`, que rebutja
    qualsevol cos de més de `DATA_UPLOAD_MAX_MEMORY_SIZE` (2,5 MiB per
    defecte). Els endpoints que reben un document en base64 dins el JSON fan
    servir aquest parser per admetre'n més sense apujar el límit de tota
    l'aplicació: llegeix del flux com a màxim `max_bytes` (més un byte per
    detectar l'excés) i respon 413 si el passa.

    No hereta de `JSONParser` expressament: DRF hi passa sempre `request.body`.
    """

    media_type = "application/json"
    renderer_class = JSONRenderer
    strict = api_settings.STRICT_JSON

    def get_max_bytes(self):
        raise NotImplementedError("LimitedJSONParser needs get_max_bytes().")

    def parse(self, stream, media_type=None, parser_context=None):
        parser_context = parser_context or {}
        encoding = get_encoding(parser_context)
        max_bytes = int(self.get_max_bytes())
        raw = stream.read(max_bytes + 1)
        if len(raw) > max_bytes:
            raise RequestBodyTooLarge({"error": RequestBodyTooLarge.default_detail})
        try:
            parse_constant = json.strict_constant if self.strict else None
            return json.loads(raw.decode(encoding), parse_constant=parse_constant)
        except ValueError as exc:
            raise ParseError("JSON parse error - %s" % str(exc))
