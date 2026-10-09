<script setup>
import { ref, watch, onMounted, computed } from 'vue';
import { useToast } from 'vue-toastification';
import FieldDetail from '../atoms/FieldDetail.vue';
import { useConfigStore } from '~/stores/useConfigStore';
import { storeToRefs } from 'pinia';
import { formatDate } from '~/utils/date';

const props = defineProps({
    contract: {
        type: Object,
        required: true
    },
    is_request: {
        type: Boolean,
        default: false
    }
})
const { t } = useI18n();
const toast = useToast();
const { $DocumentManagerApiService, $ContractRequestApiService, $ContractApiService, $ContractRequestDocumentationApiService, $ConfiglistApiService, $ContractRequestTypeApiService } = useNuxtApp();

const configStore = useConfigStore();
const { documentSignEnabled } = storeToRefs(configStore);
configStore.fetchDocumentSignEnabled();

const emit = defineEmits(['update-item', 'refresh']);

const loading_file = ref(false);
const loading_contract = ref(false);
const contract = ref(props.contract);

const activeDocumentationFiles = computed(() => {
    return (contract.value?.documentation_files || [])
        .filter(d => d.is_active !== false)
        .slice()
        .sort((a, b) => {
            const dateA = new Date(a.created_at || a.file?.created_at || a.file?.date || 0).getTime();
            const dateB = new Date(b.created_at || b.file?.created_at || b.file?.date || 0).getTime();
            return dateB - dateA;
        });
});

const activeContractFile = computed(() => {
    return contract.value?.contract_file && contract.value.contract_file.is_active !== false
        ? contract.value.contract_file
        : null;
});

/**
 * Id del contracte real associat, per firma OTP (DocumentSign.contract).
 * En una sol·licitud (is_request) només existeix quan ja té un contracte vinculat
 * (p. ex. baixa/canvi de titular). Si no n'hi ha, s'usa `signContractRequestId` en el
 * seu lloc (backend accepta `contract_request_id` mentre la sol·licitud encara no té
 * contracte). Un cop finalitzada la sol·licitud i creat el contracte definitiu, la
 * migració del DocumentSign de contract_request a contract NO és automàtica.
 */
const signContractId = computed(() => {
    if (!props.is_request) return contract.value?.id || null;
    return contract.value?.contract?.id || contract.value?.contract || null;
});

/** Id de la sol·licitud, usat com a fallback mentre encara no hi ha contracte. */
const signContractRequestId = computed(() => {
    if (!props.is_request || signContractId.value) return null;
    return contract.value?.id || null;
});

/** Nom/email/telèfon per preomplir el formulari de firma OTP, a partir de les dades ja disponibles al contracte/sol·licitud. */
const signOtpDefaultName = computed(() => {
    const holder = contract.value?.holder;
    if (!holder) return '';
    return holder.full_name || [holder.name, holder.surname].filter(Boolean).join(' ') || '';
});

const signOtpDefaultEmail = computed(() => {
    const digitalContact = contract.value?.person_contact_email;
    if (digitalContact?.email) return digitalContact.email;
    const contactWithEmail = (contract.value?.contacts || []).find(c => c.email);
    return contactWithEmail?.email || contract.value?.holder?.email || '';
});

const signOtpDefaultPhone = computed(() => {
    const contactWithPhone = (contract.value?.contacts || []).find(c => c.phone);
    return contactWithPhone?.phone || contract.value?.holder?.phone || '';
});

watch(() => props.contract, (newVal) => {
    if (newVal) {
        contract.value = newVal;
        getDocTypes();
    }
}, { deep: true });

const doc_types = ref([]);
const selected_doc_type = ref(null);
const doc_file = ref(null);
const doc_text = ref('');
const loading_doc_types = ref(true);

const getDocTypes = async () => {
    try {
        const data = await $ConfiglistApiService.getAll('contract/contract-documentation-type');
        doc_types.value = data.results;
    } catch (error) {
        console.error('Error getting doc types:', error);
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
        downloadLink.download = document_name || `${props.contract.token}`;
        downloadLink.click();

        // Clean up the object URL after download
        setTimeout(() => {
            URL.revokeObjectURL(downloadUrl);
        }, 100);

        /* const newWindow = window.open(downloadUrl, '_blank');

        if (newWindow) {
            setTimeout(() => {
                window.URL.revokeObjectURL(downloadUrl);
            }, 250);
        } */

    } catch (error) {
        console.log(error)
    }
}

