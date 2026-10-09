<script setup>
import SearchEntityInput from './SearchEntityInput.vue';

const props = defineProps({
  contract_data: Object,
})

const { t } = useI18n();
const emit = defineEmits(['change'])
const { $ConfiglistApiService } = useNuxtApp();

const contract_filter_data = ref({})

const selectedContractStatuses = ref([])
const selectedPersonTypes = ref(['holder'])
const selectedClauses = ref([])

const selectedAddedContracts = ref([])
const selectedPriceRates = ref([])

const contractStatuses = ref([])
const priceRates = ref([])
const clauses = ref([])

const loadingContractStatuses = ref(false)
const loadingPriceRates = ref(false)
const loadingClauses = ref(false)

const personOptions = [
  { value: 'holder', name: 'contract_block.holder' },
  { value: 'tenant', name: 'contract_block.tenant' },
  { value: 'owner', name: 'contract_block.owner' },
]

const fetchConfigData = async (service, entity, targetArray, loading) => {
  try {
    loading.value = true;
    const data = await $ConfiglistApiService.getAll(service + '/' + entity);
    targetArray.value = [];

    if (data.results) {
      data.results.forEach(data => {
        targetArray.value.push({
          label: data.name? data.name: data.title? data.title: data.token,
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
  await fetchConfigData('pricing', 'price-rate', priceRates, loadingPriceRates);
  await fetchConfigData('contract', 'contract-request-status', contractStatuses, loadingContractStatuses);
  await fetchConfigData('contract', 'contract-clauses', clauses, loadingClauses);
}

const loadData = async (contractData) => {
  if (contractData?.price_rates) selectedPriceRates.value = priceRates.value.filter(c => contractData?.price_rates.includes(c.code))
  if (contractData?.contract_statuses) selectedContractStatuses.value = contractStatuses.value.filter(c => contractData?.contract_statuses.includes(c.code))
  if (contractData?.clauses) selectedClauses.value = clauses.value.filter(c => contractData?.clauses.includes(c.code))
  if (contractData?.contracts) {
    if (selectedPriceRates.value.length == 0 && selectedContractStatuses.value.length == 0 && selectedClauses.value.length == 0) {
      selectedAddedContracts.value = contractData?.contracts
    }
  }
}

const onContractSelected = async (contract) => {
  selectedPriceRates.value = []
  selectedContractStatuses.value = []
  selectedClauses.value = []

  if (!selectedAddedContracts.value.includes(contract)) {
    selectedAddedContracts.value.push(contract);
  }
  await emitChange()
}

const removeSelectedContract = async (item) => {
  selectedAddedContracts.value = selectedAddedContracts.value.filter(c => c.id !== item.id)
  await emitChange()
}

const emitChange = () => {
  contract_filter_data.value = {
    price_rates: selectedPriceRates.value.map(c => c.code),
    contract_statuses: selectedContractStatuses.value.map(c => c.code),
    clauses: selectedClauses.value.map(c => c.code),
    person_type: selectedPersonTypes.value,
    contracts: selectedAddedContracts.value,
  }
  emit('change', contract_filter_data.value)
}

const onPersonTypeChange = async (event) => {
  if (event.target.checked) {
    selectedPersonTypes.value.push(event.target.value)
  } else {
    selectedPersonTypes.value = selectedPersonTypes.value.filter(c => c !== event.target.value)
  }
  console.log(selectedPersonTypes.value)
  await emitChange()
}

onMounted(async () => {
  await loadSelectData()
  await loadData(props.contract_data)
})

watch([
  selectedPriceRates,
  selectedContractStatuses,
  selectedClauses,
], async () => {
  if (selectedAddedContracts.value.length > 0) {
    if (
      selectedPriceRates.value.length > 0 ||
      selectedContractStatuses.value.length > 0 ||
      selectedClauses.value.length > 0) {
      selectedAddedContracts.value = []
    }
  }
  await emitChange()
}, { deep: true });

watch(props.contract_data, async (newVal) => {
  await loadData(newVal)
}, { deep: true });

</script>

<template>
  <div class="py-3 bg-white rounded-lg shadow-sm">

    <div class="mb-5">
      <label class="block text-sm font-medium text-slate-600 mb-2">{{ $t('common.includes') }}</label>
      <div class="flex flex-wrap gap-3">
        <div v-for="option in personOptions" :key="option.value" class="flex items-center">
          <input type="checkbox" :id="option.value" :value="option.value"
            :checked="selectedPersonTypes.includes(option.value)"
            @change="onPersonTypeChange"
            class="w-4 h-4 text-sky-600 bg-gray-100 border-gray-300 rounded focus:ring-sky-500">
          <label :for="option.value" class="ml-2 text-sm font-medium text-gray-700">
            {{ t(option.name) }}
          </label>
        </div>
      </div>
    </div>

    <div class="grid grid-cols-2 gap-4">
      <SearchEntityInput :service="$ContractRequestApiService" @select="onContractSelected" :title="$t('search_block.search_contract_request')"
        :result_value="'holder_full_name'" class="mt-auto" />
      <div v-if="selectedAddedContracts?.length > 0" class="mb-2">
        <label class="block text-sm font-medium text-slate-600 mb-2">{{ $t('contract_block.selected_contracts') }}</label>
        <div class="flex flex-wrap gap-2 ">
          <span v-for="contract in selectedAddedContracts" :key="contract.id"
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

      <div>
        <label class="block text-sm font-medium text-slate-600 mb-2">{{ $t('common.status') }}: {{ $t('contract_request') }}</label>
        <v-select multiple class="block w-full mr-1 custom-select" v-model="selectedContractStatuses"
          :options="contractStatuses" :loading="loadingContractStatuses" />
      </div>

      <div>
        <label class="block text-sm font-medium text-slate-600 mb-2">{{ $t('common.price_rates') }}</label>
        <v-select multiple class="block w-full mr-1 custom-select" v-model="selectedPriceRates" :options="priceRates"
          :loading="loadingPriceRates" />
      </div>

      <div>
        <label class="block text-sm font-medium text-slate-600 mb-2">{{ $t('contract_block.clauses') }}</label>
        <v-select multiple class="block w-full mr-1 custom-select" v-model="selectedClauses" :options="clauses"
          :loading="loadingClauses" />
      </div>

    </div>
  </div>
</template>

<style scoped>
.grid {
  transition: all 0.3s ease;
}
</style>