<script setup>
import { toRaw, ref, onMounted } from 'vue';
import { useI18n } from 'vue-i18n';
import MultiSelectList from '../molecules/MultiSelectList.vue';
import _ from 'lodash';
import debounce from 'lodash.debounce';
import StatusesNav from '~/components/atoms/StatusesNav.vue';
import AffectedClaimContracts from '../molecules/AffectedClaimContracts.vue';
import ClaimStepMiniDetail from '../molecules/ClaimStepMiniDetail.vue';
import ButtonSeleccio from '~/components/atoms/ButtonSeleccio.vue';
import ButtonOutline from '../atoms/ButtonOutline.vue';
import { useToast } from 'vue-toastification';
import ContractRegion from './ContractRegion.vue';
import InvoiceRegion from './InvoiceRegion.vue';
import AtomsInputDate from '~/components/atoms/InputDate.vue';
import AddContracts from '../molecules/AddContracts.vue';
import ContractDetail from '../molecules/ContractDetail.vue';
import Date from '~/components/atoms/Date.vue';
import ColorBadge from '~/components/atoms/ColorBadge.vue';
import { formatMoney } from '~/utils/money';
import SearchEntityInput from '../molecules/SearchEntityInput.vue';
import { checkPermission } from '~/middleware/permission';
import WizardStatusNav from '../molecules/WizardStatusNav.vue';

const route = useRoute();
const router = useRouter();

const props = defineProps({
  id: Number,
});

const toast = useToast()
const { t } = useI18n();
const { $ConfiglistApiService, $InvoiceApiService, $ContractApiService, $ConfigProjectApiService, $RouteApiService, $ProductApiService, $ClaimRequestApiService, $ExploitationApiService } = useNuxtApp();

// Estats generals
const currentStep = ref(0);
const loading = ref(true);
const saving = ref(false);
const showAlert = ref(true);

const wizardSteps = computed(() => [
  { id: 0, label: `${t('billing_block.step')} 1`, title: t('claim_block.request_payment_sel'), icon: 'fa6-solid:credit-card' },
  { id: 1, label: `${t('billing_block.step')} 2`, title: t('common.summary'), icon: 'fa6-solid:list-ul' },
  { id: 2, label: `${t('billing_block.step')} 3`, title: t('common.confirmation'), icon: 'fa6-solid:circle-check' }
])
const maxStep = computed(() => {
  if (contracts.value.length > 0 && contracts.value.length > contractsToIgnore.value.length) return 2
  if (contracts.value.length > 0 && contracts.value.length <= contractsToIgnore.value.length) return 1
  return 0
})

// Dades de selecció
const selectedClientTypes = ref([])
const selectedUseTypes = ref([])
const selectedZones = ref([])
const selectedDebtMngs = ref([])
const selectedOrigins = ref([])
const selectedContractStatuses = ref([])
const selectedPaymentTypes = ref([])
const selectedRejectionReasons = ref([])
const selectedExploitation = ref(null)
const selectedStep = ref(null)
const selectedAddedContracts = ref([])
const minPendingInvoices = ref(0)
const maxPendingInvoices = ref(0)
const totalExpiredInvoices = ref(0)

const showSelectedContractWarning = ref(false)

// Dades de filtre
const filter_date_start = ref(null)
const filter_date_end = ref(null)
const filter_due_date_start = ref(null)
const filter_due_date_end = ref(null)
const excludeReturnFeeInvoices = ref(false)
const filter_return_start = ref(null)
const filter_return_end = ref(null)
const due_date = ref('')

// Dades de contractes i factures
const contracts = ref([]);
const invoices = ref([]);
const sharedContractsInvoices = ref([]);
const contractsToIgnore = ref([])
const payments = ref([]);
const paymentsToIgnore = ref([])

const isContractExcluded = (contract) => contractsToIgnore.value.some(c => c.id === contract.id);
const isPaymentExcluded = (payment) => paymentsToIgnore.value.some(p => p.id === payment.id);

// Dades de configuració
const clientTypes = ref([])
const useTypes = ref([])
const zones = ref([])
const debtManagements = ref([])
const origins = ref([])
const contractStatuses = ref([])
const exploitations = ref([])
const paymentTypes = ref([])
const rejectionReasons = ref([])
const steps = ref([])
const stepsValue = ref([]) // per v-select
const selectedTemplate = ref(null)
const claimName = ref(null)

// Estats de càrrega
const loading_contracts = ref(true)
const loadingUseTypesIds = ref(false)
const loadingClientTypesIds = ref(false)
const loadingZonesIds = ref(false)
const loadingDebtMngsIds = ref(false)
const loadingOriginsIds = ref(false)
const loadingContractStatuses = ref(false)
const loadingPaymentTypes = ref(false)
const loadingRejectionReasons = ref(false)
const loadingStep = ref(null)
const loadingExploitation = ref(null)

// Regió lateral
const showRegion = ref(false);
const isSubRegionOpen = ref(false);
const showRegionDetailComponent = ref(false)
const regionDetailId = ref(false)
const claimRequestTemplates = ref([])
const claimRequestTemplatesValues = ref([]) // pel v-select
const objectPermissions = ref(null);

// Afegim la lògica per gestionar els contractes expandits
const expandedContracts = ref(new Set())

// Pagination for better performance
const currentPage = ref(1);
const itemsPerPage = ref(50);
const maxVisiblePages = ref(5);

const searchQuery = ref('');
const debouncedSearchQuery = ref('');
const showExcluded = ref(true);

const totalSelectedPayments = computed(() => {
  return contracts.value.reduce((count, contract) => {
    if (isContractExcluded(contract)) return count;
    const contractPayments = contract.payments || [];
    return count + contractPayments.filter(p => !isPaymentExcluded(p)).length;
  }, 0);
});

const countExcludedPayments = computed(() => {
  return contracts.value.reduce((acc, curr) => acc + (curr.payments_count || 0), 0) - totalSelectedPayments.value;
});

const updateDebouncedSearch = debounce((value) => {
  debouncedSearchQuery.value = value;
  currentPage.value = 1;
}, 300);

