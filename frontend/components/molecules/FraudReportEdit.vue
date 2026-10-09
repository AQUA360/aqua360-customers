<script setup>
import H1Region from '../atoms/H1Region.vue';
import TableHeader from '../atoms/TableHeader.vue';
import { useToast } from 'vue-toastification';
import ContractDetail from './ContractDetail.vue';
import DocumentList from './DocumentList.vue';
import ImagesView from './ImagesView.vue';

const toast = useToast();
const { t } = useI18n();
const { $FraudApiService, $FraudReportApiService, $ConfigProjectApiService } = useNuxtApp();

const emit = defineEmits(['changed']);
const props = defineProps({
    id: {
        type: Number,
        default: null,
    },
    fraud_id: {
        type: Number,
        default: null,
    },
    canChange: {
        type: Boolean,
        default: true
    }
});

const loading = ref(true);
const loading_document = ref(true);
const loading_image = ref(true);
const saving = ref(false);
const attemptedSave = ref(false);

const fraud = ref(null)
const report = ref(null)

const report_date = ref(null)
const description = ref('')

const documents = ref([])
const images = ref([])

const getData = async () => {
    //loading.value = true;
    try {
        if (props.id) {
            let response = await $FraudReportApiService.getDetail(props.id);
            report.value = response;
            report_date.value = response.report_date;
            description.value = response.description;
            documents.value = response.documentation_files;
            images.value = response.image_files;
        } else if (report.value) {
            let response = await $FraudReportApiService.getDetail(report.value.id);
            report.value = response;
            report_date.value = response.report_date;
            description.value = response.description;
            documents.value = response.documentation_files;
            images.value = response.image_files;
        }
    } catch (error) {
        console.error(error);
    } finally {
        loading.value = false;
        loading_document.value = false;
        loading_image.value = false;
    }

}


const save = async (close = false) => {
    attemptedSave.value = true;
    if (!isValid()) return

    try {
        let save_data = {
            id: report.value ? report.value.id : null,
            fraud: props.fraud_id || null,
            description: description.value,
            report_date: report_date.value,
        }

        let response = await $FraudReportApiService.save(save_data)
        report.value = response
        if (response) {
            emit('changed', close)
        }

    } catch (error) {
        console.error(error)
    }
}

const saveDocument = async (file) => {
    if (report_date.value == null || report_date.value == '') toast.error(t("warning_block.warning_before_save_doc_date"))
    loading_document.value = true;
    await save(false)
    let save_data = {
        id: report.value.id,
        file: file,
    }
    let response = await $FraudReportApiService.saveDocument(save_data)
    if (response) {
        await getData()
        emit('changed', false)
    }
}

const saveImage = async (file) => {
    //check if file is a .pgn, .jpeg or other image file
    const allowedTypes = ['image/jpeg', 'image/png', 'image/jpg'];
    if (!file || !allowedTypes.includes(file.type)) {
        toast.warning(t('warning_block.warning_valid_img'));
        return;
    }
    
    if (report_date.value == null || report_date.value == '') toast.error(t("warning_block.warning_before_save_doc_date"))
    loading_image.value = true;
    await save(false)
    let save_data = {
        id: report.value.id,
        file: file,
    }
    let response = await $FraudReportApiService.saveImage(save_data)
    if (response) {
        getData()
        emit('changed', false)
    }
}

const isValid = () => {
    if (report_date.value == null || report_date.value == '') return false
    return true
}

onMounted(() => {
    getData()
})

watch(() => props.id, (newValue, oldValue) => {
    getData()
});

watch(() => props.fraud_id, (newValue, oldValue) => {
    getData()
});

</script>
<template>
    <div v-if="!loading" id="wrapper" class="region__content">
        <div class="mb-6">
            <H1Region>{{ props.id ? $t('common.report_detail') + ': ' + report.token : $t('billing_block.new_report') }}
            </H1Region>
        </div>


        <div v-if="!props.id" class="mb-6 w-[50%]">
            <AtomsInputDate v-model="report_date" :label="t('common.date')" class="mb-2"
                :invalid="attemptedSave && (report_date == null || report_date == '')" :required="true" />
        </div>
        <div class="mb-6">
            <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('common.description') }}</label>
            <textarea :disabled="!canChange" name="description" id="description" cols="30" rows="5" v-model="description"
                class="w-full border border-slate-300 rounded-md p-2 focus:outline-none focus:border-primary"></textarea>
        </div>
        <hr class="my-2">

        <details class="bg-white rounded-lg bg-sky-50 border border-slate-300 group overflow-hidden bg-sky-50">
            <summary class="flex items-center gap-5 p-4 cursor-pointer text-slate-500 font-medium">
                <Icon name="fa6-solid:angle-down"
                    class="text-gray-500 w-4 h-4 transform transition-transform duration-200 group-open:rotate-180" />
                {{ t('common.documentation') }}
            </summary>
            <div v-if="loading_document" class="flex justify-center items-center">
                <Icon name="fa6-solid:spinner" class="animate-spin text-2xl text-slate-500" />
                <span class="ml-2">{{ $t('common.loading') }}...</span>
            </div>
            <div v-else-if="!loading_document && documents.length > 0">
                <DocumentList :documents="documents" @change="getData" />
            </div>
            <div v-if="!canChange && documents.length == 0">
                <p class="text-slate-500 px-3">{{ $t('common.no_records') }}</p>
            </div>
            <AtomsInputFile v-if="canChange" @update="saveDocument" :name="'fraudDocumentFile'" :uploaded="null" :fullWidth="true"
                class="w-full" />
        </details>
        <hr class="my-2">

        <details class="bg-white rounded-lg bg-sky-50 border border-slate-300 group overflow-hidden bg-sky-50">
            <summary class="flex items-center gap-5 p-4 cursor-pointer text-slate-500 font-medium">
                <Icon name="fa6-solid:angle-down"
                    class="text-gray-500 w-4 h-4 transform transition-transform duration-200 group-open:rotate-180" />
                {{ t('common.imgs') }}
            </summary>
            <div v-if="loading_image" class="flex justify-center items-center">
                <Icon name="fa6-solid:spinner" class="animate-spin text-2xl text-slate-500" />
                <span class="ml-2">{{ $t('common.loading') }}...</span>
            </div>
            <div v-else-if="!loading_image && images.length > 0" class="my-4 px-4 py-1">
                <ImagesView :images="images" />
            </div>
            <div v-if="!canChange && images.length == 0">
                <p class="text-slate-500 px-3">{{ $t('common.no_imgs') }}</p>
            </div>
            <AtomsInputFile v-if="canChange" @update="saveImage" :name="'fraudImageFile'" :uploaded="null" :fullWidth="true"
                class="w-full" />
        </details>

        <hr class="my-2" />
        <div v-if="canChange" class="flex flex-row-reverse gap-3 mt-4">
            <button @click="save(true)" class="button-primary">
                <Icon name="fa6-solid:floppy-disk" />&nbsp; {{
                    $t('common.save') }}
            </button>
        </div>
    </div>
    <div v-else class="p-4">
        <div class="flex justify-center items-center">
            <Icon name="fa6-solid:spinner" class="animate-spin text-2xl text-slate-500" />
            <span class="ml-2">{{ $t('common.loading') }}...</span>
        </div>
    </div>
</template>