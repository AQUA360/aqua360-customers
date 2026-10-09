<script setup>
import { useDebounceFn } from '@vueuse/core'
import BillingDetail from './BillingDetail.vue';
import ClaimRequestDetail from './ClaimRequestDetail.vue';
import SEPARemittanceDetailMinimal from './SEPARemittanceDetailMinimal.vue';
import SupplyCutDetail from './SupplyCutDetail.vue';
import OptionSelectorGroup from '../atoms/OptionSelectorGroup.vue';

const props = defineProps({
    data: Object,
    search: Boolean,
    isFixed: Boolean,
    // Empresa seleccionada al pas 1 (només amb múltiples empreses): exclou contractes d'altres empreses
    companyId: {
        type: [Number, String],
        default: null,
    },
})

const emit = defineEmits(['change', 'load', 'remove-fix'])
const { t } = useI18n();
const { $ConfiglistApiService, $CommunicationProcessApiService, $apiManager } = useNuxtApp();

const group_same = ref([])
const group_by_person = ref(false)
const taskFailed = ref(false)
const addressType = ref('contract')

const addressOptions = [
    { value: 'invoice', name: 'invoice' },
    { value: 'contract', name: 'contract' },
    { value: 'default', name: 'default' },
]
// L'objecte fixat marca quina adreça té sentit: la d'una facturació és la de la
// factura i la d'un tall és la del punt de subministrament. 'invoice' queda
// fora perquè un tall no genera factura, igual que al pas 1.
const disabledAddressOptions = computed(() => ['invoice'])

const loading = ref(false)
const filter_data = ref({})
const persons_data = ref([])
const showNoPersonsWarning = ref(false)

const messageTypesOptions = ref([])
const messageTypeSelect = ref([])

const statuses = ref([])
const commitStatuses = ref([])
const paymentTypes = ref([])

const expireStartDate = ref(null)
const expireEndDate = ref(null)
const issueStartDate = ref(null)
const issueEndDate = ref(null)
const returnStartDate = ref(null)
const returnEndDate = ref(null)
const selectedStatuses = ref([])
const selectedCommitStatuses = ref([])
const selectedPaymentTypes = ref([])

const loadingStatuses = ref(false)
const loadingPaymentTypes = ref(false)
const loadingCommitStatuses = ref(false)

const filteringTaskId = ref(null)
const attachReadings = ref(false)

// Un tall de 7847 destinataris trigava uns 125 s a la tasca de Celery: es sona
// cada 4 s per no saturar /task-progress/ i es dona marge de 240 s abans de
// considerar que la tasca s'ha perdut.
const TASK_POLL_INTERVAL = 4000
const TASK_POLL_TIMEOUT = 240000

// Espera activa de la tasca. Abans l'esperava AtomsProcessColorBadge, un
// component invisible (v-show="false") que només polla si el seu watch de taskId
// s'activa; si checkTask no tornava res el bucle era silenciós i el spinner del
// peu de pàgina es quedava carregant per sempre.
const waitForTask = async (taskId) => {
    const deadline = Date.now() + TASK_POLL_TIMEOUT
    while (Date.now() < deadline) {
        await new Promise((resolve) => setTimeout(resolve, TASK_POLL_INTERVAL))
        const res = await $apiManager.checkTask(taskId)
        if (!res) continue
        if (res.state === 'SUCCESS') return 'SUCCESS'
        if (res.state === 'FAILURE' || res.state === 'REVOKED') return res.state
    }
    return 'TIMEOUT'
}

const getData = async () => {
    loading.value = true
    taskFailed.value = false
    emit('load', true)
    try {
        filter_data.value.entity = props.data.entity
        filter_data.value.id = props.data.id
        filter_data.value.message_types = messageTypeSelect.value
        filter_data.value.address_type = addressType.value
        filter_data.value.company = props.companyId || null
        //filter_data.value.include = includeSelect.value
        let response_data = {
            type: 'FIXED',
            group_same: group_by_person.value ? group_same.value : [],
            filters: filter_data.value
        }
        const response = await $CommunicationProcessApiService.getCommunicationProcessData(response_data)
        if (response && response.task_id) {
            filteringTaskId.value = response.task_id
            const state = await waitForTask(response.task_id)
            if (state === 'SUCCESS') {
                await refreshData()
            } else {
                handleTaskError({ state })
            }
        } else {
            handleTaskError({ state: 'NO_TASK' })
        }
    } catch (error) {
        console.error(error)
        handleTaskError({ state: 'ERROR' })
    } finally {
        // Garantit: cap branca pot deixar el spinner del peu de pàgina penjant.
        loading.value = false
        emit('load', false)
    }
}