watch(searchQuery, (newValue) => {
  updateDebouncedSearch(newValue);
});

watch(showExcluded, () => {
  currentPage.value = 1;
});

const filteringTaskId = ref(null);
const savingTaskId = ref(null);

const allowSearch = computed(() => {
  if (filter_date_start.value && filter_date_end.value) return true;
  if (filter_due_date_start.value && filter_due_date_end.value) return true;
  if (filter_return_start.value && filter_return_end.value) return true;
  if (selectedAddedContracts.value.length > 0) return true;
  if (selectedExploitation.value) return true;
  if (selectedRejectionReasons.value.length > 0) return true;
  return false;
})

// Funcions de càrrega de dades
const loadData = async () => {
  loading.value = true;
  try {
    await getClientTypes()
    await getUseTypes()
    await getRouteZones()
    await getDebtManagements()
    await getOrigins()
    await getContractStatuses()
    await getExploitations()
    await getPaymentType()
    await getClaimRequestTemplates()
    // await getClaimData()
    await getRejectionReasons()
  } catch (error) {
    console.error('Error loading data:', error);
  } finally {
    loading.value = false;
  }
}

const getClaimRequestTemplates = async () => {
  try {
    const response = await $ClaimRequestApiService.getClaimRequestTemplates()
    claimRequestTemplates.value = response.results
    claimRequestTemplatesValues.value = response.results.map(item => ({
      label: item.name,
      code: item.id,
      ...item
    }))

    // Seleccionem el template per defecte
    const defaultTemplate = claimRequestTemplatesValues.value.find(template => template.is_default)
    if (defaultTemplate) {
      selectedTemplate.value = defaultTemplate
      // Actualitzem els passos amb els del template per defecte
      steps.value = defaultTemplate.steps || []
      stepsValue.value = steps.value.map(step => ({
        label: step.name,
        code: step.id,
        ...step
      }))
      // Seleccionem el primer pas per defecte
      if (stepsValue.value.length > 0) {
        selectedStep.value = stepsValue.value[0]
      }
    }
  } catch (error) {
    console.error('Error loading claim request templates:', error);
  }
}

const getClientTypes = async () => {
  loadingClientTypesIds.value = true
  clientTypes.value = [];
  try {
    let fetchData = await $ConfiglistApiService.getAll('contract/contract-client-type');
    fetchData.results.forEach(function (item) {
      clientTypes.value.push({
        label: item.name,
        code: item.id
      })
    })
  } catch (error) {
    console.error('Error loading client types:', error);
  } finally {
    loadingClientTypesIds.value = false
  }
}

const getRejectionReasons = async () => {
  loadingRejectionReasons.value = true
  rejectionReasons.value = [];
  try {
    let fetchData = await $ConfiglistApiService.getAll('billing/reject-motive');
    fetchData.results.forEach(function (item) {
      rejectionReasons.value.push({
        label: item.name,
        code: item.id
      })
    })
  } catch (error) {
    console.error('Error loading rejection motives:', error);
  } finally {
    loadingRejectionReasons.value = false
  }
}

const getUseTypes = async () => {
  loadingUseTypesIds.value = true
  useTypes.value = [];
  try {
    let fetchData = await $ConfiglistApiService.getAll('contract/contract-use-type');
    fetchData.results.forEach(function (item) {
      useTypes.value.push({
        label: item.name,
        code: item.id
      })
    })
  } catch (error) {
    console.error('Error loading use types:', error);
  } finally {
    loadingUseTypesIds.value = false
  }
}

const getRouteZones = async () => {
  loadingZonesIds.value = true
  zones.value = [];
  try {
    let exploitation_id = selectedExploitation.value ? selectedExploitation.value.code : null
    let fetchData = await $RouteApiService.getRouteZones(exploitation_id)
    fetchData.forEach(function (item) {
      zones.value.push({
        label: item.name,
        code: item.id
      })
    })
  } catch (error) {
    console.error('Error loading invoices:', error);
  } finally {
    loadingZonesIds.value = false
  }
};

const getDebtManagements = async () => {
  loadingDebtMngsIds.value = true
  debtManagements.value = [];
  try {
    /* let fetchData = await $ConfiglistApiService.getAll('contract/contract-debt-management');
    fetchData.results.forEach(item => {
      debtManagements.value.push({
        label: item.name,
        code: item.id
      })
    }) */

    debtManagements.value = [
      {
        label: t("contract_block.no_vulnerable"),
        code: 0,
      },
      {
        label: t("contract_block.short_in_social_risk"),
        code: 1,
      },
      {
        label: t("contract_block.vulnerable"),
        code: 2,
      },
    ]
  } catch (err) {
    console.error(err)
  } finally {
    loadingDebtMngsIds.value = false
  }
}

const getPaymentType = async () => {
  loadingPaymentTypes.value = true
  paymentTypes.value = [];
  try {
    let fetchData = await $ConfiglistApiService.getAll('contract/contract-payment-type');
    fetchData.results.forEach(item => {
      if (item.token != 'BALANCE') {
        paymentTypes.value.push({
          label: item.name,
          code: item.id,
          token: item.token
        })
      }
    })
  } catch (err) {
    console.error(err)
  } finally {
    loadingPaymentTypes.value = false
  }
}

const getExploitations = async () => {
  loadingExploitation.value = true
  exploitations.value = [];
  try {
    let fetchData = await $ExploitationApiService.getData();
    fetchData.results.forEach(item => {
      exploitations.value.push({
        label: item.name,
        code: item.id
      })
    })
    selectedExploitation.value = exploitations.value[0]
  } catch (err) {
    console.error(err)
  } finally {
    loadingExploitation.value = false
  }
}

const getOrigins = async () => {
  loadingOriginsIds.value = true
  origins.value = [];
  try {
    let fetchData = await $ProductApiService.getOrigins();
    fetchData.results.forEach(item => {
      origins.value.push({
        label: item.name,
        code: item.id
      })
    })
  } catch (err) {
    console.error(err)
  } finally {
    loadingOriginsIds.value = false
  }
}

