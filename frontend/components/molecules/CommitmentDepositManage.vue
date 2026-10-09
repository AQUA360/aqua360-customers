<script setup>
import debounce from 'lodash.debounce';
import AddInvoices from '~/components/molecules/AddInvoices.vue';
import SupplyPointRegion from '../organisms/SupplyPointRegion.vue';
import ContractRegion from '../organisms/ContractRegion.vue';
import ExploitationRegion from '../organisms/ExploitationRegion.vue';
import CompanyRegion from '../organisms/CompanyRegion.vue';
import ContractRequestRegion from '../organisms/ContractRequestRegion.vue';
import PaymentCommitmentList from '../molecules/PaymentCommitmentList.vue';
import FieldDetail from '../atoms/FieldDetail.vue';
import ButtonSeleccio from '../atoms/ButtonSeleccio.vue';
import InvoiceDetail from './InvoiceDetail.vue';
import H1 from '../atoms/H1.vue';

const { t } = useI18n();

const props = defineProps({
    request: Object,
    holder: Object,
    contract: Object,
    payments: Array
});

const emit = defineEmits(['change']);

const selectedFilter = ref('holder')
const selectedInvoices = ref([])

const stop_watchers = ref(false);
const loading_invoices = ref(false);
const infoData = ref({})

const request = ref(null);
const totalInvoices = ref(0)
const totalPayments = ref(0)
const holder = ref(null);

const showRegion = ref(false);
const isSubRegionOpen = ref(false);
const showRegionDetailComponent = ref(null);
const regionDetailId = ref(null);

const foundDifferentHolder = ref(false)

const closeAllRegions = () => {
    showRegionDetailComponent.value = null
    regionDetailId.value = null
    showRegion.value = false;
};

const getData = async () => {
    stop_watchers.value = true
    await nextTick()
    request.value = props.request;
    totalInvoices.value = request.value.invoices.length;
    totalPayments.value = props.payments ? props.payments.length : 0;
    holder.value = props.holder;
    await nextTick()
    stop_watchers.value = false
}

const getDebouncedData = debounce(getData, 300);

const openRegion = (component, id = null) => {
    closeAllRegions();
    showRegionDetailComponent.value = component;
    regionDetailId.value = id;
    showRegion.value = true;
};

const onInvoiceSelected = async (item) => {
    if (selectedInvoices.value.includes(item) || selectedInvoices.value.filter(x => x.id === item.id).length > 0) {
        selectedInvoices.value = selectedInvoices.value.filter(x => x.id !== item.id);
    } else {
        selectedInvoices.value.push(item);
    }

    //foundDifferentHolder is true if any of the selected invoices has a different holder than the first one or a different token from holder.token
    foundDifferentHolder.value = selectedInvoices.value.some(invoice => invoice.customer_token_final !== selectedInvoices.value[0].customer_token_final || invoice.customer_token_final !== holder.value.token)
    //closeAllRegions();
}

const emitChange = () => {
    loading_invoices.value = true;

    infoData.value = {
        invoices: selectedInvoices.value,
        ignored_invoices: [],
        disable: foundDifferentHolder.value,
    }
    emit('change', infoData.value)
}

onMounted(() => {
    getDebouncedData()
})

watch(() => selectedFilter.value, (newVal) => {
    if (stop_watchers.value) return
    emitChange()
})

watch(() => selectedInvoices.value, (newVal) => {
    if (stop_watchers.value) return
    emitChange()
}, { deep: true, immediate: true })

watch(
    [props.request, props.holder, props.payments]
    , (newVal) => {
        getDebouncedData()
    }, { deep: true, immediate: true })

