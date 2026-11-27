"""Permís necessari per veure un document segons el tipus d'entitat a què pertany.

Un `Document` és d'un contracte, d'una factura, d'un mandat SEPA, d'una ordre... i qui el veu ha
de poder veure també aquella entitat: tenir `documentmanager.view_document` no n'hi ha prou, o
qualsevol usuari baixaria els documents bancaris o d'identitat de qualsevol altre mòdul.

El tipus és el camp `entity` (en majúscules). En alguns serveis `entity` és el token de
l'objecte (frau, incidència, ordre) i el tipus és al camp `field`; per això el segon mapa.

Un tipus que no és en cap mapa és NOMÉS per als superusuaris (es falla tancat): si surt un tipus
nou legítim, s'ha d'afegir aquí. `manage.py documents_entities_audit` llista els tipus existents i
quins encara no hi són.

Cada valor és una llista de permisos: n'hi ha prou amb tenir-ne un.
"""

from django.db.models import Q
from django.db.models.functions import Upper

ENTITY_PERMISSIONS = {
    # Contractes
    'CONTRACT': ('contract.view_contract', 'contract.view_contractrequest'),
    'CONTRACT_REQUEST': ('contract.view_contractrequest',),
    'CONTRACT_TERMINATION_REQUEST': ('contract.view_contractterminationrequest',),
    'BAIL': ('contract.view_bail',),
    'DOCUMENT_SIGN': ('documentmanager.view_documentsign', 'contract.view_contract'),
    # Facturació i cobraments
    'SEPA': ('billing.view_payment', 'contract.view_contract'),
    'REBUTS': ('billing.view_payment', 'billing.view_invoice', 'communication.view_communication'),
    'FACTURES': ('billing.view_invoice',),
    'INVOICE': ('billing.view_invoice',),
    'PAGAMENT_BANCARI': ('billing.view_payment',),
    'PAYMENT': ('billing.view_payment',),
    'JOINED_PAYMENT': ('billing.view_joinedpayment',),
    'PAYMENT_REMITTANCE': ('billing.view_paymentremittance',),
    'PAYMENT_REMITTANCE_RETURN': ('billing.view_paymentremittancereturn',),
    'COMMITMENT_DEPOSIT': ('billing.view_commitmentdeposit',),
    'INSOLVENCY_PROCESS': ('billing.view_insolvencyprocess',),
    'BILLER': ('billing.view_biller',),
    'BILLING': ('billing.view_billing',),
    'BILLING_MESSAGE': ('billing.view_billing',),
    'INVOICE_TEMPLATE': ('billing.view_invoicetemplate',),
    'TEMPLATES': ('billing.view_invoicetemplate', 'billing.view_billing'),
    'READING': ('billing.view_reading',),
    'READING_BATCH': ('billing.view_readingbatch',),
    'READING_BATCH_TEMPLATE': ('billing.view_readingbatchtemplate',),
    # Tarifes
    'BILLING_RANGE': ('pricing.view_billingrange',),
    'LINE_ITEM_TYPE': ('pricing.view_lineitemtype',),
    'PRICE_RATE': ('pricing.view_pricerate',),
    'PRODUCT': ('pricing.view_product',),
    # Comunicacions i reclamacions
    'COMMUNICATION': ('communication.view_communication',),
    'COMUNICACIO': ('communication.view_communication',),
    'COMMUNICATION_PROCESS': ('communication.view_communicationprocess',),
    'MESSAGE_TEMPLATE': ('communication.view_messagetemplate',),
    'CLAIM_REQUEST': ('claimrequest.view_claimrequest',),
    'VULNERABILITY': ('claimrequest.view_vulnerabilityrequest',),
    # Incidències, frau i ordres
    'INCIDENT': ('notification.view_incident',),
    'CALENDAR': ('notification.view_calendartask',),
    'FRAUD': ('fraud.view_fraud',),
    'ORDER': ('order.view_order',),
    'ORDRES': ('order.view_order',),
    'ORDER_REPORT': ('order.view_orderreport', 'order.view_order'),
    'ORDER_FORM_SUBMISSION': ('got.view_orderformsubmission', 'order.view_order'),
    'ORDER_FORM_SUBMISSION_PENDING': ('got.view_orderformsubmission', 'order.view_order'),
    'ORDER_TYPE': ('order.view_ordertype',),
    # Servei
    'METER': ('service.view_meter',),
    'ROUTE': ('service.view_route',),
    'CLUSTER': ('service.view_cluster',),
    'CONNECTION': ('service.view_connection',),
    'CONNECTION_REQUEST': ('service.view_connectionrequest',),
    'PROPERTY': ('service.view_property',),
    'SUPPLY_POINT': ('service.view_supplypoint',),
    'EXPLOITATION': ('service.view_exploitation',),
    # Persones, carrers i usuaris
    'PERSON': ('coredata.view_person',),
    'STREET': ('coredata.view_street',),
    'USER': ('auth.view_user',),
    'GROUP': ('auth.view_group',),
    # Verifactu
    'VERIFACTU_NOTIFICATION': ('verifactu.view_verifactunotification',),
    'VERIFACTU_INVOICE': ('verifactu.view_verifactuinvoice',),
}

# Tipus quan `entity` és el token de l'objecte i no un tipus conegut.
FIELD_PERMISSIONS = {
    'FRAUD': ('fraud.view_fraud',),
    'INCIDENT': ('notification.view_incident',),
    'ORDER': ('order.view_order',),
}


def _has_any(user, permissions):
    return any(user.has_perm(permission) for permission in permissions)


def viewable_documents(user, queryset):
    """Els documents de `queryset` que `user` pot veure, descarregar o esborrar."""
    if not user or not user.is_authenticated:
        return queryset.none()
    if user.is_superuser:
        return queryset

    entities = [entity for entity, permissions in ENTITY_PERMISSIONS.items() if _has_any(user, permissions)]
    fields = [field for field, permissions in FIELD_PERMISSIONS.items() if _has_any(user, permissions)]
    return queryset.annotate(_entity_upper=Upper('entity'), _field_upper=Upper('field')).filter(
        Q(_entity_upper__in=entities)
        | (~Q(_entity_upper__in=list(ENTITY_PERMISSIONS)) & Q(_field_upper__in=fields))
    )
