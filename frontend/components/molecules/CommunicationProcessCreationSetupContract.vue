<script setup>
import SearchEntityInput from './SearchEntityInput.vue';

const props = defineProps({
  contract_data: Object,
})

const { t } = useI18n();
const emit = defineEmits(['change'])
const { $ConfiglistApiService, $ContractApiService } = useNuxtApp();

const route = useRoute()

const contract_filter_data = ref({})

const selectedClientTypes = ref([])
const selectedUseTypes = ref([])
const selectedDebtMngs = ref([])
const selectedContractStatuses = ref([])
const selectedPaymentTypes = ref([])
const selectedRejectionReasons = ref([])
const selectedAddedContracts = ref([])
const selectedCategories = ref([])
const selectedPersonTypes = ref(['holder'])

const clientTypes = ref([])
const useTypes = ref([])
const debtManagements = ref([])
const contractStatuses = ref([])
const paymentTypes = ref([])
const rejectionReasons = ref([])
const categories = ref([])

const loadingUseTypesIds = ref(false)
const loadingClientTypesIds = ref(false)
const loadingDebtMngsIds = ref(false)
const loadingContractStatuses = ref(false)
const loadingPaymentTypes = ref(false)
const loadingRejectionReasons = ref(false)
const loadingCategories = ref(false)

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
          label: data.name || data.token,
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
  await fetchConfigData('contract', 'contract-category', categories, loadingCategories);
  await fetchConfigData('contract', 'contract-client-type', clientTypes, loadingClientTypesIds);
  await fetchConfigData('contract', 'contract-use-type', useTypes, loadingUseTypesIds);
  await fetchConfigData('contract', 'contract-debt-management', debtManagements, loadingDebtMngsIds);
  await fetchConfigData('contract', 'contract-payment-type', paymentTypes, loadingPaymentTypes);
  await fetchConfigData('billing', 'reject-motive', rejectionReasons, loadingRejectionReasons);
  await fetchConfigData('contract', 'contract-status', contractStatuses, loadingContractStatuses);
}

const loadData = async (contractData) => {
  if (contractData?.client_types) selectedClientTypes.value = clientTypes.value.filter(c => contractData?.client_types?.includes(c.code))
  if (contractData?.use_types) selectedUseTypes.value = useTypes.value.filter(c => contractData?.use_types?.includes(c.code))
  if (contractData?.debt_managements) selectedDebtMngs.value = debtManagements.value.filter(c => contractData?.debt_managements?.includes(c.code))
  if (contractData?.contract_statuses) selectedContractStatuses.value = contractStatuses.value.filter(c => contractData?.contract_statuses?.includes(c.code))
  if (contractData?.payment_types) selectedPaymentTypes.value = paymentTypes.value.filter(c => contractData?.payment_types?.includes(c.code))
  if (contractData?.rejectionReasons) selectedRejectionReasons.value = rejectionReasons.value.filter(c => contractData?.rejection_reasons?.includes(c.code))
  if (contractData?.categories) selectedCategories.value = categories.value.filter(c => contractData?.categories?.includes(c.code))
  if (contractData?.person_type) selectedPersonTypes.value = personOptions.value.filter(c => contractData?.person_type?.includes(c.value))
  if (contractData?.contracts) {
    if (selectedClientTypes.value.length == 0 && selectedUseTypes.value.length == 0 && selectedDebtMngs.value.length == 0 && selectedContractStatuses.value.length == 0 && selectedPaymentTypes.value.length == 0 && selectedRejectionReasons.value.length == 0 && selectedCategories.value.length == 0) {
      selectedAddedContracts.value = contractData?.contracts
    }
  }
}

