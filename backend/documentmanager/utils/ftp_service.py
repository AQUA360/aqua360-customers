from datetime import datetime
import os
import locale
import ftplib
from django.conf import settings
from django.http import Http404, HttpResponse


def upload_to_ftp(file, entity, field, entity_id, entity_token, folder, document_name, document, date=None):
    print("Uploading to FTP")
    try:
        locale.setlocale(locale.LC_TIME, 'ca_ES.UTF-8')
    except locale.Error:
        pass
    date_year = date.year if date else datetime.now().year
    month_name = datetime.now().strftime('%B').capitalize()
    month_folder_name = (f'{field}_{month_name}').upper()
    
    remote_folder = f"{field}/{entity}/{date_year}/{month_folder_name}/{entity_token}"
    remote_file_path = os.path.join(remote_folder, document_name)
    
    ftp = ftplib.FTP(settings.FTP_HOST, settings.FTP_USER, settings.FTP_PASSWORD)
    ftp.encoding = 'utf-8'
    
    try:
        ftp.cwd(remote_folder)
    except ftplib.error_perm:
        for part in remote_folder.split('/'):
            try:
                ftp.cwd(part)  
            except ftplib.error_perm:
                ftp.mkd(part)  
                ftp.cwd(part)  
                
    """ try:
        ftp.cwd(remote_folder) 
        files = ftp.nlst()  
        if document_name in files:
            name, ext = os.path.splitext(document_name)
            counter = 1
            while True:
                unique_name = f"{name}({counter}){ext}"
                if unique_name not in files:
                    document_name = unique_name
                    remote_file_path = os.path.join(remote_folder, document_name)
                    break
                counter += 1
    except ftplib.error_perm as e:
        print(f"Error checking for existing files: {e}") """            
                
    print(f"Uploading file to {remote_file_path}")
    ftp.storbinary(f'STOR {document_name}', file)

    ftp.quit()

    document.location = None  
    document.location_url = f"ftp://{settings.FTP_HOST}/{remote_file_path}"
    document.document_name = document_name
    document.save()

    return document

def download_document_from_ftp(document):
    print("Downloading from FTP")

    remote_file_path = document.location_url.replace("ftp://", "").split("/", 1)[1]
    remote_folder = "/".join(remote_file_path.split("/")[:-1])
    document_name = document.document_name

    ftp = ftplib.FTP(settings.FTP_HOST, settings.FTP_USER, settings.FTP_PASSWORD)
    ftp.encoding = 'utf-8'

    try:
        ftp.cwd(remote_folder)
        print(f"Changing to directory: {remote_folder}")

        file_data = []

        def callback(data):
            file_data.append(data)

        print(f"Downloading file: {document_name}")
        ftp.retrbinary(f'RETR {document_name}', callback)

        file_data = b''.join(file_data)

        response = HttpResponse(file_data, content_type="application/octet-stream")
        response['Content-Disposition'] = f'attachment; filename="{document_name}"'
        return response

    except ftplib.error_perm as e:
        raise Http404(f"Permission error: {str(e)}")
    except FileNotFoundError:
        raise Http404(f"Document {document_name} not found on FTP.")
    except Exception as e:
        raise Http404(f"An error occurred while downloading the document: {str(e)}")
    finally:
        ftp.quit()