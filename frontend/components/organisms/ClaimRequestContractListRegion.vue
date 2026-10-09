<script setup>
import { ref, computed, onMounted } from 'vue';
import { useI18n } from 'vue-i18n';
import { useToast } from 'vue-toastification';
import { useNuxtApp } from '#app';
import { formatMoney } from '~/utils/money';
import Date from '~/components/atoms/Date.vue';
import ColorBadge from '~/components/atoms/ColorBadge.vue';
import ContractRegion from './ContractRegion.vue';
import InvoiceRegion from './InvoiceRegion.vue';

const props = defineProps({
  request: Object,
  contracts: {
    type: Array,
    default: () => []
  }
});

const { t } = useI18n();
const toast = useToast();
const emit = defineEmits(['close', 'show-detail', 'change']);
const { $ClaimRequestApiService } = useNuxtApp();

const loading = ref(false);
const searchQuery = ref('');
const searchInput = ref(null);
const localContracts = ref([]);
const expandedContracts = ref(new Set());
const hideExcluded = ref(true);
const showVulnerable = ref(false);
const loadingContractId = ref(null);

const showRegion = ref(false);
const isSubRegionOpen = ref(false);
const showRegionDetailComponent = ref(null);
const regionDetailId = ref(null);

// Funcions per gestionar els contractes expandits
const toggleContract = (contractId) => {
  if (expandedContracts.value.has(contractId)) {
    expandedContracts.value.delete(contractId)
  } else {
    expandedContracts.value.add(contractId)
  }
}

const isContractExpanded = (contractId) => {
  return expandedContracts.value.has(contractId)
}

// Funció per mostrar detalls
const showDetail = (component, id) => {
  closeAllRegions();
  showRegionDetailComponent.value = component;
  regionDetailId.value = id;
  showRegion.value = true;
  emit('show-detail', true);
}

// Carregar els contractes associats a la reclamació
const loadContracts = async () => {
  loading.value = true;
  try {
    const response = await $ClaimRequestApiService.getContracts(props.request.id);
    localContracts.value = response;
  } catch (error) {
    toast.error(t('common.error_load'));
    console.error(error);
  } finally {
    loading.value = false;
  }
};

// Filtrar els contractes basats en la cerca i l'estat d'exclusió
const filteredContracts = computed(() => {
  let contracts = localContracts.value.results || [];
  
  // Filtrar per exclusió
  if (hideExcluded.value) {
    contracts = contracts.filter(contract => !contract.is_excluded);
  }

  if (showVulnerable.value) {
    contracts = contracts.filter(contract => contract.holder_vulnerability_level >= 0);
  } else {
    contracts = contracts.filter(contract => contract.holder_vulnerability_level == 0);
  }
  
  // Filtrar per cerca
  if (!searchQuery.value) return contracts;
  
  const query = searchQuery.value.toLowerCase();
  return contracts.filter(contract => {
    const fullName = `${contract.holder_name} ${contract.holder_surname}`.toLowerCase();
    const holderToken = contract.holder_token?.toLowerCase() || '';
    const contractToken = contract.token?.toLowerCase() || '';
    
    return fullName.includes(query) || 
           holderToken.includes(query) || 
           contractToken.includes(query);
  });
});

// Excloure un contracte i els seus pagaments
const excludeContract = async (contractId) => {
  if (!confirm(t('confirmation_text_block.confirm_exclude_contract'))) return;

  loadingContractId.value = contractId;
  try {
    await $ClaimRequestApiService.excludeContract({
      request_id: props.request.id,
      contract_id: contractId
    });
    toast.success(t('informative_block.info_exclude_correct'));
    // Recarreguem els contractes
    await loadContracts();
    // Notifiquem el canvi al pare sense mostrar loading
    emit('change', false);
  } catch (error) {
    toast.error(t('common.error'));
    console.error(error);
  } finally {
    loadingContractId.value = null;
  }
};


const closeAllRegions = () => {
  showRegion.value = false;
  showRegionDetailComponent.value = null
  regionDetailId.value = null
  emit('show-detail', false);
};

// Carregar els contractes al iniciar
onMounted(async () => {
  await loadContracts();
  searchInput.value?.focus();
});
</script>

