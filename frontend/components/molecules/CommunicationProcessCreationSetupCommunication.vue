<script setup>
import SearchEntityInput from './SearchEntityInput.vue';
import OptionSelectorGroup from '../atoms/OptionSelectorGroup.vue';

const props = defineProps({
  communication_data: Object,
})

const { t } = useI18n();
const emit = defineEmits(['change'])
const { $ConfiglistApiService, $StreetApiService, $AddressApiService } = useNuxtApp();

const loadingConfig = ref(false)

const loadingUseTypes = ref(false)
const loadingTypes = ref(false)
const loadingStatuses = ref(false)

const statuses = ref([])
const useTypes = ref([])
const types = ref([])


const selectedPersons = ref([])
const selectedContracts = ref([])
const selectedHasInvoices = ref(['has_invoices', 'no_has_invoices'])
const selectedHasReadings = ref(['has_readings', 'no_has_readings'])
const inProcess = ref(false)
const selectedUseTypes = ref([])
const selectedTypes = ref([])
const selectedStatuses = ref([])
const selectedStartCreatedDate = ref(null)
const selectedEndCreatedDate = ref(null)

const communication_filter_data = ref({})

const containsInvoicesOptions = [
  { value: 'has_invoices', name: 'customer_service_block.contains_invoices' },
  { value: 'no_has_invoices', name: 'customer_service_block.no_contains_invoices' },
]

const containsReadingsOptions = [
  { value: 'has_readings', name: 'customer_service_block.contains_readings' },
  { value: 'no_has_readings', name: 'customer_service_block.no_contains_readings' },
]


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

const onContractSelected = async (contract) => {
  if (!selectedContracts.value.includes(contract)) {
    selectedContracts.value.push(contract);
  }
  await emitChange()
}

const removeSelectedContract = async (item) => {
  selectedContracts.value = selectedContracts.value.filter(c => c.id !== item.id)
  await emitChange()
}

const changeHasInvoices = (value) => {
  if (selectedHasInvoices.value.includes(value)) {
    selectedHasInvoices.value = selectedHasInvoices.value.filter(a => a !== value)
  }
  else {
    selectedHasInvoices.value.push(value)
  }
}

const changeHasReadings = (value) => {
  if (selectedHasReadings.value.includes(value)) {
    selectedHasReadings.value = selectedHasReadings.value.filter(a => a !== value)
  }
  else {
    selectedHasReadings.value.push(value)
  }
}

const onPersonSelected = async (event) => {
  if (selectedPersons.value.includes(event)) {
    selectedPersons.value = selectedPersons.value.filter(a => a.id !== event.id)
  }
  else {
    selectedPersons.value.push(event)
  }
  await emitChange()
}

const removeSelectedPerson = (person) => {
  selectedPersons.value = selectedPersons.value.filter(a => a.id !== person.id)
  emitChange()
}

const loadData = async (contractData) => {
  if (contractData?.persons) selectedPersons.value = contractData?.persons
  if (contractData?.contracts) selectedContracts.value = contractData?.contracts
  if (contractData?.comm_use_types) selectedUseTypes.value = useTypes.value.filter(c => contractData?.comm_use_types?.includes(c.code))
  if (contractData?.comm_types) selectedTypes.value = types.value.filter(c => contractData?.comm_types?.includes(c.code))
  if (contractData?.containsInvoices) selectedHasInvoices.value = containsInvoicesOptions.filter(m => contractData?.containsInvoices.includes(m.value))
  if (contractData?.containsReadings) selectedHasReadings.value = containsReadingsOptions.filter(m => contractData?.containsReadings.includes(m.value))
  if (contractData?.comm_start_created_date) selectedStartCreatedDate.value = contractData?.comm_start_due_date
  if (contractData?.comm_end_created_date) selectedEndCreatedDate.value = contractData?.comm_end_due_date
  if (contractData?.comm_statuses) selectedStatuses.value = statuses.value.filter(c => contractData?.comm_statuses?.includes(c.code))
  if (contractData?.in_process) inProcess.value = contractData?.in_process
}

