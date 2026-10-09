import boto3
from datetime import datetime
import os
import ftplib
from botocore.exceptions import ClientError
from django.core.exceptions import ValidationError
from django.conf import settings
from django.http import Http404, HttpResponse

from documentmanager.utils.alfresco_service import *
from documentmanager.utils.aws_service import *
from documentmanager.utils.ftp_service import download_document_from_ftp, upload_to_ftp
from documentmanager.utils.hdd_service import delete_document_from_hdd, download_document_from_hdd, upload_to_hdd
from documentmanager.utils.sign_certificate_service import *
from documentmanager.utils.azure_service import *
from ..models import Document

def get_next_version(entity, field, entity_id, folder, base_name):
    latest = Document.objects.filter(
        entity=entity,
        field=field,
        entity_id=entity_id,
        document_name__startswith=base_name
    ).order_by('-version').first()

    return (latest.version + 1) if latest else 1

def delete_document(document):
    if document is None:
        return None
    
    if document.service == 'hdd':
        return delete_document_from_hdd(document)
    else:
        #raise ValidationError(f"Unsupported service: {document.service}")
        print(f"Unsupported service: {document.service} Unable to delete document")

def download_document(document):
    if document.service == 'hdd':
        return download_document_from_hdd(document)
    elif document.service == 'ftp':
        return download_document_from_ftp(document)
    elif document.service == 'azure':
        return download_document_from_azure(document)
    elif document.service == 'cloud':
        pass
    elif document.service == 'aws':
        """ bucket_name = document.location  
        object_key = document.folder
        return download_document_from_aws(bucket_name, object_key)   """
        return download_document_from_aws(document)
    elif document.service == 'alfresco':
        return download_document_from_alfresco(document)
    else:
        raise Http404("Document service not supported yet.")

def download_multiple_documents(document_ids, service):
    if service == 'aws':
        return download_multiple_documents_from_aws(document_ids)
    elif service == 'azure':
        return download_multiple_documents_from_azure(document_ids)
    else:
        raise ValidationError(f"Unsupported service: {service}")

def upload_document(file, entity, field, entity_id, entity_token, folder, service, document_name, date=None):
    """Function to handle document uploads depending on the service."""
    if '.' in document_name:
        ext = document_name[document_name.find('.'):]
        base_name = document_name[:document_name.find('.')]
        document_name = f"{base_name}{ext}"
    else:
        ext = ''
        base_name = document_name
        document_name = f"{document_name}"
    
    version = get_next_version(entity, field, entity_id, folder, base_name)
    if version > 1:
        versioned_name = f"{base_name}({version}){ext}" if service not in ['alfresco','azure'] else document_name
    else:
        versioned_name = document_name
    
    latest_doc = Document.objects.filter(
        entity=entity,
        field=field,
        entity_id=entity_id,
        document_name__startswith=base_name
    ).order_by('-version').first()
    
    document = Document(
        entity=entity,
        field=field,
        entity_id=entity_id,
        document_name=versioned_name,
        service=service,
        file=None,
        #file=file if service in ['hdd','ftp'] else None,
        version=version,
        parent_document=latest_doc if latest_doc else None
    )
    
    # if ext.lower() == '.pdf':
        # if is_signed_pdf(file):
            # print("file is signed")
        # else:
            # print("file is not signed")
    
    file.seek(0)
    
    if service == 'hdd':
        document = upload_to_hdd(file, entity, field, entity_id, entity_token, folder, versioned_name, document, date)
    elif service == 'ftp':
        document = upload_to_ftp(file, entity, field, entity_id, entity_token, folder, versioned_name, document, date)
    elif service == 'azure':
        document = upload_to_azure(file, entity, field, entity_id, entity_token, folder, versioned_name, document, date)
    elif service == 'cloud':
        pass
    elif service == 'aws':
        document = upload_to_aws(file, document, versioned_name, field, entity)
    elif service == 'alfresco':
        document = upload_to_alfresco(file, entity, field, entity_id, entity_token, folder, versioned_name, document, date)
    else:
        raise ValidationError(f"Invalid service: {service}")
    
    #do not delete old document versions
    #Document.objects.filter(entity=entity, field=field, entity_id=entity_id).exclude(id=document.id).delete()
    
    return document

    