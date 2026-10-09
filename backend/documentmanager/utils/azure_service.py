import io
import logging
import os
import uuid
import locale
from datetime import datetime
import calendar
from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient, ContainerClient, BlobBlock, BlobClient, StandardBlobTier, ContentSettings
from azure.core.credentials import AzureNamedKeyCredential
from azure.core.exceptions import ResourceExistsError
from django.conf import settings
from django.http import Http404, HttpResponse

from documentmanager.models import Document

def authenticate_azure():
    account_name = settings.AZURE_ACCOUNT_NAME
    account_key = settings.AZURE_ACCOUNT_KEY
    account_url = settings.AZURE_ACCOUNT_URL
    print("account_url")
    print(account_url)
    #credential = DefaultAzureCredential()
    credential = AzureNamedKeyCredential(account_name, account_key)
    blob_service_client = BlobServiceClient(account_url=account_url, credential=credential)

    try:
        blob_service_client.get_service_properties()  
        print("\n\n\033[92mAzure Blob Storage connection successful.\033[0m")
    except Exception as e:
        raise Exception(f"Azure connection failed: {e}")

    return blob_service_client

def upload_to_azure(file, entity, field, entity_id, entity_token, folder, document_name, document, date=None):
    print("\n\nUploading to Azure")
    try:
        locale.setlocale(locale.LC_TIME, 'ca_ES.UTF-8')
    except locale.Error:
        pass
    date_year = date.year if date else datetime.now().year
    month_name = datetime.now().strftime('%B').capitalize()
    month_folder_name = (f'{field}_{month_name}').upper()

    container_name = settings.AZURE_CONTAINER_NAME

    blob_name = f"{field}/{entity}/{date_year}/{month_folder_name}/{document_name}"

    blob_service = authenticate_azure()
    print("authenticated")
    container_client = blob_service.get_container_client(container_name)
    print("\ngetting container")
    print(container_client)
    
    

    try:
        print("before try")
        if not container_client.exists():
            print("\ncreating container")
            try:
                container_client.create_container()
                print(f"Created container: {container_name}")
            except Exception as e:
                raise Exception(f"A container with this name already exists: {e}")
    except Exception as e:
        raise Exception(f"Failed to ensure container: {e}")

    print("container exists")
        
    #check if blob exists
    version = 1
    blob_found = True
    while blob_found:
        blob_client = container_client.get_blob_client(blob_name)
        
        if not blob_client.exists():
            blob_found = False
        else:
            blob_name = f"{field}/{entity}/{date_year}/{month_folder_name}/{document_name[:document_name.find('.'):]}({version}){document_name[document_name.find('.'):]}"
            version += 1
    
    #BLOBL METADATA AND TAGS
    """ properties = blob_client.get_blob_properties()
    blob_headers = ContentSettings(
        content_type=properties.content_settings.content_type,
        content_encoding=properties.content_settings.content_encoding,
        content_language="en-US",
        content_disposition=properties.content_settings.content_disposition,
        cache_control=properties.content_settings.cache_control,
        content_md5=properties.content_settings.content_md5
        )
    blob_client.set_http_headers(blob_headers) """
    file_date = date.strftime('%Y%m%d%H%M') if date else datetime.now().strftime('%Y%m%d%H%M')
    
    from order.middleware import get_current_user
    current_user = get_current_user()
    sample_tags = {"Date": file_date, "Last Upload User": current_user.username if current_user else "Admin"}
    
    #blob_client = container_client.get_blob_client(blob_name)
    try:
        blob_client.upload_blob(data=file, overwrite=True, tags=sample_tags) 
        print(f"Uploaded blob: {blob_name}")
    except Exception as e:
        raise Exception(f"Failed to upload blob: {e}")

    document.location = container_name
    document.location_url = blob_name
    document.document_name = document_name
    document.save()

    return document


def download_document_from_azure(document):
    print("Downloading from Azure")
    
    blob_service = authenticate_azure()
    print("authenticated")
    try:
        blob_client = blob_service.get_blob_client(container=document.location, blob=document.location_url)
        file_content = blob_client.download_blob().readall()
        response = HttpResponse(file_content, content_type="application/octet-stream")
        response['Content-Disposition'] = f'attachment; filename="{document.document_name}"'
        return response
    except ResourceExistsError:
        raise Http404(f"Document {document.document_name} not found on Azure.")
    except Exception as e:
        raise Http404(f"An error occurred while downloading the document: {str(e)}")

def download_multiple_documents_from_azure(document_ids):
    blob_service = authenticate_azure()
    files = []  
    
    documents = Document.objects.filter(id__in=document_ids)

    for document in documents:
        try:
            blob_client = blob_service.get_blob_client(
                container=document.location, blob=document.location_url
            )  
            file_content = blob_client.download_blob().readall()
            filename = document.document_name
            files.append((filename, file_content))
        except ResourceExistsError:
            logging.error(
                f"Document {document.document_name} not found on Azure."
            )  
            continue
        except Exception as e:
            logging.error(
                f"Error downloading {document.document_name} from Azure: {e}"
            )  
            continue

    return files