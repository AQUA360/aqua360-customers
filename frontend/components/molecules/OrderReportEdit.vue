<script setup>
import H1Region from '../atoms/H1Region.vue';
import FieldDetail from '../atoms/FieldDetail.vue';
import InputDate from '../atoms/InputDate.vue';
import InputTime from '../atoms/InputTime.vue';
import { useToast } from 'vue-toastification';
import DocumentList from './DocumentList.vue';

const toast = useToast();
const { t } = useI18n();
const { $OperatorApiService, $OrderApiService, $ConfigProjectApiService, $gotApi, $DocumentManagerApiService } = useNuxtApp();

const emit = defineEmits(['changed']);
const props = defineProps({
    id: {
        type: Number,
        default: null,
    },
    order_id: {
        type: Number,
        default: null,
    }
});

const loading = ref(true);
const loading_document = ref(true);
const loading_operators = ref(true);
const saving = ref(false);
const attemptedSave = ref(false);

const order = ref(null)
const report = ref(null)
const form = ref(null)

const start_at = ref(null)
const end_at = ref(null)
const report_date = ref(null)
const time_dedicated = ref(null)
const observation = ref('')

const selected_operator = ref(null)
const operators = ref([])

const documents = ref([])
const showAllDocuments = ref(false)
const formData = ref([])

const getData = async () => {
    //loading.value = true;
    try {
        if (props.id) {
            let response = await $OrderApiService.getReportDetail(props.id);
            report.value = response;
            report_date.value = response.report_date;
            time_dedicated.value = response.time_dedicated;
            start_at.value = extractTime(response.start_at);
            end_at.value = extractTime(response.end_at);
            observation.value = response.observation;
            if (showAllDocuments.value) {
                documents.value = response.documents;
            } else {
                documents.value = response.documents.filter(document => document.file.is_active == true);
            }
            selected_operator.value = { 
                code: typeof response.operator === 'object' && response.operator !== null ? response.operator.id : response.operator, 
                label: response.operator_full_name 
            };
            
            // Processar el formulari i les respostes
            processFormData(response);
            
        } else if (report.value) {
            report_date.value = report.value.report_date;
            time_dedicated.value = report.value.time_dedicated;
            observation.value = report.value.observation;
            documents.value = report.value.documents;
            start_at.value = extractTime(report.value.start_at);
            end_at.value = extractTime(report.value.end_at);
            selected_operator.value = { 
                code: typeof report.value.operator === 'object' && report.value.operator !== null ? report.value.operator.id : report.value.operator, 
                label: report.value.operator_full_name 
            };
            
            // Processar el formulari i les respostes
            processFormData(report.value);
        }
    } catch (error) {
        console.error(error);
    } finally {
        loading.value = false;
        loading_document.value = false;
    }

}

const extractTime = (val) => {
    if (!val) return null;
    // If it's a full ISO string like "2024-05-06T14:00:00Z"
    if (val.includes('T')) {
        return val.split('T')[1].substring(0, 5);
    }
    // If it's already a time string like "14:00:00"
    if (val.includes(':')) {
        return val.substring(0, 5);
    }
    return val;
}

const processFormData = (response) => {
    formData.value = [];

    const formStructure = response.order_form?.structure || [];
    const formSubmissions = response.form_submission?.filled_form || [];
    const structureByToken = new Map(formStructure.map(field => [field.token, field]));

    // The structure sets the field order when the CRM has one; otherwise follow the submission.
    const tokens = formStructure.length
        ? formStructure.map(field => field.token)
        : formSubmissions.map(sub => sub.token);

    // Answers whose token is missing from the structure must still be shown.
    formSubmissions.forEach(sub => {
        if (!tokens.includes(sub.token)) tokens.push(sub.token);
    });

    tokens.forEach(token => {
        const field = structureByToken.get(token) || {};
        const submission = formSubmissions.find(sub => sub.token === token) || {};

        const fieldData = {
            token: token,
            name: submission.name || field.name || token,
            type: submission.type || field.type || 'text',
            required: field.required ?? submission.required ?? false,
            response: submission.response ?? null,
            response_url: submission.response_url ?? null
        };

        formData.value.push(fieldData);
    });
}

