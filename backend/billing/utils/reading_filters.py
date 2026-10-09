from django.db.models import Q

# Una lectura es considera PENDENT de facturar si no te cap factura definitiva
# (Invoice.type_final == 'F'). Les prefactures ('P') no compten com a facturada.
#
# NO facis servir mai la forma  Q(invoices__isnull=True) | Q(invoices__type_final='P').
# 'invoices' es una relacio multivaluada (M2M Invoice.readings): dins d'un filter()
# l'OR s'avalua sobre el JOIN, de manera que una lectura amb prefactura (P) I factura
# definitiva (F) alhora compleix la segona branca i passa el filtre com si fos pendent.
# Aixo va fer que el lot "SANT JULIA DE VILATORTA TELELECTURA AGOST" recollis 20
# lectures ja facturades (liquidacions de baixa i una liquidacio amb rectificativa),
# perque la PF/... queda vinculada a la lectura per sempre.
#
# La forma negada genera un NOT EXISTS (subconsulta), que si expressa "cap factura F".
PENDING_READING_FILTER = ~Q(invoices__type_final='F')

# Complementari: lectures que ja tenen factura definitiva.
BILLED_READING_FILTER = Q(invoices__type_final='F')
