"""
Bateries d'una finca per al Lecturapp: dades i fotos.

Res no viatja amb la descàrrega del lot. L'app ho demana quan l'operari obre
l'apartat «Bateries» d'una finca, i cada foto es baixa per separat (miniatura per
a la llista, original en ampliar-la). Les fotos que fa l'operari queden com a
documents de la bateria, igual que les que es pugen des del web.
"""
import base64
import binascii
import json
import logging
from io import BytesIO

from django.conf import settings
from django.core.exceptions import RequestDataTooBig
from django.core.files.base import ContentFile
from django.db.models import Q
from django.http import JsonResponse
from django.utils import timezone
from PIL import Image, ImageOps, UnidentifiedImageError

from documentmanager.utils.main_utils import download_document, upload_document
from service.models import Cluster, ClusterDocumentationFile, ClusterDocumentationType

from .decorators import lecturapp_auth_required

logger = logging.getLogger(__name__)

PHOTO_TOKEN = 'photos'
THUMBNAIL_SIZE = (300, 300)
# L'app ja comprimeix les fotos a uns 200 KB. El màxim queda per sota del límit de
# cos de Django (DATA_UPLOAD_MAX_MEMORY_SIZE, 2,5 MiB) un cop codificat en base64.
MAX_PHOTO_BYTES = 1536 * 1024
IMAGE_MIME_TYPES = {
    '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.png': 'image/png',
    '.gif': 'image/gif', '.webp': 'image/webp',
}
IMAGE_EXTENSIONS = tuple(IMAGE_MIME_TYPES)


def _property_clusters(property_id):
    """Bateries actives de la finca: lligades a la finca o als seus punts de subministrament."""
    return Cluster.objects.filter(is_active=True).filter(
        Q(property_id=property_id) | Q(nozzles__supply_points__property_id=property_id)
    ).distinct().select_related(
        'status', 'address_street', 'address_street_number', 'address_city',
    ).prefetch_related('nozzles').order_by('token', 'id')


def _is_image(photo_file):
    return (photo_file.file.document_name or '').lower().endswith(IMAGE_EXTENSIONS)


def _photo_files(cluster):
    """Documents actius de la bateria que són imatges (per extensió del nom)."""
    files = ClusterDocumentationFile.objects.filter(
        cluster=cluster, is_active=True, file__isnull=False, file__is_active=True,
    ).select_related('file', 'type').order_by('-created_at', '-id')
    return [f for f in files if _is_image(f)]


def _serialize_photo(photo_file):
    return {
        'id': photo_file.id,
        'name': photo_file.file.document_name,
        'type': photo_file.type.name if photo_file.type else None,
        'created_at': photo_file.created_at,
    }


def _serialize_cluster(cluster):
    address = ' '.join(
        str(part) for part in (cluster.address_street, cluster.address_street_number, cluster.address_city) if part
    )
    nozzles = sorted(cluster.nozzles.all(), key=lambda n: (n.row or 0, n.col or 0, n.position or 0))
    return {
        'id': cluster.id,
        'token': cluster.token,
        'status': cluster.status.name if cluster.status else None,
        'status_color': cluster.status.color if cluster.status else None,
        'installation_at': cluster.installation_at,
        'nb_nozzles': cluster.nb_nozzles or len(nozzles),
        'address': address or None,
        'is_potable': cluster.is_potable,
        'usage_destination': cluster.usage_destination,
        'nozzles': [{
            'token': n.token,
            'row': n.row,
            'col': n.col,
            'position': n.position,
            'destination': n.destination,
        } for n in nozzles],
        'photos': [_serialize_photo(f) for f in _photo_files(cluster)],
    }


def _document_bytes(document):
    """Contingut del document, sigui quin sigui el servei on està desat."""
    response = download_document(document)
    if hasattr(response, 'streaming_content'):
        return b''.join(response.streaming_content)
    if hasattr(response, 'content'):
        return response.content
    if hasattr(response, 'getvalue'):
        return response.getvalue()
    return response


def _thumbnail(data):
    image = ImageOps.exif_transpose(Image.open(BytesIO(data)))
    image.thumbnail(THUMBNAIL_SIZE)
    buffer = BytesIO()
    image.convert('RGB').save(buffer, 'JPEG', quality=75)
    return buffer.getvalue()