const deleteFormPhoto = async (field) => {
    if (!confirm(t("confirmation_text_block.confirm_deactivate"))) return;
    try {
        await $gotApi.removeFormPhoto(props.order_id, field.response);
        field.response = null;
        field.response_url = null;
        await save(false);
        toast.success(t("common.saved_successfully"));
    } catch (error) {
        console.error('Error deleting form photo:', error);
        toast.error(t("common.error_save"));
    }
}

const uploadFormPhoto = async (field, file) => {
    try {
        loading_document.value = true;
        const response = await $gotApi.uploadFormPhoto(props.order_id, file, field.token);
        if (response.success) {
            field.response = response.document_id;
            field.response_url = response.url;
            await save(false);
            toast.success(t("common.saved_successfully"));
        }
    } catch (error) {
        console.error('Error uploading form photo:', error);
        toast.error(t("common.error_save"));
    } finally {
        loading_document.value = false;
    }
}

const getOperators = async () => {
    loading_operators.value = true;
    try{
        let response = await $OperatorApiService.getAll();
        response.results.forEach(operator => {
            operators.value.push({
                code: operator.id,
                label: `${operator.name} ${operator.surname} (${operator.token})`,
            })
        })
    } catch (error) {
        console.error(error);
    } finally {
        loading_operators.value = false;
    }
}


