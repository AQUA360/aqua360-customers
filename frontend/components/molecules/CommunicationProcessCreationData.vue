<script setup>
import { format } from 'date-fns';
import { useDebounceFn } from '@vueuse/core'
import CommunicationMessageEdit from './CommunicationMessageEdit.vue';

const props = defineProps({
    data: Object,
    hasReadings: Boolean,
    // Token del tipus d'ús a preseleccionar segons el context del pas 1 (p. ex. 'billing')
    defaultUseTypeToken: {
        type: String,
        default: null,
    },
    // Empresa seleccionada al pas 1 per preseleccionar la seva configuració d'empresa
    defaultCompanyId: {
        type: [Number, String],
        default: null,
    },
})

const { $ConfiglistApiService, $CommunicationProcessApiService, $MessageTemplateApiService, $ConfigProjectApiService } = useNuxtApp();
const { t } = useI18n();
const emit = defineEmits(['change'])

const due_date = ref(null)
const description = ref('')

const selectedCompanyConfigEmail = ref(null)
const selectedCompanyConf = ref(null)
const companiesConf = ref([])
const attachLetter = ref(false)
const attachInvoices = ref(false)

const useTypes = ref([])
const selectedUseType = ref(null)

const finalData = ref({})
const useTypeReadings = ref(null)

const loadData = async () => {
    
    if (props.data) {
        finalData.value = props.data
        due_date.value = props.data.due_date || format(new Date(), 'yyyy-MM-dd').toString()
        description.value = props.data.description || ''
        // Si no hi ha res desat es mantenen les preseleccions (tipus d'ús per context, empresa única)
        selectedUseType.value = props.data.use_type || selectedUseType.value
        changeCompanyConf(companiesConf.value.find(c => c.code == props.data.company?.code) || selectedCompanyConf.value)
        if (props.data.company_config_email) {
            selectedCompanyConfigEmail.value = props.data.company_config_email
        }
        attachLetter.value = props.data.attach_letter || false
        emitChange()
    }
}

const emitChange = () => {
    finalData.value = {
        company: selectedCompanyConf.value,
        company_config_email: selectedCompanyConfigEmail.value,
        due_date: due_date.value,
        description: description.value,
        messages_data: props?.data?.messages_data?.length > 0 ? props?.data?.messages_data : [],
        attach_letter: attachLetter.value,
        attach_invoices: attachInvoices.value,
        use_type: selectedUseType.value,
    }
    emit('change', finalData.value)
}

const loadCompaniesConf = async () => {
    let response = await $ConfiglistApiService.getAll('service/company-config')
    response.results.forEach(companyies => {
        const company = companyies.company;
        companiesConf.value.push({
            code: companyies.id,
            label: company.name,
            ...companyies
        })
    })

    if (companiesConf.value.length === 1) {
        selectedCompanyConf.value = companiesConf.value[0]
    } else if (props.defaultCompanyId) {
        selectedCompanyConf.value = companiesConf.value.find(c => c.company?.id == props.defaultCompanyId) || null
    }

}

const loadUseTypes = async () => {
    try {
        const response = await $ConfiglistApiService.getAll('communication/communication-use-type')
        useTypes.value = response.results.map(item => ({
            label: item.name,
            value: item.id,
            token: item.token,
            is_default: item.is_default,
        }))
        const preferredToken = props.hasReadings ? useTypeReadings.value : props.defaultUseTypeToken
        selectedUseType.value = useTypes.value.find(type => preferredToken && type.token == preferredToken)
            || useTypes.value.find(type => type.is_default)
            || null
    } catch (error) {
        console.error(error)
    }
}

const changeCompanyConf = (newVal) => {
    selectedCompanyConf.value = newVal
    if (newVal && newVal?.company_config_emails?.length > 0) {
        const useTypeEmail = selectedUseType.value
            ? newVal.company_config_emails.find(email => email.use_type?.token === selectedUseType.value.token)
            : null
        if (useTypeEmail) {
            selectedCompanyConfigEmail.value = useTypeEmail;
        } else {
            selectedCompanyConfigEmail.value = newVal.company_config_emails.find(email => email.is_default);
        }
    } else {
        selectedCompanyConfigEmail.value = null;
    }
    emitChange()
}

// En canviar el tipus d'ús es proposa el remitent configurat per aquest tipus, si n'hi ha
const changeUseType = (newVal) => {
    selectedUseType.value = newVal
    const useTypeEmail = newVal
        ? selectedCompanyConf.value?.company_config_emails?.find(email => email.use_type?.token === newVal.token)
        : null
    if (useTypeEmail) {
        selectedCompanyConfigEmail.value = useTypeEmail
    }
    emitChange()
}

const debouncedEmitChange = useDebounceFn(() => {
    emitChange()
}, 500)

watch([due_date, selectedCompanyConfigEmail], () => {
    emitChange()
})


