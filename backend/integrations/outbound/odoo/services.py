from django.utils import timezone

from billing.models import CommitmentDeposit, Invoice, PaymentMovement

from coredata.models import ConfigProject
from integrations.models import (
    SendBatch,
    SendBatchProvider,
    SendBatchStatus,
    SendBatchType,
)
from integrations.utils.send_batch_status import payload_is_final_batch_result

from .batch_utils import MAX_BATCH_ITEMS, chunked, generate_batch_id
from .client import OdooClient, ensure_commitments_supported
from .exceptions import OdooApiError, OdooMappingError
from .mappers import (
    map_commitment_deposit_cancel_to_odoo,
    map_commitment_deposit_create_to_odoo,
    map_invoice_to_odoo,
    map_payment_movement_to_odoo,
)


def _get_odoo_provider_token() -> str:
    try:
        return ConfigProject.objects.get(token="send_batch_provider_odoo_token").value
    except ConfigProject.DoesNotExist:
        return "odoo"


def _get_odoo_provider() -> SendBatchProvider:
    token = _get_odoo_provider_token()
    try:
        return SendBatchProvider.objects.get(token=token)
    except SendBatchProvider.DoesNotExist as exc:
        raise OdooApiError(
            f"SendBatchProvider no trobat (token={token!r}). "
            "Executeu les migracions / reviseu ConfigProject "
            "'send_batch_provider_odoo_token'."
        ) from exc


def _get_client_for_provider(provider: SendBatchProvider | None, *, client=None):
    """
    Resol el client HTTP a partir del SendBatchProvider.
    Si el token coincideix amb ConfigProject send_batch_provider_odoo_token → OdooClient.
    """
    if client is not None:
        return client
    if not provider:
        raise OdooApiError("Cal un SendBatchProvider per resoldre el client.")
    odoo_token = _get_odoo_provider_token()
    if provider.token == odoo_token:
        return OdooClient()
    raise OdooApiError(
        f"No hi ha client configurat per al provider {provider.token!r}."
    )


def _get_client_for_batch_type(batch_type: SendBatchType | None, *, client=None):
    if not batch_type:
        raise OdooApiError("Cal un SendBatchType per resoldre el client.")
    return _get_client_for_provider(batch_type.provider, client=client)


def _get_client_for_batch(batch: SendBatch, *, client=None):
    if not batch.batch_type_id:
        raise OdooApiError(f"El lot {batch.token!r} no té tipus assignat.")
    return _get_client_for_batch_type(batch.batch_type, client=client)


def push_invoice(invoice_id: int, *, client=None, dry_run=False) -> dict:
    invoice = Invoice.objects.select_related(
        "serie",
        "parent_invoice",
        "company",
        "contract__company",
        "payment_type",
    ).prefetch_related(
        "line_items__product",
        "line_items__tax",
    ).get(pk=invoice_id)

    payload = map_invoice_to_odoo(invoice)
    if dry_run:
        return payload

    odoo_client = _get_client_for_provider(_get_odoo_provider(), client=client)
    return odoo_client.push_invoice(payload)


def push_payment_movement(movement_id: int, *, client=None, dry_run=False) -> dict:
    movement = PaymentMovement.objects.select_related(
        "payment__invoice__serie",
        "payment__invoice__company",
        "payment__invoice__contract__company",
        "payment__invoice__parent_invoice",
        "payment__invoice__payment_company_bank__bank",
        "payment__contract__company",
        "payment_type",
        "payoff_invoice__serie",
        "payoff_invoice__company",
        "payoff_invoice__contract__company",
        "payment_remittance__company_bank__bank",
    ).get(pk=movement_id)

    payload = map_payment_movement_to_odoo(movement)
    if dry_run:
        return payload

    odoo_client = _get_client_for_provider(_get_odoo_provider(), client=client)
    return odoo_client.push_payment(payload)


