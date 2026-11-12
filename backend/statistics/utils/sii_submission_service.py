"""AEAT SII (facturas emitidas) handler for the generic submission dispatcher."""

from __future__ import annotations

import logging

from django.conf import settings

from statistics.utils.sii_client import SiiSubmitClient
from statistics.utils.submission_service import (
    SUBMISSION_CHANNEL_SII_EMITIDAS,
    SubmissionError,
    SubmissionResult,
    read_document_text,
)

logger = logging.getLogger(__name__)


def handle_sii_emitidas(daily_document) -> SubmissionResult:
    if not getattr(settings, "SII_ENABLED", False):
        raise SubmissionError("SII submission is disabled (SII_ENABLED=False)", status_code=503)

    xml_string = read_document_text(daily_document.document)
    client = SiiSubmitClient()
    sii = client.submit_issued_invoices(xml_string)

    return SubmissionResult(
        ok=sii.ok,
        channel=SUBMISSION_CHANNEL_SII_EMITIDAS,
        submission_status=sii.submission_status,
        reference=sii.csv,
        response_body=sii.response_xml,
        error_message=sii.error_message,
        http_status=sii.http_status,
        details={
            "estado_envio": sii.estado_envio,
            "invoice_results": [
                {
                    "invoice_number": line.invoice_number,
                    "status": line.status,
                    "error_code": line.error_code,
                    "error_description": line.error_description,
                }
                for line in sii.invoice_results
            ],
        },
    )
