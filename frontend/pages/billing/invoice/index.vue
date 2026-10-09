<script setup>
import { useRouter } from 'vue-router';
import debounce from 'lodash.debounce';
import { useI18n } from 'vue-i18n';
import { formatDate } from '~/utils/date';
import { formatMoneyWithCurrency } from '~/utils/money';
import InvoiceRegion from '~/components/organisms/InvoiceRegion.vue';
import Pagination from '~/components/molecules/Pagination.vue';
import H1 from '~/components/atoms/H1.vue';
import TableHeader from '~/components/atoms/TableHeader.vue';
import FilterSelect from '~/components/atoms/FilterSelect.vue';
import AddInvoiceBudget from '~/components/molecules/AddInvoiceBudget.vue';
import { useToast } from 'vue-toastification';
import ManageInvoicesPaidRegion from '~/components/organisms/ManageInvoicesPaidRegion.vue';
import DataTable from '~/components/organisms/DataTable.vue';

const { t } = useI18n();
const toast = useToast();
const showRegion = ref(false);
const detail = ref(null);
const selectedItemId = ref(null);
const isSubRegionOpen = ref(false);

const toggleRegion = (force, isReload = false) => {
  showRegion.value = force !== undefined ? force : !showRegion.value;
  if (showRegion.value == false) {
    isSubRegionOpen.value = false;
    regionComponent.value = null
    detail.value = null;
    selectedItemId.value = null;
    if (!isReload) {
      nextTick(() => {
        if (!showRegion.value && route.query.id) {
          const query = { ...route.query };
          delete query.id;
          router.replace({ path: route.path, query });
        }
      });
    }
  }
}

const openIndexDropdown = ref(false)

const route = useRoute();
const router = useRouter();
const { $InvoiceApiService, $ConfiglistApiService } = useNuxtApp();
const pending = ref(true);
const error = ref(null);
const items = ref([]);
const activeSearchInput = ref('searchInput');
const searchInput = ref('');
const searchInputTotalFinal = ref('');
const searchInputLineItem = ref('');
const sortBy = ref(null);
const sortDesc = ref(false);
const regionComponent = ref(null)
const permissions = ref(null);
const selectedFilters = ref([]);
const selectedOrigins = ref([]);
const selectedBilling = ref([]);
const selectedIssueDate = ref([]);
const selectedDueDate = ref([]);
const selectedSerie = ref([]);
const selectedPaymentTypes = ref([]);

const filter_status = ref([])
const filter_origins = ref([])
const filter_serie = ref([])
const filter_payment_types = ref([])
const issue_date = ref({})
const due_date = ref({})
const statuses = ref([])
const origin = ref(null)
const billing = ref(null)
const serie = ref([]);
const payment_types = ref([]);

const isFilterOpen = ref(false);
const isFilterShown = ref([]);
const filtersExtra = ref([]);

const selectedCustomInvoice = ref(null);

const pagination = ref({
  page: 1,
  perPage: 50,
  total: 0,
  totalPages: 0,
  previous: null,
  next: null,
  isFiltered: false
});

const getPermissions = async () => {
  error.value = null;
  try {
    const data = await $InvoiceApiService.getPermissions();
    permissions.value = data;
  } catch (err) {
    error.value = err;
  }
}

const getData = async (searchQuery = '', filters = [], page = 1, sort = null, desc = false, contract = null, is_invoice = true, origin = null, billing = null, issue_date = null, due_date = null, serie = [], total_query = '', payment_types = [], line_item = '') => {
  if (!permissions.value?.can_view) {
    toast.error(t('common.no_permissions'));
    return navigateTo('/');
  }
  pending.value = true;
  error.value = null;
  try {
    const data = await $InvoiceApiService.getAll(searchQuery, filters, page, sort, desc, contract, is_invoice, origin, billing, issue_date, due_date, serie, total_query, payment_types, line_item);

    items.value = data.results;
    Object.assign(pagination.value, {
      total: data.count,
      totalPages: Math.ceil(data.count / pagination.value.perPage),
      previous: data.previous,
      next: data.next,
      isFiltered: String(searchQuery).trim() !== ''
    });
    // console.log("getdata")
    // console.log(items.value)

    nextTick(() => {
      const activeInput = document.getElementById(activeSearchInput.value);
      if (activeInput) {
        activeInput.focus();
      }
    });
  } catch (err) {
    error.value = err;
  } finally {
    pending.value = false;
  }
}