def build_invoice_payload(invoice_id: int) -> dict:
    """Retorna el JSON Odoo sense enviar-lo (útil per validació i tests)."""
    try:
        return push_invoice(invoice_id, dry_run=True)
    except OdooMappingError:
        raise


def build_payment_movement_payload(movement_id: int) -> dict:
    """Retorna el JSON Odoo sense enviar-lo (útil per validació i tests)."""
    try:
        return push_payment_movement(movement_id, dry_run=True)
    except OdooMappingError:
        raise


def _get_batch_type(*, token=None, is_default=False) -> SendBatchType:
    provider = _get_odoo_provider()
    qs = SendBatchType.objects.filter(provider=provider)
    try:
        if is_default:
            return qs.get(is_default=True)
        return qs.get(token=token)
    except SendBatchType.DoesNotExist as exc:
        raise OdooApiError(
            f"SendBatchType no trobat (provider={provider.token!r}, token={token!r}, "
            f"is_default={is_default}). Executeu les migracions / reviseu el catàleg."
        ) from exc


def _get_default_batch_status():
    try:
        token = ConfigProject.objects.get(token="send_batch_status_pending_token").value
        return SendBatchStatus.objects.get(token=token)
    except (ConfigProject.DoesNotExist, SendBatchStatus.DoesNotExist):
        return SendBatchStatus.objects.filter(is_default=True).first()


def _store_instant_response(batch: SendBatch, status_code: int, payload):
    """
    Desa la resposta immediata del POST del lot.

    HTTP 200/202 (acceptat, sense error d'enviament) → estat processing.
    Si la resposta ja porta el resultat final tractable → finalized.
    Altres codis / errors: es queda a pending.
    """
    batch.sent_at = timezone.now()
    batch.instant_status_code = status_code
    batch.instant_response = payload
    if isinstance(payload, dict):
        if "summary" in payload:
            batch.summary = payload.get("summary")
        # 200 d'un lot ja processat porta l'estat complet (results).
        if "results" in payload:
            batch.final_response = payload

    if status_code in (200, 202):
        config_token = (
            "send_batch_status_finalized_token"
            if payload_is_final_batch_result(payload)
            else "send_batch_status_processing_token"
        )
        try:
            token = ConfigProject.objects.get(token=config_token).value
            batch.status = SendBatchStatus.objects.get(token=token)
        except (ConfigProject.DoesNotExist, SendBatchStatus.DoesNotExist):
            pass

    batch.save(
        update_fields=[
            "sent_at",
            "instant_status_code",
            "instant_response",
            "status",
            "summary",
            "final_response",
            "updated_at",
        ]
    )


def _batch_items_for_retry(batch: SendBatch) -> list:
    type_token = batch.batch_type.token if batch.batch_type else ""
    if type_token == "payments":
        movements = list(
            batch.payments.select_related(
                "payment__invoice__serie",
                "payment__invoice__company",
                "payment__invoice__contract__company",
                "payment__invoice__parent_invoice",
                "payment__invoice__payment_company_bank__bank",
                "payment__contract__company",
                "payment_type",
                "payoff_invoice__serie",
                "payoff_invoice__company",
                "payoff_invoice__contract__company",
                "payment_remittance__company_bank__bank",
            ).all()
        )
        if not movements:
            raise OdooApiError("El lot no té moviments per reenviar.")
        return [map_payment_movement_to_odoo(mov) for mov in movements]
    if type_token in ("commitment_create", "commitment_cancel"):
        deposits = list(
            batch.commitment_deposits.select_related("status", "contract")
            .prefetch_related(
                "invoices",
                "payment_commitments",
            )
            .all()
        )
        if not deposits:
            raise OdooApiError("El lot no té compromisos per reenviar.")
        mapper = (
            map_commitment_deposit_cancel_to_odoo
            if type_token == "commitment_cancel"
            else map_commitment_deposit_create_to_odoo
        )
        return [mapper(dep) for dep in deposits]
    invoices = list(
        batch.invoices.select_related(
            "serie",
            "parent_invoice",
            "company",
            "contract__company",
            "payment_type",
        )
        .prefetch_related("line_items__product", "line_items__tax")
        .all()
    )
    if not invoices:
        raise OdooApiError("El lot no té factures per reenviar.")
    return [map_invoice_to_odoo(inv) for inv in invoices]


