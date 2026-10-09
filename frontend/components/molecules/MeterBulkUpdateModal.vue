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
const showUnchanged = ref(false);
const showDuplicates = ref(true);

const hasPreview = computed(() => !!preview.value);
const canConfirm = computed(() => (preview.value?.stats?.to_update ?? 0) > 0);
const duplicateCodes = computed(() => preview.value?.duplicate_codes_in_file ?? []);
const duplicateCount = computed(() =>
  preview.value?.stats?.duplicate_codes_in_file ?? duplicateCodes.value.length
);

const downloadTemplate = () => {
  const a = document.createElement('a');
  a.href = '/templates/meter_bulk_update_template.xlsx';
  a.download = 'meter_bulk_update_template.xlsx';
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
  showUnchanged.value = false;
  showDuplicates.value = true;
  if (fileInputRef.value) {
    fileInputRef.value.value = '';
  }
};

watch(open, (isOpen) => {
  if (!isOpen) {
    resetState();
  }
});

const handleCancel = () => {
  if (loadingPreview.value || loadingConfirm.value) return;
  open.value = false;
};

const handleFileChange = (event) => {
  const file = event.target.files?.[0] ?? null;
  selectedFile.value = file;
  preview.value = null;
};

const handleClearFile = () => {
  selectedFile.value = null;
  preview.value = null;
  if (fileInputRef.value) {
    fileInputRef.value.value = '';
  }
};

const formatChangeValue = (value) => {
  if (value === null || value === undefined || value === '') {
    return '—';
  }
  if (typeof value === 'boolean') {
    return value ? t('common.yes') : t('common.no');
  }
  if (typeof value === 'object') {
    return value.name || value.token || value.id || '—';
  }
  return String(value);
};

const formatFieldLabel = (field) => {
  const key = `service_block.meter_bulk_field_${field}`;
  const translated = t(key);
  return translated === key ? field : translated;
};

const formatUnchangedReason = (reason) => {
  if (!reason) return '';
  const key = `service_block.meter_bulk_unchanged_reason_${reason}`;
  const translated = t(key);
  return translated === key ? reason : translated;
};

