import datetime
from decimal import Decimal
from types import SimpleNamespace

from django.test import TestCase
from django.utils import timezone

from billing.models import Invoice, InvoiceLineItem, InvoiceStatus, Payment
from coredata.models import ConfigProject
from pricing.models import ArticleCode, LineItemType, Product
from service.models import Exploitation
from statistics.models import AcaDeclaration
from statistics.utils.aca_declaration_service import aca_declaration_selection, build_aca_declaration

REQUEST = SimpleNamespace(data={})
JUNE = (datetime.date(2026, 6, 1), datetime.date(2026, 6, 30))
OCTOBER = (datetime.date(2026, 10, 1), datetime.date(2026, 10, 31))


class AcaDeclarationTests(TestCase):
    """Mesos de la Declaració ACA ja presentats: surten tal com es van declarar i les factures del mes
    que no s'hi van declarar passen al primer mes obert."""

    def setUp(self):
        for token, value in (
            ('invoice_type_invoice_token', 'F'),
            ('invoice_status_cancelled_token', '-6'),
            ('invoice_status_pending_token', '1'),
            ('token_product_aca', 'ACA'),
            ('invoice_status_paid_token', '-1'),
        ):
            ConfigProject.objects.create(token=token, value=value)
        self.paid = InvoiceStatus.objects.create(token='0', name='Confirmada')
        self.cancelled = InvoiceStatus.objects.create(token='-6', name='Anul·lada')
        self.product = Product.objects.create(token='ACA')
        self.fixed = LineItemType.objects.create(article=ArticleCode.objects.create(token='part_fixa', name='Part fixa'))
        self.variable = LineItemType.objects.create(article=ArticleCode.objects.create(token='part_variable', name='Part variable'))
        self.masnou = Exploitation.objects.create(name='MUNICIPI A', code='080001')
        self.other = Exploitation.objects.create(name='MUNICIPI B', code='080002')

    def invoice(self, number, issue_date, exploitation=None, fixed='1.00', variable='10.00', created_at=None):
        invoice = Invoice.objects.create(
            serie_final=number, token=number, issue_date=issue_date, type_final='F', status=self.paid,
            exploitation=exploitation or self.masnou,
        )
        if created_at:
            Invoice.objects.filter(id=invoice.id).update(created_at=created_at)
        Payment.objects.create(invoice=invoice, amount=Decimal('1'))
        InvoiceLineItem.objects.create(invoice=invoice, product=self.product, line_item_type=self.fixed, price=Decimal(fixed))
        InvoiceLineItem.objects.create(invoice=invoice, product=self.product, line_item_type=self.variable, price=Decimal(variable))
        return invoice

    def deactivate(self, invoice):
        Invoice.objects.filter(id=invoice.id).update(is_active=False, status=self.cancelled)
        invoice.payments.update(is_active=False)
        invoice.line_items.update(is_active=False)

    def freeze(self, exploitation, year, month, presented_at, **kwargs):
        result = build_aca_declaration(exploitation, year, month, presented_at, **kwargs)
        declaration = AcaDeclaration.objects.create(
            exploitation=exploitation, year=year, month=month, presented_at=presented_at,
            fixed_amount=result.fixed_amount, variable_amount=result.variable_amount,
        )
        declaration.line_items.set(result.line_ids)
        return result

    def selected(self, period):
        selection = aca_declaration_selection(*period, REQUEST)
        invoices = set(selection.invoices.values_list('serie_final', flat=True))
        total = sum(
            (Decimal(str(price)) for price in InvoiceLineItem.objects.filter(
                selection.line_items_q, invoice__in=selection.invoices,
            ).values_list('price', flat=True)),
            Decimal(0),
        ).quantize(Decimal('0.01'))
        return invoices, total

    def test_without_declarations_uses_current_state(self):
        self.invoice('FC/1', datetime.date(2026, 6, 10))
        cancelled = self.invoice('FC/2', datetime.date(2026, 6, 11))
        self.deactivate(cancelled)
        self.assertEqual(self.selected(JUNE), ({'FC/1'}, Decimal('11.00')))

    def test_presented_month_keeps_declared_invoices(self):
        self.invoice('FC/1', datetime.date(2026, 6, 10))
        deactivated = self.invoice('FC/2', datetime.date(2026, 6, 11))
        result = self.freeze(self.masnou, 2026, 6, timezone.now())
        self.assertEqual((result.fixed_amount, result.variable_amount), (Decimal('2.00'), Decimal('20.00')))

        # Desactivada després de presentar el mes: continua declarada amb les seves línies
        self.deactivate(deactivated)
        self.assertEqual(self.selected(JUNE), ({'FC/1', 'FC/2'}, Decimal('22.00')))
        self.assertEqual(self.selected(OCTOBER), (set(), Decimal('0.00')))

    def test_late_invoice_goes_to_first_open_month(self):
        self.invoice('FC/1', datetime.date(2026, 6, 10))
        presented_at = timezone.now()
        self.invoice('FF/LATE', datetime.date(2026, 6, 12), created_at=presented_at + datetime.timedelta(days=30))
        self.freeze(self.masnou, 2026, 6, presented_at)
        self.freeze(self.masnou, 2026, 7, presented_at)

        self.assertEqual(self.selected(JUNE), ({'FC/1'}, Decimal('11.00')))
        # Juliol també està presentat: la factura passa a l'agost
        self.assertEqual(self.selected((datetime.date(2026, 8, 1), datetime.date(2026, 8, 31))), ({'FF/LATE'}, Decimal('11.00')))
        # L'acumulat la compta una sola vegada
        self.assertEqual(self.selected((datetime.date(2026, 1, 1), OCTOBER[1])), ({'FC/1', 'FF/LATE'}, Decimal('22.00')))

    def test_listed_invoice_is_declared_with_inactive_lines(self):
        # Al full de factures presentat, però ja desactivada (amb les línies) en congelar el mes
        listed = self.invoice('FC/LISTED', datetime.date(2026, 6, 10), fixed='4.50', variable='9.87')
        self.deactivate(listed)
        result = self.freeze(self.masnou, 2026, 6, timezone.now(), listed_numbers=['FC/LISTED', 'FR/UNKNOWN'])
        self.assertEqual((result.fixed_amount, result.variable_amount), (Decimal('4.50'), Decimal('9.87')))
        self.assertEqual(result.unresolved, ['FR/UNKNOWN'])
        self.assertEqual(result.inactive_line_invoices, [listed.id])
        self.assertEqual(self.selected(JUNE), ({'FC/LISTED'}, Decimal('14.37')))

    def test_other_exploitation_is_not_frozen(self):
        self.invoice('FC/1', datetime.date(2026, 6, 10))
        self.freeze(self.masnou, 2026, 6, timezone.now())
        self.invoice('FC/NEW', datetime.date(2026, 6, 20))
        self.invoice('FC/B', datetime.date(2026, 6, 20), exploitation=self.other)
        self.assertEqual(self.selected(JUNE), ({'FC/1', 'FC/B'}, Decimal('22.00')))

    def test_command_only_saves_matching_totals(self):
        from io import StringIO

        from django.core.management import CommandError, call_command

        self.invoice('FC/1', datetime.date(2026, 6, 10))
        args = ['aca_freeze_declaration', '--exploitation', '080001', '--month', '2026-06', '--commit']
        with self.assertRaises(CommandError):
            call_command(*args, '--fixed', '1.00', '--variable', '9.99', stdout=StringIO())
        self.assertFalse(AcaDeclaration.objects.exists())

        call_command(*args, '--fixed', '1.00', '--variable', '10.00', stdout=StringIO())
        declaration = AcaDeclaration.objects.get()
        self.assertEqual((declaration.year, declaration.month, declaration.line_items.count()), (2026, 6, 2))

    def test_report_filters_apply_to_presented_months(self):
        self.invoice('FC/1', datetime.date(2026, 6, 10))
        self.invoice('FR/1', datetime.date(2026, 6, 11))
        self.freeze(self.masnou, 2026, 6, timezone.now())
        selection = aca_declaration_selection(*JUNE, SimpleNamespace(data={'prefix': 'FC/'}))
        self.assertEqual(set(selection.invoices.values_list('serie_final', flat=True)), {'FC/1'})

    def test_factdeta_uses_the_same_selection(self):
        from unittest import mock

        from statistics.utils.report_factdeta_service import generate_factdeta_report

        self.invoice('FC/1', datetime.date(2026, 6, 10))
        deactivated = self.invoice('FC/2', datetime.date(2026, 6, 11))
        self.freeze(self.masnou, 2026, 6, timezone.now())
        self.deactivate(deactivated)
        with mock.patch('statistics.utils.report_factdeta_service.generate_factdeta_document', return_value=[]) as generate:
            generate_factdeta_report(SimpleNamespace(data={'year': 2026}))
        _exploitations, invoices = generate.call_args.args
        lines = InvoiceLineItem.objects.filter(generate.call_args.kwargs['line_items_q'], invoice__in=invoices)
        self.assertEqual(set(invoices.values_list('serie_final', flat=True)), {'FC/1', 'FC/2'})
        self.assertEqual(lines.count(), 4)


