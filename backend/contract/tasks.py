import datetime
from celery import shared_task
from django.utils import timezone
from contract.utils.bail_service import pending_bail_contract_termination
from coredata.models import ConfigProject
from logger.models import LogContractExpiredBonificationsVariables
from .models import Bonification, Contract, ContractTerminationRequest, Variable

@shared_task
def deactivate_expired_bonifications_variables():
    now = timezone.now().date()
    expired_bonifications = Bonification.objects.filter(end_at__lt=now, is_active=True)
    expired_variables = Variable.objects.filter(end_at__lt=now, is_active=True)
    
    for variable in expired_variables:
        LogContractExpiredBonificationsVariables.objects.get_or_create(
            object=variable.contract if variable.contract else None,
            expired_bonification=variable.bonification if variable.bonification else None,
            expired_variable=variable,
            expiring_date = timezone.now().date()
        )
        
        variable.contract = None
        variable.is_active = False
        if variable.bonification:
            bonification = variable.bonification
            bonification.contract = None
            bonification.is_active = False
            bonification.save()
            
        variable.save()
        
@shared_task
def return_bails_termination_requests():
    days_after_termination = ConfigProject.objects.get(token='return_bails_after').value
    contract_termination_requests_approved = ContractTerminationRequest.objects.filter(
        approved_at__lte=timezone.now().date() - datetime.timedelta(days=int(days_after_termination)))
    for contract_termination_request in contract_termination_requests_approved:
        contract = contract_termination_request.contract
        if contract:
            pending_bail_contract_termination(None, contract)


@shared_task
def fill_contract_use_aca_task(update_all_contracts=False):
    try:
        from contract.utils.use_aca_service import run_fill_contract_use_aca
        return run_fill_contract_use_aca(
            update_all_contracts=update_all_contracts,
            dry_run=False,
        )
    except Exception as e:
        return {
            'status': 'error',
            'message': f'Error filling contract use ACA: {e}',
        }


@shared_task
def export_contracts_csv_task(query_params):
    try:
        from contract.filters.contract_filter import ContractFilter
        from contract.utils.contract_list_queryset import default_contract_list_queryset
        from contract.utils.contract_csv_export import build_contract_export_csv_bytes
        from documentmanager.utils.main_utils import upload_document
        from django.core.files.base import ContentFile
        from django.conf import settings
        
        # Filtrar el queryset segons els query_params rebuts
        filterset = ContractFilter(
            data=query_params,
            queryset=default_contract_list_queryset(),
        )
        filtered = filterset.qs
        
        csv_bytes = build_contract_export_csv_bytes(filtered)
        
        filename = f"contracts_export_{timezone.now().strftime('%Y%m%d_%H%M%S')}.csv"
        service = settings.DOCUMENT_MANAGER_SERVICES.get("statistics", "hdd")
        content_file = ContentFile(csv_bytes, name=filename)
        
        document = upload_document(
            file=content_file,
            entity="CONTRACT",
            field="EXPORT",
            entity_id=0,
            entity_token="CONTRACT_EXPORT",
            folder="",
            service=service,
            document_name=filename,
            date=timezone.now()
        )
        
        return {
            "status": "success",
            "message": "Contracts export generated successfully",
            "document_id": document.id,
            "filename": filename
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Error generating contracts export: {str(e)}"
        }