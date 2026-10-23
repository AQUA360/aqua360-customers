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
