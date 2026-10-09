<script setup>
import { useToast } from 'vue-toastification';
import { checkPermission } from '~/middleware/permission';
import AddInvoices from '../molecules/AddInvoices.vue';
import AddContracts from '../molecules/AddContracts.vue';
import ButtonOutline from '../atoms/ButtonOutline.vue';
import InvoiceRegion from './InvoiceRegion.vue';
import ContractRegion from './ContractRegion.vue';
import AppLoading from '~/components/atoms/AppLoading.vue';
import Pagination from '~/components/molecules/Pagination.vue';
import PersonSearch from './PersonSearch.vue';
import PersonRegion from './PersonRegion.vue';

const { t } = useI18n()
const toast = useToast();
const objectPermissions = ref(null);
const { $apiManager, $ConfiglistApiService, $InvoiceApiService, $ConfigProjectApiService, $ExploitationApiService, $DocumentManagerApiService, $BillingApiService } = useNuxtApp();
import { openAuthenticatedFileUrl } from '~/utils/open-authenticated-file';
const emit = defineEmits(['refresh']);

/* 

ONCE DONE, DELETE ELECTRONICINVOICEEDIT.VUE AND SUBCOMPONENTS

*/

const loading = ref(true);
const loadingPayment = ref(false)

const is_fetching = ref(false)
const saving = ref(false)
const attemptedSave = ref(false)

const loadingExploitations = ref(false)
const loadingBillings = ref(false)
const loadingOrigins = ref(false)
const loadingInvoiceStatuses = ref(false)

const filter_issue_date_start = ref('')
const filter_issue_date_end = ref('')

const exploitations = ref([])
const billings = ref([])
const invoiceStatuses = ref([])
const origins = ref([])

const selectedExploitation = ref(null)
const selectedBilling = ref(null)
const selectedOrigins = ref(null);
const selectedInvoiceStatuses = ref([])
const selectedContracts = ref([])
const selectedInvoices = ref([])
const selectedPersons = ref([])

const invoices = ref([]);
const hasSearched = ref(false);

const invoicePagination = ref({
  page: 1,
  perPage: 50,
  total: 0,
  totalPages: 0,
  previous: null,
  next: null,
  isFiltered: false,
});

const paginatedInvoices = computed(() => {
  const start = (invoicePagination.value.page - 1) * invoicePagination.value.perPage;
  return invoices.value.slice(start, start + invoicePagination.value.perPage);
});

const updateInvoicePagination = () => {
  const total = invoices.value.length;
  const totalPages = Math.max(1, Math.ceil(total / invoicePagination.value.perPage));
  invoicePagination.value.total = total;
  invoicePagination.value.totalPages = totalPages;
  if (invoicePagination.value.page > totalPages) {
    invoicePagination.value.page = totalPages;
  }
};

const handleInvoicePageChange = (newPage) => {
  invoicePagination.value.page = newPage;
};

const showRegionDetailComponent = ref(null)
const regionDetailId = ref(null)
const isSubRegionOpen = ref(false);

const highlightFooter = ref(false);

const taskId = ref(null);
const loadingTask = ref(false);

const confirmedInvoiceToken = ref(null);
const expiredInvoiceToken = ref(null);

const computedAllowSearch = computed(() => {
  const anyEspecificFilter = selectedInvoices.value.length > 0 || selectedContracts.value.length > 0 || selectedPersons.value.length > 0;
  if (selectedBilling.value || selectedExploitation.value || anyEspecificFilter || filter_issue_date_start.value || filter_issue_date_end.value || selectedInvoiceStatuses.value.length > 0) return false;
  return true;
})

