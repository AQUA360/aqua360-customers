import datetime
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.db import transaction
from django.db.models import Case, When, Q, Value, IntegerField, Count, F
from django.utils import timezone
from django.utils.translation import gettext as _
from rest_framework.decorators import permission_classes
from rest_framework.permissions import AllowAny
import json
import uuid
from django.http import HttpResponse
from coredata.models import ConfigProject
from documentmanager.views import DocumentViewSet
from documentmanager.models import Document
from documentmanager.utils.main_utils import upload_document, delete_document
from coredata.utils.language_utils import use_default_language
from got.models import OrderForm, OrderFormSubmission
from got.serializers import OrderGotSerializer

from order.models import Order, OrderStatus, OrderObservation, Operator, OrderType
from order.serializers.order_serializer import OrderSerializer
from lecturapp.decorators import lecturapp_auth_required as token_required
from lecturapp.models import ReadingOperator


# Form Validation Helpers


def ensure_json_list(value):
    """Normalize a JSONField that may be stored as a JSON string instead of a list."""
    if not value:
        return []
    if isinstance(value, str):
        try:
            value = json.loads(value)
            if isinstance(value, str):
                value = json.loads(value)
        except (json.JSONDecodeError, TypeError, ValueError):
            return []
    if isinstance(value, dict):
        return [value]
    if isinstance(value, list):
        return value
    return []


def validate_filled_form(filled_form, order_form_structure):
    """
    Validate that filled_form matches the OrderForm structure.

    Args:
        filled_form: List of dicts with {token, response}
        order_form_structure: List of dicts from OrderForm.structure

    Returns:
        tuple: (is_valid, error_message, validated_form)
    """
    filled_form = ensure_json_list(filled_form)
    order_form_structure = ensure_json_list(order_form_structure)

    if not isinstance(filled_form, list):
        return False, "filled_form must be a list", None

    # Build a map of structure tokens for quick lookup
    structure_map = {field["token"]: field for field in order_form_structure}
    filled_map = {
        field.get("token"): field for field in filled_form if field.get("token")
    }

    # Check all required structure tokens are present in filled_form
    for struct_field in order_form_structure:
        token = struct_field["token"]

        if token not in filled_map:
            return False, f"Missing required field: {token}", None

        filled_field = filled_map[token]
        response = filled_field.get("response")

        # Check required fields have a response
        if struct_field.get("required", False):
            if response is None or response == "":
                return False, f"Field '{token}' is required but has no response", None

    # Check no extra tokens in filled_form
    for filled_field in filled_form:
        token = filled_field.get("token")
        if not token:
            return False, "Each filled_form item must have a 'token'", None
        if token not in structure_map:
            return False, f"Unknown field token: {token}", None
        if "response" not in filled_field:
            return False, f"Field '{token}' must have a 'response' key", None

    # Build validated form with URL for photo fields
    validated_form = []
    for filled_field in filled_form:
        token = filled_field["token"]
        struct_field = structure_map[token]
        response = filled_field.get("response")

        validated_item = {
            "token": token,
            "response": response,
        }

        # For photo fields, if response is a document_id, add the URL
        if struct_field.get("type") == "photo" and response:
            try:
                doc_id = int(response)
                doc = Document.objects.filter(id=doc_id, is_active=True).first()
                if doc:
                    # Use location_url if available, otherwise build view endpoint URL
                    if doc.location_url:
                        validated_item["response_url"] = doc.location_url
                    else:
                        validated_item["response_url"] = (
                            f"/got/orders/view-document/{doc.id}/"
                        )
                else:
                    return False, f"Photo document with id {doc_id} not found", None
            except (ValueError, TypeError):
                # response might already be a URL string, keep as-is
                validated_item["response_url"] = response

        validated_form.append(validated_item)

    return True, None, validated_form


def get_photo_document_ids(filled_form, order_form_structure):
    """
    Extract document IDs from photo fields in filled_form.

    Returns:
        list: List of document IDs
    """
    structure_map = {
        field["token"]: field for field in ensure_json_list(order_form_structure)
    }
    doc_ids = []

    for field in filled_form:
        token = field.get("token")
        response = field.get("response")

        if token and token in structure_map:
            if structure_map[token].get("type") == "photo" and response:
                try:
                    doc_ids.append(int(response))
                except (ValueError, TypeError):
                    pass

    return doc_ids


def cleanup_photo_documents(document_ids):
    """
    Delete photo documents on error.

    Args:
        document_ids: List of document IDs to delete
    """
    for doc_id in document_ids:
        try:
            doc = Document.objects.get(id=doc_id)
            delete_document(doc)
            doc.delete()
        except Document.DoesNotExist:
            pass
        except Exception as e:
            print(f"Error deleting document {doc_id}: {e}")


def get_authenticated_operator(request):
    """Get the authenticated ReadingOperator from the request."""
    return getattr(request, "lecturapp_operator", None)


def get_order_operator(lc_operator):
    """
    Get the Operator linked to the authenticated ReadingOperator.
    Returns None if no Operator is linked.
    """
    try:
        return Operator.objects.get(app_user=lc_operator)
    except Operator.DoesNotExist:
        return None


