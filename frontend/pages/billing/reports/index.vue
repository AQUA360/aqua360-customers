<script setup>
import { ref, onMounted, onUnmounted, nextTick, computed, watch } from 'vue';
import { useRouter } from 'vue-router';
import debounce from 'lodash.debounce';
import { useI18n } from 'vue-i18n';
import { formatDate, formatDateTime } from '~/utils/date';
import { useToast } from 'vue-toastification';
import Pagination from '~/components/molecules/Pagination.vue';
import H1 from '~/components/atoms/H1.vue';
import BillingRegion from '~/components/organisms/BillingRegion.vue';
import TableHeader from '~/components/atoms/TableHeader.vue';
import DataTable from '~/components/organisms/DataTable.vue';

const { t } = useI18n();
const toast = useToast();
const showRegion = ref(false);

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
const { $apiManager, $ReportsApiService, $ConfigProjectApiService, $DocumentManagerApiService } = useNuxtApp();

const fullQueueList = ref([]);
const showPendingList = ref(true);
const showFinishedList = ref(false);
const queueInterval = ref(null);

// El botó cap a "Resum de la facturació general" només es mostra si el
// ConfigProject ho té activat per aquest client.
const generalBillingSummaryEnabled = ref(false);

const loadGeneralBillingSummaryConfig = async () => {
  try {
    const response = await $ConfigProjectApiService.getAll('general_billing_summary_preview_enabled');
    const value = Array.isArray(response) && response.length > 0 ? response[0].value : null;
    generalBillingSummaryEnabled.value = value === true || value === 'true';
  } catch (error) {
    console.error(error);
    generalBillingSummaryEnabled.value = false;
  }
};

const runningTasks = computed(() => fullQueueList.value.filter(item => item.status === 'running'));
const pendingTasks = computed(() => fullQueueList.value.filter(item => item.status === 'pending'));
const finishedTasks = computed(() => fullQueueList.value.filter(item => ['completed', 'failed', 'skipped', 'warning'].includes(item.status)));

const checkQueueStatus = async () => {
  try {
    const queueList = await $ReportsApiService.getReportsQueue();
    if (queueList && Array.isArray(queueList)) {
      fullQueueList.value = queueList;
    }
  } catch (err) {
    console.error('Error checking reports queue:', err);
  }
};

const queueActionLoadingId = ref(null);

const confirmMessages = {
  kill: 'confirmation_text_block.confirm_kill_queue_task',
  skip: 'confirmation_text_block.confirm_skip_queue_task',
  restart: 'confirmation_text_block.confirm_restart_queue_task',
};

const sendQueueAction = async (item, action) => {
  if (!confirm(t(confirmMessages[action]))) return;
  queueActionLoadingId.value = item.id;
  try {
    await $ReportsApiService.sendReportsQueueAction(item.id, action);
    await checkQueueStatus();
  } catch (err) {
    console.error(`Error sending '${action}' to report queue item ${item.id}:`, err);
    toast.error(t('reports_block.error_queue_action') || 'Error en gestionar la tasca.');
  } finally {
    queueActionLoadingId.value = null;
  }
};
const pending = ref(true);
const error = ref(null);
const items = ref([]);
const processingStatusTokens = ref([]);
const searchInput = ref('');
const sortBy = ref('id');
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
    const data = await $ReportsApiService.getPermissions();
    permissions.value = data;
  } catch (err) {
    error.value = err;
  }
}

