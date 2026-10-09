from rest_framework import status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from service.models import Meter
from service.serializers.meter_lookup_serializer import MeterLookupSerializer
from service.utils.meter_lookup_service import lookup_meters_by_codes, normalize_meter_codes


class MeterLookupViewSet(viewsets.ViewSet):
    """
    Lookup de comptadors per llista de meter.code (JSON + export CSV async).
    """
    permission_classes = [IsAuthenticated]
    queryset = Meter.objects.all()
    required_permissions = ['service.view_meter']

    def get_queryset(self):
        return Meter.objects.filter(is_active=True)

    def check_permissions(self, request):
        super().check_permissions(request)
        for perm in self.required_permissions:
            if not request.user.has_perm(perm):
                self.permission_denied(request)

    def _parse_codes(self, request):
        codes = request.data.get('codes')
        if codes is None:
            return None, Response(
                {"error": "El camp 'codes' és obligatori (llista de meter.code)."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not isinstance(codes, list):
            return None, Response(
                {"error": "El camp 'codes' ha de ser una llista."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return normalize_meter_codes(codes), None

    def lookup_by_codes(self, request):
        codes, error_response = self._parse_codes(request)
        if error_response:
            return error_response

        found, not_found = lookup_meters_by_codes(codes)
        serializer = MeterLookupSerializer(found, many=True)
        return Response(
            {
                "found_count": len(found),
                "not_found_count": len(not_found),
                "found": serializer.data,
                "not_found": not_found,
            },
            status=status.HTTP_200_OK,
        )

    def lookup_by_codes_csv(self, request):
        codes, error_response = self._parse_codes(request)
        if error_response:
            return error_response

        from service.tasks import lookup_meters_by_codes_csv_task

        task = lookup_meters_by_codes_csv_task.delay(codes)
        return Response(
            {
                "task_id": task.id,
                "status": "pending",
                "message": (
                    "Generació de l'exportació de lookup de comptadors iniciada. "
                    "Utilitza el task_id per comprovar l'estat."
                ),
            },
            status=status.HTTP_202_ACCEPTED,
        )
