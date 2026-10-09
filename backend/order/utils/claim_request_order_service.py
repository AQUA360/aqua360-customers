from datetime import datetime
from django.contrib.auth.models import User
from django.db import transaction

from coredata.utils.name_utils import generate_token

from ..models import Order, OrderType, OrderStatus
from claimrequest.models import ClaimRequest, ClaimRequestPayment

def get_order_type_initials(token: str) -> str:
    """
    Obté les inicials d'un token d'ordre.
    Per exemple:
    - meter_remove -> MR
    - cut_supply -> CS
    
    Args:
        token: El token del tipus d'ordre
        
    Returns:
        str: Les inicials del token
    """
    if not token:
        return ""
    
    # Dividir el token per guions baixos i obtenir la primera lletra de cada paraula
    words = token.split('_')
    initials = ''.join(word[0].upper() for word in words if word)
    
    return initials

def create_orders_from_claim_request(
    claim_request_id: int,
    order_type_token: str,
    action_date: str,
    contracts: list[int],
    user: User
) -> tuple[list[int], str]:
    """
    Crea o actualitza ordres per a tots els contractes associats a un claim request.
    Si ja existeix una ordre amb el mateix claim_request, type i contract, s'actualitza.
    
    Args:
        claim_request_id: ID del claim request
        order_type_token: Token del tipus d'ordre
        action_date: Data d'acció en format YYYY-MM-DD
        user: Usuari que crea les ordres
        
    Returns:
        tuple: (llista d'IDs de les ordres creades/actualitzades, missatge)
        
    Raises:
        OrderType.DoesNotExist: Si el tipus d'ordre no existeix
        ClaimRequest.DoesNotExist: Si el claim request no existeix
        ValueError: Si el format de la data és invàlid
    """
    # Validar i obtenir el tipus d'ordre
    order_type = OrderType.objects.get(token=order_type_token)
    
    # Validar el claim request
    claim_request = ClaimRequest.objects.get(id=claim_request_id)
    
    # Validar la data
    try:
        action_date = datetime.strptime(action_date, '%Y-%m-%d').date()
    except ValueError:
        raise ValueError('Format de data invàlid. Utilitzeu YYYY-MM-DD')
    
    # Obtenir l'estat per defecte
    default_status = OrderStatus.objects.get(is_default=True)
    
    # Obtenir tots els pagaments associats al claim request
    payments = ClaimRequestPayment.objects.filter(
        claim_request=claim_request,
        is_excluded=False,
        contract__id__in=contracts
    ).select_related('contract')

    with transaction.atomic():
        # Obtenir totes les ordres existents en una sola consulta
        existing_orders = {
            (order.claim_request_id, order.type_id, order.contract_id): order
            for order in Order.objects.filter(
                claim_request=claim_request,
                type=order_type,
                #contract__in=[p.contract for p in payments]
            )
        }

        orders_to_create = []
        orders_to_update = []
        created_orders = []

        total_existing_orders = len(existing_orders) + 1
        print("total_existing_orders")
        print(total_existing_orders)
        try:
            for i, payment in enumerate(payments, 1):
                key = (claim_request.id, order_type.id, payment.contract.id)
                if key in existing_orders:
                    print("key in existing_orders")
                    continue
                    # Actualitzar l'ordre existent
                    order = existing_orders[key]
                    order.status = default_status
                    order.is_active = True
                    orders_to_update.append(order)
                    # created_orders.append(order.id)    # NO NEED TO CREATE AGAIN ORDER
                else:
                    print("key not in existing_orders")
                    # Preparar nova ordre
                    #get last order id
                    contract_supply_points = payment.contract.supply_points.all()
                    for sp in contract_supply_points:
                        order = Order.objects.create(
                            token=generate_token(Order, '-id', get_order_type_initials(order_type.token), offset=i),
                            claim_request=claim_request,
                            contract=payment.contract,
                            type=order_type,
                            status=default_status,
                            is_active=True,
                            supply_point=sp
                        )
                        orders_to_create.append(order)
                        created_orders.append(order.id)
                        existing_orders[key] = order
        except Exception as e:
            print(f"Error creating orders: {e}")
            raise Exception(e)
        
        # COMENTAT DEGUT A QUE MOLTES FUNCIONS COM EL RABBIT ES TROBEN ALS SIGNALS
        # Crear totes les noves ordres en una sola operació
        # if orders_to_create:
        #     Order.objects.bulk_create(orders_to_create)

        # Actualitzar totes les ordres existents en una sola operació
        if orders_to_update:
            Order.objects.bulk_update(orders_to_update, ['status', 'is_active'])

    return created_orders, f"S'han creat/actualitzat {len(created_orders)} ordres" 