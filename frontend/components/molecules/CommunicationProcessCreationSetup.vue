<script setup>
import CommunicationProcessCreationSetupContract from './CommunicationProcessCreationSetupContract.vue';
import CommunicationProcessCreationSetupBilling from './CommunicationProcessCreationSetupBilling.vue';
import CommunicationProcessCreationSetupContractRequest from './CommunicationProcessCreationSetupContractRequest.vue';
import CommunicationProcessCreationSetupAddress from './CommunicationProcessCreationSetupAddress.vue';
import CommunicationProcessCreationSetupPerson from './CommunicationProcessCreationSetupPerson.vue';
import CommunicationProcessCreationSetupSupplyPoint from './CommunicationProcessCreationSetupSupplyPoint.vue';
import CommunicationProcessCreationSetupSupplyCut from './CommunicationProcessCreationSetupSupplyCut.vue';
import CommunicationProcessCreationSetupCommunication from './CommunicationProcessCreationSetupCommunication.vue';
import ButtonOutline from '../atoms/ButtonOutline.vue';
import OptionSelectorGroup from '../atoms/OptionSelectorGroup.vue';
import { useDebounceFn } from '@vueuse/core'


const props = defineProps({
    request: Object,
    search: Boolean,
    // Empresa seleccionada al pas 1 (només amb múltiples empreses): exclou contractes d'altres empreses
    companyId: {
        type: [Number, String],
        default: null,
    },
})

const emit = defineEmits(['change', 'load', 'show-detail', 'change-supply-cuts'])
const { t } = useI18n();
const { $ConfiglistApiService, $CommunicationProcessApiService, $apiManager } = useNuxtApp();

const typeSelect = ref('CONTRACT')
const addressSelect = ref('default')
const messageTypeSelect = ref([])
const includeSelect = ref(['is_juridic', 'is_physical'])
const group_same = ref([])

const loading = ref(false)
const filter_data = ref({})
const persons_data = ref([])
const showNoPersonsWarning = ref(false)
const firstWarning = ref(true)
const attachInvoices = ref(false)
const attachReadings = ref(false)

const filteringTaskId = ref(null)

const options = [
    { value: 'CONTRACT', name: 'contract', icon: 'fa6-solid:file-contract' },
    { value: 'CONTRACTREQUEST', name: 'contract_request', icon: 'fa6-solid:file-circle-plus' },
    { value: 'BILLING', name: 'billing', icon: 'fa6-solid:clipboard' },
    { value: 'ADDRESS', name: 'address_block.address', icon: 'fa6-solid:location-dot' },
    { value: 'PERSON', name: 'person', icon: 'fa6-solid:user' },
    { value: 'SUPPLYPOINT', name: 'common.short_supply', icon: 'fa6-solid:street-view' },
    { value: 'SUPPLYCUT', name: 'common.supply_cuts', icon: 'fa6-solid:faucet' },
    { value: 'COMMUNICATION', name: 'common.comms', icon: 'fa6-solid:envelope' },
    //{ value: 'CONNECTION', name: 'Escomesa'), icon: 'fa6-solid:plug' },
    //{ value: 'ZONE', name: 'Zona'), icon: 'fa6-solid:map-location-dot' },
]

const addressOptions = [
    { value: 'invoice', name: 'invoice' },
    { value: 'contract', name: 'contract' },
    { value: 'default', name: 'default' },
]

const includeOptions = [
    { value: 'is_juridic', name: 'common.juridic' },
    { value: 'is_physical', name: 'common.physical' },
]


/* const messageTypesOptions = [
    { value: 'postal', name: t('A. Postal') },
    { value: 'sms', name: t('SMS') },
    { value: 'email', name: t('E-mail') },
] */

const messageTypesOptions = ref([])
const disabledAddressOptions = computed(() => {
    const disabled = []
    if (typeSelect.value !== 'BILLING') {
        disabled.push('invoice')
    }
    if (typeSelect.value === 'SUPPLYPOINT') {
        disabled.push('invoice', 'default')
    }
    if (typeSelect.value === 'COMMUNICATION') {
        disabled.push('invoice', 'contract')
    }
    return [...new Set(disabled)]
})

