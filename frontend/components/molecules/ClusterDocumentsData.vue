<script setup>
import { ref, watch, onMounted, computed } from 'vue';
import { useToast } from 'vue-toastification';
import FieldDetail from '../atoms/FieldDetail.vue';

const props = defineProps({
    cluster: {
        type: Object,
        required: true
    }
})
const { t } = useI18n();
const toast = useToast();
const { $DocumentManagerApiService, $ClusterApiService, $ConfiglistApiService } = useNuxtApp();

const emit = defineEmits(['update-item']);

const loading_file = ref(false);
const cluster = ref(props.cluster);

const activeDocumentationFiles = computed(() => {
    return (cluster.value?.documentation_files || []).filter(d => d.is_active !== false);
});

watch(() => props.cluster, (newVal) => {
    if (newVal) {
        cluster.value = newVal;
        getDocTypes();
    }
}, { deep: true });

const doc_types = ref([]);
const selected_doc_type = ref('');
const doc_file = ref(null);
const loading_doc_types = ref(true);

const getDocTypes = async () => {
    try {
        const data = await $ConfiglistApiService.getData('service/cluster-documentation-type');
        doc_types.value = Array.isArray(data) ? data : (data.results || []);
    } catch (error) {
        console.error('Error getting doc types:', error);
        doc_types.value = [];
    } finally {
        loading_doc_types.value = false;
    }
}

const getMimeType = (filename) => {
    const ext = filename.split('.').pop().toLowerCase();
    const mimeTypes = {
        'pdf': 'application/pdf',
        'png': 'image/png',
        'jpg': 'image/jpeg',
        'jpeg': 'image/jpeg',
        'gif': 'image/gif',
        'csv': 'text/csv',
        'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        'xls': 'application/vnd.ms-excel',
        'doc': 'application/msword',
        'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'txt': 'text/plain',
        'zip': 'application/zip',
        'rar': 'application/x-rar-compressed',
    };
    return mimeTypes[ext] || 'application/octet-stream';
}

const printDoc = async (document_id, document_name) => {
    try {
        const file = await $DocumentManagerApiService.viewDocument(document_id);
        const mimeType = getMimeType(document_name || '');
        const blob = new Blob([file], { type: mimeType });
        const downloadLink = document.createElement('a');
        const downloadUrl = URL.createObjectURL(blob);
        downloadLink.href = downloadUrl;
        downloadLink.download = document_name || `${props.cluster.id}`;
        downloadLink.click();
        setTimeout(() => URL.revokeObjectURL(downloadUrl), 100);
    } catch (error) {
        console.log(error);
    }
}

const deleteDocument = async (doc) => {
    if (!confirm(`${t('confirmation_text_block.confirm_delete_doc')}`)) return;
    try {
        await $DocumentManagerApiService.deleteItems({ doc_ids: [doc.file?.id || doc.id] });
        cluster.value.documentation_files = cluster.value.documentation_files.filter(d => d.id !== doc.id);
        emit('update-item', cluster.value);
        toast.success(t('common.deleted_successfully'));
    } catch (error) {
        toast.error(t('common.delete_failed'));
        console.error('Error deleting document:', error);
    }
}

const inputOther = async () => {
    loading_file.value = true;
    try {
        const save_data = {
            id: cluster.value.id,
            file: doc_file.value,
            cluster_type: selected_doc_type.value,
        };
        const response = await $ClusterApiService.saveFile(save_data);
        if (response) {
            cluster.value = response;
            emit('update-item', response);
            toast.success(t('common.doc_correct_upload'));
        }
    } catch (error) {
        toast.error(t('common.error_save'));
        console.error('Error saving document:', error);
    } finally {
        loading_file.value = false;
        selected_doc_type.value = '';
        doc_file.value = null;
    }
}

const handleDocumentUpdate = (file) => {
    doc_file.value = file;
}

onMounted(async () => {
    await getDocTypes();
});
</script>

<template>
    <div>
        <FieldDetail :label="$t('contract_block.validated_documents')"></FieldDetail>
        <hr class="my-2" />
        <div class="bg-gradient-to-br from-slate-50 to-sky-50 rounded-lg p-4 mb-3 border border-slate-200 shadow-sm">
            <div class="flex flex-col sm:flex-row gap-3 items-stretch sm:items-end">
                <div class="flex-1 min-w-0">
                    <label for="cluster_doc_type" class="block text-xs font-medium text-slate-600 mb-1.5">
                        {{ $t('common.doc_type') }}
                    </label>
                    <select v-model="selected_doc_type" id="cluster_doc_type"
                        class="w-full px-3 py-2.5 text-sm border border-slate-300 rounded-lg bg-white shadow-sm transition-all">
                        <option value="" disabled hidden>{{ $t('common.select') }}...</option>
                        <option v-for="docType in doc_types" :value="docType.id" :key="docType.id">
                            {{ docType.list_name || docType.name }}
                        </option>
                    </select>
                </div>

                <div class="flex-1 min-w-0">
                    <AtomsInputFile @update="handleDocumentUpdate" :name="'clusterDocFile'" :uploaded="null"
                        :fullWidth="true" class="w-full" />
                </div>

                <button v-if="!loading_file" @click="inputOther" :disabled="!selected_doc_type || !doc_file"
                    class="button-secondary flex items-center gap-x-2">
                    <Icon name="fa-solid:plus" class="text-white my-0.5" />
                    <span class="my-0.5">{{ $t('common.add') }}</span>
                </button>
                <button v-else disabled class="button-default flex items-center gap-x-2">
                    <Icon name="fa-solid:spinner" class="animate-spin my-0.5" />
                    <span class="my-0.5">{{ t('common.uploading') }}...</span>
                </button>
            </div>
        </div>

        <div v-if="activeDocumentationFiles && activeDocumentationFiles.length > 0">
            <div v-for="d in activeDocumentationFiles" :key="d.id"
                class="grid grid-cols-[1fr,25px] gap-x-2 items-center">
                <button @click="printDoc(d.file?.id || d.id, d.file?.document_name || d.document_name)"
                    class="button-default w-full flex gap-3 items-center mb-2">
                    <Icon name="fa6-regular:file" class="text-slate-500" />
                    <span class="font-semibold">
                        {{ d.type ? (d.type.list_name || d.type.name) : (d.cluster_type?.list_name || d.cluster_type?.name) }}
                    </span>
                    <span class="px-4 text-slate-500">
                        {{ d.file?.document_name || d.document_name }}
                    </span>
                </button>
                <button @click="deleteDocument(d)"
                    class="rounded-lg text-red-500 bg-white hover:text-red-700 flex items-center mb-2">
                    <Icon name="fa6-solid:trash" class="m-auto" />
                </button>
            </div>
        </div>
        <div v-else>
            <span class="footering text-slate-500 p-2">
                {{ t('common.no_data_found') }}
            </span>
        </div>
    </div>
</template>
