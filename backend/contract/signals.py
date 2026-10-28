from django.db.models.signals import post_save, pre_save, pre_delete
import uuid
from django.dispatch import receiver
from datetime import datetime
from django.utils import timezone
from dateutil.relativedelta import relativedelta
from django.db.models import Q, Value
from django.db.models.functions import Coalesce
import random
import datetime
from faker import Faker
from django.db.models import Sum, Count
from billing.models import Invoice
from claimrequest.models import ClaimRequest, ClaimRequestPayment, ClaimRequestStatus, VulnerabilityRequest
from billing.utils.payment_service import *
from communication.models import Communication
from coredata.utils.name_utils import generate_token
from logger.models import LogClaimRequestContractChange
from billing.models import InvoiceStatus, Payment, PaymentStatus, Reading
from billing.utils.invoice_service import change_status_logger, get_invoice_status, invoice_claim_paid_generate, invoice_return_charge
from coredata.models import ConfigProject, PersonDeliquency
from contract.utils.bail_service import pending_bail_contract_termination
from coredata.models import Person
from logger.models import LogContractBonificationsVariablesChange, LogContractExpiredBonificationsVariables
from order.models import Order, OrderStatus
from .models import ACABonificationRequest, ACADocument, ACADocumentStatus, Bonification, BonificationDocumentation, BonificationType, Contract, ContractDataChange, ContractLog, ContractObservation, ContractPriceRate, ContractPriceRateHistory, ContractRequest, ContractRequestDocumentation, ContractSurrogation, ContractSurrogationDocument, ContractTenantChange, ContractTerminationRequest, Variable, VariableType
from .middleware import get_current_user
from .utils.contract_request_service import contract_request_check_orders

""" 
@receiver(post_save, sender=ContractRequest)
def contract_request_created(sender, instance, created, **kwargs):
    if created:
        if instance.type:
            print("in signals")
            contract_price_rates = []
            print("what")
            print("price rates", instance.type.price_rates.all())
            for price_rate in instance.type.price_rates.all():
                print("price rate", price_rate)
                print("supply points", instance.supply_points.all())
                for supply_point in instance.supply_points.all():
                    contract_price_rate = ContractPriceRate.objects.create(
                        token=instance.token,
                            supply_point=supply_point,
                            price_rate=price_rate
                        )
                    contract_price_rates.append(contract_price_rate)
            instance.price_rates.set(contract_price_rates)
            instance.registration_price_rates.set(instance.type.registration_price_rates.all())
            instance.order_types.set(instance.type.order_types.all()) """
    
@receiver(pre_save, sender=ContractRequest)
def contract_request_pre_save(sender, instance, **kwargs):
    if instance.type and instance.type.token == 'canvi_nom':
        instance.is_change_of_name = True

    if instance.pk:  # This is an update
        try:
            old_instance = ContractRequest.objects.get(pk=instance.pk)
            if instance.type and old_instance.type != instance.type:
                # Type has changed, update the related fields
                contract_price_rates = []
                for price_rate in instance.type.price_rates.all():
                    for supply_point in instance.supply_points.all():
                        contract_price_rate, _ = ContractPriceRate.objects.get_or_create(
                            supply_point=supply_point,
                            price_rate=price_rate
                        )
                        contract_price_rates.append(contract_price_rate)
                instance.price_rates.set(contract_price_rates)
                instance.registration_price_rates.set(instance.type.get_registration_price_rates(instance.is_change_of_name))
                instance.order_types.set(instance.type.get_order_types(instance.is_change_of_name))
        except ContractRequest.DoesNotExist:
            pass
    return instance

@receiver(post_save, sender=Contract)
def terminate_contract_update_bail(sender, instance, **kwargs):
    if instance.id:
        terminated_token = ConfigProject.objects.get(token='contract_terminated_status').value
        if instance.status and instance.status.token == terminated_token:
            user = None
            user = get_current_user()
                
            pending_bail_contract_termination(user, instance)

@receiver(post_save, sender=Contract)
def contract_created_log(sender, instance, created, **kwargs):
    # Registra a l'historial l'usuari que ha donat d'alta el contracte
    if not created:
        return
    ContractLog.objects.create(
        contract=instance,
        field_name='created',
        old_value=None,
        new_value=instance.token,
        operation_token=str(uuid.uuid4()),
        user=get_current_user()
    )

