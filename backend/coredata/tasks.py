from celery import shared_task
from django.core.files.storage import default_storage
import os
import shutil

@shared_task
def clean_tmp_dir():
    tmp_dir = 'tmp'
    if not default_storage.exists(tmp_dir):
        return

    def _delete_recursive(prefix: str) -> None:
        directories, files = default_storage.listdir(prefix)
        for file_name in files:
            default_storage.delete(f"{prefix}/{file_name}")
        for dir_name in directories:
            _delete_recursive(f"{prefix}/{dir_name}")

    _delete_recursive(tmp_dir)

    try:
        base_path = default_storage.path(tmp_dir) 
    except Exception:
        base_path = None

    if base_path and os.path.isdir(base_path):
        for entry in os.listdir(base_path):
            entry_path = os.path.join(base_path, entry)
            if os.path.isdir(entry_path):
                shutil.rmtree(entry_path, ignore_errors=True)
    