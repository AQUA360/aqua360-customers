import base64
import json
import os
import re
from django.conf import settings
from django.template.loader import render_to_string
from django.http import JsonResponse
import fitz
from rest_framework import status
from rest_framework.response import Response
from django.core.files.base import ContentFile
from django.utils.safestring import mark_safe
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext as _
from io import BytesIO
import numpy as np
from PIL import Image
from xhtml2pdf import pisa
from datetime import datetime
from reportlab.platypus import tables as reportlab_tables
from billing.templatetags.billing_filters import format_eu
from django.core.mail import send_mail, EmailMultiAlternatives
import http.client
from communication.models import Communication, CommunicationFile, CommunicationStatus, MessageType
from contract.serializers.contract_serializer import ContractSerializer
from coredata.models import ConfigProject, Person
from coredata.serializers import AddressSerializer, PersonAddressSerializer, PersonContractMinimalSerializer, PersonSerializer
from coredata.utils.name_utils import generate_token
from documentmanager.utils.sign_certificate_service import sign_pdf

from documentmanager.utils.main_utils import upload_document
from documentmanager.views import get_all_documents
from logger.models import LogCommunicationStatusChange
from service.models import CompanyConfig
from service.serializers.company_serializer import CompanySerializer
from service.utils.exploitation_logo import exploitation_logo_source

def get_uploaded_file_from_request(request, field_name='document'):
    """
    Funció helper per obtenir un fitxer pujat des d'una request de Django REST Framework.
    Intenta obtenir el fitxer de request.FILES primer (correcte), i si no existeix, de request.data (fallback).
    
    Args:
        request: Request object de Django REST Framework
        field_name: Nom del camp que conté el fitxer (default: 'document')
    
    Returns:
        UploadedFile o None: El fitxer pujat, o None si no existeix
    """
    uploaded_file = None
    if field_name in request.FILES:
        uploaded_file = request.FILES[field_name]
    elif field_name in request.data:
        file_data = request.data.get(field_name)
        # Handle both list and single file object
        if isinstance(file_data, list) and len(file_data) > 0:
            uploaded_file = file_data[0]
        elif hasattr(file_data, 'read'):  # It's a file-like object
            uploaded_file = file_data
    
    return uploaded_file


def upload_communication_document(uploaded_file, communication, is_letter=False):
    """
    Funció helper per pujar un document i crear un CommunicationFile vinculat a una comunicació.
    
    Args:
        uploaded_file: Fitxer pujat (des de request.FILES o request.data)
        communication: Instància de Communication
        is_letter: Boolean indicant si és una carta generada (default: False)
    
    Returns:
        CommunicationFile: Instància creada del CommunicationFile
    
    Raises:
        Exception: Si hi ha un error en pujar el document
    """
    service = settings.DOCUMENT_MANAGER_SERVICES.get("communication")
    document = upload_document(
        uploaded_file,
        'COMUNICACIO',
        'COMUNICACIO',
        communication.id,
        communication.token,
        '',
        service,
        uploaded_file.name if hasattr(uploaded_file, 'name') else 'document'
    )
    
    comm_file = CommunicationFile.objects.create(
        token=generate_token(CommunicationFile),
        communication=communication,
        file=document,
        is_active=True,
        is_letter=is_letter
    )
    
    return comm_file