@receiver(pre_save, sender=Contract)
def contract_pre_save(sender, instance, **kwargs):
    if instance.pk:  # This is an update
        try:
            old_instance = Contract.objects.get(pk=instance.pk)
            current_user = get_current_user()

            # Fallback: if there is no real user (e.g. management command),
            # try to use the first user in the DB; if none, log with user=None.
            if not current_user or getattr(current_user, "is_anonymous", False):
                from django.contrib.auth import get_user_model
                User = get_user_model()
                current_user = User.objects.order_by("id").first()

            operation_token = str(uuid.uuid4())

            fields = [f.name for f in Contract._meta.fields]

            for field in fields:
                old_value = getattr(old_instance, field)
                new_value = getattr(instance, field)

                if old_value != new_value:
                    old_value_str = str(old_value) if old_value is not None else None
                    new_value_str = str(new_value) if new_value is not None else None

                    ContractLog.objects.create(
                        contract=instance,
                        field_name=field,
                        old_value=old_value_str,
                        new_value=new_value_str,
                        operation_token=operation_token,
                        user=current_user  # can be a real user, fallback user, or None
                    )
        except Contract.DoesNotExist:
            pass

@receiver(post_save, sender=ContractTerminationRequest)
def update_termination_status(sender, instance, **kwargs):
    if instance.id:
        if instance.status and instance.status.token!="3" and instance.status.token!="1":
            order_status = ConfigProject.objects.get(token = 'order_status_completed_token').value
            orders = Order.objects.filter(contract_termination_request=instance).exclude(status__token=order_status)
            for order in orders:
                order.status = OrderStatus.objects.get(token="1")
                order.save()
        
     
@receiver(post_save, sender=BonificationType)
def deactivate_bonification_type(sender, instance, **kwargs):
    if instance.id:
        if instance.is_active == False:
            if hasattr(instance, '_skip_signal'):
                return  
            
            bonifications = Bonification.objects.filter(bonification_type=instance)
            for bonification in bonifications:
                bonification.is_active = False
                bonification.save()
            
            print(instance.end_at)
            if not instance.end_at or instance.end_at == None:
                instance._skip_signal = True
                instance.end_at = timezone.now().date()
                instance.save()
        
            
@receiver(post_save, sender=Bonification)
def deactivate_bonification(sender, instance, **kwargs):
    if hasattr(instance, '_skip_signal'):
        return  

    if instance.id:
        if instance.is_active == False:
            try:
                user = None
                from order.middleware import get_current_user
                user = get_current_user()
                    
                variables = Variable.objects.filter(bonification=instance)
                if variables:
                    for variable in variables:
                        try:
                            LogContractBonificationsVariablesChange.objects.create(
                                object=instance.contract,
                                previous_bonification=instance,
                                current_bonification=None,
                                previous_variable= None if hasattr(instance, '_skip_variable') else variable,
                                current_variable=None,
                                user=user,
                                observation=None
                            )
                            LogContractExpiredBonificationsVariables.objects.get_or_create(
                                object=instance.contract if instance.contract else None,
                                expired_bonification=instance,
                                expired_variable=variable,
                                expiring_date = timezone.now().date()
                            )
                        except Exception as e:
                            print(e)
                        
                        if not hasattr(instance, '_skip_variable'):
                            variable.is_active = False
                            variable.type.is_active = False
                            variable.contract = None
                            variable.save()
                            print(f"Deactivated variable: {variable}")

                instance._skip_signal = True
                instance.contract = None  
                if not instance.end_at:
                    instance.end_at = timezone.now().date()
                instance.save()

            except Exception as e:
                print(e)

@receiver(post_save, sender=Variable)
def modified_variables_bonifications(sender, instance, **kwargs):
    if instance.id:
        try:
            
            user = None
            from order.middleware import get_current_user
            user = get_current_user()
            try:
                LogContractBonificationsVariablesChange.objects.create(
                    object=instance.contract,
                    previous_bonification=None,
                    current_bonification=instance.bonification,
                    previous_variable=None,
                    current_variable=instance,
                    user=user,
                    observation=None
                )
            except Exception as e:
                print(e)
                
        except Exception as e:
            print(e)
        

