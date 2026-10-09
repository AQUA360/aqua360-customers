import base64
import mimetypes
from django.http import HttpResponse
import requests
from datetime import datetime
from django.conf import settings
from django.core.exceptions import ValidationError
import calendar
import locale

from documentmanager.models import Document

def download_document_from_alfresco(document):
    token = get_alfresco_token()
    encoded_token = encode_token(token)
    
    location = document.location
    folder_id = decode_token(location)
    print("folder_id")
    print(folder_id)
    
    folder = check_folder_exists_by_id(encoded_token, folder_id)
    if not folder:
        print("folder does not exist")
        raise Exception("Folder does not exist")
    return get_document(encoded_token, folder_id, document.document_name)

def download_multiple_documents_from_alfresco(document_ids):
    
    token = get_alfresco_token()
    encoded_token = encode_token(token)
    
    files = []
    for document_id in document_ids:
        document = Document.objects.get(id=document_id)
        files.append((document.document_name, download_document_from_alfresco(document)))
    return files

def upload_to_alfresco(file, entity, field, entity_id, entity_token, folder, versioned_name, document, date):
    token = get_alfresco_token()
    encoded_token = encode_token(token)
    
    """ if not check_alfresco_connection(encoded_token):
        raise Exception("Alfresco connection failed") """
    
    try:
        locale.setlocale(locale.LC_TIME, 'ca_ES.UTF-8')
    except locale.Error:
        pass
    date_year = date.year if date else datetime.now().year
    month_name = datetime.now().strftime('%B').capitalize()
    month_folder_name = (f'{field}_{month_name}').upper()
    #folder_name = f'{field}/{date_year}/{date_month}/{versioned_name}'
    
    """ 
    customers_folder = check_folder_exists(encoded_token, 'ABONATS_TEST')
    if customers_folder is None:
        print("customers folder does not exist")
        customers_folder = create_folder(encoded_token, 'ABONATS_TEST')
    else:
        print("customers folder exists")
    
    field_folder = check_folder_exists(encoded_token, field, customers_folder.get('id'))
    if field_folder is None:
        print("field folder does not exist")
        field_folder = create_folder(encoded_token, field, customers_folder.get('id'))
    else:
        print("field folder exists")
    
    date_year_folder = check_folder_exists(encoded_token, date_year, field_folder.get('id'))
    if date_year_folder is None:
        print("date_year folder does not exist")
        date_year_folder = create_folder(encoded_token, date_year, field_folder.get('id'))
    else:
        print("date_year folder exists")
    
    date_month_folder = check_folder_exists(encoded_token, month_folder_name, date_year_folder.get('id'))
    if date_month_folder is None:
        print("date_month folder does not exist")
        date_month_folder = create_folder(encoded_token, month_folder_name, date_year_folder.get('id'))
    else:
        print("date_month folder exists")
    """
    
    customers_folder = ensure_folder_exists(encoded_token, "ABONATS_TEST")
    field_folder = ensure_folder_exists(
            encoded_token, field, customers_folder.get("id")
        )
    entity_folder = ensure_folder_exists(
            encoded_token, entity, field_folder.get("id")
        )
    date_year_folder = ensure_folder_exists(
            encoded_token, date_year, entity_folder.get("id")
        )
    date_month_folder = ensure_folder_exists(
            encoded_token, month_folder_name, date_year_folder.get("id")
        )
    print("folders checkd/created")
    document.document_name = versioned_name
    if document.version > 1 and document.parent_document and document.parent_document.service == 'alfresco':
        print("in versioned")
        parent_token = decode_token(document.parent_document.location)
        doc_id = get_document_id(encoded_token, parent_token, document.parent_document.document_name)
        document_folder = upload_versioned_document(encoded_token, file, versioned_name, doc_id, document.parent_document.document_name, date_month_folder.get('id'))
    else:
        print("not in versioned")
        #check if document name exists
        document_folder = upload_document(encoded_token, file, versioned_name, document, date_month_folder.get('id'))
    document_folder = encode_token(document_folder)
    
    document.location = document_folder
    document.save()
    
    return document
    

#
#FOLDER FUNCTIONS
#

def ensure_folder_exists(encoded_token, folder_name, parent_id=None):
    
    folder = check_folder_exists(encoded_token, folder_name, parent_id)
    if folder is None:
        print(f"{folder_name} folder does not exist")
        folder = create_folder(encoded_token, folder_name, parent_id if parent_id else "-my-")
    else:
        print(f"{folder_name} folder exists")
    return folder

