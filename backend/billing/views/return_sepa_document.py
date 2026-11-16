# views.py (or wherever your API view is defined)
import logging

import defusedxml.ElementTree as ET
from defusedxml.common import DefusedXmlException
from rest_framework import status
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from rest_framework.response import Response
from rest_framework.views import APIView

from billing.models import Reading
from billing.utils.sepa_service import (
    extract_clients_data,
    extract_company_data,
    extract_og_msg_id,
    extract_report_data,
    getDocumentSEPAPayments,
)

logger = logging.getLogger(__name__)


class ReturnSEPADocument(APIView):
    permission_classes = [IsAuthenticated, DjangoModelPermissions]
    queryset = Reading.objects.all().order_by('-created_at')
    def put(self, request, *args, **kwargs):
        """Process an uploaded SEPA status report and return payment rejections.

        Return HTTP 400 for missing uploads, unsupported namespaces or malformed
        XML; log parse errors and return a generic message.
        """
        file = request.data.get("file")
        print("in sepa return")
        if not file:
            return Response(
                {"error": "No file was uploaded."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            file_content = file.read()
            if isinstance(file_content, bytes):
                file_content = file_content.decode("utf-8")
                
            # Uploaded SEPA return file: forbid DTDs/entities (XXE / XML bombs).
            root = ET.fromstring(file_content, forbid_dtd=True)

            namespaces = [
                {
                    "pain": "urn:iso:std:iso:20022:tech:xsd:pain.002.001.03"
                },
                {
                    "pain": "urn:iso:std:iso:20022:tech:xsd:pain.002.001.10"
                }
            ]
            
            reports, company_data, clients_data, og_msg_id, rjt_date = self.parse_sepa_report(
                root, namespaces
            )
            if reports and reports[0]:
                rejections = getDocumentSEPAPayments(
                    reports[0]["orgn_msg_id"], company_data, clients_data, file_content, og_msg_id, rjt_date
                )
            else:
                return Response(
                    {"error": f"Wrong namespace in file. Contact technical support."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            return Response(
                {"rejections": rejections, "og_msg_id": og_msg_id}, status=status.HTTP_200_OK
            )

        except (ET.ParseError, DefusedXmlException):
            logger.exception("El fitxer XML de retorn no és vàlid")
            return Response(
                {"error": "El fitxer XML no és vàlid."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            logger.exception("Error inesperat")
            return Response(
                {"error": "Error processing file."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def parse_sepa_report(self, root, namespaces):
        reports = []
        company_data = {}
        clients_data = []
        og_msg_id = None

        for namespace in namespaces:
            for report in root.findall(".//pain:CstmrPmtStsRpt", namespace):
                report_data, rjt_date = extract_report_data(report, namespace)
                company_data = extract_company_data(report, namespace)
                clients_data = extract_clients_data(report, namespace, rjt_date)
                og_msg_id = extract_og_msg_id(report, namespace)
                reports.append(report_data)

        return reports, company_data, clients_data, og_msg_id, rjt_date