def build_orders_queryset(base_filter=None, exploitation_id=None):
    """
    Build the base orders queryset with standard annotations and ordering.

    Args:
        base_filter: Optional Q object or dict for filtering

    Returns:
        Annotated and ordered QuerySet of Orders
    """
    queryset = Order.objects.annotate(
        # Use priority position for sorting (default to 0 if null)
        priority_value=Case(
            When(
                priority__position__isnull=False,
                then=F("priority__position"),
            ),
            default=Value(0),
            output_field=IntegerField(),
        ),
        # Create sort key: completed orders go last
        is_completed=Case(
            When(completed_at__isnull=True, then=Value(0)),  # Not completed = 0 (first)
            default=Value(1),  # Completed = 1 (last)
            output_field=IntegerField(),
        ),
    ).order_by(
        "is_completed",  # 1 Uncompleted orders first
        "dueDateAt",  # 2 Oldest due date first (nulls last by default in PostgreSQL)
        "-priority_value",  # 3 Higher priority first
        "-created_at",  # 4 Newer orders first as tiebreaker
    )

    if base_filter:
        if isinstance(base_filter, Q):
            queryset = queryset.filter(base_filter)
        else:
            queryset = queryset.filter(**base_filter)
    
    if exploitation_id:
        queryset = queryset.filter(
            Q(contract__supply_point_default__connection__exploitation__id=exploitation_id) |
            Q(contract_request__supply_point_default__connection__exploitation__id=exploitation_id) |
            Q(supply_point__connection__exploitation__id=exploitation_id) |
            Q(connection__exploitation__id=exploitation_id) |
            Q(connection_request__exploitation__id=exploitation_id) |
            Q(address__city__exploitations__id=exploitation_id) |
            Q(claim_request__payments__contract__supply_point_default__connection__exploitation__id=exploitation_id)
            )
    return queryset


def paginate_queryset(queryset, request):
    """
    Apply pagination to a queryset based on request parameters.

    Args:
        queryset: The QuerySet to paginate
        request: The HTTP request containing pagination params

    Returns:
        tuple: (paginated_queryset, pagination_metadata)
    """
    try:
        page = int(request.GET.get("page", 1))
        per_page = int(request.GET.get("per_page", 20))

        # Validate parameters
        if page < 1:
            page = 1
        if per_page < 1:
            per_page = 20
        if per_page > 100:  # Max limit to prevent abuse
            per_page = 100

    except (ValueError, TypeError):
        page = 1
        per_page = 20

    # Get total count before pagination
    total_count = queryset.count()

    # Calculate pagination
    start_index = (page - 1) * per_page
    end_index = start_index + per_page

    # Apply pagination
    paginated_queryset = queryset[start_index:end_index]

    # Calculate total pages
    total_pages = (total_count + per_page - 1) // per_page if total_count > 0 else 0

    pagination_metadata = {
        "total": total_count,
        "page": page,
        "per_page": per_page,
        "total_pages": total_pages,
        "has_next": page < total_pages,
        "has_previous": page > 1,
    }

    return paginated_queryset, pagination_metadata


@permission_classes([AllowAny])
@token_required
def operator_orders(request):
    """
    Get orders with filtering by operator assignment.

    Query Parameters:
        - lecture_user_id: Filter by specific ReadingOperator ID
        - unassigned: If 'true', return orders with no operators assigned
        - page: Page number (default: 1)
        - per_page: Items per page (default: 20, max: 100)

    Default behavior: Returns orders assigned to the authenticated operator.
    """
    lc_operator = get_authenticated_operator(request)
    order_operator = get_order_operator(lc_operator)

    if not order_operator:
        return JsonResponse(
            {
                "success": True,
                "orders": [],
                "total": 0,
                "page": 1,
                "per_page": 20,
                "total_pages": 0,
                "has_next": False,
                "has_previous": False,
                "message": "No operator profile found for this operator",
            }
        )

    # Parse filter parameters
    lecture_user_id = request.GET.get("lecture_user_id")
    unassigned = request.GET.get("unassigned", "").lower() == "true"
    
    cancelled_status = ConfigProject.objects.get(token='order_status_cancelled_token').value
    draft_status = ConfigProject.objects.get(token='order_status_draft_token').value
    
    # Build the filter based on parameters
    if unassigned:
        # Return orders with no operators assigned
        orders = (
            build_orders_queryset().exclude(status__token__in=[draft_status, cancelled_status]).distinct()
            .annotate(operator_count=Count("operators"))
            .filter(operator_count=0)
        )
    elif lecture_user_id:
        # Filter by specific lecture user
        try:
            target_operator = Operator.objects.get(app_user_id=lecture_user_id)
            orders = build_orders_queryset({"operators": target_operator}).exclude(status__token__in=[draft_status, cancelled_status]).distinct()
        except Operator.DoesNotExist:
            return JsonResponse(
                {
                    "success": False,
                    "message": f"No operator found for lecture user ID {lecture_user_id}",
                },
                status=404,
            )
    else:
        # Default: filter by authenticated operator
        orders = build_orders_queryset({"operators": order_operator}).exclude(status__token__in=[draft_status, cancelled_status]).distinct()

    # Apply pagination
    paginated_orders, pagination = paginate_queryset(orders, request)
    serializer = OrderGotSerializer(paginated_orders, many=True)

    return JsonResponse(
        {
            "success": True,
            "orders": serializer.data,
            **pagination,
        }
    )


