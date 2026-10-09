import os
from datetime import datetime
from io import BytesIO

from django.conf import settings
from django.template.loader import render_to_string
from django.utils import timezone
from xhtml2pdf import pisa

from coredata.models import ConfigProject
from coredata.serializers import AddressSerializer, PersonCardSerializer
from coredata.utils.template_utils import build_template_candidates
from documentmanager.utils.sign_certificate_service import sign_pdf
from contract.models import Contract, ContractRequestDocumentation, ContractRequestType, ContractUseType
from contract.serializers.contract_price_rate_serializer import ContractPriceRateSerializer
from contract.utils.contract_service import get_contract_tarifa_bop
from service.models import Company, Exploitation
from service.serializers.company_serializer import CompanySerializer
from service.utils.exploitation_logo import exploitation_logo_path
from service.serializers.meter_serializer import MeterSerializer


class ContractPdfGenerationError(Exception):
    pass


def format_date_to_catalan_words(date_value):
    if not date_value:
        return ""

    if hasattr(date_value, "date"):
        pass
    elif isinstance(date_value, str):
        try:
            date_value = datetime.fromisoformat(date_value.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            return ""
    else:
        return ""

    day = date_value.day
    month = date_value.month
    year = date_value.year

    mesos = {
        1: "gener",
        2: "febrer",
        3: "març",
        4: "abril",
        5: "maig",
        6: "juny",
        7: "juliol",
        8: "agost",
        9: "setembre",
        10: "octubre",
        11: "novembre",
        12: "desembre",
    }

    month_name = mesos.get(month, "")
    if month_name in ["abril", "agost", "octubre"]:
        prep = "d'"
    else:
        prep = "de "

    return f"{day} {prep}{month_name} de {year}"


def format_date_to_string(date_value):
    if not date_value:
        return None

    if hasattr(date_value, "strftime"):
        return date_value.strftime("%d/%m/%Y")
    if isinstance(date_value, str):
        try:
            dt = datetime.fromisoformat(date_value.replace("Z", "+00:00"))
            return dt.strftime("%d/%m/%Y")
        except (ValueError, AttributeError):
            return None

    return None


def get_contract_pdf_filename(instance):
    token = (instance.token or str(instance.id)).replace("/", "")
    return f"{token}.pdf"


def generate_contract_pdf_bytes(instance, *, include_requested_at=False, request=None):
    """
    Genera el PDF del contracte en memòria (signatura digital de l'empresa inclosa).

    `instance` pot ser un `Contract` o un `ContractRequest`.
    """
    serializer_context = {"request": request} if request else {}

    company = None
    city = None
    domain_media = settings.DOMAIN_MEDIA if hasattr(settings, "DOMAIN_MEDIA") else ""

    exploitation = None
    if (
        instance.supply_point_default
        and instance.supply_point_default.connection
        and instance.supply_point_default.connection.exploitation
    ):
        exploitation = instance.supply_point_default.connection.exploitation

    exploitation_image = exploitation_logo_path(exploitation) if exploitation and exploitation.id else None

    if (
        instance.supply_point_default is not None
        and instance.supply_point_default.connection is not None
        and instance.supply_point_default.connection.exploitation is not None
        and instance.supply_point_default.connection.exploitation.company is not None
    ):
        company = CompanySerializer(
            instance.supply_point_default.connection.exploitation.company,
            context=serializer_context,
        ).data

    if (
        instance.supply_point_default is not None
        and instance.supply_point_default.address is not None
        and instance.supply_point_default.address.city is not None
    ):
        city = instance.supply_point_default.address.city.name

    if company is None:
        first_exploitation = Exploitation.objects.first()
        if first_exploitation and first_exploitation.company:
            company = CompanySerializer(
                first_exploitation.company, context=serializer_context
            ).data

    logo_db = company["logo"] if company else None
    logo = None
    if not logo_db:
        fallback_company = Company.objects.all().first()
        company = (
            CompanySerializer(fallback_company, context=serializer_context).data
            if fallback_company
            else None
        )
        logo_db = company["logo"] if company else None
    if logo_db:
        logo_db = f"uploads/{logo_db.split('uploads/')[1]}"
        if hasattr(settings, "DOMAIN_MEDIA") and settings.DOMAIN_MEDIA:
            logo = os.path.join(settings.DOMAIN_MEDIA, f"media/{logo_db}")
        else:
            logo = os.path.join(settings.MEDIA_ROOT, logo_db)

    holder = (
        PersonCardSerializer(instance.holder, context=serializer_context).data
        if instance.holder
        else None
    )
    representative = (
        PersonCardSerializer(
            instance.representatives.first().person, context=serializer_context
        ).data
        if instance.representatives.count() > 0
        else None
    )
    supply_address = (
        AddressSerializer(instance.supply_point_default.address).data
        if instance.supply_point_default and instance.supply_point_default.address
        else None
    )
    meter = (
        MeterSerializer(instance.supply_point_default.meter).data
        if instance.supply_point_default and instance.supply_point_default.meter
        else None
    )
    meter_installation_at = (
        format_date_to_string(meter["installation_at"])
        if meter and "installation_at" in meter
        else None
    )
    caliber = (
        int(float(meter["caliber"]["name"]))
        if meter
        and "caliber" in meter
        and meter["caliber"]
        and "name" in meter["caliber"]
        and meter["caliber"]["name"] != ""
        else None
    )
    cluster_nozzle = (
        instance.supply_point_default.cluster_nozzle
        if instance.supply_point_default and instance.supply_point_default.cluster_nozzle
        else None
    )
    cluster = cluster_nozzle.cluster if cluster_nozzle and cluster_nozzle.cluster else None
    clauses = []

    billing_address = None
    if instance and instance.address_billing:
        billing_address = instance.address_billing.address
    elif (
        instance.holder
        and instance.holder.addresses
        and instance.holder.addresses.count() > 0
    ):
        try:
            billing_address = instance.holder.addresses.get(is_billing=True).address
        except Exception:
            billing_address = instance.holder.addresses.first().address
    billing_address_serialized = (
        AddressSerializer(billing_address).data if billing_address else None
    )

    try:
        requested_meter_caliber = (
            instance.requested_meter_caliber if instance.requested_meter_caliber else None
        )
    except Exception:
        requested_meter_caliber = None

    caliber = (
        requested_meter_caliber.name if requested_meter_caliber and not caliber else caliber
    )

    data_now = datetime.now().strftime("%d/%m/%Y")
    dia_setmana_opcions = [
        "Dilluns",
        "Dimarts",
        "Dimecres",
        "Dijous",
        "Divendres",
        "Dissabte",
        "Diumenge",
    ]
    mesos_opcions_text = [
        "de gener",
        "de febrer",
        "de març",
        "d'abril",
        "de maig",
        "de juny",
        "de juliol",
        "d'agost",
        "de setembre",
        "d'octubre",
        "de novembre",
        "de desembre",
    ]
    dia_setmana_now = dia_setmana_opcions[datetime.now().weekday()]
    mes_now = mesos_opcions_text[datetime.now().month - 1]
    dia_now = datetime.now().strftime("%d")
    any_now = datetime.now().strftime("%Y")
    now_str_complete = f"{dia_setmana_now}, {dia_now} {mes_now} de {any_now}"

    requested_at = (
        format_date_to_string(instance.requested_at)
        if include_requested_at and hasattr(instance, "requested_at")
        else None
    )
    created_at = format_date_to_string(instance.created_at)
    created_at_catalan = format_date_to_catalan_words(instance.created_at)
    registration_date = (
        format_date_to_string(instance.registration_date)
        if hasattr(instance, "registration_date")
        else None
    )

    signed_image = f"{domain_media}/media/uploads/logo/{company['id']}/signed.jpg"

    if instance.clauses.exists():
        for clause in instance.clauses.all():
            clauses.append(clause)

    main_color = "#000000"
    try:
        main_color = ConfigProject.objects.get(token="invoice_main_color").value
    except ConfigProject.DoesNotExist:
        pass

    contract_date = registration_date or now_str_complete
    contract_date_inst = instance.registration_date if instance.registration_date else instance.created_at

    use_type_name = None
    if getattr(instance, "use_type", None):
        use_type_name = instance.use_type.name

    price_rates = ContractPriceRateSerializer(
        instance.price_rates.filter(is_active=True, price_rate__isnull=False)
        .select_related("price_rate", "price_rate__product")
        .order_by("price_rate__product__position", "id"),
        many=True,
        context=serializer_context,
    ).data

    contract_template = "contract_template.html"
    try:
        contract_template = ConfigProject.objects.get(token="contract_template").value
    except ConfigProject.DoesNotExist:
        pass

    contract_lang = getattr(instance, "language", None) or settings.LANGUAGE_CODE
    contract_template = build_template_candidates(contract_template, lang=contract_lang)

    tarifa_bop = get_contract_tarifa_bop(instance)

    documentation_texts = {}
    # Mateixa data que mostra el front al costat de cada document
    documentation_dates = {}
    if isinstance(instance, Contract):
        doc_qs = ContractRequestDocumentation.objects.filter(
            contract=instance
        ).select_related("type", "contract_type", "file")
    else:
        doc_qs = ContractRequestDocumentation.objects.filter(
            contract_request=instance
        ).select_related("type", "contract_type", "file")
    for doc in doc_qs:
        if doc.text:
            if doc.contract_type and doc.contract_type.token:
                doc_token = doc.contract_type.token
            elif doc.type and doc.type.token:
                doc_token = doc.type.token
            else:
                continue
            documentation_texts[doc_token] = doc.text
            doc_date = doc.created_at or (doc.file.date if doc.file else None)
            if isinstance(doc_date, datetime) and timezone.is_aware(doc_date):
                doc_date = timezone.localtime(doc_date)
            documentation_dates[doc_token] = format_date_to_string(doc_date)
    html_content = render_to_string(
        contract_template,
        {
            "clauses": clauses,
            "exploitation_image": exploitation_image,
            "logo": logo,
            "request": instance,
            "requested_at": requested_at,
            "created_at": created_at,
            "created_at_catalan": created_at_catalan,
            "registration_date": registration_date,
            "company": company,
            "city": city,
            "holder": holder,
            "main_color": main_color,
            "meter": meter,
            "meter_installation_at": meter_installation_at,
            "caliber": caliber,
            "cluster_nozzle": cluster_nozzle,
            "cluster": cluster,
            "supply_address": supply_address,
            "representative": representative,
            "billing_address": billing_address_serialized
            if billing_address_serialized
            else supply_address,
            "footer_text": company.get("invoice_footer_text")
            if company and company.get("invoice_footer_text")
            else None,
            "now_str_complete": now_str_complete,
            "data_now": data_now,
            "signed_image": signed_image,
            "data_protection_law_text": company.get("data_protection_law_text")
            if company
            else None,
            "documentation_texts": documentation_texts,
            "documentation_dates": documentation_dates,
            "tarifa_bop": tarifa_bop,
            "use_type_name": use_type_name,
            "price_rates": price_rates,
            "contract_date": contract_date,
            "contract_date_inst": contract_date_inst,
            "variables": instance.variables.all(),
        },
    )
    pdf_buffer = BytesIO()
    pisa_status = pisa.CreatePDF(html_content, dest=pdf_buffer)
    if pisa_status.err:
        raise ContractPdfGenerationError("PDF generation failed")

    signed_pdf_buffer = sign_pdf(pdf_buffer, company, "CONTRACTE", "CONTRACTE")
    return signed_pdf_buffer.getvalue()



def contract_change_use_type_communication_pdf(instance_id, use_type_id, contract_type_id, request=None):
    try:
        serializer_context = {"request": request} if request else {}
        print("instance_id: ", instance_id)
        print("use_type_id: ", use_type_id)
        print("contract_type_id: ", contract_type_id)
        try:
            contract = Contract.objects.get(id=instance_id)
        except:
            raise Exception("Contract not found")
        try:
            use_type = ContractUseType.objects.get(id=use_type_id)
        except:
            use_type = None
        try:
            contract_type = ContractRequestType.objects.get(id=contract_type_id)
        except:
            contract_type = None
        
        today = datetime.now()
        
        billing_address = None
        if contract and contract.address_billing:
            billing_address = contract.address_billing.address
        billing_address_serialized = (
            AddressSerializer(billing_address).data if billing_address else None
        )
        
        domain_media = settings.DOMAIN_MEDIA if hasattr(settings, "DOMAIN_MEDIA") else ""
        exploitation = None
        if (
            contract.supply_point_default
            and contract.supply_point_default.connection
            and contract.supply_point_default.connection.exploitation
        ):
            exploitation = contract.supply_point_default.connection.exploitation
        
        exploitation_image = exploitation_logo_path(exploitation) if exploitation and exploitation.id else None

        if (
            contract.supply_point_default is not None
            and contract.supply_point_default.connection is not None
            and contract.supply_point_default.connection.exploitation is not None
            and contract.supply_point_default.connection.exploitation.company is not None
        ):
            company = CompanySerializer(
                contract.supply_point_default.connection.exploitation.company,
                context=serializer_context,
            ).data

        if (
            contract.supply_point_default is not None
            and contract.supply_point_default.address is not None
            and contract.supply_point_default.address.city is not None
        ):
            city = contract.supply_point_default.address.city.name
        supply_address = (
            AddressSerializer(contract.supply_point_default.address).data
            if contract.supply_point_default and contract.supply_point_default.address
            else None
        )
        holder = (
            PersonCardSerializer(contract.holder, context=serializer_context).data
            if contract.holder
            else None
        )
        if company is None:
            first_exploitation = Exploitation.objects.first()
            if first_exploitation and first_exploitation.company:
                company = CompanySerializer(
                    first_exploitation.company, context=serializer_context
                ).data

        logo_db = company["logo"] if company else None
        logo = None
        if not logo_db:
            fallback_company = Company.objects.all().first()
            company = (
                CompanySerializer(fallback_company, context=serializer_context).data
                if fallback_company
                else None
            )
            logo_db = company["logo"] if company else None
        if logo_db:
            logo_db = f"uploads/{logo_db.split('uploads/')[1]}"
            if hasattr(settings, "DOMAIN_MEDIA") and settings.DOMAIN_MEDIA:
                logo = os.path.join(settings.DOMAIN_MEDIA, f"media/{logo_db}")
            else:
                logo = os.path.join(settings.MEDIA_ROOT, logo_db)

        signed_image = f"{domain_media}/media/uploads/logo/{company['id']}/signed.jpg"
        main_color = "#000000"
        try:
            main_color = ConfigProject.objects.get(token="invoice_main_color").value
        except ConfigProject.DoesNotExist:
            pass
        
        contract_template = "contract_use_change_template.html"
        contract_lang = getattr(contract, "language", None) or settings.LANGUAGE_CODE
        contract_template = build_template_candidates(contract_template, lang=contract_lang)
        
        html_content = render_to_string(
            contract_template,
            {
                "main_color": main_color,
                "contract": contract,
                "use_type": use_type,
                "contract_type": contract_type,
                "exploitation_image": exploitation_image,
                "signed_image": signed_image,
                "logo": logo,
                "holder": holder,
                "company": company,
                "billing_address": billing_address_serialized,
                "supply_address": supply_address,
                "today": today,
            },
        )
        pdf_buffer = BytesIO()
        pisa_status = pisa.CreatePDF(html_content, dest=pdf_buffer)
        if pisa_status.err:
            raise ContractPdfGenerationError("PDF generation failed")

        signed_pdf_buffer = sign_pdf(pdf_buffer, company, "CONTRACTE", "CONTRACTE")
        
        filename = contract.token.replace("/", "") + "_" + use_type.name + ".pdf"
        return signed_pdf_buffer.getvalue(), filename
    except Exception as e:
        raise e