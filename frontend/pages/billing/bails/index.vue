<script setup>
import { ref, onMounted, nextTick, computed, watch } from 'vue';
import { useRouter } from 'vue-router';
import debounce from 'lodash.debounce';
import { useI18n } from 'vue-i18n';
import { formatDate } from '~/utils/date';
import { useToast } from 'vue-toastification';
import Pagination from '~/components/molecules/Pagination.vue';
import H1 from '~/components/atoms/H1.vue';
import TableHeader from '~/components/atoms/TableHeader.vue';
import FilterSelect from '~/components/atoms/FilterSelect.vue';
import BailRegion from '~/components/organisms/BailRegion.vue';
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
const { $BailApiService } = useNuxtApp();
const pending = ref(true);
const error = ref(null);
const items = ref([]);
const searchInput = ref('');
const filter_status = ref([]);
const selectedFilters = ref([]);
const filter_contract_status = ref([]);
const selectedContractStatuses = ref([]);
const selectedContractStatusFilters = computed(() => selectedContractStatuses.value.map(status => status.id));
const sortBy = ref(null);
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
    const data = await $BailApiService.getPermissions();
    permissions.value = data;
  } catch (err) {
    error.value = err;
  }
}

const getData = async (searchQuery = '', filters = [], page = 1, sort = null, desc = false, contractStatusFilters = []) => {
  if (!permissions.value?.can_view) {
    toast.error(t('common.no_permissions'));
    return navigateTo('/');
  }
  pending.value = true;
  error.value = null;
  try {
    const data = await $BailApiService.getAll(searchQuery, filters, page, sort, desc, contractStatusFilters);
    items.value = data.results;
    Object.assign(pagination.value, {
      total: data.count,
      totalPages: Math.ceil(data.count / pagination.value.perPage),
      previous: data.previous,
      next: data.next,
      isFiltered: String(searchQuery).trim() !== '' || filters.length > 0 || contractStatusFilters.length > 0
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
    const data = await $BailApiService.getFilterStatus();
    filter_status.value = data;
    handleSearch();
  } catch (err) {
    error.value = err;
  }
}

const getFilterContractStatus = async () => {
  error.value = null;
  try {
    const data = await $BailApiService.getFilterContractStatus();
    filter_contract_status.value = data;
  } catch (err) {
    error.value = err;
  }
}

const debouncedGetData = debounce((query, filters, sort, desc, contractStatusFilters) => {
  getData(query, filters, pagination.value.page, sort, desc, contractStatusFilters);
}, 300);

const handleSearch = () => {
  pagination.value.page = 1;
  debouncedGetData(searchInput.value, selectedFilters.value, sortBy.value, sortDesc.value, selectedContractStatusFilters.value);
}

const handleFilterChange = () => {
  pagination.value.page = 1;
  handleSearch();
}

const handleContractStatusChange = (statuses) => {
  selectedContractStatuses.value = statuses;
  handleFilterChange();
}

const handlePageChange = (newPage) => {
  pagination.value.page = newPage;
  getData(searchInput.value, selectedFilters.value, newPage, sortBy.value, sortDesc.value, selectedContractStatusFilters.value);
}

const handleSort = (key) => {
  if (sortBy.value === key) {
    sortDesc.value = !sortDesc.value;
  } else {
    sortBy.value = key;
    sortDesc.value = false;
  }
  getData(searchInput.value, selectedFilters.value, pagination.value.page, sortBy.value, sortDesc.value, selectedContractStatusFilters.value);
}

const onChangeRegion = async () => {
  await getData(searchInput.value, selectedFilters.value, pagination.value.page, sortBy.value, sortDesc.value, selectedContractStatusFilters.value);
}

const exportColumns = computed(() => [
  { header: t('common.date'), value: (row) => row.created_at ? formatDate(row.created_at) : '', key: 'created_at' },
  { header: t('common.identification'), value: (row) => row.token, key: 'token' },
  { header: t('common.status'), value: (row) => row.status_name, key: 'status' },
  { header: t('contract'), value: (row) => row.contract_token, key: 'contract' },
  { header: t('contract_block.holder'), value: (row) => [row.contract_holder, row.contract_holder_surname].filter(Boolean).join(' ') },
  { header: t('billing_block.contract_status'), value: (row) => row.contract_status_name, key: 'contract_status' },
  { header: t('product'), value: (row) => row.product_name, key: 'product' },
  { header: t('common.amount'), value: (row) => Number(row.amount ?? 0), key: 'amount' },
  { header: t('common.returned'), value: (row) => row.return_date ? formatDate(row.return_date) : '', key: 'return_date' },
]);

const exportBails = (columns) => $BailApiService.exportData(searchInput.value, selectedFilters.value, sortBy.value, sortDesc.value, columns, selectedContractStatusFilters.value);

const resetFilters = () => {
  searchInput.value = '';
  selectedFilters.value = [];
  selectedContractStatuses.value = [];
  pagination.value.page = 1;
  getData();
};

onMounted(async () => {
  await getPermissions();
  if (permissions.value?.can_view) {
    getData();
    getFilterStatus();
    getFilterContractStatus();
    checkRouteQuery()
  } else {
    toast.error(t('common.no_permissions'));
    pending.value = false;
    return navigateTo('/');
  }
});

const checkRouteQuery = () => {
  if (route.query?.action == 'showDetail') {
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
      <H1 class="mb-2">{{ $t('common.bails') }}</H1>
      <span>
        <AtomsDownloadXlsxButton :rows="items" :columns="exportColumns" file-name="bails"
          :total-pages="pagination.totalPages" :server-export-fn="exportBails" />
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

      <FilterSelect :plain="true" :options="filter_contract_status" :filters="selectedContractStatuses"
        :multiple="true" :placeholder="$t('billing_block.contract_status')"
        @update:modelValue="handleContractStatusChange($event)">
        <template #icon>
          <Icon name="fa6-solid:file-contract" class="text-md ml-2 mr-1" size="10px" />
        </template>
      </FilterSelect>

      <span>
        <button id="filterReset" name="form_filter" type="button" class="px-2 py-1 hover:bg-slate-300 rounded"
          @click="resetFilters" title="reset">
          <Icon name="fa6-solid:rotate-right" class="text-slate-500" />
        </button>
      </span>
    </form>
    <DataTable
      grid-template="80px,120px,150px,150px,200px,80px,150px,100px,150px"
      :pending="pending"
      :error="error"
      :is-empty="items.length === 0"
      @retry="getData">
      <template #header>
        <TableHeader :label="$t('common.date')" sortKey="created_at" :currentSortBy="sortBy" :sortDesc="sortDesc"
          @sort="handleSort" />
        <TableHeader :label="$t('common.identification')" sortKey="token" :currentSortBy="sortBy" :sortDesc="sortDesc"
          @sort="handleSort" />
        <TableHeader :label="$t('common.status')" sortKey="status" :currentSortBy="sortBy" :sortDesc="sortDesc"
          @sort="handleSort" />
        <TableHeader :label="$t('contract')" :sortable="false" />
        <TableHeader :label="$t('contract_block.holder')" :sortable="false" />
        <TableHeader :label="$t('billing_block.contract_status')" :sortable="false" />
        <TableHeader :label="$t('product')" :sortable="false" />
        <TableHeader :label="$t('common.amount')" sortKey="amount" :currentSortBy="sortBy" :sortDesc="sortDesc"
          @sort="handleSort" />
        <TableHeader :label="$t('common.returned')" sortKey="return_date" :currentSortBy="sortBy" :sortDesc="sortDesc"
          @sort="handleSort" />
      </template>

      <template #default="{ gridStyle }">
        <div v-for="item in items" :key="item.id"
          class="gap-3 text-base border-b items-center bg-white group"
          :style="gridStyle"
          :class="{ 'bg-yellow-50': item.id === selectedItemId }">
          <span class="p-0">{{ item.created_at ? formatDate(item.created_at) : '-' }}</span>
          <span>
            <button class="group flex justify-between w-full items-center p-1 text-sky-500 text-nowrap text-left"
              @click="showDetail(item.id);">
              <abbr :title="item.id" class="no-underline">{{ item.token }}</abbr>
              <Icon name="fa6-solid:eye"
                class="opacity-0 group-hover:opacity-100 text-slate-500 mr-1 transition-opacity duration-200 ease-in-out" />
            </button>
          </span>
          <span class="p-1">
            <AtomsColorBadge :value="item.status_name" :color="item.status_color" />
          </span>
          <span class="p-0">{{ item.contract_token }}</span>
          <span class="p-0">{{ item.contract_holder }} {{ item.contract_holder_surname }}</span>
          <span class="p-1">
            <AtomsColorBadge :value="item.contract_status_name" :color="item.contract_status_color" />
          </span>
          <span class="p-0">{{ item.product_name }}</span>
          <span class="p-0">{{ item.amount }}</span>
          <span class="p-0">{{ item.return_date ? formatDate(item.return_date) : '-' }}</span>
        </div>
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
      <BailRegion v-if="detail" :id="detail" :isSubRegionOpen="isSubRegionOpen" @show-subregion="handleSubRegionEvent"
        @changed="onChangeRegion" @close-subregion="toggleRegion(false)" />
    </div>
  </div>

</template>
