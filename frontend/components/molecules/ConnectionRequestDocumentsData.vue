<script setup>
import { ref, computed, watch, onMounted } from 'vue';
import { useToast } from 'vue-toastification';

const props = defineProps({
  request: {
    type: Object,
    required: true
  },
  readonly: {
    type: Boolean,
    default: false
  }
});

const emit = defineEmits(['update-item']);

const { t } = useI18n();
const toast = useToast();
const { $DocumentManagerApiService, $ConnectionRequestApiService, $ConfiglistApiService } = useNuxtApp();

const files = ref(props.request?.documentation_files || []);
const docTypes = ref([]);
const selectedDocType = ref('');
const docFile = ref(null);
const uploading = ref(false);
// Es fa servir per reiniciar l'input de fitxer després de pujar-ne un.
const inputKey = ref(0);

watch(() => props.request?.documentation_files, (newVal) => {
  files.value = newVal || [];
});

// Si no hi ha cap tipus configurat (o no es poden llegir), es permet pujar sense tipus.
const canUpload = computed(() => docFile.value && (selectedDocType.value || docTypes.value.length === 0));

const getDocTypes = async () => {
  try {
    const data = await $ConfiglistApiService.getData('service/connection-documentation-type');
    docTypes.value = (Array.isArray(data) ? data : (data.results || [])).filter(d => d.is_active !== false);
  } catch (error) {
    console.error('Error getting doc types:', error);
    docTypes.value = [];
  }
};

const downloadDoc = async (doc) => {
  try {
    const file = await $DocumentManagerApiService.viewDocument(doc.file.id);
    const blob = new Blob([file]);
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = doc.file.document_name || `${props.request.token}`;
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 100);
  } catch (error) {
    console.error(error);
  }
};

const deleteDoc = async (doc) => {
  if (!confirm(t('confirmation_text_block.confirm_delete_doc'))) return;
  try {
    await $DocumentManagerApiService.deleteItems({ doc_ids: [doc.file.id] });
    files.value = files.value.filter(d => d.id !== doc.id);
    toast.success(t('common.deleted_successfully'));
  } catch (error) {
    toast.error(t('common.delete_failed'));
    console.error('Error deleting document:', error);
  }
};

const uploadDoc = async () => {
  uploading.value = true;
  try {
    const response = await $ConnectionRequestApiService.saveFile({
      id: props.request.id,
      file: docFile.value,
      doc_type: selectedDocType.value,
    });
    files.value = response.documentation_files || [];
    emit('update-item', response);
    toast.success(t('common.doc_correct_upload'));
  } catch (error) {
    toast.error(t('common.error_save'));
    console.error('Error saving document:', error);
  } finally {
    uploading.value = false;
    selectedDocType.value = '';
    docFile.value = null;
    inputKey.value++;
  }
};

onMounted(() => {
  if (!props.readonly) getDocTypes();
});
</script>

<template>
  <div>
    <div v-if="!readonly" class="bg-gradient-to-br from-slate-50 to-sky-50 rounded-lg p-4 mb-3 border border-slate-200 shadow-sm max-w-3xl">
      <div class="flex flex-col sm:flex-row gap-3 items-stretch sm:items-end">
        <div v-if="docTypes.length" class="flex-1 min-w-0">
          <label for="connection_request_doc_type" class="block text-xs font-medium text-slate-600 mb-1.5">
            {{ $t('common.doc_type') }}
          </label>
          <select v-model="selectedDocType" id="connection_request_doc_type"
            class="w-full px-3 py-2.5 text-sm border border-slate-300 rounded-lg bg-white shadow-sm">
            <option value="" disabled hidden>{{ $t('common.select') }}...</option>
            <option v-for="docType in docTypes" :value="docType.id" :key="docType.id">
              {{ docType.name }}
            </option>
          </select>
        </div>
        <div class="flex-1 min-w-0">
          <AtomsInputFile :key="inputKey" @update="docFile = $event" :name="'connectionRequestDocFile'" :uploaded="null"
            :fullWidth="true" class="w-full" />
        </div>
        <button v-if="!uploading" @click="uploadDoc" :disabled="!canUpload"
          class="button-secondary flex items-center gap-x-2">
          <Icon name="fa-solid:plus" class="text-white my-0.5" />
          <span class="my-0.5">{{ $t('common.add') }}</span>
        </button>
        <button v-else disabled class="button-default flex items-center gap-x-2">
          <Icon name="fa-solid:spinner" class="animate-spin my-0.5" />
          <span class="my-0.5">{{ $t('common.uploading') }}...</span>
        </button>
      </div>
    </div>

    <div v-if="files.length" class="max-w-3xl">
      <div v-for="d in files" :key="d.id" class="grid grid-cols-[1fr,25px] items-center gap-x-2">
        <button @click="downloadDoc(d)" class="button-default w-full flex gap-3 items-center mb-2">
          <Icon name="fa6-regular:file" class="text-slate-500" />
          <span v-if="d.type" class="font-semibold">{{ d.type.name }}</span>
          <span class="px-4 text-slate-500">{{ d.file?.document_name }}</span>
        </button>
        <button v-if="!readonly" @click="deleteDoc(d)" class="text-red-500 hover:text-red-700 flex items-center mb-2">
          <Icon name="fa6-solid:trash" class="m-auto" />
        </button>
      </div>
    </div>
    <p v-else class="text-slate-500 text-sm">{{ $t('common.no_data_found') }}</p>
  </div>
</template>
