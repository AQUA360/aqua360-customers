from rest_framework import serializers
from functools import lru_cache
import hashlib

from billing.serializers.reading_serializer import ReadingMinimalSerializer, ReadingSerializer
from billing.tasks import fix_readings_batch
from billing.utils.reading_service import get_existing_reading
from coredata.models import ConfigProject
from service.models import Meter, Route, SupplyPoint
from service.serializers.route_serializer import RouteListSerializer
from service.utils.route_positions_service import route_count_total_readings
from django.core.cache import cache
from django.db.models import Count, Sum, Q

from ..models import Reading, ReadingBatch, ReadingBatchStatus, ReadingBatchTemplate

# Shared across batches with the same route (or meter) set — the heavy graph walk.
READING_BATCH_GRAPH_METRICS_TIMEOUT = 180


@lru_cache(maxsize=1)
def reading_batch_list_config_tokens():
    return {
        "active_contract": ConfigProject.objects.get(token="contract_active_token").value,
        "activate_sp": ConfigProject.objects.get(
            token="supply_point_status_activate_token"
        ).value,
        "no_meter": ConfigProject.objects.get(token="token_meter_status_no_meter").value,
    }


class ReadingBatchStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReadingBatchStatus
        fields = '__all__'

class ReadingBatchTemplateSerializer(serializers.ModelSerializer):
    route_ids = serializers.PrimaryKeyRelatedField(queryset=Route.objects.all(), many=True, write_only=True, required=False, allow_null=True)
    
    routes = RouteListSerializer(many=True, read_only=True, required=False, allow_null=True)
    class Meta:
        model = ReadingBatchTemplate
        fields = '__all__'
        
    def create(self, validated_data):
        routes_data = validated_data.pop('route_ids', [])  # Extract routes
        reading_batch_template = ReadingBatchTemplate.objects.create(**validated_data)
        reading_batch_template.routes.set(routes_data)  # Set many-to-many relationship
        return reading_batch_template
    
    def update(self, instance, validated_data):
        routes_data = validated_data.pop('route_ids', None)  # Extract routes if provided
        instance = super().update(instance, validated_data)
        
        if routes_data is not None:
            instance.routes.set(routes_data)  # Update many-to-many relationship
        return instance
        
    def to_representation(self, instance):
        representation = super().to_representation(instance)
        
        representation['num_routes'] = instance.routes.count()
        
        return representation

class ReadingBatchMinimalListSerializer(serializers.ListSerializer):
    """Batch reading-count queries for the whole page instead of per row."""

    def to_representation(self, data):
        iterable = list(data.all() if hasattr(data, "all") else data)
        batch_ids = [obj.pk for obj in iterable]
        tokens = reading_batch_list_config_tokens()
        reading_stats = {}
        if batch_ids:
            rows = (
                Reading.objects.filter(batch_id__in=batch_ids)
                .values("batch_id")
                .annotate(
                    num_readings=Count("id"),
                    num_warnings=Count("id", filter=Q(alert__isnull=False)),
                    num_read_contracts=Count(
                        "contract",
                        filter=Q(
                            is_control=False,
                            reading_value__isnull=False,
                            contract__isnull=False,
                        ),
                        distinct=True,
                    ),
                )
            )
            reading_stats = {row["batch_id"]: row for row in rows}

        self.child.context["reading_batch_tokens"] = tokens
        self.child.context["reading_stats_by_batch"] = reading_stats
        # Batches that share the same routes (common when created with all routes)
        # reuse one graph aggregate for the whole page / process.
        self.child.context["_graph_metrics_memo"] = {}
        return [self.child.to_representation(item) for item in iterable]