const save = async (close = false) => {
    attemptedSave.value = true;
    if (!isValid()) return

    try {
        let save_data = {
            id: report.value ? report.value.id : null,
            order: props.order_id || null,
            observation: observation.value,
            report_date: report_date.value,
            operator_id: typeof selected_operator.value === 'object' && selected_operator.value !== null ? selected_operator.value.code : selected_operator.value,
            start_at: start_at.value,
            end_at: end_at.value,
            filled_form: formData.value.map(field => ({
                token: field.token,
                response: field.response
            }))
        }

        let response = await $OrderApiService.saveReport(save_data)
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
    let response = await $OrderApiService.saveDocument(save_data)
    if (response) {
        await getData()
        emit('changed', false)
    }
}

const updateSelected = (e) => {
    if (e.entity == 'operator') {
        selected_operator.value = e.id;
    }
}

const viewFormDocument = async (documentId) => {
    if (!documentId) {
        toast.error(t('common.error') || 'Error');
        return;
    }
    
    try {
        const file = await $DocumentManagerApiService.viewDocument(documentId);
        
        // Create blob URL for image
        const imageBlob = new Blob([file], { type: 'image/jpeg' });
        const blobUrl = URL.createObjectURL(imageBlob);
        
        // Open in new window
        const newWindow = window.open(blobUrl, '_blank');
        
        // Cleanup blob URL after opening
        if (newWindow) {
            setTimeout(() => {
                URL.revokeObjectURL(blobUrl);
            }, 250);
        } else {
            URL.revokeObjectURL(blobUrl);
            toast.error(t('common.error_opening_window') || 'Could not open window');
        }
    } catch (error) {
        console.error('Error viewing document:', error);
        toast.error(t('common.error') || 'Error loading document');
    }
}

const isValid = () => {
    if (report_date.value == null || report_date.value == '') return false
    //if (time_dedicated.value == null || time_dedicated.value == '' || time_dedicated.value == 0) return false
    if (start_at.value == null || start_at.value == '') return false
    if (end_at.value == null || end_at.value == '') return false
    if (selected_operator.value == null) return false
    return true
}

onMounted( async () => {
    await getOperators()
    await getData()
})

watch(() => props.id, (newValue, oldValue) => {
    getData()
});

watch(() => props.order_id, (newValue, oldValue) => {
    getData()
});

</script>
<template>
    <div v-if="!loading" id="wrapper" class="region__content">
        <div class="mb-6">
            <H1Region>{{ props.id ? $t('common.report_detail') + ': ' + report.token : $t('billing_block.new_report') }}
            </H1Region>
        </div>


        <div class="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
            <InputDate v-model="report_date" :label="t('common.date')" required :invalid="attemptedSave && (report_date == null || report_date == '')" />
            <InputTime v-model="start_at" :label="t('common.start')" required :invalid="attemptedSave && (start_at == null || start_at == '')" />
            <InputTime v-model="end_at" :label="t('common.end')" required :invalid="attemptedSave && (end_at == null || end_at == '')" />
        </div>
        <div class="mb-6">
            <label class="block text-sm font-medium text-slate-500 mb-2">
                {{ t('operator') }} 
                <span class="text-red-500">*</span>
            </label>
            <v-select class="block w-full mr-2 required" :class="{ 'invalid': attemptedSave && selected_operator == null }"
              :disabled="loading_operators || operators.length == 0" :model-value="selected_operator"
              @update:modelValue="updateSelected({ entity: 'operator', id: $event })" :options="operators"></v-select>
        </div>
        <div class="mb-6">
            <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('common.observation') }}</label>
            <textarea name="observation" id="observation" cols="30" rows="5" v-model="observation"
                class="w-full border border-slate-300 rounded-md p-2 focus:outline-none focus:border-primary"></textarea>
        </div>

        <!-- Secció del formulari -->
        <div v-if="formData && formData.length > 0" class="mb-6">
            <div class="bg-white rounded-lg border border-slate-300 p-4">
                <h3 class="text-lg font-medium text-slate-700 mb-4">{{ t('common.form_data') || 'Dades del formulari' }}</h3>
                <div class="space-y-2">
                    <div v-for="field in formData" :key="field.token" 
                         class="grid grid-cols-2 gap-4 py-2 border-b border-slate-100 last:border-b-0">
                        
                        <!-- Columna esquerra: Label -->
                        <div class="flex items-center justify-between">
                            <label class="text-sm font-medium text-slate-600 flex items-center gap-1">
                                {{ field.name }}
                                <span v-if="field.required" class="text-red-500 ml-1">*</span>
                                <span class="cursor-help text-slate-400 hover:text-sky-500" :title="field.token">
                                    <Icon name="fa6-solid:circle-question" class="text-xs" /> 
                                </span>
                            </label>
                            <span class="text-xs text-slate-400 uppercase ml-2">{{ field.type }}</span>
                        </div>
                        
                        <!-- Columna dreta: Resposta -->
                        <div class="flex items-center">
                            <div v-if="field.type === 'photo'" class="flex items-center space-x-2 w-full">
                                <template v-if="field.response">
                                    <Icon name="fa6-solid:image" class="text-blue-500" />
                                    <button @click="viewFormDocument(field.response)" 
                                       class="text-blue-600 hover:text-blue-800 underline font-bold cursor-pointer">
                                        {{ t('common.view_image') || 'Veure imatge' }} (ID: {{ field.response }})
                                    </button>
                                    <button @click="deleteFormPhoto(field)" class="text-red-600 hover:text-red-800 ml-2" :title="t('common.delete')">
                                        <Icon name="fa6-solid:trash-can" />
                                    </button>
                                </template>
                                <template v-else>
                                    <AtomsInputFile @update="(file) => uploadFormPhoto(field, file)" 
                                                    :name="'formPhoto_' + field.token" 
                                                    class="w-full" />
                                </template>
                            </div>
                            <div v-else class="w-full">
                                <input v-if="field.type === 'text'" type="text" v-model="field.response" 
                                       class="w-full border border-slate-300 rounded p-1 text-sm" />
                                <input v-else-if="field.type === 'numeric'" type="number" v-model="field.response" 
                                       class="w-full border border-slate-300 rounded p-1 text-sm" />
                                <div v-else class="text-slate-800 font-bold">
                                    {{ field.response }}
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        <!-- Registre del canvi de comptador -->
        <div v-if="report?.change_meter_status?.applied" class="mb-6">
          <div class="bg-white rounded-lg border border-slate-300 p-4">
            <h3 class="text-lg font-medium text-slate-700 mb-4">{{ t('order_block.change_meter_record') }}</h3>
            <div class="space-y-2 text-sm">
              <div class="flex items-center gap-2 text-green-700">
                <Icon name="fa6-solid:circle-check" />
                {{ t('order_block.change_meter_applied_to_system') }}
              </div>
              <div>{{ t('order_block.change_meter_applied_by') }}: <strong>{{ report.change_meter_status.applied_by }}</strong></div>
              <div>{{ t('order_block.change_meter_applied_at') }}: <strong>{{ formatDateTime(report.change_meter_status.applied_at) }}</strong></div>
            </div>
          </div>
        </div>

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
            <div v-else-if="!loading_document && documents?.length > 0">
                <DocumentList :documents="documents" @change="getData" />
            </div>
            <AtomsInputFile @update="saveDocument" :name="'orderReportDocumentFile'" :uploaded="null" :fullWidth="true"
                class="w-full" />
        </details>

        <hr class="my-2" />
        <div class="flex flex-row-reverse gap-3 mt-4">
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