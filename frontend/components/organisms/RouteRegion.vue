<script setup>
import { ref, watch, onMounted, onUnmounted } from 'vue';
import { useRouter } from 'vue-router';
import { useI18n } from 'vue-i18n';
import AppLoading from '~/components/atoms/AppLoading.vue';
import H1Region from '~/components/atoms/H1Region.vue';
import OptionsDropdown from '~/components/molecules/OptionsDropdown.vue';
import RouteDetail from '~/components/molecules/RouteDetail.vue';
import DropdownOption from '~/components/atoms/DropdownOption.vue';
import TableHeader from '~/components/atoms/TableHeader.vue';
import Pagination from '~/components/molecules/Pagination.vue';
import FilterSelect from '~/components/atoms/FilterSelect.vue';
import { useToast } from 'vue-toastification';
import { usePermissions } from '~/middleware/permission';
import PropertyRegion from '~/components/organisms/PropertyRegion.vue';

const { t } = useI18n();
const toast = useToast();
const { permissions, loading } = usePermissions();

const props = defineProps({
  id: Number, // ID de l'element
  isSubRegion: { type: Boolean, default: false },
  isSubRegionOpen: Boolean,
});
const emit = defineEmits(['show-subregion', 'close-subregion']);
const SubRegion = ref(props.isSubRegionOpen);
const showRegionDetailComponent = ref(null);
const regionDetailId = ref(null);
const router = useRouter();
const {
  $RouteApiService,
  $apiManager,
  $DocumentManagerApiService,
  $SupplyPointApiService,
  $ContractApiService,
} = useNuxtApp();
const pending = ref(true);
const error = ref(null);
const data = ref(null);
const objectPermissions = ref(null);
const exportingCsv = ref(false);
const exportingSupplyPointsCsv = ref(false);
// tabs
const routePositions = ref([]);
const routePositionsPending = ref(false);
const routePositionsError = ref(null);

const activeTab = ref('routepositions');

// pagination (positions)
const pagination = ref({
  page: 1,
  perPage: 50,
  total: 0,
  totalPages: 0,
  previous: null,
  next: null,
  isFiltered: false
});

const sortBy = ref('position');
const sortDesc = ref(false);

// supply points tab (lazy)
const supplyPoints = ref([]);
const supplyPointsPending = ref(false);
const supplyPointsError = ref(null);
const supplyPointsLoaded = ref(false);
const supplyPointStatusOptions = ref([]);
const contractStatusOptions = ref([]);
const selectedSupplyPointStatuses = ref([]);
const selectedContractStatuses = ref([]);
const supplyPointsSortBy = ref('');
const supplyPointsSortDesc = ref(false);
const supplyPointsPagination = ref({
  page: 1,
  perPage: 20,
  total: 0,
  totalPages: 0,
  previous: null,
  next: null,
  isFiltered: false
});

const getRoutePositions = async (routeId, page = 1, sort = 'token', desc = false) => {
  routePositionsPending.value = true;
  routePositionsError.value = null;
  try {
    const data = await $RouteApiService.getAllRoutePositions('', page, sort, desc, routeId);

    routePositions.value = data.results;
    Object.assign(pagination.value, {
      total: data.count,
      totalPages: Math.ceil(data.count / pagination.value.perPage),
      previous: data.previous,
      next: data.next,
      isFiltered: false
    });
  } catch (err) {
    routePositionsError.value = err;
  } finally {
    routePositionsPending.value = false;
  }
}

const ensureSupplyPointFilterCatalogs = async () => {
  if (supplyPointStatusOptions.value.length === 0) {
    try {
      supplyPointStatusOptions.value = await $SupplyPointApiService.getFilterStatus() || [];
    } catch (err) {
      console.error(err);
    }
  }
  if (contractStatusOptions.value.length === 0) {
    try {
      contractStatusOptions.value = await $ContractApiService.getFilterStatus() || [];
    } catch (err) {
      console.error(err);
    }
  }
}

const getSupplyPointsOrdering = () => {
  if (!supplyPointsSortBy.value) return null;
  return `${supplyPointsSortDesc.value ? '-' : ''}${supplyPointsSortBy.value}`;
}