const getFilterStatus = async () => {
  error.value = null;
  try {
    const data = await $ConfiglistApiService.getAll('billing/invoice-status')
    filter_status.value = data.results;
    // console.log("filters")
    // console.log(filter_status.value)
  } catch (err) {
    console.error(err)
  }
}

const getFilterOrigin = async () => {
  error.value = null;
  try {
    const data = await $ConfiglistApiService.getAll('pricing/product-origin')
    filter_origins.value = data.results;
    filter_origins.value.unshift(
      {
        name: t("common.origin"),
        id: null,
      }
    );
  } catch (err) {
    console.error(err)
  }
}

const getFilterSerie = async () => {
  error.value = null;
  try {
    const data = await $ConfiglistApiService.getAll('billing/invoice-serie')
    filter_serie.value = data.results;
  } catch (err) {
    console.error(err)
  }
}

const getFilterPaymentType = async () => {
  error.value = null;
  try {
    const data = await $ConfiglistApiService.getAll('billing/payment-type')
    filter_payment_types.value = data.results;
  } catch (err) {
    console.error(err)
  }
}

const debouncedGetData = debounce((query, filters, sort, desc, contract, is_invoice, origin, billing, issue_date, due_date, serie, total_query, payment_types, line_item) => {
  getData(query, filters, pagination.value.page, sort, desc, contract, is_invoice, origin, billing, issue_date, due_date, serie, total_query, payment_types, line_item);
}, 300);

const handleSearch = () => {
  pagination.value.page = 1;
  // console.log(billing.value)
  debouncedGetData(searchInput.value, statuses.value, sortBy.value, sortDesc.value, null, true, origin.value, billing.value, issue_date.value, due_date.value, serie.value, searchInputTotalFinal.value, payment_types.value, searchInputLineItem.value);
}

const handleTotalFinalInput = (event) => {
  const value = event.target.value;
  // Only allow numbers, dots, and commas
  const filtered = value.replace(/[^0-9.,]/g, '');
  searchInputTotalFinal.value = filtered;
  handleSearch();
}

const refresh = () => {
  debouncedGetData(searchInput.value, statuses.value, sortBy.value, sortDesc.value, null, true, origin.value, billing.value, issue_date.value, due_date.value, serie.value, searchInputTotalFinal.value, payment_types.value, searchInputLineItem.value);
}

const handleFilterChange = () => {
  pagination.value.page = 1;
  handleSearch();
}

const handlePageChange = (newPage) => {
  pagination.value.page = newPage;
  getData(searchInput.value, statuses.value, newPage, sortBy.value, sortDesc.value, null, true, origin.value, billing.value, issue_date.value, due_date.value, serie.value, searchInputTotalFinal.value, payment_types.value, searchInputLineItem.value);
}

// XLSX export — columns mirror the visible table columns (in display order).
const exportColumns = computed(() => [
  { header: t('common.identification'), value: (row) => row.serie_final, key: 'serie' },
  { header: t('common.date'), value: (row) => row.issue_date ? formatDate(row.issue_date) : '', key: 'issue_date' },
  { header: t('common.title'), value: (row) => row.title_final, key: 'number' },
  { header: t('contract_block.holder'), value: (row) => [row.customer_final, row.customer_token].filter(Boolean).join(' '), key: 'customer' },
  { header: t('contract'), value: (row) => row.contract_token || row.contract_request_token || row.contract_termination_contract_token || '', key: 'contract' },
  { header: t('billing_block.total_invoice'), value: (row) => Number(row.total_final ?? 0), key: 'total_final' },
  { header: t('billing_block.total_to_pay'), value: (row) => Number(row.left_to_pay ?? 0), key: 'left_to_pay' },
  { header: t('payment_types'), value: (row) => row.payment_type_final, key: 'payment_type' },
  { header: t('common.origin'), value: (row) => row.origin_name, key: 'origin' },
  { header: t('common.status'), value: (row) => row.status_name, key: 'status' },
  { header: t('common.due_date'), value: (row) => row.due_date ? formatDate(row.due_date) : '', key: 'due_date' },
]);