const getContractStatuses = async () => {
  loadingContractStatuses.value = true
  contractStatuses.value = [];
  try {
    let fetchData = await $ConfiglistApiService.getAll('contract/contract-status');
    fetchData.results.forEach(item => {
      contractStatuses.value.push({
        label: item.name,
        code: item.id
      })
    })
  } catch (err) {
    console.error(err)
  } finally {
    loadingContractStatuses.value = false
  }
}

const getClaimData = async () => {
  loading_contracts.value = true
  try {
    let save_data = {
      selectedUseTypesIds: selectedUseTypes.value.map(el => el.code),
      selectedExploitationId: selectedExploitation.value.code,
      selectedClientTypesIds: selectedClientTypes.value.map(el => el.code),
      selectedZonesIds: selectedZones.value.map(el => el.code),
      selectedDebtMngsIds: selectedDebtMngs.value.map(el => el.code),
      selectedContractStatusesIds: selectedContractStatuses.value.map(el => el.code),
      selectedOriginsIds: selectedOrigins.value.map(el => el.code),
      filter_date_start: filter_date_start.value,
      filter_date_end: filter_date_end.value,
      filter_due_date_start: filter_due_date_start.value,
      filter_due_date_end: filter_due_date_end.value,
      filter_return_start: filter_return_start.value,
      filter_return_end: filter_return_end.value,
      rejection_motives: selectedRejectionReasons.value.map(el => el.code),
      selected_contracts_id: selectedAddedContracts.value.map(el => el.id),
      exclude_return_fee_invoices: excludeReturnFeeInvoices.value,
      name: claimName.value,
      max_pending_invoices: maxPendingInvoices.value,
      min_pending_invoices: minPendingInvoices.value,
    }

    let response = await $ClaimRequestApiService.getClaimData(save_data)
    filteringTaskId.value = response.task_id
  } catch (e) {
    console.error(e)
  } finally {
    loading_contracts.value = false
  }
}

// Funcions de gestió de contractes
const removeContract = (contract) => {
  // if (!confirm(t('confirmation_text_block.confirm_exclude_contract'))) return
  if (contractsToIgnore.value.find(c => c.id == contract.id)) {
    contractsToIgnore.value = contractsToIgnore.value.filter(c => c.id != contract.id)
  } else {
    contractsToIgnore.value.push(contract)
  }
}

// Funcions de gestió de pagaments
const removePayment = (payment) => {
  // if (!confirm(t('confirmation_text_block.confirm_exclude_payment'))) return
  if (paymentsToIgnore.value.find(p => p.id == payment.id)) {
    paymentsToIgnore.value = paymentsToIgnore.value.filter(p => p.id != payment.id)
  } else {
    paymentsToIgnore.value.push(payment)
  }
}

const onContractSelected = async (item) => {
  selectedClientTypes.value = []
  selectedUseTypes.value = []
  selectedContractStatuses.value = []
  selectedDebtMngs.value = []
  selectedOrigins.value = []
  selectedZones.value = []
  selectedRejectionReasons.value = []
  filter_date_start.value = null
  filter_date_end.value = null
  filter_due_date_start.value = null
  filter_due_date_end.value = null
  filter_return_start.value = null
  filter_return_end.value = null
  if (!selectedAddedContracts.value.includes(item)) {
    selectedAddedContracts.value.push(item);
  }
  toggleRegion(false)
};

const removeSelectedContract = async (item) => {
  selectedAddedContracts.value = selectedAddedContracts.value.filter(c => c.id !== item.id)
}

const checkSelectedContract = () => {
  let total = contracts.value.reduce((acc, curr) => acc + curr.total_amount, 0)
  if (contracts.value.length > 0 && selectedAddedContracts.value.length > 0 && total > 0 && (due_date.value != null && due_date.value != '')) nextStep()
  showSelectedContractWarning.value = selectedAddedContracts.value.length > 0 && total == 0
}


// Funcions de gestió de passos
const nextStep = () => {
  if (currentStep.value < 2) {
    currentStep.value++;
  }
}

const prevStep = () => {
  if (currentStep.value > 0) {
    currentStep.value--;
  }
}

// Funcions de validació i guardat
const isValid = () => {
  if (!selectedTemplate.value) {
    toast.warning(t('warning_block.warning_select_template'))
    return false
  }
  if (!selectedStep.value) {
    toast.warning(t('warning_block.warning_select_step'))
    return false
  }
  const selectedContracts = contracts.value.filter(c => !isContractExcluded(c))
  if (selectedContracts.length === 0) {
    toast.warning(t('warning_block.warning_select_contract'))
    return false
  }
  return true
}

const save = async () => {
  saving.value = true;
  try {
    if (isValid()) {
      const selectedContracts = contracts.value.filter(c => !isContractExcluded(c))
      const payment_ids = selectedContracts.flatMap(contract =>
        contract.payments.map(payment => payment.id)
      )

      const save_data = {
        id: props.id ? props.id : null,
        payment_ids: payment_ids,
        ignore_contract_ids: contractsToIgnore.value.map(c => c.id),
        ignore_payment_ids: paymentsToIgnore.value.map(p => p.id),
        step: selectedStep.value.code,
        template: selectedTemplate.value.code,
        start_at: filter_date_start.value,
        end_at: filter_date_end.value,
        due_date_start: filter_due_date_start.value,
        due_date_end: filter_due_date_end.value,
        return_start: filter_return_start.value,
        return_end: filter_return_end.value,
        contract_status_ids: selectedContractStatuses.value.map(el => el.code),
        client_types_ids: selectedClientTypes.value.map(el => el.code),
        use_types_ids: selectedUseTypes.value.map(el => el.code),
        zones_ids: selectedZones.value.map(el => el.code),
        debt_management_ids: selectedDebtMngs.value.map(el => el.code),
        exploitation: selectedExploitation.value.code,
        name: claimName.value,
        max_pending_invoices: maxPendingInvoices.value,
        min_pending_invoices: minPendingInvoices.value,
      }

      await $ClaimRequestApiService.save(save_data)
      return navigateTo('/billing/claim-managements/')
    }
  } catch (err) {
    console.error(err)
    toast.error(t('Error al guardar la gestió'))
  } finally {
    saving.value = false;
  }
}

