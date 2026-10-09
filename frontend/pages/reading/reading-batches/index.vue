<script setup>
import { ref, onMounted, nextTick, computed, watch } from 'vue';
import { useRouter, useRoute } from 'vue-router';
import debounce from 'lodash.debounce';
import { useI18n } from 'vue-i18n';
import { formatDate } from '~/utils/date';

import Pagination from '~/components/molecules/Pagination.vue';
import H1 from '~/components/atoms/H1.vue';
import ReadingBatchRegion from '~/components/organisms/ReadingBatchRegion.vue';
import TableHeader from '~/components/atoms/TableHeader.vue';
import DataTable from '~/components/organisms/DataTable.vue';
import { useToast } from 'vue-toastification';
import ReadingBatchSummary from '~/components/molecules/ReadingBatchSummary.vue';

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
const { $ReadingBatchApiService, $ReadingApiService } = useNuxtApp();
const pending = ref(true);
const error = ref(null);
const items = ref([]);
const searchInput = ref('');
const sortBy = ref('created_at');
const sortDesc = ref(true);
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
    const data = await $ReadingApiService.getPermissions();
    permissions.value = data;
  } catch (err) {
    error.value = err;
    pending.value = false;
  }
}

const getData = async (searchQuery = '', filters = [], page = 1, sort = 'created_at', desc = true) => {
  if (!permissions.value?.can_view) {
    return;
  }
  pending.value = true;
  error.value = null;
  try {
    const data = await $ReadingBatchApiService.getAll(searchQuery, filters, page, sort, desc);

    items.value = data.results;
    Object.assign(pagination.value, {
      total: data.count,
      totalPages: Math.ceil(data.count / pagination.value.perPage),
      previous: data.previous,
      next: data.next,
      isFiltered: String(searchQuery).trim() !== ''
    });

    nextTick(() => {
      const searchEl = document.getElementById('searchInput');
      if (searchEl) searchEl.focus();
    });
  } catch (err) {
    error.value = err;
  } finally {
    pending.value = false;
  }
}

const debouncedGetData = debounce((query, filters, sort, desc) => {
  getData(query, filters, pagination.value.page, sort, desc);
}, 300);

const handleSearch = () => {
  pagination.value.page = 1;
  debouncedGetData(searchInput.value, [], sortBy.value, sortDesc.value);
}

const handleFilterChange = () => {
  pagination.value.page = 1;
  handleSearch();
}

const handlePageChange = (newPage) => {
  pagination.value.page = newPage;
  getData(searchInput.value, [], newPage, sortBy.value, sortDesc.value);
}

const handleSort = (key) => {
  if (sortBy.value === key) {
    sortDesc.value = !sortDesc.value;
  } else {
    sortBy.value = key;
    sortDesc.value = false;
  }
  getData(searchInput.value, [], pagination.value.page, sortBy.value, sortDesc.value);
}

const exportColumns = computed(() => [
  { header: t('common.identification'), value: (row) => row.token, key: 'token' },
  { header: t('common.name'), value: (row) => row.name, key: 'name' },
  { header: t('common.creation_date'), value: (row) => formatDate(row.created_at), key: 'created_at' },
  { header: t('common.status'), value: (row) => row.status?.name, key: 'status' },
  { header: t('common.read_contracts_total_contracts'), value: (row) => `${row.num_read_contracts || 0} / ${row.num_contracts || 0}` },
  { header: t('common.total_readings'), value: (row) => row.num_readings || 0, key: 'num_readings' },
  { header: t('common.total_supply_points'), value: (row) => row.num_supplies || 0, key: 'num_supplies' },
]);

const exportReadingBatches = (columns) => $ReadingBatchApiService.exportData(searchInput.value, [], sortBy.value, sortDesc.value, columns);

const resetFilters = () => {
  searchInput.value = '';
  pagination.value.page = 1;
  sortBy.value = 'created_at';
  sortDesc.value = true;
  getData();
};

const checkRouteQuery = () => {
  if (route.query?.action == 'showDetail' || route.query?.id ) {
    showDetail(route.query.id)
  } else if (route.query?.action == 'filterPage') {
    searchInput.value = route.query.search || '';
    handleSearch();
  }
}

onMounted(async () => {
  await getPermissions();
  if (permissions.value?.can_view) {
    getData();
    checkRouteQuery();
  } else {
    pending.value = false;
    toast.error(t('common.no_permissions'));
    return navigateTo('/');
  }
});

const initialMode = ref('detail');
const summaryCounters = ref(null);
const summaryTaskId = ref(null);

const showDetail = async (id, mode = 'detail') => {
  await toggleRegion(false);
  detail.value = id;
  selectedItemId.value = id;
  initialMode.value = mode;

  if (mode === 'summary') {
    try {
      const summary = await $ReadingBatchApiService.getSummary(id);
      summaryCounters.value = summary.counters || summary.counters_pending;
      summaryTaskId.value = summary.task_id;
    } catch (err) {
      console.error(err);
      toast.error(t('common.error_loading_data'));
    }
  }

  toggleRegion(true);
}

watch(() => route.query, () => {
  checkRouteQuery()
});

const handleSubRegionEvent = (event) => {
  isSubRegionOpen.value = event;
}

// Navegació interna disparada pel component de detall (p.ex. clic a
// "Exclòs de" per anar del lot exclòs al lot original). No fem servir la
// URL/query per evitar el problema que Vue Router no torna a disparar el
// watch quan la query resultant és idèntica a l'actual.
const handleSelectBatch = (id) => {
  showDetail(id);
}

watch(() => showRegion.value, (newVal) => {
  if (!newVal) {
    isSubRegionOpen.value = false;
  }
})

</script>