// Hybrid export: single page → client-side; multiple pages → server (all-pages, filter-aware).
const exportInvoices = (columns) => $InvoiceApiService.exportData(
  searchInput.value, statuses.value, sortBy.value, sortDesc.value, null, true,
  origin.value, billing.value, issue_date.value, due_date.value, serie.value,
  searchInputTotalFinal.value, payment_types.value, searchInputLineItem.value,
  null, null, columns,
);

const handleSort = (key) => {
  if (sortBy.value === key) {
    sortDesc.value = !sortDesc.value;
  } else {
    sortBy.value = key;
    sortDesc.value = false;
  }
  getData(searchInput.value, statuses.value, pagination.value.page, sortBy.value, sortDesc.value, null, true, origin.value, billing.value, issue_date.value, due_date.value, serie.value, searchInputTotalFinal.value, payment_types.value, searchInputLineItem.value);
}

const resetFilters = () => {
  searchInput.value = '';
  searchInputLineItem.value = '';
  pagination.value.page = 1;
  selectedFilters.value = []
  statuses.value = []
  selectedOrigins.value = []
  origin.value = null
  isFilterShown.value = [];
  issue_date.value = {};
  due_date.value = {};
  isFilterOpen.value = false
  serie.value = [];
  payment_types.value = [];
  selectedPaymentTypes.value = [];
  // filtersExtra.value = [];
  getData();
};

const handleStatusChange = (event) => {
  selectedFilters.value = event;
  statuses.value = []
  selectedFilters.value.forEach(element => {
    statuses.value.push(element.id);
  })
  pagination.value.page = 1;
  handleSearch();
}

const handleBillingChange = (event) => {
  selectedBilling.value = event;
  billing.value = null
  billing.value = selectedBilling.value[0]
  pagination.value.page = 1;
  handleSearch();
}

const handleSerieChange = (event) => {
  selectedSerie.value = event;
  serie.value = [];
  selectedSerie.value.forEach(element => {
    serie.value.push(element.id);
  })
  pagination.value.page = 1;
  handleSearch();
}

const handleIssueDateChange = (event) => {
  //HANDLE ISSUE DATE
  issue_date.value = event;
  pagination.value.page = 1;
  handleSearch();
}

const handleDueDateChange = (event) => {
  //HANDLE ISSUE DATE
  due_date.value = event;
  pagination.value.page = 1;
  handleSearch();
}

const handleOriginChange = (event) => {
  selectedOrigins.value = event;
  origin.value = null
  origin.value = selectedOrigins.value[0].id
  pagination.value.page = 1;
  handleSearch();
}

const handlePaymentTypeChange = (event) => {
  selectedPaymentTypes.value = event;
  payment_types.value = []
  selectedPaymentTypes.value.forEach(element => {
    payment_types.value.push(element.token);
  })
  pagination.value.page = 1;
  handleSearch();
}

const handleFiltersChange = (event) => {
  let newFilters = event
    .filter(el => !isFilterShown.value.includes(el.id));

  checkInAdvacedFilters(newFilters)
  isFilterShown.value = [];
  isFilterShown.value = [...isFilterShown.value, ...newFilters];
}

const checkInAdvacedFilters = (newFilters) => {
  if (isFilterShown.value.some(filter => filter.id === 'issue_date') && !newFilters.some(filter => filter.id === 'issue_date')) {
    issue_date.value = {};
    selectedIssueDate.value = [];
    handleSearch();
  } else if (isFilterShown.value.some(filter => filter.id === 'due_date') && !newFilters.some(filter => filter.id === 'due_date')) {
    due_date.value = {};
    selectedDueDate.value = [];
    handleSearch();
  } else if (isFilterShown.value.some(filter => filter.id === 'origin') && !newFilters.some(filter => filter.id === 'origin')) {
    origin.value = null;
    selectedOrigins.value = [];
    handleSearch();
  } else if (isFilterShown.value.some(filter => filter.id === 'serie') && !newFilters.some(filter => filter.id === 'serie')) {
    serie.value = [];
    selectedSerie.value = [];
    handleSearch();
  } else if (isFilterShown.value.some(filter => filter.id === 'payment_type') && !newFilters.some(filter => filter.id === 'payment_type')) {
    payment_types.value = [];
    selectedPaymentTypes.value = [];
    handleSearch();
  }
}