// Funcions de gestió de la regió lateral
const showDetail = (component, id) => {
  showRegionDetailComponent.value = component;
  regionDetailId.value = id;
  toggleRegion(true)
}

const toggleRegion = (force) => {
  showRegion.value = force !== undefined ? force : !showRegion.value;
  if (!force) {
    showRegionDetailComponent.value = null
    regionDetailId.value = null
    isSubRegionOpen.value = false;
  }
}

const handleSubRegionEvent = (event) => {
  isSubRegionOpen.value = event;
}

const refreshData = async () => {
  if (filteringTaskId.value) {
    const response = await $ClaimRequestApiService.getClaimData(null, filteringTaskId.value)
    filteringTaskId.value = response.task_id
    contracts.value = response.contracts
    totalExpiredInvoices.value = response.total_expired_invoices
    currentPage.value = 1
    searchQuery.value = ''
    debouncedSearchQuery.value = ''
  }
}

const contractMatchesSearch = (contract, query) => {
  return contract.token?.toLowerCase().includes(query)
    || contract.holder?.toLowerCase().includes(query)
    || contract.holder_token?.toLowerCase().includes(query);
};

const paymentMatchesSearch = (payment, query) => {
  return payment.payment_bank_final?.toLowerCase().includes(query)
    || payment.invoice_serie_final?.toLowerCase().includes(query)
    || payment.invoice_token?.toLowerCase().includes(query);
};

const contractMatchesSearchQuery = (contract) => {
  const query = debouncedSearchQuery.value?.trim().toLowerCase();
  if (!query) return true;

  if (contractMatchesSearch(contract, query)) return true;

  return (contract.payments || []).some(payment => paymentMatchesSearch(payment, query));
};

const filteredContracts = computed(() => {
  let result = contracts.value || [];

  if (!showExcluded.value) {
    result = result.filter(contract => !isContractExcluded(contract));
  }

  if (debouncedSearchQuery.value?.trim()) {
    result = result.filter(contract => contractMatchesSearchQuery(contract));
  }

  return result;
});

const getContractPayments = (contract) => {
  let payments = contract.payments || [];
  const query = debouncedSearchQuery.value?.trim().toLowerCase();

  if (!showExcluded.value) {
    payments = payments.filter(payment => !isPaymentExcluded(payment));
  }

  if (query && !contractMatchesSearch(contract, query)) {
    payments = payments.filter(payment => paymentMatchesSearch(payment, query));
  }

  return payments;
};

const totalExcludedContracts = computed(() => contractsToIgnore.value.length);
const totalExcludedPayments = computed(() => paymentsToIgnore.value.length);

const activeContractsSummary = computed(() => {
  const active = contracts.value.filter(c => !isContractExcluded(c));
  return {
    contractsCount: active.length,
    paymentsCount: active.reduce((acc, curr) => acc + (curr.payments_count || 0), 0),
    totalAmount: active.reduce((acc, curr) => acc + parseFloat(curr.total_amount || 0), 0),
  };
});

const statsBoxPinging = ref(false);

const triggerStatsBoxPing = () => {
  statsBoxPinging.value = false;
  nextTick(() => {
    statsBoxPinging.value = true;
    setTimeout(() => {
      statsBoxPinging.value = false;
    }, 1200);
  });
};

watch(
  () => {
    const summary = activeContractsSummary.value;
    return `${summary.contractsCount}|${summary.paymentsCount}|${summary.totalAmount}`;
  },
  (_newVal, oldVal) => {
    if (oldVal === undefined) return;
    triggerStatsBoxPing();
  },
);

const paginatedContracts = computed(() => {
  const start = (currentPage.value - 1) * itemsPerPage.value;
  const end = start + itemsPerPage.value;
  return filteredContracts.value.slice(start, end);
});

