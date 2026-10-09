#sign_certificate_service
import tempfile
from PyPDF2 import PdfReader
from django.conf import settings
from urllib.request import urlopen
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.exceptions import InvalidSignature
import base64
from io import BytesIO
import os
import subprocess
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend
from cryptography import x509

from datetime import datetime
from pypdf import PdfReader, PdfWriter

from cryptography.hazmat.primitives.serialization import pkcs12

from pyhanko_certvalidator.registry import CertificateStore
from pyhanko import stamp
from pyhanko.pdf_utils import generic
from pyhanko.sign.signers import PdfSignatureMetadata
from pyhanko.sign.signers import SimpleSigner
from pyhanko.sign import sign_pdf as pyhanko_sign_pdf
from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter
from pyhanko.sign import signers, fields
from pyhanko.sign.fields import SigFieldSpec
from pyhanko.pdf_utils import incremental_writer
from asn1crypto import pem
from asn1crypto import x509 as asn1x509
from pyhanko.keys import load_private_key_from_pemder_data

from pyhanko.sign.fields import SigSeedSubFilter

from pyhanko_certvalidator import ValidationContext

import logging

from cryptography.hazmat.primitives.asymmetric import rsa, dsa, ec

logger = logging.getLogger(__name__)

def load_key_and_cert(private_key_path, certificate_path):
    with open(private_key_path, "rb") as key_file:
        private_key = serialization.load_pem_private_key(
            key_file.read(),
            password=None,
            backend=default_backend()
        )

    with open(certificate_path, "rb") as cert_file:
        certificate = x509.load_pem_x509_certificate(
            cert_file.read(),
            default_backend()
        )
    return private_key, certificate

def is_signed_pdf(file):
    try:
        reader = PdfReader(file)
        if '/AcroForm' in reader.trailer['/Root']:
            fields = reader.get_fields()
            signature_fields = [k for k, v in fields.items() if v.get('/FT') == '/Sig']
            # print("\nsignature_fields")
            # print(signature_fields)
            if signature_fields:
                file.seek(0)

                with tempfile.NamedTemporaryFile(delete=True, suffix='.pdf') as tmp:
                    tmp.write(file.read())
                    tmp.flush()
                    validate_signatures_with_pdfsig(tmp.name)
                
                file.seek(0)

                return True
            #return bool(signature_fields)
        return False
    except Exception as e:
        logger.warning("Error checking PDF signature", exc_info=e)
        return None

def validate_signatures_with_pdfsig(file_path):
    try:
        result = subprocess.run(['pdfsig', file_path], capture_output=True, text=True)
        output = result.stdout
        print("\nSignature Validation Output:")
        print(output)

        if "Signature validation failed" in output or "Signature is invalid" in output or "Signature has not yet been verified" in output:
            print("\n\033[93mOne or more signatures are invalid.\033[0m\n")
        else:
            print("\n\033[92mAll signatures are valid.\033[0m\n")
    except FileNotFoundError:
        print("'pdfsig' not found. Install poppler-utils to enable signature validation.")
    except Exception as e:
        logger.warning("Error validating PDF signatures", exc_info=e)



def sign_pdf(pdf_buffer, company, title, keywords):
    cert_path = settings.PFX_PATH  
    cert_password = settings.PFX_PASS.encode("utf-8")

    if not os.path.exists(cert_path):
        # print(f"Certificate file not found at {cert_path}")
        return pdf_buffer
    try:
        with open(cert_path, "rb") as f:
            pfx_data = f.read()
        
        pdf_buffer.seek(0)
        
        private_key, cert, other_certs = pkcs12.load_key_and_certificates(
            pfx_data,
            password=cert_password,
            backend=default_backend()
        )
        print(f"Type of loaded certificate: {type(cert)}")

        if cert is None:
            print("Error: Could not load certificate from PFX.")
            return pdf_buffer
        
        # Create a signer for pyHanko
        cert_registry = CertificateStore()
        if other_certs:
            for c in other_certs:
                cert_registry.add_cert(c)

        signer = signers.SimpleSigner.load_pkcs12(
            cert_path, 
            passphrase=cert_password,
        )
        
        signature_meta = signers.PdfSignatureMetadata(
            field_name='Signature1', md_algorithm='sha256',
            subfilter=SigSeedSubFilter.PADES,
            validation_context=ValidationContext(allow_fetching=True),
            embed_validation_info=True,
            use_pades_lta=True
        )
        
        writer = IncrementalPdfFileWriter(pdf_buffer)
        
        signed_pdf = pyhanko_sign_pdf(
            writer,
            signer=signer,
            signature_meta=signature_meta,
        )

        signed_pdf.seek(0)
        return signed_pdf
    except Exception as e:
        print(f"Error signing PDF: {e}")
        return pdf_buffer
