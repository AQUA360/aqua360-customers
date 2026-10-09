<script setup>
import { ref, computed, onBeforeUnmount } from 'vue';
import { useI18n } from 'vue-i18n';
import { useToast } from 'vue-toastification';

const { t } = useI18n();
const toast = useToast();
const config = useRuntimeConfig();
const { $ReadingBatchApiService, $apiManager, $DocumentManagerApiService } = useNuxtApp();

const props = defineProps({
  batch_id: {
    type: Number,
    required: true,
  },
});

const routeDownloadFormat = ref('xlsx');

const routeFormatOptions = [
  { value: 'csv', icon: 'fa6-solid:file-csv', label: 'CSV' },
  { value: 'xls', icon: 'fa6-solid:file-excel', label: 'XLS' },
  { value: 'xlsx', icon: 'fa6-solid:file-excel', label: 'XLSX' },
];

const selectedRouteFormatOption = computed(
  () => routeFormatOptions.find((o) => o.value === routeDownloadFormat.value) ?? routeFormatOptions[2],
);

const routeDownloadBusy = ref(false);
/** 'starting' = request queued; 'generating' = waiting on background task / file */
const routeDownloadPhase = ref('idle');

const routeDownloadStatusText = computed(() => {
  if (!routeDownloadBusy.value) return '';
  return routeDownloadPhase.value === 'starting' ? t('common.loading') : t('common.generating');
});

/** Aborts in-flight route download polling when the component unmounts or a new download starts. */
const routeDownloadPollAbort = ref(null);

onBeforeUnmount(() => {
  routeDownloadPollAbort.value?.abort();
  routeDownloadPollAbort.value = null;
});

const sleep = (ms, signal) =>
  new Promise((resolve, reject) => {
    if (signal?.aborted) {
      reject(new DOMException('Aborted', 'AbortError'));
      return;
    }
    const t = setTimeout(() => {
      signal?.removeEventListener('abort', onAbort);
      resolve();
    }, ms);
    const onAbort = () => {
      clearTimeout(t);
      signal?.removeEventListener('abort', onAbort);
      reject(new DOMException('Aborted', 'AbortError'));
    };
    signal?.addEventListener('abort', onAbort, { once: true });
  });

