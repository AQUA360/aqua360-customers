import calendar
import datetime
import re
import unicodedata
from io import BytesIO

from django.http import HttpResponse
from rest_framework import status
from rest_framework.response import Response

from contract.models import Bail, Contract
from coredata.models import StreetType
from statistics.utils.incasol import resolve_incasol_num
from statistics.utils.report_filters import get_multi_ids, contract_multi_filter_q
from statistics.views.reports_views import save_report

# Sufix de canvi de nom que el sistema afegeix al contracte antic: "<base_token>/0001".
# Un Bail pot quedar vinculat a la fila de Contract que originalment tenia el token
# "net" i que, arran d'un canvi de nom posterior, ha quedat renombrada amb aquest
# sufix — cal recuperar sempre el token base perquè l'identificador de la fiança
# coincideixi amb el contracte vigent (i no amb l'històric intern).
_SUFFIX_RE = re.compile(r"/\d+$")


def _base_token(token):
    return _SUFFIX_RE.sub("", token) if token else token


def _trimestre_from_month(month):
    if month in (1, 2, 3):
        return "01"
    if month in (4, 5, 6):
        return "02"
    if month in (7, 8, 9):
        return "03"
    return "04"


def _presentation_deadline(end_date):
    next_month = end_date.month + 1
    next_year = end_date.year
    if next_month > 12:
        next_month = 1
        next_year += 1
    last_day = calendar.monthrange(next_year, next_month)[1]
    return datetime.date(next_year, next_month, last_day)


def _remove_accents(text):
    nfd = unicodedata.normalize('NFD', str(text))
    return ''.join(c for c in nfd if unicodedata.category(c) != 'Mn')


def _txt(content, length):
    return _remove_accents(content or "")[:length].upper().ljust(length)


def _digits(value, length):
    cents = int(round((value or 0) * 100))
    return str(abs(cents)).rjust(length, "0")[-length:]


def _build_header_line(n_con, trimestre, year, num_altes, num_baixes, import_altes, import_baixes):
    line = ""
    line += n_con[:5].ljust(5)
    line += str(trimestre).rjust(5, "0")
    line += "T"
    line += str(year).rjust(4, "0")
    line += "0" * 9
    line += str(num_altes).rjust(6, "0")
    line += str(num_baixes).rjust(6, "0")
    line += "+"
    line += _digits(import_altes, 10)
    line += "-"
    line += _digits(import_baixes, 10)
    return line


def _build_detail_line(tipus, contract_token, bail_date, amount, street_type, street_name,
                        street_number, stair, floor, door, postal_code, municipi,
                        nif, cognoms, nom):
    sign = "-" if amount < 0 else "+"
    line = ""
    line += _txt(tipus, 2)
    line += _txt(contract_token, 30)
    line += bail_date.strftime('%d%m%Y') if bail_date else "".ljust(8)
    line += sign
    line += _digits(amount, 10)
    line += _txt(street_type, 5)
    line += _txt(street_name, 50)
    line += _txt(street_number, 9)
    line += _txt(stair, 1)
    line += " "
    line += _txt(floor, 1)
    line += _txt(door, 1)
    line += _txt(postal_code, 5)
    line += _txt(municipi, 100)
    line += _txt("", 21)
    line += _txt(nif, 9)
    line += " "
    line += _txt(cognoms, 50)
    line += _txt(nom, 15)
    line += "0" * 9
    line += " " * 74
    return line


