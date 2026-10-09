import csv
import datetime
import io
import uuid
from celery import shared_task
from django.conf import settings
from django.core.files.base import ContentFile
from django.db.models import Max, Prefetch, Q
from django.utils import timezone
from coredata.models import ConfigProject
from logger.models import LogSupplyPointChange
from notification.models import Notification
from service.utils import supply_cut_service
from .models import Meter, Route, SupplyCutStatus, SupplyPoint


@shared_task
def export_route_positions_csv_task(route_id):
    try:
        from service.utils.route_export_csv import build_route_export_csv_bytes
        from documentmanager.utils.main_utils import upload_document
        from django.core.files.base import ContentFile
        from django.conf import settings

        route = Route.objects.get(id=route_id)
        csv_bytes = build_route_export_csv_bytes(route)

        filename = f"route_{route.token or route.id}_positions_{timezone.now().strftime('%Y%m%d_%H%M%S')}.csv"
        service = settings.DOCUMENT_MANAGER_SERVICES.get("service", "hdd")
        content_file = ContentFile(csv_bytes, name=filename)

        document = upload_document(
            file=content_file,
            entity="ROUTE",
            field="EXPORT_POSITIONS",
            entity_id=route.id,
            entity_token="ROUTE_EXPORT_POSITIONS",
            folder="",
            service=service,
            document_name=filename,
            date=timezone.now()
        )

        return {
            "status": "success",
            "message": "Route positions export generated successfully",
            "document_id": document.id,
            "filename": filename
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Error generating route positions export: {str(e)}"
        }


@shared_task
def export_route_supply_points_csv_task(route_id):
    """
    Exporta els SupplyPoints d'una Route (mateixes columnes que l'export per ReadingBatch).
    Sense lot: HasReading=No i columnes Reading buides.
    """
    try:
        from service.utils.supply_points_route_csv_export import build_route_supply_points_csv_bytes
        from documentmanager.utils.main_utils import upload_document
        from django.core.files.base import ContentFile
        from django.conf import settings

        route = Route.objects.get(id=route_id, is_active=True)
        csv_bytes, error_message = build_route_supply_points_csv_bytes(route_id)
        if error_message:
            return {
                "status": "error",
                "message": error_message,
            }

        filename = f"route_{route.token or route.id}_supply_points_{timezone.now().strftime('%Y%m%d_%H%M%S')}.csv"
        service = settings.DOCUMENT_MANAGER_SERVICES.get("service", "hdd")
        content_file = ContentFile(csv_bytes, name=filename)

        document = upload_document(
            file=content_file,
            entity="ROUTE",
            field="EXPORT_SUPPLY_POINTS",
            entity_id=route.id,
            entity_token="ROUTE_EXPORT_SUPPLY_POINTS",
            folder="",
            service=service,
            document_name=filename,
            date=timezone.now(),
        )

        return {
            "status": "success",
            "message": "Route supply points export generated successfully",
            "document_id": document.id,
            "filename": filename,
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Error generating route supply points export: {str(e)}"
        }


@shared_task
def lookup_meters_by_codes_csv_task(codes):
    """
    CSV del lookup de comptadors per llista de meter.code (found + not_found).
    """
    try:
        from service.utils.meter_lookup_service import build_meter_lookup_csv_bytes
        from documentmanager.utils.main_utils import upload_document
        from django.core.files.base import ContentFile
        from django.conf import settings

        csv_bytes, found_count, not_found_count = build_meter_lookup_csv_bytes(codes)
        filename = f"meters_lookup_{timezone.now().strftime('%Y%m%d_%H%M%S')}.csv"
        service = settings.DOCUMENT_MANAGER_SERVICES.get("service", "hdd")
        content_file = ContentFile(csv_bytes, name=filename)

        document = upload_document(
            file=content_file,
            entity="METER",
            field="LOOKUP_EXPORT",
            entity_id=0,
            entity_token="METER_LOOKUP_EXPORT",
            folder="",
            service=service,
            document_name=filename,
            date=timezone.now(),
        )

        return {
            "status": "success",
            "message": "Meter lookup export generated successfully",
            "document_id": document.id,
            "filename": filename,
            "found_count": found_count,
            "not_found_count": not_found_count,
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Error generating meter lookup export: {str(e)}"
        }