def build_send_payload_preview(batch: SendBatch, aqua_ids) -> dict:
    """
    Reconstrueix el JSON d'enviament {batch_id, items} només per als aqua_id demanats.
    Útil per inspeccionar objectes problemàtics des del front.
    """
    if not isinstance(aqua_ids, list) or not aqua_ids:
        raise OdooApiError("aqua_ids és obligatori (llista no buida).")

    aqua_ids = [str(a) for a in aqua_ids]
    type_token = batch.batch_type.token if batch.batch_type else ""
    items = []
    mapping_errors = []

    if type_token == "payments":
        movements = list(
            batch.payments.select_related(
                "payment__invoice__serie",
                "payment__invoice__company",
                "payment__invoice__contract__company",
                "payment__invoice__parent_invoice",
                "payment__invoice__payment_company_bank__bank",
                "payment__contract__company",
                "payment_type",
                "payoff_invoice__serie",
                "payoff_invoice__company",
                "payoff_invoice__contract__company",
                "payment_remittance__company_bank__bank",
            ).filter(token__in=aqua_ids)
        )
        by_token = {mov.token: mov for mov in movements if mov.token}
        for aqua_id in aqua_ids:
            mov = by_token.get(aqua_id)
            if not mov:
                mapping_errors.append(
                    {"aqua_id": aqua_id, "detail": "Moviment no trobat al lot."}
                )
                continue
            try:
                items.append(map_payment_movement_to_odoo(mov))
            except OdooMappingError as exc:
                mapping_errors.append({"aqua_id": aqua_id, "detail": str(exc)})
    elif type_token in ("commitment_create", "commitment_cancel"):
        deposits = list(
            batch.commitment_deposits.select_related("status", "contract")
            .prefetch_related("invoices", "payment_commitments")
            .filter(token__in=aqua_ids)
        )
        by_token = {dep.token: dep for dep in deposits if dep.token}
        mapper = (
            map_commitment_deposit_cancel_to_odoo
            if type_token == "commitment_cancel"
            else map_commitment_deposit_create_to_odoo
        )
        for aqua_id in aqua_ids:
            dep = by_token.get(aqua_id)
            if not dep:
                mapping_errors.append(
                    {"aqua_id": aqua_id, "detail": "Compromís no trobat al lot."}
                )
                continue
            try:
                items.append(mapper(dep))
            except OdooMappingError as exc:
                mapping_errors.append({"aqua_id": aqua_id, "detail": str(exc)})
    else:
        invoices = list(
            batch.invoices.select_related(
                "serie",
                "parent_invoice",
                "company",
                "contract__company",
                "payment_type",
            )
            .prefetch_related("line_items__product", "line_items__tax")
            .filter(token__in=aqua_ids)
        )
        by_token = {inv.token: inv for inv in invoices if inv.token}
        for aqua_id in aqua_ids:
            inv = by_token.get(aqua_id)
            if not inv:
                mapping_errors.append(
                    {"aqua_id": aqua_id, "detail": "Factura no trobada al lot."}
                )
                continue
            try:
                items.append(map_invoice_to_odoo(inv))
            except OdooMappingError as exc:
                mapping_errors.append({"aqua_id": aqua_id, "detail": str(exc)})

    return {
        "batch_id": batch.token,
        "items": items,
        "mapping_errors": mapping_errors,
        "provider": (
            batch.batch_type.provider.token
            if batch.batch_type and batch.batch_type.provider_id
            else None
        ),
        "batch_type": batch.batch_type.token if batch.batch_type else None,
    }


