<script setup>
import { ref, onMounted, nextTick, computed, watch } from 'vue';
import { useRouter } from 'vue-router';
import debounce from 'lodash.debounce';
import { useI18n } from 'vue-i18n';
import FilterSelect from '~/components/atoms/FilterSelect.vue';
import Pagination from '~/components/molecules/Pagination.vue';
import H1 from '~/components/atoms/H1.vue';
import ContractRequestRegion from '~/components/organisms/ContractRequestRegion.vue';
import TableHeader from '~/components/atoms/TableHeader.vue';
import { useToast } from 'vue-toastification';
import DataTable from '~/components/organisms/DataTable.vue';

const { t } = useI18n();
const toast = useToast();
const showRegion = ref(false);
const isSubRegionOpen = ref(false);
const detail = ref(null);
const selectedItemId = ref(null);

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
const { $ContractRequestApiService, $ConfiglistApiService, $ConfigProjectApiService } = useNuxtApp();
const pending = ref(true);
const error = ref(null);
const items = ref([]);
const searchInput = ref('');
const searchByAddress = ref('');
const filter_status = ref([]);
const selectedFilters = ref([]);
const sortBy = ref('created_at');
const sortDesc = ref(true);

const permissions = ref(null);

const isFilterOpen = ref(false);
const showAddressSearch = ref(false);
const isFilterShown = ref([]);
const filtersExtra = ref([]);

const filter_client_type = ref([]);
const filter_category = ref([]);
const filter_use_type = ref([]);
const filter_has_invoice = ref([]);
const has_invoice = ref(null);
const client_types = ref([]);
const categories = ref([]);
const use_types = ref([]);
const selected_boolean = ref([]);
const selected_client_types = ref([]);
const selected_categories = ref([]);
const selected_use_types = ref([]);

const pagination = ref({
  page: 1,
  perPage: 50,
  total: 0,
  totalPages: 0,
  previous: null,
  next: null,
  isFiltered: false
})

const exportColumns = computed(() => [
  { header: t('common.creation'), value: (row) => formatDate(row.created_at), key: 'created_at' },
  { header: t('common.identification'), value: (row) => row.token, key: 'token' },
  { header: t('common.requester'), value: (row) => [row.person_name, row.person_surname].filter(Boolean).join(' ') },
  { header: t('common.usage_type'), value: (row) => row.type_name, key: 'type' },
  { header: t('common.short_supply'), value: (row) => row.supply_point_default_token, key: 'supply_point_default' },
  { header: t('meter'), value: (row) => row.meters, key: 'meters' },
  { header: t('address_block.address'), value: (row) => row.supply_point, key: 'supply_point' },
  { header: t('common.status'), value: (row) => row.status_name || row.status_token, key: 'status' },
]);

const exportContractRequests = (columns) => $ContractRequestApiService.exportData(
  searchInput.value, selectedFilters.value, sortBy.value, sortDesc.value,
  categories.value, use_types.value, client_types.value, has_invoice.value,
  searchByAddress.value, columns
);

const getPermissions = async () => {
  error.value = null;
  try {
    const data = await $ContractRequestApiService.getPermissions();
    permissions.value = data;
  } catch (err) {
    error.value = err;
  }
}

