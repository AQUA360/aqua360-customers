<script setup>
import { ref, onMounted, nextTick, computed, watch, onUnmounted } from 'vue';
import { useRouter } from 'vue-router';
import debounce from 'lodash.debounce';
import { useI18n } from 'vue-i18n';
import { formatDate } from '~/utils/date';
import FilterSelect from '~/components/atoms/FilterSelect.vue';
import Pagination from '~/components/molecules/Pagination.vue';
import H1 from '~/components/atoms/H1.vue';
import MeterRegion from '~/components/organisms/MeterRegion.vue';
import TableHeader from '~/components/atoms/TableHeader.vue';
import { useToast } from 'vue-toastification';
import { remoteTypeOptions } from '~/utils/service';
import DataTable from '~/components/organisms/DataTable.vue';
import MeterLookupModal from '~/components/molecules/MeterLookupModal.vue';
import MeterBulkUpdateModal from '~/components/molecules/MeterBulkUpdateModal.vue';

const LOOKUP_CODES_KEY = 'meter_lookup_codes';

const { t } = useI18n();
const toast = useToast();
const showRegion = ref(false);

const selectedItemId = ref(null);
const isSubRegionOpen = ref(false);
const toggleRegion = (force) => {
  showRegion.value = force !== undefined ? force : !showRegion.value;
  if (showRegion.value == false) {
    isSubRegionOpen.value = false;
    supplyPointRegion.value = null
    selectedItemId.value = null
  }
}

const router = useRouter();
const route = useRoute()
const { $MeterApiService, $ConfigProjectApiService, $apiManager, $DocumentManagerApiService } = useNuxtApp();
const pending = ref(true);
const error = ref(null);
const items = ref([]);
const searchInput = ref('');
const searchByAddress = ref('');
const filter_status = ref([]);
const selectedFilters = ref([]);
const sortBy = ref('code');
const sortDesc = ref(false);
const permissions = ref(null);
const filter_is_property = ref([]);
const filter_is_general = ref([]);
const filter_is_compound = ref([]);
const is_property = ref(null);
const is_compound = ref(null);
const is_general = ref(null);
const selected_bool_property = ref([]);
const selected_bool_compound = ref([]);
const selected_bool_general = ref([]);
const filter_remote_reading_type = ref([]);
const selected_remote_reading_type = ref([]);
const remote_reading_type = ref(null);
const filter_has_remote_reading = ref([]);
const selected_has_remote_reading = ref([]);
const has_remote_reading = ref(null);

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
    const data = await $MeterApiService.getPermissions();
    permissions.value = data;
  } catch (err) {
    error.value = err;
  }
}

const checkRouteQuery = () => {
  if (route.query?.action == 'showDetail' || route.query?.id) {
    toggleRegion(false);
    showSupplyPointRegion(route.query.id)
  }
}

const supplyPointRegion = ref(null);

const showSupplyPointRegion = async (id) => {
  await toggleRegion(false);
  supplyPointRegion.value = id;
  selectedItemId.value = id;
  toggleRegion(true);
}

const handleSubRegionEvent = (event) => {
  isSubRegionOpen.value = event;
}

