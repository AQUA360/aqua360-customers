<script setup>
// Taula dinàmica (agrupació per files i, opcionalment, columnes) sobre el resultat d'un informe.
import { ref, computed, watch } from 'vue';

const props = defineProps({
  columns: { type: Array, default: () => [] },
  rows: { type: Array, default: () => [] },
});
const { t, locale } = useI18n();

const rowField = ref(null);
const colField = ref(null);
const valueField = ref(null);
const aggregation = ref('count');

watch(() => props.columns, (columns) => {
  // Es conserva la configuració si les columnes no han canviat (p. ex. en tornar a executar).
  const valid = (i) => i !== null && i < columns.length;
  if (!valid(rowField.value)) rowField.value = columns.length ? 0 : null;
  if (!valid(colField.value)) colField.value = null;
  if (!valid(valueField.value)) valueField.value = null;
}, { immediate: true });

const aggregations = ['count', 'sum', 'avg', 'min', 'max'];
const needsValue = computed(() => aggregation.value !== 'count');

const numberFormat = computed(() => new Intl.NumberFormat(locale.value, { maximumFractionDigits: 2 }));
const collator = computed(() => new Intl.Collator(locale.value, { numeric: true, sensitivity: 'base' }));

const EMPTY = '\u0000empty';
const keyOf = (value) => (value === null || value === undefined || value === '' ? EMPTY : String(value));
const labelOf = (key) => (key === EMPTY ? t('custom_report_block.empty_value') : key);
const sortKeys = (keys) => [...keys].sort((a, b) => (a === EMPTY) - (b === EMPTY) || collator.value.compare(a, b));

const newAcc = () => ({ count: 0, n: 0, sum: 0, min: null, max: null });
const addTo = (acc, raw) => {
  acc.count += 1;
  if (raw === null || raw === undefined || raw === '') return;
  const value = typeof raw === 'number' ? raw : Number(raw);
  if (!Number.isFinite(value)) return;
  acc.n += 1;
  acc.sum += value;
  acc.min = acc.min === null ? value : Math.min(acc.min, value);
  acc.max = acc.max === null ? value : Math.max(acc.max, value);
};
const resultOf = (acc) => {
  if (!acc) return null;
  switch (aggregation.value) {
    case 'count': return acc.count;
    case 'sum': return acc.n ? acc.sum : null;
    case 'avg': return acc.n ? acc.sum / acc.n : null;
    case 'min': return acc.min;
    case 'max': return acc.max;
    default: return null;
  }
};

const pivot = computed(() => {
  if (rowField.value === null || (needsValue.value && valueField.value === null)) return null;
  const r = rowField.value;
  const c = colField.value;
  const v = valueField.value;
  const cells = new Map();
  const rowTotals = new Map();
  const colTotals = new Map();
  const grand = newAcc();
  for (const row of props.rows) {
    const rk = keyOf(row[r]);
    const ck = c === null ? '' : keyOf(row[c]);
    const raw = v === null ? null : row[v];
    if (!cells.has(rk)) cells.set(rk, new Map());
    const rowMap = cells.get(rk);
    if (!rowMap.has(ck)) rowMap.set(ck, newAcc());
    if (!rowTotals.has(rk)) rowTotals.set(rk, newAcc());
    if (!colTotals.has(ck)) colTotals.set(ck, newAcc());
    for (const acc of [rowMap.get(ck), rowTotals.get(rk), colTotals.get(ck), grand]) addTo(acc, raw);
  }
  return {
    rowKeys: sortKeys(cells.keys()),
    colKeys: c === null ? [''] : sortKeys(colTotals.keys()),
    cells,
    rowTotals,
    colTotals,
    grand,
  };
});

const format = (value) => (value === null || value === undefined ? '' : numberFormat.value.format(value));
const cell = (rk, ck) => format(resultOf(pivot.value.cells.get(rk)?.get(ck)));
</script>

