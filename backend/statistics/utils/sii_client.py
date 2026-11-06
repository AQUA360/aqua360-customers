"""
AEAT SII client: submit already-built SOAP XML for issued invoices (facturas emitidas).

Uses mutual TLS with the company PFX certificate (PFX_PATH / PFX_PASS).
"""

from __future__ import annotations

import logging
import os
import tempfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

import requests
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.serialization import pkcs12
from django.conf import settings

logger = logging.getLogger(__name__)

# AEAT endpoints for SuministroLRFacturasEmitidas (SiiFactFEV1SOAP)
_SII_ENDPOINTS = {
    ("test", False): "https://prewww1.aeat.es/wlpl/SSII-FACT/ws/fe/SiiFactFEV1SOAP",
    ("test", True): "https://prewww10.aeat.es/wlpl/SSII-FACT/ws/fe/SiiFactFEV1SOAP",
    ("prod", False): "https://www1.agenciatributaria.gob.es/wlpl/SSII-FACT/ws/fe/SiiFactFEV1SOAP",
    ("prod", True): "https://www10.agenciatributaria.gob.es/wlpl/SSII-FACT/ws/fe/SiiFactFEV1SOAP",
}

# Map AEAT EstadoEnvio -> DailyDocumentSubmissionStatus.token
ESTADO_ENVIO_TO_STATUS = {
    "Correcto": "correct",
    "ParcialmenteCorrecto": "partially_correct",
    "Incorrecto": "incorrect",
}


@dataclass
class SiiInvoiceResult:
    invoice_number: Optional[str] = None
    status: Optional[str] = None
    error_code: Optional[str] = None
    error_description: Optional[str] = None


@dataclass
class SiiSubmitResult:
    ok: bool
    http_status: int
    estado_envio: Optional[str] = None
    submission_status: str = "error"
    csv: Optional[str] = None
    response_xml: Optional[str] = None
    error_message: Optional[str] = None
    invoice_results: List[SiiInvoiceResult] = field(default_factory=list)


def get_sii_endpoint() -> str:
    env = (getattr(settings, "SII_ENVIRONMENT", "test") or "test").strip().lower()
    if env in ("production", "prod", "pro"):
        env_key = "prod"
    else:
        env_key = "test"
    use_seal = bool(getattr(settings, "SII_USE_SEAL_CERT", True))
    return _SII_ENDPOINTS[(env_key, use_seal)]


def _load_pfx_as_pem_files(
    pfx_path: Optional[str] = None,
    pfx_password: Optional[str] = None,
) -> Tuple[str, str]:
    """Extract cert + key from PKCS#12 into temporary PEM files. Caller must clean up."""
    cert_path = pfx_path or getattr(settings, "PFX_PATH", "") or ""
    password = pfx_password if pfx_password is not None else getattr(settings, "PFX_PASS", "") or ""

    if not cert_path:
        raise ValueError("PFX_PATH is not configured")
    if not os.path.exists(cert_path):
        raise FileNotFoundError(f"Certificate file not found: {cert_path}")

    with open(cert_path, "rb") as f:
        pkcs12_data = f.read()

    private_key, certificate, _additional = pkcs12.load_key_and_certificates(
        pkcs12_data,
        password.encode("utf-8") if password else None,
        backend=default_backend(),
    )
    if not certificate or not private_key:
        raise ValueError("PFX file does not contain both a certificate and a private key")

    cert_fd, cert_pem = tempfile.mkstemp(suffix=".pem", prefix="sii_cert_")
    key_fd, key_pem = tempfile.mkstemp(suffix=".pem", prefix="sii_key_")
    try:
        with os.fdopen(cert_fd, "wb") as cert_file:
            cert_file.write(certificate.public_bytes(serialization.Encoding.PEM))
        with os.fdopen(key_fd, "wb") as key_file:
            key_file.write(
                private_key.private_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PrivateFormat.PKCS8,
                    encryption_algorithm=serialization.NoEncryption(),
                )
            )
    except Exception:
        for path in (cert_pem, key_pem):
            if os.path.exists(path):
                os.unlink(path)
        raise

    return cert_pem, key_pem


def _local_name(tag: str) -> str:
    if "}" in tag:
        return tag.rsplit("}", 1)[-1]
    return tag


def _find_text(root: ET.Element, name: str) -> Optional[str]:
    for el in root.iter():
        if _local_name(el.tag) == name and el.text and el.text.strip():
            return el.text.strip()
    return None


