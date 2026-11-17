from datetime import datetime
import os
import locale
import ftplib
import logging
import ssl
from django.conf import settings
from django.http import Http404, HttpResponse

logger = logging.getLogger(__name__)


def _connect():
    """Obre una connexió FTPS (TLS explícit) amb el certificat verificat i el canal de dades xifrat.

    Mai FTP en clar: les credencials i els documents (contractes, mandats, DNI) no poden viatjar sense xifrar.
    """
    # El context per defecte verifica la cadena del certificat i que el nom coincideixi amb FTP_HOST.
    context = ssl.create_default_context()
    ftp = ftplib.FTP_TLS(context=context)
    try:
        ftp.connect(settings.FTP_HOST)
        # login() fa l'AUTH TLS abans d'enviar l'usuari i la contrasenya.
        ftp.login(settings.FTP_USER, settings.FTP_PASSWORD)
        # Xifra també les transferències de fitxers, no només el canal de control.
        ftp.prot_p()
        ftp.encoding = 'utf-8'
    except Exception:
        ftp.close()
        raise
    return ftp


def _close(ftp):
    try:
        ftp.quit()
    except Exception:
        ftp.close()


def upload_to_ftp(file, entity, field, entity_id, entity_token, folder, document_name, document, date=None):
    """Uploads a file to the FTP server, creating the destination folder if needed, and updates the document record."""
    try:
        locale.setlocale(locale.LC_TIME, 'ca_ES.UTF-8')
    except locale.Error:
        pass
    date_year = date.year if date else datetime.now().year
    month_name = datetime.now().strftime('%B').capitalize()
    month_folder_name = (f'{field}_{month_name}').upper()

    remote_folder = f"{field}/{entity}/{date_year}/{month_folder_name}/{entity_token}"
    remote_file_path = os.path.join(remote_folder, document_name)

    ftp = _connect()
    try:
        try:
            ftp.cwd(remote_folder)
        except ftplib.error_perm:
            for part in remote_folder.split('/'):
                try:
                    ftp.cwd(part)
                except ftplib.error_perm:
                    ftp.mkd(part)
                    ftp.cwd(part)

        ftp.storbinary(f'STOR {document_name}', file)
    finally:
        _close(ftp)

    document.location = None
    document.location_url = f"ftp://{settings.FTP_HOST}/{remote_file_path}"
    document.document_name = document_name
    document.save()

    return document

def download_document_from_ftp(document):
    """Downloads a document from the FTP server and returns it as an HTTP response."""
    remote_file_path = document.location_url.replace("ftp://", "").split("/", 1)[1]
    remote_folder = "/".join(remote_file_path.split("/")[:-1])
    document_name = document.document_name

    ftp = _connect()

    try:
        ftp.cwd(remote_folder)

        file_data = []

        def callback(data):
            file_data.append(data)

        ftp.retrbinary(f'RETR {document_name}', callback)

        file_data = b''.join(file_data)

        response = HttpResponse(file_data, content_type="application/octet-stream")
        response['Content-Disposition'] = f'attachment; filename="{document_name}"'
        return response

    # Sense rutes ni noms de fitxer al registre ni a la resposta: poden contenir dades personals.
    except ftplib.error_perm:
        logger.warning("FTP permission error downloading document %s", document.id)
        raise Http404("Document not available.")
    except Exception:
        logger.exception("FTP error downloading document %s", document.id)
        raise Http404("Document not available.")
    finally:
        _close(ftp)