@permission_classes([AllowAny])
@token_required
def operator_orders_list(request):
    """
    Get orders with filtering by operator assignment.

    Query Parameters:
        - lecture_user_id: Filter by specific ReadingOperator ID
        - unassigned: If 'true', return orders with no operators assigned
        - page: Page number (default: 1)
        - per_page: Items per page (default: 20, max: 100)

    Default behavior: Returns orders assigned to the authenticated operator.
    """
    lc_operator = get_authenticated_operator(request)
    order_operator = get_order_operator(lc_operator)
    
    if not order_operator:
        return JsonResponse(
            {
                "success": True,
                "orders": [],
                "total": 0,
                "page": 1,
                "per_page": 20,
                "total_pages": 0,
                "has_next": False,
                "has_previous": False,
                "message": "No operator profile found for this operator",
            }
        )

    # Parse filter parameters
    lecture_user_id = request.GET.get("lecture_user_id")
    unassigned = request.GET.get("unassigned", "").lower() == "true"
    exploitation_id = request.GET.get("exploitation", "")
    show_pending = request.GET.get("show_pending", "").lower() == "true"
    show_completed = request.GET.get("show_completed", "").lower() == "true"
    order_cancelled_token = ConfigProject.objects.get(token='order_status_cancelled_token').value
    
    if exploitation_id == "":
        exploitation_id = None

    # Build the filter based on parameters
    if unassigned:
        # Return orders with no operators assigned
        orders = (
            build_orders_queryset(exploitation_id=exploitation_id)
            .annotate(operator_count=Count("operators"))
            .filter(operator_count=0).exclude(status__token=order_cancelled_token).distinct()
        )
    elif lecture_user_id:
        # Filter by specific lecture user
        try:
            target_operator = Operator.objects.get(app_user_id=lecture_user_id)
            orders = build_orders_queryset({"operators": target_operator}, exploitation_id=exploitation_id).exclude(status__token=order_cancelled_token).distinct()
        except Operator.DoesNotExist:
            return JsonResponse(
                {
                    "success": False,
                    "message": f"No operator found for lecture user ID {lecture_user_id}",
                },
                status=404,
            )
    else:
        # Default: all orders
        orders = build_orders_queryset(exploitation_id=exploitation_id).exclude(status__token=order_cancelled_token).distinct()
    
    
    total_completed_orders = orders.filter(is_completed=True).count()
    total_pending_orders = orders.filter(is_completed=False).count()
    if not show_pending:
        orders = orders.filter(is_completed=True)
    if not show_completed:
        orders = orders.filter(is_completed=False)

    # Apply pagination
    paginated_orders, pagination = paginate_queryset(orders, request)
    serializer = OrderGotSerializer(paginated_orders, many=True)

    return JsonResponse(
        {
            "success": True,
            "orders": serializer.data,
            "total_completed_orders": total_completed_orders,
            "total_pending_orders": total_pending_orders,
            **pagination,
        }
    )
    
    
@permission_classes([AllowAny])
@token_required
def exploitations(request):
    from service.serializers.exploitation_serializer import ExploitationSerializer
    from service.models import Exploitation
    """
    Get exploitations
    """
    lc_operator = get_authenticated_operator(request)
    order_operator = get_order_operator(lc_operator)

    if not order_operator:
        return JsonResponse(
            {
                "success": True,
                "orders": [],
                "total": 0,
                "page": 1,
                "per_page": 20,
                "total_pages": 0,
                "has_next": False,
                "has_previous": False,
                "message": "No operator profile found for this operator",
            }
        )

    exploitations = Exploitation.objects.all()

    # Apply pagination
    paginated_exploitations, pagination = paginate_queryset(exploitations, request)
    exploitations_serialized = ExploitationSerializer(paginated_exploitations, many=True)

    return JsonResponse(
        {
            "success": True,
            "exploitations": exploitations_serialized.data,
            **pagination,
        }
    )


@permission_classes([AllowAny])
@token_required
def order_detail(request, order_id):
    """Get detailed information about a specific order"""
    lc_operator = get_authenticated_operator(request)
    order_operator = get_order_operator(lc_operator)

    if not order_operator:
        return JsonResponse(
            {"success": False, "message": "No operator profile found"}, status=403
        )

    # Allow viewing any order (not just assigned to current operator)
    order = get_object_or_404(Order, id=order_id)
    serializer = OrderGotSerializer(order)

    return JsonResponse({"success": True, "order": serializer.data})


@permission_classes([AllowAny])
@token_required
def get_order_form(request, order_id):
    """
    Get the OrderForm structure for a specific order.

    This endpoint returns the form structure that should be filled when
    creating a report for this order. If the order type doesn't have a
    form, returns null for form_structure.

    Response:
        {
            "success": true,
            "has_form": true,
            "form": {
                "id": 1,
                "name": "Formulari inspecció",
                "structure": [
                    {"name": "Foto anterior", "type": "photo", "token": "foto_anterior", "required": true},
                    {"name": "Observacions", "type": "text", "token": "observacions", "required": false}
                ]
            }
        }
    """
    lc_operator = get_authenticated_operator(request)
    order_operator = get_order_operator(lc_operator)

    if not order_operator:
        return JsonResponse(
            {"success": False, "message": "No operator profile found"}, status=403
        )

    order = get_object_or_404(Order, id=order_id)

    order_form = None
    if order.type:
        order_form = OrderForm.objects.filter(order_type=order.type).first()

    if order_form:
        return JsonResponse(
            {
                "success": True,
                "has_form": True,
                "form": {
                    "id": order_form.id,
                    "name": order_form.name,
                    "structure": ensure_json_list(order_form.structure),
                },
            }
        )
    else:
        return JsonResponse({"success": True, "has_form": False, "form": None})


# =============================================================================
# Lecture User Management Endpoints
# =============================================================================


@permission_classes([AllowAny])
@token_required
def order_lecture_users(request):
    """
    Get all available lecture users (ReadingOperators) that have an associated Operator.

    This endpoint returns all users that can be assigned to orders.
    Only active users with a linked Operator profile are returned.

    Returns:
        List of lecture users with their basic info and operator status.
    """
    lc_operator = get_authenticated_operator(request)
    order_operator = get_order_operator(lc_operator)

    if not order_operator:
        return JsonResponse(
            {"success": False, "message": "No operator profile found"}, status=403
        )

    # Get all active ReadingOperators that have an associated Operator
    # Note: 'operator' is a reverse FK relation, so we use prefetch_related instead of select_related
    lecture_users = ReadingOperator.objects.filter(is_active=True).prefetch_related(
        "operator_set"
    )

    users_data = []
    for user in lecture_users:
        # Get the operator linked to this ReadingOperator
        operator = Operator.objects.filter(app_user=user).first()
        if operator:
            users_data.append(
                {
                    "id": user.id,
                    "name": user.name,
                    "surname": user.surname,
                    "username": user.username,
                    "full_name": f"{user.name} {user.surname}".strip(),
                    "operator_id": operator.id,
                    "operator_token": operator.token,
                    "is_current_user": user.id == lc_operator.id,
                }
            )

    return JsonResponse(
        {
            "success": True,
            "lecture_users": users_data,
            "total": len(users_data),
        }
    )


