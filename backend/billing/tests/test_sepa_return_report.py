import datetime
import xml.etree.ElementTree as ET

from django.test import SimpleTestCase

from billing.utils.sepa_service import extract_report_data, identify_report_bank, parse_report_creation_date

NAMESPACE = {"pain": "urn:iso:std:iso:20022:tech:xsd:pain.002.001.03"}


def build_report(cre_dt_tm, header_bic="CGUIESBAXXX", creditor_iban="ES0031400000000000000000"):
    """Informe de retorn pain.002.001.03 amb l'estructura dels que genera Caixa Guissona."""
    header_agent = (
        f"<CdtrAgt><FinInstnId><BIC>{header_bic}</BIC></FinInstnId></CdtrAgt>" if header_bic else ""
    )
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Document xmlns="{NAMESPACE['pain']}">
<CstmrPmtStsRpt>
  <GrpHdr><MsgId>MSG0001</MsgId><CreDtTm>{cre_dt_tm}</CreDtTm>{header_agent}</GrpHdr>
  <OrgnlGrpInfAndSts>
    <OrgnlMsgId>2026-08-19REMESA0001</OrgnlMsgId><OrgnlMsgNmId>pain.008.001.02</OrgnlMsgNmId>
    <OrgnlNbOfTxs>1</OrgnlNbOfTxs><OrgnlCtrlSum>10.00</OrgnlCtrlSum>
  </OrgnlGrpInfAndSts>
  <OrgnlPmtInfAndSts>
    <OrgnlPmtInfId>REMESA0001</OrgnlPmtInfId>
    <TxInfAndSts>
      <OrgnlEndToEndId>0100000000001-01</OrgnlEndToEndId><TxSts>RJCT</TxSts>
      <StsRsnInf><Rsn><Cd>AM04</Cd></Rsn></StsRsnInf>
      <OrgnlTxRef>
        <Amt><InstdAmt Ccy="EUR">10.00</InstdAmt></Amt><ReqdColltnDt>2026-08-15</ReqdColltnDt>
        <Dbtr><Nm>DEUTOR DE PROVA</Nm></Dbtr>
        <DbtrAcct><Id><IBAN>ES0000000000000000000000</IBAN></Id></DbtrAcct>
        <Cdtr><Nm>CREDITOR DE PROVA</Nm></Cdtr>
        <CdtrAcct><Id><IBAN>{creditor_iban}</IBAN></Id></CdtrAcct>
      </OrgnlTxRef>
    </TxInfAndSts>
  </OrgnlPmtInfAndSts>
</CstmrPmtStsRpt>
</Document>"""
    root = ET.fromstring(xml.encode("utf-8"))
    return root.find(".//pain:CstmrPmtStsRpt", NAMESPACE)


class TestIdentifyReportBank(SimpleTestCase):
    def test_bank_from_header_bic(self):
        self.assertEqual(identify_report_bank(build_report("2026-13-10T14:16:00"), NAMESPACE), "CGUIESBA")

    def test_bank_from_creditor_iban_when_header_has_no_bic(self):
        report = build_report("2026-13-10T14:16:00", header_bic=None)
        self.assertEqual(identify_report_bank(report, NAMESPACE), "CGUIESBA")

    def test_debtor_bic_does_not_identify_the_bank(self):
        # Un deutor amb compte a Caixa Guissona no fa que l'informe d'un altre banc es llegeixi com de Guissona
        report = build_report("2026-09-10T10:00:00", header_bic="CAIXESBBXXX")
        debtor = report.find(".//pain:Dbtr", NAMESPACE)
        ET.SubElement(debtor, f"{{{NAMESPACE['pain']}}}BICOrBEI").text = "CGUIESBAXXX"
        self.assertEqual(identify_report_bank(report, NAMESPACE), "CAIXESBB")

    def test_unknown_bank(self):
        report = build_report("2026-10-13T14:16:00", header_bic=None, creditor_iban="ES0021000000000000000000")
        self.assertIsNone(identify_report_bank(report, NAMESPACE))


class TestParseReportCreationDate(SimpleTestCase):
    def test_guissona_day_before_month(self):
        self.assertEqual(parse_report_creation_date("2026-13-10T14:16:00", "CGUIESBA"), datetime.datetime(2026, 10, 13))

    def test_guissona_ambiguous_date_uses_bank_format(self):
        # 2026-09-10 en ISO seria el 10/09; Caixa Guissona el genera per al 9/10
        self.assertEqual(parse_report_creation_date("2026-09-10T10:00:00", "CGUIESBA"), datetime.datetime(2026, 10, 9))

    def test_guissona_iso_date_when_bank_format_is_not_valid(self):
        self.assertEqual(parse_report_creation_date("2026-10-13T10:00:00", "CGUIESBA"), datetime.datetime(2026, 10, 13))

    def test_other_banks_use_iso(self):
        self.assertEqual(parse_report_creation_date("2026-09-10T10:00:00", "CAIXESBB"), datetime.datetime(2026, 9, 10))

    def test_other_banks_swap_day_and_month_when_iso_is_not_valid(self):
        self.assertEqual(parse_report_creation_date("2026-13-10T10:00:00", None), datetime.datetime(2026, 10, 13))

    def test_invalid_or_empty_date(self):
        self.assertIsNone(parse_report_creation_date("2026-13-13T10:00:00", None))
        self.assertIsNone(parse_report_creation_date(None, "CGUIESBA"))


class TestExtractReportDataGuissona(SimpleTestCase):
    def test_reject_date_comes_from_report_date_not_from_remittance_id(self):
        # Abans el CreDtTm no es podia llegir i es feia servir la data de l'OrgnlMsgId (generació de
        # la remesa), anterior a la data de cobrament: tots els retorns es descartaven
        report_data, rjt_date = extract_report_data(build_report("2026-13-10T14:16:00"), NAMESPACE)
        self.assertEqual(report_data["bank_bic"], "CGUIESBA")
        self.assertEqual(rjt_date, "2026-10-13T00:00:00")
