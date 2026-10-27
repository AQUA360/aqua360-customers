from django.db import transaction


@transaction.atomic
def get_or_create_dictionary_value(model, name, **filters):
    normalized_name = (name or '').strip()
    if not normalized_name:
        raise ValueError('The dictionary value cannot be empty.')

    lookup = {**filters, 'name__iexact': normalized_name}
    value = model.objects.filter(**lookup).order_by('id').first()
    if value:
        return value

    return model.objects.create(name=normalized_name, **filters)
