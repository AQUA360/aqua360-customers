<script setup>
import { computed } from 'vue';
import { useRouter } from 'vue-router';
import debounce from 'lodash.debounce';
import { useI18n } from 'vue-i18n';
import { formatDate } from '~/utils/date';
import { formatMoneyWithCurrency } from '~/utils/money';
import InvoiceRegion from '~/components/organisms/InvoiceRegion.vue';
import Pagination from '~/components/molecules/Pagination.vue';
import H1 from '~/components/atoms/H1.vue';
import ContractRegion from '~/components/organisms/ContractRegion.vue';
import ContractRequestRegion from '~/components/organisms/ContractRequestRegion.vue';
import TableHeader from '~/components/atoms/TableHeader.vue';
import FilterSelect from '~/components/atoms/FilterSelect.vue';
import { useToast } from 'vue-toastification';
import AddInvoiceBudget from '~/components/molecules/AddInvoiceBudget.vue';
import DataTable from '~/components/organisms/DataTable.vue';

const { t } = useI18n();
const toast = useToast();
const showRegion = ref(false);

const detail = ref(null);
const selectedItemId = ref(null);
const isSubRegionOpen = ref(false);
const toggleRegion = (force) => {
  showRegion.value = force !== undefined ? force : !showRegion.value;
  if (showRegion.value == false) {
    isSubRegionOpen.value = false;
    detail.value = null
    selectedItemId.value = null
    regionComponent.value = null
  }
}

const route = useRoute();
const router = useRouter();
const { $InvoiceApiService, $ConfiglistApiService } = useNuxtApp();
const pending = ref(true);
const error = ref(null);
const items = ref([]);
const searchInput = ref('');
const sortBy = ref(null);
const sortDesc = ref(false);
const regionComponent = ref(null)

const selectedFilters = ref([]);
const selectedOrigins = ref([]);
const selectedBilling = ref([]);
const selectedIssueDate = ref([]);
const selectedDueDate = ref([]);

const filter_status = ref([])
const filter_origins = ref([])
const issue_date = ref({})
const due_date = ref({})
const statuses = ref([])
const origin = ref(null)
const billing = ref(null)

const isFilterOpen = ref(false);
const isFilterShown = ref([]);
const filtersExtra = ref([]);

const permissions = ref(null);
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

