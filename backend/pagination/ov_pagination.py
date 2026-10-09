from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response


class OVLimitPagination(PageNumberPagination):
    """
    Pagination for the OV API.

    Two differences from DRF's ``PageNumberPagination``:

    1. The page size is read from the ``limit`` query parameter instead of
       ``page_size``.
    2. ``get_paginated_response`` returns an explicit
       ``{count, page, limit, total_pages, results}`` envelope, matching
       ``ContractListResponse`` in ``docs/ov/openapi.yaml``.

    An out-of-range or non-numeric page number surfaces as
    ``rest_framework.exceptions.NotFound`` from ``paginate_queryset`` so the
    calling view can translate it into the HTTP 400 documented in the spec.
    """

    page_query_param = "page"
    page_size_query_param = "limit"
    page_size = 20
    max_page_size = 100

    def get_page_size(self, request):
        """
        Clamp ``limit`` to ``max_page_size``.

        DRF's default implementation silently falls back to ``page_size`` when
        the requested value is invalid or above the cutoff; clamping keeps the
        behaviour documented in the spec ("el servidor acota el valor al
        máximo configurado aunque se solicite uno mayor").
        """
        raw = request.query_params.get(self.page_size_query_param)
        if raw is None or raw == "":
            return self.page_size
        try:
            value = int(raw)
        except (TypeError, ValueError):
            return self.page_size
        if value < 1:
            return self.page_size
        return min(value, self.max_page_size)

    def get_paginated_response(self, data):
        return Response(
            {
                "count": self.page.paginator.count,
                "page": self.page.number,
                "limit": self.get_page_size(self.request),
                "total_pages": self.page.paginator.num_pages,
                "results": data,
            }
        )


class OVConsumptionPagination(PageNumberPagination):
    """
    Pagination for ``GET /ov/consumptions/``.

    Keeps DRF's standard ``{count, next, previous, results}`` envelope (the
    ``ConsumptionHistoryResponse`` schema) and reads the page size from the
    ``page_size`` query parameter. DRF's ``get_page_size`` clamps the value to
    ``max_page_size`` and falls back to ``page_size`` for invalid input, which
    matches the spec ("el servidor acota el valor al máximo indicado aunque se
    solicite uno mayor").

    An out-of-range or non-numeric page number surfaces as
    ``rest_framework.exceptions.NotFound`` from ``paginate_queryset`` so the
    calling view can translate it into the HTTP 400 documented in the spec.
    """

    page_query_param = "page"
    page_size_query_param = "page_size"
    page_size = 50
    max_page_size = 100
