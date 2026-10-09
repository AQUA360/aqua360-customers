<script setup>
import { computed, ref } from 'vue';
import { useExportJobsStore } from '~/stores/useExportJobs';

// Top-bar entry to the user's downloads queue (server-side exports). Files are
// listed here until dismissed, wherever the export was launched from.
const store = useExportJobsStore();
const { t } = useI18n();

const open = ref(false);
const busyId = ref(null);

const hasFinished = computed(() => store.jobs.some(job => !['pending', 'running'].includes(job.status)));

const statusClass = {
    pending: 'bg-slate-100 text-slate-600',
    running: 'bg-sky-100 text-sky-700',
    completed: 'bg-green-100 text-green-700',
    failed: 'bg-red-100 text-red-700',
    cancelled: 'bg-slate-100 text-slate-500',
};

const toggle = async () => {
    open.value = !open.value;
    if (open.value) {
        store.markSeen();
        await store.refresh();
    }
};

const run = async (job, fn) => {
    busyId.value = job.id;
    try {
        await fn(job);
    } catch (err) {
        console.error('Export job action error:', err);
    } finally {
        busyId.value = null;
    }
};
</script>

<template>
    <div class="relative" v-click-outside="() => (open = false)">
        <abbr :title="t('export_jobs.title')">
            <button @click="toggle" class="group relative flex items-center justify-center rounded w-6 h-6 border"
                :class="store.activeJobs.length > 0 || store.unseenCount > 0
                    ? 'border-sky-200 hover:bg-sky-100'
                    : 'border-slate-200 hover:bg-slate-100'">
                <Icon :name="store.activeJobs.length > 0 ? 'fa6-solid:spinner' : 'fa6-solid:download'"
                    class="w-3.5 h-3.5 group-hover:text-slate-500"
                    :class="store.activeJobs.length > 0 ? 'text-sky-500 animate-spin' : (store.unseenCount > 0 ? 'text-sky-400' : 'text-slate-400')" />
                <span v-if="store.unseenCount > 0 && store.activeJobs.length === 0"
                    class="absolute -top-1.5 -right-1.5 min-w-[1rem] h-4 px-1 rounded-full bg-sky-500 text-white text-[10px] leading-4 text-center">
                    {{ store.unseenCount }}
                </span>
            </button>
        </abbr>

        <div v-if="open"
            class="absolute right-0 mt-2 w-[26rem] max-h-[70vh] overflow-y-auto bg-white border border-slate-200 rounded-lg shadow-lg z-30 text-sm">
            <div class="flex items-center justify-between px-4 py-2 border-b border-slate-100">
                <span class="font-semibold text-slate-700">
                    {{ t('export_jobs.title') }}
                    <span v-if="store.activeJobs.length" class="ml-1 font-normal text-sky-600">
                        · {{ t('export_jobs.active', { count: store.activeJobs.length }) }}
                    </span>
                </span>
                <button v-if="hasFinished" class="text-xs text-slate-500 hover:text-slate-800 hover:underline"
                    @click="store.clearFinished()">
                    {{ t('export_jobs.clear_finished') }}
                </button>
            </div>

            <p v-if="store.jobs.length === 0" class="px-4 py-6 text-center text-slate-400">
                {{ t('export_jobs.empty') }}
            </p>

            <ul v-else class="divide-y divide-slate-100">
                <li v-for="job in store.jobs" :key="job.id" class="px-4 py-2 flex items-start gap-3">
                    <div class="min-w-0 flex-1">
                        <div class="flex items-center gap-2">
                            <span class="truncate font-medium text-slate-800" :title="job.name">{{ job.name }}</span>
                            <span class="shrink-0 rounded px-1.5 py-0.5 text-[11px]" :class="statusClass[job.status]">
                                {{ t(`export_jobs.status_${job.status}`) }}
                            </span>
                        </div>
                        <div class="text-xs text-slate-400 flex gap-2">
                            <AtomsTimeRelative :datetime="job.created_at" />
                            <span v-if="job.status === 'completed' && job.duration_seconds != null">
                                · {{ t('export_jobs.duration', { seconds: job.duration_seconds }) }}
                            </span>
                        </div>
                        <div v-if="job.status === 'failed' && job.error_message" class="text-xs text-red-600 break-words">
                            {{ job.error_message }}
                        </div>
                    </div>
                    <div class="shrink-0 flex items-center gap-1">
                        <button v-if="job.status === 'completed'" class="button-secondary !py-1 !px-2"
                            :disabled="busyId === job.id" :title="t('common.download')"
                            @click="run(job, store.download)">
                            <Icon name="fa6-solid:download" />
                        </button>
                        <button v-if="['pending', 'running'].includes(job.status)"
                            class="px-2 py-1 text-xs text-slate-500 hover:text-red-600"
                            :disabled="busyId === job.id" @click="run(job, store.cancel)">
                            {{ t('export_jobs.cancel') }}
                        </button>
                        <button v-else class="px-1.5 py-1 text-slate-400 hover:text-slate-700"
                            :disabled="busyId === job.id" :title="t('export_jobs.dismiss')"
                            @click="run(job, store.dismiss)">
                            <Icon name="fa6-solid:xmark" />
                        </button>
                    </div>
                </li>
            </ul>
        </div>
    </div>
</template>
