import * as XLSX from 'xlsx';

/**
 * Column definition for an XLSX export.
 * - `header`: the text shown in the sheet header row (already translated).
 * - `value`: accessor returning the cell value for a given row. Return a
 *   primitive (string / number / Date / boolean) — objects are stringified.
 * - `key`: backend field name for this column, used for the server-side
 *   export's `columns` query param (see useServerExport). Omit for columns
 *   that only make sense client-side (no backend equivalent).
 */
export interface XlsxColumn<T = any> {
    header: string;
    value: (row: T) => unknown;
    key?: string;
}

/**
 * Label/value pair shown above the table as a summary block (e.g. totals or
 * general info of the exported entity). The label must already be translated.
 */
export type XlsxSummaryRow = [label: string, value: unknown];

const toCell = (raw: unknown): unknown => {
    if (raw === null || raw === undefined) return '';
    if (raw instanceof Date) return raw;
    if (typeof raw === 'object') return JSON.stringify(raw);
    return raw;
};

const sanitizeFileName = (name: string): string =>
    (name || 'export')
        .toString()
        .trim()
        .replace(/[^a-z0-9_\-]+/gi, '_')
        .replace(/_+/g, '_')
        .replace(/^_|_$/g, '') || 'export';

/**
 * Generates and triggers the download of an .xlsx file from already-loaded
 * table data. It exports exactly the `rows` and `columns` it receives, so the
 * caller decides which rows (respecting active filters) and which columns
 * (matching what's rendered) to include.
 *
 * @param rows     The data rows to export (already filtered/sorted as shown).
 * @param columns  The visible columns, in display order.
 * @param fileName File name without extension (`.xlsx` is appended).
 * @param sheetName Optional worksheet name (max 31 chars, Excel limit).
 * @param summary  Optional label/value rows written above the table, followed
 *                 by an empty row.
 */
export const exportToXlsx = <T = any>(
    rows: T[],
    columns: XlsxColumn<T>[],
    fileName = 'export',
    sheetName = 'Sheet1',
    summary: XlsxSummaryRow[] = [],
): void => {
    const safeRows = Array.isArray(rows) ? rows : [];

    const summaryAoa: unknown[][] = summary.length
        ? [...summary.map(([label, value]) => [label, toCell(value)]), []]
        : [];

    const tableAoa: unknown[][] = [
        columns.map((c) => c.header),
        ...safeRows.map((row) => columns.map((col) => toCell(col.value(row)))),
    ];

    const aoa: unknown[][] = [...summaryAoa, ...tableAoa];

    const worksheet = XLSX.utils.aoa_to_sheet(aoa);

    // Basic auto width based on content length.
    worksheet['!cols'] = columns.map((col, i) => {
        const maxLen = aoa.reduce((max, r) => {
            const cell = r[i];
            const len = cell == null ? 0 : String(cell).length;
            return Math.max(max, len);
        }, 0);
        return { wch: Math.min(Math.max(maxLen + 2, 10), 60) };
    });

    const workbook = XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(workbook, worksheet, (sheetName || 'Sheet1').slice(0, 31));

    XLSX.writeFile(workbook, `${sanitizeFileName(fileName)}.xlsx`);
};