const onContractSelected = async (contract) => {
  selectedClientTypes.value = []
  selectedUseTypes.value = []
  selectedDebtMngs.value = []
  selectedContractStatuses.value = []
  selectedPaymentTypes.value = []
  selectedRejectionReasons.value = []
  selectedCategories.value = []

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
    client_types: selectedClientTypes.value.map(c => c.code),
    use_types: selectedUseTypes.value.map(c => c.code),
    categories: selectedCategories.value.map(c => c.code),
    debt_managements: selectedDebtMngs.value.map(c => c.code),
    payment_types: selectedPaymentTypes.value.map(c => c.code),
    rejection_reasons: selectedRejectionReasons.value.map(c => c.code),
    contract_statuses: selectedContractStatuses.value.map(c => c.code),
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
  await emitChange()
}

onMounted(async () => {
  await loadSelectData()
  await loadData(props.contract_data)
  if (route.query.contract_id){
      let response = await $ContractApiService.getDetail(route.query.contract_id)
      let contract_data = {
        id: response.id,
        token: response.token,
      }
      selectedAddedContracts.value = [contract_data]
      await emitChange()
    }
})

watch([
  selectedClientTypes,
  selectedUseTypes,
  selectedCategories,
  selectedContractStatuses,
  selectedRejectionReasons,
  selectedDebtMngs,
], async () => {
  if (selectedAddedContracts.value.length > 0) {
    if (
      selectedClientTypes.value.length > 0 ||
      selectedUseTypes.value.length > 0 ||
      selectedCategories.value.length > 0 ||
      selectedContractStatuses.value.length > 0 ||
      selectedDebtMngs.value.length > 0 ||
      selectedRejectionReasons.value.length > 0) {
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
      <label class="block text-sm font-medium text-slate-600 mb-2">{{ $t('common.include') }}</label>
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
      <SearchEntityInput :service="$ContractApiService" @select="onContractSelected" :title="$t('search_block.search_contract')"
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
        <label class="block text-sm font-medium text-slate-600 mb-2">{{ $t('common.status') }}: {{ $t('contract') }}</label>
        <v-select multiple class="block w-full mr-1 custom-select" v-model="selectedContractStatuses"
          :options="contractStatuses" :loading="loadingContractStatuses" />
      </div>

      <div>
        <label class="block text-sm font-medium text-slate-600 mb-2">{{ $t('contract_block.client_type') }}</label>
        <v-select multiple class="block w-full mr-1 custom-select" v-model="selectedClientTypes" :options="clientTypes"
          :loading="loadingClientTypesIds" />
      </div>

      <div>
        <label class="block text-sm font-medium text-slate-600 mb-2">{{ $t('common.usage_type') }}</label>
        <v-select multiple class="block w-full mr-1 custom-select" v-model="selectedUseTypes" :options="useTypes"
          :loading="loadingUseTypesIds" />
      </div>

      <div>
        <label class="block text-sm font-medium text-slate-600 mb-2">{{ $t('contract_block.category') }}</label>
        <v-select multiple class="block w-full mr-1 custom-select" v-model="selectedCategories" :options="categories"
          :loading="loadingCategories" />
      </div>

      <div>
        <label class="block text-sm font-medium text-slate-600 mb-2">{{ $t('contract_block.debt_management_type') }}</label>
        <v-select multiple class="block w-full mr-1 custom-select" v-model="selectedDebtMngs" :options="debtManagements"
          :loading="loadingDebtMngsIds" />
      </div>

      <div>
        <label class="block text-sm font-medium text-slate-600 mb-2">{{ $t('common.payment_method') }}</label>
        <v-select multiple class="block w-full mr-1 custom-select" v-model="selectedPaymentTypes"
          :options="paymentTypes" :loading="loadingPaymentTypes" />
      </div>

      <div v-if="selectedPaymentTypes.some(paymentType => paymentType.token === 'DIRECT_DEBIT')">
        <label class="block text-sm font-medium text-slate-600 mb-2">{{ $t('common.return') }}</label>
        <v-select multiple class="block w-full mr-1 custom-select" v-model="selectedRejectionReasons"
          :options="rejectionReasons" :loading="loadingRejectionReasons" />
      </div>
    </div>
  </div>
</template>

<style scoped>
.grid {
  transition: all 0.3s ease;
}
</style>