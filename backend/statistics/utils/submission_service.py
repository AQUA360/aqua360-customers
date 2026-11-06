"""
Generic external submission for DailyDocuments.

AvailableReport.submission_channel selects the handler. Channel-specific
logic (e.g. AEAT SII) lives in dedicated modules and is registered here.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from django.utils import timezone

from documentmanager.utils.main_utils import download_document

logger = logging.getLogger(__name__)

SUBMISSION_CHANNEL_SII_EMITIDAS = "sii_emitidas"


@dataclass
class SubmissionResult:
    """Channel-agnostic outcome of an external submission."""

    ok: bool
    channel: str
    submission_status: str
    reference: Optional[str] = None
    response_body: Optional[str] = None
    error_message: Optional[str] = None
    http_status: int = 0
    details: Dict[str, Any] = field(default_factory=dict)

    def to_api_dict(self) -> dict:
        return {
            "ok": self.ok,
            "channel": self.channel,
            "submission_status": self.submission_status,
            "reference": self.reference,
            "http_status": self.http_status,
            "error_message": self.error_message,
            "details": self.details,
        }


class SubmissionError(Exception):
    """Business-rule failure before or while submitting externally."""

    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


SubmissionHandler = Callable[[Any], SubmissionResult]


def get_submission_channel(daily_document) -> Optional[str]:
    template = getattr(daily_document, "template", None)
    if not template:
        return None
    report = getattr(template, "available_report", None)
    if not report:
        return None
    return report.submission_channel or None


def read_document_text(document) -> str:
    response = download_document(document)
    content = getattr(response, "content", None)
    if content is None:
        raise SubmissionError("Could not read document content", status_code=500)
    if isinstance(content, bytes):
        return content.decode("utf-8")
    return str(content)


def _mark_daily_document_completed(daily_document, user=None) -> list:
    """Set completed status/fields like the manual 'send' action. Returns update_fields."""
    from coredata.models import ConfigProject
    from statistics.models import DailyDocumentStatus

    update_fields = []
    try:
        completed_status_token = ConfigProject.objects.get(
            token="daily_document_status_completed_token"
        ).value
        completed_status = DailyDocumentStatus.objects.get(token=completed_status_token)
    except Exception:
        logger.exception("Could not resolve completed DailyDocumentStatus")
        completed_status = None

    now = timezone.now()
    if not daily_document.is_completed:
        daily_document.is_completed = True
        update_fields.append("is_completed")
    if not daily_document.completed_at:
        daily_document.completed_at = now
        update_fields.append("completed_at")
    if completed_status is not None and daily_document.status_id != completed_status.id:
        daily_document.status = completed_status
        update_fields.append("status")
    if user is not None and not daily_document.completed_by_id:
        daily_document.completed_by = user
        update_fields.append("completed_by")
    return update_fields


def _resolve_submission_status(token: Optional[str]):
    """Map handler token (e.g. 'correct') to a DailyDocumentSubmissionStatus row."""
    from statistics.models import DailyDocumentSubmissionStatus

    if not token:
        return None
    status = DailyDocumentSubmissionStatus.objects.filter(token=token, is_active=True).first()
    if status is not None:
        return status
    # Fallback so a missing seed row never blocks persistence of the submission.
    status = DailyDocumentSubmissionStatus.objects.filter(token="error", is_active=True).first()
    if status is None:
        logger.error("DailyDocumentSubmissionStatus token=%r (and fallback 'error') not found", token)
    elif token != "error":
        logger.error(
            "DailyDocumentSubmissionStatus token=%r not found; falling back to 'error'",
            token,
        )
    return status


def _persist_result(daily_document, result: SubmissionResult, user=None) -> None:
    daily_document.submitted_at = timezone.now()
    daily_document.submission_status = _resolve_submission_status(result.submission_status)
    daily_document.submission_csv = result.reference
    daily_document.submission_response = result.response_body
    daily_document.submission_error = result.error_message
    update_fields = [
        "submitted_at",
        "submission_status",
        "submission_csv",
        "submission_response",
        "submission_error",
        "updated_at",
    ]
    # Correct external submission finalizes the daily document (sent/completed).
    if result.ok and not (daily_document.cancelled_at or daily_document.cancelled_by_id):
        update_fields.extend(_mark_daily_document_completed(daily_document, user=user))
    daily_document.save(update_fields=update_fields)


def _get_handlers() -> Dict[str, SubmissionHandler]:
    # Lazy imports keep channel modules optional and avoid circular imports.
    from statistics.utils.sii_submission_service import handle_sii_emitidas

    return {
        SUBMISSION_CHANNEL_SII_EMITIDAS: handle_sii_emitidas,
    }


def supported_channels() -> List[str]:
    return list(_get_handlers().keys())


def submit_daily_document(daily_document, user=None) -> SubmissionResult:
    channel = get_submission_channel(daily_document)
    if not channel:
        raise SubmissionError(
            "This daily document has no submission channel",
            status_code=400,
        )

    handler = _get_handlers().get(channel)
    if not handler:
        raise SubmissionError(
            f"Unsupported submission channel: {channel}",
            status_code=400,
        )

    if daily_document.cancelled_at or daily_document.cancelled_by_id:
        raise SubmissionError("Cannot submit a cancelled daily document", status_code=400)

    if not daily_document.document_id:
        raise SubmissionError("Daily document has no file to submit", status_code=400)

    result = handler(daily_document)
    _persist_result(daily_document, result, user=user)
    return result