const refreshData = async () => {
    try {
        const response = await $apiManager.checkTask(filteringTaskId.value)
        persons_data.value = response.result.persons
        showNoPersonsWarning.value = response.result.persons.length === 0
        emit('change', persons_data.value, null, false, attachReadings.value)
        filteringTaskId.value = null;
    } catch (error) {
        console.error(error)
    } finally {
        loading.value = false
        emit('load', false)
    }
}

const fetchConfigData = async (service, entity, targetArray, loading) => {
    try {
        loading.value = true;
        const data = await $ConfiglistApiService.getAll(service + '/' + entity);
        targetArray.value = [];

        if (data.results) {
            data.results.forEach(data => {
                targetArray.value.push({
                    label: data.name || data.token,
                    code: data.id
                })
            });
        }
    } catch (error) {
        console.error(`Error fetching ${entity}:`, error);
    } finally {
        loading.value = false;
    }
}

const toggleAttachReadings = () => {
    attachReadings.value = !attachReadings.value
    emit('change', persons_data.value, null, false, attachReadings.value)
}

// La tasca de cerca pot fallar (p. ex. una entitat de fixed_data que el backend
// no coneix). Sense això el wizard es quedava carregant i amb la llista buida,
// sense cap senyal d'error.
const handleTaskError = (payload) => {
    console.error('Communication process data task failed:', payload)
    taskFailed.value = true
    loading.value = false
    emit('load', false)
}

const loadSelectData = async () => {
    await fetchConfigData('billing', 'invoice-status', statuses, loadingStatuses);
    await fetchConfigData('contract', 'contract-payment-type', paymentTypes, loadingPaymentTypes);
    await fetchConfigData('billing', 'commitment-deposit-status', commitStatuses, loadingCommitStatuses);
}

const debouncedGetData = useDebounceFn(
    getData, 1500)



const loadMsgTypes = async () => {
    let response = await $ConfiglistApiService.getAll('communication/message-type')
    response.results.forEach(item => {
        messageTypesOptions.value.push({
            value: item.token,
            name: item.name
        })
    })

    messageTypeSelect.value = messageTypesOptions.value.map(item => item.value)
    group_same.value = messageTypesOptions.value.map(item => item.value)
}


onMounted(async () => {
    // Els filtres de facturació (estats, tipus de pagament, dates) no apliquen als
    // talls de subministrament: no en cal carregar les llistes.
    if (props.data.entity !== 'supplycut') await loadSelectData()
    await loadMsgTypes()
    await getData()
})

watch([
    issueStartDate,
    issueEndDate,
    expireStartDate,
    expireEndDate,
    returnStartDate,
    returnEndDate,
    selectedStatuses,
    selectedPaymentTypes,
    selectedCommitStatuses
], async () => {
    filter_data.value = {
        issue_start_date: issueStartDate.value,
        issue_end_date: issueEndDate.value,
        expire_start_date: expireStartDate.value,
        expire_end_date: expireEndDate.value,
        return_start_date: returnStartDate.value,
        return_end_date: returnEndDate.value,
        statuses: selectedStatuses.value.map(item => item.code),
        payment_types: selectedPaymentTypes.value.map(item => item.code),
        commitment_statuses: selectedCommitStatuses.value.map(item => item.code)
    }
})

const changeGroupSame = (newVal) => {
    if (group_same.value.includes(newVal)) {
        group_same.value = group_same.value.filter(item => item !== newVal)
    } else {
        group_same.value.push(newVal)
    }
}

watch(() => props.search, async (newVal, oldVal) => {
    if (newVal !== oldVal) {
        await getData()
    }
}, { immediate: false })
</script>

