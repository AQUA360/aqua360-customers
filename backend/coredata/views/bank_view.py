from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter, SearchFilter
import schwifty

from coredata.models import Bank
from coredata.serializers import BankSerializer
from coredata.filters.bank_filter import BankFilter
from coredata.permissions import PersonPermission

class BankViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows Bank to be viewed or edited.
    """
    queryset = Bank.objects.all().order_by('token')
    serializer_class = BankSerializer
    permission_classes = [IsAuthenticated, PersonPermission]
    filter_backends = [DjangoFilterBackend, OrderingFilter, SearchFilter]
    filterset_class = BankFilter
    search_fields = ['name', 'token', 'bic']
    ordering_fields = ['name', 'token', 'bic']
    pagination_class = None

    @action(detail=False, methods=['get'], url_path='get-swift')
    def get_swift(self, request):
        # Rebem només el prefix (ex: primers 12 caràcters)
        iban_prefix = request.query_params.get('iban_prefix')
        if not iban_prefix:
            return Response({'error': 'iban_prefix is required'}, status=400)

        try:
            # Moltes entitats es poden identificar només amb els primers caràcters
            # Si la llibreria requereix un IBAN complet per validar,
            # es pot fer un 'pad' amb zeros per fer la cerca de l'entitat
            valid_length = 24 # Dependrà del país, 24 per ES
            mock_iban = iban_prefix.ljust(valid_length, '0')
            iban_obj = schwifty.IBAN(mock_iban, allow_invalid=True)

            return Response({
                'bic': iban_obj.bic,
                'bank_name': iban_obj.bank.get('name') if iban_obj.bank and isinstance(iban_obj.bank, dict) else None
            })
        except Exception:
            return Response({'bic': None, 'bank_name': None, 'error': 'Could not identify bank from prefix'})