def _to_jpeg(data):
    """Foto rebuda de l'app (qualsevol format d'imatge) desada sempre com a JPEG."""
    image = ImageOps.exif_transpose(Image.open(BytesIO(data)))
    buffer = BytesIO()
    image.convert('RGB').save(buffer, 'JPEG', quality=85)
    return buffer.getvalue()


def _data_url(data, name):
    extension = name.lower()[name.rfind('.'):] if '.' in name else ''
    mime = IMAGE_MIME_TYPES.get(extension, 'image/jpeg')
    return f'data:{mime};base64,' + base64.b64encode(data).decode('utf-8')


@lecturapp_auth_required
def property_clusters(request, property_id):
    """GET: bateries de la finca amb les seves dades i la llista de fotos (sense imatges)."""
    if request.method != 'GET':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    return JsonResponse({'results': [_serialize_cluster(c) for c in _property_clusters(property_id)]})


@lecturapp_auth_required
def cluster_photo(request, cluster_id, photo_id):
    """GET: una foto de la bateria; ?size=thumbnail per a la miniatura de la llista."""
    if request.method != 'GET':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    photo_file = ClusterDocumentationFile.objects.filter(
        id=photo_id, cluster_id=cluster_id, cluster__is_active=True,
        is_active=True, file__isnull=False, file__is_active=True,
    ).select_related('file').first()
    # Només imatges: per aquí no es poden llegir altres documents de la bateria
    if not photo_file or not _is_image(photo_file):
        return JsonResponse({'error': 'Photo not found'}, status=404)
    name = photo_file.file.document_name or ''
    try:
        data = _document_bytes(photo_file.file)
        if request.GET.get('size') == 'thumbnail':
            data, name = _thumbnail(data), 'thumbnail.jpg'
    except Exception:
        logger.exception('No s\'ha pogut llegir la foto de bateria %s', photo_id)
        return JsonResponse({'error': 'Photo not available'}, status=404)
    return JsonResponse({'id': photo_file.id, 'photo': _data_url(data, name)})


@lecturapp_auth_required
def upload_cluster_photo(request, cluster_id):
    """POST {photo: base64}: desa la foto com a document de la bateria (tipus «Fotos»)."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    cluster = Cluster.objects.filter(id=cluster_id, is_active=True).first()
    if not cluster:
        return JsonResponse({'error': 'Cluster not found'}, status=404)

    try:
        body = request.body
    except RequestDataTooBig:
        return JsonResponse({'error': 'Photo too large'}, status=413)
    try:
        photo = (json.loads(body or b'{}').get('photo') or '').strip()
        if photo.startswith('data:'):
            photo = photo.partition(',')[2]
        data = base64.b64decode(photo, validate=True)
    except (ValueError, binascii.Error, AttributeError):
        return JsonResponse({'error': 'Invalid photo'}, status=400)
    if not data:
        return JsonResponse({'error': 'Invalid photo'}, status=400)
    if len(data) > MAX_PHOTO_BYTES:
        return JsonResponse({'error': 'Photo too large'}, status=413)
    try:
        Image.open(BytesIO(data)).verify()
        data = _to_jpeg(data)
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError):
        return JsonResponse({'error': 'Invalid photo'}, status=400)

    photo_type = (
        ClusterDocumentationType.objects.filter(token=PHOTO_TOKEN, is_active=True).first()
        or ClusterDocumentationType.objects.filter(is_default=True, is_active=True).first()
    )
    name = f"bateria_{cluster.token or cluster.id}_{timezone.now().strftime('%Y%m%d_%H%M%S')}.jpg".replace(' ', '_').replace('/', '_')
    try:
        document = upload_document(
            ContentFile(data, name=name), 'CLUSTER', 'CLUSTER', cluster.id, cluster.token, '',
            settings.DOCUMENT_MANAGER_SERVICES.get('connection'), name, cluster.created_at,
        )
        photo_file = ClusterDocumentationFile.objects.create(cluster=cluster, file=document, type=photo_type)
    except Exception:
        logger.exception('No s\'ha pogut desar la foto de la bateria %s', cluster_id)
        return JsonResponse({'error': 'Photo could not be saved'}, status=500)
    return JsonResponse(_serialize_photo(photo_file), status=201)
