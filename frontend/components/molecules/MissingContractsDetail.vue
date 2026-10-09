<script setup>
import { useI18n } from 'vue-i18n';
import { useToast } from 'vue-toastification';
import FieldDetail from '../atoms/FieldDetail.vue';
import ContractRegion from '../organisms/ContractRegion.vue';
import AppLoading from '../atoms/AppLoading.vue';
const { t } = useI18n()
const toast = useToast()

const props = defineProps({
    loading: Boolean,
    missingContracts: {
        type: Array,
        default: () => []
    },
    type: String,
    billingId: Number,
    startDate: String,
    endDate: String
});

const { $BillingApiService, $ConfigProjectApiService, $apiManager } = useNuxtApp();
const emit = defineEmits(['show-subregion', 'reload']);
const pending = ref(props.loading);
const showSubRegion = ref(false);
const regionDetailId = ref(null);
const showRegionDetailComponent = ref(null)

const saving = ref(false);
const selectedContracts = ref([]);
const filterContracts = ref([])
const appliedFilters = ref([])

const statusTerminated = ref(null)

const searchQuery = ref('')

const availableFilters = computed(() => {
    const reasons = new Set();

    missingContractsSafe.value.forEach((contract) => {
        if (!Array.isArray(contract?.missing_reasons)) return;

        contract.missing_reasons.forEach((reason) => {
            if (typeof reason === 'string' && reason.trim()) {
                reasons.add(reason);
            }
        });
    });

    return Array.from(reasons);
});

const displayedContracts = computed(() => {
    const query = searchQuery.value.trim().toLowerCase();
    const hasSearch = query.length > 0;
    const hasFilters = appliedFilters.value.length > 0;

    if (!hasSearch && !hasFilters) return missingContractsSafe.value;

    return missingContractsSafe.value.filter((contract) => {
        if (hasSearch) {
            const token = String(contract?.contract_token ?? '').toLowerCase();
            const holder_name = String(contract?.contract_holder_name ?? '').toLowerCase();
            const holder_token = String(contract?.contract_holder_token ?? '').toLowerCase();
            if (!token.includes(query) && !holder_name.includes(query) && !holder_token.includes(query)) return false;
        }

        if (hasFilters) {
            if (!Array.isArray(contract?.missing_reasons)) return false;
            return contract.missing_reasons.some((reason) => {
                return typeof reason === 'string' && appliedFilters.value.includes(reason);
            });
        }

        return true;
    });
});
const allSelected = computed(() => {
    return selectedContracts.value.length == displayedContracts.value.filter((contract) => !checkDisabled(contract.missing_reasons)).length || selectedContracts.value.length == missingContractsSafe.value.filter((contract) => !checkDisabled(contract.missing_reasons)).length;
});

const openSubRegion = (component, id) => {
    //emit('show-subregion', id);
    showSubRegion.value = true;
    regionDetailId.value = id;
    showRegionDetailComponent.value = component;
};

const closeSubRegion = () => {
    showSubRegion.value = false;
    regionDetailId.value = null;
    showRegionDetailComponent.value = null;
};

const missingContractsSafe = computed(() => {
    if (!Array.isArray(props.missingContracts)) return [];
    return props.missingContracts;
});

const formattedTypeTitle = computed(() => {
    if (!props.type) return '';
    const translated = `billing_block.${props.type}`;
    return translated;
});

const getReasonKey = (reason, index) => {
    if (typeof reason === 'string') return `${reason}-${index}`;
    if (reason && typeof reason === 'object') return `${Object.keys(reason)[0] || 'reason'}-${index}`;
    return `reason-${index}`;
};

const getReasonLabel = (reason) => {
    if (typeof reason === 'string') {
        return t(`billing_block.cause_${reason}`);
    }

    if (reason && typeof reason === 'object') {
        if ('current_route' in reason) {
            return `${t('billing_block.different_route')}: ${reason.current_route}`;
        }

        const [reasonKey, reasonValue] = Object.entries(reason)[0] || [];
        if (reasonKey) {
            return reasonValue ? `${t(`billing_block.cause_${reasonKey}`)}: ${reasonValue}` : t(`billing_block.cause_${reasonKey}`);
        }
    }

    return t('common.no_data');
};

const checkDisabled = (reasons) => {
    if (!Array.isArray(reasons)) return false;
    return reasons.some((reason) => {
        return (typeof reason === 'object' && 'current_route' in reason) || reason === 'no_price_rate' || reason === 'block_billing' || reason === 'no_meter';
    });
};

