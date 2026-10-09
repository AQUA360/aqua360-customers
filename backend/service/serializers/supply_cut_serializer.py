from billing.models import Reading
from contract.models import Contract
from coredata.utils.name_utils import generate_token
from django.db.models import Prefetch
from logger.models import LogSupplyCutStatus
from rest_framework import serializers
from notification.models import Incident, IncidentStatus, IncidentType
from service.serializers.supply_point_serializer import SupplyPointListSerializer, SupplyPointMinimalSerializer, SupplyPointSerializer
from service.serializers.value_objects_serializer import SupplyCutCauseSerializer, SupplyCutStatusSerializer
from ..models import SupplyCut, SupplyCutCause, SupplyCutObservation, SupplyCutStatus, SupplyPoint, Meter
from auth.serializers import UserMinimalSerializer
from service.utils import supply_cut_service
import datetime

class SupplyCutObservationSerializer(serializers.ModelSerializer):
    user = UserMinimalSerializer(required=False, allow_null=True)

    class Meta:
        model = SupplyCutObservation
        fields = '__all__'

class SupplyCutSerializer(serializers.ModelSerializer):
    
    cause = SupplyCutCauseSerializer(required=False, allow_null=True)
    cause_id = serializers.CharField(write_only=True, required=False, allow_null=True, allow_blank=True)
    #supply_points = SupplyPointMinimalSerializer(many=True, read_only=False, allow_null=True)
    supply_points = serializers.ListField(child=serializers.IntegerField(), write_only=True, required=False, allow_null=True)
    contract_ids = serializers.ListField(child=serializers.IntegerField(), write_only=True, required=False, allow_null=True)
    
    class Meta:
        model = SupplyCut
        fields = '__all__'
        read_only_fields = (
            'cause_raw',
            'state_raw',
            'mincut_cause_token',
            'mincut_state_token',
            'requires_review',
        )

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        # Preload the supply points and their relations to avoid N+1 when
        # serializing the detail (used by retrieve, create/update and
        # remove_supply_point alike).
        supply_points = instance.supply_points.select_related(
            'type', 'status', 'source', 'supply_type', 'meter',
            'meter__address_street__type',
            'connection__exploitation', 'property__route_position',
            'cluster_nozzle', 'address__street__type',
            'address__street_number__number_type', 'address__city', 'address__country',
        ).prefetch_related(
            'supply_point_children',
            Prefetch(
                'meter__sub_meters',
                queryset=Meter.objects.select_related('status'),
            ),
            Prefetch(
                'meter__sub_meters__supply_points',
                queryset=SupplyPoint.objects.select_related('address__street__type'),
            ),
            Prefetch(
                'contracts',
                queryset=Contract.objects.select_related('status', 'holder').filter(is_active=True),
                to_attr='_active_contracts',
            ),
            Prefetch(
                'supply_cuts',
                queryset=SupplyCut.objects.select_related('status', 'cause').order_by('-id'),
                to_attr='_prefetched_supply_cuts',
            ),
        )
        sp_list = list(supply_points)
        self._attach_latest_readings(sp_list)
        representation.update({
            'supply_points': SupplyPointListSerializer(sp_list, many=True, context=self.context).data,
            'status': SupplyCutStatusSerializer(instance.status, context=self.context).data
        })
        return representation

    @staticmethod
    def _attach_latest_readings(sp_list):
        """Computes the latest reading of each (supply point, contract) in a
        single query to avoid the N+1 of the cut detail.
        """
        if not sp_list:
            return
        sp_ids = [sp.id for sp in sp_list]
        contract_ids = set()
        for sp in sp_list:
            contracts = getattr(sp, '_active_contracts', None)
            if contracts is None:
                contracts = list(sp.contracts.filter(is_active=True))
                sp._active_contracts = contracts
            contract_ids.update(c.id for c in contracts)
        if not contract_ids:
            return
        latest_readings = Reading.objects.filter(
            supply_point_id__in=sp_ids,
            contract_id__in=contract_ids,
            is_active=True,
            is_close=False,
            is_control=False,
        ).order_by(
            'supply_point_id', 'contract_id', '-reading_date'
        ).distinct('supply_point_id', 'contract_id')
        by_sp = {}
        for reading in latest_readings:
            by_sp.setdefault(reading.supply_point_id, {})[reading.contract_id] = reading
        for sp in sp_list:
            sp._prefetched_latest_readings = by_sp.get(sp.id, {})

    def create(self, validated_data):
        contract_ids = validated_data.pop('contract_ids', None)
        """ if contract_ids:
            contracts = Contract.objects.filter(id__in=contract_ids).distinct()
            for contract in contracts:
                Incident.objects.create(
                    token=generate_token(Incident),
                    contract=contract,
                    type=IncidentType.objects.get(is_default=True),
                    status=IncidentStatus.objects.get(is_default=True),
                    name=f"Tall de subm. del {validated_data.get('date_start')} al {validated_data.get('date_end')}"
                ) """
        return self._save_supply_cut(None, validated_data)

    def update(self, instance, validated_data):
        return self._save_supply_cut(instance, validated_data)

    def _save_supply_cut(self, instance, validated_data):
        supply_points = validated_data.pop('supply_points', None)
        
        cause_id = validated_data.pop('cause_id', None)
        
        previous_status = instance.status if instance else None
        previous_temporary = supply_cut_service.is_temporary_cause(instance) if instance else None

        # A new cut is always born Planned (token "0", planificada). When
        # updating one, the incoming status must be respected: if "pending" was
        # forced here again, the status change (and therefore the closing of the
        # cut, i.e. the date_end) was never saved.
        if instance is None:
            validated_data['status'] = SupplyCutStatus.objects.get(
                token=supply_cut_service.PLANNED_STATUS_TOKEN
            )
        
        if cause_id:
            cause_instance = SupplyCutCause.objects.get(id=cause_id)
            validated_data['cause'] = cause_instance
        
        created = False
        # Crea o actualitza la instància
        if instance is None:
            instance, created = SupplyCut.objects.get_or_create(**validated_data)
        else:
            for attr, value in validated_data.items():
                setattr(instance, attr, value)
            instance.save()

        if supply_points is not None:
            # Supply points leaving the cut must recover the active state:
            # before, only set() was done and they stayed cut forever.
            removed = list(instance.supply_points.exclude(id__in=supply_points)) if not created else []
            instance.supply_points.set(supply_points)
            if removed:
                supply_cut_service.restore_supply_points(
                    instance.id,
                    supply_points=removed,
                    user=self._request_user(),
                    observation=self.initial_data.get('observation') if hasattr(self, 'initial_data') else None,
                )

        observation = self.initial_data.get('observation') if hasattr(self, 'initial_data') else None

        if created:
            pass
        else:
            self._sync_supply_points_status(
                previous_status, instance, previous_temporary=previous_temporary, observation=observation
            )
        
        # Registra el canvi d'estat si cal
        #TODO: optimitza. Al desar molts talls, el log estarà molt llarg
        self.log_status_change(previous_status, instance, observation)
        return instance

    def _request_user(self):
        request = self.context.get('request')
        return getattr(request, 'user', None) if request else None

    def _sync_supply_points_status(self, previous_status, instance, previous_temporary=None, observation=None):
        """Delegates the state-driven propagation to the single source of
        truth in `supply_cut_service` (same machine used by the start/finish
        and resolve-review actions and by the recurring tasks)."""
        supply_cut_service.sync_supply_points_status(
            instance,
            previous_status=previous_status,
            previous_temporary=previous_temporary,
            user=self._request_user(),
            observation=observation,
        )

    def validate(self, attrs):
        """Transicions d'estat i la regla de la data de fi, amb l'única font de
        veritat de `supply_cut_service` (la mateixa màquina que les accions
        start/finish i les tasques)."""

        instance = self.instance

        # -- Transicions d'estat --
        new_status = attrs.get('status')
        if instance is not None and new_status is not None:
            prev_token = instance.status.token if instance.status else None
            new_token = new_status.token if hasattr(new_status, 'token') else new_status
            if new_token and prev_token and not supply_cut_service.validate_transition(
                prev_token, new_token
            ):
                raise serializers.ValidationError({
                    'status': f"Transició no permesa: {prev_token} -> {new_token}.",
                })

        # -- data de fi obligatòria per talls puntuals (temp) NOTIFICABLES --
        cause = attrs.get('cause')
        cause_id = attrs.get('cause_id')
        if cause is None and cause_id:
            cause = SupplyCutCause.objects.filter(id=cause_id).first()
        if cause is None and instance is not None:
            cause = instance.cause
        source = attrs.get('source')
        if source is None and instance is not None:
            source = instance.source

        date_end = attrs.get('date_end')
        if date_end is None and instance is not None:
            date_end = instance.date_end

        if cause is not None and cause.is_temporary:
            accidental = source == SupplyCut.SOURCE_GISWATER and cause.token == 'Accidental'
            if not accidental and not date_end:
                raise serializers.ValidationError({
                    'date_end': "Data de fi obligatòria per a talls puntuals previstos.",
                })

        return attrs

    def log_status_change(self, previous_status, instance, observation=None):
        user = self._request_user()
        current_status = instance.status

        if previous_status != current_status:
            LogSupplyCutStatus.objects.create(
                object=instance,
                previous_status=previous_status,
                current_status=current_status,
                user=user,
                observation=observation
            )

