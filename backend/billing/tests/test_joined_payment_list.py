from decimal import Decimal

from django.test import TestCase
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory

from billing.filter.joined_payment_filter import JoinedPaymentFilter, JoinedPaymentOrderingFilter
from billing.models import JoinedPayment, JoinedPaymentStatus
from billing.views.joined_payment_view import JoinedPaymentViewSet
from contract.models import PaymentType


class TestJoinedPaymentList(TestCase):
    """Cerca, filtres i ordenació del llistat de pagaments agrupats."""

    def setUp(self):
        """Crea tres pagaments agrupats amb client, estat i mètode diferents."""
        self.pending = JoinedPaymentStatus.objects.create(token='1', name='Pendent', position=1)
        self.paid = JoinedPaymentStatus.objects.create(token='0', name='Pagat', position=2)
        self.transfer = PaymentType.objects.create(name='Transferència')

        self.first = JoinedPayment.objects.create(
            token='JP-1', number='JP-1', customer_final='Client Beta', customer_token_final='B1',
            status=self.paid, payment_type=self.transfer, payment_type_name='Transferència',
            total_final=Decimal('10.00'))
        self.second = JoinedPayment.objects.create(
            token='JP-2', number='JP-2', customer_final='Client Alfa', customer_token_final='A1',
            status=self.pending, payment_type_name='Efectiu', total_final=Decimal('10.00'))
        self.third = JoinedPayment.objects.create(
            token='JP-3', number='JP-3', customer_final='Client Gamma', customer_token_final='G1',
            status=self.pending, total_final=Decimal('5.00'))

    def filtered(self, **params):
        """Aplica el FilterSet del llistat amb els paràmetres indicats."""
        return JoinedPaymentFilter(params, queryset=JoinedPayment.objects.all()).qs

    def ordered(self, ordering):
        """Aplica el filtre d'ordenació de la vista amb el paràmetre `ordering`."""
        request = Request(APIRequestFactory().get('/', {'ordering': ordering}))
        view = JoinedPaymentViewSet()
        queryset = JoinedPayment.objects.all()
        return list(JoinedPaymentOrderingFilter().filter_queryset(request, queryset, view))

    def test_cerca_pel_nom_del_client_del_pagament_agrupat(self):
        """La cerca troba el pagament pel nom i pel codi de client propis."""
        self.assertEqual(list(self.filtered(search='alfa')), [self.second])
        self.assertEqual(list(self.filtered(search='G1')), [self.third])

    def test_la_vista_no_combina_la_cerca_amb_search_filter(self):
        """Només el FilterSet tracta `search`; un SearchFilter hi faria un AND."""
        backends = [backend.__name__ for backend in JoinedPaymentViewSet.filter_backends]
        self.assertNotIn('SearchFilter', backends)

    def test_filtre_metode_de_pagament_amb_opcio_cap(self):
        """`null` selecciona els que no tenen mètode; es pot combinar amb ids."""
        self.assertEqual(set(self.filtered(payment_type='null')), {self.second, self.third})
        self.assertEqual(
            set(self.filtered(payment_type=f'{self.transfer.id},null')),
            {self.first, self.second, self.third})
        self.assertEqual(list(self.filtered(payment_type=str(self.transfer.id))), [self.first])

    def test_ordena_per_client_estat_metode_i_identificacio(self):
        """Les columnes de text del llistat s'ordenen al backend."""
        self.assertEqual(self.ordered('customer_final'), [self.second, self.first, self.third])
        self.assertEqual(self.ordered('-number'), [self.third, self.second, self.first])
        self.assertEqual(self.ordered('status__position')[-1], self.first)
        self.assertEqual(self.ordered('payment_type_name'), [self.second, self.first, self.third])

    def test_desempat_estable_per_id(self):
        """Amb imports iguals l'ordre és determinista (desempat per `-id`)."""
        self.assertEqual(self.ordered('-total_final'), [self.second, self.first, self.third])