const getData = async (searchQuery = '', filters = [], page = 1, sort = 'code', desc = false, searchByAddressQuery = '') => {
  if (!permissions.value?.can_view) {
    toast.error(t('common.no_permissions'));
    return navigateTo('/');
  }
  pending.value = true;
  error.value = null;

  try {
    const data = await $MeterApiService.getData(
      searchQuery,
      filters,
      page,
      sort,
      desc,
      false,                 // noSupplyPoint
      null,                  // exclude
      is_property.value,
      is_compound.value,
      is_general.value,
      searchByAddressQuery,
      remote_reading_type.value,
      has_remote_reading.value
    );

    items.value = data.results;
    Object.assign(pagination.value, {
      total: data.count,
      totalPages: Math.ceil(data.count / pagination.value.perPage),
      previous: data.previous,
      next: data.next,
      isFiltered: String(searchQuery).trim() !== '' || filters.length > 0 || String(searchByAddressQuery).trim() !== '' || remote_reading_type.value != null || has_remote_reading.value !== null
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
    const data = await $MeterApiService.getFilterStatus();
    filter_status.value = data;
  } catch (err) {
    error.value = err;
  }

  try {
    const data = await $ConfigProjectApiService.get('meter_default_status_filter_token')
    if (data) {
      selectedFilters.value.push(filter_status.value.filter(f => f.token == data)[0].id)
    }
  } catch (err) {
    console.log('Meter Status Default Filter could not be established')
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

const handleFiltersSelectChange = (event) => {
  let newFilters = event
    .filter(el => !isFilterShown.value.includes(el.id));

  checkInAdvacedFilters(newFilters)
  isFilterShown.value = [];
  isFilterShown.value = [...isFilterShown.value, ...newFilters];
}

const checkInAdvacedFilters = (newFilters) => {
  if (isFilterShown.value.some(filter => filter.id === 'is_property') && !newFilters.some(filter => filter.id === 'is_property')) {
    is_property.value = null;
    getData();
  } else if (isFilterShown.value.some(filter => filter.id === 'is_compound') && !newFilters.some(filter => filter.id === 'is_compound')) {
    is_compound.value = null;
    getData();
  } else if (isFilterShown.value.some(filter => filter.id === 'is_general') && !newFilters.some(filter => filter.id === 'is_general')) {
    is_general.value = null;
    getData();
  } else if (isFilterShown.value.some(filter => filter.id === 'remote_reading_type') && !newFilters.some(filter => filter.id === 'remote_reading_type')) {
    remote_reading_type.value = null;
    getData();
  } else if (isFilterShown.value.some(filter => filter.id === 'has_remote_reading') && !newFilters.some(filter => filter.id === 'has_remote_reading')) {
    has_remote_reading.value = null;
    getData();
  }
}

const handleFilterPropertyChange = (event) => {
  selected_bool_property.value = event;
  is_property.value = event[0].id;
  handleSearch();
}

const handleFilterCompoundChange = (event) => {
  selected_bool_compound.value = event;
  is_compound.value = event[0].id;
  handleSearch();
}

const handleFilterGeneralChange = (event) => {
  selected_bool_general.value = event;
  is_general.value = event[0].id;
  handleSearch();
}

const handleFilterRemoteReadingTypeChange = (event) => {
  selected_remote_reading_type.value = event;
  remote_reading_type.value = event[0]?.id ?? null;
  handleSearch();
}

const handleFilterHasRemoteReadingChange = (event) => {
  selected_has_remote_reading.value = event;
  has_remote_reading.value = event[0]?.id ?? null;
  handleSearch();
}

const exportColumns = computed(() => [
  { header: t('common.code'), value: (row) => row.code, key: 'code' },
  { header: t('supply_point'), value: (row) => row.supply_point, key: 'supply_point' },
  { header: t('common.exploitation'), value: (row) => row.exploitation_name || '', key: 'exploitation' },
  { header: t('common.status'), value: (row) => row.status_name, key: 'status' },
  { header: t('service_block.install_date'), value: (row) => row.installation_at ? formatDate(row.installation_at) : '', key: 'installation_at' },
  { header: t('service_block.short_uninstall_date'), value: (row) => row.uninstallation_at ? formatDate(row.uninstallation_at) : '', key: 'uninstallation_at' },
  { header: t('service_block.telecontrol'), value: (row) => row.has_remote_reading ? t('common.yes') : t('common.no'), key: 'has_remote_reading' },
  { header: t('service_block.manufacturer'), value: (row) => row.manufacturer || '', key: 'manufacturer' },
  { header: t('service_block.manufacturing_year'), value: (row) => row.manufacturing_year || '', key: 'manufacturing_year' },
  { header: t('service_block.tech'), value: (row) => row.comm_technology || '', key: 'comm_technology' },
  { header: t('service_block.caliber'), value: (row) => row.caliber_token || '', key: 'caliber' },
]);

const exportMeters = (columns) => $MeterApiService.exportData(
  searchInput.value, selectedFilters.value, sortBy.value, sortDesc.value,
  false, null, is_property.value, is_compound.value, is_general.value,
  searchByAddress.value, remote_reading_type.value, has_remote_reading.value,
  columns,
);

const resetFilters = () => {
  searchInput.value = '';
  searchByAddress.value = '';
  selectedFilters.value = [];
  isFilterShown.value = [];
  selected_bool_compound.value = [];
  selected_bool_property.value = [];
  selected_bool_general.value = [];
  selected_remote_reading_type.value = [];
  selected_has_remote_reading.value = [];
  is_compound.value = null;
  is_property.value = null;
  is_general.value = null;
  remote_reading_type.value = null;
  has_remote_reading.value = null;
  pagination.value.page = 1;
  isFilterOpen.value = false;
  showAddressSearch.value = false;
  getData();
};

onMounted(async () => {
  await getPermissions();
  if (!permissions.value?.can_view) {
    pending.value = false;
    toast.error(t('No teniu permisos per veure aquesta pàgina'));
    return navigateTo('/');
  }
  filtersExtra.value.push(
    { name: t("service_block.is_property"), id: "is_property" },
    { name: t("service_block.is_general"), id: "is_general" },
    { name: t("service_block.is_compound"), id: "is_compound" },
    { name: t("service_block.remote_type"), id: "remote_reading_type" },
    { name: t("service_block.telecontrol"), id: "has_remote_reading" }
  );
  await getFilterStatus();
  filter_is_property.value = [{ id: true, name: t("service_block.is_property") }, { id: false, name: t("service_block.no_property") }]
  filter_is_compound.value = [{ id: true, name: t("service_block.is_compound") }, { id: false, name: t("service_block.no_compound") }]
  filter_is_general.value = [{ id: true, name: t("service_block.is_general") }, { id: false, name: t("service_block.no_general") }]
  filter_remote_reading_type.value = remoteTypeOptions.map(({ code, label }) => ({ id: code, name: label }));
  filter_has_remote_reading.value = [
    { id: 0, name: t('service_block.no_remote_reading') },
    { id: 1, name: t('service_block.ever_remote_reading') },
    { id: 2, name: t('service_block.current_remote_reading') },
  ];
  getData('', selectedFilters.value);

  checkRouteQuery();
});

// Watch for changes in searchInput and reset pagination to 1
watch(searchInput, () => {
  pagination.value.page = 1;
  handleSearch();
});

const downloadingCsv = ref(false);
const csvExportProgress = ref(0);
const csvExportTaskId = ref(null);
let csvExportInterval = null;

onUnmounted(() => {
  if (csvExportInterval) {
    clearInterval(csvExportInterval);
  }
});

const exportCsv = async () => {
  if (downloadingCsv.value) return;
  downloadingCsv.value = true;
  csvExportProgress.value = 0;

  try {
    const response = await $MeterApiService.exportCsv(
      searchInput.value,
      selectedFilters.value,
      sortBy.value,
      sortDesc.value,
      is_property.value,
      is_compound.value,
      is_general.value
    );

    if (response && response.task_id) {
      csvExportTaskId.value = response.task_id;

      csvExportInterval = setInterval(async () => {
        try {
          const res = await $apiManager.checkTask(csvExportTaskId.value);
          if (res) {
            if (res.state === 'PENDING' || res.state === 'RUNNING') {
              csvExportProgress.value = res.percent || 0;
            } else if (res.state === 'SUCCESS') {
              clearInterval(csvExportInterval);
              csvExportProgress.value = 100;

              if (res.result && res.result.document_id) {
                const fileBlob = await $DocumentManagerApiService.viewDocument(res.result.document_id);
                const url = window.URL.createObjectURL(fileBlob);
                const a = document.createElement("a");
                a.href = url;
                a.download = res.result.filename || `meters_${new Date().toISOString().slice(0, 10).replace(/-/g, '')}.csv`;
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
                window.URL.revokeObjectURL(url);
                toast.success(t('common.export_completed') || 'Exportació completada');
              } else {
                toast.error(t('common.export_error') || 'Error en l\'exportació');
              }
              downloadingCsv.value = false;
              csvExportTaskId.value = null;
            } else if (res.state === 'FAILURE') {
              clearInterval(csvExportInterval);
              const errMsg = res.error || t('common.export_error') || 'Error en l\'exportació';
              toast.error(errMsg);
              downloadingCsv.value = false;
              csvExportTaskId.value = null;
            }
          }
        } catch (pollErr) {
          clearInterval(csvExportInterval);
          console.error(pollErr);
          toast.error(t('common.export_error') || 'Error en l\'exportació');
          downloadingCsv.value = false;
          csvExportTaskId.value = null;
        }
      }, 2000);
    } else {
      throw new Error('No s\'ha rebut task_id');
    }
  } catch (err) {
    console.error(err);
    toast.error(t('common.export_error') || 'Error en l\'exportació');
    downloadingCsv.value = false;
    csvExportTaskId.value = null;
  }
};
watch(() => route.query, () => {
  checkRouteQuery()
}, { immediate: true })

const showLookupModal = ref(false);
const lookupModalRef = ref(null);
const showBulkUpdateModal = ref(false);

const handleLookupSearch = (codesList) => {
  if (!codesList?.length) return;
  sessionStorage.setItem(LOOKUP_CODES_KEY, JSON.stringify(codesList));
  lookupModalRef.value?.setSearching(false);
  showLookupModal.value = false;
  navigateTo('/service/meters/lookup');
};

const handleBulkUpdateDone = () => {
  getData(
    searchInput.value,
    selectedFilters.value,
    pagination.value.page,
    sortBy.value,
    sortDesc.value,
    searchByAddress.value
  );
};
</script>

<template>
  <div id="wrapper" class="text-base">
    <div class="flex justify-between items-center mb-2">
      <H1>{{ $t('common.meters') }}</H1>
      <div class="flex gap-2">
        <NuxtLink v-if="permissions?.can_add" to="/service/meters/add" class="button-primary">{{
          $t('service_block.new_meter') }}</NuxtLink>
        <button v-if="permissions?.can_change" class="button-default flex items-center gap-1.5"
          @click="showBulkUpdateModal = true" :title="$t('service_block.meter_bulk_update_title')">
          <Icon name="fa6-solid:file-import" class="text-slate-500" />
        </button>
        <button class="button-default flex items-center gap-1.5" @click="showLookupModal = true"
          :title="$t('service_block.meter_lookup_title')">
          <Icon name="fa6-solid:magnifying-glass" class="text-slate-500" />
        </button>
        <button class="button-default flex items-center gap-1.5" @click="exportCsv" :disabled="downloadingCsv"
          title="Exportar">
          <Icon :name="downloadingCsv ? 'fa6-solid:spinner' : 'fa6-solid:file-csv'" class="text-slate-500"
            :class="{ 'animate-spin': downloadingCsv }" />
          <span v-if="downloadingCsv" class="text-xs text-slate-500 font-semibold">
            {{ csvExportProgress }}%
          </span>
        </button>
        <span>
          <AtomsDownloadXlsxButton :rows="items" :columns="exportColumns" file-name="meters"
            :total-pages="pagination.totalPages" :server-export-fn="exportMeters" />
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
        <button id="filterAddress" name="form_filter" type="button" class="px-2 py-1 hover:bg-slate-300 rounded"
          :class="{ 'bg-slate-300': showAddressSearch }" @click="toggleAddressFilter"
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

      <FilterSelect v-if="isFilterShown.some(filter => filter.id === 'is_property')" :options="filter_is_property"
        :filters="selected_bool_property" :multiple="false" :placeholder="t(`service_block.is_property`)"
        @update:modelValue="handleFilterPropertyChange($event)">
        <template #icon>
          <Icon name="fa6-solid:circle-check" class="text-md ml-2 mr-1" size="10px" />
        </template>
      </FilterSelect>

      <FilterSelect v-if="isFilterShown.some(filter => filter.id === 'is_compound')" :options="filter_is_compound"
        :filters="selected_bool_compound" :multiple="false" :placeholder="t(`service_block.is_compound`)"
        @update:modelValue="handleFilterCompoundChange($event)">
        <template #icon>
          <Icon name="fa6-solid:circle-check" class="text-md ml-2 mr-1" size="10px" />
        </template>
      </FilterSelect>

      <FilterSelect v-if="isFilterShown.some(filter => filter.id === 'is_general')" :options="filter_is_general"
        :filters="selected_bool_general" :multiple="false" :placeholder="t(`service_block.is_general`)"
        @update:modelValue="handleFilterGeneralChange($event)">
        <template #icon>
          <Icon name="fa6-solid:circle-check" class="text-md ml-2 mr-1" size="10px" />
        </template>
      </FilterSelect>

      <FilterSelect v-if="isFilterShown.some(filter => filter.id === 'remote_reading_type')"
        :options="filter_remote_reading_type" :filters="selected_remote_reading_type" :multiple="false"
        :placeholder="t(`service_block.remote_type`)" @update:modelValue="handleFilterRemoteReadingTypeChange($event)">
        <template #icon>
          <Icon name="fa6-solid:circle-check" class="text-md ml-2 mr-1" size="10px" />
        </template>
      </FilterSelect>

      <FilterSelect v-if="isFilterShown.some(filter => filter.id === 'has_remote_reading')"
        :options="filter_has_remote_reading" :filters="selected_has_remote_reading" :multiple="false"
        :placeholder="t(`service_block.telecontrol`)" @update:modelValue="handleFilterHasRemoteReadingChange($event)">
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
      grid-template="106px,200px,150px,120px,125px,100px,80px,100px,80px,100px,80px"
      :pending="pending"
      :error="error"
      :is-empty="items.length === 0"
      @retry="getData">
      <template #header>
        <TableHeader :label="$t('common.code')" sortKey="code" :currentSortBy="sortBy" :sortDesc="sortDesc"
          @sort="handleSort" />
        <TableHeader :label="$t('supply_point')" sortKey="supply_point_address" :currentSortBy="sortBy"
          :sortDesc="sortDesc" @sort="handleSort" />
        <TableHeader :label="$t('common.exploitation')" sortKey="exploitation_name" :currentSortBy="sortBy"
          :sortDesc="sortDesc" @sort="handleSort" />
        <TableHeader :label="$t('common.status')" sortKey="status_name" :currentSortBy="sortBy" :sortDesc="sortDesc"
          @sort="handleSort" />
        <TableHeader :label="$t('service_block.install_date')" sortKey="installation_at" :currentSortBy="sortBy" :sortDesc="sortDesc"
          @sort="handleSort" />
        <TableHeader :label="$t('service_block.short_uninstall_date')" sortKey="uninstallation_at" :currentSortBy="sortBy"
          :sortDesc="sortDesc" @sort="handleSort" />
        <TableHeader :label="$t('service_block.telecontrol')" sortKey="has_remote_reading" :currentSortBy="sortBy"
          :sortDesc="sortDesc" @sort="handleSort" />
        <TableHeader :label="$t('service_block.manufacturer')" sortKey="manufacturer" :currentSortBy="sortBy"
          :sortDesc="sortDesc" @sort="handleSort" />
        <TableHeader :label="$t('service_block.manufacturing_year')" sortKey="manufacturing_year" :currentSortBy="sortBy"
          :sortDesc="sortDesc" @sort="handleSort" />
        <TableHeader :label="$t('service_block.tech')" sortKey="comm_technology" :currentSortBy="sortBy"
          :sortDesc="sortDesc" @sort="handleSort" />
        <TableHeader :label="$t('service_block.caliber')" sortKey="caliber_token" :currentSortBy="sortBy"
          :sortDesc="sortDesc" @sort="handleSort" />
      </template>

      <template #default="{ gridStyle }">
        <div v-for="item in items" :key="item.id"
          class="gap-3 text-base border-b items-center bg-white"
          :style="gridStyle"
          :class="{ 'bg-yellow-50': item.id === selectedItemId }">
          <span>
            <button class="group flex justify-between w-full items-center p-1 text-sky-500 text-nowrap text-left"
              @click="showSupplyPointRegion(item.id);">
              <abbr :title="item.code" class="no-underline">{{ item.code }}</abbr>
              <Icon name="fa6-solid:eye"
                class="opacity-0 group-hover:opacity-100 text-slate-500 mr-1 transition-opacity duration-200 ease-in-out" />
            </button>
          </span>
          <span class="p-0 flex truncate items-center min-w-0" :title="item.supply_point">
            <AtomsCircleBadge :color="item.supply_point_status_color" class="flex-shrink-0"></AtomsCircleBadge>
            <span class="truncate ml-1">{{ item.supply_point }}</span>
          </span>
          <span class="p-1 truncate text-nowrap" :title="item.exploitation_name || ''">{{ item.exploitation_name || '-' }}</span>
          <span class="p-1 truncate">
            <AtomsColorBadge :value="item.status_name" :color="item.status_color"></AtomsColorBadge>
          </span>
          <span class="p-1 text-nowrap">{{ item.installation_at ? formatDate(item.installation_at) : '-' }}</span>
          <span class="p-1 text-nowrap">{{ item.uninstallation_at ? formatDate(item.uninstallation_at) : '-' }}</span>
          <span class="p-1 text-nowrap">
            <Icon v-if="item.has_remote_reading" name="fa6-solid:circle-check" class="text-green-500" />
            <span v-else>-</span>
          </span>
          <span class="p-1 text-nowrap">{{ item.manufacturer || '-' }}</span>
          <span class="p-1 text-nowrap">{{ item.manufacturing_year || '-' }}</span>
          <span class="p-1 text-nowrap">{{ item.comm_technology || '-' }}</span>
          <span class="p-1 text-nowrap">{{ item.caliber_token || '-' }}</span>
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
      <button @click="toggleRegion(false)" class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300">
        <Icon name="fa6-solid:angles-right" class="text-slate-500" />
      </button>
    </div>
    <div class="pl-10 h-full">
      <MeterRegion v-if="supplyPointRegion" :id="supplyPointRegion" :isSubRegionOpen="isSubRegionOpen"
        @show-subregion="handleSubRegionEvent" @close-subregion="toggleRegion(false)"></MeterRegion>
    </div>
  </div>

  <MeterLookupModal ref="lookupModalRef" v-model:open="showLookupModal" @search="handleLookupSearch" />
  <MeterBulkUpdateModal v-model:open="showBulkUpdateModal" @done="handleBulkUpdateDone" />

</template>
