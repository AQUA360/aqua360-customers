<script setup>
import { useToast } from 'vue-toastification';
import H1 from '~/components/atoms/H1.vue';
import { checkPermission } from '~/middleware/permission';
import ButtonOutline from '~/components/atoms/ButtonOutline.vue';
import CommitmentDepositInvoiceSummary from '~/components/molecules/CommitmentDepositInvoiceSummary.vue';

const { t } = useI18n();
const toast = useToast();
const objectPermissions = ref(null);
const { $PaymentApiService, $ConfiglistApiService } = useNuxtApp();

const loading = ref(false);
const loadingFile = ref(false);
const found_invoices = ref([]);
const ignored_invoices = ref([]);
const show_data = ref({})
const show_first_info = ref(true)

const invoiceStatuses = ref([])
const invoiceSeries = ref([])
const origins = ref([])
const loadingInvoiceStatuses = ref(false)
const loadingInvoiceSeries = ref(false)
const loadingOrigins = ref(false)

const issueStartDate = ref(null);
const issueEndDate = ref(null);
const expireStartDate = ref(null);
const expireEndDate = ref(null);
const selectedInvoiceStatuses = ref([])
const selectedInvoiceSeries = ref([])
const selectedOrigins = ref([])

const regionDetailComponent = ref(null)
const regionDetailId = ref(null)
const showRegion = ref(false)
const isSubRegionOpen = ref(false)

const fetchConfigData = async (service, entity, targetArray, loading) => {
    try {
        loading.value = true;
        const data = await $ConfiglistApiService.getAll(service + '/' + entity);
        targetArray.value = [];

        if (data.results) {
            data.results.forEach(data => {
                targetArray.value.push({
                    label: data.name || data.token,
                    code: data.id,
                    token: data.token || data.id
                })
            });
        }
    } catch (error) {
        console.error(`Error fetching ${entity}:`, error);
    } finally {
        loading.value = false;
    }
}

const search = async () => {
    if (!issueStartDate.value && !issueEndDate.value) {
        toast.error(t('common.required_fields'));
        return;
    }

    show_first_info.value = false;
    loading.value = true;
    try {
        let data = {
            issue_start_date: issueStartDate.value,
            issue_end_date: issueEndDate.value,
            expire_start_date: expireStartDate.value,
            expire_end_date: expireEndDate.value,
            invoice_statuses: selectedInvoiceStatuses.value.map(status => status.code),
            invoice_series: selectedInvoiceSeries.value.map(series => series.code),
            origins: selectedOrigins.value.map(origin => origin.code)
        }

        const response = await $PaymentApiService.getSiiInvoices(data);
        found_invoices.value = response.invoices;
        show_data.value.invoices = response.invoices;
        ignored_invoices.value = [];
        show_data.value.ignored_invoices = [];
    } catch (error) {
        console.error("Error fetching invoices:", error);
    } finally {
        loading.value = false;
    }
}

const loadSelectData = async () => {
    const today = new Date();
    const todayString = today.toISOString().split('T')[0];
    issueStartDate.value = todayString;
    issueEndDate.value = todayString;
    await fetchConfigData('billing', 'invoice-status', invoiceStatuses, loadingInvoiceStatuses);
    await fetchConfigData('billing', 'invoice-serie', invoiceSeries, loadingInvoiceSeries);
    await fetchConfigData('pricing', 'product-origin', origins, loadingOrigins);
}

const handleInvoicesChange = (data) => {
    ignored_invoices.value = data.ignored_invoices
}

const getFile = async () => {
    loadingFile.value = true;
    try {
        let data = {
            invoices: found_invoices.value.filter(invoice => !ignored_invoices.value.map(invoice => invoice.id).includes(invoice.id)).map(invoice => invoice.id)
        }
        const response = await $PaymentApiService.getSiiFile(data)
        if (response) {
            downloadFile(response.file, response.name)
        }
    } catch (error) {
        console.error("Error fetching file:", error);
    } finally {
        loadingFile.value = false;
    }
}

const downloadFile = (file, name) => {
    try {
        if (file?.type !== "application/xml") {
          const blob = new Blob([file], { type: "application/xml" });
          file = blob;
        }

        const link = document.createElement('a');
        const file_url = URL.createObjectURL(file);
        link.href = file_url
        link.download = name;
    
        link.click();
    
        setTimeout(() => {
          window.URL.revokeObjectURL(file_url);
        }, 250);
    } catch (error) {
        console.error("Error downloading file:", error);
    }
}

const showDetail = (component, id, open = false) => {
    regionDetailComponent.value = component
    regionDetailId.value = id
    showRegion.value = true
    isSubRegionOpen.value = open
}

const closeSubRegion = () => {
    regionDetailComponent.value = null
    regionDetailId.value = null
    showRegion.value = false
    isSubRegionOpen.value = false
}

const handleSubRegionEvent = (event) => {
    isSubRegionOpen.value = event
}