class ReadingBatchMinimalSerializer(serializers.ModelSerializer):
    status = ReadingBatchStatusSerializer(read_only=True, required=False, allow_null=True)
    num_readings = serializers.SerializerMethodField()
    no_meter_readings = serializers.SerializerMethodField()
    num_total_readings = serializers.SerializerMethodField()
    num_warnings = serializers.SerializerMethodField()
    num_contracts = serializers.SerializerMethodField()
    num_read_contracts = serializers.SerializerMethodField()
    num_supplies = serializers.SerializerMethodField()

    class Meta:
        model = ReadingBatch
        list_serializer_class = ReadingBatchMinimalListSerializer
        fields = [
            "id",
            "status",
            "name",
            "token",
            "num_readings",
            "num_total_readings",
            "num_warnings",
            "no_meter_readings",
            "created_at",
            "num_contracts",
            "num_read_contracts",
            "num_supplies",
        ]

    def _tokens(self):
        tokens = self.context.get("reading_batch_tokens")
        if tokens is None:
            tokens = reading_batch_list_config_tokens()
            self.context["reading_batch_tokens"] = tokens
        return tokens

    def _has_routes(self, obj):
        # Prefer prefetch cache when present (.exists() always hits the DB).
        return bool(obj.routes.all())

    def _has_fix_meters(self, obj):
        return bool(obj.fix_meters.all())

    def _memo_get(self, memo_key):
        memo = self.context.setdefault("_graph_metrics_memo", {})
        if memo_key in memo:
            return memo[memo_key]
        digest = hashlib.md5(repr(memo_key).encode("utf-8")).hexdigest()
        cache_key = f"reading_batch_graph_metrics:{digest}"
        cached = cache.get(cache_key)
        if cached is not None:
            memo[memo_key] = cached
            return cached
        return None

    def _memo_set(self, memo_key, value):
        memo = self.context.setdefault("_graph_metrics_memo", {})
        memo[memo_key] = value
        digest = hashlib.md5(repr(memo_key).encode("utf-8")).hexdigest()
        cache.set(
            f"reading_batch_graph_metrics:{digest}",
            value,
            READING_BATCH_GRAPH_METRICS_TIMEOUT,
        )
        return value

    def _compute_route_graph_metrics(self, route_ids, include_manual, include_telecontrol, tokens):
        active_contract = tokens["active_contract"]
        no_meter_token = tokens["no_meter"]
        routes_qs = Route.objects.filter(id__in=route_ids)

        meter_filter = Q()
        contract_meter_filter = Q(
            positions__properties__supply_points__contracts__status__token=active_contract,
            positions__properties__supply_points__contracts__is_active=True,
        )
        if include_manual and not include_telecontrol:
            meter_filter = Q(
                positions__properties__supply_points__meter__has_remote_reading=False
            ) | Q(
                positions__properties__supply_points__meter__force_manual_reading=True
            )
            contract_meter_filter &= Q(
                positions__properties__supply_points__meter__has_remote_reading=False
            ) | Q(
                positions__properties__supply_points__meter__force_manual_reading=True
            )
        elif include_telecontrol and not include_manual:
            meter_filter = Q(
                positions__properties__supply_points__meter__has_remote_reading=True,
                positions__properties__supply_points__meter__force_manual_reading=False
            )
            contract_meter_filter &= Q(
                positions__properties__supply_points__meter__has_remote_reading=True,
                positions__properties__supply_points__meter__force_manual_reading=False
            )

        agg_kwargs = {
            "num_supplies": Count(
                "positions__properties__supply_points__meter",
                filter=meter_filter,
                distinct=True,
            ),
            "num_contracts": Count(
                "positions__properties__supply_points__contracts__id",
                filter=contract_meter_filter,
                distinct=True,
            ),
        }
        if include_telecontrol:
            agg_kwargs["no_meter_tele"] = Count(
                "positions__properties__supply_points__meter",
                filter=Q(
                    positions__properties__supply_points__meter__has_remote_reading=True,
                    positions__properties__supply_points__meter__force_manual_reading=False,
                    positions__properties__supply_points__meter__status__token=no_meter_token,
                ),
                distinct=True,
            )
            agg_kwargs["total_tele"] = Count(
                "positions__properties__supply_points__meter",
                filter=(
                    Q(
                        positions__properties__supply_points__meter__status__token__isnull=False
                    )
                    & Q(
                        positions__properties__supply_points__meter__has_remote_reading=True,
                        positions__properties__supply_points__meter__force_manual_reading=False
                    )
                    & ~Q(
                        positions__properties__supply_points__meter__status__token__in=[
                            no_meter_token,
                            "-1",
                        ]
                    )
                ),
                distinct=True,
            )
        if include_manual:
            agg_kwargs["no_meter_manual"] = Count(
                "positions__properties__supply_points__meter",
                filter=Q(
                    positions__properties__supply_points__meter__has_remote_reading=False,
                    positions__properties__supply_points__meter__status__token=no_meter_token,
                ) | Q(
                    positions__properties__supply_points__meter__force_manual_reading=True,
                    positions__properties__supply_points__meter__status__token=no_meter_token,
                ),
                distinct=True,
            )
            agg_kwargs["total_manual"] = Count(
                "positions__properties__supply_points__meter",
                filter=(
                    Q(
                        positions__properties__supply_points__meter__status__token__isnull=False
                    )
                    & (
                        Q(
                            positions__properties__supply_points__meter__has_remote_reading=False
                        ) | Q(
                            positions__properties__supply_points__meter__force_manual_reading=True
                        )
                    )
                    & ~Q(
                        positions__properties__supply_points__meter__status__token__in=[
                            no_meter_token,
                            "-1",
                        ]
                    )
                ),
                distinct=True,
            )

        data = routes_qs.aggregate(**agg_kwargs)
        return {
            "num_supplies": data.get("num_supplies") or 0,
            "num_contracts": data.get("num_contracts") or 0,
            "no_meter_readings": (data.get("no_meter_tele") or 0)
            + (data.get("no_meter_manual") or 0),
            "num_total_readings": (data.get("total_tele") or 0)
            + (data.get("total_manual") or 0),
        }

    def _compute_fix_meter_graph_metrics(self, meter_ids, tokens):
        active_contract = tokens["active_contract"]
        fix_data = Meter.objects.filter(id__in=meter_ids).aggregate(
            num_supplies=Count("supply_points__id", distinct=True),
            num_contracts=Count(
                "supply_points__contracts__id",
                filter=Q(
                    supply_points__contracts__status__token=active_contract,
                    supply_points__contracts__is_active=True,
                ),
                distinct=True,
            ),
            num_meters=Count("id", distinct=True),
        )
        return {
            "num_supplies": fix_data["num_supplies"] or 0,
            "num_contracts": fix_data["num_contracts"] or 0,
            "no_meter_readings": 0,
            "num_total_readings": fix_data["num_meters"] or 0,
        }

    def _compute_all_sp_graph_metrics(self, include_manual, include_telecontrol, tokens):
        activate_token = tokens["activate_sp"]
        active_contract = tokens["active_contract"]
        sp_base = SupplyPoint.objects.filter(
            is_active=True, status__token=activate_token
        )
        if not include_telecontrol:
            sp_base = sp_base.filter(Q(meter__has_remote_reading=False) | Q(meter__force_manual_reading=True))
        elif not include_manual:
            sp_base = sp_base.filter(meter__has_remote_reading=True, meter__force_manual_reading=False)

        return {
            "num_supplies": sp_base.count(),
            "num_contracts": (
                sp_base.filter(
                    contracts__status__token=active_contract,
                    contracts__is_active=True,
                )
                .values("contracts__id")
                .distinct()
                .count()
            ),
            "no_meter_readings": 0,
            "num_total_readings": 0,
        }

    def _graph_metrics(self, obj):
        tokens = self._tokens()
        include_manual = obj.include_manual
        include_telecontrol = obj.include_telecontrol

        if self._has_routes(obj):
            route_ids = tuple(sorted(r.id for r in obj.routes.all()))
            memo_key = (
                "routes",
                route_ids,
                include_manual,
                include_telecontrol,
                tokens["active_contract"],
                tokens["no_meter"],
            )
            hit = self._memo_get(memo_key)
            if hit is not None:
                return hit
            return self._memo_set(
                memo_key,
                self._compute_route_graph_metrics(
                    route_ids, include_manual, include_telecontrol, tokens
                ),
            )

        if self._has_fix_meters(obj):
            meter_ids = tuple(sorted(m.id for m in obj.fix_meters.all()))
            memo_key = (
                "fix_meters",
                meter_ids,
                tokens["active_contract"],
            )
            hit = self._memo_get(memo_key)
            if hit is not None:
                return hit
            return self._memo_set(
                memo_key,
                self._compute_fix_meter_graph_metrics(meter_ids, tokens),
            )

        memo_key = (
            "all_sp",
            include_manual,
            include_telecontrol,
            tokens["active_contract"],
            tokens["activate_sp"],
        )
        hit = self._memo_get(memo_key)
        if hit is not None:
            return hit
        return self._memo_set(
            memo_key,
            self._compute_all_sp_graph_metrics(
                include_manual, include_telecontrol, tokens
            ),
        )

    def _get_all_metrics(self, obj):
        """Reading stats (per batch) + graph metrics (shared by route/meter set)."""
        cached = getattr(obj, "_all_metrics_cache", None)
        if cached is not None:
            return cached

        reading_stats = (self.context.get("reading_stats_by_batch") or {}).get(obj.pk)
        if reading_stats is not None:
            num_readings = reading_stats["num_readings"] or 0
            num_warnings = reading_stats["num_warnings"] or 0
            num_read_contracts = reading_stats["num_read_contracts"] or 0
        else:
            num_readings = obj.readings.count()
            num_warnings = obj.readings.filter(alert__isnull=False).count()
            num_read_contracts = (
                obj.readings.filter(
                    is_control=False,
                    reading_value__isnull=False,
                    contract__isnull=False,
                )
                .values("contract")
                .distinct()
                .count()
            )

        graph = self._graph_metrics(obj)
        result = {
            "num_supplies": graph["num_supplies"],
            "num_contracts": graph["num_contracts"],
            "num_read_contracts": num_read_contracts,
            "num_readings": num_readings,
            "num_warnings": num_warnings,
            "no_meter_readings": graph["no_meter_readings"],
            "num_total_readings": graph["num_total_readings"],
        }
        obj._all_metrics_cache = result
        obj._metrics_cache = {
            "num_supplies": result["num_supplies"],
            "num_contracts": result["num_contracts"],
            "num_read_contracts": result["num_read_contracts"],
        }
        return result

    def _get_metrics(self, obj):
        # Public helper for ReadingBatchSerializer / other callers.
        metrics = self._get_all_metrics(obj)
        return {
            "num_supplies": metrics["num_supplies"],
            "num_contracts": metrics["num_contracts"],
            "num_read_contracts": metrics["num_read_contracts"],
        }

    def get_num_contracts(self, obj):
        return self._get_all_metrics(obj)["num_contracts"]

    def get_num_read_contracts(self, obj):
        return self._get_all_metrics(obj)["num_read_contracts"]

    def get_num_supplies(self, obj):
        return self._get_all_metrics(obj)["num_supplies"]

    def get_num_warnings(self, obj):
        return self._get_all_metrics(obj)["num_warnings"]

    def get_num_readings(self, obj):
        return self._get_all_metrics(obj)["num_readings"]

    def get_no_meter_readings(self, obj):
        return self._get_all_metrics(obj)["no_meter_readings"]

    def get_num_total_readings(self, obj):
        return self._get_all_metrics(obj)["num_total_readings"]