class SupplyCutMinimalSerializer(serializers.ModelSerializer):
    status_name = serializers.CharField(source='status.name', read_only=True)
    status_color = serializers.CharField(source='status.color', read_only=True)
    cause_name = serializers.CharField(source='cause.name', read_only=True)
    cause_color = serializers.CharField(source='cause.color', read_only=True)
    affected_supply_points = serializers.SerializerMethodField(read_only=True)
    distinct_streets = serializers.SerializerMethodField(read_only=True)
    supply_point_ids = serializers.SerializerMethodField(read_only=True)
    
    def _get_supply_points(self, obj):
        prefetched = getattr(obj, '_prefetched_supply_points', None)
        if prefetched is not None:
            return prefetched
        return list(obj.supply_points.select_related('address__street__type').all())

    def get_affected_supply_points(self, obj):
        return len(self._get_supply_points(obj))

    def get_distinct_streets(self, obj):
        supply_points = self._get_supply_points(obj)
        street_names = {
            f"{sp.address.street.type.abbreviation}. {sp.address.street.name}"
            for sp in supply_points
            if sp.address and sp.address.street and sp.address.street.type
        }
        return ', '.join(street_names)

    def get_supply_point_ids(self, obj):
        return [sp.id for sp in self._get_supply_points(obj)]
    
    class Meta:
        model = SupplyCut
        fields = ['id', 'token', 'source', 'date_start', 'date_end',
                  'exec_start', 'exec_end',
                  'status_name', 'status_color',
                  'affected_supply_points', 
                  'distinct_streets', 'supply_point_ids',   
                  'cause_name', 'cause_color',
                  'requires_review']