@shared_task
def activate_supply_cut():
    """Cuts the supply points of the cuts that have already started.

    Manual ones are created in pending state and activated by `date_start`
    (forecast). Giswater ones are activated by `exec_start` (real execution),
    not by the forecast: a mincut with forecast and no execution does not cut.
    """
    now = timezone.now().date()
    status_cut_token = ConfigProject.objects.get(token='supply_cut_status_active_token').value
    status_instance = SupplyCutStatus.objects.get(token=status_cut_token)

    affected = 0
    for supply_cut in supply_cut_service.supply_cuts_due_to_activate(now):
        affected += supply_cut_service.cut_supply_points(supply_cut.id)
        supply_cut.status = status_instance
        supply_cut.save(update_fields=['status', 'updated_at'])
        supply_cut_service.stamp_exec_start(supply_cut)

    if affected:
        Notification.objects.create(
            token=uuid.uuid4().hex,
            name="Tall de punts de subministrament",
            description=f"Punts de subministrament tallats al {now.strftime('%d/%m/%Y')}",
            module='service',
            entity='supply-cut',
            object_id=None,
            is_active=True,
        )


@shared_task
def deactivate_supply_cut():
    """Closes the cuts whose end date has passed and reactivates the points.

    Manual: `date_end`. Giswater: `exec_end`. A mincut without finished
    execution is not closed even if the forecast has already expired.
    """
    now = timezone.now().date()
    status_instance = SupplyCutStatus.objects.get(
        token=supply_cut_service.closed_status_token()
    )

    affected = 0
    for supply_cut in supply_cut_service.supply_cuts_due_to_deactivate(now):
        supply_cut.status = status_instance
        supply_cut.save(update_fields=['status', 'updated_at'])
        supply_cut_service.stamp_exec_end(supply_cut)
        # Marks it as closed before reactivating, because restore_supply_points
        # checks whether the point still belongs to another open cut.
        affected += supply_cut_service.restore_supply_points(supply_cut.id)

    if affected:
        Notification.objects.create(
            token=uuid.uuid4().hex,
            name="Reactivació de punts de subministrament",
            description=f"Punts de subministrament reactivats al {now.strftime('%d/%m/%Y')}",
            module='service',
            entity='supply-cut',
            object_id=None,
            is_active=True,
        )