@permission_classes([AllowAny])
@token_required
def assign_lecture_user(request, order_id):
    """
    Assign or deassign lecture users (operators) to/from an order.

    This endpoint allows:
    - Assigning the current user to an order
    - Assigning another lecture user to an order
    - Deassigning all operators (making the order unassigned)
    - Adding multiple operators to an order

    Methods:
        POST: Assign/deassign operators

    Request Body (JSON):
        - action: "assign" | "deassign" | "set"
            - "assign": Add operator(s) to existing assignments
            - "deassign": Remove specific operator(s) from the order
            - "set": Replace all operators with the specified ones
        - lecture_user_id: ID of the ReadingOperator to assign (optional for deassign all)
        - lecture_user_ids: List of ReadingOperator IDs (for multiple assignments)

    Examples:
        Assign self: {"action": "assign"}  # assigns current user
        Assign specific: {"action": "assign", "lecture_user_id": 5}
        Assign multiple: {"action": "assign", "lecture_user_ids": [1, 2, 3]}
        Deassign self: {"action": "deassign"}
        Deassign specific: {"action": "deassign", "lecture_user_id": 5}
        Deassign all: {"action": "set", "lecture_user_ids": []}
        Replace all: {"action": "set", "lecture_user_ids": [1, 2]}
    """
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    lc_operator = get_authenticated_operator(request)
    order_operator = get_order_operator(lc_operator)

    if not order_operator:
        return JsonResponse(
            {"success": False, "message": "No operator profile found"}, status=403
        )

    # Get the order - any operator can modify assignments
    order = get_object_or_404(Order, id=order_id)

    # Parse request body
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse(
            {"success": False, "message": "Invalid JSON data"}, status=400
        )

    action = data.get("action", "assign")
    lecture_user_id = data.get("lecture_user_id")
    lecture_user_ids = data.get("lecture_user_ids", [])

    # Validate action
    if action not in ["assign", "deassign", "set"]:
        return JsonResponse(
            {
                "success": False,
                "message": "Invalid action. Use 'assign', 'deassign', or 'set'",
            },
            status=400,
        )

    with transaction.atomic():
        if action == "set":
            # Replace all operators with the specified ones
            if not lecture_user_ids and lecture_user_id is None:
                # Clear all operators
                order.operators.clear()
                return JsonResponse(
                    {
                        "success": True,
                        "message": "All operators removed from order",
                        "order_id": order.id,
                        "assigned_operators": [],
                    }
                )

            # Build list of operator IDs
            target_ids = lecture_user_ids if lecture_user_ids else [lecture_user_id]
            operators_to_set = []

            for uid in target_ids:
                try:
                    target_operator = Operator.objects.get(app_user_id=uid)
                    operators_to_set.append(target_operator)
                except Operator.DoesNotExist:
                    return JsonResponse(
                        {
                            "success": False,
                            "message": f"No operator found for lecture user ID {uid}",
                        },
                        status=404,
                    )

            order.operators.set(operators_to_set)

            return JsonResponse(
                {
                    "success": True,
                    "message": f"Order operators updated successfully",
                    "order_id": order.id,
                    "assigned_operators": [
                        {
                            "operator_id": op.id,
                            "operator_token": op.token,
                            "lecture_user_id": op.app_user_id,
                            "name": (
                                f"{op.name} {op.surname}".strip()
                                if op.name
                                else op.token
                            ),
                        }
                        for op in operators_to_set
                    ],
                }
            )

        elif action == "assign":
            # Add operator(s) to existing assignments
            if not lecture_user_ids and lecture_user_id is None:
                # Default: assign current user
                target_operators = [order_operator]
            else:
                target_ids = lecture_user_ids if lecture_user_ids else [lecture_user_id]
                target_operators = []
                for uid in target_ids:
                    try:
                        target_operator = Operator.objects.get(app_user_id=uid)
                        target_operators.append(target_operator)
                    except Operator.DoesNotExist:
                        return JsonResponse(
                            {
                                "success": False,
                                "message": f"No operator found for lecture user ID {uid}",
                            },
                            status=404,
                        )

            for op in target_operators:
                order.operators.add(op)

            current_operators = list(order.operators.all())

            return JsonResponse(
                {
                    "success": True,
                    "message": f"Operator(s) assigned successfully",
                    "order_id": order.id,
                    "assigned_operators": [
                        {
                            "operator_id": op.id,
                            "operator_token": op.token,
                            "lecture_user_id": op.app_user_id,
                            "name": (
                                f"{op.name} {op.surname}".strip()
                                if op.name
                                else op.token
                            ),
                        }
                        for op in current_operators
                    ],
                }
            )

        elif action == "deassign":
            # Remove operator(s) from the order
            if not lecture_user_ids and lecture_user_id is None:
                # Default: deassign current user
                target_operators = [order_operator]
            else:
                target_ids = lecture_user_ids if lecture_user_ids else [lecture_user_id]
                target_operators = []
                for uid in target_ids:
                    try:
                        target_operator = Operator.objects.get(app_user_id=uid)
                        target_operators.append(target_operator)
                    except Operator.DoesNotExist:
                        return JsonResponse(
                            {
                                "success": False,
                                "message": f"No operator found for lecture user ID {uid}",
                            },
                            status=404,
                        )

            for op in target_operators:
                order.operators.remove(op)

            current_operators = list(order.operators.all())

            return JsonResponse(
                {
                    "success": True,
                    "message": f"Operator(s) removed successfully",
                    "order_id": order.id,
                    "assigned_operators": [
                        {
                            "operator_id": op.id,
                            "operator_token": op.token,
                            "lecture_user_id": op.app_user_id,
                            "name": (
                                f"{op.name} {op.surname}".strip()
                                if op.name
                                else op.token
                            ),
                        }
                        for op in current_operators
                    ],
                }
            )


