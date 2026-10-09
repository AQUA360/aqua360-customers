from rest_framework import serializers
from billing.models import Invoice, Reading
from coredata.models import ConfigProject


class BillingContractInvoicesOVSerializer(serializers.Serializer):
    
    contract_number = serializers.CharField(source='contract.token', read_only=True)
    contract_serie = serializers.CharField(source='contract.serie_final', read_only=True)
    invoice_number = serializers.CharField(source='token', read_only=True)
    invoice_date = serializers.DateField(source='issue_date', read_only=True)
    invoice_amount = serializers.FloatField(source='total_final', read_only=True)
    invoice_status = serializers.CharField(source='status.token', read_only=True)
    
    class Meta:
        model = Invoice
        fields = ['contract_number', 'contract_serie', 'invoice_number', 'invoice_date', 
                  'invoice_amount', 'invoice_status']


class ContractConsumptionOVSerializer(serializers.Serializer):
    contract_number = serializers.CharField(source='contract.token', read_only=True)
    contract_serie = serializers.CharField(source='contract.serie_final', read_only=True)
    
    class Meta:
        model = Reading
        fields = ['contract_number', 'contract_serie', 'reading_value', 'reading_date']
    
    def to_representation(self, instance):
        data = super().to_representation(instance)
        invoice = None
        try:
            invoice_pending_status = ConfigProject.objects.get(token='invoice_status_pending_token').value
            invoice_cancelled_status = ConfigProject.objects.get(token='invoice_status_cancelled_token').value
            invoices = instance.invoices.all().exclude(status__token__in=[invoice_pending_status, invoice_cancelled_status])
            if invoices.count() > 0:
                invoice = invoices.order_by('-created_at').first()
        except:
            pass
        data['invoice_number'] = invoice.token
        data['invoice_serie'] = invoice.serie_final
        data['meter_code'] = instance.meter.code if instance.meter.code else instance.meter.token
        data['origin'] = "ESTIMATED" if instance.is_estimated else "CALCULATED"
        data['consumption'] = instance.real_consumption if instance.real_consumption else instance.calculated_value
        return data