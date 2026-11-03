from django.db import transaction
from django.utils import timezone
from rest_framework import serializers
from django_filters import rest_framework as filters

from auth.serializers import UserMinimalSerializer
from billing.serializers.commitment_deposit_serializer import CommitmentDepositListSerializer
from billing.serializers.invoice_serializer import InvoiceMinimalSerializer
from contract.serializers.contract_minimal_serializer import ContractMinimalSerializer
from logger.models import LogIncidentChange, LogIncidentStatusChange
from notification.serializers.calendar_task_serializer import CalendarTaskSerializer
from notification.serializers.value_objects_serializer import (
    IncidentChannelSerializer, IncidentReportSerializer,
    IncidentStatusSerializer, IncidentTypeSerializer,
)
from notification.utils.incident_utils import (
    compute_due_at, get_closed_status_token, get_config, incident_exploitation, is_overdue, notify_assignment,
)
from order.serializers.order_serializer import OrderMinimalSerializer
from service.serializers.cluster_serializer import ClusterListSerializer
from service.serializers.supply_cut_serializer import SupplyCutMinimalSerializer
from service.serializers.supply_point_serializer import SupplyPointMinimalSerializer
from ..models import *
from django.db import models as dj_models
from django.utils.translation import gettext_lazy as _

# Camps de la incidència dels quals es desa l'historial de canvis (l'estat té el seu propi log)
TRACKED_FIELDS = [
    'name', 'description', 'type', 'channel', 'contact_email', 'assigned_to', 'due_at',
    'first_response_at', 'resolution', 'contract', 'invoice', 'commitment_deposit',
    'order_incident', 'supply_point', 'cluster', 'supply_cut',
]


class IncidentObservationSerializer(serializers.ModelSerializer):
    user = UserMinimalSerializer(required=False, allow_null=True)
    class Meta:
        model = IncidentObservation
        fields = '__all__'


class OverdueMixin:
    """El token de l'estat tancat es consulta un sol cop per serialitzador (llistats)."""

    def get_is_overdue(self, obj):
        if not hasattr(self, '_closed_status_token'):
            self._closed_status_token = get_closed_status_token()
        return is_overdue(obj, self._closed_status_token)


class IncidentSerializer(OverdueMixin, serializers.ModelSerializer):

    contract = ContractMinimalSerializer(read_only=True, required=False, allow_null=True)
    invoice = InvoiceMinimalSerializer(read_only=True, required=False, allow_null=True)
    commitment_deposit = CommitmentDepositListSerializer(read_only=True, required=False, allow_null=True)
    order_incident = OrderMinimalSerializer(read_only=True, required=False, allow_null=True)
    supply_point = SupplyPointMinimalSerializer(read_only=True, required=False, allow_null=True)
    cluster = ClusterListSerializer(read_only=True, required=False, allow_null=True)
    supply_cut = SupplyCutMinimalSerializer(read_only=True, required=False, allow_null=True)
    orders = OrderMinimalSerializer(many=True, read_only=True, required=False, allow_null=True)
    reports = serializers.SerializerMethodField()
    status = IncidentStatusSerializer(read_only=True, required=False, allow_null=True)
    type = IncidentTypeSerializer(read_only=True, required=False, allow_null=True)
    channel = IncidentChannelSerializer(read_only=True, required=False, allow_null=True)
    tasks = CalendarTaskSerializer(many=True, read_only=True, required=False, allow_null=True)
    call_register_count = serializers.SerializerMethodField()
    created_by = UserMinimalSerializer(read_only=True, required=False, allow_null=True)
    assigned_to = UserMinimalSerializer(read_only=True, required=False, allow_null=True)
    deleted_by = UserMinimalSerializer(read_only=True, required=False, allow_null=True)
    is_overdue = serializers.SerializerMethodField()
    closed_on_time = serializers.BooleanField(read_only=True)
    receipt_document_name = serializers.CharField(source='receipt_document.document_name', read_only=True, default=None)

    class Meta:
        model = Incident
        fields = '__all__'

    def get_call_register_count(self, obj):
        return obj.call_registers.count()

    def get_reports(self, obj):
        # Els informes esborrats (lògicament) no es mostren
        reports = obj.reports.filter(is_active=True).order_by('-created_at')
        return IncidentReportSerializer(reports, many=True, context=self.context).data


