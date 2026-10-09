<script setup>
import { ref, onMounted, nextTick, computed, watch } from 'vue';
import { useRouter } from 'vue-router';
import debounce from 'lodash.debounce';
import { useI18n } from 'vue-i18n';
import { formatDate } from '~/utils/date';
import FilterSelect from '~/components/atoms/FilterSelect.vue';
import Pagination from '~/components/molecules/Pagination.vue';
import H1 from '~/components/atoms/H1.vue';
import IncidentRegion from '~/components/organisms/IncidentRegion.vue';
import TableHeader from '~/components/atoms/TableHeader.vue';
import IncidentEdit from '~/components/molecules/IncidentEdit.vue';
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
    detail.value = null;
    selectedItemId.value = null;
    editing.value = false;
  }
}

const route = useRoute();
const router = useRouter();
const { $IncidentApiService, $ConfiglistApiService, $DocumentManagerApiService, $apiManager } = useNuxtApp();
const pending = ref(true);
const error = ref(null);
const items = ref([]);
const searchInput = ref('');
const selectedFilters = ref([]);
const selected_types = ref([]);
const filter_status = ref([]);
const filter_type = ref([]);
const sortBy = ref(null);
const sortDesc = ref(false);
const editing = ref(false);

const types = ref([]);

const permissions = ref(null);

const isFilterOpen = ref(false);
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
    const data = await $IncidentApiService.getPermissions();
    permissions.value = data;
  } catch (err) {
    error.value = err;
  }
}

const getData = async (searchQuery = '', filters = [], page = 1, sort = null, desc = false) => {
  if (!permissions.value?.can_view) {
    toast.error(t('common.no_permissions'));
    return navigateTo('/');
  }
  pending.value = true;
  error.value = null;

  try {
    const data = await $IncidentApiService.getAll(searchQuery, filters, page, sort, desc, null, null, types.value);

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
    const data = await $ConfiglistApiService.getAll('notification/incident-status');
    filter_status.value = data.results;
  } catch (err) {
    error.value = err;
  }
}

const getFilterTypes = async () => {
  error.value = null;
  try {
    const data = await $ConfiglistApiService.getAll('notification/incident-type');
    data.results.forEach(item => {
      filter_type.value.push({
        name: item.name,
        id: item.id
      })
    })
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
    filter_type.value = [];
    selected_types.value = [];
    getData();
  }
}

