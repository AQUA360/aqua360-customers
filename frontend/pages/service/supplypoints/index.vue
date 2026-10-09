<script setup>
import { ref, onMounted, nextTick, computed, watch } from 'vue';
import { useRouter } from 'vue-router';
import debounce from 'lodash.debounce';
import { useToast } from 'vue-toastification';
import Pagination from '~/components/molecules/Pagination.vue';
import H1 from '~/components/atoms/H1.vue';
import SupplyPointRegion from '~/components/organisms/SupplyPointRegion.vue';
import FilterSelect from '~/components/atoms/FilterSelect.vue';
import DataTable from '~/components/organisms/DataTable.vue';

const showRegion = ref(false);
const supplyPointRegion = ref(null);
const selectedItemId = ref(null);

const { t } = useI18n();
const toast = useToast();
const isSubRegionOpen = ref(false);
const toggleRegion = (force, isReload = false) => {
  showRegion.value = force !== undefined ? force : !showRegion.value;
  if (showRegion.value == false) {
    isSubRegionOpen.value = false;
    supplyPointRegion.value = null
    selectedItemId.value = null
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

const router = useRouter();
const route = useRoute()
const { $SupplyPointApiService, $ClusterNozzleApiService, $ConfiglistApiService, $ConfigProjectApiService } = useNuxtApp();
const pending = ref(true);
const error = ref(null);
const items = ref([]);
const searchInput = ref('');
const searchByAddress = ref('');
const filter_status = ref([]);
const selectedFilters = ref([]);
const sortBy = ref(null);
const sortDesc = ref(false);

const permissions = ref(null);


const isFilterOpen = ref(false);
const showAddressSearch = ref(false);
const isFilterShown = ref([]);
const filtersExtra = ref([]);

const filter_is_potable = ref([]);
const filter_has_fraud = ref([]);
const is_potable = ref(null);
const has_fraud = ref(null);
const selected_bool = ref([]);

const filter_noozle_types = ref([]);
const selected_noozle_type = ref([]);
const noozle_types = ref([]);

const filter_types = ref([]);
const selected_types = ref([]);
const types = ref([]);

const filter_supply_types = ref([]);
const selected_supply_types = ref([]);
const supply_types = ref([]);

const filter_placements = ref([]);
const selected_placements = ref([]);
const placements = ref([]);

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
    const data = await $SupplyPointApiService.getPermissions();
    permissions.value = data;
  } catch (err) {
    error.value = err;
  }
}

