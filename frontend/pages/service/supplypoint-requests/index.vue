<script setup>
import { ref, onMounted, nextTick, computed, watch } from 'vue';
import { useRouter } from 'vue-router';
import debounce from 'lodash.debounce';
import { useI18n } from 'vue-i18n';
import { formatDate } from '~/utils/date';

import Pagination from '~/components/molecules/Pagination.vue';
import H1 from '~/components/atoms/H1.vue';
import SupplyPointRequestRegion from '~/components/organisms/SupplyPointRequestRegion.vue';
import DataTable from '~/components/organisms/DataTable.vue';

const { t } = useI18n();

const showRegion = ref(false);
const toggleRegion = (force) => {
  showRegion.value = force !== undefined ? force : !showRegion.value;
  if (showRegion.value == false) {
    isSubRegionOpen.value = false;
  }
}

const router = useRouter();
const { $SupplyPointRequestApiService } = useNuxtApp();
const pending = ref(true);
const error = ref(null);
const items = ref([]);
const searchInput = ref('');
const filter_status = ref([]);
const selectedFilters = ref([]);
const sortBy = ref('token');
const sortDesc = ref(false);

const pagination = ref({
  page: 1,
  perPage: 50,
  total: 0,
  totalPages: 0,
  previous: null,
  next: null,
  isFiltered: false
});