const search = async (download = false) => {
  is_fetching.value = true;
  try {
    const searchData = {
      exploitation: selectedExploitation.value ? selectedExploitation.value.value : null,
      billing: selectedBilling.value ? selectedBilling.value.value : null,
      origin: selectedOrigins.value ? selectedOrigins.value.value : null,

      contracts: selectedContracts.value.map(contract => contract.id),
      invoices: selectedInvoices.value.map(invoice => invoice.id),
      persons: selectedPersons.value.map(person => person.id),
      invoice_statuses: selectedInvoiceStatuses.value.map(status => status.value),

      issue_date_start: filter_issue_date_start.value || null,
      issue_date_end: filter_issue_date_end.value || null,

      download: download,
    }

    const result = await $InvoiceApiService.getElectronicInvoiceData(searchData)
    if (download) {
      taskId.value = result.task_id;
      loadingTask.value = true;
    } else {
      invoices.value = result.invoices ?? [];
      invoicePagination.value.page = 1;
      updateInvoicePagination();
      hasSearched.value = true;
    }
  } catch (error) {
    console.error(error);
  }
  finally {
    is_fetching.value = false;
  }
}

const getExploitations = async () => {
  loadingExploitations.value = true;
  try {
    const result = await $ExploitationApiService.getData();
    result.results;
    result.results.forEach(exploitation => {
      exploitations.value.push({
        value: exploitation.id,
        label: exploitation.name,
        company: exploitation.company.id
      })
    })
    exploitations.value.unshift({
      value: null,
      label: `--`,
    })
    if (exploitations.value.length === 1) {
      selectedExploitation.value = { value: exploitations.value[0].value, label: exploitations.value[0].label, company: exploitations.value[0].company }
    }
  } catch (err) {
    console.error(err);
  } finally {
    loadingExploitations.value = false;
  }
}
const fetchConfigData = async (service, entity, targetArray, loading) => {
  try {
    loading.value = true;
    const data = await $ConfiglistApiService.getAll(service + '/' + entity);
    targetArray.value = [];

    if (data.results) {
      data.results.forEach(data => {
        targetArray.value.push({
          label: data.name || data.token,
          value: data.id,
          token: data.token
        })
      });
    }
  } catch (error) {
    console.error(`Error fetching ${entity}:`, error);
  } finally {
    loading.value = false;
  }
}

const getData = async () => {
  getExploitations();
  confirmedInvoiceToken.value = await $ConfigProjectApiService.get('invoice_status_confirmed_token');
  expiredInvoiceToken.value = await $ConfigProjectApiService.get('invoice_status_expired_token');
  fetchConfigData('pricing', 'product-origin', origins, loadingOrigins);
  fetchConfigData('billing', 'billing', billings, loadingBillings);
  await fetchConfigData('billing', 'invoice-status', invoiceStatuses, loadingInvoiceStatuses);
}

const onInvoiceSelected = (invoice) => {
  selectedContracts.value = [];
  selectedPersons.value = [];
  if (selectedInvoices.value.find(x => x.id == invoice.id)) {
    selectedInvoices.value = selectedInvoices.value.filter(x => x.id != invoice.id);
  } else {
    selectedInvoices.value.push({
      id: invoice.id,
      serie_final: invoice.serie_final,
      send_at: invoice.send_at || null,
    });
  }
}

const onPersonSaved = (person) => {
  selectedContracts.value = [];
  selectedInvoices.value = [];
  if (selectedPersons.value.find(x => x.id == person.id)) {
    selectedPersons.value = selectedPersons.value.filter(x => x.id != person.id);
  } else {
    selectedPersons.value.push({
      id: person.id,
      name: person.full_name,
      token: person.token,
    });
  }
  closeSubRegion();
}


const onContractSelected = (contract) => {
  selectedInvoices.value = [];
  selectedPersons.value = [];
  if (selectedContracts.value.find(x => x.id == contract.id)) {
    selectedContracts.value = selectedContracts.value.filter(x => x.id != contract.id);
  } else {
    selectedContracts.value.push({
      id: contract.id,
      token: contract.token,
      send_at: contract.send_at || null,
    });
  }
}

const openRegion = (component, id) => {
  closeSubRegion();
  showRegionDetailComponent.value = component;
  regionDetailId.value = id;
  if (component == 'AddContracts' || component == 'AddInvoices') {
    handleSubRegionEvent(true);
  }
}

