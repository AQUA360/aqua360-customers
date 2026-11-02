<script setup>
import { ref, onMounted, onUnmounted, nextTick, computed, watch } from 'vue';
import { useRouter } from 'vue-router';
import debounce from 'lodash.debounce';
import { useI18n } from 'vue-i18n';
import { formatDateTime } from '~/utils/date';
import { useToast } from 'vue-toastification';
import Pagination from '~/components/molecules/Pagination.vue';
import H1 from '~/components/atoms/H1.vue';
import SupplyCutRegion from '~/components/organisms/SupplyCutRegion.vue';
import DataTable from '~/components/organisms/DataTable.vue';

const { t } = useI18n();
const toast = useToast();
const showRegion = ref(false);
const selectedItemId = ref(null);
const isSubRegionOpen = ref(false);
const toggleRegion = (force) => {
  showRegion.value = force !== undefined ? force : !showRegion.value;
  if (showRegion.value == false) {
    isSubRegionOpen.value = false;
    itemDetail.value = null;
    selectedItemId.value = null;
  }
}

const router = useRouter();
const route = useRoute();
const { $SupplyCutApiService, $ConfigProjectApiService, $apiManager } = useNuxtApp();
const pending = ref(true);
const error = ref(null);
const items = ref([]);
const searchInput = ref('');
const searchByAddress = ref('');
const showAddressSearch = ref(false);
const filter_status = ref([]);
const selectedFilters = ref([]);
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

let requestSeq = 0;

// Botó «Sincronitzar amb GIS Water»: només si el projecte el té activat.
const giswaterSyncEnabled = ref(false);
const syncingGiswater = ref(false);
let giswaterSyncInterval = null;
// Si la tasca no acaba en aquest temps (p. ex. cap worker de Celery actiu), es deixa d'esperar.
const GISWATER_SYNC_POLL_MS = 2000;
const GISWATER_SYNC_TIMEOUT_MS = 5 * 60 * 1000;

const loadGiswaterSyncEnabled = async () => {
  try {
    const value = await $ConfigProjectApiService.get('giswater_supply_cut_sync_enabled');
    // Mateixos valors que el backend (`is_supply_cut_manual_sync_enabled`).
    giswaterSyncEnabled.value = value === true
      || ['true', '1', 'yes'].includes(String(value).trim().toLowerCase());
  } catch {
    giswaterSyncEnabled.value = false;
  }
};

const stopGiswaterSyncPolling = () => {
  if (giswaterSyncInterval) {
    clearInterval(giswaterSyncInterval);
    giswaterSyncInterval = null;
  }
  syncingGiswater.value = false;
};

const syncGiswater = async () => {
  if (syncingGiswater.value) return;
  syncingGiswater.value = true;
  try {
    const response = await $SupplyCutApiService.syncGiswater();
    if (!response?.task_id) throw new Error('task_id not received');
    toast.info(t('service_block.sync_giswater_running'));
    const pollStartedAt = Date.now();
    giswaterSyncInterval = setInterval(async () => {
      try {
        const res = await $apiManager.checkTask(response.task_id);
        if (!res || res.state === 'PENDING' || res.state === 'RUNNING') {
          if (Date.now() - pollStartedAt >= GISWATER_SYNC_TIMEOUT_MS) {
            stopGiswaterSyncPolling();
            toast.error(t('service_block.sync_giswater_timeout'));
          }
          return;
        }
        stopGiswaterSyncPolling();
        // La tasca captura els errors i acaba en SUCCESS amb `status: 'error'`.
        if (res.state === 'SUCCESS' && res.result?.status !== 'error') {
          toast.success(t('service_block.sync_giswater_done'));
          reloadData();
        } else {
          toast.error(res.result?.message || res.error || t('service_block.sync_giswater_error'));
        }
      } catch {
        stopGiswaterSyncPolling();
        toast.error(t('service_block.sync_giswater_error'));
      }
    }, GISWATER_SYNC_POLL_MS);
  } catch {
    stopGiswaterSyncPolling();
    toast.error(t('service_block.sync_giswater_error'));
  }
};

onUnmounted(() => {
  if (giswaterSyncInterval) clearInterval(giswaterSyncInterval);
});

