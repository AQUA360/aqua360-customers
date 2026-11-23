from decimal import Decimal
from datetime import datetime, timedelta, date
import uuid
# nosemgrep: python.lang.security.use-defused-xml.use-defused-xml
# Generation only (Element/SubElement/tostring); no untrusted XML is parsed here.
import xml.etree.ElementTree as ET
from decouple import config
from django.utils import timezone
import re
from django.utils.translation import gettext as _
from coredata.models import Bank, ConfigProject
from coredata.utils.address_utils import get_address_complete_without_city
from coredata.utils.iban_validator_utils import get_spanish_bic
from billing.utils.remittance_bank_check import normalize_account_code
from pricing.models import ProductOrigin
from service.models import Exploitation
from service.serializers.company_serializer import CompanySerializer
from faker import Faker
fake = Faker()
from schwifty import IBAN as SchwiftyIBAN

def generate_payment_remittance_ident_msg(vat):
    """
    Build MsgId as {vat}{YYYYMMDD}{NNN}, where NNN is 1 + the highest
    existing PaymentRemittance.token sequence for the same vat+date prefix.
    """
    from billing.models import PaymentRemittance

    base_token = f"{vat}{datetime.now().strftime('%Y%m%d')}"
    existing_tokens = PaymentRemittance.objects.filter(
        token__startswith=base_token
    ).values_list('token', flat=True)

    max_seq = 0
    prefix_len = len(base_token)
    for token in existing_tokens:
        if not token:
            continue
        suffix = token[prefix_len:]
        if suffix.isdigit():
            max_seq = max(max_seq, int(suffix))

    return f"{base_token}{max_seq + 1:03d}"

# Longitud màxima del concepte (RmtInf/Ustrd) segons l'esquema SEPA.
SEPA_USTRD_MAX_LENGTH = 140

def build_sepa_concept(prefix, invoice_numbers, invoice_label="FRA"):
    """
    Concepte del rebut: el prefix seguit dels números de factura, perquè el client
    i el banc vegin quines factures es cobren. Si el banc retorna el rebut, el
    retorn conserva aquest concepte.
    Si no hi caben totes, s'afegeix "+N" amb les que falten.
    """
    numbers = [n for n in invoice_numbers if n]
    if not numbers:
        return prefix[:SEPA_USTRD_MAX_LENGTH]

    concept = f"{prefix} {invoice_label}" if prefix else invoice_label
    for index, number in enumerate(numbers):
        candidate = f"{concept} {number}"
        remaining = len(numbers) - index - 1
        suffix = f" +{remaining}" if remaining else ""
        if len(candidate) + len(suffix) > SEPA_USTRD_MAX_LENGTH:
            suffix = f" +{len(numbers) - index}"
            return f"{concept[:SEPA_USTRD_MAX_LENGTH - len(suffix)]}{suffix}"
        concept = candidate
    return concept

# Camps que es poden mostrar al concepte del rebut (l'usuari tria quins; per defecte, tots).
SEPA_CONCEPT_FIELDS = ("contract", "invoice", "amount", "consumption", "supply_point")

SEPA_CONCEPT_FIELDS_CONFIG_TOKEN = "sepa_concept_fields"

def get_saved_concept_fields():
    """
    Camps del concepte que l'usuari ha desat (configuració global, per a tots els usuaris).
    None = encara no s'ha desat res: es mostren tots.
    """
    config_row = ConfigProject.objects.filter(token=SEPA_CONCEPT_FIELDS_CONFIG_TOKEN).first()
    if config_row is None or config_row.value is None:
        return None
    return [field.strip() for field in config_row.value.split(",") if field.strip()]

def save_concept_fields(fields):
    """Desa la configuració global; retorna els camps normalitzats (en l'ordre del concepte)."""
    selected = normalize_concept_fields(fields)
    ordered = [field for field in SEPA_CONCEPT_FIELDS if field in selected]
    ConfigProject.objects.update_or_create(
        token=SEPA_CONCEPT_FIELDS_CONFIG_TOKEN,
        defaults={
            "name": "Camps del concepte del rebut bancari SEPA (separats per comes)",
            "value": ",".join(ordered),
        },
    )
    return ordered

def normalize_concept_fields(fields):
    """None (sense configurar) = tots els camps. Ignora valors desconeguts."""
    if fields is None:
        return set(SEPA_CONCEPT_FIELDS)
    return {field for field in fields if field in SEPA_CONCEPT_FIELDS}

_SEPA_DETAIL_LABELS = {
    "ca": ("IMPORT", "CONSUM", "PUNT SUBM."),
    "es": ("IMPORTE", "CONSUMO", "PUNTO SUM."),
}
_SEPA_DETAIL_LABELS_DEFAULT = ("AMOUNT", "CONSUMPTION", "SUPPLY POINT")
SEPA_ELLIPSIS = "..."