<template>
  <div id="wrapper" class="text-base">
    <div class="flex justify-between items-center mb-2">
      <H1 class="mb-2">{{ $t('common.reading_batches') }}</H1>
      <div class="flex items-center gap-2">
        <AtomsDownloadXlsxButton :rows="items" :columns="exportColumns" file-name="reading_batches"
          :total-pages="pagination.totalPages" :server-export-fn="exportReadingBatches" />
        <NuxtLink v-if="permissions?.can_add" to="/reading/reading-batches/add" class="button-primary">{{ $t('billing_block.new_reading_batch') }}</NuxtLink>
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
        <button id="filterReset" name="form_filter" type="button" class="px-2 py-1 hover:bg-slate-300 rounded"
          @click="resetFilters" title="reset">
          <Icon name="fa6-solid:rotate-right" class="text-slate-500" />
        </button>
      </span>
    </form>

    <DataTable
      grid-template="1.2fr,1.7fr,1.1fr,1fr,0.7fr,0.5fr,0.8fr"
      :pending="pending"
      :error="error"
      :is-empty="items.length === 0"
      @retry="getData">
      <template #header>
        <TableHeader :label="$t('common.identification')" sortKey="token" :currentSortBy="sortBy" :sortDesc="sortDesc"
          @sort="handleSort" />
        <TableHeader :label="$t('common.name')" sortKey="name" :currentSortBy="sortBy" :sortDesc="sortDesc"
          @sort="handleSort" />
        <TableHeader :label="$t('common.creation_date')" sortKey="created_at" :currentSortBy="sortBy" :sortDesc="sortDesc"
          @sort="handleSort" />
        <TableHeader :label="$t('common.status')" sortKey="status__name" :currentSortBy="sortBy" :sortDesc="sortDesc"
          @sort="handleSort" />
        <TableHeader :label="$t('common.read_contracts_total_contracts')" :sortable="false" />
        <TableHeader :label="$t('common.total_readings')" :sortable="false" />
        <TableHeader :label="$t('common.total_supply_points')" :sortable="false" />
      </template>

      <template #default="{ gridStyle }">
        <div v-for="item in items" :key="item.id"
          class="gap-3 text-base border-b items-center bg-white"
          :style="gridStyle"
          :class="{ 'bg-yellow-50': item.id === selectedItemId }">
          <span class="truncate min-w-0">
            <button class="group flex justify-between w-full items-center p-1 text-sky-500 text-left min-w-0 truncate"
              @click="showDetail(item.id);">
              <abbr :title="item.token" class="no-underline truncate">{{ item.token }}</abbr>
              <Icon name="fa6-solid:eye"
                class="opacity-0 group-hover:opacity-100 text-slate-500 mr-1 flex-shrink-0 transition-opacity duration-200 ease-in-out" />
            </button>
          </span>
          <span class="p-0 truncate min-w-0" :title="item.name">{{ item.name }}</span>
          <span class="p-1 truncate min-w-0" :title="formatDate(item.created_at)">{{ formatDate(item.created_at) }}</span>
          <span class="p-1 flex items-center gap-2 min-w-0">
            <AtomsColorBadge :value="item.status?.name" :color="item.status?.color" class="truncate"></AtomsColorBadge>
            <button v-if="item.num_warnings > 0"
              class="flex-shrink-0 flex items-center gap-1 text-yellow-500 hover:text-yellow-600 transition-colors"
              @click.stop="showDetail(item.id, 'summary')"
              :title="t('common.warnings')">
              <Icon name="fa6-solid:triangle-exclamation" />
              <span class="text-xs font-bold">{{ item.num_warnings }}</span>
            </button>
          </span>
          <span class="p-1 truncate min-w-0" :title="`${item.num_read_contracts || 0} / ${item.num_contracts || 0 }`">
            {{ item.num_read_contracts || 0 }} / {{ item.num_contracts || 0 }}
          </span>
          <span class="p-1 truncate min-w-0">
            {{ item.num_readings || 0 }}
          </span>
          <span class="p-1 truncate min-w-0">
            {{ item.num_supplies || 0 }}
          </span>
        </div>
      </template>
    </DataTable>

    <div id="list__footer">
      <Pagination v-if="items.length > 0" :pagination="pagination" @update:page="handlePageChange" />
    </div>

    <!-- Right Region -->
    <div role="region" id="right_page"
      class="fixed h-full border-l border-gray-100 top-0 right-0 transition-all duration-500 ease py-2 text-base bg-white flex flex-col"
      :class="{ 
      'translate-x-0': showRegion, 
      'translate-x-[2000px]': !showRegion, 
      'w-[95%]': isSubRegionOpen, 
      'w-[90%]': !isSubRegionOpen && initialMode === 'summary',
      'w-1/2': !isSubRegionOpen && initialMode !== 'summary' 
    }">
      <div id="region_nav" class="flex-shrink-0 mb-3 px-3">
        <button @click="toggleRegion(false)" class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300">
          <Icon name="fa6-solid:angles-right" class="text-slate-500" />
        </button>
      </div>
      <div class="flex-1 min-h-0">
        <ReadingBatchRegion v-if="detail && initialMode !== 'summary'" :id="detail" 
          :isSubRegionOpen="isSubRegionOpen"
          @show-subregion="handleSubRegionEvent"
          @close-subregion="toggleRegion(false)"
          @select-batch="handleSelectBatch">
        </ReadingBatchRegion>
        
        <ReadingBatchSummary v-if="detail && initialMode === 'summary'" 
          :batch_id="detail"
          :counters="summaryCounters"
          :taskId="summaryTaskId"
          initialFilter="warning"
          :isEmbedded="true"
          @show-subregion="handleSubRegionEvent"
        />
      </div>
    </div>
  </div>
</template>