const tableColumns = computed(() => [
  { key: 'token', label: t('common.identification'), sortKey: 'id', width: 110, min: 95, priority: 1, removable: false },
  {
    key: 'affected_sp', label: t('service_block.affected_sp'),
    width: 70, min: 60, priority: 3, cellClass: 'justify-center',
  },
  { key: 'address', label: t('address_block.address'), width: 260, grow: 4, min: 160, priority: 1, removable: false },
  {
    key: 'status', label: t('common.status'), sortKey: 'status_name',
    width: 150, min: 110, priority: 1, cellClass: 'inline-flex gap-2 items-center',
  },
  { key: 'date_start', label: t('service_block.cut_date_expected_start'), sortKey: 'date_start', width: 140, min: 120, priority: 2 },
  { key: 'date_end', label: t('service_block.cut_date_expected_end'), sortKey: 'date_end', width: 140, min: 120, priority: 3 },
  { key: 'exec_start', label: t('service_block.cut_date_real_start'), sortKey: 'exec_start', width: 140, min: 120, priority: 2 },
  { key: 'exec_end', label: t('service_block.cut_date_real_end'), sortKey: 'exec_end', width: 140, min: 120, priority: 3 },
  { key: 'cause', label: t('order_block.reason'), width: 170, grow: 1, min: 120, priority: 2 },
]);

const rowClass = (item) => ({
  'bg-yellow-50': item.id === selectedItemId.value,
});

const getPermissions = async () => {
  error.value = null;
  try {
    const data = await $SupplyCutApiService.getPermissions();
    permissions.value = data;
  } catch (err) {
    error.value = err;
  }
}

const getData = async (searchQuery = '', filters = [], page = 1, sort = null, desc = false, searchByAddressQuery = '') => {
  if (!permissions.value?.can_view) {
    requestSeq++;
    pending.value = false;
    toast.error(t('common.no_permissions'));
    return navigateTo('/');
  }
  const seq = ++requestSeq;
  pending.value = true;
  error.value = null;
  try {
    const data = await $SupplyCutApiService.getData(searchQuery, filters, page, sort, desc, null, null, searchByAddressQuery);
    if (seq !== requestSeq) return;
    items.value = data.results;
    Object.assign(pagination.value, {
      total: data.count,
      totalPages: Math.ceil(data.count / pagination.value.perPage),
      previous: data.previous,
      next: data.next,
      isFiltered: String(searchQuery).trim() !== '' || filters.length > 0 || String(searchByAddressQuery).trim() !== ''
    });

    nextTick(() => {
      document.getElementById('searchInput').focus();
    });
  } catch (err) {
    if (seq !== requestSeq) return;
    error.value = err;
    if (err?.response?.status === 401) {
      pending.value = false;
    }
    // Pàgina desada (última cerca) que ja no existeix: es torna a la primera.
    if (err?.response?.status === 404 && page > 1) {
      pagination.value.page = 1;
      getData(searchQuery, filters, 1, sort, desc, searchByAddressQuery);
    }
  } finally {
    if (seq === requestSeq) {
      pending.value = false;
    }
  }
}

const getFilterStatus = async () => {
  error.value = null;
  try {
    const data = await $SupplyCutApiService.getFilterStatus();
    filter_status.value = data;
  } catch (err) {
    error.value = err;
  }
}

// Última cerca: es desa a sessionStorage (com a Contractes) i es recupera en tornar a la pàgina.
const STORAGE_KEY = 'supplyCutsSearchState';
// Mentre es restaura l'estat inicial, els watchers no han de rellançar la cerca.
const searchReady = ref(false);

const saveSearchState = () => {
  try {
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify({
      searchInput: searchInput.value,
      searchByAddress: searchByAddress.value,
      showAddressSearch: showAddressSearch.value,
      selectedFilters: selectedFilters.value,
      sortBy: sortBy.value,
      sortDesc: sortDesc.value,
      page: pagination.value.page,
    }));
  } catch {
    // sessionStorage no disponible: la pàgina funciona igual, sense recordar la cerca.
  }
};

const loadSearchState = () => {
  try {
    const state = JSON.parse(sessionStorage.getItem(STORAGE_KEY) || 'null');
    if (!state) return false;
    if (state.searchInput !== undefined) searchInput.value = state.searchInput;
    if (state.searchByAddress !== undefined) searchByAddress.value = state.searchByAddress;
    if (state.showAddressSearch !== undefined) showAddressSearch.value = state.showAddressSearch;
    if (Array.isArray(state.selectedFilters)) selectedFilters.value = state.selectedFilters;
    if (state.sortBy !== undefined) sortBy.value = state.sortBy;
    if (state.sortDesc !== undefined) sortDesc.value = state.sortDesc;
    if (state.page) pagination.value.page = state.page;
    return true;
  } catch {
    return false;
  }
};