@permission_classes([AllowAny])
@token_required
def add_order_observation(request, order_id):
    """Add an observation to an order"""
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    lc_operator = get_authenticated_operator(request)
    order_operator = get_order_operator(lc_operator)

    if not order_operator:
        return JsonResponse(
            {"success": False, "message": "No operator profile found"}, status=403
        )

    order = get_object_or_404(Order, id=order_id, operators=order_operator)

    # Parse request body
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse(
            {"success": False, "message": "Invalid JSON data"}, status=400
        )

    observation_text = data.get("observation", "")
    if not observation_text:
        return JsonResponse(
            {"success": False, "message": "Observation text is required"},
            status=400,
        )

    # Create the observation
    OrderObservation.objects.create(
        order=order,
        operator=order_operator,
        observation=f"{observation_text} (by operator {order_operator.token})",
        user=None,  # GOT operators don't have Django user accounts
    )

    return JsonResponse(
        {"success": True, "message": "Observation added successfully"}, status=201
    )


@permission_classes([AllowAny])
@token_required
def finalize_order(request, order_id):
    """Finalize an order (change status to a specified status)"""
    if request.method not in ["PUT", "PATCH", "POST"]:
        return JsonResponse({"error": "Method not allowed"}, status=405)

    lc_operator = get_authenticated_operator(request)
    order_operator = get_order_operator(lc_operator)

    if not order_operator:
        return JsonResponse(
            {"success": False, "message": "No operator profile found"}, status=403
        )

    import datetime
    from order.models import OrderReport

    order = get_object_or_404(Order, id=order_id, operators=order_operator)

    # Check if order has at least one report
    if not OrderReport.objects.filter(order=order).exists():
        return JsonResponse(
            {
                "success": False,
                "message": "Cannot finalize order without at least one report",
            },
            status=400,
        )

    # Parse request body
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse(
            {"success": False, "message": "Invalid JSON data"}, status=400
        )

    observation_text = data.get("observation", None)

    # Update order status
    try:
        from coredata.models import ConfigProject

        completed_status_token = (
            ConfigProject.objects.filter(token="for_validate_order_status_token")
            .first()
        )
        
        if not completed_status_token:
            print("ConfigProject for 'order_stfor_validate_order_status_token' not found or has no value. Using 2")
            completed_status_token = "2"
        else:
            completed_status_token = completed_status_token.value
        
        new_status = OrderStatus.objects.get(token=completed_status_token)
            
        with transaction.atomic():
            order.status = new_status
            order.save()
            order.completed_at = datetime.datetime.now()
            order.save()

            if observation_text:
                OrderObservation.objects.create(
                    order=order,
                    observation=f"{observation_text} (by operator {order_operator.token})",
                    user=None,  # GOT operators don't have Django user accounts
                )

        return JsonResponse(
            {
                "success": True,
                "message": "Order status updated successfully",
                "order": OrderSerializer(order).data,
            }
        )
    except OrderStatus.DoesNotExist:
        return JsonResponse(
            {"success": False, "message": "Invalid status ID"}, status=400
        )


@permission_classes([AllowAny])
@token_required
def add_order_report(request, order_id):
    """
    Create a new order report for the authenticated operator.

    If the order's type has an OrderForm, the request must include a filled_form
    that matches the form structure. Photos should be uploaded first via
    upload-form-photo endpoint and referenced by document_id.

    Validation Rules:
        - start_at and end_at are optional, but if one is provided, both must be provided
        - If order does NOT have a form: observation is required
        - If order has a form: filled_form is required

    Request Body:
        {
            "start_at": "11:05",        // Optional (HH:MM or HH:MM:SS)
            "end_at": "13:05",          // Optional (HH:MM or HH:MM:SS)
            "observation": "text",      // Required if order has no form
            "filled_form": [            // Required only if OrderForm exists for this order type
                {"token": "field_token", "response": "value or document_id"},
                ...
            ]
        }
    """
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    lc_operator = get_authenticated_operator(request)
    order_operator = get_order_operator(lc_operator)

    if not order_operator:
        return JsonResponse(
            {"success": False, "message": "No operator profile found"}, status=403
        )

    from order.models import OrderReport
    from coredata.utils.name_utils import generate_token
    from datetime import datetime, date

    order = get_object_or_404(Order, id=order_id, operators=order_operator)

    # Parse request body
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse(
            {"success": False, "message": "Invalid JSON data"}, status=400
        )

    # Extract fields
    start_at = data.get("start_at")
    end_at = data.get("end_at")
    observation = data.get("observation", "")
    filled_form = data.get("filled_form")

    # Check if this order type has an OrderForm
    order_form = None
    if order.type:
        order_form = OrderForm.objects.filter(order_type=order.type).first()

    # Validation rules:
    # - If order has NO form: observation is required
    # - start_at and end_at are optional, but if one is provided, both must be provided
    if not order_form:
        # No form - observation is required
        if not observation or observation.strip() == "":
            return JsonResponse(
                {
                    "success": False,
                    "message": "Observation is required for orders without a form",
                },
                status=400,
            )

    # Validate time fields - both must be provided if one is provided
    if (start_at and not end_at) or (end_at and not start_at):
        return JsonResponse(
            {
                "success": False,
                "message": "Both start_at and end_at must be provided together",
            },
            status=400,
        )

    # Parse time strings if provided
    start_time = None
    end_time = None
    time_dedicated = None

    if start_at and end_at:
        try:
            from datetime import time

            start_time = (
                datetime.strptime(start_at, "%H:%M:%S").time()
                if len(start_at) == 8
                else datetime.strptime(start_at, "%H:%M").time()
            )
            end_time = (
                datetime.strptime(end_at, "%H:%M:%S").time()
                if len(end_at) == 8
                else datetime.strptime(end_at, "%H:%M").time()
            )
        except ValueError:
            return JsonResponse(
                {
                    "success": False,
                    "message": "Invalid time format. Use HH:MM or HH:MM:SS",
                },
                status=400,
            )

        # Calculate time dedicated in minutes
        today = date.today()
        time_dedicated = (
            datetime.combine(today, end_time) - datetime.combine(today, start_time)
        ).total_seconds() / 60

        if time_dedicated < 0:
            return JsonResponse(
                {"success": False, "message": "end_at must be after start_at"},
                status=400,
            )

        time_dedicated = int(time_dedicated)

    # Validate filled_form if order has a form
    validated_form = None
    photo_document_ids = []

    if order_form:
        # OrderForm exists - filled_form is required
        if not filled_form:
            return JsonResponse(
                {
                    "success": False,
                    "message": "This order type requires a filled_form",
                },
                status=400,
            )

        # Validate filled_form against OrderForm structure
        is_valid, error_msg, validated_form = validate_filled_form(
            filled_form, order_form.structure
        )

        if not is_valid:
            return JsonResponse(
                {"success": False, "message": error_msg},
                status=400,
            )

        # Get photo document IDs for potential cleanup
        photo_document_ids = get_photo_document_ids(filled_form, order_form.structure)

    # Create the order report and submission in a transaction
    try:
        with transaction.atomic():
            # Create the order report
            order_report = OrderReport.objects.create(
                order=order,
                operator=order_operator,
                start_at=start_time,
                end_at=end_time,
                time_dedicated=time_dedicated,
                report_date=date.today(),
                observation=observation,
                token=generate_token(OrderReport),
            )

            # Create OrderFormSubmission if OrderForm exists
            submission = None
            if order_form and validated_form:
                submission = OrderFormSubmission.objects.create(
                    order_report=order_report,
                    filled_form=validated_form,
                )

                # Update photo documents to link to submission
                if photo_document_ids:
                    Document.objects.filter(id__in=photo_document_ids).update(
                        entity="ORDER_FORM_SUBMISSION",
                        entity_id=submission.id,
                    )

        from order.serializers.order_report_serializer import OrderReportSerializer

        serializer = OrderReportSerializer(order_report)

        response_data = {
            "success": True,
            "message": "Order report created successfully",
            "report": serializer.data,
        }

        if submission:
            response_data["form_submission"] = {
                "id": submission.id,
                "filled_form": submission.filled_form,
            }

        return JsonResponse(response_data, status=201)

    except Exception as e:
        # Cleanup photo documents on error
        if photo_document_ids:
            cleanup_photo_documents(photo_document_ids)

        import traceback

        print("ERROR:", str(e))
        print("TRACEBACK:", traceback.format_exc())

        return JsonResponse(
            {"success": False, "message": f"Error creating report: {str(e)}"},
            status=500,
        )