const getRouteSupplyPoints = async (page = 1) => {
  supplyPointsPending.value = true;
  supplyPointsError.value = null;
  try {
    await ensureSupplyPointFilterCatalogs();
    const statusIds = selectedSupplyPointStatuses.value.map((s) => s.id);
    const contractStatusIds = selectedContractStatuses.value.map((s) => s.id);
    const result = await $RouteApiService.getRouteSupplyPoints(
      props.id,
      page,
      supplyPointsPagination.value.perPage,
      statusIds,
      contractStatusIds,
      getSupplyPointsOrdering()
    );

    supplyPoints.value = result.results || [];
    Object.assign(supplyPointsPagination.value, {
      page,
      total: result.count || 0,
      totalPages: Math.ceil((result.count || 0) / supplyPointsPagination.value.perPage),
      previous: result.previous ?? null,
      next: result.next ?? null,
      isFiltered: statusIds.length > 0 || contractStatusIds.length > 0
    });
    supplyPointsLoaded.value = true;
  } catch (err) {
    supplyPointsError.value = err;
    supplyPoints.value = [];
  } finally {
    supplyPointsPending.value = false;
  }
}

const resetSupplyPointsState = () => {
  supplyPoints.value = [];
  supplyPointsLoaded.value = false;
  supplyPointsError.value = null;
  selectedSupplyPointStatuses.value = [];
  selectedContractStatuses.value = [];
  supplyPointsSortBy.value = '';
  supplyPointsSortDesc.value = false;
  Object.assign(supplyPointsPagination.value, {
    page: 1,
    total: 0,
    totalPages: 0,
    previous: null,
    next: null,
    isFiltered: false
  });
}

const getPermissions = async () => {
  error.value = null;
  try {
    const data = await $RouteApiService.getPermissions();
    objectPermissions.value = data;
  } catch (err) {
    error.value = err;
  }
}
const getData = async () => {
  if (!objectPermissions.value?.can_view) {
    emit('close-subregion');
    return
  }
  pending.value = true;
  error.value = null;
  resetSupplyPointsState();
  try {
    const result = await $RouteApiService.getDetail(props.id);
    data.value = result;

  } catch (err) {
    error.value = err;
  } finally {
    pending.value = false;
    await getRoutePositions(props.id, 1, sortBy.value, sortDesc.value);
    if (activeTab.value === 'supplypoints') {
      await getRouteSupplyPoints(1);
    }
  }
}

watch(() => props.id, () => {
  if (!objectPermissions.value?.can_view) {
    emit('close-subregion');
    return
  }
  closeSubRegion();
  activeTab.value = 'routepositions';
  getData();
});

watch(() => props.isSubRegionOpen, (newValue) => {
  SubRegion.value = newValue;
  if (!newValue) {
    showRegionDetailComponent.value = null;
    regionDetailId.value = null;
  }
});

const closeSubRegion = () => {
  SubRegion.value = false;
  showRegionDetailComponent.value = null;
  regionDetailId.value = null;
  emit('show-subregion', false);
}

const showDetail = (component, id) => {
  if (!id) return;
  showRegionDetailComponent.value = component;
  regionDetailId.value = id;
  SubRegion.value = true;
  emit('show-subregion', true);
}

const propertyLabel = (prop) => {
  if (!prop || typeof prop !== 'object') return prop;
  return prop.name
    || [prop.address_street?.name, prop.address_street_number?.name, prop.address_city?.name].filter(Boolean).join(' ')
    || prop.token;
}

const edit = function () {
  navigateTo('/service/routes/edit/' + props.id);
}

const setActiveTab = async (tab) => {
  activeTab.value = tab;
  if (tab === 'supplypoints' && !supplyPointsLoaded.value && !supplyPointsPending.value) {
    await getRouteSupplyPoints(1);
  }
}

const handlePageChange = (newPage) => {
  pagination.value.page = newPage;
  getRoutePositions(props.id, newPage, sortBy.value, sortDesc.value);
}

const handleSort = (key) => {
  if (sortBy.value === key) {
    sortDesc.value = !sortDesc.value;
  } else {
    sortBy.value = key;
    sortDesc.value = false;
  }
  getRoutePositions(props.id, pagination.value.page, sortBy.value, sortDesc.value);
}

const handleSupplyPointsPageChange = (newPage) => {
  supplyPointsPagination.value.page = newPage;
  getRouteSupplyPoints(newPage);
}

const handleSupplyPointsSort = (key) => {
  if (supplyPointsSortBy.value === key) {
    supplyPointsSortDesc.value = !supplyPointsSortDesc.value;
  } else {
    supplyPointsSortBy.value = key;
    supplyPointsSortDesc.value = false;
  }
  getRouteSupplyPoints(1);
}

