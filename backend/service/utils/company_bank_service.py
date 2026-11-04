from coredata.models import ConfigProject


def get_company_bank(company, invoice=None):
    """
    Retorna el CompanyBank a utilitzar per a una factura o document de cobrament.

    Prioritat:
      1. El compte de cobrament assignat a la factura (payment_company_bank).
      2. El compte per defecte i actiu de l'empresa.
      3. El primer compte actiu de l'empresa.
      4. El primer compte de l'empresa.

    Els comptes s'ordenen per id perquè la tria no depengui de l'ordre en què
    la base de dades retorna les files. S'itera sobre .all() per aprofitar un
    possible prefetch de company_banks.
    """
    if invoice is not None and getattr(invoice, 'payment_company_bank', None):
        return invoice.payment_company_bank

    if not company:
        return None

    banks = sorted(company.company_banks.all(), key=lambda cb: cb.id)
    if not banks:
        return None

    for cb in banks:
        if cb.is_default and cb.is_active:
            return cb
    for cb in banks:
        if cb.is_active:
            return cb
    return banks[0]


def get_payment_company_bank(company, payment):
    """
    Retorna el CompanyBank on es cobra un pagament (codi de barres, IBAN i SWIFT
    dels documents de cobrament).

    Prioritat:
      1. Transferència o pagament bancari: el compte actiu de l'empresa amb
         l'IBAN triat al pagament (payment_bank).
      2. El compte de cobrament de la factura o, en un compromís de pagament,
         el de la seva primera factura o el del pagament del contracte.
      3. El compte de l'empresa segons get_company_bank.
    """
    if not company:
        return None

    payment_bank = getattr(payment, 'payment_bank', None)
    if payment_bank and getattr(payment, 'payment_type_token', None) in ('BANK_TRANSFER', _bank_payment_token()):
        selected = company.company_banks.filter(iban=payment_bank, is_active=True).first()
        if selected:
            return selected

    invoice = payment.invoice
    commitment_deposit = getattr(payment, 'commitment_deposit', None)
    if not invoice and commitment_deposit:
        invoice = commitment_deposit.invoices.first()
        if not (invoice and invoice.payment_company_bank):
            contract_payment = getattr(commitment_deposit.contract, 'payment', None) if commitment_deposit.contract else None
            if contract_payment and contract_payment.company_iban:
                return contract_payment.company_iban

    return get_company_bank(company, invoice)


def _bank_payment_token():
    return ConfigProject.objects.filter(token='bank_payment_token').values_list('value', flat=True).first()
