<script setup>
// Càrrega de lectures de Smart Metering des d'«Introduir lectures».
// Genera un document de lectures (amb Excel) que després el lot selecciona
// com qualsevol altre fitxer de lectures.
import { ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import { format } from 'date-fns';
import { useToast } from 'vue-toastification';
import SmartMeteringReadingsDialog from '~/components/molecules/SmartMeteringReadingsDialog.vue';

const { t } = useI18n();
const toast = useToast();
const { $SmartMeteringApiService, $apiManager } = useNuxtApp();

defineProps({
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

// La confirmació de substituir només val per a la data en què s'ha demanat.
watch(readingDate, () => {
  replace.value = false;
});

const reset = () => {
  replace.value = false;
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
  previewLoading.value = true;
  try {
    const response = await $SmartMeteringApiService.previewReadings({
      reading_date: readingDate.value,
      replace: replace.value,
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

        <div class="p-6">
          <AtomsInputDate
            v-model="readingDate"
            :label="t('billing_block.reading_date')"
            :disabled="previewLoading || !!previewTaskId"
          />
        </div>

        <div class="flex justify-end items-center gap-3 p-6 border-t border-gray-200">
          <button
            type="button"
            :disabled="previewLoading || !!previewTaskId"
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
            :disabled="previewLoading"
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