const loadSelectData = async () => {
  await fetchConfigData('communication', 'communication-use-type', useTypes, loadingUseTypes);
  await fetchConfigData('communication', 'message-type', types, loadingTypes);
  await fetchConfigData('communication', 'communication-status', statuses, loadingStatuses);
}


const emitChange = () => {
  communication_filter_data.value = {
    persons: selectedPersons.value,
    contracts: selectedContracts.value,
    comm_use_types: selectedUseTypes.value.map(c => c.code),
    comm_types: selectedTypes.value.map(c => c.code),
    containsInvoices: selectedHasInvoices.value,
    containsReadings: selectedHasReadings.value,
    comm_start_created_date: selectedStartCreatedDate.value,
    comm_end_created_date: selectedEndCreatedDate.value,
    comm_statuses: selectedStatuses.value.map(c => c.code),
    in_process: inProcess.value,
  }
  emit('change', communication_filter_data.value)
}

onMounted(async () => {
  await loadSelectData()
  await loadData(props.person_data)
})


watch([
  selectedHasInvoices,
  selectedHasReadings,
  selectedUseTypes,
  selectedTypes,
  selectedStatuses,
  selectedStartCreatedDate,
  selectedEndCreatedDate,
  selectedPersons,
  selectedContracts,
  inProcess,
], async () => {
  await emitChange()
}, { deep: true });

watch(props.communication_data, async (newVal) => {
  await loadData(newVal)
}, { deep: true });

watch(props.communication_data, async (newVal) => {
  await loadData(newVal)
}, { deep: true });

</script>

