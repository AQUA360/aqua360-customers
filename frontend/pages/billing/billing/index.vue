<script setup>
import { ref, onMounted, nextTick, computed, watch } from 'vue';
import { useRouter } from 'vue-router';
import debounce from 'lodash.debounce';
import { useI18n } from 'vue-i18n';
import { formatDate } from '~/utils/date';
import { useToast } from 'vue-toastification';
import Pagination from '~/components/molecules/Pagination.vue';
import H1 from '~/components/atoms/H1.vue';
import BillingRegion from '~/components/organisms/BillingRegion.vue';
import TableHeader from '~/components/atoms/TableHeader.vue';
import AppLoading from '~/components/atoms/AppLoading.vue';
import DataTable from '~/components/organisms/DataTable.vue';

const { t } = useI18n();
const toast = useToast();
const showRegion = ref(false);

const detail = ref(null);
const selectedItemId = ref(null);
const isSubRegionOpen = ref(false);
const toggleRegion = (force, isReload = false) => {
  showRegion.value = force !== undefined ? force : !showRegion.value;
  if (showRegion.value == false) {
    isSubRegionOpen.value = false;
    detail.value = null
    selectedItemId.value = null
  }
}

const route = useRoute();
const router = useRouter();
const { $BillingApiService, $ConfigProjectApiService, $BillerApiService } = useNuxtApp();
const pending = ref(true);
const error = ref(null);
const items = ref([]);
const processingStatusTokens = ref([]);
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
    const data = await $BillingApiService.getPermissions();
    permissions.value = data;
  } catch (err) {
    error.value = err;
  }
}

