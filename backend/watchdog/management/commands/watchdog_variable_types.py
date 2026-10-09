import re
from collections import Counter

from billing.models import MessageCondition
from contract.models import VariableType
from pricing.models import AdjustmentCondition

VARIABLE_REFERENCE_PREFIX = "variable."
VARIABLE_FORMULA_PATTERN = re.compile(r"%variable\.([A-Za-z0-9_-]+)")


def variable_type_token_counts():
    return Counter(VariableType.objects.values_list("token", flat=True))


def validate_variable_token(token, token_counts):
    if not token:
        return "Token buit després de 'variable.'"
    count = token_counts.get(token, 0)
    if count == 0:
        return f"VariableType amb token '{token}' no existeix"
    if count > 1:
        return f"Existeixen {count} VariableType amb token '{token}'"
    return None


def extract_variable_references(condition):
    references = []

    quantity = condition.quantity
    if isinstance(quantity, dict):
        value = quantity.get("value")
        if isinstance(value, str) and value.startswith(VARIABLE_REFERENCE_PREFIX):
            token = value[len(VARIABLE_REFERENCE_PREFIX) :]
            references.append(("quantity", value, token))

    formula = condition.formula
    if formula:
        for match in VARIABLE_FORMULA_PATTERN.finditer(formula):
            references.append(("formula", match.group(0), match.group(1)))

    return references


def format_adjustment_condition_issue(condition, source, reference, token, reason):
    adjustment = condition.adjustment
    line_item_type = adjustment.line_item_type if adjustment else None

    billing_range = (
        line_item_type.billing_range
        if line_item_type
        else None
    )

    price_rate = (
        billing_range.price_rate
        if billing_range
        else None
    )

    return "\n".join([
        (
            f"LineItemType: {line_item_type.name or 'N/A'} ({line_item_type.token})"
            if line_item_type
            else "LineItemType: N/A"
        ),
        (
            f"PriceRate: {price_rate.name} ({price_rate.token})"
            if price_rate
            else "PriceRate: N/A"
        ),
        (
            f"Adjustment: {adjustment.name} ({adjustment.token})"
            if adjustment
            else "Adjustment: N/A"
        ),
        f"Condition: {condition.name} (ID {condition.id})",
        f"Camp: {source}",
        f"Referència: {reference}",
        f"VariableType: {token}",
        f"Error: {reason}",
    ])


def format_message_condition_issue(condition, source, reference, token, reason):
    message_label = condition.message_id or "N/A"
    if condition.message and condition.message.title:
        message_label = f"{condition.message_id} ({condition.message.title!r})"
    return "\n".join([
    f"Message: {message_label}",
    f"Condition: {condition.name} (ID {condition.id})",
    f"Camp: {source}",
    f"Referència: {reference}",
    f"VariableType: {token}",
    f"Error: {reason}",
])


def check_condition_variable_type_references():
    """
    Comprova que totes les referències variable.* als condicionals
    (AdjustmentCondition i MessageCondition) apuntin a un VariableType existent.
    """
    issues = []
    token_counts = variable_type_token_counts()

    for condition in AdjustmentCondition.objects.select_related(
    "adjustment",
    "adjustment__line_item_type",
    "adjustment__line_item_type__billing_range",
    "adjustment__line_item_type__billing_range__price_rate",
    ).iterator(
        chunk_size=200
    ):
        for source, reference, token in extract_variable_references(condition):
            reason = validate_variable_token(token, token_counts)
            if reason:
                issues.append(
                    format_adjustment_condition_issue(
                        condition, source, reference, token, reason
                    )
                )

    for condition in MessageCondition.objects.select_related("message").iterator(
        chunk_size=200
    ):
        for source, reference, token in extract_variable_references(condition):
            reason = validate_variable_token(token, token_counts)
            if reason:
                issues.append(
                    format_message_condition_issue(
                        condition, source, reference, token, reason
                    )
                )

    return issues