// Estats seleccionats per defecte: els oberts (Planificat, Actiu i Conflicte),
// és a dir, tots els que no són a `supply_cut_status_closed_tokens`.
const loadClosedStatusTokens = async () => {
  try {
    const value = await $ConfigProjectApiService.get('supply_cut_status_closed_tokens');
    const tokens = String(value ?? '').split(',').map((token) => token.trim()).filter(Boolean);
    return tokens.length ? tokens : ['2', '3'];
  } catch {
    return ['2', '3'];
  }
};

const defaultStatusFilters = (closedTokens) => filter_status.value
  .filter((status) => !closedTokens.includes(String(status.token)))
  .map((status) => status.id);

let closedStatusTokens = ['2', '3'];

const reloadData = () => getData(
  searchInput.value, selectedFilters.value, pagination.value.page, sortBy.value, sortDesc.value, searchByAddress.value
);

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
  getData(searchInput.value, selectedFilters.value, pagination.value.page, sortBy.value, sortDesc.value, searchByAddress.value);
}

const resetFilters = () => {
  searchReady.value = false;
  searchInput.value = '';
  searchByAddress.value = '';
  selectedFilters.value = defaultStatusFilters(closedStatusTokens);
  sortBy.value = null;
  sortDesc.value = false;
  pagination.value.page = 1;
  showAddressSearch.value = false;
  saveSearchState();
  reloadData();
  nextTick(() => { searchReady.value = true; });
};

const toggleAddressFilter = () => {
  showAddressSearch.value = !showAddressSearch.value;
};

onMounted(async () => {
  await getPermissions();
  if (!permissions.value?.can_view) {
    pending.value = false;
    toast.error(t('common.no_permissions'));
    return navigateTo('/');
  }
  const [, closedTokens] = await Promise.all([getFilterStatus(), loadClosedStatusTokens()]);
  closedStatusTokens = closedTokens;
  if (!loadSearchState()) {
    selectedFilters.value = defaultStatusFilters(closedStatusTokens);
  }
  await reloadData();
  await nextTick();
  searchReady.value = true;
  loadGiswaterSyncEnabled();
  checkRouteQuery();
});

const checkRouteQuery = () => {
  if (route.query?.action == 'showDetail') {
    toggleRegion(false);
    showItemDetail(route.query.id)
  }
}

const itemDetail = ref(null);

const requestDeleted = () => {
  toggleRegion(false)
  reloadData();
}

const showItemDetail = async (id) => {
  await toggleRegion(false);
  itemDetail.value = id;
  selectedItemId.value = id;
  toggleRegion(true);
}

const regionAccept = () => {
  reloadData();
  toggleRegion(false);
}

// Watch for changes in searchInput and selectedFilters and reset pagination to 1
watch([searchInput, selectedFilters], () => {
  if (!searchReady.value) return;
  pagination.value.page = 1;
  handleSearch();
});

watch(
  () => [searchInput.value, searchByAddress.value, showAddressSearch.value, selectedFilters.value,
    sortBy.value, sortDesc.value, pagination.value.page],
  () => {
    if (searchReady.value) saveSearchState();
  },
  { deep: true }
);

const handleSubRegionEvent = (event) => {
  isSubRegionOpen.value = event;
}

const formattedSupplyPointIds = (item) => {
  return Array.isArray(item?.supply_point_ids)
    ? item.supply_point_ids.join("\n")
    : t("service_block.no_affected_sp")
}
watch(() => route.query, () => {
  checkRouteQuery()
}, { immediate: true })
</script>

