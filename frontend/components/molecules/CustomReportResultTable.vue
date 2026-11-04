<script setup>
// Taula de resultats d'un informe personalitzat: filtre, ordenació i paginació al client.
import { ref, computed, watch } from 'vue';

const props = defineProps({
  columns: { type: Array, default: () => [] },
  rows: { type: Array, default: () => [] },
});
const { t, locale } = useI18n();

const PAGE_SIZE = 100;
const filter = ref('');
const sortIndex = ref(null);
const sortDesc = ref(false);
const page = ref(1);

watch(() => [props.rows, filter.value], () => { page.value = 1; });
watch(() => props.columns, () => { sortIndex.value = null; sortDesc.value = false; });

const collator = computed(() => new Intl.Collator(locale.value, { numeric: true, sensitivity: 'base' }));
const numberFormat = computed(() => new Intl.NumberFormat(locale.value, { maximumFractionDigits: 6 }));

const filteredRows = computed(() => {
  const q = filter.value.trim().toLowerCase();
  if (!q) return props.rows;
  return props.rows.filter((row) => row.some((v) => v !== null && String(v).toLowerCase().includes(q)));
});

const compare = (a, b) => {
  if (a === b) return 0;
  if (a === null || a === undefined) return 1;
  if (b === null || b === undefined) return -1;
  if (typeof a === 'number' && typeof b === 'number') return a - b;
  return collator.value.compare(String(a), String(b));
};

const sortedRows = computed(() => {
  if (sortIndex.value === null) return filteredRows.value;
  const i = sortIndex.value;
  const dir = sortDesc.value ? -1 : 1;
  return [...filteredRows.value].sort((a, b) => dir * compare(a[i], b[i]));
});

const pages = computed(() => Math.max(1, Math.ceil(sortedRows.value.length / PAGE_SIZE)));
const pageRows = computed(() => sortedRows.value.slice((page.value - 1) * PAGE_SIZE, page.value * PAGE_SIZE));

const numericColumns = computed(() =>
  props.columns.map((_, i) => props.rows.some((r) => typeof r[i] === 'number') && props.rows.every((r) => r[i] === null || typeof r[i] === 'number'))
);

const sortBy = (i) => {
  if (sortIndex.value === i) {
    if (sortDesc.value) { sortIndex.value = null; sortDesc.value = false; } else { sortDesc.value = true; }
  } else {
    sortIndex.value = i;
    sortDesc.value = false;
  }
};

const display = (value) => {
  if (value === null || value === undefined) return '';
  if (typeof value === 'number') return numberFormat.value.format(value);
  if (typeof value === 'boolean') return value ? '✓' : '✗';
  if (typeof value === 'object') return JSON.stringify(value);
  return String(value);
};
</script>

<template>
  <div>
    <div class="mb-2 flex flex-wrap items-center justify-between gap-2">
      <input
        v-model="filter"
        type="search"
        class="w-64 max-w-full rounded border border-slate-300 px-2 py-1.5 text-sm focus:border-sky-500 focus:outline-none focus:ring-1 focus:ring-sky-500"
        :placeholder="t('custom_report_block.filter_results')"
      />
      <div v-if="pages > 1" class="flex items-center gap-2 text-sm text-slate-600">
        <button type="button" class="rounded border border-slate-300 px-2 py-1 hover:bg-slate-50 disabled:opacity-40" :disabled="page <= 1" @click="page--">
          {{ t('custom_report_block.previous') }}
        </button>
        <span>{{ t('custom_report_block.page_of', { page, pages }) }}</span>
        <button type="button" class="rounded border border-slate-300 px-2 py-1 hover:bg-slate-50 disabled:opacity-40" :disabled="page >= pages" @click="page++">
          {{ t('custom_report_block.next') }}
        </button>
      </div>
    </div>
    <div class="max-h-[60vh] overflow-auto rounded-md border border-slate-300">
      <table class="min-w-full border-collapse text-sm">
        <thead class="sticky top-0 z-10 bg-slate-50">
          <tr>
            <th
              v-for="(column, i) in columns"
              :key="i"
              scope="col"
              class="cursor-pointer select-none whitespace-nowrap border-b border-slate-300 px-3 py-2 text-left font-semibold text-slate-700 hover:bg-slate-100"
              :class="{ 'text-right': numericColumns[i] }"
              @click="sortBy(i)"
            >
              {{ column }}
              <Icon v-if="sortIndex === i" :name="sortDesc ? 'fa6-solid:arrow-down-wide-short' : 'fa6-solid:arrow-up-short-wide'" class="ml-1 text-[11px] text-sky-700" />
            </th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(row, r) in pageRows" :key="r" class="odd:bg-white even:bg-slate-50/60 hover:bg-sky-50/60">
            <td
              v-for="(value, i) in row"
              :key="i"
              class="max-w-[28rem] truncate whitespace-nowrap border-b border-slate-100 px-3 py-1.5 text-slate-800"
              :class="{ 'text-right tabular-nums': numericColumns[i], 'text-slate-400': value === null }"
              :title="display(value)"
            >
              {{ display(value) }}
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
