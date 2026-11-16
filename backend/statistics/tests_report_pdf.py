import datetime

from django.test import SimpleTestCase, override_settings
from openpyxl import Workbook
from openpyxl.styles import Font

from statistics.utils.report_pdf_service import (
    MAX_PDF_COLUMNS,
    ReportTooLargeForPdf,
    _sheet_to_blocks,
    build_palette,
    convert_report_content_to_pdf,
    format_cell_value,
    get_pdf_export_options,
    pdf_export,
)


@override_settings(LANGUAGE_CODE="ca")
class FormatCellValueTests(SimpleTestCase):
    def test_number_formats(self):
        self.assertEqual(format_cell_value(1234.5, "#,##0.00"), ("1.234,50", True))
        self.assertEqual(format_cell_value(1234.5, "#,##0.00 €"), ("1.234,50 €", True))
        self.assertEqual(format_cell_value(0.255, "0.0%"), ("25,5 %", True))
        # Decimals opcionals: fora els zeros finals fins al mínim.
        self.assertEqual(format_cell_value(9.939, "#,##0.00########"), ("9,939", True))
        self.assertEqual(format_cell_value(2, "#,##0.00########"), ("2,00", True))

    def test_general_integers_have_no_thousands_separator(self):
        # Poden ser codis o anys.
        self.assertEqual(format_cell_value(2026), ("2026", True))
        self.assertEqual(format_cell_value(12.345), ("12,35", True))

    @override_settings(LANGUAGE_CODE="en")
    def test_english_separators(self):
        self.assertEqual(format_cell_value(1234.5, "#,##0.00"), ("1,234.50", True))

    def test_dates_and_text(self):
        self.assertEqual(format_cell_value(datetime.date(2026, 3, 1)), ("01/03/2026", False))
        self.assertEqual(format_cell_value(None), ("", False))
        self.assertEqual(format_cell_value("Text"), ("Text", False))

    def test_formulas(self):
        self.assertEqual(format_cell_value('=HYPERLINK("http://x","Veure")'), ("Veure", False))
        self.assertEqual(format_cell_value("=SUM(A1:A3)"), ("", False))


