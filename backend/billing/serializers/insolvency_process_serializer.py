from rest_framework import serializers

from auth.serializers import UserMinimalSerializer
from billing.models import InsolvencyProcess, InsolvencyProcessContract
from billing.utils.insolvency_service import (
    delinquency_status_tokens,
    delinquency_targets,
    excluded_invoice_status_tokens,
    process_invoices,
)


class InsolvencyInvoiceSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    serie_final = serializers.CharField(allow_null=True)
    issue_date = serializers.DateField(allow_null=True)
    total_final = serializers.DecimalField(max_digits=12, decimal_places=2, allow_null=True)
    left_to_pay = serializers.DecimalField(max_digits=12, decimal_places=2, allow_null=True)
    status_name = serializers.CharField(source='status.name', allow_null=True, default=None)
    contract_token = serializers.CharField(source='contract.token', allow_null=True, default=None)
    # Estats als quals l'usuari la pot passar: endowment (morositat) i/o irrecoverable
    delinquency_targets = serializers.SerializerMethodField()

    def get_delinquency_targets(self, obj):
        # Una sola lectura de la configuració per a totes les files
        if 'insolvency_delinquency_tokens' not in self.context:
            self.context['insolvency_delinquency_tokens'] = delinquency_status_tokens()
        return delinquency_targets(obj, self.context['insolvency_delinquency_tokens'])


class InsolvencyContractSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    token = serializers.CharField(allow_null=True)
    status_name = serializers.CharField(source='status.name', allow_null=True, default=None)
    debt_management_name = serializers.CharField(source='debt_management.name', allow_null=True, default=None)
    payment_type = serializers.SerializerMethodField()
    has_iban = serializers.SerializerMethodField()

    def get_payment_type(self, obj):
        payment_type = obj.payment.type if obj.payment_id and obj.payment and obj.payment.type_id else None
        if not payment_type:
            return None
        return {'id': payment_type.id, 'token': payment_type.token, 'name': payment_type.name}

    def get_has_iban(self, obj):
        return bool(obj.payment_id and obj.payment and obj.payment.IBAN_id)


class InsolvencyProcessContractSerializer(serializers.ModelSerializer):
    contract_token = serializers.CharField(source='contract.token', read_only=True)
    previous_payment_type_name = serializers.CharField(source='previous_payment_type.name', read_only=True, default=None)
    new_payment_type_name = serializers.CharField(source='new_payment_type.name', read_only=True, default=None)
    previous_debt_management_name = serializers.CharField(source='previous_debt_management.name', read_only=True,
                                                          default=None)

    class Meta:
        model = InsolvencyProcessContract
        fields = [
            'id', 'contract', 'contract_token', 'previous_payment_type_name', 'new_payment_type_name',
            'payment_restored', 'previous_debt_management_name', 'debt_management_changed',
            'debt_management_restored', 'created_at',
        ]


class InsolvencyProcessListSerializer(serializers.ModelSerializer):
    person_name = serializers.SerializerMethodField()
    person_token = serializers.CharField(source='person.token', read_only=True)
    kind_display = serializers.CharField(source='get_kind_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    invoices_count = serializers.SerializerMethodField()
    user = UserMinimalSerializer(read_only=True)

    class Meta:
        model = InsolvencyProcess
        fields = [
            'id', 'created_at', 'person', 'person_name', 'person_token', 'kind', 'kind_display',
            'start_date', 'case_number', 'status', 'status_display', 'invoices_count', 'user', 'closed_at',
        ]

    def _excluded_status(self):
        # Una sola lectura per petició: el context és compartit per totes les files del llistat
        if 'insolvency_excluded_status' not in self.context:
            self.context['insolvency_excluded_status'] = excluded_invoice_status_tokens()
        return self.context['insolvency_excluded_status']

    def get_invoices_count(self, obj):
        if obj.status == InsolvencyProcess.STATUS_OPEN:
            return process_invoices(obj, self._excluded_status()).count()
        return getattr(obj, 'invoices_count', None) or obj.invoices.count()

    def get_person_name(self, obj):
        return str(obj.person).strip() if obj.person_id else None


class InsolvencyProcessSerializer(InsolvencyProcessListSerializer):
    invoices = serializers.SerializerMethodField()
    contracts = InsolvencyProcessContractSerializer(many=True, read_only=True)
    documents = serializers.SerializerMethodField()
    closed_by = UserMinimalSerializer(read_only=True)
    end_date = serializers.SerializerMethodField()

    class Meta(InsolvencyProcessListSerializer.Meta):
        fields = InsolvencyProcessListSerializer.Meta.fields + [
            'observation', 'invoices', 'contracts', 'documents', 'closed_by', 'anomaly', 'end_date',
        ]

    def get_end_date(self, obj):
        # Data de tancament triada (la de fi de l'anomalia); closed_at és el moment de l'operació
        if obj.status != InsolvencyProcess.STATUS_CLOSED:
            return None
        if obj.anomaly_id and obj.anomaly and obj.anomaly.end_date:
            return obj.anomaly.end_date
        return obj.closed_at.date() if obj.closed_at else None

    def get_invoices(self, obj):
        # Obert: totes les factures emeses des de la data, també les noves; tancat: les que hi havia en tancar-lo
        invoices = process_invoices(obj, self._excluded_status()).select_related('contract')
        return InsolvencyInvoiceSerializer(invoices, many=True, context=self.context).data

    def get_documents(self, obj):
        return [
            {'id': document.id, 'document_name': document.document_name, 'date': document.date}
            for document in obj.documents.filter(is_active=True).order_by('id')
        ]