const handleSupplyPointStatusFilter = (selected) => {
  selectedSupplyPointStatuses.value = selected || [];
  getRouteSupplyPoints(1);
}

const handleContractStatusFilter = (selected) => {
  selectedContractStatuses.value = selected || [];
  getRouteSupplyPoints(1);
}

const resetSupplyPointFilters = () => {
  selectedSupplyPointStatuses.value = [];
  selectedContractStatuses.value = [];
  getRouteSupplyPoints(1);
}

onMounted(async () => {
  await getPermissions();
  if (!objectPermissions.value?.can_view) {
    pending.value = false;
    toast.error(t('common.no_permissions'));
    emit('close-subregion');
    return;
  }
  await getData();
});

const exportPollingInterval = ref(null);
const supplyPointsExportPollingInterval = ref(null);

const stopExportPolling = () => {
  if (exportPollingInterval.value) {
    clearInterval(exportPollingInterval.value);
    exportPollingInterval.value = null;
  }
}

const stopSupplyPointsExportPolling = () => {
  if (supplyPointsExportPollingInterval.value) {
    clearInterval(supplyPointsExportPollingInterval.value);
    supplyPointsExportPollingInterval.value = null;
  }
}

const downloadExportedDocument = async (documentId, documentName) => {
  try {
    const file = await $DocumentManagerApiService.viewDocument(documentId);
    const link = document.createElement('a');
    const fileUrl = URL.createObjectURL(file);
    link.href = fileUrl;
    link.download = documentName || `${data.value?.token || 'route'}_export.csv`;
    link.click();
    setTimeout(() => URL.revokeObjectURL(fileUrl), 250);
  } catch (err) {
    console.error('Error downloading route export:', err);
    toast.error(t('common.error'));
  }
}

const pollExportTask = ({ taskId, setIntervalValue, clearIntervalFn, loadingRef, defaultFilename }) => {
  const intervalId = setInterval(async () => {
    try {
      const response = await $apiManager.checkTask(taskId);
      const status = response?.state || response?.status;
      if (status === 'SUCCESS' || status === 'completed') {
        clearIntervalFn();
        loadingRef.value = false;
        const result = response?.result || response;
        if (result?.status === 'error') {
          toast.error(result.message || t('common.error'));
        } else if (result?.document_id) {
          await downloadExportedDocument(
            result.document_id,
            result.filename || result.document_name || defaultFilename
          );
          toast.success(t('common.export_completed') || t('common.saved_successfully'));
        } else {
          toast.error(t('common.error'));
        }
      } else if (status === 'FAILURE' || status === 'failed') {
        clearIntervalFn();
        loadingRef.value = false;
        toast.error(response?.error || t('common.error'));
      }
    } catch (err) {
      console.error('Error polling route export task:', err);
      clearIntervalFn();
      loadingRef.value = false;
      toast.error(t('common.error'));
    }
  }, 2000);
  setIntervalValue(intervalId);
}

const downloadRoutePositionsCsv = async () => {
  if (exportingCsv.value) return;
  exportingCsv.value = true;
  try {
    const response = await $RouteApiService.exportRoutePositions(props.id);
    if (response?.task_id) {
      pollExportTask({
        taskId: response.task_id,
        setIntervalValue: (id) => { exportPollingInterval.value = id; },
        clearIntervalFn: stopExportPolling,
        loadingRef: exportingCsv,
        defaultFilename: `${data.value?.token || 'route'}_positions.csv`,
      });
    } else {
      exportingCsv.value = false;
      toast.error(t('common.error'));
    }
  } catch (err) {
    console.error('Error triggering route positions export:', err);
    exportingCsv.value = false;
    toast.error(t('common.error'));
  }
}

const downloadRouteSupplyPointsCsv = async () => {
  if (exportingSupplyPointsCsv.value) return;
  exportingSupplyPointsCsv.value = true;
  try {
    const response = await $RouteApiService.exportRouteSupplyPoints(props.id);
    if (response?.task_id) {
      pollExportTask({
        taskId: response.task_id,
        setIntervalValue: (id) => { supplyPointsExportPollingInterval.value = id; },
        clearIntervalFn: stopSupplyPointsExportPolling,
        loadingRef: exportingSupplyPointsCsv,
        defaultFilename: `${data.value?.token || 'route'}_supply_points.csv`,
      });
    } else {
      exportingSupplyPointsCsv.value = false;
      toast.error(t('common.error'));
    }
  } catch (err) {
    console.error('Error triggering route supply points export:', err);
    exportingSupplyPointsCsv.value = false;
    toast.error(t('common.error'));
  }
}