def get_communication_file(id):
    letter_token = ConfigProject.objects.get(token='message_type_letter_token').value
    communication_file = CommunicationFile.objects.get(id=id)
    communication = communication_file.communication
    
    config_company = communication.company_config
    companies = config_company.company_configs.all()
    company_ins = companies.first() if len(companies) > 0 else None
    company = CompanySerializer(company_ins).data if company_ins else None
    # try:
    #   person = PersonSerializer(communication.person, context=None).data if communication.person else None
    # except:
    person = PersonContractMinimalSerializer(communication.person, context=None).data if communication.person else None
    
    now_date = datetime.now().date()
    com_values = get_com_values(person, communication, company)
    letter_msg = None
    try:
      letter_msg = communication.messages.get(type__token=letter_token)
    except:
      pass
      #process = communication.process
      #letter_msg = process.messages.get(type__token=letter_token)
    if not letter_msg:
      try:
        process = communication.process
        letter_msg = process.messages.get(type__token=letter_token)
      except:
        pass
    subject = letter_msg.subject if letter_msg else ""
    body = letter_msg.body if letter_msg else ""
    
    subject = refactor_text(subject, com_values)
    body = refactor_text(body, com_values)
    
    body = format_letter_body(body)
    
    logo_db = company.get('logo')
    logo = None
    domain_media = settings.DOMAIN_MEDIA if hasattr(settings, 'DOMAIN_MEDIA') else ''

    if logo_db:
        # netejem logo_db assegurant-nos que sempre arriba el mateix format, potser que arribi una url o un path que comenci per /media/
        logo_db = f'uploads/{logo_db.split("uploads/")[1]}'
        
        if domain_media:
            logo = os.path.join(domain_media, f'media/{logo_db}')
        else:
            # Fallback a MEDIA_ROOT si DOMAIN_MEDIA no està definit
            logo = os.path.join(settings.MEDIA_ROOT, logo_db)
    full_name_upper = person.get('full_name', '').upper() if person else ''
    contract = communication.contracts.first()
    contract_address = None
    exploitation_image = None
    
    main_color = "#074df0"
    secondary_color = "#ffffff"
    try:
        main_color = company_ins.invoice_main_color if company_ins.invoice_main_color else ConfigProject.objects.get(token='invoice_main_color').value
        secondary_color = company_ins.invoice_secondary_color if company_ins.invoice_secondary_color else ConfigProject.objects.get(token='invoice_secondary_color').value
    except:
        pass
    
    if contract:
      contract_address = str(contract.supply_point_default.address)
      
      if contract.supply_point_default.connection and contract.supply_point_default.connection.exploitation:
        exploitation_image = exploitation_logo_source(contract.supply_point_default.connection.exploitation)
    
    
    
    html_content = render_to_string(
      'basic_letter.html', 
      {
        'company': company,
        'exploitation_image': exploitation_image,
        'main_color': main_color,
        'secondary_color': secondary_color,
        'logo': logo,
        'person': person,
        'full_name_upper': full_name_upper,
        'address': communication.used_address,
        'subject': subject, 
        'body': body,
        'contract': contract,
        'contract_address': contract_address,
        'now_date': now_date,
        'readings': communication.readings.all(),
        })
    pdf_buffer = BytesIO()

    # Generate PDF from HTML
    pisa_status = pisa.CreatePDF(html_content, dest=pdf_buffer)
    if pisa_status.err:
        return JsonResponse({"error": "PDF generation failed"}, status=500)

    #SIGNATURE
    signed_pdf_buffer = sign_pdf(pdf_buffer, company, subject, 'COMMUNICATION')

    # Save PDF to `contract_file` field in ContractRequest instance
    pdf_filename = f"{communication_file.token}.pdf"
    
    service = settings.DOCUMENT_MANAGER_SERVICES.get("communication")
    document_file = upload_document(
      ContentFile(signed_pdf_buffer.getvalue(), name=pdf_filename), 
      'COMUNICACIO', 
      'COMUNICACIO', 
      communication.id, 
      communication.token, 
      '', 
      service, 
      pdf_filename)
    
    return document_file

