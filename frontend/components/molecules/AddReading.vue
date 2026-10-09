<script setup>

import H1Region from '../atoms/H1Region.vue';
import FieldDetail from '../atoms/FieldDetail.vue';
import SupplyPointRegion from '../organisms/SupplyPointRegion.vue';
import MeterRegion from '../organisms/MeterRegion.vue';
import ReadingDetail from './ReadingDetail.vue';
import EstimateSingleReadingDialog from './EstimateSingleReadingDialog.vue';
import { useToast } from 'vue-toastification';

const props = defineProps({
    contract: Object,
    contract_ids: Array,
    supply_point_ids: Array,
    isSubRegion: {
        type: Boolean,
        default: false
    }
})

const toast = useToast();
const { t } = useI18n();
const emit = defineEmits(['show-subregion']);
const { $SupplyPointApiService, $ReadingApiService } = useNuxtApp();

const loading = ref(false);
const estimating = ref(false);
const saving = ref(null);
const supply_points = ref([]);
const last_readings = ref({})
const new_readings = ref({})

const showRegion = ref(false);
const showRegionDetailComponent = ref(null);
const regionDetailId = ref(null);
//
//IF COMPONENT STARTS BEING USED OUT OF CONTRACT, MATCH LAST READINGS WITH PASSED CONTRACTS OR FIND A WAY???
//
const getData = async (load = true) => {
    loading.value = load;
    try {
        if (props.contract_ids) {
            const response = await $SupplyPointApiService.getByContract(props.contract_ids);
            supply_points.value = response.results;
            for (const supply_point of supply_points.value) {
                console.log("supply_point", supply_point);
                if (props.contract) {
                    let supply_point_contract_reading = supply_point.last_readings_by_contract.find(reading => reading.contract_id == props.contract?.id);
                    console.log("supply_point_contract_reading", supply_point.last_readings_by_contract);
                    if (supply_point_contract_reading) {
                        const response = await $ReadingApiService.getDetail(supply_point_contract_reading.id);
                        console.log("response", response);
                        last_readings.value[supply_point.id] = response;
                    } else {
                        last_readings.value[supply_point.id] = {
                            id: null,
                            reading_date: null,
                            reading_value: null,
                            leak_value: null,
                            is_control: false,
                            is_estimated: false,
                        }
                    }
                }
                new_readings.value[supply_point.id] = {
                    reading_date: new Date(Date.now()).toISOString().split('T')[0],
                    reading_value: null,
                    leak_value: null,
                    is_control: false,
                    is_estimated: false,
                    add_to_all: false,
                }
            }
        }
    } catch (error) {
        console.error(error);
    } finally {
        loading.value = false;
    }
}

const showingDetailId = ref(null);
const onShowDetail = (id) => {
    showingDetailId.value = id;
}

const showDetail = (component, id) => {
    showRegion.value = true;
    showRegionDetailComponent.value = component?.component ? component.component : component;
    regionDetailId.value = component?.component ? component.id : id;
    emit('show-subregion', true);
}

const closeSubRegion = () => {
    showRegion.value = false;
    showRegionDetailComponent.value = null;
    regionDetailId.value = null;
    emit('show-subregion', false);
}

const showEstimateDialog = ref(false);
const estimateSupplyPointId = ref(null);

const estimateReading = (supply_point_id) => {
    estimateSupplyPointId.value = supply_point_id;
    showEstimateDialog.value = true;
}

const handleEstimateConfirm = async (params) => {
    const supply_point_id = estimateSupplyPointId.value;
    estimating.value = true;
    try {
        let used_date = null;
        try {
            used_date = new_readings.value[supply_point_id].reading_date;
        } catch (error) {
            used_date = null;
        }
        const response = await $ReadingApiService.estimateReading({ supply_points: [supply_point_id], reading_date: used_date, ...params });
        if (response) {
            toast.success(t('billing_block.correct_estimate'));
            await getData(false);
        }
    } catch (error) {
        console.error(error);
    } finally {
        estimating.value = false;
        showEstimateDialog.value = false;
        estimateSupplyPointId.value = null;
    }
}

