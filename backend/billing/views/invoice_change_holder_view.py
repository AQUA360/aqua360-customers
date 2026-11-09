from django.db import transaction
from rest_framework import status
from rest_framework.permissions import DjangoModelPermissions, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from billing.models import Invoice
from billing.serializers.invoice_serializer import InvoiceFullSerializer
from billing.utils.invoice_service import apply_holder_to_budget
from coredata.models import ConfigProject, Person


class InvoiceChangeHolderView(APIView):
    """Canvia el titular d'un pressupost pendent sense regenerar-lo.

    URL: POST /invoice/<invoice id>/change-holder/  amb {"holder_id": <person id>}

    Les línies del pressupost (incloses les afegides o editades a mà) es mantenen:
    només canvien el titular i les seves dades fixades. Un cop confirmat, el titular
    només es pot canviar refacturant.
    """
    permission_classes = [IsAuthenticated, DjangoModelPermissions]
    queryset = Invoice.objects.all()

    @transaction.atomic
    def post(self, request, id, *args, **kwargs):
        invoice = Invoice.objects.select_related('type', 'status').filter(id=id).first()
        if not invoice:
            return Response({'error': 'Pressupost no trobat.'}, status=status.HTTP_404_NOT_FOUND)

        holder_id = request.data.get('holder_id')
        try:
            holder = Person.objects.filter(id=int(holder_id)).first()
        except (TypeError, ValueError):
            holder = None
        if not holder:
            return Response({'error': 'El titular seleccionat no existeix.'}, status=status.HTTP_400_BAD_REQUEST)

        # Mateix criteri que el panell d'edició: només els pressupostos pendents són editables.
        pending_token = ConfigProject.objects.get(token='invoice_status_pending_token').value
        if invoice.status and invoice.status.token != pending_token:
            return Response({'error': 'El titular només es pot canviar en un pressupost no confirmat.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            apply_holder_to_budget(invoice, holder)
        except ValueError:
            return Response({'error': 'El titular només es pot canviar en un pressupost no confirmat.'}, status=status.HTTP_400_BAD_REQUEST)

        return Response(InvoiceFullSerializer(invoice).data, status=status.HTTP_200_OK)
