<script setup>
import { ref, watch, computed } from 'vue';
import { useI18n } from 'vue-i18n';
import { useToast } from 'vue-toastification';

const { t } = useI18n();
const toast = useToast();
const { $MeterApiService } = useNuxtApp();

const open = defineModel('open', { type: Boolean, default: false });
const emit = defineEmits(['done']);

const fileInputRef = ref(null);
const selectedFile = ref(null);
const preview = ref(null);
const loadingPreview = ref(false);
const loadingConfirm = ref(false);
const showNotFound = ref(true);
const showErrors = ref(true);
const showDuplicates = ref(true);

const hasPreview = computed(() => !!preview.value);
const canConfirm = computed(() => (preview.value?.stats?.to_change ?? 0) > 0);
const duplicateCodes = computed(() => preview.value?.duplicate_codes_in_file ?? []);
const duplicateCount = computed(() => preview.value?.stats?.duplicate_codes_in_file ?? duplicateCodes.value.length);

const downloadTemplate = () => {
  const a = document.createElement('a');
  a.href = '/templates/meter_bulk_change_template.xlsx';
  a.download = 'meter_bulk_change_template.xlsx';
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
};

const resetState = () => {
  selectedFile.value = null;
  preview.value = null;
  loadingPreview.value = false;
  loadingConfirm.value = false;
  showNotFound.value = true;
  showErrors.value = true;
  showDuplicates.value = true;
  if (fileInputRef.value) fileInputRef.value.value = '';
};

watch(open, (isOpen) => {
  if (!isOpen) resetState();
});

const handleCancel = () => {
  if (loadingPreview.value || loadingConfirm.value) return;
  open.value = false;
};

const handleFileChange = (event) => {
  selectedFile.value = event.target.files?.[0] ?? null;
  preview.value = null;
};

const handleClearFile = () => {
  selectedFile.value = null;
  preview.value = null;
  if (fileInputRef.value) fileInputRef.value.value = '';
};

const formatDate = (iso) => (iso ? iso.split('-').reverse().join('/') : '—');

const handlePreview = async () => {
  if (!selectedFile.value || loadingPreview.value) return;
  loadingPreview.value = true;
  try {
    preview.value = await $MeterApiService.bulkChangePreview(selectedFile.value);
  } catch (err) {
    console.error(err);
    preview.value = null;
  } finally {
    loadingPreview.value = false;
  }
};

