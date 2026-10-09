<script setup>
const { t } = useI18n();

const { $DocumentManagerApiService } = useNuxtApp();

const props = defineProps({
    isSubRegion: Boolean,
    documents: Array,
    loading: Boolean,
});

const emit = defineEmits(['change']);

const today_date_string = new Date().toISOString().slice(0, 10);
const loading = ref(false);
const downloading = ref(false);
const documentsData = ref([]);
const showInactiveDocuments = ref(false);


const getFileExtension = (documentName) => {
    if (!documentName?.includes('.')) return null;
    return documentName.split('.').pop().toLowerCase();
};

const availableExtensions = computed(() => {
    const extensionSet = new Set();
    for (const item of documentsData.value) {
        const extension = getFileExtension(item.file?.document_name);
        if (extension) extensionSet.add(extension);
    }
    return ['allext', ...[...extensionSet].sort()];
});

const selectedExtension = ref('allext');

const printDocument = async (item) => {
    try {
        const document_file = await $DocumentManagerApiService.getDetail(item.file.id)

        const file = await $DocumentManagerApiService.viewDocument(item.file.id);

        //when downloading, allow user to select download folder instead of default download folder
        const link = document.createElement('a');
        const file_url = URL.createObjectURL(file);
        link.href = file_url
        link.download = document_file.document_name;

        link.click();

        setTimeout(() => {
            window.URL.revokeObjectURL(file_url);
        }, 250);

    } catch (error) {
        console.error(error)
    }

}

const downloadDocuments = async () => {
    downloading.value = true;
    try {
        const file_ids = filteredDocumentData.value.map(item => item.file.id);
        const payload = {
            doc_ids: file_ids
        }
        const zippedDocs = await $DocumentManagerApiService.downloadDocuments(payload);
        const blob = new Blob([zippedDocs], { type: 'application/zip' });

        const url = window.URL.createObjectURL(blob);

        const a = document.createElement('a');
        a.href = url;
        a.download = `${t('GOT.documents').toLowerCase()}${today_date_string}.zip`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);
    } catch (error) {
        console.error(error)
    } finally {
        downloading.value = false;
    }
}

const filteredDocumentData = computed(() => {
    let localData = [...documentsData.value];
    localData.sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
    if (!showInactiveDocuments.value) {
        localData = localData.filter(item => item.file.is_active);
    }
    if (selectedExtension.value !== 'allext') {
        localData = localData.filter(
            item => getFileExtension(item.file?.document_name) === selectedExtension.value
        );
    }
    return localData;
});

const deleteDocument = async (item) => {
    if (!confirm(t("confirmation_text_block.confirm_deactivate"))) return
    try {
        let del_data = {
            doc_ids: [item.file.id],
        }
        await $DocumentManagerApiService.deleteItems(del_data);
        emit('change', item.id)
    } catch (error) {
        console.error('Error deleting document:', error);
    }
}
/* const deleteDocument = async (id) => {
    if(!confirm(t("Estàs segur que vols esborrar el document?"))) return
    try {
        await $VulnerabilityRequestApiService.deleteDocumentFile(id);
        emit('change')
    } catch (error) {
        console.error('Error deleting document:', error);
    }
} */

onMounted(() => {
    documentsData.value = props.documents;
    loading.value = props.loading
});

watch(() => props.documents, (newVal) => {
    documentsData.value = newVal;
});

watch(() => props.loading, (newVal) => {
    loading.value = newVal;
});

</script>
<template>
    <div v-if="loading" class="flex justify-center items-center">
        <Icon name="fa6-solid:spinner" class="animate-spin text-2xl text-slate-500" />
        <span class="ml-2">{{ $t('common.loading') }}...</span>
    </div>
    <div v-else @click.stop>
        <div class="flex flex-wrap items-center justify-between gap-3 p-2">
            <div class="flex flex-wrap items-center gap-2">
                <button type="button" class="button-secondary" :disabled="downloading" @click="downloadDocuments">
                    <Icon v-if="downloading" name="fa6-solid:spinner" class="animate-spin" />
                    <Icon v-else name="fa6-solid:download" />
                    {{ downloading ? `${t('common.loading')}...` : t('common.download') }}
                </button>
                <select v-model="selectedExtension" class="w-max-xs text-base border border-gray-300 rounded p-2">
                    <option v-for="extension in availableExtensions" :value="extension" :key="extension">
                        {{ extension === 'allext' ? t('common.all') : extension }}
                    </option>
                </select>
                <div>
                    <p class="text-xs font-medium uppercase tracking-wide text-slate-500">{{ $t('common.bulk_download')
                        }}</p>
                    <p class="text-sm text-slate-700">{{ $t('informative_block.info_bulk_download') }}</p>
                </div>
            </div>

            <label class="inline-flex items-center rounded-md bg-white px-2 py-1 shadow-sm">
                <input type="checkbox" v-model="showInactiveDocuments"
                    class="form-checkbox h-4 w-4 text-sky-600 rounded border-gray-300 focus:ring-sky-500" />
                <span class="ml-2 text-sm text-gray-700">{{ $t('common.show') }} {{ t('common.doc_inactive') }}</span>
            </label>
        </div>
        <div class="my-4 mx-2 rounded-md border border-gray-300 divide-y bg-white">
            <div class="group grid grid-cols-[1fr,2fr,50px,50px] divide-x text-sm leading-4 ">
                <span class="p-2 pl-3 text-slate-600"> {{ t('common.date') }} </span>
                <span class="p-2 pl-3 text-slate-600"> {{ t('common.doc') }} </span>
                <span class="col-span-2"></span>
            </div>
            <div v-for="item in filteredDocumentData"
                class="group grid grid-cols-[1fr,2fr,50px,50px] divide-x text-sm leading-4 transition-all duration-100">
                <div class="footering text-slate-500 p-2 w-full">
                    {{ formatDate(item.created_at) }}
                </div>
                <div class="footering text-slate-500 p-2 w-full">
                    {{ item.file.document_name }}
                </div>
                <div class="footering text-slate-500 p-2 w-full text-center items-center">
                    <abbr :title="`${t('common.download')} ${t('common.doc')}`"
                        class="text-slate-500 rounded-full border border-slate-500 cursor-pointer p-1 hover:bg-slate-50 hover:text-slate-700 hover:border-slate-700">
                        <button type="button" @click="printDocument(item)" class="w-4 h-4">
                            <Icon name="fa6-solid:download" />
                        </button>
                    </abbr>
                </div>
                <div class="footering text-slate-500 p-2 w-full text-center items-center">
                    <abbr :title="`${t('common.delete')} ${t('common.doc')}`"
                        class="text-slate-500 rounded-full border border-slate-500 cursor-pointer p-1 hover:bg-red-50 hover:text-red-700 hover:border-red-700">
                        <button type="button" @click="deleteDocument(item)" class="w-4 h-4">
                            <Icon name="fa6-solid:trash-can" />
                        </button>
                    </abbr>
                </div>
            </div>
            <div v-if="filteredDocumentData.length === 0" class="text-slate-500 p-2 w-full text-center">
                {{ t('common.no_data') }}
            </div>
        </div>
    </div>
</template>