@receiver(post_save, sender=Variable)
def added_end_at_variable(sender, instance, created, **kwargs):
    if hasattr(instance, '__skip_signal'):
        return
    if created:
        return
    if instance.id:
        if instance.end_at and instance.end_at <= timezone.now().date():
            # print(f"Added end_at to variable: {instance}")
            # if end_at is has not yet happened (before today), return and do not update
            try:
                user = None
                from order.middleware import get_current_user
                user = get_current_user()
                try:
                    LogContractBonificationsVariablesChange.objects.create(
                        object=instance.contract,
                        previous_bonification=None,
                        current_bonification=None,
                        previous_variable=None,
                        current_variable=instance,
                        user=user,
                        observation=None
                    )
                    LogContractExpiredBonificationsVariables.objects.get_or_create(
                        object=instance.contract if instance.contract else None,
                        expired_bonification=instance.bonification if instance.bonification else None,
                        expired_variable=instance,
                        expiring_date = timezone.now().date()
                    )
                except Exception as e:
                    print(e)
                
                bonification = instance.bonification
                if bonification:
                    bonification._skip_signal = True
                    bonification.end_at = instance.end_at
                    bonification.is_active = False
                    bonification.contract = None
                    bonification.save()
                
                instance.is_active = False
                instance.contract = None
                instance.__skip_signal = True
                instance.save()
                    
            except Exception as e:
                print(e)

@receiver(post_save, sender=ACADocument)
def assign_variables(sender, instance, **kwargs):
    """Quan un document rebut de l'ACA (Cànon social o Ampliació de trams) passa a
    l'estat 'aca_bonification_processed', aplica als contractes les línies
    acceptades (veure contract/utils/aca_document_apply_service.py)."""
    if not instance.id:
        return
    try:
        token = ConfigProject.objects.filter(token='aca_bonification_processed').values_list('value', flat=True).first()
        if not token or not instance.status or instance.status.token != token:
            return
        # Els fitxers que genera l'aplicació per enviar a l'ACA també són ACADocument.
        if instance.source == 'Entitat subministradora' and instance.aca_bonification_requests.exists():
            return

        from .utils.aca_document_apply_service import apply_aca_document
        result = apply_aca_document(instance)
        if result['skipped']:
            print(f"ACADocument {instance.id}: línies no aplicades {result['skipped']}")
    except Exception as exception:
        print('ERROR')
        print(exception)

@receiver(post_save, sender=Bonification)
def track_aca_bonification_request(sender, instance, **kwargs):
    """Detecta quan s'afegeix (o es desactiva) al contracte una Bonification del
    tipus 'Ampliació de trams' d'ACA, per acumular-la a la llista de sol·licituds
    pendents d'enviar a l'ACA (veure ACABonificationRequest).

    Aquest tracking (i tot el que en depèn: sol·licituds pendents, exportació del
    fitxer) només s'activa amb `aca_notification_enabled` (ConfigProject); la
    Bonification/Variable en si es crea igualment (veure
    `contract.utils.aca_tram_service.sync_aca_tram_with_total_persons`), només amb `uses_aca`."""
    if getattr(instance, '_skip_signal', False):
        return

    from watchdog.aca_config import aca_notification_enabled
    if not aca_notification_enabled():
        return

    bonification_token = ConfigProject.objects.filter(token='aca_at_token').first()
    if not bonification_token:
        return

    is_aca_type = (
        instance.bonification_type
        and bonification_token.value
        and bonification_token.value.lower() in (instance.bonification_type.token or '').lower()
    )
    if not is_aca_type:
        return

    if instance.is_active and instance.contract_id:
        aca_request, created = ACABonificationRequest.objects.get_or_create(bonification=instance)
        if created and not instance.requested_at:
            # Data de registre de la sol·licitud ACA: es fixa en el moment de crear-se
            # la petició, no en el moment d'exportar (veure build_detail_record).
            Bonification.objects.filter(pk=instance.pk).update(requested_at=timezone.now())
        if aca_request.num_persons_to_apply is None:
            _sync_num_persons_from_variable(aca_request)
    else:
        ACABonificationRequest.objects.filter(bonification=instance, sent_at__isnull=True).delete()

