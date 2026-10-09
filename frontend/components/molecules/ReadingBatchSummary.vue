<script setup>
import { ref, computed, onMounted, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import { useToast } from 'vue-toastification';
import debounce from 'lodash.debounce';
import _ from 'lodash';
import H1 from '~/components/atoms/H1.vue';
import ReadingExport from './ReadingExport.vue';
import Pagination from '~/components/molecules/Pagination.vue';
import TableHeader from '~/components/atoms/TableHeader.vue';

const { t } = useI18n();
const toast = useToast();
const { $apiManager, $ReadingApiService, $ReadingBatchApiService } = useNuxtApp();

const props = defineProps({
  batch_id: {
    type: Number,
    default: null
  },
  taskId: String,
  counters: Object,
  counters_pending: Object,
  initialFilter: String,
  isEmbedded: Boolean,
  isSubRegion: {
    type: Boolean,
    default: false
  }
});

const emit = defineEmits(['change', 'show-subregion']);

const pagination = ref({
  page: 1,
  perPage: 50,
  total: 0,
  totalPages: 0,
  previous: null,
  next: null,
  isFiltered: false
});

const error = ref(false);
const partialErrors = ref([]);
const loadingReadings = ref(false);
const progress = ref(0)
const batch_id = ref(props.batch_id)
const counters = ref(null)
const readings = ref([])

const numReadings = ref(0)
const numAlreadyBilled = ref(0)
const numSuccessReadings = ref(0)
const numWarningReadings = ref(0)

const showingDetailId = ref(0)
const subRegionId = ref(0)
const subRegionEntity = ref('')
const showLeak = ref(false)
const showLeakCurrent = ref(false)

const warningReadings = ref([])
const showReadings = ref([])
const allowChange = ref(false)

const searchInput = ref('');
const sortBy = ref('calculated_value');
const sortDesc = ref(false);
const search_filter = ref('')
const title = ref('')
const medianDuration = ref(0);
const numDateRangeWarnings = ref(0);

const selectedReadingIds = ref([]);
const recalculating = ref(false);

const toggleReadingSelection = (id) => {
  if (selectedReadingIds.value.includes(id)) {
    selectedReadingIds.value = selectedReadingIds.value.filter(x => x !== id);
  } else {
    selectedReadingIds.value = [...selectedReadingIds.value, id];
  }
};

const hasEstimatedSelected = computed(() =>
  selectedReadingIds.value.some(id => showReadings.value.find(r => r.id === id)?.is_estimated)
);

const recalculateSelected = async () => {
  const estimatedIds = selectedReadingIds.value.filter(id =>
    showReadings.value.find(r => r.id === id)?.is_estimated
  );
  if (!estimatedIds.length) return;
  recalculating.value = true;
  try {
    const response = await $ReadingApiService.recalculateEstimatedReadings(estimatedIds);
    if (response?.readings) {
      response.readings.forEach(updated => {
        const idx = showReadings.value.findIndex(r => r.id === updated.id);
        if (idx !== -1) showReadings.value[idx] = { ...showReadings.value[idx], ...updated };
      });
    }
    toast.success(t('billing_block.correct_recalculate_estimated'));
    selectedReadingIds.value = [];
  } catch (error) {
    toast.error(t('billing_block.error_recalculate_estimated'));
  } finally {
    recalculating.value = false;
  }
};

const pendingCounters = ref(null);
const numPendingReadings = ref(0);
const numPendingMissingReadings = ref(0);
const numPendingExtraReadings = ref(0);
const numPendingReadingsWithReaderAlert = ref(0);
const numPendingReadingWithoutReadingValue = ref(0);
const numPendingReadingsWithRemoteReader = ref(0);
const numPendingReadingsWithRemoteAlert = ref(0);
const numPendingReadingsInactiveSupplyPoints = ref(0);
const numPendingNoRouteSupplyPoints = ref(0);

const setPendingCounters = () => {
  if (!pendingCounters.value) return;
  const c = pendingCounters.value;
  numPendingReadings.value = (c.assigned_readings || 0) + (c.already_billed || 0);
  numPendingMissingReadings.value = c.missing_readings || 0;
  numPendingExtraReadings.value = c.discarded_readings || 0;
  numPendingReadingsWithReaderAlert.value = c.readings_with_reader_alerts || 0;
  numPendingReadingWithoutReadingValue.value = c.readings_without_reading_value || 0;
  numPendingReadingsWithRemoteReader.value = c.readings_remote_reading || 0;
  numPendingReadingsWithRemoteAlert.value = c.readings_with_remote_alerts || 0;
  numPendingReadingsInactiveSupplyPoints.value = c.readings_inactive_supplypoints || 0;
  numPendingNoRouteSupplyPoints.value = c.no_route_supply_points_count || 0;
};

const loadPendingCounters = async () => {
  if (!batch_id.value) return;
  try {
    const data = await $ReadingBatchApiService.getSummary(batch_id.value);
    if (data?.counters_pending) {
      const cp = data.counters_pending;
      const hasData = (cp.assigned_readings || 0) + (cp.already_billed || 0) > 0;
      if (hasData) {
        pendingCounters.value = cp;
        setPendingCounters();
      }
    }
    partialErrors.value = data?.last_task_status === 'partial' && Array.isArray(data?.last_task_errors)
      ? data.last_task_errors
      : [];
    if (data?.counters && Object.keys(data.counters).length > 0) {
      counters.value = data.counters;
      setCounters();
    }
  } catch (e) {
    console.error(e);
  }
};

const showPendingRegion = ref(false);
const pendingRegionTitle = ref('');
const pendingRegionFilter = ref('');
const showPendingReadings = ref([]);
const loadingPendingReadings = ref(false);
const pendingPagination = ref({ page: 1, next: null });

const getPendingReadings = async (filter, page = 1) => {
  loadingPendingReadings.value = true;
  try {
    if (page === 1) showPendingReadings.value = [];
    const result = await $ReadingBatchApiService.getSetupReadings(batch_id.value, filter, page, '');
    if (result.results) showPendingReadings.value.push(...result.results);
    pendingPagination.value = { page, next: result.next };
  } catch (e) {
    console.error(e);
  } finally {
    loadingPendingReadings.value = false;
  }
};

const openPendingDetail = (filter, titleKey) => {
  pendingRegionFilter.value = filter;
  pendingRegionTitle.value = t(titleKey);
  showPendingRegion.value = true;
  getPendingReadings(filter, 1);
};

const onPendingScroll = async (event) => {
  const { scrollTop, scrollHeight, clientHeight } = event.target;
  if (scrollTop + clientHeight >= scrollHeight - 50 && !loadingPendingReadings.value && pendingPagination.value.next) {
    await getPendingReadings(pendingRegionFilter.value, pendingPagination.value.page + 1);
  }
};

const showRegionComponent = ref(null);

const showRegion = ref(false);
const showSubRegion = ref(false);
const toggleRegion = (force) => {
  showRegion.value = force !== undefined ? force : !showRegion.value;
  if (!force){
    showRegionComponent.value = null;
  }
}
const toggleSubRegion = (force) => {
  showSubRegion.value = force !== undefined ? force : !showSubRegion.value;
  if (!force){
    pagination.value.page = 1;
  }
  emit('show-subregion', showSubRegion.value);
}

const getData = async (page = 1, filter = '', showLeak = false, showLeakCurrent = false) => {
  loadingReadings.value = true;
  try {
    const result = await $ReadingApiService.getReadingsByBatchMinimal(batch_id.value, page, filter, showLeak, showLeakCurrent, sortBy.value, sortDesc.value, searchInput.value);
    showReadings.value = result.results || [];

    if (result.date_range_median) medianDuration.value = result.date_range_median;

    Object.assign(pagination.value, {
      page: page,
      total: result.count,
      totalPages: Math.ceil(result.count / pagination.value.perPage),
      previous: result.previous,
      next: result.next,
      isFiltered: false
    });

  } catch (err) {
    console.error(err);
  } finally {
    loadingReadings.value = false;
  }
}

const handlePageChange = (newPage) => {
  pagination.value.page = newPage;
  getData(newPage, search_filter.value, showLeak.value, showLeakCurrent.value);
}

const sortReadingsBy = (field) => {
  if (field == sortBy.value) {
    sortDesc.value = !sortDesc.value;
  } else {
    sortBy.value = field;
    sortDesc.value = false;
  }
  getData(1, search_filter.value, showLeak.value, showLeakCurrent.value)
}

const exportCheckReadings = () => {
  showRegionComponent.value = "ExportReadings";
  showRegion.value = true;
}

const openDetail = (filter, warningName) => {
  pagination.value.page = 1;
  showReadings.value = [];
  selectedReadingIds.value = [];
  showRegionComponent.value = "readings";
  allowChange.value = false;
  title.value = '';
  showLeak.value = false;
  showLeakCurrent.value = false;
  switch (filter) {
    case 'all':
      // showReadings.value = readings.value;
      search_filter.value = ''
      break;
    case 'correct':
      title.value = t('billing_block.readings_correct');
      search_filter.value='alert=null'
      break;
    case 'warning':
      if (warningName) {
        title.value = warningName;
        search_filter.value='alert='+warningName
      } else {
        title.value = t('billing_block.readings_incorrect');
        search_filter.value='alert=any'
      }
      allowChange.value = true;
      break;
    case 'billed':
      title.value = t('already_billed');
      search_filter.value='billed=true'
      break;
  }
  getData(1, search_filter.value, showLeak.value, showLeakCurrent.value)
  showRegion.value = true;
};

const setCounters = () => {
  numReadings.value = counters.value.total;
  numAlreadyBilled.value = counters.value.total_billed;
  numWarningReadings.value = 0;
  warningReadings.value = [];
  
  if (counters.value.date_range_median) {
    medianDuration.value = counters.value.date_range_median;
  }

  for (let [key, value] of Object.entries(counters.value)) {
    if (key != 'total' && key != 'total_billed' && key != 'total_correct' && key != 'total_warnings' && key != 'date_range_median') {
      if (key === 'date_range_above_margin_count') {
        // Avís calculat a part: les lectures fora de marge poden tenir també una
        // alerta, per això no se sumen al total d'avisos.
        key = 'warning_date_range';
        numDateRangeWarnings.value = value;
      } else {
        numWarningReadings.value += value;
      }
      warningReadings.value.push({
        alert: key,
        count: value
      })
    }
  }
  // El backend envia els totals amb el mateix criteri que els llistats (alert=any / alert=null)
  if (counters.value.total_warnings !== undefined) numWarningReadings.value = counters.value.total_warnings;
  numSuccessReadings.value = counters.value.total_correct !== undefined
    ? counters.value.total_correct
    : numReadings.value - numWarningReadings.value;
}

const translateWarningAlert = (alertStr) => {
  if (!alertStr) return '';
  if (alertStr === 'Unusually low consumption') return t('billing_block.unusually_low_consumption');
  if (alertStr === 'Unusually high consumption') return t('billing_block.unusually_high_consumption');
  if (alertStr === 'Lectura 0') return t('billing_block.reading_zero') || 'Lectura 0';
  if (alertStr === 'Lectura Negativa') return t('billing_block.reading_negative') || 'Lectura negativa';
  if (alertStr === 'Lectura inusual') return t('billing_block.reading_unusual') || 'Lectura inusual';
  
  const blockKey = `billing_block.${alertStr}`;
  const translatedBlock = t(blockKey);
  if (translatedBlock !== blockKey) return translatedBlock;
  
  const globalKey = alertStr;
  const translatedGlobal = t(globalKey);
  if (translatedGlobal !== globalKey) return translatedGlobal;

  return alertStr;
};

const loadData = async () => {

  if (props.readings && props.readings.length > 0)
    readings.value = props.readings

  if (props.counters) {
    counters.value = props.counters
    progress.value = 100
    setCounters()
  }
  else if (props.taskId && !counters.value) {
    error.value = false;
    const interval = setInterval(async () => {
      try {
        const res = await $apiManager.checkTask(props.taskId)
        // console.log(res)
        if (res) {
          progress.value = res.percent || 0
          numReadings.value = res.current || 0
    
          if (res.state === 'SUCCESS') {
            clearInterval(interval)
            counters.value = res.result?.counters;
            partialErrors.value = res.result?.status === 'partial' ? (res.result?.errors || []) : [];
            progress.value = 100
            setCounters()
            loadPendingCounters()
            loadData();
          }
          else if (res.state === 'FAILURE') {
            error.value = true;
            clearInterval(interval)
          }
        }
      }
      catch (e) {
        console.log(e)
        clearInterval(interval)
      }
    }, 500)
  }
};

const leakFilter = async () => {
  pagination.value.page = 1;
  await getData(1, search_filter.value, showLeak.value, showLeakCurrent.value)
}

const leakCurrentFilter = async () => {
  pagination.value.page = 1;
  await getData(1, search_filter.value, showLeak.value, showLeakCurrent.value)
}

const handleSearch = () => {
  pagination.value.page = 1;
  debouncedGetData();
}

const debouncedGetData = debounce(() => {
  getData(pagination.value.page, search_filter.value, showLeak.value, showLeakCurrent.value);
}, 300);

const openRegion = (e, id) => {
  if (typeof e === 'string') {
    subRegionEntity.value = e;
    subRegionId.value = id;
  } else {
    subRegionEntity.value = e.entity;
    subRegionId.value = e.id;
  }
  toggleSubRegion(true);
}
const onShowDetail = (id) => {
  showingDetailId.value = id;
}

const showFixRegion = ref(false);
const fixReadingId = ref(null);
const fixReadingDetail = ref(null);
const fixReadingDateValue = ref('');
const fixLoading = ref(false);
const fixSaving = ref(false);

const openFixError = async (err) => {
  fixReadingId.value = err.reading_id;
  fixReadingDetail.value = null;
  fixReadingDateValue.value = '';
  showFixRegion.value = true;
  fixLoading.value = true;
  try {
    fixReadingDetail.value = await $ReadingApiService.getDetail(err.reading_id);
    fixReadingDateValue.value = fixReadingDetail.value?.reading_date || '';
  } catch (e) {
    console.error(e);
    toast.error(e?.data?.error || e?.message || t('common.error'));
  } finally {
    fixLoading.value = false;
  }
}

const closeFixRegion = () => {
  if (fixSaving.value) return;
  showFixRegion.value = false;
}

const saveFixReadingDate = async () => {
  if (!fixReadingDateValue.value || !fixReadingId.value) {
    toast.error(t('billing_block.reading_date'));
    return;
  }
  fixSaving.value = true;
  try {
    await $ReadingApiService.save({
      id: fixReadingId.value,
      reading_date: fixReadingDateValue.value
    });
    toast.success(t('common.correct_save'));
    partialErrors.value = partialErrors.value.filter(err => err.reading_id !== fixReadingId.value);
    showFixRegion.value = false;
    // Refresca la llista de lectures del lot i els comptadors pendents perque
    // la lectura corregida quedi reflectida (ja pertanyia al lot, nomes calia
    // completar-li la data per poder-la processar correctament).
    await getData(pagination.value.page, search_filter.value, showLeak.value, showLeakCurrent.value);
    await loadPendingCounters();
  } catch (e) {
    console.error(e);
    toast.error(e?.data?.error || e?.message || t('common.error'));
  } finally {
    fixSaving.value = false;
  }
}

onMounted(() => {
  loadData();
  if (props.initialFilter) {
    openDetail(props.initialFilter);
  }
  if (props.counters_pending) {
    pendingCounters.value = props.counters_pending;
    setPendingCounters();
  }
  // Sempre es crida, encara que counters_pending ja vingui per props: es l'unica
  // via per recuperar last_task_status/last_task_errors del darrer processament.
  loadPendingCounters();
});

watch(() => props.counters_pending, (newVal) => {
  if (newVal) {
    pendingCounters.value = newVal;
    setPendingCounters();
  }
});

watch(() => props.taskId, () => {
  progress.value = 0;
  readings.value = [];
  loadData();
})
watch(() => props.readings, () => {
  loadData();
})
watch(() => props.batch_id, (newVal) => {
  batch_id.value = newVal;
  loadData();
})


</script>

<template>
  <div class="region__content pr-2 relative pb-24" :class="{ 'h-full overflow-y-auto': !isSubRegion }">
  <div id="wrapper" class="text-base" :class="{'h-full flex overflow-hidden': isEmbedded}">
    <!-- Summary (Visible only when NOT embedded) -->
    <div v-if="!isEmbedded">
      <h2 class="text-xl font-semibold mb-2">{{ $t('common.summary') }} {{ $t('common.reading_batch_detail') }}</h2>
      <div v-if="medianDuration > 0" class="mb-4 text-sm text-slate-600 italic">
        {{ t('common.median') }}: <span class="font-bold font-mono">{{ medianDuration }} {{ t('common.days') }}</span>
      </div>

      <div class="mb-4 grid grid-cols-2 gap-x-2">
        <!-- LEFT: Processed readings summary -->
        <div class="footering border border-gray-300 rounded-md bg-white max-w-md">
          <AtomsProgressBar :progress="progress" :error="error"/>
          <div class="px-4" v-if="partialErrors.length > 0">
            <AtomsPartialErrorsBanner :errors="partialErrors" @fix-error="openFixError" />
          </div>
          <ul class="divide-y divide-gray-200">
            <li class="flex justify-between items-center p-4 relative group">
              <span class="font-bold">{{ t('all_readings') }}:</span>
              <span class="inline-flex items-center bg-slate-300 text-slate-700 text-sm rounded-full px-2 py-1 ml-2 mr-5">{{ numReadings }}</span>
              <div class="w-10 cursor-pointer opacity-0 group-hover:opacity-100 transition-all duration-150 bg-gradient-to-r from-transparent to-slate-300 h-full absolute top-0 right-0 flex items-center justify-center"
                @click="openDetail('all')">
                <Icon name="fa6-solid:eye" class="w-4 h-4 text-slate-500" />
              </div>
            </li>
            <li v-if="numAlreadyBilled > 0" class="flex justify-between items-center p-4 relative group">
              <div class="flex flex-col gap-y-1">
                <span class="font-bold">{{ t('already_billed') }}:</span>
                <span class="text-xs text-slate-400">{{ t('informative_block.info_already_billed') }}</span>
              </div>
              <span class="inline-flex items-center bg-slate-300 text-slate-700 text-sm rounded-full px-2 py-1 ml-2 mr-5">{{ numAlreadyBilled }}</span>
              <div class="w-10 cursor-pointer opacity-0 group-hover:opacity-100 transition-all duration-150 bg-gradient-to-r from-transparent to-slate-300 h-full absolute top-0 right-0 flex items-center justify-center"
                @click="openDetail('billed')">
                <Icon name="fa6-solid:eye" class="w-4 h-4 text-slate-500" />
              </div>
            </li>
            <li class="flex justify-between items-center p-4 relative group">
              <span class="font-bold">{{ t('billing_block.readings_correct') }}:</span>
              <span class="inline-flex items-center bg-green-300 text-slate-700 text-sm rounded-full px-2 py-1 ml-2 mr-5">{{ numSuccessReadings }}</span>
              <div class="w-10 cursor-pointer opacity-0 group-hover:opacity-100 transition-all duration-150 bg-gradient-to-r from-transparent to-slate-300 h-full absolute top-0 right-0 flex items-center justify-center"
                @click="openDetail('correct')">
                <Icon name="fa6-solid:eye" class="w-4 h-4 text-slate-500" />
              </div>
            </li>
            <li>
              <div class="flex relative group justify-between items-center p-4">
                <span class="font-bold">{{ t('common.warnings') }}:</span>
                <span class="inline-flex items-center bg-yellow-400 text-slate-700 text-sm rounded-full px-2 py-1 ml-2 mr-5">{{ numWarningReadings }}</span>
                <div v-if="numWarningReadings != 0" class="w-10 cursor-pointer opacity-0 group-hover:opacity-100 transition-all duration-150 bg-gradient-to-r from-transparent to-slate-300 h-full absolute top-0 right-0 flex items-center justify-center"
                  @click="openDetail('warning')">
                  <Icon name="fa6-solid:eye" class="w-4 h-4 text-slate-500" />
                </div>
              </div>
              <div v-for="warning in warningReadings" :key="warning.alert">
                <div class="flex justify-between items-center py-3 px-4 relative group">
                  <span class="pl-5 text-sm font-semibold">{{ translateWarningAlert(warning.alert) }}</span>
                  <span class="inline-flex items-center bg-yellow-400 text-slate-700 text-sm rounded-full px-2 py-1 ml-2 mr-5">{{ warning.count }}</span>
                  <div class="w-10 cursor-pointer opacity-0 group-hover:opacity-100 transition-all duration-150 bg-gradient-to-r from-transparent to-slate-300 h-full absolute top-0 right-0 flex items-center justify-center"
                    @click="openDetail('warning', warning.alert)">
                    <Icon name="fa6-solid:eye" class="w-4 h-4 text-slate-500" />
                  </div>
                </div>
              </div>
            </li>
          </ul>
        </div>

        <!-- RIGHT: Pending counters (step 3) + export button -->
        <div class="flex flex-col items-end gap-2">
          <div v-if="progress == 100">
            <button class="button-secondary flex items-center gap-2" @click="exportCheckReadings">
              <Icon name="fa6-solid:file-excel" />
              {{ $t('billing_block.export_check_readings') }}
            </button>
          </div>

          <div v-if="pendingCounters" class="w-full max-w-md border border-slate-200 rounded-lg bg-white h-fit">
            <div class="border-b border-slate-200 px-4 py-3">
              <p class="text-xs font-bold uppercase tracking-wider text-slate-500">{{ $t('assigned_readings') }}</p>
            </div>
            <ul class="divide-y divide-gray-100">
              <li class="flex justify-between items-center px-4 py-3 relative group">
                <span class="text-sm font-semibold text-slate-700">{{ $t('total_assigned_readings') }}:</span>
                <span class="inline-flex items-center bg-green-300 text-slate-700 text-sm rounded-full px-2 py-1 ml-2 mr-8">{{ numPendingReadings }}</span>
              </li>
              <li class="flex items-center justify-between rounded-lg bg-slate-50/70 px-3 py-2 mx-2 my-1 relative group">
                <span class="text-sm font-medium text-slate-700">{{ $t('readings_with_reader_alert') }}:</span>
                <div class="flex items-center gap-1 mr-6">
                  <span v-if="numPendingReadingsWithReaderAlert > 0" class="inline-flex items-center bg-yellow-300 text-slate-700 text-sm rounded-full px-2 py-1 ml-2">{{ numPendingReadingsWithReaderAlert }}</span>
                  <span v-else class="text-sm text-slate-400 ml-2">-</span>
                </div>
                <div v-if="numPendingReadingsWithReaderAlert > 0" class="w-7 cursor-pointer opacity-0 group-hover:opacity-100 transition-all duration-150 absolute top-0 right-0 h-full flex items-center justify-center"
                  @click="openPendingDetail('reader_alert', 'readings_with_reader_alert')">
                  <Icon name="fa6-solid:eye" class="w-3.5 h-3.5 text-slate-500" />
                </div>
              </li>
              <li class="flex items-center justify-between rounded-lg bg-slate-50/70 px-3 py-2 mx-2 my-1 relative group">
                <span class="text-sm font-medium text-slate-700">{{ $t('readings_with_remote_alert') }}:</span>
                <div class="flex items-center gap-1 mr-6">
                  <span v-if="numPendingReadingsWithRemoteAlert > 0" class="inline-flex items-center bg-yellow-300 text-slate-700 text-sm rounded-full px-2 py-1 ml-2">{{ numPendingReadingsWithRemoteAlert }}</span>
                  <span v-else class="text-sm text-slate-400 ml-2">-</span>
                </div>
                <div v-if="numPendingReadingsWithRemoteAlert > 0" class="w-7 cursor-pointer opacity-0 group-hover:opacity-100 transition-all duration-150 absolute top-0 right-0 h-full flex items-center justify-center"
                  @click="openPendingDetail('remote_alert', 'readings_with_remote_alert')">
                  <Icon name="fa6-solid:eye" class="w-3.5 h-3.5 text-slate-500" />
                </div>
              </li>
              <li class="flex items-center justify-between rounded-lg bg-slate-50/70 px-3 py-2 mx-2 my-1 relative group">
                <span class="text-sm font-medium text-slate-700">{{ $t('readings_without_reading_value') }}:</span>
                <div class="flex items-center gap-1 mr-6">
                  <span v-if="numPendingReadingWithoutReadingValue > 0" class="inline-flex items-center bg-red-500 text-white text-sm rounded-full px-2 py-1 ml-2">{{ numPendingReadingWithoutReadingValue }}</span>
                  <span v-else class="text-sm text-slate-400 ml-2">-</span>
                </div>
                <div v-if="numPendingReadingWithoutReadingValue > 0" class="w-7 cursor-pointer opacity-0 group-hover:opacity-100 transition-all duration-150 absolute top-0 right-0 h-full flex items-center justify-center"
                  @click="openPendingDetail('no_reading_value', 'readings_without_reading_value')">
                  <Icon name="fa6-solid:eye" class="w-3.5 h-3.5 text-slate-500" />
                </div>
              </li>
              <li class="flex items-center justify-between rounded-lg bg-slate-50/70 px-3 py-2 mx-2 my-1 relative group">
                <span class="text-sm font-medium text-slate-700">{{ $t('discarded_readings') }}:</span>
                <div class="flex items-center gap-1 mr-6">
                  <span v-if="numPendingExtraReadings > 0" class="inline-flex items-center bg-orange-400 text-slate-700 text-sm rounded-full px-2 py-1 ml-2">{{ numPendingExtraReadings }}</span>
                  <span v-else class="text-sm text-slate-400 ml-2">-</span>
                </div>
                <div v-if="numPendingExtraReadings > 0" class="w-7 cursor-pointer opacity-0 group-hover:opacity-100 transition-all duration-150 absolute top-0 right-0 h-full flex items-center justify-center"
                  @click="openPendingDetail('extra', 'discarded_readings')">
                  <Icon name="fa6-solid:eye" class="w-3.5 h-3.5 text-slate-500" />
                </div>
              </li>
              <li class="flex items-center justify-between rounded-lg bg-slate-50/70 px-3 py-2 mx-2 my-1 relative group">
                <span class="text-sm font-medium text-slate-700">{{ $t('remote_readings') }}:</span>
                <div class="flex items-center gap-1 mr-6">
                  <span v-if="numPendingReadingsWithRemoteReader > 0" class="inline-flex items-center bg-cyan-400 text-slate-700 text-sm rounded-full px-2 py-1 ml-2">{{ numPendingReadingsWithRemoteReader }}</span>
                  <span v-else class="text-sm text-slate-400 ml-2">-</span>
                </div>
                <div v-if="numPendingReadingsWithRemoteReader > 0" class="w-7 cursor-pointer opacity-0 group-hover:opacity-100 transition-all duration-150 absolute top-0 right-0 h-full flex items-center justify-center"
                  @click="openPendingDetail('remote_reader', 'remote_readings')">
                  <Icon name="fa6-solid:eye" class="w-3.5 h-3.5 text-slate-500" />
                </div>
              </li>
              <li class="flex items-center justify-between rounded-lg bg-slate-50/70 px-3 py-2 mx-2 my-1 relative group">
                <span class="text-sm font-medium text-slate-700">{{ $t('readings_inactive_supplypoints') }}:</span>
                <div class="flex items-center gap-1 mr-6">
                  <span v-if="numPendingReadingsInactiveSupplyPoints > 0" class="inline-flex items-center bg-stone-500 text-white text-sm rounded-full px-2 py-1 ml-2">{{ numPendingReadingsInactiveSupplyPoints }}</span>
                  <span v-else class="text-sm text-slate-400 ml-2">-</span>
                </div>
                <div v-if="numPendingReadingsInactiveSupplyPoints > 0" class="w-7 cursor-pointer opacity-0 group-hover:opacity-100 transition-all duration-150 absolute top-0 right-0 h-full flex items-center justify-center"
                  @click="openPendingDetail('inactive_sp', 'readings_inactive_supplypoints')">
                  <Icon name="fa6-solid:eye" class="w-3.5 h-3.5 text-slate-500" />
                </div>
              </li>
              <li class="flex items-center justify-between rounded-lg bg-slate-50/70 px-3 py-2 mx-2 my-1 relative group">
                <span class="text-sm font-medium text-slate-700">{{ $t('no_route_supply_points_count') }}:</span>
                <div class="flex items-center gap-1 mr-6">
                  <span v-if="numPendingNoRouteSupplyPoints > 0" class="inline-flex items-center bg-orange-300 text-slate-700 text-sm rounded-full px-2 py-1 ml-2">{{ numPendingNoRouteSupplyPoints }}</span>
                  <span v-else class="text-sm text-slate-400 ml-2">-</span>
                </div>
              </li>
              <li class="flex justify-between items-center border-t border-slate-200 px-4 py-3 mt-1 relative group">
                <span class="text-sm font-semibold text-slate-700">{{ $t('service_block.supplies_no_reading') }}:</span>
                <div class="flex items-center gap-1 mr-8">
                  <span v-if="numPendingMissingReadings > 0" class="inline-flex items-center bg-red-400 text-slate-700 text-sm rounded-full px-2 py-1 ml-2">{{ numPendingMissingReadings }}</span>
                  <span v-else class="text-sm text-slate-400 ml-2">-</span>
                </div>
                <div v-if="numPendingMissingReadings > 0" class="w-8 cursor-pointer opacity-0 group-hover:opacity-100 transition-all duration-150 bg-gradient-to-r from-transparent to-slate-100 h-full absolute top-0 right-0 flex items-center justify-center rounded-r-lg"
                  @click="openPendingDetail('missing', 'service_block.supplies_no_reading')">
                  <Icon name="fa6-solid:eye" class="w-3.5 h-3.5 text-slate-500" />
                </div>
              </li>
            </ul>
          </div>
        </div>
      </div>
    </div>

    <!-- Detail Region (Readings List) -->
    <div role="region" 
      :class="[
        isEmbedded ? 'h-full flex-1 flex flex-col min-h-0' : 'fixed h-full border-l border-gray-100 top-0 right-0 transition-all duration-500 ease py-2 text-base bg-white z-20 overflow-hidden flex flex-col',
        !isEmbedded ? { 
          'translate-x-0': showRegion, 
          'translate-x-[2000px]': !showRegion, 
          'w-[90%]': showRegionComponent != 'ExportReadings', 
          'w-[55%]': showRegionComponent == 'ExportReadings' 
        } : ''
      ]" 
      v-if="isEmbedded || showRegion"
    >
      <div id="region_nav" class="mb-3 px-3" v-if="!isEmbedded">
        <button @click="toggleRegion(false)" class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300" >
          <Icon name="fa6-solid:angles-right" class="text-slate-500" />
        </button>
      </div>
      
      <div v-if="showRegionComponent == 'ExportReadings'" class="px-10 flex flex-col h-full">
        <ReadingExport :batch_id="batch_id" />
      </div>

      <div v-if="showRegionComponent == 'readings'" class="px-10 flex flex-col flex-1 min-h-0">
        <h1 class="text-2xl font-bold mb-4">{{ t('readings') }} {{ translateWarningAlert(title) }}</h1>
        <span class="input-group flex flex-start items-center gap-2 w-80">
          <Icon name="fa6-solid:magnifying-glass" class="text-slate-500" />
          <input v-model="searchInput" @input="handleSearch" id="searchInput" type="text" name="search"
            :placeholder="$t('contract_block.search_by_token')" class="w-full p-1 rounded-md focus:outline-none focus-visible:border-0"
            autocomplete="off" />
        </span>
        <div class="flex items-center gap-2 mt-3">
          <input type="checkbox" v-model="showLeak" @change="leakFilter()">
          <label>{{ t('billing_block.prev_leaks') }}</label>
          <input type="checkbox" v-model="showLeakCurrent" @change="leakCurrentFilter()">
          <label>{{ t('billing_block.current_leaks') }}</label>
        </div>
        <div class="flex items-center gap-3 mb-2 min-h-[36px]">
          <template v-if="selectedReadingIds.length > 0">
            <span class="text-sm text-slate-500">{{ selectedReadingIds.length }} {{ t('common.selected') }}</span>
            <button v-if="hasEstimatedSelected" :disabled="recalculating"
              class="flex items-center gap-2 px-3 py-1.5 text-sm rounded bg-amber-500 text-white hover:bg-amber-600 disabled:opacity-50 transition-colors"
              @click="recalculateSelected">
              <Icon :name="recalculating ? 'fa6-solid:spinner' : 'fa6-solid:rotate'" :class="{ 'animate-spin': recalculating }" />
              {{ t('billing_block.recalculate_estimated_readings') }}
            </button>
            <span v-else class="text-xs text-slate-400 italic">{{ t('billing_block.select_estimated_to_recalculate') }}</span>
          </template>
          <template v-else>
            <span class="text-xs text-slate-400 italic flex items-center gap-1">
              <Icon name="fa6-solid:circle-info" class="text-slate-300" />
              {{ t('billing_block.checkbox_recalculate_hint') }}
            </span>
          </template>
        </div>
        <div class="overflow-y-auto flex-grow pb-10">
          <div
            class="sticky top-0 z-10 grid grid-cols-[24px,1.2fr,1fr,1fr,1fr,1fr,1fr,1fr,1fr,1fr,2fr,80px,40px,100px] gap-2 px-4 divide-x divide-gray-200 border-b border-gray-200 items-center bg-white">
            <span class="p-2"></span>
            <span class="p-3 text-xs font-medium uppercase tracking-wider text-gray-400 truncate min-w-0">{{ t('common.contracts') }}</span>
            <span class="p-3 text-xs font-medium uppercase tracking-wider text-gray-400 truncate min-w-0">{{ t('common.type') }}</span>
            <span class="p-3 text-xs font-medium uppercase tracking-wider text-gray-400 truncate min-w-0">{{ t('billing_block.prev_leak') }}</span>
            <span class="p-3 text-xs font-medium uppercase tracking-wider text-gray-400 truncate min-w-0">{{ t('billing_block.previous_reading') }}</span>
            <TableHeader class="p-3 text-xs font-medium uppercase tracking-wider" :label="t('reading')" sortKey="reading_value" :currentSortBy="sortBy"
              :sortDesc="sortDesc" @sort="sortReadingsBy" />
            <span class="p-3 text-xs font-medium uppercase tracking-wider text-gray-400 truncate min-w-0 flex items-center gap-2">
              {{ t('billing_block.leak') }}
              <abbr :title="t('informative_block.info_leak_consumption')">
                <Icon name="fa6-solid:circle-info" class="text-slate-400" />
              </abbr>
            </span>
            <TableHeader class="p-3 text-xs font-medium uppercase tracking-wider" :label="t('billing_block.consumption')" sortKey="calculated_value"
              :currentSortBy="sortBy" :sortDesc="sortDesc" @sort="sortReadingsBy" />
            <span class="p-3 text-xs font-medium uppercase tracking-wider text-gray-400 truncate min-w-0">{{ t('service_block.is_general') }}</span>
            <span class="p-3 text-xs font-medium uppercase tracking-wider text-gray-400 truncate min-w-0">{{ t('billing_block.estimated') }}</span>
            <span class="p-3 text-xs font-medium uppercase tracking-wider text-gray-400 truncate min-w-0">{{ t('billing_block.alerts') }}</span>
            <span class="p-3 text-xs font-medium uppercase tracking-wider text-gray-400 truncate min-w-0">{{ t('common.days') }}</span>
            <span class="p-4"></span>
            <span class="p-3"></span>
          </div>
          <div v-for="reading in showReadings" :key="reading.id">
            <AtomsReadingEdit @show-edit="onShowDetail" @open-region="openRegion" @toggle-select="toggleReadingSelection"
            :reading="reading" :showDetail="showingDetailId == reading.id" :allowChange="allowChange" :medianDuration="medianDuration"
            :selected="selectedReadingIds.includes(reading.id)" />
          </div>
          <div v-if="loadingReadings" class="text-center py-4">{{ $t('common.loading') }}...</div>
          <div v-if="!loadingReadings && showReadings.length === 0" class="text-center py-8 text-sm text-slate-400">
            {{ $t('common.no_records') }}
          </div>
        </div>
        <Pagination v-if="showReadings.length > 0" :pagination="pagination" @update:page="handlePageChange" />
      </div>
    </div>

    <!-- Sub-region Detail (Supply Point, Contract, etc.) -->
    <div role="region" id="right_over_page"
      :class="[
        isEmbedded ? 'h-full border-l border-gray-100 py-2 bg-white w-1/2 overflow-y-auto' : 'fixed h-full border-l border-gray-100 top-0 right-0 transition-all duration-500 ease py-2 text-base bg-white w-[60%] z-50 shadow',
        !isEmbedded ? { 'translate-x-0': showSubRegion, 'translate-x-[2000px]': !showSubRegion } : { 'hidden': !showSubRegion }
      ]">
      <div id="region_nav" class="mb-3 px-3">
        <button @click="toggleSubRegion(false)" class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300">
          <Icon name="fa6-solid:angles-right" class="text-slate-500" />
        </button>
      </div>
      <div class="px-10">
        <OrganismsPersonRegion v-if="subRegionEntity == 'person'" :id="subRegionId" :isSubRegion="true"/>
        <OrganismsContractRegion v-if="subRegionEntity == 'contract'" :id="subRegionId" :isSubRegion="true"/>
        <OrganismsSupplyPointRegion v-if="subRegionEntity == 'supply_point'" :id="subRegionId" :isSubRegion="true"/>
      </div>
    </div>
  </div>

    <!-- Pending Readings Read-only Region -->
    <div role="region"
      class="fixed h-full border-l border-gray-100 top-0 right-0 transition-all duration-500 ease py-2 text-base bg-white w-[80%] z-40 overflow-hidden flex flex-col shadow-lg"
      :class="{ 'translate-x-0': showPendingRegion, 'translate-x-[2000px]': !showPendingRegion }">
      <div class="mb-3 px-3">
        <button @click="showPendingRegion = false" class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300">
          <Icon name="fa6-solid:angles-right" class="text-slate-500" />
        </button>
      </div>
      <div class="px-10 flex flex-col flex-1 min-h-0">
        <h1 class="text-2xl font-bold mb-4">{{ pendingRegionTitle }}</h1>
        <div class="grid grid-cols-[1.5fr,2fr,2fr,1fr,1fr] gap-2 px-4 divide-x divide-gray-200 border-b border-gray-400 items-end">
          <span class="p-3 font-bold">{{ $t('contract') }}</span>
          <span class="p-3 font-bold">{{ $t('common.roles.HOLDER') }}</span>
          <span class="p-3 font-bold">{{ $t('supply_point') }}</span>
          <span class="p-3 font-bold">{{ $t('billing_block.last_reading') }}</span>
          <span class="p-3 font-bold">{{ $t('billing_block.reading_date') }}</span>
        </div>
        <div class="overflow-y-auto flex-grow pb-10" @scroll="onPendingScroll">
          <div v-for="supply in showPendingReadings" :key="supply.id"
            class="grid grid-cols-[1.5fr,2fr,2fr,1fr,1fr] gap-2 px-4 divide-x divide-gray-200 border-b border-gray-100 items-center min-h-[40px]">
            <div class="p-3 text-sm">
              <a v-if="supply.contracts?.length > 0" href="#" class="text-sky-600 font-bold hover:underline" @click.prevent="openRegion('contract', supply.contracts[0].id)">
                {{ supply.contracts[0].token }}
              </a>
              <span v-else class="text-slate-400">-</span>
            </div>
            <div class="p-3 text-sm truncate">
              <span v-if="supply.contracts?.length > 0">{{ supply.contracts[0].holder }}</span>
              <span v-else class="text-slate-400">-</span>
            </div>
            <div class="p-3 text-sm truncate">{{ supply.address_complete || '-' }}</div>
            <div class="p-3 text-sm font-mono">{{ supply.last_reading_value ?? '-' }}</div>
            <div class="p-3 text-sm text-slate-500">{{ supply.last_reading_date ?? '-' }}</div>
          </div>
          <div v-if="loadingPendingReadings" class="text-center py-4 text-sm text-slate-500">
            {{ $t('common.loading') }}...
          </div>
          <div v-if="!loadingPendingReadings && showPendingReadings.length === 0" class="text-center py-8 text-sm text-slate-400">
            {{ $t('common.no_results') }}
          </div>
        </div>
      </div>
    </div>

    <!-- Fix Reading Error Region -->
    <div role="region"
      class="fixed h-full border-l border-gray-100 top-0 right-0 transition-all duration-500 ease py-2 text-base bg-white w-[30%] z-[60] overflow-hidden flex flex-col shadow-lg"
      :class="{ 'translate-x-0': showFixRegion, 'translate-x-[2000px]': !showFixRegion }">
      <div class="mb-3 px-3">
        <button @click="closeFixRegion" class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300">
          <Icon name="fa6-solid:angles-right" class="text-slate-500" />
        </button>
      </div>
      <div class="px-8 flex flex-col flex-1 min-h-0">
        <h1 class="text-xl font-bold mb-4">{{ t('billing_block.reading_id') }} #{{ fixReadingId }}</h1>

        <div v-if="fixLoading" class="flex items-center justify-center py-8">
          <Icon name="fa6-solid:spinner" class="animate-spin text-2xl text-slate-500" />
        </div>

        <div v-else class="space-y-4">
          <div v-if="fixReadingDetail" class="text-sm text-slate-500 space-y-1 border border-slate-200 rounded-md p-3 bg-slate-50">
            <div v-if="fixReadingDetail.contract?.token">{{ t('contract') }}: <span class="font-medium text-slate-700">{{ fixReadingDetail.contract.token }}</span></div>
            <div v-if="fixReadingDetail.supply_point?.token">{{ t('supply_point') }}: <span class="font-medium text-slate-700">{{ fixReadingDetail.supply_point.token }}</span></div>
            <div v-if="fixReadingDetail.reading_value !== null && fixReadingDetail.reading_value !== undefined">{{ t('reading') }}: <span class="font-medium text-slate-700">{{ fixReadingDetail.reading_value }}</span></div>
          </div>

          <div>
            <label class="block text-sm font-medium text-slate-600 mb-1" for="fix-reading-date">
              {{ t('billing_block.reading_date') }}
            </label>
            <input id="fix-reading-date" type="date" v-model="fixReadingDateValue"
              class="w-full border border-slate-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-sky-400" />
          </div>

          <div class="flex justify-end gap-2 pt-2">
            <button class="button-secondary" :disabled="fixSaving" @click="closeFixRegion">
              {{ t('common.cancel') }}
            </button>
            <button class="button-primary flex items-center gap-2" :disabled="fixSaving || !fixReadingDateValue" @click="saveFixReadingDate">
              <Icon v-if="fixSaving" name="fa6-solid:spinner" class="animate-spin" />
              {{ t('common.save') }}
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.shadow-left {
  box-shadow: -4px 0 6px -1px rgb(0 0 0 / 0.1), -2px 0 4px -2px rgb(0 0 0 / 0.1);
}
</style>
