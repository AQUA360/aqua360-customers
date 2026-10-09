<script setup>
import { ref, onMounted, nextTick, computed, watch } from 'vue';
import { useRouter } from 'vue-router';
import debounce from 'lodash.debounce';
import { useI18n } from 'vue-i18n';
import { formatDate } from '~/utils/date';
import FilterSelect from '~/components/atoms/FilterSelect.vue';
import Pagination from '~/components/molecules/Pagination.vue';
import H1 from '~/components/atoms/H1.vue';
import ConnectionRegion from '~/components/organisms/ConnectionRegion.vue';
import TableHeader from '~/components/atoms/TableHeader.vue';
import { useToast } from 'vue-toastification';
import DataTable from '~/components/organisms/DataTable.vue';

const { t } = useI18n();
const route = useRoute();
const router = useRouter();
const toast = useToast();
const showRegion = ref(false);
const isSubRegionOpen = ref(false);
const selectedItemId = ref(null);
const toggleRegion = (force) => {
  showRegion.value = force !== undefined ? force : !showRegion.value;
  if (showRegion.value == false) {
    isSubRegionOpen.value = false;
    connectionRegion.value = null
    selectedItemId.value = null
  }
}

const handleSubRegionEvent = (event) => {
  isSubRegionOpen.value = event;
}

const { $ConnectionApiService, $ConfiglistApiService } = useNuxtApp();
const pending = ref(true);
const error = ref(null);
const items = ref([]);
const searchInput = ref('');
const searchByAddress = ref('');
const filter_status = ref([]);
const selectedFilters = ref([]);
const sortBy = ref('token');
const sortDesc = ref(false);
const permissions = ref(null);
const filter_types = ref([]);
const filter_use_types = ref([]);
const filter_materials = ref([]);
const filter_valve_types = ref([]);

const types = ref([]);
const use_types = ref([]);
const materials = ref([]);
const valve_types = ref([]);

const selected_types = ref([]);
const selected_use_types = ref([]);
const selected_materials = ref([]);
const selected_valve_types = ref([]);

const isFilterOpen = ref(false);
const showAddressSearch = ref(false);
const isFilterShown = ref([]);
const filtersExtra = ref([]);

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
    const data = await $ConnectionApiService.getPermissions();
    permissions.value = data;
  } catch (err) {
    error.value = err;
  }
}

