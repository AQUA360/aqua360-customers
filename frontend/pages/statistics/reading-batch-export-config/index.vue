<script setup>
import { ref, onMounted } from 'vue';
import H1 from '~/components/atoms/H1.vue';
import Draggable from 'vuedraggable';
import { useToast } from 'vue-toastification';
import AppLoading from '~/components/atoms/AppLoading.vue';

const { t } = useI18n();
const toast = useToast();
const { $ReadingBatchExportColumnApiService } = useNuxtApp();

let colSeq = 0;
const newCol = () => ({
  id: `local_${++colSeq}`,
  header: '',
  cell: '',
});

const columns = ref([newCol()]);
const pending = ref(true);
const saving = ref(false);
const clearing = ref(false);

const normalizeListResponse = (data) => {
  if (Array.isArray(data)) return data;
  if (data?.results && Array.isArray(data.results)) return data.results;
  return [];
};

const mapApiRowToColumn = (row) => ({
  id: row.id,
  header: row.name ?? '',
  cell: row.value ?? '',
  position: row.position,
});

const applyRowsFromApi = (rows) => {
  const list = normalizeListResponse(rows);
  if (list.length === 0) {
    colSeq = 0;
    columns.value = [newCol()];
    return;
  }
  const mapped = list.map(mapApiRowToColumn);
  mapped.sort((a, b) => (a.position ?? 0) - (b.position ?? 0));
  columns.value = mapped;
};

const loadColumns = async () => {
  pending.value = true;
  try {
    const data = await $ReadingBatchExportColumnApiService.getAll();
    applyRowsFromApi(data);
  } catch (e) {
    console.error(e);
  } finally {
    pending.value = false;
  }
};

const addColumn = () => {
  columns.value.push(newCol());
};

const removeColumn = (id) => {
  if (columns.value.length <= 1) return;
  const i = columns.value.findIndex((c) => c.id === id);
  if (i !== -1) {
    columns.value.splice(i, 1);
  }
};

/** 1-based position in the current column order (updates after drag). */
const columnOrderNumber = (id) => {
  const i = columns.value.findIndex((c) => c.id === id);
  return i === -1 ? 0 : i + 1;
};

const columnsToSyncPayload = () =>
  columns.value.map((c, index) => ({
    name: c.header ?? '',
    value: c.cell ?? '',
    position: index + 1,
  }));

const saveConfig = async () => {
  saving.value = true;
  try {
    const response = await $ReadingBatchExportColumnApiService.sync({
      columns: columnsToSyncPayload(),
    });
    applyRowsFromApi(response);
    toast.success(t('common.correct_save'));
  } catch (e) {
    console.error(e);
  } finally {
    saving.value = false;
  }
};

const clearAllColumns = async () => {
  if (!window.confirm(t('statistics_block.reading_batch_export_confirm_clear_all'))) return;
  clearing.value = true;
  try {
    await $ReadingBatchExportColumnApiService.clear();
    applyRowsFromApi([]);
    toast.success(t('common.deleted_successfully'));
  } catch (e) {
    console.error(e);
  } finally {
    clearing.value = false;
  }
};

onMounted(() => {
  loadColumns();
});

const escapeHtml = (s) =>
  String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');

/** Bold variable paths like %contract.token (safe for v-html: escapes first, then wraps matches). */
const legendHtml = (translationKey) => {
  const escaped = escapeHtml(t(translationKey));
  return escaped.replace(/(%[\w.]+)/g, '<strong class="font-semibold text-slate-900">$1</strong>');
};

/** Root token only (e.g. %meter), not dotted paths (%meter.comm_module stays plain after the root). */
const EXPORT_VAR_ROOT = /(%[a-zA-Z_][a-zA-Z0-9_]*)/g;

/** Split body cell text for overlay highlighting only (value stays unchanged). */
const splitExportVarSegments = (raw) => {
  const s = raw ?? '';
  if (!s) return [];
  return s.split(EXPORT_VAR_ROOT).map((text) => ({
    text,
    isVar: /^%[a-zA-Z_][a-zA-Z0-9_]*$/.test(text),
  }));
};