class ReadingBatchSaveSerializer(serializers.ModelSerializer):
    status_token = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    status = ReadingBatchStatusSerializer(read_only=True, required=False, allow_null=True)
    route_ids = serializers.PrimaryKeyRelatedField(queryset=Route.objects.all(), many=True, write_only=True, required=False, allow_null=True)
    routes = RouteListSerializer(many=True, read_only=True, required=False, allow_null=True)
    fileMeters = serializers.ListField(write_only=True, required=False, allow_null=True)
    fileReadings = serializers.ListField(write_only=True, required=False, allow_null=True)
    reading_ids = serializers.ListField(child=serializers.IntegerField(), write_only=True, required=False, allow_null=True)
    template_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    class Meta:
        model = ReadingBatch
        fields = '__all__'
        
    def create(self, validated_data):
        routes_data = validated_data.pop('route_ids', [])  # Extract routes
        fileMeters = validated_data.pop('fileMeters', [])
        fileReadings = validated_data.pop('fileReadings', [])
        reading_ids = validated_data.pop('reading_ids', [])
        template_id = validated_data.pop('template_id', None)
        
        meters = []
        if fileMeters and len(fileMeters) > 0 and fileReadings and len(fileReadings) > 0:
            meters = Meter.objects.filter(code__in=fileMeters)
            fix_readings_batch.delay(fileReadings)
        
        if not routes_data and (not meters or len(meters) == 0) and not reading_ids:
            routes_data = Route.objects.filter(is_active=True).all()
        
        # Ensure token is set if not provided, using name as fallback
        if not validated_data.get('token') and validated_data.get('name'):
            validated_data['token'] = validated_data['name']

        reading_batch = ReadingBatch.objects.create(**validated_data)
        
        if template_id:
            reading_batch.reading_batch_template_id = template_id
            
        reading_batch.routes.set(routes_data)
        reading_batch.fix_meters.set(meters)
        
        if reading_ids:
            Reading.objects.filter(id__in=reading_ids).update(batch=reading_batch)
            # If readings are already provided (e.g. from estimation), set status to finished (Pending billing)
            try:
                finish_status_token = ConfigProject.objects.get(token='batch_status_finish_token').value
                finish_status = ReadingBatchStatus.objects.get(token=finish_status_token)
                reading_batch.status = finish_status
            except Exception:
                # Fallback to default if token not found or fails
                status = ReadingBatchStatus.objects.filter(is_default=True).first()
                reading_batch.status = status
        else:
            status = ReadingBatchStatus.objects.filter(is_default=True).first()
            reading_batch.status = status

        reading_batch.save()
        return reading_batch
        
    def update(self, instance, validated_data):

        token = validated_data.pop('status_token', None)
        if token:
            status = ReadingBatchStatus.objects.get(token=token)
            self._validate_status_transition(instance, status)
            instance.status = status
        return super().update(instance, validated_data)

    def _validate_status_transition(self, instance, new_status):
        """
        Un lot amb lectures ja facturades en factura definitiva (type_final='F')
        no pot tornar a un estat anterior a 'finish' (p. ex. 'processing'), ja que
        aquest pas dispara la regeneracio/esborrat de Reading i trencaria la
        traçabilitat de factures ja emeses.
        """
        current_token = instance.status.token if instance.status else None
        finish_token = ConfigProject.objects.filter(token='batch_status_finish_token').first()

        if current_token != (finish_token.value if finish_token else None):
            return
        if new_status.token == current_token:
            return

        has_final_invoice = Reading.objects.filter(
            batch=instance,
            invoices__type_final='F',
        ).exists()

        if has_final_invoice:
            raise serializers.ValidationError({
                'status_token': (
                    "No es pot canviar l'estat del lot: hi ha lectures amb factura "
                    "definitiva (type_final='F') vinculades. Cal gestionar aquestes "
                    "factures abans de reobrir el lot."
                )
            })
    
    def to_representation(self, instance):
        representation = super().to_representation(instance)
        
        db_readings = Reading.objects.filter(batch=instance).all()
        readings = []
        for reading in db_readings:
            readings.append(get_existing_reading(reading))
            
        representation['readings'] = readings
        
        return representation