const handleSubRegionEvent = (event) => {
  isSubRegionOpen.value = event;
}

const closeSubRegion = () => {
  showRegionDetailComponent.value = null;
  regionDetailId.value = null;
  isSubRegionOpen.value = false;
}


const triggerFooterHighlight = () => {
  highlightFooter.value = false;
  nextTick(() => {
    highlightFooter.value = true;
    setTimeout(() => (highlightFooter.value = false), 1800);
  });
};

const resetFilters = (reset_all = true, invoice_selected = false) => {
  if (reset_all) {
    selectedExploitation.value = null;
  }
  selectedBilling.value = null;
  selectedOrigins.value = null;
  filter_issue_date_start.value = '';
  filter_issue_date_end.value = '';
  selectedContracts.value = [];
  selectedPersons.value = [];
  if (!invoice_selected) selectedInvoices.value = [];
  selectedInvoiceStatuses.value = [];
  invoices.value = [];
  hasSearched.value = false;
  invoicePagination.value.page = 1;
  updateInvoicePagination();
}

onMounted(async () => {
  objectPermissions.value = await checkPermission($InvoiceApiService);
  if (!objectPermissions.value.can_change) {
    toast.error(t('common.no_permissions'));
    return navigateTo('/');
  }

  await getData();
  invoiceStatuses.value.forEach(status => {
    if (status.token == confirmedInvoiceToken.value || status.token == expiredInvoiceToken.value) {
      selectedInvoiceStatuses.value.push(status);
    }
  });
  loading.value = false;
});

const getFiles = async () => {
  try {
    const res = await $apiManager.checkTask(taskId.value)
    if (res && res.result?.file_url) {
      await openAuthenticatedFileUrl(res.result.file_url, false);
    }
  } catch (error) {
    console.error(error);
  } finally {
    loadingTask.value = false;
    taskId.value = null;
  }
}

watch(selectedExploitation, () => {
  if (!selectedExploitation.value) {
    selectedOrigins.value = null;
  }
});

watch([selectedInvoices], () => {
  if (selectedInvoices.value.length > 0) {
    resetFilters(true, true)
  }
}, { deep: true });

watch(
  invoices,
  () => {
    updateInvoicePagination();
    triggerFooterHighlight();
  },
  { deep: true }
);
</script>

