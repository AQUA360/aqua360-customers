from datetime import timedelta
import uuid
from django.conf import settings
from django.db import transaction
from django.utils import timezone, translation
from django.utils.translation import gettext as _
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from billing.utils.payment_service import disconnect_payment_signals, reconnect_payment_signals
from contract.models import Contract, ContractTerminationRequest, ContractRequest, PiggyBank
from service.models import ConnectionRequest, CompanyBank, Exploitation
from coredata.models import ConfigProject, Person, PersonBank
from contract.models import PaymentType

from billing.models import Billing, BillingBatch, EstimatedBagMovement, Invoice, Reading
from billing.serializers.invoice_serializer import InvoiceFullSerializer
from billing.utils.invoice_service import (
    generate_consumption_invoice_multiple,
    pass_budget_to_invoice,
    invoice_contract_termination_generate,
    invoice_connection_generate,
    invoice_contract_generate,
    generate_empty_invoice,
)

class GenerateInvoiceBudgetView(APIView):
    permission_classes = [IsAuthenticated, DjangoModelPermissions]
    queryset = Invoice.objects.all().order_by('-created_at')

    @transaction.atomic
    def post(self, request, *args, **kwargs):
        
        entity = request.data.get('entity', None)
        object_id = request.data.get('object_id', None)
        is_budget = request.data.get('is_budget', None)
        redo_budget = request.data.get('redo_budget', None)
        payment_data = request.data.get('payment_data', None)
        redo_option = request.data.get('redo_option', None)
        # Check if refactor info is at top level
        top_invoice_token = request.data.get('invoice_token') or request.data.get('invoice_id')
        
        selected_custom = request.data.get('selected_custom', None)
        bill_termination_requester = request.data.get('bill_termination_requester', False)
        
        print(f"[GenerateInvoiceBudgetView] entity: {entity}, object_id: {object_id}, is_budget: {is_budget}")
        print(f"[GenerateInvoiceBudgetView] redo_option: {redo_option}")

        # print("object: ", object_id)
        # print("is_budget: ", is_budget)
        # print("redo_budget: ", redo_budget)
        # print("payment_data: ", payment_data)
        # print("redo_option: ", redo_option)
        # print("selected_custom: ", selected_custom)
        
        invoice = None
        due_date = None
        send_at = None
        issue_date = None
        readings = None
        
        payment_type = None
        payment_bank = None
        company_bank = None
        electronic_data = None
        cancel_invoice_token = ConfigProject.objects.get(token='invoice_status_cancelled_token').value
        if payment_data:
            payment_type = payment_data.get("type_id")
            payment_bank = payment_data.get("IBAN")
            company_bank = payment_data.get("company_iban", None)
            electronic_data = payment_data.get("electronic_data")
            due_date = payment_data.get("due_date")
            send_at = payment_data.get("send_at", None)
            issue_date = payment_data.get("issue_date", None)
            selected_exploitation = payment_data.get("selected_exploitation", None)
            exploitation = None
            if selected_exploitation:
                try:
                    exploitation = Exploitation.objects.get(id=selected_exploitation)
                except:
                    pass
        if not due_date:
            due_date = (timezone.now() + timedelta(days=30)).date()
            
        
        if redo_budget:
            print("redo_budget")
            """ budget = self.updatePaymentBudget(redo_budget, payment_type, payment_bank, company_bank, electronic_data)
            invoice_serialized = InvoiceFullSerializer(budget).data
            print("returning invoice")
            return Response({'invoice': invoice_serialized}, status=status.HTTP_200_OK) """
            try:
                budget = Invoice.objects.get(id=redo_budget)
                budget.delete()
            except Invoice.DoesNotExist:
                pass
            
        if entity == "contract_termination_request":
            
            contract_termination_request = ContractTerminationRequest.objects.get(id=object_id)
            contract = contract_termination_request.contract
            
            print("contract_termination_request")
            # Find linked contract request for surrogation/alta cases (Alta + Baixa vinculades)
            linked_contract_request = contract_termination_request.contract_requests_termination_requests.filter(bill_cut_reading=True, is_active=True).first()

            # Save bill_cut_reading if provided in the request.
            # Qui decideix si la lectura de tall es cobra a l'alta és la ContractRequest: la
            # pantalla de la baixa envia sempre bill_cut_reading=False i no ha de desactivar
            # el que s'ha marcat a l'alta.
            bill_cut_reading = request.data.get('bill_cut_reading', None)
            if bill_cut_reading is not None and not (linked_contract_request and not bill_cut_reading):
                contract_termination_request.bill_cut_reading = bill_cut_reading
                contract_termination_request.save()

            # Si hi ha una alta vinculada que ha de cobrar la lectura de tall, ella manda:
            # la pantalla de la baixa munta el diàleg de facturació amb
            # bill_termination_requester=true fix (ContractTerminationRegion.vue), i a
            # invoice_contract_termination_generate aquest flag guanyava el billing_entity,
            # de manera que la factura tornava a sortir a nom del titular que es dona de baixa.
            if linked_contract_request:
                bill_termination_requester = False

            budget_type_token = ConfigProject.objects.get(token='invoice_type_budget_token').value

            if not is_budget:
                # Només el pressupost es pot convertir en factura: si la baixa ja té
                # factures anteriors (anul·lades, abonaments...) no s'han de tornar a passar.
                budget = Invoice.objects.filter(
                    contract_termination=contract_termination_request,
                    type__token=budget_type_token,
                ).order_by('-created_at').first()
                print("passing from budget to invoice")
                invoice = pass_budget_to_invoice(budget)
            else:
                Invoice.objects.filter(contract_termination=contract_termination_request, type__token=budget_type_token).delete()
                #invoice = invoice_contract_termination_generate(None, object_id, payment_type, payment_bank, is_budget, electronic_data)
                invoice = invoice_contract_termination_generate(None, contract_termination_request.id, payment_type, payment_bank, is_budget, electronic_data, billing_entity=linked_contract_request, is_initiation=(linked_contract_request is not None), bill_termination_requester=bill_termination_requester)
            print("invoice")
            print(invoice)
        
        elif entity == "connection_request":
            connection_request = ConnectionRequest.objects.get(id=object_id)
            
            if not is_budget:
                try:
                    budget = Invoice.objects.get(connection_request=connection_request)
                except:
                    budget = Invoice.objects.filter(connection_request=connection_request).first()
                print("passing from budget to invoice")
                invoice = pass_budget_to_invoice(budget)
            else:
                """ payment_data = {
                    "type_id": payment_type,
                    "IBAN": payment_bank,
                    "company_iban": company_bank,
                    "electronic_data": electronic_data
                } """
                # invoice = invoice_connection_generate(None, object_id, 'SOL·LICITUD D\'ESCOMESA', payment_type, payment_bank, company_bank, is_budget, electronic_data)
                invoice = generate_empty_invoice(None, connection_request, connection_request.person, 'SOL·LICITUD D\'ESCOMESA', payment_data, connection_request.exploitation)
            print("invoice")
            print(invoice)
        
        elif entity == "invoice":
            if is_budget:
                return Response({'error': 'No es pot generar un pressupost d\'una factura ja existent.'}, status=status.HTTP_400_BAD_REQUEST)
            budget = Invoice.objects.get(id=object_id)
            invoice = pass_budget_to_invoice(budget)
        
        elif entity == "contract_request":
            contract_request = ContractRequest.objects.get(id=object_id)
            
            new_holder_id = None
            if redo_option:
                reason = redo_option.get("reason")
                new_holder_id = redo_option.get("new_holder", None)
            # Save bill_cut_reading if provided in the request and propagate to terminations
            bill_cut_reading = request.data.get('bill_cut_reading', None)
            if bill_cut_reading is not None:
                contract_request.bill_cut_reading = bill_cut_reading
                contract_request.save()
                # Propagate to linked termination requests
                for tr in contract_request.contract_termination_requests.all():
                    tr.bill_cut_reading = bill_cut_reading
                    tr.save()

            if not is_budget:
                try:
                    budget = Invoice.objects.get(contract_request=contract_request)
                except:
                    budget = Invoice.objects.filter(contract_request=contract_request).first()
                print("passing from budget to invoice")
                invoice = pass_budget_to_invoice(budget)
            else:
                with translation.override(settings.LANGUAGE_CODE):
                    contract_creation_title = _('ALTA CONTRACTE')

                invoice = invoice_contract_generate(
                    None, object_id, contract_creation_title, payment_type,
                    payment_bank, False, None,
                    electronic_data, is_budget, company_bank,
                    company_id=payment_data.get('company_id') if payment_data else None,
                    category_id=payment_data.get('category_id') if payment_data else None,
                    new_holder=new_holder_id)
        elif entity == "contract":
            contract = Contract.objects.get(id=object_id)
            title = 'Facturació'
            refactor_invoice_token = None
            new_holder_id = None
            
            if redo_option: # or top_invoice_token:
                # If redo_option is missing but we have a token, we initialize it
                # if not redo_option:
                #     redo_option = {
                #         'invoice_token': top_invoice_token,
                #         'reason': 'other',
                #         'title': 'Refacturació',
                #         'leak_consum': {}
                #     }
                reason = redo_option.get("reason")
                new_holder_id = redo_option.get("new_holder", None)
                title = redo_option.get("title", 'Refacturació')
                refactor_invoice_token = redo_option.get("invoice_token")
                
                print(f"[GenerateInvoiceBudgetView] Refactor detected. Reason: {reason}")
                leak_consumption = redo_option.get("leak_consum")
                reading_ids = []
                readings = []
                og_readings = []
                
                # if leak_consumption:
                try:
                    for value, leak in leak_consumption.items():
                        
                        reading_ids.append(value)
                        reading = Reading.objects.get(id=value)
                        new_reading = reading.modified_readings.filter(is_control=False).first()
                        if not new_reading:
                            try:
                                og_reading = reading.original_readings.first()
                                og_reading = og_reading.modified_readings.filter(is_control=False).first()
                                if og_reading:
                                    new_reading = og_reading
                            except:
                                pass
                        og_readings.append(reading)
                        if reason == "other" or reason == "holder":
                            readings.append(reading)
                        else:
                            if reading:
                                # Fallback to original reading if modified one is not found
                                readings.append(new_reading if new_reading else reading)
                except:
                    pass
                
                # If readings list is still empty, try to get them from the original invoice being refactored
                invoice_ref = refactor_invoice_token or redo_option.get("invoice_id")
                """ if not readings and invoice_ref:
                    try:
                        if isinstance(invoice_ref, int) or (isinstance(invoice_ref, str) and invoice_ref.isdigit()):
                            old_invoice = Invoice.objects.get(id=invoice_ref)
                        else:
                            old_invoice = Invoice.objects.get(token=invoice_ref)
                        
                        readings = list(old_invoice.readings.all())
                        print(f"[GenerateInvoiceBudgetView] Recovered {len(readings)} readings from original invoice {old_invoice.token}")
                        
                        if not og_readings:
                            og_readings = readings
                    except Invoice.DoesNotExist:
                        print(f"[GenerateInvoiceBudgetView] Could not find original invoice with reference {invoice_ref}")
                        pass """
            else:
                # If no redo_option, try to find pending readings for the contract
                readings = list(Reading.objects.filter(contract=contract, batch__isnull=True, is_active=True, is_control=False).order_by('reading_date'))
                og_readings = readings
                print(f"[GenerateInvoiceBudgetView] Found {len(readings)} pending readings for contract {contract.id}")

            if readings:
                try:
                    billing = None
                    billing_batch = None
                    # Try to find context from the most recent reading that was previously billed
                    for r in og_readings:
                        last_inv = r.invoices.filter(contract__id=contract.id).first()
                        if last_inv:
                            billing = last_inv.billing
                            billing_batch = last_inv.batch
                            break
                except:
                    billing = None
                    billing_batch = None
                
                if not billing:
                    # Resolve biller from reading route chain:
                    biller = None
                    first_reading = og_readings[0] if og_readings else None
                    supply_point = getattr(first_reading, "supply_point", None)
                    prop = getattr(supply_point, "property", None)
                    route_position = getattr(prop, "route_position", None)
                    route = getattr(route_position, "route", None)
                    biller = getattr(route, "biller", None)
                else:
                    biller = billing.biller
                    
                period_type = biller.period_type if biller else 'trimestral'
                PERIOD_MONTHS_MAP = {
                    'trimestral': 90,
                    'semestral': 180,
                    'bimestral': 60,
                    'quadrimestral': 120,
                    'anual': 360,
                    'mensual': 30,
                }
                period_days = payment_data.get("period_days") if payment_data and payment_data.get("period_days") else PERIOD_MONTHS_MAP[period_type]
                period_months = period_days / 30
                
                print(f"[GenerateInvoiceBudgetView] Period months: {period_months}")
                
                invoice = generate_consumption_invoice_multiple(contract, readings, title, refactor_invoice=refactor_invoice_token, is_budget=True, extra_payment_data=payment_data, billing=billing, billing_batch=billing_batch, period_months=period_months, new_holder=new_holder_id)
        
        elif entity == "custom":
            entity_custom = selected_custom.get("entity")
            custom_id = selected_custom.get("id")
            contract = None
            person = None
            
            title = selected_custom.get("title") if selected_custom.get("title") else selected_custom.get("label")

            if payment_data is None:
                payment_data = {}
            if selected_custom.get("company") is not None:
                payment_data['company_id'] = selected_custom.get("company")
            if selected_custom.get("category") is not None:
                payment_data['category_id'] = selected_custom.get("category")

            try:
                exploitation = Exploitation.objects.get(id=selected_custom.get("exploitation"))
            except:
                pass
            if entity_custom == "contract":
                contract = Contract.objects.get(id=custom_id)
            elif entity_custom == "person":
                person = Person.objects.get(id=custom_id)
            billing_batch_id = selected_custom.get("billing_batch_id")
            billing_id = selected_custom.get("billing_id")
            billing_batch = None
            billing = None
            
            if billing_batch_id:
                try:
                    if isinstance(billing_batch_id, int) or str(billing_batch_id).isdigit():
                        try:
                            billing_batch = BillingBatch.objects.get(id=billing_batch_id)
                            billing = billing_batch.billing
                        except BillingBatch.DoesNotExist:
                            # Try as billing ID since sometimes they are confused in the frontend
                            try:
                                billing = Billing.objects.get(id=billing_batch_id)
                            except Billing.DoesNotExist:
                                pass
                    else:
                        try:
                            billing_batch = BillingBatch.objects.get(token=billing_batch_id)
                            billing = billing_batch.billing
                        except BillingBatch.DoesNotExist:
                            try:
                                billing = Billing.objects.get(token=billing_batch_id)
                            except Billing.DoesNotExist:
                                pass
                except (ValueError, TypeError):
                    pass
            
            if not billing and billing_id:
                try:
                    if isinstance(billing_id, int) or str(billing_id).isdigit():
                        billing = Billing.objects.get(id=billing_id)
                    else:
                        billing = Billing.objects.get(token=billing_id)
                except (Billing.DoesNotExist, ValueError, TypeError):
                    pass

            if selected_custom.get("type") == "reading":
                readings = Reading.objects.filter(id__in=selected_custom.get("readings"), is_close=False)
                
                biller = None
                first_reading = readings[0] if readings else None
                supply_point = getattr(first_reading, "supply_point", None)
                prop = getattr(supply_point, "property", None)
                route_position = getattr(prop, "route_position", None)
                route = getattr(route_position, "route", None)
                biller = getattr(route, "biller", None)
                    
                period_type = biller.period_type if biller else 'trimestral'
                PERIOD_MONTHS_MAP = {
                    'trimestral': 90,
                    'semestral': 180,
                    'bimestral': 60,
                    'quadrimestral': 120,
                    'anual': 360,
                    'mensual': 30,
                }
                period_days = PERIOD_MONTHS_MAP[period_type]
                period_months = period_days / 30
                
                invoice = generate_consumption_invoice_multiple(contract, readings, title, None, is_budget=True, extra_payment_data=payment_data, period_months=period_months, billing=billing, billing_batch=billing_batch)
            else:
                invoice = generate_empty_invoice(contract, None, person, title, payment_data, exploitation, billing=billing, billing_batch=billing_batch)

        if not invoice:
            if readings is not None and len(readings) > 0 and readings[0] and readings[0].consumption_days < 0:
                return Response({'error': 'No se ha podido generar el documento. La lectura anterior es posterior a la lectura actual (comparar la lectura con la creación del contrato)'}, status=status.HTTP_400_BAD_REQUEST)
            
            error_msg = 'No se ha podido generar el documento.'
            if not readings or len(readings) == 0:
                error_msg += ' No s\'han proporcionat lectures per facturar.'
            else:
                error_msg += ' És possible que no s\'hagin generat línies de factura (comprovi els preus del contracte).'
                
            return Response({'error': error_msg}, status=status.HTTP_400_BAD_REQUEST)

        disconnect_payment_signals()
        if issue_date:
            if isinstance(issue_date, str):
                from django.utils.dateparse import parse_date
                parsed_issue_date = parse_date(issue_date)
                if parsed_issue_date:
                    invoice.issue_date = parsed_issue_date
            else:
                invoice.issue_date = issue_date
        invoice.due_date = due_date
        invoice.send_at = send_at

        invoice.save()
        reconnect_payment_signals()
        invoice_serialized = InvoiceFullSerializer(invoice).data
        
        return Response({'invoice': invoice_serialized}, status=status.HTTP_200_OK)

    def updatePaymentBudget(self, redo_budget, payment_type, payment_bank, company_bank, electronic_data):
        try:
            print("updating payment budget")
            payment_type_instance = PaymentType.objects.get(id = payment_type)
            print("payment type")
            print(payment_type_instance)
            payment_bank_instance = PersonBank.objects.get(id = payment_bank) if payment_bank else None
            payment_comp_bank_instance = CompanyBank.objects.get(id = company_bank) if company_bank else None
            iban = None
            swift = None
            if payment_bank_instance:
                iban = payment_bank_instance.iban if payment_bank_instance.iban else None
                swift = payment_bank_instance.swift if payment_bank_instance.swift else None
            if payment_comp_bank_instance:
                iban = payment_comp_bank_instance.iban if payment_comp_bank_instance.iban else None
                swift = payment_comp_bank_instance.swift if payment_comp_bank_instance.swift else None
            budget = Invoice.objects.get(id=redo_budget)
            budget.payment_type = payment_type_instance
            budget.payment_type_final = payment_type_instance.name if payment_type_instance else "Sense pagament configurat"
            budget.payment_type_token_final = payment_type_instance.token if payment_type_instance else "Sense pagament configurat"
            budget.payment_company_bank = payment_comp_bank_instance
            budget.payment_bank = payment_bank_instance
            budget.payment_bank_final = iban
            budget.payment_swift_final = swift
            budget.accounting_office_final = electronic_data.get('accounting_office') if electronic_data and 'accounting_office' in electronic_data else None
            budget.managing_body_final = electronic_data.get('managing_body') if electronic_data and 'managing_body' in electronic_data else None
            budget.processing_unit_final = electronic_data.get('processing_unit') if electronic_data and 'processing_unit' in electronic_data else None
            budget.save()
            return budget
        except:
            raise Exception("Failed to redo_budget")