def retry_send_batch(batch: SendBatch, *, client=None) -> SendBatch:
    """
    Torna a POST el mateix lot (mateix batch_id) després d'un error d'enviament.
    """
    if not batch.batch_type or not batch.batch_type.endpoint:
        raise OdooApiError("El tipus de lot no té endpoint configurat.")

    items = _batch_items_for_retry(batch)
    odoo_client = _get_client_for_batch(batch, client=client)
    try:
        response = odoo_client.push_batch(
            batch.batch_type.endpoint,
            batch.token,
            items,
            object_type=f"send_batch_{batch.batch_type.token}",
        )
        _store_instant_response(batch, response["status_code"], response["payload"])
    except OdooApiError as exc:
        batch.sent_at = timezone.now()
        batch.instant_status_code = None
        batch.instant_response = {"detail": str(exc)}
        batch.save(
            update_fields=[
                "sent_at",
                "instant_status_code",
                "instant_response",
                "updated_at",
            ]
        )
        raise
    return batch


def check_batch_status(batch: SendBatch, *, client=None, apply=True) -> dict:
    """
    Consulta l'estat actual del lot via el client del provider del tipus.
    Si apply=True, desa la resposta amb la mateixa lògica que l'inbound.
    """
    from integrations.inbound.odoo.services import apply_odoo_batch_result

    odoo_client = _get_client_for_batch(batch, client=client)
    response = odoo_client.get_batch_status(batch.token)
    payload = response.get("payload") or {}
    applied = None
    # Només desar / passar a finalized quan la resposta és un resultat tractable.
    if apply and payload_is_final_batch_result(payload):
        applied = apply_odoo_batch_result(payload)

    message = None
    if isinstance(payload, dict):
        message = payload.get("message") or payload.get("detail")
        if not message and isinstance(payload.get("summary"), dict):
            summary = payload["summary"]
            message = (
                f"total={summary.get('total', 0)}, "
                f"ok={summary.get('ok', 0)}, "
                f"error={summary.get('error', 0)}, "
                f"pending={summary.get('pending', 0)}"
            )

    batch.refresh_from_db()
    return {
        # Estat Aqua del lot (0/1/2), no el `status` textual del proveïdor.
        "status": batch.status.token if batch.status else None,
        "message": message,
        "summary": payload.get("summary") if isinstance(payload, dict) else None,
        "payload": payload,
        "applied": applied,
        "status_code": response.get("status_code"),
    }


def push_invoice_batch(
    invoice_ids,
    *,
    billing=None,
    related_batch=None,
    client=None,
    dry_run=False,
    send=True,
    batch_id=None,
) -> list:
    """
    Envia factures en lots de fins a 1000.
    Retorna la llista de SendBatch creats (o payloads si dry_run).

    - dry_run=True: només retorna el JSON del lot (no crea SendBatch ni crida Odoo).
    - send=False: crea SendBatch i relaciona factures, però no fa POST a l'endpoint.
    """
    if dry_run and not send:
        raise OdooApiError("dry_run i send=False són incompatibles.")

    ids = list(invoice_ids)
    if not ids:
        raise OdooApiError("Cal almenys una factura per al lot.")

    invoices = list(
        Invoice.objects.select_related(
            "serie",
            "parent_invoice",
            "company",
            "contract__company",
            "payment_type",
        )
        .prefetch_related("line_items__product", "line_items__tax")
        .filter(pk__in=ids)
    )
    by_id = {inv.pk: inv for inv in invoices}
    ordered = [by_id[i] for i in ids if i in by_id]
    if len(ordered) != len(ids):
        missing = set(ids) - set(by_id)
        raise OdooApiError(f"Factures no trobades: {sorted(missing)}")

    batch_type = _get_batch_type(is_default=True)
    pending_status = _get_default_batch_status()
    odoo_client = _get_client_for_batch_type(batch_type, client=client)
    results = []

    for chunk in chunked(ordered, MAX_BATCH_ITEMS):
        items = [map_invoice_to_odoo(inv) for inv in chunk]
        current_batch_id = batch_id or generate_batch_id(batch_type.token)
        payload = {"batch_id": current_batch_id, "items": items}
        if dry_run:
            results.append(payload)
            batch_id = None
            continue

        batch = SendBatch.objects.create(
            token=current_batch_id,
            batch_type=batch_type,
            billing=billing,
            related_batch=related_batch,
            status=pending_status,
        )
        batch.invoices.set(chunk)

        if not send:
            results.append(batch)
            batch_id = None
            continue

        try:
            if not batch_type.endpoint:
                raise OdooApiError(
                    f"SendBatchType '{batch_type.token}' no té endpoint configurat."
                )
            response = odoo_client.push_batch(
                batch_type.endpoint,
                current_batch_id,
                items,
                object_type=f"send_batch_{batch_type.token}",
            )
            _store_instant_response(batch, response["status_code"], response["payload"])
        except OdooApiError as exc:
            batch.sent_at = timezone.now()
            batch.instant_response = {"detail": str(exc)}
            batch.save(update_fields=["sent_at", "instant_response", "updated_at"])
            raise

        results.append(batch)
        batch_id = None

    return results