def check_folder_exists(ticket, folder, parent_folder=None, description=''):
    url = f"{settings.ALFRESCO_BASE_URL}/alfresco/api/-default-/public/search/versions/1/search"
    print("Checking folder exists using POST /search...")

    headers = {
        "Authorization": f"Basic {ticket}",
        "accept": "application/json",
        "Content-Type": "application/json"
    }
    cm_folder_type = "cm:folder"

    query_parts = [f'cm:name:"{folder}"', f'TYPE:"{cm_folder_type}"']
    if parent_folder:
        #query_parts.append(f'PATH:"{parent_folder}"')
        query_parts.append(f'ANCESTOR:\"workspace://SpacesStore/{parent_folder}\"')

    query_str = " AND ".join(query_parts)
    
    data = {
        "query": {
            "query": query_str
        },
        "paging": {
            "maxItems": 1000,
            "skipCount": 0
        }
    }

    response = requests.post(url, headers=headers, json=data)

    if response.status_code == 200:
        results = response.json()['list']['entries']
        print("search folder results")
        if results:
            # Folder exists, return its name and ID
            folder_name = results[0]['entry']['name']
            folder_id = results[0]['entry']['id']
            folder_data = {
                'name': folder_name,
                'id': folder_id
            }
            return folder_data
        else:
            # Folder does not exist
            return None
    else:
        print(f"Error checking folder: {response.status_code} - {response.text}")
        return None

def check_folder_exists_by_id(ticket, folder_id):
    url = f"{settings.ALFRESCO_BASE_URL}/alfresco/api/-default-/public/alfresco/versions/1/nodes/{folder_id}"
    print("Checking folder exists using POST /search...")

    headers = {
        "Authorization": f"Basic {ticket}",
        "Accept": "application/json"
    }

    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        print("json results check folder exists")
        result = response.json()
        if result:
            # Folder exists, return its name and ID
            folder_name = result['entry']['name']
            folder_id = result['entry']['id']
            folder_data = {
                'name': folder_name,
                'id': folder_id
            }
            return folder_data
        else:
            # Folder does not exist
            return None
    else:
        print(f"Error checking folder: {response.status_code} - {response.text}")
        return None

def create_folder(ticket, folder, parent_folder='-my-', description=''):
    """ 
    FOLDER CREATION INFO
    https://docs.alfresco.com/content-services/6.0/develop/rest-api-guide/folders-files/#createfolder
    """
    
    url = f"{settings.ALFRESCO_BASE_URL}/alfresco/api/-default-/public/alfresco/versions/1/nodes/{parent_folder}/children"
    print("Creating folder...")
    headers = {
        "Authorization": f"Basic {ticket}",
        "Accept": "application/json"
    }
    data = {
        'name': folder,
        'nodeType': 'cm:folder',
        'properties': {
            'cm:title': folder,
            'cm:description': description
        }
    }
   
    
    response = requests.post(url, headers=headers, json=data)
    if response.status_code == 201:
        #return response.json()
        #return folder name and id
        folder_name = response.json()['entry']['name']
        folder_id = response.json()['entry']['id']
        folder_data = {
            'name': folder_name,
            'id': folder_id
        }
        return folder_data
    else:
        raise Exception("Failed to create folder")

#
#DOCUMENT FUNCTIONS
#

def upload_document(ticket, file, name, document, parent_folder='-my-', description=''):
    """ 
    DOCUMENT UPLOAD INFO
    https://docs.alfresco.com/content-services/6.0/develop/rest-api-guide/folders-files/#uploadfile
    """
    print("upload_document")
    document_exists = True
    version = 1
    version_name = name
    while document_exists:
        doc_id = get_document_id(ticket, parent_folder, version_name)
        document_exists = doc_id is not None
        if doc_id is not None:
            version_name = f"{name[:name.find('.'):]}({version}){name[name.find('.'):]}"
            version += 1
    
    
    url = f"{settings.ALFRESCO_BASE_URL}/alfresco/api/-default-/public/alfresco/versions/1/nodes/{parent_folder}/children"
    print("Uploading document...")
    headers = {
        "Authorization": f"Basic {ticket}",
    }
    
    mime_type, _ = mimetypes.guess_type(version_name)
    if not mime_type:
        mime_type = 'application/octet-stream'
    files = {"filedata": file}
    from order.middleware import get_current_user
    current_user = get_current_user()
    
    data = {
        'name': version_name,
        'nodeType': 'cm:content',
        'properties': {
            'cm:title': version_name[:version_name.find('.')],
            'cm:description': description,
            "cm:creator": current_user.username if current_user else 'Admin',
        },
        #"filedata": file.read()         
    }
    
    #response = requests.post(url, headers=headers, json=data)
    response = requests.post(url, headers=headers, data=data, files=files)
    if response.status_code == 201:
        print("response upload document results")
        return parent_folder
    else:
        raise Exception("Failed to create document")