const getData = async (searchQuery = '', filters = [], page = 1, sort = null, desc = false, load = true, searchByAddressQuery = '') => {
  if (!permissions.value?.can_view) {
    toast.error(t('common.no_permissions'));
    return navigateTo('/');
  }
  pending.value = load;
  error.value = null;
  
  try {
    const data = await $ContractRequestApiService.getAll(
      searchQuery, filters, page, sort, desc,
      categories.value, use_types.value, client_types.value, has_invoice.value,
      searchByAddressQuery
    );

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

const debouncedGetData = debounce((query, filters, sort, desc, load = true, searchByAddressQuery = '') => {
  getData(query, filters, pagination.value.page, sort, desc, load, searchByAddressQuery);
}, 300);

const handleSearch = () => {
  pagination.value.page = 1;
  debouncedGetData(searchInput.value, selectedFilters.value, sortBy.value, sortDesc.value, true, searchByAddress.value);
}

const handleAddressChange = (addressString) => {
  searchByAddress.value = addressString;
  pagination.value.page = 1;
  debouncedGetData(searchInput.value, selectedFilters.value, sortBy.value, sortDesc.value, true, addressString);
}

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
}

const handleFilterChange = () => {
  pagination.value.page = 1;
  handleSearch();
}

const getFilterStatus = async () => {
  error.value = null;
  try {
    const data = await $ContractRequestApiService.getFilterStatus();
    filter_status.value = data;
  } catch (err) {
    error.value = err;
  }

  try {
    const data = await $ConfigProjectApiService.get('contract_request_pending_token')
    if (data) {
      selectedFilters.value.push(filter_status.value.filter(f => f.is_default == true)[0].id)
      selectedFilters.value.push(filter_status.value.filter(f => f.token == data)[0].id)
    }
  } catch (err) {
    console.error(err)
  }
}

const getFilterClientType = async () => {
  error.value = null;
  try {
    const data = await $ConfiglistApiService.getAll('contract/contract-client-type');
    filter_client_type.value = data.results;
  } catch (err) {
    error.value = err;
  }
}

const getFilterCategory = async () => {
  error.value = null;
  try {
    const data = await $ConfiglistApiService.getAll('contract/contract-category');
    filter_category.value = data.results;
  } catch (err) {
    error.value = err;
  }
}

const getFilterUseType = async () => {
  error.value = null;
  try {
    const data = await $ConfiglistApiService.getAll('contract/contract-use-type');
    filter_use_type.value = data.results;
  } catch (err) {
    error.value = err;
  }
}

const handleHasInvoiceChange = (event) => {
  if (event && event.length > 0) has_invoice.value = event[0].id;
  else has_invoice.value = null;
  pagination.value.page = 1;
  handleSearch();
}

const handleClientTypeChange = (event) => {
  selected_client_types.value = event;
  client_types.value = []
  selected_client_types.value.forEach(element => {
    client_types.value.push(element.id);
  })
  pagination.value.page = 1;
  handleSearch();
}

const handleCategoryChange = (event) => {
  selected_categories.value = event;
  categories.value = []
  selected_categories.value.forEach(element => {
    categories.value.push(element.id);
  })
  pagination.value.page = 1;
  handleSearch();
}

const handleUseTypeChange = (event) => {
  selected_use_types.value = event;
  use_types.value = []
  selected_use_types.value.forEach(element => {
    use_types.value.push(element.id);
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
  if (isFilterShown.value.some(filter => filter.id === 'client_type') && !newFilters.some(filter => filter.id === 'client_type')) {
    client_types.value = [];
    selected_client_types.value = [];
    getData(searchInput.value, selectedFilters.value, pagination.value.page, sortBy.value, sortDesc.value);
  } else if (isFilterShown.value.some(filter => filter.id === 'category') && !newFilters.some(filter => filter.id === 'category')) {
    categories.value = [];
    selected_categories.value = [];
    getData(searchInput.value, selectedFilters.value, pagination.value.page, sortBy.value, sortDesc.value);
  } else if (isFilterShown.value.some(filter => filter.id === 'use_type') && !newFilters.some(filter => filter.id === 'use_type')) {
    use_types.value = [];
    selected_use_types.value = [];
    getData(searchInput.value, selectedFilters.value, pagination.value.page, sortBy.value, sortDesc.value);
  } else if (isFilterShown.value.some(filter => filter.id === 'no_invoice') && !newFilters.some(filter => filter.id === 'no_invoice')) {
    has_invoice.value = null;
    getData(searchInput.value, selectedFilters.value, pagination.value.page, sortBy.value, sortDesc.value);
  }
}

const handlePageChange = (newPage) => {
  pagination.value.page = newPage;
  getData(searchInput.value, selectedFilters.value, newPage, sortBy.value, sortDesc.value, true, searchByAddress.value);
}

const handleSort = (key) => {
  if (sortBy.value === key) {
    sortDesc.value = !sortDesc.value;
  } else {
    sortBy.value = key;
    sortDesc.value = false;
  }
  getData(searchInput.value, selectedFilters.value, pagination.value.page, sortBy.value, sortDesc.value);
}

const resetFilters = () => {
  searchInput.value = '';
  searchByAddress.value = '';
  pagination.value.page = 1;
  categories.value = [];
  selectedFilters.value = [];
  selected_categories.value = [];
  use_types.value = [];
  selected_use_types.value = [];
  client_types.value = [];
  selected_client_types.value = [];
  has_invoice.value = null;
  isFilterShown.value = [];
  isFilterOpen.value = false;
  showAddressSearch.value = false;
  selected_boolean.value = [];
  sortBy.value = 'created_at';
  sortDesc.value = true;
  getData('', [], 1, sortBy.value, sortDesc.value);
};

onMounted(async () => {
  await getPermissions();
  if (permissions.value?.can_view) {
    filtersExtra.value.push(
        { name: t("contract_block.client_type"), id: "client_type" },
        { name: t("contract_block.category"), id: "category" },
        { name: t("common.usage_type"), id: "use_type" },
        { name: t("common.no_invoice"), id: "no_invoice" },
      );
    filter_has_invoice.value = [{id: true, name: t("common.no_invoice")}, {id: false, name: t("common.has_invoice")}];
    await getFilterStatus();
    await getData('', selectedFilters.value, 1, sortBy.value, sortDesc.value);
    await getFilterClientType();
    await getFilterCategory();
    await getFilterUseType();
    checkRouteQuery()
  } else {
    pending.value = false;
    toast.error(t('common.no_permissions'));
    return navigateTo('/');
  }
})

const checkRouteQuery = () => {
  if (route.query?.id) {
    showDetail(route.query.id)
  }
}

const refresh = () => {
  getData(searchInput.value, selectedFilters.value, pagination.value.page, sortBy.value, sortDesc.value);
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
})

const handleSubRegionEvent = (event) => {
  isSubRegionOpen.value = event;
}

const handleRegionChange = (item) => {
  refresh();
}

const onClose = () => {
  showDetail(null);
  toggleRegion(false);
  refresh();
}

watch(() => route.query, () => {
  checkRouteQuery()
}, { immediate: true })
</script>

<template>
  <div id="wrapper" class="text-base">
    <div class="flex justify-between items-center mb-2">
      <H1 class="mb-2">{{ $t('contract_requests') }}</H1>
      <div class="flex items-center gap-2">
        <AtomsDownloadXlsxButton :rows="items" :columns="exportColumns" file-name="contract_requests"
          :total-pages="pagination.totalPages" :server-export-fn="exportContractRequests" :sheet-name="t('contract_requests')" />
        <NuxtLink v-if="permissions?.can_add" to="/contract/contract-requests/add" class="button-primary">{{ $t('contract_block.new_contract_request') }}</NuxtLink>
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

      <FilterSelect v-if="isFilterShown.some(filter => filter.id === 'client_type')" :options="filter_client_type"
        :filters="selected_client_types" :multiple="true" :placeholder="t(`contract_block.client_type`)"
        @update:modelValue="handleClientTypeChange($event)">
        <template #icon>
          <Icon name="fa6-solid:users" class="text-md ml-2 mr-1" size="10px" />
        </template>
      </FilterSelect>

      <FilterSelect v-if="isFilterShown.some(filter => filter.id === 'no_invoice')" :options="filter_has_invoice"
        :filters="selected_boolean" :multiple="true" :placeholder="t(`common.no_invoice`)"
        @update:modelValue="handleHasInvoiceChange($event)">
        <template #icon>
          <Icon name="fa6-solid:circle-check" class="text-md ml-2 mr-1" size="10px" />
        </template>
      </FilterSelect>

      <FilterSelect v-if="isFilterShown.some(filter => filter.id === 'category')" :options="filter_category"
        :filters="selected_categories" :multiple="true" :placeholder="t(`contract_block.category`)"
        @update:modelValue="handleCategoryChange($event)">
        <template #icon>
          <Icon name="fa6-solid:tag" class="text-md ml-2 mr-1" size="10px" />
        </template>
      </FilterSelect>

      <FilterSelect v-if="isFilterShown.some(filter => filter.id === 'use_type')" :options="filter_use_type"
        :filters="selected_use_types" :multiple="true" :placeholder="t(`common.usage_type`)"
        @update:modelValue="handleUseTypeChange($event)">
        <template #icon>
          <Icon name="fa6-solid:wrench" class="text-md ml-2 mr-1" size="10px" />
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
      grid-template="80px,150px,150px,150px,150px,150px,200px,150px"
      :pending="pending"
      :error="error"
      :is-empty="items.length === 0"
      @retry="getData">
      <template #header>
        <TableHeader :label="$t('common.creation')" sortKey="created_at" :currentSortBy="sortBy" :sortDesc="sortDesc"
          @sort="handleSort" />
        <TableHeader :label="$t('common.identification')" sortKey="token" :currentSortBy="sortBy" :sortDesc="sortDesc"
          @sort="handleSort" />
        <TableHeader :label="$t('common.requester')" :sortable="false" />
        <TableHeader :label="$t('common.usage_type')" :sortable="false" />
        <TableHeader :label="$t('common.short_supply')" :sortable="false" />
        <TableHeader :label="$t('meter')" :sortable="false" />
        <TableHeader :label="$t('address_block.address')" :sortable="false" />
        <TableHeader :label="$t('common.status')" sortKey="status" :currentSortBy="sortBy" :sortDesc="sortDesc"
          @sort="handleSort" />
      </template>

      <template #default="{ gridStyle }">
        <div v-for="item in items" :key="item.id"
          class="gap-3 text-base border-b items-center bg-white group"
          :style="gridStyle"
          :class="{ 'bg-yellow-50': item.id === selectedItemId }">
          <span class="p-1">{{ formatDate(item.created_at) }}</span>
          <span>
            <button class="group flex justify-between w-full items-center p-1 text-sky-500 text-nowrap text-left"
              @click="showDetail(item.id);">
              <abbr :title="item.id" class="no-underline">{{ item.token }}</abbr>
              <Icon name="fa6-solid:eye"
                class="opacity-0 group-hover:opacity-100 text-slate-500 mr-1 transition-opacity duration-200 ease-in-out" />
            </button>
          </span>
          <span class="p-1"><abbr :title=item.person_token>{{ item.person_name }} {{ item.person_surname
              }}</abbr></span>
          <span class="p-1">{{ item.type_name }}</span>
          <span class="p-1">{{ item.supply_point_default_token }}</span>
          <span class="p-1">{{ item.meters }}</span>
          <span class="p-1">{{ item.supply_point }}</span>
          <span class="p-1">
            <AtomsColorBadge :value="item.status_name || item.status_token" :color="item.status_color">
            </AtomsColorBadge>
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
      <ContractRequestRegion v-if="detail" :id="detail" :isSubRegionOpen="isSubRegionOpen" @changed="handleRegionChange"
        @close="onClose" @show-subregion="handleSubRegionEvent" @close-subregion="toggleRegion(false)" />
    </div>
  </div>

</template>
