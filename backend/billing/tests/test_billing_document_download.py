from django.contrib.auth.models import Permission, User
from django.contrib.contenttypes.models import ContentType
from django.urls import reverse
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient

from billing.models import Billing, BillingDocumentDownload, Invoice
from billing.utils.billing_document_download import (
    DownloadOptionsError,
    open_pdf_zip,
    ordered_billing_invoices,
    ordered_process_files,
    pack_by_count,
    pack_by_size,
    parse_download_options,
    parse_download_request,
    pdfs_under_limit,
)
from communication.models import Communication, CommunicationFile, CommunicationProcess
from contract.models import Contract
from coredata.models import Address, ConfigProject, PersonAddress
from documentmanager.models import Document


def seed_configs():
    ConfigProject.objects.get_or_create(token='contract_terminated_status', defaults={'value': '0'})
    ConfigProject.objects.get_or_create(token='invoice_status_cancelled_token', defaults={'value': '-1'})
    ConfigProject.objects.get_or_create(token='message_type_letter_token', defaults={'value': 'letter'})
    ConfigProject.objects.get_or_create(token='message_type_email_token', defaults={'value': 'email'})


class BatchPackingTests(SimpleTestCase):
    def test_count_chunks_keep_order(self):
        self.assertEqual(
            pack_by_count(['a', 'b', 'c', 'd', 'e'], 2),
            [['a', 'b'], ['c', 'd'], ['e']],
        )

    def test_size_respects_the_limit_and_isolates_oversized_or_unknown_files(self):
        self.assertEqual(
            pack_by_size(['a', 'b', 'c', 'd'], [40, 50, 30, 200], 100),
            [['a', 'b'], ['c'], ['d']],
        )
        self.assertEqual(
            pack_by_size(['a', 'b', 'c'], [10, 0, 10], 100),
            [['a'], ['b'], ['c']],
        )

    def test_merged_pdf_over_the_limit_is_split_but_a_single_document_stays_whole(self):
        def render(batch):
            return b'x' * sum(batch)

        self.assertEqual([len(part) for part in pdfs_under_limit([60, 60], 100, render)], [60, 60])
        self.assertEqual(len(pdfs_under_limit([150], 100, render)[0]), 150)

    def test_zip_names_the_lots_in_order(self):
        import os
        import zipfile

        temp, count = open_pdf_zip([b'%PDF-a', b'%PDF-b'], lambda index: f'lot_{index:03d}.pdf')
        try:
            self.assertEqual(count, 2)
            with zipfile.ZipFile(temp.name) as archive:
                self.assertEqual(archive.namelist(), ['lot_001.pdf', 'lot_002.pdf'])
                self.assertEqual(archive.read('lot_002.pdf'), b'%PDF-b')
        finally:
            temp.close()
            os.unlink(temp.name)