const totalPages = computed(() => {
  return Math.ceil(filteredContracts.value.length / itemsPerPage.value) || 1;
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

// Afegim la lògica per gestionar els contractes expandits
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

// Funcions de gestió de templates i passos
const handleTemplateChange = (template) => {
  if (template) {
    steps.value = template.steps || []
    stepsValue.value = steps.value.map(step => ({
      label: step.name,
      code: step.id,
      ...step
    }))
    // Resetegem el pas seleccionat quan canviem de template
    selectedStep.value = null
  } else {
    steps.value = []
    stepsValue.value = []
    selectedStep.value = null
  }
}

onMounted(async () => {
  objectPermissions.value = await checkPermission($ClaimRequestApiService);
  if (!objectPermissions.value.can_change) {
    toast.error(t('common.no_permissions'));
    return navigateTo('/');
  }
  loadData()
  if (route?.query?.contract_id) {
    selectedAddedContracts.value = [{ id: parseInt(route.query.contract_id), token: route.query.contract_token }]
  }
});

// Watchers
watch(() => selectedExploitation.value, () => {
  getRouteZones()
}, { immediate: true });

</script>

<template>
  <div v-if="objectPermissions?.can_change" class="wrapper text-base max-w-full mb-20">


    <WizardStatusNav :steps="wizardSteps" :current-step="currentStep" :max-step="maxStep" disabled
      :show-description="false" />

    <div class="border border-gray-300 rounded py-4 px-4 bg-white">

      <!-- <div v-if="!loading && (contracts.length == 0 || totalExpiredInvoices == 0)"
        class="bg-orange-50 border-l-4 border-orange-400 px-4 py-2 mb-4 grid grid-cols-[auto,1fr] flex items-center gap-3">
        <Icon name="fa6-solid:triangle-exclamation" class="text-lg text-orange-400" />
        <div>
          <div v-if="contracts.length == 0" class="flex items-center text-orange-500 font-semibold">
            <p>{{ $t('informative_block.info_no_affected_contracts') }}</p>
          </div>
          <div v-if="totalExpiredInvoices == 0" class="flex items-center text-orange-500 font-semibold">
            <p>{{ $t('informative_block.info_no_expired_invoices') }}</p>
          </div>
        </div>
      </div> -->
      <div class="">
        <!-- Pas 1: Configuració -->
        <div v-show="currentStep === 0" class="space-y-4">

          <div class="grid grid-cols-3 gap-x-4">
            <div class="pr-2 border-r border-slate-200">
              <p class="block text-sm font-bold text-slate-600 mb-2">{{ $t('common.due_date') }}</p>
              <div class="grid grid-cols-2 gap-2">
                <AtomsInputDate v-model="filter_due_date_start" class="w-full" :label="$t('common.from')"
                  :disabled="!!filter_return_start || !filter_return_start == '' || !!filter_return_end || !filter_return_end == '' || !!filter_date_start || !filter_date_start == '' || !!filter_date_end || !filter_date_end == ''" />
                <AtomsInputDate v-model="filter_due_date_end" class="w-full" :label="$t('common.until')"
                  :disabled="!!filter_return_start || !filter_return_start == '' || !!filter_return_end || !filter_return_end == '' || !!filter_date_start || !filter_date_start == '' || !!filter_date_end || !filter_date_end == ''" />
              </div>
            </div>
            <div class="pr-2 border-r border-slate-200">
              <p class="block text-sm font-bold text-slate-600 mb-2">{{ $t('billing_block.return_sepa') }}</p>
              <div class="grid grid-cols-2 gap-2">
                <AtomsInputDate v-model="filter_return_start" class="w-full" :label="$t('common.from')"
                  :disabled="!!filter_due_date_start || !filter_due_date_start == '' || !!filter_due_date_end || !filter_due_date_end == '' || !!filter_date_start || !filter_date_start == '' || !!filter_date_end || !filter_date_end == ''" />
                <AtomsInputDate v-model="filter_return_end" class="w-full" :label="$t('common.until')"
                  :disabled="!!filter_due_date_start || !filter_due_date_start == '' || !!filter_due_date_end || !filter_due_date_end == '' || !!filter_date_start || !filter_date_start == '' || !!filter_date_end || !filter_date_end == ''" />
              </div>
            </div>
            <div class="pr-2">
              <p class="block text-sm font-bold text-slate-600 mb-2">{{ $t('billing') }}</p>
              <div class="grid grid-cols-2 gap-2">
                <AtomsInputDate v-model="filter_date_start" class="w-full" :label="$t('common.from')"
                  :disabled="!!filter_due_date_start || !filter_due_date_start == '' || !!filter_due_date_end || !filter_due_date_end == '' || !!filter_return_start || !filter_return_start == '' || !!filter_return_end || !filter_return_end == ''" />
                <AtomsInputDate v-model="filter_date_end" class="w-full" :label="$t('common.until')"
                  :disabled="!!filter_due_date_start || !filter_due_date_start == '' || !!filter_due_date_end || !filter_due_date_end == '' || !!filter_return_start || !filter_return_start == '' || !!filter_return_end || !filter_return_end == ''" />
              </div>
            </div>
            <div class="pr-2 border-r border-slate-200">
              <p class="block text-sm font-bold text-slate-600 mb-2">{{ $t('billing_block.pending_invoices') }}</p>
              <div class="grid grid-cols-2 gap-2">
                <div>
                  <label for="selected_max_consumption" class="block text-xs font-semibold text-slate-500 mb-1">
                    {{ $t('pricing_block.min') }}
                  </label>
                  <input id="selected_max_consumption" type="number" class="input w-full"
                  v-model.number="minPendingInvoices" placeholder="9999">
                </div>
                <div>
                  <label for="selected_min_consumption" class="block text-xs font-semibold text-slate-500 mb-1">
                    {{ $t('pricing_block.max') }}
                  </label>
                  <input id="selected_min_consumption" type="number" class="input w-full"
                    v-model.number="maxPendingInvoices" placeholder="0">
                </div>
              </div>
            </div>
          </div>

          <hr />

          <div class="grid grid-cols-2 gap-4">
            <SearchEntityInput :service="$ContractApiService" @select="onContractSelected"
              :title="`${$t('dashboard.search')} ${$t('contract')}`" :result_value="'holder_full_name'"
              class="mt-auto" />
            <div v-if="selectedAddedContracts?.length > 0" class="">
              <label class="block text-sm font-medium text-slate-600 mb-2">
                {{ $t('contract_block.selected_contracts') }}</label>
              <div class="flex flex-wrap gap-2 ">
                <span v-for="contract in selectedAddedContracts" :key="contract.id"
                  class="group relative bg-slate-100 text-slate-800 px-3 py-1 rounded-full text-sm border border-slate-300 flex items-center gap-2">
                  <abbr v-if="contract.expired_invoices === 0" :title="t('informative_block.info_no_expired_invoices')"
                    class="flex items-center">
                    <Icon name="fa6-solid:triangle-exclamation" class="text-orange-400 text-sm my-auto" />
                  </abbr>
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

            <span v-else>
            </span>
            <div>
              <label class="block text-sm font-medium text-slate-600 mb-2">{{ $t('exploitation') }}</label>
              <v-select class="block w-full mr-1 custom-select" v-model="selectedExploitation" :options="exploitations"
                :disabled="exploitations?.length == 1" :loading="loadingExploitation" />
            </div>

            <div>
              <label class="block text-sm font-medium text-slate-600 mb-2">{{ $t('service_block.zone') }}</label>
              <v-select multiple class="block w-full mr-1 custom-select" v-model="selectedZones" :options="zones"
                :loading="loadingZonesIds" />
            </div>

            <div>
              <label class="block text-sm font-medium text-slate-600 mb-2">{{ $t('billing_block.contract_status')
              }}</label>
              <v-select multiple class="block w-full mr-1 custom-select" v-model="selectedContractStatuses"
                :options="contractStatuses" :loading="loadingContractStatuses" />
            </div>

            <div>
              <label class="block text-sm font-medium text-slate-600 mb-2">{{ $t('contract_block.client_type')
              }}</label>
              <v-select multiple class="block w-full mr-1 custom-select" v-model="selectedClientTypes"
                :options="clientTypes" :loading="loadingClientTypesIds" />
            </div>

            <div>
              <label class="block text-sm font-medium text-slate-600 mb-2">{{ $t('common.usage_type') }}</label>
              <v-select multiple class="block w-full mr-1 custom-select" v-model="selectedUseTypes" :options="useTypes"
                :loading="loadingUseTypesIds" />
            </div>

            <div>
              <label class="block text-sm font-medium text-slate-600 mb-2">{{ $t('contract_block.debt_management_type')
              }}</label>
              <v-select multiple class="block w-full mr-1 custom-select" v-model="selectedDebtMngs"
                :options="debtManagements" :loading="loadingDebtMngsIds" />
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

          <label class="flex items-center gap-2 text-sm text-slate-600">
            <input type="checkbox" v-model="excludeReturnFeeInvoices" />
            <span>{{ $t('billing_block.exclude_return_fee_invoices') }}</span>
          </label>

          <div v-if="showAlert"
            class="bg-sky-100 text-sky-700 py-3 px-5 rounded-lg mb-3 flex items-center justify-between">
            <span>{{ $t('informative_block.info_show_all_data_no_filter') }}</span>
            <button @click="showAlert = false" class="text-sky-700 hover:text-sky-900 text-xl"
              :title="$t('common.hide')">&times;</button>
          </div>

        </div>

        <!-- Pas 2: Selecció de pagaments -->
        <div v-show="currentStep === 1" class="space-y-4">
          <div v-if="!loading_contracts" class="mt-2">
            <!-- Caixa de resum -->
            <!-- <div class="bg-white border border-gray-200 rounded-lg p-4 mb-4">
              <div class="grid grid-cols-3 gap-4">
                <div class="text-center">
                  <div class="text-2xl font-bold text-sky-600">
                    {{contracts.filter(c => !isContractExcluded(c)).length}}
                  </div>
                  <div class="text-sm text-gray-500">
                    {{ $t('common.contracts') }}
                  </div>
                </div>
                <div class="text-center">
                  <div class="text-2xl font-bold text-sky-600">
                    {{contracts.filter(c => !isContractExcluded(c)).reduce((acc, curr) => acc +
                      curr.payments_count, 0)}}
                  </div>
                  <div class="text-sm text-gray-500">
                    {{ $t('billing_block.payments') }}
                  </div>
                </div>
                <div class="text-center">
                  <div class="text-2xl font-bold text-sky-600">
                    {{formatMoney(contracts.filter(c => !isContractExcluded(c)).reduce((acc, curr) => acc +
                      parseFloat(curr.total_amount), 0))}} €
                  </div>
                  <div class="text-sm text-gray-500">
                    {{ $t('common.amount') }}
                  </div>
                </div>
              </div>
            </div> -->

            <div class="mb-4 space-y-4">
              <div class="relative">
                <div class="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                  <Icon name="fa6-solid:magnifying-glass" class="text-gray-400" />
                </div>
                <input v-model="searchQuery" type="text"
                  :placeholder="`${$t('dashboard.search')} ${$t('contract')}, ${$t('invoice')}, ${$t('common.iban')}`"
                  class="pl-10 pr-4 py-2 w-full border border-gray-300 rounded-md focus:ring-primary-500 focus:border-primary-500" />
              </div>

              <div class="flex items-center gap-5">
                <label class="inline-flex items-center">
                  <input type="checkbox" v-model="showExcluded"
                    class="form-checkbox h-4 w-4 text-sky-600 rounded border-gray-300 focus:ring-sky-500" />
                  <span class="ml-2 text-sm text-gray-700">{{ $t('common.show') }} {{
                    $t('billing_block.excluded_multiple') }}</span>
                </label>
              </div>
            </div>

            <div class="flex justify-between items-center mb-2">
              <span class="text-sm text-gray-500">
                {{ $t('common.total') }}: {{ filteredContracts.length }}
                <span v-if="totalExcludedContracts > 0 || totalExcludedPayments > 0">
                  ({{ totalExcludedContracts }} {{ $t('billing_block.excluded_multiple') }}
                  <span v-if="countExcludedPayments > 0">, {{ countExcludedPayments }} {{ $t('billing_block.payments')
                  }}</span>)
                </span>
              </span>
            </div>

            <div class="divide-y divide-gray-200 h-[55vh] overflow-auto">
              <div v-if="filteredContracts.length === 0" class="footering text-slate-500 p-2">
                {{ $t('common.no_data_found') }}
              </div>
              <div v-for="(contract, index) in paginatedContracts" :key="contract.id" class="bg-white">
                <div class="px-4 py-3 flex justify-between items-center hover:bg-gray-50" :class="{
                  'bg-red-50': isContractExcluded(contract),
                  'bg-white': index % 2 !== 0 && !isContractExcluded(contract),
                  'bg-sky-50': index % 2 === 0 && !isContractExcluded(contract),
                }">
                  <div class="flex items-center space-x-3">
                    <button @click="toggleContract(contract.id)" class="text-gray-500 hover:text-gray-700"
                      :title="`${$t('common.expand')}/${$t('common.collapse')} ${$t('contract')}`">
                      <Icon
                        :name="isContractExpanded(contract.id) ? 'fa6-solid:chevron-down' : 'fa6-solid:chevron-right'" />
                    </button>
                    <div>
                      <div class="grid grid-cols-[100px,80px,300px,80px,80px,1fr] gap-2">
                        <button @click="showDetail('ContractRegion', contract.id)"
                          class="text-sky-500 hover:text-sky-700 underline text-left"
                          :title="`${$t('common.show')} ${$t('common.details')}`">
                          {{ contract.token }}
                          <AtomsVulnerabilityCheck
                            v-if="contract.vulnerability_level && contract.vulnerability_level > 0"
                            :vulnerability_level="contract.vulnerability_level" :small="true" />
                        </button>
                        <span>{{ contract.holder_token }}</span>
                        <span>{{ contract.holder }}</span>
                        <span>{{ formatMoney(contract.total_amount) }} €</span>
                        <ColorBadge :color="contract.status?.color" :value="contract.status?.name" />
                        <span></span>
                      </div>
                      <div class="text-sm text-gray-500 mt-1 grid grid-cols-[100px,1fr] gap-2">
                        <span class="mr-2">{{ $t('billing_block.payments') }}: {{ contract.payments_count }}</span>
                        <span>
                          <abbr :title="$t('common.usage_type')" class="mr-2">{{ contract.use_type }}</abbr>
                          <span class="mr-2">|</span>
                          <abbr :title="$t('contract_block.client_type')" class="mr-2">{{ contract.client_type }}</abbr>
                          <span class="mr-2" v-if="contract.category">|</span>
                          <abbr :title="$t('contract_block.category')" class="mr-2">{{ contract.category }}</abbr>
                          <span class="mr-2" v-if="contract.debt_management">|</span>
                          <abbr :title="$t('contract_block.debt_management_type')" class="mr-2">{{
                            contract.debt_management }}</abbr>
                        </span>
                      </div>
                    </div>
                  </div>
                  <button @click="removeContract(contract)" class="text-red-600 hover:text-red-900 text-lg"
                    :title="`${$t('billing_block.exclude')} ${$t('contract')}`">
                    <Icon :name="isContractExcluded(contract) ? 'fa6-regular:circle-down' : 'fa6-solid:ban'" />
                  </button>
                </div>
                <div v-if="isContractExpanded(contract.id)" class="px-4 py-2 bg-gray-50">
                  <table class="min-w-full divide-y divide-gray-200">
                    <thead>
                      <tr>
                        <th class="px-3 py-1 text-left text-xs font-medium text-gray-500 uppercase">
                          {{ $t('invoice') }}
                        </th>
                        <th class="px-3 py-1 text-left text-xs font-medium text-gray-500 uppercase">
                          {{ $t('common.due_date') }}</th>
                        <th class="px-3 py-1 text-left text-xs font-medium text-gray-500 uppercase">
                          {{ $t('common.amount') }}
                        </th>
                        <th class="px-3 py-1 text-left text-xs font-medium text-gray-500 uppercase">
                          {{ $t('common.payment_method') }}</th>
                        <th class="px-3 py-1 text-left text-xs font-medium text-gray-500 uppercase">
                          {{ $t('common.status') }}
                        </th>
                        <th class="px-3 py-1 text-left text-xs font-medium text-gray-500 uppercase">
                          {{ $t('common.actions') }}
                        </th>
                      </tr>
                    </thead>
                    <tbody class="bg-white divide-y divide-gray-200">
                      <tr v-if="getContractPayments(contract).length === 0">
                        <td colspan="6" class="px-3 py-2 text-sm text-slate-500">
                          {{ $t('common.no_data_found') }}
                        </td>
                      </tr>
                      <tr v-for="payment in getContractPayments(contract)" :key="payment.id" :class="{
                        'bg-red-50': isPaymentExcluded(payment) || isContractExcluded(contract),
                        'bg-white': index % 2 !== 0 && !isPaymentExcluded(payment) && !isContractExcluded(contract),
                        'bg-sky-50': index % 2 === 0 && !isPaymentExcluded(payment) && !isContractExcluded(contract),
                      }">
                        <td class="px-3 py-1 whitespace-nowrap">
                          <button @click="showDetail('InvoiceRegion', payment.invoice_id)"
                            class="text-sm text-sky-600 hover:text-sky-900 underline"
                            :title="`${$t('common.show')} ${$t('common.details')}`">
                            {{ payment.invoice_serie_final || payment.invoice_token }}
                          </button>
                        </td>
                        <td class="px-3 py-1 whitespace-nowrap">
                          <Date :date="payment.due_date" />
                        </td>
                        <td class="px-3 py-1 whitespace-nowrap">
                          <span class="text-sm text-gray-900">{{ formatMoney(payment.amount) }} €</span>
                        </td>
                        <td class="px-3 py-1 whitespace-nowrap">
                          <span class="text-sm text-gray-900">{{ payment.payment_type }}</span>
                        </td>
                        <td class="px-3 py-1 whitespace-nowrap">
                          <ColorBadge :color="payment.status?.color" :value="payment.status?.name" />
                        </td>
                        <td class="px-3 py-1 whitespace-nowrap">
                          <button @click="removePayment(payment)" class="text-red-600 hover:text-red-900 text-lg"
                            :title="`${$t('common.delete')} ${$t('billing_block.payment')}`">
                            <Icon :name="isPaymentExcluded(payment) ? 'fa6-regular:circle-down' : 'fa6-solid:ban'" />
                          </button>
                        </td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </div>
            </div>

            <!-- Pagination Controls -->
            <div v-if="totalPages > 1" class="flex justify-center items-center gap-2 mt-4 pb-2">
              <button @click="prevPage" :disabled="currentPage === 1"
                class="px-3 py-1 border border-gray-300 rounded hover:bg-gray-100 disabled:opacity-50 disabled:cursor-not-allowed"
                :title="$t('common.previous')">
                <Icon name="fa6-solid:chevron-left" />
              </button>

              <button v-if="visiblePages[0] > 1" @click="goToPage(1)"
                class="px-3 py-1 border border-gray-300 rounded hover:bg-gray-100">
                1
              </button>

              <span v-if="visiblePages[0] > 2" class="px-2">...</span>

              <button v-for="page in visiblePages" :key="page" @click="goToPage(page)" :class="{
                'bg-sky-500 text-white border-sky-500': page === currentPage,
                'border-gray-300 hover:bg-gray-100': page !== currentPage
              }" class="px-3 py-1 border rounded">
                {{ page }}
              </button>

              <span v-if="visiblePages[visiblePages.length - 1] < totalPages - 1" class="px-2">...</span>

              <button v-if="visiblePages[visiblePages.length - 1] < totalPages" @click="goToPage(totalPages)"
                class="px-3 py-1 border border-gray-300 rounded hover:bg-gray-100">
                {{ totalPages }}
              </button>

              <button @click="nextPage" :disabled="currentPage === totalPages"
                class="px-3 py-1 border border-gray-300 rounded hover:bg-gray-100 disabled:opacity-50 disabled:cursor-not-allowed"
                :title="$t('common.next')">
                <Icon name="fa6-solid:chevron-right" />
              </button>

              <span class="ml-4 text-sm text-gray-600">
                {{ $t('common.page') }} {{ currentPage }} {{ $t('common.of') }} {{ totalPages }}
              </span>
            </div>
          </div>
          <div v-else class="mx-auto text-center p-5">
            <Icon name="fa:spinner" class="text-slate-600 max-auto items-center animate-spin" />
            <span class="ml-2">{{ $t('common.loading') }}</span>
          </div>
        </div>

        <!-- Pas 3: Confirmació -->
        <div v-show="currentStep === 2" class="space-y-4">


          <div class="grid grid-cols-2 gap-4">
            <div>
              <label class="text-slate-500">{{ $t('common.name') }}</label>
              <input type="text" v-model="claimName" class="input" />
            </div>
            <div></div>
            <div>
              <label class="text-slate-500">{{ $t('common.template') }}</label>
              <v-select class="block w-full mr-1 custom-select" v-model="selectedTemplate"
                :options="claimRequestTemplatesValues" :loading="loading" @update:modelValue="handleTemplateChange" />
            </div>
            <div>
              <label class="text-slate-500">{{ $t('billing_block.mng_current_step') }}</label>
              <v-select class="block w-full mr-1 custom-select" v-model="selectedStep" :options="stepsValue"
                :disabled="!selectedTemplate" />
            </div>
          </div>

          <!-- mostrem els steps -->
          <div v-for="step in steps" :key="step.id">
            <ClaimStepMiniDetail :item="step" :current="selectedStep?.id === step.id" />
          </div>
        </div>
      </div>
    </div>
    <!-- Barra de navegació fixada al footer -->
    <div class="fixed right-0 bottom-0 z-[9999] border-t border-gray-200 py-4 px-4 shadow-lg bg-[#FAE2DA]"
      style="width: calc(100% - 250px)" :class="{ 'animate-stats-box-ping': statsBoxPinging }">
      <div class="mx-auto flex justify-between items-center px-4">
        <div class="grid auto-cols-max grid-flow-col items-center gap-x-10">
          <div class="flex flex-col">
            <div class="text-lg font-bold text-sky-700">
              {{ activeContractsSummary.contractsCount }} ({{ contracts.length }})
            </div>
            <div class="text-sm font-semibold text-slate-700">
              {{ $t('common.contracts') }}
            </div>
          </div>
          <div class="flex flex-col">
            <div class="text-lg font-bold text-sky-700">
              {{ totalSelectedPayments }} ({{contracts.reduce((acc, curr) => acc + (curr.payments_count || 0), 0)}})
            </div>
            <div class="text-sm font-semibold text-slate-700">
              {{ $t('billing_block.payments') }}
            </div>
          </div>
          <div class="flex flex-col">
            <div class="text-lg font-bold text-sky-700">
              {{ formatMoney(activeContractsSummary.totalAmount) }} €
            </div>
            <div class="text-sm font-semibold text-slate-700">
              {{ $t('common.amount') }}
            </div>
          </div>
        </div>
        <div class="flex items-center gap-4">
          <button v-if="currentStep > 0" @click="prevStep" class="button-secondary flex items-center gap-2"
            :title="$t('billing_block.go_prev_step')">
            <Icon name="fa6-solid:chevron-left" /> {{ $t('common.previous') }}
          </button>
          <div class="flex space-x-4">
            <button v-if="currentStep == 0 && !filteringTaskId" @click="getClaimData"
              class="button-default flex items-center gap-2" :title="$t('common.search')" :disabled="!allowSearch">
              {{ $t('common.search') }}
              <Icon name="fa6-solid:magnifying-glass" />
            </button>
            <AtomsProcessColorBadge class="w-fit flex items-center gap-x-2" v-if="currentStep == 0 && filteringTaskId"
              @refresh="refreshData" :value="t('common.loading')" :color="'blue'" :taskId="filteringTaskId" />
            <button v-if="currentStep < 2" @click="nextStep" class="button-primary flex items-center gap-2"
              :title="$t('billing_block.go_next_step')"
              :disabled="contracts.length == 0 || showSelectedContractWarning">
              {{ $t('common.next') }}
              <Icon name="fa6-solid:chevron-right" />
            </button>
            <button v-if="currentStep === 2" @click="save" :disabled="saving"
              class="button-primary flex items-center gap-2" :title="$t('common.save')">
              <Icon name="fa6-solid:floppy-disk" /> {{ $t('common.save') }}
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- Regió lateral -->
    <div role="region" id="right_page"
      class="fixed h-full border-l border-gray-100 top-0 right-0 transition-all duration-500 ease py-2 text-base bg-white z-10"
      :class="{
        'translate-x-0': showRegion,
        'translate-x-[2000px]': !showRegion,
        'w-[95%]': isSubRegionOpen,
        'w-[55%]': !isSubRegionOpen
      }">
      <div id="region_nav" class="mb-3 px-3">
        <button @click="toggleRegion(false)" class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300">
          <Icon name="fa6-solid:angles-right" class="text-slate-500" />
        </button>
      </div>
      <div class="px-10">
        <ContractRegion v-if="showRegionDetailComponent === 'ContractRegion'" :id="regionDetailId"
          :isSubRegion="isSubRegionOpen" @show-subregion="handleSubRegionEvent" />
        <InvoiceRegion v-if="showRegionDetailComponent === 'InvoiceRegion'" :id="regionDetailId" :isSubRegion="false"
          @show-subregion="handleSubRegionEvent" />
        <AddContracts v-if="showRegionDetailComponent === 'AddContracts'" :selected_items="selectedAddedContracts"
          @item-clicked="onContractSelected" :multiple="true" />
      </div>
    </div>
  </div>
</template>

<style scoped lang="postcss">
.wrapper {
  padding-bottom: 80px;
  /* Espai per la barra de navegació fixada */
}

.button-primary {
  @apply bg-sky-600 text-white px-4 py-2 rounded hover:bg-sky-700 transition-colors;
}

.button-secondary {
  @apply bg-gray-200 text-gray-700 px-4 py-2 rounded hover:bg-gray-300 transition-colors;
}

.custom-select .vs__selected-options {
  max-height: 50px;
  overflow-y: auto;
}
</style>