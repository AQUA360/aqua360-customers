<script setup>
import H1Region from '../atoms/H1Region.vue';
import TableHeader from '../atoms/TableHeader.vue';
import FieldDetail from '../atoms/FieldDetail.vue';
import { useToast } from 'vue-toastification';
import ContractDetail from './ContractDetail.vue';
import SearchEntityInput from './SearchEntityInput.vue';
import SupplyPointDetail from './SupplyPointDetail.vue';

const toast = useToast();
const { t } = useI18n();
const { $FraudApiService, $SupplyPointApiService, $ConfiglistApiService } = useNuxtApp();

const emit = defineEmits(['changed']);
const props = defineProps({
    id: {
        type: Number,
        default: null,
    },
    supply_point_id: {
        type: Number,
        default: null,
    },
    contract_id: {
        type: Number,
        default: null,
    }
});

const loading = ref(true);
const saving = ref(false);
const attemptedSave = ref(false);

const fraud = ref(null)

const supply_point = ref(null)
const contracts = ref([])
const selected_contract = ref(null)
const selected_type = ref(null)
const detection_date = ref(null)
const blockEditContract = ref(false)

const types = ref([])

const selectedSupplyPoint = ref(null)
const continueSaving = ref(false)
const contractDetailId = ref(null)

const getData = async () => {
    loading.value = true;
    try {
        supply_point.value = null

        if (props.supply_point_id || selectedSupplyPoint.value) {
            const response = await $SupplyPointApiService.getDetail(props.supply_point_id || selectedSupplyPoint.value.id);
            supply_point.value = response;

            getSupplyPointContracts()

            if (contracts.value.length == 1) {
                selected_contract.value = contracts.value[0]
            }
        }

        if (props.id) {
            const response = await $FraudApiService.getDetail(props.id);
            fraud.value = response;

            supply_point.value = await $SupplyPointApiService.getDetail(response.supply_point?.id);
            if (fraud.value.contract) {
                selected_contract.value = supply_point.value.contracts.find(contract => contract.id == fraud.value.contract.id);
                blockEditContract.value = true;
            }
            detection_date.value = fraud.value.detection_date;
            getSupplyPointContracts()
        }
    } catch (error) {
        console.log(error);
    } finally {
        loading.value = false;
    }

}

const getTypes = async () => {
    try {
        const response = await $ConfiglistApiService.getAll('fraud/fraud-type');
        response.results.forEach(item => {
            types.value.push({
                label: item.name,
                code: item.id
            })
        })
    } catch (error) {
        console.error(error)
    }
}

const getSupplyPointContracts = async () => {
    const uniqueContractIds = new Set();
    if (props.contract_id) {
        //blockEditContract && selected_contract
        blockEditContract.value = true;
        selectedSupplyPoint.value = supply_point.value;
        selected_contract.value = supply_point.value.contracts.find(contract => contract.id == props.contract_id);
        contracts.value.push(supply_point.value.contracts.find(contract => contract.id == props.contract_id));
    } else {
        for (let contract of supply_point.value.contracts) {
            if (!uniqueContractIds.has(contract.id)) {
                uniqueContractIds.add(contract.id);
                contracts.value.push(contract);
            }
        }
    }
}

const showContractDetail = (id) => {
    if (contractDetailId.value == id) {
        contractDetailId.value = null
    } else {
        contractDetailId.value = id
    }
}

const contractClicked = ((contract) => {
    if (selected_contract.value == contract) {
        selected_contract.value = null
        return
    }
    selected_contract.value = contract
})

const save = async () => {
    attemptedSave.value = true;
    if (!isValid()) return

    try {
        let save_data = {
            id: props.id ? props.id : null,
            detection_date: detection_date.value,
            type: selected_type.value.code,
            contract: selected_contract.value ? selected_contract.value.id : null,
            supply_point: supply_point.value.id,
        }

        let response = await $FraudApiService.save(save_data)
        if (response) {
            emit('changed', response)
        }

    } catch (error) {
        console.log(error)
    }
}

const onSupplyPointSelected = async (item) => {
    selectedSupplyPoint.value = item;
}

const continueSave = async () => {
    if (selectedSupplyPoint.value) {
        await getData()
        continueSaving.value = true
    }
}

const isValid = () => {
    if (detection_date.value == null) return false
    if (selected_type.value == null) return false
    return true
}

onMounted(async () => {
    await getTypes()
    await getData()
})

watch(() => props.supply_point_id, (newVal) => {
    getData()
})