@permission_classes([AllowAny])
@token_required
def upload_form_photo(request, order_id):
    """
    Upload a photo for a form field before creating the order report.

    This endpoint should be called for each photo field BEFORE calling add_order_report.
    The returned document_id should be used as the 'response' value for that field
    in the filled_form array.

    Request: multipart/form-data
        - file: The photo file (required)
        - field_token: The token of the form field this photo is for (required)

    Response:
        {
            "success": true,
            "document_id": 123,
            "url": "https://...",
            "field_token": "foto_anterior"
        }
    """
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    lc_operator = get_authenticated_operator(request)
    order_operator = get_order_operator(lc_operator)

    if not order_operator:
        return JsonResponse(
            {"success": False, "message": "No operator profile found"}, status=403
        )

    from django.conf import settings
    from coredata.utils.name_utils import generate_token

    order = get_object_or_404(Order, id=order_id, operators=order_operator)

    # Validate file is present
    if not request.FILES:
        return JsonResponse(
            {"success": False, "message": "No file provided"},
            status=400,
        )

    # Get file - try 'file' key first, otherwise use first available
    if "file" in request.FILES:
        uploaded_file = request.FILES["file"]
    else:
        file_key = list(request.FILES.keys())[0]
        uploaded_file = request.FILES[file_key]

    # Get field_token from POST data
    field_token = request.POST.get("field_token")
    if not field_token:
        return JsonResponse(
            {"success": False, "message": "field_token is required"},
            status=400,
        )

    # Validate that this order type has an OrderForm with this field token
    order_form = None
    if order.type:
        order_form = OrderForm.objects.filter(order_type=order.type).first()

    if not order_form:
        return JsonResponse(
            {"success": False, "message": "This order type does not have a form"},
            status=400,
        )

    # Check field exists and is a photo type
    field_found = False
    for field in ensure_json_list(order_form.structure):
        if field.get("token") == field_token:
            if field.get("type") != "photo":
                return JsonResponse(
                    {
                        "success": False,
                        "message": f"Field '{field_token}' is not a photo field",
                    },
                    status=400,
                )
            field_found = True
            break

    if not field_found:
        return JsonResponse(
            {
                "success": False,
                "message": f"Field '{field_token}' not found in form structure",
            },
            status=400,
        )

    try:
        # Generate a unique document name with timestamp and UUID
        import os
        from datetime import datetime

        file_ext = os.path.splitext(uploaded_file.name)[1] or ".jpg"
        doc_name = f"{field_token}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{str(uuid.uuid4())[:8]}{file_ext}"

        # Upload document to ORDER entity (will be re-linked to submission later)
        service = settings.DOCUMENT_MANAGER_SERVICES.get("order")
        document = upload_document(
            uploaded_file,
            "ORDER",  # entity
            f"form_photos/{field_token}",  # field
            order.id,  # entity_id
            order.token,  # entity_token
            "",  # folder
            service,  # service
            doc_name,  # document_name
        )

        # Build URL - use location_url if available, otherwise build view endpoint URL
        doc_url = document.location_url
        if not doc_url:
            # Build relative URL to our view-document endpoint
            doc_url = f"/got/orders/view-document/{document.id}/"

        return JsonResponse(
            {
                "success": True,
                "document_id": document.id,
                "url": doc_url,
                "field_token": field_token,
            },
            status=201,
        )

    except Exception as e:
        import traceback

        print("ERROR:", str(e))
        print("TRACEBACK:", traceback.format_exc())
        return JsonResponse(
            {"success": False, "message": f"Error uploading photo: {str(e)}"},
            status=500,
        )