</script>
<template>
    <div v-if="request" id="wrapper" class="container mx-auto text-base">
        <h2 class="text-xl font-semibold mb-4">
            {{ $t('claim_block.selected_invoicess_commitment') }}:
            {{ request.token }}
        </h2>

        <div class="grid gap-8 lg:grid-cols-2">
            <!-- Commitment Summary -->
            <div v-if="holder">
                <details open
                    class="w-full open:h-[65vh] overflow-y-auto p-6 border border-sky-300 rounded-lg bg-sky-50">
                    <summary
                        class="font-semibold text-[14px] text-slate-700 px-4 py-2 bg-white rounded-md mb-4 border border-sky-300 cursor-pointer">
                        {{ t('claim_block.commitment_summary') }}
                    </summary>
                    <div class="space-y-4">
                        <div class="px-4 flex items-center text-sm text-slate-600">
                            <FieldDetail :strong="true" :label="t('common.affected')">
                                <span>{{ holder.name }} {{ holder?.surname }}
                                    <span class="text-xs text-slate-500 italic ml-1">({{ holder.token }})</span>
                                </span>
                            </FieldDetail>
                        </div>

                        <li class="px-4 flex items-center text-sm text-slate-600">
                            <FieldDetail :strong="true" :label="t('contract')">
                                <button class="text-sky-500 hover:underline hover:text-sky-600"
                                    @click="openRegion('ContractRegion', contract.id)">
                                    {{ contract.token }}</button>
                            </FieldDetail>
                        </li>

                        <div class="px-4 flex items-center text-sm text-slate-600">
                            <FieldDetail :strong="true" :label="t('billing_block.total_affected_invoices')" :value="totalInvoices" />
                        </div>

                        <div class="w-full">
                            <PaymentCommitmentList :id="request.id" @show-detail="openRegion" :isGuide="true"
                                class="bg-white rounded-md border border-slate-200" />
                        </div>
                    </div>
                </details>
            </div>

            <!-- Selected Invoices -->
            <div>
                <div v-if="foundDifferentHolder" class="bg-red-100 p-4 rounded relative max-w-xl group">
                    <p class="flex justify-between">
                        <span class="font-semibold ">
                            {{ t('claim_block.invoices_diff_holder') }}
                        </span>
                    </p>
                </div>
                <div v-if="selectedInvoices && selectedInvoices.length > 0"
                    class="relative group overflow-y-auto my-auto h-[65vh] p-4 gap-4 border border-slate-300 rounded-lg">
                    <div v-for="invoice in selectedInvoices" :key="invoice.id"
                        class="bg-green-50 p-4 mb-3 rounded-lg border border-green-200 relative">
                        <InvoiceDetail :id="invoice.id" @show-detail="openRegion" />
                    </div>
                    <!-- Keep ButtonSeleccio -->
                    <button @click="openRegion('invoiceEdit')"
                        class="absolute cursor-pointer shadow-md border text-sm w-8 h-8 bg-white right-3 top-3 rounded-md text-slate-600 opacity-0 transition-all duration-300 group-hover:opacity-100">
                        <Icon name="fa6-solid:pencil" />
                    </button>
                </div>
                <div v-else class="p-6 bg-white rounded-lg border border-slate-300">
                    <p class="text-center text-slate-600 mb-4">
                        {{ $t('claim_block.no_invoice_selected_commitment') }}
                    </p>
                    <div class="flex justify-center">
                        <!-- Keep ButtonSeleccio -->
                        <ButtonSeleccio @click="openRegion('invoiceEdit')">
                            {{ $t('billing_block.select_invoice') }}
                        </ButtonSeleccio>
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
                'w-[95%]': isSubRegionOpen || showRegionDetailComponent==='invoiceEdit',
                'w-1/2': !isSubRegionOpen && showRegionDetailComponent!='invoiceEdit'
            }">
            <div id="region_nav" class="mb-3 px-3">
                <button @click="closeAllRegions" class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300">
                    <Icon name="fa6-solid:angles-right" class="text-slate-500" />
                </button>
            </div>
            <div class="px-10">
                <AddInvoices v-if="showRegionDetailComponent == 'invoiceEdit'" :multiple="true"
                    :selected_items="selectedInvoices" @item-clicked="onInvoiceSelected" :contract="contract.id" />
                <SupplyPointRegion v-if="showRegionDetailComponent === 'SupplyPointRegion'"
                    :id="parseInt(regionDetailId)" :isSubRegion="true" />
                <ExploitationRegion v-if="showRegionDetailComponent === 'ExploitationRegion'"
                    :id="parseInt(regionDetailId)" :isSubRegion="true" />
                <CompanyRegion v-if="showRegionDetailComponent === 'CompanyRegion'" :id="parseInt(regionDetailId)"
                    :isSubRegion="true" />
                <ContractRegion v-if="showRegionDetailComponent === 'ContractRegion'" :id="parseInt(regionDetailId)"
                    :isSubRegion="true" />
                <ContractRequestRegion v-if="showRegionDetailComponent === 'ContractRequestRegion'"
                    :id="parseInt(regionDetailId)" :isSubRegion="true" />
            </div>
        </div>
    </div>
    <div v-else class="flex justify-center items-center h-screen p-4">
        <Icon name="fa6-solid:spinner" class="animate-spin text-4xl text-sky-500" />
        <span class="ml-4 text-lg text-sky-600">{{ $t('common.loading') }}...</span>
    </div>
</template>