@shared_task
def export_meters_csv_task(status_param=None, ordering_param='code', exploitation_param=None):
    from billing.models import Reading
    from documentmanager.utils.main_utils import upload_document

    try:
        # Construir el queryset base
        queryset = Meter.objects.filter(is_active=True)
        
        # Aplicar filtre per status si existeix
        if status_param is not None:
            try:
                status_id = int(status_param)
                queryset = queryset.filter(status_id=status_id)
            except ValueError:
                pass
        
        # Aplicar filtre per exploitation si existeix
        if exploitation_param is not None:
            try:
                exploitation_id = int(exploitation_param)
                queryset = queryset.filter(
                    Q(supply_points__connection__exploitation__id=exploitation_id) |
                    Q(supply_points__connection__exploitation__isnull=True)
                ).distinct()
            except ValueError:
                pass

        # Validar i aplicar l'ordenació
        valid_ordering_fields = [
            'id', 'code', 'code2', 'has_remote_reading', 'created_at', 
            'updated_at', 'installation_at', 'manufacturer', 'model',
            'comm_technology', 'status', 'caliber'
        ]
        
        ordering_fields = []
        if ordering_param:
            for field in ordering_param.split(','):
                field = field.strip()
                if field.startswith('-'):
                    field_name = field[1:]
                    if field_name in valid_ordering_fields:
                        ordering_fields.append(field)
                else:
                    if field in valid_ordering_fields:
                        ordering_fields.append(field)
        
        if not ordering_fields:
            ordering_fields = ['code']
        
        # Obtenir els comptadors amb les seves relacions
        meters = queryset.select_related(
            'status',
            'caliber',
            'meter_general'
        ).prefetch_related(
            Prefetch(
                'supply_points',
                queryset=SupplyPoint.objects.filter(
                    is_active=True
                ).select_related('address'),
                to_attr='active_supply_points'
            )
        ).order_by(*ordering_fields)
        
        # Obtenir les últimes lectures per tots els comptadors
        meter_ids = list(meters.values_list('id', flat=True))
        last_readings_dict = {}
        if meter_ids:
            max_dates = Reading.objects.filter(
                meter_id__in=meter_ids,
                is_active=True
            ).values('meter_id').annotate(
                max_date=Max('reading_date'),
                max_created=Max('created_at')
            )
            
            for meter_id in meter_ids:
                max_date_info = next((x for x in max_dates if x['meter_id'] == meter_id), None)
                if max_date_info:
                    last_reading = Reading.objects.filter(
                        meter_id=meter_id,
                        is_active=True,
                        reading_date=max_date_info['max_date']
                    ).order_by('-created_at').first()
                    if last_reading:
                        last_readings_dict[meter_id] = last_reading

        # Crear el buffer per al CSV
        csv_buffer = io.StringIO()
        # Escriure BOM per UTF-8 (per compatibilitat amb Excel)
        csv_buffer.write('\ufeff')
        
        writer = csv.writer(csv_buffer, delimiter=';')
        
        headers = [
            'id', 'token', 'code', 'code2', 'is_compound', 'is_property', 'is_general',
            'manufacturer', 'manufacturing_year', 'model', 'comm_module', 'comm_module_type',
            'comm_technology', 'network_provider', 'installation_at', 'uninstallation_at',
            'digits', 'has_remote_reading',
            
            'status_token', 'status_name', 'status_color', 'caliber_token', 'caliber_name',
            'meter_general_id', 'meter_general_code',
            
            'supply_point_token', 'supply_point_address',
            
            'created_at', 'updated_at',
            
            'last_reading_id', 'last_reading_token', 'last_reading_date', 'last_reading_value',
            'last_reading_calculated_value', 'last_reading_leak_value', 'last_reading_estimated_used',
            'last_reading_consumption_days', 'last_reading_origin', 'last_reading_is_control',
            'last_reading_is_estimated', 'last_reading_is_close', 'last_reading_created_at',
            'last_reading_updated_at',
        ]
        
        writer.writerow(headers)
        
        for meter in meters:
            last_reading = last_readings_dict.get(meter.id)
            
            supply_point = None
            supply_point_address = ''
            if hasattr(meter, 'active_supply_points') and meter.active_supply_points:
                supply_point = meter.active_supply_points[0]
                supply_point_address = str(supply_point.address) if supply_point.address else ''
            
            row = [
                meter.id,
                meter.token or '',
                meter.code or '',
                meter.code2 or '',
                meter.is_compound,
                meter.is_property,
                meter.is_general,
                meter.manufacturer or '',
                meter.manufacturing_year or '',
                meter.model or '',
                meter.comm_module or '',
                meter.comm_module_type or '',
                meter.comm_technology or '',
                meter.network_provider or '',
                meter.installation_at.strftime('%Y-%m-%d') if meter.installation_at else '',
                meter.uninstallation_at.strftime('%Y-%m-%d') if meter.uninstallation_at else '',
                meter.digits or '',
                meter.has_remote_reading,
                
                meter.status.token if meter.status else '',
                meter.status.name if meter.status else '',
                meter.status.color if meter.status else '',
                meter.caliber.token if meter.caliber else '',
                meter.caliber.name if meter.caliber else '',
                meter.meter_general.id if meter.meter_general else '',
                meter.meter_general.code if meter.meter_general else '',
                
                supply_point.token if supply_point else '',
                supply_point_address,
                
                meter.created_at.strftime('%Y-%m-%d %H:%M:%S') if meter.created_at else '',
                meter.updated_at.strftime('%Y-%m-%d %H:%M:%S') if meter.updated_at else '',
                
                last_reading.id if last_reading else '',
                last_reading.token if last_reading else '',
                last_reading.reading_date.strftime('%Y-%m-%d') if last_reading and last_reading.reading_date else '',
                float(last_reading.reading_value) if last_reading and last_reading.reading_value else '',
                float(last_reading.calculated_value) if last_reading and last_reading.calculated_value else '',
                float(last_reading.leak_value) if last_reading and last_reading.leak_value else '',
                float(last_reading.estimated_used) if last_reading and last_reading.estimated_used else '',
                last_reading.consumption_days if last_reading else '',
                last_reading.origin if last_reading else '',
                last_reading.is_control if last_reading else '',
                last_reading.is_estimated if last_reading else '',
                last_reading.is_close if last_reading else '',
                last_reading.created_at.strftime('%Y-%m-%d %H:%M:%S') if last_reading and last_reading.created_at else '',
                last_reading.updated_at.strftime('%Y-%m-%d %H:%M:%S') if last_reading and last_reading.updated_at else '',
            ]
            writer.writerow(row)
            
        csv_data = csv_buffer.getvalue()
        csv_bytes = csv_data.encode('utf-8')
        
        filename = f"meters_export_{timezone.now().strftime('%Y%m%d_%H%M%S')}.csv"
        
        # Guardar com a Document
        service = settings.DOCUMENT_MANAGER_SERVICES.get("statistics", "hdd")
        content_file = ContentFile(csv_bytes, name=filename)
        
        document = upload_document(
            file=content_file,
            entity="METER",
            field="EXPORT",
            entity_id=0,
            entity_token="METER_EXPORT",
            folder="",
            service=service,
            document_name=filename,
            date=timezone.now()
        )
        
        return {
            "status": "success",
            "message": "Meters export generated successfully",
            "document_id": document.id,
            "filename": filename
        }
        
    except Exception as e:
        return {
            "status": "error",
            "message": f"Error generating meters export: {str(e)}"
        }