def upload_versioned_document(
    ticket, file, name, parent_token, parent_name, parent_folder='-my-', description=''
):
    print("upload_versioned_document")
    """
    DOCUMENT UPLOAD INFO
    https://docs.alfresco.com/content-services/latest/develop/rest-api-guide/folders-files/#uploadnewversionfile
    """
    url = (
        f"{settings.ALFRESCO_BASE_URL}/alfresco/api/-default-/public/"
        f"alfresco/versions/1/nodes/{parent_token}/content?majorVersion=false&name={parent_name}"
    )

    mime_type, _ = mimetypes.guess_type(name)
    if not mime_type:
        mime_type = "application/octet-stream"
    headers = {
        "Authorization": f"Basic {ticket}",
        "Content-Type": mime_type,
    }

    #files = {"filedata": (name, file, mime_type)}  
    file_content = file.read()

    from order.middleware import get_current_user
    current_user = get_current_user()
    metadata = {
        "cm:title": name[: name.find(".")],
        "cm:description": description,
        "cm:creator": current_user.username if current_user else "Admin",
    }

    data = {
        "name": name,  
        "nodeType": "cm:content",
        "properties": str(metadata), 
    }

    response = requests.put(url, headers=headers, data=file_content)

    if response.status_code == 200: 
        print("Versioned document uploaded successfully!")
        return parent_folder
    else:
        print(f"Failed to upload versioned document. Status code: {response.status_code}")
        print(f"Response text: {response.text}") 
        raise Exception(
            f"Failed to upload versioned document.  Status code: {response.status_code}, Response: {response.text}"
        )

def get_document(ticket, folder_id, document_name):
    #url = f"{settings.ALFRESCO_BASE_URL}/alfresco/api/-default-/public/alfresco/versions/1/nodes/{folder_id}/children"
    doc_id = get_document_id(ticket, folder_id, document_name)
    url = f"{settings.ALFRESCO_BASE_URL}/alfresco/api/-default-/public/alfresco/versions/1/nodes/{doc_id}/content"
    print("Getting document...")
    headers = {
        "Authorization": f"Basic {ticket}",
        "accept": "application/json",
    }
    
    
    response = requests.get(url, headers=headers, stream=True)
    print("response get document")
    if response.status_code == 200:
        #return file in reponse as HttpResponse()
        content_type = response.headers.get('Content-Type', 'application/octet-stream')
        content_disposition = response.headers.get('Content-Disposition', f'attachment; filename="{document_name}"')
        return HttpResponse(
            response.content,
            content_type=content_type,
            headers={'Content-Disposition': content_disposition}
        )
    else:
        raise Exception("Failed to get document")
    
def get_document_id(ticket, folder_id, document_name):
    items = get_alfresco_items(ticket, folder_id)
    print("items get document id")
    #trying different approach since request is not filtering as it should
    
    if items and items['list']['entries']:
        for entry in items['list']['entries']:
            if entry['entry']['isFile'] and entry['entry']['name'] == document_name:
                document_id = entry['entry']['id']
                return document_id
        
        return None  
    else:
        return None
    
""" def get_document_id(ticket, folder_id, document_name):
    url = f"{settings.ALFRESCO_BASE_URL}/alfresco/api/-default-/public/search/versions/1/search"
    print("Getting document id...")
    headers = {
        "Authorization": f"Basic {ticket}",
        "accept": "application/json",
        "Content-Type": "application/json"
    }
    
    query_parts = [f'cm:name:"{document_name}"', f'nodeType:"cm:content"']
    #if folder_id:
    #    query_parts.append(f'ANCESTOR:\"workspace://SpacesStore/{folder_id}\"')

    query_str = " AND ".join(query_parts)
    
    print("query_str")
    print(query_str)
    
    data = {
        "query": {
            "query": query_str
        },
        "paging": {
            "maxItems": 2,
            "skipCount": 0
        }
    }
    
    response = requests.post(url, headers=headers, json=data)
    print("response")
    print(response.json())
    if response.status_code == 200:
        result = response.json()['list']['entries'][0]
        print("json results")
        print(result)
        return result['entry']['id']
    else:
        raise Exception("Failed to get document") """

#
#AUTH FUNCTIONS
#


def get_alfresco_token():
    url = f"{settings.ALFRESCO_BASE_URL}/alfresco/api/-default-/public/authentication/versions/1/tickets"
    payload = {
        "userId": settings.ALFRESCO_USERNAME,
        "password": settings.ALFRESCO_PASSWORD
    }
    print("Getting Alfresco token...")

    response = requests.post(url, json=payload)
    print("response getting token")
    if response.status_code == 201:
        return response.json()["entry"]["id"]
    else:
        raise Exception("Failed to authenticate with Alfresco")

def encode_token(token):
    encode_token = token.encode('utf-8')
    encoded_token = base64.b64encode(encode_token)
    encoded_token = encoded_token.decode('utf-8')
    
    return encoded_token

def decode_token(encoded_token):
    decode_token = base64.b64decode(encoded_token)
    decode_token = decode_token.decode('utf-8')
    
    return decode_token

#
#OTHERS
#

def check_alfresco_connection(ticket):
    url = f"{settings.ALFRESCO_BASE_URL}/alfresco/api/discovery"
    print("Checking Alfresco connection...")
    headers = {
        "Authorization": f"Basic {ticket}",
        "Accept": "application/json"
    }
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return True
    else:
        return False


def get_alfresco_items(ticket, folder_id):
    url = f"{settings.ALFRESCO_BASE_URL}/alfresco/api/-default-/public/alfresco/versions/1/nodes/{folder_id}/children?where=(isFile=true)"
    print("Getting Alfresco items...")
    headers = {
        "Authorization": f"Basic {ticket}",
        "Accept": "application/json"
    }
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.json()
    else:
        raise Exception("Failed to get Alfresco items")

