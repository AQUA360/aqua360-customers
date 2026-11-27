import logging

from django.conf import settings
from django.db import IntegrityError
from django.db.models import Count, Q
from django.utils.dateparse import parse_date
from django_filters import rest_framework as filters
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from auth.permissions import PermissionManager
from billing.models import InsolvencyProcess
from billing.permissions import PaymentPermission
from billing.serializers.insolvency_process_serializer import (
    InsolvencyContractSerializer,
    InsolvencyInvoiceSerializer,
    InsolvencyProcessListSerializer,
    InsolvencyProcessSerializer,
)
from billing.utils.insolvency_service import (
    InsolvencyProcessError,
    change_invoices_delinquency_status,
    close_insolvency_process,
    create_insolvency_process,
    eligible_invoices,
    holder_contracts,
    insolvency_error_message,
    is_person_insolvent,
)
from coredata.models import Person

logger = logging.getLogger(__name__)


class InsolvencyProcessFilter(filters.FilterSet):
    person_id = filters.NumberFilter(field_name='person_id')
    status = filters.CharFilter(field_name='status')
    search = filters.CharFilter(method='filter_search')

    class Meta:
        model = InsolvencyProcess
        fields = ['person_id', 'status', 'search']

    def filter_search(self, queryset, name, value):
        value = (value or '').strip()
        if not value:
            return queryset
        return queryset.filter(
            Q(person__token__icontains=value) | Q(person__name__icontains=value)
            | Q(person__surname__icontains=value) | Q(case_number__icontains=value)
        )


def _get_person(raw_id):
    try:
        return Person.objects.get(pk=int(raw_id))
    except (TypeError, ValueError, Person.DoesNotExist):
        raise InsolvencyProcessError('invalid_person')


def _get_date(raw):
    value = parse_date(str(raw)) if raw else None
    if not value:
        raise InsolvencyProcessError('invalid_date')
    return value


class InsolvencyProcessViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """Processos d'insolvència: llistat, detall, previsualització, alta, documents i tancament."""
    queryset = InsolvencyProcess.objects.select_related('person', 'user', 'closed_by', 'anomaly').annotate(
        invoices_count=Count('invoices', distinct=True))
    permission_classes = [IsAuthenticated, PaymentPermission]
    filter_backends = (filters.DjangoFilterBackend,)
    filterset_class = InsolvencyProcessFilter

    def get_serializer_class(self):
        if self.action == 'list':
            return InsolvencyProcessListSerializer
        return InsolvencyProcessSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        if self.action == 'retrieve':
            queryset = queryset.prefetch_related(
                'invoices__status', 'invoices__contract',
                'contracts__contract', 'contracts__previous_payment_type', 'contracts__new_payment_type',
                'contracts__previous_debt_management',
            )
        return queryset

    @action(detail=False, methods=['get'], url_path='permissions')
    def permissions(self, request):
        return Response(PermissionManager.get_model_permissions(request.user, 'payment', 'billing'))

    @action(detail=False, methods=['post'])
    def preview(self, request):
        """Factures emeses des de la data i contractes on la persona és titular."""
        try:
            person = _get_person(request.data.get('person_id'))
            start_date = _get_date(request.data.get('start_date'))
        except InsolvencyProcessError as error:
            return Response({'error': insolvency_error_message(error.code)}, status=status.HTTP_400_BAD_REQUEST)
        open_process = InsolvencyProcess.objects.filter(person=person, status=InsolvencyProcess.STATUS_OPEN).first()
        invoices = eligible_invoices(person, start_date).select_related('contract')
        return Response({
            'person': {'id': person.id, 'token': person.token, 'name': str(person).strip(),
                       'is_juridic': person.is_juridic},
            'is_insolvent': is_person_insolvent(person),
            'open_process_id': open_process.id if open_process else None,
            'invoices': InsolvencyInvoiceSerializer(invoices, many=True).data,
            'contracts': InsolvencyContractSerializer(holder_contracts(person), many=True).data,
        })

    def create(self, request):
        data = request.data
        try:
            process = create_insolvency_process(
                person=_get_person(data.get('person_id')),
                kind=data.get('kind'),
                start_date=_get_date(data.get('start_date')),
                case_number=data.get('case_number'),
                observation=data.get('observation'),
                payment_changes=data.get('payment_changes'),
                invoice_status_changes=data.get('invoice_status_changes'),
                user=request.user,
            )
        except InsolvencyProcessError as error:
            return Response({'error': insolvency_error_message(error.code)}, status=status.HTTP_400_BAD_REQUEST)
        except IntegrityError:
            # Dues altes alhora per a la mateixa persona: la restricció de BD n'atura una
            return Response({'error': insolvency_error_message('already_open')}, status=status.HTTP_400_BAD_REQUEST)
        return Response(InsolvencyProcessSerializer(self.get_queryset().get(pk=process.pk)).data,
                        status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def close(self, request, pk=None):
        process = self.get_object()
        try:
            end_date = _get_date(request.data.get('end_date')) if request.data.get('end_date') else None
            close_insolvency_process(process, request.user, end_date,
                                     restore_payment=request.data.get('restore_payment') is True)
        except InsolvencyProcessError as error:
            return Response({'error': insolvency_error_message(error.code)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(InsolvencyProcessSerializer(self.get_queryset().get(pk=process.pk)).data)

    @action(detail=True, methods=['post'], url_path='invoice-status')
    def invoice_status(self, request, pk=None):
        """Passa les factures seleccionades del procés a morositat o a irrecuperable (decisió manual).
        Cos: {"invoice_ids": [...], "target": "endowment" | "irrecoverable"}."""
        process = self.get_object()
        try:
            change_invoices_delinquency_status(process, request.data.get('invoice_ids'),
                                               request.data.get('target'), request.user)
        except InsolvencyProcessError as error:
            return Response({'error': insolvency_error_message(error.code)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(InsolvencyProcessSerializer(self.get_queryset().get(pk=process.pk)).data)

    @action(detail=True, methods=['post'], url_path='upload-document')
    def upload_document(self, request, pk=None):
        from documentmanager.utils.main_utils import upload_document
        process = self.get_object()
        file = request.FILES.get('file')
        if not file:
            return Response({'error': 'Cal un fitxer.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            service = settings.DOCUMENT_MANAGER_SERVICES.get('billing')
            document = upload_document(file, 'insolvency_process', 'INSOLVENCY', process.id,
                                       str(process.id), '', service, file.name)
        except Exception:
            logger.exception("No s'ha pogut desar el document del procés d'insolvència")
            return Response({'error': "No s'ha pogut desar el document."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        process.documents.add(document)
        return Response(InsolvencyProcessSerializer(self.get_queryset().get(pk=process.pk)).data)
