<script setup>
import SearchEntityInput from './SearchEntityInput.vue';

const props = defineProps({
  supply_point_data: Object,
})

const { t } = useI18n();
const emit = defineEmits(['change'])
const { $ConfiglistApiService, $ConnectionApiService } = useNuxtApp();


const statuses = ref([])
const exploitations = ref([])
const connections = ref([])
const connectionTypes = ref([])
const supplyTypes = ref([])
const types = ref([])
const sources = ref([])

const selectedStatuses = ref([])
const selectedExploitation = ref(null)
const selectedConnection = ref(null)
const selectedConnectionTypes = ref([])
const selectedSupplyTypes = ref([])
const selectedTypes = ref([])
const selectedSources = ref([])
const installedAtStartDate = ref(null)
const installedAtEndDate = ref(null)
const cadastral = ref(null)

const selectedSupplyPoints = ref([])

const loadingStatuses = ref(false)
const loadingExploitations = ref(false)
const loadingConnections = ref(false)
const loadingConnectionTypes = ref(false)
const loadingSupplyTypes = ref(false)
const loadingTypes = ref(false)
const loadingSources = ref(false)

const sp_filter_data = ref({})


const fetchConfigData = async (service, entity, targetArray, loading) => {
  try {
    loading.value = true;
    const data = await $ConfiglistApiService.getAll(service + '/' + entity);
    targetArray.value = [];

    if (data.results) {
      data.results.forEach(data => {
        targetArray.value.push({
          label: data.name ? data.name : data.title ? data.title : data.token,
          code: data.id
        })
      });
    }
  } catch (error) {
    console.error(`Error fetching ${entity}:`, error);
  } finally {
    loading.value = false;
  }
}

const loadSelectData = async () => {
  await fetchConfigData('service', 'supply-point-status', statuses, loadingStatuses)
  await fetchConfigData('service', 'exploitation', exploitations, loadingExploitations)
  await fetchConfigData('service', 'connection-type', connectionTypes, loadingConnectionTypes)
  await fetchConfigData('service', 'supply-point-supply-type', supplyTypes, loadingSupplyTypes)
  await fetchConfigData('service', 'supply-point-type', types, loadingTypes)
  await fetchConfigData('service', 'supply-point-source', sources, loadingSources)
}

const loadConnections = async (page = 1, search = '') => {
  let response = null;
  loadingConnections.value = true;
  try {
    response = await $ConnectionApiService.getData(search, [], page, null, false, selectedExploitation.value? selectedExploitation.value.code : null);

    const items = response.results.map(item => ({
      value: item.id,
      label: item.token + ' - ' + item.street
    }));

    connections.value = items;

    return {
      items: items,
      hasNextPage: response && response.next ? true : false
    };
  } catch (error) {
    console.error(`Error fetching connections:`, error);
    return {
      items: [],
      hasNextPage: false
    };
  } finally {
    loadingConnections.value = false;
  }
}


const onSupplyPointSelected = async (event) => {
  selectedStatuses.value = []
  selectedTypes.value = []
  selectedSupplyTypes.value = []
  selectedConnectionTypes.value = []
  selectedSources.value = []
  selectedExploitation.value = null
  selectedConnection.value = null
  installedAtStartDate.value = null
  installedAtEndDate.value = null

  if (selectedSupplyPoints.value.includes(event)) {
    selectedSupplyPoints.value = selectedSupplyPoints.value.filter(a => a.id !== event.id)
  }
  else {
    selectedSupplyPoints.value.push(event)
  }
  await emitChange()
}

const removeSelectedSupplyPoint = (sp) => {
  selectedSupplyPoints.value = selectedSupplyPoints.value.filter(a => a.id !== sp.id)
  emitChange()
}

const updateSelect = (event, entity) => {
  switch (entity) {
    case 'connection':
      selectedConnection.value = null
      selectedConnection.value = event;
      emitChange()
      break;
  }
}

const loadData = async (spData) => {
  if (spData?.supply_points) selectedSupplyPoints.value = spData?.supply_points
  if (spData?.statuses) selectedStatuses.value = statuses.value.filter(s => spData?.statuses.includes(s.code))
  if (spData?.types) selectedTypes.value = types.value.filter(t => spData?.types.includes(t.code))
  if (spData?.supply_types) selectedSupplyTypes.value = supplyTypes.value.filter(st => spData?.supply_types.includes(st.code))
  if (spData?.connection_types) selectedConnectionTypes.value = connectionTypes.value.filter(ct => spData?.connection_types.includes(ct.code))
  if (spData?.sources) selectedSources.value = sources.value.filter(s => spData?.sources.includes(s.code))
  if (spData?.exploitation) selectedExploitation.value = exploitations.value.filter(e => spData?.exploitation.includes(e.code))
  if (spData?.connection) selectedConnection.value = connections.value.filter(c => spData?.connection.includes(c.value))
  if (spData?.installed_at_start_date) installedAtStartDate.value = spData?.installed_at_start_date
  if (spData?.installed_at_end_date) installedAtEndDate.value = spData?.installed_at_end_date
}


const emitChange = () => {
  sp_filter_data.value = {
    supply_points: selectedSupplyPoints.value,
    statuses: selectedStatuses.value.map(s => s.code),
    types: selectedTypes.value.map(t => t.code),
    supply_types: selectedSupplyTypes.value.map(st => st.code),
    connection_types: selectedConnectionTypes.value.map(ct => ct.code),
    sources: selectedSources.value.map(s => s.code),
    exploitation: selectedExploitation.value ? selectedExploitation.value.code : null,
    connection: selectedConnection.value ? selectedConnection.value.value : null,
    installed_at_start_date: installedAtStartDate.value,
    installed_at_end_date: installedAtEndDate.value
  }
  emit('change', sp_filter_data.value)
}