class ReadingBatchSerializer(serializers.ModelSerializer):
    status = ReadingBatchStatusSerializer(read_only=True, required=False, allow_null=True)
    routes = RouteListSerializer(many=True, read_only=True, required=False, allow_null=True)
    # readings = ReadingMinimalSerializer(many=True, read_only=True, required=False, allow_null=True)
    class Meta:
        model = ReadingBatch
        fields = '__all__'
    
    def to_representation(self, instance):
        representation = super().to_representation(instance)
        
        # db_readings = Reading.objects.filter(batch=instance).all()
        # readings = []
        # for reading in db_readings:
        #     readings.append(get_existing_reading(reading))
            
        # representation['readings'] = readings
        if instance.billing_missing:
            from billing.serializers.billing_serializer import BillingListSerializer
            representation['billing_missing'] = BillingListSerializer(instance.billing_missing).data
        
        representation['num_warnings'] = instance.readings.filter(alert__isnull=False).count()

        # Mateixos criteris que ReadingBatchMinimalSerializer (llistat); només camps addicionals.
        metrics = ReadingBatchMinimalSerializer()._get_metrics(instance)
        representation['num_routes'] = instance.routes.count()
        representation['num_supplies'] = metrics['num_supplies']
        representation['num_active_supplies'] = self._count_active_supplies(instance)
        representation['num_readings'] = instance.readings.count()

        return representation

    def _count_active_supplies(self, obj):
        """Mateix àmbit que num_supplies (rutes / tele·manual), només SupplyPoints actius."""
        activate_token = ConfigProject.objects.get(token='supply_point_status_activate_token').value
        include_manual = obj.include_manual
        include_telecontrol = obj.include_telecontrol

        if obj.routes.exists():
            active_filter = Q(
                positions__properties__supply_points__is_active=True,
                positions__properties__supply_points__status__token=activate_token,
            )
            if include_manual and not include_telecontrol:
                active_filter &= Q(
                    positions__properties__supply_points__meter__has_remote_reading=False
                ) | Q(
                    positions__properties__supply_points__meter__force_manual_reading=True
                )
            elif include_telecontrol and not include_manual:
                active_filter &= Q(
                    positions__properties__supply_points__meter__has_remote_reading=True,
                    positions__properties__supply_points__meter__force_manual_reading=False
                )
            return obj.routes.aggregate(
                total=Count(
                    'positions__properties__supply_points__meter',
                    filter=active_filter,
                    distinct=True,
                )
            )['total'] or 0

        if obj.fix_meters.exists():
            return obj.fix_meters.aggregate(
                total=Count(
                    'supply_points__id',
                    filter=Q(
                        supply_points__is_active=True,
                        supply_points__status__token=activate_token,
                    ),
                    distinct=True,
                )
            )['total'] or 0

        sp_base = SupplyPoint.objects.filter(
            is_active=True, status__token=activate_token
        )
        if not include_telecontrol:
            sp_base = sp_base.filter(Q(meter__has_remote_reading=False) | Q(meter__force_manual_reading=True))
        elif not include_manual:
            sp_base = sp_base.filter(meter__has_remote_reading=True, meter__force_manual_reading=False)
        return sp_base.count()