def create_email_template(communication):
  try:
      email_token = ConfigProject.objects.get(token='message_type_email_token').value
      subject = communication.messages.filter(type__token=email_token).first().subject
      body = communication.messages.filter(type__token=email_token).first().body
      
      config_company = communication.company_config
      companies = config_company.company_configs.all()
      company_ins = companies.first() if len(companies) > 0 else None
      company = CompanySerializer(company_ins).data if company_ins else None
      
      logo_db = company.get('logo')
      logo = None
      domain_media = settings.DOMAIN_MEDIA if hasattr(settings, 'DOMAIN_MEDIA') else ''

      if logo_db:
          # netejem logo_db assegurant-nos que sempre arriba el mateix format, potser que arribi una url o un path que comenci per /media/
          logo_db = f'uploads/{logo_db.split("uploads/")[1]}'
          
          if domain_media:
              logo = os.path.join(domain_media, f'media/{logo_db}')
          else:
              # Fallback a MEDIA_ROOT si DOMAIN_MEDIA no està definit
              logo = os.path.join(settings.MEDIA_ROOT, logo_db)

      
      person = PersonSerializer(communication.person).data if communication.person else None
      now_date = datetime.now().date()
      
      com_values = get_com_values(person, communication, company)
      
      subject = refactor_text(subject, com_values)
      body = refactor_text(body, com_values)
      body = mark_safe(body.replace('\n', '<br>'))
      
      html_content = render_to_string(
          'basic_email.html',
          {
              'company': company,
              'person': communication.person,
              'address': communication.used_address,
              'subject': subject,
              'body': body,
              'now_date': now_date,
              'logo': logo,
          }
      )
      
      communication.email_html_content = html_content
      communication.save()
  except Exception as e:
    print(f"Error creating email template: {str(e)}")
    raise Exception(str(e))

def refactor_text(text, com_values):
  for key, value in com_values.items():
    text = text.replace(f'%{key}', str(value))
  # replace format tag markers like **BOLD** something **BOLD** to <b>something</b> or **ITALIC** smt **ITALIC** to <i>smt</i>
  text = re.sub(r'\*\*BOLD\*\*(.*?)\*\*BOLD\*\*', r'<b>\1</b>', text, flags=re.DOTALL)
  text = re.sub(r'\*\*ITALIC\*\*(.*?)\*\*ITALIC\*\*', r'<i>\1</i>', text, flags=re.DOTALL)
  text = re.sub(r'\*\*UNDERLINE\*\*(.*?)\*\*UNDERLINE\*\*', r'<u>\1</u>', text, flags=re.DOTALL)
  text = re.sub(r'\*\*ALIGN-RIGHT\*\*(.*?)\*\*ALIGN-RIGHT\*\*', r'<div style="text-align: right;">\1</div>', text, flags=re.DOTALL)
  text = re.sub(r'\*\*ALIGN-CENTER\*\*(.*?)\*\*ALIGN-CENTER\*\*', r'<div style="text-align: center;">\1</div>', text, flags=re.DOTALL)
  text = re.sub(r'\*\*ALIGN-LEFT\*\*(.*?)\*\*ALIGN-LEFT\*\*', r'<div style="text-align: left;">\1</div>', text, flags=re.DOTALL)
  text = re.sub(
    r'(\n*)\*\*OL\*\*[ \t]*\n?(.*?)\n?[ \t]*\*\*OL\*\*[ \t]*\n?',
    lambda match: _replace_marked_list(match, ordered=True),
    text,
    flags=re.DOTALL,
  )
  text = re.sub(
    r'(\n*)\*\*UL\*\*[ \t]*\n?(.*?)\n?[ \t]*\*\*UL\*\*[ \t]*\n?',
    lambda match: _replace_marked_list(match, ordered=False),
    text,
    flags=re.DOTALL,
  )
  return text

_LI_MARKER_RE = re.compile(r'\*\*LI\*\*(.*?)\*\*LI\*\*', re.DOTALL)
_TD = 'padding:0;margin:0;border:0;vertical-align:top;line-height:1.3;'


def _extract_list_items(content):
  marked_items = [item.strip() for item in _LI_MARKER_RE.findall(content or '') if item.strip()]
  if marked_items:
    return marked_items

  normalized = (content or '').replace('\r\n', '\n').replace('\r', '\n').strip('\n')
  items = []
  for line in normalized.split('\n'):
    stripped = line.strip()
    if not stripped:
      if items and items[-1] is not None:
        items.append(None)
      continue
    stripped = re.sub(r'^\d+\s*[\.\)\-]\s+', '', stripped)
    stripped = re.sub(r'^[-*•]\s+', '', stripped)
    items.append(stripped)
  return items


