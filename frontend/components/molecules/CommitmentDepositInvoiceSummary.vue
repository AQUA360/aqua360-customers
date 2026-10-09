<script setup>
import debounce from 'lodash.debounce';
import InvoiceRegion from '~/components/organisms/InvoiceRegion.vue';
import InvoiceSelectionRegion from '../organisms/InvoiceSelectionRegion.vue';


const { t } = useI18n();

const props = defineProps({
    data: Object,
    isSubRegion: {
        type: Boolean,
        default: false
    }
});

const emit = defineEmits(['change']);

const stop_watchers = ref(false);
const loading_invoices = ref(true);
const totalInvoices = ref(0)
const invoices = ref([])
const ignoredInvoices = ref([])
const selectedInvoices = ref([])

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
        totalInvoices.value = props.data.invoices.length
        invoices.value = props.data.invoices
        ignoredInvoices.value = props.data.ignored_invoices
        selectedInvoices.value = invoices.value.filter(invoice => !ignoredInvoices.value.includes(invoice))
    }
    await nextTick()
    stop_watchers.value = false
    loading_invoices.value = false;
}

const getDebouncedData = debounce(getData, 300);

const updateSelectedInvoices = (invoices_ids) => {
    ignoredInvoices.value = invoices.value.filter(invoice => !invoices_ids.includes(invoice.id))
    emitChange()
}

const openRegion = (component, id = null) => {
    closeAllRegions();
    showRegionDetailComponent.value = component;
    regionDetailId.value = id;
    showRegion.value = true;
};

const emitChange = () => {

    let remainingInvoices = invoices.value.filter(invoice => !ignoredInvoices.value.includes(invoice))
    let infoData = {
        invoices: invoices.value,
        ignored_invoices: ignoredInvoices.value,
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
    <div id="wrapper" class="text-base">
        <h2 class="text-xl font-semibold mb-4">{{ $t('claim_block.check_affected_invoices') }}</h2>
        <div v-if="!isSubRegion" class="flex justify-end px-5">
            <div class="w-[30%] h-fit my-auto p-3 border border-slate-300 rounded">
                <span v-if="!loading_invoices" class="m-auto">
                    {{ $t('claim_block.selected_affected_invoices') }}: {{ totalInvoices - ignoredInvoices.length }}
                </span>
                <span v-else class="m-auto">
                    <Icon name="fa6-solid:spinner" class="animate-spin text-md text-slate-500" />
                    <span class="ml-2">{{ $t('common.loading') }}...</span>
                </span>
            </div>
        </div>

        <div class="m-2 border border-slate-300 rounded p-4 customers-shadow">
            <!-- <div v-if="invoices.length == 1" class="absolute z-10 top-0 right-0 text-sm w-full h-full opacity-25 bg-slate-100 flex justify-center items-center">
            </div> -->
            <InvoiceSelectionRegion :selectedInvoices="invoices" :checked_invoices="selectedInvoices"
                @update:selected="updateSelectedInvoices" :disabled="invoices.length == 1" @show-detail="openRegion" />
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
                <InvoiceRegion v-if="showRegionDetailComponent === 'InvoiceRegion'" :id="parseInt(regionDetailId)"
                    :isSubRegion="true" />
            </div>
        </div>
    </div>


</template>