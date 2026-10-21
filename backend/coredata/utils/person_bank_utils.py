import unicodedata

# El SEPA no exigeix el document del titular del compte i de vegades el mandat
# arriba sense. Aquest és el valor genèric que es fa servir en aquests casos.
DEFAULT_HOLDER_DNI = '99999999R'


def _normalize_name(value):
    text = unicodedata.normalize('NFKD', str(value or ''))
    text = ''.join(ch for ch in text if not unicodedata.combining(ch))
    return ' '.join(text.upper().split())


def _person_full_name(person):
    if person.is_juridic:
        return person.name
    return ' '.join(part for part in (person.name, person.surname) if part)


def resolve_holder_dni(dni, holder_name, person):
    """
    DNI a desar en un PersonBank.

    Si arriba informat, es manté. Si és buit:
    - el titular és la mateixa persona del compte (o no s'ha indicat titular):
      el document de la persona;
    - el titular és una altra persona: DEFAULT_HOLDER_DNI.
    """
    dni = (dni or '').strip()
    if dni:
        return dni
    if person is None:
        return DEFAULT_HOLDER_DNI
    name = _normalize_name(holder_name)
    same_holder = not name or name == _normalize_name(_person_full_name(person))
    if same_holder and person.token:
        return person.token
    return DEFAULT_HOLDER_DNI


def fill_holder_dni(bank_data, person=None):
    """Aplica `resolve_holder_dni` a un dict de dades de PersonBank (el modifica)."""
    person = person or bank_data.get('person')
    bank_data['dni'] = resolve_holder_dni(bank_data.get('dni'), bank_data.get('name'), person)
    return bank_data
