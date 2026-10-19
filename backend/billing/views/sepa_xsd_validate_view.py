from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions

from billing.models import PaymentRemittance
from billing.validators.sepa_xsd_validator import XSD_PATHS_BY_TYPE, validate_sepa_xml


class SepaXsdValidateView(APIView):
    """
    POST multipart/form-data amb el camp `file` i, opcionalment, `type`:
    `sepa` (per defecte, rebuts pain.008.001.02) o `trf` (transferències pain.001.001.03).
    Retorna el resultat de la validació contra l'XSD corresponent.
    """
    permission_classes = [IsAuthenticated, DjangoModelPermissions]
    queryset = PaymentRemittance.objects.all()

    def post(self, request, *args, **kwargs):
        """Valida el fitxer amb l'XSD del tipus indicat i retorna 200 o 400 segons el resultat."""
        uploaded = request.FILES.get('file') or request.data.get('file')
        if not uploaded:
            return Response(
                {'error': 'No file was uploaded. Send multipart field "file".'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            content = uploaded.read()
        except Exception as exc:
            return Response(
                {'error': f'Could not read file: {exc}'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not content:
            return Response(
                {'error': 'Uploaded file is empty.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        file_type = request.data.get('type') or 'sepa'
        if file_type not in XSD_PATHS_BY_TYPE:
            return Response(
                {'error': f'Unknown file type "{file_type}". Use one of: {", ".join(XSD_PATHS_BY_TYPE)}.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        result = validate_sepa_xml(content, XSD_PATHS_BY_TYPE[file_type])
        http_status = (
            status.HTTP_200_OK if result['valid'] else status.HTTP_400_BAD_REQUEST
        )
        return Response(result, status=http_status)
