<script setup>
import SearchEntityInput from './SearchEntityInput.vue';
import OptionSelectorGroup from '../atoms/OptionSelectorGroup.vue';

const props = defineProps({
  billing_data: Object,
})

const { t } = useI18n();
const emit = defineEmits(['change'])
const { $ConfiglistApiService } = useNuxtApp();

const invoice_filter_data = ref({})

const selectedAddedInvoices = ref([])
const selectedAddedBilling = ref([])

const expireStartDate = ref(null)
const expireEndDate = ref(null)
const issueStartDate = ref(null)
const issueEndDate = ref(null)
const returnStartDate = ref(null)
const returnEndDate = ref(null)

const selectedPaymentTypes = ref([])
const selectedInvoiceStatuses = ref([])
const selectedRejectionReasons = ref([])
const selectedRejectionTypes = ref([])
const selectedOrigins = ref([])
const selectedSeries = ref([])
const selectedCompanies = ref([])

const group_by_customer = ref(false)
const consumptionSelect = ref([])
const modificationSelect = ref([])

const attachInvoices = ref(true)
const attachReadings = ref(true)

const consumptionOptions = [
  { value: 'responsible_consumption', name: 'responsible_consumption' },
  { value: 'irresponsible_consumption', name: 'billing_block.consumption_irresponsible' },
]

const modificationOptions = [
  { value: 'manually_modified', name: 'common.manually_modified' },
  { value: 'not_modified', name: 'common.not_modified' },
]


const paymentTypes = ref([])
const invoiceStatuses = ref([])
const rejectionReasons = ref([])
const rejectionTypes = ref([])
const origins = ref([])
const series = ref([])
const companies = ref([])

const loadingPaymentTypes = ref(false)
const loadingInvoiceStatuses = ref(false)
const loadingRejectionReasons = ref(false)
const loadingRejectionTypes = ref(false)
const loadingOrigins = ref(false)
const loadingSeries = ref(false)
const loadingCompanies = ref(false)

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

const loadRejectionTypes = async () => {
  loadingRejectionTypes.value = true;
  try {
    const data = await $ConfiglistApiService.getAll('billing/reject-motive-type');
    rejectionTypes.value = [];
    if (data.results) {
      data.results.forEach(data => {
        rejectionTypes.value.push({
          label: data.name,
          code: data.id,
          rejects: data.rejects.map(r => r.name)
        })
      })
    }
  } catch (err) {
    console.error(err)
  } finally {
    loadingRejectionTypes.value = false;
  }
}

const loadSelectData = async () => {
  await fetchConfigData('contract', 'contract-payment-type', paymentTypes, loadingPaymentTypes);
  await fetchConfigData('billing', 'invoice-status', invoiceStatuses, loadingInvoiceStatuses);
  await fetchConfigData('billing', 'reject-motive', rejectionReasons, loadingRejectionReasons);
  await fetchConfigData('pricing', 'product-origin', origins, loadingOrigins);
  await fetchConfigData('billing', 'invoice-serie', series, loadingSeries);
  await fetchConfigData('service', 'company', companies, loadingCompanies);
  //await fetchConfigData('billing', 'reject-motive-type', rejectionTypes, loadingRejectionTypes);
  await loadRejectionTypes()
}

const loadData = async (billingData) => {
  if (billingData?.payment_types) selectedPaymentTypes.value = paymentTypes.value.filter(c => billingData?.payment_types.includes(c.code))
  if (billingData?.invoice_statuses) selectedInvoiceStatuses.value = invoiceStatuses.value.filter(c => billingData?.invoice_statuses.includes(c.code))
  if (billingData?.rejection_reasons) selectedRejectionReasons.value = rejectionReasons.value.filter(c => billingData?.rejection_reasons.includes(c.code))
  if (billingData?.group_by_customer) group_by_customer.value = billingData?.group_by_customer
  if (billingData?.invoices) selectedAddedInvoices.value = billingData?.invoices
  if (billingData?.billings) selectedAddedBilling.value = billingData?.billings
  if (billingData?.issue_start_date) issueStartDate.value = billingData?.issue_start_date
  if (billingData?.issue_end_date) issueEndDate.value = billingData?.issue_end_date
  if (billingData?.expire_start_date) expireStartDate.value = billingData?.expire_start_date
  if (billingData?.expire_end_date) expireEndDate.value = billingData?.expire_end_date
  if (billingData?.return_start_date) returnStartDate.value = billingData?.return_start_date
  if (billingData?.return_end_date) returnEndDate.value = billingData?.return_end_date
  if (billingData?.consumption) consumptionSelect.value = billingData?.consumption
  if (billingData?.modification) modificationSelect.value = billingData?.modification
  if (billingData?.series) selectedSeries.value = series.value.filter(c => billingData?.series.includes(c.code))
  if (billingData?.companies) selectedCompanies.value = companies.value.filter(c => billingData?.companies.includes(c.code))
  if (billingData?.rejection_types) selectedRejectionTypes.value = rejectionTypes.value.filter(c => billingData?.rejection_types.includes(c.code))
  if (billingData?.attach_invoices) attachInvoices.value = billingData?.attach_invoices
  if (billingData?.attach_readings) attachReadings.value = billingData?.attach_readings
}