def _render_marked_list(content, ordered=True):
  items = _extract_list_items(content)
  if not items:
    return ''
  rows = []
  number = 0
  for item in items:
    if item is None:
      rows.append(f'<tr><td colspan="3" style="{_TD}height:8pt;font-size:1pt;">&nbsp;</td></tr>')
      continue
    number += 1
    marker = f'{number}.' if ordered else '•'
    rows.append(
      '<tr>'
      f'<td width="20" style="width:20pt;{_TD}">&nbsp;</td>'
      f'<td width="18" style="width:18pt;{_TD}">{marker}</td>'
      f'<td style="{_TD}text-align:left;">{item}</td>'
      '</tr>'
    )
  return (
    '<table class="letter-list" width="100%" cellpadding="0" cellspacing="0" border="0" '
    f'style="width:100%;border-collapse:collapse;margin:0;padding:0;">{"".join(rows)}</table>'
  )


def _replace_marked_list(match, ordered):
  list_html = _render_marked_list(match.group(2), ordered)
  if not list_html:
    return match.group(1) or ''
  preceding = match.group(1) or ''
  # Un sol return és la línia del marcador: la taula ja salta de línia, sense forat extra.
  # Si hi ha un return de més (línia en blanc), es conserva l'espai davant de la llista.
  extra_newlines = max(0, preceding.count('\n') - 1)
  if extra_newlines:
    return '\n\n&nbsp;\n\n' + list_html
  return list_html


def format_letter_body(body):
  if not body:
    return mark_safe('')

  normalized = body.replace('\r\n', '\n').replace('\r', '\n').strip()
  if not normalized:
    return mark_safe('')

  paragraphs = [p.strip() for p in re.split(r'\n\s*\n+', normalized) if p.strip()]
  html_paragraphs = []
  for paragraph in paragraphs:
    paragraph = paragraph.replace('\n', '<br>')
    html_paragraphs.append(f'<p>{paragraph}</p>')

  return mark_safe(''.join(html_paragraphs))

