<script setup>
import { ref, onMounted, nextTick, computed, watch } from 'vue';
import { useRouter } from 'vue-router';
import debounce from 'lodash.debounce';
import { useI18n } from 'vue-i18n';
import { formatDate } from '~/utils/date';
import Pagination from '~/components/molecules/Pagination.vue';
import H1 from '~/components/atoms/H1.vue';
import TableHeader from '~/components/atoms/TableHeader.vue';
import CommunicationRegion from '~/components/organisms/CommunicationRegion.vue';
import FilterSelect from '~/components/atoms/FilterSelect.vue';
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
    openAddFraud.value = false
  }
}

const route = useRoute();
const router = useRouter();
const { $CommunicationApiService, $ConfiglistApiService, $apiManager, $DocumentManagerApiService } = useNuxtApp();
const pending = ref(true);
const error = ref(null);
const items = ref([]);
const searchInput = ref('');
const sortBy = ref(null);
const sortDesc = ref(false);

const selectedFilters = ref([]);
const selected_bool = ref([]);
const selected_types = ref([]);

const statuses = ref([]);
const types = ref([]);
const is_individual = ref(null);

const filter_is_individual = ref([]);
const filter_types = ref([]);
const filter_status = ref([]);

const selectedDateRangeArr = ref([]);
const date_range = ref({});

const isFilterOpen = ref(false);
const isFilterShown = ref([]);
const filtersExtra = ref([]);

const permissions = ref(null);
const openAddFraud = ref(false)

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
    const data = await $CommunicationApiService.getPermissions();
    permissions.value = data;
  } catch (err) {
    error.value = err;
  }
}

const exportColumns = computed(() => [
  { header: t('common.date'), value: (row) => row.created_at ? formatDate(row.created_at) : '', key: 'created_at' },
  { header: t('common.identification'), value: (row) => row.token, key: 'token' },
  { header: t('customer_service_block.recipient'), value: (row) => row.person_name, key: 'person_name' },
  { header: t('common.status'), value: (row) => row.status_name, key: 'status' },
  { header: t('common.type'), value: (row) => row.type_names, key: 'type_names' },
  { header: t('common.use_type'), value: (row) => row.use_type_name, key: 'use_type' },
  { header: t('customer_service_block.process'), value: (row) => row.process_token || t('customer_service_block.individual'), key: 'process_token' },
  { header: t('customer_service_block.sent'), value: (row) => row.sent_at ? formatDate(row.sent_at) : '', key: 'sent_at' },
  { header: t('user'), value: (row) => row.user_username, key: 'user' },
]);

const exportCommunications = (columns) => $CommunicationApiService.exportData(
  searchInput.value, statuses.value, sortBy.value, sortDesc.value, null, [], is_individual.value, types.value, null, date_range.value, columns
);

const getData = async (searchQuery = '', filters = [], page = 1, sort = null, desc = false, is_individual = null, types = []) => {
  if (!permissions.value?.can_view) {
    toast.error(t('common.no_permissions'));
    return navigateTo('/');
  }
  pending.value = true;
  error.value = null;

  try {
    const data = await $CommunicationApiService.getAll(searchQuery, filters, page, sort, desc, null, [], is_individual, types, null, date_range.value);

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
    const data = await $ConfiglistApiService.getAll('communication/communication-status');
    filter_status.value = data.results;
  } catch (err) {
    error.value = err;
  }
}

const getFilterTypes = async () => {
  error.value = null;
  try {
    const data = await $ConfiglistApiService.getAll('communication/message-type');
    filter_types.value = data.results;
  } catch (err) {
    error.value = err;
  }
}

const debouncedGetData = debounce((query, filters, sort, desc, is_individual, types) => {
  getData(query, filters, pagination.value.page, sort, desc, is_individual, types);
}, 300);

const handleSearch = () => {
  pagination.value.page = 1;
  debouncedGetData(searchInput.value, statuses.value, sortBy.value, sortDesc.value, is_individual.value, types.value);
}

const handleFilterChange = () => {
  pagination.value.page = 1;
  handleSearch();
}

const handlePageChange = (newPage) => {
  pagination.value.page = newPage;
  getData(searchInput.value, statuses.value, newPage, sortBy.value, sortDesc.value, is_individual.value, types.value);
}

