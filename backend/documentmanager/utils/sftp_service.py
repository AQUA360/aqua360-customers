from datetime import datetime
import io
import locale
import logging
import posixpath

import paramiko
from django.conf import settings
from django.http import Http404, HttpResponse
from documentmanager.utils.http_utils import attachment_disposition

logger = logging.getLogger(__name__)


def _connect():
    """Obre una connexió SFTP verificant la clau del servidor amb el known_hosts configurat.

    Si la clau del servidor no hi és o no coincideix, es rebutja la connexió: les credencials i els
    documents (contractes, mandats, DNI) només viatgen pel canal xifrat cap al servidor esperat.
    Retorna (client SSH, client SFTP).
    """
    client = paramiko.SSHClient()
    # Mai les claus del sistema ni les de l'usuari: només el known_hosts de la configuració.
    if settings.SFTP_KNOWN_HOSTS:
        client.load_host_keys(settings.SFTP_KNOWN_HOSTS)
    client.set_missing_host_key_policy(paramiko.RejectPolicy())
    try:
        client.connect(
            settings.SFTP_HOST,
            port=settings.SFTP_PORT,
            username=settings.SFTP_USER,
            password=settings.SFTP_PASSWORD or None,
            key_filename=settings.SFTP_KEY_FILE or None,
            # Només les credencials configurades: ni l'agent SSH ni les claus de ~/.ssh.
            allow_agent=False,
            look_for_keys=False,
            timeout=settings.SFTP_TIMEOUT,
            banner_timeout=settings.SFTP_TIMEOUT,
            auth_timeout=settings.SFTP_TIMEOUT,
        )
        sftp = client.open_sftp()
        sftp.get_channel().settimeout(settings.SFTP_TIMEOUT)
    except Exception:
        client.close()
        raise
    return client, sftp


def _close(client, sftp):
    try:
        sftp.close()
    finally:
        client.close()


def _makedirs(sftp, remote_folder):
    """Crea la carpeta remota i les intermèdies que faltin."""
    path = ''
    for part in remote_folder.split('/'):
        if not part:
            continue
        path = posixpath.join(path, part)
        try:
            sftp.stat(path)
        except FileNotFoundError:
            sftp.mkdir(path)


def upload_to_sftp(file, entity, field, entity_id, entity_token, folder, document_name, document, date=None):
    """Uploads a file to the SFTP server, creating the destination folder if needed, and updates the document record."""
    try:
        locale.setlocale(locale.LC_TIME, 'ca_ES.UTF-8')
    except locale.Error:
        pass
    date_year = date.year if date else datetime.now().year
    month_name = datetime.now().strftime('%B').capitalize()
    month_folder_name = (f'{field}_{month_name}').upper()

    remote_folder = f"{field}/{entity}/{date_year}/{month_folder_name}/{entity_token}"
    remote_file_path = posixpath.join(remote_folder, document_name)

    client, sftp = _connect()
    try:
        _makedirs(sftp, remote_folder)
        sftp.putfo(file, remote_file_path)
    finally:
        _close(client, sftp)

    document.location = None
    document.location_url = f"sftp://{settings.SFTP_HOST}/{remote_file_path}"
    document.document_name = document_name
    document.save()

    return document


def download_document_from_sftp(document):
    """Downloads a document from the SFTP server and returns it as an HTTP response."""
    remote_file_path = document.location_url.replace("sftp://", "", 1).split("/", 1)[1]
    document_name = document.document_name

    try:
        client, sftp = _connect()
    except Exception:
        # Sense el detall de l'excepció: pot portar el nom del servidor o de l'usuari.
        logger.error("SFTP connection error downloading document %s", document.id)
        raise Http404("Document not available.")

    try:
        buffer = io.BytesIO()
        sftp.getfo(remote_file_path, buffer)
    except Exception:
        # Sense rutes ni noms de fitxer al registre ni a la resposta: poden contenir dades personals.
        logger.error("SFTP error downloading document %s", document.id)
        raise Http404("Document not available.")
    finally:
        _close(client, sftp)

    response = HttpResponse(buffer.getvalue(), content_type="application/octet-stream")
    response['Content-Disposition'] = attachment_disposition(document_name)
    return response