onUnmounted(() => {
  stopExportPolling();
  stopSupplyPointsExportPolling();
});
</script>

<template>
  <div class="region__content" :class="{ 'h-full': !isSubRegion }">

    <div v-if="pending" class="h-full min-h-[400px]">
      <AppLoading :text="$t('common.loading')" />
    </div>
    <div v-else-if="error">
      <p>{{ $t('common.error') }}: {{ error.message }}</p>
      <p><button @click="getData" class="underline text-sky-500 hover:no-underline">{{ $t('common.load_again')
          }}</button></p>
    </div>
    <div v-else-if="objectPermissions?.can_view" class="pr-2 relative transition-all duration-500 ease"
      :class="{ 'h-full overflow-y-auto': !isSubRegion, 'mr-[48vw]': SubRegion }">
      <div class="flex justify-between relative">
        <H1Region class="mb-3">{{ $t('route') }}</H1Region>
        <OptionsDropdown v-if="objectPermissions?.can_change" id="ConnectionRequestRegionOptions">
          <DropdownOption :name="`${t('common.modify')} ${t('route')}`" @click="edit"></DropdownOption>
        </OptionsDropdown>
      </div>


      <div v-if="data" id="item_data" :data-rel=id>
        <RouteDetail :id="props.id" :data="data"></RouteDetail>
        <AtomsTabs>
          <li class="me-2">
            <a href="#tab_routepositions" @click.prevent="setActiveTab('routepositions')"
              :class="{ 'text-sky-600 border-sky-600': activeTab === 'routepositions', 'hover:text-gray-600 hover:border-gray-300': activeTab !== 'routepositions' }"
              aria-current="page">
              <Icon name="fa6-solid:street-view" class="display-inline mr-2" />{{ $t("service_block.route_order") }} ({{ pagination?.total || 0 }})
            </a>
          </li>
          <li class="me-2">
            <a href="#tab_supplypoints" @click.prevent="setActiveTab('supplypoints')"
              :class="{ 'text-sky-600 border-sky-600': activeTab === 'supplypoints', 'hover:text-gray-600 hover:border-gray-300': activeTab !== 'supplypoints' }">
              <Icon name="fa6-solid:faucet" class="display-inline mr-2" />{{ $t("common.supply_points") }}
              <span v-if="supplyPointsLoaded"> ({{ supplyPointsPagination?.total || 0 }})</span>
            </a>
          </li>
        </AtomsTabs>
        <div id="tabpanels">
          <section v-show="activeTab === 'routepositions'" role="tabpanel" id="tab_routepositions"
            class="bg-white antialiased py-3">
            <div v-if="routePositionsPending">
              <AppLoading :text="$t('common.loading')" />
            </div>
            <div v-else-if="routePositionsError">
              <p>{{ $t('common.error') }}: {{ routePositionsError.message }}</p>
            </div>
            <div v-else>
              <div class="flex justify-end gap-2 mb-2">
                <button @click="downloadRoutePositionsCsv" :disabled="exportingCsv"
                  class="button button-secondary flex items-center gap-2">
                  <Icon :name="exportingCsv ? 'fa6-solid:spinner' : 'fa6-solid:file-csv'" :class="{ 'animate-spin': exportingCsv }" />
                  {{ exportingCsv ? t('common.loading') + '...' : t('common.download') + ' CSV' }}
                </button>
              </div>
              <!-- Table Header -->
              <div class="grid grid-cols-[50px,200px,1fr,1fr] gap-3 text-base border-b items-center font-semibold text-gray-700 py-2">
                <span>{{ $t('order') }}</span>
                <TableHeader :label="$t('common.code')" sortKey="token" :currentSortBy="sortBy"
                  :sortDesc="sortDesc" @sort="handleSort" />
                <TableHeader :label="$t('common.properties')" sortKey="properties" :currentSortBy="sortBy"
                  :sortDesc="sortDesc" @sort="handleSort" />
                <TableHeader :label="$t('common.reader_observation')" sortKey="reader_observation" :currentSortBy="sortBy"
                  :sortDesc="sortDesc" @sort="handleSort" />
              </div>

              <!-- Table Rows -->
              <div class="max-h-[55vh] overflow-y-auto">
                <div v-for="routePosition in routePositions" :key="routePosition.id"
                  class="grid grid-cols-[50px,200px,1fr,1fr] gap-3 p-1 border-b hover:bg-gray-50 transition-colors duration-200">
                  <span>{{ routePosition.position }}.</span>
                  <span v-format-route-code>{{ routePosition.token }}</span>
                  <span>
                    <template v-if="routePosition.properties?.length && typeof routePosition.properties[0] === 'object'">
                      <template v-for="(prop, i) in routePosition.properties" :key="prop.id || i">
                        <span v-if="i > 0">, </span>
                        <button v-if="prop.id" type="button"
                          class="text-sky-500 hover:underline text-left"
                          :class="{ 'font-semibold': showRegionDetailComponent === 'PropertyRegion' && regionDetailId === prop.id }"
                          @click="showDetail('PropertyRegion', prop.id)">
                          {{ propertyLabel(prop) }}
                        </button>
                        <span v-else>{{ propertyLabel(prop) }}</span>
                      </template>
                    </template>
                    <template v-else-if="routePosition._properties_display">
                      <span v-for="(prop, i) in routePosition._properties_display" :key="i">{{ i > 0 ? ', ' : '' }}{{ prop }}</span>
                    </template>
                    <template v-else-if="routePosition.properties && routePosition.properties.length > 0">
                      <span v-for="(prop, i) in routePosition.properties" :key="i">{{ i > 0 ? ', ' : '' }}{{ prop }}</span>
                    </template>
                  </span>
                  <span>
                    {{ routePosition.reader_observation }}
                  </span>
                </div>
              </div>

              <!-- Pagination -->
              <div v-if="routePositions.length > 0" class="mt-4">
                <Pagination :pagination="pagination" @update:page="handlePageChange" />
              </div>
            </div>
          </section>

          <section v-show="activeTab === 'supplypoints'" role="tabpanel" id="tab_supplypoints"
            class="bg-white antialiased py-3">
            <div class="flex flex-wrap items-center justify-between gap-2 mb-3 relative z-20">
              <div class="flex flex-wrap items-center gap-2">
                <FilterSelect
                  :plain="true"
                  :options="supplyPointStatusOptions"
                  :filters="selectedSupplyPointStatuses"
                  :multiple="true"
                  :placeholder="t('common.supply_point_status')"
                  @update:modelValue="handleSupplyPointStatusFilter($event)">
                  <template #icon>
                    <Icon name="fa6-solid:circle-dot" class="text-md ml-2 mr-1" size="10px" />
                  </template>
                </FilterSelect>
                <FilterSelect
                  :plain="true"
                  :options="contractStatusOptions"
                  :filters="selectedContractStatuses"
                  :multiple="true"
                  :placeholder="`${t('contract')}: ${t('common.statuses')}`"
                  @update:modelValue="handleContractStatusFilter($event)">
                  <template #icon>
                    <Icon name="fa6-solid:file-contract" class="text-md ml-2 mr-1" size="10px" />
                  </template>
                </FilterSelect>
                <button
                  type="button"
                  class="px-2 py-1 hover:bg-slate-300 rounded"
                  :title="t('common.no_filter')"
                  @click="resetSupplyPointFilters">
                  <Icon name="fa6-solid:rotate-right" class="text-slate-500" />
                </button>
              </div>
              <button
                @click="downloadRouteSupplyPointsCsv"
                :disabled="exportingSupplyPointsCsv"
                class="px-3 py-1 border border-slate-300 text-slate-600 bg-white rounded hover:bg-slate-50 active:bg-slate-100 transition-colors flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
                :title="t('common.export_supply_points_csv')">
                <Icon
                  :name="exportingSupplyPointsCsv ? 'fa6-solid:spinner' : 'fa6-solid:file-csv'"
                  class="text-sm text-slate-500"
                  :class="{ 'animate-spin': exportingSupplyPointsCsv }" />
                {{ exportingSupplyPointsCsv ? t('common.loading') + '...' : t('common.export_supply_points_csv') }}
              </button>
            </div>

            <div v-if="supplyPointsPending">
              <AppLoading :text="$t('common.loading')" />
            </div>
            <div v-else-if="supplyPointsError">
              <p>{{ $t('common.error') }}: {{ supplyPointsError.message }}</p>
              <p>
                <button @click="getRouteSupplyPoints(supplyPointsPagination.page)" class="underline text-sky-500 hover:no-underline">
                  {{ $t('common.load_again') }}
                </button>
              </p>
            </div>
            <div v-else>
              <div class="max-h-[55vh] overflow-y-auto relative z-0">
                <div class="grid grid-cols-[70px,1fr,1fr,1.2fr,1fr,80px,1.5fr] gap-2 text-sm border-b items-center font-semibold text-gray-700 py-2 sticky top-0 bg-white z-[1]">
                  <span>{{ $t('order') }}</span>
                  <TableHeader
                    :label="$t('common.properties')"
                    sortKey="property__token"
                    :currentSortBy="supplyPointsSortBy"
                    :sortDesc="supplyPointsSortDesc"
                    @sort="handleSupplyPointsSort" />
                  <TableHeader
                    :label="$t('common.supply_points')"
                    sortKey="token"
                    :currentSortBy="supplyPointsSortBy"
                    :sortDesc="supplyPointsSortDesc"
                    @sort="handleSupplyPointsSort" />
                  <TableHeader
                    :label="$t('common.status')"
                    sortKey="status__name"
                    :currentSortBy="supplyPointsSortBy"
                    :sortDesc="supplyPointsSortDesc"
                    @sort="handleSupplyPointsSort" />
                  <span>{{ $t('meter') }}</span>
                  <span>{{ $t('reading') }}</span>
                  <TableHeader
                    :label="$t('contract')"
                    sortKey="contracts__status__name"
                    :currentSortBy="supplyPointsSortBy"
                    :sortDesc="supplyPointsSortDesc"
                    @sort="handleSupplyPointsSort" />
                </div>

                <div
                  v-for="item in supplyPoints"
                  :key="item.id"
                  class="grid grid-cols-[70px,1fr,1fr,1.2fr,1fr,80px,1.5fr] gap-2 text-sm p-1 border-b hover:bg-gray-50 transition-colors duration-200 items-start">
                  <span class="text-slate-600">
                    {{ item.route_position?.position ?? '—' }}
                    <span v-if="item.route_position?.token" class="block text-xs text-slate-400">{{ item.route_position.token }}</span>
                  </span>
                  <span class="truncate" :title="item.property?.token">{{ item.property?.token || '—' }}</span>
                  <span class="truncate font-medium" :title="item.token">{{ item.token || '—' }}</span>
                  <span>
                    <AtomsColorBadge
                      v-if="item.status"
                      :value="item.status.name || item.status.token"
                      :color="item.status.color" />
                    <span v-else>—</span>
                  </span>
                  <span class="truncate" :title="item.meter?.code">{{ item.meter?.code || '—' }}</span>
                  <span>{{ item.has_reading ? t('common.yes') : t('common.no') }}</span>
                  <span class="min-w-0">
                    <template v-if="item.contracts?.length">
                      <div v-for="(contract, idx) in item.contracts" :key="`${item.id}-${contract.token}-${idx}`" class="flex items-center gap-1 mb-0.5">
                        <span class="truncate text-xs" :title="contract.token">{{ contract.token }}</span>
                        <AtomsColorBadge
                          v-if="contract.status"
                          :value="contract.status.name || contract.status.token"
                          :color="contract.status.color"
                          class="scale-90 origin-left" />
                      </div>
                    </template>
                    <span v-else class="text-slate-400">—</span>
                  </span>
                </div>
                <div v-if="supplyPoints.length === 0" class="py-4 text-sm text-slate-500">
                  {{ $t('common.no_records') }}
                </div>
              </div>

              <div v-if="supplyPointsPagination.total > 0" class="mt-4">
                <Pagination :pagination="supplyPointsPagination" @update:page="handleSupplyPointsPageChange" />
              </div>
            </div>
          </section>
        </div>
      </div><!-- end if data -->
    </div><!-- end if pending -->

    <div v-if="SubRegion" role="region" id="subregion"
      class="h-full border-l border-gray-100 transition-all duration-500 ease text-base bg-white flex flex-col overflow-hidden fixed top-0 right-0 w-[48vw] z-50"
      :class="{ 'translate-x-0': SubRegion, 'translate-x-full': !SubRegion }">
      <div id="region_nav" class="mb-3 px-3">
        <button @click="closeSubRegion()" class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300">
          <Icon name="fa6-solid:angles-right" class="text-slate-500" />
        </button>
      </div>
      <div class="pl-10 flex-1 overflow-y-auto pb-24 pr-2">
        <PropertyRegion v-if="showRegionDetailComponent === 'PropertyRegion'" :id="regionDetailId"
          :isSubRegion="true" />
      </div>
    </div>
  </div>
</template>