onMounted(async () => {
    objectPermissions.value = await checkPermission($PaymentApiService);
    if (!objectPermissions.value.can_change) {
        toast.error(t('common.no_permissions'));
        return navigateTo('/');
    }
    await loadSelectData();
})
</script>

<template>
    <div id="wrapper" class="text-base p-4 max-w-full">
        <div class="flex justify-between items-center mb-6">
            <H1>{{ $t(`billing_block.mng_sii`) }}</H1>
        </div>

        <div class="wrapper text-base max-w-full">
            <div class="flex">
                <div class="p-2 grid grid-cols-[1fr,auto] items-center gap-2">
                    <span>{{ t('invoices') }}</span>
                    <button :disabled="found_invoices.length == 0 && !loading" @click="showDetail('SiiInvoices', null, true)"
                        class="text-sky-500 enabled:hover:underline enabled:hover:text-sky-600 enabled:cursor-pointer enabled:font-bold disabled:text-slate-400">
                        {{ found_invoices.length - ignored_invoices.length }}
                    </button>
                </div>

            </div>
            <div class="border border-gray-300 rounded p-4 bg-white">
                <div v-if="show_first_info"
                    class="border-l-2 border-sky-500 rounded-r-md p-2 bg-sky-50 text-sky-500 mb-3">
                    {{ t('common.start_by_filtering') }}
                </div>
                <div v-else-if="!show_first_info && found_invoices.length == 0 && !loading"
                    class="border-l-2 border-orange-500 rounded-r-md p-2 bg-orange-50 text-orange-500 mb-3">
                    {{ t('common.no_data_found') }}
                </div>

                <div class="grid grid-cols-2 gap-3 mb-3">
                    <div class="pr-2">
                        <label class="block text-sm font-medium text-slate-600 mb-2">
                            {{ $t('common.send_date') }} <span class="text-red-500">*</span></label>
                        <div class="grid grid-cols-[auto,1fr,auto,1fr] items-center gap-2">
                            <label class="block text-sm font-medium text-slate-600 mb-2 mr-5">{{ $t('common.from') }}:</label>
                            <AtomsInputDate v-model="issueStartDate" class="mb-2" />
                            <label class="block text-sm font-medium text-slate-600 mb-2 mr-5">{{ $t('common.to') }}:</label>
                            <AtomsInputDate v-model="issueEndDate" class="mb-2" />
                        </div>
                    </div>

                    <div>
                        <label class="block text-sm font-medium text-slate-600 mb-2">
                            {{ $t('invoice') }}: {{ $t('common.origin') }}
                        </label>
                        <v-select multiple class="block w-full mr-1 custom-select" v-model="selectedOrigins"
                            :options="origins" :loading="loadingOrigins" />
                    </div>
                    <div>
                        <label class="block text-sm font-medium text-slate-600 mb-2">
                            {{ $t('invoice') }}: {{ $t('common.status') }}
                        </label>
                        <v-select multiple class="block w-full mr-1 custom-select" v-model="selectedInvoiceStatuses"
                            :options="invoiceStatuses" :loading="loadingInvoiceStatuses" />
                    </div>
                    <div>
                        <label class="block text-sm font-medium text-slate-600 mb-2">
                            {{ $t('invoice') }}: {{ $t('billing_block.serie') }}
                        </label>
                        <v-select multiple class="block w-full mr-1 custom-select" v-model="selectedInvoiceSeries"
                            :options="invoiceSeries" :loading="loadingInvoiceSeries" />
                    </div>
                </div>

                <div>
                    <button class="button-default flex items-center gap-2" @click="search">
                        <Icon :name="loading ? 'fa6-solid:spinner' : 'fa6-solid:magnifying-glass'"
                            :class="{ 'animate-spin': loading }" />
                        {{ loading ? $t('common.loading') + '...' : $t('dashboard.search') }}
                    </button>
                </div>

                <hr class="my-3">
                <div class="flex gap-3">
                    <ButtonOutline :disabled="found_invoices.length == 0 || loadingFile" @click="getFile">
                        {{ loadingFile ? $t('common.loading') + '...' : $t('billing_block.download_sii') }}</ButtonOutline>
                </div>
            </div>
        </div>

    </div>
    <div role="region" id="right_page"
        class="fixed h-full border-l border-gray-100 top-0 right-0 transition-all duration-500 ease py-2 text-base bg-white"
        :class="{ 'translate-x-0': showRegion, 'translate-x-[2000px]': !showRegion, 'w-[95%]': isSubRegionOpen, 'w-1/2': !isSubRegionOpen }">
        <div id="region_nav" class="mb-3 px-3">
            <button @click="closeSubRegion" class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300">
                <Icon name="fa6-solid:angles-right" class="text-slate-500" />
            </button>
        </div>
        <div class="px-10">
            <CommitmentDepositInvoiceSummary v-if="regionDetailComponent === 'SiiInvoices'" 
             :data="show_data" @change="handleInvoicesChange" :isSubRegion="true" />
        </div>
    </div>
</template>