class BillingDocumentDownloadSelectionTests(TestCase):
    def setUp(self):
        seed_configs()
        self.billing = Billing.objects.create(token='FAC-1')
        self.other_billing = Billing.objects.create(token='FAC-2')

    def contact(self, search):
        address = Address.objects.create()
        Address.objects.filter(pk=address.pk).update(address_search=search)
        return PersonAddress.objects.create(address_id=address.pk)

    def contract(self, token, communication_type, address=None):
        return Contract.objects.create(
            token=token,
            communication_type=communication_type,
            address_contact=self.contact(address) if address else None,
        )

    def invoice(self, serie, contract=None, payment='DIRECT_DEBIT', billing=None, **kwargs):
        return Invoice.objects.create(
            billing=billing or self.billing,
            contract=contract,
            serie_final=serie,
            token=serie,
            payment_type_token_final=payment,
            **kwargs,
        )

    def series(self, billing_ids=None, **options):
        return list(ordered_billing_invoices(
            billing_ids or [self.billing.id], **options,
        ).values_list('serie_final', flat=True))

    def test_payment_type_and_billing_scope(self):
        self.invoice('CASH', self.contract('C-1', 'DIGITAL'), payment='CASH')
        self.invoice('DEBIT', self.contract('C-2', 'DIGITAL'), payment='DIRECT_DEBIT')
        self.invoice('OTHER', self.contract('C-3', 'DIGITAL'), payment='CASH', billing=self.other_billing)

        self.assertEqual(self.series(payment_type_tokens=['CASH']), ['CASH'])

    def test_several_billings_are_sorted_together(self):
        self.invoice('F-2', self.contract('C-2', 'PAPER'))
        self.invoice('F-1', self.contract('C-1', 'PAPER'), billing=self.other_billing)

        self.assertEqual(
            self.series([self.billing.id, self.other_billing.id], ordering='invoice_code'),
            ['F-1', 'F-2'],
        )

    def test_skips_excluded_and_inactive(self):
        self.invoice('OK', self.contract('C-1', 'DIGITAL'))
        self.invoice('OUT', self.contract('C-2', 'DIGITAL'), is_excluded=True)
        self.invoice('OFF', self.contract('C-3', 'DIGITAL'), is_active=False)

        self.assertEqual(self.series(), ['OK'])

    def test_orders_by_contract_invoice_and_contact_address(self):
        self.invoice('F-2', self.contract('C-2', 'PAPER', 'Carrer B'))
        self.invoice('F-10', self.contract('C-10', 'PAPER', 'Carrer A'))
        self.invoice('F-1', self.contract('C-1', 'PAPER'), address_final='Carrer Z')

        self.assertEqual(
            self.series(ordering='contract_token'),
            ['F-1', 'F-10', 'F-2'],
        )
        self.assertEqual(
            self.series(ordering='contract_token', descending=True),
            ['F-2', 'F-10', 'F-1'],
        )
        self.assertEqual(self.series(ordering='invoice_code'), ['F-1', 'F-10', 'F-2'])
        self.assertEqual(
            self.series(ordering='contact_address'),
            ['F-10', 'F-2', 'F-1'],
        )

    def test_parse_download_options(self):
        options = parse_download_options({
            'payment_type_tokens': 'CASH, DIRECT_DEBIT',
            'delivery': 'postal',
            'ordering': 'invoice_code',
            'descending': '1',
        })
        self.assertEqual(options['payment_type_tokens'], ['CASH', 'DIRECT_DEBIT'])
        self.assertTrue(options['descending'])
        self.assertEqual(parse_download_options({})['ordering'], 'contact_address')
        self.assertEqual(parse_download_options({})['batch_mode'], 'none')
        self.assertIsNone(parse_download_options({})['batch_size'])
        with self.assertRaises(DownloadOptionsError):
            parse_download_options({'delivery': 'sms'})
        with self.assertRaises(DownloadOptionsError) as raised:
            parse_download_options({'batch_mode': 'size'})
        self.assertEqual(raised.exception.field, 'batch_size')
        with self.assertRaises(DownloadOptionsError):
            parse_download_options({'batch_mode': 'count', 'batch_size': 0})

    def test_channel_filter_requires_a_process(self):
        parsed = parse_download_request({
            'billing_ids': [self.billing.id, self.other_billing.id],
            'ordering': 'invoice_code',
        })
        self.assertEqual(parsed['billing_ids'], [self.billing.id, self.other_billing.id])
        self.assertEqual(parsed['communication_process_ids'], [])
        with self.assertRaises(DownloadOptionsError) as raised:
            parse_download_request({'billing_ids': '1', 'delivery': 'postal'})
        self.assertEqual(raised.exception.field, 'delivery')
        with self.assertRaises(DownloadOptionsError) as raised:
            parse_download_request({'billing_ids': [1], 'communication_process_id': 2})
        self.assertEqual(raised.exception.field, 'source')
        with self.assertRaises(DownloadOptionsError):
            parse_download_request({})


