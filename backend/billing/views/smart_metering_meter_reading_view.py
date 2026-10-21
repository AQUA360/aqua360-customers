from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from billing.permissions import ReadingPermission
from billing.utils.smart_metering_service import (
    SmartMeteringApiError,
    fetch_smart_metering_meter_reading,
)
import logging

logger = logging.getLogger(__name__)


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
        """Return a reading for a meter code or ID with optional date and margin.

        Return HTTP 400 for invalid inputs and HTTP 502 for provider failures,
        logging provider errors and returning a generic message.
        """
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
        except SmartMeteringApiError:
            # El detall (configuració o resposta de l'API externa) queda al log.
            logger.exception("Error del servei de telelectura")
            return Response({"error": "No s'ha pogut obtenir la lectura del servei de telelectura."}, status=status.HTTP_502_BAD_GATEWAY)
        except ValueError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as exc:
            logger.exception("Error inesperat")
            return Response(
                {"error": "Unexpected error occurred."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
