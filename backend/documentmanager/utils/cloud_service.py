from django.conf import settings
from django.http import HttpResponse
from google.cloud import storage
from datetime import datetime
import calendar


def upload_document_to_cloud(file, entity, field, entity_id, entity_token, folder, document_name, document, date=None):
    print("Uploading to Cloud")
    date_year = date.year if date else datetime.now().year
    date_month = date.month if date else datetime.now().month
    date_month_string = calendar.month_name[date_month]
    
    bucket_name = settings.CLOUD_BUCKET_NAME
    blob_name = f"{field}/{entity}/{date_year}/{date_month_string}/{document_name}"
    
    from order.middleware import get_current_user
    current_user = get_current_user()
    #NO TAGS IN CLOUD, ALL IN METADATA
    file_metadata = {
        "author": current_user.username if current_user else 'Admin', 
        "category": "report", 
        }
    
    """Uploads a file to the bucket."""
    # The ID of your GCS bucket
    # bucket_name = "your-bucket-name"
    # The path to your file to upload
    # source_file_name = "local/path/to/file"
    # The ID of your GCS object
    # destination_blob_name = "storage-object-name"

    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(blob_name)
    blob.metadata = file_metadata
    
    #FROM MEMORY
    """ 
    blob.upload_from_string(file)
    blob.patch()

    print(
        f"{blob_name} with contents {contents} uploaded to {bucket_name}."
    )
     """
    
    #FROM FILES
    """
    # Optional: set a generation-match precondition to avoid potential race conditions
    # and data corruptions. The request to upload is aborted if the object's
    # generation number does not match your precondition. For a destination
    # object that does not yet exist, set the if_generation_match precondition to 0.
    # If the destination object already exists in your bucket, set instead a
    # generation-match precondition using its generation number.
     generation_match_precondition = 0

    blob.upload_from_filename(document_name, if_generation_match=generation_match_precondition)
    blob.patch()
    
    print(
        f"File {document_name} uploaded to {blob_name}."
    ) 
    """
    
    document.location = blob_name
    document.save()
    
    return document

def download_document_from_cloud(document):
    print("Downloading from Cloud")
    """ 
    OFFICIAL DOC: https://cloud.google.com/storage/docs/downloading-objects?hl=es-419
    """
    
    bucket_name = settings.CLOUD_BUCKET_NAME
    blob_name = document.location
    
    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(blob_name)
    
    #file_content = blob.download_as_string()
    file_content = blob.download_as_bytes()
    response = HttpResponse(file_content, content_type="application/octet-stream")
    response['Content-Disposition'] = f'attachment; filename="{document.document_name}"'
    return response

#
#IN CASE THERE'S A MULTIPLE FILES UPLOAD IN THE FUTURE HERE'S AN OFFICIAL DOC EXAMPLE
# MORE IN https://cloud.google.com/storage/docs/uploading-objects?hl=es-419#storage-upload-object-python
# MORE IN https://cloud.google.com/storage/docs/uploading-objects-from-memory?hl=es-419#storage-upload-object-from-memory-python
# WE FIND ALSO EXAMPLES OF THIS FOR MULTIPLE FILES DOWNLOADED FROM THE CLOUD
#
""" 
def upload_many_blobs_with_transfer_manager(
    bucket_name, filenames, source_directory="", workers=8
):
    #Upload every file in a list to a bucket, concurrently in a process pool.

    #Each blob name is derived from the filename, not including the
    #`source_directory` parameter. For complete control of the blob name for each
    #file (and other aspects of individual blob metadata), use
    #transfer_manager.upload_many() instead.
    

    # The ID of your GCS bucket
    # bucket_name = "your-bucket-name"

    # A list (or other iterable) of filenames to upload.
    # filenames = ["file_1.txt", "file_2.txt"]

    # The directory on your computer that is the root of all of the files in the
    # list of filenames. This string is prepended (with os.path.join()) to each
    # filename to get the full path to the file. Relative paths and absolute
    # paths are both accepted. This string is not included in the name of the
    # uploaded blob; it is only used to find the source files. An empty string
    # means "the current working directory". Note that this parameter allows
    # directory traversal (e.g. "/", "../") and is not intended for unsanitized
    # end user input.
    # source_directory=""

    # The maximum number of processes to use for the operation. The performance
    # impact of this value depends on the use case, but smaller files usually
    # benefit from a higher number of processes. Each additional process occupies
    # some CPU and memory resources until finished. Threads can be used instead
    # of processes by passing `worker_type=transfer_manager.THREAD`.
    # workers=8

    from google.cloud.storage import Client, transfer_manager

    storage_client = Client()
    bucket = storage_client.bucket(bucket_name)

    results = transfer_manager.upload_many_from_filenames(
        bucket, filenames, source_directory=source_directory, max_workers=workers
    )

    for name, result in zip(filenames, results):
        # The results list is either `None` or an exception for each filename in
        # the input list, in order.

        if isinstance(result, Exception):
            print("Failed to upload {} due to exception: {}".format(name, result))
        else:
            print("Uploaded {} to {}.".format(name, bucket.name))
"""

    