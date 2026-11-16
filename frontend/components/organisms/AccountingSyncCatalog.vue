<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { useToast } from 'vue-toastification';
import { exportToXlsx } from '~/utils/xlsx-export';

const props = defineProps({
  exploitationId: {
    type: [Number, String],
    default: null,
  },
});

const { t } = useI18n();
const toast = useToast();
const { $LineItemTypeApiService } = useNuxtApp();

const loading = ref(true);
const columns = ref([]);
const rows = ref([]);
const searchQuery = ref('');
const downloadOpen = ref(false);
const menuRoot = ref(null);
let requestSerial = 0;

const visibleRows = computed(() => {
  const query = searchQuery.value.trim().toLowerCase();
  if (!query) return rows.value;
  return rows.value.filter((row) =>
    columns.value.some((column) => String(row[column] ?? '').toLowerCase().includes(query)),
  );
});

const displayCell = (value) => {
  if (value === null || value === undefined || value === '') return '—';
  return value;
};

const loadCatalog = async () => {
  const serial = ++requestSerial;
  loading.value = true;
  try {
    const response = await $LineItemTypeApiService.getAccountingCatalog(props.exploitationId);
    if (serial !== requestSerial) return;
    columns.value = Array.isArray(response.columns) ? response.columns : [];
    rows.value = response.results;
  } catch (error) {
    if (serial !== requestSerial) return;
    console.error(error);
    columns.value = [];
    rows.value = [];
    toast.error(t('pricing_block.accounting_sync_load_error'));
  } finally {
    if (serial === requestSerial) loading.value = false;
  }
};

const xlsxColumns = () =>
  columns.value.map((column) => ({
    header: column,
    value: (row) => row[column] ?? '',
  }));

const downloadXlsx = () => {
  exportToXlsx(rows.value, xlsxColumns(), 'line-item-types', 'LineItemType');
  downloadOpen.value = false;
};