def _fit_supply_point(address, fallback_name, budget):
    """
    Punt de subministrament dins de `budget` caràcters, sense municipi. Per ordre de prioritat:
    1. Adreça sencera + codi postal.
    2. Adreça sencera (el codi postal es treu sencer, mai a mitges).
    3. Carrer retallat amb "..." però conservant sempre el número (per saber on cal trucar).
    """
    if budget <= 0:
        return ""
    if not address:
        name = fallback_name or ""
        return name if len(name) <= budget else name[:max(budget - len(SEPA_ELLIPSIS), 0)].rstrip() + SEPA_ELLIPSIS

    # Col·lapsa els espais dobles que deixen els camps buits (edifici, escala...).
    full = " ".join(get_address_complete_without_city(address, include_extra=False).split()).rstrip(", ")
    postal_code = address.postal_code
    if postal_code and len(full) + 1 + len(postal_code) <= budget:
        return f"{full} {postal_code}"
    if len(full) <= budget:
        return full

    # Mateixa normalització d'espais que `full`, si no `full.startswith(street)` falla amb espais dobles.
    street = " ".join(str(address.street).split())
    tail = full[len(street):] if full.startswith(street) else ""
    # Si ni amb el carrer mínim hi cap tota la cua (escala, pis...), es queda només el número.
    for candidate_tail in (tail, f", {address.street_number}" if address.street_number else ""):
        room = budget - len(candidate_tail) - len(SEPA_ELLIPSIS)
        if room > 0:
            return f"{street[:room].rstrip()}{SEPA_ELLIPSIS}{candidate_tail}"
    return full[:max(budget - len(SEPA_ELLIPSIS), 0)].rstrip() + SEPA_ELLIPSIS

def _invoice_supply_points(invoice):
    """
    Punts de subministrament que cobreix la factura (els de les seves lectures, sense repetits).
    Si no en té, el punt per defecte del contracte.
    """
    points = {}
    readings = invoice.readings.all() if getattr(invoice, "readings", None) is not None else []
    if hasattr(readings, "select_related"):
        readings = readings.select_related("supply_point__address__street", "supply_point__address__street_number")
    for reading in readings:
        point = reading.supply_point
        if point is not None:
            points.setdefault(point.pk if point.pk is not None else id(point), point)
    if points:
        return [points[key] for key in sorted(points, key=lambda k: (not isinstance(k, int), k if isinstance(k, int) else 0))]
    default = invoice.contract.supply_point_default if invoice.contract else None
    return [default] if default else []

def _natural_key(value):
    digits = "".join(ch for ch in value if ch.isdigit())
    return (int(digits) if digits else 0, value)

def _render_supply_point_group(entries, with_units):
    """
    entries: [(carrer, número, [unitats])]. Un sol cop el carrer, els números separats per comes, i les unitats (escala/pis/porta) entre parèntesis darrere del seu número.
    """
    streets = {}
    for street, number, units in entries:
        streets.setdefault(street, {}).setdefault(number, []).extend(units)
    texts = []
    for street, numbers in streets.items():
        labels = []
        for number in sorted(numbers, key=_natural_key):
            units = sorted(set(numbers[number]), key=_natural_key) if with_units else []
            if units:
                labels.append(f"{number} ({','.join(units)})".strip() if number else ",".join(units))
            elif number:
                labels.append(number)
        texts.append(f"{street} {', '.join(labels)}".strip())
    return "; ".join(texts)

def _fit_supply_points(supply_points, budget):
    """
    Diversos punts de subministrament (p. ex. una comunitat de veïns) en poc espai:
    "AV PAISOS CATALANS 1 (1B,2B), 24, 26". Si no hi caben, per ordre: es treuen les unitats,
    es treu el codi postal i, per últim, es llisten només els primers amb "(+N)" al final.
    Els punts sense adreça hi surten pel seu nom (o token), perquè cap punt no desaparegui.
    """
    entries = []
    addresses = []
    for point in supply_points:
        address = point.address
        if not address:
            name = " ".join(str(point.name or point.token or "").split())
            if name:
                entries.append((name, "", []))
            continue
        addresses.append(address)
        unit = " ".join(filter(None, [
            address.building, address.stair, "-".join(filter(None, [address.floor, address.door])),
        ]))
        number = str(address.street_number) if address.street_number else ""
        entries.append((" ".join(str(address.street).split()), number, [unit] if unit else []))
    entries.sort(key=lambda e: (e[0], _natural_key(e[1])))
    postal_codes = {a.postal_code for a in addresses if a.postal_code}
    postal_code = next(iter(postal_codes)) if len(postal_codes) == 1 else None

    for with_units in (True, False):
        text = _render_supply_point_group(entries, with_units)
        if postal_code and len(text) + 1 + len(postal_code) <= budget:
            return f"{text} {postal_code}"
        if len(text) <= budget:
            return text
    for shown in range(len(entries) - 1, 0, -1):
        text = f"{_render_supply_point_group(entries[:shown], False)} (+{len(entries) - shown})"
        if len(text) <= budget:
            return text
    text = _render_supply_point_group(entries, False)
    return text[:max(budget - len(SEPA_ELLIPSIS), 0)].rstrip() + SEPA_ELLIPSIS

def append_sepa_invoice_detail(concept, invoice, language="ca", concept_fields=None):
    """
    Afegeix al concepte el detall de la factura: import, consum i punt de subministrament.
    (El número de contracte i el de factura ja hi són al prefix.) Els camps buits s'ometen.
    El punt de subministrament té prioritat sobre el codi postal i s'adapta al que queda dels
    140 caràcters de l'esquema SEPA (vegeu `_fit_supply_point`).
    """
    amount_label, consumption_label, supply_point_label = _SEPA_DETAIL_LABELS.get(
        language, _SEPA_DETAIL_LABELS_DEFAULT
    )
    fields = normalize_concept_fields(concept_fields)
    parts = [concept]
    if "amount" in fields and invoice.total_final is not None:
        parts.append(f"{amount_label} {invoice.total_final:.2f}EUR")
    consumption = invoice.consumption if invoice.consumption is not None else invoice.real_consumption
    if "consumption" in fields and consumption is not None:
        parts.append(f"{consumption_label} {consumption:g}m3")
    head = " ".join(parts)

    supply_points = _invoice_supply_points(invoice) if "supply_point" in fields else []
    if supply_points:
        prefix = f"{head} {supply_point_label} "
        budget = SEPA_USTRD_MAX_LENGTH - len(prefix)
        if len(supply_points) > 1:
            detail = _fit_supply_points(supply_points, budget)
        else:
            supply_point = supply_points[0]
            detail = _fit_supply_point(supply_point.address, supply_point.name or supply_point.token, budget)
        if detail:
            head = prefix + detail
    return head[:SEPA_USTRD_MAX_LENGTH].rstrip()

