<script setup>
// Càrrega de lectures de Smart Metering des d'«Introduir lectures».
// Genera un document de lectures (amb Excel) que després el lot selecciona
// com qualsevol altre fitxer de lectures. Es pot limitar a unes rutes, zones o
// lots, o carregar tots els comptadors Smart Metering.
import { computed, ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import { format } from 'date-fns';
import { useToast } from 'vue-toastification';
import SmartMeteringReadingsDialog from '~/components/molecules/SmartMeteringReadingsDialog.vue';

const { t } = useI18n();
const toast = useToast();
const { $SmartMeteringApiService, $apiManager } = useNuxtApp();

const props = defineProps({
  show: {
    type: Boolean,
    default: false,
  },
});

const emit = defineEmits(['close', 'loaded']);

const readingDate = ref(format(new Date(), 'yyyy-MM-dd'));
const replace = ref(false);
const previewLoading = ref(false);
const previewTaskId = ref(null);
const preview = ref(null);
const showPreviewDialog = ref(false);
const saving = ref(false);
const loadAll = ref(false);
const routeIds = ref([]);
const routeZoneIds = ref([]);
const batchIds = ref([]);
const scopeOptions = ref({ routes: [], route_zones: [], batches: [] });

const scope = computed(() => (loadAll.value ? null : {
  route_ids: routeIds.value,
  route_zone_ids: routeZoneIds.value,
  batch_ids: batchIds.value,
}));
const hasScope = computed(() => loadAll.value
  || routeIds.value.length > 0
  || routeZoneIds.value.length > 0
  || batchIds.value.length > 0);
const busy = computed(() => previewLoading.value || !!previewTaskId.value);

const loadScopeOptions = async () => {
  try {
    scopeOptions.value = await $SmartMeteringApiService.getScopeOptions();
  } catch (error) {
    console.error(error);
    toast.error(error?.data?.error || error?.message || t('common.error'));
  }
};

watch(() => props.show, (show) => {
  if (show) loadScopeOptions();
}, { immediate: true });

// La confirmació de substituir només val per a la data i els comptadors en què s'ha demanat.
watch([readingDate, scope], () => {
  replace.value = false;
}, { deep: true });

const reset = () => {
  replace.value = false;
  loadAll.value = false;
  routeIds.value = [];
  routeZoneIds.value = [];
  batchIds.value = [];
  previewLoading.value = false;
  previewTaskId.value = null;
  preview.value = null;
  showPreviewDialog.value = false;
  saving.value = false;
};

const handleClose = () => {
  if (previewLoading.value || previewTaskId.value || saving.value) return;
  reset();
  emit('close');
};

/** 409: ja hi ha una càrrega per a la data. Retorna true si l'usuari accepta substituir-la. */
const confirmReplaceOnConflict = (error) => {
  const existing = error?.data?.existing_document;
  if (error?.response?.status !== 409 || !existing) return false;
  if (existing.processing) {
    toast.error(t('reading_block.smart_metering_load_in_progress'));
    return false;
  }
  if (existing.count > 1) {
    toast.error(t('reading_block.smart_metering_already_loaded_several', { token: existing.token }));
    return false;
  }
  if (existing.scope_reduced) {
    toast.error(t('reading_block.smart_metering_scope_reduced', { token: existing.token }));
    return false;
  }
  if (!existing.replaceable) {
    toast.error(t('reading_block.smart_metering_already_loaded_locked', { token: existing.token }));
    return false;
  }
  return confirm(t('reading_block.smart_metering_replace_confirm', { token: existing.token }));
};

const startPreview = async () => {
  if (!readingDate.value) {
    toast.error(t('billing_block.reading_date'));
    return;
  }
  if (!hasScope.value) {
    toast.error(t('reading_block.smart_metering_select_scope'));
    return;
  }
  previewLoading.value = true;
  try {
    const response = await $SmartMeteringApiService.previewReadings({
      reading_date: readingDate.value,
      replace: replace.value,
      scope: scope.value,
    });
    if (!response?.task_id) {
      throw new Error(t('common.error'));
    }
    // La barra de progrés (ProcessColorBadge) obre la previsualització en acabar (@refresh).
    previewTaskId.value = response.task_id;
  } catch (error) {
    if (!replace.value && confirmReplaceOnConflict(error)) {
      replace.value = true;
      previewLoading.value = false;
      await startPreview();
      return;
    }
    if (error?.response?.status !== 409) {
      console.error(error);
      toast.error(error?.data?.error || error?.message || t('common.error'));
    }
  } finally {
    previewLoading.value = false;
  }
};

const onPreviewTaskRefresh = async () => {
  const taskId = previewTaskId.value;
  previewTaskId.value = null;
  if (!taskId) return;

  try {
    const res = await $apiManager.checkTask(taskId);
    if (res?.state === 'SUCCESS' && res.result) {
      preview.value = res.result;
      showPreviewDialog.value = true;
    } else if (res?.state === 'FAILURE') {
      toast.error(res.error || t('common.error'));
    }
  } catch (error) {
    console.error(error);
    toast.error(error?.data?.error || error?.message || t('common.error'));
  }
};

const waitForTask = (taskId) => new Promise((resolve, reject) => {
  const poll = async () => {
    try {
      const res = await $apiManager.checkTask(taskId);
      if (res?.state === 'SUCCESS') {
        resolve(res.result);
        return;
      }
      if (!res || res.state === 'FAILURE') {
        reject(new Error(res?.error || t('common.error')));
        return;
      }
      setTimeout(poll, 2000);
    } catch (error) {
      reject(error);
    }
  };
  poll();
});

const handlePreviewClose = () => {
  if (saving.value) return;
  showPreviewDialog.value = false;
};

const handleSave = async () => {
  saving.value = true;
  try {
    const response = await $SmartMeteringApiService.importReadings({
      reading_date: readingDate.value,
      preview: preview.value,
      replace: replace.value,
      scope: scope.value,
    });
    if (!response?.task_id) {
      throw new Error(t('common.error'));
    }
    const result = await waitForTask(response.task_id);
    toast.success(t('reading_block.smart_metering_loaded', {
      saved: result?.saved_readings ?? 0,
      not_saved: result?.not_saved_readings ?? 0,
    }));
    const documentId = result?.document_id ?? response.document_id;
    reset();
    emit('loaded', documentId);
  } catch (error) {
    console.error(error);
    toast.error(error?.data?.error || error?.message || t('common.error'));
  } finally {
    saving.value = false;
  }
};
</script>

<template>
  <div v-if="show && !showPreviewDialog">
    <div class="fixed inset-0 bg-black bg-opacity-50 h-[150vh] z-40" @click="handleClose" />

    <div class="fixed inset-0 z-50 flex items-center justify-center pointer-events-none p-4">
      <div class="bg-white rounded-lg shadow-xl max-w-md w-full pointer-events-auto" @click.stop>
        <div class="flex items-start justify-between gap-4 p-6 border-b border-gray-200">
          <div>
            <h3 class="text-xl font-bold text-slate-800 mb-1">{{ t('reading_block.smart_metering_load_title') }}</h3>
            <p class="text-slate-500 text-sm">{{ t('reading_block.smart_metering_load_help') }}</p>
          </div>
          <button type="button" class="text-gray-500 hover:text-gray-700" @click="handleClose">
            <Icon name="fa6-solid:xmark" class="text-xl" />
          </button>
        </div>

        <div class="p-6 flex flex-col gap-4">
          <AtomsInputDate
            v-model="readingDate"
            :label="t('billing_block.reading_date')"
            :disabled="busy"
          />

          <label class="flex items-center gap-2 text-sm text-slate-700 cursor-pointer">
            <input v-model="loadAll" type="checkbox" class="checkbox" :disabled="busy" />
            {{ t('reading_block.smart_metering_load_all') }}
          </label>

          <template v-if="!loadAll">
            <div>
              <p class="text-xs uppercase tracking-wide text-slate-500 mb-2">{{ t('reading_block.smart_metering_routes') }}</p>
              <v-select multiple :options="scopeOptions.routes" label="label" :reduce="option => option.id"
                class="w-full custom-select" v-model="routeIds" :close-on-select="false" :disabled="busy" />
            </div>
            <div>
              <p class="text-xs uppercase tracking-wide text-slate-500 mb-2">{{ t('reading_block.smart_metering_route_zones') }}</p>
              <v-select multiple :options="scopeOptions.route_zones" label="label" :reduce="option => option.id"
                class="w-full custom-select" v-model="routeZoneIds" :close-on-select="false" :disabled="busy" />
            </div>
            <div>
              <p class="text-xs uppercase tracking-wide text-slate-500 mb-2">{{ t('reading_block.smart_metering_batches') }}</p>
              <v-select multiple :options="scopeOptions.batches" label="label" :reduce="option => option.id"
                class="w-full custom-select" v-model="batchIds" :close-on-select="false" :disabled="busy" />
            </div>
          </template>
        </div>

        <div class="flex justify-end items-center gap-3 p-6 border-t border-gray-200">
          <button
            type="button"
            :disabled="busy"
            class="px-4 py-2 text-slate-600 font-semibold hover:bg-slate-100 rounded-lg transition-colors disabled:opacity-50"
            @click="handleClose"
          >
            {{ t('common.cancel') }}
          </button>
          <AtomsProcessColorBadge
            v-if="previewTaskId"
            class="!inline-flex items-center h-[42px] px-4 text-sm font-medium"
            :value="t('billing_block.smart_metering_loading_preview')"
            color="blue"
            :taskId="previewTaskId"
            @refresh="onPreviewTaskRefresh"
          />
          <button
            v-else
            type="button"
            class="button-primary flex items-center gap-2"
            :disabled="previewLoading || !hasScope"
            @click="startPreview"
          >
            <Icon
              :name="previewLoading ? 'fa6-solid:spinner' : 'fa6-solid:tower-broadcast'"
              :class="{ 'animate-spin': previewLoading }"
            />
            {{ t('reading_block.smart_metering_get_readings') }}
          </button>
        </div>
      </div>
    </div>
  </div>

  <SmartMeteringReadingsDialog
    :show="showPreviewDialog"
    :preview="preview"
    :loading="saving"
    @close="handlePreviewClose"
    @save="handleSave"
  />
</template>
