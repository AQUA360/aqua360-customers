"""Avisos dels pagaments que arriben retornats en un fitxer bancari.

Abans de processar un retorn, l'usuari ha de saber si el pagament és d'un abonat
donat de baixa o d'una factura que ja s'ha anul·lat i refet: en aquest segon cas el
deute ja és a la factura nova i no s'ha de tornar a reclamar l'antiga; si el cobrament
havia passat al saldo, se'n treurà (veure rectified_invoice_return_service).
"""
from billing.models import Invoice, Payment
from billing.utils.rectified_invoice_return_service import rectified_return_plan
from contract.models import Contract
from coredata.models import ConfigProject


def _config_value(token):
    return ConfigProject.objects.filter(token=token).values_list('value', flat=True).first()


def payment_contract(payment):
    """Contracte del pagament (directe, de la factura, de la sol·licitud, de la baixa o del compromís)."""
    if payment.commitment_deposit_id and payment.commitment_deposit.contract_id:
        return payment.commitment_deposit.contract
    invoice = payment.invoice
    if invoice:
        if invoice.contract_id:
            return invoice.contract
        if invoice.contract_request_id:
            return Contract.objects.filter(contract_request_id=invoice.contract_request_id).order_by('id').first()
        if invoice.contract_termination_id and invoice.contract_termination.contract_id:
            return invoice.contract_termination.contract
    return payment.contract


def is_rectified_invoice(invoice, cancelled_token=None):
    """La factura s'ha anul·lat amb una rectificativa (i, normalment, s'ha refet)."""
    if not invoice:
        return False
    if invoice.return_token:
        return True
    if cancelled_token is None:
        cancelled_token = _config_value('invoice_status_cancelled_token')
    return bool(cancelled_token and invoice.status_id and invoice.status.token == cancelled_token)


def payment_return_warnings(payment, terminated_token=None, cancelled_token=None, invoice_type_token=None):
    """Avisos d'un pagament retornat: abonat de baixa i factura rectificada/refeta."""
    contract = payment_contract(payment)
    contract_terminated = bool(
        terminated_token and contract and contract.status_id and contract.status.token == terminated_token
    )
    invoice = payment.invoice
    invoice_rectified = is_rectified_invoice(invoice, cancelled_token or '')
    rectifying_invoice = None
    refactored_invoice = None
    balance_plan = None
    if invoice_rectified:
        invoices = Invoice.objects.all()
        if invoice_type_token:
            invoices = invoices.filter(type__token=invoice_type_token)
        if invoice.return_token:
            rectifying_invoice = invoices.filter(token=invoice.return_token).values_list('serie_final', flat=True).first()
        refactored_invoice = (
            invoices.filter(refactored_token=invoice.token).exclude(token__isnull=True)
            .order_by('-created_at').values_list('serie_final', flat=True).first()
            if invoice.token else None
        )
        plan = rectified_return_plan(payment)
        if plan:
            balance_plan = {
                "balance_to_remove": float(plan['balance_to_remove']),
                "refactored_debt": float(plan['refactored_debt']),
                "uncovered": float(plan['uncovered']),
            }
    return {
        "contract_terminated": contract_terminated,
        "contract_termination_date": str(contract.termination_date) if contract_terminated and contract.termination_date else None,
        "invoice_rectified": invoice_rectified,
        "rectifying_invoice": rectifying_invoice,
        "refactored_invoice": refactored_invoice,
        # Saldo que es traurà i deute que quedarà a la factura refeta en processar el retorn
        "rectified_balance": balance_plan,
    }


def annotate_rejection_warnings(rejections):
    """Afegeix els avisos a cada devolució trobada (amb `payment_id`) de la previsualització."""
    payment_ids = [r.get("payment_id") for r in rejections if r.get("payment_id")]
    if not payment_ids:
        return rejections
    terminated_token = _config_value('contract_terminated_status')
    cancelled_token = _config_value('invoice_status_cancelled_token')
    invoice_type_token = _config_value('invoice_type_invoice_token')
    payments = Payment.objects.filter(id__in=payment_ids).select_related(
        'contract__status',
        'invoice__status', 'invoice__contract__status', 'invoice__contract_termination__contract__status',
        'commitment_deposit__contract__status',
    )
    warnings_by_payment = {
        payment.id: payment_return_warnings(payment, terminated_token, cancelled_token, invoice_type_token)
        for payment in payments
    }
    for rejection in rejections:
        warnings = warnings_by_payment.get(rejection.get("payment_id"))
        if warnings:
            rejection.update(warnings)
    return rejections