def build_payment_sepa_concept(payment, language, origin_water, is_return=False, concept_fields=None):
    """
    Concepte (RmtInf/Ustrd) del rebut d'un pagament. El fa servir tant la generació del fitxer
    com la previsualització, perquè mostrin exactament el mateix.
    """
    # Sense factura ni compromís, el concepte no es pot quedar amb el del pagament anterior.
    title = payment.token or ""
    invoice_label = "FRA" if language in ("ca", "es") else "INV"
    if payment.commitment_deposit:
        if language == "ca":
            title = f"COMPROMÍS DE PAGAMENT {payment.commitment_deposit.token}"
        elif language == "es":
            title = f"COMPROMISO DE PAGAMENTO {payment.commitment_deposit.token}"
        else:
            title = f"PAYMENT COMMITMENT {payment.commitment_deposit.token}"
        # Pagament agrupat: el compromís cobra diverses factures alhora.
        commitment_invoice_numbers = payment.commitment_deposit.invoices.exclude(
            serie_final__isnull=True
        ).order_by("serie_final").values_list("serie_final", flat=True)
        title = build_sepa_concept(title, list(commitment_invoice_numbers), invoice_label)
    if payment.invoice:
        title = payment.invoice.serie_final or title
        if payment.invoice.contract and origin_water is not None and payment.invoice.origin == origin_water:
            fields = normalize_concept_fields(concept_fields)
            water = {"ca": "AIGUA", "es": "AGUA"}.get(language, "WATER")
            contract_word = {"ca": "CONTRACTE", "es": "CONTRATO"}.get(language, "CONTRACT")
            title = f"{water} {contract_word} {payment.invoice.contract.token}" if "contract" in fields else water
            if "invoice" in fields:
                title = build_sepa_concept(title, [payment.invoice.serie_final], invoice_label)
            title = append_sepa_invoice_detail(title, payment.invoice, language, concept_fields)
    if is_return:
        title = f"{_('Return xml msg')} {payment.contract.token if payment.contract else payment.person.token if payment.person else payment.token}"
        if payment.invoice:
            title = build_sepa_concept(title, [payment.invoice.serie_final], invoice_label)
    return title

def get_sepa_signature_date(payment):
    """
    Returns the SEPA signature date for a payment.
    The logic follows: contract -> payment -> sepa_document -> updated_at/created_at
    Fallback: contract -> payment -> IBAN -> updated_at/created_at
    """
    try:
        # Get contract from payment (either directly or via commitment_deposit)
        contract = getattr(payment, 'contract', None)
        if not contract and hasattr(payment, 'commitment_deposit') and payment.commitment_deposit:
            contract = payment.commitment_deposit.contract
        
        if contract and contract.payment:
            # Priority 1: sepa_document in contract.payment
            if hasattr(contract.payment, 'sepa_document'):
                sepa_doc = contract.payment.sepa_document
                if sepa_doc:
                    sig_date = sepa_doc.updated_at or sepa_doc.created_at
                    if sig_date:
                        return sig_date.strftime("%Y-%m-%d")

            # Priority 2: IBAN object in contract.payment
            if hasattr(contract.payment, 'IBAN') and contract.payment.IBAN:
                iban_obj = contract.payment.IBAN
                sig_date = getattr(iban_obj, 'updated_at', None) or getattr(iban_obj, 'created_at', None)
                if sig_date:
                    return sig_date.strftime("%Y-%m-%d")

    except Exception as e:
        # Silently fail and return None to use fallback logic
        pass
    return None