const getData = async (searchQuery = '', filters = [], page = 1, sort = null, desc = false, is_potable = null, cluster_nozzle_type = null, type = [], has_fraud = null, supply_type = [], searchByAddressQuery = '', placement_id = []) => {
  if (!permissions.value?.can_view) {
    toast.error(t('common.no_permissions'));
    return navigateTo('/');
  }
  pending.value = true;
  error.value = null;
  
  try {
    const data = await $SupplyPointApiService.getList(searchQuery, filters, page, sort, desc, false, false, is_potable, cluster_nozzle_type, type, has_fraud, supply_type, searchByAddressQuery, placement_id);

    items.value = data.results;
    Object.assign(pagination.value, {
      total: data.count,
      totalPages: Math.ceil(data.count / pagination.value.perPage),
      previous: data.previous,
      next: data.next,
      isFiltered: String(searchQuery).trim() !== '' || filters.length > 0 || String(searchByAddressQuery).trim() !== '' || placement_id.length > 0
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
    const data = await $SupplyPointApiService.getFilterStatus();
    filter_status.value = data;
  } catch (err) {
    error.value = err;
  }

  try {
    const data = await $ConfigProjectApiService.get('supply_point_status_activate_token')
    if (data) {
      selectedFilters.value.push(filter_status.value.filter(f => f.token == data)[0].id)
    }
  } catch (err) {
    console.error(err)
    console.log('Supply Point active status filter could not be established...')
  }
}

const getFilterSupplyType = async () => {
  error.value = null;
  try {
    const data = await $ConfiglistApiService.getAll('service/supply-point-supply-type');
    filter_supply_types.value = data.results;
  } catch (err) {
    error.value = err;
  }
}

const getFilterPlacement = async () => {
  error.value = null;
  try {
    const data = await $ConfiglistApiService.getAll('service/supply-point-placement');
    // El nom visible (p. ex. "Zona 1") ve del backend; a l'API s'envia l'id.
    filter_placements.value = data.results;
  } catch (err) {
    error.value = err;
  }
}

const getFilterNozzleType = async () => {
  error.value = null;
  try {
    const data = await $ClusterNozzleApiService.getNozzleType();
    filter_noozle_types.value = data;
  } catch (err) {
    error.value = err;
  }
}

const getType = async () => {
  error.value = null;
  try {
    const data = await $ConfiglistApiService.getAll('service/supply-point-type');
    filter_types.value = data.results;
  } catch (err) {
    error.value = err;
  }
}

const debouncedGetData = debounce((query, filters, sort, desc, is_potable, noozle_types, type, has_fraud, supply_type, searchByAddressQuery = '', placement_id = []) => {
  getData(query, filters, pagination.value.page, sort, desc, is_potable, noozle_types, type, has_fraud, supply_type, searchByAddressQuery, placement_id);
}, 300);

const handleSearch = () => {
  pagination.value.page = 1;
  debouncedGetData(searchInput.value, selectedFilters.value, sortBy.value, sortDesc.value, is_potable.value, noozle_types.value, types.value, has_fraud.value, supply_types.value, searchByAddress.value, placements.value);
}

const handleAddressChange = (addressString) => {
  searchByAddress.value = addressString;
  pagination.value.page = 1;
  debouncedGetData(searchInput.value, selectedFilters.value, sortBy.value, sortDesc.value, is_potable.value, noozle_types.value, types.value, has_fraud.value, supply_types.value, addressString, placements.value);
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

const handleFiltersSelectChange = (event) => {
  let newFilters = event
    .filter(el => !isFilterShown.value.includes(el.id));

  checkInAdvacedFilters(newFilters)
  isFilterShown.value = [];
  isFilterShown.value = [...isFilterShown.value, ...newFilters];
}

const checkInAdvacedFilters = (newFilters) => {
  if (isFilterShown.value.some(filter => filter.id === 'is_potable') && !newFilters.some(filter => filter.id === 'is_potable')) {
    is_potable.value = null;
    getData();
  } else if (isFilterShown.value.some(filter => filter.id === 'has_fraud') && !newFilters.some(filter => filter.id === 'has_fraud')) {
    has_fraud.value = null;
    getData();
  } else if (isFilterShown.value.some(filter => filter.id === 'cluster_nozzle_type') && !newFilters.some(filter => filter.id === 'cluster_nozzle_type')) {
    noozle_types.value = [];
    selected_noozle_type.value = [];
  } else if (isFilterShown.value.some(filter => filter.id === 'type') && !newFilters.some(filter => filter.id === 'type')) {
    types.value = [];
    selected_types.value = [];
    getData();
  } else if (isFilterShown.value.some(filter => filter.id === 'supply_type') && !newFilters.some(filter => filter.id === 'supply_type')) {
    supply_types.value = [];
    selected_supply_types.value = [];
  } else if (isFilterShown.value.some(filter => filter.id === 'placement') && !newFilters.some(filter => filter.id === 'placement')) {
    placements.value = [];
    selected_placements.value = [];
    getData(searchInput.value, selectedFilters.value, pagination.value.page, sortBy.value, sortDesc.value, is_potable.value, noozle_types.value, types.value, has_fraud.value, supply_types.value, searchByAddress.value, []);
  }
}

const handleFilterPotableChange = (event) => {
  is_potable.value = event[0].id;
  pagination.value.page = 1;
  handleSearch();
}

const handleFilterFraudChange = (event) => {
  has_fraud.value = event[0].id;
  pagination.value.page = 1;
  handleSearch();
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

const handleFilterSupplyTypeChange = (event) => {
  selected_supply_types.value = event;
  supply_types.value = [];
  selected_supply_types.value.forEach(element => {
    supply_types.value.push(element.id);
  })
  pagination.value.page = 1;
  handleSearch();
}

const handleFilterPlacementChange = (event) => {
  selected_placements.value = event;
  placements.value = [];
  selected_placements.value.forEach(element => {
    placements.value.push(element.id);
  })
  pagination.value.page = 1;
  handleSearch();
}

const handleFilterNoozleTypeChange = (event) => {
  selected_noozle_type.value = event;
  noozle_types.value = [];
  selected_noozle_type.value.forEach(element => {
    noozle_types.value.push(element.id);
  })
  pagination.value.page = 1;
  handleSearch();
}

const handlePageChange = (newPage) => {
  pagination.value.page = newPage;
  getData(searchInput.value, selectedFilters.value, newPage, sortBy.value, sortDesc.value, is_potable.value, noozle_types.value, types.value, has_fraud.value, supply_types.value, searchByAddress.value, placements.value);
}

const handleSort = (key) => {
  if (sortBy.value === key) {
    sortDesc.value = !sortDesc.value;
  } else {
    sortBy.value = key;
    sortDesc.value = false;
  }
  getData(searchInput.value, selectedFilters.value, pagination.value.page, sortBy.value, sortDesc.value, is_potable.value, noozle_types.value, types.value, has_fraud.value, supply_types.value, searchByAddress.value, placements.value);
}

const exportColumns = computed(() => [
  { header: t('common.identification'), value: (row) => row.token, key: 'token' },
  { header: t('address_block.address'), value: (row) => row.address_complete, key: 'address_complete' },
  { header: t('address_block.locality'), value: (row) => row.address_city, key: 'address_city' },
  { header: t('common.type'), value: (row) => row.type_name || row.type_token, key: 'type' },
  { header: t('common.status'), value: (row) => row.status_name || row.status_token, key: 'status' },
  { header: t('service_block.potable'), value: (row) => row.is_potable ? t('service_block.potable') : t('service_block.no_potable'), key: 'is_potable' },
  { header: t('route'), value: (row) => row.property_route_position_token, key: 'property_route_position' },
  { header: t('meter'), value: (row) => row.meter_code, key: 'meter' },
  { header: t('cluster'), value: (row) => row.cluster_nozzle_token, key: 'cluster_nozzle' },
  { header: t('connection'), value: (row) => row.connection_name || row.connection_token, key: 'connection' },
  { header: t('contract'), value: (row) => row.contracts?.length ? row.contracts[0].token : '' },
  { header: t('exploitation'), value: (row) => row.connection_exploitation_name || row.connection_exploitation_token, key: 'connection_exploitation' },
  { header: t('service_block.zone'), value: (row) => row.placement_name || '', key: 'placement' },
]);

/**
 * Columnes configurables (mateix patró que contractes): l'usuari pot mostrar/amagar,
 * reordenar i redimensionar; es guarda a localStorage per usuari (`useTableColumns`).
 */
const tableColumns = computed(() => [
  {
    key: 'token', label: t('common.identification'), sortKey: 'token',
    width: 118, min: 100, priority: 1, removable: false,
    cellClass: 'flex items-center gap-1',
  },
  {
    key: 'address', label: t('address_block.address'), sortKey: 'address_complete',
    width: 250, grow: 3, min: 160, priority: 1, removable: false,
  },
  {
    key: 'locality', label: t('address_block.locality'), sortKey: 'address_city',
    width: 130, grow: 1, min: 90, priority: 3,
  },
  {
    key: 'type', label: t('common.type'), sortKey: 'type_name',
    width: 120, min: 90, grow: 1, priority: 3,
  },
  {
    key: 'status', label: t('common.status'), sortKey: 'status_name',
    width: 110, min: 80, priority: 1,
  },
  {
    key: 'is_potable', label: t('service_block.potable'),
    width: 100, min: 80, priority: 4,
  },
  {
    key: 'route', label: t('route'), sortKey: 'property_route_position_token',
    width: 120, min: 90, priority: 3,
  },
  {
    key: 'meter', label: t('meter'), sortKey: 'meter_code',
    width: 110, min: 90, grow: 1, priority: 3,
  },
  {
    key: 'cluster', label: t('cluster'), sortKey: 'cluster_nozzle_token',
    width: 110, min: 90, priority: 4,
  },
  {
    key: 'connection', label: t('connection'), sortKey: 'connection_token',
    width: 120, min: 90, priority: 3,
  },
  {
    key: 'contract', label: t('contract'),
    width: 110, min: 90, priority: 2,
  },
  {
    key: 'exploitation', label: t('exploitation'), sortKey: 'connection_exploitation_name',
    width: 130, min: 100, grow: 1, priority: 4,
  },
  {
    key: 'placement', label: t('service_block.zone'), sortKey: 'placement_name',
    width: 120, min: 90, priority: 2,
  },
]);

const rowClass = (item) => ({
  'bg-yellow-50': item.id === selectedItemId.value,
});

const exportSupplyPoints = (columns) => $SupplyPointApiService.exportData(
  searchInput.value, selectedFilters.value, sortBy.value, sortDesc.value,
  false, false, is_potable.value, noozle_types.value, types.value, has_fraud.value, supply_types.value, searchByAddress.value,
  placements.value, columns,
);

const resetFilters = () => {
  searchInput.value = '';
  searchByAddress.value = '';
  selectedFilters.value = [];
  noozle_types.value = [];
  selected_noozle_type.value = [];
  is_potable.value = null;
  has_fraud.value = null;
  isFilterShown.value = [];
  selected_bool.value = [];
  selected_types.value = [];
  types.value = [];
  supply_types.value = [];
  selected_supply_types.value = [];
  placements.value = [];
  selected_placements.value = [];
  pagination.value.page = 1;
  isFilterOpen.value = false;
  showAddressSearch.value = false;
  getData();
};

const checkRouteQuery = () => {
  if (route.query?.action == 'showDetail') {
    toggleRegion(false);
    showSupplyPointRegion(route.query.id)
  } else if (route.query?.action == 'filterPage') {
    for (let filter in route.query.variables) {
      selectedFilters.value.push(parseInt(route.query.variables[filter].replaceAll('"', ' ')));
    }
    handleFilterChange();
  } else {
    if (route.query.id &&
      !(selectedItemId.value && String(selectedItemId.value) === String(route.query.id) && showRegion.value)) {
      showSupplyPointRegion(route.query.id);
    }
  }
}

const showSupplyPointRegion = (id) => {
  if (id && selectedItemId.value && String(selectedItemId.value) === String(id) && showRegion.value) {
    toggleRegion(false, true);
    nextTick(() => {
      supplyPointRegion.value = id;
      selectedItemId.value = id;
      toggleRegion(true);
    });
    return;
  }
  toggleRegion(false);
  supplyPointRegion.value = id;
  selectedItemId.value = id;
  toggleRegion(true);
  if (route.query.id !== String(id)) {
    router.replace({ path: route.path, query: { ...route.query, id: id } });
  }
}

// Watch for changes in searchInput and reset pagination to 1
watch(searchInput, () => {
  pagination.value.page = 1;
  handleSearch();
});

const handleSubRegionEvent = (event) => {
  isSubRegionOpen.value = event;
}

onMounted(async () => {
  await getPermissions();
  if (!permissions.value?.can_view) {
    pending.value = false;
    toast.error(t('common.no_permissions'));
    return navigateTo('/');
  }
  filtersExtra.value.push(
      { name: t("service_block.potable"), id: "is_potable" }, 
      { name: t("service_block.has_fraud"), id: "has_fraud" }, 
      { name: t("service_block.nozzle_type"), id: "cluster_nozzle_type" },
      { name: t("service_block.short_type"), id: "type" },
      { name: t("service_block.short_supply_type"), id: "supply_type" },
      { name: t("service_block.zone"), id: "placement" }
    );
  await getFilterStatus();
  await getData('', selectedFilters.value);
  await getFilterNozzleType();
  await getType();
  await getFilterSupplyType();
  await getFilterPlacement();
  filter_is_potable.value = [{id: true, name: t("service_block.potable")}, {id: false, name: t("service_block.no_potable")}]
  filter_has_fraud.value = [{id: true, name: t("service_block.has_fraud")}, {id: false, name: t("service_block.no_fraud")}]
  checkRouteQuery()
});
watch(() => route.query, () => {
  checkRouteQuery()
}, { immediate: true })
</script>

<template>
  <div id="wrapper" class="text-base">
    <div class="flex justify-between items-center mb-2">
      <H1>{{ $t('common.supply_points') }}</H1>
      <span>
        <AtomsDownloadXlsxButton :rows="items" :columns="exportColumns" file-name="supply_points"
          :total-pages="pagination.totalPages" :server-export-fn="exportSupplyPoints" />
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
        <button id="filterReset" name="form_filter" type="button"
          class="px-2 py-1 hover:bg-slate-300 rounded flex items-center" @click="resetFilters" title="reset">
          <Icon name="fa6-solid:rotate-right" class="text-slate-500" />
        </button>
      </span>
    </form>

    <div class="px-2 text-base flex flex-start gap-2 justify-start items-center flex-wrap" v-if="isFilterOpen">

      <span v-if="showAddressSearch" class="flex items-center gap-2">
        <AtomsInputAddressSearch :value="searchByAddress" @change="handleAddressChange" />
      </span>

      <FilterSelect v-if="isFilterShown.some(filter => filter.id === 'cluster_nozzle_type')" :options="filter_noozle_types"
        :filters="selected_noozle_type" :multiple="true" :placeholder="t(`service_block.nozzle_type`)"
        @update:modelValue="handleFilterNoozleTypeChange($event)">
        <template #icon>
          <Icon name="fa6-solid:circle-check" class="text-md ml-2 mr-1" size="10px" />
        </template>
      </FilterSelect>

      <FilterSelect v-if="isFilterShown.some(filter => filter.id === 'is_potable')" :options="filter_is_potable"
        :filters="selected_bool" :multiple="false" :placeholder="t(`service_block.potable`)"
        @update:modelValue="handleFilterPotableChange($event)">
        <template #icon>
          <Icon name="fa6-solid:circle-check" class="text-md ml-2 mr-1" size="10px" />
        </template>
      </FilterSelect>
      
      <FilterSelect v-if="isFilterShown.some(filter => filter.id === 'has_fraud')" :options="filter_has_fraud"
        :filters="selected_bool" :multiple="false" :placeholder="t(`service_block.has_fraud`)"
        @update:modelValue="handleFilterFraudChange($event)">
        <template #icon>
          <Icon name="fa6-solid:circle-check" class="text-md ml-2 mr-1" size="10px" />
        </template>
      </FilterSelect>

      <FilterSelect v-if="isFilterShown.some(filter => filter.id === 'type')" :options="filter_types"
        :filters="selected_types" :multiple="true" :placeholder="t(`service_block.short_type`)"
        @update:modelValue="handleFilterTypeChange($event)">
        <template #icon>
          <Icon name="fa6-solid:circle-check" class="text-md ml-2 mr-1" size="10px" />
        </template>
      </FilterSelect>

      <FilterSelect v-if="isFilterShown.some(filter => filter.id === 'supply_type')" :options="filter_supply_types"
        :filters="selected_supply_types" :multiple="true" :placeholder="t(`service_block.short_supply_type`)"
        @update:modelValue="handleFilterSupplyTypeChange($event)">
        <template #icon>
          <Icon name="fa6-solid:circle-check" class="text-md ml-2 mr-1" size="10px" />
        </template>
      </FilterSelect>

      <FilterSelect v-if="isFilterShown.some(filter => filter.id === 'placement')" :options="filter_placements"
        :filters="selected_placements" :multiple="true" :placeholder="t(`service_block.zone`)"
        @update:modelValue="handleFilterPlacementChange($event)">
        <template #icon>
          <Icon name="fa6-solid:circle-check" class="text-md ml-2 mr-1" size="10px" />
        </template>
      </FilterSelect>

      <FilterSelect :options="filtersExtra" :filters="isFilterShown" :multiple="true" :selector="true"
        :placeholder="$t('common.additional_filters')" @update:modelValue="handleFiltersSelectChange($event)">
        <template #icon>
          <Icon name="fa6-solid:plus" class="text-md ml-2 mr-1" size="10px" />
        </template>
      </FilterSelect>

    </div>

    <DataTable
      table-key="supply-points"
      :columns="tableColumns"
      :items="items"
      :row-class="rowClass"
      :current-sort-by="sortBy"
      :sort-desc="sortDesc"
      :pending="pending"
      :error="error"
      :is-empty="items.length === 0"
      @sort="handleSort"
      @retry="getData">
      <template #cell-token="{ item }">
        <button class="group flex justify-between w-full items-center text-sky-500 text-nowrap text-left gap-1"
          @click="showSupplyPointRegion(item.id);">
          <span class="flex items-center gap-1 min-w-0">
            <abbr :title="item.id" class="no-underline min-w-0">{{ item.token }}</abbr>
            <abbr v-if="item.current_fraud" :title="t('service_block.supply_with_fraud')" class="shrink-0">
              <Icon name="fa6-solid:mask" class="text-orange-500" />
            </abbr>
            <abbr v-else-if="item.previous_fraud" :title="t('service_block.supply_with_fraud_history')" class="shrink-0">
              <Icon name="fa6-solid:mask" class="text-slate-500" />
            </abbr>
            <abbr v-if="item.supply_cut_alert" :title="t('service_block.supply_with_cut')" class="shrink-0">
              <Icon name="fa6-solid:scissors" :class="item.supply_cut_alert.temporary ? 'text-sky-500' : 'text-red-500'" />
            </abbr>
          </span>
          <Icon name="fa6-solid:eye"
            class="opacity-0 group-hover:opacity-100 text-slate-500 mr-1 transition-opacity duration-200 ease-in-out shrink-0" />
        </button>
      </template>

      <template #cell-address="{ item }">
        <span class="truncate" :title="item.address_complete">{{ item.address_complete }}</span>
      </template>
      <template #cell-locality="{ item }">
        <span class="truncate" :title="item.address_city">{{ item.address_city }}</span>
      </template>
      <template #cell-type="{ item }">{{ item.type_name || item.type_token }}</template>

      <template #cell-status="{ item }">
        <AtomsColorBadge :value="item.status_name || item.status_token" :color="item.status_color" />
      </template>

      <template #cell-is_potable="{ item }">
        <AtomsColorBadge :value="item.is_potable ? $t('service_block.potable') : $t('service_block.no_potable')"
          :color="item.is_potable ? 'blue' : '-'" />
      </template>

      <template #cell-route="{ item }">{{ item.property_route_position_token }}</template>
      <template #cell-meter="{ item }">{{ item.meter_code }}</template>
      <template #cell-cluster="{ item }">{{ item.cluster_nozzle_token }}</template>
      <template #cell-connection="{ item }">{{ item.connection_name || item.connection_token }}</template>
      <template #cell-contract="{ item }">{{ item.contracts?.length ? item.contracts[0].token : '-' }}</template>
      <template #cell-exploitation="{ item }">{{ item.connection_exploitation_name || item.connection_exploitation_token }}</template>
      <template #cell-placement="{ item }">{{ item.placement_name || '-' }}</template>
    </DataTable>
    <div id="list__footer">
      <Pagination v-if="items.length > 0" :pagination="pagination" @update:page="handlePageChange" />
    </div>
  </div><!-- end wrapper -->

  <div role="region" id="right_page"
    class="fixed z-20 h-full border-l border-gray-100 top-0 transition-[right,width] duration-500 ease py-2 text-base bg-white"
    :class="[showRegion ? 'right-0' : 'right-[-2000px]', isSubRegionOpen ? 'w-[95%]' : 'w-[60%]']">
    <div id="region_nav" class="mb-3 px-3">
      <button @click="toggleRegion(false)" class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300">
        <Icon name="fa6-solid:angles-right" class="text-slate-500" />
      </button>
    </div>
    <div class="pl-10 h-full">
      <SupplyPointRegion v-if="supplyPointRegion" :id="parseInt(supplyPointRegion)" :isSubRegionOpen="isSubRegionOpen"
        @show-subregion="handleSubRegionEvent" @close-subregion="toggleRegion(false)"></SupplyPointRegion>
    </div>
  </div>

</template>