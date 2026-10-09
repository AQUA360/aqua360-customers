<script setup>
import debounce from 'lodash.debounce';
import ButtonSeleccio from '~/components/atoms/ButtonSeleccio.vue';
import PersonSearch from '~/components/organisms/PersonSearch.vue';
import AddContracts from '~/components/molecules/AddContracts.vue';
import AddInvoices from '~/components/molecules/AddInvoices.vue';
import FieldDetail from '../atoms/FieldDetail.vue';
import ContractDetail from './ContractDetail.vue';
import InvoiceDetail from './InvoiceDetail.vue';
import SupplyPointRegion from '../organisms/SupplyPointRegion.vue';
import ContractRegion from '../organisms/ContractRegion.vue';
import ExploitationRegion from '../organisms/ExploitationRegion.vue';
import CompanyRegion from '../organisms/CompanyRegion.vue';
import ContractRequestRegion from '../organisms/ContractRequestRegion.vue';

const { t } = useI18n();
const route = useRoute()

const props = defineProps({
    data: Object
});

const emit = defineEmits(['change']);

const selectedFilter = ref('contract')
const selectedPerson = ref(null)
const selectedContract = ref([])        //Array to work with component, will use single item
const selectedInvoice = ref([])        //Array to work with component, will use single item

const stop_watchers = ref(false);
const loading_invoices = ref(false);
const totalInvoices = ref(0)
const infoData = ref({})

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
    await nextTick()
    if (props.data) {
        loading_invoices.value = props.data.loading_invoices
        totalInvoices.value = props.data.total_invoices
        selectedInvoice.value = props.data.selected_invoice ? [props.data.selected_invoice] : []
        selectedContract.value = props.data.selected_contract ? [props.data.selected_contract] : []
        selectedPerson.value = props.data.selected_person
    }
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

const onPersonSaved = async (item) => {
    selectedPerson.value = item;
    //emitChange();
    closeAllRegions();
};

const onContractSelected = async (item) => {
    if (selectedContract?.value[0]?.id == item.id) {
        selectedContract.value = []
    } else {
        selectedContract.value = [item];
    }
    closeAllRegions();
}

const onInvoiceSelected = async (item) => {
    if (selectedInvoice.value.includes(item)) {
        selectedInvoice.value = []
    }
    selectedInvoice.value = [item];
    closeAllRegions();
}

const emitChange = () => {
    loading_invoices.value = true;
    infoData.value = {
        loading_invoices: loading_invoices.value,
        total_invoices: totalInvoices.value,
        selected_invoice: selectedInvoice?.value?.length > 0 ? selectedInvoice.value[0] : null,
        selected_contract: selectedContract?.value?.length > 0 ? selectedContract.value[0] : null,
        selected_person: selectedPerson.value || null
    }
    emit('change', infoData.value)
}

onMounted(() => {
    getDebouncedData()
    if (route.query.invoice_id) {
        selectedFilter.value = 'invoice'
    }
    if (route.query.contract_id) {
        selectedFilter.value = 'contract'
    }
})

watch(() => selectedFilter.value, (newVal) => {
    selectedContract.value = []
    selectedInvoice.value = []
    selectedPerson.value = null
    if (stop_watchers.value) return
    emitChange()
})

watch([
    selectedContract,
    selectedInvoice,
    selectedPerson
], () => {
    if (stop_watchers.value) return
    emitChange()
})

watch(() => props.data, (newVal) => {
    getDebouncedData()
}, { deep: true, immediate: true })