def get_com_values(person, communication, company):
    return {
        'person.token': person.get('token') if person else '',
        'person.name': person.get('full_name') if person else '',
        'person.address_complete': communication.used_address if communication.used_address else '',
        
        'company.name': company.get('name') if company else '',
        'company.phone': company.get('phone') if company else '',
        'company.email': communication.company_config_email.mail_send_user if communication.company_config_email and communication.company_config_email.mail_send_user else company.get('contact_email') if company and company.get('contact_email') else '',
        'company.address_complete': company.get('address_complete') if company else '',
        
        'contract.token': '\n'.join([contract.token for contract in communication.contracts.all()]) if communication.contracts.all() else [],
        'contract.supply_address': '\n'.join([str(contract.supply_point_default.address) for contract in communication.contracts.all()]) if communication.contracts.all() else [],
        'contract.persons': str(sum([contract.total_persons for contract in communication.contracts.all()])) if communication.contracts.all() else '',
        'contract.previous_daily_consumption': communication.contracts.first().consumption_stats.order_by('-year', '-period').first().daily_consumption if communication.contracts.first() and communication.contracts.first().consumption_stats.exists() and communication.contracts.first().consumption_stats.order_by('-year', '-period').first() else '',
        'contract.previous_period_consumption': communication.contracts.first().consumption_stats.filter(year=datetime.now().year-1, period__range=(datetime.now().month-1, datetime.now().month+1)).order_by('-year', '-period').first().daily_consumption if communication.contracts.first() and communication.contracts.first().consumption_stats.exists() and communication.contracts.first().consumption_stats.filter(year=datetime.now().year-1, period__range=(datetime.now().month-1, datetime.now().month+1)).order_by('-year', '-period').first() else '',
        
        'date.today': datetime.now().strftime('%d/%m/%y'),
        'communication.due_date': communication.due_date.strftime('%d/%m/%y') if communication.due_date else '',
        
        'invoice.issue_date': communication.invoices.first().issue_date.strftime('%d/%m/%y') if communication.invoices and communication.invoices.first() and communication.invoices.first().issue_date else '',
        'invoice.due_date': communication.invoices.first().due_date.strftime('%d/%m/%y') if communication.invoices and communication.invoices.first() and communication.invoices.first().due_date else '',
        'invoice.send_at': communication.invoices.first().send_at.strftime('%d/%m/%y') if communication.invoices and communication.invoices.first() and communication.invoices.first().send_at else '',
        'invoice.serie_final': '\n'.join([invoice.serie_final for invoice in communication.invoices.all()]) if communication.invoices.all() else [],
        'invoice.consumption': f"{format_eu((int(sum(invoice.consumption or 0 for invoice in communication.invoices.all()))),0)} m3" if communication.invoices.all() else '',
        'invoice.total': f"{format_eu(sum(invoice.left_to_pay or 0 for invoice in communication.invoices.all()))} €" if communication.invoices.all() else '',
        
        'reading.data': '\n'.join([
            (
                f"{_('Meter')} {reading.meter.code} - "
                f"{_('Reading')} {reading.reading_value} "
                f"{_('Reading date')}: {reading.reading_date.strftime('%d/%m/%y')} . "
                f"{_('Consumption')}: {reading.calculated_value} m3"
                f"{' - ' + _('Leak value') + ': ' + str(reading.leak_value) + ' m3' if reading.leak_value else ''}"
            )
            for reading in communication.readings.all()
        ]) if communication.readings.all() else '',
   
        'reading.meter_code': communication.readings.first().meter.code if communication.readings.first() and communication.readings.first().meter else '',
        'reading.reading_value': str(int(communication.readings.first().reading_value)) if communication.readings.first() and communication.readings.first().reading_value else '',
        'reading.reading_date': communication.readings.first().reading_date.strftime('%d/%m/%Y') if communication.readings.first() and communication.readings.first().reading_date else '',
        'reading.calculated_value': str(int(communication.readings.first().calculated_value)) if communication.readings.first() and communication.readings.first().calculated_value else '',
        'reading.leak_value': str(int(communication.readings.first().leak_value)) if communication.readings.first() and communication.readings.first().leak_value else '',
        'reading.previous_reading_value': str(int(communication.readings.first().previous_reading.reading_value)) if communication.readings.first() and communication.readings.first().previous_reading and communication.readings.first().previous_reading.reading_value else '',
        'reading.previous_reading_date': communication.readings.first().previous_reading.reading_date.strftime('%d/%m/%Y') if communication.readings.first() and communication.readings.first().previous_reading and communication.readings.first().previous_reading.reading_date else '',
    }

def handle_communication(comm, comm_types):
  print("inside handle communication")
  if 'email' in comm_types:
    send_electronic_mail(comm)
  if 'letter' in comm_types:
    pass
  if 'electronic_invoice' in comm_types:
    pass
  else:
    pass

