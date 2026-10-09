import datetime
import uuid
from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver

from coredata.models import ConfigProject
from order.models import Order, OrderStatus, OrderType
from service.middleware import get_current_user
from .models import Cluster, MeterLog, SupplyCut, SupplyPointStatus, Meter, MeterManufacturer, MeterModel

def get_or_create_manufacturer(manufacturer_name):
    if not manufacturer_name:
        return None
    manufacturer, created = MeterManufacturer.objects.get_or_create(name=manufacturer_name)
    if created:
        print('MANUFACTURER CREATED', created, manufacturer_name)
    return manufacturer

def get_or_create_model(model_name, manufacturer):
    if not model_name:
        return None
    model, created = MeterModel.objects.get_or_create(name=model_name, manufacturer=manufacturer)
    if created:
        print('MODEL CREATED', created, model_name)
    return model

@receiver(post_save, sender=Meter)
def create_manufacturer_and_model(sender, instance, **kwargs):
    created = kwargs.get('created', False)
    if created:
        current_user = get_current_user()
        MeterLog.objects.create(
            meter=instance,
            field_name=None,
            old_value=None,
            new_value=None,
            operation_token="create",
            user=current_user if current_user and not current_user.is_anonymous else None
        )

    if instance.manufacturer:
        manufacturer = get_or_create_manufacturer(instance.manufacturer)
        instance.manufacturer = manufacturer.name
    
    if instance.model:
        manufacturer = get_or_create_manufacturer(instance.manufacturer)
        model = get_or_create_model(instance.model, manufacturer)
        instance.model = model.name

@receiver(pre_save, sender=Meter)
def meter_pre_save(sender, instance, **kwargs):
    if instance.pk:
        try:
            old_instance = Meter.objects.get(pk=instance.pk)
            current_user = get_current_user()

            operation_token = str(uuid.uuid4())
            fields = [f.name for f in Meter._meta.fields]
            
            for field in fields:
                old_value = getattr(old_instance, field)
                new_value = getattr(instance, field)
                
                if old_value != new_value:
                    old_value_str = str(old_value) if old_value is not None else None
                    new_value_str = str(new_value) if new_value is not None else None
                    
                    MeterLog.objects.create(
                        meter=instance,
                        field_name=field,
                        old_value=old_value_str,
                        new_value=new_value_str,
                        operation_token=operation_token,
                        user=current_user if current_user and not current_user.is_anonymous else None
                    )
        except Meter.DoesNotExist:
            pass


@receiver(pre_save, sender=Cluster)
def status_change_contractable(sender, instance, **kwargs):
    if instance.id:
        try:
            # Obtenim el valor anterior del model
            previous_instance = Cluster.objects.get(id=instance.id)
            previous_status = previous_instance.status
            
            non_contractable_token = ConfigProject.objects.get(token = 'supply_point_status_not_contractable_token').value
            pending_token = ConfigProject.objects.get(token = 'supply_point_pending_contract').value
            status_non_contractable = SupplyPointStatus.objects.get(token = non_contractable_token)
            status_pending = SupplyPointStatus.objects.get(token = pending_token)
            
            if previous_status != instance.status:
                # Comprova si l'status ha canviat a "no contractable"
                if instance.status.token == non_contractable_token:
                    # Executa la funció o acció desitjada
                    
                    for nozzle in instance.nozzles.all():
                        for supply_point in nozzle.supply_points.all():
                            supply_point.status = status_non_contractable
                            supply_point.save()
                    
                # Comprova si l'status ha canviat de "no contractable"
                elif previous_instance.status and previous_instance.status.token == non_contractable_token:
                    
                    for nozzle in instance.nozzles.all():
                        for supply_point in nozzle.supply_points.all():
                            supply_point.status = status_pending
                            supply_point.save()
        except Exception as exception:
            """ print("Error en el update")
            print(exception) """
            return

@receiver(post_save, sender=SupplyCut)
def create_order_supply_cut(sender, instance, created, **kwargs):
    if instance.id:
        if created:
            #supply_cut_type = OrderType.objects.get(token=ConfigProject.objects.get(token='order_type_supply_cut_token').value)
            #status = OrderStatus.objects.get(token=ConfigProject.objects.get(token='order_status_pending_token').value)
            #TODO: CHECK PROCESS FIRST
            """ Order.objects.create(
                token=f"{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}/SPCUT{instance.id}",
                supply_point=instance.supply_point,
                address=instance.supply_point.address,
                type=supply_cut_type,
                status=status
            ) """
            #print(f"Order created for supply point {instance.supply_point.token}")