@override_settings(LANGUAGE_CODE="ca")
class SheetStructureTests(SimpleTestCase):
    def _sample_sheet(self):
        wb = Workbook()
        ws = wb.active
        ws["A1"] = "Títol de l'informe"
        ws.append([])
        ws.append(["Zona", "Abonats", "Import"])
        ws.append(["Zona A"])
        ws["A4"].font = Font(bold=True)
        ws.append(["Zona A", 10, 100.5])
        ws.append(["Zona A", 5, 50])
        ws.append(["Total", 15, 150.5])
        for cell in ws[7]:
            cell.font = Font(bold=True)
        ws.column_dimensions["D"].hidden = True
        ws["D5"] = "ocult"
        return wb, ws

    def test_titles_header_sections_and_totals(self):
        _, ws = self._sample_sheet()
        sheet = _sheet_to_blocks(ws)

        self.assertEqual(sheet["titles"], ["Títol de l'informe"])
        self.assertEqual(sheet["column_count"], 3)  # la columna oculta no compta
        table = sheet["tables"][0]
        header = table["header"][0]["cells"]
        self.assertEqual([c["text"] for c in header], ["Zona", "Abonats", "Import"])
        self.assertEqual([c["numeric"] for c in header], [False, True, True])
        self.assertEqual([r["css"] for r in table["rows"]], ["section", "", "", "total"])
        self.assertEqual(table["rows"][0]["cells"][0]["colspan"], 3)

    def test_merged_cells(self):
        wb = Workbook()
        ws = wb.active
        ws.append(["Grup", None, "C"])
        ws.merge_cells("A1:B1")
        ws.append(["a", "b", "c"])
        ws.append(["d", "e", "f"])
        sheet = _sheet_to_blocks(ws)
        header = sheet["tables"][0]["header"][0]["cells"]
        self.assertEqual([(c["text"], c["colspan"]) for c in header], [("Grup", 2), ("C", 1)])

    def test_blank_rows_continue_the_table_and_groups_repeat_their_title(self):
        bold = Font(bold=True)
        big_bold = Font(bold=True, size=13)
        wb = Workbook()
        ws = wb.active
        ws.append(["Ús", "Descripció", "Unitats", "Import"])
        for cell in ws[1]:
            cell.font = bold
        for group in ("Producte 1", "Producte 2"):
            ws.append([None, group])
            ws.cell(row=ws.max_row, column=2).font = big_bold
            for subgroup in ("Ús A", "Ús B"):
                ws.append([subgroup, "Nom"])
                for cell in ws[ws.max_row]:
                    cell.font = bold
                ws.append([None, "Concepte", 3, 10.5])
                ws.append([None, "Concepte", 4, 11.5])
                ws.append([None, None, 7, 22])
                for cell in ws[ws.max_row]:
                    cell.font = bold
                ws.append([])
        ws.append(["Resum de l'IVA"])
        ws.append([])
        ws.append([None, "Base", "% IVA", "Total"])
        for cell in ws[ws.max_row]:
            cell.font = bold
        ws.append([None, 44, 10, 48.4])

        tables = _sheet_to_blocks(ws)["tables"]

        # Una taula per producte (amb columnes + producte repetits) i la de l'IVA.
        self.assertEqual(len(tables), 3)
        for table, group in zip(tables[:2], ("Producte 1", "Producte 2")):
            self.assertEqual(table["repeat"], 2)
            self.assertEqual(table["header"][0]["cells"][0]["text"], "Ús")
            self.assertEqual(table["header"][1]["kind"], "section")
            self.assertIn(group, [c["text"] for c in table["header"][1]["cells"]])
            self.assertEqual(
                [r["css"] for r in table["rows"]],
                ["subsection", "", "", "total", "spacer", "subsection", "", "", "total"],
            )
        self.assertEqual(tables[2]["captions"], ["Resum de l'IVA"])
        self.assertEqual([c["text"] for c in tables[2]["header"][0]["cells"] if not c["empty"]], ["Base", "% IVA", "Total"])

    def test_too_many_columns(self):
        wb = Workbook()
        ws = wb.active
        ws.append([f"C{i}" for i in range(MAX_PDF_COLUMNS + 1)])
        with self.assertRaises(ReportTooLargeForPdf):
            _sheet_to_blocks(ws)

    def test_non_excel_content_is_left_untouched(self):
        content, filename = convert_report_content_to_pdf("línia;de;text", "informe.txt", "Informe")
        self.assertEqual((content, filename), ("línia;de;text", "informe.txt"))


class PdfExportContextTests(SimpleTestCase):
    def test_context_sets_and_resets_options(self):
        self.assertIsNone(get_pdf_export_options())
        with pdf_export(title="Informe", filters_display=[{"label": "Període", "value": "x"}]) as options:
            self.assertIs(get_pdf_export_options(), options)
            self.assertEqual(options["title"], "Informe")
        self.assertIsNone(get_pdf_export_options())


class BuildPaletteTests(SimpleTestCase):
    def test_dark_background_with_light_text(self):
        palette = build_palette("#074df0", "#ffffff")
        self.assertEqual(palette["accent"], "#074df0")
        self.assertEqual(palette["on_accent"], "#ffffff")

    def test_order_does_not_matter_the_darker_color_is_the_accent(self):
        palette = build_palette("#eaf0f2", "#395675")
        self.assertEqual(palette["accent"], "#395675")
        self.assertEqual(palette["on_accent"], "#eaf0f2")

    def test_too_light_colors_are_darkened_to_be_readable(self):
        palette = build_palette("#ffff00", "#ffffff")
        self.assertNotEqual(palette["accent"], "#ffff00")
        self.assertEqual(palette["on_accent"], "#ffffff")

    def test_invalid_values_fall_back_to_the_default_color(self):
        palette = build_palette("red; } body { x", None)
        self.assertEqual(palette["accent"], "#074df0")