def send_electronic_mail(comm):
  document_files = []
  status_sent = CommunicationStatus.objects.get(
      token=ConfigProject.objects.get(token='communication_status_sent_token').value
  )
  pending_status = CommunicationStatus.objects.get(is_default=True)
  try:
    rejected_token = ConfigProject.objects.get(token='communication_status_rejected_token').value
  except Exception as e:
    rejected_token = '-2'
  status_rejected = CommunicationStatus.objects.get(token=rejected_token)

  # Re-check status from DB to avoid double sending in concurrent task chains
  comm_db = Communication.objects.get(id=comm.id)
  if comm_db.status not in (pending_status, status_rejected):
    print(f"Skipping send for communication {comm_db.id}: status is not pending/rejected.")
    return
  comm = comm_db

  # `attach_to_email=False` exclou el fitxer del correu sense desvincular-lo de la
  # comunicació: el document es continua generant i arxivant al documentmanager.
  files = []
  if comm.always_attach:
    files = comm.files.all().filter(file__is_active=True, attach_to_email=True)
  else:
    files = comm.files.all().filter(file__is_active=True, is_letter=False, attach_to_email=True)

  file_ids = [file.file.id for file in files]
  document_files = get_all_documents(file_ids)

  comm_email = comm.used_email
  comm_config = comm.company_config
  type_instance = MessageType.objects.get(token=ConfigProject.objects.get(token='message_type_email_token').value)
  body = ''
  subject = ''
  try:
    # Preparant subjecte/cos i comprovant les dades mínimes per poder enviar. Qualsevol
    # error aquí (comm/process sense Message del tipus email, falta company config, etc.)
    # ha d'acabar marcant la comunicació com a rebutjada amb un motiu clar -- si no,
    # l'excepció es propaga sense capturar fins al bucle de send_communications_task,
    # que la ignora silenciosament i la comunicació es queda "Pendent" per sempre.
    try:
      subject = comm.messages.get(type=type_instance).subject
      body = comm.messages.get(type=type_instance).body
    except Exception:
      if comm.process:
        subject = comm.process.messages.get(type=type_instance).subject
        body = comm.process.messages.get(type=type_instance).body
      else:
        subject = ''
        body = ''

    companies = comm_config.company_configs.all() if comm_config else []
    company_ins = companies.first() if companies and len(companies) > 0 else None
    company = CompanySerializer(company_ins).data if company_ins else None
    person = PersonSerializer(comm.person).data if comm.person else None
    subject = refactor_text(subject, get_com_values(person, comm, company))

    if not comm_config:
      raise Exception("No company configuration found")

    if comm.company_config_email and comm.company_config_email.mail_send_user:
      from_email = comm.company_config_email.mail_send_user
    else:
      from_email = comm_config.company_config_emails.filter(is_default=True).first().mail_send_user
      if not from_email:
        from_email = comm_config.company_config_emails.first().mail_send_user

    if not from_email:
      try:
          from_email = comm.company_config_email.mail_send_mail if comm.company_config_email and comm.company_config_email.mail_send_mail else comm_config.company_config_emails.filter(is_default=True).first().mail_send_mail
      except Exception as e:
        print(f"Error getting from email: {str(e)}")

    if not comm_email:
      raise Exception("No receiver email address found")
    if not from_email:
      raise Exception("No sender email address found")
  except Exception as e:
    error_msg = f"Error preparing email: {str(e)}"
    print(error_msg)
    comm.rejection_reason = error_msg
    comm.status = status_rejected
    comm.save()
    return

  print(f"Attempting to send email from {from_email} to {comm_email}")

  try:
    parts = [e.strip() for e in str(comm_email).split(';')]
    comm_emails = [e for e in parts if e]
  except Exception as e:
    print(f"Error splitting emails: {str(e)}")
    comm_emails = [comm_email]

  try:
    email_backend = getattr(settings, "EMAIL_BACKEND", "")

    if email_backend == "msgraphbackend.MSGraphBackend":
      _send_via_msgraph(comm_emails, subject, comm.email_html_content, from_email, document_files)
    else:
      _send_via_smtp(comm_emails, subject, comm.email_html_content, from_email, document_files, comm_config, comm.company_config_email)

    try:
      LogCommunicationStatusChange.objects.create(
        object=comm,
        previous_status=comm.status,
        current_status=status_sent,
        user=comm.user
      )
    except Exception as e:
      print(f"Error logging communication status change: {str(e)}")

    comm.sent_at = timezone.now()
    comm.status = status_sent
    comm.save()
    print("Email sent successfully")

  except Exception as e:
    error_msg = f"Error sending email: {str(e)}"
    print(error_msg)
    print(f"[error debug] email_backend: {email_backend}")
    print(f"[error debug] comm_config: {comm_config}")
    print(f"[error debug] comm_emails: {comm_emails}")
    print(f"[error debug] subject: {subject}")
    print(f"[error debug] from_email: {from_email}")
    print(f"[error debug] document_files: {document_files}")
    print(f"[error debug] status_rejected: {status_rejected}")
    comm.rejection_reason = error_msg
    comm.status = status_rejected
    comm.save()
    
    

