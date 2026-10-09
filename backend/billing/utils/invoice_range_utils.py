import re

from django.db.models import BigIntegerField
from django.db.models.functions import Cast, Substr

SERIE_FINAL_PARTS_RE = re.compile(r'^(?P<prefix>.*?)(?P<number>\d+)$')


def split_serie_final(value):
    """Separa un serie_final (o un extrem de rang) en el prefix de serie i la part
    numerica final: "12345678" -> ("", "12345678"), "D1234567" -> ("D", "1234567"),
    "FC/AAAAMM/000001" -> ("FC/AAAAMM/", "000001").

    El prefix es tot el que hi ha abans de l'ultim grup de digits, sigui lletres
    ("D1234567") o serie i periode ("FC/AAAAMM/000001", "DDMMAAAAAE00000001"):
    es el tros que identifica la serie, i el rang [from, to]
    nomes es compara entre factures que el comparteixen. Amb numeros totalment
    numerics el prefix es buit i el filtre es comporta com un rang numeric directe.

    Retorna (None, None) si el valor no acaba en digits (p.ex. una cadena buida),
    perque el cridant pugui rebutjar-lo (retornant un 400) en lloc de petar amb un
    ValueError. Els clients que necessitin una altra regla ho poden personalitzar
    amb `invoice_range_utils_personalized.split_serie_final` (veure el hook al
    final d'aquest modul)."""
    match = SERIE_FINAL_PARTS_RE.match(str(value).strip())
    if not match:
        return None, None
    return match.group('prefix'), match.group('number')


def filter_invoices_by_serie_final_range(queryset, serie_final_from=None, serie_final_to=None, prefix=None):
    """Filtra un queryset d'Invoice pel rang del camp serie_final (numero de factura).

    El serie_final d'aquest sistema incrusta un digit de categoria/serie i l'any a
    l'inici (p.ex. "22612345" = categoria "2" + any "26" + seqüencial "12345"), així
    que un simple rang numeric pot barrejar series diferents que coincideixin en
    magnitud. Quan es passa `prefix`, només es consideren les factures el serie_final
    de les quals comenci per aquest prefix, de manera que el rang [from, to] queda
    acotat a una unica serie/categoria.

    El prefix alfabetic dels extrems (i de `prefix`) surt de `split_serie_final`,
    que per defecte no n'admet cap: amb series numeriques el filtre es comporta
    igual que un rang numeric directe. Als clients que personalitzen
    `split_serie_final` amb series amb lletra (p.ex. "D1234567"), els extrems es
    poden donar amb o sense la lletra, el rang es compara nomes contra la part
    numerica de les factures d'aquella mateixa serie i les factures amb un prefix
    alfabetic diferent queden fora del rang."""
    bounds = {}
    alphas = set()

    if prefix:
        # El prefix pot ser nomes la part alfabetica ("D"), que no es un numero de
        # factura valid per si sol: s'hi afegeix un digit per poder-ne treure la
        # lletra. Sense aixo, un prefix "D" amb extrems donats sense lletra
        # deixaria el regex en ^\d+$ i el rang tornaria 0 factures sense avisar.
        prefix_alpha, _ = split_serie_final(prefix)
        if prefix_alpha is None:
            prefix_alpha, _ = split_serie_final(f"{prefix}0")
        if prefix_alpha:
            alphas.add(prefix_alpha)

    for key, value in (('from', serie_final_from), ('to', serie_final_to)):
        # Nomes `None` vol dir "sense limit" (ho fa servir la previsualitzacio per
        # buscar les factures anteriors al rang). Una cadena buida es un extrem
        # invalid i ha de petar, com abans amb int(''): hi ha cridants que no
        # validen els extrems (report_service.py::generate_register_billing_summary)
        # i, si '' es tractes com "sense limit", el rang s'obriria de bat a bat.
        if value is None:
            continue
        value_alpha, value_number = split_serie_final(value)
        if value_number is None:
            raise ValueError(f"serie_final_{key} no te un format de numero de factura valid: {value}")
        if value_alpha:
            alphas.add(value_alpha)
        bounds[key] = int(value_number)

    if len(alphas) > 1:
        raise ValueError(f"El rang barreja series amb prefixos diferents: {sorted(alphas)}")
    alpha_prefix = alphas.pop() if alphas else ''

    numeric_qs = queryset.filter(serie_final__regex=rf'^{re.escape(alpha_prefix)}\d+$')
    if prefix:
        numeric_qs = numeric_qs.filter(serie_final__startswith=str(prefix))
    numeric_qs = numeric_qs.annotate(
        serie_final_num=Cast(
            Substr('serie_final', len(alpha_prefix) + 1),
            output_field=BigIntegerField(),
        )
    )
    if 'from' in bounds:
        numeric_qs = numeric_qs.filter(serie_final_num__gte=bounds['from'])
    if 'to' in bounds:
        numeric_qs = numeric_qs.filter(serie_final_num__lte=bounds['to'])
    return numeric_qs


# Permet personalitzar per client: si existeix invoice_range_utils_personalized,
# s'usa la seva split_serie_final en lloc de la d'aquest modul (series amb prefix
# alfabetic). `filter_invoices_by_serie_final_range` la resol per nom en cada
# crida, per tant tambe fa servir la versio personalitzada.
try:
    from billing.utils import invoice_range_utils_personalized
    if hasattr(invoice_range_utils_personalized, 'split_serie_final'):
        split_serie_final = invoice_range_utils_personalized.split_serie_final
except ImportError:
    pass
