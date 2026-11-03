"""Selecció i ordre dels documents d'una descàrrega de facturació.

Les facturacions només aporten factures. El filtre de carta o correu es fa
sobre els documents d'un procés de comunicació, amb les mateixes regles que
el menú del procés, perquè no ens saltem les cartes ni el marcatge d'enviament.
"""
import os

from django.db.models import CharField, F, Prefetch, Value
from django.db.models.functions import Coalesce, Lower, NullIf

from billing.models import BillingDocumentDownload, Invoice

DELIVERY_ALL = BillingDocumentDownload.DELIVERY_ALL
DELIVERY_POSTAL = BillingDocumentDownload.DELIVERY_POSTAL
DELIVERY_EMAIL = BillingDocumentDownload.DELIVERY_EMAIL
DELIVERIES = {DELIVERY_ALL, DELIVERY_POSTAL, DELIVERY_EMAIL}

ORDER_CONTACT_ADDRESS = BillingDocumentDownload.ORDER_CONTACT_ADDRESS
ORDER_CONTRACT_TOKEN = BillingDocumentDownload.ORDER_CONTRACT_TOKEN
ORDER_INVOICE_CODE = BillingDocumentDownload.ORDER_INVOICE_CODE
ORDERINGS = {ORDER_CONTACT_ADDRESS, ORDER_CONTRACT_TOKEN, ORDER_INVOICE_CODE}

BATCH_NONE = BillingDocumentDownload.BATCH_NONE
BATCH_COUNT = BillingDocumentDownload.BATCH_COUNT
BATCH_SIZE = BillingDocumentDownload.BATCH_SIZE
BATCH_MODES = {BATCH_NONE, BATCH_COUNT, BATCH_SIZE}
MAX_BATCH_SIZE = 100000


class DownloadOptionsError(ValueError):
    def __init__(self, field):
        self.field = field
        super().__init__(field)


def parse_download_options(data):
    """Normalitza filtres d'ordre i forma de pagament. No decideix l'origen."""
    data = data or {}

    raw_tokens = data.get('payment_type_tokens') or []
    if isinstance(raw_tokens, str):
        raw_tokens = [part.strip() for part in raw_tokens.split(',') if part.strip()]
    if not isinstance(raw_tokens, list):
        raise DownloadOptionsError('payment_type_tokens')
    tokens = []
    for token in raw_tokens:
        if not isinstance(token, str) or not token.strip():
            raise DownloadOptionsError('payment_type_tokens')
        tokens.append(token.strip())

    delivery = data.get('delivery') or DELIVERY_ALL
    if delivery not in DELIVERIES:
        raise DownloadOptionsError('delivery')

    ordering = data.get('ordering') or ORDER_CONTACT_ADDRESS
    if ordering not in ORDERINGS:
        raise DownloadOptionsError('ordering')

    descending = data.get('descending', False)
    if isinstance(descending, str):
        descending = descending.strip().lower() in ('1', 'true', 'yes')
    elif not isinstance(descending, bool):
        raise DownloadOptionsError('descending')

    batch_mode = data.get('batch_mode') or BATCH_NONE
    if isinstance(batch_mode, str):
        batch_mode = batch_mode.strip().lower()
    if batch_mode not in BATCH_MODES:
        raise DownloadOptionsError('batch_mode')
    batch_size = None
    if batch_mode != BATCH_NONE:
        batch_size = _positive_int(data.get('batch_size'), 'batch_size')

    return {
        'payment_type_tokens': tokens,
        'delivery': delivery,
        'ordering': ordering,
        'descending': descending,
        'batch_mode': batch_mode,
        'batch_size': batch_size,
    }


def _positive_int(raw, field):
    if isinstance(raw, bool) or raw in (None, ''):
        raise DownloadOptionsError(field)
    if isinstance(raw, str):
        raw = raw.strip()
        if not raw.isdigit():
            raise DownloadOptionsError(field)
        raw = int(raw)
    elif not isinstance(raw, int):
        raise DownloadOptionsError(field)
    if raw < 1 or raw > MAX_BATCH_SIZE:
        raise DownloadOptionsError(field)
    return raw