def _send_via_smtp(comm_emails, subject, html_content, from_email, document_files, comm_config, comm_config_email):
  smtp_server = comm_config.mail_send_smtp_server
  smtp_port = comm_config.mail_send_smtp_port
  smtp_user = comm_config_email.mail_send_mail if comm_config_email and comm_config_email.mail_send_mail else comm_config.company_config_emails.filter(is_default=True).first().mail_send_mail if comm_config.company_config_emails.filter(is_default=True).first() else comm_config.company_config_emails.first()
  smtp_password = getattr(settings, comm_config.token, None) if comm_config.token else settings.EMAIL_HOST_PASSWORD
  if not smtp_password:
    smtp_password = getattr(settings, "EMAIL_HOST_PASSWORD", "")
  use_tls = comm_config.use_TLS if comm_config.use_TLS is not None else getattr(settings, "EMAIL_USE_TLS", True)
  use_ssl = comm_config.use_SSL if comm_config.use_SSL is not None else getattr(settings, "EMAIL_USE_SSL", False)

  from django.core.mail.backends.smtp import EmailBackend
  backend = EmailBackend(
    host=smtp_server,
    port=smtp_port,
    username=smtp_user,
    password=smtp_password,
    use_tls=use_tls,
    use_ssl=use_ssl,
    fail_silently=False
  )

  msg = EmailMultiAlternatives(
      subject=subject,
      body='',
      from_email=from_email,
      to=comm_emails,
      connection=backend
  )

  if html_content:
      msg.attach_alternative(html_content, "text/html")

  if document_files:
    for file in document_files:
      msg.attach(file[0], file[1], 'application/pdf')

  msg.send()


def _send_via_msgraph(comm_emails, subject, html_content, from_email, document_files):
  msg = EmailMultiAlternatives(
      subject=subject,
      body='',
      from_email=from_email,
      to=comm_emails,
  )

  if html_content:
      msg.attach_alternative(html_content, "text/html")

  if document_files:
    for file in document_files:
      msg.attach(file[0], file[1], 'application/pdf')

  msg.send(fail_silently=False)

def _get_page_content_rect(page, padding=4):
  rect = None

  for block in page.get_text("blocks"):
    block_rect = fitz.Rect(block[:4])
    if block_rect.is_empty:
      continue
    rect = block_rect if rect is None else rect | block_rect

  for info in page.get_image_info():
    block_rect = fitz.Rect(info["bbox"])
    if not block_rect.is_empty:
      rect = block_rect if rect is None else rect | block_rect

  for drawing in page.get_drawings():
    block_rect = fitz.Rect(drawing["rect"])
    if not block_rect.is_empty:
      rect = block_rect if rect is None else rect | block_rect

  if rect is None or rect.is_empty:
    return page.rect

  rect = rect + (-padding, -padding, padding, padding)
  return rect & page.rect


def _trim_whitespace(image, threshold=252, padding=4):
  arr = np.asarray(image.convert("RGB"))
  mask = np.any(arr < threshold, axis=2)
  if not mask.any():
    return image

  rows = np.where(mask.any(axis=1))[0]
  cols = np.where(mask.any(axis=0))[0]
  top = max(0, int(rows[0]) - padding)
  bottom = min(image.height, int(rows[-1]) + 1 + padding)
  left = max(0, int(cols[0]) - padding)
  right = min(image.width, int(cols[-1]) + 1 + padding)
  return image.crop((left, top, right, bottom))


def _render_page_to_image(page, matrix):
  clip = _get_page_content_rect(page)
  pixmap = page.get_pixmap(matrix=matrix, clip=clip)
  image = Image.frombytes("RGB", [pixmap.width, pixmap.height], pixmap.samples)
  return _trim_whitespace(image)


def _is_row_heights_mismatch_error(error):
  match = re.search(r"data error - (\d+) rows in data but (\d+) row heights", str(error))
  if not match:
    return False
  return int(match.group(1)) > int(match.group(2))