const refreshData = async () => {
    try {
        const response = await $apiManager.checkTask(filteringTaskId.value)
        firstWarning.value = false
        persons_data.value = response.result.persons
        showNoPersonsWarning.value = response.result.persons.length === 0
        emit('change', persons_data.value, typeSelect.value, attachInvoices.value, attachReadings.value)
        filteringTaskId.value = null;
    } catch (error) {
        console.error(error)
    } finally {
        loading.value = false
        emit('load', false)
    }
}

const getData = async () => {
    loading.value = true
    emit('load', true)
    try {
        filter_data.value.address_type = addressSelect.value
        filter_data.value.message_types = messageTypeSelect.value
        filter_data.value.company = props.companyId || null
        //filter_data.value.include = includeSelect.value
        let response_data = {
            type: typeSelect.value,
            group_same: group_same.value,
            filters: filter_data.value
        }
        
        const response = await $CommunicationProcessApiService.getCommunicationProcessData(response_data)
        console.log("Response setup: ", response);
        // if (response) {
        //     firstWarning.value = false
        //     persons_data.value = response.persons
        //     showNoPersonsWarning.value = response.persons.length === 0
        //     emit('change', persons_data.value, typeSelect.value, attachInvoices.value)
        // }
        if (response) filteringTaskId.value = response.task_id
    } catch (error) {
        console.error(error)
    // } finally {
    //     loading.value = false
    //     emit('load', false)
    }
}

const showDetail = (component, id) => {
    emit('show-detail', component, id)
}

const debouncedGetData = useDebounceFn(
    getData, 1500)

const onFilterChange = async (newVal) => {
    filter_data.value = newVal
    attachInvoices.value = newVal.attach_invoices || false
    attachReadings.value = (newVal.attach_readings && newVal.attach_invoices) || false
    // El filtre de talls arriba com a objectes, però el payload de save() espera
    // ids: es normalitzen aquí perquè el vincle es pugui llegir després del procés.
    const cuts = Array.isArray(newVal?.supply_cuts) ? newVal.supply_cuts : []
    emit('change-supply-cuts', cuts.map(cut => (typeof cut === 'object' ? cut.id : cut)).filter(Boolean))
    //await debouncedGetData()
}

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
    await loadMsgTypes()
    //getData()
})

const changeAddress = (newVal) => {
    if (newVal === 'invoice' && typeSelect.value !== 'BILLING') {
        return;
    }
    if (newVal != 'contract' && typeSelect.value === "SUPPLYPOINT") {
        return;
    }
    addressSelect.value = newVal
    //debouncedGetData()
}

const changeMessageType = (newVal) => {
    if (messageTypeSelect.value.includes(newVal)) {
        messageTypeSelect.value = messageTypeSelect.value.filter(item => item !== newVal)
    } else {
        messageTypeSelect.value.push(newVal)
    }
    //debouncedGetData()
}

const changeGroupSame = (newVal) => {
    //group_same.value = !group_same.value
    if (group_same.value.includes(newVal)) {
        group_same.value = group_same.value.filter(item => item !== newVal)
    } else {
        group_same.value.push(newVal)
    }
    //debouncedGetData()
}

watch(typeSelect, async (newVal) => {
    filter_data.value = {}
    if (newVal != 'BILLING' && addressSelect.value == 'invoice') {
        addressSelect.value = 'default'
    }
    if (newVal == 'SUPPLYPOINT' && addressSelect.value != 'contract') {
        addressSelect.value = 'contract'
    }
})

watch(() => props.search, async (newVal, oldVal) => {
    if (newVal !== oldVal) {
        await getData()
    }
}, { immediate: false })

</script>

