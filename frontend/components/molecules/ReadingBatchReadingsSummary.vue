<script setup>
import { ref, computed, onMounted, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import debounce from 'lodash.debounce';
import _ from 'lodash';
import H1 from '~/components/atoms/H1.vue';
import { useToast } from 'vue-toastification';
import EstimateReadingsDialog from '~/components/molecules/EstimateReadingsDialog.vue';
import DataTable from '~/components/organisms/DataTable.vue';

const { t } = useI18n();
const { $ReadingBatchApiService, $ReadingApiService, $ConfiglistApiService, $ConfigProjectApiService } = useNuxtApp();

const props = defineProps({
  batch_id: Number,
  counters: Object,
  defaultReadingDate: String,
  estimateReadingsTaskId: String,
  isSubRegion: {
    type: Boolean,
    default: false
  },
  allow_force_manual: {
    type: Boolean,
    default: false
  }
});

const toast = useToast();
const emit = defineEmits(['refresh', 'allowContinue', 'show-subregion']);

const totalReaderAlerts = computed(() => {
  const breakdown = counters.value?.reader_alert_breakdown || {};
  return Object.values(breakdown).reduce((sum, count) => sum + Number(count || 0), 0);
});

const pagination = ref({
  page: 1,
  perPage: 50,
  total: 0,
  totalPages: 0,
  previous: null,
  next: null,
  isFiltered: false
});

const loadingReadings = ref(false);
const estimatingReadings = ref(false);
const batch_id = ref(props.batch_id)
const counters = ref(null)
const orderTypes = ref([]);
const orderTypeReadMeter = ref({});
const orderStatuses = ref([]);

const reading_date = ref(props.defaultReadingDate);

const remoteAlerts = ref([])

const numReadings = ref(0)
const numMissingReadings = ref(0)
const numExtraReadings = ref(0)
const numReadingsWithReaderAlert = ref(0)
const numReadingWithoutReadingValue = ref(0)
const numReadingsWithRemoteReader = ref(0)
const numReadingsWithRemoteAlert = ref(0)
const numReadingsInactiveSupplyPoints = ref(0)
const numNoRouteSupplyPoints = ref(0)

const showingDetailId = ref(0)
const subRegionId = ref(0)
const subRegionEntity = ref('')

const showReadings = ref([])

const search_filter = ref('')
const searchInput = ref('');
const title = ref('')

const estimateReadingsTaskId = ref(null)

const showRegion = ref(false);
const showSubRegion = ref(false);
const toggleRegion = (force) => {
  showRegion.value = force !== undefined ? force : !showRegion.value;
}
const toggleSubRegion = (force) => {
  showSubRegion.value = force !== undefined ? force : !showSubRegion.value;
}

const showEstimateReadingsDialog = ref(false);
const estimateReadingsConfig = ref({ all: false, extra_filter: null });

const allowUpdateForceManual = ref(props.allow_force_manual);
const updatingForceManual = ref(false);
const creatingMissingBatch = ref(false);

const updateForceManual = async () => {
  updatingForceManual.value = true;
  try {
    const response = await $ReadingBatchApiService.updateForceManual(batch_id.value);
    if (response) {
      toast.success(t('common.correct_save'));
      toggleRegion(false);
      emit('refresh');
    }
  } catch (err) {
    console.error(err);
  } finally {
    allowUpdateForceManual.value = false;
    updatingForceManual.value = false;
  }
}

/**
 * Crea un lot de lectures nou que conté NOMÉS els subministraments d'aquest lot
 * que han quedat sense lectura (no tot el padró). El backend calcula la llista
 * amb el mateix criteri que el llistat de "Subministraments sense lectura" i
 * fixa el nou lot pels seus comptadors, de manera que no cal triar rutes.
 */
const createMissingReadingsBatch = async () => {
  const name = window.prompt(t('billing_block.new_missing_readings_batch_prompt'));
  if (!name) return;

  creatingMissingBatch.value = true;
  try {
    const response = await $ReadingBatchApiService.createMissingBatch(
      batch_id.value,
      `Sub. sense lectura - ${name}`
    );

    if (response?.id) {
      toast.success(t('billing_block.missing_readings_batch_created', { count: response.num_supply_points }));
      await navigateTo(`/reading/reading-batches/edit/${response.id}?step=2`);
    }
  } catch (err) {
    // $apiManager ja mostra el toast amb el `detail` retornat pel backend.
    console.error(err);
  } finally {
    creatingMissingBatch.value = false;
  }
};

const loadingMore = ref(false);

const getData = async (page = 1, filter = '', append = false) => {
  if (append) {
    loadingMore.value = true;
  } else {
    loadingReadings.value = true;
  }
  try {
    const result = filter === 'assigned'
      ? await $ReadingApiService.getReadingsByBatchMinimal(batch_id.value, page, null, false, false, null, false, searchInput.value)
      : await $ReadingBatchApiService.getSetupReadings(batch_id.value, filter, page, searchInput.value);

    const pageResults = result.results || [];
    showReadings.value = append ? [...showReadings.value, ...pageResults] : pageResults;

    if (result.no_route_supply_points_count !== undefined) {
      numNoRouteSupplyPoints.value = result.no_route_supply_points_count;
    }

    Object.assign(pagination.value, {
      page: page,
      total: result.count,
      totalPages: Math.ceil(result.count / (pagination.value.perPage || 50)),
      previous: result.previous,
      next: result.next,
      isFiltered: searchInput.value !== ''
    });

  } catch (err) {
    console.error(err);
  } finally {
    loadingReadings.value = false;
    loadingMore.value = false;
  }
}

const loadMoreOnScroll = (event) => {
  const el = event.target;
  if (loadingMore.value || loadingReadings.value) return;
  if (!pagination.value.next) return;
  if (el.scrollTop + el.clientHeight < el.scrollHeight - 150) return;
  getData(pagination.value.page + 1, search_filter.value, true);
}

const openDetail = (filter) => {
  title.value = '';
  switch (filter) {

    case 'assigned':
      title.value = 'assigned_readings';
      search_filter.value = 'assigned'
      break;
    case 'reader_alert':
      title.value = 'readings_with_reader_alert';
      search_filter.value = 'reader_alert'
      break;
    case 'missing':
      title.value = 'service_block.supplies_no_reading';
      search_filter.value = 'missing'
      break;
    case 'extra':
      title.value = 'discarded_readings';
      search_filter.value = 'extra'
      break;
    case 'remote_reader':
      title.value = 'remote_readings';
      search_filter.value = 'remote_reader'
      break;
    case 'remote_alert':
      title.value = 'billing_block.remote_alerts';
      search_filter.value = 'remote_alert'
      break;
    case 'no_reading_value':
      title.value = 'readings_without_reading_value';
      search_filter.value = 'no_reading_value'
      break;
    case 'inactive_sp':
      title.value = 'readings_inactive_supplypoints';
      search_filter.value = 'inactive_sp'
      break;
    case 'no_route':
      title.value = 'no_route_supply_points_count';
      search_filter.value = 'no_route'
      break;
  }
  pagination.value.page = 1;
  searchInput.value = '';
  if (filter != 'no_route') {
    getData(1, search_filter.value)
  }
  showRegion.value = true;
};

const estimateReadings = (all = false, extra_filter = null) => {
  estimateReadingsConfig.value = { all, extra_filter };
  showEstimateReadingsDialog.value = true;
}

const handleEstimateReadingsConfirm = async (params) => {
  try {
    estimatingReadings.value = true;
    const { all, extra_filter } = estimateReadingsConfig.value;

    const payload = {
      supply_points: all ? 'all' : showReadings.value.map(reading => reading.id),
      extra_filter: extra_filter,
      ...params
    };

    const response = await $ReadingBatchApiService.estimateReadings(batch_id.value, payload);
    if (response) {
      if (all && response.task_id) {
        estimateReadingsTaskId.value = response.task_id;
      } else {
        toast.success(t('billing_block.correct_estimates'));
        emit('refresh');
      }
    }
    showEstimateReadingsDialog.value = false;
    toggleRegion(false);
  } catch (err) {
    console.error(err);
  } finally {
    estimatingReadings.value = false;
  }
}

const loadData = async () => {
  if (props.counters) {
    console.log("props.estimateReadingsTaskId")
    console.log(props);
    counters.value = props.counters;
    console.log("counters")
    console.log(counters.value);
    numReadings.value = counters.value.assigned_readings;
    numMissingReadings.value = counters.value.missing_readings;
    numExtraReadings.value = counters.value.discarded_readings;
    numReadingsWithReaderAlert.value = counters.value.readings_with_reader_alerts;
    numReadingWithoutReadingValue.value = counters.value.readings_without_reading_value;
    numReadingsWithRemoteReader.value = counters.value.readings_remote_reading;
    numReadingsWithRemoteAlert.value = counters.value.readings_with_remote_alerts;
    numReadingsInactiveSupplyPoints.value = counters.value.readings_inactive_supplypoints;
    numNoRouteSupplyPoints.value = counters.value.no_route_supply_points_count || 0;
    estimateReadingsTaskId.value = props.estimateReadingsTaskId;
    //emit('allowContinue', numReadingWithoutReadingValue.value > 0);
    setupData();
  }
};

const loadRemoteAlerts = async () => {
  try {
    const response = await $ConfiglistApiService.getAll('billing/remote-reading-alert');
    response.results.forEach(item => {
      remoteAlerts.value.push({
        value: item.id,
        label: item.name
      });
    });
  } catch (err) {
    console.error(err);
  }
}

const setupData = async () => {
  const order_types = await $ConfiglistApiService.getAll('order/order-type');
  orderTypes.value = order_types.results;
  const order_type_token = await $ConfigProjectApiService.get('order_type_read_meter_token');
  orderTypeReadMeter.value = order_types.results.find(item => item.token == order_type_token);

  // carreguem els status de orders
  const order_statuses = await $ConfiglistApiService.getAll('order/order-status');
  orderStatuses.value = order_statuses.results;
};

const openRegion = (e) => {
  subRegionId.value = e.id;
  subRegionEntity.value = e.entity;
  showSubRegion.value = true;
}
const onShowDetail = (id) => {
  showingDetailId.value = id;
}

const handleSearch = () => {
  pagination.value.page = 1;
  debouncedGetData();
}

const debouncedGetData = debounce(() => {
  getData(pagination.value.page, search_filter.value);
}, 300);

const { fetchFireUsageTypeTokens, isFireContract } = useFireUsageTypeTokens();

onMounted(async () => {
  loadData();
  loadRemoteAlerts();
  await fetchFireUsageTypeTokens();
});

watch(() => props.counters, () => {
  loadData();
})

watch(() => props.estimateReadingsTaskId, () => {
  loadData();
})

</script>

<template>
  <div class="region__content pr-2 relative pb-24" :class="{ 'h-full overflow-y-auto': !isSubRegion }">
    <div id="wrapper" class="text-base">
      <h2 class="text-xl font-semibold mb-4">{{ $t('assigned_readings') }}</h2>
      <div v-if="estimateReadingsTaskId" class="mb-4 footering border border-gray-300 rounded-md bg-white max-w-md">
        <ul class="divide-y divide-gray-200">
          <li class="flex justify-between items-center p-4 relative group border-b-2 border-gray-400">
            <span class="font-bold">{{ t('readings') }}:</span>
            <span
              class="inline-flex items-center bg-green-300 text-slate-700 text-sm rounded-full px-2 py-1 ml-2 mr-5">{{
                numReadings }}</span>
            <div v-if="numReadings > 0"
              class="w-10 cursor-pointer opacity-0 group-hover:opacity-100 transition-all duration-150 bg-gradient-to-r from-transparent to-slate-300 h-full absolute top-0 right-0 flex items-center justify-center"
              @click="openDetail('assigned')">
              <Icon name="fa6-solid:eye" class="w-4 h-4 text-slate-500" />
            </div>
          </li>
          <li class="flex justify-between items-center p-4 relative group h-[75px] !border-t-2 !border-gray-400">
            <AtomsProcessColorBadge
              class="flex items-center w-full h-[50px] my-[2px] px-5 border border-green-500 rounded-md text-md"
              :taskId="estimateReadingsTaskId" @refresh="estimateReadingsTaskId = null; emit('refresh')"
              :value="t('common.estimating_readings')" :color="'green'" />
          </li>
        </ul>
      </div>
      <div v-else class="mb-4 grid grid-cols-1 lg:grid-cols-3 gap-4 items-start">
        <!-- Columna 1: Informació -->
        <div class="footering border border-gray-300 rounded-md bg-white">
          <ul class="divide-y divide-gray-100">
            <li class="flex justify-between items-center p-4 relative group border-b !border-gray-300">
              <span class="font-bold">Total {{ t('assigned_readings') }}:</span>
              <span
                class="inline-flex items-center bg-green-300 text-slate-700 text-sm rounded-full px-2 py-1 ml-2 mr-5">{{
                  numReadings }}</span>
            </li>
            <li class="flex justify-between items-center p-4 pl-8 relative group">
              <span class="font-bold">{{ t('remote_readings') }}:</span>
              <span v-if="numReadingsWithRemoteReader > 0"
                class="inline-flex items-center bg-cyan-400 text-slate-700 text-sm rounded-full px-2 py-1 ml-2 mr-3">{{
                  numReadingsWithRemoteReader }}</span>
              <span v-else class="inline-flex items-center text-slate-700 text-sm px-2 ml-2 mr-3">
                -
              </span>
              <div v-if="numReadingsWithRemoteReader > 0"
                class="w-10 cursor-pointer opacity-0 group-hover:opacity-100 transition-all duration-150 bg-gradient-to-r from-transparent to-slate-300 h-full absolute top-0 right-0 flex items-center justify-center"
                @click="openDetail('remote_reader')">
                <Icon name="fa6-solid:eye" class="w-4 h-4 text-slate-500" />
              </div>
            </li>
            <li class="p-4 pl-8 relative group">
              <div class="flex justify-between items-center">
                <span class="font-bold">{{ t('readings_with_reader_alert') }}:</span>
                <span v-if="numReadingsWithReaderAlert > 0"
                  class="inline-flex items-center bg-yellow-300 text-slate-700 text-sm rounded-full px-2 py-1 ml-2 mr-3">{{
                    numReadingsWithReaderAlert }}</span>
                <span v-else class="inline-flex items-center text-slate-700 text-sm px-2 ml-2 mr-3">
                  -
                </span>
                <div v-if="numReadingsWithReaderAlert > 0"
                  class="w-10 cursor-pointer opacity-0 group-hover:opacity-100 transition-all duration-150 bg-gradient-to-r from-transparent to-slate-300 h-full absolute top-0 right-0 flex items-center justify-center"
                  @click="openDetail('reader_alert')">
                  <Icon name="fa6-solid:eye" class="w-4 h-4 text-slate-500" />
                </div>
              </div>
            </li>
            <li class="p-4 pl-8 relative group">
              <div class="flex justify-between items-center">
                <span class="font-bold">{{ t('readings_with_remote_alert') }}:</span>
                <span v-if="numReadingsWithRemoteAlert > 0"
                  class="inline-flex items-center bg-yellow-300 text-slate-700 text-sm rounded-full px-2 py-1 ml-2 mr-3">{{
                    numReadingsWithRemoteAlert }}</span>
                <span v-else class="inline-flex items-center text-slate-700 text-sm px-2 ml-2 mr-3">
                  -
                </span>
                <div v-if="numReadingsWithRemoteAlert > 0"
                  class="w-10 cursor-pointer opacity-0 group-hover:opacity-100 transition-all duration-150 bg-gradient-to-r from-transparent to-slate-300 h-full absolute top-0 right-0 flex items-center justify-center"
                  @click="openDetail('remote_alert')">
                  <Icon name="fa6-solid:eye" class="w-4 h-4 text-slate-500" />
                </div>
              </div>
            </li>
            <li v-if="totalReaderAlerts > 0" class="flex justify-between items-center p-4 pl-8 relative group">
              <span class="font-bold">{{ t('billing_block.reader_alerts') }}:</span>
              <span class="inline-flex items-center bg-red-100 text-red-700 text-sm rounded-full px-2 py-1 ml-2 mr-3">{{
                totalReaderAlerts }}</span>
              <div
                class="w-10 cursor-pointer opacity-0 group-hover:opacity-100 transition-all duration-150 bg-gradient-to-r from-transparent to-slate-300 h-full absolute top-0 right-0 flex items-center justify-center"
                :title="t('billing_block.view_alert_readings')"
                @click="emit('show-subregion', { type: 'reader-alerts' })">
                <Icon name="fa6-solid:triangle-exclamation" class="w-4 h-4 text-red-500" />
              </div>
            </li>
            <li class="flex justify-between items-center p-4 pl-8 relative group">
              <span class="font-bold">{{ t('discarded_readings') }}:</span>
              <span v-if="numExtraReadings > 0"
                class="inline-flex items-center bg-orange-400 text-slate-700 text-sm rounded-full px-2 py-1 ml-2 mr-3">{{
                  numExtraReadings }}</span>
              <span v-else class="inline-flex items-center text-slate-700 text-sm px-2 ml-2 mr-3">
                -
              </span>
              <div v-if="numExtraReadings > 0"
                class="w-10 cursor-pointer opacity-0 group-hover:opacity-100 transition-all duration-150 bg-gradient-to-r from-transparent to-slate-300 h-full absolute top-0 right-0 flex items-center justify-center"
                @click="openDetail('extra')">
                <Icon name="fa6-solid:eye" class="w-4 h-4 text-slate-500" />
              </div>
            </li>
          </ul>
        </div>

        <!-- Columna 2: Avisos que requereixen acció -->
        <div class="space-y-2">
          <div class="footering border border-amber-300 rounded-md bg-white">
            <ul class="divide-y divide-gray-100">
              <li class="flex justify-between items-center p-4 relative group">
                <span class="font-bold">{{ t('readings_without_reading_value') }}:</span>
                <span v-if="numReadingWithoutReadingValue > 0"
                  class="inline-flex items-center bg-red-500 text-white text-sm rounded-full px-2 py-1 ml-2 mr-3">{{
                    numReadingWithoutReadingValue }}</span>
                <span v-else class="inline-flex items-center text-slate-700 text-sm px-2 ml-2 mr-3">
                  -
                </span>
                <div v-if="numReadingWithoutReadingValue > 0"
                  class="w-10 cursor-pointer opacity-0 group-hover:opacity-100 transition-all duration-150 bg-gradient-to-r from-transparent to-slate-300 h-full absolute top-0 right-0 flex items-center justify-center"
                  @click="openDetail('no_reading_value')">
                  <Icon name="fa6-solid:eye" class="w-4 h-4 text-slate-500" />
                </div>
              </li>
              <li class="flex justify-between items-center p-4 relative group">
                <span class="font-bold">{{ t('readings_inactive_supplypoints') }}:</span>
                <span v-if="numReadingsInactiveSupplyPoints > 0"
                  class="inline-flex items-center bg-stone-500 text-white text-sm rounded-full px-2 py-1 ml-2 mr-3">{{
                    numReadingsInactiveSupplyPoints }}</span>
                <span v-else class="inline-flex items-center text-slate-700 text-sm px-2 ml-2 mr-3">
                  -
                </span>
                <div v-if="numReadingsInactiveSupplyPoints > 0"
                  class="w-10 cursor-pointer opacity-0 group-hover:opacity-100 transition-all duration-150 bg-gradient-to-r from-transparent to-slate-300 h-full absolute top-0 right-0 flex items-center justify-center"
                  @click="openDetail('inactive_sp')">
                  <Icon name="fa6-solid:eye" class="w-4 h-4 text-slate-500" />
                </div>
              </li>
              <li class="flex justify-between items-center p-4 relative group">
                <span class="font-bold">{{ t('no_route_supply_points_count') }}:</span>
                <span v-if="numNoRouteSupplyPoints > 0"
                  class="inline-flex items-center bg-orange-300 text-slate-700 text-sm rounded-full px-2 py-1 ml-2 mr-3">{{
                    numNoRouteSupplyPoints }}</span>
                <span v-else class="inline-flex items-center text-slate-700 text-sm px-2 ml-2 mr-3">
                  -
                </span>
                <div v-if="numNoRouteSupplyPoints > 0"
                  class="w-10 cursor-pointer opacity-0 group-hover:opacity-100 transition-all duration-150 bg-gradient-to-r from-transparent to-slate-300 h-full absolute top-0 right-0 flex items-center justify-center"
                  @click="openDetail('no_route')">
                  <Icon name="fa6-solid:eye" class="w-4 h-4 text-slate-500" />
                </div>
              </li>
            </ul>
          </div>
          <div v-if="numReadingWithoutReadingValue > 0"
            class="footering border border-red-300 rounded-md bg-red-50 px-4 py-2 flex items-center">
            <Icon name="fa6-solid:circle-exclamation" class="w-4 h-4 text-red-600 mr-3 flex-shrink-0" />
            <span class="font-semibold text-red-800 text-sm leading-relaxed">{{
              t('informative_block.info_readings_without_reading_value') }}</span>
          </div>
          <div v-if="numNoRouteSupplyPoints > 0"
            class="footering border border-orange-300 rounded-md bg-orange-50 px-4 py-2 flex items-center cursor-pointer hover:bg-orange-100 transition-all"
            @click="openDetail('no_route')">
            <Icon name="fa6-solid:circle-exclamation" class="w-4 h-4 text-orange-600 mr-3 flex-shrink-0" />
            <span class="font-semibold text-orange-800 text-sm leading-relaxed">{{
              t('informative_block.info_no_route_supply_points', { count: numNoRouteSupplyPoints }) }}</span>
          </div>
        </div>

        <!-- Columna 3: Subministraments sense lectura -->
        <div class="footering border border-red-300 rounded-md bg-white">
          <ul>
            <li class="flex justify-between items-center p-4 relative group">
              <span class="font-bold">{{ t('service_block.supplies_no_reading') }}:</span>
              <span v-if="numMissingReadings > 0"
                class="inline-flex items-center bg-red-400 text-slate-700 text-sm rounded-full px-2 py-1 ml-2 mr-5">{{
                  numMissingReadings }}</span>
              <span v-else class="inline-flex items-center text-slate-700 text-sm px-2 ml-2 mr-5">
                -
              </span>
              <div v-if="numMissingReadings > 0"
                class="w-10 cursor-pointer opacity-0 group-hover:opacity-100 transition-all duration-150 bg-gradient-to-r from-transparent to-slate-300 h-full absolute top-0 right-0 flex items-center justify-center"
                @click="openDetail('missing')">
                <Icon name="fa6-solid:eye" class="w-4 h-4 text-slate-500" />
              </div>
            </li>
          </ul>
        </div>
      </div>
      <div role="region"
        class="fixed h-full border-l border-gray-100 top-0 right-0 transition-all duration-500 ease py-2 text-base bg-white w-[90%] z-20 overflow-hidden flex flex-col"
        :class="{ 'translate-x-0': showRegion, 'translate-x-[2000px]': !showRegion, }">
        <div id="region_nav" class="mb-3 px-3">
          <button @click="toggleRegion(false)" class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300">
            <Icon name="fa6-solid:angles-right" class="text-slate-500" />
          </button>
        </div>
        <div v-if="search_filter == 'missing'" class="px-10 flex flex-col h-full">
          <H1>{{ t(title) }}</H1>
          <span class="input-group flex flex-start items-center gap-2 w-80 mb-4">
            <Icon name="fa6-solid:magnifying-glass" class="text-slate-500" />
            <input v-model="searchInput" @input="handleSearch" id="searchInput" type="text" name="search"
              :placeholder="$t('contract_block.search_by_token')"
              class="w-full p-1 rounded-md focus:outline-none focus-visible:border-0" autocomplete="off" />
          </span>
          <div class="grid grid-cols-2 flex items-start gap-x-2">
            <div class="w-full">
              <button type="button" class="button-default w-full flex items-center gap-2"
                :disabled="creatingMissingBatch || numMissingReadings === 0"
                :title="t('billing_block.new_missing_readings_batch_info', { count: numMissingReadings })"
                @click="createMissingReadingsBatch">
                <Icon :name="creatingMissingBatch ? 'fa6-solid:spinner' : 'fa6-solid:plus'"
                  :class="{ 'animate-spin': creatingMissingBatch }" />
                {{ $t('billing_block.new_missing_readings_batch') }}
              </button>
              <p class="mt-1 text-xs text-slate-500 leading-snug flex items-start gap-1">
                <Icon name="fa6-solid:circle-info" class="w-3 h-3 mt-[3px] flex-shrink-0 text-slate-400" />
                <span>{{ t('billing_block.new_missing_readings_batch_info', { count: numMissingReadings }) }}</span>
              </p>
            </div>
            <div class="w-full">
              <button type="button" :disabled="!props.allow_force_manual"
                class="button-default w-full flex items-center gap-2"
                :class="{ 'text-orange-600 cursor-not-allowed': !props.allow_force_manual }" @click="updateForceManual">
                <Icon v-if="props.allow_force_manual"
                  :name="updatingForceManual ? 'fa6-solid:spinner' : 'fa6-solid:pencil'"
                  :class="{ 'animate-spin': updatingForceManual }" />
                <span :class="{ 'text-orange-500 italic': !props.allow_force_manual }">
                  {{ props.allow_force_manual ?
                    $t('billing_block.update_reading_force_manual') :
                    $t('billing_block.unallow_update_reading_force_manual') }}
                </span>
              </button>
            </div>
          </div>
          <div class="overflow-y-auto flex-grow pb-10" @scroll="loadMoreOnScroll">
            <div
              class="sticky top-0 z-10 grid grid-cols-[1.8fr,1.8fr,2fr,1fr,1.2fr,1fr,0.8fr,1fr,1fr] gap-2 px-4 divide-x divide-gray-200 border-b border-gray-400 items-center bg-white">
              <span class="p-3 text-xs font-medium uppercase tracking-wider text-gray-400 truncate min-w-0">{{
                t('contract') }}</span>
              <span class="p-3 text-xs font-medium uppercase tracking-wider text-gray-400 truncate min-w-0">{{
                t('common.roles.HOLDER') }}</span>
              <span class="p-3 text-xs font-medium uppercase tracking-wider text-gray-400 truncate min-w-0">{{
                t('supply_point') }}</span>
              <span class="p-3 text-xs font-medium uppercase tracking-wider text-gray-400 truncate min-w-0">{{
                t('billing_block.last_reading') }}</span>
              <span class="p-3 text-xs font-medium uppercase tracking-wider text-gray-400 truncate min-w-0">{{
                t('billing_block.reading_date') }}</span>
              <span class="p-3 text-xs font-medium uppercase tracking-wider text-gray-400 truncate min-w-0">{{
                t('reading') }}</span>
              <span class="p-3 text-xs font-medium uppercase tracking-wider text-gray-400 truncate min-w-0">{{
                t('billing_block.leak') }}</span>
              <span class="p-3 text-xs font-medium uppercase tracking-wider text-gray-400 truncate min-w-0">{{
                t('billing_block.consumption') }}</span>
              <span class="p-3 flex items-center gap-2">
                <button class="button-default flex items-center" :disabled="estimatingReadings"
                  @click="estimateReadings(true)">
                  <Icon v-if="estimatingReadings" name="fa6-solid:spinner" class="animate-spin mr-2" />
                  {{ estimatingReadings ? t('common.processing') : t('billing_block.estimate') }} {{ t('common.all') }}
                </button>
              </span>
            </div>
            <div v-for="reading in showReadings" :key="reading.id">
              <AtomsMissingReadingEdit @refresh="emit('refresh')" @open-region="openRegion" :batch_id="batch_id"
                :orderTypeReadMeter="orderTypeReadMeter" :orderStatuses="orderStatuses" :supply="reading"
                :showDetail="showingDetailId == reading.id" :readingDate="reading_date"
                :disableAll="estimatingReadings" />
            </div>
            <div v-if="loadingReadings" class="text-center py-4 flex items-center justify-center">
              {{ $t('common.loading') }}...
            </div>
            <div v-if="loadingMore" class="text-center py-4 flex items-center justify-center">
              <Icon name="fa6-solid:spinner" class="animate-spin mr-2" />
              {{ $t('common.loading') }}...
            </div>
            <div v-if="!loadingReadings && showReadings.length === 0" class="text-center py-8 text-sm text-slate-400">
              {{ $t('common.no_records') }}
            </div>
          </div>
        </div>
        <div v-else-if="search_filter == 'assigned'" class="px-10 flex flex-col h-full">
          <H1>{{ t(title) }}</H1>
          <span class="input-group flex flex-start items-center gap-2 w-80 mb-4">
            <Icon name="fa6-solid:magnifying-glass" class="text-slate-500" />
            <input v-model="searchInput" @input="handleSearch" id="searchInput" type="text" name="search"
              :placeholder="$t('contract_block.search_by_token')"
              class="w-full p-1 rounded-md focus:outline-none focus-visible:border-0" autocomplete="off" />
          </span>
          <DataTable grid-template="1.2fr,1fr,1fr,1fr,1fr,1fr" :loading="loadingReadings"
            :is-empty="showReadings.length === 0" :height-offset="300" @scroll="loadMoreOnScroll">
            <template #header>
              <span>{{ t('contract') }}</span>
              <span>{{ t('billing_block.reading_date') }}</span>
              <span>{{ t('reading') }}</span>
              <span>{{ t('billing_block.leak') }}</span>
              <span>{{ t('billing_block.consumption') }}</span>
              <span>{{ t('billing_block.estimated') }}</span>
            </template>
            <template #default="{ gridStyle }">
              <div v-for="reading in showReadings" :key="reading.id"
                class="gap-3 text-base border-b items-center bg-white" :style="gridStyle">
                <span class="p-1 flex items-center gap-1">
                  <span>{{ reading.contract }}</span>
                  <Icon v-if="reading.is_fire" name="mdi:fire-hydrant" class="text-red-500"
                    :title="t('common.fire_hydrant')" />
                </span>
                <span class="p-1">
                  <AtomsDate :date="reading.reading_date" />
                </span>
                <span class="p-1">{{ reading.reading_value }}</span>
                <span class="p-1">{{ reading.leak_value ?? '-' }}</span>
                <span class="p-1">{{ reading.calculated_value }}</span>
                <span class="p-1">
                  <Icon v-if="reading.is_estimated" name="fa6-solid:check" class="text-green-500" />
                  <span v-else>-</span>
                </span>
              </div>
              <div v-if="loadingMore" class="text-center py-4 flex items-center justify-center">
                <Icon name="fa6-solid:spinner" class="animate-spin mr-2" />
                {{ $t('common.loading') }}...
              </div>
            </template>
          </DataTable>
        </div>
        <div v-else-if="search_filter == 'extra'" class="px-10 flex flex-col h-full">
          <H1>{{ t(title) }}</H1>
          <span class="input-group flex flex-start items-center gap-2 w-80 mb-4">
            <Icon name="fa6-solid:magnifying-glass" class="text-slate-500" />
            <input v-model="searchInput" @input="handleSearch" id="searchInput" type="text" name="search"
              :placeholder="$t('contract_block.search_by_token')"
              class="w-full p-1 rounded-md focus:outline-none focus-visible:border-0" autocomplete="off" />
          </span>
          <DataTable grid-template="1.2fr,1.8fr,2fr,1fr" :loading="loadingReadings"
            :is-empty="showReadings.length === 0" :height-offset="300" @scroll="loadMoreOnScroll">
            <template #header>
              <span>{{ t('contract') }}</span>
              <span>{{ t('common.roles.HOLDER') }}</span>
              <span>{{ t('supply_point') }}</span>
              <span>{{ t('reading') }}</span>
            </template>
            <template #default="{ gridStyle }">
              <div v-for="reading in showReadings" :key="reading.id"
                class="gap-3 text-base border-b items-center bg-white" :style="gridStyle">
                <span class="p-1 flex items-center gap-1">
                  <span v-if="reading.contracts && reading.contracts.length > 0">{{ reading.contracts[0].token }}</span>
                  <Icon v-if="reading.contracts && reading.contracts.length > 0 && isFireContract(reading.contracts[0])"
                    name="mdi:fire-hydrant" class="text-red-500" :title="t('common.fire_hydrant')" />
                  <span v-else-if="!(reading.contracts && reading.contracts.length > 0)">-</span>
                </span>
                <span class="p-1">
                  <span v-if="reading.contracts && reading.contracts.length > 0">{{ reading.contracts[0].holder
                    }}</span>
                  <span v-else>-</span>
                </span>
                <span class="p-1">{{ reading.address }}</span>
                <span class="p-1">{{ reading.reading_value }}</span>
              </div>
              <div v-if="loadingMore" class="text-center py-4 flex items-center justify-center">
                <Icon name="fa6-solid:spinner" class="animate-spin mr-2" />
                {{ $t('common.loading') }}...
              </div>
            </template>
          </DataTable>
        </div>
        <div v-else-if="search_filter == 'remote_reader' || search_filter == 'remote_alert'"
          class="px-10 flex flex-col h-full">
          <H1>{{ t(title) }}</H1>
          <span class="input-group flex flex-start items-center gap-2 w-80 mb-4">
            <Icon name="fa6-solid:magnifying-glass" class="text-slate-500" />
            <input v-model="searchInput" @input="handleSearch" id="searchInput" type="text" name="search"
              :placeholder="$t('contract_block.search_by_token')"
              class="w-full p-1 rounded-md focus:outline-none focus-visible:border-0" autocomplete="off" />
          </span>
          <div class="overflow-y-auto flex-grow pb-10" @scroll="loadMoreOnScroll">
            <div
              class="sticky top-0 z-10 grid grid-cols-[1.8fr,1.8fr,1fr,100px,120px,1fr,1fr,1fr,1.5fr,1fr,1fr] gap-2 px-4 divide-x divide-gray-200 border-b border-gray-400 items-center bg-white">
              <span class="p-3 text-xs font-medium uppercase tracking-wider text-gray-400 truncate min-w-0">{{
                t('contract')
                }}</span>
              <span class="p-3 text-xs font-medium uppercase tracking-wider text-gray-400 truncate min-w-0">{{
                t('common.roles.HOLDER') }}</span>
              <span class="p-3 text-xs font-medium uppercase tracking-wider text-gray-400 truncate min-w-0">{{
                t('supply_point')
                }}</span>
              <span class="p-3 text-xs font-medium uppercase tracking-wider text-gray-400 truncate min-w-0">{{
                t('billing_block.last_reading') }}</span>
              <span class="p-3 text-xs font-medium uppercase tracking-wider text-gray-400 truncate min-w-0">{{
                t('billing_block.reading_date') }}</span>
              <span class="p-3 text-xs font-medium uppercase tracking-wider text-gray-400 truncate min-w-0">{{
                t('reading')
                }}</span>
              <span class="p-3 text-xs font-medium uppercase tracking-wider text-gray-400 truncate min-w-0">{{
                t('billing_block.leak') }}</span>
              <span class="p-3 text-xs font-medium uppercase tracking-wider text-gray-400 truncate min-w-0">{{
                t('billing_block.consumption') }}</span>
              <span class="p-3 text-xs font-medium uppercase tracking-wider text-gray-400 truncate min-w-0">{{
                t('billing_block.remote_alert') }}</span>
              <span class="p-3 text-xs font-medium uppercase tracking-wider text-gray-400 truncate min-w-0">{{
                t('common.photo')
                }}</span>
              <span class="p-3"></span>
            </div>
            <div v-for="reading in showReadings" :key="reading.id">
              <AtomsMissingReadingEdit @refresh="emit('refresh')" @open-region="openRegion" :batch_id="batch_id"
                :orderTypeReadMeter="orderTypeReadMeter" :orderStatuses="orderStatuses" :supply="reading"
                :remoteAlert="remoteAlerts" :showDetail="showingDetailId == reading.id" :readingDate="reading_date"
                :disableAll="estimatingReadings" />
            </div>
            <div v-if="loadingReadings" class="text-center py-4 flex items-center justify-center">
              {{ $t('common.loading') }}...
            </div>
            <div v-if="loadingMore" class="text-center py-4 flex items-center justify-center">
              <Icon name="fa6-solid:spinner" class="animate-spin mr-2" />
              {{ $t('common.loading') }}...
            </div>
            <div v-if="!loadingReadings && showReadings.length === 0" class="text-center py-8 text-sm text-slate-400">
              {{ $t('common.no_records') }}
            </div>
          </div>
        </div>
        <div
          v-else-if="search_filter == 'reader_alert' || search_filter == 'no_reading_value' || search_filter == 'inactive_sp'"
          class="px-10 flex flex-col h-full">
          <H1>{{ t(title) }}</H1>
          <span class="input-group flex flex-start items-center gap-2 w-80 mb-4">
            <Icon name="fa6-solid:magnifying-glass" class="text-slate-500" />
            <input v-model="searchInput" @input="handleSearch" id="searchInput" type="text" name="search"
              :placeholder="$t('contract_block.search_by_token')"
              class="w-full p-1 rounded-md focus:outline-none focus-visible:border-0" autocomplete="off" />
          </span>
          <div class="overflow-y-auto flex-grow pb-10" @scroll="loadMoreOnScroll">
            <div
              class="sticky top-0 z-10 grid grid-cols-[1.8fr,1.8fr,1fr,100px,120px,1fr,1fr,1fr,1.5fr,1fr,1fr] gap-2 px-4 divide-x divide-gray-200 border-b border-gray-400 items-center bg-white">
              <span class="p-3 text-xs font-medium uppercase tracking-wider text-gray-400 truncate min-w-0">
                {{ t('contract') }}</span>
              <span class="p-3 text-xs font-medium uppercase tracking-wider text-gray-400 truncate min-w-0">{{
                t('common.roles.HOLDER') }}</span>
              <span class="p-3 text-xs font-medium uppercase tracking-wider text-gray-400 truncate min-w-0">
                {{ t('supply_point') }}</span>
              <span class="p-3 text-xs font-medium uppercase tracking-wider text-gray-400 truncate min-w-0">{{
                t('billing_block.last_reading') }}</span>
              <span class="p-3 text-xs font-medium uppercase tracking-wider text-gray-400 truncate min-w-0">{{
                t('billing_block.reading_date') }}</span>
              <span class="p-3 text-xs font-medium uppercase tracking-wider text-gray-400 truncate min-w-0">
                {{ t('reading') }}</span>
              <span class="p-3 text-xs font-medium uppercase tracking-wider text-gray-400 truncate min-w-0">{{
                t('billing_block.leak') }}</span>
              <span class="p-3 text-xs font-medium uppercase tracking-wider text-gray-400 truncate min-w-0">{{
                t('billing_block.consumption') }}</span>
              <span class="p-3 text-xs font-medium uppercase tracking-wider text-gray-400 truncate min-w-0">{{
                t('billing_block.reader_alert') }}</span>
              <span class="p-3 text-xs font-medium uppercase tracking-wider text-gray-400 truncate min-w-0">
                {{ t('common.photo') }}</span>
              <span class="p-3">
                <button v-if="search_filter == 'no_reading_value'" class="button-default flex items-center"
                  :disabled="estimatingReadings" @click="estimateReadings(true, 'no_reading_value')">
                  <Icon v-if="estimatingReadings" name="fa6-solid:spinner" class="animate-spin mr-2" />
                  {{ estimatingReadings ? t('common.processing') : t('billing_block.estimate') }} {{ t('common.all') }}
                </button>
              </span>
            </div>
            <div v-for="reading in showReadings" :key="reading.id">
              <AtomsMissingReadingEdit @refresh="emit('refresh')" @open-region="openRegion" :batch_id="batch_id"
                :orderTypeReadMeter="orderTypeReadMeter" :orderStatuses="orderStatuses" :supply="reading"
                :readerAlert="true" :showDetail="showingDetailId == reading.id" :readingDate="reading_date"
                :disableAll="estimatingReadings" />
            </div>
            <div v-if="loadingReadings" class="text-center py-4 flex items-center justify-center">
              {{ $t('common.loading') }}...
            </div>
            <div v-if="loadingMore" class="text-center py-4 flex items-center justify-center">
              <Icon name="fa6-solid:spinner" class="animate-spin mr-2" />
              {{ $t('common.loading') }}...
            </div>
            <div v-if="!loadingReadings && showReadings.length === 0" class="text-center py-8 text-sm text-slate-400">
              {{ $t('common.no_records') }}
            </div>
          </div>
        </div>
        <div v-else-if="search_filter == 'no_route'" class="px-10 flex flex-col h-full">
          <MoleculesNoRouteSupplyPointsList :batchId="batch_id" :title="title" @openRegion="openRegion" />
        </div>
      </div>
      <div role="region" id="right_over_page"
        class="fixed h-full border-l border-gray-100 top-0 right-0 transition-all duration-500 ease py-2 text-base bg-white w-[60%] z-30 shadow"
        :class="{ 'translate-x-0': showSubRegion, 'translate-x-[2000px]': !showSubRegion }">
        <div id="region_nav" class="mb-3 px-3">
          <button @click="toggleSubRegion(false)" class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300">
            <Icon name="fa6-solid:angles-right" class="text-slate-500" />
          </button>
        </div>
        <div class="px-10">
          <OrganismsPersonRegion v-if="subRegionEntity == 'person'" :id="subRegionId" :isSubRegion="true" />
          <OrganismsContractRegion v-if="subRegionEntity == 'contract'" :id="subRegionId" :isSubRegion="true" />
          <OrganismsSupplyPointRegion v-if="subRegionEntity == 'supply_point'" :id="subRegionId" :isSubRegion="true" />
        </div>
      </div>
      <EstimateReadingsDialog :show="showEstimateReadingsDialog" :defaultReadingDate="reading_date"
        :loading="estimatingReadings" @close="showEstimateReadingsDialog = false"
        @confirm="handleEstimateReadingsConfirm" />
    </div>
  </div>
</template>