def _int_ids(raw, field):
    if raw is None or raw == '':
        return []
    if isinstance(raw, bool):
        raise DownloadOptionsError(field)
    if isinstance(raw, int):
        return [raw]
    if isinstance(raw, str):
        raw = [part.strip() for part in raw.split(',') if part.strip()]
    if not isinstance(raw, (list, tuple)):
        raise DownloadOptionsError(field)
    ids = []
    seen = set()
    for item in raw:
        if isinstance(item, bool) or item in (None, ''):
            raise DownloadOptionsError(field)
        try:
            value = int(item)
        except (TypeError, ValueError):
            raise DownloadOptionsError(field)
        if value not in seen:
            seen.add(value)
            ids.append(value)
    return ids


def parse_download_request(data):
    """Origen excloent: facturacions o processos. El canal només val amb processos."""
    options = parse_download_options(data)
    data = data or {}
    billing_ids = _int_ids(data.get('billing_ids'), 'billing_ids')
    process_ids = _int_ids(data.get('communication_process_ids'), 'communication_process_ids')
    legacy = data.get('communication_process_id')
    if legacy not in (None, '', 'null'):
        for process_id in _int_ids(legacy, 'communication_process_id'):
            if process_id not in process_ids:
                process_ids.append(process_id)

    if bool(billing_ids) == bool(process_ids):
        raise DownloadOptionsError('source')
    if billing_ids and options['delivery'] != DELIVERY_ALL:
        raise DownloadOptionsError('delivery')

    options['billing_ids'] = billing_ids
    options['communication_process_ids'] = process_ids
    return options


def _blank_as_null(lookup):
    return NullIf(lookup, Value(''))


def _sort_expression(ordering):
    if ordering == ORDER_CONTRACT_TOKEN:
        return Coalesce(
            _blank_as_null('contract__token'),
            _blank_as_null('contract_request__token'),
            _blank_as_null('contract_termination__contract__token'),
            output_field=CharField(),
        )
    if ordering == ORDER_INVOICE_CODE:
        return Coalesce(
            _blank_as_null('serie_final'),
            _blank_as_null('token'),
            _blank_as_null('number'),
            output_field=CharField(),
        )
    return Coalesce(
        _blank_as_null('contract__address_contact__address__address_search'),
        _blank_as_null('contract_termination__contract__address_contact__address__address_search'),
        _blank_as_null('contract_request__address_contact__address__address_search'),
        _blank_as_null('address_final'),
        output_field=CharField(),
    )


def ordered_billing_invoices(billing_ids, *, payment_type_tokens=None,
                             ordering=ORDER_CONTACT_ADDRESS, descending=False):
    """Factures actives de les facturacions, sense filtre de canal."""
    if isinstance(billing_ids, int):
        billing_ids = [billing_ids]
    queryset = Invoice.objects.filter(
        billing_id__in=list(billing_ids or []), is_active=True, is_excluded=False,
    ).select_related('invoice_file')

    tokens = [token for token in (payment_type_tokens or []) if token]
    if tokens:
        queryset = queryset.filter(payment_type_token_final__in=tokens)

    queryset = queryset.annotate(_download_sort=Lower(_sort_expression(ordering)))
    direction = (
        F('_download_sort').desc(nulls_last=True)
        if descending else
        F('_download_sort').asc(nulls_last=True)
    )
    tie = '-id' if descending else 'id'
    return queryset.order_by(direction, tie)


def _channel_tokens():
    from coredata.models import ConfigProject
    try:
        postal = ConfigProject.objects.get(token='message_type_letter_token').value
        email = ConfigProject.objects.get(token='message_type_email_token').value
    except ConfigProject.DoesNotExist:
        raise DownloadOptionsError('channel')
    return postal, email


def _channel_included(comm_file, postal_token, email_token, delivery):
    communication = comm_file.communication
    type_tokens = (communication.type_tokens or '').split(',') if communication else []
    comm_is_postal = postal_token in type_tokens
    comm_is_email = email_token in type_tokens
    is_postal = comm_is_postal and comm_file.attach_to_letter
    is_email = comm_is_email and comm_file.attach_to_email
    if delivery == DELIVERY_POSTAL:
        return is_postal
    if delivery == DELIVERY_EMAIL:
        return is_email
    if (comm_is_postal or comm_is_email) and not (is_postal or is_email):
        return False
    return True


