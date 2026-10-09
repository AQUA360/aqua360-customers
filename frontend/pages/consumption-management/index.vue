<script setup>
import { ref, computed, nextTick, watch, onMounted } from 'vue';
import debounce from 'lodash.debounce';
import { useI18n } from 'vue-i18n';
import { formatDate } from '~/utils/date';
import { useToast } from 'vue-toastification';
import Pagination from '~/components/molecules/Pagination.vue';
import H1 from '~/components/atoms/H1.vue';
import TableHeader from '~/components/atoms/TableHeader.vue';
import DataTable from '~/components/organisms/DataTable.vue';
import ContractRegion from '~/components/organisms/ContractRegion.vue';
import { usePermissions } from '~/middleware/permission';

const { t } = useI18n();
const toast = useToast();

const { $ConsumptionManagementApiService, $BillingApiService } = useNuxtApp();
const { permissions, loading: permissionsLoading } = usePermissions();
const pending = ref(true);
const error = ref(null);
const items = ref([]);
const searchInput = ref('');
const selectedTypes = ref([]);
const sortBy = ref(null);
const sortDesc = ref(false);
const activeMode = ref('current');

const selectedBillingBatch = ref(null);
const billingOptions = ref([]);
const loadingBillings = ref(false);

const showRegion = ref(false);
const selectedItemId = ref(null);
const isSubRegionOpen = ref(false);

const TYPE_FILTERS = [
  { value: 'fire_hydrant',          label: 'consumption_management.type_fire_hydrant' },
  { value: 'inactive_consumption',  label: 'consumption_management.type_inactive_consumption' },
  { value: 'duplicate_readings',    label: 'consumption_management.type_duplicate_readings' },
];

const TYPE_COLORS = {
  fire_hydrant:         { bg: 'bg-red-100',    text: 'text-red-700',    border: 'border-red-300' },
  inactive_consumption: { bg: 'bg-orange-100', text: 'text-orange-700', border: 'border-orange-300' },
  duplicate_readings:   { bg: 'bg-yellow-100', text: 'text-yellow-700', border: 'border-yellow-300' },
};

const pagination = ref({
  page: 1,
  perPage: 50,
  total: 0,
  totalPages: 0,
  previous: null,
  next: null,
  isFiltered: false,
});

const canView = computed(() => permissions.value?.permissions?.view_contract ?? false);

const loadBillings = async () => {
  loadingBillings.value = true;
  try {
    const data = await $BillingApiService.getAll('', [], 1, null, false);
    billingOptions.value = data.results || [];
  } catch (e) {
    console.error('Error loading billings:', e);
  } finally {
    loadingBillings.value = false;
  }
};

const getData = async (searchQuery = '', types = [], page = 1, sort = null, desc = false) => {
  if (!canView.value) {
    toast.error(t('common.no_permissions'));
    return navigateTo('/');
  }
  pending.value = true;
  error.value = null;

  const typeParam = types.length === 1 ? types[0] : null;

  try {
    const data = await $ConsumptionManagementApiService.getAll(searchQuery, typeParam, page, sort, desc, activeMode.value, selectedBillingBatch.value);

    items.value = data.results;
    Object.assign(pagination.value, {
      total: data.count,
      totalPages: Math.ceil(data.count / pagination.value.perPage),
      previous: data.previous,
      next: data.next,
      isFiltered: String(searchQuery).trim() !== '' || types.length > 0,
    });

    nextTick(() => {
      document.getElementById('searchInput')?.focus();
    });
  } catch (err) {
    error.value = err;
  } finally {
    pending.value = false;
  }
};

const handleSearch = () => {
  pagination.value.page = 1;
  getData(searchInput.value, selectedTypes.value, 1, sortBy.value, sortDesc.value);
};

const debouncedSearch = debounce(handleSearch, 300);

const handlePageChange = (newPage) => {
  pagination.value.page = newPage;
  getData(searchInput.value, selectedTypes.value, newPage, sortBy.value, sortDesc.value);
};

const handleSort = (key) => {
  if (sortBy.value === key) {
    sortDesc.value = !sortDesc.value;
  } else {
    sortBy.value = key;
    sortDesc.value = false;
  }
  getData(searchInput.value, selectedTypes.value, pagination.value.page, sortBy.value, sortDesc.value);
};

const exportColumns = computed(() => [
  { header: t('consumption_management.type'), value: (row) => row.type_display, key: 'type' },
  { header: t('contract'), value: (row) => row.contract_token, key: 'contract' },
  { header: t('common.holder'), value: (row) => row.holder_name, key: 'holder' },
  { header: t('supply_point'), value: (row) => row.supply_point_address },
  { header: t('consumption_management.consumption'), value: (row) => row.readings_in_period !== null ? row.readings_in_period : (row.consumption !== null ? row.consumption : '') },
  { header: t('consumption_management.reading_date'), value: (row) => row.period_start && row.period_end ? `${formatDate(row.period_start)} - ${formatDate(row.period_end)}` : (row.reading_date ? formatDate(row.reading_date) : '') },
]);

