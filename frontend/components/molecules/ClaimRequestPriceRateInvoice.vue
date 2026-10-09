<script setup>

import { useI18n } from 'vue-i18n';
import { formatMoneyWithCurrency } from '~/utils/money';
import ClaimRequestContractSelectionRegion from '../organisms/ClaimRequestContractSelectionRegion.vue';
import ClaimRequestStepExpensesRegion from '../organisms/ClaimRequestStepExpensesRegion.vue';

const props = defineProps({
    request: {
        type: Object,
        required: true,
    },
    step: {
        type: Object,
        required: true,
    },
    generateTaskId: {
        type: String,
        required: false,
    }
});

const emit = defineEmits(['generate-expenses', 'get-task-data']);

const { t } = useI18n();

const availablePriceRates = ref([])

const selectedContracts = ref([]);
const showRegion = ref(false);
const showContractSelection = ref(false);
const showGeneratedExpenses = ref(false);
const isSubRegionOpen = ref(false);

const generatingTaskId = ref(null);

const atCurrentStep = computed(() => {
  return props.request.current_step?.id === props.step.id;
});

const openContractSelection = () => {
    showGeneratedExpenses.value = false;
    showContractSelection.value = true;
    showRegion.value = true;
    isSubRegionOpen.value = true;
}

const openGeneratedExpenses = () => {
    showContractSelection.value = false;
    showGeneratedExpenses.value = true;
    showRegion.value = true;
    isSubRegionOpen.value = true;
}

const closeRegions = () => {
    showContractSelection.value = false;
    showGeneratedExpenses.value = false;
    showRegion.value = false;
    isSubRegionOpen.value = false;
}

const handleSubRegionEvent = (event) => {
    isSubRegionOpen.value = event;
}

const generateInvoiceExpenses = () => {
    emit('generate-expenses', {
        claim_request_id: props.request.id,
        claim_request_step_id: props.step.id,
        contract_ids: [...selectedContracts.value],
        price_rate_ids: availablePriceRates.value.map(priceRate => priceRate.id),
    });
}

const getTaskData = () => {
    emit('get-task-data', generatingTaskId.value);
}

watch(() => props.step, (step) => {
    availablePriceRates.value = step?.price_rates ?? [];
    console.log("availablePriceRates.value", availablePriceRates.value);
    console.log("step", step);
}, { deep: true, immediate: true });

watch(() => props.generateTaskId, (generateTaskId) => {
    generatingTaskId.value = generateTaskId ?? null;
}, { deep: true, immediate: true });

const lineItemTypes = function (priceRate) {
    return priceRate?.billing_range_active?.line_item_types ?? [];
}

const getPriceInterval = function (lineItemType) {
    const interval = lineItemType?.price_interval;
    if (!interval || interval === 'None') {
        return null;
    }
    return typeof interval === 'object' ? interval.token : interval;
}

const getPriceLabel = function (lineItemType) {
    if (lineItemType?.price == null && lineItemType?.proportional_price != null) {
        return t('pricing_block.proportional_price');
    }
    if (lineItemType?.price == null && getPriceInterval(lineItemType)) {
        return t('pricing_block.price_interval');
    }
    return t('common.price');
}

const getPrice = function (lineItemType) {
    if (lineItemType?.price != null) {
        return formatMoneyWithCurrency(lineItemType.price);
    }
    if (lineItemType?.proportional_price != null) {
        return formatMoneyWithCurrency(lineItemType.proportional_price);
    }
    return getPriceInterval(lineItemType) ?? '-';
}

</script>