const syncBodyCellMirrorScroll = (event) => {
  const input = event.target;
  const wrap = input.closest('.cell-body-input');
  const mirror = wrap?.querySelector('[data-cell-value-mirror]');
  if (mirror) mirror.scrollLeft = input.scrollLeft;
};

/** Collapsible reference: common % paths grouped by root (contract, supply, …). */
const exportPathReferenceGroups = [
  {
    id: 'contract',
    labelKey: 'statistics_block.reading_batch_export_ref_contract',
    paths: [
      '%contract.token',
      '%contract.holder',
      '%contract.owner',
      '%contract.tenant',
      '%contract.status',
    ],
  },
  {
    id: 'supply',
    labelKey: 'statistics_block.reading_batch_export_ref_supply',
    paths: [
      '%supply.token',
      '%supply.address',
      '%supply.address.city',
      '%supply.address.country',
      '%supply.address.province',
      '%supply.address.street',
      '%supply.cadastral',
      '%supply.reader_observation',
      '%supply.property',
      '%supply.type',
    ],
  },
  {
    id: 'meter',
    labelKey: 'statistics_block.reading_batch_export_ref_meter',
    paths: [
      '%meter.code',
      '%meter.code2',
      '%meter.manufacturer',
      '%meter.manufacturing_year',
      '%meter.model',
      '%meter.comm_module',
      '%meter.comm_module_type',
      '%meter.comm_technology',
      '%meter.network_provider',
      '%meter.has_remote_reading',
    ],
  },
  {
    id: 'route',
    labelKey: 'statistics_block.reading_batch_export_ref_route',
    paths: ['%route.nate', '%route.token'],
  },
  {
    id: 'position',
    labelKey: 'statistics_block.reading_batch_export_ref_position',
    paths: ['%position.position', '%position.token'],
  },
  {
    id: 'contact',
    labelKey: 'statistics_block.reading_batch_export_ref_contact',
    paths: ['%contact.person', '%contact.phone', '%contact.email'],
  },
];

const exportPathSuffix = (groupId, path) => {
  const prefix = `%${groupId}.`;
  return path.startsWith(prefix) ? path.slice(prefix.length) : path;
};
</script>

