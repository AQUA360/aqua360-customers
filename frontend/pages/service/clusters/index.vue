<script setup>
import { ref, onMounted, nextTick, computed, watch } from 'vue';
import { useRouter } from 'vue-router';
import debounce from 'lodash.debounce';
import { useI18n } from 'vue-i18n';
import { formatDate } from '~/utils/date';
import { useToast } from 'vue-toastification';
import Pagination from '~/components/molecules/Pagination.vue';
import H1 from '~/components/atoms/H1.vue';
import ClusterRegion from '~/components/organisms/ClusterRegion.vue';
import TableHeader from '~/components/atoms/TableHeader.vue';
import DataTable from '~/components/organisms/DataTable.vue';

const { t } = useI18n();
const toast = useToast();
const showRegion = ref(false);
const region = ref(null)

const detail = ref(null);
const selectedItemId = ref(null);
const isSubRegionOpen = ref(false);
const toggleRegion = (force) => {
  showRegion.value = force !== undefined ? force : !showRegion.value;
  if (showRegion.value == false) {
    isSubRegionOpen.value = false;
    region.value = null
    detail.value = null;
    selectedItemId.value = null;
  }
}

const router = useRouter();
const route = useRoute();
const { $ClusterApiService } = useNuxtApp();
const pending = ref(true);
const error = ref(null);
const items = ref([]);
const searchInput = ref('');
const searchByAddress = ref('');
const showAddressSearch = ref(false);
const filter_status = ref([]);
const selectedFilters = ref([]);
const sortBy = ref('token');
const sortDesc = ref(false);
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
    const data = await $ClusterApiService.getPermissions();
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
    const data = await $ClusterApiService.getData(searchQuery, filters, page, sort, desc, null, searchByAddressQuery);
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

const exportColumns = computed(() => [
  { header: t('common.identification'), value: (row) => row.token, key: 'token' },
  { header: t('address_block.address'), value: (row) => [row.street, row.street_number && row.street_number != 'None' ? row.street_number : null].filter(Boolean).join(', ') },
  { header: t('service_block.nozzles'), value: (row) => row.nb_nozzles, key: 'nb_nozzles' },
  { header: t('common.connections'), value: (row) => row.connection_name || row.connection_token || '', key: 'connection' },
  { header: t('common.status'), value: (row) => row.status_name || row.status_token || '', key: 'status' },
]);

const exportClusters = (columns) => $ClusterApiService.exportData(searchInput.value, selectedFilters.value, sortBy.value, sortDesc.value, null, searchByAddress.value, columns);

