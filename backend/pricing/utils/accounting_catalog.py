from django.db.models import F, Q

from pricing.models import LineItemType

# Mateixes claus a l'Excel i al JSON, perquè el proveïdor pugui importar qualsevol dels dos.
ACCOUNTING_CATALOG_COLUMNS = (
    "Product.Company",
    "Product.name",
    "Product.token",
    "Product.Origin",
    "PriceRate.name",
    "PriceRate.token",
    "LineItemType.token",
    "LineItemType.name",
    "LineItemType.Iva",
    "LineItemType.tax_token",
    "LineItemType.tax_percent",
    "LineItemType.article.token",
    "LineItemType.article.name",
)


def _text(value):
    return value or ""


def accounting_catalog_queryset(exploitation_id=None):
    """
    Conceptes del tram vigent: els que es facturen ara i, per tant, els que
    es sincronitzen amb comptabilitat.

    El tram vigent és el `billing_range_active` de la tarifa. Si la tarifa no
    en té, es fan servir els trams oberts (sense data de fi).
    """
    queryset = (
        LineItemType.objects.filter(
            is_active=True,
            billing_range__isnull=False,
            billing_range__is_active=True,
            billing_range__price_rate__isnull=False,
            billing_range__price_rate__is_active=True,
            billing_range__price_rate__product__isnull=False,
            billing_range__price_rate__product__is_active=True,
        )
        .filter(
            Q(billing_range_id=F("billing_range__price_rate__billing_range_active_id"))
            | Q(
                billing_range__price_rate__billing_range_active__isnull=True,
                billing_range__end__isnull=True,
            )
        )
        .select_related(
            "billing_range__price_rate__product__company",
            "billing_range__price_rate__product__origin",
            "tax",
            "article",
        )
        .order_by(
            "billing_range__price_rate__product__name",
            "billing_range__price_rate__name",
            "name",
            "token",
        )
    )
    if exploitation_id:
        queryset = queryset.filter(
            Q(billing_range__price_rate__product__exploitation_id=exploitation_id)
            | Q(billing_range__price_rate__product__exploitation__isnull=True)
        )
    return queryset


def line_item_type_catalog_row(line_item):
    billing_range = line_item.billing_range
    price_rate = billing_range.price_rate if billing_range else None
    product = price_rate.product if price_rate else None
    company = product.company if product else None
    origin = product.origin if product else None
    tax = line_item.tax
    article = line_item.article
    return {
        "Product.Company": _text(company.name if company else None),
        "Product.name": _text(product.name if product else None),
        "Product.token": _text(product.token if product else None),
        "Product.Origin": _text((origin.name or origin.token) if origin else None),
        "PriceRate.name": _text(price_rate.name if price_rate else None),
        "PriceRate.token": _text(price_rate.token if price_rate else None),
        "LineItemType.token": _text(line_item.token),
        "LineItemType.name": _text(line_item.name),
        "LineItemType.Iva": _text(tax.name if tax else None),
        "LineItemType.tax_token": _text(tax.token if tax else None),
        "LineItemType.tax_percent": tax.percent if tax is not None and tax.percent is not None else None,
        "LineItemType.article.token": _text(article.token if article else None),
        "LineItemType.article.name": _text(article.name if article else None),
    }


def accounting_catalog_rows(exploitation_id=None):
    return [
        line_item_type_catalog_row(line_item)
        for line_item in accounting_catalog_queryset(exploitation_id)
    ]