<template>
    <div>
        
        <div class="p-3 bg-white rounded-lg shadow-sm">
            <!-- STATIC OPTIONS: management, address and channels apply to every filter type -->
            <!-- <div class="my-2">
                <button
                    class="group bg-white border border-slate-300 rounded-lg px-3 py-1 flex items-center hover:bg-sky-50 hover:text-sky-500 hover:border-sky-500"
                    @click="getData">
                    <Icon name="fa6-solid:magnifying-glass" class="text-slate-500 mr-2 group-hover:text-sky-500" />
                    {{ t('Cerca') }}
                </button>
            </div> -->
            <div class="grid grid-cols-[1fr,2fr] gap-4 mb-6 pb-6 border-b border-gray-200">
                <!-- <div class="col-span-2 mt-2">
                    <div class="flex items-center gap-2 py-1.5">
                        <button class="shrink-0" @click="changeGroupSame">
                            <Icon :name="group_same ? 'fa6-solid:toggle-on' : 'fa6-solid:toggle-off'" 
                                class="h-6 w-6 transition-all duration-300 ease-in-out transform"
                                :class="{ 
                                    'text-sky-500': group_same, 
                                    'text-slate-400': !group_same 
                                }" />
                        </button>
                        <span class="text-xs font-medium text-gray-500">
                            {{ t('Agrupar comunicacions amb el mateix destinatari i adreça') }}
                        </span>
                    </div>
                </div> -->


                <div>
                    <ButtonOutline @click="showDetail('openManageOptions', null)">
                        <span>{{ t('customer_service_block.select_mng') }}</span>
                    </ButtonOutline>
                </div>
                <span></span>
                <!-- <div class="col-span-2">
                    <div class="text-sm font-medium text-gray-500 mb-2 flex items-center gap-2">
                        <abbr :title="t('customer_service_block.no_grouping')"
                            class="flex items-center">
                            <Icon name="fa6-solid:circle-info" class="text-slate-500" />
                        </abbr>
                        <span>
                            {{ t('customer_service_block.group_recipients') }}:
                        </span>
                    </div>
                    <div class="flex gap-3">
                        <div v-for="option in messageTypesOptions" :key="option.value"
                            @click="changeGroupSame(option.value)"
                            class="cursor-pointer flex items-center gap-2 px-3 py-1.5 rounded-md transition-all duration-200"
                            :class="[
                                group_same.includes(option.value)
                                    ? 'bg-sky-50 ring-1 ring-sky-500'
                                    : 'hover:bg-gray-50'
                            ]">
                            <div class="w-3.5 h-3.5 rounded-sm border-2 flex items-center justify-center shrink-0" :class="[
                                group_same.includes(option.value)
                                    ? 'border-sky-500 bg-sky-500'
                                    : 'border-gray-300'
                            ]">
                                <Icon v-if="group_same.includes(option.value)" name="fa6-solid:check" class="text-white" />
                            </div>
                            <span class="text-xs font-medium" :class="[
                                group_same.includes(option.value)
                                    ? 'text-sky-700'
                                    : 'text-gray-600'
                            ]">
                                {{ option.name }}
                            </span>
                        </div>
                    </div>
                </div> -->
                <div>
                    <div class="flex items-center gap-2 text-sm font-medium text-gray-500 mb-2">
                        <span>
                            {{ t('customer_service_block.select_address') }}
                        </span>
                        <abbr
                            v-if="addressSelect === 'contract' && typeSelect != 'CONTRACT' && typeSelect != 'CONTRACTREQUEST' && typeSelect != 'SUPPLYCUT'"
                            :title="t('informative_block.info_person_no_contract')" class="flex items-center">
                            <Icon name="fa6-solid:circle-info" class="text-orange-500" />
                        </abbr>
                    </div>
                    <OptionSelectorGroup :options="addressOptions" :selected-value="addressSelect"
                        selection-mode="single" indicator-type="radio" :disabled-values="disabledAddressOptions"
                        @select="changeAddress" />
                </div>
                <div>
                    <div class="text-sm font-medium text-gray-500 mb-2">
                        {{ t('customer_service_block.select_recipients_channels') }}:
                    </div>
                    <OptionSelectorGroup :options="messageTypesOptions" :selected-values="messageTypeSelect"
                        :translate-labels="false" selection-mode="multiple" indicator-type="checkbox"
                        @select="changeMessageType" />
                </div>
            </div>
            <!-- FILTER SELECT -->
            <h3 class="text-md font-medium text-gray-900 mb-3">{{ t('customer_service_block.select_filter_type') }}</h3>
            <div class="grid grid-cols-2 sm:grid-cols-4 gap-2 mb-5">
                <div v-for="option in options" :key="option.value" class="relative" @click="typeSelect = option.value">
                    <div class="cursor-pointer px-2.5 py-2 rounded-md border transition-all duration-200 min-w-[100px] hover:shadow-sm"
                        :class="[
                            typeSelect === option.value
                                ? 'border-sky-500 bg-sky-50 ring-1 ring-sky-500/10'
                                : 'border-gray-200 hover:border-gray-300 hover:bg-gray-50'
                        ]">
                        <div class="flex items-center gap-2">
                            <input type="radio" :value="option.value" v-model="typeSelect" class="hidden" />
                            <div class="flex items-center justify-center w-5 h-5 rounded-full shrink-0" :class="[
                                typeSelect === option.value
                                    ? 'bg-sky-500 text-white shadow-sm shadow-sky-200'
                                    : 'bg-gray-100 text-gray-400'
                            ]">
                                <Icon :name="option.icon" class="w-2.5 h-2.5" />
                            </div>
                            <span class="font-medium text-sm text-gray-700 truncate">{{ t(option.name) }}</span>
                        </div>
                    </div>
                </div>
            </div>
            <div v-if="firstWarning"
                class="bg-sky-50 border-l-4 border-sky-400 px-4 py-2 mb-4 grid grid-cols-[auto,1fr] flex items-center gap-3">
                <Icon name="fa6-solid:magnifying-glass" class="text-lg text-sky-400" />
                <span class="text-sky-500 font-semibold">
                    {{ t('common.start_by_filtering') }}
                </span>
            </div>
            <div v-if="showNoPersonsWarning"
                class="bg-orange-50 border-l-4 border-orange-400 px-4 py-2 mb-4 grid grid-cols-[auto,1fr] flex items-center gap-3">
                <Icon name="fa6-solid:triangle-exclamation" class="text-lg text-orange-400" />
                <span class="text-orange-500 font-semibold">
                    {{ t('common.no_data_found') }}
                </span>
            </div>
            <!-- CONTRACT -->
            <div v-if="typeSelect === 'CONTRACT'">
                <CommunicationProcessCreationSetupContract :contract_data="filter_data" @change="onFilterChange" />
            </div>

            <div v-else-if="typeSelect === 'CONTRACTREQUEST'">
                <CommunicationProcessCreationSetupContractRequest :contract_data="filter_data"
                    @change="onFilterChange" />
            </div>

            <div v-else-if="typeSelect === 'BILLING'">
                <CommunicationProcessCreationSetupBilling :billing_data="filter_data" @change="onFilterChange" />
            </div>

            <div v-else-if="typeSelect === 'ADDRESS'">
                <CommunicationProcessCreationSetupAddress :address_data="filter_data" @change="onFilterChange" />
            </div>

            <div v-else-if="typeSelect === 'PERSON'">
                <CommunicationProcessCreationSetupPerson :person_data="filter_data" @change="onFilterChange" />
            </div>

            <div v-else-if="typeSelect === 'SUPPLYPOINT'">
                <CommunicationProcessCreationSetupSupplyPoint :supply_point_data="filter_data"
                    @change="onFilterChange" />
            </div>

            <div v-else-if="typeSelect === 'SUPPLYCUT'">
                <CommunicationProcessCreationSetupSupplyCut :supply_cut_data="filter_data"
                    @change="onFilterChange" />
            </div>

            <div v-else-if="typeSelect === 'COMMUNICATION'">
                <CommunicationProcessCreationSetupCommunication :communication_data="filter_data"
                    @change="onFilterChange" />
            </div>

            <!-- <div v-else-if="typeSelect === 'CONNECTION'">
            </div> -->

            <AtomsProcessColorBadge class="w-fit flex items-center gap-x-2" v-show="false"
            @refresh="refreshData" :value="t('common.loading')" :color="'blue'" :taskId="filteringTaskId" />

        </div>
        <div class="my-50"></div>
    </div>
</template>
