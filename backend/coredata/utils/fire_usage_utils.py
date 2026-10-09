from coredata.models import ConfigProject


def get_fire_usage_tokens():
    """Returns the list of ContractUseType tokens considered fire hydrant usage.

    The ConfigProject value can hold several tokens separated by commas
    (e.g. 'AV BIE D,AV BIE I') to support clients with more than one
    fire-related use type.
    """
    try:
        raw_value = ConfigProject.objects.get(token='fire_usage_type_token').value
    except ConfigProject.DoesNotExist:
        try:
            raw_value = ConfigProject.objects.get(token='fire_usage_type_id').value
        except ConfigProject.DoesNotExist:
            raw_value = 'inc'

    return [token.strip() for token in (raw_value or '').split(',') if token.strip()]
