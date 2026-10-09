import calendar
import boto3
import logging
import locale
from django.conf import settings
from django.core.exceptions import ValidationError
from botocore.exceptions import ClientError
from botocore.config import Config
from datetime import datetime
from django.http import Http404, HttpResponse
from order.middleware import get_current_user
from documentmanager.models import Document

def upload_to_aws(file, document, name, field, entity):
    print("going in service aws")
    s3_client = boto3.client(
        's3',
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        region_name=settings.AWS_REGION
    )
    
    try:
        locale.setlocale(locale.LC_TIME, 'ca_ES.UTF-8')
    except locale.Error:
        pass
    date_year = datetime.now().year
    month_name = datetime.now().strftime('%B').capitalize()
    month_folder_name = (f'{field}_{month_name}').upper()
    
    print("got s3_client")
    print(s3_client)
    bucket_name = settings.AWS_STORAGE_BUCKET_NAME  
    print(bucket_name)
    s3_file_path = f"{field}/{entity}/{date_year}/{month_folder_name}/{name}"  
    print(s3_file_path)
    
    current_user = get_current_user()
    
    tags = {
        "user": current_user.username if current_user else 'Admin', 
        "category": entity,
    }
    tags_str = "&".join(f"{key}={value}" for key, value in tags.items())

    file_exists = True
    version = 1
    try:
        while file_exists:
            file_exists = file_already_exists_check(bucket_name, s3_file_path)
            if file_exists:
                name = f"{name[:name.find('.'):]}({version}){name[name.find('.'):]}"
                version += 1
    except Exception as e:
        raise ValidationError(f"Error checking if file already exists: {e}")
    
    
    try:
        print("going in try")
        s3_client.upload_fileobj(file, bucket_name, s3_file_path, ExtraArgs={"Tagging": tags_str})
        print("uploaded")
        
        """ if file.closed:
            raise ValueError("File is already closed before upload.") """
        #file.seek(0)
        document.file = None
        document.location = bucket_name  
        #document.location_url = f"https://{bucket_name}.s3.{settings.AWS_REGION}.amazonaws.com/{s3_file_path}"
        document.document_name = name
        document.folder = s3_file_path  
        print("saved document values")
        document.save()  
        print("saved document")
        return document
    except ClientError as e:
        raise ValidationError(f"Error uploading to S3: {e}")

#TODO: UPLOAD MULTIPLE FILES (MAX 5GB?)

def download_document_from_aws(document):
    # download_document_from_aws(bucket_name, s3_file_path, file_type, expiration=3600):
    s3_client = boto3.client(
        's3',
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID, 
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        region_name=settings.AWS_REGION,) 
    
    try:
        response = s3_client.get_object(
            Bucket=document.location,
            Key=document.folder
        )
        
        file_content = response['Body'].read()
        content_type = response['ContentType']
        print("\ncontent type") 
        print(content_type)
        file_name = document.folder.split('/')[-1]  
        
        # Return the file as an HttpResponse
        response = HttpResponse(
            file_content,
            content_type=content_type,
            headers={
                'Content-Disposition': f'attachment; filename="{file_name}"'
            }
        )
        return response
        
        """ response = s3_client.generate_presigned_url(
            'get_object',  
            Params={
                'Bucket': bucket_name,
                'Key': s3_file_path
            },
            ExpiresIn=expiration
        ) """
       
    except ClientError as e:
        logging.error(e)
        return None
    except Exception as e:
        print(f"AWS S3 Error: {e}")
        raise ValidationError(f"AWS S3 Pre-signed URL Error: {e}")


def download_multiple_documents_from_aws(document_ids):
    s3_client = boto3.client(
        's3',
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        region_name=settings.AWS_REGION,
    )
    
    documents = Document.objects.filter(id__in=document_ids)

    files = []  
    for document in documents:
        try:
            response = s3_client.get_object(
                Bucket=document.location,
                Key=document.folder,
            )
            file_content = response['Body'].read()
            filename = document.document_name  
            files.append((filename, file_content))
        except ClientError as e:
            logging.error(f"Error downloading {document.document_name} from S3: {e}")
            

    return files 



def file_already_exists_check(location, folder):
    s3_client = boto3.client(
        's3',
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID, 
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        region_name=settings.AWS_REGION,) 
    
    try:
        response = s3_client.get_object(
            Bucket=location,
            Key=folder
        )
        return True
    except ClientError as e:
        logging.error(e)
        return False    