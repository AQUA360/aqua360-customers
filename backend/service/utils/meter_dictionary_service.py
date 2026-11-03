from django.db import IntegrityError, transaction


@transaction.atomic
def get_or_create_dictionary_value(model, name, **filters):
    if not isinstance(name, str):
        raise ValueError('The dictionary value must be a string.')
    normalized_name = name.strip()
    if not normalized_name:
        raise ValueError('The dictionary value cannot be empty.')
    max_length = model._meta.get_field('name').max_length
    if len(normalized_name) > max_length:
        raise ValueError(f'The dictionary value cannot exceed {max_length} characters.')

    lookup = {**filters, 'name__iexact': normalized_name}
    value = model.objects.filter(**lookup).order_by('id').first()
    if value:
        return value, False

    try:
        with transaction.atomic():
            return model.objects.create(name=normalized_name, **filters), True
    except IntegrityError:
        value = model.objects.filter(**lookup).order_by('id').first()
        if value is None:
            raise
        return value, False
