from django.utils import timezone


def exclude_future_invoices(queryset):
    """Treu les factures amb data d'emissió posterior a avui.

    L'OV no les ha de mostrar (ni deixar-les consultar, descarregar o pagar)
    fins que arribi la seva data. Les factures sense `issue_date` es mantenen.
    """
    return queryset.exclude(issue_date__gt=timezone.localdate())