const handlePreview = async () => {
  if (!selectedFile.value || loadingPreview.value) return;
  loadingPreview.value = true;
  try {
    preview.value = await $MeterApiService.bulkUpdatePreview(selectedFile.value);
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
    const result = await $MeterApiService.bulkUpdateConfirm(selectedFile.value);
    const updated = result?.stats?.updated ?? 0;
    toast.success(t('service_block.meter_bulk_update_success', { count: updated }));
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
        aria-modal="true" aria-labelledby="meter-bulk-update-title" @click="handleCancel">
        <div class="bg-white rounded-lg shadow-xl p-6 max-w-4xl w-full relative max-h-[90vh] flex flex-col"
          @click.stop>
          <button type="button" class="absolute top-4 right-4 text-gray-500 hover:text-gray-700"
            :aria-label="t('common.cancel')" :disabled="loadingPreview || loadingConfirm" @click="handleCancel">
            <Icon name="fa6-solid:xmark" class="text-xl" />
          </button>

          <h2 id="meter-bulk-update-title" class="text-lg font-semibold text-slate-800 mb-1 pr-8">
            {{ t('service_block.meter_bulk_update_title') }}
          </h2>
          <p class="text-sm text-slate-600 mb-4">
            {{ t('service_block.meter_bulk_update_help') }}
          </p>

          <!-- Upload step -->
          <div v-if="!hasPreview" class="space-y-4">
            <div class="rounded border border-slate-200 bg-slate-50 px-3 py-3 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
              <p class="text-sm text-slate-600">
                {{ t('service_block.meter_bulk_update_template_help') }}
              </p>
              <button type="button" class="button-default flex items-center gap-2 whitespace-nowrap self-start"
                @click="downloadTemplate">
                <Icon name="fa6-solid:file-excel" class="text-green-700" />
                {{ t('service_block.meter_bulk_update_download_template') }}
              </button>
            </div>

            <div>
              <label class="block text-sm font-medium text-slate-500 mb-1" for="meter-bulk-file">
                {{ t('service_block.meter_bulk_update_file_label') }}
              </label>
              <div class="flex items-center gap-2 flex-wrap">
                <input id="meter-bulk-file" ref="fileInputRef" type="file" accept=".csv,.xlsx,.xls"
                  class="block w-full text-sm text-slate-600 file:mr-3 file:py-1.5 file:px-3 file:rounded file:border-0 file:bg-slate-100 file:text-slate-700 hover:file:bg-slate-200"
                  @change="handleFileChange" />
                <button v-if="selectedFile" type="button" class="button-default text-sm" @click="handleClearFile">
                  {{ t('common.clear') }}
                </button>
              </div>
              <p v-if="selectedFile" class="mt-1 text-xs text-slate-500">
                {{ selectedFile.name }}
              </p>
              <p class="mt-2 text-xs text-slate-500">
                {{ t('service_block.meter_bulk_update_file_hint') }}
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
                {{ t('service_block.meter_bulk_stat_total', { count: preview.stats?.total_rows ?? 0 }) }}
              </span>
              <span class="px-2.5 py-1 rounded-full text-xs font-semibold bg-sky-100 text-sky-800">
                {{ t('service_block.meter_bulk_stat_to_update', { count: preview.stats?.to_update ?? 0 }) }}
              </span>
              <span class="px-2.5 py-1 rounded-full text-xs font-semibold bg-slate-100 text-slate-600">
                {{ t('service_block.meter_bulk_stat_unchanged', { count: preview.stats?.unchanged ?? 0 }) }}
              </span>
              <span class="px-2.5 py-1 rounded-full text-xs font-semibold bg-amber-100 text-amber-800">
                {{ t('service_block.meter_bulk_stat_not_found', { count: preview.stats?.not_found ?? 0 }) }}
              </span>
              <span class="px-2.5 py-1 rounded-full text-xs font-semibold bg-red-100 text-red-800">
                {{ t('service_block.meter_bulk_stat_errors', { count: preview.stats?.errors ?? 0 }) }}
              </span>
              <span v-if="duplicateCount" class="px-2.5 py-1 rounded-full text-xs font-semibold bg-violet-100 text-violet-800">
                {{ t('service_block.meter_bulk_stat_duplicates', { count: duplicateCount }) }}
              </span>
            </div>

            <p v-if="duplicateCount" class="text-xs text-violet-800 mb-3">
              {{ t('service_block.meter_bulk_update_duplicates_warning') }}
            </p>
            <p v-if="(preview.stats?.not_found || preview.stats?.errors) && canConfirm"
              class="text-xs text-amber-700 mb-3">
              {{ t('service_block.meter_bulk_update_partial_warning') }}
            </p>
            <p v-else-if="!canConfirm" class="text-xs text-slate-600 mb-3">
              {{ t('service_block.meter_bulk_update_nothing_to_apply') }}
            </p>

            <div class="overflow-y-auto flex-1 min-h-0 space-y-4 pr-1">
              <!-- Updates table -->
              <section v-if="preview.updates?.length">
                <h3 class="text-sm font-semibold text-slate-700 mb-2">
                  {{ t('service_block.meter_bulk_section_updates') }}
                </h3>
                <div class="border border-slate-200 rounded overflow-hidden">
                  <table class="w-full text-sm">
                    <thead class="bg-slate-50 text-slate-600 text-left">
                      <tr>
                        <th class="px-3 py-2 font-medium w-16">{{ t('service_block.meter_bulk_row') }}</th>
                        <th class="px-3 py-2 font-medium w-28">{{ t('common.code') }}</th>
                        <th class="px-3 py-2 font-medium">{{ t('service_block.meter_bulk_section_changes') }}</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr v-for="row in preview.updates" :key="`${row.row}-${row.code}`"
                        class="border-t border-slate-100 align-top">
                        <td class="px-3 py-2 text-slate-500">{{ row.row }}</td>
                        <td class="px-3 py-2 font-medium text-slate-800">{{ row.code }}</td>
                        <td class="px-3 py-2">
                          <ul class="space-y-1">
                            <li v-for="(change, field) in row.changes" :key="field" class="text-slate-700">
                              <span class="font-medium text-slate-600">{{ formatFieldLabel(field) }}:</span>
                              <span class="text-slate-500"> {{ formatChangeValue(change.old) }} </span>
                              <span class="text-slate-400 mx-1">→</span>
                              <span class="text-sky-700">{{ formatChangeValue(change.new) }}</span>
                            </li>
                          </ul>
                        </td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </section>

              <!-- Duplicate codes in file -->
              <section v-if="duplicateCodes.length">
                <button type="button"
                  class="flex items-center gap-2 text-sm font-semibold text-slate-700 mb-2 hover:text-slate-900"
                  @click="showDuplicates = !showDuplicates">
                  <Icon :name="showDuplicates ? 'fa6-solid:chevron-down' : 'fa6-solid:chevron-right'" class="text-xs" />
                  {{ t('service_block.meter_bulk_section_duplicates') }}
                  ({{ duplicateCodes.length }})
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
                  {{ t('service_block.meter_bulk_section_not_found') }}
                  ({{ preview.not_found.length }})
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
                  {{ t('service_block.meter_bulk_section_errors') }}
                  ({{ preview.errors.length }})
                </button>
                <ul v-if="showErrors" class="text-sm text-red-800 bg-red-50 rounded px-3 py-2 space-y-1">
                  <li v-for="(err, idx) in preview.errors" :key="idx">
                    <span class="font-medium">{{ t('service_block.meter_bulk_row') }} {{ err.row }}</span>
                    <span v-if="err.code" class="font-mono"> ({{ err.code }})</span>:
                    {{ err.message }}
                  </li>
                </ul>
              </section>

              <!-- Unchanged (collapsed by default) -->
              <section v-if="preview.unchanged?.length">
                <button type="button"
                  class="flex items-center gap-2 text-sm font-semibold text-slate-700 mb-2 hover:text-slate-900"
                  @click="showUnchanged = !showUnchanged">
                  <Icon :name="showUnchanged ? 'fa6-solid:chevron-down' : 'fa6-solid:chevron-right'" class="text-xs" />
                  {{ t('service_block.meter_bulk_section_unchanged') }}
                  ({{ preview.unchanged.length }})
                </button>
                <ul v-if="showUnchanged" class="text-sm text-slate-600 bg-slate-50 rounded px-3 py-2 space-y-0.5">
                  <li v-for="item in preview.unchanged" :key="`${item.row}-${item.code}`">
                    <span class="font-mono">{{ item.code }}</span>
                    <span class="text-slate-400">({{ t('service_block.meter_bulk_row') }} {{ item.row }})</span>
                    <span v-if="item.reason" class="text-violet-700 ml-1">
                      — {{ formatUnchangedReason(item.reason) }}
                    </span>
                  </li>
                </ul>
              </section>
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
