<script setup>
import { ref, onMounted, nextTick, computed, watch } from 'vue';
import { useRouter } from 'vue-router';
import debounce from 'lodash.debounce';
import { useI18n } from 'vue-i18n';
import { formatDate } from '~/utils/date';
import FilterSelect from '~/components/atoms/FilterSelect.vue';
import Pagination from '~/components/molecules/Pagination.vue';
import H1 from '~/components/atoms/H1.vue';
import OrderRegion from '~/components/organisms/OrderRegion.vue';
import TableHeader from '~/components/atoms/TableHeader.vue';
import { useToast } from 'vue-toastification';
import AppLoading from '~/components/atoms/AppLoading.vue';
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
const { $OrderApiService, $ConfiglistApiService, $ConnectionApiService, $UserApiService } = useNuxtApp();
const connectionAddresses = ref({});
const related_contract_token = ref('');
const creator = ref(null);
const pending = ref(true);
const error = ref(null);
const items = ref([]);
const searchInput = ref('');
const searchAllAddressInput = ref('');
const searchByAddress = ref('');
const filter_status = ref([]);
const selectedFilters = ref([]);
const sortBy = ref(null);
const sortDesc = ref(false);

const isFilterOpen = ref(false);
const showAddressSearch = ref(false);
const isFilterShown = ref([]);
const filtersExtra = ref([]);

const permissions = ref(null);

const filter_type = ref([]);
const selected_types = ref([]);
const types = ref([]);
const filter_creator = ref([]);
const selected_creators = ref([]);
const creators = ref([]);
const filter_city = ref([]);
const selected_cities = ref([]);
const cities = ref([]);
const statuses = ref([]);
const isInitialLoad = ref(true);

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
    const data = await $OrderApiService.getPermissions();
    permissions.value = data;
  } catch (err) {
    error.value = err;
  }
}