class ProcessDocumentDownloadSelectionTests(TestCase):
    def setUp(self):
        seed_configs()
        self.process = CommunicationProcess.objects.create(token='PROC-1')
        self.billing = Billing.objects.create(token='FAC-P')

    def add_file(self, type_tokens, *, address, serie=None, payment='DIRECT_DEBIT',
                 attach_letter=True, attach_email=True, is_letter=False, contract_token=None,
                 process=None):
        communication = Communication.objects.create(
            process=process or self.process,
            type_tokens=type_tokens,
            used_address=address,
        )
        if contract_token:
            communication.contracts.add(Contract.objects.create(token=contract_token, communication_type='PAPER'))
        invoice = None
        if serie:
            invoice = Invoice.objects.create(
                billing=self.billing,
                serie_final=serie,
                token=serie,
                payment_type_token_final=payment,
            )
            communication.invoices.add(invoice)
        document = Document.objects.create(entity_id=communication.id, service='hdd', document_name=serie or address)
        return CommunicationFile.objects.create(
            communication=communication,
            file=document,
            invoice=invoice,
            is_letter=is_letter,
            attach_to_letter=attach_letter,
            attach_to_email=attach_email,
        )

    def names(self, **options):
        files = ordered_process_files(self.process.id, **options)
        return [comm_file.file.document_name for comm_file in files]

    def test_channel_follows_the_process_menu(self):
        self.add_file('letter', address='Carta', serie='C', attach_email=False)
        self.add_file('email', address='Correu', serie='E', attach_letter=False)
        self.add_file('letter', address='Fora', attach_letter=False, attach_email=False, is_letter=True)

        self.assertCountEqual(self.names(delivery='postal'), ['C'])
        self.assertCountEqual(self.names(delivery='email'), ['E'])
        self.assertCountEqual(self.names(delivery='all'), ['C', 'E'])

    def test_payment_filter_keeps_the_letter_with_the_matching_invoice(self):
        self.add_file('letter', address='Casa', serie='CASH', payment='CASH', is_letter=False)
        letter = self.add_file('letter', address='Casa 2', is_letter=True, attach_email=False)
        cash = Invoice.objects.get(serie_final='CASH')
        letter.communication.invoices.add(cash)
        self.add_file('letter', address='Altra', serie='DEBIT', payment='DIRECT_DEBIT')

        self.assertCountEqual(
            self.names(delivery='postal', payment_type_tokens=['CASH']),
            ['CASH', 'Casa 2'],
        )

    def test_orders_process_files_by_address_and_contract(self):
        self.add_file('letter', address='Carrer B', serie='F-2', contract_token='C-2')
        self.add_file('letter', address='Carrer A', serie='F-10', contract_token='C-10')

        self.assertEqual(self.names(ordering='contact_address'), ['F-10', 'F-2'])
        self.assertEqual(self.names(ordering='contract_token'), ['F-10', 'F-2'])
        self.assertEqual(self.names(ordering='invoice_code'), ['F-10', 'F-2'])

    def test_several_processes_are_sorted_together(self):
        other = CommunicationProcess.objects.create(token='PROC-2')
        self.add_file('letter', address='Carrer B', serie='B')
        self.add_file('letter', address='Carrer A', serie='A', process=other)

        files = ordered_process_files(
            [self.process.id, other.id], ordering='contact_address',
        )
        self.assertEqual([comm_file.file.document_name for comm_file in files], ['A', 'B'])

    def test_descending_order_handles_prefix_values(self):
        for value in ('F-1', 'F-10', 'F-2'):
            self.add_file('letter', address=value, serie=value, contract_token=value)
        self.add_file('letter', address='')

        for ordering in ('invoice_code', 'contract_token', 'contact_address'):
            with self.subTest(ordering=ordering):
                self.assertEqual(
                    self.names(ordering=ordering, descending=True),
                    ['F-2', 'F-10', 'F-1', ''],
                )