const save = async (supply_point_id) => {
    let save_data = {
        supply_point: supply_point_id,
        contract: props.contract ? props.contract.id : null,
        meter: supply_points.value.find(supply_point => supply_point.id == supply_point_id).meter_id,
        reading_date: new_readings.value[supply_point_id].reading_date,
        reading_value: new_readings.value[supply_point_id].reading_value,
        leak_value: new_readings.value[supply_point_id].leak_value,
        previous_reading_id: !last_readings.value[supply_point_id].is_control ? last_readings.value[supply_point_id].id : null,
        add_to_all: new_readings.value[supply_point_id].add_to_all,
        is_control: new_readings.value[supply_point_id].is_control,
        is_estimated: new_readings.value[supply_point_id].is_estimated,
        origin: 'manual',
        token: `${supply_points.value.find(supply_point => supply_point.id == supply_point_id).meter_code}/MANUAL`,
    }

    try {
        const response_check = await $ReadingApiService.checkAllowSave(save_data);
        if (!response_check.allow) {
            toast.warning(t('warning_block.warning_reading_too_close_to_last'),{timeout: 6500});
            return;
        }

    } catch (error) {
        console.error(error);
        return;
    }
    if (new_readings.value[supply_point_id].reading_date == null || new_readings.value[supply_point_id].reading_date == '' || new_readings.value[supply_point_id].reading_value == null) {
        toast.warning(t('warning_block.warning_readin_empty'));
        return;
    }
    let confirm_message = t('confirmation_text_block.confirm_manual_reading');
    if (new_readings.value[supply_point_id].reading_date < last_readings.value[supply_point_id].reading_date) {
        confirm_message = t('confirmation_text_block.extra_confirm_manual_reading');
    }
    if (!confirm(confirm_message)) return
    saving.value = supply_point_id;
    
    try {
        let response = await $ReadingApiService.save(save_data);
        if (response) {
            toast.success(t('billing_block.correct_manual_reading'));
            await getData(false);
        }
    } catch (error) {
        console.error(error);
    } finally {
        saving.value = null;
    }
}

onMounted(async () => {
    getData()
})

</script>