def _payment_matches(comm_file, tokens):
    if not tokens:
        return True
    invoice = comm_file.invoice
    if invoice is not None:
        return invoice.payment_type_token_final in tokens
    communication = comm_file.communication
    if communication is None:
        return False
    for related in communication.invoices.all():
        if related.payment_type_token_final in tokens:
            return True
    for sibling in communication.files.all():
        if sibling.invoice_id and sibling.invoice and sibling.invoice.payment_type_token_final in tokens:
            return True
    return False


def _text(*values):
    for value in values:
        if value:
            return value
    return ''


def _sort_value(comm_file, ordering):
    communication = comm_file.communication
    invoice = comm_file.invoice
    if ordering == ORDER_CONTRACT_TOKEN:
        if communication is not None:
            tokens = sorted(contract.token for contract in communication.contracts.all() if contract.token)
            if tokens:
                return tokens[0]
        contract = getattr(invoice, 'contract', None) if invoice is not None else None
        return _text(getattr(contract, 'token', None))
    if ordering == ORDER_INVOICE_CODE:
        if invoice is not None:
            code = _text(invoice.serie_final, invoice.token, invoice.number)
            if code:
                return code
        if communication is not None:
            codes = sorted(
                _text(related.serie_final, related.token, related.number)
                for related in communication.invoices.all()
            )
            codes = [code for code in codes if code]
            if codes:
                return codes[0]
        return ''
    if communication is not None:
        if communication.used_address:
            return communication.used_address
        person_address = communication.address
        address = person_address.address if person_address is not None else None
        if address is not None and address.address_search:
            return address.address_search
    if invoice is not None:
        contract = invoice.contract
        contact = contract.address_contact if contract is not None else None
        address = contact.address if contact is not None else None
        if address is not None and address.address_search:
            return address.address_search
        return invoice.address_final or ''
    return ''


class _DescendingText(str):
    def __lt__(self, other):
        return super().__gt__(other)


def _sort_key(comm_file, ordering, descending):
    value = (_sort_value(comm_file, ordering) or '').lower()
    comparable = _DescendingText(value) if descending else value
    communication_id = comm_file.communication_id or 0
    return (
        value == '',
        comparable,
        -communication_id if descending else communication_id,
        0 if comm_file.is_letter else 1,
        comm_file.id,
    )


def ordered_process_files(process_ids, *, payment_type_tokens=None, delivery=DELIVERY_ALL,
                          ordering=ORDER_CONTACT_ADDRESS, descending=False):
    """Documents dels processos, amb el mateix criteri de canal que el seu menú."""
    from communication.models import Communication, CommunicationFile

    if isinstance(process_ids, int):
        process_ids = [process_ids]
    if delivery not in DELIVERIES:
        raise DownloadOptionsError('delivery')
    postal_token, email_token = _channel_tokens()
    tokens = [token for token in (payment_type_tokens or []) if token]

    file_queryset = CommunicationFile.objects.filter(
        is_active=True, file__isnull=False,
    ).select_related(
        'file', 'invoice', 'invoice__contract', 'invoice__contract__address_contact__address',
    )
    communications = Communication.objects.filter(process_id__in=list(process_ids or [])).prefetch_related(
        Prefetch('files', queryset=file_queryset),
        'contracts',
        'invoices',
        'address__address',
    )

    selected = []
    for communication in communications:
        for comm_file in communication.files.all():
            comm_file.communication = communication
            if not _channel_included(comm_file, postal_token, email_token, delivery):
                continue
            if not _payment_matches(comm_file, tokens):
                continue
            selected.append(comm_file)
    selected.sort(key=lambda comm_file: _sort_key(comm_file, ordering, descending))
    return selected


def render_billing_download_pdf(invoices):
    """Ajunta els PDF de les factures, en l'ordre rebut. Retorna els bytes del fitxer."""
    import fitz
    from coredata.utils.pdf_utils import merge_pdfs

    merged = merge_pdfs(*invoices)
    try:
        with fitz.open(merged.name) as pdf:
            if pdf.page_count == 0:
                raise DownloadOptionsError('empty_pdf')
        with open(merged.name, 'rb') as handle:
            return handle.read()
    finally:
        try:
            os.unlink(merged.name)
        except OSError:
            pass