</script>
<template>
    <div id="wrapper" class="text-base">
        <h2 class="text-xl font-semibold mb-4">{{ $t('claim_block.selected_invoicess_commitment') }}</h2>
        <div class="gap-5 px-5 items-start">
            <div class="flex justify-between">
                <div class="w-fit">
                    <legend class="block text-sm font-medium text-slate-500 mb-2 bg-white p-1">
                        {{ t('claim_block.commitment_select_by') }}
                    </legend>
                    <fieldset class="p-5 my-2 border border-sky-200 rounded bg-sky-50 ">
                        <div class="flex items-center gap-5">
                            <!-- <label class="flex items-center">
                                <input type="radio" value="holder" v-model="selectedFilter" class="mr-2">
                                {{ $t('Titular') }}
                            </label> -->
                            <label class="flex items-center">
                                <input type="radio" value="contract" v-model="selectedFilter" class="mr-2">
                                {{ $t('contract') }}
                            </label>
                            <label class="flex items-center">
                                <input type="radio" value="invoice" v-model="selectedFilter" class="mr-2">
                                {{ $t('invoice') }}
                            </label>
                        </div>
                    </fieldset>
                </div>
                <div class="w-[30%] h-fit my-auto p-3 border border-slate-300 rounded">
                    <span v-if="!loading_invoices" class="m-auto">
                        {{ $t('claim_block.found_invoices') }}: {{ totalInvoices }}
                    </span>
                    <span v-else class="m-auto">
                        <Icon name="fa6-solid:spinner" class="animate-spin text-md text-slate-500" />
                        <span class="ml-2">{{ $t('common.loading') }}...</span>
                    </span>
                </div>
            </div>

            <!-- SELECT BY HOLDER -->
            <div v-if="selectedFilter == 'holder'">
                <div v-if="selectedPerson" class=" bg-green-100 p-4 rounded relative max-w-xl group">

                    <p class="flex justify-between">
                        <span class="font-semibold ">
                            {{ selectedPerson.full_name || selectedPerson.name + ' ' + selectedPerson.surname }} <br>
                            <span class="text-sm text-gray-500">{{ selectedPerson.token }}</span>
                        </span>
                        <span class="pr-[40px]">
                            <FieldDetail class="bg-red-500/20 font-medium rounded px-2 py-1" :label="$t('common.debt')" :value="formatMoneyWithCurrency(selectedPerson.debt_amount)" />
                        </span>
                    </p>
                    <button @click="openRegion('personEdit')"
                        class="absolute cursor-pointer shadow-md border text-sm w-8 h-8 bg-white right-3 top-3 rounded-md text-slate-600 opacity-0 transition-all duration-300 group-hover:opacity-100">
                        <Icon name="fa6-solid:pencil" />
                    </button>
                </div>
                <div v-else class="mt-2">
                    <ButtonSeleccio @click="openRegion('personEdit')">{{ $t('claim_block.select_affected') }}
                    </ButtonSeleccio>
                </div>
            </div>

            <!-- SELECT BY CONTRACT -->
            <div v-if="selectedFilter == 'contract'" class="mt-3">
                <div v-if="selectedContract && selectedContract.length > 0"
                    class=" bg-green-100 p-4 rounded relative max-w-2xl group">
                    <ContractDetail :id="selectedContract[0].id" @show-subregion="openRegion" :showPayment="false"
                        :showCommunication="false" :showImportantObservations="true" />
                    <button @click="openRegion('contractEdit')"
                        class="absolute cursor-pointer shadow-md border text-sm w-8 h-8 bg-white right-3 top-3 rounded-md text-slate-600 opacity-0 transition-all duration-300 group-hover:opacity-100">
                        <Icon name="fa6-solid:pencil" />
                    </button>
                </div>
                <div v-else class="mt-2">
                    <ButtonSeleccio @click="openRegion('contractEdit')">{{ $t('contract_block.select_single_contract') }}
                    </ButtonSeleccio>
                </div>
            </div>

            <!-- SELECT INVOICE -->
            <div v-if="selectedFilter == 'invoice'" class="mt-3">
                <div v-if="selectedInvoice && selectedInvoice.length > 0"
                    class=" bg-green-100 p-4 rounded relative max-w-2xl group">
                    <InvoiceDetail :id="selectedInvoice[0].id" @show-detail="openRegion" />
                    <button @click="openRegion('invoiceEdit')"
                        class="absolute cursor-pointer shadow-md border text-sm w-8 h-8 bg-white right-3 top-3 rounded-md text-slate-600 opacity-0 transition-all duration-300 group-hover:opacity-100">
                        <Icon name="fa6-solid:pencil" />
                    </button>
                </div>
                <div v-else class="mt-2">
                    <ButtonSeleccio @click="openRegion('invoiceEdit')">{{ $t('billing_block.select_invoice') }}
                    </ButtonSeleccio>
                </div>
            </div>
            <hr class="my-2" />
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
                <PersonSearch v-if="showRegionDetailComponent == 'personEdit'" @saved="onPersonSaved" />
                <AddContracts v-if="showRegionDetailComponent == 'contractEdit'" :multiple="false"
                    :selected_items="selectedContract" @item-clicked="onContractSelected" />
                <AddInvoices v-if="showRegionDetailComponent == 'invoiceEdit'" :multiple="false"
                    :selected_items="selectedInvoice" @item-clicked="onInvoiceSelected" />
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


</template>