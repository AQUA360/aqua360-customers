import datetime
import uuid
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied

from auth.serializers import UserMinimalSerializer
from contract.serializers.contract_minimal_serializer import ContractMinimalSerializer
from notification.utils import recurrence as recurrence_utils
from notification.utils.task_notifications import notify_due_today
from ..models import *

# Camps de la tasca que es copien a la plantilla de la sèrie i a les ocurrències pendents.
SERIES_FIELDS = ['name', 'description', 'color', 'user', 'time']


class CalendarTaskRecurrenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = CalendarTaskRecurrence
        fields = ['id', 'frequency', 'interval', 'weekdays', 'start_date', 'end_date', 'is_active']
        read_only_fields = ['id', 'start_date', 'is_active']

    def validate_weekdays(self, value):
        """Return sorted unique weekday numbers, rejecting values outside 0 to 6."""
        try:
            days = sorted({int(d) for d in (value or [])})
        except (TypeError, ValueError):
            raise serializers.ValidationError('Invalid weekdays')
        if any(d < 0 or d > 6 for d in days):
            raise serializers.ValidationError('Weekdays must be between 0 (monday) and 6 (sunday)')
        return days


class CalendarTaskOrderSerializer(serializers.ModelSerializer):
    type = serializers.CharField(source='type.name', read_only=True, default=None)

    class Meta:
        model = Order
        fields = ['id', 'token', 'type']