const handleFilterTypeChange = (event) => {
  selected_types.value = event;
  types.value = []
  selected_types.value.forEach(element => {
    types.value.push(element.id);
  })
  pagination.value.page = 1;
  handleSearch();
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

const resetFilters = () => {
  searchInput.value = '';
  pagination.value.page = 1;
  getData();
};

onMounted(async () => {
  await getPermissions();
  if (permissions.value?.can_view) {
    filtersExtra.value.push(
      { name: t("common.type"), id: "type" },
    );
    getData();
    getFilterStatus();
    getFilterTypes();
    checkRouteQuery()
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


const showDetail = async (id) => {
  await toggleRegion(false);
  detail.value = id;
  selectedItemId.value = id;
  toggleRegion(true);
}

const openEdit = () => {
  toggleRegion(false);
  editing.value = true;
  toggleRegion(true);
}

const newIncident = async (id) => {
  toggleRegion(false);
  await getData()
  await nextTick()
  showDetail(id)
}

// Watch for changes in searchInput and selectedFilters and reset pagination to 1
watch([searchInput], () => {
  pagination.value.page = 1;
  handleSearch();
});

const handleSubRegionEvent = (event) => {
  isSubRegionOpen.value = event;
}

const exporting = ref(false);
const exportTaskId = ref(null);

const startExport = async () => {
  exporting.value = true;
  try {
    const response = await $IncidentApiService.exportExcel(
      searchInput.value,
      selectedFilters.value,
      types.value
    );
    if (response && response.task_id) {
      exportTaskId.value = response.task_id;
    } else {
      toast.error(t('common.error_load'));
    }
  } catch (error) {
    console.error('Error starting export:', error);
  } finally {
    exporting.value = false;
  }
};

const handleExportSuccess = async () => {
  if (!exportTaskId.value) return;
  try {
    const response = await $apiManager.checkTask(exportTaskId.value);
    if (response?.state !== 'SUCCESS') {
      exportTaskId.value = null;
      return;
    }
    const result = response?.result;
    const documentId = result?.document_id;
    if (documentId) {
      const file = await $DocumentManagerApiService.viewDocument(documentId);
      const link = document.createElement('a');
      const fileUrl = URL.createObjectURL(file);
      link.href = fileUrl;
      link.download = result?.filename || 'incidents_export.xlsx';
      link.click();
      setTimeout(() => {
        window.URL.revokeObjectURL(fileUrl);
      }, 250);
      toast.success(t('common.correct_download'));
    }
  } catch (error) {
    console.error('Error downloading export document:', error);
  } finally {
    exportTaskId.value = null;
  }
};
watch(() => route.query, () => {
  checkRouteQuery()
}, { immediate: true })
</script>

<template>
  <div id="wrapper" class="text-base">
    <div class="flex justify-between items-center mb-2">
      <H1 class="mb-2">{{ $t('customer_service_block.incident_mngs') }}</H1>
      <div class="flex items-center gap-2">
        <AtomsProcessColorBadge
          v-if="exportTaskId"
          class="w-fit py-1.5 px-3 text-sm"
          :value="`${t('common.loading')}...`"
          color="green"
          :task-id="exportTaskId"
          @refresh="handleExportSuccess"
        />
        <button v-else-if="permissions?.can_view" class="button-secondary flex items-center gap-2" :disabled="exporting" @click="startExport">
          <Icon v-if="exporting" name="fa6-solid:spinner" class="animate-spin" />
          <Icon v-else name="fa6-solid:file-excel" />
          {{ t('common.export') || 'Exportar' }}
        </button>
        <button v-if="permissions?.can_add" class="button-primary" @click="openEdit()">
          {{ t('customer_service_block.new_incident') }}
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
      <span class="flex gap-3" v-if="filter_status.length">
        <label v-for="status in filter_status" :key="status.id"
          class="text-slate-800 text-base flex items-center gap-1">
          <input type="checkbox" v-model="selectedFilters" :value="status.id" @change="handleFilterChange" /> {{
            status.name }}
        </label>
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

      <FilterSelect :options="filter_type" v-if="isFilterShown.some(filter => filter.id === 'type')"
        :filters="selected_types" :multiple="false" :placeholder="t(`common.type`)"
        @update:modelValue="handleFilterTypeChange($event)">
        <template #icon>
          <Icon name="fa6-solid:cube" class="text-slate-500 " />
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
      grid-template="80px,150px,1fr,100px,150px,150px,150px"
      :pending="pending"
      :error="error"
      :is-empty="permissions?.can_view && items.length === 0"
      @retry="getData">
      <template #header>
        <TableHeader :label="$t('common.date')" sortKey="created_at" :currentSortBy="sortBy" :sortDesc="sortDesc"
          @sort="handleSort" />
        <TableHeader :label="$t('common.identification')" sortKey="token" :currentSortBy="sortBy" :sortDesc="sortDesc"
          @sort="handleSort" />
        <TableHeader :label="$t('common.title')" sortKey="name" :currentSortBy="sortBy" :sortDesc="sortDesc"
          @sort="handleSort" />
        <TableHeader :label="$t('common.type')" sortKey="type" :currentSortBy="sortBy" :sortDesc="sortDesc"
          @sort="handleSort" />
        <TableHeader :label="$t('contract')" :sortable="false" />
        <TableHeader :label="$t('common.work_order')" :sortable="false" />
        <TableHeader :label="$t('common.status')" sortKey="status" :currentSortBy="sortBy" :sortDesc="sortDesc"
          @sort="handleSort" />
      </template>

      <template #default="{ gridStyle }">
        <template v-if="permissions?.can_view">
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
            <span class="p-1">{{ item.name }}</span>
            <span class="p-1">{{ item.type_name }}</span>
            <span class="p-1">{{ item.contract_token || '-' }}</span>
            <span class="p-1 truncate">{{ item.order_token || '-' }}</span>
            <span class="p-1">
              <AtomsColorBadge :color="item.status_color" :value="item.status_name" />
            </span>
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
    :class="{ 'translate-x-0': showRegion, 'translate-x-[2000px]': !showRegion, 'w-[95%]': isSubRegionOpen, 'w-[55%]': !isSubRegionOpen }">
    <div id="region_nav" class="mb-3 px-3">
      <button @click="toggleRegion(false)" class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300">
        <Icon name="fa6-solid:angles-right" class="text-slate-500" />
      </button>
    </div>
    <div class="pl-10 h-full">
      <IncidentRegion v-if="detail" :id="detail" :isSubRegionOpen="isSubRegionOpen"
        @show-subregion="handleSubRegionEvent" @changed="getData" @close-subregion="toggleRegion(false)"></IncidentRegion>
      <IncidentEdit v-if="editing" :id="null" @change="newIncident"></IncidentEdit>
    </div>
  </div>

</template>
