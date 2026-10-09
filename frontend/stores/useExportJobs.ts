import { defineStore } from 'pinia';
import { computed, ref } from 'vue';
import { useToast } from 'vue-toastification';
import { openAuthenticatedFileUrl } from '~/utils/open-authenticated-file';

export interface ExportJob {
    id: number;
    kind: string;
    name: string;
    status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';
    error_message: string | null;
    document_id: number | null;
    file_url: string | null;
    file_name: string | null;
    created_at: string;
    started_at: string | null;
    completed_at: string | null;
    duration_seconds: number | null;
}

const ACTIVE = ['pending', 'running'];
const POLL_INTERVAL = 3000;
// Jobs launched from this tab: downloaded automatically when they finish, even
// after a refresh (sessionStorage survives reloads of the same tab).
const AUTO_DOWNLOAD_KEY = 'export_jobs_auto_download';
// Last time the user opened the downloads menu, to badge the files finished since then.
const LAST_SEEN_KEY = 'export_jobs_last_seen';

const readIds = (): number[] => {
    try {
        return JSON.parse(sessionStorage.getItem(AUTO_DOWNLOAD_KEY) || '[]');
    } catch {
        return [];
    }
};

const writeIds = (ids: number[]) => {
    try {
        sessionStorage.setItem(AUTO_DOWNLOAD_KEY, JSON.stringify(ids));
    } catch {
        /* storage unavailable: auto-download only lasts for this page load */
    }
};

/**
 * General downloads queue (backend `ExportJob`, `/documentmanager/export-job/`).
 *
 * Server-side exports no longer depend on the page that launched them: the job
 * is tracked here, polled while active, downloaded automatically when it was
 * launched from this tab, and always reachable from the downloads menu.
 */
export const useExportJobsStore = defineStore('exportJobs', () => {
    const jobs = ref<ExportJob[]>([]);
    const loaded = ref(false);
    const autoDownloadIds = ref<number[]>([]);
    const lastSeenAt = ref<string | null>(null);
    let pollTimer: ReturnType<typeof setTimeout> | null = null;

    const activeJobs = computed(() => jobs.value.filter(job => ACTIVE.includes(job.status)));
    const unseenCount = computed(() => jobs.value.filter(job =>
        job.status === 'completed' && job.completed_at && (!lastSeenAt.value || job.completed_at > lastSeenAt.value),
    ).length);

    const t = (key: string, params?: Record<string, unknown>) => useNuxtApp().$i18n.t(key, params || {});

    const download = async (job: ExportJob) => {
        if (job.document_id) {
            const { $DocumentManagerApiService } = useNuxtApp();
            const file = await $DocumentManagerApiService.viewDocument(job.document_id);
            const link = document.createElement('a');
            const fileUrl = URL.createObjectURL(file);
            link.href = fileUrl;
            link.download = job.file_name || 'export.xlsx';
            link.click();
            setTimeout(() => URL.revokeObjectURL(fileUrl), 250);
        } else if (job.file_url) {
            await openAuthenticatedFileUrl(job.file_url, false);
        }
    };

    const forgetAutoDownload = (id: number) => {
        autoDownloadIds.value = autoDownloadIds.value.filter(other => other !== id);
        writeIds(autoDownloadIds.value);
    };

    // Reacts to jobs that have just finished: downloads the ones launched from
    // this tab and notifies about the rest.
    const handleFinished = async (previous: Map<number, string>) => {
        const toast = useToast();
        for (const job of jobs.value) {
            if (ACTIVE.includes(job.status)) continue;
            const wasActive = ACTIVE.includes(previous.get(job.id) || '');
            const isMine = autoDownloadIds.value.includes(job.id);
            if (!isMine && !wasActive) continue;

            if (isMine) forgetAutoDownload(job.id);
            if (job.status === 'completed') {
                if (isMine) {
                    try {
                        await download(job);
                    } catch (err) {
                        console.error('Export download error:', err);
                    }
                } else {
                    toast.success(t('export_jobs.ready', { name: job.name }));
                }
            } else if (job.status === 'failed') {
                toast.error(t('export_jobs.failed', { name: job.name }));
            }
        }
    };

    const refresh = async () => {
        const { $ExportJobApiService } = useNuxtApp();
        const previous = new Map(jobs.value.map(job => [job.id, job.status]));
        try {
            const response = await $ExportJobApiService.getAll();
            jobs.value = response?.results || [];
            loaded.value = true;
        } catch (err) {
            console.error('Error loading export jobs:', err);
            return;
        }
        await handleFinished(previous);
        // A job launched from this tab that no longer appears in the list (dismissed elsewhere) is dropped.
        const listed = new Set(jobs.value.map(job => job.id));
        autoDownloadIds.value.filter(id => !listed.has(id)).forEach(forgetAutoDownload);
    };

    const schedulePoll = () => {
        if (pollTimer) return;
        pollTimer = setTimeout(async () => {
            pollTimer = null;
            await refresh();
            if (activeJobs.value.length > 0) schedulePoll();
        }, POLL_INTERVAL);
    };

    const init = async () => {
        autoDownloadIds.value = readIds();
        try {
            lastSeenAt.value = localStorage.getItem(LAST_SEEN_KEY);
        } catch {
            lastSeenAt.value = null;
        }
        await refresh();
        if (activeJobs.value.length > 0) schedulePoll();
    };

    /**
     * Registers a job just created by an export endpoint (`{ export_job_id }`).
     * The file is downloaded automatically when it is ready, wherever the user is.
     */
    const track = (exportJobId: number, name: string) => {
        if (!jobs.value.some(job => job.id === exportJobId)) {
            jobs.value.unshift({
                id: exportJobId, kind: '', name, status: 'pending', error_message: null,
                document_id: null, file_url: null, file_name: null,
                created_at: new Date().toISOString(), started_at: null, completed_at: null, duration_seconds: null,
            });
        }
        autoDownloadIds.value = [...autoDownloadIds.value, exportJobId];
        writeIds(autoDownloadIds.value);
        useToast().info(t('export_jobs.queued', { name }));
        schedulePoll();
    };

    const markSeen = () => {
        lastSeenAt.value = new Date().toISOString();
        try {
            localStorage.setItem(LAST_SEEN_KEY, lastSeenAt.value);
        } catch {
            /* ignore */
        }
    };

    const cancel = async (job: ExportJob) => {
        const { $ExportJobApiService } = useNuxtApp();
        await $ExportJobApiService.cancel(job.id);
        forgetAutoDownload(job.id);
        await refresh();
    };

    const dismiss = async (job: ExportJob) => {
        const { $ExportJobApiService } = useNuxtApp();
        await $ExportJobApiService.dismiss(job.id);
        forgetAutoDownload(job.id);
        jobs.value = jobs.value.filter(other => other.id !== job.id);
    };

    const clearFinished = async () => {
        const { $ExportJobApiService } = useNuxtApp();
        await $ExportJobApiService.clearFinished();
        jobs.value = jobs.value.filter(job => ACTIVE.includes(job.status));
    };

    return {
        jobs, loaded, activeJobs, unseenCount,
        init, refresh, track, download, markSeen, cancel, dismiss, clearFinished,
    };
});
