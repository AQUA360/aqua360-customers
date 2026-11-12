import base64
import logging
from io import BytesIO

from PIL import Image, ImageOps

from rest_framework import status
from rest_framework.decorators import action
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from django.db.models import Q, Prefetch

from billing.models import ReadingBatch, Reading
from billing.serializers.reading_serializer import ReadingSerializer
from coredata.models import ConfigProject
from service.models import SupplyPoint
from service.utils.route_scope import effective_route_select_related
from billing.utils.reading_batch_service import (
    SETUP_FILTERS,
    get_photo_readings_queryset,
    get_setup_filter_supply_point_ids,
)
from service.serializers.supply_point_serializer import SupplyPointContractsSerializer, SupplyPointMinimalContractsSerializer, SupplyPointMinimalSerializer
from billing.permissions import ReadingPermission

logger = logging.getLogger(__name__)


# Mida màxima de les miniatures de la galeria de lectures amb foto
PHOTO_THUMBNAIL_SIZE = (400, 400)


def encode_photo(photo, thumbnail=False):
    """Foto de la lectura en base64; amb thumbnail=True, reduïda per a la galeria."""
    try:
        with photo.open('rb') as f:
            if not thumbnail:
                data = f.read()
            else:
                image = ImageOps.exif_transpose(Image.open(f))
                image.thumbnail(PHOTO_THUMBNAIL_SIZE)
                buffer = BytesIO()
                image.convert('RGB').save(buffer, 'JPEG', quality=75)
                data = buffer.getvalue()
        return 'data:image/jpeg;base64,' + base64.b64encode(data).decode('utf-8')
    except Exception:
        logger.exception("No s'ha pogut llegir la foto de la lectura")
        return None


def serialize_photo_reading(reading):
    """Targeta de la galeria: dades de la lectura i miniatura de la foto."""
    return {
        'id': reading.id,
        'supply_point_id': reading.supply_point_id,
        'supply_point_token': reading.supply_point.token if reading.supply_point else None,
        'address': str(reading.supply_point.address) if reading.supply_point and reading.supply_point.address else None,
        'contract_id': reading.contract_id,
        'contract_token': reading.contract.token if reading.contract else None,
        'holder': reading.contract.holder.name if reading.contract and reading.contract.holder else None,
        'meter_code': reading.meter.code if reading.meter else None,
        'reading_value': reading.reading_value,
        'reading_date': reading.reading_date,
        'reader_alert': reading.reader_alert.name if reading.reader_alert else None,
        'thumbnail': encode_photo(reading.photo, thumbnail=True),
    }


class ReadingBatchSetupViewSet(viewsets.ViewSet):

    permission_classes = [IsAuthenticated, ReadingPermission]
    lookup_field = 'id'
    queryset = ReadingBatch.objects.all().order_by('-created_at')
    
    def retrieve(self, request, id=None):
        try:
            # Optimize the initial query
            reading_batch = ReadingBatch.objects.select_related('status').prefetch_related(
                'routes',
                'readings',
                'documents__readings',
                'fix_meters'
            ).get(id=id)
            
            filter = request.query_params.get('readings')
            search = request.query_params.get('search')
            if filter == 'photo':
                # Galeria: es pagina per lectures, igual que el comptador del resum
                readings = get_photo_readings_queryset(reading_batch).select_related(
                    'supply_point__address', 'meter', 'contract__holder', 'reader_alert',
                ).order_by('supply_point_id', 'id')
                if search:
                    readings = readings.filter(
                        Q(contract__token__icontains=search) |
                        Q(contract__holder__name__icontains=search) |
                        Q(supply_point__address__address_search__icontains=search)
                    )
                paginator = PageNumberPagination()
                paginator.page_size = 30
                page = paginator.paginate_queryset(readings, request)
                return paginator.get_paginated_response([serialize_photo_reading(r) for r in page])

            active_contract = ConfigProject.objects.get(token='contract_active_token').value
            
            response = []
            
            def apply_search(qs):
                if search:
                    from django.db.models import Q
                    return qs.filter(
                        Q(contracts__token__icontains=search) |
                        Q(contracts__holder__name__icontains=search) |
                        Q(address__address_search__icontains=search)
                    ).distinct()
                return qs

            if filter in SETUP_FILTERS:
                supply_point_ids = get_setup_filter_supply_point_ids(
                    reading_batch, filter, active_contract
                )
                if not supply_point_ids:
                    return Response({
                        'count': 0,
                        'next': None,
                        'previous': None,
                        'results': []
                    })

                supply_points = SupplyPoint.objects.select_related(
                    'type', 'status', *effective_route_select_related()
                ).filter(id__in=supply_point_ids).order_by('id')
                supply_points = apply_search(supply_points)

                paginator = PageNumberPagination()
                paginator.page_size = 30  # Default page size, can be overridden with ?page_size=XX
                paginated_queryset = paginator.paginate_queryset(supply_points, request)

                if filter == 'extra':
                    # Valor de la lectura del fitxer per a cada supply point sobrant
                    page_ids = [sp.id for sp in paginated_queryset]
                    readings_objects = {
                        reading.supply_point_id: reading
                        for reading in Reading.objects.filter(
                            document__batch=reading_batch,
                            is_control=False,
                            supply_point_id__in=page_ids,
                        )
                    }
                    serialized_supply_points = SupplyPointMinimalSerializer(paginated_queryset, many=True).data
                    response = [{
                        'id': sp['id'],
                        'token': sp['token'],
                        'address': sp['address_complete'],
                        'reading_value': readings_objects.get(sp['id']).reading_value if readings_objects.get(sp['id']) else None
                    } for sp in serialized_supply_points]
                else:
                    response = SupplyPointMinimalContractsSerializer(paginated_queryset, many=True).data

                return paginator.get_paginated_response(response)

            print(reading_batch)
            
            return Response({
                'status': 'ok',
                'data': response,
                'count': len(response)
            })
            
        except ReadingBatch.DoesNotExist:
            return Response(
                {"error": "el lot de lectura no existeix"},
                status=status.HTTP_404_NOT_FOUND
            )

    def photo(self, request, id=None, reading_id=None):
        """Foto original d'una lectura de la galeria, per ampliar-la."""
        # Només lectures de la galeria d'aquest lot (pendents, amb foto)
        reading_batch = ReadingBatch.objects.filter(id=id).first()
        reading = get_photo_readings_queryset(reading_batch).filter(
            id=reading_id
        ).first() if reading_batch else None
        photo = encode_photo(reading.photo) if reading else None
        if not photo:
            return Response({"error": "foto no disponible"}, status=status.HTTP_404_NOT_FOUND)
        return Response({'id': reading.id, 'photo': photo})
