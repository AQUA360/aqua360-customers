import json
import tempfile

from django.test import SimpleTestCase

from billing.validators.sepa_xsd_validator import PAIN_001_XSD_PATH, PAIN_008_XSD_PATH, validate_sepa_xml


def build_transfer(pmt_mtd="TRF"):
    """Fitxer de transferència pain.001.001.03 mínim amb l'estructura que genera `generate_xml_payments`."""
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<Document xmlns="urn:iso:std:iso:20022:tech:xsd:pain.001.001.03">
<CstmrCdtTrfInitn>
  <GrpHdr>
    <MsgId>MSG0001</MsgId><CreDtTm>2026-10-19T08:00:00</CreDtTm><NbOfTxs>1</NbOfTxs><CtrlSum>10.00</CtrlSum>
    <InitgPty><Nm>EMPRESA DE PROVA</Nm><Id><OrgId><Othr><Id>B00000000</Id></Othr></OrgId></Id></InitgPty>
  </GrpHdr>
  <PmtInf>
    <PmtInfId>MSG0001</PmtInfId><PmtMtd>{pmt_mtd}</PmtMtd><BtchBookg>false</BtchBookg>
    <NbOfTxs>1</NbOfTxs><CtrlSum>10.00</CtrlSum>
    <PmtTpInf><SvcLvl><Cd>SEPA</Cd></SvcLvl></PmtTpInf>
    <ReqdExctnDt>2026-10-20</ReqdExctnDt>
    <Dbtr><Nm>EMPRESA DE PROVA</Nm></Dbtr>
    <DbtrAcct><Id><IBAN>ES9121000418450200051332</IBAN></Id></DbtrAcct>
    <DbtrAgt><FinInstnId><BIC>CAIXESBBXXX</BIC></FinInstnId></DbtrAgt>
    <ChrgBr>SLEV</ChrgBr>
    <CdtTrfTxInf>
      <PmtId><EndToEndId>0100000000001-1</EndToEndId></PmtId>
      <Amt><InstdAmt Ccy="EUR">10.00</InstdAmt></Amt>
      <CdtrAgt><FinInstnId><BIC>CAIXESBBXXX</BIC></FinInstnId></CdtrAgt>
      <Cdtr><Nm>PERSONA DE PROVA</Nm></Cdtr>
      <CdtrAcct><Id><IBAN>ES7921000813610123456789</IBAN></Id></CdtrAcct>
      <RmtInf><Ustrd>DEVOLUCIO</Ustrd></RmtInf>
    </CdtTrfTxInf>
  </PmtInf>
</CstmrCdtTrfInitn>
</Document>"""


class TransferXsdValidatorTests(SimpleTestCase):
    def test_valid_transfer(self):
        """Comprova que una transferència vàlida compleix l'XSD pain.001."""
        result = validate_sepa_xml(build_transfer(), PAIN_001_XSD_PATH)
        self.assertTrue(result["valid"], result)

    def test_rejects_non_sepa_payment_method(self):
        """Comprova que l'XSD SEPA rebutja el mètode de pagament CHK."""
        # L'XSD de l'ISO accepta CHK; el de la DK només TRF.
        result = validate_sepa_xml(build_transfer(pmt_mtd="CHK"), PAIN_001_XSD_PATH)
        self.assertFalse(result["valid"])
        self.assertTrue(any("PmtMtd" in e["message"] for e in result["errors"]))

    def test_transfer_is_not_a_valid_direct_debit(self):
        """Comprova que un XML de transferència no compleix l'XSD de rebuts."""
        result = validate_sepa_xml(build_transfer(), PAIN_008_XSD_PATH)
        self.assertFalse(result["valid"])


class XsdValidatorXmlSafetyTests(SimpleTestCase):
    def with_doctype(self, doctype):
        """Insereix un DOCTYPE després de la declaració XML d'una transferència."""
        # La capçalera XML va abans del DOCTYPE; la resta del document és un TRF vàlid.
        header, body = build_transfer().split("\n", 1)
        return f"{header}\n{doctype}\n{body}"

    def test_rejects_external_entity_without_reading_the_file(self):
        """Comprova que es rebutgen entitats externes sense exposar el fitxer local."""
        with tempfile.NamedTemporaryFile("w", suffix=".txt") as canary:
            canary.write("CANARY-CONTENT")
            canary.flush()
            xml = self.with_doctype(
                f'<!DOCTYPE Document [<!ENTITY x SYSTEM "file://{canary.name}">]>'
            ).replace("<Ustrd>DEVOLUCIO</Ustrd>", "<Ustrd>&x;</Ustrd>")

            result = validate_sepa_xml(xml, PAIN_001_XSD_PATH)

        self.assertFalse(result["valid"])
        self.assertNotIn("CANARY-CONTENT", json.dumps(result))

    def test_rejects_entity_expansion_bomb(self):
        """Comprova que es rebutja un XML amb expansió recursiva d'entitats."""
        entities = '<!ENTITY a0 "aaaaaaaaaa">' + "".join(
            f'<!ENTITY a{i} "{f"&a{i - 1};" * 10}">' for i in range(1, 8)
        )
        xml = self.with_doctype(f"<!DOCTYPE Document [{entities}]>").replace(
            "<Ustrd>DEVOLUCIO</Ustrd>", "<Ustrd>&a7;</Ustrd>"
        )

        result = validate_sepa_xml(xml, PAIN_001_XSD_PATH)

        self.assertFalse(result["valid"])

    def test_rejects_any_doctype(self):
        """Comprova que qualsevol DOCTYPE produeix l'error de DTD no permès."""
        result = validate_sepa_xml(self.with_doctype("<!DOCTYPE Document>"), PAIN_001_XSD_PATH)

        self.assertFalse(result["valid"])
        self.assertEqual(result["error"], "DTD not allowed")