class IncidentListSerializer(OverdueMixin, serializers.ModelSerializer):

    status_color = serializers.CharField(source='status.color', read_only=True)
    status_name = serializers.CharField(source='status.name', read_only=True)
    type_name = serializers.CharField(source='type.name', read_only=True)
    type_due_unit = serializers.CharField(source='type.due_unit', read_only=True)
    channel_name = serializers.CharField(source='channel.name', read_only=True)
    contract_token = serializers.CharField(source='contract.token', read_only=True)
    invoice_token = serializers.CharField(source='invoice.token', read_only=True)
    order_token = serializers.SerializerMethodField()
    total_tasks = serializers.SerializerMethodField()
    supply_point = SupplyPointMinimalSerializer(read_only=True, required=False, allow_null=True)
    assigned_to_username = serializers.CharField(source='assigned_to.username', read_only=True)
    is_overdue = serializers.SerializerMethodField()
    closed_on_time = serializers.BooleanField(read_only=True)

    class Meta:
        model = Incident
        fields = [
            'id', 'token', 'name',
            'status_color', 'status_name',
            'contract_token', 'invoice_token',
            'total_tasks', 'type_name', 'created_at',
            'order_token', 'supply_point',
            'assigned_to_username', 'due_at', 'type_due_unit', 'paused_at', 'is_overdue',
            'channel_name', 'closed_at', 'closed_on_time',
        ]

    def get_total_tasks(self, obj):
        return obj.tasks.count()

    def get_order_token(self, obj):
        if obj.order_incident:
            return obj.order_incident.token
        # Si no té order_incident, mirem si té ordres vinculades a través de Order.incident
        first_order = obj.orders.first()
        return first_order.token if first_order else None


def assign_token(incident):
    """
    Referència única: data de registre + identificador (sense truncar, de manera
    que no es pot repetir com passava amb els tres últims dígits).
    """
    created = timezone.localtime(incident.created_at) if incident.created_at else timezone.localtime()
    incident.token = f"{created.strftime('%y%m%d')}{incident.id:03d}"
    Incident.objects.filter(pk=incident.pk).update(token=incident.token)


def after_create(incident, user=None):
    """Passos comuns en registrar una incidència (des de l'aplicació, l'OV o l'app)."""
    assign_token(incident)
    LogIncidentStatusChange.objects.create(object=incident, current_status=incident.status, user=user)
    notify_assignment(incident)
    if incident.type and incident.type.send_receipt:
        from notification.tasks import send_incident_receipt
        transaction.on_commit(lambda: send_incident_receipt.delay(incident.id))


def _log_value(value):
    if value is None:
        return None
    if isinstance(value, dj_models.Model):
        return str(value)
    if hasattr(value, 'isoformat'):
        return value.isoformat()
    return str(value)