@permission_classes([AllowAny])
@token_required
def remove_form_photo(request, order_id):
    """
    Remove a previously uploaded form photo.

    This endpoint allows the frontend to delete a photo that was uploaded
    via upload-form-photo before the report is created.

    Request: DELETE or POST with JSON body
        {
            "document_id": 123
        }

    Response:
        {
            "success": true,
            "message": "Photo removed successfully"
        }
    """
    if request.method not in ["DELETE", "POST"]:
        return JsonResponse({"error": "Method not allowed"}, status=405)

    lc_operator = get_authenticated_operator(request)
    order_operator = get_order_operator(lc_operator)

    if not order_operator:
        return JsonResponse(
            {"success": False, "message": "No operator profile found"}, status=403
        )

    order = get_object_or_404(Order, id=order_id, operators=order_operator)

    # Parse request body
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse(
            {"success": False, "message": "Invalid JSON data"}, status=400
        )

    document_id = data.get("document_id")
    if not document_id:
        return JsonResponse(
            {"success": False, "message": "document_id is required"},
            status=400,
        )

    try:
        # Find the document - must belong to this order
        document = Document.objects.filter(
            id=document_id,
            entity="ORDER",
            entity_id=order.id,
            is_active=True,
        ).first()

        if not document:
            return JsonResponse(
                {"success": False, "message": "Document not found or not accessible"},
                status=404,
            )

        # Delete the document using the document manager
        delete_document(document)

        # Mark as inactive (soft delete)
        document.is_active = False
        document.save()

        return JsonResponse(
            {
                "success": True,
                "message": "Photo removed successfully",
                "document_id": document_id,
            }
        )

    except Exception as e:
        import traceback

        print("ERROR:", str(e))
        print("TRACEBACK:", traceback.format_exc())
        return JsonResponse(
            {"success": False, "message": f"Error removing photo: {str(e)}"},
            status=500,
        )


@permission_classes([AllowAny])
@token_required
def order_report(request, order_id):
    """Get all reports for a specific order, including filled_form if exists"""
    lc_operator = get_authenticated_operator(request)
    order_operator = get_order_operator(lc_operator)

    if not order_operator:
        return JsonResponse(
            {"success": False, "message": "No operator profile found"}, status=403
        )

    from order.models import OrderReport
    from order.serializers.order_report_serializer import OrderReportSerializer

    # Allow viewing reports for any order (not just assigned to current operator)
    order = get_object_or_404(Order, id=order_id)

    reports = OrderReport.objects.filter(order=order).order_by(
        "-report_date", "-created_at"
    )

    serializer = OrderReportSerializer(reports, many=True)

    # Get OrderForm structure for this order type (if exists)
    order_form = None
    structure_map = {}
    if order.type:
        order_form = OrderForm.objects.filter(order_type=order.type).first()
        if order_form and order_form.structure:
            structure_map = {
                field["token"]: field
                for field in ensure_json_list(order_form.structure)
                if isinstance(field, dict) and field.get("token")
            }

    # Add filled_form to each report that has a submission
    reports_data = serializer.data
    for report_data in reports_data:
        report_id = report_data.get("id")
        if report_id:
            submission = OrderFormSubmission.objects.filter(
                order_report_id=report_id
            ).first()
            if submission and submission.filled_form:
                # Enrich filled_form with structure metadata (name, type, required, etc.)
                enriched_form = []
                for filled_field in ensure_json_list(submission.filled_form):
                    if not isinstance(filled_field, dict):
                        continue
                    token = filled_field.get("token")
                    struct_field = structure_map.get(token, {})

                    resolved_type = filled_field.get("type") or struct_field.get(
                        "type", "text"
                    )

                    enriched_field = {
                        "token": token,
                        "name": filled_field.get("name") or struct_field.get("name", token),
                        "type": resolved_type,
                        "required": struct_field.get(
                            "required", filled_field.get("required", False)
                        ),
                        "response": filled_field.get("response"),
                    }

                    # Add response_url for photo fields
                    if filled_field.get("response_url"):
                        enriched_field["response_url"] = filled_field["response_url"]
                    elif resolved_type == "photo" and filled_field.get(
                        "response"
                    ):
                        # Build URL if not already present
                        try:
                            doc_id = int(filled_field["response"])
                            doc = Document.objects.filter(
                                id=doc_id, is_active=True
                            ).first()
                            if doc:
                                enriched_field["response_url"] = (
                                    doc.location_url
                                    or f"/got/orders/view-document/{doc.id}/"
                                )
                        except (ValueError, TypeError):
                            pass

                    enriched_form.append(enriched_field)

                report_data["filled_form"] = enriched_form
            else:
                report_data["filled_form"] = None

    return JsonResponse({"success": True, "reports": reports_data})