<template>
  <div class="region__content pr-1">

    <div class="h-full flex flex-col transition-all duration-500 ease" :class="{ 'mr-[48vw]': showRegion }">
      <div class="flex justify-between items-center mb-4">
        <h3 class="text-lg font-semibold">{{ $t('contract_block.contract_list') }}</h3>
        <!-- <button @click="$emit('close')" class="text-gray-500 hover:text-gray-700">
          <Icon name="fa6-solid:xmark" class="text-xl" />
        </button> -->
      </div>
  
      <div class="mb-4 space-y-4">
        <div class="relative">
          <div class="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
            <Icon name="fa6-solid:magnifying-glass" class="text-gray-400" />
          </div>
          <input
            ref="searchInput"
            v-model="searchQuery"
            type="text"
            :placeholder="`${$t('dashboard.search')} ${$t('common.name')}, ${$t('common.identificator')}  ${$t('common.or')} ${$t('contract')}`"
            class="pl-10 pr-4 py-2 w-full border border-gray-300 rounded-md focus:ring-primary-500 focus:border-primary-500"
          />
        </div>
  
        <div class="flex items-center gap-5">
          <label class="inline-flex items-center">
            <input
              type="checkbox"
              v-model="hideExcluded"
              class="form-checkbox h-4 w-4 text-sky-600 rounded border-gray-300 focus:ring-sky-500"
            />
            <span class="ml-2 text-sm text-gray-700">{{ $t('common.show') }} {{ $t('contract_block.excluded_contracts') }}</span>
          </label>
          <label class="inline-flex items-center">
            <input
              type="checkbox"
              v-model="showVulnerable"
              class="form-checkbox h-4 w-4 text-sky-600 rounded border-gray-300 focus:ring-sky-500"
            />
            <span class="ml-2 text-sm text-gray-700">{{ $t('common.show') }} {{ $t('contract_block.vulnerables') }}</span>
          </label>
        </div>
      </div>
  
      <!-- afegim comptadors -->
      <div class="flex gap-3 items-center mb-4" v-if="!loading">
        <div>
          {{ $t('common.contracts') }}: {{ localContracts.count }}
        </div>
        <div>
          {{ $t('common.affected_multiple') }}: {{ localContracts.count - localContracts.count_excluded }}
        </div>
        <div>
          {{ $t('billing_block.excluded_multiple') }}: {{ localContracts.count_excluded }}
        </div>
      </div>
  
      <div class="flex-1 overflow-y-auto">
        <div v-if="loading && !localContracts.results?.length" class="flex justify-center items-center h-full">
          <Icon name="fa6-solid:spinner" class="animate-spin text-2xl" />
        </div>
        <div v-else>
          <div class="divide-y divide-gray-200 h-[70vh] overflow-y-auto">
            <div v-for="(contract, index) in filteredContracts" :key="contract.id" class="bg-white">
              <div class="px-4 py-3 flex justify-between items-center hover:bg-gray-50 relative"
                :class="{ 
                  'bg-white': index % 2 !== 0 && !contract.is_excluded, 
                  'bg-sky-50': index % 2 === 0 && !contract.is_excluded,
                  'bg-red-50': contract.is_excluded
                }">
                <div v-if="loadingContractId === contract.id" 
                  class="absolute inset-0 bg-white bg-opacity-75 flex items-center justify-center">
                  <Icon name="fa6-solid:spinner" class="animate-spin text-xl text-sky-600" />
                </div>
  
                <div class="flex items-center space-x-3">
                  <button @click="toggleContract(contract.id)" 
                    class="text-gray-500 hover:text-gray-700"
                    :disabled="loadingContractId === contract.id"
                    :title="`${$t('common.expand')}/${$t('common.collapse')} ${$t('contract')}`">
                    <Icon
                      :name="isContractExpanded(contract.id) ? 'fa6-solid:chevron-down' : 'fa6-solid:chevron-right'" />
                  </button>
                  <div>
                    <div class="grid grid-cols-[100px,100px,200px,50px,80px,80px,1fr] gap-2">
                      <button @click="showDetail('ContractRegion', contract.id)"
                        class="text-sky-500 hover:text-sky-700 underline text-left"
                        :title="`${$t('common.show')} ${$t('common.details')}`">
                        {{ contract.token }}
                      </button>
                      <span>{{ contract.holder_token }}</span>
                      <span>{{ contract.holder_name }} {{ contract.holder_surname }}</span>
                      <AtomsVulnerabilityCheck v-if="contract.holder_vulnerability_level" :vulnerability_level="contract.holder_vulnerability_level" :small="true" />
                      <span v-else></span>
                      <span>{{ formatMoney(contract.claim_payments.reduce((acc, curr) => curr.payment? acc + parseFloat(curr.payment.amount) : acc, 0)) }} €</span>
                      <ColorBadge :color="contract.status?.color" :value="contract.status?.name" />
                      <span></span>
                    </div>
                    <div class="text-sm text-gray-500 mt-1 grid grid-cols-[100px,1fr] gap-2">
                      <span class="mr-2">{{ $t('billing_block.payments') }}: {{ contract.claim_payments.length }}</span>
                      <span>
                        <abbr v-if="contract.use_type && contract.use_type.name" :title="$t('common.usage_type')" class="mr-2">{{ contract.use_type.name }}</abbr>
                        <abbr v-if="contract.client_type && contract.client_type.name" :title="$t('contract_block.client_type')" class="mr-2">{{ contract.client_type.name }}</abbr>
                        <abbr v-if="contract.category && contract.category.name" :title="$t('contract_block.category')" class="mr-2">{{ contract.category.name }}</abbr>
                        <abbr v-if="contract.debt_management && contract.debt_management.name" :title="$t('contract_block.debt_management')" class="mr-2">{{ contract.debt_management.name }}</abbr>
                      </span>
                    </div>
                  </div>
                </div>
                <button v-if="!contract.is_excluded" 
                  @click="excludeContract(contract.id)" 
                  class="flex items-center gap-2 text-red-600 hover:text-red-900 text-lg"
                  :disabled="loadingContractId === contract.id"
                  :title="`${$t('billing_block.exclude')} ${$t('contract')}`">
                  <Icon name="fa6-solid:ban" /> <span class="text-sm">{{ $t('billing_block.exclude') }} {{ $t('contract') }}</span>
                </button>
                <span v-else class="text-red-600 text-sm">{{ $t('billing_block.excluded') }}</span>
              </div>
              <div v-if="isContractExpanded(contract.id)" class="px-4 py-2 bg-gray-50">
                <table class="min-w-full divide-y divide-gray-200">
                  <thead>
                    <tr>
                      <th class="px-3 py-1 text-left text-xs font-medium text-gray-500 uppercase">{{ $t('invoice') }}</th>
                      <th class="px-3 py-1 text-left text-xs font-medium text-gray-500 uppercase">{{ $t('common.due_date') }}</th>
                      <th class="px-3 py-1 text-left text-xs font-medium text-gray-500 uppercase">{{ $t('common.amount') }}</th>
                      <th class="px-3 py-1 text-left text-xs font-medium text-gray-500 uppercase">{{ $t('common.status') }}</th>
                    </tr>
                  </thead>
                  <tbody class="bg-white divide-y divide-gray-200">
                    <tr v-for="claimPayment in contract.claim_payments" :key="claimPayment.id">
                      <td class="px-3 py-1 whitespace-nowrap">
                        <button @click="showDetail('InvoiceRegion', claimPayment.payment.invoice_id)"
                          class="text-sm text-sky-600 hover:text-sky-900 underline"
                          :title="`${$t('common.show')} ${$t('common.details')}`">
                          {{ claimPayment.payment ? claimPayment.payment.invoice_serie_final : '-' }}
                        </button>
                      </td>
                      <td class="px-3 py-1 whitespace-nowrap">
                        <Date v-if="claimPayment.payment" :date="claimPayment.payment.due_date" />
                        <span v-else>-</span>
                      </td>
                      <td class="px-3 py-1 whitespace-nowrap">
                        <span class="text-sm text-gray-900">{{ formatMoney(claimPayment.payment ? claimPayment.payment.amount : 0) }} €</span>
                      </td>
                      <td class="px-3 py-1 whitespace-nowrap">
                        <ColorBadge :color="claimPayment.payment ? claimPayment.payment.status.color : 'gray'" :value="claimPayment.payment ? claimPayment.payment.status.name : '-' " />
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
    <div v-if="showRegion == true" role="region" id="subregion"
      class="h-full border-l border-gray-100 transition-all duration-500 ease py-2 text-base bg-white fixed top-0 right-0 w-[48vw] z-50"
      :class="{ 'translate-x-0': showRegion, 'translate-x-full': !showRegion }">
      <div id="region_nav" class="mb-3 px-3">
        <button @click="closeAllRegions()" class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300">
          <Icon name="fa6-solid:angles-right" class="text-slate-500" />
        </button>
      </div>
      <div class="px-10">
        <!-- Subregions aqui -->
        <ContractRegion v-if="showRegionDetailComponent === 'ContractRegion'" :id="regionDetailId"
          :isSubRegion="true"/>
        <InvoiceRegion v-if="showRegionDetailComponent === 'InvoiceRegion'" :id="regionDetailId"
          :isSubRegion="true"/>
        <!-- /end Subregions aqui -->
      </div>
    </div>
  </div>
</template> 