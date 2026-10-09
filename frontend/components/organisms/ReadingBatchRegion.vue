<script setup>
// components/organisms/ReadingBatchRegion.vue
import { ref, computed, watch, onUnmounted } from 'vue';
import { useRouter } from 'vue-router';
import { useI18n } from 'vue-i18n';
import H1Region from '~/components/atoms/H1Region.vue';
import OptionsDropdown from '~/components/molecules/OptionsDropdown.vue';
import DropdownOption from '~/components/atoms/DropdownOption.vue';
import StatusesNav from '~/components/atoms/StatusesNav.vue';
import ChangeStatus from '~/components/molecules/ChangeStatus.vue';
import Pagination from '~/components/molecules/Pagination.vue';
import { useToast } from 'vue-toastification';
import { usePermissions } from '~/middleware/permission';
// Importar el component SupplyPointRegion per a la subregion
import FieldDetail from '~/components/atoms/FieldDetail.vue';
import AppLoading from '~/components/atoms/AppLoading.vue';
import TableHeader from '~/components/atoms/TableHeader.vue';

const { t } = useI18n();
const toast = useToast();
const { permissions, loading } = usePermissions();
const props = defineProps({
  id: Number, // ID de l'element
  isSubRegion: false,
  isSubRegionOpen: Boolean
});

const emit = defineEmits(['show-subregion', 'close-subregion', 'select-batch']);
const router = useRouter();
const { $ReadingBatchApiService, $ConfiglistApiService, $ConfigProjectApiService, $ReadingApiService, $apiManager } = useNuxtApp();
const config = useRuntimeConfig();
const pending = ref(true);

const downloadingCsv = ref(false);
const csvExportProgress = ref(0);
const csvExportTaskId = ref(null);
let csvExportInterval = null;

const downloadingSupplyPointsCsv = ref(false);
const supplyPointsCsvExportProgress = ref(0);
const supplyPointsCsvExportTaskId = ref(null);
let supplyPointsCsvExportInterval = null;

onUnmounted(() => {
  if (csvExportInterval) {
    clearInterval(csvExportInterval);
  }
  if (supplyPointsCsvExportInterval) {
    clearInterval(supplyPointsCsvExportInterval);
  }
});