@permission_classes([AllowAny])
@token_required
def add_order_report_document(request, order_id, report_id):
    """Upload a document to an order report"""
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    lc_operator = get_authenticated_operator(request)
    order_operator = get_order_operator(lc_operator)

    if not order_operator:
        return JsonResponse(
            {"success": False, "message": "No operator profile found"}, status=403
        )

    from order.models import OrderReport, OrderReportDocument
    from documentmanager.utils.main_utils import upload_document
    from coredata.utils.name_utils import generate_token
    from django.conf import settings

    try:
        order = get_object_or_404(Order, id=order_id, operators=order_operator)
        order_report = get_object_or_404(
            OrderReport, id=report_id, order=order, operator=order_operator
        )

        if not request.FILES:
            return JsonResponse(
                {
                    "success": False,
                    "message": "No file provided. Make sure to use form-data in Postman and select File type.",
                    "debug": {
                        "files_keys": list(request.FILES.keys()),
                        "content_type": request.content_type,
                    },
                },
                status=400,
            )

        # Get file - try 'file' key first, otherwise use first available
        if "file" in request.FILES:
            uploaded_file = request.FILES["file"]
        else:
            file_key = list(request.FILES.keys())[0]
            uploaded_file = request.FILES[file_key]
            print(f"Using file from key: {file_key}")

        # Upload document using the document manager
        service = settings.DOCUMENT_MANAGER_SERVICES.get("order")
        document = upload_document(
            uploaded_file,
            order.token,
            "ORDER",
            order_report.id,
            order_report.token,
            "",
            service,
            uploaded_file.name,
        )

        # Create the order report document
        order_report_doc = OrderReportDocument.objects.create(
            order_report=order_report,
            file=document,
            token=generate_token(OrderReportDocument),
        )

        from order.serializers.order_report_serializer import (
            OrderReportDocumentSerializer,
        )

        serializer = OrderReportDocumentSerializer(order_report_doc)

        return JsonResponse(
            {
                "success": True,
                "message": "Document uploaded successfully",
                "document": serializer.data,
            },
            status=201,
        )

    except Exception as e:
        import traceback

        print("ERROR:", str(e))
        print("TRACEBACK:", traceback.format_exc())
        return JsonResponse(
            {"success": False, "message": f"Error uploading document: {str(e)}"},
            status=500,
        )


@permission_classes([AllowAny])
def view_document(request, pk):
    """View a document by its primary key - accessible without authentication"""
    from order.models import OrderReportDocument
    from documentmanager.models import Document
    from documentmanager.utils.main_utils import download_document

    # Get the document
    document = get_object_or_404(Document, pk=pk, is_active=True)

    # Allow public access to documents - removed authentication checks
    # This endpoint is now accessible from other applications without authentication
    
    # If all checks pass, download and return the document
    download_info = download_document(document)
    return download_info

@permission_classes([AllowAny])
@token_required
@use_default_language
def get_orders_report(request):
    import openpyxl
    from statistics.views.reports_views import add_row, adjust_column_widths, jump_row, save_report
    """Get orders as report"""
    lc_operator = get_authenticated_operator(request)
    order_operator = get_order_operator(lc_operator)
    

    if not order_operator:
        return JsonResponse(
            {
                "success": True,
                "orders": [],
                "total": 0,
                "page": 1,
                "per_page": 20,
                "total_pages": 0,
                "has_next": False,
                "has_previous": False,
                "message": "No operator profile found for this operator",
            }
        )
        
        
    lecture_user_id = request.GET.get("lecture_user_id")
    unassigned = request.GET.get("unassigned", "").lower() == "true"
    exploitation_id = request.GET.get("exploitation", "")
    show_pending = request.GET.get("show_pending", "").lower() == "true"
    show_completed = request.GET.get("show_completed", "").lower() == "true"
    
    if unassigned:
        # Return orders with no operators assigned
        orders = (
            build_orders_queryset(exploitation_id=exploitation_id)
            .annotate(operator_count=Count("operators"))
            .filter(operator_count=0)
        )
    elif lecture_user_id:
        # Filter by specific lecture user
        try:
            target_operator = Operator.objects.get(app_user_id=lecture_user_id)
            orders = build_orders_queryset({"operators": target_operator}, exploitation_id=exploitation_id)
        except Operator.DoesNotExist:
            return JsonResponse(
                {
                    "success": False,
                    "message": f"No operator found for lecture user ID {lecture_user_id}",
                },
                status=404,
            )
    else:
        # Default: all orders
        orders = build_orders_queryset(exploitation_id=exploitation_id)
    
    if not show_pending:
        orders = orders.filter(is_completed=True)
    if not show_completed:
        orders = orders.filter(is_completed=False)
    
    wb = openpyxl.Workbook()
    sheet = wb.active
    right_now = datetime.datetime.now().strftime('%d%m%Y%H%M%S')
    sheet.title = f"{right_now}"
    
    row = 0
    titles = [_("Ordre"), _("Estat"), _("Data"), _("Finalització"), _("Adreça"), _("Operaris")]
    row = add_row(sheet, row, titles)
    
    def get_order_address(order):
        order_address = ""
        if order.address:
            order_address = str(order.address)
        if not order_address or order_address == "":
            if order.supply_point and order.supply_point.address:
                order_address = str(order.supply_point.address)
        if not order_address or order_address == "":
            if order.contract_request and order.contract_request.supply_point_default and order.contract_request.supply_point_default.address:
                order_address = str(order.contract_request.supply_point_default.address)
            elif order.contract and order.contract.supply_point_default and order.contract.supply_point_default.address:
                order_address = str(order.contract.supply_point_default.address)
            elif order.contract_termination_request and order.contract_termination_request.contract.supply_point_default and order.contract_termination_request.contract.supply_point_default.address:
                order_address = str(order.contract_termination_request.contract.supply_point_default.address)
            elif order.connection or order.connection_request:
                conn = order.connection if order.connection else order.connection_request.connection
                order_address = f"{str(conn.address_street)}, {str(conn.address_street_number)} - {str(conn.address_postal_code)} {str(conn.address_city)}"
        return order_address
    
    for order in orders:
        order_address = get_order_address(order)
        order_row = [
            order.token,
            order.status.name.upper(),
            order.created_at.strftime('%d/%m/%Y'),
            order.completed_at.strftime('%d/%m/%Y') if order.completed_at else "",
            order_address,
        ]
        for operator in order.operators.all():
            order_row.append(f"{operator.name} {operator.surname} ({operator.token})")
        row = add_row(sheet, row, order_row)
    
    adjust_column_widths(sheet)
    
    filename = f"orders_time_{datetime.datetime.now().strftime('%m_%y')}.xlsx"
    
    wb.save(filename)

    with open(filename, "rb") as f:
        response = HttpResponse(f.read(), content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        response["Content-Disposition"] = f"attachment; filename={filename}"
    
    return response