const getData = async (searchQuery = '', filters = [], page = 1, sort = 'token', desc = false, searchByAddressQuery = '') => {
  if (!permissions.value?.can_view) {
    toast.error(t('common.no_permissions'));
    return navigateTo('/');
  }
  pending.value = true;
  error.value = null;
  
  try {
    const data = await $ConnectionApiService.getData(
      searchQuery, filters, page, sort, desc,
      null, types.value, use_types.value, materials.value, valve_types.value, searchByAddressQuery
    );

    items.value = data.results;
    Object.assign(pagination.value, {
      total: data.count,
      totalPages: Math.ceil(data.count / pagination.value.perPage),
      previous: data.previous,
      next: data.next,
      isFiltered: String(searchQuery).trim() !== '' || filters.length > 0 || String(searchByAddressQuery).trim() !== ''
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
    const data = await $ConnectionApiService.getFilterStatus();
    filter_status.value = data;
  } catch (err) {
    error.value = err;
  }
}

const getFilterTypes = async () => {
  error.value = null;
  try {
    const data = await $ConfiglistApiService.getAll('service/connection-type');
    filter_types.value = data.results;
  } catch (err) {
    error.value = err;
  }
}

const getFilterUseTypes = async () => {
  error.value = null;
  try {
    const data = await $ConfiglistApiService.getAll('service/connection-use-type');
    filter_use_types.value = data.results;
  } catch (err) {
    error.value = err;
  }
}

const getFilterMaterials = async () => {
  error.value = null;
  try {
    const data = await $ConfiglistApiService.getAll('service/connection-material');
    filter_materials.value = data.results;
  } catch (err) {
    error.value = err;
  }
}

const getFilterValveTypes = async () => {
  error.value = null;
  try {
    const data = await $ConfiglistApiService.getAll('service/connection-valve-type');
    filter_valve_types.value = data.results;
  } catch (err) {
    error.value = err;
  }
}

const debouncedGetData = debounce((query, filters, sort, desc, searchByAddressQuery = '') => {
  getData(query, filters, pagination.value.page, sort, desc, searchByAddressQuery);
}, 300);

const handleSearch = () => {
  pagination.value.page = 1;
  debouncedGetData(searchInput.value, selectedFilters.value, sortBy.value, sortDesc.value, searchByAddress.value);
}

const handleAddressChange = (addressString) => {
  searchByAddress.value = addressString;
  pagination.value.page = 1;
  debouncedGetData(searchInput.value, selectedFilters.value, sortBy.value, sortDesc.value, addressString);
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

const handlePageChange = (newPage) => {
  pagination.value.page = newPage;
  getData(searchInput.value, selectedFilters.value, newPage, sortBy.value, sortDesc.value, searchByAddress.value);
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

const handleTypeChange = (event) => {
  selected_types.value = event;
  types.value = []
  selected_types.value.forEach(element => {
    types.value.push(element.id);
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

const handleMaterialChange = (event) => {
  selected_materials.value = event;
  materials.value = []
  selected_materials.value.forEach(element => {
    materials.value.push(element.id);
  })
  pagination.value.page = 1;
  handleSearch();
}

const handleValveTypeChange = (event) => {
  selected_valve_types.value = event;
  valve_types.value = []
  selected_valve_types.value.forEach(element => {
    valve_types.value.push(element.id);
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
  if (isFilterShown.value.some(filter => filter.id === 'type') && !newFilters.some(filter => filter.id === 'type')) {
    types.value = [];
    selected_types.value = [];
    getData();
  } else if (isFilterShown.value.some(filter => filter.id === 'use_type') && !newFilters.some(filter => filter.id === 'use_type')) {
    use_types.value = [];
    selected_use_types.value = [];
    getData();
  } else if (isFilterShown.value.some(filter => filter.id === 'material') && !newFilters.some(filter => filter.id === 'material')) {
    materials.value = [];
    selected_materials.value = [];
    getData();
  } else if (isFilterShown.value.some(filter => filter.id === 'valve_type') && !newFilters.some(filter => filter.id === 'valve_type')) {
    valve_types.value = [];
    selected_valve_types.value = [];
    getData();
  }
}

const exportColumns = computed(() => [
  { header: t('common.identification'), value: (row) => row.token, key: 'token' },
  { header: t('address_block.address'), value: (row) => `${row.street || ''}${row.street_number && row.street_number != 'None' ? ', ' + row.street_number : ''}${row.address_extra ? ', ' + row.address_extra : ''}` },
  { header: t('common.status'), value: (row) => row.status_name, key: 'status' },
  { header: t('service_block.diameter'), value: (row) => row.diameter_name, key: 'diameter' },
  { header: t('common.usage'), value: (row) => row.use_type_name, key: 'use_type' },
  { header: t('service_block.short_install_date'), value: (row) => row.installation_at ? formatDate(row.installation_at) : '', key: 'installation_at' },
  { header: t('service_block.dma'), value: (row) => row.dma_name || row.dma_token, key: 'dma' },
  { header: t('exploitation'), value: (row) => row.exploitation_name || row.exploitation_token, key: 'exploitation' },
]);

const exportConnections = (columns) => $ConnectionApiService.exportData(
  searchInput.value, selectedFilters.value, sortBy.value, sortDesc.value,
  null, types.value, use_types.value, materials.value, valve_types.value, searchByAddress.value,
  columns,
);

const resetFilters = () => {
  searchInput.value = '';
  searchByAddress.value = '';
  selectedFilters.value = [];
  pagination.value.page = 1;
  types.value = [];
  selected_types.value = [];
  use_types.value = [];
  selected_use_types.value = [];
  materials.value = [];
  selected_materials.value = [];
  valve_types.value = [];
  selected_valve_types.value = [];
  isFilterShown.value = [];
  isFilterOpen.value = false;
  showAddressSearch.value = false;
  getData();
};

onMounted(async () => {
  await getPermissions();
  if (!permissions.value?.can_view) {
    pending.value = false;
    toast.error(t('common.no_permissions'));
    return navigateTo('/');
  }
  filtersExtra.value.push(
      { name: t('common.type'), id: "type" },
      { name: t('common.usage_type'), id: "use_type" },
      { name: t('service_block.materials'), id: "material" },
      { name: t('service_block.valve_type'), id: "valve_type" }
    );
  await getData();
  await getFilterStatus();
  await getFilterTypes();
  await getFilterUseTypes();
  await getFilterMaterials();
  await getFilterValveTypes();

  checkRouteQuery();
});

const checkRouteQuery = () => {
  if (route.query?.action == 'showDetail') {
    toggleRegion(false);
    showConnectionRegion(route.query.id)
  } else {
    if (route.query.id) {
      showConnectionRegion(route.query.id);
    }
  }
}
const connectionRegion = ref(null);

const showConnectionRegion = async (id) => {
  await toggleRegion(false);
  connectionRegion.value = id;
  selectedItemId.value = id;
  toggleRegion(true);
}

// Watch for changes in searchInput and selectedFilters and reset pagination to 1
watch([searchInput, selectedFilters], () => {
  pagination.value.page = 1;
  handleSearch();
});
watch(() => route.query, () => {
  checkRouteQuery()
}, { immediate: true })
</script>

<template>
  <div id="wrapper" class="text-base">
    <div class="flex justify-between items-center mb-2">
      <H1 class="mb-2">{{ $t('common.connections') }}</H1>
      <div class="flex items-center gap-2">
        <AtomsDownloadXlsxButton :rows="items" :columns="exportColumns" file-name="connections"
          :total-pages="pagination.totalPages" :server-export-fn="exportConnections" />
        <NuxtLink v-if="permissions?.can_add" to="/service/connections/add" class="button-primary">{{ $t('service_block.new_connection') }}</NuxtLink>
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

      <FilterSelect v-if="isFilterShown.some(filter => filter.id === 'type')" :options="filter_types"
        :filters="selected_types" :multiple="true" :placeholder="t(`common.type`)"
        @update:modelValue="handleTypeChange($event)">
        <template #icon>
          <Icon name="fa6-solid:circle-check" class="text-md ml-2 mr-1" size="10px" />
        </template>
      </FilterSelect>

      <FilterSelect v-if="isFilterShown.some(filter => filter.id === 'use_type')" :options="filter_use_types"
        :filters="selected_use_types" :multiple="true" :placeholder="t(`common.usage_type`)"
        @update:modelValue="handleUseTypeChange($event)">
        <template #icon>
          <Icon name="fa6-solid:circle-check" class="text-md ml-2 mr-1" size="10px" />
        </template>
      </FilterSelect>

      <FilterSelect v-if="isFilterShown.some(filter => filter.id === 'material')" :options="filter_materials"
        :filters="selected_materials" :multiple="true" :placeholder="t(`service_block.materials`)"
        @update:modelValue="handleMaterialChange($event)">
        <template #icon>
          <Icon name="fa6-solid:circle-check" class="text-md ml-2 mr-1" size="10px" />
        </template>
      </FilterSelect>

      <FilterSelect v-if="isFilterShown.some(filter => filter.id === 'valve_type')" :options="filter_valve_types"
        :filters="selected_valve_types" :multiple="true" :placeholder="t(`service_block.valve_type`)"
        @update:modelValue="handleValveTypeChange($event)">
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
      grid-template="2fr,3fr,1fr,1fr,1fr,1fr,2fr,2fr"
      :pending="pending"
      :error="error"
      :is-empty="items.length === 0"
      @retry="getData">
      <template #header>
        <TableHeader :label="$t('common.identification')" sortKey="token" :currentSortBy="sortBy" :sortDesc="sortDesc"
          @sort="handleSort" />
        <TableHeader :label="$t('address_block.address')" sortKey="address_id" :currentSortBy="sortBy" :sortDesc="sortDesc"
          @sort="handleSort" />
        <TableHeader :label="$t('common.status')" sortKey="status_name" :currentSortBy="sortBy" :sortDesc="sortDesc"
          @sort="handleSort" />
        <TableHeader :label="$t('service_block.diameter')" sortKey="diameter_name" :currentSortBy="sortBy" :sortDesc="sortDesc"
          @sort="handleSort" />
        <TableHeader :label="$t('common.usage')" sortKey="use_type_name" :currentSortBy="sortBy" :sortDesc="sortDesc"
          @sort="handleSort" />
        <TableHeader :label="$t('service_block.short_install_date')" sortKey="installation_at" :currentSortBy="sortBy" :sortDesc="sortDesc"
          @sort="handleSort" />
        <TableHeader :label="$t('service_block.dma')" sortKey="dma_name" :currentSortBy="sortBy" :sortDesc="sortDesc"
          @sort="handleSort" />
        <TableHeader :label="$t('exploitation')" sortKey="exploitation_name" :currentSortBy="sortBy" :sortDesc="sortDesc"
          @sort="handleSort" />
      </template>

      <template #default="{ gridStyle }">
        <template v-if="permissions?.can_view">
          <div v-for="item in items" :key="item.id"
            class="gap-3 text-base border-b items-center bg-white"
            :style="gridStyle"
            :class="{ 'bg-yellow-50': item.id === selectedItemId }">
            <span>
              <button class="group flex justify-between w-full items-center p-1 text-sky-500 text-nowrap text-left"
              @click="showConnectionRegion(item.id);">
                <abbr :title="item.token" class="no-underline">{{ item.token }}</abbr>
                <Icon name="fa6-solid:eye"
                class="opacity-0 group-hover:opacity-100 text-slate-500 mr-1 transition-opacity duration-200 ease-in-out" />
              </button>
            </span>
            <span class="p-1" :title="`${ item.street } ${ item.street_number && item.street_number != 'None' ? ', ' + item.street_number : '' } ${ item.address_extra ? ', '+item.address_extra : '' }`">{{ item.street }} {{ item.street_number && item.street_number != 'None' ? ', ' + item.street_number : '' }}  {{ item.address_extra ? ', '+item.address_extra : '' }}</span>
            <span class="p-1 text-nowrap">
              <AtomsColorBadge :value="item.status_name" :color="item.status_color"></AtomsColorBadge>
            </span>
            <span class="p-1" :title="item.diameter_name">{{ item.diameter_name }}</span>
            <span class="p-1" :title="item.use_type_name">{{ item.use_type_name }}</span>
            <span class="p-1" :title="item.installation_at ? formatDate(item.installation_at) : '-'">{{ item.installation_at ? formatDate(item.installation_at) : '-' }}</span>
            <span class="p-1 truncate" :title="item.dma_name || item.dma_token">{{ item.dma_name || item.dma_token }}</span>
            <span class="p-1" :title="item.exploitation_name || item.exploitation_token">{{ item.exploitation_name || item.exploitation_token }}</span>
          </div><!-- end for items -->
        </template>
      </template>
    </DataTable>
    <div id="list__footer">
      <Pagination v-if="items.length > 0" :pagination="pagination" @update:page="handlePageChange" />
    </div>
  </div><!-- end wrapper -->

  <div role="region" id="right_page"
    class="fixed h-full border-l border-gray-100 top-0 right-0 transition-all duration-500 ease py-2 text-base bg-white"
    :class="{ 'translate-x-0': showRegion, 'translate-x-[2000px]': !showRegion, 'w-[95%]': isSubRegionOpen, 'w-1/2': !isSubRegionOpen }">
    <div id="region_nav" class="mb-3 px-3">
      <button @click="toggleRegion(false)" class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300">
        <Icon name="fa6-solid:angles-right" class="text-slate-500" />
      </button>
    </div>
    <div class="pl-10 h-full">
      <ConnectionRegion v-if="connectionRegion" :id="connectionRegion" 
        @show-subregion="handleSubRegionEvent" @close="toggleRegion(false); getData()"
        :isSubRegionOpen="isSubRegionOpen">
      </ConnectionRegion>
    </div>
  </div>

</template>