class IncidentSaveSerializer(serializers.ModelSerializer):


    new_task = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    # Com s'ha resolt la incidència; el canvi d'estat l'envia com a motiu en tancar-la
    reason = serializers.CharField(write_only=True, required=False, allow_blank=True)
    class Meta:
        model = Incident
        fields = '__all__'
        read_only_fields = [
            'token', 'created_by', 'closed_at', 'is_active', 'deleted_at', 'deleted_by',
            'warned_at', 'escalated_at', 'paused_at', 'pause_warned_at',
            'receipt_document', 'receipt_sent_at',
        ]

    def validate(self, attrs):
        # Transicions d'estat: si l'estat actual en té de configurades, només s'hi pot passar
        new_status = attrs.get('status')
        if self.instance and new_status and new_status != self.instance.status and self.instance.status:
            allowed = self.instance.status.allowed_next.all()
            if allowed.exists() and new_status not in allowed:
                raise serializers.ValidationError({'status': _("This status change is not allowed.")})
        return attrs

    def _user(self):
        request = self.context.get('request')
        return request.user if request and request.user.is_authenticated else None

    def create(self, validated_data):
        default_status = IncidentStatus.objects.get(is_default=True)
        validated_data['status'] = default_status
        validated_data['created_by'] = self._user()
        validated_data.pop('new_task', None)
        reason = validated_data.pop('reason', None)
        if reason:
            validated_data['resolution'] = reason
        if not validated_data.get('channel'):
            validated_data['channel'] = IncidentChannel.objects.filter(is_default=True).first()

        commitment = validated_data.get('commitment_deposit', None)
        invoice = validated_data.get('invoice', None)
        order = validated_data.get('order_incident', None)
        if commitment:
            validated_data['contract'] = commitment.contract
        if invoice:
            validated_data['contract'] = invoice.contract if invoice.contract else None
        if order:
            validated_data['contract'] = order.contract if order.contract else None

        incident = Incident.objects.create(**validated_data)
        if not incident.due_at:
            incident.due_at = compute_due_at(incident.type, incident.created_at, incident_exploitation(incident))
            Incident.objects.filter(pk=incident.pk).update(due_at=incident.due_at)

        after_create(incident, self._user())
        return incident

    def update(self, instance, validated_data):
        new_task = validated_data.pop('new_task', None)
        reason = validated_data.pop('reason', None)
        previous = {field: getattr(instance, field) for field in TRACKED_FIELDS}

        if new_task:
            task = CalendarTask.objects.get(id=new_task)
            instance.tasks.add(task)

        if reason:
            validated_data['resolution'] = reason

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        # Si canvia el tipus i no s'informa la data, es recalcula el venciment des del registre
        if instance.type != previous['type'] and 'due_at' not in validated_data:
            instance.due_at = compute_due_at(instance.type, instance.created_at, incident_exploitation(instance))
        if instance.due_at != previous['due_at']:
            instance.warned_at = None
            instance.escalated_at = None

        # Usuari per al log de canvi d'estat (senyal pre_save)
        instance._change_user = self._user()
        instance.save()

        for field in TRACKED_FIELDS:
            old, new = previous[field], getattr(instance, field)
            if old != new:
                LogIncidentChange.objects.create(
                    object=instance, field=field, old_value=_log_value(old), new_value=_log_value(new),
                    user=self._user(),
                )

        if instance.assigned_to_id and instance.assigned_to_id != (previous['assigned_to'].id if previous['assigned_to'] else None):
            notify_assignment(instance)


        return instance

class IncidentAppSerializer(serializers.ModelSerializer):

    category_token = serializers.CharField(write_only=True, required=False, allow_null=True)
    category_name = serializers.CharField(write_only=True, required=False, allow_null=True)
    title = serializers.CharField(write_only=True, required=False, allow_null=True)

    class Meta:
        model = Incident
        fields = '__all__'
        read_only_fields = [
            'token', 'created_by', 'assigned_to', 'due_at', 'closed_at', 'resolution', 'is_active',
            'deleted_at', 'deleted_by', 'warned_at', 'escalated_at', 'paused_at', 'pause_warned_at',
            'first_response_at', 'receipt_document', 'receipt_sent_at',
        ]

    def create(self, validated_data):
        default_status = IncidentStatus.objects.get(is_default=True)
        validated_data['status'] = default_status

        category_token = validated_data.pop('category_token', None)
        category_name = validated_data.pop('category_name', None)
        title = validated_data.pop('title', None)
        if title:
            validated_data['name'] = title
        # Canal de l'app de lectures, si el client l'ha configurat
        if not validated_data.get('channel'):
            app_channel_token = get_config('incident_channel_app_token')
            validated_data['channel'] = IncidentChannel.objects.filter(token=app_channel_token).first() if app_channel_token else None

        incident = Incident.objects.create(**validated_data)

        if category_token and category_name:
            existing = IncidentType.objects.filter(token=category_token).first()
            if existing:
                type = existing
            else:
                type = IncidentType.objects.create(token=category_token, name=category_name)
            incident.type = type
            incident.due_at = compute_due_at(type, incident.created_at, incident_exploitation(incident))

        incident.save()
        after_create(incident)
        return incident