const exportConsumptionManagement = (columns) => {
  const typeParam = selectedTypes.value.length === 1 ? selectedTypes.value[0] : null;
  return $ConsumptionManagementApiService.exportData(searchInput.value, typeParam, sortBy.value, sortDesc.value, activeMode.value, selectedBillingBatch.value, columns);
};

const resetFilters = () => {
  searchInput.value = '';
  selectedTypes.value = [];
  selectedBillingBatch.value = null;
  pagination.value.page = 1;
  getData();
};

const switchMode = (mode) => {
  if (activeMode.value === mode) return;
  activeMode.value = mode;
  searchInput.value = '';
  selectedTypes.value = [];
  selectedBillingBatch.value = null;
  pagination.value.page = 1;
  if (mode === 'history' && billingOptions.value.length === 0) {
    loadBillings();
  }
  getData();
};

const handleBillingBatchChange = () => {
  pagination.value.page = 1;
  getData(searchInput.value, selectedTypes.value, 1, sortBy.value, sortDesc.value);
};

const toggleRegion = (force) => {
  showRegion.value = force !== undefined ? force : !showRegion.value;
  if (!showRegion.value) {
    selectedItemId.value = null;
    isSubRegionOpen.value = false;
  }
};

const showDetail = (contractId) => {
  toggleRegion(false);
  selectedItemId.value = contractId;
  toggleRegion(true);
};

const handleSubRegionEvent = (event) => {
  isSubRegionOpen.value = event;
};

const route = useRoute();

onMounted(() => {
  const billingBatchParam = route.query.billing_batch;
  if (billingBatchParam) {
    selectedBillingBatch.value = Number(billingBatchParam);
    activeMode.value = 'history';
    loadBillings();
  }
});

watch(permissionsLoading, (isLoading) => {
  if (!isLoading) {
    if (!canView.value) {
      pending.value = false;
      toast.error(t('common.no_permissions'));
      navigateTo('/');
    } else {
      getData();
    }
  }
});

watch([searchInput], () => {
  pagination.value.page = 1;
  debouncedSearch();
});
</script>

