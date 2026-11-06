<script setup>
// Importació de rutes des d'un Excel/CSV: plantilla → fitxer + mode → previsualització → confirmació.
// Les files amb error s'ometen en confirmar.
import { ref, computed, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import { useToast } from 'vue-toastification';

const { t } = useI18n();
const toast = useToast();
const { $RouteApiService } = useNuxtApp();

const open = defineModel('open', { type: Boolean, default: false });
const emit = defineEmits(['done']);

const COLUMNS = [
  'route_token', 'route_name', 'route_zone', 'position', 'property_token',
  'supply_point_token', 'street', 'street_number', 'notebook', 'reader_observation'
];

const fileInputRef = ref(null);
const selectedFile = ref(null);
const mode = ref('append');
const preview = ref(null);
const loadingPreview = ref(false);
const loadingConfirm = ref(false);
const downloadingTemplate = ref(false);
const rowFilter = ref('all'); // 'all' | 'error' | 'warning'

const hasPreview = computed(() => !!preview.value);
const totals = computed(() => preview.value?.totals || {});
const rows = computed(() => preview.value?.rows || []);
const filteredRows = computed(() => {
  if (rowFilter.value === 'all') return rows.value;
  return rows.value.filter(row => row.status === rowFilter.value);
});
const validRows = computed(() => (totals.value.ok ?? 0) + (totals.value.warnings ?? 0));
const canConfirm = computed(() => validRows.value > 0);
const busy = computed(() => loadingPreview.value || loadingConfirm.value);

const modeOptions = computed(() => [
  { value: 'append', label: t('service_block.route_import_mode_append'), help: t('service_block.route_import_mode_append_help') },
  { value: 'replace', label: t('service_block.route_import_mode_replace'), help: t('service_block.route_import_mode_replace_help') }
]);

const downloadTemplate = async () => {
  if (downloadingTemplate.value) return;
  downloadingTemplate.value = true;
  try {
    await $RouteApiService.downloadImportTemplate();
  } catch (err) {
    console.error(err);
    toast.error(err?.message || t('common.error'));
  } finally {
    downloadingTemplate.value = false;
  }
};

const resetState = () => {
  selectedFile.value = null;
  mode.value = 'append';
  preview.value = null;
  loadingPreview.value = false;
  loadingConfirm.value = false;
  rowFilter.value = 'all';
  if (fileInputRef.value) {
    fileInputRef.value.value = '';
  }
};

watch(open, (isOpen) => {
  if (!isOpen) resetState();
});

// Canviar el mode invalida la previsualització
watch(mode, () => {
  preview.value = null;
});

const handleCancel = () => {
  if (busy.value) return;
  open.value = false;
};

const handleFileChange = (event) => {
  selectedFile.value = event.target.files?.[0] ?? null;
  preview.value = null;
};

const handleClearFile = () => {
  selectedFile.value = null;
  preview.value = null;
  if (fileInputRef.value) {
    fileInputRef.value.value = '';
  }
};

const handlePreview = async () => {
  if (!selectedFile.value || loadingPreview.value) return;
  loadingPreview.value = true;
  try {
    preview.value = await $RouteApiService.importPreview(selectedFile.value, mode.value);
    rowFilter.value = (preview.value?.totals?.errors ?? 0) > 0 ? 'error' : 'all';
  } catch (err) {
    console.error(err);
    preview.value = null;
  } finally {
    loadingPreview.value = false;
  }
};

const handleConfirm = async () => {
  if (!selectedFile.value || !canConfirm.value || loadingConfirm.value) return;
  if (mode.value === 'replace' && !confirm(t('service_block.route_import_replace_confirm'))) return;
  loadingConfirm.value = true;
  try {
    const result = await $RouteApiService.importConfirm(selectedFile.value, mode.value);
    toast.success(t('service_block.route_import_success', {
      routes: result?.routes_created ?? 0,
      positions: result?.positions_created ?? 0,
      properties: result?.properties_assigned ?? 0,
      supply_points: result?.supply_points_assigned ?? 0
    }));
    if (result?.skipped) {
      toast.warning(t('service_block.route_import_skipped', { count: result.skipped }));
    }
    open.value = false;
    emit('done', result);
  } catch (err) {
    console.error(err);
  } finally {
    loadingConfirm.value = false;
  }
};

const handleBackToUpload = () => {
  preview.value = null;
};

const statusClass = (status) => {
  if (status === 'error') return 'bg-red-100 text-red-800';
  if (status === 'warning') return 'bg-amber-100 text-amber-800';
  return 'bg-green-100 text-green-800';
};

const rowClass = (status) => {
  if (status === 'error') return 'bg-red-50/60';
  if (status === 'warning') return 'bg-amber-50/60';
  return '';
};

const translateOr = (key, fallback) => {
  const translated = t(key);
  return translated === key ? fallback : translated;
};

const statusLabel = (status) => translateOr(`service_block.route_import_status_${status}`, status);
const actionLabel = (action) => (action ? translateOr(`service_block.route_import_action_${action}`, action) : '');
</script>

<template>
  <Teleport to="body">
    <div v-if="open">
      <div class="fixed inset-0 bg-black bg-opacity-50 z-[60]" @click="handleCancel" />
      <div class="fixed inset-0 z-[70] flex items-center justify-center overflow-y-auto p-4" role="dialog"
        aria-modal="true" aria-labelledby="route-import-title" @click="handleCancel">
        <div class="bg-white rounded-lg shadow-xl p-6 max-w-5xl w-full relative max-h-[90vh] flex flex-col" @click.stop>
          <button type="button" class="absolute top-4 right-4 text-gray-500 hover:text-gray-700"
            :aria-label="t('common.cancel')" :disabled="busy" @click="handleCancel">
            <Icon name="fa6-solid:xmark" class="text-xl" />
          </button>

          <h2 id="route-import-title" class="text-lg font-semibold text-slate-800 mb-1 pr-8">
            {{ t('service_block.route_import_title') }}
          </h2>
          <p class="text-sm text-slate-600 mb-4">
            {{ t('service_block.route_import_help') }}
          </p>

          <!-- Pas 1: fitxer i mode -->
          <div v-if="!hasPreview" class="space-y-4 overflow-y-auto min-h-0 pr-1">
            <div class="rounded border border-slate-200 bg-slate-50 px-3 py-3 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
              <p class="text-sm text-slate-600">
                {{ t('service_block.route_import_template_help') }}
              </p>
              <button type="button" class="button-default flex items-center gap-2 whitespace-nowrap self-start"
                :disabled="downloadingTemplate" @click="downloadTemplate">
                <Icon :name="downloadingTemplate ? 'fa6-solid:spinner' : 'fa6-solid:file-excel'"
                  :class="downloadingTemplate ? 'animate-spin' : 'text-green-700'" />
                {{ t('service_block.meter_bulk_update_download_template') }}
              </button>
            </div>

            <details class="rounded border border-slate-200 px-3 py-2 text-sm text-slate-600">
              <summary class="cursor-pointer font-medium text-slate-700">{{ t('service_block.route_import_columns') }}</summary>
              <ul class="mt-2 space-y-1">
                <li v-for="col in COLUMNS" :key="col">
                  <span class="font-mono text-slate-800">{{ col }}</span>:
                  {{ t(`service_block.route_import_col_${col}`) }}
                </li>
              </ul>
              <p class="mt-2 text-xs text-slate-500">{{ t('service_block.route_import_columns_rule') }}</p>
            </details>

            <fieldset>
              <legend class="block text-sm font-medium text-slate-500 mb-1">{{ t('service_block.route_import_mode') }}</legend>
              <div class="flex flex-col gap-2">
                <label v-for="opt in modeOptions" :key="opt.value" class="flex items-start gap-2 text-sm text-slate-700">
                  <input v-model="mode" type="radio" name="route-import-mode" :value="opt.value" class="mt-1" />
                  <span>
                    <span class="font-medium">{{ opt.label }}</span>
                    <span class="block text-xs text-slate-500">{{ opt.help }}</span>
                  </span>
                </label>
              </div>
            </fieldset>

            <div>
              <label class="block text-sm font-medium text-slate-500 mb-1" for="route-import-file">
                {{ t('service_block.meter_bulk_update_file_label') }}
              </label>
              <div class="flex items-center gap-2 flex-wrap">
                <input id="route-import-file" ref="fileInputRef" type="file" accept=".csv,.xlsx,.xls"
                  class="block w-full text-sm text-slate-600 file:mr-3 file:py-1.5 file:px-3 file:rounded file:border-0 file:bg-slate-100 file:text-slate-700 hover:file:bg-slate-200"
                  @change="handleFileChange" />
                <button v-if="selectedFile" type="button" class="button-default text-sm" @click="handleClearFile">
                  {{ t('common.clear') }}
                </button>
              </div>
              <p v-if="selectedFile" class="mt-1 text-xs text-slate-500">{{ selectedFile.name }}</p>
              <p class="mt-2 text-xs text-slate-500">{{ t('service_block.route_import_file_hint') }}</p>
            </div>

            <div class="flex justify-end gap-2 mt-6">
              <button type="button" class="button-default" :disabled="loadingPreview" @click="handleCancel">
                {{ t('common.cancel') }}
              </button>
              <button type="button" class="button-primary flex items-center gap-2"
                :disabled="!selectedFile || loadingPreview" @click="handlePreview">
                <Icon :name="loadingPreview ? 'fa6-solid:spinner' : 'fa6-solid:eye'" :class="{ 'animate-spin': loadingPreview }" />
                {{ loadingPreview ? t('common.loading') + '...' : t('common.preview') }}
              </button>
            </div>
          </div>

          <!-- Pas 2: previsualització -->
          <div v-else class="flex flex-col min-h-0 flex-1 overflow-hidden">
            <div class="flex flex-wrap gap-2 mb-3">
              <span class="px-2.5 py-1 rounded-full text-xs font-semibold bg-slate-100 text-slate-700">
                {{ t('service_block.meter_bulk_stat_total', { count: totals.rows ?? 0 }) }}
              </span>
              <span class="px-2.5 py-1 rounded-full text-xs font-semibold bg-green-100 text-green-800">
                {{ t('service_block.route_import_stat_ok', { count: totals.ok ?? 0 }) }}
              </span>
              <span class="px-2.5 py-1 rounded-full text-xs font-semibold bg-amber-100 text-amber-800">
                {{ t('service_block.route_import_stat_warnings', { count: totals.warnings ?? 0 }) }}
              </span>
              <span class="px-2.5 py-1 rounded-full text-xs font-semibold bg-red-100 text-red-800">
                {{ t('service_block.meter_bulk_stat_errors', { count: totals.errors ?? 0 }) }}
              </span>
              <span class="px-2.5 py-1 rounded-full text-xs font-semibold bg-violet-100 text-violet-800">
                {{ t('service_block.route_import_stat_new_routes', { count: totals.new_routes ?? 0 }) }}
              </span>
              <span class="px-2.5 py-1 rounded-full text-xs font-semibold bg-sky-100 text-sky-800">
                {{ t('service_block.route_add_street_stat_positions', { count: totals.positions ?? 0 }) }}
              </span>
              <span class="px-2.5 py-1 rounded-full text-xs font-semibold bg-sky-100 text-sky-800">
                {{ t('service_block.route_add_street_stat_properties', { count: totals.properties ?? 0 }) }}
              </span>
              <span class="px-2.5 py-1 rounded-full text-xs font-semibold bg-sky-100 text-sky-800">
                {{ t('service_block.route_import_stat_supply_points', { count: totals.supply_points ?? 0 }) }}
              </span>
            </div>

            <p v-if="mode === 'replace'" class="text-xs text-amber-700 mb-2 flex items-center gap-1">
              <Icon name="fa6-solid:triangle-exclamation" />
              {{ t('service_block.route_import_replace_warning') }}
            </p>
            <p v-if="totals.errors > 0 && canConfirm" class="text-xs text-red-700 mb-2">
              {{ t('service_block.route_import_errors_skipped', { count: totals.errors }) }}
            </p>
            <p v-else-if="!canConfirm" class="text-xs text-slate-600 mb-2">
              {{ t('service_block.meter_bulk_update_nothing_to_apply') }}
            </p>

            <div class="flex gap-1 mb-2 text-sm">
              <button v-for="f in ['all', 'error', 'warning']" :key="f" type="button"
                class="px-3 py-1 rounded border"
                :class="rowFilter === f ? 'bg-sky-600 border-sky-600 text-white' : 'border-slate-300 text-slate-600 hover:bg-slate-50'"
                @click="rowFilter = f">
                {{ t(`service_block.route_import_filter_${f}`) }}
                <span class="opacity-75">({{ f === 'all' ? rows.length : rows.filter(r => r.status === f).length }})</span>
              </button>
            </div>

            <div class="overflow-y-auto flex-1 min-h-0 border border-slate-200 rounded">
              <table class="w-full text-sm">
                <thead class="bg-slate-50 text-slate-600 text-left sticky top-0">
                  <tr>
                    <th class="px-3 py-2 font-medium w-16">{{ t('service_block.meter_bulk_row') }}</th>
                    <th class="px-3 py-2 font-medium w-24">{{ t('route') }}</th>
                    <th class="px-3 py-2 font-medium w-20">{{ t('common.position') }}</th>
                    <th class="px-3 py-2 font-medium">{{ t('service_block.route_import_target') }}</th>
                    <th class="px-3 py-2 font-medium w-28">{{ t('common.status') }}</th>
                    <th class="px-3 py-2 font-medium">{{ t('service_block.route_import_message') }}</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="row in filteredRows" :key="row.row" class="border-t border-slate-100 align-top"
                    :class="rowClass(row.status)">
                    <td class="px-3 py-2 text-slate-500">{{ row.row }}</td>
                    <td class="px-3 py-2 font-medium text-slate-800">{{ row.route_token || '—' }}</td>
                    <td class="px-3 py-2 text-slate-700">{{ row.position ?? '—' }}</td>
                    <td class="px-3 py-2 text-slate-700">{{ row.target || '—' }}</td>
                    <td class="px-3 py-2">
                      <span class="px-2 py-0.5 rounded-full text-xs font-semibold" :class="statusClass(row.status)">
                        {{ statusLabel(row.status) }}
                      </span>
                      <span v-if="row.action && row.action !== 'none'" class="block mt-1 text-xs text-slate-500">
                        {{ actionLabel(row.action) }}
                      </span>
                    </td>
                    <td class="px-3 py-2 text-slate-600">{{ row.message || '' }}</td>
                  </tr>
                  <tr v-if="filteredRows.length === 0">
                    <td colspan="6" class="px-3 py-4 text-center text-slate-400">{{ t('common.no_records') }}</td>
                  </tr>
                </tbody>
              </table>
            </div>

            <div class="flex justify-between gap-2 mt-6 pt-4 border-t border-slate-100 flex-shrink-0">
              <button type="button" class="button-default" :disabled="loadingConfirm" @click="handleBackToUpload">
                {{ t('service_block.meter_bulk_update_back') }}
              </button>
              <div class="flex gap-2">
                <button type="button" class="button-default" :disabled="loadingConfirm" @click="handleCancel">
                  {{ t('common.cancel') }}
                </button>
                <button type="button" class="button-primary flex items-center gap-2"
                  :disabled="!canConfirm || loadingConfirm" @click="handleConfirm">
                  <Icon :name="loadingConfirm ? 'fa6-solid:spinner' : 'fa6-solid:check'" :class="{ 'animate-spin': loadingConfirm }" />
                  {{ loadingConfirm ? t('common.loading') + '...' : t('common.confirm') }}
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </Teleport>
</template>