const resolveTaskFileMediaUrl = (path) => {
  if (!path) return '';
  if (/^https?:\/\//i.test(path)) return path;
  const apiHost = config.public.apiHost || '';
  try {
    return new URL(path, new URL(apiHost).origin).href;
  } catch {
    return path;
  }
};
const pendingReadings = ref(true);
const error = ref(null);
const data = ref([]);
const activeTab = ref('contracts');
const SubRegion = ref(props.isSubRegionOpen);

const readingBatchStatuses = ref([]);
const readingBatchStatus = ref(null);

const editingChangeStatus = ref(false);
const objectPermissions = ref(null);
const batchData = ref(null);

// Dades del lot original quan el lot actual és un lot d'excloses (batchData.is_excluded === true)
const originBatchData = ref(null);
const originBatchLoading = ref(false);

const pagination = ref({
  page: 1,
  perPage: 50,
  total: 0,
  totalPages: 0,
  previous: null,
  next: null,
  isFiltered: false
});

const sortBy = ref('routeposition_position');
const sortDesc = ref(false);

const readingsGridCols = '140px 100px 140px 100px 90px 90px 90px 150px';

// Un lot d'excloses (is_excluded) no té rutes pròpies: hereta la informació
// de rutes/agregats del lot original (excluded_from) en lloc de comptar
// els seus propis subministraments exclosos.
const isExcludedBatch = computed(() => !!batchData.value?.is_excluded);

// Font de dades per als agregats: el lot original quan és un lot exclòs
// i ja s'ha carregat, si no, el propi lot.
const aggregatesSource = computed(() => {
  if (isExcludedBatch.value && originBatchData.value) return originBatchData.value;
  return batchData.value;
});

// Agregats del detall del lot (num_routes / num_supplies / num_readings del backend, amb fallback)
const numRoutes = computed(() => {
  const source = aggregatesSource.value;
  if (source?.num_routes != null) return source.num_routes;
  return source?.routes?.length ?? 0;
});

const numSupplies = computed(() => {
  const source = aggregatesSource.value;
  if (source?.num_supplies != null) return source.num_supplies;
  return (source?.routes || []).reduce(
    (sum, route) => sum + (route.num_total_readings || 0),
    0
  );
});

const numActiveSupplies = computed(() => {
  const source = aggregatesSource.value;
  if (source?.num_active_supplies != null) return source.num_active_supplies;
  return null;
});

// numReadings sempre es refereix a les lectures pròpies del lot que s'està
// visualitzant (no s'hereten del lot original).
const numReadings = computed(() => {
  if (batchData.value?.num_readings != null) return batchData.value.num_readings;
  return pagination.value.total ?? 0;
});

// Rutes a mostrar al desplegable "Rutes": si és un lot exclòs, les del lot original
const displayRoutes = computed(() => aggregatesSource.value?.routes || []);

const handlePageChange = (newPage) => {
  pagination.value.page = newPage;
  getData(newPage);
}

const handleSort = (key) => {
  if (sortBy.value === key) {
    sortDesc.value = !sortDesc.value;
  } else {
    sortBy.value = key;
    sortDesc.value = false;
  }
  pagination.value.page = 1;
  getData(1);
}

const getPermissions = async () => {
  error.value = null;
  try {
    const data = await $ReadingApiService.getPermissions();
    objectPermissions.value = data;
  } catch (err) {
    error.value = err;
  }
}

// Carrega les dades del lot original quan el lot actual és un lot d'excloses
const fetchOriginBatch = async (excludedFromId) => {
  if (!excludedFromId) {
    originBatchData.value = null;
    return;
  }
  originBatchLoading.value = true;
  try {
    originBatchData.value = await $ReadingBatchApiService.getDetail(excludedFromId);
  } catch (err) {
    console.error('Error fetching origin batch:', err);
    originBatchData.value = null;
  } finally {
    originBatchLoading.value = false;
  }
}

const getData = async (page = 1) => {
  if (!objectPermissions.value?.can_view) {
    emit('close-subregion');
    return
  }

  try {
    error.value = null;
    const batchResult = await $ReadingBatchApiService.getDetail(props.id);
    batchData.value = batchResult;

    if (batchResult?.is_excluded && batchResult?.excluded_from) {
      await fetchOriginBatch(batchResult.excluded_from);
    } else {
      originBatchData.value = null;
    }

    await fetchConfigData('billing/reading-batch-status', readingBatchStatuses);

    if (batchData.value?.status) {
      readingBatchStatus.value = batchData.value.status;
    } else {
      const defaultStatus = readingBatchStatuses.value.find(s => s.is_default == true);
      if (defaultStatus) {
        readingBatchStatus.value = defaultStatus;
      }
    }
  } catch (err) {
    console.error(err);
    error.value = err;
    pending.value = false;
    pendingReadings.value = false;
    return;
  } finally {
    pending.value = false;
  }

  pendingReadings.value = true;
  try {
    const result = await $ReadingApiService.getReadingsByBatchMinimal(
      props.id,
      page,
      null,
      false,
      false,
      sortBy.value,
      sortDesc.value
    );
    data.value = result?.results || [];

    Object.assign(pagination.value, {
      total: result?.count || 0,
      totalPages: Math.ceil((result?.count || 0) / pagination.value.perPage),
      previous: result?.previous ?? null,
      next: result?.next ?? null,
      isFiltered: false
    });
  } catch (err) {
    console.error(err);
    data.value = [];
    Object.assign(pagination.value, {
      total: 0,
      totalPages: 0,
      previous: null,
      next: null,
      isFiltered: false
    });
  } finally {
    pendingReadings.value = false;
  }
}

const fetchConfigData = async (entity, targetArray) => {
  try {
    const data = await $ConfiglistApiService.getAll(entity);
    targetArray.value = data.results;
  } catch (error) {
    console.error(`Error fetching ${entity}:`, error);
  }
}

watch(() => props.id, () => {
  if (!objectPermissions.value?.can_view) {
    emit('close-subregion');
    return
  }
  cancelEditBatchMeta();
  getData();
  closeSubRegion();
});

watch(() => props.isSubRegionOpen, (newValue) => {
  SubRegion.value = newValue;
});

onMounted(async () => {
  await getPermissions();
  if (objectPermissions.value?.can_view) {
    getData();
  } else {
    toast.error(t('common.no_permissions'));
    emit('close-subregion');
  }
});

const changeStatus = async () => {
  if (confirm(t('confirmation_text_block.confirm_cancel'))) {

    try {
      const token = await $ConfigProjectApiService.get('batch_status_cancel_token');
      const data = {
        id: props.id,
        status_token: token
      }
      const res = await $ReadingBatchApiService.update(data);
      getData();
    }
    catch (error) {
      // $apiManager.fetch already shows a toast with the status_token message (400) or error detail
      console.error(error);
    }
  }
}

const handleStatusChanged = () => {
  editingChangeStatus.value = false;
  SubRegion.value = false;
  emit('show-subregion', false)
  getData()
}

const closeSubRegion = function () {
  SubRegion.value = false;
  showRegionDetailComponent.value = null;
  emit('show-subregion', false);
}

const showSubRegion = function () {
  SubRegion.value = true;
  emit('show-subregion', true);
}

// subregions details
const showRegionDetailComponent = ref(null);
const regionDetailId = ref(null);

const showDetail = function (component, id) {
  showRegionDetailComponent.value = component;
  regionDetailId.value = id;
  showSubRegion();
}

const edit = () => {
  return navigateTo('/reading/reading-batches/edit/' + props.id)
}

const setActiveTab = (tab) => {
  activeTab.value = tab;
}

const startAsyncCsvExport = async ({
  startRequest,
  downloadingRef,
  progressRef,
  taskIdRef,
  getInterval,
  setIntervalRef,
  defaultFilename,
}) => {
  if (downloadingRef.value) return;
  downloadingRef.value = true;
  progressRef.value = 0;

  try {
    const response = await startRequest();

    if (response && response.task_id) {
      taskIdRef.value = response.task_id;

      const intervalId = setInterval(async () => {
        try {
          const res = await $apiManager.checkTask(taskIdRef.value);
          if (res) {
            if (res.state === 'PENDING' || res.state === 'RUNNING') {
              progressRef.value = res.percent || 0;
            } else if (res.state === 'SUCCESS') {
              clearInterval(getInterval());
              progressRef.value = 100;

              const result = res.result;
              if (result?.status === 'error') {
                toast.error(result.message || t('common.export_error') || 'Error en l\'exportació');
              } else if (result?.file_url && (result.status === 'ok' || !result.status)) {
                const absoluteUrl = resolveTaskFileMediaUrl(result.file_url);
                const authToken = localStorage.getItem('auth_token') || '';
                const fileRes = await fetch(absoluteUrl, {
                  method: 'GET',
                  headers: { Authorization: `Token ${authToken}` },
                });

                if (!fileRes.ok) {
                  throw new Error(t('common.export_error') || 'Error en l\'exportació');
                }

                const blob = await fileRes.blob();
                const objectUrl = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = objectUrl;
                a.download = result.filename || defaultFilename;
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
                window.URL.revokeObjectURL(objectUrl);
                toast.success(t('common.export_completed') || 'Exportació completada');
              } else {
                toast.error(t('common.export_error') || 'Error en l\'exportació');
              }
              downloadingRef.value = false;
              taskIdRef.value = null;
            } else if (res.state === 'FAILURE') {
              clearInterval(getInterval());
              const errMsg = res.error || t('common.export_error') || 'Error en l\'exportació';
              toast.error(errMsg);
              downloadingRef.value = false;
              taskIdRef.value = null;
            }
          }
        } catch (pollErr) {
          clearInterval(getInterval());
          console.error(pollErr);
          toast.error(t('common.export_error') || 'Error en l\'exportació');
          downloadingRef.value = false;
          taskIdRef.value = null;
        }
      }, 2000);

      setIntervalRef(intervalId);
    } else {
      throw new Error('No s\'ha rebut task_id');
    }
  } catch (error) {
    console.error('Error exportant CSV:', error);
    toast.error(t('common.export_error') || 'Error en l\'exportació');
    downloadingRef.value = false;
    taskIdRef.value = null;
  }
}

const exportCsv = async () => {
  await startAsyncCsvExport({
    startRequest: () => $ReadingBatchApiService.exportCsv(props.id),
    downloadingRef: downloadingCsv,
    progressRef: csvExportProgress,
    taskIdRef: csvExportTaskId,
    getInterval: () => csvExportInterval,
    setIntervalRef: (id) => { csvExportInterval = id; },
    defaultFilename: `lectures_batch_${props.id}_${new Date().toISOString().slice(0, 10).replace(/-/g, '')}.csv`,
  });
}

const exportSupplyPointsCsv = async () => {
  await startAsyncCsvExport({
    startRequest: () => $ReadingBatchApiService.exportSupplyPointsCsv(props.id),
    downloadingRef: downloadingSupplyPointsCsv,
    progressRef: supplyPointsCsvExportProgress,
    taskIdRef: supplyPointsCsvExportTaskId,
    getInterval: () => supplyPointsCsvExportInterval,
    setIntervalRef: (id) => { supplyPointsCsvExportInterval = id; },
    defaultFilename: `supply_points_batch_${props.id}_${new Date().toISOString().slice(0, 10).replace(/-/g, '')}.csv`,
  });
}

const isEditingBatchMeta = ref(false);
const savingBatchMeta = ref(false);
const editToken = ref('');
const editName = ref('');
const editDate = ref('');

const toDateInputValue = (iso) => {
  if (!iso) return '';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '';
  const year = d.getFullYear();
  const month = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
};

const buildCreatedAtPayload = (dateStr) => {
  if (!dateStr) return null;
  const existing = batchData.value?.created_at;
  if (existing && typeof existing === 'string' && existing.includes('T')) {
    const timeAndZone = existing.slice(existing.indexOf('T') + 1);
    return `${dateStr}T${timeAndZone}`;
  }
  return `${dateStr}T00:00:00`;
};

const startEditBatchMeta = () => {
  editToken.value = batchData.value?.token || '';
  editName.value = batchData.value?.name || '';
  editDate.value = toDateInputValue(batchData.value?.created_at);
  isEditingBatchMeta.value = true;
};

const cancelEditBatchMeta = () => {
  isEditingBatchMeta.value = false;
  editToken.value = '';
  editName.value = '';
  editDate.value = '';
};

const saveBatchMeta = async () => {
  const token = (editToken.value || '').trim();
  const name = (editName.value || '').trim();
  if (!token || !name) {
    toast.error(t('common.error_save'));
    return;
  }
  if (savingBatchMeta.value) return;
  savingBatchMeta.value = true;
  try {
    const payload = {
      id: props.id,
      token,
      name,
      created_at: buildCreatedAtPayload(editDate.value),
    };
    const response = await $ReadingBatchApiService.update(payload);
    // Refrescar detall complet per no perdre routes / mètriques si el PUT torna un payload parcial
    try {
      const refreshed = await $ReadingBatchApiService.getDetail(props.id);
      batchData.value = refreshed;
    } catch {
      if (response && typeof response === 'object') {
        batchData.value = {
          ...batchData.value,
          token: response.token ?? token,
          name: response.name ?? name,
          created_at: response.created_at ?? payload.created_at,
        };
      }
    }
    isEditingBatchMeta.value = false;
    toast.success(t('common.saved_successfully'));
  } catch (err) {
    console.error(err);
    toast.error(err?.data?.detail || err?.message || t('common.error_save'));
  } finally {
    savingBatchMeta.value = false;
  }
};

const formatDate = (date) => {
  if (!date) return '-';
  return new Date(date).toLocaleDateString();
}

</script>

<template>
  <div class="region__content h-full">
    <div class="px-10 flex flex-col h-full overflow-hidden transition-all duration-500 ease"
      :class="{ 'mr-[48vw]': SubRegion }">
      <div v-if="pending || loading" class="h-full">
        <AppLoading :text="$t('common.loading')" />
      </div>
      <div v-else-if="error">
        <p>{{ $t('common.error') }}: {{ error.message }}</p>
        <p><button @click="getData" class="underline text-sky-500 hover:no-underline">{{ $t('common.load_again')
            }}</button></p>
      </div>
      <div v-else-if="objectPermissions?.can_view" class="flex flex-col h-full overflow-hidden">
        <div class="flex justify-between relative flex-shrink-0">
          <H1Region class="mb-3">{{ $t('common.reading_batch_detail') }}</H1Region>
          <OptionsDropdown v-if="objectPermissions?.can_change" id="ReadingBatchRegionOptions">
            <DropdownOption :name="`${t('common.modify')} ${t('common.reading_batch_detail')}`" @click="edit"></DropdownOption>
            <DropdownOption :name="`${t('common.cancel')} ${t('common.reading_batch_detail')}`" @click="changeStatus"></DropdownOption>
          </OptionsDropdown>
        </div>
        <!-- <StatusesNav v-if="readingBatchStatuses" :active="readingBatchStatus" :statuses="readingBatchStatuses" class="flex-shrink-0"/> -->

        <div class="mt-4 flex-1 overflow-y-auto" v-if="batchData" id="item_data" :data-rel="id">
          <div class="flex flex-col mb-4">
            <div class="flex justify-end mb-1" v-if="objectPermissions?.can_change">
              <button
                v-if="!isEditingBatchMeta"
                type="button"
                class="px-2 py-1 text-slate-500 hover:text-slate-700 hover:bg-slate-100 rounded"
                :title="t('common.modify')"
                @click="startEditBatchMeta">
                <Icon name="fa6-solid:pencil" />
              </button>
              <div v-else class="flex items-center gap-1">
                <button
                  type="button"
                  class="px-2 py-1 text-slate-500 hover:text-slate-700 hover:bg-slate-100 rounded disabled:opacity-50"
                  :disabled="savingBatchMeta"
                  :title="t('common.save')"
                  @click="saveBatchMeta">
                  <Icon :name="savingBatchMeta ? 'fa6-solid:spinner' : 'fa6-solid:floppy-disk'" :class="{ 'animate-spin': savingBatchMeta }" />
                </button>
                <button
                  type="button"
                  class="px-2 py-1 text-slate-500 hover:text-slate-700 hover:bg-slate-100 rounded disabled:opacity-50"
                  :disabled="savingBatchMeta"
                  :title="t('common.cancel')"
                  @click="cancelEditBatchMeta">
                  <Icon name="fa6-solid:xmark" />
                </button>
              </div>
            </div>
            <div v-if="!isEditingBatchMeta" class="grid grid-cols-2 gap-3">
              <FieldDetail :label='$t("common.identification")' :value="batchData.token"></FieldDetail>
              <FieldDetail :label='$t("common.name")' :value="batchData.name"></FieldDetail>
              <FieldDetail :label='$t("common.date")' :value="formatDate(batchData.created_at)"></FieldDetail>
              <FieldDetail
                v-if="isExcludedBatch"
                :label='$t("common.excluded_from")'>
                <button
                  type="button"
                  class="text-sky-500 hover:underline text-left disabled:text-slate-400 disabled:no-underline disabled:cursor-default"
                  :disabled="originBatchLoading || !batchData.excluded_from"
                  @click="emit('select-batch', batchData.excluded_from)">
                  <span v-if="originBatchLoading">{{ $t('common.loading') }}...</span>
                  <span v-else>
                    {{ originBatchData?.name || originBatchData?.token || ('#' + batchData.excluded_from) }}
                  </span>
                </button>
              </FieldDetail>
            </div>
            <div v-else class="grid grid-cols-2 gap-3">
              <FieldDetail :label='$t("common.identification")'>
                <input type="text" v-model="editToken" class="input w-full" :disabled="savingBatchMeta" />
              </FieldDetail>
              <FieldDetail :label='$t("common.name")'>
                <input type="text" v-model="editName" class="input w-full" :disabled="savingBatchMeta" />
              </FieldDetail>
              <FieldDetail :label='$t("common.date")'>
                <input type="date" v-model="editDate" class="input w-full" :disabled="savingBatchMeta" />
              </FieldDetail>
            </div>
          </div>

          <hr class="my-4">

          <div class="mb-4 grid grid-cols-2 gap-3 text-sm">
            <div>
              <div class="text-slate-500">{{ $t('common.num_routes') }}</div>
              <div class="text-slate-800 font-semibold tabular-nums">{{ numRoutes }}</div>
            </div>
            <div>
              <div class="text-slate-500">{{ $t('billing_block.batch_readings') }}</div>
              <div class="text-slate-800 font-semibold tabular-nums">{{ numReadings }}</div>
            </div>
            <div>
              <div class="text-slate-500">{{ $t('common.total_supply_points') }}</div>
              <div class="text-slate-800 font-semibold tabular-nums">{{ numSupplies }}</div>
            </div>
            <div>
              <div class="text-slate-500">{{ $t('common.active_supply_points') }}</div>
              <div class="text-slate-800 font-semibold tabular-nums">
                {{ numActiveSupplies != null ? numActiveSupplies : '—' }}
              </div>
            </div>
          </div>

          <div>
            <details v-if="displayRoutes.length > 0" class="mb-2">
              <summary class="text-sm text-slate-500">
                {{ $t('common.routes') }}:
              </summary>
              <div class="px-4 mt-2 space-y-1 divide-y divide-slate-300">
                <div v-for="route in displayRoutes" :key="route.id" class="grid grid-cols-[1fr,auto] gap-4 items-center">
                  <span class="text-sm text-slate-700">{{ route.name }}</span>
                  <span class="text-sm text-slate-500">{{ route.num_total_readings }} {{ $t('common.supplys') }}</span>
                </div>
              </div>
              <hr class="mt-2">
            </details>
            <div v-else>
              <span class="text-sm text-orange-500">
                {{ $t('common.no_records') }}
              </span>
            </div>
          </div>

          <div class="pb-3 flex justify-end gap-2">
            <button
              @click="exportSupplyPointsCsv"
              :disabled="downloadingSupplyPointsCsv"
              class="px-3 py-1 border border-slate-300 text-slate-600 bg-white rounded hover:bg-slate-50 active:bg-slate-100 transition-colors flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
              :title="t('common.export_supply_points_csv')">
              <Icon
                :name="downloadingSupplyPointsCsv ? 'fa6-solid:spinner' : 'fa6-solid:file-csv'"
                class="text-sm text-slate-500"
                :class="{ 'animate-spin': downloadingSupplyPointsCsv }" />
              {{ t('common.export_supply_points_csv') }}
              <span v-if="downloadingSupplyPointsCsv" class="text-xs font-semibold text-slate-500">
                {{ supplyPointsCsvExportProgress }}%
              </span>
            </button>
            <button
              @click="exportCsv"
              :disabled="downloadingCsv || numReadings === 0"
              class="px-3 py-1 bg-green-500 text-white rounded hover:bg-green-600 active:bg-green-700 transition-colors flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed">
              <Icon
                :name="downloadingCsv ? 'fa6-solid:spinner' : 'fa6-solid:download'"
                class="text-sm"
                :class="{ 'animate-spin': downloadingCsv }" />
              {{ t('common.export_csv') }}
              <span v-if="downloadingCsv" class="text-xs font-semibold">
                {{ csvExportProgress }}%
              </span>
            </button>
          </div>

          <div v-if="pendingReadings" class="flex justify-center items-center h-[44vh]">
            <AppLoading :text="$t('common.loading')" :size="40" />
          </div>

          <div class="divide-y divide-slate-300" v-else-if="data.length > 0">
            <div class="overflow-x-auto">
              <div
                class="grid gap-2 pt-2 pb-1 font-bold bg-white sticky top-0 z-10 border-b border-slate-200 text-sm items-center"
                :style="{ gridTemplateColumns: readingsGridCols }">
                <TableHeader :label="t('service_block.route_position')" sortKey="routeposition_position"
                  :currentSortBy="sortBy" :sortDesc="sortDesc" @sort="handleSort" />
                <TableHeader :label="t('billing_block.reading_date')" sortKey="reading_date"
                  :currentSortBy="sortBy" :sortDesc="sortDesc" @sort="handleSort" />
                <TableHeader :label="t('contract')" sortKey="contract"
                  :currentSortBy="sortBy" :sortDesc="sortDesc" @sort="handleSort" />
                <TableHeader :label="t('meter')" sortKey="meter_code"
                  :currentSortBy="sortBy" :sortDesc="sortDesc" @sort="handleSort" />
                <TableHeader :label="t('reading')" sortKey="reading_value"
                  :currentSortBy="sortBy" :sortDesc="sortDesc" @sort="handleSort" />
                <TableHeader :label="t('billing_block.consumption')" sortKey="calculated_value"
                  :currentSortBy="sortBy" :sortDesc="sortDesc" @sort="handleSort" />
                <TableHeader :label="t('common.origin')" sortKey="origin"
                  :currentSortBy="sortBy" :sortDesc="sortDesc" @sort="handleSort" />
                <TableHeader :label="t('billing_block.reader_alert')" sortKey="alert_notes"
                  :currentSortBy="sortBy" :sortDesc="sortDesc" @sort="handleSort" />
              </div>
              <div
                v-for="item in data"
                :key="item.id"
                class="grid gap-2 py-2 border-b border-slate-100 text-sm items-center"
                :style="{ gridTemplateColumns: readingsGridCols }">
                <span class="truncate" :title="item.routeposition_code || ''">{{ item.routeposition_code || '—' }}</span>
                <span class="truncate">{{ item.reading_date || '—' }}</span>
                <span class="truncate" :title="item.contract || ''">{{ item.contract || '—' }}</span>
                <span class="truncate" :title="item.meter_code || ''">{{ item.meter_code || '—' }}</span>
                <span class="tabular-nums">{{ item.read2 ?? '—' }}</span>
                <span class="tabular-nums">{{ parseInt(item.calculated_value) || 0 }}</span>
                <span class="truncate" :title="item.origin || ''">{{ item.origin || '—' }}</span>
                <span class="truncate" :title="item.alert_notes || ''">{{ item.alert_notes || '—' }}</span>
              </div>
            </div>
          </div>

          <div v-else class="py-4">
            <span class="text-sm text-slate-500">{{ $t('common.no_records') }}</span>
          </div>

          <div id="list__footer" class="mt-4">
            <Pagination v-if="data.length > 0" :pagination="pagination" @update:page="handlePageChange" />
          </div>
        </div><!-- end if batchData -->
      </div><!-- end if objectPermissions -->
    </div>

    <div v-if="SubRegion == true" role="region" id="subregion"
      class="h-full border-l border-gray-100 transition-all duration-500 ease py-2 text-base bg-white fixed top-0 right-0 w-[48vw] z-50">
      <div id="region_nav" class="mb-3 px-3">
        <button @click="closeSubRegion()" class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300">
          <Icon name="fa6-solid:angles-right" class="text-slate-500" />
        </button>
      </div>
      <div class="px-10">
        <ChangeStatus v-if="editingChangeStatus" entity="reading-batch" parent_entity="reading_batch"
        :id="props.id" :status="readingBatchStatus?.id" module="billing" @changed="handleStatusChanged" />
      </div>
    </div>
  </div><!-- end region__content -->
</template>