<template>
  <div>
    <div class="mb-3 grid grid-cols-2 gap-3 md:grid-cols-4">
      <label class="text-xs font-medium text-slate-600">
        {{ t('custom_report_block.pivot_rows') }}
        <select v-model="rowField" class="mt-1 w-full rounded border border-slate-300 bg-white px-2 py-1.5 text-sm">
          <option :value="null">{{ t('custom_report_block.pivot_none') }}</option>
          <option v-for="(column, i) in columns" :key="i" :value="i">{{ column }}</option>
        </select>
      </label>
      <label class="text-xs font-medium text-slate-600">
        {{ t('custom_report_block.pivot_columns') }}
        <select v-model="colField" class="mt-1 w-full rounded border border-slate-300 bg-white px-2 py-1.5 text-sm">
          <option :value="null">{{ t('custom_report_block.pivot_none') }}</option>
          <option v-for="(column, i) in columns" :key="i" :value="i">{{ column }}</option>
        </select>
      </label>
      <label class="text-xs font-medium text-slate-600">
        {{ t('custom_report_block.pivot_aggregation') }}
        <select v-model="aggregation" class="mt-1 w-full rounded border border-slate-300 bg-white px-2 py-1.5 text-sm">
          <option v-for="agg in aggregations" :key="agg" :value="agg">{{ t(`custom_report_block.agg_${agg}`) }}</option>
        </select>
      </label>
      <label class="text-xs font-medium text-slate-600" :class="{ 'opacity-50': !needsValue }">
        {{ t('custom_report_block.pivot_values') }}
        <select v-model="valueField" :disabled="!needsValue" class="mt-1 w-full rounded border border-slate-300 bg-white px-2 py-1.5 text-sm">
          <option :value="null">{{ t('custom_report_block.pivot_none') }}</option>
          <option v-for="(column, i) in columns" :key="i" :value="i">{{ column }}</option>
        </select>
      </label>
    </div>

    <p v-if="!pivot" class="rounded border border-dashed border-slate-300 p-6 text-center text-sm text-slate-500">
      {{ t('custom_report_block.pivot_select_rows') }}
    </p>
    <div v-else class="max-h-[60vh] overflow-auto rounded-md border border-slate-300">
      <table class="min-w-full border-collapse text-sm">
        <thead class="sticky top-0 z-10 bg-slate-50">
          <tr>
            <th class="border-b border-r border-slate-300 px-3 py-2 text-left font-semibold text-slate-700">
              {{ columns[rowField] }}<template v-if="colField !== null"> / {{ columns[colField] }}</template>
            </th>
            <th
              v-for="ck in pivot.colKeys"
              :key="ck"
              class="whitespace-nowrap border-b border-slate-300 px-3 py-2 text-right font-semibold text-slate-700"
            >
              {{ colField === null ? t(`custom_report_block.agg_${aggregation}`) : labelOf(ck) }}
            </th>
            <th v-if="colField !== null" class="border-b border-l border-slate-300 bg-slate-100 px-3 py-2 text-right font-semibold text-slate-800">
              {{ t('custom_report_block.total') }}
            </th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="rk in pivot.rowKeys" :key="rk" class="odd:bg-white even:bg-slate-50/60 hover:bg-sky-50/60">
            <th class="whitespace-nowrap border-b border-r border-slate-200 px-3 py-1.5 text-left font-medium text-slate-800" :class="{ 'italic text-slate-400': rk === EMPTY }">
              {{ labelOf(rk) }}
            </th>
            <td v-for="ck in pivot.colKeys" :key="ck" class="border-b border-slate-100 px-3 py-1.5 text-right tabular-nums text-slate-800">
              {{ cell(rk, ck) }}
            </td>
            <td v-if="colField !== null" class="border-b border-l border-slate-200 bg-slate-50 px-3 py-1.5 text-right font-medium tabular-nums">
              {{ format(resultOf(pivot.rowTotals.get(rk))) }}
            </td>
          </tr>
        </tbody>
        <tfoot class="sticky bottom-0 bg-slate-100 font-semibold">
          <tr>
            <th class="border-t border-r border-slate-300 px-3 py-2 text-left">{{ t('custom_report_block.total') }}</th>
            <td v-for="ck in pivot.colKeys" :key="ck" class="border-t border-slate-300 px-3 py-2 text-right tabular-nums">
              {{ format(resultOf(pivot.colTotals.get(ck))) }}
            </td>
            <td v-if="colField !== null" class="border-l border-t border-slate-300 px-3 py-2 text-right tabular-nums">
              {{ format(resultOf(pivot.grand)) }}
            </td>
          </tr>
        </tfoot>
      </table>
    </div>
  </div>
</template>