const getData = async (searchQuery = '', filters = [], page = 1, sort = null, desc = false, searchAllAddress = '', searchByAddressQuery = '') => {
  if (!permissions.value?.can_view) {
    toast.error(t('common.no_permissions'));
    return navigateTo('/');
  }
  pending.value = true;
  error.value = null;

  try {
    const data = await $OrderApiService.getAll(searchQuery, filters, page, sort, desc, null, types.value, null, null, null, null, searchAllAddress, searchByAddressQuery, related_contract_token.value, creators.value, cities.value);

    items.value = data.results;
    updateFilterCities();
    // muntem la paginacio
    Object.assign(pagination.value, {
      total: data.count,
      totalPages: Math.ceil(data.count / pagination.value.perPage),
      previous: data.previous,
      next: data.next,
      isFiltered: String(searchQuery).trim() !== '' || String(searchAllAddress).trim() !== '' || String(searchByAddressQuery).trim() !== ''
    });

    // Check for items that need connection address lookup
    items.value.forEach(item => {
      if (!item.supply_point?.address_complete && !item.address?.address_complete && item.connection?.id && !item.connection?.address_complete) {
        fetchConnectionAddress(item.connection.id);
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
    const data = await $OrderApiService.getFilterStatus();
    filter_status.value = data;
  } catch (err) {
    error.value = err;
  }
}

const getFilterType = async () => {
  error.value = null;
  try {
    const data = await $ConfiglistApiService.getAll('order/order-type');
    filter_type.value = data.results;
  } catch (err) {
    error.value = err;
  }
}

const getFilterCreator = async () => {
  error.value = null;
  try {
    const data = await $UserApiService.getAll();
    filter_creator.value = data.results.map(user => ({
      id: user.id,
      name: user.first_name && user.last_name ? `${user.first_name} ${user.last_name}` : user.username
    }));
  } catch (err) {
    error.value = err;
  }
}

const getFilterCity = async () => {
  error.value = null;
  try {
    const data = await $OrderApiService.getFilterCities();
    filter_city.value = data
      .map(city => ({ id: city.id, name: city.name }))
      .sort((a, b) => (a.name || '').localeCompare(b.name || ''));
  } catch (err) {
    error.value = err;
  }
}

const handleFiltersSelectChange = (event) => {
  let newFilters = event
    .filter(el => !isFilterShown.value.includes(el.id));

  checkInAdvacedFilters(newFilters)
  isFilterShown.value = [];
  isFilterShown.value = [...isFilterShown.value, ...newFilters];
}

const checkInAdvacedFilters = (newFilters) => {
  if (isFilterShown.value.some(filter => filter.id === 'type') && !newFilters.some(filter => filter.id === 'type')) {
    types.value = [];
    selected_types.value = [];
    getData();
  }
  if (isFilterShown.value.some(filter => filter.id === 'contract_filter') && !newFilters.some(filter => filter.id === 'contract_filter')) {
    related_contract_token.value = '';
    getData();
  }
  if (isFilterShown.value.some(filter => filter.id === 'creator') && !newFilters.some(filter => filter.id === 'creator')) {
    creators.value = [];
    selected_creators.value = [];
    getData();
  }
  if (isFilterShown.value.some(filter => filter.id === 'municipality') && !newFilters.some(filter => filter.id === 'municipality')) {
    cities.value = [];
    selected_cities.value = [];
    getData();
  }
}

const handleFilterTypeChange = (event) => {
  selected_types.value = event;
  types.value = [];
  selected_types.value.forEach(element => {
    types.value.push(element.id);
  })
  pagination.value.page = 1;
  handleSearch();
}

const handleFilterCreatorChange = (event) => {
  selected_creators.value = event;
  creators.value = [];
  selected_creators.value.forEach(element => {
    creators.value.push(element.id);
  })
  pagination.value.page = 1;
  handleSearch();
}

const handleFilterCityChange = (event) => {
  selected_cities.value = event;
  cities.value = [];
  selected_cities.value.forEach(element => {
    cities.value.push(element.id);
  })
  pagination.value.page = 1;
  handleSearch();
}

const handleContractTokenChange = () => {
  pagination.value.page = 1;
  handleSearch();
}

const fetchConnectionAddress = async (connectionId) => {
  if (connectionAddresses.value[connectionId]) return;

  try {
    const data = await $ConnectionApiService.getDetail(connectionId);
    if (data?.address_complete) {
      connectionAddresses.value[connectionId] = data.address_complete;
    }
  } catch (err) {
    console.error(`Error loading address for connection ${connectionId}:`, err);
  }
}

const debouncedGetData = debounce((query, filters, sort, desc, searchAllAddress = '', searchByAddressQuery = '') => {
  getData(query, filters, pagination.value.page, sort, desc, searchAllAddress, searchByAddressQuery);
}, 300);

const handleSearch = () => {
  pagination.value.page = 1;
  debouncedGetData(searchInput.value, statuses.value, sortBy.value, sortDesc.value, searchAllAddressInput.value, searchByAddress.value);
}

const handleAddressChange = (addressString) => {
  searchByAddress.value = addressString;
  pagination.value.page = 1;
  debouncedGetData(searchInput.value, statuses.value, sortBy.value, sortDesc.value, searchAllAddressInput.value, addressString);
}

const toggleAddressFilter = () => {
  // If we are hiding the address search and there are no extra filters, close the whole extra filters area
  if (showAddressSearch.value) {
    showAddressSearch.value = false;
    if (!isFilterShown.value.length) {
      isFilterOpen.value = false;
      return;
    }
  } else {
    // Show address search and ensure filters area is open
    showAddressSearch.value = true;
    isFilterOpen.value = true;
  }
}

const handleFilterChange = () => {
  pagination.value.page = 1;
  handleSearch();
}

const handleStatusChange = (event) => {
  selectedFilters.value = event;
  statuses.value = []
  selectedFilters.value.forEach(element => {
    statuses.value.push(element.id);
  })
  pagination.value.page = 1;
  handleSearch();
}

const handlePageChange = (newPage) => {
  pagination.value.page = newPage;
  getData(searchInput.value, statuses.value, newPage, sortBy.value, sortDesc.value, searchAllAddressInput.value, searchByAddress.value);
}

const handleSort = (key) => {
  if (sortBy.value === key) {
    sortDesc.value = !sortDesc.value;
  } else {
    sortBy.value = key;
    sortDesc.value = false;
  }
  getData(searchInput.value, statuses.value, pagination.value.page, sortBy.value, sortDesc.value, searchAllAddressInput.value, searchByAddress.value);
}

const exportColumns = computed(() => [
  { header: t('common.creation_date'), value: (row) => formatDate(row.created_at), key: 'created_at' },
  { header: t('common.identification'), value: (row) => row.token, key: 'token' },
  { header: t('common.type'), value: (row) => row.type?.name, key: 'type' },
  { header: t('order_block.reason'), value: (row) => row.reason?.name, key: 'reason' },
  { header: t('common.creator'), value: (row) => (row.created_by?.first_name && row.created_by?.last_name) ? `${row.created_by.first_name} ${row.created_by.last_name}` : (row.created_by?.username || '') },
  { header: `${t('contract')} / ${t('contract_block.short_contract_request')}`, value: (row) => row.related_contract_token || '', key: 'related_contract_token' },
  { header: t('common.status'), value: (row) => row.status?.name || row.status?.token, key: 'status' },
  { header: t('order_block.scheduled_date'), value: (row) => row.dueDateAt ? formatDate(row.dueDateAt) : '', key: 'dueDateAt' },
  { header: t('common.operators'), value: (row) => (row.operators || []).map(o => (o?.name && o?.surname) ? `${o.name} ${o.surname}` : o?.token).join(', ') },
  { header: t('common.completion'), value: (row) => row.completed_at ? formatDate(row.completed_at) : '', key: 'completed_at' },
  { header: t('common.priority'), value: (row) => row.priority?.name || '', key: 'priority' },
]);

const exportOrders = (columns) => $OrderApiService.exportData(
  searchInput.value, statuses.value, sortBy.value, sortDesc.value,
  null, types.value, null, null, null, null,
  searchAllAddressInput.value, searchByAddress.value, related_contract_token.value, creators.value, cities.value,
  undefined, columns,
);

const resetFilters = () => {
  searchInput.value = '';
  searchAllAddressInput.value = '';
  searchByAddress.value = '';
  selectedFilters.value = [];
  pagination.value.page = 1;
  selected_types.value = [];
  types.value = [];
  related_contract_token.value = '';
  isFilterShown.value = [];
  isFilterOpen.value = false;
  showAddressSearch.value = false;
  selected_creators.value = [];
  creators.value = [];
  selected_cities.value = [];
  cities.value = [];
  getData();
};

const onChangeRegion = (event) => {
  getData(searchInput.value, statuses.value, pagination.value.page, sortBy.value, sortDesc.value, searchAllAddressInput.value, searchByAddress.value);
}

const updateFilterCities = () => {
  // Ensure currently selected cities are not lost from the dropdown options
  // even if they are not part of the full municipality list returned by the API.
  selected_cities.value.forEach(city => {
    if (city && city.id && city.name && !filter_city.value.some(c => c.id === city.id)) {
      filter_city.value.push({ id: city.id, name: city.name });
      filter_city.value.sort((a, b) => (a.name || '').localeCompare(b.name || ''));
    }
  });
};

const STORAGE_KEY = 'ordersSearchState';

const saveSearchState = () => {
  const state = {
    searchInput: searchInput.value,
    searchAllAddressInput: searchAllAddressInput.value,
    searchByAddress: searchByAddress.value,
    selectedFilters: selectedFilters.value,
    statuses: statuses.value,

    types: types.value,
    selected_types: selected_types.value,

    creators: creators.value,
    selected_creators: selected_creators.value,

    cities: cities.value,
    selected_cities: selected_cities.value,

    related_contract_token: related_contract_token.value,

    sortBy: sortBy.value,
    sortDesc: sortDesc.value,
    isFilterOpen: isFilterOpen.value,
    showAddressSearch: showAddressSearch.value,
    isFilterShown: isFilterShown.value,
    page: pagination.value.page
  };
  sessionStorage.setItem(STORAGE_KEY, JSON.stringify(state));
};

const loadSearchState = () => {
  const state = sessionStorage.getItem(STORAGE_KEY);
  if (state) {
    try {
      const parsed = JSON.parse(state);
      if (parsed.searchInput !== undefined) searchInput.value = parsed.searchInput;
      if (parsed.searchAllAddressInput !== undefined) searchAllAddressInput.value = parsed.searchAllAddressInput;
      if (parsed.searchByAddress !== undefined) searchByAddress.value = parsed.searchByAddress;
      if (parsed.selectedFilters !== undefined) selectedFilters.value = parsed.selectedFilters;
      if (parsed.statuses !== undefined) statuses.value = parsed.statuses;

      if (parsed.types !== undefined) types.value = parsed.types;
      if (parsed.selected_types !== undefined) selected_types.value = parsed.selected_types;

      if (parsed.creators !== undefined) creators.value = parsed.creators;
      if (parsed.selected_creators !== undefined) selected_creators.value = parsed.selected_creators;

      if (parsed.cities !== undefined) cities.value = parsed.cities;
      if (parsed.selected_cities !== undefined) selected_cities.value = parsed.selected_cities;

      if (parsed.related_contract_token !== undefined) related_contract_token.value = parsed.related_contract_token;

      if (parsed.sortBy !== undefined) sortBy.value = parsed.sortBy;
      if (parsed.sortDesc !== undefined) sortDesc.value = parsed.sortDesc;
      if (parsed.isFilterOpen !== undefined) isFilterOpen.value = parsed.isFilterOpen;
      if (parsed.showAddressSearch !== undefined) showAddressSearch.value = parsed.showAddressSearch;
      if (parsed.isFilterShown !== undefined) isFilterShown.value = parsed.isFilterShown;

      if (parsed.page !== undefined) pagination.value.page = parsed.page;
    } catch (e) {
      console.error('Error parsing search state', e);
    }
  }
};

onMounted(async () => {
  await getPermissions();
  if (!permissions.value?.can_view) {
    toast.error(t('common.no_permissions'));
    return navigateTo('/');
  }
  filtersExtra.value.push(
    { name: t('common.type'), id: "type" },
    { name: t('contract') + ' / ' + t('contract_block.short_contract_request'), id: "contract_filter" },
    { name: t('common.creator'), id: "creator" },
    { name: t('address_block.municipality'), id: "municipality" }
  );

  await Promise.all([
    getFilterStatus(),
    getFilterType(),
    getFilterCreator(),
    getFilterCity()
  ]);

  // 1. Fetch unfiltered orders first to populate the list of municipalities (cities)
  await getData('', [], 1, sortBy.value, sortDesc.value, '', '');

  // 2. Load the saved search state
  loadSearchState();

  // 3. If there are any active filters/searches in the saved state, load the filtered data
  const hasActiveFilters =
    searchInput.value !== '' ||
    searchAllAddressInput.value !== '' ||
    searchByAddress.value !== '' ||
    selectedFilters.value.length > 0 ||
    types.value.length > 0 ||
    creators.value.length > 0 ||
    cities.value.length > 0 ||
    related_contract_token.value !== '' ||
    pagination.value.page !== 1;

  if (hasActiveFilters) {
    await getData(searchInput.value, statuses.value, pagination.value.page, sortBy.value, sortDesc.value, searchAllAddressInput.value, searchByAddress.value);
  }

  checkRouteQuery();

  // 4. Wait for nextTick to flush all watch updates before marking initial load as finished
  await nextTick();
  isInitialLoad.value = false;
});

const checkRouteQuery = () => {
  if (route.query?.id) {
    showDetail(route.query.id)
  }
}

const showDetail = async (id) => {
  await toggleRegion(false);
  detail.value = id;
  selectedItemId.value = id;
  toggleRegion(true);
}

// Watch for changes in searchInput and selectedFilters and reset pagination to 1
watch([searchInput, selectedFilters, searchAllAddressInput, related_contract_token, creators, cities], () => {
  if (isInitialLoad.value) return;
  pagination.value.page = 1;
  handleSearch();
});

// Watch for changes and save state
watch(
  () => [
    searchInput.value,
    searchAllAddressInput.value,
    searchByAddress.value,
    selectedFilters.value,
    statuses.value,
    types.value,
    selected_types.value,
    creators.value,
    selected_creators.value,
    cities.value,
    selected_cities.value,
    related_contract_token.value,
    sortBy.value,
    sortDesc.value,
    isFilterOpen.value,
    showAddressSearch.value,
    isFilterShown.value,
    pagination.value.page
  ],
  () => {
    saveSearchState();
  },
  { deep: true }
);

const handleSubRegionEvent = (event) => {
  isSubRegionOpen.value = event;
}

// Helper function to get related badges
const getRelatedBadges = (item) => {
  const badges = [];

  // Supply point: mostrar token (l'adreça ja va a la seva columna)
  if (item.supply_point?.token) {
    badges.push({ text: `${t('common.supply')} ${item.supply_point.token}`, type: 'supply' });
  }

  // Contract termination request
  if (item.contract_termination_request_token) {
    badges.push({ text: `${t('common.contract_termination_detail')}: ${item.contract_termination_request_token}`, type: 'termination' });
  }

  // Connection: mostrar token (l'adreça ja va a la seva columna)
  if (item.connection?.token) {
    badges.push({ text: `${t('common.connection')}: ${item.connection.token}`, type: 'connection' });
  }

  console.log(item);
  if (item.address?.address_complete) {
    badges.push({ text: `${t('common.address')}: ${item.address.address_complete}`, type: 'address' });
  }

  return badges;
}

const getAddress = (item) => {
  // Si hi ha punt de subministrament, l'adreça és allà. 
  // Si no, mirem si l'ordre és d'una escomesa o té una adreça assignada directament.
  if (item.supply_point?.address_complete) return item.supply_point.address_complete;
  if (item.connection?.address_complete) return item.connection.address_complete;
  if (item.address?.address_complete) return item.address.address_complete;

  // Si no ho hem trobat a l'objecte original però tenim l'adreça carregada asíncronament
  if (item.connection?.id && connectionAddresses.value[item.connection.id]) {
    return connectionAddresses.value[item.connection.id];
  }

  return '-';
}
watch(() => route.query, () => {
  checkRouteQuery()
}, { immediate: true })
</script>

<template>
  <div id="wrapper" class="text-base">
    <div class="flex justify-between items-center gap-2 mb-2">
      <H1 class="mb-0">{{ $t('common.orders') }}</H1>
      <div class="flex items-center gap-2">
        <AtomsDownloadXlsxButton :rows="items" :columns="exportColumns" file-name="orders"
          :total-pages="pagination.totalPages" :server-export-fn="exportOrders" />
        <NuxtLink v-if="permissions?.can_change" to="/order/orders/add"
          class="button-primary text-sm sm:text-base whitespace-nowrap">{{ $t('order_block.short_new_order') }}</NuxtLink>
      </div>
    </div>
    <form id="form_filter" role="search"
      class="mb-3 text-base border-b border-gray-400 flex flex-col md:flex-row flex-start gap-2 md:gap-4 justify-start items-start md:items-center"
      @submit.prevent="handleSearch">

      <span class="input-group flex flex-start items-center gap-2 w-full md:w-80">
        <Icon name="fa6-solid:magnifying-glass" class="text-slate-500" />
        <input v-model="searchInput" @input="handleSearch" id="searchInput" type="text" name="search"
          :placeholder="$t('dashboard.search')" class="w-full p-1 rounded-md focus:outline-none focus-visible:border-0"
          autocomplete="off" />
      </span>

      <div class="hidden md:block h-8 w-px bg-gray-300"></div>

      <span class="input-group flex flex-start items-center gap-2 w-full md:w-60">
        <Icon name="fa6-solid:house" class="text-slate-500" />
        <input v-model="searchAllAddressInput" @input="handleSearch" id="searchAllAddressInput" type="text"
          name="search" :placeholder="$t('contract_block.search_address_info')"
          class="w-full p-1 rounded-md focus:outline-none focus-visible:border-0 " autocomplete="off" />
      </span>

      <div class="hidden md:block h-8 w-px bg-gray-300"></div>

      <!-- <span class="flex flex-wrap gap-2 md:gap-3 w-full md:w-auto" v-if="filter_status.length">
        <label v-for="status in filter_status" :key="status.id"
          class="text-slate-800 text-sm md:text-base flex items-center gap-1">
          <input type="checkbox" v-model="selectedFilters" :value="status.id" @change="handleFilterChange" /> {{
            status?.name }}
        </label>
      </span> -->

      <FilterSelect :plain="true" :options="filter_status" :filters="selectedFilters" :multiple="true"
        :placeholder="t(`common.statuses`)" @update:modelValue="handleStatusChange($event)">
        <template #icon>
          <Icon name="fa6-solid:ruler-combined" class="text-md ml-2 mr-1" size="10px" />
        </template>
      </FilterSelect>

      <span class="flex gap-2">
        <button id="filterShow" name="form_filter" type="button" class="px-2 py-1 hover:bg-slate-300 rounded"
          @click="isFilterOpen = !isFilterOpen" title="show">
          <Icon name="fa:filter" class="text-slate-500" />
        </button>

        <button id="filterAddress" name="form_filter" type="button" class="px-2 py-1 hover:bg-slate-300 rounded"
          :class="{ 'bg-slate-300': showAddressSearch }" @click="toggleAddressFilter"
          :title="$t('address_block.address')">
          <span class="text-slate-500">
            <Icon name="fa6-solid:house" />+
          </span>
        </button>

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

      <FilterSelect v-if="isFilterShown.some(filter => filter.id === 'type')" :options="filter_type"
        :filters="selected_types" :multiple="true" :placeholder="t(`common.type`)"
        @update:modelValue="handleFilterTypeChange($event)">
        <template #icon>
          <Icon name="fa6-solid:circle-check" class="text-md ml-2 mr-1" size="10px" />
        </template>
      </FilterSelect>

      <FilterSelect v-if="isFilterShown.some(filter => filter.id === 'creator')" :options="filter_creator"
        :filters="selected_creators" :multiple="true" :placeholder="t(`common.creator`)"
        @update:modelValue="handleFilterCreatorChange($event)">
        <template #icon>
          <Icon name="fa6-solid:user" class="text-md ml-2 mr-1" size="10px" />
        </template>
      </FilterSelect>

      <FilterSelect v-if="isFilterShown.some(filter => filter.id === 'municipality')" :options="filter_city"
        :filters="selected_cities" :multiple="true" :placeholder="t(`address_block.municipality`)"
        @update:modelValue="handleFilterCityChange($event)">
        <template #icon>
          <Icon name="fa6-solid:location-dot" class="text-md ml-2 mr-1" size="10px" />
        </template>
      </FilterSelect>


      <FilterSelect :options="filtersExtra" :filters="isFilterShown" :multiple="true" :selector="true"
        :placeholder="$t('common.additional_filters')" @update:modelValue="handleFiltersSelectChange($event)">
        <template #icon>
          <Icon name="fa6-solid:plus" class="text-md ml-2 mr-1" size="10px" />
        </template>
      </FilterSelect>

      <div v-if="isFilterShown.some(filter => filter.id === 'contract_filter')"
        class="flex flex-col md:flex-row gap-2 w-full md:w-auto">
        <span
          class="input-group flex items-center gap-2 px-2 py-1 bg-white rounded border border-slate-300 w-full md:w-64">
          <Icon name="fa6-solid:file-contract" class="text-slate-500" />
          <input v-model="related_contract_token" @input="handleContractTokenChange" type="text"
            :placeholder="t('contract') + ' / ' + t('contract_block.short_contract_request')"
            class="w-full focus:outline-none bg-transparent" />
          <button v-if="related_contract_token" @click="related_contract_token = ''; handleSearch()"
            class="text-slate-400 hover:text-red-500">
            <Icon name="fa6-solid:xmark" size="12px" />
          </button>
        </span>
      </div>

    </div>

    <!-- Mobile Card View -->
    <div class="md:hidden flex flex-col overflow-hidden" :style="{
      minHeight: isFilterOpen ? 'calc(100vh - 263px)' : 'calc(100vh - 230px)',
      maxHeight: isFilterOpen ? 'calc(100vh - 263px)' : 'calc(100vh - 230px)',
    }">
      <div class="flex-1 min-h-0 overflow-y-auto">
        <div v-if="pending">
          <AppLoading :text="$t('common.loading')" />
        </div>
        <div v-else-if="error">
          <p>Error: {{ error.message }}</p>
          <p><button @click="getData" class="underline text-sky-500 hover:no-underline">{{ $t('common.load_again')
              }}</button></p>
        </div>
        <div v-else>
          <div v-for="item in items" :key="item.id"
            class="p-3 mb-2 border-b bg-white rounded shadow-sm cursor-pointer hover:bg-slate-50 active:bg-slate-100 transition-colors"
            :class="{ 'bg-yellow-50': item.id === selectedItemId }" @click="showDetail(item.id)">
            <div class="flex flex-col gap-2">
              <!-- Header row: Token and Status -->
              <div class="flex justify-between items-center">
                <span class="text-sky-500 font-semibold">
                  <abbr :title="item.id" class="no-underline">{{ item.token }}</abbr>
                </span>
                <AtomsColorBadge :value="item.status?.name || item.status?.token" :color="item.status?.color" />
              </div>

              <div class="flex flex-wrap gap-1 text-sm" v-if="item.related_contract_token">
                <span class="text-slate-600">
                  {{ item.related_contract_token }}
                </span>
              </div>

              <div class="flex flex-wrap gap-x-3 gap-y-1 text-sm">
                <span>{{ formatDate(item.created_at) }}</span>
                <span>{{ item.type?.name }}</span>
                <span v-if="item.reason?.name">{{ item.reason.name }}</span>
                <span class="text-slate-500 italic">{{ getAddress(item) }}</span>
                <span v-if="item.created_by" class="text-xs text-slate-400">({{ t('common.creator') }}: {{
                  item.created_by.first_name && item.created_by.last_name ? `${item.created_by.first_name}
                  ${item.created_by.last_name}` : item.created_by.username }})</span>
              </div>

              <!-- Dates and Operators row -->
              <div class="flex flex-wrap gap-x-3 gap-y-1 text-sm text-gray-600">
                <span v-if="item.dueDateAt">{{ formatDate(item.dueDateAt) }}</span>
                <span v-if="item.completed_at">{{ formatDate(item.completed_at) }}</span>
                <span v-if="item.priority">
                  <AtomsColorBadge :value="item.priority?.name" :color="item.priority?.color" />
                </span>
              </div>

              <!-- Operators row -->
              <div class="flex flex-wrap gap-1" v-if="item.operators && item.operators.length > 0">
                <AtomsColorBadge v-for="operator in item.operators" :key="operator.id"
                  :value="operator?.name && operator?.surname ? `${operator.name} ${operator.surname}` : operator?.token"
                  color="blue" class="text-xs" />
              </div>

              <!-- Related items row (badges) -->
              <div class="flex flex-wrap gap-1" v-if="getRelatedBadges(item).length > 0">
                <template v-for="badge in getRelatedBadges(item)" :key="badge.type">
                  <span class="inline-flex items-center px-2 py-1 rounded text-xs bg-gray-100 text-gray-700">
                    {{ badge.text }}
                  </span>
                </template>
              </div>
            </div>
          </div>

          <div v-if="items.length === 0" class="my-3">
            <p class="text-">{{ $t('common.no_records') }}</p>
          </div>
        </div>
      </div>
    </div>

    <!-- Desktop Grid View -->
    <div class="hidden md:flex md:flex-col md:overflow-x-auto">
      <DataTable
        grid-template="80px,180px,120px,100px,180px,120px,160px,80px,100px,120px,120px,100px,140px"
        :pending="pending"
        :error="error"
        :is-empty="items.length === 0"
        @retry="getData">
        <template #header>
          <TableHeader :label="$t('common.creation_date')" sortKey="created_at" :currentSortBy="sortBy"
            :sortDesc="sortDesc" @sort="handleSort" />
          <TableHeader :label="$t('common.identification')" sortKey="token" :currentSortBy="sortBy" :sortDesc="sortDesc"
            @sort="handleSort" />
          <TableHeader :label="$t('common.type')" sortKey="type" :currentSortBy="sortBy" :sortDesc="sortDesc"
            @sort="handleSort" />
          <TableHeader :label="$t('order_block.reason')" sortKey="type" :currentSortBy="sortBy" :sortDesc="sortDesc"
            @sort="handleSort" />
          <div class="p-1 text-base font-semibold">{{ $t('common.address') }}</div>
          <TableHeader :label="$t('common.creator')" sortKey="created_by__username" :currentSortBy="sortBy"
            :sortDesc="sortDesc" @sort="handleSort" />
          <TableHeader :label="`${$t('contract')} / ${$t('contract_block.short_contract_request')}`"
            sortKey="related_contract_token" :currentSortBy="sortBy" :sortDesc="sortDesc" @sort="handleSort" />
          <TableHeader :label="$t('common.status')" sortKey="status" :currentSortBy="sortBy" :sortDesc="sortDesc"
            @sort="handleSort" />
          <TableHeader :label="$t('order_block.scheduled_date')" sortKey="dueDateAt" :currentSortBy="sortBy"
            :sortDesc="sortDesc" @sort="handleSort" />
          <TableHeader :label="$t('common.operators')" sortKey="operators" :currentSortBy="sortBy" :sortDesc="sortDesc"
            @sort="handleSort" />
          <TableHeader :label="$t('common.completion')" sortKey="completed_at" :currentSortBy="sortBy"
            :sortDesc="sortDesc" @sort="handleSort" />
          <TableHeader :label="$t('common.priority')" sortKey="priority__token" :currentSortBy="sortBy"
            :sortDesc="sortDesc" @sort="handleSort" />
          <div class="p-1 text-base font-semibold">{{ $t('common.related') }}</div>
        </template>

        <template #default="{ gridStyle }">
          <div v-for="item in items" :key="`desktop-${item.id}`"
            class="gap-3 text-base border-b items-center bg-white"
            :style="gridStyle"
            :class="{ 'bg-yellow-50': item.id === selectedItemId }">
            <span class="p-1 text-nowrap">{{ formatDate(item.created_at) }}</span>
            <span>
              <button class="group flex justify-between w-full items-center p-1 text-sky-500 text-nowrap text-left"
                @click="showDetail(item.id);">
                <abbr :title="item.id" class="no-underline">{{ item.token }}</abbr>
              </button>
            </span>
            <span class="p-1">{{ item.type?.name }}</span>
            <span class="p-1">{{ item.reason?.name }}</span>
            <span class="p-1 overflow-hidden text-ellipsis whitespace-nowrap" :title="getAddress(item)">{{
              getAddress(item) }}</span>
            <span class="p-1 truncate"
              :title="item.created_by?.first_name && item.created_by?.last_name ? `${item.created_by.first_name} ${item.created_by.last_name}` : item.created_by?.username">
              {{ item.created_by?.first_name && item.created_by?.last_name ? `${item.created_by.first_name}
              ${item.created_by.last_name}` : item.created_by?.username || '-' }}
            </span>
            <div class="p-1 flex flex-col overflow-hidden">
              <template v-if="item.related_contract_token">
                <div class="font-semibold truncate">{{ item.related_contract_token }}</div>
                <div class="text-xs text-gray-500 truncate"
                  v-if="item.contract?.holder || item.supply_point?.contracts?.[0]?.holder">
                  {{ item.contract?.holder || item.supply_point?.contracts?.[0]?.holder }}
                </div>
              </template>
              <span v-else class="text-gray-400">-</span>
            </div>
            <span class="p-1 text-nowrap">
              <AtomsColorBadge :value="item.status?.name || item.status?.token" :color="item.status?.color" />
            </span>
            <span class="p-1 text-nowrap" v-if="item.dueDateAt">{{ formatDate(item.dueDateAt) }}</span>
            <span class="p-1 text-nowrap" v-else>{{ '-' }}</span>
            <!-- Operators column -->
            <span class="p-1 flex flex-wrap gap-1">
              <AtomsColorBadge v-for="operator in item.operators" :key="operator.id"
                :value="operator?.name && operator?.surname ? `${operator.name} ${operator.surname}` : operator?.token"
                color="blue" class="text-xs" />
              <span v-if="!item.operators || item.operators.length === 0" class="text-gray-400">-</span>
            </span>
            <span class="p-1 text-nowrap" v-if="item.completed_at">{{ formatDate(item.completed_at) }}</span>
            <span class="p-1 text-nowrap" v-else>{{ '-' }}</span>
            <span class="p-1 text-nowrap" v-if="item.priority">
              <AtomsColorBadge :value="item.priority?.name" :color="item.priority?.color" />
            </span>
            <span class="p-1 text-nowrap" v-else>{{ '-' }}</span>
            <!-- Consolidated related items column -->
            <span class="p-1 flex flex-wrap gap-1">
              <template v-for="badge in getRelatedBadges(item)" :key="badge.type">
                <span class="inline-flex items-center px-2 py-1 rounded text-xs bg-gray-100 text-gray-700">
                  {{ badge.text }}
                </span>
              </template>
              <span v-if="getRelatedBadges(item).length === 0" class="text-gray-400">-</span>
            </span>
          </div><!-- end for items -->
        </template>
      </DataTable>
    </div><!-- end desktop grid view -->
    <div id="list__footer">
      <Pagination v-if="items.length > 0" :pagination="pagination" @update:page="handlePageChange" />
    </div>
  </div><!-- end wrapper -->

  <!-- Overlay for mobile -->
  <div v-if="showRegion" class="fixed inset-0 bg-black bg-opacity-50 z-40 md:hidden transition-opacity duration-500"
    @click="toggleRegion(false)">
  </div>

  <div role="region" id="right_page"
    class="fixed h-full top-0 transition-all duration-500 ease py-2 text-base bg-white z-50 overflow-y-auto" :class="{
      'left-0 md:right-0 md:left-auto': true,
      'border-l-0 md:border-l md:border-gray-100': true,
      'translate-x-0': showRegion,
      '-translate-x-full md:translate-x-[2000px]': !showRegion,
      'w-screen max-w-full md:w-[95%]': isSubRegionOpen,
      'w-screen max-w-full md:w-1/2': !isSubRegionOpen
    }" style="max-width: 100vw;">
    <div id="region_nav"
      class="md:hidden mb-3 px-3 md:px-3 flex items-center justify-end border-b border-gray-200 pb-2">
      <button @click="toggleRegion(false)"
        class="px-3 py-2 text-sky-500 hover:bg-slate-200 active:bg-slate-300 rounded-md flex items-center gap-2">
        <Icon name="fa6-solid:xmark" class="text-slate-500 md:hidden text-xl" />
        <span class="md:hidden font-medium">{{ $t('common.close') }}</span>
      </button>
    </div>
    <div id="region_nav" class="mb-3 px-3">
      <button @click="toggleRegion(false)"
        class="px-3 py-2 text-sky-500 hover:bg-slate-200 active:bg-slate-300 rounded-md flex items-center gap-2">
        <Icon name="fa6-solid:angles-right" class="text-slate-500 hidden md:block justify-start" />
      </button>
    </div>
    <div class="pl-10 h-full">
      <OrderRegion v-if="detail" :id="detail" :isSubRegionOpen="isSubRegionOpen" @show-subregion="handleSubRegionEvent"
        @changed="onChangeRegion" @close-subregion="toggleRegion(false)" />
    </div>
  </div>

</template>
