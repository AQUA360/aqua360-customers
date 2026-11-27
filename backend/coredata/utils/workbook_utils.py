from io import BytesIO


def workbook_to_bytes(wb):
    """Serialitza un Workbook d'openpyxl en memòria.

    Evita desar fitxers temporals al directori de treball, que dins del
    contenidor no és escrivible per l'usuari que executa el procés.
    """
    buffer = BytesIO()
    wb.save(buffer)
    return buffer.getvalue()