<template>
  <div id="wrapper" class="text-base">
    <div class="flex justify-between items-center mb-2">
      <H1 class="mb-2">{{ $t('consumption_management.title') }}</H1>
      <span>
        <AtomsDownloadXlsxButton :rows="items" :columns="exportColumns" file-name="consumption_management"
          :total-pages="pagination.totalPages" :server-export-fn="exportConsumptionManagement" />
      </span>
    </div>

    <div class="flex gap-0 mb-3 border-b border-gray-300">
      <button
        class="px-4 py-2 text-sm font-medium border-b-2 transition-colors"
        :class="activeMode === 'current'
          ? 'border-sky-500 text-sky-600'
          : 'border-transparent text-slate-500 hover:text-slate-700'"
        @click="switchMode('current')">
        {{ $t('consumption_management.tab_current') }}
      </button>
      <button
        class="px-4 py-2 text-sm font-medium border-b-2 transition-colors"
        :class="activeMode === 'history'
          ? 'border-sky-500 text-sky-600'
          : 'border-transparent text-slate-500 hover:text-slate-700'"
        @click="switchMode('history')">
        {{ $t('consumption_management.tab_history') }}
      </button>
    </div>

    <form id="form_filter" role="search"
      class="mb-3 text-base border-b border-gray-400 flex flex-start gap-4 justify-start items-center pb-2"
      @submit.prevent="handleSearch">

      <span class="input-group flex flex-start items-center gap-2 w-80">
        <Icon name="fa6-solid:magnifying-glass" class="text-slate-500" />
        <input v-model="searchInput" @input="debouncedSearch" id="searchInput" type="text" name="search"
          :placeholder="$t('dashboard.search')" class="w-full p-1 rounded-md focus:outline-none focus-visible:border-0"
          autocomplete="off" />
      </span>

      <span class="flex gap-3">
        <label v-for="tf in TYPE_FILTERS" :key="tf.value"
          class="text-slate-800 text-base flex items-center gap-1 cursor-pointer">
          <input type="checkbox" v-model="selectedTypes" :value="tf.value" @change="handleSearch" />
          {{ $t(tf.label) }}
        </label>
      </span>

      <span v-if="activeMode === 'history'" class="flex items-center gap-2">
        <label class="text-slate-600 text-sm font-medium">{{ $t('billing') }}:</label>
        <div class="relative">
          <select v-model="selectedBillingBatch" @change="handleBillingBatchChange"
            class="appearance-none pl-3 pr-8 py-1 text-sm border border-slate-300 rounded-md bg-white text-slate-700 focus:outline-none focus:ring-1 focus:ring-sky-400 focus:border-sky-400 min-w-[180px]"
            :disabled="loadingBillings">
            <option :value="null">{{ $t('common.all') }}</option>
            <option v-for="billing in billingOptions" :key="billing.id" :value="billing.id">
              {{ billing.name || billing.token || billing.id }}
            </option>
          </select>
          <Icon v-if="loadingBillings" name="fa6-solid:spinner" class="animate-spin absolute right-2 top-1/2 -translate-y-1/2 text-slate-400 w-3 h-3 pointer-events-none" />
          <Icon v-else name="fa6-solid:chevron-down" class="absolute right-2 top-1/2 -translate-y-1/2 text-slate-400 w-3 h-3 pointer-events-none" />
        </div>
      </span>

      <span>
        <button id="filterReset" type="button" class="px-2 py-1 hover:bg-slate-300 rounded"
          @click="resetFilters" title="reset">
          <Icon name="fa6-solid:rotate-right" class="text-slate-500" />
        </button>
      </span>
    </form>

    <DataTable
      grid-template="200px,1fr,1fr,1fr,120px,120px"
      :pending="pending"
      :error="error"
      :is-empty="items.length === 0"
      @retry="getData">
      <template #header>
        <TableHeader :label="$t('consumption_management.type')" sortKey="type"
          :currentSortBy="sortBy" :sortDesc="sortDesc" @sort="handleSort" />
        <TableHeader :label="$t('contract')" sortKey="contract_token"
          :currentSortBy="sortBy" :sortDesc="sortDesc" @sort="handleSort" />
        <TableHeader :label="$t('common.holder')" sortKey="holder_name"
          :currentSortBy="sortBy" :sortDesc="sortDesc" @sort="handleSort" />
        <TableHeader :label="$t('supply_point')" sortKey="supply_point_address"
          :currentSortBy="sortBy" :sortDesc="sortDesc" @sort="handleSort" />
        <TableHeader :label="$t('consumption_management.consumption')" sortKey="consumption"
          :currentSortBy="sortBy" :sortDesc="sortDesc" @sort="handleSort" />
        <TableHeader :label="$t('consumption_management.reading_date')" sortKey="reading_date"
          :currentSortBy="sortBy" :sortDesc="sortDesc" @sort="handleSort" />
      </template>

      <template #default="{ gridStyle }">
        <div v-for="item in items" :key="item.id"
          class="gap-3 text-base border-b items-center bg-white hover:bg-slate-50"
          :style="gridStyle"
          :class="{ 'bg-yellow-50': item.contract_id === selectedItemId }">

          <span class="p-1">
            <span
              class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium border"
              :class="[
                TYPE_COLORS[item.type]?.bg    ?? 'bg-slate-100',
                TYPE_COLORS[item.type]?.text  ?? 'text-slate-700',
                TYPE_COLORS[item.type]?.border ?? 'border-slate-300',
              ]">
              {{ item.type_display }}
            </span>
          </span>

          <span class="p-1">
            <button class="group flex justify-between w-full items-center p-1 text-sky-500 text-nowrap text-left"
              @click="showDetail(item.contract_id)">
              <span class="font-mono text-sm">{{ item.contract_token }}</span>
              <Icon name="fa6-solid:eye"
                class="opacity-0 group-hover:opacity-100 text-slate-500 mr-1 transition-opacity duration-200 ease-in-out" />
            </button>
          </span>

          <span class="p-1 truncate" :title="item.holder_name">{{ item.holder_name }}</span>

          <span class="p-1 text-sm text-slate-600 truncate" :title="item.supply_point_address">
            {{ item.supply_point_address }}
          </span>

          <span class="p-1 text-sm">
            <template v-if="item.readings_in_period !== null">
              {{ item.readings_in_period }} {{ $t('consumption_management.readings') }}
            </template>
            <template v-else-if="item.consumption !== null">
              {{ item.consumption }} {{ item.consumption_unit }}
            </template>
            <template v-else>—</template>
          </span>

          <span class="p-1 text-sm text-slate-500">
            <template v-if="item.period_start && item.period_end">
              {{ formatDate(item.period_start) }} – {{ formatDate(item.period_end) }}
            </template>
            <template v-else-if="item.reading_date">
              {{ formatDate(item.reading_date) }}
            </template>
            <template v-else>—</template>
          </span>
        </div>
      </template>
    </DataTable>

    <div id="list__footer">
      <Pagination v-if="pagination.total > 0" :pagination="pagination" @update:page="handlePageChange" />
    </div>
  </div>

  <div role="region" id="right_page"
    class="fixed h-full border-l border-gray-100 top-0 right-0 transition-all duration-500 ease py-2 text-base bg-white"
    :class="{
      'translate-x-0': showRegion,
      'translate-x-[2000px]': !showRegion,
      'w-[95%]': isSubRegionOpen,
      'w-[55%]': !isSubRegionOpen,
    }">
    <div id="region_nav" class="mb-3 px-3">
      <button @click="toggleRegion(false)" class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300">
        <Icon name="fa6-solid:angles-right" class="text-slate-500" />
      </button>
    </div>
    <div class="pl-10 h-full">
      <ContractRegion
        v-if="selectedItemId"
        :id="selectedItemId"
        :isSubRegionOpen="isSubRegionOpen"
        @show-subregion="handleSubRegionEvent"
        @close-subregion="toggleRegion(false)"
        @changed="handleSearch"
      />
    </div>
  </div>
</template>