class AcaVolumeTests(TestCase):
    """Els m³ de la Declaració ACA surten amb el mateix càlcul que el FACTDETA en baixa."""

    def setUp(self):
        from pricing.models import VariableCalculation

        for token, value in (('invoice_status_paid_token', '-1'), ('invoice_status_cancelled_token', '-6')):
            ConfigProject.objects.create(token=token, value=value)
        self.paid = InvoiceStatus.objects.create(token='0', name='Confirmada')
        self.fixed = LineItemType.objects.create(article=ArticleCode.objects.create(token='part_fixa', name='Part fixa'))
        self.leak = LineItemType.objects.create(name='FUITA', quantity=VariableCalculation.objects.create(token='diferencia_fuita'))
        self.domestic = LineItemType.objects.create(name='CANON DOMESTIC')
        self.general = LineItemType.objects.create(name='GRAVAMEN GENERAL INDUSTRIAL')
        self.specific = LineItemType.objects.create(name='GRAVAMEN ESPECIFIC INDUSTRIAL')

    def invoice(self, number, used_aca, consumption, lines):
        invoice = Invoice.objects.create(
            serie_final=number, token=number, issue_date=datetime.date(2026, 6, 1), type_final='F',
            status=self.paid, used_aca=used_aca, real_consumption=consumption,
        )
        created = [InvoiceLineItem.objects.create(invoice=invoice, line_item_type=self.fixed, price=1, units=1)]
        for line_type, units, price_unit, interval in lines:
            created.append(InvoiceLineItem.objects.create(
                invoice=invoice, line_item_type=line_type, units=units, price_unit=price_unit,
                price=units * price_unit, interval=interval,
            ))
        return invoice, created

    def volumes(self, *invoices):
        from billing.utils.generate_factdeta_service import factdeta_invoice_volumes

        lines = {invoice.id: created for invoice, created in invoices}
        return {
            volume.invoice.serie_final: volume
            for volume in factdeta_invoice_volumes([invoice for invoice, _ in invoices], lines, 'part_fixa', 'tarifa_social')
        }

    def test_domestic_volumes(self):
        volumes = self.volumes(self.invoice('FC/D', 'D', 30, [
            (self.domestic, 10, 0.5, 1), (self.domestic, 8, 1.0, 2), (self.leak, 2, 0.5, None), (self.domestic, 5, 0, None),
        ]))
        volume = volumes['FC/D']
        self.assertEqual((volume.tariff_type, volume.consumed, volume.billed), ('D', Decimal('30'), Decimal('25')))
        # La fuita va al primer tram i les línies a preu 0, a tarifa social 0
        self.assertEqual(volume.trams, [Decimal('12'), Decimal('8'), Decimal('0'), Decimal('0')])
        self.assertEqual(volume.social_zero, Decimal('5'))

    def test_domestic_use_billed_as_industrial_counts_volume_once(self):
        volumes = self.volumes(
            self.invoice('FC/I', 'D', 7, [(self.general, 7, 0.1, None), (self.specific, 7, 0.2, None)]),
            self.invoice('FC/L', 'L', 9, [(self.domestic, 9, 0.5, 1)]),
        )
        self.assertEqual(set(volumes), {'FC/I'})
        self.assertEqual((volumes['FC/I'].tariff_type, volumes['FC/I'].billed), ('I', Decimal('7')))
