import uuid

from django.db import IntegrityError, transaction


def normalize_dictionary_name(model, name):
    """Valida i normalitza (trim) el nom d'un valor de diccionari de comptadors."""
    if not isinstance(name, str):
        raise ValueError('The dictionary value must be a string.')
    normalized_name = name.strip()
    if not normalized_name:
        raise ValueError('The dictionary value cannot be empty.')
    max_length = model._meta.get_field('name').max_length
    if len(normalized_name) > max_length:
        raise ValueError(f'The dictionary value cannot exceed {max_length} characters.')
    return normalized_name


@transaction.atomic
def get_or_create_dictionary_value(model, name, **filters):
    normalized_name = normalize_dictionary_name(model, name)

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


def _meter_field_for(instance):
    from service.models import MeterCommTechnology, MeterManufacturer, MeterModel

    if isinstance(instance, MeterManufacturer):
        return 'manufacturer'
    if isinstance(instance, MeterModel):
        return 'model'
    if isinstance(instance, MeterCommTechnology):
        return 'comm_technology'
    raise TypeError(f'Unsupported meter dictionary model: {type(instance).__name__}')


def meters_using(instance, name=None):
    """Comptadors que fan servir (sense distingir majúscules) el valor de diccionari.

    El text del comptador es compara retallat: un valor desat com " Kamstrup "
    correspon a l'entrada de diccionari "Kamstrup".
    """
    from django.db.models import Q
    from django.db.models.functions import Trim
    from service.models import Meter, MeterModel

    name = instance.name if name is None else name
    name = name.strip() if isinstance(name, str) else ''
    if not name:
        return Meter.objects.none()

    field = _meter_field_for(instance)
    meters = Meter.objects.annotate(_dict_value=Trim(field)).filter(_dict_value__iexact=name)
    if isinstance(instance, MeterModel):
        meters = meters.annotate(_dict_manufacturer=Trim('manufacturer'))
        if instance.manufacturer_id:
            manufacturer_name = instance.manufacturer.name or ''
            meters = meters.filter(_dict_manufacturer__iexact=manufacturer_name.strip())
        else:
            meters = meters.filter(Q(manufacturer__isnull=True) | Q(_dict_manufacturer=''))
    return meters


def collect_meters_to_rename(instance):
    """Snapshot (id, valor actual) dels comptadors afectats abans de canviar el nom."""
    field = _meter_field_for(instance)
    return field, list(meters_using(instance).values_list('id', field))


def apply_meter_rename(field, affected, new_name, user=None):
    """Propaga el nou nom als comptadors afectats i en deixa traça a MeterLog."""
    from service.models import Meter, MeterLog

    if not affected:
        return 0

    Meter.objects.filter(id__in=[meter_id for meter_id, _ in affected]).update(**{field: new_name})

    operation_token = str(uuid.uuid4())
    MeterLog.objects.bulk_create([
        MeterLog(
            meter_id=meter_id,
            field_name=field,
            old_value=old_value,
            new_value=new_name,
            operation_token=operation_token,
            user=user,
        )
        for meter_id, old_value in affected
        if old_value != new_name
    ])
    return len(affected)


@transaction.atomic
def rename_dictionary_value(instance, new_name, user=None):
    """
    Canvia el nom d'un valor de diccionari i propaga el nou nom al text dels
    comptadors que el fan servir. Retorna el nombre de comptadors actualitzats.
    """
    persisted = type(instance).objects.select_for_update().get(pk=instance.pk)
    field, affected = collect_meters_to_rename(persisted)
    instance.name = new_name
    instance.save(update_fields=['name'])
    return apply_meter_rename(field, affected, new_name, user=user)
