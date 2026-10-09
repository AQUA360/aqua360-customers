def client_info_overlaps_header(pdf_buffer):
    """xhtml2pdf, amb pàgines de múltiples @frame (header/content/footer), no
    crea una pàgina nova quan el contingut desborda el content_frame: el
    torna a dibuixar des de dalt de la mateixa pàgina, sobreposant-se al que
    ja hi havia (típicament el header_frame). Ho detectem comprovant si hi ha
    blocs de text que es solapen geomètricament de manera significativa."""
    try:
        import fitz
        pdf_buffer.seek(0)
        doc = fitz.open(stream=pdf_buffer.getvalue(), filetype="pdf")
        try:
            for page in doc:
                blocks = [
                    fitz.Rect(b["bbox"])
                    for b in page.get_text("dict")["blocks"]
                    if b.get("lines")
                ]
                for i in range(len(blocks)):
                    for j in range(i + 1, len(blocks)):
                        inter = blocks[i] & blocks[j]
                        if inter.is_empty:
                            continue
                        min_area = min(blocks[i].get_area(), blocks[j].get_area())
                        if min_area > 0 and inter.get_area() / min_area > 0.3:
                            return True
            return False
        finally:
            doc.close()
    except Exception as e:
        print(f"Error en detectar overlap de contingut al PDF: {str(e)}")
        return False
