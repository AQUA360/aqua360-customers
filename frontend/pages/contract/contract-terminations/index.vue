<script setup>
import { ref, onMounted, nextTick, computed, watch } from 'vue';
import { useRouter } from 'vue-router';
import debounce from 'lodash.debounce';
import { useI18n } from 'vue-i18n';
import { formatDate } from '~/utils/date';
import FilterSelect from '~/components/atoms/FilterSelect.vue';
import Pagination from '~/components/molecules/Pagination.vue';
import H1 from '~/components/atoms/H1.vue';
import ContractTerminationRegion from '~/components/organisms/ContractTerminationRegion.vue';
import TableHeader from '~/components/atoms/TableHeader.vue';
import { useToast } from 'vue-toastification';
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
  }
}

const route = useRoute();
const router = useRouter();
const { $ContractTerminationApiService, $ConfiglistApiService, $ConfigProjectApiService } = useNuxtApp();
const pending = ref(true);
const error = ref(null);
const items = ref([]);
const searchInput = ref('');
const searchByAddress = ref('');
const selectedFilters = ref([]);
const filter_status = ref([]);
const sortBy = ref(null);
const sortDesc = ref(false);

const filter_types = ref([]);
const types = ref([]);
const selected_types = ref([]);

const filter_has_invoice = ref([]);
const has_invoice = ref(null);
const selected_has_invoice = ref([]);

const isFilterOpen = ref(false);
const showAddressSearch = ref(false);
const isFilterShown = ref([]);
const filtersExtra = ref([]);

const finishedStatusToken = ref(null);
const objectPermissions = ref(null);

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
    const data = await $ContractTerminationApiService.getPermissions();
    objectPermissions.value = data;
  } catch (err) {
    error.value = err;
  }
}

const exportColumns = computed(() => [
  { header: t('common.date'), value: (row) => formatDate(row.created_at), key: 'created_at' },
  { header: t('common.identification'), value: (row) => row.token, key: 'token' },
  { header: t('common.approval_date'), value: (row) => row.approved_at ? formatDate(row.approved_at) : '-', key: 'approved_at' },
  { header: t('contract'), value: (row) => row.contract_name || row.contract_token },
  { header: t('supply_point'), value: (row) => row.supply_point, key: 'contract__supply_point_default' },
  { header: t('contract_block.holder'), value: (row) => row.holder_name, key: 'contract__holder' },
  { header: t('common.status'), value: (row) => row.status_name, key: 'status' },
]);

const exportContractTerminations = (columns) => $ContractTerminationApiService.exportData(
  searchInput.value, selectedFilters.value, sortBy.value, sortDesc.value,
  types.value, has_invoice.value, searchByAddress.value, columns
);

