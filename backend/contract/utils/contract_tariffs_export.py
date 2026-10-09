"""
Export CSV "Contractes: informació i PriceRate".

Se sembla a l'export general de contractes (base columns reutilitzant contract_csv_export),
i afegeix 2 columnes per cada Product d'origen aigua (Product.origin_id == 1):
- token de PriceRate seleccionada al contracte
- nom de la PriceRate seleccionada al contracte

Les "PriceRates seleccionades" les obtenim de Contract.price_rates (ContractPriceRate),
i de cada ContractPriceRate agafem price_rate.product.
"""

import csv
from io import StringIO

from pricing.models import Product
from contract.models import ContractPriceRate

from contract.utils.contract_csv_export import (
    build_contract_export_headers,
    contract_row_values,
    debt_amount_by_contract_id,
    prepare_contract_export_queryset,
)


def _water_products_origin_id() -> int:
    # Requisit del frontend: "id origen: 1"
    return 1


def _get_water_products_ordered(water_origin_id: int):
    """
    Productes d'origen aigua ordenats per Product.position (i després id).
    Si position és null, sempre cau al final per id.
    """
    return list(
        Product.objects.filter(origin_id=water_origin_id).order_by(
            "position", "id"
        )
    )


def _contract_price_rate_token_name_by_contract_and_product(
    contract_ids: list[int], water_origin_id: int
):
    """
    Retorna mapa:
      contract_id -> { product_id -> (price_rate_token, price_rate_name) }
    """
    rows = (
        ContractPriceRate.objects.filter(
            contracts_price_rates__id__in=contract_ids,
            is_active=True,
            price_rate__product__origin_id=water_origin_id,
        )
        .order_by(
            "contracts_price_rates__id",
            "price_rate__product_id",
            "id",
        )
        .values(
            "contracts_price_rates__id",
            "price_rate__product_id",
            "price_rate__token",
            "price_rate__name",
            "id",
        )
    )

    out = {}
    for r in rows:
        cid = r["contracts_price_rates__id"]
        pid = r["price_rate__product_id"]
        out.setdefault(cid, {})
        # com que anem ordenats per id ASC, primer que entra és el que fem servir
        if pid not in out[cid]:
            out[cid][pid] = (
                (r.get("price_rate__token") or "").strip(),
                (r.get("price_rate__name") or "").strip(),
            )
    return out


def build_contract_tariffs_export_csv_bytes(filtered_queryset):
    variable_names = []  # reutilitzem el mateix "base columns" de l'export 1
    base_headers = build_contract_export_headers(variable_names)

    water_origin_id = _water_products_origin_id()
    water_products = _get_water_products_ordered(water_origin_id)

    tariff_headers = []
    # Dues columnes per producte d'aigua:
    # - columna 1: codi (token) de la PriceRate del contracte per aquest producte
    # - columna 2: nom de la PriceRate del contracte per aquest producte
    # Els títols mostren el token i el nom del *producte* (no la PriceRate).
    for idx, p in enumerate(water_products, start=1):
        product_token = (p.token or '').strip() or str(p.id)
        product_name = (p.name or '').strip()
        tariff_headers.append(f"P{idx} {product_token}")
        tariff_headers.append(f"P{idx} {product_name}")

    export_qs = prepare_contract_export_queryset(filtered_queryset)

    contract_ids = list(export_qs.values_list("pk", flat=True))
    debt_map = debt_amount_by_contract_id(contract_ids)
    pr_by_contract_pid = (
        _contract_price_rate_token_name_by_contract_and_product(
            contract_ids=contract_ids,
            water_origin_id=water_origin_id,
        )
    )

    buffer = StringIO()
    buffer.write("\ufeff")
    writer = csv.writer(buffer, delimiter=";")
    writer.writerow(base_headers + tariff_headers)

    for contract in export_qs.iterator(chunk_size=500):
        row = contract_row_values(contract, variable_names, debt_map, {})
        by_product = pr_by_contract_pid.get(contract.id, {})
        for p in water_products:
            entry = by_product.get(p.id)
            if entry:
                token, name = entry
                row.append(token)
                row.append(name)
            else:
                row.append("")
                row.append("")

        writer.writerow(row)

    return buffer.getvalue().encode("utf-8")

