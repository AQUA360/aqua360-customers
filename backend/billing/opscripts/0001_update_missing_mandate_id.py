from django.core.management.color import color_style

from billing.models import (
    GeneralPayment,
    GeneralPaymentMandateLog,
)
from contract.signals import *

style = color_style()


def run():
    general_payments_with_mndt = GeneralPayment.objects.filter(
        mandate_id__isnull=False
    ).distinct()

    general_payments_without_mndt = GeneralPayment.objects.filter(
        mandate_id__isnull=True,
        IBAN__isnull=False,
        IBAN__iban__isnull=False
    ).distinct()

    gen_payment_sepa_no_iban = GeneralPayment.objects.filter(
        Q(IBAN__isnull=True) | Q(IBAN__iban__isnull=True)
    ).filter(
        type__token='DIRECT_DEBIT'
        ).distinct()
    contracts_with_sepa_no_iban = Contract.objects.filter(
        payment__in=gen_payment_sepa_no_iban,
        is_active=True
    ).distinct()
    # set error logger
    if len(gen_payment_sepa_no_iban) > 0:
        print(style.ERROR(
            f"Found {len(gen_payment_sepa_no_iban)} general payments with SEPA as payment method and no iban"
        ))
        if len(contracts_with_sepa_no_iban) == 0:
            print(style.WARNING("No affected contracts found"))
            print("-------\n")
    if len(contracts_with_sepa_no_iban) > 0:
        print(style.ERROR(
            f"Found {len(contracts_with_sepa_no_iban)} contracts with SEPA as payment method and no iban"
        ))
        print("Showing first contracts with SEPA as payment method and no IBAN:")
        for csepn in contracts_with_sepa_no_iban[:5]:
            print(csepn.token)
        print("-------\n")

    print(f'Found {len(general_payments_with_mndt)} general payments with mandate id')
    print(f'Found {len(general_payments_without_mndt)} general payments without mandate id')

    contracts = Contract.objects.filter(
        payment__in=general_payments_without_mndt,
        is_active=True
    ).distinct()

    contract_without_payment = Contract.objects.filter(
        payment__isnull=True,
        is_active=True,
    ).distinct()

    if len(contract_without_payment) > 0:
        print("\n-------")
        print(style.ERROR(
            f"Found {len(contract_without_payment)} contracts without payment"
        ))
        print(style.WARNING("Showing first contracts without payment:"))
        for cwp in contract_without_payment[:5]:
            print(cwp.token)
        print("-------\n")

    print(f'Found {len(contracts)} contracts with missing mandate id')

    payments_to_update = []
    payments_with_repeated_mandate = []
    set_mandate_id = set()
    logs_to_create = []

    counter = 0

    for contract in contracts:
        counter += 1
        if counter % 1000 == 0:
            print(f"Processed {counter} contracts of {len(contracts)}")
        new_mandate_id = generate_mandate_id(contract.payment, contract.token)
        if GeneralPayment.objects.filter(mandate_id=new_mandate_id).exists():
            print(f"Mandate id {new_mandate_id} for contract {contract.token} already exists")
            continue
        if new_mandate_id in set_mandate_id:
            payments_with_repeated_mandate.append({'contract': contract, 'mandate_id': new_mandate_id})
            # continue # if we want to skip contracts with repeated mandate id

        set_mandate_id.add(new_mandate_id)
        logs_to_create.append(GeneralPaymentMandateLog(
            general_payment=contract.payment,
            previous_mandate_id=contract.payment.mandate_id if contract.payment else None,
            new_mandate_id=new_mandate_id,
            user=None,
            is_manual=False
        ))
        contract.payment.mandate_id = new_mandate_id
        payments_to_update.append(contract.payment)

    print(f'Found {len(payments_to_update)} payments to update')

    print(style.WARNING(
        f"Found {len(payments_with_repeated_mandate)} contracts with repeated mandate id"
    ))
    for pwrm in payments_with_repeated_mandate:
        print(style.ERROR(
            f"Contract {pwrm['contract'].token} has repeated mandate id {pwrm['mandate_id']}"
        ))

    print(f"Updating now and creating mandate id and logs for {len(payments_to_update)} contracts")
    GeneralPayment.objects.bulk_update(payments_to_update, ['mandate_id'], batch_size=1000)
    GeneralPaymentMandateLog.objects.bulk_create(logs_to_create, batch_size=1000)
    print(style.SUCCESS(f"Updated {len(payments_to_update)} payments"))
    print(style.SUCCESS(f"Created {len(logs_to_create)} mandate id and logs"))