const selectAll = () => {
    if (saving.value) return;
    if (allSelected.value) {
        selectedContracts.value = [];
        return;
    }

    selectedContracts.value = displayedContracts.value.filter((contract) => !checkDisabled(contract.missing_reasons)).map((contract) => contract.contract_id);
};

const getAllowedFilters = () => {
    filterContracts.value = availableFilters.value;
}

const toggleFilter = (filter) => {
    if (!saving.value) selectedContracts.value = [];
    if (appliedFilters.value.includes(filter)) {
        appliedFilters.value = appliedFilters.value.filter((f) => f !== filter);
        return;
    }

    appliedFilters.value.push(filter);
};

const downloadCSV = async () => {
    if (saving.value) return;
    saving.value = true;
    try {
        const response = await $BillingApiService.checkMissingContracts(props.billingId, props.type, true);
        if (response) {
            let response_buffer = await response.arrayBuffer();
            downloadFile(response_buffer, `${t('billing_block.possible_non_billed').replace(' ', '_').toUpperCase()}.xlsx`);
        }
    } catch (error) {
        console.error(error);
    } finally {
        saving.value = false;
    }
}

const downloadFile = (buffer, fileName) => {
    const blob = new Blob([buffer], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = fileName;
    a.click();
}

const generateNewBatch = async () => {
    if (selectedContracts.value.length == 0) return;

    if (!confirm(`${t('informative_block.info_generate_missing_batch')}\n${t('confirmation_text_block.confirm_continue')}`)) return;
    saving.value = true;
    try {
        const save_data = {
            billing_id: props.billingId,
            contract_ids: selectedContracts.value,
            start_date: props.startDate,
            end_date: props.endDate
        }
        const response = await $BillingApiService.generateMissingBatch(save_data);
        if (response) {
            let url = `/reading/reading-batches/?id=${response.new_reading_batch}`;
            const newWindow = window.open(url, '_blank');
            if (newWindow) {
                newWindow.focus();
            }
            emit('reload');
        }
    } catch (error) {
        console.error(error);
    } finally {
        saving.value = false;
    }
}

const handleEstimatedReading = async (contractId) => {
    if (saving.value) return;
    saving.value = true;
    try {
        await $BillingApiService.addEstimatedReading(props.billingId, contractId);
        toast.success(t('billing_block.correct_estimate'));
        emit('reload');
    } catch (error) {
        console.error(error);
        toast.error(error?.response?.data?.detail || error?.message || t('billing_block.error_recalculate_smart'));
    } finally {
        saving.value = false;
    }
};

const handleAddToBatch = async (contractId) => {
    if (saving.value) return;
    saving.value = true;
    try {
        await $BillingApiService.addToBatch(props.billingId, contractId);
        toast.success(t('billing_block.correct_add_to_batch'));
        emit('reload');
    } catch (error) {
        console.error(error);
        toast.error(error?.response?.data?.detail || error?.message || t('billing_block.error_recalculate_smart'));
    } finally {
        saving.value = false;
    }
};

const hasNoPriceRate = (reasons) => {
    if (!Array.isArray(reasons)) return false;
    return reasons.some((reason) => reason === 'no_price_rate');
};

const handleProcessContract = async (contractId) => {
    if (saving.value) return;
    const contract = missingContractsSafe.value.find((c) => c.contract_id === contractId);
    if (hasNoPriceRate(contract?.missing_reasons)) return;
    saving.value = true;
    try {
        await $BillingApiService.processContract(props.billingId, contractId);
        toast.success(t('billing_block.correct_process_contract'));
        emit('reload');
    } catch (error) {
        console.error(error);
        toast.error(error?.response?.data?.detail || error?.message || t('billing_block.error_recalculate_smart'));
    } finally {
        saving.value = false;
    }
};

const taskPending = ref(false);
const taskProgress = ref(0);
const taskError = ref(false);
let taskInterval = null;

const cleanTaskInterval = () => {
    if (taskInterval) {
        clearInterval(taskInterval);
        taskInterval = null;
    }
};

onBeforeUnmount(() => {
    cleanTaskInterval();
});

const processSelected = async () => {
    const processableIds = selectedContracts.value.filter((id) => {
        const contract = missingContractsSafe.value.find((c) => c.contract_id === id);
        return !hasNoPriceRate(contract?.missing_reasons);
    });
    if (processableIds.length == 0) return;
    saving.value = true;
    taskPending.value = true;
    taskProgress.value = 0;
    taskError.value = false;
    try {
        const response = await $BillingApiService.processSelectedContracts(props.billingId, processableIds);
        console.log("Response from processSelectedContracts:", response);

        let resData = response;
        if (typeof resData === 'string') {
            try {
                resData = JSON.parse(resData);
            } catch (e) {
                console.error("Failed to parse response as JSON:", e);
            }
        }

        const taskId = resData?.task_id || resData?.task?.id;
        console.log("Extracted taskId:", taskId);

        if (taskId) {
            taskInterval = setInterval(async () => {
                try {
                    const status = await $apiManager.checkTask(taskId);
                    console.log("Task status response:", status);
                    if (status) {
                        taskProgress.value = status.percent || 0;
                        if (status.state === 'SUCCESS') {
                            cleanTaskInterval();
                            taskPending.value = false;
                            toast.success(t('billing_block.correct_process_contract') || 'Processat correctament');
                            selectedContracts.value = [];
                            emit('reload');
                        } else if (status.state === 'FAILURE') {
                            cleanTaskInterval();
                            taskPending.value = false;
                            taskError.value = true;
                            toast.error(t('billing_block.error_recalculate_smart'));
                        }
                    }
                } catch (err) {
                    console.error("Error checking task status:", err);
                    cleanTaskInterval();
                    taskPending.value = false;
                }
            }, 1000);
        } else {
            toast.success(t('billing_block.correct_process_selected') || 'Procés dels contractes seleccionats iniciat correctament');
            taskPending.value = false;
            selectedContracts.value = [];
            emit('reload');
        }
    } catch (error) {
        console.error(error);
        toast.error(error?.response?.data?.detail || error?.message || t('billing_block.error_recalculate_smart'));
        taskPending.value = false;
    } finally {
        saving.value = false;
    }
};

onMounted(async () => {
    statusTerminated.value = await $ConfigProjectApiService.get('contract_terminated_status');
});

watch(() => props.loading, (newVal) => {
    pending.value = newVal;
});

watch(() => props.missingContracts, () => {
    getAllowedFilters();
    appliedFilters.value = [];
}, { immediate: true });

</script>

<template>
    <div class="region__content h-full">
        <div v-if="pending || loading || taskPending"
            class="h-full min-h-[400px] flex flex-col items-center justify-center p-6 text-center">
            <AppLoading v-if="pending || loading" :text="$t('common.loading')" />
            <div v-else class="w-full max-w-sm space-y-4">
                <p class="font-semibold text-slate-700">{{ t('common.processing') || 'Processant...' }}</p>
                <div class="w-full bg-slate-100 rounded-full h-2 overflow-hidden shadow-inner">
                    <div class="bg-indigo-600 h-2 rounded-full transition-all duration-300"
                        :style="{ width: `${taskProgress}%` }"></div>
                </div>
                <p class="text-xs text-slate-500 font-semibold font-mono">{{ taskProgress }}%</p>
            </div>
        </div>
        <div v-else class="pr-2 relative pb-24 h-full overflow-y-auto">
            <section>
                <header class="mb-3 flex flex-wrap items-center justify-between gap-3 pb-1">
                    <div>
                        <h2 class="text-lg font-semibold text-slate-900">
                            {{ t('billing_block.possible_non_billed') }}
                        </h2>
                        <div class="flex items-start justify-start gap-x-1 font-semibold text-slate-400">
                            <span>{{ t('common.from') }}</span>
                            <span>{{ formatDate(startDate) }}</span>
                            <span>{{ t('common.to') }}</span>
                            <span>{{ formatDate(endDate) }}</span>
                        </div>
                    </div>
                    <div class="flex items-center gap-2">
                        <p v-if="props.type"
                            class="inline-flex items-center gap-1 rounded-full bg-slate-100 px-2.5 py-1 text-xs font-medium text-slate-700">
                            <span class="text-slate-500">{{ t('common.type') }}:</span>
                            <span>{{ t(formattedTypeTitle) }}</span>
                        </p>
                        <span
                            class="inline-flex items-center rounded-full bg-rose-100 px-2.5 py-1 text-xs font-semibold text-rose-700">
                            {{ missingContractsSafe.length }}
                        </span>
                    </div>
                </header>

                <div class="flex items-center gap-x-2 justify-between">

                    <div>
                        <span class="input-group flex flex-start items-center gap-2 w-60">
                            <Icon name="fa6-solid:magnifying-glass" class="text-slate-500" />
                            <input v-model="searchQuery" id="searchQuery" type="text" name="search"
                                :placeholder="$t('common.start_search')"
                                class="w-full p-1 rounded-md focus:outline-none focus-visible:border-0 "
                                autocomplete="off" />
                        </span>
                    </div>

                    <div class="flex flex-row-reverse gap-x-2">
                        <div :class="{
                            'opacity-60': selectedContracts.length == 0 || saving
                        }">
                            <button class="button-default" :disabled="selectedContracts.length == 0 || saving" :class="{
                                'cursor-not-allowed': selectedContracts.length == 0 || saving
                            }" @click="generateNewBatch">
                                {{ t('billing_block.generate_missing_batch') }}
                            </button>
                        </div>
                        <div :class="{
                            'opacity-60': selectedContracts.length == 0 || saving
                        }">
                            <button
                                class="button-default bg-indigo-600 border-indigo-600 hover:bg-indigo-700 hover:border-indigo-700 text-white"
                                :disabled="selectedContracts.length == 0 || saving" :class="{
                                    'cursor-not-allowed': selectedContracts.length == 0 || saving
                                }" @click="processSelected">
                                {{ t('billing_block.process_contract') }}
                            </button>
                        </div>
                        <button class="button-default" :disabled="saving" :class="{
                            'cursor-not-allowed': saving
                        }" @click="downloadCSV">
                            {{ t('export_csv') }}
                        </button>
                    </div>
                </div>


                <div class="my-2 flex flex-wrap items-start justify-between gap-2">
                    <div class="min-w-0 flex-1 ml-1">
                        <div v-if="filterContracts.length" class="flex flex-wrap gap-1.5">
                            <button v-for="filter in filterContracts" :key="filter" @click="toggleFilter(filter)"
                                class="rounded-md px-2 py-1 text-[11px]"
                                :class="appliedFilters.includes(filter)
                                    ? 'bg-sky-500 text-white ring-sky-500 border border-white'
                                    : 'bg-white text-slate-700 ring-slate-200 hover:bg-slate-50 border border-slate-300'">
                                {{ t(`billing_block.cause_${filter}`) }}
                            </button>
                        </div>
                    </div>
                    <div class="flex items-center gap-x-2 self-end">
                        <button @click="selectAll()"
                            :disabled="saving || (allSelected && selectedContracts.length == 0)"
                            class="inline-flex items-center gap-1.5 rounded-md border border-slate-200 bg-white px-2 py-1 text-xs font-medium text-slate-700 transition-colors hover:bg-slate-50"
                            :class="{
                                'cursor-not-allowed opacity-50': saving || (allSelected && selectedContracts.length == 0)
                            }">
                            <Icon :name="allSelected ? 'fa6-solid:square-check' : 'fa6-solid:check-double'"
                                class="text-sm" />
                            {{ allSelected ? $t('common.deselect') : $t('common.select') }} {{
                                $t('common.all').toLowerCase() }}
                        </button>
                        <span class="text-xs text-slate-500">
                            {{ selectedContracts.length }} {{ t('common.selected') }}
                        </span>
                    </div>
                </div>

                <hr class="mb-2.5 border-slate-200">

                <div class="flex-1 overflow-y-auto pr-1 pb-1">
                    <div v-if="displayedContracts.length > 0" class="space-y-2">
                        <article v-for="contract in displayedContracts" :key="contract.contract_id"
                            class="rounded-lg border border-slate-200 p-2.5 shadow-sm transition-all hover:shadow-md"
                            :class="{ 'bg-red-50': contract.contract_status_token === statusTerminated }">
                            <div class="flex justify-between items-center">
                                <div class="min-w-0">
                                    <FieldDetail :label="$t('contract')" :value="contract.contract_token">
                                        <div class="flex items-center gap-2 min-w-0">
                                            <button @click="openSubRegion('ContractRegion', contract.contract_id)"
                                                class="text-start text-sky-500 underline">{{
                                                    contract.contract_token }}</button>
                                            <span v-if="contract.contract_holder_name"
                                                class="truncate text-sm text-slate-600"
                                                :title="contract.contract_holder_name">- {{
                                                    contract.contract_holder_name }}</span>
                                            <AtomsRedirectButton :id="contract.contract_id"
                                                :path="'/contract/contracts/'" />
                                        </div>
                                    </FieldDetail>
                                </div>
                                <div class="flex items-center gap-x-2">
                                    <div v-if="contract.contract_status_token === statusTerminated && selectedContracts.includes(contract.contract_id)"
                                        class="inline-flex items-center rounded-full bg-rose-100 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-rose-700">
                                        {{ t('informative_block.info_batch_contract_terminated') }}
                                    </div>

                                    <input type="checkbox" v-if="!checkDisabled(contract.missing_reasons)"
                                        v-model="selectedContracts" :value="contract.contract_id"
                                        :checked="selectedContracts.includes(contract.contract_id)"
                                        class="form-checkbox h-4 w-4 rounded border-gray-300 text-sky-600 focus:ring-sky-500">
                                </div>
                            </div>
                            <div class="mt-2 border-t pt-2 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2"
                                :class="{
                                    'border-red-100': contract.contract_status_token === statusTerminated,
                                    'border-slate-100': contract.contract_status_token !== statusTerminated
                                }">
                                <div class="flex-1">
                                    <p
                                        class="mb-1.5 inline-flex items-center rounded-full bg-amber-100 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-amber-700">
                                        {{ Array.isArray(contract.missing_reasons) ? contract.missing_reasons.length : 0
                                        }}
                                        {{ contract.missing_reasons.length == 1 ? t('billing_block.possible_reasons') :
                                            t('billing_block.possible_reasons') }}
                                    </p>
                                    <ul v-if="Array.isArray(contract.missing_reasons) && contract.missing_reasons.length > 0"
                                        class="flex flex-wrap gap-1">
                                        <li v-for="(reason, idx) in contract.missing_reasons"
                                            :key="`${contract.contract_id}-${getReasonKey(reason, idx)}`"
                                            class="inline-flex max-w-full items-center rounded-md bg-slate-50 px-2 py-0.5 text-[11px] text-slate-700 ring-1 ring-slate-200">
                                            {{ getReasonLabel(reason) }}
                                        </li>
                                    </ul>
                                    <p v-else class="text-xs text-slate-500">
                                        {{ t('common.no_data') }}
                                    </p>
                                </div>
                                <div v-if="!contract.missing_reasons?.includes('no_meter')"
                                    class="flex items-center gap-1.5 self-end sm:self-center shrink-0">
                                    <button v-if="contract.missing_reasons?.includes('no_reading')" :disabled="saving"
                                        @click="handleEstimatedReading(contract.contract_id)"
                                        class="inline-flex items-center gap-1 rounded bg-sky-500 hover:bg-sky-600 px-2.5 py-1 text-xs font-semibold text-white transition-colors disabled:opacity-50">
                                        <Icon name="fa6-solid:plus" class="text-xs" />
                                        {{ t('billing_block.add_estimated_reading') || 'Afegir lectura estimada' }}
                                    </button>
                                    <button
                                        v-if="!contract.missing_reasons?.includes('no_reading') && (contract.missing_reasons?.includes('no_batch') || contract.missing_reasons?.includes('no_billing'))"
                                        :disabled="saving" @click="handleAddToBatch(contract.contract_id)"
                                        class="inline-flex items-center gap-1 rounded bg-emerald-500 hover:bg-emerald-600 px-2.5 py-1 text-xs font-semibold text-white transition-colors disabled:opacity-50">
                                        <Icon name="fa6-solid:link" class="text-xs" />
                                        {{ t('billing_block.add_to_batch') || 'Afegir al lot' }}
                                    </button>
                                    <button
                                        v-if="!hasNoPriceRate(contract.missing_reasons) && !contract.missing_reasons?.includes('no_reading') && !contract.missing_reasons?.includes('no_batch') && !contract.missing_reasons?.includes('no_billing')"
                                        :disabled="saving" @click="handleProcessContract(contract.contract_id)"
                                        class="inline-flex items-center gap-1 rounded bg-indigo-500 hover:bg-indigo-600 px-2.5 py-1 text-xs font-semibold text-white transition-colors disabled:opacity-50">
                                        <Icon name="fa6-solid:gears" class="text-xs" />
                                        {{ t('billing_block.process_contract') || 'Processar' }}
                                    </button>
                                </div>
                            </div>
                        </article>
                    </div>

                    <div v-else
                        class="rounded-lg border border-dashed border-slate-300 bg-slate-50 px-4 py-6 text-center text-xs text-slate-500">
                        {{ t('common.no_results') }}
                    </div>
                </div>
            </section>
        </div>
        <div role="region" id="right_over_page"
            class="fixed h-full border-l border-gray-100 top-0 right-0 transition-all duration-500 ease py-2 text-base bg-white w-[85%] z-30 shadow"
            :class="{ 'translate-x-0': showSubRegion, 'translate-x-[2000px]': !showSubRegion }">
            <div id="region_nav" class="mb-3 px-3">
                <button @click="closeSubRegion()" class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300">
                    <Icon name="fa6-solid:angles-right" class="text-slate-500" />
                </button>
            </div>
            <div class="pl-10 flex-1 overflow-y-auto pb-24 pr-2">
                <ContractRegion v-if="showRegionDetailComponent === 'ContractRegion'" :id="regionDetailId"
                    :isSubRegion="true" />

            </div>
        </div>
    </div>
</template>