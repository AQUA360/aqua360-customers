<script setup>
import { ref, computed, onMounted, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import { useToast } from 'vue-toastification';
import { useNuxtApp } from '#app';
import ColorBadge from '~/components/atoms/ColorBadge.vue';
import H1Region from '~/components/atoms/H1Region.vue';
import ContractRegion from './ContractRegion.vue';

const { t } = useI18n();
const props = defineProps({
  request: Object,
  selectedContracts: {
    type: Array,
    default: () => []
  },
  title: {
    type: String,
    default: 'common.contracts'
  },
  highlightColor: {
    type: String,
    default: 'bg-amber-100'
  },
  isVulnerabilityContext: {
    type: Boolean,
    default: false
  },
  allowSelectFiltering: {
    type: Boolean,
    default: false
  },
  allowDocumentSelection: {
    type: Boolean,
    default: true
  },
  currentStep: {
    type: Object,
    default: () => null
  }
});

const toast = useToast();
const emit = defineEmits(['update:selectedContracts', 'close', 'show-detail']);

const showRegion = ref(false);
const isSubRegionOpen = ref(false);
const showRegionDetailComponent = ref(null);
const regionDetailId = ref(null);
const { $ClaimRequestApiService, $ConfiglistApiService } = useNuxtApp();

const loading = ref(false);
const contracts = ref([]);
const localSelectedContracts = ref([...props.selectedContracts]);
const searchQuery = ref('');
const searchInput = ref(null);
const hideJuridic = ref(props.isVulnerabilityContext);
const hideVulnerability = ref(false);
const contractStatuses = ref([]);
const useTypes = ref([]);
const selectedStatus = ref('');
const hideTerminated = ref(false);

const selectedTypeTab = ref('manual')

const currentPage = ref(1);
const itemsPerPage = 25;
const maxVisiblePages = ref(5);

const minPendingPayments = ref(0);
const maxPendingPayments = ref(0);
const minPreviousVulnRequest = ref(null);
const maxPreviousVulnRequest = ref(null);
const minPendingImport = ref(0);
const maxPendingImport = ref(0);
const selectedUseTypes = ref([]);
const selectedContractStatuses = ref([]);


const loadConfigData = async (entity, targetArray, forSelection = false) => {
  try {
    const response = await $ConfiglistApiService.getAll(entity);
    if (forSelection) {
      targetArray.value = response.results.map(item => ({
        label: item.name,
        value: item.id
      }));
    } else {
      targetArray.value = response.results || [];
    }
  } catch (error) {
    console.error(`Error loading ${entity}:`, error);
  }
};

const loadData = async () => {
  await loadConfigData('contract/contract-use-type', useTypes, true);
  await loadConfigData('contract/contract-status', contractStatuses, true);
};


// Funció per comprovar si un contracte té un procés de baixa
const hasTerminationProcess = (contractToken) => {
  return props.request.contract_termination_requests?.some(
    termination => termination.contract?.token === contractToken
  );
};

const hasCutSupplyOrder = (contractToken) => {
  return props.request.cut_suply_orders?.some(
    order => order.contract_token === contractToken
  );
};

const hasRemoveMeterOrder = (contractToken) => {
  return props.request.remove_meter_orders?.some(
    order => order.contract_token === contractToken
  );
};

// Filtrar els contractes basats en la cerca, el filtre de persones jurídiques i l'estat
const filteredContracts = computed(() => {
  let filtered = contracts.value;

  //Filtrar per contractes no exclosos
  filtered = filtered.filter(contract => !contract.is_excluded);

  // Filtrar per persones jurídiques
  if (hideJuridic.value) {
    filtered = filtered.filter(contract => !contract.holder_is_juridic);
  }

  if (hideVulnerability.value) {
    filtered = filtered.filter(contract => contract?.holder_vulnerability_level == 0);
  }

  // Filtrar per estat
  if (selectedStatus.value) {
    filtered = filtered.filter(contract => contract.status?.id === selectedStatus.value);
  }

  // Filtrar per processos de baixa
  if (hideTerminated.value) {
    filtered = filtered.filter(contract => !hasTerminationProcess(contract.token));
  }

  // Filtrar per cerca
  if (!searchQuery.value) return filtered;

  const query = searchQuery.value.toLowerCase();
  return filtered.filter(contract => {
    const fullName = `${contract.holder_name} ${contract.holder_surname}`.toLowerCase();
    const holderToken = contract.holder_token?.toLowerCase() || '';
    const contractToken = contract.token?.toLowerCase() || '';

    return fullName.includes(query) ||
      holderToken.includes(query) ||
      contractToken.includes(query);
  });
});

const paginatedContracts = computed(() => {
  const start = (currentPage.value - 1) * itemsPerPage;
  const end = start + itemsPerPage;
  return filteredContracts.value.slice(start, end);
});

const totalPages = computed(() => {
  return Math.ceil(filteredContracts.value.length / itemsPerPage);
});

const visiblePages = computed(() => {
  const pages = [];
  const halfVisible = Math.floor(maxVisiblePages.value / 2);
  let startPage = Math.max(1, currentPage.value - halfVisible);
  let endPage = Math.min(totalPages.value, startPage + maxVisiblePages.value - 1);

  if (endPage - startPage < maxVisiblePages.value - 1) {
    startPage = Math.max(1, endPage - maxVisiblePages.value + 1);
  }

  for (let i = startPage; i <= endPage; i++) {
    pages.push(i);
  }

  return pages;
});

const goToPage = (page) => {
  if (page >= 1 && page <= totalPages.value) {
    currentPage.value = page;
  }
};

const nextPage = () => {
  if (currentPage.value < totalPages.value) {
    currentPage.value++;
  }
};

const prevPage = () => {
  if (currentPage.value > 1) {
    currentPage.value--;
  }
};

watch([hideJuridic, hideVulnerability, hideTerminated, selectedStatus, searchQuery], () => {
  currentPage.value = 1;
});

const documentSelectedContractIds = ref([]);
const lastSelectionMethod = ref('manual');

const documentSelectedContracts = computed(() => {
  return documentSelectedContractIds.value
    .map(id => contracts.value.find(contract => contract.id === id))
    .filter(Boolean);
});

const filterResultContractIds = ref([]);
const filterLoading = ref(false);

const filterSelectedContracts = computed(() => {
  return filterResultContractIds.value
    .map(id => contracts.value.find(contract => contract.id === id))
    .filter(Boolean);
});

const hasNumericRangeFilter = (min, max) => {
  return Number(min) > 0 || Number(max) > 0;
};

const isInNumericRange = (value, min, max) => {
  if (Number(min) > 0 && value < Number(min)) return false;
  if (Number(max) > 0 && value > Number(max)) return false;
  return true;
};

const isDateInRange = (dateStr, minDate, maxDate) => {
  if (!minDate && !maxDate) return true;
  if (!dateStr) return false;
  const date = new Date(dateStr);
  if (minDate && date < new Date(minDate)) return false;
  if (maxDate && date > new Date(`${maxDate}T23:59:59`)) return false;
  return true;
};

const getContractLastVulnerabilityRequest = (contract) => {
  return contract.last_vulnerability_request
    ?? contract.last_vulnerability_request_date
    ?? null;
};

const getContractPendingPaymentsCount = (contract) => {
  return contract.pending_payments_count
    ?? contract.claim_payments?.filter(claimPayment => claimPayment.payment && !claimPayment.payment.is_paid)?.length
    ?? contract.claim_payments?.length
    ?? 0;
};

const getContractPendingImport = (contract) => {
  if (contract.pending_import != null) return Number(contract.pending_import);
  if (contract.pending_amount != null) return Number(contract.pending_amount);

  return contract.claim_payments?.reduce((total, claimPayment) => {
    if (!claimPayment.payment || claimPayment.payment.is_paid) return total;
    return total + parseFloat(claimPayment.payment.amount || 0);
  }, 0) ?? 0;
};

const applyClientSideFilters = () => {
  const filtered = contracts.value
    .filter(contract => !contract.is_excluded)
    .filter(contract => {
      if (!isDateInRange(
        getContractLastVulnerabilityRequest(contract),
        minPreviousVulnRequest.value,
        maxPreviousVulnRequest.value
      )) {
        return false;
      }

      if (hasNumericRangeFilter(minPendingPayments.value, maxPendingPayments.value)
        && !isInNumericRange(
          getContractPendingPaymentsCount(contract),
          minPendingPayments.value,
          maxPendingPayments.value
        )) {
        return false;
      }

      if (hasNumericRangeFilter(minPendingImport.value, maxPendingImport.value)
        && !isInNumericRange(
          getContractPendingImport(contract),
          minPendingImport.value,
          maxPendingImport.value
        )) {
        return false;
      }

      return true;
    });

  filterResultContractIds.value = filtered.map(contract => contract.id);
  lastSelectionMethod.value = 'filter';
  updateSelectedContracts();
};

const clearOtherSelections = (active) => {
  if (active !== 'manual') localSelectedContracts.value = [];
  if (active !== 'filter') filterResultContractIds.value = [];
  if (active !== 'document') documentSelectedContractIds.value = [];
};

const getActiveSelection = () => {
  switch (lastSelectionMethod.value) {
    case 'filter':
      return [...filterResultContractIds.value];
    case 'document':
      return [...documentSelectedContractIds.value];
    default:
      return [...localSelectedContracts.value];
  }
};

const setActiveTab = (tab) => {
  selectedTypeTab.value = tab;
};

const applyFilters = async () => {
  filterLoading.value = true;
  try {
    clearOtherSelections('filter');
    const payload = {
      claim_request_id: props.request.id,
    };

    if (minPreviousVulnRequest.value) payload.min_previous_vuln_request = minPreviousVulnRequest.value;
    if (maxPreviousVulnRequest.value) payload.max_previous_vuln_request = maxPreviousVulnRequest.value;
    if (hasNumericRangeFilter(minPendingPayments.value, maxPendingPayments.value)) {
      payload.min_pending_payments = minPendingPayments.value;
      payload.max_pending_payments = maxPendingPayments.value;
    }
    if (hasNumericRangeFilter(minPendingImport.value, maxPendingImport.value)) {
      payload.min_pending_import = minPendingImport.value;
      payload.max_pending_import = maxPendingImport.value;
    }
    if (selectedUseTypes.value.length > 0) payload.use_types = selectedUseTypes.value.map(type => type.value);
    if (selectedContractStatuses.value.length > 0) payload.contract_statuses = selectedContractStatuses.value.map(status => status.value);

    const response = await $ClaimRequestApiService.getContractsClaimRequest(payload);
    if (response?.contract_ids) {
      filterResultContractIds.value = response.contract_ids;
      lastSelectionMethod.value = 'filter';
      updateSelectedContracts();
      return;
    }
  } catch (error) {
    console.error(error);
  } finally {
    filterLoading.value = false;
  }

  applyClientSideFilters();
};

const handleDocumentUpdate = async (event) => {
  try {
    clearOtherSelections('document');
    const response = await $ClaimRequestApiService.getContractsClaimRequest({
      file: event,
      claim_request_id: props.request.id
    });
    if (response) {
      documentSelectedContractIds.value = response.contract_ids;
      lastSelectionMethod.value = 'document';
      updateSelectedContracts();
    }
  } catch (error) {
    console.error(error);
  }
};

const showStepExpensesHighlight = computed(() => Boolean(props.currentStep) && !props.allowDocumentSelection);

const selectedContractsWithStepExpenses = computed(() => {
  if (!showStepExpensesHighlight.value) return [];
  const selectedIds = new Set(getActiveSelection());
  return contracts.value.filter(contract => selectedIds.has(contract.id) && contract?.has_claim_step_payments);
});

// Carregar els contractes associats a la reclamació
const loadContracts = async () => {
  loading.value = true;
  try {
    const response = await $ClaimRequestApiService.getContracts(props.request.id, null, props.currentStep?.id || null);
    if (response && Array.isArray(response.results)) {
      contracts.value = response.results;
    } else {
      contracts.value = [];
      console.warn('Unexpected response format:', response);
    }
    console.log("contracts.value");
    console.log(contracts.value);
  } catch (error) {
    toast.error(t('common.error_load'));
    console.error(error);
    contracts.value = [];
  } finally {
    loading.value = false;
  }
};

// Actualitzar els contractes seleccionats
const updateSelectedContracts = () => {
  emit('update:selectedContracts', getActiveSelection());
};

const showDetail = (component, id) => {
  showRegionDetailComponent.value = component;
  regionDetailId.value = id;
  showRegion.value = true;
};

const closeAllRegions = () => {
  showRegion.value = false;
  showRegionDetailComponent.value = null;
  regionDetailId.value = null;
  isSubRegionOpen.value = false;
  // emit('show-detail', false);
};

const handleSubRegionEvent = (event) => {
  isSubRegionOpen.value = event;
  emit('show-detail', event);
};

// Tancar la regió
const closeRegion = () => {
  closeAllRegions();
  // Assegurem que els contractes seleccionats s'actualitzen abans de tancar
  updateSelectedContracts();
  emit('close');
};

// Funció per alternar la selecció d'un contracte
const toggleContractSelection = (contractId) => {
  clearOtherSelections('manual');
  lastSelectionMethod.value = 'manual';
  const index = localSelectedContracts.value.indexOf(contractId);
  if (index === -1) {
    localSelectedContracts.value.push(contractId);
  } else {
    localSelectedContracts.value.splice(index, 1);
  }
  updateSelectedContracts();
};

// Funció per seleccionar tots els contractes
const toggleAllContracts = () => {
  clearOtherSelections('manual');
  lastSelectionMethod.value = 'manual';
  if (localSelectedContracts.value.length === filteredContracts.value.length) {
    // Si tots estan seleccionats, deseleccionar-los tots
    localSelectedContracts.value = [];
  } else {
    // Si no tots estan seleccionats, seleccionar-los tots
    localSelectedContracts.value = filteredContracts.value.map(contract => contract.id);
  }
  updateSelectedContracts();
};

const onManualSelectionChange = () => {
  clearOtherSelections('manual');
  lastSelectionMethod.value = 'manual';
  updateSelectedContracts();
};

// Afegim un watcher per mantenir sincronitzats els contractes seleccionats
watch(() => props.selectedContracts, (newValue) => {
  localSelectedContracts.value = newValue;
}, { deep: true });

// Carregar els contractes al iniciar
onMounted(async () => {
  await loadData();
  await loadContracts();
  searchInput.value?.focus();
});
</script>

<template>
  <div class="h-full">
    <div class="h-full flex flex-col gap-3 min-h-0 overflow-hidden">
      <!-- Header -->
      <div class="flex items-center justify-between gap-3">
        <H1Region>{{ $t(title) }}</H1Region>
        <div class="flex items-center gap-2 text-xs">
          <span v-if="selectedContracts.length > 0"
            class="inline-flex items-center gap-1.5 rounded-full border border-slate-300 bg-slate-100 px-2.5 py-1 font-medium text-slate-700">
            {{ $t('common.selection') }}
            <span class="font-semibold tabular-nums text-slate-800">{{ selectedContracts.length }}</span>
          </span>
          <span
            class="inline-flex items-center gap-1.5 rounded-full border border-slate-200 bg-slate-50 px-2.5 py-1 font-medium text-slate-500">
            {{ $t('common.total') }}
            <span class="font-semibold tabular-nums text-slate-800">{{ filteredContracts.length }}</span>
          </span>
        </div>
      </div>

      <AtomsTabs v-if="allowSelectFiltering" class="mb-3">
        <li class="me-2">
          <a href="#tab_manual" @click.prevent="setActiveTab('manual')"
            :class="{ 'text-sky-600 border-sky-600': selectedTypeTab === 'manual', 'hover:text-gray-600 hover:border-gray-300': selectedTypeTab !== 'manual' }"
            class="inline-flex items-center justify-center p-2 md:p-4 border-b-2 rounded-t-lg text-sm md:text-base">
            <Icon name="fa6-solid:arrow-pointer" class="display-inline mr-1 md:mr-2" />
            <span class="whitespace-nowrap">{{ $t("common.manual_selection") }}</span>
          </a>
        </li>
        <li class="me-2">
          <a href="#tab_filter" @click.prevent="setActiveTab('filter')"
            :class="{ 'text-sky-600 border-sky-600': selectedTypeTab === 'filter', 'hover:text-gray-600 hover:border-gray-300': selectedTypeTab !== 'filter' }"
            class="inline-flex items-center justify-center p-2 md:p-4 border-b-2 rounded-t-lg text-sm md:text-base">
            <Icon name="fa6-solid:filter" class="display-inline mr-1 md:mr-2" />
            <span class="whitespace-nowrap">{{ $t("common.filter") }}</span>
          </a>
        </li>
        <li v-if="allowDocumentSelection" class="me-2">
          <a href="#tab_document" @click.prevent="setActiveTab('document')"
            :class="{ 'text-sky-600 border-sky-600': selectedTypeTab === 'document', 'hover:text-gray-600 hover:border-gray-300': selectedTypeTab !== 'document' }"
            class="inline-flex items-center justify-center p-2 md:p-4 border-b-2 rounded-t-lg text-sm md:text-base">
            <Icon name="fa6-solid:file" class="display-inline mr-1 md:mr-2" />
            <span class="whitespace-nowrap">{{ $t("common.doc") }}</span>
          </a>
        </li>
      </AtomsTabs>

      <!-- Filter tab -->
      <section v-show="selectedTypeTab === 'filter'" class="flex flex-col min-h-0">
        <div>
          <div class="px-3 space-y-2">
            <div class="grid gap-3 grid-cols-3">
              <div v-if="allowDocumentSelection" class="rounded-md border border-slate-100 bg-slate-50/60 p-2.5">
                <span class="mb-2 block text-[11px] font-semibold uppercase tracking-wide text-slate-500">{{
                  t('claim_block.last_vulnerability_request') }}</span>
                <div class="grid grid-cols-2 gap-2">
                  <div>
                    <label class="mb-1 block text-[10px] font-medium uppercase tracking-wide text-slate-400">{{
                      t('common.from_long') }}</label>
                    <AtomsInputDate v-model="minPreviousVulnRequest" class="w-full" :label="''" />
                  </div>
                  <div>
                    <label class="mb-1 block text-[10px] font-medium uppercase tracking-wide text-slate-400">{{
                      t('common.to') }}</label>
                    <AtomsInputDate v-model="maxPreviousVulnRequest" class="w-full" :label="''" />
                  </div>
                </div>
              </div>
              
              <div class="rounded-md border border-slate-100 bg-slate-50/60 p-2.5">
                <span class="mb-2 block text-[11px] font-semibold uppercase tracking-wide text-slate-500">{{
                  t('billing_block.pending_payments') }}</span>
                <div class="grid grid-cols-2 gap-2">
                  <div>
                    <label class="mb-1 block text-[10px] font-medium uppercase tracking-wide text-slate-400">{{
                      t('common.from_long') }}</label>
                    <input type="number" v-model="minPendingPayments" class="w-full input" />
                  </div>
                  <div>
                    <label class="mb-1 block text-[10px] font-medium uppercase tracking-wide text-slate-400">{{
                      t('common.to') }}</label>
                    <input type="number" v-model="maxPendingPayments" class="w-full input" />
                  </div>
                </div>
              </div>

              <div class="rounded-md border border-slate-100 bg-slate-50/60 p-2.5">
                <span class="mb-2 block text-[11px] font-semibold uppercase tracking-wide text-slate-500">{{
                  t('billing_block.pending_import') }}</span>
                <div class="grid grid-cols-2 gap-2">
                  <div>
                    <label class="mb-1 block text-[10px] font-medium uppercase tracking-wide text-slate-400">{{
                      t('common.from_long') }}</label>
                    <input type="number" v-model="minPendingImport" class="w-full input" />
                  </div>
                  <div>
                    <label class="mb-1 block text-[10px] font-medium uppercase tracking-wide text-slate-400">{{
                      t('common.to') }}</label>
                    <input type="number" v-model="maxPendingImport" class="w-full input" />
                  </div>
                </div>
              </div>
              <div v-if="!allowDocumentSelection"></div>

              <div class="rounded-md border border-slate-100 bg-slate-50/60 p-2.5">
                <span class="mb-2 block text-[11px] font-semibold uppercase tracking-wide text-slate-500">{{
                  t('common.use_type') }}</span>
                <v-select multiple v-model="selectedUseTypes" class="block w-full custom-select" :options="useTypes" />
              </div>

              <div class="rounded-md border border-slate-100 bg-slate-50/60 p-2.5">
                <span class="mb-2 block text-[11px] font-semibold uppercase tracking-wide text-slate-500">{{
                  t('common.status') }} ({{ $t('contract') }})</span>
                <v-select multiple v-model="selectedContractStatuses" class="block w-full custom-select"
                  :options="contractStatuses" />
              </div>
            </div>

            <button class="button-default flex items-center gap-x-1.5" @click="applyFilters">
              <Icon name="fa6-solid:magnifying-glass" />
              {{ $t('common.search') }}
            </button>
          </div>
        </div>

        <hr class="my-2" />

        <div v-if="filterLoading" class="flex flex-col items-center justify-center py-8 text-xs text-slate-400">
          <Icon name="fa6-solid:spinner" class="animate-spin text-lg text-slate-400" />
        </div>
        <div v-else-if="filterSelectedContracts.length > 0" class="overflow-auto" :style="{
          minHeight: 'calc(100vh-360px)',
          maxHeight: 'calc(100vh-360px)',
        }">
          <table class="min-w-full text-sm">
            <thead class="sticky top-0 z-10 bg-slate-50/95 backdrop-blur-sm">
              <tr>
                <th
                  class="whitespace-nowrap px-3 py-2 text-left text-[10px] font-semibold uppercase tracking-wider text-slate-500">
                  {{ $t('contract') }}</th>
                <th
                  class="whitespace-nowrap px-3 py-2 text-left text-[10px] font-semibold uppercase tracking-wider text-slate-500">
                  {{ $t('contract_block.holder') }}</th>
                <th
                  class="whitespace-nowrap px-3 py-2 text-left text-[10px] font-semibold uppercase tracking-wider text-slate-500">
                  {{ $t('common.identificator') }}</th>
                <th
                  class="whitespace-nowrap px-3 py-2 text-left text-[10px] font-semibold uppercase tracking-wider text-slate-500">
                  {{ $t('billing_block.pending_import') }}</th>
                <th
                  class="whitespace-nowrap px-3 py-2 text-left text-[10px] font-semibold uppercase tracking-wider text-slate-500">
                  {{ $t('common.status') }}</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-slate-100">
              <tr v-for="contract in filterSelectedContracts" :key="contract.id">
                <td class="whitespace-nowrap px-3 py-1.5 align-middle">
                  <button @click="showDetail('ContractRegion', contract.id)"
                    class="text-sm font-medium leading-tight text-sky-500 underline hover:text-sky-700 text-left"
                    :title="`${$t('common.show')} ${$t('common.details')}`">
                    {{ contract.token }}
                  </button>
                </td>
                <td class="whitespace-nowrap px-3 py-1.5 align-middle">
                  <div class="text-sm font-medium leading-tight text-slate-800">{{ contract.holder_name }} {{
                    contract.holder_surname }}</div>
                  <div v-if="contract.is_juridic" class="text-[11px] text-slate-400">{{
                    $t('contract_block.short_person_juridic') }}</div>
                </td>
                <td class="whitespace-nowrap px-3 py-1.5 align-middle"><span
                    class="text-xs text-slate-500 [font-family:ui-monospace,monospace]">{{
                      contract.holder_token }}</span></td>
                <td class="whitespace-nowrap px-3 py-1.5 align-middle"><span
                    class="text-xs text-slate-500 [font-family:ui-monospace,monospace]">{{
                      formatMoneyWithCurrency(contract.pending_payments_amount) }}</span></td>
                <td class="whitespace-nowrap px-3 py-1.5 align-middle">
                  <ColorBadge v-if="contract.status" :color="contract.status?.color" :value="contract.status?.name" />
                  <span v-else class="text-xs text-slate-300">—</span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <div v-else class="flex flex-col items-center justify-center py-8 text-xs text-slate-400">
          <Icon name="fa6-solid:inbox" class="text-slate-300 text-xl mb-1" />
          <span>{{ $t('common.no_data') }}</span>
        </div>
      </section>

      <!-- Document tab -->
      <section v-if="allowDocumentSelection" v-show="selectedTypeTab === 'document'"
        class="flex flex-col gap-3 min-h-0">
        <div>
          <div
            class="flex items-start gap-2 rounded-md border border-slate-100 bg-slate-50 px-3 py-2 text-xs mb-2 leading-relaxed text-slate-600 w-fit">
            <Icon name="fa6-solid:circle-info" class="shrink-0 text-slate-400" />
            <span>{{ $t('informative_block.info_select_contracts_from_file') }}</span>
          </div>
          <div>
            <AtomsInputFile @update="handleDocumentUpdate" :name="'communicationDocumentFile'" :uploaded="null"
              :fullWidth="true" class="w-full max-w-md" />
          </div>
        </div>

        <div v-if="documentSelectedContracts.length > 0" class="overflow-auto" :style="{
          minHeight: 'calc(100vh-340px)',
          maxHeight: 'calc(100vh-340px)',
        }">
          <table class="min-w-full text-sm">
            <thead class="sticky top-0 z-10 bg-slate-50/95 backdrop-blur-sm">
              <tr>
                <th
                  class="whitespace-nowrap px-3 py-2 text-left text-[10px] font-semibold uppercase tracking-wider text-slate-500">
                  {{ $t('contract') }}</th>
                <th
                  class="whitespace-nowrap px-3 py-2 text-left text-[10px] font-semibold uppercase tracking-wider text-slate-500">
                  {{ $t('contract_block.holder') }}</th>
                <th
                  class="whitespace-nowrap px-3 py-2 text-left text-[10px] font-semibold uppercase tracking-wider text-slate-500">
                  {{ $t('common.identificator') }}</th>
                <th
                  class="whitespace-nowrap px-3 py-2 text-left text-[10px] font-semibold uppercase tracking-wider text-slate-500">
                  {{ $t('billing_block.pending_import') }}</th>
                <th
                  class="whitespace-nowrap px-3 py-2 text-left text-[10px] font-semibold uppercase tracking-wider text-slate-500">
                  {{ $t('common.status') }}</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-slate-100">
              <tr v-for="contract in documentSelectedContracts" :key="contract.id">
                <td class="whitespace-nowrap px-3 py-1.5 align-middle"><span
                    class="text-sm font-medium leading-tight text-slate-800">{{
                      contract.holder_token }}</span></td>
                <td class="whitespace-nowrap px-3 py-1.5 align-middle">
                  <div class="text-sm font-medium leading-tight text-slate-800">{{ contract.holder_name }} {{
                    contract.holder_surname }}</div>
                  <div v-if="contract.is_juridic" class="text-[11px] text-slate-400">{{
                    $t('contract_block.short_person_juridic') }}</div>
                </td>
                <td class="whitespace-nowrap px-3 py-1.5 align-middle">
                  <button @click="showDetail('ContractRegion', contract.id)"
                    class="text-xs text-sky-500 underline hover:text-sky-700 [font-family:ui-monospace,monospace] text-left"
                    :title="`${$t('common.show')} ${$t('common.details')}`">
                    {{ contract.token }}
                  </button>
                </td>
                <td class="whitespace-nowrap px-3 py-1.5 align-middle"><span
                    class="text-xs text-slate-500 [font-family:ui-monospace,monospace]">{{
                      formatMoneyWithCurrency(contract.pending_payments_amount) }}</span></td>
                <td class="whitespace-nowrap px-3 py-1.5 align-middle">
                  <ColorBadge v-if="contract.status" :color="contract.status?.color" :value="contract.status?.name" />
                  <span v-else class="text-xs text-slate-300">—</span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <div v-else class="flex flex-col items-center justify-center py-8 text-xs text-slate-400">
          <Icon name="fa6-solid:inbox" class="text-slate-300 text-xl mb-1" />
          <span>{{ $t('common.no_data') }}</span>
        </div>
      </section>

      <!-- Manual selection tab -->
      <section v-show="selectedTypeTab === 'manual'" class="flex flex-col gap-2.5 min-h-0 flex-1">
        <div>
          <div class="relative mb-2">
            <Icon name="fa6-solid:magnifying-glass"
              class="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-xs text-slate-400" />
            <input ref="searchInput" v-model="searchQuery" type="text"
              :placeholder="`${$t('dashboard.search')} ${$t('common.name')}, ${$t('common.identificator')} ${$t('common.or')} ${$t('contract')}`"
              class="w-full rounded-md border border-slate-200 bg-slate-50/50 py-1.5 pl-8 pr-3 text-sm text-slate-800 placeholder:text-slate-400 transition-colors focus:border-slate-300 focus:bg-white focus:outline-none focus:ring-2 focus:ring-slate-200" />
          </div>

          <div class="flex flex-wrap items-center justify-between gap-2">
            <div class="flex flex-wrap items-center gap-2">
              <label
                class="inline-flex cursor-pointer items-center gap-1.5 rounded-md border border-slate-200 bg-white px-2 py-1 text-xs text-slate-600 transition-colors hover:border-slate-300 hover:bg-slate-50">
                <input type="checkbox" v-model="hideJuridic"
                  class="h-3.5 w-3.5 rounded border-slate-300 text-slate-700 focus:ring-slate-400" />
                <span>{{ $t('common.hide') }} {{ $t('contract_block.person_juridic') }}</span>
              </label>

              <label
                class="inline-flex cursor-pointer items-center gap-1.5 rounded-md border border-slate-200 bg-white px-2 py-1 text-xs text-slate-600 transition-colors hover:border-slate-300 hover:bg-slate-50">
                <input type="checkbox" v-model="hideTerminated"
                  class="h-3.5 w-3.5 rounded border-slate-300 text-slate-700 focus:ring-slate-400" />
                <span>{{ $t('common.hide') }} {{ $t('contract_block.contracts_in_termination') }}</span>
              </label>

              <label
                class="inline-flex cursor-pointer items-center gap-1.5 rounded-md border border-slate-200 bg-white px-2 py-1 text-xs text-slate-600 transition-colors hover:border-slate-300 hover:bg-slate-50">
                <input type="checkbox" v-model="hideVulnerability"
                  class="h-3.5 w-3.5 rounded border-slate-300 text-slate-700 focus:ring-slate-400" />
                <span>{{ $t('common.hide') }} {{ $t('contract_block.vulnerability') }}</span>
              </label>

              <div class="inline-flex items-center gap-1.5">
                <label for="contract_status" class="text-xs text-slate-500">{{ $t('common.status') }}</label>
                <select id="contract_status" v-model="selectedStatus"
                  class="h-7 rounded-md border border-slate-200 bg-white px-2 text-xs text-slate-700 focus:border-slate-300 focus:outline-none focus:ring-2 focus:ring-slate-200">
                  <option value="">{{ $t('common.statuses') }}</option>
                  <option v-for="status in contractStatuses" :key="status.value" :value="status.value">
                    {{ status.label }}
                  </option>
                </select>
              </div>
            </div>

            <button @click="toggleAllContracts"
              class="button-default text-xs py-1.5 px-3 flex items-center gap-1.5 shrink-0">
              <Icon
                :name="localSelectedContracts.length === filteredContracts.length ? 'fa6-solid:check-double' : 'fa6-solid:square-check'"
                class="text-xs" />
              {{ localSelectedContracts.length === filteredContracts.length
                ? `${$t('common.deselect')} ${$t('common.all')}`
                : `${$t('common.select')} ${$t('common.all')}` }}
            </button>
          </div>
        </div>

        <div v-if="showStepExpensesHighlight" class="flex flex-col gap-2 grid grid-cols-2 items-center">
          <div
            class="flex items-start gap-2 rounded-md border border-sky-100 bg-sky-50 px-2.5 py-1.5 text-[11px] leading-relaxed text-sky-700 w-fit">
            <!-- <span class="mt-0.5 h-3 w-3 shrink-0 rounded-sm border border-sky-300 bg-sky-100"></span> -->
            <span>{{ $t('informative_block.info_step_expenses_highlight') }}</span>
          </div>

          <div v-if="selectedContractsWithStepExpenses.length > 0"
            class="flex items-start gap-2 rounded-md border border-amber-200 bg-amber-50 px-3 py-1.5 text-xs leading-relaxed text-amber-800">
            <Icon name="fa6-solid:triangle-exclamation" class="mt-0.5 shrink-0 text-amber-500" />
            <span>{{ $t('informative_block.info_selected_contracts_with_expenses', {
              count: selectedContractsWithStepExpenses.length
            }) }}</span>
          </div>
        </div>

        <div class="overflow-auto" :style="{
          minHeight: 'calc(100vh-240px)',
          maxHeight: 'calc(100vh-240px)',
        }">
          <AtomsAppLoading v-if="loading" />
          <div v-else-if="!contracts.length"
            class="flex flex-col items-center justify-center py-8 text-xs text-slate-400 h-full">
            <Icon name="fa6-solid:inbox" class="text-slate-300 text-xl mb-1" />
            <span>{{ $t('common.no_data') }}</span>
          </div>
          <div v-else-if="!filteredContracts.length"
            class="flex flex-col items-center justify-center py-8 text-xs text-slate-400 h-full">
            <Icon name="fa6-solid:magnifying-glass" class="text-slate-300 text-xl mb-1" />
            <span>{{ $t('common.no_data_found') }}</span>
          </div>
          <template v-else>
            <table class="min-w-full text-sm">
              <thead class="sticky top-0 z-10 bg-slate-50/95 backdrop-blur-sm">
                <tr>
                  <th
                    class="w-10 whitespace-nowrap px-3 py-2 text-left text-[10px] font-semibold uppercase tracking-wider text-slate-500">
                  </th>
                  <th
                    class="whitespace-nowrap px-3 py-2 text-left text-[10px] font-semibold uppercase tracking-wider text-slate-500">
                    {{ $t('contract') }}</th>
                  <th
                    class="whitespace-nowrap px-3 py-2 text-left text-[10px] font-semibold uppercase tracking-wider text-slate-500">
                    {{ $t('contract_block.holder') }}</th>
                  <th
                    class="whitespace-nowrap px-3 py-2 text-left text-[10px] font-semibold uppercase tracking-wider text-slate-500">
                    {{ $t('common.identificator') }}</th>
                  <th
                    class="whitespace-nowrap px-3 py-2 text-left text-[10px] font-semibold uppercase tracking-wider text-slate-500">
                    {{ $t('billing_block.pending_import') }}</th>
                  <th
                    class="whitespace-nowrap px-3 py-2 text-left text-[10px] font-semibold uppercase tracking-wider text-slate-500">
                    {{ $t('common.status') }}</th>
                  <th
                    class="text-center whitespace-nowrap px-3 py-2 text-[10px] font-semibold uppercase tracking-wider text-slate-500">
                    {{ $t('order_block.cut_order') }}</th>
                  <th
                    class="text-center whitespace-nowrap px-3 py-2 text-[10px] font-semibold uppercase tracking-wider text-slate-500">
                    {{ $t('order_block.remove_order') }}</th>
                  <th
                    class="whitespace-nowrap px-3 py-2 text-left text-[10px] font-semibold uppercase tracking-wider text-slate-500">
                    {{ $t('common.contract_termination_detail') }}</th>
                </tr>
              </thead>
              <tbody class="divide-y divide-slate-100">
                <tr v-for="contract in paginatedContracts" :key="contract.id"
                  class="cursor-pointer transition-colors duration-100" :class="{
                    'ring-1 ring-inset ring-slate-300/50': localSelectedContracts.includes(contract.id),
                    'hover:bg-slate-50/80': !localSelectedContracts.includes(contract.id) && !contract?.has_claim_step_payments,
                    'bg-sky-50': contract?.has_claim_step_payments && !localSelectedContracts.includes(contract.id),
                    'bg-sky-100': contract?.has_claim_step_payments && localSelectedContracts.includes(contract.id),
                    [highlightColor]: localSelectedContracts.includes(contract.id) && !contract?.has_claim_step_payments
                  }" @click="toggleContractSelection(contract.id)">
                  <td class="whitespace-nowrap px-3 py-1.5 align-middle text-center">
                    <input type="checkbox" v-model="localSelectedContracts" :value="contract.id"
                      class="h-3.5 w-3.5 rounded border-slate-300 text-slate-700 focus:ring-slate-400"
                      @change="onManualSelectionChange" @click.stop />
                  </td>
                  <td class="whitespace-nowrap px-3 py-1.5 align-middle">
                    <button @click.stop="showDetail('ContractRegion', contract.id)"
                      class="text-sm font-medium leading-tight text-sky-500 underline hover:text-sky-700 text-left flex items-center gap-x-2 justify-between"
                      :title="`${$t('common.show')} ${$t('common.details')}`">
                      {{ contract.token }}
                      <AtomsVulnerabilityCheck v-if="contract.holder_vulnerability_level > 0" :vulnerability_level="contract.holder_vulnerability_level"
                        :extra_small="true" class="w-1 h-1" />
                    </button>
                  </td>
                  <td class="whitespace-nowrap px-3 py-1.5 align-middle">
                    <div class="text-sm font-medium leading-tight text-slate-800">{{ contract.holder_name }} {{
                      contract.holder_surname }}</div>
                    <div v-if="contract.is_juridic" class="text-[11px] text-slate-400">{{
                      $t('contract_block.short_person_juridic') }}
                    </div>
                  </td>
                  <td class="whitespace-nowrap px-3 py-1.5 align-middle"><span
                      class="text-slate-500 [font-family:ui-monospace,monospace]">{{
                        contract.holder_token }}</span></td>
                  <td class="whitespace-nowrap px-3 py-1.5 align-middle"><span
                      class="text-slate-500 [font-family:ui-monospace,monospace]">
                      {{ formatMoneyWithCurrency(contract.pending_payments_amount) }}</span></td>
                  <td class="whitespace-nowrap px-3 py-1.5 align-middle">
                    <ColorBadge v-if="contract.status" :color="contract.status?.color" :value="contract.status?.name" />
                    <span v-else class="text-xs text-slate-300">—</span>
                  </td>
                  <td class="whitespace-nowrap px-3 py-1.5 align-middle text-center">
                    <Icon v-if="hasCutSupplyOrder(contract.token)" name="fa6-solid:check"
                      class="text-emerald-600 text-xs" />
                    <span v-else class="text-xs text-slate-300">—</span>
                  </td>
                  <td class="whitespace-nowrap px-3 py-1.5 align-middle text-center">
                    <Icon v-if="hasRemoveMeterOrder(contract.token)" name="fa6-solid:check"
                      class="text-emerald-600 text-xs" />
                    <span v-else class="text-xs text-slate-300">—</span>
                  </td>
                  <td class="whitespace-nowrap px-3 py-1.5 align-middle">
                    <ColorBadge v-if="hasTerminationProcess(contract.token)" color="red"
                      :value="$t('customer_service_block.in_process')" />
                    <span v-else class="text-xs text-slate-300">—</span>
                  </td>
                </tr>
              </tbody>
            </table>

            <div v-if="totalPages > 1"
              class="sticky bottom-0 flex flex-wrap items-center justify-center gap-1 border-t border-slate-100 bg-white/95 px-3 py-2 backdrop-blur-sm">
              <button @click="prevPage" :disabled="currentPage === 1"
                class="inline-flex h-7 min-w-[1.75rem] items-center justify-center rounded border border-slate-200 bg-white px-2 text-xs font-medium text-slate-600 transition-colors hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-40"
                :title="$t('common.previous')">
                <Icon name="fa6-solid:chevron-left" class="text-xs" />
              </button>

              <button v-if="visiblePages[0] > 1" @click="goToPage(1)"
                class="inline-flex h-7 min-w-[1.75rem] items-center justify-center rounded border border-slate-200 bg-white px-2 text-xs font-medium text-slate-600 transition-colors hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-40">1</button>
              <span v-if="visiblePages[0] > 2" class="px-1 text-xs text-slate-400">…</span>

              <button v-for="page in visiblePages" :key="page" @click="goToPage(page)"
                class="inline-flex h-7 min-w-[1.75rem] items-center justify-center rounded border px-2 text-xs font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-40"
                :class="page === currentPage
                  ? 'border-slate-700 bg-slate-800 text-white hover:bg-slate-700'
                  : 'border-slate-200 bg-white text-slate-600 hover:bg-slate-50'">
                {{ page }}
              </button>

              <span v-if="visiblePages[visiblePages.length - 1] < totalPages - 1"
                class="px-1 text-xs text-slate-400">…</span>
              <button v-if="visiblePages[visiblePages.length - 1] < totalPages" @click="goToPage(totalPages)"
                class="inline-flex h-7 min-w-[1.75rem] items-center justify-center rounded border border-slate-200 bg-white px-2 text-xs font-medium text-slate-600 transition-colors hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-40">
                {{ totalPages }}
              </button>

              <button @click="nextPage" :disabled="currentPage === totalPages"
                class="inline-flex h-7 min-w-[1.75rem] items-center justify-center rounded border border-slate-200 bg-white px-2 text-xs font-medium text-slate-600 transition-colors hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-40"
                :title="$t('common.next')">
                <Icon name="fa6-solid:chevron-right" class="text-xs" />
              </button>

              <span class="ml-2 text-[11px] tabular-nums text-slate-500">
                {{ $t('common.page') }} {{ currentPage }} {{ $t('common.of') }} {{ totalPages }}
              </span>
            </div>
          </template>
        </div>
      </section>
    </div>

    <div role="region" id="subregion"
      class="fixed h-full border-l border-gray-100 top-0 right-0 transition-all duration-500 ease py-2 text-base bg-white z-20 shadow-2xl"
      :class="{
        'translate-x-0': showRegion,
        'translate-x-[2000px]': !showRegion,
        'w-[95%]': isSubRegionOpen,
        'w-[55%]': !isSubRegionOpen,
      }">
      <div id="region_nav" class="mb-3 px-3">
        <button @click="closeAllRegions()" class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300">
          <Icon name="fa6-solid:angles-right" class="text-slate-500" />
        </button>
      </div>
      <div class="pl-10 h-full overflow-y-auto pb-24">
        <ContractRegion v-if="showRegionDetailComponent === 'ContractRegion'" :id="regionDetailId" :isSubRegion="true"
          :isSubRegionOpen="isSubRegionOpen" @show-subregion="handleSubRegionEvent"
          @close-subregion="closeAllRegions" />
      </div>
    </div>
  </div>
</template>