const deleteDocument = async (document) => {
    if (!confirm(`${t('confirmation_text_block.confirm_delete_doc')}`)) return;
    try {
        await $ContractRequestDocumentationApiService.doDelete(document);
        contract.value.documentation_files = contract.value.documentation_files.filter(d => d.id !== document.id);
        emit('update-item', contract.value);
        toast.success(t('common.deleted_successfully'));
    } catch (error) {
        toast.error(t('common.delete_failed'));
        console.error('Error deleting document:', error);
    }
}
const deleteContractDocument = async (document) => {
    try {
    if (confirm(t("confirmation_text_block.confirm_exit"))) {
      let del_data = {
        doc_ids: [document.id]
      }
      await $DocumentManagerApiService.deleteItems(del_data);
      contract.value.contract_file = null;
      emit('update-item', contract.value);
      toast.success(t('common.deleted_successfully'));
    }
  }
  catch (error) {
    toast.error(t('common.delete_failed'));
    console.error('Error deleting contract document:', error);
  }
}

const inputContract = async (file) => {
    await inputDocument(file.target.files[0], true);
}

const inputOther = async () => {
    if (!doc_file.value && !doc_text.value) {
        toast.error(t('common.file_or_text_required'));
        return;
    }
    await inputDocument(doc_file.value || null, false);
}

const inputDocument = async (file, is_contract = false) => {
    loading_file.value = !is_contract;
    loading_contract.value = is_contract;
    try {
        let response = null;
        let save_data = {
            id: contract.value.id,
            file: file,
            is_contract: is_contract,
            contract_type: selected_doc_type.value,
            text: doc_text.value || null,
        };

        if (props.is_request) {
            response = await $ContractRequestApiService.saveFile(save_data);
        } else {
            response = await $ContractApiService.saveFile(save_data);
        }
        
        if (response) {
            if (response.documentation_files !== undefined) {
                contract.value = response;
                emit('update-item', response);
            } else {
                emit('refresh');
            }
            toast.success(t("common.doc_correct_upload"));
        }
        // const response = await $ContractApiService.saveFile(save_data);
    } catch (error) {
        toast.error(t("common.error_save"));
        console.error('Error saving document:', error);
    } finally {
        loading_file.value = false;
        loading_contract.value = false;
        selected_doc_type.value = null;
        doc_file.value = null;
        doc_text.value = '';
    }
};

const handleDocumentUpdate = async (file) => {
    doc_file.value = file;
}

onMounted(async () => {
    await getDocTypes();
});

</script>