def generate_xml(self, document, document_data, bank_instance):
        root = ET.Element("Document", {
            "xmlns": "urn:iso:std:iso:20022:tech:xsd:pain.008.001.02",
            "xmlns:xsi": "http://www.w3.org/2001/XMLSchema-instance"
        })
        date_time = (datetime.now() + timedelta(days=1)).strftime('%Y%m%d%H%M%S') 
        exploitation = Exploitation.objects.filter(is_active=True).first()
        
        if (exploitation.company.company_banks.count() == 0):
            raise Exception("Company has no banks")

        bank = bank_instance
        cstmrCdtTrfInitn = ET.SubElement(root, "CstmrDrctDbtInitn")
        grpHdr = ET.SubElement(cstmrCdtTrfInitn, "GrpHdr")

        #TODO: If there's more than one exploitation in the payments document, fix the conflict
        #Get the existing exploitation company CIF for the moment
        uuid_str = str(uuid.uuid4())
        unique_value = "".join(
                str((int(c, 16) % 10) + 1) if c in "0123456789abcdef" else c
                for c in uuid_str
            )[:10]

        from billing.views.sepa_payment_document_generate_view import calculate_control_code
        ident = "ES" + calculate_control_code(exploitation.company.vat) + '001' + exploitation.company.vat
        ident_msg = f"{exploitation.company.vat}{datetime.now().strftime('%Y%m%d')}{unique_value}"
        
        document.msgId = ident_msg
        document.save()
        ET.SubElement(grpHdr, "MsgId").text = ident_msg
        ET.SubElement(grpHdr, "CreDtTm").text = datetime.now().strftime("%Y-%m-%dT%H:%M:%S:%f")[:-4]
        
        total_transactions = sum(len(line.payments.all()) for line in document.lines.all())
        ET.SubElement(grpHdr, "NbOfTxs").text = str(total_transactions)

        total_amount = sum(data['amount'] for iban, customers in document_data.items() for customer_token, data in customers.items())
        ET.SubElement(grpHdr, "CtrlSum").text = f"{total_amount:.2f}"

        #InitgPty
        initg_pty = ET.SubElement(grpHdr, "InitgPty")
        ET.SubElement(initg_pty, "Nm").text = exploitation.company.alias
        initg_id = ET.SubElement(initg_pty, "Id")
        initg_prvt_id = ET.SubElement(initg_id, "PrvtId")
        initg_other = ET.SubElement(initg_prvt_id, "Othr")
        ET.SubElement(initg_other, "Id").text = bank.sepa_cred_identifier
        initg_schmenm =ET.SubElement(initg_other, "SchmeNm")
        ET.SubElement(initg_schmenm, "Prtry").text = "SEPA"
        ET.SubElement(initg_other, "Issr").text = "ISO"
        #END GrpHdr
        
        #PmtInf
        #PmtInfId
        pmtInf = ET.SubElement(cstmrCdtTrfInitn, "PmtInf")
        ET.SubElement(pmtInf, "PmtInfId").text = ident[:25]
        ET.SubElement(pmtInf, "PmtMtd").text = "DD"
        ET.SubElement(pmtInf, "NbOfTxs").text = str(total_transactions)
        ET.SubElement(pmtInf, "CtrlSum").text = f"{total_amount:.2f}"

        pmtTpInf = ET.SubElement(pmtInf, "PmtTpInf")
        svcLvl = ET.SubElement(pmtTpInf, "SvcLvl")
        ET.SubElement(svcLvl, "Cd").text = "SEPA"  
        lclinstrm = ET.SubElement(pmtTpInf, "LclInstrm")
        ET.SubElement(lclinstrm, "Cd").text = "CORE"
        ET.SubElement(pmtTpInf, "SeqTp").text = "RCUR"
        #END PmtInfId

        ET.SubElement(pmtInf, "ReqdColltnDt").text = date_time
        cdtr = ET.SubElement(pmtInf, "Cdtr")
        ET.SubElement(cdtr, "Nm").text = exploitation.company.alias
        
        """ pstlAdr = ET.SubElement(cdtr, "PstlAdr")
        ET.SubElement(pstlAdr, "Ctry").text = "ES"
        ET.SubElement(pstlAdr, "AdrLine").text = f"{exploitation.company.address}, {exploitation.company.location}" """

        cdtr_acct = ET.SubElement(pmtInf, "CdtrAcct")
        cdtr_acct_id = ET.SubElement(cdtr_acct, "Id")
        ET.SubElement(cdtr_acct_id, "IBAN").text = bank.iban

        cdtr_agt = ET.SubElement(pmtInf, "CdtrAgt")
        fin_instn_id = ET.SubElement(cdtr_agt, "FinInstnId")
        ET.SubElement(fin_instn_id, "BIC").text = bank.swift

        chrg_br = ET.SubElement(pmtInf, "ChrgBr")
        chrg_br.text = "SLEV"

        cdtr_schme_id = ET.SubElement(pmtInf, "CdtrSchmeId")
        id_element = ET.SubElement(cdtr_schme_id, "Id")
        prvt_id = ET.SubElement(id_element, "PrvtId")
        othr = ET.SubElement(prvt_id, "Othr")
        ET.SubElement(othr, "Id").text = bank.sepa_cred_identifier
        schmeNm = ET.SubElement(othr, "SchmeNm")
        ET.SubElement(schmeNm, "Prtry").text = "SEPA"
        
        ident=0
        for iban, customers in document_data.items():
            for customer_token, data in customers.items():
                ident += 1
                drct_dbt_tx_inf = ET.SubElement(pmtInf, "DrctDbtTxInf")
                pmtId = ET.SubElement(drct_dbt_tx_inf, "PmtId")
                end_to_end_id = f"{date_time}_{customer_token}_{unique_value}"
                ET.SubElement(pmtId, "InstrId").text = end_to_end_id
                ET.SubElement(pmtId, "EndToEndId").text = end_to_end_id

                amount = Decimal(str(data["amount"]))
                instdAmt = ET.SubElement(
                    drct_dbt_tx_inf, "InstdAmt", {"Ccy": "EUR"}
                )
                instdAmt.text = f"{amount:.2f}"

                drct_dbt_tx = ET.SubElement(drct_dbt_tx_inf, "DrctDbtTx")
                mndt_rltd_inf = ET.SubElement(drct_dbt_tx, "MndtRltdInf")
                ET.SubElement(mndt_rltd_inf, "MndtId").text = customer_token
                
                # Get signature date from contract sepa document if possible
                from billing.models import Payment
                sig_date_str = None
                payment_id = data.get('payment_ids', [None])[0]
                if payment_id:
                    payment_item = Payment.objects.filter(id=payment_id).first()
                    if payment_item:
                        sig_date_str = get_sepa_signature_date(payment_item)
                
                if not sig_date_str:
                    sig_date_str = datetime.now().strftime("%Y-%m-%d")

                ET.SubElement(mndt_rltd_inf, "DtOfSgntr").text = sig_date_str

                dbtr = ET.SubElement(drct_dbt_tx_inf, "Dbtr")
                ET.SubElement(dbtr, "Nm").text = data["tax_name"]

                iban_country = data["iban"][:2].upper() if data.get("iban") else ""
                non_eea_sepa_countries = ['GB', 'CH', 'GI', 'JE', 'GG', 'IM', 'MC', 'SM', 'VA'] # removed AD for now
                
                if iban_country in non_eea_sepa_countries:
                    dbtr_adr = ET.SubElement(dbtr, "PstlAdr")
                    
                    country_code = data.get("country_code") or data.get("country") or iban_country
                    ET.SubElement(dbtr_adr, "Ctry").text = country_code[:2].upper()
                    
                    if data.get("postal_code"):
                        town = data.get("city") or data.get("location") or "Unknown"
                        ET.SubElement(dbtr_adr, "AdrLine").text = f"{data['postal_code'][:16]} {town[:35]}"
                        
                    # ET.SubElement(dbtr_adr, "TwnNm").text = town[:35]
                    
                    if data.get("address"):
                        ET.SubElement(dbtr_adr, "AdrLine").text = data["address"][:70]

                dbtr_acct = ET.SubElement(drct_dbt_tx_inf, "DbtrAcct")
                dbtr_acct_id = ET.SubElement(dbtr_acct, "Id")
                
                is_iban = data["iban"] and re.match(r'^[A-Z]{2}\d{2}[A-Z0-9]{11,30}$', data["iban"])
                if is_iban:
                    ET.SubElement(dbtr_acct_id, "IBAN").text = data["iban"]
                else:
                    othr = ET.SubElement(dbtr_acct_id, "Othr")
                    ET.SubElement(othr, "Id").text = data["iban"]

                #OPTIONAL?
                rmtInf = ET.SubElement(drct_dbt_tx_inf, "RmtInf")
                ET.SubElement(rmtInf, "Ustrd").text = f"FRA  {customer_token}"
                

        xml_string = ET.tostring(root, encoding='utf-8', xml_declaration=True).decode('utf-8')
        return xml_string
    

