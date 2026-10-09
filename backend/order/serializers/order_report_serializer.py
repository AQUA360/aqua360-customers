from rest_framework import serializers

from coredata.utils.name_utils import generate_token
from documentmanager.serializers import DocumentSerializer
from order.models import Operator, OrderReport, OrderReportDocument
from got.models import OrderFormSubmission, OrderForm
from order.serializers.operator_serializer import OperatorSerializer
from datetime import datetime, date
from django.db import transaction


class OrderFormSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderForm
        fields = '__all__'


class OrderFormSubmissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderFormSubmission
        fields = '__all__'


class OrderReportDocumentSerializer(serializers.ModelSerializer):
    file = DocumentSerializer(read_only=True, required=False, allow_null=True)
    class Meta:
        model = OrderReportDocument
        fields = '__all__'

class OrderReportSerializer(serializers.ModelSerializer):
    documents = OrderReportDocumentSerializer(many=True, read_only=True, required=False, allow_null=True)
    operator = OperatorSerializer(read_only=True, required=False, allow_null=True)
    
    operator_id = serializers.IntegerField(required=False, allow_null=True)
    filled_form = serializers.ListField(child=serializers.DictField(), write_only=True, required=False)
    
    class Meta:
        model = OrderReport
        fields = '__all__'
    
    def to_representation(self, instance):
        data = super().to_representation(instance)
        if instance.operator:
            data['operator_full_name'] = f"{instance.operator.name} {instance.operator.surname} ({instance.operator.token})"
        else:
            data['operator_full_name'] = None
        
        active_documents = instance.documents.filter(file__is_active=True)
        data['active_documents'] = active_documents.count()
        
        # Afegir informació del OrderForm via Order -> OrderType -> OrderForm
        if instance.order and instance.order.type:
            try:
                order_form = instance.order.type.orderform
                data['order_form'] = {
                    'id': order_form.id,
                    'name': order_form.name,
                    'structure': order_form.structure,
                    'created_at': order_form.created_at,
                    'updated_at': order_form.updated_at
                }
            except:
                data['order_form'] = None
        else:
            data['order_form'] = None
        
        # Afegir informació del OrderFormSubmission
        try:
            submission = instance.orderformsubmission
            data['form_submission'] = {
                'id': submission.id,
                'filled_form': submission.filled_form,
                'created_at': submission.created_at,
                'updated_at': submission.updated_at
            }
        except OrderFormSubmission.DoesNotExist:
            data['form_submission'] = None

        if instance.order and instance.order.change_meter_applied_at:
            applied_by = instance.order.change_meter_applied_by
            data['change_meter_status'] = {
                'applied': True,
                'applied_by': applied_by.get_full_name() or applied_by.username if applied_by else None,
                'applied_at': instance.order.change_meter_applied_at,
            }
        else:
            data['change_meter_status'] = None

        return data
    
    def _save_filled_form(self, report, filled_form):
        """
        Fusiona les respostes rebudes ({token, response}) amb l'OrderFormSubmission
        de l'informe. Manté la resta de claus de cada camp (name, type, required,
        response_url...) i afegeix els tokens que encara no hi eren.
        Si l'informe no té submissió i arriben respostes, la crea.
        """
        if not filled_form:
            return

        incoming = {}
        for item in filled_form:
            token = item.get('token')
            if not token:
                continue
            response = item.get('response')
            if response == '':
                response = None
            incoming[token] = response

        submission = OrderFormSubmission.objects.filter(order_report=report).first()

        if not submission:
            OrderFormSubmission.objects.create(
                order_report=report,
                filled_form=[{'token': t, 'response': r} for t, r in incoming.items()],
            )
            return

        current = submission.filled_form or []
        seen = set()
        for field in current:
            if isinstance(field, dict) and field.get('token') in incoming:
                token = field['token']
                field['response'] = incoming[token]
                if incoming[token] is None:
                    field.pop('response_url', None)
                seen.add(token)

        for token, response in incoming.items():
            if token not in seen:
                current.append({'token': token, 'response': response})

        submission.filled_form = current
        submission.save(update_fields=['filled_form', 'updated_at'])

    @transaction.atomic
    def create(self, validated_data):
        filled_form = validated_data.pop('filled_form', None)
        operator_id = validated_data.pop('operator_id', None)
        start_at = validated_data.get('start_at', None)
        end_at = validated_data.get('end_at', None)

        if operator_id:
            operator = Operator.objects.get(id=operator_id)
            validated_data['operator'] = operator

        if start_at and end_at:
            today = date.today()
            time_dedicated = (datetime.combine(today, end_at) - datetime.combine(today, start_at)).total_seconds() / 60
            validated_data['time_dedicated'] = time_dedicated

        validated_data['token'] = generate_token(OrderReport)
        report = super().create(validated_data)
        self._save_filled_form(report, filled_form)
        return report

    @transaction.atomic
    def update(self, instance, validated_data):
        filled_form = validated_data.pop('filled_form', None)
        operator_id = validated_data.pop('operator_id', None)
        start_at = validated_data.get('start_at', None)
        end_at = validated_data.get('end_at', None)

        if operator_id:
            operator = Operator.objects.get(id=operator_id)
            validated_data['operator'] = operator

        if start_at and end_at:
            today = date.today()
            time_dedicated = (datetime.combine(today, end_at) - datetime.combine(today, start_at)).total_seconds() / 60
            validated_data['time_dedicated'] = time_dedicated

        report = super().update(instance, validated_data)
        self._save_filled_form(report, filled_form)
        return report