<template>
    <div>
        <div class="p-3 bg-white rounded-lg shadow-sm">
            <!-- FILTER SELECT -->
            <div
                class="bg-sky-50 border-l-4 border-sky-400 px-4 py-2 mb-4 grid grid-cols-[auto,1fr] flex items-center gap-3">
                <Icon name="fa6-solid:magnifying-glass" class="text-lg text-sky-400" />
                <div class="flex items-center gap-2">
                    <span class="text-sky-500 font-semibold">
                        {{ t('informative_block.info_filter_change') }}
                    </span>
                    <!-- <div class="px-4 py-1 bg-white text-sky-500 rounded border border-sky-400">
                        {{ t('Cercar') }}
                    </div> -->
                </div>
            </div>

            <div v-if="showNoPersonsWarning"
                class="bg-orange-50 border-l-4 border-orange-400 px-4 py-2 mb-4 grid grid-cols-[auto,1fr] flex items-center gap-3">
                <Icon name="fa6-solid:triangle-exclamation" class="text-lg text-orange-400" />
                <span class="text-orange-500 font-semibold">
                    {{ t('common.no_data_found') }}
                </span>
            </div>

            <div v-if="taskFailed"
                class="bg-red-50 border-l-4 border-red-400 px-4 py-2 mb-4 grid grid-cols-[auto,1fr] flex items-center gap-3">
                <Icon name="fa6-solid:circle-exclamation" class="text-lg text-red-400" />
                <span class="text-red-500 font-semibold">
                    {{ t('customer_service_block.error_search_recipients') }}
                </span>
            </div>

            <div class="group relative">
                <div v-if="data.entity === 'billing'">
                    <fieldset class="mb-5 border border-slate-300 rounded-lg">
                        <legend class="text-lg font-bold text-slate-600 ml-5">{{ t('billing') }}</legend>
                        <div class="p-2">
                            <BillingDetail :id="data.id" />
                        </div>
                    </fieldset>
                    <!-- <div class="p-2 bg-green-50 border-l-4 border-green-200 mb-5">
                            <BillingDetail :id="data.id" />
                    </div> -->
                </div>

                <div v-else-if="data.entity === 'claimrequest'">
                    <fieldset class="mb-5 border border-slate-300 rounded-lg">
                        <legend class="text-lg font-bold text-slate-600 ml-5">{{ t('claim_block.claim_payments') }}
                        </legend>
                        <div class="p-2">
                            <ClaimRequestDetail :id="data.id" :isSubRegion="true" />
                        </div>
                    </fieldset>
                </div>
                <div v-else-if="data.entity === 'sepa_payments'">
                    <fieldset class="mb-5 border border-slate-300 rounded-lg">
                        <legend class="text-lg font-bold text-slate-600 ml-5">{{ t('common.sepa_managements') }}
                        </legend>
                        <div class="p-2">
                            <SEPARemittanceDetailMinimal :remittance_id="data.id" :isSubRegion="true" />
                        </div>
                    </fieldset>
                </div>

                <div v-else-if="data.entity === 'supplycut'">
                    <fieldset class="mb-5 border border-slate-300 rounded-lg">
                        <legend class="text-lg font-bold text-slate-600 ml-5">{{ t('common.supply_cuts') }}
                        </legend>
                        <div class="p-2">
                            <SupplyCutDetail :id="data.id" />
                        </div>
                    </fieldset>
                </div>

                <!-- <button @click="showDetail('BillingForm', data.id)"
                class="absolute border border-slate-300 top-1 right-8 bg-white h-6 w-6 rounded flex items-center justify-center opacity-0 group-hover:opacity-100 hover:bg-slate-200 transition-all duration-200 ease">
                    <Icon name="fa6-solid:pencil" class="text-slate-500" />
                </button> -->
                <button v-if="!isFixed" @click="emit('remove-fix')"
                    class="absolute border border-slate-300 top-1 right-1 bg-white h-6 w-6 rounded flex items-center justify-center opacity-0 group-hover:opacity-100 hover:bg-slate-200 transition-all duration-200 ease">
                    <Icon name="fa6-solid:xmark" class="text-red-500" />
                </button>
            </div>

            <div class="flex items-center gap-2">
                <div v-if="data.entity === 'billing'" class="flex gap-3 h-fit items-center my-auto">
                    <div @click="toggleAttachReadings"
                        class="flex items-center gap-2 cursor-pointer px-3 py-1.5 rounded-md transition-all duration-200" >
                        <div class="w-4 h-4 rounded border-2 flex items-center justify-center shrink-0"
                            :class="[attachReadings ? 'border-sky-600 bg-sky-600' : 'border-gray-300']">
                            <Icon v-if="attachReadings" name="fa6-solid:check" class="text-white" />
                        </div>
                        <span class="text-sm text-gray-600">
                            {{ t('customer_service_block.attach_readings') }}
                        </span>
                    </div>
                </div>

                <div class="flex items-center gap-2">
                    <input type="checkbox" v-model="group_by_person" />
                    <label class="text-sm text-slate-600">{{ t('customer_service_block.group_by_person') }}</label>
                    <abbr :title="t('informative_block.info_group_by_person')"
                        class="text-slate-500 flex items-center justify-center">
                        <Icon name="fa6-solid:circle-exclamation" />
                    </abbr>
                </div>

                <div v-if="data.entity === 'supplycut'" class="min-w-[220px]">
                    <div class="text-sm font-medium text-gray-500 mb-2">
                        {{ t('customer_service_block.select_address') }}
                    </div>
                    <OptionSelectorGroup :options="addressOptions" :selected-value="addressType"
                        selection-mode="single" indicator-type="radio" :disabled-values="disabledAddressOptions"
                        @select="addressType = $event" />
                </div>
            </div>


            <div class="grid grid-cols-2 gap-2 mt-3" v-if="data.entity !== 'supplycut'">
                <div class="col-span-2">
                    <div class="grid gap-4" :class="{
                        'grid-cols-2': data.entity === 'billing',
                        'grid-cols-3': data.entity === 'claimrequest'
                    }">
                        <div class="pr-2 border-r border-slate-200">
                            <label class="block text-sm font-medium text-slate-600 mb-2">{{ $t('common.send_date')
                            }}</label>
                            <div class="grid grid-cols-[auto,1fr,auto,1fr] items-center gap-2">
                                <label class="block text-sm font-medium text-slate-600 mb-2 mr-5">{{ $t('common.from')
                                }}:</label>
                                <AtomsInputDate v-model="issueStartDate" class="mb-2" />
                                <label class="block text-sm font-medium text-slate-600 mb-2 mr-5">{{ $t('common.to')
                                    }}:</label>
                                <AtomsInputDate v-model="issueEndDate" class="mb-2" />
                            </div>
                        </div>

                        <div class="pr-2 border-r border-slate-200">
                            <label class="block text-sm font-medium text-slate-600 mb-2">{{ $t('common.due_date')
                            }}</label>
                            <div class="grid grid-cols-[auto,1fr,auto,1fr] items-center gap-2">
                                <label class="block text-sm font-medium text-slate-600 mb-2 mr-5">{{ $t('common.from')
                                }}:</label>
                                <AtomsInputDate v-model="expireStartDate" class="mb-2" />
                                <label class="block text-sm font-medium text-slate-600 mb-2 mr-5">{{ $t('common.to')
                                    }}:</label>
                                <AtomsInputDate v-model="expireEndDate" class="mb-2" />
                            </div>
                        </div>

                        <div v-if="data.entity === 'claimrequest'" class="pr-2 border-r border-slate-200">
                            <label class="block text-sm font-medium text-slate-600 mb-2">{{
                                $t('billing_block.sepa_return_date')
                                }}</label>
                            <div class="grid grid-cols-[auto,1fr,auto,1fr] items-center gap-2">
                                <label class="block text-sm font-medium text-slate-600 mb-2 mr-5">{{ $t('common.from')
                                }}:</label>
                                <AtomsInputDate v-model="returnStartDate" class="mb-2" />
                                <label class="block text-sm font-medium text-slate-600 mb-2 mr-5">{{ $t('common.to')
                                    }}:</label>
                                <AtomsInputDate v-model="returnEndDate" class="mb-2" />
                            </div>
                        </div>
                    </div>
                </div>
                <div>
                    <label class="block text-sm font-medium text-slate-600 mb-2">{{ $t('common.status') }}: {{
                        $t('invoice') }}</label>
                    <v-select multiple class="block w-full mr-1 custom-select" v-model="selectedStatuses"
                        :options="statuses" :loading="loadingStatuses" />
                </div>
                <div v-if="data.entity === 'claimrequest'">
                    <label class="block text-sm font-medium text-slate-600 mb-2">{{ $t('common.status') }}: {{
                        $t('commitment_deposit') }}</label>
                    <v-select multiple class="block w-full mr-1 custom-select" v-model="selectedCommitStatuses"
                        :options="commitStatuses" :loading="loadingCommitStatuses" />
                </div>
                <div>
                    <label class="block text-sm font-medium text-slate-600 mb-2">{{ $t('common.payment_method')
                        }}</label>
                    <v-select multiple class="block w-full mr-1 custom-select" v-model="selectedPaymentTypes"
                        :options="paymentTypes" :loading="loadingPaymentTypes" />
                </div>
            </div>



        </div>
    </div>
</template>