const getData = async (searchQuery = '', filters = [], page = 1, sort = 'created_at', desc = true) => {
  if (!permissions.value?.can_view) {
    toast.error(t('common.no_permissions'));
    return navigateTo('/');
  }
  pending.value = true;
  error.value = null;
  try {
    const data = await $BillingApiService.getAll(searchQuery, filters, page, sort, desc);

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

// XLSX export — columns mirror the visible table columns (in display order).
const exportColumns = computed(() => [
  { header: t('common.identification'), value: (row) => row.token, key: 'token' },
  { header: t('common.name'), value: (row) => row.name, key: 'name' },
  { header: t('common.creation_date'), value: (row) => row.created_at ? formatDate(row.created_at) : '', key: 'created_at' },
  { header: t('common.status'), value: (row) => row.status?.name, key: 'status' },
]);

// Hybrid export: single page → client-side; multiple pages → server (all-pages, filter-aware).
const exportBillings = (columns) => $BillingApiService.exportData(
  searchInput.value, [], sortBy.value, sortDesc.value, columns
);

const resetFilters = () => {
  searchInput.value = '';
  pagination.value.page = 1;
  if (billingBadgesRef.value && billingBadgesRef.value.refresh) {
    billingBadgesRef.value.refresh();
  }
  getData();
};

const checkRouteQuery = () => {
  if (route.query?.action == 'showDetail' || route?.query?.id) {
    showDetail(route.query.id)
  }else if (route.query?.action == 'filterPage') {
    searchInput.value = route.query.search;
    handleSearch();
  }
}

const showDetail = (id) => {
  if (id && selectedItemId.value && String(selectedItemId.value) === String(id) && showRegion.value) {
    toggleRegion(false, true);
    nextTick(() => {
      detail.value = id;
      selectedItemId.value = id;
      toggleRegion(true);
    });
    return;
  }
  toggleRegion(false);
  detail.value = id;
  selectedItemId.value = id;
  toggleRegion(true);
}

onMounted( async () => {
  await getPermissions();
    if (permissions.value?.can_view) {
    const processing = await $ConfigProjectApiService.get('billing_batch_processing');
    const processingDocuments = await $ConfigProjectApiService.get('billing_batch_processing_documents');
    processingStatusTokens.value = [processing, processingDocuments];

    getData();
    checkRouteQuery();
    
  } else {
    toast.error(t('common.no_permissions'));
    pending.value = false;
    return navigateTo('/');
  }
});

// Watch for changes in searchInput and selectedFilters and reset pagination to 1
watch([searchInput], () => {
  pagination.value.page = 1;
  handleSearch();
});

const handleSubRegionEvent = (event) => {
  isSubRegionOpen.value = event;
}

// Add ref for AtomsBillingBadges component
const billingBadgesRef = ref(null);

// ------------------------------------------------------------------
// Modal state for biller selection
// ------------------------------------------------------------------
const showBillerModal = ref(false);
const billers = ref([]);
const selectedBiller = ref(null); // objecte complet del facturador (no només l'id)
const loadingBillers = ref(false);

// --- Càlcul del període (trimestre/semestre/mes/...) a partir del "time now" ---
const PERIOD_INTERVALS = {
  mensual: 1,
  bimestral: 2,
  trimestral: 3,
  quadrimestral: 4,
  semestral: 6,
  anual: 12,
};

const PERIOD_LETTERS = {
  mensual: 'M',
  bimestral: 'B',
  trimestral: 'T',
  quadrimestral: 'Q',
  semestral: 'S',
};

const getCurrentPeriodLabel = (periodType) => {
  const now = new Date();
  const monthIndex = now.getMonth() + 1; // 1-12
  const year = now.getFullYear();

  if (periodType === 'anual') {
    return `${year}`;
  }

  const interval = PERIOD_INTERVALS[periodType] || 1;
  const periodNumber = Math.ceil(monthIndex / interval);
  const letter = PERIOD_LETTERS[periodType] || 'P';

  return `${letter}${periodNumber}/${year}`;
};

// Camps editables del codi i el nom (pas 2 del modal)
const billerCode = ref('');
const billerName = ref('');

// Genera els valors per defecte a partir del facturador seleccionat
const generateDefaults = (biller) => {
  if (!biller) {
    billerCode.value = '';
    billerName.value = '';
    return;
  }
  const base = biller.token || biller.name || '';
  const periodLabel = getCurrentPeriodLabel(biller.period_type);
  billerCode.value = `${base}_${periodLabel}`;
  billerName.value = `Fact.${base}_${periodLabel}`;
};

// Quan canvia el facturador seleccionat, recalcula codi/nom per defecte
watch(selectedBiller, (newBiller) => {
  generateDefaults(newBiller);
});

const fetchBillers = async () => {
  loadingBillers.value = true;
  error.value = null;
  try {
    const data = await $BillerApiService.getAll('', [], 1, null, false);
    billers.value = data.results || [];
  } catch (err) {
    error.value = err;
    toast.error(t('common.error_loading_data'));
  } finally {
    loadingBillers.value = false;
  }
};

const openBillerModal = async () => {
  showBillerModal.value = true;
  selectedBiller.value = null;
  billerCode.value = '';
  billerName.value = '';
  await fetchBillers();
};

const closeBillerModal = () => {
  showBillerModal.value = false;
  selectedBiller.value = null;
  billerCode.value = '';
  billerName.value = '';
};

const confirmBillerSelection = async () => {
  if (!selectedBiller.value) {
    toast.error(t('common.please_select_biller') || 'Please select a biller');
    return;
  }
  if (!billerCode.value.trim() || !billerName.value.trim()) {
    toast.error(t('common.required_fields') || 'Codi i nom són obligatoris');
    return;
  }

  try {
    await $BillingApiService.start(
      selectedBiller.value.id,
      billerCode.value.trim(),
      billerName.value.trim()
    );
    toast.success(t('billing_block.billing_started') || 'Billing started successfully');
    closeBillerModal();

    getData();
    // Call method on AtomsBillingBadges component if it exists
    // if (billingBadgesRef.value && billingBadgesRef.value.refresh) {
    //   billingBadgesRef.value.refresh();
    // }
    resetFilters();
  } catch (err) {
    error.value = err;
    toast.error(t('common.error') || 'Error starting billing');
  }
};

const startBilling = async () => {
  await openBillerModal();
}
watch(() => route.query, () => {
  checkRouteQuery()
}, { immediate: true })
</script>

<template>
  <div id="wrapper" class="text-base">
    <div class="flex justify-between items-center mb-2">
      <H1 class="mb-2">{{ $t('common.billings') }}</H1>
      <!-- <AtomsBillingBadges v-if="permissions?.can_view" ref="billingBadgesRef"/> -->
      <!--<NuxtLink to="/billing/billing-batches/add" class="button-primary">{{ $t('Nou lot de facturació') }}</NuxtLink>-->
      <div class="flex items-center gap-2">
        <AtomsDownloadXlsxButton :rows="items" :columns="exportColumns" file-name="billings"
          :total-pages="pagination.totalPages" :server-export-fn="exportBillings" :sheet-name="t('common.billings')" />
        <button v-if="permissions?.can_add" @click="startBilling" class="button-primary">{{ $t('billing_block.start_billing') }}</button>
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
          @click="resetFilters" title="reset"><Icon name="fa6-solid:rotate-right" class="text-slate-500" /></button>
      </span>
    </form>
    <DataTable
      grid-template="1fr,1fr,1fr,1fr"
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
        <TableHeader :label="$t('common.status')" sortKey="status" :currentSortBy="sortBy" :sortDesc="sortDesc"
          @sort="handleSort" />
      </template>

      <template #default="{ gridStyle }">
        <div v-for="item in items" :key="item.id"
          class="gap-3 text-base border-b items-center bg-white"
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
          <span class="p-0" :title="item.name">{{ item.name }}</span>
          <span class="p-1" :title="formatDate(item.created_at)">{{ formatDate(item.created_at) }}</span>
          <span class="p-1">
            <AtomsProcessColorBadge @refresh="resetFilters" v-if="processingStatusTokens.findIndex(i => i == item.status?.token?.toString()) != -1" :value="item.status?.name" :color="item.status?.color" :taskId="item.task_id" :billingId="item.id"></AtomsProcessColorBadge>
            <AtomsColorBadge v-else :value="item.status?.name" :color="item.status?.color"></AtomsColorBadge>
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
      <BillingRegion v-if="detail" :id="detail" :isSubRegionOpen="isSubRegionOpen"
        @show-subregion="handleSubRegionEvent" @close-subregion="toggleRegion(false)" @changed="getData"></BillingRegion>
    </div>
  </div>

  <!-- Biller Selection Modal -->
  <div v-if="showBillerModal" class="fixed inset-0 z-50 flex items-center justify-center overflow-y-auto">
    <div class="bg-white rounded-lg shadow-xl p-6 max-w-lg w-full mx-4 my-auto relative">
      <button @click="closeBillerModal" class="absolute top-4 right-4 text-gray-500 hover:text-gray-700">
        <Icon name="fa6-solid:xmark" class="text-xl" />
      </button>
      <h2 class="text-xl font-semibold mb-4">{{ $t('billing_block.select_biller') || 'Select Biller' }}</h2>

      <div v-if="loadingBillers" class="my-4">
        <AppLoading :text="$t('common.loading')" />
      </div>

      <div v-else>
        <div class="mb-4">
          <label class="block font-medium text-slate-500 mb-2">
            {{ $t('common.select') }} {{ $t('billing_block.biller') || 'Biller' }}
          </label>
          <select
            v-model="selectedBiller"
            class="w-full text-base border border-gray-300 rounded p-2"
            id="biller-select"
          >
            <option :value="null">
              -- {{ $t('common.select') }} {{ $t('billing_block.biller') || 'Biller' }} --
            </option>
            <option v-for="biller in billers" :value="biller" :key="biller.id">
              {{ biller.name || biller.token }}
            </option>
          </select>
        </div>

        <!-- Pas 2: codi i nom, editables, precalculats en seleccionar facturador -->
        <template v-if="selectedBiller">
          <div class="mb-4">
            <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('common.identificator') }}</label>
            <input type="text" v-model="billerCode" class="input w-full text-base border border-gray-300 rounded p-2" />
          </div>
          <div class="mb-4">
            <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('common.name') }}</label>
            <input type="text" v-model="billerName" class="input w-full text-base border border-gray-300 rounded p-2" />
          </div>
        </template>

        <div class="flex justify-end gap-2 mt-6">
          <button @click="closeBillerModal" class="button-default">
            {{ $t('common.cancel') }}
          </button>
          <button @click="confirmBillerSelection" class="button-primary" :disabled="!selectedBiller">
            {{ $t('common.confirm') || 'Confirm' }}
          </button>
        </div>
      </div>
    </div>
  </div>

</template>