onMounted(async () => {
    try {
        useTypeReadings.value = await $ConfigProjectApiService.get('communication_use_type_reading');
        await loadUseTypes()
        await loadCompaniesConf()
        await loadData()
    } catch (error) {
        console.error(error)
    }
})

</script>
<template>
    <div class="">
        <div class="mb-2 grid grid-cols-2 gap-4">
            <div>
                <AtomsInputDate v-model="due_date" class="w-full" :label="$t('common.send_date')" :required="true" />
                <div class="mb-3">
                    <div class="text-sm font-medium text-gray-500 mb-2">
                        {{ t('customer_service_block.select_company') }}
                        <span class="text-red-500">*</span>
                    </div>
                    <div>
                        <v-select class="block w-full mr-2 required" :disabled="companiesConf.length == 0"
                            :model-value="selectedCompanyConf" @update:modelValue="changeCompanyConf($event)"
                            :options="companiesConf"></v-select>
                    </div>
                </div>
                <div class="mb-3">
                    <div class="text-sm font-medium text-gray-500 mb-2">
                        {{ t('service_block.config_mail_sender') }}
                        <span class="text-red-500">*</span>
                    </div>
                    <div>
                        <v-select class="block w-full mr-2 required" :disabled="!selectedCompanyConf || !selectedCompanyConf?.company_config_emails || selectedCompanyConf?.company_config_emails?.length == 0"
                            :model-value="selectedCompanyConfigEmail" @update:modelValue="selectedCompanyConfigEmail = $event"
                            :options="selectedCompanyConf?.company_config_emails || []"></v-select>
                    </div>
                </div>
                <div>
                    <label class="text-sm font-medium text-gray-500 mb-2">
                        {{ t('common.use_type') }}<span class="text-red-500">*</span>
                    </label>
                    <v-select class="block w-full mr-2 required" :disabled="useTypes.length == 0 || (props.hasReadings && selectedUseType?.token == useTypeReadings)"
                        :model-value="selectedUseType"
                        @update:modelValue="changeUseType($event)"
                        :options="useTypes" />
                </div>
            </div>
            <div>
                <p class="block text-sm font-medium text-slate-600 mb-2">{{
                    $t('customer_service_block.process_description') }} *</p>
                <textarea id="messageTextarea" v-model="description" class="input w-full h-[180px]"
                    :label="$t('common.description')" :required="true" @input="debouncedEmitChange" />
            </div>
        </div>

        <hr class="my-4">
        <div>
            <p class="block text-sm font-medium text-slate-600 mb-2">{{ $t('common.actions') }}</p>
            <div class="grid grid-cols-2 gap-4">
                <label
                    class="flex cursor-pointer items-start gap-3 rounded-lg border bg-white p-3 transition-colors"
                    :class="attachLetter ? 'border-sky-500 bg-sky-50/60' : 'border-slate-200 hover:border-slate-300 hover:bg-slate-50'">
                    <span class="flex h-8 w-8 shrink-0 items-center justify-center rounded-md transition-colors"
                        :class="attachLetter ? 'bg-sky-100 text-sky-600' : 'bg-slate-100 text-slate-500'">
                        <Icon name="fa6-solid:file-pdf" />
                    </span>
                    <span class="min-w-0 flex-1">
                        <span class="block text-sm font-medium text-slate-700">
                            {{ t('common.attach_letter_to_email') }}
                        </span>
                        <span class="mt-0.5 block text-xs leading-snug text-slate-500">
                            {{ t('informative_block.info_always_attach') }}
                        </span>
                    </span>
                    <input type="checkbox" v-model="attachLetter" @change="debouncedEmitChange"
                        class="mt-1 h-4 w-4 shrink-0 cursor-pointer rounded border-slate-300 text-sky-600 focus:ring-sky-500" />
                </label>

                <label v-if="props.hasReadings"
                    class="flex cursor-pointer items-start gap-3 rounded-lg border bg-white p-3 transition-colors"
                    :class="attachInvoices ? 'border-sky-500 bg-sky-50/60' : 'border-slate-200 hover:border-slate-300 hover:bg-slate-50'">
                    <span class="flex h-8 w-8 shrink-0 items-center justify-center rounded-md transition-colors"
                        :class="attachInvoices ? 'bg-sky-100 text-sky-600' : 'bg-slate-100 text-slate-500'">
                        <Icon name="fa6-solid:file-invoice" />
                    </span>
                    <span class="min-w-0 flex-1">
                        <span class="block text-sm font-medium text-slate-700">
                            {{ t('customer_service_block.select_attach_invoices') }}
                        </span>
                        <span class="mt-0.5 block text-xs leading-snug text-slate-500">
                            {{ t('informative_block.info_attach_only_existing_invoices') }}
                        </span>
                    </span>
                    <input type="checkbox" v-model="attachInvoices" @change="debouncedEmitChange"
                        class="mt-1 h-4 w-4 shrink-0 cursor-pointer rounded border-slate-300 text-sky-600 focus:ring-sky-500" />
                </label>
            </div>
        </div>

    </div>

</template>