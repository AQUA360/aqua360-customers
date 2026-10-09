<script setup>
import SearchEntityInput from './SearchEntityInput.vue';

const props = defineProps({
  supply_cut_data: Object,
})

const { t } = useI18n();
const emit = defineEmits(['change'])
const { $ConfiglistApiService, $SupplyCutApiService } = useNuxtApp();

const statuses = ref([])
const causes = ref([])

const selectedStatuses = ref([])
const selectedCauses = ref([])
const dateStart = ref(null)
const dateEnd = ref(null)
const execStart = ref(null)
const execEnd = ref(null)
const selectedSupplyCuts = ref([])

const loadingStatuses = ref(false)
const loadingCauses = ref(false)

const fetchConfigData = async (service, entity, targetArray, loading) => {
  try {
    loading.value = true;
    const data = await $ConfiglistApiService.getAll(service + '/' + entity);
    targetArray.value = [];
    if (data.results) {
      data.results.forEach(item => {
        targetArray.value.push({
          label: item.name ? item.name : item.title ? item.title : item.token,
          code: item.id
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
  await fetchConfigData('service', 'supply-cut-status', statuses, loadingStatuses)
  try {
    causes.value = (await $SupplyCutApiService.getCauses()).map(item => ({
      label: item.name ? item.name : item.token,
      code: item.id
    }))
  } catch (error) {
    console.error('Error fetching supply cut causes:', error);
  } finally {
    loadingCauses.value = false;
  }
}

const onSupplyCutSelected = (event) => {
  if (!event?.id) return;
  if (selectedSupplyCuts.value.some(cut => cut.id === event.id)) {
    selectedSupplyCuts.value = selectedSupplyCuts.value.filter(cut => cut.id !== event.id)
  } else {
    selectedSupplyCuts.value.push(event)
  }
  emitChange()
}

const removeSelectedSupplyCut = (cut) => {
  selectedSupplyCuts.value = selectedSupplyCuts.value.filter(item => item.id !== cut.id)
  emitChange()
}

const loadData = (cutData) => {
  if (cutData?.supply_cuts) selectedSupplyCuts.value = cutData.supply_cuts
  if (cutData?.statuses) selectedStatuses.value = statuses.value.filter(s => cutData.statuses.includes(s.code))
  if (cutData?.causes) selectedCauses.value = causes.value.filter(c => cutData.causes.includes(c.code))
  if (cutData?.date_start) dateStart.value = cutData.date_start
  if (cutData?.date_end) dateEnd.value = cutData.date_end
  if (cutData?.exec_start) execStart.value = cutData.exec_start
  if (cutData?.exec_end) execEnd.value = cutData.exec_end
}

const emitChange = () => {
  emit('change', {
    supply_cuts: selectedSupplyCuts.value,
    statuses: selectedStatuses.value.map(s => s.code),
    causes: selectedCauses.value.map(c => c.code),
    date_start: dateStart.value,
    date_end: dateEnd.value,
    exec_start: execStart.value,
    exec_end: execEnd.value,
  })
}

onMounted(async () => {
  await loadSelectData()
  loadData(props.supply_cut_data)
})

watch([
  selectedStatuses,
  selectedCauses,
  dateStart,
  dateEnd,
  execStart,
  execEnd
], async () => {
  emitChange()
}, { deep: true });

watch(() => props.supply_cut_data, async (newVal) => {
  loadData(newVal)
}, { deep: true });
</script>

<template>
  <div class="py-3 bg-white rounded-lg shadow-sm">
    <div class="grid grid-cols-2 gap-4">

      <div class="pr-2 border-r border-slate-200">
        <label class="block text-sm font-medium text-slate-600 mb-2">{{ $t('service_block.cut_date_expected_start') }}</label>
        <div class="grid grid-cols-[auto,1fr,auto,1fr] items-center gap-2">
          <label class="block text-sm font-medium text-slate-600 mb-2 mr-5">{{ $t('common.from') }}:</label>
          <AtomsInputDate v-model="dateStart" class="mb-2" />
          <label class="block text-sm font-medium text-slate-600 mb-2 mr-5">{{ $t('common.to') }}:</label>
          <AtomsInputDate v-model="dateEnd" class="mb-2" />
        </div>
      </div>

      <div class="pr-2 border-r border-slate-200">
        <label class="block text-sm font-medium text-slate-600 mb-2">{{ $t('service_block.cut_date_real_start') }}</label>
        <div class="grid grid-cols-[auto,1fr,auto,1fr] items-center gap-2">
          <label class="block text-sm font-medium text-slate-600 mb-2 mr-5">{{ $t('common.from') }}:</label>
          <AtomsInputDate v-model="execStart" class="mb-2" />
          <label class="block text-sm font-medium text-slate-600 mb-2 mr-5">{{ $t('common.to') }}:</label>
          <AtomsInputDate v-model="execEnd" class="mb-2" />
        </div>
      </div>

      <div>
        <label class="block text-sm font-medium text-slate-600 mb-2">{{ $t('common.status') }}: {{ $t('supply_cut') }}</label>
        <v-select multiple class="block w-full mr-1 custom-select" v-model="selectedStatuses" :options="statuses"
          :loading="loadingStatuses" />
      </div>

      <div>
        <label class="block text-sm font-medium text-slate-600 mb-2">{{ $t('order_block.reason') }}: {{ $t('supply_cut') }}</label>
        <v-select multiple class="block w-full mr-1 custom-select" v-model="selectedCauses" :options="causes"
          :loading="loadingCauses" />
      </div>

      <SearchEntityInput :service="$SupplyCutApiService" @select="onSupplyCutSelected"
        :title="$t('search_block.search_supply_cut')" :result_value="'distinct_streets'" :methodName="'getData'" />

      <div v-if="selectedSupplyCuts?.length > 0">
        <label class="block text-sm font-medium text-slate-600 mb-2">{{ $t('service_block.selected_supply_cuts') }}</label>
        <div class="flex flex-wrap gap-2">
          <span v-for="cut in selectedSupplyCuts" :key="cut.id"
            class="group relative bg-slate-100 text-slate-800 px-3 py-1 rounded-full text-sm border border-slate-300 flex items-center gap-2">
            <span>
              {{ cut.token }}
              <span v-if="cut.date_start" class="ml-2 text-xs text-slate-500">
                {{ formatDateTime(cut.date_start) }}
              </span>
            </span>
            <button @click="removeSelectedSupplyCut(cut)"
              class="absolute right-0 top-0 h-4 w-4 bg-white rounded-full text-slate-500 opacity-0 hover:text-slate-700 hover:underline group-hover:opacity-100 transition-all duration-300">
              <Icon name="fa6-solid:xmark"
                class="text-red-500 text-sm m-auto opacity-0 group-hover:opacity-100 m-auto" />
            </button>
          </span>
        </div>
      </div>
      <span v-else></span>
    </div>
  </div>
</template>