const getFilterStatus = async () => {
  error.value = null;
  try {
    const data = await $ClusterApiService.getFilterStatus();
    filter_status.value = data;
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

const resetFilters = () => {
  searchInput.value = '';
  searchByAddress.value = '';
  selectedFilters.value = [];
  pagination.value.page = 1;
  showAddressSearch.value = false;
  getData();
};

const toggleAddressFilter = () => {
  showAddressSearch.value = !showAddressSearch.value;
};

const onChangeRegion = (event) => {
  getData(searchInput.value, selectedFilters.value, pagination.value.page, sortBy.value, sortDesc.value);
}

onMounted(async () => {
  await getPermissions();
  if (!permissions.value?.can_view) {
    pending.value = false;
    toast.error(t('common.no_permissions'));
    return navigateTo('/');
  }
  await getData();
  getFilterStatus();
  checkRouteQuery();
});
const checkRouteQuery = () => {
  if (route.query?.action == 'showDetail') {
    toggleRegion(false);
    showDetail(route.query.id)
  }
}


const showDetail = async (id) => {
  await toggleRegion(false);
  region.value = 'detail'
  detail.value = id;
  selectedItemId.value = id;
  toggleRegion(true);
}

const connection = ref(null)
const showConnectionDetail = (connection_id) => {
  region.value = 'connection'
  connection.value = connection_id
  toggleRegion(true)
}




// Watch for changes in searchInput and selectedFilters and reset pagination to 1
watch([searchInput, selectedFilters], () => {
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
      <H1 class="mb-2">{{ $t('common.clusters') }}</H1>
      <div class="flex items-center gap-2">
        <AtomsDownloadXlsxButton :rows="items" :columns="exportColumns" file-name="clusters"
          :total-pages="pagination.totalPages" :server-export-fn="exportClusters" :sheet-name="$t('common.clusters')" />
        <NuxtLink v-if="permissions?.can_add" to="/service/clusters/add" class="button-primary">{{ $t('service_block.new_cluster') }}</NuxtLink>
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
        <button id="filterReset" name="form_filter" type="button" class="px-2 py-1 hover:bg-slate-300 rounded"
          @click="resetFilters" title="reset">
          <Icon name="fa6-solid:rotate-right" class="text-slate-500" />
        </button>
        <button id="filterAddress" name="form_filter" type="button"
          class="px-2 py-1 hover:bg-slate-300 rounded"
          :class="{ 'bg-slate-300': showAddressSearch }"
          @click="toggleAddressFilter"
          :title="$t('address_block.address')">
          <Icon name="fa6-solid:house" class="text-slate-500" />
        </button>
      </span>
    </form>

    <div v-if="showAddressSearch" class="mb-2 px-2 flex flex-start gap-2 justify-start items-center">
      <AtomsInputAddressSearch :value="searchByAddress" @change="handleAddressChange" />
    </div>
    <DataTable
      v-if="permissions?.can_view"
      grid-template="150px,250px,150px,150px,150px"
      :pending="pending"
      :error="error"
      :is-empty="items.length === 0"
      @retry="getData">
      <template #header>
        <TableHeader :label="$t('common.identification')" sortKey="token" :currentSortBy="sortBy" :sortDesc="sortDesc"
          @sort="handleSort" />
        <TableHeader :label="$t('address_block.address')" sortKey="address_complete" :currentSortBy="sortBy" :sortDesc="sortDesc"
          @sort="handleSort" />
        <TableHeader :label="$t('service_block.nozzles')" sortKey="nb_nozzles" :currentSortBy="sortBy" :sortDesc="sortDesc"
          @sort="handleSort" />
        <TableHeader :label="$t('common.connections')" sortKey="connection_token" :currentSortBy="sortBy" :sortDesc="sortDesc"
          @sort="handleSort" />
        <TableHeader :label="$t('common.status')" sortKey="status_name" :currentSortBy="sortBy" :sortDesc="sortDesc"
          @sort="handleSort" />
      </template>

      <template #default="{ gridStyle }">
        <div v-for="item in items" :key="item.id"
          class="gap-3 text-base border-b items-center bg-white mr-3"
          :style="gridStyle"
          :class="{ 'bg-yellow-50': item.id === selectedItemId }">
          <span>
            <button class="group flex justify-between w-full items-center p-1 text-sky-500 text-nowrap text-left"
              @click="showDetail(item.id);">
              <abbr :title="item.token" class="no-underline">{{ item.token }}</abbr>
              <Icon name="fa6-solid:eye"
                class="opacity-0 group-hover:opacity-100 text-slate-500 mr-1 transition-opacity duration-200 ease-in-out" />
            </button>
          </span>
          <span class="p-0" :title="`${ item.street } ${ item.street_number && item.street_number != 'None' ? ', '+item.street_number : '' }`">{{ item.street }} {{ item.street_number && item.street_number != 'None' ? ', '+item.street_number : '' }}</span>
          <span class="p-1">{{ item.nb_nozzles }}</span>
          <span class="p-1">
            <button class="group flex justify-between w-full items-center p-1 text-sky-500 text-nowrap text-left"
              @click="showConnectionDetail(item.connection_id)">
              <abbr :title="item.connection_name || item.connection_token || '-'" class="no-underline">{{ item.connection_name || item.connection_token || '-' }}</abbr>
              <Icon name="fa6-solid:eye"
                class="opacity-0 group-hover:opacity-100 text-slate-500 mr-1 transition-opacity duration-200 ease-in-out" />
            </button>
          </span>
          <span class="p-1 text-nowrap">
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
    :class="{ 'translate-x-0': showRegion, 'translate-x-[2000px]': !showRegion, 'w-[95%]': isSubRegionOpen, 'w-1/2': !isSubRegionOpen }">
    <div id="region_nav" class="mb-3 px-3">
      <button @click="toggleRegion(false)"
        class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300"><Icon name="fa6-solid:angles-right"
          class="text-slate-500" /></button>
    </div>
    <div class="pl-10 h-full">
      <ClusterRegion v-if="region == 'detail' && detail" :id="detail" :isSubRegionOpen="isSubRegionOpen"
        @show-subregion="handleSubRegionEvent" @changed="onChangeRegion" @close-subregion="toggleRegion(false)"></ClusterRegion>
      <OrganismsConnectionRegion v-else-if="region == 'connection' && connection" 
        :id="connection" 
        @show-subregion="handleSubRegionEvent"
        :isSubRegionOpen="isSubRegionOpen"
        @close="toggleRegion(false)"></OrganismsConnectionRegion>
    </div>
  </div>

</template>