<template>
    <div class="">
        <div class="transition-all duration-500 ease" :class="{ 'mr-[48%]': showRegion }">

            <div v-if="loading" class="flex justify-center items-center py-12">
                <div class="flex items-center space-x-3 text-slate-600">
                    <Icon name="fa6-solid:spinner" class="animate-spin text-lg" />
                    <span class="text-sm font-medium">{{ $t('common.loading') }}...</span>
                </div>
            </div>

            <div v-else class="space-y-6 h-[90vh]">
                <div class="border-b border-slate-200 pb-4">
                    <H1Region>
                        {{ t('common.add') }} {{ t('readings') }}
                    </H1Region>

                    <div v-if="contract" class="flex items-center space-x-6 text-xs text-slate-500">
                        <div class="flex items-center space-x-1">
                            <span class="font-medium">{{ t('contract') }}:</span>
                            <span class="font-mono">{{ contract.token }}</span>
                        </div>
                        <div class="flex items-center space-x-1">
                            <span class="font-medium">{{ t('common.supply_points') }}:</span>
                            <span class="font-mono">{{ supply_points.length }}</span>
                        </div>
                        <div class="flex items-center space-x-1">
                            <span class="font-medium">{{ t('common.meters') }}:</span>
                            <span class="font-mono">{{supply_points.filter(supply_point => supply_point.meter_id).length
                                }}</span>
                        </div>
                    </div>
                </div>

                <div class="space-y-4 max-h-[88%] overflow-y-auto scrollbar-hide">
                    <div v-for="supply_point in supply_points" :key="supply_point.id"
                        class="bg-white border border-slate-200 rounded-lg">

                        <div class="px-4 py-3 border-b border-slate-100 bg-slate-50 rounded-t-lg">
                            <div class="flex items-center justify-between">
                                <div class="flex flex-col">
                                    <div class="flex items-center gap-2 text-sm">
                                        <span class="text-slate-500">
                                            {{ t('common.short_supply') }}
                                        </span>
                                        <button
                                            class="text-start font-medium text-sky-500 hover:text-sky-700 hover:underline"
                                            @click="showDetail('SupplyPointRegion', supply_point.id)">{{
                                                supply_point.address_complete }}</button>
                                    </div>
                                    <div class="flex items-center gap-2 mt-1">
                                        <span class="text-xs text-slate-500">
                                            {{ t('meter') }}
                                        </span>
                                        <button
                                            class="text-start text-xs text-sky-500 hover:text-sky-700 hover:underline"
                                            @click="showDetail('MeterRegion', supply_point.meter_id)">{{
                                                supply_point.meter_code
                                            }}</button>
                                    </div>
                                </div>
                                
                                <div class="flex items-center gap-x-2">
                                    <abbr :title="(new_readings[supply_point.id].reading_date == '' || new_readings[supply_point.id].reading_date == null) ? 
                                        t('warning_block.warning_estimate_date') : t('billing_block.estimate')">
                                        <button @click="estimateReading(supply_point.id)"
                                            class="inline-flex items-center w-7 h-7 justify-center text-xs font-medium text-white bg-orange-500 rounded-full hover:bg-orange-700 focus:outline-none disabled:opacity-70 disabled:cursor-not-allowed"
                                             >
                                             <!-- :disabled="new_readings[supply_point.id].reading_date == '' || new_readings[supply_point.id].reading_date == null"> -->
                                            <Icon :name="estimating ? 'fa6-solid:spinner' : 'fa6-solid:calculator'" class="w-3 h-3" :class="{ 'animate-spin': estimating }" />
                                        </button>
                                    </abbr>
                                    <abbr :title="t('common.save')">
                                        <button
                                            class="inline-flex items-center w-7 h-7 justify-center text-xs font-medium text-white bg-sky-500 rounded-full hover:bg-sky-700 focus:outline-none"
                                            @click="save(supply_point.id)">
                                            <Icon
                                                :name="saving == supply_point.id ? 'fa6-solid:spinner' : 'fa6-solid:floppy-disk'"
                                                class="w-3 h-3" :class="{ 'animate-spin': saving == supply_point.id }" />
                                        </button>
                                    </abbr>
                                </div>
                            </div>
                        </div>

                        <div class="p-4">
                            <div class="grid grid-cols-3 gap-x-4">
                                <div>
                                    <AtomsInputDate v-model="new_readings[supply_point.id].reading_date"
                                        :label="t('billing_block.reading_date')" class="text-xs" />
                                </div>
                                <div>
                                    <label class="block text-sm font-medium text-slate-600 mb-2">
                                        {{ t('reading') }}</label>
                                    <input type="number"
                                        class="w-full px-3 py-2.5 text-sm border border-slate-300 rounded-md focus:outline-none focus:border-sky-500"
                                        v-model="new_readings[supply_point.id].reading_value">
                                </div>
                                <div>
                                    <label class="block text-sm font-medium text-slate-600 mb-2">
                                        {{ t('billing_block.leak') }}</label>
                                    <input type="number"
                                        class="w-full px-3 py-2.5 text-sm border border-slate-300 rounded-md focus:outline-none focus:border-sky-500"
                                        v-model="new_readings[supply_point.id].leak_value">
                                </div>
                                <div class="flex items-center ml-2 text-slate-500">
                                    <input v-model="new_readings[supply_point.id].is_control" type="checkbox"
                                        id="is_control" name="is_control" class="checkbox" />
                                    <label for="is_control" class="ml-2">
                                        {{ t('billing_block.control_reading') }}
                                    </label>
                                </div>
                                <div class="flex items-center ml-2 text-slate-500">

                                    <input v-model="new_readings[supply_point.id].is_estimated" type="checkbox"
                                        id="is_estimated" name="is_estimated" class="checkbox" />
                                    <label for="is_estimated" class="ml-2">
                                        {{ t('billing_block.estimated_reading') }}
                                    </label>
                                </div>
                                <div v-if="supply_point.contracts.length > 1"
                                    class="flex items-center ml-2 text-slate-500">
                                    <input v-model="new_readings[supply_point.id].add_to_all" type="checkbox"
                                        id="add_to_all" name="add_to_all" class="checkbox" />
                                    <abbr class="flex items-center ml-2 truncate"
                                        :title="t('informative_block.add_to_all_info')">
                                        {{ t('billing_block.add_to_all') }}
                                    </abbr>
                                </div>
                            </div>
                        </div>

                        <div class="px-4 pb-4">
                            <div class="bg-slate-50 rounded-md p-3">
                                <div class="flex justify-between items-center">
                                    <h4 class="text-xs font-semibold text-slate-700 mb-3 flex items-center gap-2">
                                        <Icon name="fa6-solid:clock" class="w-3 h-3 text-slate-500" />
                                        {{ t('billing_block.last_contract_reading') }}
                                    </h4>
                                    <abbr :title="t('billing_block.check_all_readings')">
                                        <button
                                            class="inline-flex items-center w-7 h-7 justify-center text-xs font-medium text-slate-500 bg-white border border-slate-500 rounded-full hover:bg-slate-700 hover:text-white hover:border-none focus:outline-none"
                                            @click="showDetail('ReadingDetail', supply_point.id)">
                                            <Icon name="fa6-solid:eye" class="w-3 h-3" />
                                        </button>
                                    </abbr>
                                </div>

                                <div v-if="last_readings[supply_point.id].id" class="grid grid-cols-2 gap-x-2">
                                    <!-- <div class="space-y-1">
                                        <span class="text-xs text-slate-500">{{ t('Data') }}</span>
                                        <p class="text-sm font-medium text-slate-900">{{
                                            formatDate(last_readings[supply_point.id].reading_date) }}</p>
                                    </div> -->
                                    <FieldDetail :label="t('common.date')"
                                        :value="formatDate(last_readings[supply_point.id].reading_date)" />
                                    <FieldDetail :label="t('reading')"
                                        :value="last_readings[supply_point.id].reading_value" />
                                    <FieldDetail :label="t('billing_block.consumption_days')"
                                        :value="last_readings[supply_point.id].consumption_days ? (last_readings[supply_point.id].consumption_days).toString() : t('common.unregistered')" />
                                    <FieldDetail :label="t('billing_block.consumption')">
                                        <div class="flex items-center gap-x-1">
                                            <span>
                                                {{ last_readings[supply_point.id].calculated_value || t('common.unregistered')
                                                }}</span>

                                            <span v-if="last_readings[supply_point.id].estimated_used"
                                                class="text-sm font-bold text-yellow-600 flex items-center">
                                                (<abbr :title="t('billing_block.estimated_correction')">
                                                    {{ t('billing_block.estimated_correction_abbr') }}
                                                </abbr>:
                                                -{{ parseInt(last_readings[supply_point.id].estimated_used) }} m3)</span>
                                        </div>
                                    </FieldDetail>
                                    <FieldDetail :label="t('billing_block.leak')"
                                        :value="last_readings[supply_point.id].leak_value ?
                                            last_readings[supply_point.id].leak_value + ' m³' : t('common.unregistered')" />
                                    <FieldDetail :label="t('common.origin')" :value="last_readings[supply_point.id].origin" />
                                    <div class="flex items-center ml-2 text-slate-500 opacity-70">
                                        <input v-model="last_readings[supply_point.id].is_control" type="checkbox"
                                            id="is_control" name="is_control" class="checkbox" :disabled="true" />
                                        <label for="is_control" class="ml-2">
                                            {{ t('billing_block.control_reading') }}</label>
                                    </div>
                                    <div class="flex items-center ml-2 text-slate-500 opacity-70">
                                        <input v-model="last_readings[supply_point.id].is_estimated" type="checkbox"
                                            id="is_estimated" name="is_estimated" class="checkbox" :disabled="true" />
                                        <label for="is_estimated" class="ml-2">
                                            {{ t('billing_block.estimated_reading') }}</label>
                                    </div>
                                </div>
                                <div v-else class="text-sm text-slate-500">
                                    {{ t('common.no_records') }}
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <div v-if="showRegion == true" role="region" id="subregion"
            class="h-full border-l border-gray-100 transition-all duration-500 ease py-2 text-base bg-white fixed top-0 right-0 w-[48%] z-10 overflow-y-auto overflow-x-hidden"
            :class="{ 'translate-x-0': showRegion, 'translate-x-full': !showRegion }">
            <div id="region_nav" class="mb-3 px-3">
                <button @click="closeSubRegion()" class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300">
                    <Icon name="fa6-solid:angles-right" class="text-slate-500" />
                </button>
            </div>
            <div class="px-10">
                <SupplyPointRegion v-if="showRegionDetailComponent === 'SupplyPointRegion'" :id="regionDetailId"
                    :isSubRegion="true" />
                <MeterRegion v-if="showRegionDetailComponent === 'MeterRegion'" :id="regionDetailId"
                    :isSubRegion="true" />
                <ReadingDetail v-if="showRegionDetailComponent === 'ReadingDetail'" :contract_ids="[]"
                    :supply_point_id="regionDetailId" :isSubRegion="true" />
            </div>
        </div>

    </div>

    <EstimateSingleReadingDialog
        :show="showEstimateDialog"
        :loading="estimating"
        @close="showEstimateDialog = false"
        @confirm="handleEstimateConfirm"
    />
</template>