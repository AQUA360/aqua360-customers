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
    
    @action(detail=False, methods=['post'], url_path='resolve')
    def resolve(self, request):
        """
        Resol quin compte ha de fer servir un contracte / factura / compromís
        SENSE modificar mai una fila existent.

        Un PersonBank penja de la PERSONA i el poden compartir diversos
        contractes (via GeneralPayment.IBAN), així que editar-lo en lloc en
        canvia l'IBAN a tots alhora. Aquí, en canvi:

        - si la persona ja té un compte actiu amb aquest IBAN, es retorna
          (`reused: True`) i només se n'actualitza el SWIFT/BIC si arriba un
          valor diferent (`swift_updated: True`): és el BIC d'aquest mateix
          compte, així que corregir-lo és correcte per a tots els contractes
          que el comparteixen. La resta de dades del titular no es toquen;
        - si no, se'n crea un de nou (`reused: False`), i el compte d'origen
          queda intacte.

        L'edició en lloc continua sent possible amb PUT, que és el que fa la
        fitxa de la persona.
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
            # Un SWIFT buit no esborra el que hi ha: el frontal l'envia buit quan
            # no l'ha pogut deduir de l'IBAN, no perquè l'usuari el vulgui treure.
            swift = (data.get('swift') or '').replace(' ', '').upper()
            swift_updated = bool(swift) and swift != (match.swift or '').strip().upper()
            if swift_updated:
                match.swift = swift
                match.save(update_fields=['swift', 'updated_at'])
            payload = PersonBankSerializer(match, context=context).data
            return Response({**payload, 'reused': True, 'swift_updated': swift_updated}, status=status.HTTP_200_OK)

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