# coredata/views/person_bank_view.py

from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.response import Response

from django_filters.rest_framework import DjangoFilterBackend

from django.db.models import Prefetch, F, CharField, Value
from django.db.models.functions import Concat, Replace, Upper

from rest_framework.decorators import action

from coredata.models import (Person, PersonBank, Bank)
from coredata.serializers import (PersonSerializer, PersonBankSerializer, PersonBankSaveSerializer)
from coredata.permissions import PersonPermission
from coredata.filters.person_bank_filter import PersonBankFilter
from coredata.utils.person_bank_utils import resolve_holder_dni

class PersonBankViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows PersonBank to be viewed or edited.
    """
    queryset = PersonBank.objects.all().order_by('token')
    permission_classes = [IsAuthenticated, PersonPermission]
    filter_backends = [DjangoFilterBackend, OrderingFilter, SearchFilter]
    filterset_class = PersonBankFilter
    search_fields = ['token', 'account_number', 'iban', 'swift']
    ordering_fields = ['id', 'token', 'account_number', 'iban', 'swift']

    
    def get_serializer_class(self):
        if self.request.method in ['GET']:
            return PersonBankSerializer
        return PersonBankSaveSerializer
    
    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context
    
    # Dades del compte que es poden corregir sense canviar d'IBAN.
    RESOLVE_EDITABLE_FIELDS = ('name', 'dni', 'role', 'account_number', 'swift', 'country', 'bank')
    # Si arriben buits, es manté el valor desat: el frontal els envia buits quan no
    # els ha pogut deduir (p. ex. el SWIFT de l'IBAN), no perquè s'hagin d'esborrar.
    RESOLVE_KEEP_IF_EMPTY = ('swift', 'country')

    @action(detail=False, methods=['post'], url_path='resolve')
    def resolve(self, request):
        """
        Resol quin compte ha de fer servir un contracte / factura / compromís.

        Un PersonBank penja de la PERSONA i el poden compartir diversos
        contractes (via GeneralPayment.IBAN). Per això:

        - si la persona ja té un compte actiu amb aquest IBAN, es reaprofita
          (`reused: True`) i s'hi desen les dades editades (titular, DNI,
          càrrec, SWIFT, país, banc...). És el mateix compte bancari, així que
          la correcció és vàlida per a tots els contractes que el comparteixen.
          `updated` indica si ha canviat alguna dada;
        - si no, se'n crea un de nou (`reused: False`) i el compte d'origen
          queda intacte: canviar l'IBAN no ha d'afectar els altres contractes.

        Si el DNI arriba buit, s'aplica `resolve_holder_dni`.
        """
        data = {key: value for key, value in request.data.items()}

        person_id = data.get('person')
        iban = (data.get('iban') or '').replace(' ', '').upper()
        if not person_id:
            return Response({'detail': "Cal indicar la persona."}, status=status.HTTP_400_BAD_REQUEST)
        if not iban:
            return Response({'detail': "Cal indicar l'IBAN."}, status=status.HTTP_400_BAD_REQUEST)

        # El compte que s'estava editant: si l'IBAN no ha canviat, es manté
        # seleccionat aquest i no un altre duplicat de la mateixa persona.
        current_id = data.pop('current_id', None)
        data.pop('id', None)
        # Una còpia no hereta mai el flag de compte per defecte de l'original.
        data.pop('is_default', None)
        data['iban'] = iban
        if data.get('swift'):
            data['swift'] = data['swift'].replace(' ', '').upper()

        existing = (
            PersonBank.objects.filter(person_id=person_id, is_active=True)
            .exclude(iban__isnull=True)
            .annotate(iban_normalized=Upper(Replace('iban', Value(' '), Value(''))))
            .filter(iban_normalized=iban)
        )

        match = existing.filter(id=current_id).first() if current_id else None
        if not match:
            match = existing.order_by('-is_default', 'id').first()

        context = self.get_serializer_context()
        if match:
            changes = {
                field: data[field] for field in self.RESOLVE_EDITABLE_FIELDS
                if field in data and not (field in self.RESOLVE_KEEP_IF_EMPTY and not data[field])
            }
            if 'dni' in changes or 'name' in changes:
                changes['dni'] = resolve_holder_dni(
                    changes.get('dni', match.dni), changes.get('name', match.name), match.person
                )
            serializer = PersonBankSaveSerializer(match, data=changes, partial=True, context=context)
            serializer.is_valid(raise_exception=True)
            updated = any(
                (getattr(match, field) or None) != (value or None)
                for field, value in serializer.validated_data.items()
            )
            if updated:
                serializer.save()
            payload = PersonBankSerializer(match, context=context).data
            return Response({**payload, 'reused': True, 'updated': updated}, status=status.HTTP_200_OK)

        serializer = PersonBankSaveSerializer(data=data, context=context)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        payload = PersonBankSerializer(serializer.instance, context=context).data
        return Response({**payload, 'reused': False}, status=status.HTTP_201_CREATED)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        instance = serializer.instance
        read_serializer = PersonBankSerializer(instance, context=self.get_serializer_context())
        headers = self.get_success_headers(read_serializer.data)
        return Response(read_serializer.data, status=status.HTTP_201_CREATED, headers=headers, content_type='application/json')

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        instance = serializer.instance
        read_serializer = PersonBankSerializer(instance, context=self.get_serializer_context())
        return Response(read_serializer.data, status=status.HTTP_200_OK, content_type='application/json')