<template>
  <div class="py-3 bg-white rounded-lg">

    <div class="grid grid-cols-2 gap-4">
      <div class="col-span-2 grid grid-cols-3 gap-4">
        <div>
          <div class="text-sm font-medium text-gray-500 mb-2 flex items-center gap-2">
            <abbr :title="t('informative_block.info_show_all_data')" class="flex items-center">
              <Icon name="fa6-solid:circle-info" class="text-slate-500" />
            </abbr>
            <span>
              {{ t('customer_service_block.contains_invoices') }}
            </span>
          </div>
          <OptionSelectorGroup :options="containsInvoicesOptions" :selected-values="selectedHasInvoices"
            selection-mode="multiple" indicator-type="checkbox" @select="changeHasInvoices" />
        </div>

        <div>
          <div class="text-sm font-medium text-gray-500 mb-2 flex items-center gap-2">
            <abbr :title="t('informative_block.info_show_all_data')" class="flex items-center">
              <Icon name="fa6-solid:circle-info" class="text-slate-500" />
            </abbr>
            <span>
              {{ t('customer_service_block.contains_readings') }}
            </span>
          </div>
          <OptionSelectorGroup :options="containsReadingsOptions" :selected-values="selectedHasReadings"
            selection-mode="multiple" indicator-type="checkbox" @select="changeHasReadings" />
        </div>

        <div>
          <div class="text-sm font-medium text-gray-500 mb-2 flex items-center gap-2">
            <span>
              {{ t('customer_service_block.in_comm_process') }}
            </span>
          </div>
          <div class="flex gap-3">
            <div @click="inProcess = !inProcess"
              class="flex items-center gap-2 px-3 py-1.5 rounded-md transition-all duration-200" :class="[
                inProcess ? 'cursor-pointer bg-sky-50 ring-1 ring-sky-500' : 'cursor-pointer hover:bg-gray-50'
              ]">
              <div class="w-3.5 h-3.5 border-2 flex items-center justify-center shrink-0 rounded-sm"
                :class="[inProcess ? 'border-sky-500 bg-sky-500' : 'border-gray-300']">
                <Icon v-if="inProcess" name="fa6-solid:check" class="text-white" />
              </div>
              <span class="text-xs font-medium" :class="[inProcess ? 'text-sky-700' : 'text-gray-600']">
                {{ t('customer_service_block.in_comm_process') }}
              </span>
            </div>
          </div>
        </div>
      </div>



      <div class="pr-2">
        <label class="block text-sm font-medium text-slate-600">{{ $t('common.creation_date') }}</label>
        <div class="grid grid-cols-[auto,1fr,auto,1fr] items-center gap-2">
          <label class="block text-sm font-medium text-slate-600 mb-2 mr-5">{{ $t('common.from') }}:</label>
          <AtomsInputDate v-model="selectedStartCreatedDate" class="mb-2" />
          <label class="block text-sm font-medium text-slate-600 mb-2 mr-5">{{ $t('common.to') }}:</label>
          <AtomsInputDate v-model="selectedEndCreatedDate" class="mb-2" />
        </div>
      </div>

      <div>
        <label class="block text-sm font-medium text-slate-600 mb-2">{{ $t('common.status') }}: {{ $t('communication')
        }}</label>
        <v-select multiple class="block w-full mr-1 custom-select" v-model="selectedStatuses" :options="statuses"
          :loading="loadingStatuses" />
      </div>

      <div class="mb-2">
        <label class="block text-sm font-medium text-slate-600 mb-2">{{ $t('common.use_type') }}: {{ $t('communication')
        }}</label>
        <v-select multiple class="block w-full mr-1 custom-select" v-model="selectedUseTypes" :options="useTypes"
          :loading="loadingUseTypes" />
      </div>

      <div class="mb-2">
        <label class="block text-sm font-medium text-slate-600 mb-2">
          {{ $t('common.type') }}: {{ $t('communication') }}</label>
        <v-select multiple class="block w-full mr-1 custom-select" v-model="selectedTypes" :options="types"
          :loading="loadingTypes" />
      </div>

      <SearchEntityInput :service="$PersonApiService" @select="onPersonSelected"
        :title="$t('search_block.search_person')" :result_value="'full_name'" class="mt-auto" />

      <div v-if="selectedPersons?.length > 0" class="mb-2">
        <label class="block text-sm font-medium text-slate-600 mb-2">{{ $t('contract_block.selected_persons') }}</label>
        <div class="flex flex-wrap gap-2 ">
          <span v-for="person in selectedPersons" :key="person.id"
            class="group relative bg-slate-100 text-slate-800 px-3 py-1 rounded-full text-sm border border-slate-300 flex items-center gap-2">
            <span>
              {{ person.full_name }}
              <span class="ml-2 text-xs text-slate-500">
                {{ person.token }}
              </span>
            </span>
            <button @click="removeSelectedPerson(person)"
              class="absolute right-0 top-0 h-4 w-4 bg-white rounded-full text-slate-500 opacity-0 hover:text-slate-700 hover:underline group-hover:opacity-100 transition-all duration-300">
              <Icon name="fa6-solid:xmark"
                class="text-red-500 text-sm m-auto opacity-0 group-hover:opacity-100 m-auto" />
            </button>
          </span>
        </div>
      </div>
      <span v-else></span>

      <SearchEntityInput :service="$ContractApiService" @select="onContractSelected"
        :title="$t('search_block.search_contract')" :result_value="'holder_full_name'" class="mt-auto" />

      <div v-if="selectedContracts?.length > 0" class="mb-2">
        <label class="block text-sm font-medium text-slate-600 mb-2">
          {{ $t('contract_block.selected_contracts') }}</label>
        <div class="flex flex-wrap gap-2 ">
          <span v-for="contract in selectedContracts" :key="contract.id"
            class="group relative bg-slate-100 text-slate-800 px-3 py-1 rounded-full text-sm border border-slate-300 flex items-center gap-2">
            <span>
              {{ contract.token }}
            </span>
            <button @click="removeSelectedContract(contract)"
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

<style scoped>
.grid {
  transition: all 0.3s ease;
}
</style>