const getData = async (searchQuery = '', filters = [], page = 1, sort = 'id', desc = true) => {
  if (!permissions.value?.can_view) {
    toast.error(t('common.no_permissions'));
    return navigateTo('/');
  }
  pending.value = true;
  error.value = null;
  try {
    const data = await $ReportsApiService.getAll(searchQuery, filters, page, sort, desc);

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

const resetFilters = () => {
  searchInput.value = '';
  pagination.value.page = 1;
  getData();
};

const downloadDocument = async (id) => {
  try {
    const document_file = await $DocumentManagerApiService.getDetail(id)
    const file = await $DocumentManagerApiService.viewDocument(id);
    const link = document.createElement('a');
    const file_url = URL.createObjectURL(file);
    link.href = file_url;
    link.download = `report_${id}.xlsx`;

    link.click();

    setTimeout(() => {
      window.URL.revokeObjectURL(file_url);
    }, 250);

  } catch (error) {
    console.log(error)
  }
}

const downloadQueueDocument = async (documentId, documentName) => {
  try {
    const file = await $DocumentManagerApiService.viewDocument(documentId);
    const link = document.createElement('a');
    const file_url = URL.createObjectURL(file);
    link.href = file_url;
    link.download = documentName || `report_${documentId}.xlsx`;
    link.click();
    setTimeout(() => {
      window.URL.revokeObjectURL(file_url);
    }, 250);
  } catch (error) {
    console.error('Error downloading queue document:', error);
    toast.error(t('reports_block.error_downloading_document') || 'Error al descarregar el document.');
  }
}

onMounted(async () => {
  await getPermissions();
  if (permissions.value?.can_view) {
    getData();
  } else {
    toast.error(t('common.no_permissions'));
    pending.value = false;
    return navigateTo('/');
  }
  checkQueueStatus();
  queueInterval.value = setInterval(checkQueueStatus, 5000);
  loadGeneralBillingSummaryConfig();
});

onUnmounted(() => {
  clearInterval(queueInterval.value);
});

const detail = ref(null);
const selectedItemId = ref(null);

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

const isSubRegionOpen = ref(false);
const handleSubRegionEvent = (event) => {
  isSubRegionOpen.value = event;
}

// Etiquetes llegibles dels camps de filtre coneguts, enviats a `triggerReport` (veure add.vue)
// S'espera que el backend retorni `filters_display` (array de {label, value} ja resolts, p. ex.
// tokens/noms en lloc d'ids) i/o `filters` (payload cru) a cada item de report/report-queue.
const FILTER_LABELS = {
  date_range: 'reports_block.filter_date_range',
  start_date: 'reports_block.filter_start_date',
  end_date: 'reports_block.filter_end_date',
  exploitation_id: 'reports_block.filter_exploitation',
  billing_ids: 'reports_block.filter_billings',
  remittance_ids: 'reports_block.filter_remittances',
  person_ids: 'reports_block.filter_persons',
  contract_ids: 'reports_block.filter_contracts',
  report_type_id: 'reports_block.filter_report_type',
  include_preinvoices: 'reports_block.filter_include_preinvoices',
  include_tax_free_lines: 'reports_block.filter_include_tax_free_lines',
  model_347_year: 'reports_block.filter_year',
  product_ids: 'reports_block.filter_products',
  payment_type_ids: 'reports_block.filter_payment_types',
};

const formatFilterEntries = (item) => {
  if (Array.isArray(item?.filters_display) && item.filters_display.length > 0) {
    return item.filters_display.map(f => ({ label: f.label, value: f.value }));
  }
  const raw = item?.filters;
  if (!raw || typeof raw !== 'object') return [];
  return Object.entries(raw)
    .filter(([key, value]) => value !== null && value !== undefined && value !== '' && key in FILTER_LABELS)
    .map(([key, value]) => ({ label: t(FILTER_LABELS[key]), value: Array.isArray(value) ? value.join(', ') : String(value) }));
};

const hasFilters = (item) => formatFilterEntries(item).length > 0;

// Popover flotant (Teleport a body, mateix patró que InvoiceEdit.vue) amb tots els filtres
// aplicats, mostrat en passar el ratolí per sobre de la icona (i) de la fila corresponent.
const showFiltersInfo = ref(false);
const filtersInfoPos = ref({ x: 0, y: 0 });
const activeFiltersItem = ref(null);
let hideFiltersTimeout = null;

const showFiltersPopover = (event, item) => {
  clearTimeout(hideFiltersTimeout);
  const rect = event.currentTarget.getBoundingClientRect();
  filtersInfoPos.value = { x: rect.right - 320, y: rect.bottom + 1 };
  activeFiltersItem.value = item;
  showFiltersInfo.value = true;
};
const hideFiltersPopover = () => {
  clearTimeout(hideFiltersTimeout);
  hideFiltersTimeout = setTimeout(() => {
    showFiltersInfo.value = false;
    activeFiltersItem.value = null;
  }, 150);
};
const cancelHideFiltersPopover = () => {
  clearTimeout(hideFiltersTimeout);
};

</script>

<template>
  <div id="wrapper" class="text-base">
    <div class="flex justify-between items-center mb-2">
      <H1 class="mb-2">{{ $t('common.reports') }}</H1>
      <div class="flex items-center gap-2">
        <NuxtLink to="/billing/reports/daily-activity-summary" class="button-secondary">{{ $t('daily_activity_block.title') }}</NuxtLink>
        <NuxtLink v-if="generalBillingSummaryEnabled" to="/billing/reports/general-billing-summary" class="button-secondary">{{ $t('reports_block.general_billing_summary') }}</NuxtLink>
        <NuxtLink v-if="permissions?.can_view" to="/billing/reports/add" class="button-primary">{{ $t('billing_block.new_report') }}</NuxtLink>
      </div>
    </div>

    <!-- Cua de Processos d'Informes -->
    <div v-if="fullQueueList.length > 0" class="mb-6 border border-slate-200 rounded-md bg-slate-50 p-4">
      <h3 class="text-sm font-bold text-slate-700 uppercase tracking-wider mb-3 flex items-center gap-2">
        <Icon name="fa6-solid:list-check" class="text-sky-600" />
        {{ $t('reports_queue_title') }}
      </h3>

      <!-- Processos Actius -->
      <div v-if="runningTasks.length > 0" class="mb-4">
        <div class="space-y-3 mt-2">
          <div v-for="item in runningTasks" :key="item.id" class="p-3 border border-amber-200 bg-amber-50/70 rounded-md">
            <div class="flex justify-between items-start mb-1 text-sm">
              <span class="font-semibold text-amber-900">
                {{ item.report_name || 'Report ' + item.report_id }}
              </span>
              <span class="text-xs font-bold px-2 py-0.5 rounded bg-amber-500 text-amber-800">
                {{ $t('running') }}
              </span>
            </div>
            <div class="text-xs text-amber-800 mb-1 flex items-center gap-1">
              <span>{{ item.processed_items }} / {{ item.total_items }} ({{ item.percent }}%)</span>
              <button v-if="hasFilters(item)" type="button"
                class="w-6 h-6 rounded-full flex flex-shrink-0 items-center justify-center bg-amber-100 text-amber-700 hover:bg-amber-200"
                :title="$t('reports_block.show_filters')"
                @mouseenter="showFiltersPopover($event, item)" @mouseleave="hideFiltersPopover">
                <Icon name="fa6-solid:circle-info" />
              </button>
            </div>
            <AtomsProgressBar :progress="item.percent" :error="false" />
            <div class="flex justify-end gap-2 mt-2">
              <button type="button" :disabled="queueActionLoadingId === item.id" @click="sendQueueAction(item, 'restart')"
                class="text-xs px-2 py-1 rounded border border-sky-300 text-sky-700 bg-white hover:bg-sky-50 flex items-center gap-1 disabled:opacity-50">
                <Icon :name="queueActionLoadingId === item.id ? 'fa6-solid:spinner' : 'fa6-solid:rotate-right'" :class="{ 'animate-spin': queueActionLoadingId === item.id }" />
                {{ $t('common.restart') || 'Reiniciar' }}
              </button>
              <button type="button" :disabled="queueActionLoadingId === item.id" @click="sendQueueAction(item, 'skip')"
                class="text-xs px-2 py-1 rounded border border-slate-300 text-slate-600 bg-white hover:bg-slate-100 flex items-center gap-1 disabled:opacity-50">
                <Icon name="fa6-solid:forward" />
                {{ $t('common.skip') || 'Saltar' }}
              </button>
              <button type="button" :disabled="queueActionLoadingId === item.id" @click="sendQueueAction(item, 'kill')"
                class="text-xs px-2 py-1 rounded border border-red-300 text-red-700 bg-white hover:bg-red-50 flex items-center gap-1 disabled:opacity-50">
                <Icon name="fa6-solid:ban" />
                {{ $t('common.kill_task') || 'Matar tasca' }}
              </button>
            </div>
          </div>
        </div>
      </div>

      <!-- Processos Pendents -->
      <div v-if="pendingTasks.length > 0" class="mb-4">
        <button type="button" @click="showPendingList = !showPendingList" class="w-full flex justify-between items-center py-1.5 text-xs font-semibold text-slate-500 uppercase hover:text-slate-800 transition-colors focus:outline-none">
          <span>{{ $t('queued_processes') }} ({{ pendingTasks.length }})</span>
          <Icon :name="showPendingList ? 'fa6-solid:chevron-down' : 'fa6-solid:chevron-right'" />
        </button>
        
        <div v-if="showPendingList" class="space-y-3 mt-2">
          <div v-for="item in pendingTasks" :key="item.id" class="p-3 border border-amber-200 bg-amber-50/70 rounded-md">
            <div class="flex justify-between items-start mb-1 text-sm">
              <span class="font-semibold text-amber-900">
                {{ item.report_name || 'Report ' + item.report_id }}
              </span>
              <span class="text-xs font-bold px-2 py-0.5 rounded bg-slate-200 text-slate-700">
                {{ $t('queued_pending') }}
              </span>
            </div>
            <div class="text-xs text-amber-800 mb-1 flex items-center gap-1">
              <span>{{ $t('waiting_in_queue_turn') }}</span>
              <button v-if="hasFilters(item)" type="button"
                class="w-6 h-6 rounded-full flex flex-shrink-0 items-center justify-center bg-amber-100 text-amber-700 hover:bg-amber-200"
                :title="$t('reports_block.show_filters')"
                @mouseenter="showFiltersPopover($event, item)" @mouseleave="hideFiltersPopover">
                <Icon name="fa6-solid:circle-info" />
              </button>
            </div>
          </div>
        </div>
      </div>

      <!-- Historial de Processos Finalitzats -->
      <div v-if="finishedTasks.length > 0">
        <button type="button" @click="showFinishedList = !showFinishedList" class="w-full flex justify-between items-center py-1.5 text-xs font-semibold text-slate-500 uppercase hover:text-slate-800 transition-colors focus:outline-none">
          <span>{{ $t('last_finished_processes') }} ({{ finishedTasks.length }})</span>
          <Icon :name="showFinishedList ? 'fa6-solid:chevron-down' : 'fa6-solid:chevron-right'" />
        </button>
        
        <div v-if="showFinishedList" class="max-h-60 overflow-y-auto divide-y divide-slate-200 bg-white rounded-md border border-slate-200 mt-2">
          <div v-for="item in finishedTasks" :key="item.id" class="p-3 flex justify-between items-center text-sm">
            <div class="min-w-0">
              <p class="font-medium text-slate-700 truncate">
                {{ item.report_name || 'Report ' + item.report_id }}
              </p>
              <p v-if="item.status === 'warning' && item.error_message" class="text-xs text-amber-700 mt-1 italic">
                {{ item.error_message }}
              </p>
              <p v-else-if="item.status === 'failed' && item.error_message" class="text-xs text-red-600 mt-1 italic">
                Error: {{ item.error_message }}
              </p>
            </div>
            <div class="flex items-center gap-3 shrink-0">
              <button v-if="hasFilters(item)" type="button"
                class="w-8 h-8 rounded-full flex flex-shrink-0 items-center justify-center bg-slate-100 text-slate-500 hover:bg-slate-200"
                :title="$t('reports_block.show_filters')"
                @mouseenter="showFiltersPopover($event, item)" @mouseleave="hideFiltersPopover">
                <Icon name="fa6-solid:circle-info" />
              </button>
              <span class="text-xs text-slate-400">
                {{ item.completed_at ? new Date(item.completed_at).toLocaleString() : '' }}
              </span>
              <a v-if="item.status === 'completed' && item.document_url" :href="item.document_url.startsWith('http') ? item.document_url : useRuntimeConfig().public.apiHost + item.document_url" download class="text-sky-500 hover:text-sky-700 flex items-center gap-1 font-semibold mr-2" target="_blank">
                <Icon name="fa6-solid:download" />
                {{ $t('common.download') }}
              </a>
              <button v-else-if="item.status === 'completed' && item.document_id" @click="downloadQueueDocument(item.document_id, item.document_name)" class="text-sky-500 hover:text-sky-700 flex items-center gap-1 font-semibold mr-2">
                <Icon name="fa6-solid:download" />
                {{ $t('common.download') }}
              </button>
              <span class="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-semibold"
                :class="item.status === 'completed' ? 'bg-green-100 text-green-800' : item.status === 'skipped' ? 'bg-slate-200 text-slate-700' : item.status === 'warning' ? 'bg-amber-100 text-amber-800' : 'bg-red-100 text-red-800'">
                <Icon :name="item.status === 'completed' ? 'fa6-solid:circle-check' : item.status === 'skipped' ? 'fa6-solid:forward' : item.status === 'warning' ? 'fa6-solid:triangle-exclamation' : 'fa6-solid:circle-xmark'" />
                {{ item.status === 'completed' ? $t('correct') : item.status === 'skipped' ? $t('common.skip') : item.status === 'warning' ? $t('common.warning') : $t('failed') }}
              </span>
            </div>
          </div>
        </div>
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
      grid-template="0.5fr,1fr,1fr,0.5fr,0.2fr"
      :pending="pending"
      :error="error"
      :is-empty="items.length === 0"
      @retry="getData">
      <template #header>
        <TableHeader :label="$t('common.creation_date')" sortKey="created_at" :currentSortBy="sortBy" :sortDesc="sortDesc"
          @sort="handleSort" />
        <TableHeader :label="$t('common.name')" sortKey="name" :currentSortBy="sortBy" :sortDesc="sortDesc"
          @sort="handleSort" />
        <TableHeader :label="$t('common.doc')" :sortable="false" />
        <TableHeader :label="$t('common.type')" sortKey="type" :currentSortBy="sortBy" :sortDesc="sortDesc"
          @sort="handleSort" />
        <TableHeader :label="$t('reports_block.filters')" :sortable="false" />
      </template>

      <template #default="{ gridStyle }">
        <div v-for="item in items" :key="item.id"
          class="gap-3 text-base border-b items-center bg-white"
          :style="gridStyle"
          :class="{ 'bg-yellow-50': item.id === selectedItemId }">
          <span class="p-1 truncate">{{ formatDateTime(item.created_at) }}</span>
          <span class="p-0 truncate" :title="item.name || item.document_name || (item.type ? item.type.name : '')">{{ item.name || item.document_name || (item.type ? item.type.name : '') }}</span>
          <span class="min-w-0">
            <button class="group flex justify-between w-full items-center gap-1 p-1 text-sky-500 text-left min-w-0"
              @click="downloadDocument(item.document);">
              <abbr :title="item.token" class="no-underline truncate">{{ item.token }}</abbr>
              <Icon name="fa6-solid:eye"
                class="opacity-0 group-hover:opacity-100 text-slate-500 shrink-0 transition-opacity duration-200 ease-in-out" />
            </button>
          </span>
          <span class="p-0 truncate" :title="item.type ? item.type.name : t('common.no_type')">{{ item.type ? item.type.name : t('common.no_type') }}</span>
          <span class="p-1 flex items-center">
            <button v-if="hasFilters(item)" type="button"
              class="w-8 h-8 rounded-full flex flex-shrink-0 items-center justify-center transition-all duration-200 bg-slate-100 text-slate-500 hover:bg-slate-200"
              :title="$t('reports_block.show_filters')"
              @mouseenter="showFiltersPopover($event, item)" @mouseleave="hideFiltersPopover">
              <Icon name="fa6-solid:circle-info" />
            </button>
            <span v-else class="text-slate-300">-</span>
          </span>
          <!-- <span class="p-1">
            <AtomsProcessColorBadge @refresh="resetFilters" v-if="processingStatusTokens.findIndex(i => i == item.status?.token?.toString()) != -1" :value="item.status?.name" :color="item.status?.color" :taskId="item.task_id"></AtomsProcessColorBadge>
            <AtomsColorBadge v-else :value="item.status?.name" :color="item.status?.color"></AtomsColorBadge>
          </span> -->
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

    </div>
  </div>

  <!-- Popover flotant amb els filtres aplicats a un informe (mateix patró que InvoiceEdit.vue) -->
  <Teleport to="body">
    <div v-if="showFiltersInfo && activeFiltersItem"
      class="fixed z-[9999] w-80 rounded-lg border border-slate-200 bg-white shadow-lg text-sm"
      :style="{ top: filtersInfoPos.y + 'px', left: filtersInfoPos.x + 'px' }"
      @mouseenter="cancelHideFiltersPopover" @mouseleave="hideFiltersPopover">
      <div class="px-3 py-2 border-b border-slate-100 font-semibold text-slate-700 flex items-center gap-2">
        <Icon name="fa6-solid:circle-info" class="text-slate-400" />
        {{ $t('reports_block.show_filters') }}
      </div>
      <div class="px-3 py-2 space-y-1.5 max-h-80 overflow-y-auto">
        <div v-for="(f, idx) in formatFilterEntries(activeFiltersItem)" :key="idx" class="flex gap-2">
          <span class="text-slate-400 shrink-0 w-32">{{ f.label }}:</span>
          <span class="text-slate-700 font-medium break-words">{{ f.value }}</span>
        </div>
      </div>
    </div>
  </Teleport>
</template>