const handleFilterIndividualChange = (event) => {
  is_individual.value = event[0].id;
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

const handleDateRangeChange = (event) => {
  date_range.value = event;
  pagination.value.page = 1;
  handleSearch();
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

const handleSort = (key) => {
  if (sortBy.value === key) {
    sortDesc.value = !sortDesc.value;
  } else {
    sortBy.value = key;
    sortDesc.value = false;
  }
  getData(searchInput.value, statuses.value, pagination.value.page, sortBy.value, sortDesc.value, is_individual.value, types.value);
}

const handleFiltersSelectChange = (event) => {
  let newFilters = event
    .filter(el => !isFilterShown.value.includes(el.id));

  checkInAdvacedFilters(newFilters)
  isFilterShown.value = [];
  isFilterShown.value = [...isFilterShown.value, ...newFilters];
}

const checkInAdvacedFilters = (newFilters) => {
  if (isFilterShown.value.some(filter => filter.id === 'is_individual') && !newFilters.some(filter => filter.id === 'is_individual')) {
    is_individual.value = null;
    pagination.value.page = 1;
    debouncedGetData(searchInput.value, selectedFilters.value, sortBy.value, sortDesc.value, is_individual.value, types.value);
  } else if (isFilterShown.value.some(filter => filter.id === 'status') && !newFilters.some(filter => filter.id === 'status')){
    statuses.value = [];
    selectedFilters.value = [];
    pagination.value.page = 1;
    debouncedGetData(searchInput.value, selectedFilters.value, sortBy.value, sortDesc.value, is_individual.value, types.value);
  } else if (isFilterShown.value.some(filter => filter.id === 'types') && !newFilters.some(filter => filter.id === 'types')){
    types.value = [];
    selected_types.value = [];
    pagination.value.page = 1;
    debouncedGetData(searchInput.value, selectedFilters.value, sortBy.value, sortDesc.value, is_individual.value, types.value);
  } else if (isFilterShown.value.some(filter => filter.id === 'date_range') && !newFilters.some(filter => filter.id === 'date_range')){
    selectedDateRangeArr.value = [];
    date_range.value = {};
    pagination.value.page = 1;
    debouncedGetData(searchInput.value, selectedFilters.value, sortBy.value, sortDesc.value, is_individual.value, types.value);
  }
}

const resetFilters = () => {
  searchInput.value = '';
  pagination.value.page = 1;
  isFilterOpen.value = false;
  selectedFilters.value = []
  statuses.value = []
  types.value = []
  selected_types.value = [];
  isFilterShown.value = [];
  selected_bool.value = []; 
  is_individual.value = null;
  selectedDateRangeArr.value = [];
  date_range.value = {};
  getData();
};

onMounted(async () => {
  await getPermissions();
    if (permissions.value?.can_view) {
    filtersExtra.value.push(
        { name: t('common.date'), id: "date_range" },
        { name: t('customer_service_block.is_individual'), id: "is_individual" }, 
        { name: t('common.status'), id: "status" }, 
        { name: t('common.type'), id: "types" }, 
      );
    filter_is_individual.value = [
      {id: true, name: t("customer_service_block.individual")}, 
      {id: false, name: t("customer_service_block.in_process")}, 
      {id: 'null', name: t("common.all")}]
    getData();
    getFilterStatus();
    getFilterTypes();
    checkRouteQuery();
  } else {
    pending.value = false;
    toast.error(t('common.no_permissions'));
    return navigateTo('/');
  }
});

const checkRouteQuery = () => {
  if (route.query?.id) {
    selectedItemId.value = route.query.id;
    showDetail(route.query.id);
  }
}

const refresh = async () => {
  toggleRegion(false)
  await handleSearch()
}

// Refresca només la taula de fons (sense tancar el panell de detall).
// Es fa servir per accions com "Retornar Carta", on volem que la vista
// de detall es quedi oberta mostrant el nou estat, però la llista de
// darrere també quedi al dia.
const refreshListOnly = async () => {
  await handleSearch()
}

const showDetail = async (id) => {
  await toggleRegion(false)
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
      <H1 class="mb-2">{{ $t('common.comms') }}</H1>

      <div class="flex items-center gap-2">
        <NuxtLink v-if="permissions?.can_add" to="/communication/communications/add" class="button-primary">{{ $t('customer_service_block.new_comm') }}</NuxtLink>
        <span v-if="permissions?.can_view">
          <AtomsDownloadXlsxButton :rows="items" :columns="exportColumns" file-name="comunicacions"
            :total-pages="pagination.totalPages" :server-export-fn="exportCommunications" :sheet-name="$t('common.comms')" />
        </span>
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
      
      <FilterSelect v-if="isFilterShown.some(filter => filter.id === 'date_range')" :datePick="true"
        :filters="selectedDateRangeArr" :placeholder="t('common.date')"
        @update:modelValue="handleDateRangeChange($event)">
        <template #icon>
          <Icon name="fa6-solid:calendar" class="text-md ml-2 mr-1" size="10px" />
        </template>
      </FilterSelect>

      <FilterSelect v-if="isFilterShown.some(filter => filter.id === 'status')" :options="filter_status"
        :filters="selectedFilters" :multiple="true" :placeholder="t(`common.statuses`)"
        @update:modelValue="handleStatusChange($event)">
        <template #icon>
          <Icon name="fa6-solid:ruler-combined" class="text-md ml-2 mr-1" size="10px" />
        </template>
      </FilterSelect>

      <FilterSelect v-if="isFilterShown.some(filter => filter.id === 'types')"
        :options="filter_types" :filters="selected_types" :multiple="true"
        :placeholder="t(`common.type`)" @update:modelValue="handleTypeChange($event)">
        <template #icon>
          <Icon name="fa6-solid:users" class="text-md ml-2 mr-1" size="10px" />
        </template>
      </FilterSelect>

      <FilterSelect v-if="isFilterShown.some(filter => filter.id === 'is_individual')" :options="filter_is_individual"
        :filters="selected_bool" :multiple="false" :placeholder="t(`customer_service_block.individual`)"
        @update:modelValue="handleFilterIndividualChange($event)">
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
      grid-template="80px,200px,300px,150px,100px,100px,100px,80px,80px"
      :pending="pending"
      :loading="pending"
      :error="error"
      :is-empty="items.length === 0"
      @retry="getData">
      <template #header>
        <TableHeader :label="$t('common.date')" sortKey="created_at" :currentSortBy="sortBy" :sortDesc="sortDesc"
          @sort="handleSort" />
        <TableHeader :label="$t('common.identification')" sortKey="token" :currentSortBy="sortBy" :sortDesc="sortDesc"
          @sort="handleSort" />
        <TableHeader :label="$t('customer_service_block.recipient')" :sortable="false" />
        <TableHeader :label="$t('common.status')" sortKey="status" :currentSortBy="sortBy" :sortDesc="sortDesc"
          @sort="handleSort" />
        <TableHeader :label="$t('common.type')" :sortable="false" />
        <TableHeader :label="$t('common.use_type')" :sortable="false" />
        <TableHeader :label="$t('customer_service_block.process')" :sortable="false" />
        <TableHeader :label="$t('customer_service_block.sent')" sortKey="sent_at" :currentSortBy="sortBy" :sortDesc="sortDesc"
          @sort="handleSort" />
        <TableHeader :label="$t('user')" :sortable="false" />
      </template>

      <template #default="{ gridStyle }">
        <div v-for="item in items" :key="item.id"
          class="gap-3 text-base border-b items-center bg-white"
          :style="gridStyle"
          :class="{ 'bg-yellow-50': item.id === selectedItemId }">

          <span class="p-0">{{ formatDate(item.created_at) }}</span>
          <span>
            <button class="group flex justify-between w-full items-center p-1 text-sky-500 text-nowrap text-left"
              @click="showDetail(item.id);">
              <abbr :title="item.token" class="no-underline">{{ item.token }}</abbr>
              <Icon name="fa6-solid:eye"
                class="opacity-0 group-hover:opacity-100 text-slate-500 mr-1 transition-opacity duration-200 ease-in-out" />
            </button>
          </span>
          <span class="p-1 truncate">{{ item.person_name }}</span>
          <span class="p-1">
            <AtomsColorBadge :color="item.status_color" :value="item.status_name" />
          </span>
          <span class="p-1 truncate">{{ item.type_names }}</span>
          <span class="p-1 truncate">{{ item.use_type_name }}</span>
          <span class="p-1 truncate">{{ item.process_token || t('customer_service_block.individual') }}</span>
          <span class="p-1">{{ item.sent_at ? formatDate(item.sent_at) : '-' }}</span>
          <span class="p-1">{{ item.user_username }}</span>
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
    <div class="pl-10 h-full">
      <CommunicationRegion v-if="selectedItemId" :id="selectedItemId" :isSubRegionOpen="isSubRegionOpen" 
      @show-subregion="handleSubRegionEvent" @close-subregion="toggleRegion(false)" @changed="refresh"
      @refresh-list="refreshListOnly" />
    </div>
  </div>

</template>