<template>
    <div class="border-t pt-2">
        <div class="flex flex-wrap items-start justify-between gap-3">
            <div>
                <h3 class="text-lg font-semibold">{{ $t('billing_block.claim_expenses') }}</h3>
                <p class="text-gray-600">{{ $t('claim_block.info_claim_expenses') }}</p>
            </div>

            <div class="flex shrink-0 items-center gap-2">
                <button @click="openContractSelection" class="button-default flex items-center gap-x-1.5"
                    :title="$t('claim_block.select_expenses_contracts')" :disabled="!atCurrentStep">
                    <Icon name="fa6-solid:file-contract" />
                    {{ $t('common.contracts') }} ({{ selectedContracts.length }})
                </button>
                <AtomsProcessColorBadge class="py-2" v-if="generatingTaskId" @refresh="getTaskData(taskId)"
                  :value="`${t('common.loading')}`" :color="'blue'" :taskId="generatingTaskId"></AtomsProcessColorBadge>
                <button v-else @click="generateInvoiceExpenses" :disabled="selectedContracts.length === 0 || !atCurrentStep"
                    class="button-primary flex items-center gap-x-1.5 disabled:cursor-not-allowed disabled:opacity-50"
                    :title="$t('billing_block.generate_invoice_expenses')">
                    <Icon name="fa6-solid:file-invoice" />
                    {{ $t('billing_block.generate_invoice_expenses') }}
                </button>
            </div>
        </div>
        <div class="flex flex-row-reverse shrink-0 items-center gap-2">
            <button @click="openGeneratedExpenses" class="button-default flex items-center gap-x-1.5"
                :title="$t('claim_block.show_generated_expenses')">
                <Icon name="fa6-solid:coins" />
                {{ $t('claim_block.show_generated_expenses') }} ({{ props.step.total_claim_request_payments ?? 0 }})
            </button>
        </div>

        <p v-if="availablePriceRates.length === 0"
            class="mt-2 rounded-xl border border-dashed border-slate-200 bg-white/60 px-4 py-6 text-center text-sm text-slate-500">
            {{ $t('common.no_data_found') }}
        </p>

        <div v-else class="mt-2 flex flex-col gap-2">
            <article v-for="priceRate in availablePriceRates" :key="priceRate.id"
                class="flex items-center justify-between gap-3 rounded-xl border border-slate-200 bg-white px-4 py-3 shadow-sm transition">
                <div class="min-w-0">
                    <p class="text-xs font-semibold uppercase tracking-wide text-sky-500">
                        {{ priceRate.product ? priceRate.product.name : $t('pricing_block.no_product') }}
                    </p>
                    <p class="truncate text-base font-semibold text-slate-800">
                        {{ priceRate.name || priceRate.token }}
                    </p>
                </div>

                <div class="flex shrink-0 flex-col items-end gap-2 text-right">
                    <div v-for="lineItemType in lineItemTypes(priceRate)" :key="lineItemType.id">
                        <p class="text-xs uppercase tracking-wide text-slate-400">
                            {{ getPriceLabel(lineItemType) }}
                        </p>
                        <p class="text-base font-semibold text-slate-800">{{ getPrice(lineItemType) }}</p>
                        <p class="text-xs text-slate-500">
                            {{ lineItemType.tax ? lineItemType.tax : t('billing_block.no_taxes') }}
                        </p>
                    </div>
                </div>
            </article>
        </div>

        <div role="region" id="right_page"
            class="fixed h-full border-l border-slate-100 top-0 right-0 transition-all duration-500 ease py-2 text-base bg-white z-50"
            :class="{ 'translate-x-0': showRegion, 'translate-x-[2000px]': !showRegion, 'w-[95%]': isSubRegionOpen, 'w-[50%]': !isSubRegionOpen }">
            <div id="region_nav" class="mb-3 px-3">
                <button @click="closeRegions" class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300">
                    <Icon name="fa6-solid:angles-right" class="text-slate-500" />
                </button>
            </div>
            <div class="px-10">
                <ClaimRequestContractSelectionRegion v-if="showContractSelection" :request="request"
                    :selectedContracts="selectedContracts" :allowSelectFiltering="true" :allowDocumentSelection="false"
                    title="claim_block.select_expenses_contracts" highlightColor="bg-emerald-100"
                    @update:selectedContracts="selectedContracts = $event" @show-detail="handleSubRegionEvent"
                    @close="closeRegions" :currentStep="props.step" />
                <ClaimRequestStepExpensesRegion v-if="showGeneratedExpenses" :step="props.step"
                    @show-detail="handleSubRegionEvent" />
            </div>
        </div>
    </div>
</template>
