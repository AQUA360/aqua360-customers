<script setup>
import debounce from 'lodash.debounce';
import { addDays, format, parseISO } from 'date-fns';
import ButtonSeleccio from '~/components/atoms/ButtonSeleccio.vue';

import FieldDetail from '../atoms/FieldDetail.vue';
import ContractRegion from '../organisms/ContractRegion.vue';

import PaymentCommitmentList from '../molecules/PaymentCommitmentList.vue';


const { t } = useI18n();

const props = defineProps({
    data: Object,
    request: {
        type: Object,
        default: null
    },
    is_split: Boolean
});

const { $ConfiglistApiService } = useNuxtApp();

const emit = defineEmits(['change']);

const stop_watchers = ref(false);
const loading_invoices = ref(true);
const generating = ref(false);

const due_date_commitment = ref();
const start_date_commitment = ref();
const invoices = ref([])
const holder = ref(null)
const contract = ref(null)
const total_payments = ref(0)

const total = ref(0)
const total_payments_sum = ref(0)

const payments = ref([])
const days_next_payment = ref(30)
// Cents added to the first payment when the split is not exact (0 when there is nothing to notify)
const rounding_adjustment = ref(0)

const paymentTypeOptions = ref([]);
const paymentTypeOptionsById = ref([]);

const showRegion = ref(false);
const isSubRegionOpen = ref(false);
const showRegionDetailComponent = ref(null);
const regionDetailId = ref(null);

let searchTimeout = null;
const DEBOUNCE_DELAY = 1000;

const closeAllRegions = () => {
    showRegionDetailComponent.value = null
    regionDetailId.value = null
    showRegion.value = false;
};

const getData = async () => {
    stop_watchers.value = true
    loading_invoices.value = true;
    await nextTick()
    if (props.data) {
        holder.value = props.data.holder
        contract.value = props.data.contract
        invoices.value = props.data.invoices
        total.value = invoices.value.reduce((sum, invoice) => sum + parseFloat(invoice.left_to_pay), 0);
        payments.value = props.data.payments
        start_date_commitment.value = props.data.start_date_commitment || format(new Date(), 'yyyy-MM-dd')
        days_next_payment.value = props.data.days_next_payment
        due_date_commitment.value = props.data.due_date_commitment ? props.data.due_date_commitment : (format(new Date(), 'yyyy-MM-dd')).toString()
        //total_payments.value = payments?.value?.length || 1
        if (payments?.value?.length > 0) {
            total_payments.value = payments?.value?.length
        } else {
            total_payments.value = 1
            generatePayments()
        }
        checkPaymentsAmount(false)
    }
    await nextTick()
    stop_watchers.value = false
    loading_invoices.value = false;
}

// Split in cents: every payment gets the same base amount and the cents left over by the division
// are added to the first payment, so the payments always add up to the total.
const generatePayments = async () => {
    generating.value = true;
    payments.value = []

    const count = Math.max(parseInt(total_payments.value) || 1, 1)
    const total_cents = Math.round(total.value * 100)
    const base_cents = Math.floor(total_cents / count)
    const leftover_cents = total_cents - base_cents * count

    for (let i = 0; i < count; i++) {
        const cents = i === 0 ? base_cents + leftover_cents : base_cents
        payments.value.push({ amount: (cents / 100).toFixed(2) })
    }
    rounding_adjustment.value = leftover_cents / 100
    recalculateDates(false)

    checkPaymentsAmount()

    await nextTick()
    generating.value = false;
}

// From the commitment start date, each payment is due every `days_next_payment` days and its range starts
// the day after the previous due date. The range is informative only: a payment can be charged earlier.
const recalculateDates = (change = true) => {
    if (!start_date_commitment.value) return
    const start = parseISO(start_date_commitment.value)
    const days = parseInt(days_next_payment.value) || 0
    payments.value.forEach((payment, index) => {
        payment.due_date = format(addDays(start, (index + 1) * days), 'yyyy-MM-dd')
    })
    updateRangeStarts()
    if (payments.value.length > 0) due_date_commitment.value = payments.value[payments.value.length - 1].due_date
    if (change) emitChange()
}

const updateRangeStarts = () => {
    payments.value.forEach((payment, index) => {
        const previous = payments.value[index - 1]
        payment.start_date = previous?.due_date
            ? format(addDays(parseISO(previous.due_date), 1), 'yyyy-MM-dd')
            : start_date_commitment.value
    })
}

const onDueDateChange = () => {
    updateRangeStarts()
    emitChange()
}

const checkPaymentsAmount = (change = true) => {
    total_payments_sum.value = payments.value.reduce((sum, payment) => sum + parseFloat(payment.amount), 0);
    if (change) emitChange()
}

