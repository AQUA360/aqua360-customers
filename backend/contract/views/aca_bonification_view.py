from django.core.files.base import ContentFile
from django.db import transaction
from django.http import HttpResponse
from django.utils import timezone
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from billing.utils.aca_company_service import ACACompanyError, resolve_aca_company
from coredata.models import ConfigProject
from service.models import Company, Exploitation
from contract.models import ACABonificationRequest, ACADocument, ACADocumentStatus
from contract.permissions import ContractPermission
from contract.serializers.aca_bonification_serializer import ACABonificationRequestSerializer
from contract.utils.aca_bonification_export_service import build_ampliacio_trams_file
from watchdog.aca_config import aca_notification_enabled


class ACABonificationRequestViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ACABonificationRequestSerializer
    permission_classes = [IsAuthenticated, ContractPermission]

    def get_queryset(self):
        if not aca_notification_enabled():
            return ACABonificationRequest.objects.none()
        return ACABonificationRequest.objects.filter(sent_at__isnull=True).select_related(
            'bonification', 'bonification__contract', 'bonification__contract__holder'
        ).order_by('created_at')

    def partial_update(self, request, pk=None):
        if not aca_notification_enabled():
            return Response(status=status.HTTP_404_NOT_FOUND)

        instance = self.get_queryset().filter(pk=pk).first()
        if not instance:
            return Response(status=status.HTTP_404_NOT_FOUND)

        editable_fields = ['authorizes_census_review', 'aca_result', 'censat_adreca', 'num_persons_censats']
        for field in editable_fields:
            if field in request.data:
                setattr(instance, field, request.data.get(field))
        instance.save()

        return Response(ACABonificationRequestSerializer(instance).data)

    def _prepare_export(self, request):
        """Valida la selecció i retorna (pending, supplier_code, supplier_nif, content, file_name)
        o (None, None, None, error_response) si hi ha algun problema."""
        if not aca_notification_enabled():
            return None, Response(
                {'error': "La notificació de bonificacions a l'ACA no està activada (ConfigProject 'aca_notification_enabled')."},
                status=status.HTTP_400_BAD_REQUEST
            )

        ids = request.data.get('ids')
        queryset = self.get_queryset()
        if ids:
            queryset = queryset.filter(id__in=ids)

        pending = list(queryset)
        if not pending:
            return None, Response({'error': 'No hi ha sol·licituds pendents seleccionades.'}, status=status.HTTP_400_BAD_REQUEST)

        # Un contracte pot tenir més d'una ACABonificationRequest pendent (p.ex. per un
        # registre duplicat): només se'n genera una línia al fitxer (la més recent),
        # però totes les sol·licituds del contracte es marquen igualment com enviades.
        by_contract = {}
        for req in pending:
            by_contract.setdefault(req.bonification.contract_id, []).append(req)
        detail_requests = sorted(
            (max(reqs, key=lambda r: r.created_at) for reqs in by_contract.values()),
            key=lambda r: r.created_at,
        )

        missing = [req.id for req in detail_requests if req.num_persons_to_apply is None]
        if missing:
            return None, Response(
                {'error': "Falta la variable 'ACA-TRAM-MEMBRES' (nombre de persones) a la sol·licitud de bonificació per a algun dels contractes seleccionats.", 'ids': missing},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Mateix criteri que la resta d'exports ACA (billing/utils/aca_company_service.py): el
        # codi d'entitat subministradora (supply_code) i el NIF són els de la Company apuntada
        # per ConfigProject 'main_company_token' o, amb múltiples empreses, els de l'empresa
        # dels contractes seleccionats (tots de la mateixa).
        exploitation = Exploitation.objects.filter(is_active=True).first()
        if not exploitation:
            return None, Response({'error': "No hi ha cap explotació activa."}, status=status.HTTP_400_BAD_REQUEST)

        main_company_vat = ConfigProject.objects.filter(token='main_company_token').first()
        main_company = Company.objects.filter(vat=main_company_vat.value).first() if main_company_vat else None
        try:
            company = resolve_aca_company(
                {req.bonification.contract.company_id for req in detail_requests}, main_company, 'contractes'
            )
        except ACACompanyError as e:
            return None, Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

        today = timezone.now().date()
        number_today = ACADocument.objects.filter(date=today, source='Entitat subministradora', type='Ampliació de trams').count()
        file_name = f"AT{str(company.supply_code).zfill(4)}{today.strftime('%y%m%d')}E{str(number_today).zfill(3)}.txt"
        content = build_ampliacio_trams_file(
            detail_requests, company.supply_code, company.vat, exploitation.code, generation_date=today
        )

        return {
            'pending': pending,
            'detail_requests': detail_requests,
            'supplier_code': company.supply_code,
            'today': today,
            'number_today': number_today,
            'file_name': file_name,
            'content': content,
        }, None

    @action(detail=False, methods=['post'], url_path='preview-export')
    def preview_export(self, request):
        data, error = self._prepare_export(request)
        if error:
            return error

        return Response({
            'file_name': data['file_name'],
            'content': data['content'],
            'contracts': [
                req.bonification.contract.token if req.bonification.contract else None
                for req in data['detail_requests']
            ],
        })

    @action(detail=False, methods=['post'], url_path='generate-export')
    def generate_export(self, request):
        data, error = self._prepare_export(request)
        if error:
            return error

        pending = data['pending']
        file_name = data['file_name']
        content = data['content']

        with transaction.atomic():
            doc = ACADocument.objects.create(
                token=file_name,
                name=file_name,
                type='Ampliació de trams',
                supplier=str(data['supplier_code']),
                date=data['today'],
                source='Entitat subministradora',
                number=str(data['number_today']).zfill(3),
                closing=False,
                is_active=True,
                status=ACADocumentStatus.objects.filter(is_default=True).first(),
            )
            doc.file.save(file_name, ContentFile(content.encode('windows-1252', errors='replace')), save=True)

            now = timezone.now()
            for req in pending:
                req.sent_at = now
                req.aca_document = doc
                req.save()

        response = HttpResponse(content, content_type='text/plain')
        response['Content-Disposition'] = f'attachment; filename={file_name}'
        response['Access-Control-Expose-Headers'] = 'Content-Disposition'
        return response