def parse_sii_response(response_xml: str) -> SiiSubmitResult:
    """Parse AEAT SOAP response into a structured result."""
    try:
        root = ET.fromstring(response_xml)
    except ET.ParseError as e:
        return SiiSubmitResult(
            ok=False,
            http_status=200,
            submission_status="error",
            response_xml=response_xml,
            error_message=f"Invalid SOAP response XML: {e}",
        )

    estado = _find_text(root, "EstadoEnvio")
    csv = _find_text(root, "CSV")
    submission_status = ESTADO_ENVIO_TO_STATUS.get(estado or "", "error")

    invoice_results: List[SiiInvoiceResult] = []
    for el in root.iter():
        if _local_name(el.tag) != "RespuestaLinea":
            continue
        invoice_results.append(
            SiiInvoiceResult(
                invoice_number=_find_text(el, "NumSerieFacturaEmisor"),
                status=_find_text(el, "EstadoRegistro"),
                error_code=_find_text(el, "CodigoErrorRegistro"),
                error_description=_find_text(el, "DescripcionErrorRegistro"),
            )
        )

    error_parts = []
    if estado == "Incorrecto":
        error_parts.append("Envío incorrecto según AEAT")
    elif estado == "ParcialmenteCorrecto":
        error_parts.append("Envío parcialmente correcto")
    for line in invoice_results:
        if line.error_code or line.error_description:
            error_parts.append(
                f"{line.invoice_number or '?'}: "
                f"[{line.error_code or '-'}] {line.error_description or line.status or ''}"
            )

    ok = estado == "Correcto"
    return SiiSubmitResult(
        ok=ok,
        http_status=200,
        estado_envio=estado,
        submission_status=submission_status if estado else "error",
        csv=csv,
        response_xml=response_xml,
        error_message="; ".join(error_parts) if error_parts else None,
        invoice_results=invoice_results,
    )


class SiiSubmitClient:
    """POST raw SII SOAP XML to AEAT with client certificate auth."""

    def __init__(
        self,
        endpoint: Optional[str] = None,
        timeout: Optional[int] = None,
        verify_ssl: Optional[bool] = None,
        pfx_path: Optional[str] = None,
        pfx_password: Optional[str] = None,
    ):
        self.endpoint = endpoint or get_sii_endpoint()
        self.timeout = timeout if timeout is not None else int(getattr(settings, "SII_TIMEOUT", 60))
        self.verify_ssl = (
            verify_ssl
            if verify_ssl is not None
            else bool(getattr(settings, "SII_VERIFY_SSL", True))
        )
        self.pfx_path = pfx_path
        self.pfx_password = pfx_password

    def submit_issued_invoices(self, xml_string: str) -> SiiSubmitResult:
        if not xml_string or not xml_string.strip():
            return SiiSubmitResult(
                ok=False,
                http_status=0,
                submission_status="error",
                error_message="Empty SII XML payload",
            )

        cert_pem = key_pem = None
        try:
            cert_pem, key_pem = _load_pfx_as_pem_files(self.pfx_path, self.pfx_password)
        except Exception as e:
            logger.exception("Failed to load SII client certificate")
            return SiiSubmitResult(
                ok=False,
                http_status=0,
                submission_status="error",
                error_message=f"Certificate error: {e}",
            )

        try:
            if not self.verify_ssl:
                import urllib3

                urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

            response = requests.post(
                self.endpoint,
                data=xml_string.encode("utf-8"),
                headers={
                    "Content-Type": "text/xml; charset=utf-8",
                    "Accept": "text/xml",
                },
                cert=(cert_pem, key_pem),
                timeout=self.timeout,
                verify=self.verify_ssl,
            )
        except requests.RequestException as e:
            logger.exception("SII HTTP request failed")
            return SiiSubmitResult(
                ok=False,
                http_status=0,
                submission_status="error",
                error_message=f"HTTP error contacting AEAT: {e}",
            )
        finally:
            for path in (cert_pem, key_pem):
                if path and os.path.exists(path):
                    try:
                        os.unlink(path)
                    except OSError:
                        pass

        response_text = response.text or ""
        if response.status_code >= 400:
            return SiiSubmitResult(
                ok=False,
                http_status=response.status_code,
                submission_status="error",
                response_xml=response_text,
                error_message=f"AEAT HTTP {response.status_code}",
            )

        result = parse_sii_response(response_text)
        result.http_status = response.status_code
        return result