const debouncedCheckPaymentsAmount = () => {
    // Amounts edited by hand: the automatic adjustment no longer applies
    rounding_adjustment.value = 0
    clearTimeout(searchTimeout);
    searchTimeout = setTimeout(() => {
        checkPaymentsAmount();
    }, DEBOUNCE_DELAY);
};

const getDebouncedData = debounce(getData, 300);


const openRegion = (component, id = null) => {
    closeAllRegions();
    showRegionDetailComponent.value = component;
    regionDetailId.value = id;
    showRegion.value = true;
};

const emitChange = () => {
    let infoData = {
        payments: payments.value,
        remaining: (total.value - total_payments_sum.value).toFixed(3),
        holder: props.data.holder,
        contract: props.data.contract,
        invoices: props.data.invoices,
        days_next_payment: days_next_payment.value,
        due_date_commitment: due_date_commitment.value,
        start_date_commitment: start_date_commitment.value,
    }

    emit('change', infoData)
}

onMounted(async () => {
    //await fetchPaymentTypes();
    await getDebouncedData()
})

watch(() => props.data, (newVal) => {
    getDebouncedData()
}, { immediate: true })     //deep true false to avoid changing when changing payments

/* watch(() => payments.value, (newVal) => {
    emitChange()
}, { deep: true, immediate: true }) */