def generate_xml_payments(payments, bank_instance, send_date, is_return=False, concept_fields=None):
        if concept_fields is None:
            concept_fields = get_saved_concept_fields()

        def to_local_date(value):
            if not value:
                return None
            if isinstance(value, datetime):
                if timezone.is_aware(value):
                    value = timezone.localtime(value)
                return value.date()
            if isinstance(value, date):
                return value
            return None

        try:
            origin_reading_token = ConfigProject.objects.get(token='origin_reading_token').value
            payment = payments.first()
            today = timezone.localdate()
            send_date_strf = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
            is_unique = True
            
            if any(payment.invoice and payment.invoice.origin.token == origin_reading_token for payment in payments):
                is_unique = False
            if send_date:
                if isinstance(send_date, str):
                    send_date_obj = datetime.strptime(send_date, '%Y-%m-%d')
                else:
                    send_date_obj = send_date
                send_date_strf = send_date_obj.strftime('%Y-%m-%d')
            else:
                if payment.invoice:
                    send_at_date = to_local_date(payment.invoice.send_at)
                    if send_at_date and send_at_date >= today:
                        send_date_strf = send_at_date.strftime('%Y-%m-%d')
                    else:
                        due_date_date = to_local_date(payment.invoice.due_date)
                        if due_date_date and due_date_date >= today:
                            send_date_strf = due_date_date.strftime('%Y-%m-%d')
                elif payment.due_date and payment.due_date.date() >= today:
                    send_date_strf = payment.due_date.strftime('%Y-%m-%d')
            
        except Exception as e:
            print("error: ", e)
            if send_date:
                if isinstance(send_date, str):
                    send_date_obj = datetime.strptime(send_date, '%Y-%m-%d')
                else:
                    send_date_obj = send_date
                send_date_strf = send_date_obj.strftime('%Y-%m-%d')
            else:
                send_date_strf = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d') 
        print("send date string: ", send_date_strf)
        pain_type = "pain.008.001.02" if not is_return else "pain.001.001.03"
        root = ET.Element("Document", {
            "xmlns": f"urn:iso:std:iso:20022:tech:xsd:{pain_type}",
            "xmlns:xsi": "http://www.w3.org/2001/XMLSchema-instance"
        })
        exploitation = payments.first().invoice.exploitation if payments.first().invoice else payments.first().commitment_deposit.contract.supply_point_default.connection.exploitation if payments.first().commitment_deposit else payments.first().contract.supply_point_default.connection.exploitation if payments.first().contract and payments.first().contract.supply_point_default else None
        if not exploitation:
            exploitation = Exploitation.objects.filter(is_active=True).first()

        if not bank_instance:
            raise Exception("Company has no banks")

        # L'empresa emissora surt del compte amb que es remesa, no de
        # l'explotacio: hi ha explotacions que serveixen mes d'una empresa i
        # `exploitation.company` sempre en donaria la mateixa. Cada banc genera
        # el seu fitxer, per tant el banc es qui determina de manera coherent el
        # titular (Cdtr/Dbtr), el NIF i l'identificador de creditor del fitxer.
        company = bank_instance.company or (exploitation.company if exploitation else None)
        if not company:
            raise Exception("Company bank has no company")

        #company_address_ser = CompanySerializer(company).data
        company_address = None
        if company.address and company.address.street:
            company_address = f"{company.address.street.name}"
            if company.address.street_number:
                company_address = f"{company_address}, {str(company.address.street_number)}"

        bank = bank_instance
        cstmrCdtTrfInitn = ET.SubElement(root, "CstmrDrctDbtInitn") if not is_return else ET.SubElement(root, "CstmrCdtTrfInitn")
        grpHdr = ET.SubElement(cstmrCdtTrfInitn, "GrpHdr")

        from billing.views.sepa_payment_document_generate_view import calculate_control_code
        ident = "ES" + calculate_control_code(company.vat) + '001' + company.vat
        ident_msg = generate_payment_remittance_ident_msg(company.vat)
        
        ET.SubElement(grpHdr, "MsgId").text = ident_msg
        ET.SubElement(grpHdr, "CreDtTm").text = datetime.now().isoformat()
        
        total_transactions = len(payments)
        ET.SubElement(grpHdr, "NbOfTxs").text = str(total_transactions)

        # A les transferències de retorn els pagaments de factures negatives
        # porten l'import en negatiu: al client se li transfereix l'absolut.
        def get_amount(payment):
            amount = Decimal(str(payment.amount))
            return abs(amount) if is_return else amount

        total_amount = sum(get_amount(payment) for payment in payments)
        ET.SubElement(grpHdr, "CtrlSum").text = f"{total_amount:.2f}"

        #InitgPty
        initg_pty = ET.SubElement(grpHdr, "InitgPty")
        ET.SubElement(initg_pty, "Nm").text = company.alias
        initg_id = ET.SubElement(initg_pty, "Id")
        # A les transferències l'ordenant és l'empresa: s'identifica com a
        # organització (OrgId), no com a persona física.
        initg_party_id = ET.SubElement(initg_id, "PrvtId" if not is_return else "OrgId")
        initg_other = ET.SubElement(initg_party_id, "Othr")
        ET.SubElement(initg_other, "Id").text = bank.sepa_cred_identifier
        initg_schmenm =ET.SubElement(initg_other, "SchmeNm")
        ET.SubElement(initg_schmenm, "Prtry").text = "SEPA"
        ET.SubElement(initg_other, "Issr").text = "ISO"
        #END GrpHdr
        
        #PmtInf
        #PmtInfId
        pmtInf = ET.SubElement(cstmrCdtTrfInitn, "PmtInf")
        ET.SubElement(pmtInf, "PmtInfId").text = ident_msg #ident[:25]
        ET.SubElement(pmtInf, "PmtMtd").text = "DD" if not is_return else "TRF"
        ET.SubElement(pmtInf, "BtchBookg").text = "false"
        ET.SubElement(pmtInf, "NbOfTxs").text = str(total_transactions)
        ET.SubElement(pmtInf, "CtrlSum").text = f"{total_amount:.2f}"

        pmtTpInf = ET.SubElement(pmtInf, "PmtTpInf")
        svcLvl = ET.SubElement(pmtTpInf, "SvcLvl")
        ET.SubElement(svcLvl, "Cd").text = "SEPA"  
        # Les transferències SEPA no porten LclInstrm: "DIVI" és un codi de
        # propòsit (dividends) i no un instrument local.
        if not is_return:
            lclinstrm = ET.SubElement(pmtTpInf, "LclInstrm")
            ET.SubElement(lclinstrm, "Cd").text = "CORE"
        # ET.SubElement(pmtTpInf, "SeqTp").text = "OOFF" if is_unique else "RCUR"
        if not is_return:
            ET.SubElement(pmtTpInf, "SeqTp").text = "RCUR"
        #END PmtInfId

        if is_return:
            ET.SubElement(pmtInf, "ReqdExctnDt").text = send_date_strf
        else:
            ET.SubElement(pmtInf, "ReqdColltnDt").text = send_date_strf
        
        if not is_return:
            cdtr = ET.SubElement(pmtInf, "Cdtr")
            ET.SubElement(cdtr, "Nm").text = company.alias

            """ pstlAdr = ET.SubElement(cdtr, "PstlAdr")
            ET.SubElement(pstlAdr, "Ctry").text = "ES"
            ET.SubElement(pstlAdr, "AdrLine").text = company_address """

            cdtr_acct = ET.SubElement(pmtInf, "CdtrAcct")
            cdtr_acct_id = ET.SubElement(cdtr_acct, "Id")
            ET.SubElement(cdtr_acct_id, "IBAN").text = normalize_account_code(bank.iban)

            cdtr_agt = ET.SubElement(pmtInf, "CdtrAgt")
            fin_instn_id = ET.SubElement(cdtr_agt, "FinInstnId")
            ET.SubElement(fin_instn_id, "BIC").text = normalize_account_code(bank.swift)

            chrg_br = ET.SubElement(pmtInf, "ChrgBr")
            chrg_br.text = "SLEV"

            cdtr_schme_id = ET.SubElement(pmtInf, "CdtrSchmeId")
            id_element = ET.SubElement(cdtr_schme_id, "Id")
            prvt_id = ET.SubElement(id_element, "PrvtId")
            othr = ET.SubElement(prvt_id, "Othr")
            ET.SubElement(othr, "Id").text = bank.sepa_cred_identifier
            schmeNm = ET.SubElement(othr, "SchmeNm")
            ET.SubElement(schmeNm, "Prtry").text = "SEPA"
        else:
            dbtr = ET.SubElement(pmtInf, "Dbtr")
            ET.SubElement(dbtr, "Nm").text = company.alias
            
            dbtr_id = ET.SubElement(dbtr, "Id")
            org_id = ET.SubElement(dbtr_id, "OrgId")
            prvt_other = ET.SubElement(org_id, "Othr")
            ET.SubElement(prvt_other, "Id").text = company.vat
            schmeNm = ET.SubElement(prvt_other, "SchmeNm")
            ET.SubElement(schmeNm, "Prtry").text = "SEPA"
            
            dbtr_acct = ET.SubElement(pmtInf, "DbtrAcct")
            dbtr_acct_id = ET.SubElement(dbtr_acct, "Id")
            ET.SubElement(dbtr_acct_id, "IBAN").text = normalize_account_code(bank.iban)
            
            dbtr_agt = ET.SubElement(pmtInf, "DbtrAgt")
            fin_instn_id = ET.SubElement(dbtr_agt, "FinInstnId")
            ET.SubElement(fin_instn_id, "BIC").text = normalize_account_code(bank.swift)
            
            ET.SubElement(pmtInf, "ChrgBr").text = "SLEV"
            

        
        language = config('LANGUAGE', default="ca")
        origin_water = ProductOrigin.objects.get(token='aigua')
        
        # Track mandate ids already used. Same mandate id is allowed only if IBAN is the same.
        # If the same base mandate id appears with different IBANs, we assign a stable suffix per IBAN.
        mndt_id_to_iban = {}
        mndt_id_iban_to_assigned = {}
        mndt_id_suffix_counters = {}
        used_mndt_ids = set()
        
        ident=0
        for payment in payments:
            ident += 1
            customer_token = payment.payer_token_final if payment.payer_token_final else payment.customer_token_final
            customer_name = payment.payer_final if payment.payer_final else payment.customer_final
            customer_name = customer_name.replace("&", "N")
            address_final = payment.address_final
            location_final = payment.location_final
            payment_bank_final = payment.payment_bank
            if payment_bank_final is None:
                payment_bank_final = ""
            elif not isinstance(payment_bank_final, str):
                payment_bank_final = str(payment_bank_final)
            payment_bank_final = payment_bank_final.strip()
            bank_swift = payment.payment_swift
            
            """ payment_send_date = payment.invoice.send_at if payment.invoice and payment.invoice.send_at else payment.due_date if payment.due_date else payment.payment_date if payment.payment_date else datetime.now()
            
            send_date_aware = timezone.make_aware(send_date) if send_date else None
            # turn both dates to datetime.date to compare
            payment_send_date_date = payment_send_date.date() if isinstance(payment_send_date, datetime) else payment_send_date
            send_date_aware_date = send_date_aware.date() if isinstance(send_date_aware, datetime) else send_date_aware
            
            if not payment_send_date or (
                send_date_aware and payment_send_date_date < send_date_aware_date
            ):
                payment_send_date = send_date_aware """
            
            # PAYMENT SEND DATE IS NOT USED TO SEND PAYMENTS, BUT TO DECLARE WHEN SEPA IS SIGNED (WHOOPS)
            payment_send_date = send_date_strf
            
            title = build_payment_sepa_concept(payment, language, origin_water, is_return, concept_fields)
            
            if not bank_swift or len(bank_swift) == 0:
                inv_com = payment.invoice if payment.invoice else payment.commitment_deposit if payment.commitment_deposit else None
                if inv_com:
                    if inv_com.contract and inv_com.contract.payment and inv_com.contract.payment.IBAN:
                        if inv_com.contract.payment.IBAN.iban == payment_bank_final:
                            if inv_com.contract.payment.IBAN.swift:
                                bank_swift = inv_com.contract.payment.IBAN.swift
                            else:
                                bank_swift = None
            is_spanish_iban = payment_bank_final and payment_bank_final.startswith('ES')

            if is_spanish_iban and (not bank_swift or len(bank_swift) == 0):
                bank_token = payment_bank_final[4:8]
                
                try:
                    bank_swift = Bank.objects.get(token=bank_token).bic
                except Exception as e:
                    try:
                        bank_swift = Bank.objects.get(token=int(bank_token)).bic
                    except Exception as e:
                        bank_swift = None
            
            if not bank_swift and payment_bank_final:
                try:
                    schwifty_bank = SchwiftyIBAN(payment_bank_final)
                    bank_swift = str(schwifty_bank.bic)
                except Exception:
                    bank_swift = None

            # Un BIC incomplet (el catàleg i les factures antigues porten "BSAB") es completava a cegues
            # amb "ESMMXXX": si el registre oficial coneix l'entitat, es fa servir el seu BIC.
            if is_spanish_iban and bank_swift and len(bank_swift.strip()) not in (8, 11):
                bank_swift = get_spanish_bic(payment_bank_final[4:8]) or bank_swift
            
            if bank_swift and len(bank_swift) > 0:
                if is_spanish_iban:
                    if len(bank_swift) == 4:
                        bank_swift = f"{bank_swift}ESMMXXX"
                    elif len(bank_swift) == 6:
                        bank_swift = f"{bank_swift}MMXXX"
                    elif len(bank_swift) == 8:
                        bank_swift = f"{bank_swift}XXX"
                else:
                    if len(bank_swift) == 8:
                        bank_swift = f"{bank_swift}XXX"



            if bank_swift and len(bank_swift) > 0:
                bank_swift = bank_swift.upper()
            
            drct_dbt_tx_inf = ET.SubElement(pmtInf, "DrctDbtTxInf") if not is_return else ET.SubElement(pmtInf, "CdtTrfTxInf")
            
            pmtId = ET.SubElement(drct_dbt_tx_inf, "PmtId")
            end_to_end_id = f"{payment.token}-{ident}"
            if not is_return:
                ET.SubElement(pmtId, "InstrId").text = end_to_end_id
            ET.SubElement(pmtId, "EndToEndId").text = end_to_end_id

            amount = get_amount(payment)
            
            if not is_return:
                instAmt_parent = drct_dbt_tx_inf
            else:
                instAmt_parent = ET.SubElement(drct_dbt_tx_inf, "Amt")
            
            instdAmt = ET.SubElement(
                instAmt_parent, "InstdAmt", {"Ccy": "EUR"}
            )
            instdAmt.text = f"{amount:.2f}"

            debtor_iban = (payment_bank_final or "").strip().upper()

            if payment.contract and payment.contract.payment and payment.contract.payment.mandate_id:
                base_mndt_id = payment.contract.payment.mandate_id
            else:
                base_mndt_id = F"{customer_token}{payment.token}"

            mndt_id = base_mndt_id
            if base_mndt_id in mndt_id_to_iban:
                previous_iban = mndt_id_to_iban[base_mndt_id]
                if previous_iban != debtor_iban:
                    assigned = mndt_id_iban_to_assigned.get((base_mndt_id, debtor_iban))
                    if assigned:
                        mndt_id = assigned
                    else:
                        suffix = mndt_id_suffix_counters.get(base_mndt_id, 1)
                        mndt_id = f"{base_mndt_id}-{suffix}"
                        while mndt_id in used_mndt_ids:
                            suffix += 1
                            mndt_id = f"{base_mndt_id}-{suffix}"
                        mndt_id_suffix_counters[base_mndt_id] = suffix + 1
                        mndt_id_iban_to_assigned[(base_mndt_id, debtor_iban)] = mndt_id
            else:
                mndt_id_to_iban[base_mndt_id] = debtor_iban

            used_mndt_ids.add(mndt_id)
            if not is_return:
                drct_dbt_tx = ET.SubElement(drct_dbt_tx_inf, "DrctDbtTx")
                mndt_rltd_inf = ET.SubElement(drct_dbt_tx, "MndtRltdInf")
                ET.SubElement(mndt_rltd_inf, "MndtId").text = mndt_id
            
                # Get signature date from contract sepa document if possible
                sig_date_str = get_sepa_signature_date(payment)
                if not sig_date_str:
                    # if payment_send_date is not a date but a string, try to convert it to a date
                    if isinstance(payment_send_date, str):
                        try:
                            payment_send_date = datetime.strptime(payment_send_date, "%Y-%m-%d")
                        except:
                            raise Exception("payment_send_date is not a valid date")
                    sig_date_str = payment_send_date.strftime("%Y-%m-%d")

                ET.SubElement(mndt_rltd_inf, "DtOfSgntr").text = sig_date_str
                ET.SubElement(mndt_rltd_inf, "AmdmntInd").text = "false"
            
            # DBTRAGT
            dbtr_agt = ET.SubElement(drct_dbt_tx_inf, "DbtrAgt") if not is_return else ET.SubElement(drct_dbt_tx_inf, "CdtrAgt")
            fin_instn_id = ET.SubElement(dbtr_agt, "FinInstnId")
            if bank_swift:
                ET.SubElement(fin_instn_id, "BIC").text = bank_swift

            # DBTR
            dbtr = ET.SubElement(drct_dbt_tx_inf, "Dbtr") if not is_return else ET.SubElement(drct_dbt_tx_inf, "Cdtr")
            ET.SubElement(dbtr, "Nm").text = customer_name
            
            if not is_return:
                iban_country = payment_bank_final[:2].upper() if payment_bank_final else ""
                non_eea_sepa_countries = ['GB', 'CH', 'GI', 'JE', 'GG', 'IM', 'MC', 'SM', 'VA', 'AD']

                if iban_country in non_eea_sepa_countries:
                    dbtr_adr = ET.SubElement(dbtr, "PstlAdr")
                    
                    country_code = iban_country
                    town = location_final or "Unknown"
                    zip_code = None
                    
                    if payment.invoice:
                        country_code = payment.invoice.country_final or iban_country
                        town = payment.invoice.city_final or payment.invoice.location_final or town
                        zip_code = payment.invoice.postal_code_final

                    ET.SubElement(dbtr_adr, "Ctry").text = country_code[:2].upper()
                    
                    if zip_code:
                        ET.SubElement(dbtr_adr, "AdrLine").text = f"{str(zip_code)[:16]} {str(town)[:35]}"
                            
                        # ET.SubElement(dbtr_adr, "TwnNm").text = str(town)[:35]
                    
                    if address_final:
                        ET.SubElement(dbtr_adr, "AdrLine").text = str(address_final)[:70]
                
                dbtr_id = ET.SubElement(dbtr, "Id")
                dbtr_ord_id = ET.SubElement(dbtr_id, "OrgId")
                dbtr_other = ET.SubElement(dbtr_ord_id, "Othr")
                ET.SubElement(dbtr_other, "Id").text = customer_token
                dbtr_schemNm = ET.SubElement(dbtr_other, "SchmeNm")
                ET.SubElement(dbtr_schemNm, "Prtry").text = "SEPA"
                ET.SubElement(dbtr_other, "Issr").text = "ISO"

            dbtr_acct = ET.SubElement(drct_dbt_tx_inf, "DbtrAcct") if not is_return else ET.SubElement(drct_dbt_tx_inf, "CdtrAcct")
            dbtr_acct_id = ET.SubElement(dbtr_acct, "Id")
            
            is_iban = payment_bank_final and re.match(r'^[A-Z]{2}\d{2}[A-Z0-9]{11,30}$', payment_bank_final)
            ET.SubElement(dbtr_acct_id, "IBAN").text = payment_bank_final
            
            # OTHR DOES NO WORK LIKE THIS
            # if is_iban:
            #     ET.SubElement(dbtr_acct_id, "IBAN").text = payment_bank_final
            # else:
            #     othr = ET.SubElement(dbtr_acct_id, "Othr")
            #     ET.SubElement(othr, "Id").text = payment_bank_final
            

            rmtInf = ET.SubElement(drct_dbt_tx_inf, "RmtInf")
            ET.SubElement(rmtInf, "Ustrd").text = title
                

        xml_string = ET.tostring(root, encoding='utf-8', xml_declaration=True).decode('utf-8')
        return xml_string, ident_msg