class BillingDocumentDownloadApiTests(TestCase):
    def setUp(self):
        seed_configs()
        self.billing = Billing.objects.create(token='FAC-API')
        self.other = Billing.objects.create(token='FAC-API-2')
        contract = Contract.objects.create(token='C-API', communication_type='DIGITAL')
        Invoice.objects.create(
            billing=self.billing, contract=contract, serie_final='API-1', token='API-1',
            payment_type_token_final='DIRECT_DEBIT',
        )
        Invoice.objects.create(
            billing=self.other, contract=contract, serie_final='API-2', token='API-2',
            payment_type_token_final='CASH',
        )
        self.process = CommunicationProcess.objects.create(token='PROC-API')
        communication = Communication.objects.create(process=self.process, type_tokens='email', used_address='Carrer')
        document = Document.objects.create(entity_id=communication.id, service='hdd', document_name='correu')
        CommunicationFile.objects.create(
            communication=communication, file=document, attach_to_email=True, attach_to_letter=False,
        )
        self.user = User.objects.create_user(username='downloader', password='secret')
        content_type = ContentType.objects.get_for_model(Billing)
        permission = Permission.objects.get(codename='view_billing', content_type=content_type)
        self.user.user_permissions.add(permission)
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        self.url = reverse('billing-document-downloads')

    def test_preview_and_request_keep_a_record_for_several_billings(self):
        preview = self.client.get(reverse('billing-document-download-preview'), {
            'billing_ids': f'{self.billing.id},{self.other.id}',
            'ordering': 'invoice_code',
        })
        self.assertEqual(preview.status_code, 200)
        self.assertEqual(preview.data['count'], 2)
        self.assertIsNone(preview.data['batch_count'])

        batched = self.client.get(reverse('billing-document-download-preview'), {
            'billing_ids': f'{self.billing.id},{self.other.id}',
            'batch_mode': 'count',
            'batch_size': '1',
        })
        self.assertEqual(batched.status_code, 200)
        self.assertEqual(batched.data['batch_count'], 2)

        response = self.client.post(self.url, {
            'billing_ids': [self.billing.id],
            'ordering': 'contract_token',
            'payment_type_tokens': ['DIRECT_DEBIT'],
        }, format='json')
        self.assertEqual(response.status_code, 202)
        download = response.data['download']
        self.assertEqual(download['invoice_count'], 1)
        self.assertEqual(download['source'], 'billings')
        self.assertEqual(download['billing_ids'], [self.billing.id])
        self.assertEqual(download['delivery'], 'all')
        self.assertEqual(download['status'], 'pending')
        self.assertEqual(download['requested_by_name'], 'downloader')

        listed = self.client.get(self.url)
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(listed.data[0]['id'], download['id'])
        record = BillingDocumentDownload.objects.get(id=download['id'])
        self.assertEqual(record.task_id, response.data['task_id'])
        self.assertEqual(list(record.billings.values_list('id', flat=True)), [self.billing.id])
        self.assertEqual(record.batch_mode, 'none')

    def test_count_batches_are_stored_on_the_request(self):
        response = self.client.post(self.url, {
            'billing_ids': [self.billing.id, self.other.id],
            'batch_mode': 'count',
            'batch_size': 1,
            'ordering': 'invoice_code',
        }, format='json')
        self.assertEqual(response.status_code, 202)
        download = response.data['download']
        self.assertEqual(download['batch_mode'], 'count')
        self.assertEqual(download['batch_size'], 1)
        self.assertEqual(download['invoice_count'], 2)
        self.assertIsNone(download['batch_count'])

        missing = self.client.post(self.url, {
            'billing_ids': [self.billing.id],
            'batch_mode': 'size',
        }, format='json')
        self.assertEqual(missing.status_code, 400)
        self.assertEqual(missing.data['error'], 'batch_size')

    def test_billing_source_rejects_a_channel_filter(self):
        response = self.client.post(self.url, {
            'billing_ids': [self.billing.id],
            'delivery': 'email',
        }, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['error'], 'delivery')
        self.assertEqual(BillingDocumentDownload.objects.count(), 0)

    def test_process_source_filters_by_channel(self):
        self.user.user_permissions.set([Permission.objects.get(
            codename='view_communicationprocess',
            content_type=ContentType.objects.get_for_model(CommunicationProcess),
        )])
        preview = self.client.get(reverse('billing-document-download-preview'), {
            'communication_process_ids': str(self.process.id),
            'delivery': 'email',
        })
        self.assertEqual(preview.status_code, 200)
        self.assertEqual(preview.data['count'], 1)
        response = self.client.post(self.url, {
            'communication_process_id': self.process.id,
            'delivery': 'email',
            'ordering': 'contact_address',
        }, format='json')
        self.assertEqual(response.status_code, 202)
        download = response.data['download']
        self.assertEqual(download['source'], 'process')
        self.assertEqual(download['delivery'], 'email')
        self.assertEqual(download['invoice_count'], 1)
        self.assertEqual(download['communication_process_token'], 'PROC-API')
        self.assertEqual(download['communication_process_ids'], [self.process.id])
        record = BillingDocumentDownload.objects.get(id=download['id'])
        self.assertEqual(record.communication_process_id, self.process.id)
        self.assertEqual(
            list(record.communication_processes.values_list('id', flat=True)),
            [self.process.id],
        )

        postal = self.client.post(self.url, {
            'communication_process_id': self.process.id,
            'delivery': 'postal',
        }, format='json')
        self.assertEqual(postal.status_code, 400)
        self.assertEqual(postal.data['error'], 'no_documents')

    def test_several_processes_are_stored_together(self):
        self.user.user_permissions.set([Permission.objects.get(
            codename='view_communicationprocess',
            content_type=ContentType.objects.get_for_model(CommunicationProcess),
        )])
        other = CommunicationProcess.objects.create(token='PROC-API-2')
        communication = Communication.objects.create(process=other, type_tokens='email', used_address='Altra')
        document = Document.objects.create(entity_id=communication.id, service='hdd', document_name='altre')
        CommunicationFile.objects.create(
            communication=communication, file=document, attach_to_email=True, attach_to_letter=False,
        )
        response = self.client.post(self.url, {
            'communication_process_ids': [other.id, self.process.id],
            'delivery': 'email',
        }, format='json')
        self.assertEqual(response.status_code, 202)
        download = response.data['download']
        self.assertEqual(download['source'], 'process')
        self.assertEqual(download['invoice_count'], 2)
        self.assertCountEqual(download['communication_process_ids'], [other.id, self.process.id])
        self.assertCountEqual(download['communication_process_tokens'], ['PROC-API-2', 'PROC-API'])
        record = BillingDocumentDownload.objects.get(id=download['id'])
        self.assertIsNone(record.communication_process_id)
        self.assertCountEqual(
            record.communication_processes.values_list('id', flat=True),
            [other.id, self.process.id],
        )

    def test_empty_selection_is_rejected(self):
        response = self.client.post(self.url, {
            'billing_ids': [self.billing.id],
            'payment_type_tokens': ['NO_SUCH'],
        }, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(BillingDocumentDownload.objects.count(), 0)

    def test_billing_permission_does_not_authorize_process_downloads(self):
        for field, value in (
            ('communication_process_id', self.process.id),
            ('communication_process_ids', [self.process.id]),
        ):
            with self.subTest(field=field):
                preview = self.client.get(reverse('billing-document-download-preview'), {
                    field: str(self.process.id),
                })
                self.assertEqual(preview.status_code, 403)
                response = self.client.post(self.url, {field: value}, format='json')
                self.assertEqual(response.status_code, 403)
        self.assertFalse(BillingDocumentDownload.objects.exists())

    def test_process_permission_does_not_authorize_billing_downloads(self):
        self.user.user_permissions.set([Permission.objects.get(
            codename='view_communicationprocess',
            content_type=ContentType.objects.get_for_model(CommunicationProcess),
        )])
        preview = self.client.get(reverse('billing-document-download-preview'), {
            'billing_ids': str(self.billing.id),
        })
        self.assertEqual(preview.status_code, 403)
        response = self.client.post(self.url, {
            'billing_ids': [self.billing.id],
        }, format='json')
        self.assertEqual(response.status_code, 403)
        self.assertFalse(BillingDocumentDownload.objects.exists())

    def test_history_only_includes_current_users_downloads(self):
        own = BillingDocumentDownload.objects.create(billing=self.billing, requested_by=self.user)
        other_user = User.objects.create_user(username='other')
        BillingDocumentDownload.objects.bulk_create([
            BillingDocumentDownload(billing=self.billing, requested_by=other_user)
            for _ in range(100)
        ])
        BillingDocumentDownload.objects.create(billing=self.billing, requested_by=None)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual([download['id'] for download in response.data], [own.id])

    def test_requires_view_permission(self):
        stranger = User.objects.create_user(username='stranger', password='secret')
        client = APIClient()
        client.force_authenticate(user=stranger)
        self.assertEqual(client.get(self.url).status_code, 403)
        self.assertEqual(APIClient().get(self.url).status_code, 401)