onMounted(async () => {
  await loadConnections(1)
  await loadSelectData()
  await loadData(props.supply_point_data)
})


watch([
  selectedStatuses,
  selectedTypes,
  selectedSupplyTypes,
  selectedConnectionTypes,
  selectedSources,
  selectedExploitation,
  selectedConnection,
  installedAtStartDate,
  installedAtEndDate
], async () => {
  if (selectedSupplyPoints.value.length > 0) {
    if (selectedStatuses.value.length > 0 ||
      selectedTypes.value.length > 0 ||
      selectedSupplyTypes.value.length > 0 ||
      selectedConnectionTypes.value.length > 0 ||
      selectedSources.value.length > 0 ||
      selectedExploitation.value ||
      selectedConnection.value ||
      installedAtStartDate.value ||
      installedAtEndDate.value
    ) {
      selectedSupplyPoints.value = []
    }
  }
  await emitChange()
}, { deep: true });

watch(props.supply_point_data, async (newVal) => {
  await loadData(newVal)
}, { deep: true });

watch(selectedExploitation , async () => {
  await loadConnections(1)
  if (selectedConnection.value && !connections.value.map(c => c.value).includes(selectedConnection.value.value)) {
    selectedConnection.value = null
  }
}, { deep: true });

</script>

<template>
  <div class="py-3 bg-white rounded-lg shadow-sm">

    <div class="grid grid-cols-2 gap-4">

      <div class="pr-2 border-r border-slate-200">
        <label class="block text-sm font-medium text-slate-600 mb-2">{{ $t('service_block.install_date') }}</label>
        <div class="grid grid-cols-[auto,1fr,auto,1fr] items-center gap-2">
          <label class="block text-sm font-medium text-slate-600 mb-2 mr-5">{{ $t('common.from') }}:</label>
          <AtomsInputDate v-model="installedAtStartDate" class="mb-2" />
          <label class="block text-sm font-medium text-slate-600 mb-2 mr-5">{{ $t('common.to') }}:</label>
          <AtomsInputDate v-model="installedAtEndDate" class="mb-2" />
        </div>
      </div>
      <span></span>

      <SearchEntityInput :service="$SupplyPointApiService" @select="onSupplyPointSelected"
        :title="$t('search_block.search_supply_point')" :result_value="'address_complete'" :methodName="'getList'" class="mt-auto" />

      <div v-if="selectedSupplyPoints?.length > 0" class="mb-2">
        <label class="block text-sm font-medium text-slate-600 mb-2">{{ $t('service_block.selected_supply_points') }}</label>
        <div class="flex flex-wrap gap-2 ">
          <span v-for="sp in selectedSupplyPoints" :key="sp.id"
            class="group relative bg-slate-100 text-slate-800 px-3 py-1 rounded-full text-sm border border-slate-300 flex items-center gap-2">
            <span>
              {{ sp.address_complete }}
              <span class="ml-2 text-xs text-slate-500">
                {{ sp.token }}
              </span>
            </span>
            <button @click="removeSelectedSupplyPoint(sp)"
              class="absolute right-0 top-0 h-4 w-4 bg-white rounded-full text-slate-500 opacity-0 hover:text-slate-700 hover:underline group-hover:opacity-100 transition-all duration-300">
              <Icon name="fa6-solid:xmark"
                class="text-red-500 text-sm m-auto opacity-0 group-hover:opacity-100 m-auto" />
            </button>
          </span>
        </div>
      </div>
      <span v-else></span>

      <div>
        <label class="block text-sm font-medium text-slate-600 mb-2">{{ $t('common.status') }}: {{ $t('supply_point') }}</label>
        <v-select multiple class="block w-full mr-1 custom-select" v-model="selectedStatuses" :options="statuses"
          :loading="loadingStatuses" />
      </div>

      <div>
        <label class="block text-sm font-medium text-slate-600 mb-2">{{ $t('common.type') }}: {{ $t('supply_point') }}</label>
        <v-select multiple class="block w-full mr-1 custom-select" v-model="selectedTypes" :options="types"
          :loading="loadingTypes" />
      </div>

      <div>
        <label class="block text-sm font-medium text-slate-600 mb-2">{{ $t('service_block.supply_source') }}: {{ $t('supply_point') }}</label>
        <v-select multiple class="block w-full mr-1 custom-select" v-model="selectedSupplyTypes" :options="supplyTypes"
          :loading="loadingSupplyTypes" />
      </div>

      <div>
        <label class="block text-sm font-medium text-slate-600 mb-2">{{ $t('common.type') }}: {{ $t('connection') }}</label>
        <v-select multiple class="block w-full mr-1 custom-select" v-model="selectedConnectionTypes"
          :options="connectionTypes" :loading="loadingConnectionTypes" />
      </div>

      <div>
        <label class="block text-sm font-medium text-slate-600 mb-2">{{ $t('service_block.supply_source') }}</label>
        <v-select multiple class="block w-full mr-1 custom-select" v-model="selectedSources" :options="sources"
          :loading="loadingSources" />
      </div>

      <div>
        <label class="block text-sm font-medium text-slate-600 mb-2">{{ $t('exploitation') }}</label>
        <v-select class="block w-full mr-1 custom-select" v-model="selectedExploitation" :options="exploitations"
          :loading="loadingExploitations" />
      </div>

      <div>
        <AtomsInfiniteScrollVueSelect :labelText="t('connection')" :loadFunction="loadConnections"
          :item="selectedConnection" @update:modelValue="updateSelect($event, 'connection')">
        </AtomsInfiniteScrollVueSelect>
      </div>

    </div>
  </div>
</template>

<style scoped>
.grid {
  transition: all 0.3s ease;
}
</style>