def push_payment_movement_batch(
    movement_ids,
    *,
    billing=None,
    related_batch=None,
    client=None,
    dry_run=False,
    send=True,
    batch_id=None,
) -> list:
    """
    Envia moviments de pagament en lots de fins a 1000.
    Retorna la llista de SendBatch creats (o payloads si dry_run).

    - dry_run=True: només retorna el JSON del lot (no crea SendBatch ni crida Odoo).
    - send=False: crea SendBatch i relaciona moviments, però no fa POST a l'endpoint.
    """
    if dry_run and not send:
        raise OdooApiError("dry_run i send=False són incompatibles.")

    ids = list(movement_ids)
    if not ids:
        raise OdooApiError("Cal almenys un moviment per al lot.")

    movements = list(
        PaymentMovement.objects.select_related(
            "payment__invoice__serie",
            "payment__invoice__company",
            "payment__invoice__contract__company",
            "payment__invoice__parent_invoice",
            "payment__invoice__payment_company_bank__bank",
            "payment__contract__company",
            "payment_type",
            "payoff_invoice__serie",
            "payoff_invoice__company",
            "payoff_invoice__contract__company",
            "payment_remittance__company_bank__bank",
        ).filter(pk__in=ids)
    )
    by_id = {mov.pk: mov for mov in movements}
    ordered = [by_id[i] for i in ids if i in by_id]
    if len(ordered) != len(ids):
        missing = set(ids) - set(by_id)
        raise OdooApiError(f"Moviments no trobats: {sorted(missing)}")

    batch_type = _get_batch_type(token="payments")
    pending_status = _get_default_batch_status()
    odoo_client = _get_client_for_batch_type(batch_type, client=client)
    results = []

    for chunk in chunked(ordered, MAX_BATCH_ITEMS):
        items = [map_payment_movement_to_odoo(mov) for mov in chunk]
        current_batch_id = batch_id or generate_batch_id(batch_type.token)
        payload = {"batch_id": current_batch_id, "items": items}
        if dry_run:
            results.append(payload)
            batch_id = None
            continue

        batch = SendBatch.objects.create(
            token=current_batch_id,
            batch_type=batch_type,
            billing=billing,
            related_batch=related_batch,
            status=pending_status,
        )
        batch.payments.set(chunk)

        if not send:
            results.append(batch)
            batch_id = None
            continue

        try:
            if not batch_type.endpoint:
                raise OdooApiError(
                    f"SendBatchType '{batch_type.token}' no té endpoint configurat."
                )
            response = odoo_client.push_batch(
                batch_type.endpoint,
                current_batch_id,
                items,
                object_type=f"send_batch_{batch_type.token}",
            )
            _store_instant_response(batch, response["status_code"], response["payload"])
        except OdooApiError as exc:
            batch.sent_at = timezone.now()
            batch.instant_response = {"detail": str(exc)}
            batch.save(update_fields=["sent_at", "instant_response", "updated_at"])
            raise

        results.append(batch)
        batch_id = None

    return results