/** Task `file_url` is often relative to the API host origin (e.g. `/media/...`). */
const resolveTaskFileMediaUrl = (path) => {
  if (!path) return '';
  if (/^https?:\/\//i.test(path)) return path;
  const apiHost = config.public.apiHost || '';
  try {
    return new URL(path, new URL(apiHost).origin).href;
  } catch {
    return path;
  }
};

const downloadBlobFile = (fileBlob, filename) => {
  const url = window.URL.createObjectURL(fileBlob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  window.URL.revokeObjectURL(url);
};

const downloadRoute = async () => {
  if (!props.batch_id) return;
  if (routeDownloadBusy.value) return;

  routeDownloadPollAbort.value?.abort();
  const abortController = new AbortController();
  routeDownloadPollAbort.value = abortController;
  const signal = abortController.signal;

  routeDownloadBusy.value = true;
  routeDownloadPhase.value = 'starting';

  try {
    const batchResponse = await $ReadingBatchApiService.downloadBatch(props.batch_id, routeDownloadFormat.value);
    if (signal.aborted) return;
    if (!batchResponse?.task_id) {
      toast.error(t('common.error'));
      return;
    }

    routeDownloadPhase.value = 'generating';
    const loadingTaskId = batchResponse.task_id;
    const pollingIntervalMs = 1000;

    while (!signal.aborted) {
      const taskResponse = await $apiManager.checkTask(loadingTaskId);
      if (signal.aborted) return;

      if (taskResponse?.state === 'FAILURE') {
        const backendMsg =
          taskResponse?.error ||
          taskResponse?.message ||
          taskResponse?.result?.error ||
          taskResponse?.result?.message;
        throw new Error(backendMsg || t('common.error'));
      }

      const result = taskResponse?.result;

      const taskState = taskResponse?.state != null ? String(taskResponse.state).toUpperCase() : '';
      if (taskState === 'SUCCESS') {
        const resultStatusOk =
          result?.status == null || String(result.status).toLowerCase() === 'ok';
        if (!resultStatusOk) {
          throw new Error(
            result.error || result.message || result.detail || t('common.error'),
          );
        }
        const ext = result.format || routeDownloadFormat.value;
        const filename = result.filename || `route_batch_${props.batch_id}.${ext}`;

        if (result?.document_id) {
          if (signal.aborted) return;
          const fileBlob = await $DocumentManagerApiService.viewDocument(result.document_id);
          if (signal.aborted) return;
          downloadBlobFile(fileBlob, filename);
          toast.success(t('common.correct_download'));
          return;
        }

        if (result?.file_url) {
          const absoluteUrl = resolveTaskFileMediaUrl(result.file_url);
          const authToken = localStorage.getItem('auth_token') || '';
          const res = await fetch(absoluteUrl, {
            method: 'GET',
            headers: { Authorization: `Token ${authToken}` },
            signal,
          });
          if (signal.aborted) return;
          if (!res.ok) {
            const errText = await res.text().catch(() => '');
            throw new Error(errText || t('common.error'));
          }
          const blob = await res.blob();
          if (signal.aborted) return;
          downloadBlobFile(blob, filename);
          toast.success(t('common.correct_download'));
          return;
        }

        throw new Error(t('common.error'));
      }

      await sleep(pollingIntervalMs, signal);
    }
  } catch (error) {
    if (error?.name === 'AbortError') return;
    console.error(error);
    toast.error(error?.message || t('common.error'));
  } finally {
    routeDownloadBusy.value = false;
    routeDownloadPhase.value = 'idle';
  }
};
</script>

<template>
  <div class="flex flex-col items-end gap-2 shrink-0">
    <div class="flex items-stretch gap-2 shrink-0">
      <div
        class="inline-flex items-stretch rounded-md overflow-hidden shadow-md focus-within:ring-2 focus-within:ring-sky-400 focus-within:ring-offset-1 transition-opacity duration-200"
        :class="{ 'opacity-80': routeDownloadBusy }"
        role="group"
        :aria-busy="routeDownloadBusy"
        :aria-label="`${t('common.download')} ${t('route')}`"
      >
        <button
          type="button"
          class="inline-flex items-center px-4 py-2 text-sm font-semibold text-white bg-sky-600 hover:bg-sky-700 border-0 rounded-none focus:outline-none focus:z-10 focus:ring-2 focus:ring-inset focus:ring-sky-300 transition-colors duration-200 disabled:opacity-70 disabled:cursor-not-allowed disabled:hover:bg-sky-600"
          :disabled="routeDownloadBusy"
          @click="downloadRoute"
        >
          <Icon
            :name="routeDownloadBusy ? 'fa6-solid:spinner' : 'fa6-solid:download'"
            class="mr-2 shrink-0"
            :class="{ 'animate-spin': routeDownloadBusy }"
          />
          {{ $t('common.download') }} {{ $t('route') }}
        </button>
        <div
          id="route-download-format"
          class="flex items-stretch border-l border-sky-500 bg-sky-700 shrink-0"
        >
          <span
            class="flex items-center pl-2 pr-0.5 shrink-0 text-sky-100"
            aria-hidden="true"
          >
            <Icon :name="selectedRouteFormatOption.icon" class="text-base" />
          </span>
          <div class="relative flex items-center min-w-0">
            <select
              id="route-download-format-select"
              v-model="routeDownloadFormat"
              :disabled="routeDownloadBusy"
              :aria-label="`${t('common.download')} ${t('route')} (${selectedRouteFormatOption.label})`"
              class="h-full min-w-[4.25rem] max-w-[5.5rem] cursor-pointer appearance-none bg-transparent py-2 pl-1 pr-7 text-sm font-semibold text-white border-0 focus:outline-none focus:ring-0 disabled:opacity-70 disabled:cursor-not-allowed"
            >
              <option v-for="opt in routeFormatOptions" :key="opt.value" :value="opt.value" class="text-slate-800">
                {{ opt.label }}
              </option>
            </select>
            <Icon
              name="fa6-solid:chevron-down"
              class="pointer-events-none absolute right-1.5 top-1/2 -translate-y-1/2 text-xs text-sky-200"
            />
          </div>
        </div>
      </div>
      <NuxtLink
        to="/statistics/reading-batch-export-config"
        class="inline-flex items-center justify-center self-stretch rounded-md border border-sky-300 bg-sky-50 px-2.5 text-sky-700 shadow-sm transition-colors hover:bg-sky-100 hover:text-sky-900 hover:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-500 focus:ring-offset-0"
        :aria-label="t('settings_block.reading_batch_export_file')"
        :title="t('settings_block.reading_batch_export_file')"
      >
        <Icon name="fa6-solid:gear" class="text-base shrink-0" />
      </NuxtLink>
    </div>
    <p
      v-if="routeDownloadBusy && routeDownloadStatusText"
      class="text-xs text-sky-700 font-medium max-w-[14rem] text-right leading-snug"
      role="status"
      aria-live="polite"
    >
      {{ routeDownloadStatusText }}
    </p>
  </div>
</template>