const downloadJson = () => {
  const blob = new Blob([JSON.stringify(rows.value, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = 'line-item-types.json';
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
  downloadOpen.value = false;
};

const toggleDownload = (event) => {
  event.stopPropagation();
  downloadOpen.value = !downloadOpen.value;
};

const closeDownload = () => {
  downloadOpen.value = false;
};

onMounted(() => {
  document.addEventListener('click', closeDownload);
  loadCatalog();
});

onBeforeUnmount(() => {
  document.removeEventListener('click', closeDownload);
});

watch(() => props.exploitationId, () => {
  searchQuery.value = '';
  loadCatalog();
});
</script>

<template>
  <section class="mt-8 overflow-hidden rounded-md border bg-white" style="--accent: #0f766e; --accent-soft: #99f6e4; border-color: var(--accent-soft)">
    <header class="flex flex-wrap items-center justify-between gap-3 border-b px-4 py-3" style="border-color: var(--accent-soft)">
      <div class="flex min-w-0 items-center gap-2.5">
        <span class="shrink-0 font-mono text-[11px] font-bold tracking-[0.14em]" style="color: var(--accent)">04</span>
        <div class="relative flex size-9 shrink-0 items-center justify-center">
          <span class="absolute left-0 top-0 h-2 w-2 border-l border-t border-teal-200" />
          <span class="absolute right-0 top-0 h-2 w-2 border-r border-t border-teal-200" />
          <span class="absolute bottom-0 left-0 h-2 w-2 border-b border-l border-teal-200" />
          <span class="absolute bottom-0 right-0 h-2 w-2 border-b border-r border-teal-200" />
          <Icon name="fa6-solid:boxes-stacked" class="size-3.5" style="color: var(--accent)" />
        </div>
        <div class="min-w-0">
          <p class="truncate text-sm font-bold text-sky-950">
            {{ t('pricing_block.accounting_sync_catalog') }}
          </p>
          <p class="max-w-3xl text-[11px] leading-snug text-slate-500">
            {{ t('pricing_block.accounting_sync_catalog_description') }}
          </p>
        </div>
      </div>

      <div class="flex shrink-0 items-center gap-2">
        <form role="search" class="flex min-w-0 items-center gap-1.5 rounded-md border bg-white px-2.5 py-1.5" style="border-color: var(--accent-soft)" @submit.prevent>
          <Icon name="fa6-solid:magnifying-glass" class="size-3 shrink-0" style="color: var(--accent)" />
          <input v-model="searchQuery" type="text" :placeholder="t('dashboard.search')"
            class="w-32 bg-transparent text-[11px] text-sky-950 placeholder:text-slate-400 focus:outline-none sm:w-48"
            autocomplete="off" />
        </form>

        <div ref="menuRoot" class="relative">
          <button type="button"
            class="inline-flex items-center gap-1.5 rounded-md bg-[var(--accent-soft)] px-3 py-1.5 text-[11px] font-semibold text-[var(--accent)] transition-colors hover:bg-[var(--accent)] hover:text-white disabled:opacity-60"
            :disabled="loading || !rows.length" @click="toggleDownload">
            <Icon name="fa6-solid:download" class="size-3" />
            {{ t('pricing_block.accounting_sync_download') }}
            <Icon name="fa6-solid:chevron-down" class="size-2.5" />
          </button>
          <div v-if="downloadOpen"
            class="absolute right-0 z-20 mt-1 w-44 overflow-hidden rounded-md border bg-white shadow-md"
            style="border-color: var(--accent-soft)" @click.stop>
            <button type="button"
              class="flex w-full items-center gap-2 px-3 py-2 text-left text-[11px] font-semibold text-sky-950 hover:bg-teal-50"
              @click="downloadXlsx">
              <Icon name="fa6-solid:file-excel" class="size-3 text-emerald-700" />
              {{ t('pricing_block.accounting_sync_download_xlsx') }}
            </button>
            <button type="button"
              class="flex w-full items-center gap-2 border-t px-3 py-2 text-left text-[11px] font-semibold text-sky-950 hover:bg-teal-50"
              style="border-color: var(--accent-soft)" @click="downloadJson">
              <Icon name="fa6-solid:file-code" class="size-3" style="color: var(--accent)" />
              {{ t('pricing_block.accounting_sync_download_json') }}
            </button>
          </div>
        </div>
      </div>
    </header>

    <p class="px-4 py-2 font-mono text-[10px] tracking-widest text-slate-500">
      {{ loading ? '—' : t('pricing_block.accounting_sync_count', { count: String(visibleRows.length).padStart(2, '0') }) }}
      <span v-if="!loading && searchQuery.trim() && visibleRows.length !== rows.length">
        / {{ String(rows.length).padStart(2, '0') }}
      </span>
    </p>

    <div v-if="loading" class="space-y-2 px-4 pb-4">
      <div v-for="n in 4" :key="n" class="h-6 animate-pulse rounded-sm bg-teal-50" />
    </div>

    <p v-else-if="!visibleRows.length" class="px-4 pb-4 text-sm text-slate-500">
      {{ t('common.no_records') }}
    </p>

    <div v-else class="max-h-[28rem] overflow-auto border-t" style="border-color: var(--accent-soft)">
      <table class="min-w-full border-separate border-spacing-0 text-left text-[11px]">
        <thead>
          <tr>
            <th v-for="column in columns" :key="column"
              class="sticky top-0 whitespace-nowrap border-b bg-teal-50 px-3 py-2 font-mono text-[10px] font-semibold text-teal-900"
              style="border-color: var(--accent-soft)">
              {{ column }}
            </th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(row, index) in visibleRows" :key="`${row['LineItemType.token']}-${index}`" class="hover:bg-teal-50/40">
            <td v-for="column in columns" :key="column"
              class="whitespace-nowrap border-b px-3 py-1.5 text-slate-700"
              style="border-color: #ccfbf1">
              {{ displayCell(row[column]) }}
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>
</template>