const onInvoiceSelected = async (invoice) => {
  selectedPaymentTypes.value = []
  selectedInvoiceStatuses.value = []
  selectedRejectionReasons.value = []
  selectedOrigins.value = []
  selectedRejectionTypes.value = []
  expireStartDate.value = null
  expireEndDate.value = null
  issueStartDate.value = null
  issueEndDate.value = null
  selectedAddedBilling.value = []
  consumptionSelect.value = []
  modificationSelect.value = []
  selectedSeries.value = []
  returnStartDate.value = null
  returnEndDate.value = null
  selectedCompanies.value = []

  if (!selectedAddedInvoices.value.includes(invoice)) {
    selectedAddedInvoices.value.push(invoice);
  }
  await emitChange()
}

const onBillingSelected = async (billing) => {
  selectedPaymentTypes.value = []
  selectedInvoiceStatuses.value = []
  selectedRejectionReasons.value = []
  selectedOrigins.value = []
  selectedRejectionTypes.value = []
  expireStartDate.value = null
  expireEndDate.value = null
  issueStartDate.value = null
  issueEndDate.value = null
  selectedAddedInvoices.value = []
  consumptionSelect.value = []
  modificationSelect.value = []
  selectedSeries.value = []
  returnStartDate.value = null
  returnEndDate.value = null
  selectedCompanies.value = []
  attachInvoices.value = false
  attachReadings.value = false
  if (!selectedAddedBilling.value.includes(billing)) {
    selectedAddedBilling.value.push(billing);
  }
  await emitChange()
}

const changeConsumption = (value) => {
  if (consumptionSelect.value.includes(value)) {
    consumptionSelect.value = consumptionSelect.value.filter(c => c !== value)
  } else {
    consumptionSelect.value.push(value)
  }
}

const changeModification = (value) => {
  if (modificationSelect.value.includes(value)) {
    modificationSelect.value = modificationSelect.value.filter(c => c !== value)
  } else {
    modificationSelect.value.push(value)
  }
}

const removeSelectedInvoice = async (item) => {
  selectedAddedInvoices.value = selectedAddedInvoices.value.filter(c => c.id !== item.id)
  await emitChange()
}

const removeSelectedBilling = async (item) => {
  selectedAddedBilling.value = selectedAddedBilling.value.filter(c => c.id !== item.id)
  await emitChange()
}

const toggleAttachInvoices = async () => {
  attachInvoices.value = !attachInvoices.value
  if (!attachInvoices.value) attachReadings.value = false
  await emitChange()
}

const toggleAttachReadings = async () => {
  attachReadings.value = !attachReadings.value && attachInvoices.value
  await emitChange()
}

const emitChange = () => {
  invoice_filter_data.value = {
    invoice_statuses: selectedInvoiceStatuses.value.map(c => c.code),
    rejection_reasons: selectedRejectionReasons.value.map(c => c.code),
    origins: selectedOrigins.value.map(c => c.code),
    payment_types: selectedPaymentTypes.value.map(c => c.token),
    rejection_types: selectedRejectionTypes.value.map(c => c.token),
    issue_start_date: issueStartDate.value,
    issue_end_date: issueEndDate.value,
    expire_start_date: expireStartDate.value,
    expire_end_date: expireEndDate.value,
    return_start_date: returnStartDate.value,
    return_end_date: returnEndDate.value,
    invoices: selectedAddedInvoices.value,
    billings: selectedAddedBilling.value,
    group_by_customer: group_by_customer.value,
    consumption: consumptionSelect.value,
    modification: modificationSelect.value,
    series: selectedSeries.value.map(c => c.token),
    companies: selectedCompanies.value.map(c => c.token),
    attach_invoices: attachInvoices.value,
    attach_readings: attachReadings.value,
  }
  emit('change', invoice_filter_data.value)
}



