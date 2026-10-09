<script setup>
import debounce from 'lodash.debounce';
import InvoiceMiniDetail from './InvoiceMiniDetail.vue';
import FieldDetail from '../atoms/FieldDetail.vue';
import PaymentCommitmentList from '../molecules/PaymentCommitmentList.vue';
import ContractRegion from '../organisms/ContractRegion.vue';

const { t } = useI18n();

const props = defineProps({
    data: Object,
    request: {
        type: Object,
        default: null
    }
});

const emit = defineEmits(['change']);

const stop_watchers = ref(false);
const loading_invoices = ref(true);

const invoices = ref([])
const holder = ref(null)
const contract = ref(null)

const total = ref(0)

const payments = ref([])

const showRegion = ref(false);
const isSubRegionOpen = ref(false);
const showRegionDetailComponent = ref(null);
const regionDetailId = ref(null);

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
        payments.value = props.data.payments
        total.value = invoices.value.reduce((sum, invoice) => sum + parseFloat(invoice.total_final), 0);
    }
    await nextTick()
    stop_watchers.value = false
    loading_invoices.value = false;
}

const getDebouncedData = debounce(getData, 300);

const openRegion = (component, id = null) => {
    closeAllRegions();
    showRegionDetailComponent.value = component;
    regionDetailId.value = id;
    showRegion.value = true;
};

const emitChange = () => {
    let infoData = {
    }

    emit('change', infoData)
}

onMounted(async () => {
    await getDebouncedData()
})

watch(() => props.data, (newVal) => {
    getDebouncedData()
}, { deep: true, immediate: true })

</script>
<template>
    <div v-if="!loading_invoices" id="wrapper" class="text-base">
        <h2 class="text-xl font-semibold mb-4">{{ $t('claim_block.commitment_summary') }}</h2>

        <!-- HOLDER INFO -->
        <div v-if="holder" class="flex px-5">
            <details open class="w-full h-fit my-auto p-4 border border-sky-200 rounded-lg bg-sky-50">
                <summary
                    class="font-semibold text-slate-700 px-3 py-1 bg-white rounded-md mb-1 border border-sky-200 mb-3">
                    {{ t('claim_block.commitment_summary') }}
                </summary>
                <ul class="space-y-2">
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
                            <span v-if="request && request?.invoices">{{
                                formatMoneyWithCurrency(total +parseFloat(request.total)) }}</span>
                            <span v-else>{{ formatMoneyWithCurrency(total) }}</span>

                        </FieldDetail>
                    </li>

                    <li v-if="request && request?.invoices" class="flex items-center w-full text-sm text-slate-600">
                        <PaymentCommitmentList :id="request.id" @show-detail="openRegion" :isGuide="true"
                            class="bg-white w-full" />
                    </li>
                </ul>

            </details>
        </div>

        <!-- PAYMENTS INFO -->
        <div v-if="payments">
            <fieldset class="bg-sky-50 border border-sky-200 rounded-lg p-4 shadow-sm m-4 p-4">
                <legend class="font-semibold text-slate-700 px-3 py-1 bg-white rounded-md mb-1 border border-sky-200">
                    {{ t('claim_block.claim_payments_to_add') }}
                </legend>
                <ul v-if="!loading_invoices" class="divide-y divide-sky-200 px-5">
                    <li v-for="payment in payments" :key="payment.id" class="py-2 flex items-center justify-between">
                        <span class="text-sm font-medium text-gray-600">
                            <span v-if="payment.start_date" class="text-gray-500">{{ formatDate(payment.start_date) }} &rarr; </span>{{
                            formatDate(payment.due_date)
                            }}</span>
                        <span class="ml-2 text-sm text-gray-700">{{
                            formatMoneyWithCurrency(payment.amount)
                            }}</span>
                    </li>
                </ul>
                <div v-else class="flex justify-center items-center py-3">
                    <Icon name="fa6-solid:spinner" class="animate-spin text-md text-gray-500" />
                    <span class="ml-2 text-sm text-gray-500">{{ $t('common.loading') }}...</span>
                </div>
            </fieldset>
        </div>


        <!-- <hr class="my-2" /> -->
        <div role="region" id="right_page"
            class="fixed h-full border-l border-gray-100 top-0 right-0 transition-all duration-500 ease py-2 text-base bg-white z-10"
            :class="{
                'translate-x-0': showRegion,
                'translate-x-[2000px]': !showRegion,
                'w-[95%]': isSubRegionOpen,
                'w-1/2': !isSubRegionOpen
            }">
            <div id="region_nav" class="mb-3 px-3">
                <button @click="showRegion = false"
                    class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300">
                    <Icon name="fa6-solid:angles-right" class="text-slate-500" />
                </button>
            </div>
            <div class="px-10">
                <ContractRegion v-if="showRegionDetailComponent === 'ContractRegion'" :id="parseInt(regionDetailId)" />
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