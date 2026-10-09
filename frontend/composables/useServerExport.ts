import { ref } from 'vue';
import { useI18n } from 'vue-i18n';
import { exportToXlsx, type XlsxColumn } from '~/utils/xlsx-export';
import { useExportJobsStore } from '~/stores/useExportJobs';

export interface ServerExportOptions<T = any> {
    // Rows currently loaded (used for the client-side path).
    rows: T[];
    // Visible columns, in display order (used for the client-side path).
    columns: XlsxColumn<T>[];
    // File name without extension.
    fileName?: string;
    // Optional worksheet name.
    sheetName?: string;
    // Number of pages in the current (filtered) result set.
    totalPages?: number;
    // Triggers the server-side export. Must return the API response, which is
    // expected to contain a `task_id` (async background job). Receives the
    // ordered list of backend column keys (derived from `columns[].key`); the
    // caller closes over the active filters/search/sort.
    serverExportFn?: (columnKeys: string[]) => Promise<any>;
    // Fallback file name (without extension) for the server-generated document.
    serverFileName?: string;
    // Name shown in the downloads queue. Defaults to the sheet name, then to the
    // current page title (last breadcrumb), then to the file name.
    exportName?: string;
}

// Last breadcrumb item: the translated title of the page the export comes from.
const currentPageTitle = (): string | null => {
    const crumb = document.querySelector('nav[aria-label="Breadcrumb"] li:last-child');
    const text = crumb?.textContent?.trim();
    return text || null;
};

/**
 * Table export.
 *
 * - If `serverExportFn` is provided, the export always goes to the backend so
 *   the file contains the full filtered dataset, not the page loaded in the table.
 *   When the backend answers with `export_job_id` the job goes to the user's
 *   downloads queue (stores/useExportJobs): this returns right away, and the file
 *   is downloaded when ready even if the user has left the page, and stays
 *   reachable from the downloads menu. Older endpoints that only return
 *   `task_id` are still polled here.
 * - If no `serverExportFn` is provided, it exports the already-loaded `rows`
 *   client-side to .xlsx.
 */
export function useServerExport() {
    const { t } = useI18n();
    const { $apiManager, $DocumentManagerApiService } = useNuxtApp();

    const exporting = ref(false);
    let pollingInterval: ReturnType<typeof setInterval> | null = null;

    const stopPolling = () => {
        if (pollingInterval) {
            clearInterval(pollingInterval);
            pollingInterval = null;
        }
    };

    const downloadDocument = async (documentId: string | number, documentName?: string) => {
        const file = await $DocumentManagerApiService.viewDocument(documentId);
        const link = document.createElement('a');
        const fileUrl = URL.createObjectURL(file);
        link.href = fileUrl;
        link.download = documentName || 'export.xlsx';
        link.click();
        setTimeout(() => URL.revokeObjectURL(fileUrl), 250);
    };

    const MAX_POLL_ATTEMPTS = 150; // 2s interval → 5 minutes

    const pollTask = (taskId: string) =>
        new Promise<void>((resolve, reject) => {
            let attempts = 0;
            pollingInterval = setInterval(async () => {
                attempts++;
                try {
                    const response = await $apiManager.checkTask(taskId);
                    const status = response?.state || response?.status;
                    if (status === 'SUCCESS' || status === 'completed') {
                        stopPolling();
                        const result = response?.result || response;
                        if (result?.document_id) {
                            await downloadDocument(result.document_id, result.document_name || result.filename);
                            resolve();
                        } else {
                            reject(new Error('missing document_id'));
                        }
                    } else if (status === 'FAILURE' || status === 'failed') {
                        stopPolling();
                        reject(new Error(response?.error || 'export failed'));
                    } else if (attempts >= MAX_POLL_ATTEMPTS) {
                        stopPolling();
                        reject(new Error('export timed out'));
                    }
                } catch (err) {
                    stopPolling();
                    reject(err);
                }
            }, 2000);
        });

    const runExport = async (opts: ServerExportOptions) => {
        const {
            rows,
            columns,
            fileName = 'export',
            sheetName = 'Sheet1',
            serverExportFn,
            exportName,
        } = opts;

        // No server export → fall back to the rows already loaded in the table.
        if (!serverExportFn) {
            exportToXlsx(rows, columns, fileName, sheetName);
            return;
        }

        // Always let the server build the full, filter-aware export.
        exporting.value = true;
        const name = exportName || (sheetName !== 'Sheet1' ? sheetName : null) || currentPageTitle() || fileName;
        try {
            const columnKeys = columns.map(c => c.key).filter(Boolean);
            $apiManager.pendingExportName = name;
            let response;
            try {
                response = await serverExportFn(columnKeys);
            } finally {
                $apiManager.pendingExportName = null;
            }
            if (response?.export_job_id) {
                useExportJobsStore().track(response.export_job_id, name);
            } else if (response?.task_id) {
                await pollTask(response.task_id);
            } else if (response?.document_id) {
                // Server answered synchronously with a ready document.
                await downloadDocument(response.document_id, response.document_name);
            } else {
                throw new Error('missing task_id');
            }
        } finally {
            exporting.value = false;
        }
    };

    return { exporting, runExport, stopPolling };
}