def _sync_num_persons_from_variable(aca_request):
    """El nombre de persones a aplicar és el de la variable configurada a
    `ConfigProject.aca_tram_members_variable_token` (veure AddBonification.vue),
    no un valor per defecte del contracte."""
    from watchdog.aca_config import is_aca_tram_members_variable_type
    variable = next(
        (
            item for item in aca_request.bonification.variables.select_related('type')
            if is_aca_tram_members_variable_type(item.type)
        ),
        None,
    )
    if variable and variable.value is not None:
        try:
            aca_request.num_persons_to_apply = int(variable.value)
            aca_request.save()
        except (TypeError, ValueError):
            pass

@receiver(post_save, sender=Variable)
def sync_aca_bonification_num_persons(sender, instance, **kwargs):
    """Quan es desa la variable amb el nombre de membres de la sol·licitud
    d'ampliació de trams (creada després de la Bonification, veure
    AddBonification.vue), actualitza la sol·licitud ACA pendent associada."""
    from watchdog.aca_config import is_aca_tram_members_variable_type
    if not instance.bonification_id or not is_aca_tram_members_variable_type(instance.type):
        return

    aca_request = ACABonificationRequest.objects.filter(bonification_id=instance.bonification_id).first()
    if not aca_request:
        return

    try:
        aca_request.num_persons_to_apply = int(instance.value)
        aca_request.save()
    except (TypeError, ValueError):
        pass

def _attach_variable_to_aca_bonification(variable):
    """La variable "Membres d'ampliació de tram (ACA)" s'ha desat solta sobre un
    contracte (apartat Variables, `AddVariable.vue`), sense passar pel formulari de
    bonificació. La vinculem a la Bonification d'ampliació de trams del contracte —
    creant-la si el contracte encara no en té cap d'activa — perquè l'ampliació quedi
    lligada al contracte i segueixi el mateix camí que quan s'afegeix des
    d'`AddBonification.vue` (sol·licitud ACA pendent i `total_persons` sincronitzat).

    Retorna la Bonification vinculada, o None si aquest projecte no té configurat el
    tipus de bonificació ACA o la variable no n'és una de les seves."""
    from .utils.aca_tram_service import get_aca_tram_bonification_type
    bonification_type = get_aca_tram_bonification_type()
    if not bonification_type:
        return None
    if not bonification_type.variable_types.filter(pk=variable.type_id).exists():
        return None

    contract = variable.contract
    bonification = Bonification.objects.filter(
        contract=contract, bonification_type=bonification_type, is_active=True
    ).order_by('-id').first()
    if not bonification:
        bonification = Bonification.objects.create(
            person=contract.holder,
            contract=contract,
            bonification_type=bonification_type,
            requested_at=timezone.now(),
            is_active=True,
            token=generate_token(Bonification),
        )

    # `update()` i no `save()`: no volem tornar a disparar els post_save de Variable
    # mentre som dins d'un d'ells.
    Variable.objects.filter(pk=variable.pk).update(bonification=bonification)
    variable.bonification = bonification

    # `sync_aca_bonification_num_persons` ja ha passat de llarg (quan s'ha executat,
    # la variable encara no tenia bonificació), així que informem aquí el nombre de
    # persones de la sol·licitud ACA que s'acaba de crear.
    aca_request = ACABonificationRequest.objects.filter(bonification=bonification).first()
    if aca_request:
        _sync_num_persons_from_variable(aca_request)

    return bonification