</script>
<template>
    <div v-if="!loading" id="wrapper" class="region__content">
        <div class="mb-6">
            <H1Region>
                {{ props.id
                    ? `${$t('common.modify')} (${t('fraud')})` : $t('customer_service_block.new_fraud_title') }}
            </H1Region>
        </div>


        <div v-if="!props.supply_point_id && !props.id && !continueSaving" class="mb-6">
            <label class="block text-sm font-medium text-slate-500 mb-2">
                {{ t('service_block.select_supply_point') }}</label>
            <SearchEntityInput :service="$SupplyPointApiService" @select="onSupplyPointSelected" :methodName="'getData'"
                :title="$t('search_block.search_supply_point')" :result_value="'address_complete'" class="mt-auto" />

            <div v-if="selectedSupplyPoint" class="my-4 p-2 bg-green-50 rounded group relative">
                <SupplyPointDetail :id="selectedSupplyPoint.id" :isSubRegion="true" />
                <button @click="selectedSupplyPoint = null"
                    class="absolute cursor-pointer shadow-md border text-sm w-8 h-8 bg-white right-3 top-3 rounded-md text-red-600 opacity-0 transition-all duration-300 group-hover:opacity-100 hover:bg-slate-50">
                    <Icon name="fa6-solid:xmark" class="m-auto" />
                </button>
            </div>

            <hr class="my-2" />
            <div class="flex flex-row-reverse gap-3 mt-4">
                <button @click="continueSave" :disabled="!selectedSupplyPoint" class="button-primary">
                    {{ $t('common.continue') }}
                </button>
            </div>
        </div>
        <div v-else>
            <div v-if="selectedSupplyPoint"
                class="my-4 pt-2 bg-sky-50 rounded flex justify-between px-10 border border-sky-500 items-center">
                <FieldDetail :label="$t('common.short_supply')" :value="selectedSupplyPoint.token"></FieldDetail>
                <FieldDetail :label="$t('address_block.address')" :value="selectedSupplyPoint.address_complete">
                </FieldDetail>
            </div>
            <!-- CONTRACT SELECT -->
            <div v-if="blockEditContract && selected_contract" class="mb-6">
                <label class="block text-sm font-medium text-slate-500 mb-2">{{
                    t('customer_service_block.contract_responsible_selected')
                    }}</label>
                <details class="group p-4 mb-6  rounded">
                    <summary
                        class="bg-slate-50 p-2 flex items-center justify-between cursor-pointer border-b border-slate-300">
                        <Icon name="fa6-solid:angle-down"
                            class="text-gray-500 w-4 h-4 transform transition-transform duration-200 group-open:rotate-180" />
                        <span>{{ selected_contract.token }}</span>
                        <span> {{ selected_contract.holder }} ({{ selected_contract.holder_token }})</span>
                        <span>
                            <AtomsColorBadge :value="selected_contract.status_name"
                                :color="selected_contract.status_color" />
                        </span>
                    </summary>

                    <div class="mb-2 p-2 bg-green-50 rounded-lg mt-2">
                        <ContractDetail :id="selected_contract.id" :isSubRegion="true" :showPayment="false"
                            :showCommunication="false" :showImportantObservations="true" />
                    </div>
                </details>
            </div>

            <div v-else class="mb-6">
                <label class="block text-sm font-medium text-slate-500 mb-2">
                    {{ t('customer_service_block.select_contract_responsible') }} ({{ t('common.optional') }})
                </label>
                <div id="list" class="rounded border-b overflow-hidden"
                    style="overflow-y: auto; width: calc(-295px + 100vw); max-width: 100%;">
                    <div
                        class="grid grid-cols-[auto,10px,1fr,1fr,100px] gap-3 text-sm font-semibold text-gray-700 bg-gray-100 border-b border-gray-200 px-2 py-3 items-center">
                        <span></span>
                        <span></span>
                        <span>
                            {{ t('contract') }}
                        </span>
                        <span>
                            {{ t('contract_block.holder') }}
                        </span>
                        <span>
                            {{ t('common.status') }}
                        </span>
                    </div>

                    <div v-for="item in contracts" :key="item.id" @click="contractClicked(item)"
                        class="grid grid-cols-[auto,10px,1fr,1fr,100px] cursor-pointer gap-3 text-base border-b items-center bg-white mr-3"
                        :class="{ 'bg-yellow-50': selected_contract == item }">
                        <span>
                            <Icon v-if="selected_contract == item" name="fa6-solid:angle-right"
                                class="text-slate-500" />
                        </span>
                        <button @click.stop="showContractDetail(item.id)" class="w-5 h-5 group">
                            <Icon :name="contractDetailId == item.id ? 'fa6-solid:eye-slash' : 'fa6-solid:eye'"
                                class="text-slate-500 group-hover:text-sky-500" />
                        </button>
                        <span class="p-1 transition-all duration-200" :class="{ 'ml-5': selected_contract == item }">
                            {{ item.token }}</span>
                        <span class="p-1 transition-all duration-200" :class="{ 'ml-5': selected_contract == item }">
                            {{ item.holder }} ({{ item.holder_token }})
                        </span>
                        <span class="p-1 transition-all duration-200" :class="{ 'ml-5': selected_contract == item }">
                            <AtomsColorBadge :value="item.status_name" :color="item.status_color" />
                        </span>
                        <div v-if="contractDetailId == item.id" class="col-span-5 p-2 rounded">
                            <ContractDetail :id="item.id" :isSubRegion="true" :reducedDetail="true"
                                :showImportantObservations="true" />
                        </div>
                    </div>
                    <div v-if="contracts.length == 0" class="text-center py-2 text-sm text-gray-500">
                        {{ $t('common.no_data') }}
                    </div>
                </div>
            </div>

            <div class="mb-6 grid grid-cols-2 gap-3">
                <AtomsInputDate v-model="detection_date" :label="t('customer_service_block.detection')" class="mb-2"
                    :invalid="attemptedSave && (detection_date == null || detection_date == '')" :required="true" />
                <div>
                    <label class="block text-sm font-medium text-slate-600 mb-2">{{ $t('common.type') }} <span class="text-red-500">*</span></label>
                    <v-select class="block w-full mr-1 custom-select required" v-model="selected_type" :options="types"
                     :class="{ 'invalid': attemptedSave && selected_type == null }" />
                </div>

            </div>

            <hr class="my-2" />
            <div class="flex flex-row-reverse gap-3 mt-4">
                <button @click="save" :disabled="saving" class="button-primary">
                    <Icon name="fa6-solid:floppy-disk" />&nbsp; {{
                        $t('common.save') }}
                </button>
            </div>
        </div>

    </div>
    <div v-else class="p-4">
        <div class="flex justify-center items-center">
            <Icon name="fa6-solid:spinner" class="animate-spin text-2xl text-slate-500" />
            <span class="ml-2">{{ $t('common.loading') }}...</span>
        </div>
    </div>
</template>