def _create_pdf_with_table_rowheight_retry(html_content, pdf_buffer):
  try:
    return pisa.CreatePDF(html_content, dest=pdf_buffer)
  except ValueError as error:
    if not _is_row_heights_mismatch_error(error):
      raise

    original_table_init = reportlab_tables.Table.__init__

    def patched_table_init(self, data, colWidths=None, rowHeights=None, *args, **kwargs):
      if rowHeights is not None and data is not None:
        row_count = len(data)
        if len(rowHeights) < row_count:
          rowHeights = list(rowHeights) + [None] * (row_count - len(rowHeights))
      return original_table_init(self, data, colWidths=colWidths, rowHeights=rowHeights, *args, **kwargs)

    reportlab_tables.Table.__init__ = patched_table_init
    try:
      pdf_buffer.seek(0)
      pdf_buffer.truncate(0)
      return pisa.CreatePDF(html_content, dest=pdf_buffer)
    finally:
      reportlab_tables.Table.__init__ = original_table_init


def html_to_png_base64(html_content, zoom=2):
  pdf_buffer = BytesIO()
  pisa_status = _create_pdf_with_table_rowheight_retry(html_content, pdf_buffer)
  if pisa_status.err:
    raise ValueError("PDF generation failed")

  pdf_document = fitz.open(stream=pdf_buffer.getvalue(), filetype="pdf")
  if pdf_document.page_count == 0:
    pdf_document.close()
    raise ValueError("PDF has no pages")

  matrix = fitz.Matrix(zoom, zoom)
  page_images = [_render_page_to_image(page, matrix) for page in pdf_document]
  pdf_document.close()

  if len(page_images) == 1:
    combined = page_images[0]
  else:
    total_height = sum(img.height for img in page_images)
    max_width = max(img.width for img in page_images)
    combined = Image.new("RGB", (max_width, total_height), "white")
    y_offset = 0
    for img in page_images:
      combined.paste(img, (0, y_offset))
      y_offset += img.height

  png_buffer = BytesIO()
  combined.save(png_buffer, format="PNG")
  return base64.b64encode(png_buffer.getvalue()).decode("utf-8")


def get_email_image_preview(message, comm_id=None):
  body = message.get('body')
  subject = message.get('subject')
  person_id = message.get('person_id')
  
  company_config_id = message.get('company_config_id')
  existing_html = None
  
  if comm_id:
    comm = Communication.objects.get(id=comm_id)
    if comm.email_html_content:
      existing_html = comm.email_html_content
    person = comm.person
    person = PersonSerializer(person).data if person else None
    company = comm.company_config.company_configs.first()
    company = CompanySerializer(company).data if company else None
    body = refactor_text(body, get_com_values(person, comm, company))
    subject = refactor_text(subject, get_com_values(person, comm, company))
  
  else:
    person = Person.objects.get(id=person_id)
    person = PersonSerializer(person).data if person else None
    company_config = CompanyConfig.objects.get(id=company_config_id)
    company = company_config.company_configs.first()
    company = CompanySerializer(company).data if company else None
  
  logo_db = company.get('logo')
  logo = None
  domain_media = settings.DOMAIN_MEDIA if hasattr(settings, 'DOMAIN_MEDIA') else ''
  if logo_db:
    logo_db = f'uploads/{logo_db.split("uploads/")[1]}'
    if domain_media:
      logo = os.path.join(domain_media, f'media/{logo_db}')
    else:
      logo = os.path.join(settings.MEDIA_ROOT, logo_db)
  
  body = mark_safe(body.replace('\n', '<br>'))
  subject = mark_safe(subject.replace('\n', '<br>'))
  now_date = datetime.now().date()
  if existing_html:
    html_content = existing_html
  else:
    html_content = render_to_string(
        'basic_email.html',
        {
            'company': company,
            'person': person,
            'address': "",
            'subject': subject,
            'body': body,
            'now_date': now_date,
            'logo': logo,
        }
    )
  try:
    image_base64 = html_to_png_base64(html_content)
  except Exception as e:
    print(f"Error generating image: {e}")
    
    # Si falla és probable que sigui per la plantilla anterior a aquest canvi
    html_content = render_to_string(
        'basic_email.html',
        {
            'company': company,
            'person': person,
            'address': "",
            'subject': subject,
            'body': body,
            'now_date': now_date,
            'logo': logo,
        }
    )
    image_base64 = html_to_png_base64(html_content)
    

  return Response(
    {"image_base64": image_base64, "content_type": "image/png"},
    status=status.HTTP_200_OK,
  )