def generate_incasol_liquidation_report(request, black_fill=None, white_bold_font=None, task=None):
    try:
        date_range = request.data.get('date_range', None)
        name = request.data.get('name', '')
        type_id = request.data.get('type_id', None)
        exploitation_id = request.data.get('exploitation_id', None)

        if not date_range:
            return Response({"error": "date range is required."}, status=status.HTTP_400_BAD_REQUEST), None, None

        try:
            start_date = datetime.datetime.strptime(date_range[0], '%Y-%m-%dT%H:%M:%S.%fZ')
            end_date = datetime.datetime.strptime(date_range[1], '%Y-%m-%dT%H:%M:%S.%fZ')
        except Exception as e:
            return Response({"error": f"Ha ocorregut un error inesperat: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR), None, None

        multi_ids = get_multi_ids(request.data)
        multi_q = contract_multi_filter_q(person_ids=multi_ids['person_ids'], contract_ids=multi_ids['contract_ids'])
        contract_ids = None
        if multi_q:
            contract_ids = Contract.objects.filter(multi_q).distinct().values_list('id', flat=True)

        bails_altes = Bail.objects.filter(created_at__range=(start_date, end_date))
        bails_baixes = Bail.objects.filter(return_date__range=(start_date, end_date))
        if contract_ids is not None:
            bails_altes = bails_altes.filter(contract__id__in=contract_ids)
            bails_baixes = bails_baixes.filter(contract__id__in=contract_ids)

        incasol_num = resolve_incasol_num(exploitation_id)
        trimestre = _trimestre_from_month(end_date.month)
        n_con = f"S{incasol_num}"

        num_altes = bails_altes.count()
        num_baixes = bails_baixes.count()
        import_altes = round(sum(b.amount for b in bails_altes), 2)
        import_baixes = round(sum(b.amount for b in bails_baixes), 2)

        street_types_by_id = {st.id: st for st in StreetType.objects.all()}
        total_movements = num_altes + num_baixes

        lines = [_build_header_line(
            n_con, trimestre, end_date.year, num_altes, num_baixes, import_altes, import_baixes,
        )]

        def _bail_line(bail, tipus, bail_amount, bail_date):
            contract = bail.contract
            address = contract.supply_point_default.address if contract.supply_point_default else None
            street = address.street if address else None
            st_type = street_types_by_id.get(street.type_id) if street and street.type_id else None
            street_type = (st_type.aca_abbreviation or st_type.abbreviation or "") if st_type else ""
            municipi = ""
            if (contract.supply_point_default and contract.supply_point_default.connection
                    and contract.supply_point_default.connection.exploitation
                    and contract.supply_point_default.connection.exploitation.name):
                municipi = contract.supply_point_default.connection.exploitation.name.upper()
            holder = contract.holder
            return _build_detail_line(
                tipus, _base_token(contract.token), bail_date, bail_amount,
                street_type, street.name if street else "",
                str(address.street_number) if address and address.street_number else "",
                address.stair if address else "", address.floor if address else "", address.door if address else "",
                address.postal_code if address else "", municipi,
                holder.token if holder else "",
                holder.surname if holder else "",
                holder.name if holder else "",
            )

        idx = 0
        for bail in bails_altes:
            idx += 1
            if task and idx % 50 == 0:
                task.update_state(state='PROGRESS', meta={
                    'current': idx, 'total': total_movements,
                    'percent': round((idx / total_movements) * 100, 2) if total_movements else 0.0,
                })
            lines.append(_bail_line(bail, "FI", round(bail.amount, 2), bail.created_at))

        for bail in bails_baixes:
            idx += 1
            if task and idx % 50 == 0:
                task.update_state(state='PROGRESS', meta={
                    'current': idx, 'total': total_movements,
                    'percent': round((idx / total_movements) * 100, 2) if total_movements else 0.0,
                })
            lines.append(_bail_line(bail, "BA", -round(bail.amount, 2), bail.return_date))

        content_file = BytesIO()
        for line in lines:
            content_file.write((line + "\r\n").encode("utf-8"))

        filename = f"INCASOL_LIQUIDACIO_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"

        response = HttpResponse(content_file.getvalue(), content_type="text/plain")
        response["Content-Disposition"] = f'attachment; filename="{filename}"'

        document_id = save_report(
            content=content_file.getvalue(), filename=filename, name=name, type_id=type_id,
            start_date=start_date, end_date=end_date,
        )

        return response, document_id, None
    except Exception as e:
        return Response({"error": f"Ha ocorregut un error inesperat: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR), None, None