const handleConfirm = async () => {
  if (!selectedFile.value || !canConfirm.value || loadingConfirm.value) return;
  loadingConfirm.value = true;
  try {
    const result = await $MeterApiService.bulkChangeConfirm(selectedFile.value);
    const changed = result?.stats?.changed ?? 0;
    const failed = result?.stats?.failed ?? 0;
    const created = result?.stats?.created ?? 0;
    if (failed > 0) {
      toast.warning(t('service_block.meter_bulk_change_partial_result', { changed, failed }));
    } else {
      toast.success(created > 0
        ? t('service_block.meter_bulk_change_success_with_created', { count: changed, created })
        : t('service_block.meter_bulk_change_success', { count: changed }));
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
</script>

<template>
  <Teleport to="body">
    <div v-if="open">
      <div class="fixed inset-0 bg-black bg-opacity-50 z-[60]" @click="handleCancel" />
      <div class="fixed inset-0 z-[70] flex items-center justify-center overflow-y-auto p-4" role="dialog"
        aria-modal="true" aria-labelledby="meter-bulk-change-title" @click="handleCancel">
        <div class="bg-white rounded-lg shadow-xl p-6 max-w-4xl w-full relative max-h-[90vh] flex flex-col"
          @click.stop>
          <button type="button" class="absolute top-4 right-4 text-gray-500 hover:text-gray-700"
            :aria-label="t('common.cancel')" :disabled="loadingPreview || loadingConfirm" @click="handleCancel">
            <Icon name="fa6-solid:xmark" class="text-xl" />
          </button>

          <h2 id="meter-bulk-change-title" class="text-lg font-semibold text-slate-800 mb-1 pr-8">
            {{ t('service_block.meter_bulk_change_title') }}
          </h2>
          <p class="text-sm text-slate-600 mb-4">
            {{ t('service_block.meter_bulk_change_help') }}
          </p>

          <!-- Upload step -->
          <div v-if="!hasPreview" class="space-y-4">
            <div class="rounded border border-slate-200 bg-slate-50 px-3 py-3 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
              <p class="text-sm text-slate-600">
                {{ t('service_block.meter_bulk_change_template_help') }}
              </p>
              <button type="button" class="button-default flex items-center gap-2 whitespace-nowrap self-start"
                @click="downloadTemplate">
                <Icon name="fa6-solid:file-excel" class="text-green-700" />
                {{ t('service_block.meter_bulk_change_download_template') }}
              </button>
            </div>

            <div>
              <label class="block text-sm font-medium text-slate-500 mb-1" for="meter-bulk-change-file">
                {{ t('service_block.meter_bulk_change_file_label') }}
              </label>
              <div class="flex items-center gap-2 flex-wrap">
                <input id="meter-bulk-change-file" ref="fileInputRef" type="file" accept=".csv,.xlsx,.xls"
                  class="block w-full text-sm text-slate-600 file:mr-3 file:py-1.5 file:px-3 file:rounded file:border-0 file:bg-slate-100 file:text-slate-700 hover:file:bg-slate-200"
                  @change="handleFileChange" />
                <button v-if="selectedFile" type="button" class="button-default text-sm" @click="handleClearFile">
                  {{ t('common.clear') }}
                </button>
              </div>
              <p v-if="selectedFile" class="mt-1 text-xs text-slate-500">{{ selectedFile.name }}</p>
              <p class="mt-2 text-xs text-slate-500">
                {{ t('service_block.meter_bulk_change_file_hint') }}
              </p>
            </div>

            <div class="flex justify-end gap-2 mt-6">
              <button type="button" class="button-default" :disabled="loadingPreview" @click="handleCancel">
                {{ t('common.cancel') }}
              </button>
              <button type="button" class="button-primary flex items-center gap-2"
                :disabled="!selectedFile || loadingPreview" @click="handlePreview">
                <Icon :name="loadingPreview ? 'fa6-solid:spinner' : 'fa6-solid:eye'"
                  :class="{ 'animate-spin': loadingPreview }" />
                {{ loadingPreview ? t('common.loading') + '...' : t('common.preview') }}
              </button>
            </div>
          </div>

          <!-- Preview step -->
          <div v-else class="flex flex-col min-h-0 flex-1 overflow-hidden">
            <div class="flex flex-wrap gap-2 mb-4">
              <span class="px-2.5 py-1 rounded-full text-xs font-semibold bg-slate-100 text-slate-700">
                {{ t('service_block.meter_bulk_change_stat_total', { count: preview.stats?.total_rows ?? 0 }) }}
              </span>
              <span class="px-2.5 py-1 rounded-full text-xs font-semibold bg-sky-100 text-sky-800">
                {{ t('service_block.meter_bulk_change_stat_to_change', { count: preview.stats?.to_change ?? 0 }) }}
              </span>
              <span v-if="preview.stats?.to_create" class="px-2.5 py-1 rounded-full text-xs font-semibold bg-emerald-100 text-emerald-800">
                {{ t('service_block.meter_bulk_change_stat_to_create', { count: preview.stats.to_create }) }}
              </span>
              <span class="px-2.5 py-1 rounded-full text-xs font-semibold bg-amber-100 text-amber-800">
                {{ t('service_block.meter_bulk_change_stat_not_found', { count: preview.stats?.not_found ?? 0 }) }}
              </span>
              <span class="px-2.5 py-1 rounded-full text-xs font-semibold bg-red-100 text-red-800">
                {{ t('service_block.meter_bulk_change_stat_errors', { count: preview.stats?.errors ?? 0 }) }}
              </span>
              <span v-if="duplicateCount" class="px-2.5 py-1 rounded-full text-xs font-semibold bg-violet-100 text-violet-800">
                {{ t('service_block.meter_bulk_change_stat_duplicates', { count: duplicateCount }) }}
              </span>
            </div>

            <p v-if="duplicateCount" class="text-xs text-violet-800 mb-3">
              {{ t('service_block.meter_bulk_change_duplicates_warning') }}
            </p>
            <p v-if="(preview.stats?.not_found || preview.stats?.errors) && canConfirm"
              class="text-xs text-amber-700 mb-3">
              {{ t('service_block.meter_bulk_change_partial_warning') }}
            </p>
            <p v-else-if="!canConfirm" class="text-xs text-slate-600 mb-3">
              {{ t('service_block.meter_bulk_change_nothing_to_apply') }}
            </p>

            <div class="overflow-y-auto flex-1 min-h-0 space-y-4 pr-1">
              <!-- Changes table -->
              <section v-if="preview.changes?.length">
                <h3 class="text-sm font-semibold text-slate-700 mb-2">
                  {{ t('service_block.meter_bulk_change_section_changes') }}
                </h3>
                <div class="border border-slate-200 rounded overflow-hidden">
                  <table class="w-full text-sm">
                    <thead class="bg-slate-50 text-slate-600 text-left">
                      <tr>
                        <th class="px-3 py-2 font-medium w-16">{{ t('service_block.meter_bulk_change_row') }}</th>
                        <th class="px-3 py-2 font-medium">{{ t('service_block.meter_bulk_change_col_meters') }}</th>
                        <th class="px-3 py-2 font-medium">{{ t('service_block.meter_bulk_change_col_supply_point') }}</th>
                        <th class="px-3 py-2 font-medium">{{ t('service_block.meter_bulk_change_col_readings') }}</th>
                        <th class="px-3 py-2 font-medium w-28">{{ t('service_block.meter_bulk_change_col_date') }}</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr v-for="row in preview.changes" :key="`${row.row}-${row.code}`"
                        class="border-t border-slate-100 align-top">
                        <td class="px-3 py-2 text-slate-500">{{ row.row }}</td>
                        <td class="px-3 py-2">
                          <span class="font-mono text-slate-500">{{ row.code }}</span>
                          <span class="text-slate-400 mx-1">→</span>
                          <span class="font-mono font-medium text-sky-700">{{ row.new_code }}</span>
                          <span v-if="row.new_meter?.will_create"
                            class="ml-2 px-1.5 py-0.5 rounded text-xs font-semibold bg-emerald-100 text-emerald-800">
                            {{ t('service_block.meter_bulk_change_badge_new_meter') }}
                          </span>
                          <p v-if="row.new_meter?.will_create && (row.new_meter.caliber || row.new_meter.has_remote_reading !== undefined && row.new_meter.has_remote_reading !== null || row.new_meter.comm_technology)"
                            class="mt-1 text-xs text-slate-500">
                            <span v-if="row.new_meter.caliber">
                              {{ t('service_block.meter_bulk_change_caliber') }}: {{ row.new_meter.caliber }}
                            </span>
                            <span v-if="row.new_meter.has_remote_reading !== null && row.new_meter.has_remote_reading !== undefined" class="ml-2">
                              {{ t('service_block.meter_bulk_change_remote_reading') }}:
                              {{ row.new_meter.has_remote_reading ? t('common.yes') : t('common.no') }}
                            </span>
                            <span v-if="row.new_meter.comm_technology" class="ml-2">
                              {{ t('service_block.meter_bulk_change_comm_technology') }}: {{ row.new_meter.comm_technology }}
                            </span>
                          </p>
                          <p v-for="w in row.warnings" :key="w.code" class="mt-1 text-xs text-amber-700 flex items-start gap-1">
                            <Icon name="fa6-solid:triangle-exclamation" class="mt-0.5" />
                            {{ t(`service_block.meter_bulk_change_warning_${w.code}`, { detail: w.detail }) }}
                          </p>
                        </td>
                        <td class="px-3 py-2 text-slate-700">
                          <div class="font-medium">{{ row.supply_point?.token }}</div>
                          <div class="text-xs text-slate-500">{{ row.supply_point?.address }}</div>
                        </td>
                        <td class="px-3 py-2 text-slate-700">
                          <div>
                            <span class="text-slate-500">{{ t('service_block.meter_bulk_change_final') }}:</span>
                            {{ row.final_reading }}
                          </div>
                          <div>
                            <span class="text-slate-500">{{ t('service_block.meter_bulk_change_initial') }}:</span>
                            {{ row.initial_reading }}
                          </div>
                        </td>
                        <td class="px-3 py-2 text-slate-700">{{ formatDate(row.change_date) }}</td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </section>

              <!-- Duplicates -->
              <section v-if="duplicateCodes.length">
                <button type="button"
                  class="flex items-center gap-2 text-sm font-semibold text-slate-700 mb-2 hover:text-slate-900"
                  @click="showDuplicates = !showDuplicates">
                  <Icon :name="showDuplicates ? 'fa6-solid:chevron-down' : 'fa6-solid:chevron-right'" class="text-xs" />
                  {{ t('service_block.meter_bulk_change_section_duplicates') }} ({{ duplicateCodes.length }})
                </button>
                <ul v-if="showDuplicates" class="text-sm text-violet-800 bg-violet-50 rounded px-3 py-2 space-y-0.5">
                  <li v-for="code in duplicateCodes" :key="code" class="font-mono">{{ code }}</li>
                </ul>
              </section>

              <!-- Not found -->
              <section v-if="preview.not_found?.length">
                <button type="button"
                  class="flex items-center gap-2 text-sm font-semibold text-slate-700 mb-2 hover:text-slate-900"
                  @click="showNotFound = !showNotFound">
                  <Icon :name="showNotFound ? 'fa6-solid:chevron-down' : 'fa6-solid:chevron-right'" class="text-xs" />
                  {{ t('service_block.meter_bulk_change_section_not_found') }} ({{ preview.not_found.length }})
                </button>
                <ul v-if="showNotFound" class="text-sm text-amber-800 bg-amber-50 rounded px-3 py-2 space-y-0.5">
                  <li v-for="code in preview.not_found" :key="code" class="font-mono">{{ code }}</li>
                </ul>
              </section>

              <!-- Errors -->
              <section v-if="preview.errors?.length">
                <button type="button"
                  class="flex items-center gap-2 text-sm font-semibold text-slate-700 mb-2 hover:text-slate-900"
                  @click="showErrors = !showErrors">
                  <Icon :name="showErrors ? 'fa6-solid:chevron-down' : 'fa6-solid:chevron-right'" class="text-xs" />
                  {{ t('service_block.meter_bulk_change_section_errors') }} ({{ preview.errors.length }})
                </button>
                <ul v-if="showErrors" class="text-sm text-red-800 bg-red-50 rounded px-3 py-2 space-y-1">
                  <li v-for="(err, idx) in preview.errors" :key="idx">
                    <span class="font-medium">{{ t('service_block.meter_bulk_change_row') }} {{ err.row }}</span>
                    <span v-if="err.code" class="font-mono"> ({{ err.code }})</span>:
                    {{ err.message }}
                  </li>
                </ul>
              </section>
            </div>

            <div class="flex justify-between gap-2 mt-6 pt-4 border-t border-slate-100 flex-shrink-0">
              <button type="button" class="button-default" :disabled="loadingConfirm" @click="handleBackToUpload">
                {{ t('service_block.meter_bulk_change_back') }}
              </button>
              <div class="flex gap-2">
                <button type="button" class="button-default" :disabled="loadingConfirm" @click="handleCancel">
                  {{ t('common.cancel') }}
                </button>
                <button type="button" class="button-primary flex items-center gap-2"
                  :disabled="!canConfirm || loadingConfirm" @click="handleConfirm">
                  <Icon :name="loadingConfirm ? 'fa6-solid:spinner' : 'fa6-solid:check'"
                    :class="{ 'animate-spin': loadingConfirm }" />
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