onMounted(async () => {
  await loadSelectData()
  await loadData(props.billing_data)
  consumptionSelect.value = consumptionOptions.map(c => c.value)
  modificationSelect.value = modificationOptions.map(c => c.value)
})

watch([
  selectedPaymentTypes,
  selectedInvoiceStatuses,
  selectedRejectionReasons,
  selectedOrigins,
  selectedRejectionTypes,
  issueStartDate,
  issueEndDate,
  expireStartDate,
  expireEndDate,
  group_by_customer,
  consumptionSelect,
  modificationSelect,
  selectedSeries,
  returnStartDate,
  returnEndDate,
  selectedCompanies,
], async () => {
  if (selectedAddedInvoices.value.length > 0 || selectedAddedBilling.value.length > 0) {
    if (
      selectedPaymentTypes.length > 0 ||
      selectedInvoiceStatuses.length > 0 ||
      selectedRejectionReasons.length > 0 ||
      selectedOrigins.length > 0 ||
      selectedRejectionTypes.length > 0 ||
      issueStartDate.value ||
      issueEndDate.value ||
      expireStartDate.value ||
      expireEndDate.value ||
      consumptionSelect.value.length > 0 ||
      modificationSelect.value.length > 0 ||
      selectedSeries.value.length > 0 ||
      returnStartDate.value ||
      returnEndDate.value ||
      selectedCompanies.value.length > 0
    ) {
      selectedAddedInvoices.value = []
      selectedAddedBilling.value = []
    }
  }
  await emitChange()
}, { deep: true });

watch(props.billing_data, async (newVal) => {
  await loadData(newVal)
}, { deep: true });

</script>

