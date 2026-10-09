<script setup>
import { ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import { useToast } from 'vue-toastification';

const { t } = useI18n();
const toast = useToast();
const { $SepaRemittanceApiService } = useNuxtApp();

const props = defineProps({
  show: {
    type: Boolean,
    default: false
  }
});

const emit = defineEmits(['close']);

const fileInputRef = ref(null);
const selectedFile = ref(null);
const validating = ref(false);
const result = ref(null);
const resultText = ref('');
const showJson = ref(false);

const isXmlFile = (file) => {
  if (!file) return false;
  const name = file.name?.toLowerCase() || '';
  return name.endsWith('.xml') || file.type === 'text/xml' || file.type === 'application/xml';
};

const resetState = () => {
  selectedFile.value = null;
  validating.value = false;
  result.value = null;
  resultText.value = '';
  showJson.value = false;
  if (fileInputRef.value) {
    fileInputRef.value.value = '';
  }
};

watch(() => props.show, (isOpen) => {
  if (!isOpen) resetState();
});

const handleClose = () => {
  if (validating.value) return;
  emit('close');
};

const handleFileChange = async (event) => {
  const file = event.target.files?.[0] ?? null;
  result.value = null;
  resultText.value = '';
  showJson.value = false;

  if (!file) {
    selectedFile.value = null;
    return;
  }

  if (!isXmlFile(file)) {
    selectedFile.value = null;
    if (fileInputRef.value) fileInputRef.value.value = '';
    toast.warning(t('billing_block.sepa_xml_only'));
    return;
  }

  selectedFile.value = file;
  validating.value = true;
  try {
    const response = await $SepaRemittanceApiService.validateFile(file);
    result.value = response;
    resultText.value = JSON.stringify(response, null, 2);
  } catch (err) {
    console.error(err);
    toast.error(t('common.error'));
  } finally {
    validating.value = false;
  }
};
</script>

<template>
  <div v-if="show">
    <div class="fixed inset-0 bg-black bg-opacity-50 h-[150vh] z-40 flex items-center justify-center" @click="handleClose">
    </div>

    <div class="fixed inset-0 z-50 flex items-center justify-center overflow-y-auto pointer-events-none">
      <div class="bg-white rounded-lg shadow-xl p-6 max-w-2xl w-full mx-4 my-auto relative pointer-events-auto">
        <button @click="handleClose" class="absolute top-4 right-4 text-gray-500 hover:text-gray-700" :disabled="validating">
          <Icon name="fa6-solid:xmark" class="text-xl" />
        </button>

        <div class="mb-6">
          <h3 class="text-xl font-bold text-slate-800 mb-2 flex items-center gap-2">
            <Icon name="fa6-solid:file-circle-check" class="text-slate-500" />
            {{ t('billing_block.validate_file') }}
          </h3>
        </div>

        <div class="mb-6">
          <label class="block text-sm font-semibold text-slate-500 uppercase tracking-wide mb-2" for="sepa-validate-file">
            {{ t('common.file') }}
          </label>
          <input
            id="sepa-validate-file"
            ref="fileInputRef"
            type="file"
            accept=".xml,text/xml,application/xml"
            :disabled="validating"
            class="block w-full text-sm text-slate-600 file:mr-3 file:py-1.5 file:px-3 file:rounded file:border-0 file:bg-slate-100 file:text-slate-700 hover:file:bg-slate-200 disabled:opacity-50"
            @change="handleFileChange"
          />
          <p v-if="selectedFile" class="mt-1 text-xs text-slate-500">{{ selectedFile.name }}</p>
          <p class="mt-2 text-xs text-slate-500">{{ t('billing_block.sepa_xml_only') }}</p>
        </div>

        <div v-if="validating" class="flex items-center gap-2 text-slate-500 mb-6">
          <Icon name="fa6-solid:spinner" class="animate-spin" />
          {{ t('common.loading') }}...
        </div>

        <div v-if="result" class="mb-6">
          <div
            class="mb-3 rounded-lg px-3 py-2 text-sm font-semibold flex items-center gap-2"
            :class="result.valid ? 'bg-emerald-50 text-emerald-800 border border-emerald-200' : 'bg-red-50 text-red-800 border border-red-200'"
          >
            <Icon :name="result.valid ? 'fa6-solid:circle-check' : 'fa6-solid:circle-xmark'" />
            {{ result.valid ? t('billing_block.sepa_file_valid') : t('billing_block.sepa_file_invalid') }}
          </div>

          <p v-if="result.error" class="mb-3 text-sm text-red-700">{{ result.error }}</p>

          <ul v-if="result.errors?.length" class="mb-3 space-y-1 text-sm text-red-800 bg-red-50 rounded px-3 py-2">
            <li v-for="(err, idx) in result.errors" :key="idx">
              <span v-if="err.line != null" class="font-medium">{{ t('common.line') }} {{ err.line }}</span>
              <span v-if="err.column != null">, {{ t('editor_block.column') }} {{ err.column }}</span>
              <span v-if="err.line != null || err.column != null">: </span>
              {{ err.message || err }}
            </li>
          </ul>

          <div>
            <button type="button"
              class="flex items-center gap-2 text-sm font-semibold text-slate-700 mb-2 hover:text-slate-900"
              @click="showJson = !showJson">
              <Icon :name="showJson ? 'fa6-solid:chevron-down' : 'fa6-solid:chevron-right'" class="text-xs" />
              {{ t('common.details') }}
            </button>
            <pre v-if="showJson"
              class="whitespace-pre-wrap break-words text-xs text-slate-700 bg-slate-50 border border-slate-200 rounded-lg p-3 max-h-64 overflow-y-auto">{{ resultText }}</pre>
          </div>
        </div>

        <div class="flex justify-end">
          <button
            @click="handleClose"
            :disabled="validating"
            class="px-4 py-2 text-slate-600 font-semibold hover:bg-slate-100 rounded-lg transition-colors disabled:opacity-50"
          >
            {{ t('common.close') }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
