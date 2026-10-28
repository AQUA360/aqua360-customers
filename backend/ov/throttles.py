from rest_framework.throttling import SimpleRateThrottle


class DniEnumerationThrottle(SimpleRateThrottle):
    """
    Rate limit for `GET /ov/contracts/`, which returns contract and holder data
    for an arbitrary DNI supplied in the query string.

    Without a limit the endpoint can be used to enumerate the customer base: a
    caller only has to guess a document number. The throttle bounds how many
    lookups one authenticated OV account can perform, which raises the cost of
    an enumeration run and makes it observable.

    The cache key is the authenticated user rather than the requested DNI: an
    attacker probing the customer base varies the DNI on every call, so a
    per-DNI counter would never trip.

    `.rate` is declared on the class so that no `DEFAULT_THROTTLE_RATES` entry
    -- and therefore no settings change -- is required.

    Note: this uses Django's default cache, which is `LocMemCache` in this
    project, so the counter is held per worker process and the effective limit
    is `rate * GUNICORN_WORKERS`. Pointing `cache` at a shared backend would
    make it exact.
    """

    scope = "ov_contracts_dni"
    rate = "10/min"

    def get_cache_key(self, request, view):
        user = getattr(request, "user", None)
        if user is not None and user.is_authenticated:
            ident = user.pk
        else:
            ident = self.get_ident(request)
        return self.cache_format % {"scope": self.scope, "ident": ident}


class PersonDataThrottle(DniEnumerationThrottle):
    """
    Rate limit for `GET /ov/person-data/?dni=`, which exposes the phones,
    emails and addresses of an arbitrary DNI. Same enumeration risk as
    `/ov/contracts/`, but contact data is more sensitive, so it has its own
    scope (it does not consume the contracts budget) and a slightly more
    generous rate to cover global prefills and SMS OTP checks.

    The counter is keyed by the authenticated OV account (see the parent
    class), which is shared by the external Virtual Office service.
    """

    scope = "ov_person_data_dni"
    rate = "35/min"


class QuickPayThrottle(DniEnumerationThrottle):
    """
    Rate limit for `POST /ov/invoice/quick-pay/`, which resolves an invoice
    from a contract number, an invoice number and its exact amount supplied by
    the caller without a contract token.

    The three fields make guessing harder than a bare DNI, but the endpoint
    still leaks whether a given combination exists, so it shares the same
    per-account budget approach as the other enumeration-prone endpoints. It
    has its own scope (it does not consume the contracts or person-data
    budgets) and a 35/min rate to cover peak traffic of the shared OV account.
    """

    scope = "ov_quick_pay"
    rate = "35/min"


class PaymentReceiptThrottle(DniEnumerationThrottle):
    """
    Rate limit for `GET /ov/payment-receipt/`.

    Payment tokens are sequential, so the endpoint is enumerable even when the
    caller also has to supply the contract token and the payer's DNI. It has its
    own scope (it does not consume the contracts or person-data budgets) and the
    same 35/min rate as the person-data lookup to cover peak traffic of the
    shared OV account.
    """

    scope = "ov_payment_receipt"
    rate = "35/min"


class ReturnRequestThrottle(DniEnumerationThrottle):
    """
    Rate limit for `POST /ov/invoice/return-request/`.

    Creating incidents is a write operation, so the endpoint must not be usable
    to flood the helpdesk queue by iterating invoice tokens. It has its own
    scope (it does not consume the contracts, person-data, quick-pay or receipt
    budgets) and the same 35/min rate as the other OV endpoints.
    """

    scope = "ov_invoice_return_request"
    rate = "35/min"


class ContractProcedureThrottle(DniEnumerationThrottle):
    """
    Rate limit for `POST /ov/procedures/contract/`.

    Creating contract requests is a write operation that also materialises
    `PersonBank`/`GeneralPayment` rows, so the endpoint must not be usable to
    flood the customer-service queue or create payment records in bulk by
    iterating DNIs and properties. It has its own scope (it does not consume
    the other OV budgets) and the same 35/min rate as the other OV endpoints.
    """

    scope = "ov_procedures_contract"
    rate = "35/min"