@receiver(post_save, sender=Variable)
def sync_contract_total_persons_from_aca_variable(sender, instance, **kwargs):
    """Quan es crea o modifica la variable "Membres d'ampliació de tram (ACA)" d'una
    Bonification ACA-TRAM, actualitza `Contract.total_persons` (Persones a
    l'habitatge) amb el mateix valor — només si l'ACA està activa per aquest
    projecte (`watchdog.aca_config.uses_aca_enabled`). És el sentit invers de
    `sync_aca_tram_on_total_persons_change` (aquest mateix fitxer).

    Si la variable s'ha desat solta sobre el contracte (sense bonificació), abans la
    vinculem a la bonificació d'ampliació de trams del contracte
    (`_attach_variable_to_aca_bonification`).

    Una variable inactiva (bonificació desactivada) o per sota del mínim de persones
    (`aca_tram_min_persons`) no toca el contracte: l'API ja no accepta valors per sota
    del mínim (`VariableSaveSerializer`), però en poden arribar d'altres fluxos."""
    if getattr(instance, '_skip_signal', False):
        return
    from watchdog.aca_config import (
        aca_tram_min_persons,
        is_aca_tram_members_variable_type,
        uses_aca_enabled,
    )
    if not instance.is_active or not is_aca_tram_members_variable_type(instance.type):
        return
    if not uses_aca_enabled():
        return

    try:
        num_persons = int(instance.value)
    except (TypeError, ValueError):
        return
    if num_persons < aca_tram_min_persons():
        return

    bonification = instance.bonification
    if bonification is None and instance.contract_id:
        bonification = _attach_variable_to_aca_bonification(instance)
    if not bonification or not bonification.is_active or not bonification.contract_id:
        return

    bonification_token = ConfigProject.objects.filter(token='aca_at_token').first()
    if not bonification_token or not bonification_token.value:
        return
    if not bonification.bonification_type or bonification_token.value.lower() not in (bonification.bonification_type.token or '').lower():
        return

    contract = bonification.contract
    if contract.total_persons != num_persons:
        from logger.models import LogContractTotalMembers
        from order.middleware import get_current_user
        LogContractTotalMembers.objects.create(
            object=contract,
            previous_total_persons=contract.total_persons,
            current_total_persons=num_persons,
            user=get_current_user(),
            observation="Actualitzat des de la variable de membres de l'ampliació de trams (ACA)",
        )
        contract._skip_signal = True
        contract.total_persons = num_persons
        contract.save(update_fields=['total_persons'])

@receiver(pre_save, sender=Contract)
def capture_total_persons_before_save(sender, instance, **kwargs):
    """Guarda l'antic `total_persons` a la pròpia instància (no persistit) perquè
    `sync_aca_tram_on_total_persons_change` el pugui comparar a `post_save`,
    independentment de quin flux (vista, comanda, script) faci el `.save()`."""
    if instance.pk:
        instance._old_total_persons = Contract.objects.filter(pk=instance.pk).values_list(
            'total_persons', flat=True
        ).first()
    else:
        instance._old_total_persons = None

@receiver(post_save, sender=Contract)
def sync_aca_tram_on_total_persons_change(sender, instance, created, **kwargs):
    """Quan canvia el nombre d'habitants (`total_persons`) d'un contracte, ajusta la
    bonificació d'ampliació de trams de l'ACA (crear, actualitzar o desactivar segons el
    mínim de persones). Veure `contract.utils.aca_tram_service`."""
    if created or getattr(instance, '_skip_signal', False):
        return

    from .utils.aca_tram_service import sync_aca_tram_with_total_persons
    sync_aca_tram_with_total_persons(instance, getattr(instance, '_old_total_persons', None))

@receiver(pre_delete, sender=Contract)
def delete_contract_related(sender, instance, **kwargs):
    invoice_cancelled = ConfigProject.objects.get(token='invoice_status_cancelled_token').value
    payment_cancelled = ConfigProject.objects.get(token='payment_status_cancelled_token').value
    
    bonifications = Bonification.objects.filter(contract=instance, contract_request__isnull=True)
    variables = Variable.objects.filter(contract=instance, contract_request__isnull=True)
    documentations = ContractRequestDocumentation.objects.filter(contract=instance, contract_request__isnull=True)
    bonifications.delete()
    variables.delete()
    documentations.delete()
    if instance.piggy_bank:
        instance.piggy_bank.delete()
    invoices = Invoice.objects.filter(contract=instance)
    payments = Payment.objects.filter(contract=instance)
    invoices.update(status=InvoiceStatus.objects.get(token=invoice_cancelled))
    payments.update(status=PaymentStatus.objects.get(token=payment_cancelled))
    
    
    