import re

from django.db.models import Q
from rest_framework import status
from rest_framework.authentication import TokenAuthentication
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ov.serializers import PropertyItemSerializer
from pagination.ov_pagination import OVLimitPagination
from service.models import Property

_PROPERTY_SEARCH_SPLIT = re.compile(r"[\s,.;/]+")


def _property_search_tokens(search):
    return [token for token in _PROPERTY_SEARCH_SPLIT.split(search) if token]


class GMAOPropertySearchView(APIView):
    """GET /gmao/v1/properties/?search=<text>[&page=<n>&limit=<n>]

    Cerca d'adreces de propietats actives per a la integració amb el GMAO,
    perquè els operaris de camp localitzin la zona de treball. `search` és
    obligatori i ha de tenir com a mínim 3 caràcters (400 si no) per evitar
    escanejos complets a cada tecla. La puntuació (espais, `, . ; /`) es
    tracta com a separador: cada paraula ha de coincidir amb algun camp
    (carrer, número, ciutat, codi postal, nom o cadastral) i tots els termes
    es combinen amb AND. Els resultats es retornen paginats amb l'embolcall
    `{count, page, limit, total_pages, results}`.
    """

    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]
    pagination_class = OVLimitPagination
    min_search_length = 3

    def get(self, request):
        search = (request.query_params.get("search") or "").strip()
        if not search:
            return Response(
                {"error": "Search is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if len(search) < self.min_search_length:
            return Response(
                {"error": "Search must be at least 3 characters"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        tokens = _property_search_tokens(search)
        if not tokens:
            return Response(
                {"error": "Search must contain at least one valid term"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        filters = Q()
        for token in tokens:
            token_filters = (
                Q(address_street__name__icontains=token)
                | Q(address_street__name_2__icontains=token)
                | Q(address_street__type__abbreviation__icontains=token)
                | Q(address_city__name__icontains=token)
                | Q(address_postal_code__code__icontains=token)
                | Q(name__icontains=token)
                | Q(cadastral__icontains=token)
            )
            try:
                token_filters |= Q(address_street_number__number=int(token))
            except ValueError:
                pass
            filters &= token_filters

        properties = (
            Property.objects.filter(is_active=True)
            .filter(filters)
            .select_related(
                "address_street",
                "address_street_number",
                "address_postal_code",
                "address_city",
            )
            .order_by("address_street__name", "address_street_number__number")
        )

        paginator = self.pagination_class()
        try:
            page = paginator.paginate_queryset(properties, request, view=self)
        except NotFound:
            return Response(
                {"error": "Invalid page"}, status=status.HTTP_400_BAD_REQUEST
            )

        serializer = PropertyItemSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)