<template>
  <div class="py-3 bg-white rounded-lg mt-3">

    <div class="grid grid-cols-3 gap-4 mb-3">
      <!-- <div>
        <div class="text-sm font-medium text-gray-500 mb-2 flex items-center gap-2">
          <abbr :title="t('En cas de no seleccionar, cada client rebrà una comunicació per factura')"
            class="flex items-center">
            <Icon name="fa6-solid:circle-info" class="text-slate-500" />
          </abbr>
          <span>
            {{ t('Agrupar per client') }}:
          </span>
        </div>
        <input type="checkbox" v-model="group_by_customer" />
      </div> -->
      <div class="h-fit items-center my-auto">
        <div class="text-sm font-medium text-gray-500 mb-2">
          {{ t('customer_service_block.select_consumption_type') }}:
        </div>
        <OptionSelectorGroup :options="consumptionOptions" :selected-values="consumptionSelect"
          selection-mode="multiple" indicator-type="checkbox" @select="changeConsumption" />
      </div>
      <div class="h-fit items-center my-auto">
        <div class="text-sm font-medium text-gray-500 mb-2">
          {{ t('customer_service_block.select_modification_type') }}:
        </div>
        <OptionSelectorGroup :options="modificationOptions" :selected-values="modificationSelect"
          selection-mode="multiple" indicator-type="checkbox" @select="changeModification" />
      </div>
      <div class="h-fit items-center my-auto">
        <div class="text-sm font-medium text-gray-500 mb-2">
          {{ t('customer_service_block.select_attach_invoices') }}:
        </div>
        <div class="flex gap-x-2 items-center">
          <div class="flex gap-3 h-fit items-center my-auto">
            <div @click="toggleAttachInvoices"
              class="cursor-pointer flex items-center gap-2 px-3 py-1.5 rounded-md transition-all duration-200"
              :class="[attachInvoices ? 'bg-sky-50 ring-1 ring-sky-500' : 'hover:bg-gray-50']">
              <div class="w-3.5 h-3.5 rounded-sm border-2 flex items-center justify-center shrink-0"
                :class="[attachInvoices ? 'border-sky-500 bg-sky-500' : 'border-gray-300']">
                <Icon v-if="attachInvoices" name="fa6-solid:check" class="text-white" />
              </div>
              <span class="text-xs font-medium" :class="[attachInvoices ? 'text-sky-700' : 'text-gray-600']">
                {{ t('customer_service_block.attach_invoices') }}
              </span>
            </div>
          </div>
          <div class="flex gap-3 h-fit items-center my-auto">
            <div @click="toggleAttachReadings" :disabled="!attachInvoices"
              class="flex items-center gap-2 px-3 py-1.5 rounded-md transition-all duration-200"
              :class="[
                attachReadings ? 'bg-sky-50 ring-1 ring-sky-500 cursor-pointer' : !attachInvoices ? 'opacity-50 cursor-not-allowed' : 'hover:bg-gray-50 cursor-pointer'
                ]">
              <div class="w-3.5 h-3.5 rounded-sm border-2 flex items-center justify-center shrink-0"
                :class="[attachReadings ? 'border-sky-500 bg-sky-500' : 'border-gray-300']">
                <Icon v-if="attachReadings" name="fa6-solid:check" class="text-white" />
              </div>
              <span class="text-xs font-medium" :class="[attachReadings ? 'text-sky-700' : 'text-gray-600']">
                {{ t('customer_service_block.attach_readings') }}
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div class="col-span-2">
      <div class="grid grid-cols-3 gap-4">
        <div class="pr-2 border-r border-slate-200">
          <label class="block text-sm font-medium text-slate-600 mb-2">{{ $t('common.send_date') }}</label>
          <div class="grid grid-cols-[auto,1fr,auto,1fr] items-center gap-2">
            <label class="block text-sm font-medium text-slate-600 mb-2 mr-5">{{ $t('common.from') }}:</label>
            <AtomsInputDate v-model="issueStartDate" class="mb-2" />
            <label class="block text-sm font-medium text-slate-600 mb-2 mr-5">{{ $t('common.to') }}:</label>
            <AtomsInputDate v-model="issueEndDate" class="mb-2" />
          </div>
        </div>

        <div class="pr-2 border-r border-slate-200">
          <label class="block text-sm font-medium text-slate-600 mb-2">{{ $t('common.due_date') }}</label>
          <div class="grid grid-cols-[auto,1fr,auto,1fr] items-center gap-2">
            <label class="block text-sm font-medium text-slate-600 mb-2 mr-5">{{ $t('common.from') }}:</label>
            <AtomsInputDate v-model="expireStartDate" class="mb-2" />
            <label class="block text-sm font-medium text-slate-600 mb-2 mr-5">{{ $t('common.to') }}:</label>
            <AtomsInputDate v-model="expireEndDate" class="mb-2" />
          </div>
        </div>

        <div class="pr-2 border-r border-slate-200">
          <label class="block text-sm font-medium text-slate-600 mb-2">{{ $t('billing_block.sepa_return_date')
            }}</label>
          <div class="grid grid-cols-[auto,1fr,auto,1fr] items-center gap-2">
            <label class="block text-sm font-medium text-slate-600 mb-2 mr-5">{{ $t('common.from') }}:</label>
            <AtomsInputDate v-model="returnStartDate" class="mb-2" />
            <label class="block text-sm font-medium text-slate-600 mb-2 mr-5">{{ $t('common.to') }}:</label>
            <AtomsInputDate v-model="returnEndDate" class="mb-2" />
          </div>
        </div>
      </div>
    </div>

    <div class="grid grid-cols-2 gap-4">
      <SearchEntityInput :service="$InvoiceApiService" @select="onInvoiceSelected"
        :title="$t('search_block.search_invoice')" :result_value="'serie_final'" class="mt-auto" />
      <div v-if="selectedAddedInvoices?.length > 0" class="mb-2">
        <label class="block text-sm font-medium text-slate-600 mb-2">{{ $t('billing_block.selected_invoices') }}</label>
        <div class="flex flex-wrap gap-2 ">
          <span v-for="invoice in selectedAddedInvoices" :key="invoice.id"
            class="group relative bg-slate-100 text-slate-800 px-3 py-1 rounded-full text-sm border border-slate-300 flex items-center gap-2">
            <span>
              {{ invoice.token }}
            </span>
            <button @click="removeSelectedInvoice(invoice)"
              class="absolute right-0 top-0 h-4 w-4 bg-white rounded-full text-slate-500 opacity-0 hover:text-slate-700 hover:underline group-hover:opacity-100 transition-all duration-300">
              <Icon name="fa6-solid:xmark"
                class="text-red-500 text-sm m-auto opacity-0 group-hover:opacity-100 m-auto" />
            </button>
          </span>
        </div>
      </div>
      <span v-else></span>

      <SearchEntityInput :service="$BillingApiService" @select="onBillingSelected"
        :title="$t('search_block.search_billing')" :result_value="'title_final'" class="mt-auto" />
      <div v-if="selectedAddedBilling?.length > 0" class="mb-2">
        <label class="block text-sm font-medium text-slate-600 mb-2">{{ $t('billing_block.selected_billings') }}</label>
        <div class="flex flex-wrap gap-2 ">
          <span v-for="billing in selectedAddedBilling" :key="billing.id"
            class="group relative bg-slate-100 text-slate-800 px-3 py-1 rounded-full text-sm border border-slate-300 flex items-center gap-2">
            <span>
              {{ billing.token }}
            </span>
            <button @click="removeSelectedBilling(billing)"
              class="absolute right-0 top-0 h-4 w-4 bg-white rounded-full text-slate-500 opacity-0 hover:text-slate-700 hover:underline group-hover:opacity-100 transition-all duration-300">
              <Icon name="fa6-solid:xmark"
                class="text-red-500 text-sm m-auto opacity-0 group-hover:opacity-100 m-auto" />
            </button>
          </span>
        </div>
      </div>
      <span v-else></span>


      <div>
        <label class="block text-sm font-medium text-slate-600 mb-2">{{ $t('common.status') }}: {{ $t('invoice')
          }}</label>
        <v-select multiple class="block w-full mr-1 custom-select" v-model="selectedInvoiceStatuses"
          :options="invoiceStatuses" :loading="loadingInvoiceStatuses" />
      </div>

      <div>
        <label class="block text-sm font-medium text-slate-600 mb-2">{{ $t('company') }}</label>
        <v-select multiple class="block w-full mr-1 custom-select" v-model="selectedCompanies" :options="companies"
          :loading="loadingCompanies" />
      </div>

      <div>
        <label class="block text-sm font-medium text-slate-600 mb-2">{{ $t('common.origin') }}</label>
        <v-select multiple class="block w-full mr-1 custom-select" v-model="selectedOrigins" :options="origins"
          :loading="loadingOrigins" />
      </div>

      <div>
        <label class="block text-sm font-medium text-slate-600 mb-2">{{ $t('billing_block.serie') }}</label>
        <v-select multiple class="block w-full mr-1 custom-select" v-model="selectedSeries" :options="series"
          :loading="loadingSeries" />
      </div>

      <div>
        <label class="block text-sm font-medium text-slate-600 mb-2">{{ $t('common.payment_method') }}</label>
        <v-select multiple class="block w-full mr-1 custom-select" v-model="selectedPaymentTypes"
          :options="paymentTypes" :loading="loadingPaymentTypes" />
      </div>

      <!-- <div>
        <label class="block text-sm font-medium text-slate-600 mb-2">{{ $t('Devolució') }}</label>
        <v-select multiple class="block w-full mr-1 custom-select" v-model="selectedRejectionReasons"
          :options="rejectionReasons" :loading="loadingRejectionReasons" />
      </div> -->

      <div>
        <label class="block text-sm font-medium text-slate-600 mb-2">{{ $t('common.devolution_type') }}</label>
        <v-select multiple class="block w-full mr-1 custom-select" v-model="selectedRejectionTypes"
          :options="rejectionTypes" :loading="loadingRejectionTypes" />
        <div v-if="selectedRejectionTypes.length > 0" class="mt-2 p-3 bg-slate-50 rounded-lg border border-slate-200">
          <div class="text-xs font-medium text-slate-600 mb-2">{{
            $t('customer_service_block.available_rejection_reasons') }}:</div>
          <div class="space-y-2">
            <div v-for="rejectType in selectedRejectionTypes" :key="rejectType.code" class="space-y-1">
              <div class="text-xs font-medium text-slate-700">{{ rejectType.label }}:</div>
              <div class="flex flex-wrap gap-1.5">
                <span v-for="reject in rejectType.rejects" :key="reject"
                  class="inline-flex items-center px-2 py-1 rounded-md text-xs font-medium bg-white border border-slate-300 text-slate-700 shadow-sm">
                  {{ reject }}
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.grid {
  transition: all 0.3s ease;
}
</style>