const toggleIndexDropdown = () => {
  openIndexDropdown.value = !openIndexDropdown.value
}

const showDetail = (id, component) => {
  if (id && selectedItemId.value && String(selectedItemId.value) === String(id) && showRegion.value) {
    toggleRegion(false, true);
    nextTick(() => {
      regionComponent.value = component;
      detail.value = id;
      selectedItemId.value = id;
      toggleRegion(true);
    });
    return;
  }
  openIndexDropdown.value = false
  toggleRegion(false)
  regionComponent.value = component
  detail.value = id;
  selectedItemId.value = id;
  toggleRegion(true);
  if (id && route.query.id !== String(id)) {
    router.replace({ path: route.path, query: { ...route.query, id: id } });
  }
}

onMounted(async () => {
  await getPermissions();
  if (permissions.value?.can_view) {
    getFilterStatus()
    getFilterOrigin()
    getFilterSerie()
    getFilterPaymentType()
    filtersExtra.value.push(
      { name: t("common.date"), id: "issue_date" },
      { name: t("common.due_date"), id: "due_date" },
      { name: t("common.origin"), id: "origin" },
      { name: t("billing_block.billing_id"), id: "billing_id" },
      { name: t("billing_block.serie"), id: "serie" },
      { name: t("payment_types"), id: "payment_type" },
    );

    if (route.query?.billing) {
      billing.value = route.query.billing
      isFilterOpen.value = true
      isFilterShown.value = [{ name: t("billing_block.billing_id"), id: "billing_id" }];
    }

    await getData('', [], 1, null, false, null, true, null, billing.value);
    checkRouteQuery()
    selectedCustomInvoice.value = {
      id: null,
      title: '',
      label: t('billing_block.new_invoice'),
      period_days: 0,
      entity: 'invoice',
    }
  } else {
    toast.error(t('common.no_permissions'));
    pending.value = false;
    return navigateTo('/');
  }
});

watch(searchInput, (newValue) => {
  if (newValue) {
    searchInputTotalFinal.value = '';
    activeSearchInput.value = 'searchInput';
  }
});

watch(searchInputTotalFinal, (newValue) => {
  if (newValue) {
    searchInput.value = '';
    activeSearchInput.value = 'searchInputTotalFinal';
  }
});

watch(searchInputLineItem, (newValue) => {
  if (newValue) {
    activeSearchInput.value = 'searchInputLineItem';
  }
});

const checkRouteQuery = () => {
  if (route.query?.action == 'showDetail') {
    showDetail(route.query.id, 'InvoiceRegion')
  } else if (route?.query?.id &&
    !(selectedItemId.value && String(selectedItemId.value) === String(route.query.id) && showRegion.value)) {
    showDetail(route.query.id, 'InvoiceRegion');
  }
}

// Watch for changes in searchInput, searchInputLineItem and selectedFilters and reset pagination to 1
watch([searchInput, searchInputLineItem, selectedFilters], () => {
  pagination.value.page = 1;
  handleSearch();
});

const handleSubRegionEvent = (event) => {
  isSubRegionOpen.value = event;
}

//checkpoint
watch(() => route.query, () => {
  checkRouteQuery()
}, { immediate: true })
</script>