<template>
  <div class="pb-6 px-4">
    <H1 class="mb-4">{{ t('settings_block.reading_batch_export_file') }}</H1>

    <div v-if="pending" class="rounded-md border border-slate-200 bg-white p-8">
      <AppLoading :text="t('common.loading')" />
    </div>

    <template v-else>
      <div class="overflow-x-auto rounded-md border border-slate-300 bg-white shadow-sm">
        <table class="w-full min-w-0 border-collapse text-sm">
          <thead>
            <Draggable
              v-model="columns"
              tag="tr"
              item-key="id"
              handle=".drag-col-handle"
              ghost-class="opacity-60"
              chosen-class="bg-sky-50"
            >
              <template #item="{ element }">
                <th
                  scope="col"
                  class="relative min-w-[7rem] max-w-[10rem] border border-slate-200 bg-slate-50 px-2 py-2.5 text-left font-semibold text-slate-800 align-middle"
                >
                  <button
                    type="button"
                    class="absolute right-1 top-1 z-10 flex h-5 w-5 items-center justify-center rounded text-slate-500 transition-colors hover:bg-slate-200/80 hover:text-slate-800 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-sky-500/50 disabled:pointer-events-none disabled:opacity-0"
                    :disabled="columns.length <= 1 || saving || clearing"
                    :aria-label="t('common.delete')"
                    @click.stop="removeColumn(element.id)"
                  >
                    <Icon name="fa6-solid:xmark" class="text-[11px] leading-none" />
                  </button>
                  <div class="flex min-w-0 items-center gap-1.5 pr-5">
                    <div
                      class="flex w-9 shrink-0 flex-col items-center justify-center gap-1 rounded-md border border-slate-200/90 bg-white py-1.5 shadow-sm"
                      role="group"
                      :aria-label="t('editor_block.column')"
                    >
                      <span
                        class="inline-flex min-h-[1.25rem] min-w-[1.25rem] items-center justify-center rounded border border-sky-200 bg-sky-50 px-1 text-[11px] font-mono font-bold tabular-nums leading-none text-sky-900"
                        :title="t('editor_block.column')"
                      >
                        {{ columnOrderNumber(element.id) }}
                      </span>
                      <button
                        type="button"
                        class="drag-col-handle cursor-grab rounded p-0.5 text-slate-500 hover:bg-slate-100 hover:text-slate-800 active:cursor-grabbing disabled:cursor-not-allowed disabled:opacity-50"
                        :aria-label="t('editor_block.column')"
                        :disabled="saving || clearing"
                      >
                        <Icon name="fa6-solid:grip-vertical" class="text-[15px] leading-none" />
                      </button>
                    </div>
                    <input
                      v-model="element.header"
                      type="text"
                      class="min-w-0 flex-1 rounded border border-slate-300 px-2 py-2 text-sm font-medium text-slate-900 shadow-sm focus:border-sky-500 focus:outline-none focus:ring-1 focus:ring-sky-500"
                      :placeholder="t('editor_block.head')"
                      :disabled="saving || clearing"
                    />
                  </div>
                </th>
              </template>
            </Draggable>
          </thead>
          <tbody>
            <tr>
              <td
                v-for="col in columns"
                :key="col.id"
                class="min-w-[7rem] max-w-[10rem] border border-slate-200 bg-white px-2 py-2.5 align-top"
              >
                <div
                  class="cell-body-input relative min-w-0 rounded border border-slate-300 bg-white shadow-sm focus-within:border-sky-500 focus-within:ring-1 focus-within:ring-sky-500"
                  :class="{ 'opacity-60': saving || clearing }"
                >
                  <div
                    data-cell-value-mirror
                    class="scrollbar-hide pointer-events-none absolute inset-0 z-0 overflow-x-auto overflow-y-hidden whitespace-nowrap px-2 py-2 text-left text-sm leading-normal text-slate-900"
                    aria-hidden="true"
                  >
                    <span v-if="col.cell" class="inline">
                      <span
                        v-for="(seg, si) in splitExportVarSegments(col.cell)"
                        :key="`${col.id}-v-${si}`"
                        :class="seg.isVar ? 'font-semibold text-blue-600' : ''"
                      >
                        {{ seg.text }}
                      </span>
                    </span>
                    <span v-else class="text-slate-400">{{ t('editor_block.body') }}</span>
                  </div>
                  <input
                    v-model="col.cell"
                    type="text"
                    class="scrollbar-hide relative z-10 w-full min-w-0 border-0 bg-transparent px-2 py-2 text-sm leading-normal text-transparent caret-slate-900 outline-none ring-0 selection:bg-sky-200/50 focus:ring-0 disabled:cursor-not-allowed disabled:bg-transparent"
                    spellcheck="false"
                    autocomplete="off"
                    :placeholder="t('editor_block.body')"
                    :disabled="saving || clearing"
                    @scroll="syncBodyCellMirrorScroll"
                  />
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <div
        class="mt-4 flex flex-wrap items-center justify-between gap-2 border-t border-slate-100 pt-3"
      >
        <button
          type="button"
          class="inline-flex items-center gap-1.5 rounded-md border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-600 shadow-none transition-colors hover:border-slate-300 hover:bg-slate-50 hover:text-slate-800 disabled:cursor-not-allowed disabled:opacity-50"
          :disabled="saving || clearing"
          @click="addColumn"
        >
          <Icon name="fa6-solid:plus" class="size-4 shrink-0 opacity-80" />
          {{ t('common.add') }} {{ t('editor_block.column') }}
        </button>
        <div class="flex flex-wrap items-center gap-2">
          <button
            type="button"
            class="inline-flex items-center gap-1.5 rounded-md border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-600 shadow-none transition-colors hover:border-slate-300 hover:bg-slate-50 hover:text-slate-800 disabled:cursor-not-allowed disabled:opacity-50"
            :disabled="saving || clearing"
            @click="clearAllColumns"
          >
            <Icon
              :name="clearing ? 'fa6-solid:spinner' : 'fa6-solid:trash-can'"
              class="size-4 shrink-0 opacity-80"
              :class="{ 'animate-spin': clearing }"
            />
            {{ t('statistics_block.reading_batch_export_clear_all') }}
          </button>
          <button
            type="button"
            class="inline-flex items-center gap-1.5 rounded-md border border-sky-400/60 bg-sky-500 px-3 py-2 text-sm font-medium text-white shadow-none transition-colors hover:bg-sky-600 disabled:cursor-not-allowed disabled:opacity-50"
            :disabled="saving || clearing"
            @click="saveConfig"
          >
            <Icon
              :name="saving ? 'fa6-solid:spinner' : 'fa6-solid:floppy-disk'"
              class="size-4 shrink-0 opacity-95"
              :class="{ 'animate-spin': saving }"
            />
            {{ t('common.save') }}
          </button>
        </div>
      </div>
    </template>

    <aside
      v-if="!pending"
      class="mt-6 rounded-md border border-slate-200 bg-slate-50 px-4 py-3 text-slate-800 shadow-sm"
      role="note"
      aria-labelledby="reading-batch-export-legend-title"
    >
      <h2 id="reading-batch-export-legend-title" class="text-base font-semibold text-slate-900">
        {{ t('statistics_block.reading_batch_export_legend_title') }}
      </h2>
      <ul class="mt-2 list-disc space-y-2 pl-5 text-sm leading-relaxed text-slate-700">
        <li v-html="legendHtml('statistics_block.reading_batch_export_legend_plain')" />
        <li v-html="legendHtml('statistics_block.reading_batch_export_legend_db_access')" />
        <li v-html="legendHtml('statistics_block.reading_batch_export_legend_example')" />
        <li v-html="legendHtml('statistics_block.reading_batch_export_legend_increment')" />
      </ul>

      <details
        class="mt-4 rounded-md border border-slate-200 bg-white text-slate-800 shadow-sm [&_summary::-webkit-details-marker]:hidden"
      >
        <summary
          class="flex cursor-pointer list-none items-center gap-2 px-3 py-2.5 text-sm font-medium text-slate-800 transition-colors hover:bg-slate-50"
        >
          <Icon name="fa6-solid:chevron-down" class="size-3.5 shrink-0 text-slate-500" />
          {{ t('statistics_block.reading_batch_export_reference_summary') }}
        </summary>
        <div class="space-y-4 border-t border-slate-100 px-3 pb-3 pt-2">
          <section
            v-for="grp in exportPathReferenceGroups"
            :key="grp.id"
            class="min-w-0"
          >
            <h3 class="text-xs font-semibold uppercase tracking-wide text-slate-500">
              {{ t(grp.labelKey) }}
            </h3>
            <div class="mt-1 overflow-x-auto rounded border border-slate-200 bg-white">
              <table class="w-full min-w-[16rem] border-collapse text-xs">
                <thead>
                  <tr class="border-b border-slate-200 bg-slate-50 text-left text-slate-600">
                    <th scope="col" class="px-2 py-1.5 font-medium">
                      {{ t('statistics_block.reading_batch_export_reference_col_field') }}
                    </th>
                    <th scope="col" class="px-2 py-1.5 font-medium">
                      {{ t('statistics_block.reading_batch_export_reference_col_expression') }}
                    </th>
                  </tr>
                </thead>
                <tbody>
                  <tr
                    v-for="path in grp.paths"
                    :key="path"
                    class="border-b border-slate-100 last:border-b-0"
                  >
                    <td class="whitespace-nowrap px-2 py-1.5 text-slate-700">
                      {{ exportPathSuffix(grp.id, path) }}
                    </td>
                    <td class="px-2 py-1.5 font-mono font-semibold text-blue-600">
                      {{ path }}
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </section>
        </div>
      </details>
    </aside>
  </div>
</template>