<template>
    <div>
        <MoleculesDocumentSignStatus v-if="documentSignEnabled && (signContractId || signContractRequestId)" :contractId="signContractId"
            :contractRequestId="signContractRequestId" :contractFileId="activeContractFile?.id"
            :defaultName="signOtpDefaultName" :defaultEmail="signOtpDefaultEmail" :defaultPhone="signOtpDefaultPhone" />

        <div v-if="activeContractFile" class="mb-10">
            <button
                class="px-4 py-2 text-gray-700 border border-gray-300 rounded shadow-sm hover:bg-gray-100 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-sky-500 transition-all duration-200 w-full flex gap-3 items-center mb-2 bg-green-50"
                @click="printDoc(activeContractFile.id, activeContractFile.document_name)">
                <Icon name="fa6-regular:file" class="text-slate-500" />
                <span class="font-semibold">
                    {{ t('contract_block.signed_contract') }}
                </span>
                <span v-if="activeContractFile.created_at || activeContractFile.date || contract?.signature_date || contract?.created_at"
                    class="text-xs text-slate-500 bg-white px-2 py-0.5 rounded border border-slate-200 shrink-0 flex items-center gap-1">
                    <Icon name="fa6-regular:calendar-days" class="text-slate-400 text-[11px]" />
                    {{ formatDate(activeContractFile.created_at || activeContractFile.date || contract?.signature_date || contract?.created_at) }}
                </span>
                <span class="px-4 text-slate-500 ml-auto flex items-center gap-2">
                    {{ activeContractFile.document_name }}
                    <button @click.stop="deleteContractDocument(activeContractFile)"
                        class="rounded-lg text-red-500 bg-white m-auto p-auto hover:text-red-700 flex items-center">
                        <Icon name="fa6-solid:trash" class="m-auto" />
                    </button>
                </span>
            </button>
        </div>

        <div v-else-if="!is_request" class="mb-10 flex justify-between">
            <!-- <span class="footering text-slate-500 p-2">
                {{ t('contract_block.no_signed_contract') }}
            </span> -->
            <!-- <fieldset class="mb-3 border px-3 py-2 bg-sky-50 w-full rounded gap-3">
                <label class="inline-block" :class="'text-slate-400'">
                    {{ t('common.add') }} {{ t('common.doc') }}
                </label>
                <span class="flex gap-3 pl-1 pt-1">
                    <AtomsInputFile @update="handleDocumentUpdate"
                        :name="'contractFile'" :uploaded="null" :fullWidth="true"
                        class="w-full" />
                </span>
            </fieldset> -->
            <span class="footering text-slate-400 py-2">
                {{ t('contract_block.no_signed_contract') }}
            </span>
            <div>
                <input type="file" @change="inputContract" ref="file" style="display: none" />
                <button v-if="!activeContractFile && !loading_contract" @click="$refs.file.click()"
                    class="button-default-xs">
                    <Icon name="fa-solid:plus" class="text-slate-500 mr-1" />
                    {{ $t('common.add') }}
                </button>
                <button v-else-if="loading_contract" class="button-default" :disabled="true">
                    <Icon name="fa-solid:spinner" class="text-slate-500 mr-1 animate-spin" />
                    {{ t('common.uploading') }}...
                </button>
            </div>
        </div>

        <div class="flex items-center justify-between gap-x-2">
            <FieldDetail :label="$t('common.documentation')"></FieldDetail>

            <!-- <div>
                <input type="file" @change="inputOther" ref="fileOther" style="display: none" />
                <button v-if="!loading_file" @click="$refs.fileOther.click()" class="button-default-xs">
                    <Icon name="fa-solid:plus" class="text-slate-500 mr-1" />
                    {{ $t('common.add') }}
                </button>
                <button v-else-if="loading_file" class="button-default" :disabled="true">
                    <Icon name="fa-solid:spinner" class="text-slate-500 mr-1 animate-spin" />
                    {{ t('common.uploading') }}...
                </button>
            </div> -->
        </div>
        <hr class="my-2" />
        <div class="bg-gradient-to-br from-slate-50 to-sky-50 rounded-lg p-4 mb-3 border border-slate-200 shadow-sm">
            <div class="flex flex-col sm:flex-row gap-3 items-stretch sm:items-end">
                <div class="flex-1 min-w-0">
                    <label for="doc_type" class="block text-xs font-medium text-slate-600 mb-1.5">
                        {{ $t('common.doc_type') }} <span class="text-red-500">*</span>
                    </label>
                    <select v-model="selected_doc_type" id="doc_type"
                        class="w-full px-3 py-2.5 text-sm border border-slate-300 rounded-lg bg-white shadow-sm transition-all">
                        <option value="">{{ $t('common.select') }}...</option>
                        <option v-for="docType in doc_types" :value="docType.id" :key="docType.id">
                            {{ docType.list_name || docType.name }}
                        </option>
                    </select>
                </div>

                <div class="flex-1 min-w-0">
                    <label class="block text-xs font-medium text-slate-600 mb-1.5">
                        {{ $t('common.text') }}
                        <span class="text-slate-400 font-normal"></span>
                    </label>
                    <input v-model="doc_text" type="text"
                        class="w-full px-3 py-2.5 text-sm border border-slate-300 rounded-lg bg-white shadow-sm transition-all"
                        :placeholder="$t('common.optional')" />
                </div>

                <div class="flex-1 min-w-0">
                    <label class="block text-xs font-medium text-slate-600 mb-1.5">
                        {{ $t('common.file') }}
                        <span class="text-slate-400 font-normal"></span>
                    </label>
                    <AtomsInputFile @update="handleDocumentUpdate" :name="'docFile'" :uploaded="null" :fullWidth="true"
                        class="w-full" />
                </div>

                <button v-if="!loading_file" @click="inputOther" :disabled="!selected_doc_type || (!doc_file && !doc_text)"
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
            <div v-for="d in activeDocumentationFiles" class="flex items-start grid grid-cols-[1fr,25px] gap-x-2">
                <div class="button-default w-full flex flex-col gap-1 items-start mb-2">
                    <div class="flex gap-3 items-center w-full">
                        <Icon name="fa6-regular:file" class="text-slate-500 shrink-0" />
                        <span class="font-semibold truncate min-w-0">
                            {{ d.type ? (d.type.list_name || d.type.name) : (d.contract_type?.list_name || d.contract_type?.name) }}
                        </span>
                        <span v-if="d.created_at || d.file?.created_at || d.file?.date"
                            class="text-xs text-slate-500 bg-slate-100 px-2 py-0.5 rounded border border-slate-200 shrink-0 flex items-center gap-1"
                            :title="t('common.date') || 'Data'">
                            <Icon name="fa6-regular:calendar-days" class="text-slate-400 text-[11px]" />
                            {{ formatDate(d.created_at || d.file?.created_at || d.file?.date) }}
                        </span>
                        <button v-if="d.file" @click="printDoc(d.file.id, d.file.document_name)"
                            class="ml-auto text-sky-600 hover:text-sky-800 text-xs flex items-center gap-1 shrink-0">
                            <Icon name="fa6-solid:download" class="text-[10px]" />
                            {{ d.file.document_name }}
                        </button>
                    </div>
                    <div v-if="d.text" class="pl-6 text-slate-500 italic text-sm">
                        {{ d.text }}
                    </div>
                </div>
                <button @click="deleteDocument(d)"
                    class="rounded-lg text-red-500 bg-white m-auto p-auto hover:text-red-700 flex items-center mt-3">
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