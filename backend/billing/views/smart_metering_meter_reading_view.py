from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from billing.permissions import ReadingPermission
from billing.utils.smart_metering_service import (
    SmartMeteringApiError,
    fetch_smart_metering_meter_reading,
)


class SmartMeteringMeterReadingView(APIView):
    """
    Fetch the smart metering reading for a single meter on a given date.

    Query params:
        - meter: meter code (e.g. J26OA164970O). Optional if meter_id provided.
        - meter_id: meter id. Optional if meter provided.
        - date: reading date (YYYY-MM-DD). Optional, defaults to today.
        - margin: days margin. Optional.
    """

    permission_classes = [IsAuthenticated, ReadingPermission]

    def get(self, request):
        meter_code = request.query_params.get('meter')
        meter_id = request.query_params.get('meter_id')
        reading_date = request.query_params.get('date')
        margin = request.query_params.get('margin')

        if not meter_code and not meter_id:
            return Response(
                {"error": "meter or meter_id is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            payload = fetch_smart_metering_meter_reading(
                meter_code=meter_code,
                meter_id=meter_id,
                reading_date_str=reading_date,
                margin=int(margin) if margin else None,
            )
            return Response(payload, status=status.HTTP_200_OK)
        except SmartMeteringApiError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)
        except ValueError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as exc:
            return Response(
                {"error": f"Unexpected error occurred: {exc}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