const getData = async (searchQuery = '', filters = [], page = 1, sort = null, desc = false, contract = null, is_invoice = false, origin = null, billing = null, issue_date = null, due_date = null) => {
  if (!permissions.value?.can_view) {
    toast.error(t('common.no_permissions'));
    return navigateTo('/');
  }
  pending.value = true;
  error.value = null;
  try {
    const data = await $InvoiceApiService.getAll(searchQuery, filters, page, sort, desc, contract, false, origin, billing, issue_date, due_date);

    items.value = data.results;
    Object.assign(pagination.value, {
      total: data.count,
      totalPages: Math.ceil(data.count / pagination.value.perPage),
      previous: data.previous,
      next: data.next,
      isFiltered: String(searchQuery).trim() !== ''
    });
    
    
    nextTick(() => {
      document.getElementById('searchInput').focus();
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

const debouncedGetData = debounce((query, filters, sort, desc, contract, is_invoice, origin, billing, issue_date, due_date) => {
  getData(query, filters, pagination.value.page, sort, desc, contract, is_invoice, origin, billing, issue_date, due_date);
}, 300);

const handleSearch = () => {
  pagination.value.page = 1;
  debouncedGetData(searchInput.value, statuses.value, sortBy.value, sortDesc.value, null, false, origin.value, billing.value, issue_date.value, due_date.value);
}

const handlePageChange = (newPage) => {
  pagination.value.page = newPage;
  getData(searchInput.value, statuses.value, newPage, sortBy.value, sortDesc.value, null, false, origin.value, billing.value, issue_date.value, due_date.value);
}

const handleSort = (key) => {
  if (sortBy.value === key) {
    sortDesc.value = !sortDesc.value;
  } else {
    sortBy.value = key;
    sortDesc.value = false;
  }
  getData(searchInput.value, statuses.value, pagination.value.page, sortBy.value, sortDesc.value, null, false, origin.value, billing.value, issue_date.value, due_date.value);
}

const refresh = () => {
  debouncedGetData(searchInput.value, statuses.value, sortBy.value, sortDesc.value, null, false, origin.value, billing.value, issue_date.value, due_date.value);
}

// XLSX export — columns mirror the visible table columns (in display order).
const exportColumns = computed(() => [
  { header: t('common.identification'), value: (row) => row.serie_final, key: 'serie' },
  { header: t('billing_block.final_invoice'), value: (row) => row.invoice_budget?.serie_final || '' },
  { header: t('common.date'), value: (row) => row.issue_date ? formatDate(row.issue_date) : '', key: 'issue_date' },
  { header: t('common.title'), value: (row) => row.title_final, key: 'number' },
  { header: t('contract_block.holder'), value: (row) => row.customer_final, key: 'customer' },
  { header: t('common.total'), value: (row) => row.total_final, key: 'total_final' },
  { header: t('common.origin'), value: (row) => row.origin_name, key: 'origin' },
]);

// Hybrid export: single page → client-side; multiple pages → server (all-pages, filter-aware).
const exportBudgets = (columns) => $InvoiceApiService.exportData(
  searchInput.value, statuses.value, sortBy.value, sortDesc.value, null, false, origin.value, billing.value,
  issue_date.value, due_date.value, [], null, [], null, null, null, columns
);

const resetFilters = () => {
  searchInput.value = '';
  pagination.value.page = 1;
  selectedFilters.value = []
  statuses.value = []
  selectedOrigins.value = []
  origin.value=null
  isFilterShown.value = [];
  issue_date.value = {};
  due_date.value = {};
  isFilterOpen.value = false
  // filtersExtra.value = [];
  getData();
};

const handleBillingChange = (event) => {
  selectedBilling.value = event;
  billing.value = null
  billing.value = selectedBilling.value[0]
  pagination.value.page = 1;
  handleSearch();
}

const handleIssueDateChange = (event) => {
  //HANDLE ISSUE DATE
  issue_date.value = event;
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
  } else if (isFilterShown.value.some(filter => filter.id === 'origin') && !newFilters.some(filter => filter.id === 'origin')) {
    origin.value = null;
    selectedOrigins.value = [];
    handleSearch();
  }
}

onMounted(async () => {
  await getPermissions();
  if (permissions.value?.can_view) {
    getFilterStatus()
    getFilterOrigin()

    filtersExtra.value.push(
      { name: t("common.date"), id: "issue_date" }, 
      { name: t("common.origin"), id: "origin" }, 
      { name: t("billing_block.billing_id"), id: "billing_id" }, 
    );

    await getData('',[],1,null,false,null,true,null,billing.value);
    checkRouteQuery()
  } else {
    toast.error(t('common.no_permissions'));
    pending.value = false;
    return navigateTo('/');
  }
});

const checkRouteQuery = () => {
  if (route.query?.billing) {
    billing.value = route.query.billing
    isFilterOpen.value = true
    isFilterShown.value = [{ name: t("billing_block.billing_id"), id: "billing_id" }];
  }
  if (route.query?.action == 'showDetail') {
    showDetail(route.query.id)
  }
}


const showDetail = async (id, component) => {
  toggleRegion(false)
  regionComponent.value = component
  detail.value = id;
  selectedItemId.value = id;
  toggleRegion(true);
}

// Watch for changes in searchInput and selectedFilters and reset pagination to 1
watch([searchInput, selectedFilters], () => {
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
      <H1 class="mb-2">{{ $t('common.budgets') }}</H1>
      <div class="flex items-center gap-2">
        <AtomsDownloadXlsxButton :rows="items" :columns="exportColumns" file-name="budgets"
          :total-pages="pagination.totalPages" :server-export-fn="exportBudgets" :sheet-name="t('common.budgets')" />
        <button v-if="permissions?.can_add" class="button-primary flex items-center gap-3"
          @click="showDetail(null, 'AddInvoiceBudget')">
          <Icon name="fa6-solid:file-circle-plus" class="p-1" />
          {{ $t('billing_block.new_budget') }}
        </button>
      </div>
    </div>
    <form id="form_filter" role="search"
      class="mb-3 text-base border-b border-gray-400 flex flex-start gap-4 justify-start items-center"
      @submit.prevent="handleSearch">

      <span class="input-group flex flex-start items-center gap-2 w-80">
        <Icon name="fa6-solid:magnifying-glass" class="text-slate-500" />
        <input v-model="searchInput" @input="handleSearch" id="searchInput" type="text" name="search"
          :placeholder="$t('dashboard.search')" class="w-full p-1 rounded-md focus:outline-none focus-visible:border-0"
          autocomplete="off" />
      </span>

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

      <FilterSelect v-if="isFilterShown.some(filter => filter.id === 'origin')"
        :options="filter_origins" :filters="selectedOrigins" :multiple="false"
        :placeholder="t(`common.origin`)" @update:modelValue="handleOriginChange($event)">
        <template #icon>
          <Icon name="fa6-solid:coins" class="text-md ml-2 mr-1" size="10px" />
        </template>
      </FilterSelect>
      
      <FilterSelect v-if="isFilterShown.some(filter => filter.id === 'billing_id')" :textInput="true" :filters="selectedBilling"
        :placeholder="t(`billing_block.insert_id`)" @update:modelValue="handleBillingChange($event)" :initialValue="billing">
        <template #icon>
          <Icon name="fa6-solid:clipboard" class="text-md ml-2 mr-1" size="10px" /> {{ $t('billing_block.billing_id') }}:
        </template>
      </FilterSelect>
      
      <FilterSelect v-if="isFilterShown.some(filter => filter.id === 'issue_date')" :datePick="true" :filters="selectedIssueDate"
        :placeholder="t(`billing_block.sel_issue_date`)" @update:modelValue="handleIssueDateChange($event)">
        <template #icon>
          <Icon name="fa6-solid:calendar" class="text-md ml-2 mr-1" size="10px" />
        </template>
      </FilterSelect>

      <FilterSelect :defaultOpen="false" :options="filtersExtra" :filters="isFilterShown" :multiple="true" :selector="true"
        :placeholder="t('common.additional_filters')" @update:modelValue="handleFiltersChange($event)">
        <template #icon>
          <Icon name="fa6-solid:plus" class="text-md ml-2 mr-1" size="10px" />
        </template>
      </FilterSelect>

    </div>

    <DataTable
      grid-template="150px,150px,100px,1fr,1fr,100px,1fr"
      :pending="pending"
      :error="error"
      :is-empty="items.length === 0"
      @retry="getData">
      <template #header>
        <TableHeader :label="$t('common.identification')" sortKey="serie_final" :currentSortBy="sortBy" :sortDesc="sortDesc"
          @sort="handleSort" />
        <TableHeader :label="$t('billing_block.final_invoice')" :sortable="false"/>
        <TableHeader :label="$t('common.date')" sortKey="issue_date" :currentSortBy="sortBy" :sortDesc="sortDesc"
          @sort="handleSort" />
        <TableHeader :label="$t('common.title')" :sortable="false" />
        <TableHeader :label="$t('contract_block.holder')" :sortable="false" />
        <TableHeader :label="$t('common.total')" sortKey="total_final" :currentSortBy="sortBy" :sortDesc="sortDesc"
          @sort="handleSort" />
        <TableHeader :label="$t('common.origin')" :sortable="false" />
      </template>

      <template #default="{ gridStyle }">
        <div v-for="item in items" :key="item.id"
          class="gap-3 text-base border-b items-center bg-white"
          :style="gridStyle"
          :class="{ 'bg-yellow-50': item.id === selectedItemId}">
          <span>
            <button class="group flex justify-between w-full items-center p-1 text-sky-500 text-nowrap text-left"
              @click="showDetail(item.id, 'InvoiceRegion');">
              <abbr :title="item.id" class="no-underline">{{ item.serie_final }}</abbr>
              <Icon name="fa6-solid:eye"
                class="opacity-0 group-hover:opacity-100 text-slate-500 mr-1 transition-opacity duration-200 ease-in-out" />
            </button>
          </span>
          <span>
            <button v-if="item.invoice_budget" class="group flex justify-between w-full items-center p-1 text-sky-500 text-nowrap text-left"
              @click="showDetail(item.invoice_budget.id, 'InvoiceRegion');">
              <abbr :title="item.id" class="no-underline">{{ item.invoice_budget.serie_final }}</abbr>
              <Icon name="fa6-solid:eye"
                class="opacity-0 group-hover:opacity-100 text-slate-500 mr-1 transition-opacity duration-200 ease-in-out" />
            </button>
            <span v-else>-</span>
          </span>
          <span class="p-1">{{ formatDate(item.issue_date) }}</span>
          <span class="p-1">{{ item.title_final }}</span>
          <span class="p-1"><abbr :title="item.customer_token">{{ item.customer_final }}</abbr></span>

          <span class="p-1">{{ formatMoneyWithCurrency(item.total_final) }}</span>
          <span class="p-1">{{ item.origin_name }}</span>
        </div><!-- end for items -->
      </template>
    </DataTable>
    <div id="list__footer">
      <Pagination v-if="items.length > 0" :pagination="pagination" @update:page="handlePageChange" />
    </div>
  </div><!-- end wrapper -->

  <div role="region" id="right_page"
    class="fixed h-full border-l border-gray-100 top-0 right-0 transition-all duration-500 ease py-2 text-base bg-white"
    :class="{ 'translate-x-0': showRegion, 'translate-x-[2000px]': !showRegion, 'w-[95%]': isSubRegionOpen, 'w-[55%]': !isSubRegionOpen }">
    <div id="region_nav" class="mb-3 px-3">
      <button @click="toggleRegion(false)" class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300">
        <Icon name="fa6-solid:angles-right" class="text-slate-500" />
      </button>
    </div>
    <div class="pl-10 h-full">
      <InvoiceRegion v-if="regionComponent === 'InvoiceRegion'" :id="detail" :isSubRegionOpen="isSubRegionOpen" :isBudget="true"
        @show-subregion="handleSubRegionEvent" @changed="debouncedGetData" @close-subregion="toggleRegion(false)" />
      <AddInvoiceBudget v-if="regionComponent === 'AddInvoiceBudget'" :service="$InvoiceApiService" :entity="'custom'"
        :isSubRegion="false" :individual="true" :selectedCustom="null"
        @show-subregion="handleSubRegionEvent" @change="refresh" @close-subregion="toggleRegion(false)" />
    </div>
  </div>

</template>
