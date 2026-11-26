from django_filters import rest_framework as filters
from coredata.models import Person, PersonBank, PersonContact
from coredata.utils.phone_utils import phone_digits_expression, phone_search_digits
from unidecode import unidecode
from django.db.models import Exists, OuterRef, Q, Value
from django.db.models.functions import Replace
from urllib.parse import unquote
import re
from functools import reduce
from operator import and_

class PersonFilter(filters.FilterSet):
    search = filters.CharFilter(method='filter_search')
    is_juridic = filters.BooleanFilter(field_name='is_juridic')
    # Persones amb un procés d'insolvència obert (true) o sense (false)
    insolvency = filters.BooleanFilter(method='filter_insolvency')
    # Cerca per email, telèfon o IBAN de la persona, amb els mateixos criteris
    # que els filtres homòlegs de la llista de contractes
    search_email = filters.CharFilter(method='filter_email')
    search_phone = filters.CharFilter(method='filter_phone')
    search_iban = filters.CharFilter(method='filter_iban')

    class Meta:
        model = Person
        fields = ['search', 'is_juridic', 'insolvency']

    def filter_insolvency(self, queryset, name, value):
        if value is None:
            return queryset
        from billing.models import InsolvencyProcess
        open_person_ids = InsolvencyProcess.objects.filter(
            status=InsolvencyProcess.STATUS_OPEN).values('person_id')
        if value:
            return queryset.filter(id__in=open_person_ids)
        return queryset.exclude(id__in=open_person_ids)

    def filter_email(self, queryset, name, value):
        """Persones amb algun contacte amb aquest email."""
        value = unquote(value or '').strip()
        if not value:
            return queryset
        contacts = PersonContact.objects.filter(person=OuterRef('pk'), email__icontains=value)
        return queryset.filter(Exists(contacts))

    def filter_phone(self, queryset, name, value):
        """Persones amb algun contacte amb aquest telèfon.

        Com el filtre de telèfon de contractes, no té en compte espais, guions,
        punts ni el prefix espanyol, ni en el valor buscat ni en el desat.
        """
        digits = phone_search_digits(unquote(value or ''))
        if not digits:
            return queryset
        contacts = PersonContact.objects.annotate(
            _phone_digits=phone_digits_expression('phone')
        ).filter(person=OuterRef('pk'), _phone_digits__contains=digits)
        return queryset.filter(Exists(contacts))

    def filter_iban(self, queryset, name, value):
        """Persones amb algun compte amb aquest IBAN.

        Ignora els espais tant en el valor buscat com en l'IBAN desat
        (ex: "ES48 2100 ..." o "ES4821000254...").
        """
        normalized = re.sub(r'\s+', '', unquote(value or ''))
        if not normalized:
            return queryset
        banks = PersonBank.objects.annotate(
            _iban_normalized=Replace('iban', Value(' '), Value(''))
        ).filter(person=OuterRef('pk'), _iban_normalized__icontains=normalized)
        return queryset.filter(Exists(banks))

    def filter_search(self, queryset, name, value):
        if not value:
            return queryset
        
        search_terms = value.split()
        term_queries = []
        for term in search_terms:
            term_query = (
                Q(token__icontains=term) |
                Q(name__icontains=term) |
                Q(surname__icontains=term) 
            )
            term_queries.append(term_query)
        final_query = reduce(and_, term_queries)
        return queryset.filter(final_query)