class CalendarTaskSerializer(serializers.ModelSerializer):

    user = UserMinimalSerializer(read_only=True)
    user_id = serializers.PrimaryKeyRelatedField(source='user', queryset=User.objects.all(), write_only=True, required=False, allow_null=True)
    contract = ContractMinimalSerializer(read_only=True, required=False, allow_null=True)
    order = CalendarTaskOrderSerializer(read_only=True)
    all_users = serializers.BooleanField(write_only=True, required=False, allow_null=True)
    recurrence = CalendarTaskRecurrenceSerializer(read_only=True)
    # Regla de recurrència: crea o canvia la sèrie; `null` amb apply_to_series l'atura.
    recurrence_rule = CalendarTaskRecurrenceSerializer(write_only=True, required=False, allow_null=True)
    # En una ocurrència d'una sèrie: aplicar el canvi també a les ocurrències pendents posteriors.
    apply_to_series = serializers.BooleanField(write_only=True, required=False, default=False)
    is_overdue = serializers.SerializerMethodField()

    class Meta:
        model = CalendarTask
        fields = '__all__'
        read_only_fields = ['token', 'source', 'source_key', 'done_at', 'done_by', 'notified_at']

    def get_is_overdue(self, obj):
        """Return whether an unfinished task is dated before today."""
        return bool(not obj.task_done and obj.set_date and obj.set_date < timezone.localdate())

    def validate(self, attrs):
        """Require a recurring task start date and reject an earlier end date."""
        rule = attrs.get('recurrence_rule')
        if rule is not None and not self.instance and not attrs.get('set_date'):
            raise serializers.ValidationError({'set_date': 'A recurring task needs a start date'})
        start = attrs.get('set_date') or (self.instance.set_date if self.instance else None)
        if rule and rule.get('end_date') and start and rule['end_date'] < start:
            raise serializers.ValidationError({'recurrence_rule': 'The end date must be after the start date'})
        return attrs

    def _visible_tasks(self):
        """Ocurrències que l'usuari pot veure (com al viewset): les seves i les de tothom."""
        user = self._request_user()
        return Q(user=user) | Q(user__isnull=True)

    def _check_can_manage_series(self, recurrence):
        """Deny changes to a private recurrence owned by another user."""
        # Una sèrie privada d'un altre usuari no es pot modificar encara que alguna
        # de les seves ocurrències s'hagi fet visible per a tothom.
        user = self._request_user()
        if recurrence.user_id is not None and (not user or recurrence.user_id != user.id):
            raise PermissionDenied('This series belongs to another user')

    def _request_user(self):
        """Return the authenticated request user, or None without one."""
        request = self.context.get('request')
        return request.user if request and request.user.is_authenticated else None

    def _apply_assignment(self, validated_data):
        """Sets validated_data['user'] from 'all_users'/'user_id' when either was
        sent. Leaves 'user' untouched when neither is present, so payloads that
        only update e.g. task_done/color don't silently reassign the task."""
        has_all_users = 'all_users' in validated_data
        all_users = validated_data.pop('all_users', None)
        has_user = 'user' in validated_data

        if not has_all_users and not has_user:
            return

        if all_users:
            validated_data['user'] = None
        elif not has_user:
            validated_data['user'] = self._request_user()
        # else: validated_data['user'] already holds the chosen user_id

    def _apply_done(self, instance, validated_data):
        """Update completion time and user when marking a task done or reopening it."""
        if 'task_done' not in validated_data:
            return
        was_done = instance.task_done if instance else False
        if validated_data['task_done'] and not was_done:
            validated_data['done_at'] = timezone.now()
            validated_data['done_by'] = self._request_user()
        elif not validated_data['task_done']:
            validated_data['done_at'] = None
            validated_data['done_by'] = None

    def _new_recurrence(self, rule, template):
        """Create a recurrence from the rule and task template for the request user."""
        return CalendarTaskRecurrence.objects.create(
            token=str(uuid.uuid4()),
            created_by=self._request_user(),
            **rule,
            **{field: template.get(field) for field in SERIES_FIELDS},
        )

    @transaction.atomic
    def create(self, validated_data):
        """Create a task or recurrence and notify tasks due today after commit."""
        rule = validated_data.pop('recurrence_rule', None)
        validated_data.pop('apply_to_series', None)
        self._apply_assignment(validated_data)
        if 'user' not in validated_data:
            validated_data['user'] = self._request_user()
        self._apply_done(None, validated_data)

        if not rule:
            validated_data['token'] = uuid.uuid4()
            task = CalendarTask.objects.create(**validated_data)
            notify_due_today([task.id])
            return task

        # Tasca recurrent: es crea la sèrie i se'n generen les ocurrències; es
        # retorna la primera, que és l'única que rep la resta de camps (contracte...).
        recurrence = self._new_recurrence(
            {**rule, 'start_date': validated_data['set_date']}, validated_data,
        )
        recurrence_utils.generate_occurrences(recurrence)
        first = recurrence.tasks.order_by('set_date').first()
        if not first:
            raise serializers.ValidationError({'recurrence_rule': 'The rule does not generate any occurrence'})
        extra = {k: v for k, v in validated_data.items() if k not in SERIES_FIELDS + ['set_date']}
        if extra:
            CalendarTask.objects.filter(pk=first.pk).update(**extra)
            first.refresh_from_db()
        notify_due_today([first.id])
        return first

    @transaction.atomic
    def update(self, instance, validated_data):
        """Update a task and optionally its future pending series occurrences."""
        has_rule = 'recurrence_rule' in validated_data
        rule = validated_data.pop('recurrence_rule', None)
        apply_to_series = validated_data.pop('apply_to_series', False)
        if apply_to_series and instance.recurrence:
            self._check_can_manage_series(instance.recurrence)
        self._apply_assignment(validated_data)
        self._apply_done(instance, validated_data)
        # Si canvia de dia o es torna a obrir, s'ha de tornar a avisar quan toqui
        moved = 'set_date' in validated_data and validated_data['set_date'] != instance.set_date
        reopened = validated_data.get('task_done') is False and instance.task_done
        if moved or reopened:
            validated_data['notified_at'] = None

        instance = super().update(instance, validated_data)
        # Si la tasca passa a ser d'avui (o s'havia creat sense avisar), s'avisa ara
        notify_due_today([instance.id])
        recurrence = instance.recurrence

        if rule and not recurrence:
            # Una tasca puntual passa a ser recurrent a partir de la seva data.
            recurrence = self._new_recurrence(
                {**rule, 'start_date': instance.set_date},
                {field: getattr(instance, field) for field in SERIES_FIELDS},
            )
            instance.recurrence = recurrence
            instance.save(update_fields=['recurrence'])
            recurrence_utils.generate_occurrences(recurrence)
            return instance

        if not recurrence or not apply_to_series:
            return instance

        visible = self._visible_tasks()
        if has_rule and rule is None:
            recurrence_utils.stop_from(recurrence, instance.set_date + datetime.timedelta(days=1), tasks_filter=visible)
            return instance

        series_values = {f: getattr(instance, f) for f in SERIES_FIELDS}
        for field, value in series_values.items():
            setattr(recurrence, field, value)
        if rule:
            for field, value in rule.items():
                setattr(recurrence, field, value)
            recurrence.start_date = instance.set_date
        recurrence.save()

        if rule:
            recurrence_utils.regenerate_from(recurrence, instance.set_date + datetime.timedelta(days=1), tasks_filter=visible)
        else:
            recurrence.tasks.filter(visible, set_date__gt=instance.set_date, task_done=False).update(**series_values)
        return instance