def render_documents_pdf(documents):
    """Ajunta els PDF de documents de comunicació, en l'ordre rebut."""
    from io import BytesIO

    from PyPDF2 import PdfMerger

    from documentmanager.utils.main_utils import download_document

    merger = PdfMerger()
    try:
        for document in documents:
            content = download_document(document)
            if not content:
                raise DownloadOptionsError('empty_pdf')
            try:
                raw = content.getvalue()
            except AttributeError:
                raw = content.content
            merger.append(BytesIO(raw))
        buffer = BytesIO()
        merger.write(buffer)
        data = buffer.getvalue()
        if not data:
            raise DownloadOptionsError('empty_pdf')
        return data
    finally:
        merger.close()


def stored_file_size(file_field):
    """Bytes del fitxer, o 0 si no es pot saber sense descarregar-lo sencer."""
    if not file_field:
        return 0
    try:
        return int(file_field.size or 0)
    except Exception:
        return 0


def invoice_source_size(invoice):
    document = getattr(invoice, 'invoice_file', None)
    if document is not None:
        size = stored_file_size(getattr(document, 'file', None))
        if size:
            return size
    return stored_file_size(getattr(invoice, 'invoice_file_template', None))


def document_source_size(document):
    if document is None:
        return 0
    return stored_file_size(getattr(document, 'file', None))


def pack_by_count(items, size):
    """Trossos consecutius, conservant l'ordre."""
    items = list(items)
    if not isinstance(size, int) or isinstance(size, bool) or size < 1:
        raise DownloadOptionsError('batch_size')
    return [items[index:index + size] for index in range(0, len(items), size)]


def pack_by_size(items, sizes, limit_bytes):
    """Agrupa fins al límit. Un document sense mida, o més gran que el límit, va sol."""
    if not isinstance(limit_bytes, int) or limit_bytes < 1:
        raise DownloadOptionsError('batch_size')
    batches = []
    current = []
    used = 0
    for item, size in zip(items, sizes):
        weight = size if isinstance(size, int) and not isinstance(size, bool) and size > 0 else limit_bytes
        if current and used + weight > limit_bytes:
            batches.append(current)
            current = []
            used = 0
        current.append(item)
        used += weight
    if current:
        batches.append(current)
    return batches


def pdfs_under_limit(batch, limit_bytes, render_batch):
    """Si el PDF ajuntat passa del límit, el parteix. Un sol document es deixa sencer."""
    content = render_batch(batch)
    if len(content) <= limit_bytes or len(batch) <= 1:
        return [content]
    middle = len(batch) // 2
    return (
        pdfs_under_limit(batch[:middle], limit_bytes, render_batch)
        + pdfs_under_limit(batch[middle:], limit_bytes, render_batch)
    )


def iter_download_parts(items, sizes, render_batch, batch_mode, batch_size):
    """Genera els PDF de la descàrrega, un a un, sense acumular-los tots en memòria."""
    items = list(items)
    if batch_mode == BATCH_COUNT:
        for batch in pack_by_count(items, batch_size):
            yield render_batch(batch)
        return
    if batch_mode == BATCH_SIZE:
        limit = batch_size * 1024 * 1024
        size_list = list(sizes) if sizes is not None else [0] * len(items)
        for batch in pack_by_size(items, size_list, limit):
            yield from pdfs_under_limit(batch, limit, render_batch)
        return
    yield render_batch(items)


def open_pdf_zip(parts, name_for):
    """Escriu els PDF en un zip al disc. El cridant ha de tancar i esborrar el fitxer."""
    import tempfile
    import zipfile

    temp = tempfile.NamedTemporaryFile(suffix='.zip', delete=False)
    count = 0
    try:
        with zipfile.ZipFile(temp, 'w', compression=zipfile.ZIP_STORED) as archive:
            for content in parts:
                count += 1
                archive.writestr(name_for(count), content)
        if count == 0:
            raise DownloadOptionsError('empty_pdf')
        temp.flush()
        temp.seek(0)
        return temp, count
    except Exception:
        temp.close()
        try:
            os.unlink(temp.name)
        except OSError:
            pass
        raise
