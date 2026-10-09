import json
import logging
import pika
import time
from django.core.management.base import BaseCommand
from django.conf import settings
from django.db import close_old_connections
from order.services.consumer import process_message

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Consume messages from the instance gmao-events queue"

    def handle(self, *args, **options):
        if not settings.RABBITMQ_ENABLED:
            self.stdout.write(self.style.WARNING("RabbitMQ is disabled. Exiting..."))
            return

        reconnect_delay = 1
        max_reconnect_delay = 30

        while True:
            connection = None
            try:
                self.stdout.write(self.style.SUCCESS("Connecting to RabbitMQ..."))
                self.stdout.write(f"  URL: {settings.RABBITMQ_URL}")
                self.stdout.write(f"  Instance UID: {settings.INSTANCE_UID or '(not set)'}")
                self.stdout.write(f"  Exchange: {settings.RABBIT_IN_EXCHANGE}")
                self.stdout.write(f"  Queue: {settings.RABBIT_IN_QUEUE}")
                self.stdout.write(f"  Routing key: {settings.RABBIT_IN_ROUTING_KEY}")

                # Connect using Pika
                parameters = pika.URLParameters(settings.RABBITMQ_URL)
                parameters.heartbeat = 600
                parameters.blocked_connection_timeout = 600
                connection = pika.BlockingConnection(parameters)
                channel = connection.channel()

                # Names
                dlx_name = "failed-message-exchange"
                if settings.INSTANCE_UID:
                    dlq_name = f"failed-message-queue-{settings.INSTANCE_UID}"
                    dlx_routing_key = f"failed-{settings.INSTANCE_UID}"
                else:
                    dlq_name = "failed-message-queue"
                    dlx_routing_key = "failed"

                # Declare the Dead Letter Exchange
                channel.exchange_declare(exchange=dlx_name, exchange_type="direct", durable=True)

                # Declare the Dead Letter Queue
                channel.queue_declare(queue=dlq_name, durable=True)

                # Bind the Queue to the Exchange
                channel.queue_bind(exchange=dlx_name, queue=dlq_name, routing_key=dlx_routing_key)

                # Declare the inbound exchange (creates it if it doesn't exist)
                channel.exchange_declare(
                    exchange=settings.RABBIT_IN_EXCHANGE,
                    exchange_type="direct",
                    durable=True,
                )

                # Declare the queue (creates if doesn't exist)
                channel.queue_declare(
                    queue=settings.RABBIT_IN_QUEUE,
                    durable=True,
                    arguments={
                        "x-dead-letter-exchange": dlx_name,
                        "x-dead-letter-routing-key": dlx_routing_key,
                    },
                )

                # Bind the queue with the instance UID (or the queue name) as routing key
                channel.queue_bind(
                    exchange=settings.RABBIT_IN_EXCHANGE,
                    queue=settings.RABBIT_IN_QUEUE,
                    routing_key=settings.RABBIT_IN_ROUTING_KEY,
                )

                self.stdout.write(
                    self.style.SUCCESS(
                        f"Connected! Listening on '{settings.RABBIT_IN_QUEUE}' "
                        f"bound to '{settings.RABBIT_IN_EXCHANGE}' "
                        f"with routing key '{settings.RABBIT_IN_ROUTING_KEY}'..."
                    )
                )
                self.stdout.write("Press CTRL+C to exit.\n")

                # Reset reconnect delay on successful connection
                reconnect_delay = 1

                def callback(ch, method, properties, body):
                    """Called when a message is received."""
                    # Close stale or idle database connections before processing.
                    close_old_connections()
                    try:
                        payload = json.loads(body.decode("utf-8"))
                        self.stdout.write(self.style.HTTP_INFO("=" * 60))
                        self.stdout.write(
                            self.style.SUCCESS(
                                f"[RECEIVED] Message from '{settings.RABBIT_IN_QUEUE}'"
                            )
                        )
                        self.stdout.write(f"Routing Key: {method.routing_key}")
                        self.stdout.write("Payload:")
                        self.stdout.write(
                            json.dumps(payload, indent=2, default=str, ensure_ascii=False)
                        )
                        self.stdout.write(self.style.HTTP_INFO("=" * 60))

                        # Process the message.

                        result = process_message(payload)
                        self.stdout.write(
                            self.style.SUCCESS(f"[PROCESSED] Result: {result}")
                        )

                        # Acknowledge the message (guard against a closed channel:
                        # if the connection dropped mid-processing, skip the ack so
                        # the broker redelivers the message on reconnect).
                        if ch.is_open:
                            ch.basic_ack(delivery_tag=method.delivery_tag)
                            self.stdout.write(
                                self.style.SUCCESS("[ACK] Message acknowledged\n")
                            )
                        else:
                            self.stdout.write(
                                self.style.WARNING(
                                    "[SKIP] Channel closed before ack; "
                                    "message will be redelivered\n"
                                )
                            )

                    except json.JSONDecodeError as e:
                        self.stdout.write(
                            self.style.ERROR(f"[ERROR] Failed to decode JSON: {e}")
                        )
                        self.stdout.write(f"Raw body: {body!r}")
                        self.stdout.write(self.style.ERROR("[NACK] Message rejected\n"))
                        if ch.is_open:
                            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
                    except Exception as e:
                        self.stdout.write(
                            self.style.ERROR(f"[ERROR] Processing failed: {e}")
                        )
                        logger.exception("Processing failed; dead-lettering message")
                        self.stdout.write(self.style.ERROR("[NACK] Message rejected\n"))
                        if ch.is_open:
                            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
                    finally:
                        # Release DB connections held during processing.
                        close_old_connections()

                # Set up consumer
                channel.basic_qos(prefetch_count=1)
                channel.basic_consume(
                    queue=settings.RABBIT_IN_QUEUE,
                    on_message_callback=callback,
                    auto_ack=False,
                )

                # Start consuming (blocking)
                channel.start_consuming()

            except KeyboardInterrupt:
                self.stdout.write(self.style.WARNING("\nShutting down..."))
                if connection and connection.is_open:
                    connection.close()
                break
            except (pika.exceptions.AMQPConnectionError, pika.exceptions.ConnectionClosedByBroker) as e:
                self.stdout.write(self.style.ERROR(f"Connection failed or closed: {e}"))
            except pika.exceptions.AMQPChannelError as e:
                self.stdout.write(self.style.ERROR(f"Channel error: {e}"))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Unexpected error: {e}"))
                logger.exception("Unexpected error in RabbitMQ consumer")

            # If we reached here without a break, it means an error occurred
            if connection and connection.is_open:
                try:
                    connection.close()
                except Exception:
                    pass
                
            self.stdout.write(f"Attempting to reconnect in {reconnect_delay} seconds...")
            time.sleep(reconnect_delay)
            reconnect_delay = min(reconnect_delay * 2, max_reconnect_delay)