const getData = async (searchQuery = '', filters = [], page = 1, sort = null, desc = false, load = true, has_invoice = null, searchByAddressQuery = '') => {
  if (!objectPermissions.value?.can_view) {
    toast.error(t('common.no_permissions'));
    return navigateTo('/');
  }
  pending.value = load;
  error.value = null;
  
  try {
    finishedStatusToken.value = await $ConfigProjectApiService.get('contract_termination_completed_token');
    const data = await $ContractTerminationApiService.getAll(searchQuery, filters, page, sort, desc, types.value, has_invoice, searchByAddressQuery);

    items.value = data.results;
    Object.assign(pagination.value, {
      total: data.count,
      totalPages: Math.ceil(data.count / pagination.value.perPage),
      previous: data.previous,
      next: data.next,
      isFiltered: String(searchQuery).trim() !== '' || String(searchByAddressQuery).trim() !== ''
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
    const data = await $ContractTerminationApiService.getFilterStatus();
    filter_status.value = data;
  } catch (err) {
    error.value = err;
  }
}

const getFilterTypes = async () => {
  error.value = null;
  try {
    const data = await $ConfiglistApiService.getAll('contract/contract-termination-request-type');
    filter_types.value = data.results;
  } catch (err) {
    error.value = err;
  }
}

const debouncedGetData = debounce((query, filters, sort, desc, load = true, has_invoice = null, searchByAddressQuery = '') => {
  getData(query, filters, pagination.value.page, sort, desc, load, has_invoice, searchByAddressQuery);
}, 300);

const handleSearch = () => {
  pagination.value.page = 1;
  debouncedGetData(searchInput.value, selectedFilters.value, sortBy.value, sortDesc.value, true,has_invoice.value, searchByAddress.value);
}

const handleAddressChange = (addressString) => {
  searchByAddress.value = addressString;
  pagination.value.page = 1;
  debouncedGetData(searchInput.value, selectedFilters.value, sortBy.value, sortDesc.value, true, has_invoice.value, addressString);
}

const handleFilterChange = () => {
  pagination.value.page = 1;
  handleSearch();
}

const handlePageChange = (newPage) => {
  pagination.value.page = newPage;
  getData(searchInput.value, selectedFilters.value, newPage, sortBy.value, sortDesc.value, true, has_invoice.value, searchByAddress.value);
}

const handleSort = (key) => {
  if (sortBy.value === key) {
    sortDesc.value = !sortDesc.value;
  } else {
    sortBy.value = key;
    sortDesc.value = false;
  }
  getData(searchInput.value, selectedFilters.value, pagination.value.page, sortBy.value, sortDesc.value, true, has_invoice.value);
}

const handleTypeChange = (event) => {
  selected_types.value = event;
  types.value = []
  selected_types.value.forEach(element => {
    types.value.push(element.id);
  })
  pagination.value.page = 1;
  handleSearch();
}

const handleHasInvoiceChange = (event) => {
  if (event && event.length > 0) has_invoice.value = event[0].id;
  else has_invoice.value = null;
  pagination.value.page = 1;
  handleSearch();
}

const checkInAdvacedFilters = (newFilters) => {
  if (isFilterShown.value.some(filter => filter.id === 'type') && !newFilters.some(filter => filter.id === 'type')) {
    types.value = [];
    selected_types.value = [];
    handleSearch();
  } else if (isFilterShown.value.some(filter => filter.id === 'no_invoice') && !newFilters.some(filter => filter.id === 'no_invoice')) {
    has_invoice.value = null;
    handleSearch();
  } 
}

const handleFiltersChange = (event) => {
  let newFilters = event
    .filter(el => !isFilterShown.value.includes(el.id));

  checkInAdvacedFilters(newFilters)
  isFilterShown.value = [];
  isFilterShown.value = [...isFilterShown.value, ...newFilters];
}

const resetFilters = () => {
  searchInput.value = '';
  searchByAddress.value = '';
  pagination.value.page = 1;
  types.value = [];
  selected_types.value = [];
  selected_has_invoice.value = [];
  isFilterShown.value = [];
  has_invoice.value = null;
  isFilterOpen.value = false;
  showAddressSearch.value = false;
  getData();
};

const toggleAddressFilter = () => {
  if (showAddressSearch.value) {
    showAddressSearch.value = false;
    if (!isFilterShown.value.length) {
      isFilterOpen.value = false;
      return;
    }
  } else {
    showAddressSearch.value = true;
    isFilterOpen.value = true;
  }
};

onMounted(async() => {
  await getPermissions();
  if (objectPermissions.value?.can_view) {
    filtersExtra.value.push(
        { name: t("common.type"), id: "type" },
        { name: t("common.no_invoice"), id: "no_invoice" },
      );
    filter_has_invoice.value = [{id: true, name: t("common.no_invoice")}, {id: false, name: t("common.has_invoice")}];
    getData();
    getFilterTypes();
    getFilterStatus();
    checkRouteQuery();
  } else {
    pending.value = false;
    toast.error(t('common.no_permissions'));
    return navigateTo('/');
  }
});

const checkRouteQuery = () => {
  if (route.query?.action == 'showDetail') {
    showDetail(route.query.id)
  } else if (route.query?.action == 'filterPage') {
    selectedFilters.value = route.query.variables;
    console.log(selectedFilters.value)
    handleSearch();
  }
}


const showDetail = async (id) => {
  await toggleRegion(false);
  detail.value = id;
  selectedItemId.value = id;
  toggleRegion(true);
}

// Watch for changes in searchInput and selectedFilters and reset pagination to 1
watch([searchInput], () => {
  pagination.value.page = 1;
  handleSearch();
});

const handleSubRegionEvent = (event) => {
  isSubRegionOpen.value = event;
}
watch(() => route.query, () => {
  checkRouteQuery()
}, { immediate: true })
</script>

<template>
  <div id="wrapper" class="text-base">
    <div class="flex justify-between items-center mb-2">
      <H1 class="mb-2">{{ $t('common.contract_terminations') }}</H1>
      <span>
        <AtomsDownloadXlsxButton :rows="items" :columns="exportColumns" file-name="contract_terminations"
          :total-pages="pagination.totalPages" :server-export-fn="exportContractTerminations" :sheet-name="t('common.contract_terminations')" />
      </span>
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
      <span class="flex gap-3" v-if="filter_status.length">
        <label v-for="status in filter_status" :key="status.id"
          class="text-slate-800 text-base flex items-center gap-1">
          <input type="checkbox" v-model="selectedFilters" :value="status.id" @change="handleFilterChange" /> {{
            status.name }}
        </label>
      </span>
      <span class="flex items-center gap-1">
        <button id="filterShow" name="form_filter" type="button" class="px-2 py-1 hover:bg-slate-300 rounded"
          @click="isFilterOpen = !isFilterOpen" title="show">
          <Icon name="fa:filter" class="text-slate-500" />
        </button>
        <button id="filterAddress" name="form_filter" type="button"
          class="px-2 py-1 hover:bg-slate-300 rounded"
          :class="{ 'bg-slate-300': showAddressSearch }"
          @click="toggleAddressFilter"
          :title="$t('address_block.address')">
          <Icon name="fa6-solid:house" class="text-slate-500" />
        </button>
      </span>
      <span>
        <button id="filterReset" name="form_filter" type="button" class="px-2 py-1 hover:bg-slate-300 rounded"
          @click="resetFilters" title="reset">
          <Icon name="fa6-solid:rotate-right" class="text-slate-500" />
        </button>
      </span>
    </form>

    <div class="px-2 text-base flex flex-start gap-2 justify-start items-center flex-wrap" v-if="isFilterOpen">

      <span v-if="showAddressSearch" class="flex items-center gap-2">
        <AtomsInputAddressSearch :value="searchByAddress" @change="handleAddressChange" />
      </span>

      <FilterSelect v-if="isFilterShown.some(filter => filter.id === 'type')" :options="filter_types"
        :filters="selected_types" :multiple="true" :placeholder="t(`common.types`)"
        @update:modelValue="handleTypeChange($event)">
        <template #icon>
          <Icon name="fa6-solid:circle-check" class="text-md ml-2 mr-1" size="10px" />
        </template>
      </FilterSelect>

      <FilterSelect v-if="isFilterShown.some(filter => filter.id === 'no_invoice')" :options="filter_has_invoice"
        :filters="selected_has_invoice" :multiple="true" :placeholder="t(`common.no_invoice`)"
        @update:modelValue="handleHasInvoiceChange($event)">
        <template #icon>
          <Icon name="fa6-solid:circle-check" class="text-md ml-2 mr-1" size="10px" />
        </template>
      </FilterSelect>

      <FilterSelect :options="filtersExtra" :filters="isFilterShown" :multiple="true" :selector="true"
        :placeholder="t('common.additional_filters')" @update:modelValue="handleFiltersChange($event)">
        <template #icon>
          <Icon name="fa6-solid:plus" class="text-md ml-2 mr-1" size="10px" />
        </template>
      </FilterSelect>

    </div>

    <DataTable
      grid-template="80px,20px,1fr,1fr,1fr,2fr,150px,100px"
      :pending="pending"
      :error="error"
      :is-empty="items.length === 0"
      @retry="getData">
      <template #header>
        <TableHeader :label="$t('common.date')" sortKey="created_at" :currentSortBy="sortBy" :sortDesc="sortDesc"
          @sort="handleSort" />
          <span></span>
        <TableHeader :label="$t('common.identification')" sortKey="token" :currentSortBy="sortBy" :sortDesc="sortDesc"
          @sort="handleSort" />
        <TableHeader :label="$t('common.approval_date')" sortKey="approved_at" :currentSortBy="sortBy" :sortDesc="sortDesc"
          @sort="handleSort" />
        <TableHeader :label="$t('contract')" sortKey="contract" :currentSortBy="sortBy" :sortDesc="sortDesc"
          @sort="handleSort" />
        <TableHeader :label="$t('supply_point')" sortKey="contract__supply_point_default" :currentSortBy="sortBy"
          :sortDesc="sortDesc" @sort="handleSort" />
        <TableHeader :label="$t('contract_block.holder')" sortKey="contract__holder" :currentSortBy="sortBy" :sortDesc="sortDesc"
          @sort="handleSort" />
        <TableHeader :label="$t('common.status')" sortKey="status" :currentSortBy="sortBy" :sortDesc="sortDesc"
          @sort="handleSort" />
      </template>

      <template #default="{ gridStyle }">
        <div v-for="item in items" :key="item.id"
          class="gap-3 text-base border-b items-center bg-white group"
          :style="gridStyle"
          :class="{ 'bg-yellow-50': item.id === selectedItemId }">
          <span class="p-0">{{ formatDate(item.created_at) }}</span>
          <span class="flex justify-center items-center">
            <abbr v-if="item.status_token == finishedStatusToken && !item.has_invoice && !item.ignore_invoice" :title="t('contract_block.termination_without_invoice')">
              <Icon  name="fa6-solid:circle-exclamation" class="text-orange-500" />
            </abbr>
          </span>
          <span>
            <button class="group flex justify-between w-full items-center p-1 text-sky-500 text-nowrap text-left"
              @click="showDetail(item.id);">
              <abbr :title="item.token" class="no-underline">{{ item.token }}</abbr>
              <Icon name="fa6-solid:eye"
                class="opacity-0 group-hover:opacity-100 text-slate-500 mr-1 transition-opacity duration-200 ease-in-out" />
            </button>
          </span>
          <span class="p-0">{{ item.approved_at ? formatDate(item.approved_at) : '-' }}</span>
          <span class="p-0">{{ item.contract_name || item.contract_token }}</span>
          <span class="p-1">{{ item.supply_point }}</span>
          <span class="p-1">{{ item.holder_name }}</span>
          <span class="p-1">
            <AtomsColorBadge :color="item.status_color" :value="item.status_name" />
          </span>
        </div><!-- end for items -->
      </template>
    </DataTable>
    <div id="list__footer">
      <Pagination v-if="items.length > 0" :pagination="pagination" @update:page="handlePageChange" />
    </div>
  </div><!-- end wrapper -->

  <div role="region" id="right_page"
    class="fixed h-full border-l border-gray-100 top-0 right-0 transition-all duration-500 ease py-2 text-base bg-white"
    :class="{ 'translate-x-0': showRegion, 'translate-x-[2000px]': !showRegion, 'w-[95%]': isSubRegionOpen, 'w-[60%]': !isSubRegionOpen }">
    <div id="region_nav" class="mb-3 px-3">
      <button @click="toggleRegion(false)" class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300">
        <Icon name="fa6-solid:angles-right" class="text-slate-500" />
      </button>
    </div>
    <div class="pl-10 h-full">
      <ContractTerminationRegion v-if="detail" :id="detail" :isSubRegionOpen="isSubRegionOpen"
        @show-subregion="handleSubRegionEvent" @close-subregion="toggleRegion(false)"></ContractTerminationRegion>
    </div>
  </div>

</template>
