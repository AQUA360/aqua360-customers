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


def _persist_result(daily_document, result: SubmissionResult) -> None:
    daily_document.submitted_at = timezone.now()
    daily_document.submission_status = result.submission_status
    daily_document.submission_csv = result.reference
    daily_document.submission_response = result.response_body
    daily_document.submission_error = result.error_message
    daily_document.save(
        update_fields=[
            "submitted_at",
            "submission_status",
            "submission_csv",
            "submission_response",
            "submission_error",
            "updated_at",
        ]
    )


def _get_handlers() -> Dict[str, SubmissionHandler]:
    # Lazy imports keep channel modules optional and avoid circular imports.
    from statistics.utils.sii_submission_service import handle_sii_emitidas

    return {
        SUBMISSION_CHANNEL_SII_EMITIDAS: handle_sii_emitidas,
    }


def supported_channels() -> List[str]:
    return list(_get_handlers().keys())


def submit_daily_document(daily_document) -> SubmissionResult:
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
    _persist_result(daily_document, result)
    return result
