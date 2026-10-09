from django.db.models.signals import pre_save, post_save
from django.db import transaction
from django.dispatch import receiver

from coredata.models import ConfigProject
from service.models import ConnectionRequestStatus
from service.views.close_connection_request_view import create_connection

from .models import Order, OrderObservation
from .utils.order_service import order_complete
from logger.models import LogOrderStatus
from django.contrib.auth.models import User

order_save_flag = False


@receiver(pre_save, sender=Order)
def detect_status_change(sender, instance, **kwargs):
    if not instance.pk:
        return
    try:
        previous = sender.objects.get(pk=instance.pk)
    except sender.DoesNotExist:
        return

    # Import get_current_user here to avoid circular import issues
    from .middleware import get_current_user

    current_user = get_current_user()
    if current_user is None:
        print("No authenticated user found.")
        # return # no fem return, deixem guardar el log buit.

    if previous.status_id != instance.status_id:
        prev_name = previous.status.name if previous.status else "(sense estat)"
        curr_name = instance.status.name if instance.status else "(sense estat)"

        # Get the completed status token from config
        try:
            order_complete_status_config = ConfigProject.objects.get(
                token="order_status_completed_token"
            )
            if not order_complete_status_config:
                print( "ConfigProject for 'order_status_completed_token' has no value. Using '2' as default. This may not work well." )
                order_complete_status_token = "10"
            else:   
                order_complete_status_token = order_complete_status_config.value

            # Check if changing FROM completed status TO another status
            if (
                previous.status
                and instance.status
                and str(previous.status.token) == str(order_complete_status_token)
                and str(instance.status.token) != str(order_complete_status_token)
            ):
                instance.completed_at = None
                print(
                    f"Order {instance.pk} status changed from completed to {instance.status.name}, setting completed_at to null."
                )
        except ConfigProject.DoesNotExist:
            print("Config 'order_status_completed_token' not found.")

        # Log the status change
        print(
            f"Order {instance.pk} status changed from {prev_name} to {curr_name}"
        )

        # Create a LogOrderStatus object
        LogOrderStatus.objects.create(
            object=instance,
            previous_status=previous.status,
            current_status=instance.status,
            observation=f"Status changed from {prev_name} to {curr_name}",
            user=current_user,  # Get the current user from the middleware
        )

       


@receiver(post_save, sender=Order)
def after_order_save(sender, instance, created, **kwargs):
    global order_save_flag
    if order_save_flag:
        return  # Prevent recursive call

    if not created:
        from .middleware import get_current_user

        current_user = get_current_user()
        if current_user is None:
            print("No authenticated user found.")

        order_complete_status_config = ConfigProject.objects.get(
            token="order_status_completed_token"
        )
        order_complete_status = order_complete_status_config.value

        # Check if the order status has been updated to the 'completed' status
        if instance.status and instance.status.token == order_complete_status:
            order_save_flag = True  # Set the flag to prevent recursion
            try:
                order_complete(current_user, instance.id)
                print(
                    f"Order {instance.pk} status changed to completed, added completed_at."
                )
                response = None
                if instance.contract_request:
                    pass
                    """ from contract.utils.contract_request_service import contract_request_check_orders
                    response = contract_request_check_orders(current_user, instance.contract_request.id)
                    instance.check_response = response
                    instance.save()
                    print(f"Contract request check for Order {instance.pk} executed.") """
                if instance.contract_termination_request:
                    from contract.utils.contract_request_service import (
                        contract_termination_check_orders,
                    )

                    response = contract_termination_check_orders(
                        current_user, instance.contract_termination_request.id
                    )
                    instance.check_response = response
                    instance.save()
                    print(
                        f"Contract termination request check for Order {instance.pk} executed."
                    )
                if instance.supply_point:
                    cut_supply_token = ConfigProject.objects.get(
                        token="supply_point_status_cut_token"
                    ).value
                    pass
                if instance.connection:
                    pass
                if instance.connection_request:
                    try:
                        order_type_install_connection_token = ConfigProject.objects.get(
                            token="order_type_install_connection_token"
                        ).value
                        if instance.type and instance.type.token == order_type_install_connection_token:
                            connection_request_installed_token = (
                                ConfigProject.objects.get(
                                    token="connection_request_status_installed_token"
                                ).value
                            )
                            connection_request_installed = (
                                ConnectionRequestStatus.objects.get(
                                    token=connection_request_installed_token
                                )
                            )
                            connection = create_connection(
                                instance.connection_request.id
                            )

                            instance.check_response = {
                                "message": f"Instal·lació d'escomesa {connection.token} finalitzada correctament.",
                                "status": "success",
                            }
                            instance.save()

                            instance.connection_request.status = (
                                connection_request_installed
                            )
                            instance.connection_request.save()
                            print("saved connection request")
                    except Exception as e:
                        print(f"Error creating connection: {e}")

            finally:
                order_save_flag = False # Reset the flag after the function execution
        
        
        
        


# RabbitMQ Integration - Publish event on order creation
@receiver(post_save, sender=Order)
def publish_order_created_event(sender, instance, created, **kwargs):
    """
    Publica esdeveniment RabbitMQ quan es crea una Order.
    """
    from django.conf import settings

    if not created:
        config = ConfigProject.objects.filter(token="for_validate_order_status_token").first()
        if config:
            to_validate_status_token = config.value
        else:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(
                "ConfigProject for 'for_validate_order_status_token' not found. Using '2' as default. This may not work well."
            )
            to_validate_status_token = "2"
        # Create notification when status changes to the configured token (or '2' if not found)
        if instance.status and str(instance.status.token) == str(to_validate_status_token):
            # Use Celery task to create notification asynchronously
            from .tasks import create_order_status_notification
            try:
                create_order_status_notification.delay(
                    order_id=instance.pk,
                    order_token=instance.token,
                    status_name=instance.status.name,
                )
            except Exception as e:
                print(f"Error creating order status notification: {e}")
            
    
    
    if not settings.RABBITMQ_ENABLED:
        return

    if created:
        from .services.rabbit import publish_order_created
        try:
            transaction.on_commit(lambda: publish_order_created(instance))
        except Exception as e:
            print(f"Error publishing RabbitMQ created event for order {instance.pk}: {e}")


@receiver(post_save, sender=OrderObservation)
def publish_observation_created_event(sender, instance, created, **kwargs):
    """
    Publica esdeveniment RabbitMQ quan es crea una OrderObservation.
    """
    from django.conf import settings

    if not settings.RABBITMQ_ENABLED:
        return

    skip_signal = getattr(instance, "_skip_signal", False)
    print(f"skip_signal for OrderObservation {instance.pk}: {skip_signal}")
    if skip_signal:
        return
        
    if created:
        from .services.rabbit import publish_observation_created
        try:
            publish_observation_created(instance)
        except Exception as e:
            print(f"Error publishing RabbitMQ created event for observation {instance.pk}: {e}")
    