<template>
  <div id="wrapper" class="text-base">
    <div class="flex justify-between items-center mb-2">
      <H1 class="mb-2">{{ $t('invoices') }}</H1>
      <!-- <div class="flex gap-2">
        <button @click="showDetail(null, 'AddInvoiceBudget')" class="button-default">
          {{ $t('billing_block.new_invoice') }}</button>
        <button @click="showDetail(null, 'ManageInvoicesPaidRegion')" class="button-primary">
          {{ $t('billing_block.manage_massively_paid') }}</button>

        <NuxtLink v-if="permissions?.can_add" to="/billing/wallet-managements/e-manage" class="button-primary">
          {{ $t('billing_block.short_mng_e_invoice') }}</NuxtLink>

      </div> -->
      <div class="flex items-center gap-2">
        <AtomsDownloadXlsxButton :rows="items" :columns="exportColumns" file-name="factures"
          :total-pages="pagination.totalPages" :server-export-fn="exportInvoices" :sheet-name="$t('invoices')" />
        <div class="relative inline-block">
          <button v-if="permissions?.can_add" class="button-default flex items-center gap-3 relative" @click="toggleIndexDropdown()">
            <Icon name="fa6-solid:bars" class="p-1" />
            {{ t('common.operations') }}
          </button>
          <div v-if="openIndexDropdown"
              class="absolute top-full right-0 bg-white flex flex-col gap-2 rounded customers-shadow p-2 w-[300px] z-10">
              <button @click="showDetail(null, 'AddInvoiceBudget')" class="button-default">
                <div class="flex justify-between items-center">
                  {{ $t('billing_block.new_invoice') }}
                  <Icon name="fa-solid:file-invoice" class="display-inline mr-2" />
                </div>
              </button>
              <button @click="showDetail(null, 'ManageInvoicesPaidRegion')" class="button-default">
                <div class="flex justify-between items-center">
                  {{ $t('billing_block.manage_massively_paid') }}
                  <Icon name="fa-solid:coins" class="display-inline mr-2" />
                </div>
              </button>
              <NuxtLink to="/billing/wallet-managements/e-manage" class="button-default">
                <div class="flex justify-between items-center">
                  {{ $t('billing_block.short_mng_e_invoice') }}
                  <Icon name="fa6-solid:file" class="display-inline mr-2" />
                </div>
              </NuxtLink>
          </div>
        </div>
      </div>
    </div>
    <form id="form_filter" role="search"
      class="mb-3 text-base border-b border-gray-400 flex flex-start gap-4 justify-start items-center"
      @submit.prevent="handleSearch">

      <span class="input-group flex flex-start items-center gap-2 w-60">
        <Icon name="fa6-solid:magnifying-glass" class="text-slate-500" />
        <input v-model="searchInput" @input="handleSearch" id="searchInput" type="text" name="search"
          :placeholder="$t('dashboard.search')" class="w-full p-1 rounded-md focus:outline-none focus-visible:border-0"
          autocomplete="off" />
      </span>

      <div class="h-8 w-px bg-gray-300"></div>

      <span class="input-group flex flex-start items-center gap-2 w-60">
        <Icon name="fa6-solid:magnifying-glass" class="text-slate-500" />
        <input v-model="searchInputTotalFinal" @input="handleTotalFinalInput" id="searchInputTotalFinal" type="text" name="search"
          :placeholder="$t('search_block.search_total_final')"
          class="w-full p-1 rounded-md focus:outline-none focus-visible:border-0 " autocomplete="off" />
      </span>

      <div class="h-8 w-px bg-gray-300"></div>

      <span class="input-group flex flex-start items-center gap-2 w-60">
        <Icon name="fa6-solid:file-lines" class="text-slate-500" />
        <input v-model="searchInputLineItem" @input="handleSearch" id="searchInputLineItem" type="text" name="search"
          :placeholder="$t('search_block.search_line_item')"
          class="w-full p-1 rounded-md focus:outline-none focus-visible:border-0" autocomplete="off" />
      </span>
      <!-- <span class="flex gap-3" v-if="filter_status.length">
        <label v-for="status in filter_status" :key="status.id"
          class="text-slate-800 text-base flex items-center gap-1">
          <input type="checkbox" v-model="selectedFilters" :value="status.id" @change="handleFilterChange" /> {{
            status.name }}
        </label>
      </span> -->

      <FilterSelect :plain="true" :options="filter_status" :filters="selectedFilters" :multiple="true"
        :placeholder="t(`common.statuses`)" @update:modelValue="handleStatusChange($event)">
        <template #icon>
          <Icon name="fa6-solid:ruler-combined" class="text-md ml-2 mr-1" size="10px" />
        </template>
      </FilterSelect>

      <span>
        <button id="filterShow" name="form_filter" type="button" class="px-2 py-1 hover:bg-slate-300 rounded"
          @click="isFilterOpen = !isFilterOpen" title="show">
          <Icon name="fa:filter" class="text-slate-500" />
        </button>
      </span>

      <span>
        <button id="filterReset" name="form_filter" type="button" class="px-2 py-1 hover:bg-slate-300 rounded"
          @click="resetFilters" title="reset">
          <Icon name="fa6-solid:rotate-right" class="text-slate-500" />
        </button>
      </span>
    </form>

    <div class="px-2 text-base flex flex-start gap-2 justify-start items-center" v-if="isFilterOpen">

      <FilterSelect v-if="isFilterShown.some(filter => filter.id === 'origin')" :options="filter_origins"
        :filters="selectedOrigins" :multiple="false" :placeholder="t(`common.origin`)"
        @update:modelValue="handleOriginChange($event)">
        <template #icon>
          <Icon name="fa6-solid:coins" class="text-md ml-2 mr-1" size="10px" />
        </template>
      </FilterSelect>

      <FilterSelect v-if="isFilterShown.some(filter => filter.id === 'billing_id')" :textInput="true"
        :filters="selectedBilling" :placeholder="t(`billing_block.insert_id`)" @update:modelValue="handleBillingChange($event)"
        :initialValue="billing">
        <template #icon>
          <Icon name="fa6-solid:clipboard" class="text-md ml-2 mr-1" size="10px" /> id facturació:
        </template>
      </FilterSelect>

      <FilterSelect v-if="isFilterShown.some(filter => filter.id === 'issue_date')" :datePick="true"
        :filters="selectedIssueDate" :placeholder="t(`billing_block.sel_issue_date`)"
        @update:modelValue="handleIssueDateChange($event)">
        <template #icon>
          <Icon name="fa6-solid:calendar" class="text-md ml-2 mr-1" size="10px" />
        </template>
      </FilterSelect>

      <FilterSelect v-if="isFilterShown.some(filter => filter.id === 'due_date')" :datePick="true"
        :filters="selectedDueDate" :placeholder="t(`billing_block.sel_due_date`)"
        @update:modelValue="handleDueDateChange($event)">
        <template #icon>
          <Icon name="fa6-solid:calendar-xmark" class="text-md ml-2 mr-1" size="10px" />
        </template>
      </FilterSelect>

      <FilterSelect v-if="isFilterShown.some(filter => filter.id === 'serie')" :options="filter_serie"
        :filters="selectedSerie" :multiple="true" :placeholder="t(`billing_block.serie`)"
        @update:modelValue="handleSerieChange($event)">
        <template #icon>
          <Icon name="fa6-solid:clipboard" class="text-md ml-2 mr-1" size="10px" />
        </template>
      </FilterSelect>

      <FilterSelect v-if="isFilterShown.some(filter => filter.id === 'payment_type')" :options="filter_payment_types"
        :filters="selectedPaymentTypes" :multiple="true" :placeholder="t(`payment_types`)"
        @update:modelValue="handlePaymentTypeChange($event)">
        <template #icon>
          <Icon name="fa6-solid:credit-card" class="text-md ml-2 mr-1" size="10px" />
        </template>
      </FilterSelect>

      <FilterSelect :defaultOpen="false" :options="filtersExtra" :filters="isFilterShown" :multiple="true"
        :selector="true" :placeholder="t('common.additional_filters')" @update:modelValue="handleFiltersChange($event)">
        <template #icon>
          <Icon name="fa6-solid:plus" class="text-md ml-2 mr-1" size="10px" />
        </template>
      </FilterSelect>

    </div>

    <DataTable
      grid-template="120px,90px,220px,150px,100px,100px,100px,80px,100px,120px,90px"
      :height-offset="240"
      :pending="pending"
      :error="error"
      :is-empty="items.length === 0"
      @retry="getData">
      <template #header>
        <TableHeader :label="$t('common.identification')" sortKey="token" :currentSortBy="sortBy" :sortDesc="sortDesc"
          @sort="handleSort" />
        <TableHeader :label="$t('common.date')" sortKey="issue_date" :currentSortBy="sortBy" :sortDesc="sortDesc"
          @sort="handleSort" />
        <TableHeader :label="$t('common.title')" :sortable="false" />
        <TableHeader :label="$t('contract_block.holder')" sortKey="customer_token_final" :currentSortBy="sortBy" :sortDesc="sortDesc"
        @sort="handleSort" />
        <TableHeader :label="$t('contract')" :sortable="false" />
        <TableHeader :label="$t('billing_block.total_invoice')" sortKey="total_final" :currentSortBy="sortBy" :sortDesc="sortDesc"
          @sort="handleSort" />
        <TableHeader :label="$t('billing_block.total_to_pay')" sortKey="left_to_pay" :currentSortBy="sortBy" :sortDesc="sortDesc"
          @sort="handleSort" />
        <TableHeader :label="$t('payment_types')" sortKey="payment_type" :currentSortBy="sortBy" :sortDesc="sortDesc"
          @sort="handleSort" />
        <TableHeader :label="$t('common.origin')" :sortable="false" />
        <TableHeader :label="$t('common.status')" sortKey="status" :currentSortBy="sortBy" :sortDesc="sortDesc"
          @sort="handleSort" />
        <TableHeader :label="$t('common.due_date')" sortKey="due_date" :currentSortBy="sortBy" :sortDesc="sortDesc"
          @sort="handleSort" />
      </template>

      <template #default="{ gridStyle }">
        <div v-for="item in items" :key="item.id"
          class="gap-3 text-base border-b items-center bg-white"
          :style="gridStyle"
          :class="{ 'bg-yellow-50': item.id === selectedItemId }">
          <span>
            <button class="group flex justify-between w-full items-center p-1 text-sky-500 text-nowrap text-left"
              @click="showDetail(item.id, 'InvoiceRegion');">
              <abbr :title="item.id" class="no-underline">{{ item.serie_final }}</abbr>
              <Icon name="fa6-solid:eye"
                class="opacity-0 group-hover:opacity-100 text-slate-500 mr-1 transition-opacity duration-200 ease-in-out" />
            </button>
          </span>
          <span class="p-1">{{ formatDate(item.issue_date) }}</span>
          <span class="p-1">{{ item.title_final }}</span>
          <span class="p-1"><abbr :title="item.customer_token">{{ item.customer_final }}</abbr></span>
          <span class="p-1">{{ item.contract_token ? item.contract_token : item.contract_request_token ? item.contract_request_token : item.contract_termination_contract_token ? item.contract_termination_contract_token : '-' }}</span>

          <span class="p-1">{{ formatMoneyWithCurrency(item.total_final) }}</span>
          <span class="p-1">{{ formatMoneyWithCurrency(item.left_to_pay) }}</span>
          <span class="p-1 text-sm">{{ item.payment_type_final }}</span>
          <span class="p-1">{{ item.origin_name }}</span>
          <span>
            <AtomsColorBadge :value="item?.status_name" :color="item?.status_color" />
          </span>
          <span class="p-1">{{ item.due_date ? formatDate(item.due_date) : '' }}</span>
        </div><!-- end for items -->
      </template>
    </DataTable>
    <div id="list__footer">
      <Pagination v-if="items.length > 0" :pagination="pagination" @update:page="handlePageChange" />
    </div>
  </div><!-- end wrapper -->

  <div role="region" id="right_page"
    class="fixed h-full border-l border-gray-100 top-0 right-0 transition-all duration-500 ease py-2 text-base bg-white overflow-x-hidden"
    :class="{ 'translate-x-0': showRegion, 'translate-x-[2000px]': !showRegion, 'w-[95%]': isSubRegionOpen, 'w-[55%]': !isSubRegionOpen }">
    <div id="region_nav" class="mb-3 px-3">
      <button @click="toggleRegion(false)" class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300">
        <Icon name="fa6-solid:angles-right" class="text-slate-500" />
      </button>
    </div>
    <div v-if="regionComponent" class="pl-10 h-full">
      <InvoiceRegion v-if="regionComponent === 'InvoiceRegion'" :id="detail" :isSubRegionOpen="isSubRegionOpen"
        @show-subregion="handleSubRegionEvent" @changed="refresh" @close-subregion="toggleRegion(false)" @update-id="(newId) => detail = newId" />
      <AddInvoiceBudget v-if="regionComponent === 'AddInvoiceBudget'" :service="$InvoiceApiService" :entity="'custom'"
        :isSubRegion="false" :individual="true" :selectedCustom="null"
        @show-subregion="handleSubRegionEvent" @change="refresh" @close-subregion="toggleRegion(false)" />
      <ManageInvoicesPaidRegion v-if="regionComponent === 'ManageInvoicesPaidRegion'" 
        :filters="{ origin, billing, issue_date, due_date, serie, statuses, searchInput, searchInputTotalFinal, payment_types }"
        @changed="refresh" @close="toggleRegion(false)" />
    </div>
  </div>

</template>