def push_commitment_deposit_batch(
    deposit_ids,
    *,
    action="create",
    billing=None,
    related_batch=None,
    client=None,
    dry_run=False,
    send=True,
    batch_id=None,
    date_override=None,
) -> list:
    """
    Envia compromisos de pagament (CommitmentDeposit) en lots de fins a 1000.

    action:
      - "create" → SendBatchType commitment_create (/batch/commitment/create)
      - "cancel" → SendBatchType commitment_cancel (/batch/commitment/cancel)

    Retorna la llista de SendBatch creats (o payloads si dry_run).

    - dry_run=True: només retorna el JSON del lot (no crea SendBatch ni crida Odoo).
    - send=False: crea SendBatch i relaciona compromisos, però no fa POST.
    """
    if dry_run and not send:
        raise OdooApiError("dry_run i send=False són incompatibles.")
    if not dry_run:
        ensure_commitments_supported(client if client is not None else OdooClient())

    action = (action or "create").strip().lower()
    if action not in ("create", "cancel"):
        raise OdooApiError(
            f"Acció de compromís desconeguda: {action!r}. Usa 'create' o 'cancel'."
        )

    ids = list(deposit_ids)
    if not ids:
        raise OdooApiError("Cal almenys un compromís per al lot.")

    deposits = list(
        CommitmentDeposit.objects.select_related("status", "contract")
        .prefetch_related("invoices", "payment_commitments")
        .filter(pk__in=ids)
    )
    by_id = {dep.pk: dep for dep in deposits}
    ordered = [by_id[i] for i in ids if i in by_id]
    if len(ordered) != len(ids):
        missing = set(ids) - set(by_id)
        raise OdooApiError(f"Compromisos no trobats: {sorted(missing)}")

    type_token = (
        "commitment_cancel" if action == "cancel" else "commitment_create"
    )
    mapper = (
        map_commitment_deposit_cancel_to_odoo
        if action == "cancel"
        else map_commitment_deposit_create_to_odoo
    )
    batch_type = _get_batch_type(token=type_token)
    pending_status = _get_default_batch_status()
    odoo_client = _get_client_for_batch_type(batch_type, client=client)
    results = []

    for chunk in chunked(ordered, MAX_BATCH_ITEMS):
        items = [mapper(dep, date_override=date_override) for dep in chunk]
        current_batch_id = batch_id or generate_batch_id(batch_type.token)
        payload = {"batch_id": current_batch_id, "items": items}
        if dry_run:
            results.append(payload)
            batch_id = None
            continue

        batch = SendBatch.objects.create(
            token=current_batch_id,
            batch_type=batch_type,
            billing=billing,
            related_batch=related_batch,
            status=pending_status,
        )
        batch.commitment_deposits.set(chunk)

        if not send:
            results.append(batch)
            batch_id = None
            continue

        try:
            if not batch_type.endpoint:
                raise OdooApiError(
                    f"SendBatchType '{batch_type.token}' no té endpoint configurat."
                )
            response = odoo_client.push_batch(
                batch_type.endpoint,
                current_batch_id,
                items,
                object_type=f"send_batch_{batch_type.token}",
            )
            _store_instant_response(batch, response["status_code"], response["payload"])
        except OdooApiError as exc:
            batch.sent_at = timezone.now()
            batch.instant_response = {"detail": str(exc)}
            batch.save(update_fields=["sent_at", "instant_response", "updated_at"])
            raise

        results.append(batch)
        batch_id = None

    return results