</script>
<template>
    <div v-if="!loading_invoices" id="wrapper" class="text-base">
        <h2 class="text-xl font-semibold mb-4">{{ $t('claim_block.commitment_division') }}</h2>

        <!-- LITTLE INFO -->
        <div v-if="holder" class="flex px-5">
            <details class="w-full h-fit my-auto p-4 border border-sky-200 rounded-lg bg-sky-50">
                <summary
                    class="font-semibold text-slate-700 px-3 py-1 bg-white rounded-md mb-1 border border-sky-200">
                    {{ t('claim_block.commitment_summary') }}
                </summary>
                <ul class="space-y-2 mt-3">
                    <li class="flex items-center text-sm text-slate-600">
                        <FieldDetail :strong="true" :label="t('common.affected')">
                            <span>{{ holder.name }} {{ holder?.surname }}
                                <span class="text-xs text-slate-500 italic ml-1">({{ holder.token }})</span>
                            </span>
                        </FieldDetail>
                    </li>

                    <li class="flex items-center text-sm text-slate-600">
                        <FieldDetail :strong="true" :label="t('contract')">
                            <button class="text-sky-500 hover:underline hover:text-sky-600"
                                @click="openRegion('ContractRegion', contract.id)">
                                {{ contract.token }}</button>
                        </FieldDetail>
                    </li>

                    <li class="flex items-center text-sm text-slate-600">
                        <FieldDetail :strong="true" :label="t('billing_block.total_affected_invoices')">
                            <span v-if="request && request?.invoices">
                                {{ request.invoices.length + invoices.length }}
                            </span>
                            <span v-else>{{ invoices.length }}</span>

                        </FieldDetail>
                    </li>

                    <li class="flex items-center text-sm text-slate-600">
                        <FieldDetail :strong="true" :label="t('billing_block.total_to_pay')">
                            <span>{{ formatMoneyWithCurrency(total) }}
                                <span v-if="request && request?.invoices"
                                    class="text-xs text-slate-500 italic ml-1">(+{{ request.total
                                    }})</span>
                            </span>

                        </FieldDetail>
                    </li>

                    <li v-if="request && request?.invoices" class="flex items-center w-full text-sm text-slate-600">
                        <PaymentCommitmentList :id="request.id" @show-detail="openRegion" :isGuide="true"
                            class="bg-white w-full" />
                    </li>

                </ul>

            </details>
        </div>


        <!-- Payment Generation -->
        <div v-if="invoices && invoices.length > 0" class="p-6">
            <div class="grid grid-cols-[250px,200px,200px,200px] gap-6">
                <div v-if="is_split" class="grid grid-cols-[200px,200px] gap-6 mb-6">
                    <div>
                        <label class="block text-sm font-medium text-gray-700 mb-2">
                            {{ t('claim_block.generate_payments') }}
                        </label>
                        <div class="flex gap-3">
                            <input type="number" v-model="total_payments"
                                class="input" />
                            <button class="button-primary" @click="generatePayments">
                                {{ t('common.generate') }}
                            </button>
                        </div>
                    </div>
                </div>
                <div>
                    <label class="block text-sm font-medium text-gray-700 mb-2">
                        {{ t('pricing_block.periodicity') }} ({{ t('date.days') }})
                    </label>
                    <input type="number" v-model="days_next_payment" @input="recalculateDates()"
                        class="input"
                        :disabled="request && request?.invoices" />
                </div>
                <div>
                    <AtomsInputDate v-model="start_date_commitment" :label="t('common.start_date')" class="mb-2"
                        :required="true" @update:modelValue="recalculateDates()" />
                </div>
                <div>
                    <AtomsInputDate v-model="due_date_commitment" :label="t('common.due_date')" class="mb-2"
                        :required="true" @update:modelValue="emitChange" />
                </div>
            </div>

            <div class="py-4">
                

                <!-- Payments Input -->
                <div v-if="payments && payments.length > 0">
                    <div v-if="(total - total_payments_sum).toFixed(2) != 0" class="mb-4 w-full">
                        <div class="border border-yellow-400 rounded-md bg-yellow-50 p-3 grid grid-cols-[auto,1fr] items-center gap-3">
                            <Icon name="fa6-solid:triangle-exclamation"
                                class="h-5 w-5 text-yellow-400" />
                            <div class="text-sm text-gray-700">
                                <p class="">{{ t('claim_block.diff_to_complete') }}:</p>
                                <p class="mt-1 font-bold">
                                    {{ formatMoneyWithCurrency(
                                        (total - total_payments_sum).toFixed(2)
                                    ) }}
                                </p>
                            </div>
                        </div>
                    </div>

                    <div v-if="rounding_adjustment > 0" class="mb-4 w-full">
                        <div class="border border-sky-300 rounded-md bg-sky-50 p-3 grid grid-cols-[auto,1fr] items-center gap-3">
                            <Icon name="fa6-solid:circle-info" class="h-5 w-5 text-sky-500" />
                            <p class="text-sm text-gray-700">
                                {{ t('claim_block.rounding_adjustment_info', { amount: formatMoneyWithCurrency(rounding_adjustment) }) }}
                            </p>
                        </div>
                    </div>

                    <div class="space-y-4">
                        <div v-for="(payment, index) in payments" :key="index" class="mb-4 py-2 rounded-lg border-l border-l-2 border-sky-500"
                        :class="{ 'bg-sky-50': is_split }">
                        <div class="grid grid-cols-3 gap-4 relative px-6">
                            <div>
                                <label class="block text-sm font-medium text-gray-600 mb-2">
                                    {{ t('common.amount') }}:
                                </label>
                                <input v-if="is_split" type="number" v-model="payment.amount"
                                    @input="debouncedCheckPaymentsAmount" class="input" />
                                <span v-else
                                    class="p-2 mt-1 block w-full rounded-md border-gray-300 shadow-sm bg-slate-50">
                                    {{ formatMoneyWithCurrency(payment.amount) }}</span>
                            </div>
                            <div>
                                <label class="block text-sm font-medium text-gray-600 mb-2">
                                    {{ t('billing_block.payment_range') }}:
                                </label>
                                <span class="p-2 mt-1 block w-full rounded-md border-gray-300 shadow-sm bg-slate-50">
                                    {{ formatDate(payment.start_date) }} &rarr; {{ formatDate(payment.due_date) }}</span>
                            </div>
                            <div>
                                <AtomsInputDate v-model="payment.due_date" :label="t('common.due_date')" class="mb-2"
                                    :required="true" @update:modelValue="onDueDateChange" />
                            </div>
                        </div>
                    </div>
                    </div>
                </div>
            </div>
        </div>


        <!-- <hr class="my-2" /> -->
        <div role="region" id="right_page"
            class="fixed h-full border-l border-gray-100 top-0 right-0 transition-all duration-500 ease py-2 text-base bg-white z-10"
            :class="{
                'translate-x-0': showRegion,
                'translate-x-[2000px]': !showRegion,
                'w-[95%]': isSubRegionOpen,
                'w-[60%]': !isSubRegionOpen
            }">
            <div id="region_nav" class="mb-3 px-3">
                <button @click="showRegion = false"
                    class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300">
                    <Icon name="fa6-solid:angles-right" class="text-slate-500" />
                </button>
            </div>
            <div class="px-10">
                <ContractRegion v-if="showRegionDetailComponent === 'ContractRegion'" :id="parseInt(regionDetailId)"
                    :isSubRegion="true" />
            </div>
        </div>
    </div>

    <div v-else class="p-4">
        <div class="flex justify-center items-center">
            <Icon name="fa6-solid:spinner" class="animate-spin text-2xl text-slate-500" />
            <span class="ml-2 text-sm text-slate-500">{{ $t('common.loading') }}...</span>
        </div>

    </div>

</template>