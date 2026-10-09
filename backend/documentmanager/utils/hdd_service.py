from datetime import datetime
import os
import locale
from django.conf import settings
from django.http import Http404, HttpResponse

#from documentmanager.utils.main_utils import get_unique_document_name

def upload_to_hdd(file, entity, field, entity_id, entity_token, folder, document_name, document, date=None):
    try:
        locale.setlocale(locale.LC_TIME, 'ca_ES.UTF-8')
    except locale.Error:
        pass
    date_year = date.year if date else datetime.now().year
    month_name = datetime.now().strftime('%B').capitalize()
    month_folder_name = (f'{field}_{month_name}').upper()
    
    #file_path = os.path.join(settings.DOCUMENT_STORAGE_PATH, f"{field}/{date_year}/{date_month}", f"{folder}_{entity_token}", entity, document_name)
    file_path = os.path.join(settings.DOCUMENT_STORAGE_PATH, 
                             f"{field}/{entity}/{date_year}/{month_folder_name}", 
                             document_name)
    folder_path = os.path.dirname(file_path)
    os.makedirs(folder_path, exist_ok=True)
    
    #document_name = get_unique_document_name(folder_path, document_name)+
    #file_path = os.path.join(folder_path, document_name)
    
    with open(file_path, 'wb') as f:
        chunk_size = 8192
        while True:
            chunk = file.read(chunk_size)
            if not chunk:
                break
            f.write(chunk)
    
    document.location = file_path
    document.location_url = None
    document.document_name = document_name
    document.save()

    return document

def download_document_from_hdd(document):

    document_path = str(document.location)
    if os.path.exists(document_path):
        try:
            with open(document_path, 'rb') as f:
                file_data = f.read()

            response = HttpResponse(file_data, content_type="application/octet-stream")
            response['Content-Disposition'] = f'attachment; filename="{document.document_name}"'
            return response
        except IOError:
            raise Http404("Could not read the file from the disk.")
    else:
        raise Http404(f"Document {document.document_name} not found on HDD.")

def delete_document_from_hdd(document):
    """Deletes a document file from the hard drive."""
    #delete or deactivate
    try:
        if document.location and os.path.exists(document.location):
            os.remove(document.location)
            print(f"Document deleted from HDD: {document.location}")
        else:
            print(f"Document not found on HDD or location is not set.")
    except Exception as e:
        print(f"Error deleting document from HDD: {e}")