<template>
  <div id="wrapper" class="text-base">
    <div class="flex justify-between items-center mb-2">
      <H1>{{ $t('common.supply_cuts') }}</H1>
      <div class="flex items-center gap-2">
        <button v-if="giswaterSyncEnabled && permissions?.can_add" type="button" class="button-secondary flex items-center gap-2"
          :disabled="syncingGiswater" @click="syncGiswater">
          <Icon name="fa6-solid:arrows-rotate" :class="{ 'animate-spin': syncingGiswater }" />
          {{ $t('service_block.sync_giswater') }}
        </button>
        <NuxtLink v-if="permissions?.can_add" to="/service/supply-cut/add" class="button-primary">{{ $t('service_block.new_supply_cut') }}</NuxtLink>
      </div>
    </div>
    <form id="form_filter" role="search"
      class="mb-3 text-base border-b border-gray-400 flex flex-start gap-4 justify-start items-center"
      @submit.prevent="handleSearch">

      <span class="input-group flex flex-start items-center gap-2 w-80">
        <Icon name="fa6-solid:magnifying-glass" class="text-slate-500" />
        <input v-model="searchInput" id="searchInput" type="text" name="search"
          :placeholder="$t('dashboard.search')" class="w-full p-1 rounded-md focus:outline-none focus-visible:border-0"
          autocomplete="off" />
      </span>

      <span class="flex gap-3" v-if="filter_status.length">
        <label v-for="status in filter_status" class="text-slate-800 text-base flex items-center gap-1">
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
      table-key="supply-cuts"
      :columns="tableColumns"
      :items="permissions?.can_view ? items : []"
      :row-class="rowClass"
      :current-sort-by="sortBy"
      :sort-desc="sortDesc"
      :pending="pending"
      :error="error"
      :is-empty="permissions?.can_view && items.length === 0"
      @sort="handleSort"
      @retry="reloadData">
      <template #cell-token="{ item }">
        <button class="group flex justify-between w-full items-center text-sky-500 text-nowrap text-left"
          @click="showItemDetail(item.id);">
          <abbr :title="item.id" class="no-underline truncate">{{ item.token }}</abbr>
          <Icon name="fa6-solid:eye"
            class="opacity-0 group-hover:opacity-100 text-slate-500 mr-1 transition-opacity duration-200 ease-in-out" />
        </button>
      </template>

      <template #cell-affected_sp="{ item }">
        <abbr :title="formattedSupplyPointIds(item)" class="no-underline">{{ item.affected_supply_points }}</abbr>
      </template>

      <template #cell-address="{ item }">
        <span class="truncate" :title="item.distinct_streets">{{ item.distinct_streets || '' }}</span>
      </template>

      <template #cell-status="{ item }">
        <AtomsColorBadge :value="item.status_name || ''" :color="item.status_color || ''" />
        <abbr v-if="item.requires_review" :title="$t('service_block.requires_review')" class="flex items-center">
          <Icon name="fa6-solid:exclamation" class="text-amber-500" />
        </abbr>
      </template>

      <template #cell-date_start="{ item }">{{ item.date_start ? formatDateTime(item.date_start) : '' }}</template>
      <template #cell-date_end="{ item }">{{ item.date_end ? formatDateTime(item.date_end) : '-' }}</template>
      <template #cell-exec_start="{ item }">{{ item.exec_start ? formatDateTime(item.exec_start) : '' }}</template>
      <template #cell-exec_end="{ item }">{{ item.exec_end ? formatDateTime(item.exec_end) : '-' }}</template>

      <template #cell-cause="{ item }">
        <AtomsColorBadge :value="item.cause_name || ''" :color="item.cause_color || ''" />
      </template>
    </DataTable>
    <div id="list__footer">
      <Pagination v-if="items.length > 0" :pagination="pagination" @update:page="handlePageChange" />
    </div>
  </div><!-- end wrapper -->

  <div role="region" id="right_page"
    class="fixed z-20 h-full border-l border-gray-100 top-0 right-0 transition-all duration-500 ease py-2 text-base bg-white"
    :class="{ 'translate-x-0': showRegion, 'translate-x-full': !showRegion, 'w-[95%]': isSubRegionOpen, 'w-1/2': !isSubRegionOpen }">
    <div id="region_nav" class="mb-3 px-3">
      <button @click="toggleRegion(false)" class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300">
        <Icon name="fa6-solid:angles-right" class="text-slate-500" />
      </button>
    </div>
    <div class="pl-10 h-full">
      <SupplyCutRegion v-if="itemDetail" :id="itemDetail" @accept="regionAccept" :isSubRegionOpen="isSubRegionOpen"
        @show-subregion="handleSubRegionEvent" @deleted="requestDeleted" @changed="reloadData" @close-subregion="toggleRegion(false)"></SupplyCutRegion>
    </div>
  </div>

</template>