const getData = async (searchQuery = '', filters = [], page = 1, sort = 'token', desc = false) => {
  pending.value = true;
  error.value = null;
  try {
    const data = await $SupplyPointRequestApiService.getData(searchQuery, filters, page, sort, desc);

    items.value = data.results;
    Object.assign(pagination.value, {
      total: data.count,
      totalPages: Math.ceil(data.count / pagination.value.perPage),
      previous: data.previous,
      next: data.next,
      isFiltered: String(searchQuery).trim() !== '' || filters.length > 0
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
    const data = await $SupplyPointRequestApiService.getFilterStatus();
    filter_status.value = data;
  } catch (err) {
    error.value = err;
  }
}

const debouncedGetData = debounce((query, filters, sort, desc) => {
  getData(query, filters, pagination.value.page, sort, desc);
}, 300);

const handleSearch = () => {
  pagination.value.page = 1;
  debouncedGetData(searchInput.value, selectedFilters.value, sortBy.value, sortDesc.value);
}

const handleFilterChange = () => {
  pagination.value.page = 1;
  handleSearch();
}

const handlePageChange = (newPage) => {
  pagination.value.page = newPage;
  getData(searchInput.value, selectedFilters.value, newPage, sortBy.value, sortDesc.value);
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

const exportColumns = computed(() => [
  { header: t('Ident.'), value: (row) => row.token, key: 'token' },
  { header: t('Estat'), value: (row) => row.status?.name, key: 'status' },
  { header: t('Sol·licitant'), value: (row) => [row.person?.name, row.person?.surname].filter(Boolean).join(' ') },
  { header: t('Escomesa'), value: (row) => row.connection?.token || '', key: 'connection' },
  { header: t('Ubicació'), value: (row) => row.address?.address_complete || '' },
]);

const exportSupplyPointRequests = (columns) => $SupplyPointRequestApiService.exportData(searchInput.value, selectedFilters.value, sortBy.value, sortDesc.value, columns);

const resetFilters = () => {
  searchInput.value = '';
  selectedFilters.value = [];
  pagination.value.page = 1;
  getData();
};

onMounted(() => {
  return navigateTo('/');
  getData();
  getFilterStatus();
});

const itemDetail = ref(null);
const selectedItemId = ref(null);

const requestDeleted = () => {
  toggleRegion(false)
  getData();
}

const showItemDetail = (id) => {
  itemDetail.value = id;
  selectedItemId.value = id;
  toggleRegion(true);
}

const regionAccept = () => {
  getData();
  toggleRegion(false);
}

// Watch for changes in searchInput and selectedFilters and reset pagination to 1
watch([searchInput, selectedFilters], () => {
  pagination.value.page = 1;
  handleSearch();
});


const isSubRegionOpen = ref(false);
const handleSubRegionEvent = (event) => {
  isSubRegionOpen.value = event;
}

const rowClass = (item) => ({
  'bg-yellow-50': item.id === selectedItemId.value,
});

const tableColumns = computed(() => [
  { key: 'token', label: t('Ident.'), sortKey: 'id', width: 130, min: 100, priority: 1, removable: false },
  { key: 'status', label: t('Estat'), sortKey: 'status_name', width: 130, min: 90, priority: 1 },
  { key: 'person', label: t('Sol·licitant'), width: 200, min: 120, grow: 1, priority: 2 },
  { key: 'connection', label: t('Escomesa'), width: 130, min: 90, priority: 3 },
  { key: 'address', label: t('Ubicació'), width: 260, min: 150, grow: 2, priority: 2 },
]);

</script>

<template>
  <div id="wrapper" class="text-base">
    <div class="flex justify-between items-center mb-2">
      <H1>{{ $t('Sol·licitud Subministrament') }}</H1>
      <div class="flex items-center gap-2">
        <AtomsDownloadXlsxButton :rows="items" :columns="exportColumns" file-name="supplypoint_requests"
          :total-pages="pagination.totalPages" :server-export-fn="exportSupplyPointRequests" />
        <NuxtLink to="/service/supplypoint-requests/add" class="button-primary">{{ $t('Nova Sol·licitud') }}</NuxtLink>
      </div>
    </div>
    <form id="form_filter" role="search"
      class="mb-3 text-base border-b border-gray-400 flex flex-start gap-4 justify-start items-center"
      @submit.prevent="handleSearch">

      <span class="input-group flex flex-start items-center gap-2 w-80">
        <Icon name="fa6-solid:magnifying-glass" class="text-slate-500" />
        <input v-model="searchInput" @input="handleSearch" id="searchInput" type="text" name="search"
          :placeholder="$t('Cerca')" class="w-full p-1 rounded-md focus:outline-none focus-visible:border-0"
          autocomplete="off" />
      </span>

      <div class="h-8 w-px bg-gray-300" v-if="filter_status.length"></div>

      <span class="flex gap-3" v-if="filter_status.length">
        <label v-for="status in filter_status" class="text-slate-800 text-base flex items-center gap-1">
          <input type="checkbox" v-model="selectedFilters" :value="status.id" @change="handleFilterChange" /> {{
            status.name }}
        </label>
      </span>

      <span>
        <button id="filterReset" name="form_filter" type="button" class="px-2 py-1 hover:bg-slate-300 rounded"
          @click="resetFilters" title="reset">
          <Icon name="fa6-solid:rotate-right" class="text-slate-500" />
        </button>
      </span>
    </form>
    <DataTable
      table-key="supplypoint-requests"
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
        <button class="group flex justify-between w-full items-center text-sky-500 text-nowrap text-left"
          @click="showItemDetail(item.id);">
          <abbr :title="item.id" class="no-underline">{{ item.token }}</abbr>
          <Icon name="fa6-solid:eye"
            class="opacity-0 group-hover:opacity-100 text-slate-500 mr-1 transition-opacity duration-200 ease-in-out" />
        </button>
      </template>

      <template #cell-status="{ item }">
        <AtomsColorBadge :value="item.status?.name" :color="item.status?.color"></AtomsColorBadge>
      </template>

      <template #cell-person="{ item }">
        <AtomsPersonBadge :person="item.person" />
      </template>

      <template #cell-connection="{ item }">
        {{ item.connection?.token || "" }}
      </template>

      <template #cell-address="{ item }">
        {{ item.address?.address_complete || "" }}
      </template>
    </DataTable>
    <div id="list__footer">
      <Pagination v-if="items.length > 0" :pagination="pagination" @update:page="handlePageChange" />
    </div>
  </div><!-- end wrapper -->

  <div role="region" id="right_page"
    class="fixed h-full border-l border-gray-100 top-0 right-0 transition-all duration-500 ease py-2 text-base bg-white"
    :class="{ 'translate-x-0': showRegion, 'translate-x-full': !showRegion, 'w-[95%]': isSubRegionOpen, 'w-1/2': !isSubRegionOpen }">
    <div id="region_nav" class="mb-3 px-3">
      <button @click="toggleRegion(false)" class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300">
        <Icon name="fa6-solid:angles-right" class="text-slate-500" />
      </button>
    </div>
    <div class="pl-10 h-full">
      <SupplyPointRequestRegion v-if="itemDetail" :id="itemDetail" @accept="regionAccept"
        :isSubRegionOpen="isSubRegionOpen" @show-subregion="handleSubRegionEvent" @deleted="requestDeleted">
      </SupplyPointRequestRegion>
    </div>
  </div>

</template>