<template>
  <div v-if="objectPermissions?.can_change" class="text-base">
    <div v-if="loading">
      <AppLoading :text="$t('common.loading')" />
    </div>
    <div v-else class="mx-auto px-4 mb-20">
      <div>
        <div class="grid grid-cols-2 gap-6">
          <!-- General Filters -->
          <div class="space-y-3">
            <h3 class="text-xs font-semibold text-slate-500 uppercase tracking-wide pb-2 border-b border-gray-100">
              {{ $t('common.general_filters') }}
            </h3>
            <div class="space-y-2.5">
              <div>
                <label class="block text-xs font-medium text-slate-600 mb-1">
                  {{ t('common.exploitation') }}
                </label>
                <v-select class="block w-full custom-select" v-model="selectedExploitation" :options="exploitations"
                  :loading="loadingExploitations" :disabled="selectedBilling != null" />
              </div>
              <div>
                <label class="block text-xs font-medium text-slate-600 mb-1">
                  {{ t('common.origin') }}
                </label>
                <v-select class="block w-full custom-select" v-model="selectedOrigins" :options="origins"
                  :loading="loadingOrigins"
                  :disabled="!!selectedBilling || (!selectedExploitation && selectedContracts.length == 0 && selectedInvoices.length == 0 && selectedPersons.length == 0)" />
              </div>
              <div>
                <label class="block text-xs font-medium text-slate-600 mb-1">
                  {{ t('billing') }}
                </label>
                <v-select class="block w-full custom-select" v-model="selectedBilling" :options="billings"
                  :loading="loadingBillings" :disabled="!!selectedExploitation || !!selectedOrigins || !!selectedPersons" />
              </div>

              <div>
                <label class="block text-xs font-medium text-slate-600 mb-1">
                  {{ t('common.select') }} {{ t('common.statuses').toLowerCase() }} ({{ t('invoice') }})
                </label>
                <v-select multiple class="block w-full custom-select" v-model="selectedInvoiceStatuses"
                  :options="invoiceStatuses" :loading="loadingInvoiceStatuses" />
              </div>

              <div>
                <label class="block text-xs font-medium text-slate-600 mb-1">
                  {{ $t('billing_block.issue_date') }}
                </label>
                <div class="grid grid-cols-2 gap-2">
                  <AtomsInputDate
                    v-model="filter_issue_date_start"
                    input-id="electronic-invoice-issue-date-start"
                    :label="t('common.from')"
                    class="w-full [&_.input-group]:mb-0"
                  />
                  <AtomsInputDate
                    v-model="filter_issue_date_end"
                    input-id="electronic-invoice-issue-date-end"
                    :label="t('common.to')"
                    :start-date="filter_issue_date_start || null"
                    class="w-full [&_.input-group]:mb-0"
                  />
                </div>
              </div>

            </div>
          </div>

          <!-- Specific Filters -->
          <div class="space-y-3">
            <h3 class="text-xs font-semibold text-slate-500 uppercase tracking-wide pb-2 border-b border-gray-100">
              {{ $t('common.specific_filters') }}
            </h3>
            <div class="space-y-2 pt-5">
              <!-- falta personas -->

              <div class="grid grid-cols-2 gap-2">
                <ButtonOutline @click="openRegion('AddContracts', null)" :disabled="is_fetching">
                  {{ $t('common.select') }} {{ $t('contracts').toLowerCase() }}
                </ButtonOutline>

                <ButtonOutline @click="openRegion('AddInvoices', null)" :disabled="is_fetching">
                  {{ $t('common.select') }} {{ $t('invoices').toLowerCase() }}
                </ButtonOutline>

                <ButtonOutline @click="openRegion('PersonSearch', null)" :disabled="is_fetching">
                  {{ $t('common.select') }} {{ $t('common.persons').toLowerCase() }}
                </ButtonOutline>
              </div>

              <div>
                <div
                  v-if="selectedContracts.length == 0 && selectedInvoices.length == 0 && selectedPersons.length == 0">
                  <p class="text-xs text-slate-400">
                    {{ $t('contract_block.no_selected_contracts') }}
                  </p>
                </div>
                <div v-else>
                  <p v-if="selectedInvoices.length > 0" class="text-xs text-slate-500">
                    {{ t('billing_block.selected_invoices') }} </p>
                  <p v-if="selectedContracts.length > 0" class="text-xs text-slate-500">
                    {{ $t('contract_block.selected_contracts') }}
                  </p>
                  <p v-if="selectedPersons.length > 0" class="text-xs text-slate-500">
                    {{ $t('contract_block.selected_persons') }}
                  </p>
                  <div class="flex flex-wrap gap-2 mt-1">
                    <div v-for="invoice in selectedInvoices" :key="invoice.id"
                      class="flex items-center gap-2 p-1 border border-sky-500 rounded w-fit text-nowrap">
                      <span class="text-xs text-slate-500 ml-2">{{ invoice.serie_final }}</span>
                      <button type="button" @click="openRegion('InvoiceRegion', invoice.id)"
                        class="w-6 h-6 bg-white text-sky-500 rounded-full flex items-center justify-center enabled:hover:bg-sky-100 transition-all ml-1 disabled:opacity-30">
                        <Icon name="fa6-solid:eye" class="w-3 h-3" />
                      </button>
                      <button type="button" @click="onInvoiceSelected(invoice)"
                        class="w-6 h-6 text-red-500 bg-white rounded-full flex items-center justify-center enabled:hover:bg-red-200 transition-colors disabled:opacity-30">
                        <Icon name="fa6-solid:xmark" class="w-3 h-3" />
                      </button>
                    </div>
                    <div v-for="contract in selectedContracts" :key="contract.id"
                      class="flex items-center gap-2 p-1 border border-sky-500 rounded w-fit text-nowrap">
                      <span class="text-xs text-slate-500 ml-2">{{ contract.token }}</span>
                      <button type="button" @click="openRegion('ContractRegion', contract.id)"
                        class="w-6 h-6 bg-white text-sky-500 rounded-full flex items-center justify-center enabled:hover:bg-sky-100 transition-all ml-1 disabled:opacity-30">
                        <Icon name="fa6-solid:eye" class="w-3 h-3" />
                      </button>
                      <button type="button" @click="onContractSelected(contract)"
                        class="w-6 h-6 text-red-500 bg-white rounded-full flex items-center justify-center enabled:hover:bg-red-200 transition-colors disabled:opacity-30">
                        <Icon name="fa6-solid:xmark" class="w-3 h-3" />
                      </button>
                    </div>
                    <div v-for="person in selectedPersons" :key="person.id"
                      class="flex items-center gap-2 p-1 border border-sky-500 rounded w-fit text-nowrap">
                      <span class="text-xs text-slate-500 ml-2">{{ person.name }} ({{ person.token }})</span>
                      <button type="button" @click="openRegion('PersonRegion', person.id)"
                        class="w-6 h-6 bg-white text-sky-500 rounded-full flex items-center justify-center enabled:hover:bg-sky-100 transition-all ml-1 disabled:opacity-30">
                        <Icon name="fa6-solid:eye" class="w-3 h-3" />
                      </button>
                      <button type="button" @click="onPersonSaved(person)"
                        class="w-6 h-6 text-red-500 bg-white rounded-full flex items-center justify-center enabled:hover:bg-red-200 transition-colors disabled:opacity-30">
                        <Icon name="fa6-solid:xmark" class="w-3 h-3" />
                      </button>
                    </div>
                  </div>
                </div>
              </div>

            </div>
          </div>
        </div>

      </div>

      <hr class="my-4" />

      <div v-if="hasSearched || is_fetching" class="mb-4">
        <div class="flex flex-wrap items-center justify-between gap-2 mb-2">
          <h3 class="text-xs font-semibold text-slate-500 uppercase tracking-wide">
            {{ $t('invoices') }}
          </h3>
          <span v-if="!is_fetching" class="text-xs text-slate-500">
            {{ $t('common.total') }}: {{ invoices.length }}
          </span>
        </div>

        <div v-if="is_fetching" class="flex justify-center py-8">
          <AppLoading :text="$t('common.loading')" />
        </div>

        <template v-else>
          <div v-if="invoices.length === 0"
            class="flex items-start gap-2 rounded-lg border border-sky-200 bg-sky-50 px-3 py-2 text-sm text-sky-800">
            <Icon name="fa6-solid:circle-info" class="mt-0.5 text-sky-600 shrink-0" />
            <p>{{ $t('billing_block.no_invoices_selected') }}</p>
          </div>
          <div v-else class="border border-slate-200 rounded bg-white flex flex-col"
            style="max-height: min(50vh, calc(100vh - 450px));">
            <div class="overflow-y-auto overflow-x-auto flex-1 min-h-0">
              <table class="w-full text-sm border-collapse min-w-[1200px]">
                <thead class="sticky top-0 bg-slate-100 border-b border-slate-200 text-slate-600 font-medium z-10">
                  <tr>
                    <th class="text-left py-1.5 px-2 whitespace-nowrap">{{ $t('common.identification') }}</th>
                    <th class="text-left py-1.5 px-2 whitespace-nowrap">{{ $t('common.date') }}</th>
                    <th class="text-left py-1.5 px-2 min-w-[160px]">{{ $t('common.title') }}</th>
                    <th class="text-right py-1.5 px-2 whitespace-nowrap">{{ $t('billing_block.total_invoice') }}</th>
                    <th class="text-right py-1.5 px-2 whitespace-nowrap">{{ $t('billing_block.total_to_pay') }}</th>
                    <th class="text-left py-1.5 px-2 min-w-[140px]">{{ $t('contract_block.holder') }}</th>
                    <th class="text-left py-1.5 px-2 whitespace-nowrap">{{ $t('common.exploitation') }}</th>
                    <th class="text-left py-1.5 px-2 whitespace-nowrap">{{ $t('contract') }}</th>
                    <th class="text-left py-1.5 px-2 whitespace-nowrap">{{ $t('common.origin') }}</th>
                    <th class="text-left py-1.5 px-2 whitespace-nowrap">{{ $t('common.status') }}</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="invoice in paginatedInvoices" :key="invoice.id"
                    class="border-b border-slate-100 hover:bg-slate-50">
                    <td class="py-1 px-2 align-middle whitespace-nowrap">
                      <button type="button" @click="openRegion('InvoiceRegion', invoice.id)"
                        class="text-sky-500 hover:text-sky-700 underline text-left" :title="String(invoice.id)">
                        {{ invoice.serie_final }}
                      </button>
                    </td>
                    <td class="py-1 px-2 align-middle whitespace-nowrap">
                      {{ invoice.issue_date ? formatDate(invoice.issue_date) : '–' }}
                    </td>
                    <td class="py-1 px-2 align-middle max-w-[200px] truncate" :title="invoice.title_final">
                      {{ invoice.title_final || '–' }}
                    </td>
                    <td class="py-1 px-2 align-middle text-right whitespace-nowrap">
                      {{ formatMoneyWithCurrency(invoice.total_final) }}
                    </td>
                    <td class="py-1 px-2 align-middle text-right whitespace-nowrap">
                      {{ formatMoneyWithCurrency(invoice.left_to_pay) }}
                    </td>
                    <td class="py-1 px-2 align-middle max-w-[180px] truncate"
                      :title="`${invoice.customer_token_final || ''} ${invoice.customer_final || ''}`.trim()">
                      <span v-if="invoice.customer_token_final" class="font-medium">{{ invoice.customer_token_final
                      }}</span>
                      <span v-if="invoice.customer_final" class="ml-1">{{ invoice.customer_final }}</span>
                      <span v-if="!invoice.customer_token_final && !invoice.customer_final">–</span>
                    </td>
                    <td class="py-1 px-2 align-middle whitespace-nowrap">
                      {{ invoice.exploitation_token || '–' }}
                    </td>
                    <td class="py-1 px-2 align-middle whitespace-nowrap">
                      <button v-if="invoice.contract_id" type="button"
                        @click="openRegion('ContractRegion', invoice.contract_id)"
                        class="text-sky-500 hover:text-sky-700 underline text-left"
                        :title="String(invoice.contract_id)">
                        {{ invoice.contract_token || invoice.contract_id }}
                      </button>
                      <span v-else>{{ invoice.contract_token || '–' }}</span>
                    </td>
                    <td class="py-1 px-2 align-middle whitespace-nowrap">
                      {{ invoice.origin_name || '–' }}
                    </td>
                    <td class="py-1 px-2 align-middle whitespace-nowrap">
                      <AtomsColorBadge :value="invoice.status_name" :color="invoice.status_color" />
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
            <Pagination v-if="invoices.length > 0" :pagination="invoicePagination"
              @update:page="handleInvoicePageChange" />
          </div>
        </template>
      </div>

      <div :class="{ 'jquery-highlight': highlightFooter }"
        class="fixed right-0 bottom-0 z-[9999] border-t border-gray-200 py-3 px-6 shadow-lg bg-[#FAE2DA] z-40 flex flex-row justify-between mt-4"
        style="width: calc(100% - 250px)">
        <div class="grid auto-cols-max grid-flow-col items-center gap-x-10">

          <!-- PAGAMENTS + EXCLOSOS + BOTÓ -->
          <div class="pr-6 mr-4 border-r border-gray-300">
            <div class="grid grid-cols-[auto,30px] items-center gap-x-4">

              <div class="flex flex-col">
                <div class="flex items-center gap-2">
                  <span class="text-lg font-bold text-slate-900">{{ invoices.length }}</span>
                  <span class="text-sm font-semibold text-slate-700">
                    {{ $t('billing_block.selected_invoices') }}
                  </span>
                </div>
              </div>
            </div>
          </div>

        </div>
        <div class="flex gap-3">
          <abbr>
            <button @click="resetFilters()" class="button-default">
              <Icon name="fa6-solid:arrow-rotate-left" />&nbsp; {{ $t('common.clear') }}
            </button>
          </abbr>
          <abbr :title="computedAllowSearch ? $t('informative_block.info_filters_missing') : ''">
            <button @click="search(false)" :disabled="computedAllowSearch || is_fetching" class="button-default">
              <Icon :name="is_fetching ? 'fa6-solid:spinner' : 'fa6-solid:magnifying-glass'"
                :class="{ 'animate-spin': is_fetching }" />
              &nbsp; {{ $t('dashboard.search') }}
            </button>
          </abbr>
          <abbr>
            <button v-if="!taskId" @click="search(true)" :disabled="invoices.length === 0" class="button-secondary">
              <Icon name="fa6-solid:download" />&nbsp; {{ $t('common.download') }}
            </button>
            <AtomsProcessColorBadge v-else class="h-full items-center justify-center py-2"
              :value="$t('common.processing')" color="blue" :taskId="taskId" @refresh="getFiles()">
            </AtomsProcessColorBadge>
          </abbr>
        </div>
      </div>
    </div>

    <div role="region" id="right_page"
      class="fixed h-full border-l border-gray-100 top-0 right-0 transition-all duration-500 ease py-2 text-base bg-white w-1/2 z-50"
      :class="{
        'translate-x-0': showRegionDetailComponent,
        'translate-x-[2000px]': !showRegionDetailComponent,
        'w-[95%]': isSubRegionOpen,
        'w-[50%]': !isSubRegionOpen
      }">
      <div id="region_nav" class="mb-3 px-3">
        <button @click="closeSubRegion()" class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300">
          <Icon name="fa6-solid:angles-right" class="text-slate-500" />
        </button>
      </div>
      <div class="px-10">
        <AddInvoices v-if="showRegionDetailComponent == 'AddInvoices'" :multiple="true"
          :selected_items="selectedInvoices" @item-clicked="onInvoiceSelected" />
        <PersonSearch v-if="showRegionDetailComponent == 'PersonSearch'" :allowCreate="false"
          @saved="onPersonSaved" />
        <PersonRegion v-if="showRegionDetailComponent == 'PersonRegion'" :id="regionDetailId"
          :isSubRegionOpen="isSubRegionOpen" @show-subregion="handleSubRegionEvent" @close-subregion="closeSubRegion" />
        <AddContracts v-if="showRegionDetailComponent == 'AddContracts'" :multiple="true"
          :selected_items="selectedContracts" @item-clicked="onContractSelected" />
        <InvoiceRegion v-if="showRegionDetailComponent === 'InvoiceRegion'" :id="regionDetailId"
          :isSubRegionOpen="isSubRegionOpen" @show-subregion="handleSubRegionEvent" @close-subregion="closeSubRegion" />
        <ContractRegion v-if="showRegionDetailComponent === 'ContractRegion'" :id="regionDetailId"
          :isSubRegionOpen="isSubRegionOpen" @show-subregion="handleSubRegionEvent" @close-subregion="closeSubRegion" />
      </div>
    </div>
  </div>
</template>

<style scoped lang="postcss">
.custom-select .vs__selected-options {
  max-height: 50px;
  overflow-y: auto;
}

:deep(.custom-select.vs--open) {
  position: relative;
  z-index: 90 !important;
}

:deep(.custom-select .vs__dropdown-menu) {
  position: absolute;
  z-index: 90 !important;
  max-height: 30vh;
  overflow-y: auto;
}

:deep(.fixed.bottom-0) {
  z-index: 40;
}

#right_page {
  z-index: 100 !important;
}
</style>
