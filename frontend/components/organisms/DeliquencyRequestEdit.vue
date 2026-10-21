<script setup>
import { ref, computed, onMounted, watch, nextTick } from 'vue';
import { useI18n } from 'vue-i18n';
import debounce from 'lodash.debounce';
import { useToast } from 'vue-toastification';
import { checkPermission } from '~/middleware/permission';
import { formatMoney } from '~/utils/money';
import WizardStatusNav from '../molecules/WizardStatusNav.vue';
import SearchEntityInput from '../molecules/SearchEntityInput.vue';
import ContractRegion from './ContractRegion.vue';
import InvoiceRegion from './InvoiceRegion.vue';
import ColorBadge from '~/components/atoms/ColorBadge.vue';
import Date from '~/components/atoms/Date.vue';

const toast = useToast();
const { t } = useI18n();
const { $ConfiglistApiService, $InvoiceApiService, $ContractApiService, $ConfigProjectApiService, $RouteApiService, $PaymentApiService, $ExploitationApiService, $apiManager } = useNuxtApp();

defineProps({
  request: Object,
});

const currentStep = ref(0);
const loading = ref(true);
const saving = ref(false);
const showAlert = ref(true);
const showConfirm = ref(false);

const wizardSteps = computed(() => [
  { id: 0, label: `${t('billing_block.step')} 1`, title: t('claim_block.request_payment_sel'), icon: 'fa6-solid:credit-card' },
  { id: 1, label: `${t('billing_block.step')} 2`, title: t('common.summary'), icon: 'fa6-solid:list-ul' },
]);

const maxStep = computed(() => (contracts.value.length > 0 ? 1 : 0));

const selectedClientTypes = ref([]);
const selectedUseTypes = ref([]);
const selectedZones = ref([]);
const selectedContractStatuses = ref([]);
const selectedPaymentTypes = ref([]);
const selectedRejectionReasons = ref([]);
const selectedExploitation = ref(null);
const selectedAddedContracts = ref([]);
const selectedAddedInvoices = ref([]);
const minPendingInvoices = ref(0);
const maxPendingInvoices = ref(0);
const filter_date_start = ref(null);
const filter_date_end = ref(null);
const filter_due_date_start = ref(null);
const filter_due_date_end = ref(null);
const filter_termination_start = ref(null);
const filter_termination_end = ref(null);
const invoiceKind = ref('normal')
const searchedInvoiceKind = ref('normal')

const contracts = ref([]);
const contractsToIgnore = ref([]);
const invoicesToIgnore = ref([]);

const clientTypes = ref([]);
const useTypes = ref([]);
const zones = ref([]);
const contractStatuses = ref([]);
const exploitations = ref([]);
const paymentTypes = ref([]);
const rejectionReasons = ref([]);

const loadingUseTypesIds = ref(false);
const loadingClientTypesIds = ref(false);
const loadingZonesIds = ref(false);
const loadingContractStatuses = ref(false);
const loadingPaymentTypes = ref(false);
const loadingRejectionReasons = ref(false);
const loadingExploitation = ref(false);
const loading_contracts = ref(false);

const showRegion = ref(false);
const isSubRegionOpen = ref(false);
const showRegionDetailComponent = ref(null);
const regionDetailId = ref(null);
const objectPermissions = ref(null);

const expandedContracts = ref(new Set());
const selectedContractIds = ref(new Set());
const selectedInvoiceIds = ref(new Set());
const pageSelectAllEl = ref(null);
const currentPage = ref(1);
const itemsPerPage = ref(50);
const maxVisiblePages = ref(5);
const searchQuery = ref('');
const debouncedSearchQuery = ref('');
const showExcluded = ref(true);

const filteringTaskId = ref(null);
const savingTaskId = ref(null);

const endowmentToken = ref(null);
const irrecoverableToken = ref(null);
const targetStatusToken = ref(null);

const isContractExcluded = (contract) => contractsToIgnore.value.some(c => c.id === contract.id);
const isInvoiceExcluded = (invoice) => invoicesToIgnore.value.some(i => i.id === invoice.id);

const invoiceAmount = (invoice) => parseFloat(invoice?.left_to_pay ?? invoice?.total_final ?? 0) || 0;

const contractInvoices = (contract) => contract?.invoices || [];

const contractAmount = (contract) =>
  contractInvoices(contract).reduce((sum, invoice) => sum + invoiceAmount(invoice), 0);

const hasRange = (start, end) => !!(start || end);

const dueDateDisabled = computed(() =>
  hasRange(filter_date_start.value, filter_date_end.value)
);
const returnDateDisabled = computed(() =>
  hasRange(filter_due_date_start.value, filter_due_date_end.value)
  || hasRange(filter_date_start.value, filter_date_end.value)
);
const billingDateDisabled = computed(() =>
  hasRange(filter_due_date_start.value, filter_due_date_end.value)
);

const allowSearch = computed(() => {
  if (filter_date_start.value && filter_date_end.value) return true;
  if (filter_due_date_start.value && filter_due_date_end.value) return true;
  if (filter_termination_start.value && filter_termination_end.value) return true;
  if (selectedAddedContracts.value.length > 0) return true;
  if (selectedAddedInvoices.value.length > 0) return true;
  if (selectedExploitation.value) return true;
  if (selectedRejectionReasons.value.length > 0) return true;
  return false;
});

const totalInvoices = computed(() =>
  contracts.value.reduce((count, contract) => count + contractInvoices(contract).length, 0)
);

const totalSelectedInvoices = computed(() => {
  return contracts.value.reduce((count, contract) => {
    if (isContractExcluded(contract)) return count;
    return count + contractInvoices(contract).filter(invoice => !isInvoiceExcluded(invoice)).length;
  }, 0);
});

const countExcludedInvoices = computed(() => totalInvoices.value - totalSelectedInvoices.value);

const allowEndowmentTarget = computed(() => searchedInvoiceKind.value === 'normal');

const targetStatusLabel = computed(() => {
  if (targetStatusToken.value != null && targetStatusToken.value === irrecoverableToken.value) {
    return t('billing_block.irrecoverable_invoice');
  }
  return t('contract_block.endowment');
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

const loadData = async () => {
  loading.value = true;
  try {
    await Promise.all([
      getClientTypes(),
      getUseTypes(),
      getContractStatuses(),
      getExploitations(),
      getPaymentType(),
      getRejectionReasons(),
      loadStatusTokens(),
    ]);
    await getRouteZones();
  } catch (error) {
    console.error('Error loading data:', error);
  } finally {
    loading.value = false;
  }
};

const loadStatusTokens = async () => {
  const [endowment, irrecoverable] = await Promise.all([
    $ConfigProjectApiService.get('invoice_status_endowment_token'),
    $ConfigProjectApiService.get('invoice_status_irrecoverable_token'),
  ]);
  endowmentToken.value = endowment;
  irrecoverableToken.value = irrecoverable;
  targetStatusToken.value = endowment;
};

const getClientTypes = async () => {
  loadingClientTypesIds.value = true;
  clientTypes.value = [];
  try {
    const fetchData = await $ConfiglistApiService.getAll('contract/contract-client-type');
    fetchData.results.forEach((item) => {
      clientTypes.value.push({
        label: item.name,
        code: item.id,
      });
    });
  } catch (error) {
    console.error('Error loading client types:', error);
  } finally {
    loadingClientTypesIds.value = false;
  }
};

const getRejectionReasons = async () => {
  loadingRejectionReasons.value = true;
  rejectionReasons.value = [];
  try {
    const fetchData = await $ConfiglistApiService.getAll('billing/reject-motive');
    fetchData.results.forEach((item) => {
      rejectionReasons.value.push({
        label: item.name,
        code: item.id,
      });
    });
  } catch (error) {
    console.error('Error loading rejection motives:', error);
  } finally {
    loadingRejectionReasons.value = false;
  }
};

const getUseTypes = async () => {
  loadingUseTypesIds.value = true;
  useTypes.value = [];
  try {
    const fetchData = await $ConfiglistApiService.getAll('contract/contract-use-type');
    fetchData.results.forEach((item) => {
      useTypes.value.push({
        label: item.name,
        code: item.id,
      });
    });
  } catch (error) {
    console.error('Error loading use types:', error);
  } finally {
    loadingUseTypesIds.value = false;
  }
};

const getRouteZones = async () => {
  loadingZonesIds.value = true;
  zones.value = [];
  try {
    const exploitation_id = selectedExploitation.value ? selectedExploitation.value.code : null;
    const fetchData = await $RouteApiService.getRouteZones(exploitation_id);
    fetchData.forEach((item) => {
      zones.value.push({
        label: item.name,
        code: item.id,
      });
    });
  } catch (error) {
    console.error('Error loading zones:', error);
  } finally {
    loadingZonesIds.value = false;
  }
};

const getPaymentType = async () => {
  loadingPaymentTypes.value = true;
  paymentTypes.value = [];
  try {
    const fetchData = await $ConfiglistApiService.getAll('contract/contract-payment-type');
    fetchData.results.forEach((item) => {
      if (item.token != 'BALANCE') {
        paymentTypes.value.push({
          label: item.name,
          code: item.id,
          token: item.token,
        });
      }
    });
  } catch (err) {
    console.error(err);
  } finally {
    loadingPaymentTypes.value = false;
  }
};

const getExploitations = async () => {
  loadingExploitation.value = true;
  exploitations.value = [];
  try {
    const fetchData = await $ExploitationApiService.getData();
    fetchData.results.forEach((item) => {
      exploitations.value.push({
        label: item.name,
        code: item.id,
      });
    });
    selectedExploitation.value = exploitations.value[0];
  } catch (err) {
    console.error(err);
  } finally {
    loadingExploitation.value = false;
  }
};

const getContractStatuses = async () => {
  loadingContractStatuses.value = true;
  contractStatuses.value = [];
  try {
    const fetchData = await $ConfiglistApiService.getAll('contract/contract-status');
    fetchData.results.forEach((item) => {
      contractStatuses.value.push({
        label: item.name,
        code: item.id,
      });
    });
  } catch (err) {
    console.error(err);
  } finally {
    loadingContractStatuses.value = false;
  }
};


const buildFilterPayload = () => ({
  selectedUseTypesIds: selectedUseTypes.value.map(el => el.code),
  selectedExploitationId: selectedExploitation.value?.code ?? null,
  selectedClientTypesIds: selectedClientTypes.value.map(el => el.code),
  selectedZonesIds: selectedZones.value.map(el => el.code),
  selectedContractStatusesIds: selectedContractStatuses.value.map(el => el.code),
  selectedPaymentTypeIds: selectedPaymentTypes.value.map(el => el.code),
  filter_date_start: filter_date_start.value,
  filter_date_end: filter_date_end.value,
  filter_due_date_start: filter_due_date_start.value,
  filter_due_date_end: filter_due_date_end.value,
  filter_termination_start: filter_termination_start.value,
  filter_termination_end: filter_termination_end.value,
  rejection_motives: selectedRejectionReasons.value.map(el => el.code),
  selected_contracts_id: selectedAddedContracts.value.map(el => el.id),
  selected_invoices_id: selectedAddedInvoices.value.map(el => el.id),
  max_pending_invoices: maxPendingInvoices.value,
  min_pending_invoices: minPendingInvoices.value,
  filter_normal_invoices: invoiceKind.value === 'normal',
  filter_endowment_invoices: invoiceKind.value === 'endowment',
});

const groupInvoicesByContract = (invoiceList, contractList) => {
  const invoicesByContract = new Map();
  for (const invoice of invoiceList) {
    const key = invoice.contract ?? invoice.contract_id;
    if (key == null) continue;
    const mapKey = String(key);
    if (!invoicesByContract.has(mapKey)) invoicesByContract.set(mapKey, []);
    invoicesByContract.get(mapKey).push(invoice);
  }

  const matchedIds = new Set();
  const grouped = [];
  for (const contract of contractList) {
    const related = invoicesByContract.get(String(contract.id)) || [];
    if (!related.length) continue;
    matchedIds.add(String(contract.id));
    grouped.push({ ...contract, invoices: related });
  }

  for (const [key, related] of invoicesByContract) {
    if (matchedIds.has(key)) continue;
    const sample = related[0] || {};
    grouped.push({
      id: sample.contract ?? sample.contract_id ?? key,
      token: sample.contract_token,
      holder_token: sample.customer_token_final,
      holder_full_name: sample.customer_final,
      invoices: related,
    });
  }

  return grouped;
};

const applyContracts = (response) => {
  const invoiceList = Array.isArray(response?.invoices) ? response.invoices : [];
  const contractList = response?.contracts || response?.contract_data || [];
  contracts.value = groupInvoicesByContract(invoiceList, contractList);
  currentPage.value = 1;
  searchQuery.value = '';
  debouncedSearchQuery.value = '';
  contractsToIgnore.value = [];
  invoicesToIgnore.value = [];
  expandedContracts.value = new Set();
  clearResultSelection();
  if (!contracts.value.length) {
    toast.warning(t('common.no_data_found'), {
      position: 'top-right',
      timeout: 2500,
      closeButton: true,
      icon: true,
      rtl: false,
    });
  }
};

const applySearchResult = (response) => {
  if (response?.ERROR) {
    toast.error(t('common.error_load'));
    return;
  }
  applyContracts(response);
};

const getDeliquencyData = async () => {
  loading_contracts.value = true;
  contracts.value = [];
  contractsToIgnore.value = [];
  invoicesToIgnore.value = [];
  clearResultSelection();
  const kind = invoiceKind.value;
  try {
    const response = await $PaymentApiService.manageDeliquency({
      ...buildFilterPayload(),
    });
    searchedInvoiceKind.value = kind;
    const hasData = response?.contracts || response?.contract_data || response?.invoices;
    if (response?.task_id && !hasData) {
      filteringTaskId.value = response.task_id;
    } else {
      filteringTaskId.value = null;
      applySearchResult(response);
    }
  } catch (e) {
    console.error(e);
    toast.error(t('common.error_load'));
  } finally {
    loading_contracts.value = false;
  }
};

const refreshData = async () => {
  const taskId = filteringTaskId.value;
  if (!taskId) return;
  try {
    const res = await $apiManager.checkTask(taskId);
    const payload = res?.result;
    filteringTaskId.value = null;
    if (payload?.ERROR) {
      toast.error(t('common.error_load'));
      return;
    }
    if (Array.isArray(payload)) {
      applyContracts({ contracts: payload });
    } else {
      applyContracts(payload || {});
    }
  } catch (e) {
    console.error(e);
    filteringTaskId.value = null;
    toast.error(t('common.error_load'));
  }
};

const onSearchTaskError = () => {
  filteringTaskId.value = null;
  toast.error(t('common.error_load'));
};

const clearResultSelection = () => {
  selectedContractIds.value = new Set();
  selectedInvoiceIds.value = new Set();
};

const onContractSelected = (item) => {
  if (!selectedAddedContracts.value.some(c => c.id === item.id)) {
    selectedAddedContracts.value.push(item);
  }
};

const removeSelectedContract = (item) => {
  selectedAddedContracts.value = selectedAddedContracts.value.filter(c => c.id !== item.id);
};

const onInvoiceSelected = (item) => {
  if (!selectedAddedInvoices.value.some(i => i.id === item.id)) {
    selectedAddedInvoices.value.push(item);
  }
};

const removeSelectedInvoice = (item) => {
  selectedAddedInvoices.value = selectedAddedInvoices.value.filter(i => i.id !== item.id);
};

const nextStep = () => {
  if (currentStep.value < 1) {
    currentStep.value++;
  }
};

const prevStep = () => {
  if (currentStep.value > 0) {
    currentStep.value--;
  }
};

const openConfirm = () => {
  if (totalSelectedInvoices.value === 0) {
    toast.warning(t('warning_block.warning_select_contract'));
    return;
  }
  if (!allowEndowmentTarget.value) {
    targetStatusToken.value = irrecoverableToken.value;
  } else if (targetStatusToken.value !== irrecoverableToken.value) {
    targetStatusToken.value = endowmentToken.value;
  }
  showConfirm.value = true;
};

const closeConfirm = () => {
  if (saving.value) return;
  showConfirm.value = false;
};

const save = async () => {
  if (!allowEndowmentTarget.value) {
    targetStatusToken.value = irrecoverableToken.value;
  }
  if (!targetStatusToken.value) return;
  saving.value = true;
  try {
    const selectedContracts = contracts.value.filter(c => !isContractExcluded(c));
    const selectedInvoices = selectedContracts.flatMap(contract =>
      contractInvoices(contract).filter(invoice => !isInvoiceExcluded(invoice))
    );

    const save_data = {
      saving: true,
      status_token: targetStatusToken.value,
      invoice_ids: selectedInvoices.map(invoice => invoice.id),
      contract_ids: selectedContracts.map(c => c.id),
      ignore_contract_ids: contractsToIgnore.value.map(c => c.id),
      ignore_invoice_ids: invoicesToIgnore.value.map(invoice => invoice.id),
    };

    const response = await $PaymentApiService.manageDeliquency(save_data);
    showConfirm.value = false;
    if (response?.task_id) {
      savingTaskId.value = response.task_id;
    } else {
      await navigateTo('/billing/wallet-managements/');
    }
  } catch (err) {
    console.error(err);
    toast.error(t('common.error_save'));
  } finally {
    saving.value = false;
  }
};

const onSaveTaskDone = async () => {
  const taskId = savingTaskId.value;
  savingTaskId.value = null;
  try {
    if (taskId) {
      const res = await $apiManager.checkTask(taskId);
      if (res?.result?.ERROR) {
        toast.error(t('common.error_save'));
        return;
      }
    }
  } catch (e) {
    console.error(e);
    toast.error(t('common.error_save'));
    return;
  }
  await navigateTo('/billing/wallet-managements/');
};

const onSaveTaskError = () => {
  savingTaskId.value = null;
  toast.error(t('common.error_save'));
};

const showDetail = (component, id) => {
  showRegionDetailComponent.value = component;
  regionDetailId.value = id;
  toggleRegion(true);
};

const toggleRegion = (force) => {
  showRegion.value = force !== undefined ? force : !showRegion.value;
  if (!force) {
    showRegionDetailComponent.value = null;
    regionDetailId.value = null;
    isSubRegionOpen.value = false;
  }
};

const handleSubRegionEvent = (event) => {
  isSubRegionOpen.value = event;
};

const contractMatchesSearch = (contract, query) => {
  return contract.token?.toLowerCase().includes(query)
    || contract.holder_full_name?.toLowerCase().includes(query)
    || contract.holder?.toLowerCase().includes(query)
    || contract.holder_token?.toLowerCase().includes(query)
    || contract.supply_point?.toLowerCase().includes(query);
};

const invoiceMatchesSearch = (invoice, query) => {
  return invoice.serie_final?.toLowerCase().includes(query)
    || invoice.number?.toLowerCase().includes(query)
    || invoice.token?.toLowerCase().includes(query)
    || invoice.title_final?.toLowerCase().includes(query)
    || invoice.customer_final?.toLowerCase().includes(query)
    || invoice.payment_iban_final?.toLowerCase().includes(query);
};

const contractMatchesSearchQuery = (contract) => {
  const query = debouncedSearchQuery.value?.trim().toLowerCase();
  if (!query) return true;
  if (contractMatchesSearch(contract, query)) return true;
  return contractInvoices(contract).some(invoice => invoiceMatchesSearch(invoice, query));
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

const getContractInvoices = (contract) => {
  let rows = contractInvoices(contract);
  const query = debouncedSearchQuery.value?.trim().toLowerCase();
  if (!showExcluded.value) {
    rows = rows.filter(invoice => !isInvoiceExcluded(invoice));
  }
  if (query && !contractMatchesSearch(contract, query)) {
    rows = rows.filter(invoice => invoiceMatchesSearch(invoice, query));
  }
  return rows;
};

const totalExcludedContracts = computed(() => contractsToIgnore.value.length);

const activeContractsSummary = computed(() => {
  const active = contracts.value.filter(c => !isContractExcluded(c));
  const selectedInvoices = active.flatMap(contract =>
    contractInvoices(contract).filter(invoice => !isInvoiceExcluded(invoice))
  );
  return {
    contractsCount: active.length,
    invoicesCount: selectedInvoices.length,
    totalAmount: selectedInvoices.reduce((acc, invoice) => acc + invoiceAmount(invoice), 0),
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
    return `${summary.contractsCount}|${summary.invoicesCount}|${summary.totalAmount}`;
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

const toggleContract = (contractId) => {
  const next = new Set(expandedContracts.value);
  if (next.has(contractId)) {
    next.delete(contractId);
  } else {
    next.add(contractId);
  }
  expandedContracts.value = next;
};

const isContractExpanded = (contractId) => {
  return expandedContracts.value.has(contractId);
};

const toggleId = (setRef, id) => {
  const next = new Set(setRef.value);
  if (next.has(id)) next.delete(id);
  else next.add(id);
  setRef.value = next;
};

const toggleSelectedContract = (contractId) => {
  toggleId(selectedContractIds, contractId);
};

const toggleSelectedInvoice = (invoiceId) => {
  toggleId(selectedInvoiceIds, invoiceId);
};

const visibleInvoiceIds = (contract) => getContractInvoices(contract).map(invoice => invoice.id);

const allVisibleInvoicesSelected = (contract) => {
  const ids = visibleInvoiceIds(contract);
  return ids.length > 0 && ids.every(id => selectedInvoiceIds.value.has(id));
};

const toggleVisibleInvoices = (contract) => {
  if (isContractExcluded(contract)) return;
  const ids = visibleInvoiceIds(contract);
  const next = new Set(selectedInvoiceIds.value);
  const allSelected = ids.length > 0 && ids.every(id => next.has(id));
  ids.forEach(id => {
    if (allSelected) next.delete(id);
    else next.add(id);
  });
  selectedInvoiceIds.value = next;
};

const pageContractsAllSelected = computed(() => {
  const rows = paginatedContracts.value;
  return rows.length > 0 && rows.every(contract => selectedContractIds.value.has(contract.id));
});

const pageContractsSomeSelected = computed(() => {
  const rows = paginatedContracts.value;
  const selected = rows.filter(contract => selectedContractIds.value.has(contract.id)).length;
  return selected > 0 && selected < rows.length;
});

const syncPageSelectAll = () => {
  const el = pageSelectAllEl.value;
  if (!el) return;
  el.indeterminate = pageContractsSomeSelected.value && !pageContractsAllSelected.value;
};

const bindPageSelectAll = (el) => {
  pageSelectAllEl.value = el;
  syncPageSelectAll();
};

watch([pageContractsAllSelected, pageContractsSomeSelected], () => {
  syncPageSelectAll();
});

const togglePageContracts = () => {
  const next = new Set(selectedContractIds.value);
  const ids = paginatedContracts.value.map(contract => contract.id);
  const allSelected = ids.length > 0 && ids.every(id => next.has(id));
  ids.forEach(id => {
    if (allSelected) next.delete(id);
    else next.add(id);
  });
  selectedContractIds.value = next;
};

const selectionState = computed(() => {
  const contractIds = selectedContractIds.value;
  const invoiceIds = selectedInvoiceIds.value;
  let canExclude = false;
  let canInclude = false;

  for (const contract of contracts.value) {
    if (contractIds.has(contract.id)) {
      if (isContractExcluded(contract)) canInclude = true;
      else canExclude = true;
    }
    if (isContractExcluded(contract)) continue;
    for (const invoice of contractInvoices(contract)) {
      if (!invoiceIds.has(invoice.id)) continue;
      if (isInvoiceExcluded(invoice)) canInclude = true;
      else canExclude = true;
    }
  }

  return {
    contractsSelected: contractIds.size,
    invoicesSelected: invoiceIds.size,
    canExclude,
    canInclude,
  };
});

const excludeSelected = () => {
  const contractIds = selectedContractIds.value;
  const invoiceIds = selectedInvoiceIds.value;
  if (!contractIds.size && !invoiceIds.size) return;

  const nextContracts = [...contractsToIgnore.value];
  const ignoredContractIds = new Set(nextContracts.map(contract => contract.id));
  for (const contract of contracts.value) {
    if (!contractIds.has(contract.id) || ignoredContractIds.has(contract.id)) continue;
    nextContracts.push(contract);
    ignoredContractIds.add(contract.id);
  }

  const nextInvoices = [...invoicesToIgnore.value];
  const ignoredInvoiceIds = new Set(nextInvoices.map(invoice => invoice.id));
  for (const contract of contracts.value) {
    if (contractIds.has(contract.id) || isContractExcluded(contract)) continue;
    for (const invoice of contractInvoices(contract)) {
      if (!invoiceIds.has(invoice.id) || ignoredInvoiceIds.has(invoice.id)) continue;
      nextInvoices.push(invoice);
      ignoredInvoiceIds.add(invoice.id);
    }
  }

  contractsToIgnore.value = nextContracts;
  invoicesToIgnore.value = nextInvoices;
  clearResultSelection();
};

const includeSelected = () => {
  const contractIds = selectedContractIds.value;
  const invoiceIds = selectedInvoiceIds.value;
  contractsToIgnore.value = contractsToIgnore.value.filter(contract => !contractIds.has(contract.id));
  invoicesToIgnore.value = invoicesToIgnore.value.filter(invoice => !invoiceIds.has(invoice.id));
  clearResultSelection();
};

onMounted(async () => {
  objectPermissions.value = await checkPermission($InvoiceApiService);
  if (!objectPermissions.value.can_change) {
    toast.error(t('common.no_permissions'));
    return navigateTo('/');
  }
  loadData();
});

watch(() => selectedExploitation.value, (newVal, oldVal) => {
  if (oldVal && newVal?.code !== oldVal?.code) {
    selectedZones.value = [];
  }
  getRouteZones();
});
</script>

<template>
  <div v-if="objectPermissions?.can_change" class="mb-20 max-w-full pb-20 text-base">
    <WizardStatusNav :steps="wizardSteps" :current-step="currentStep" :max-step="maxStep" disabled
      :show-description="false" />

    <div class="rounded py-4 px-4 bg-white">
      <div v-if="loading">
        <div class="flex justify-center items-center">
          <Icon name="fa6-solid:spinner" class="animate-spin text-slate-500" />
          <span class="ml-2">{{ $t('common.loading') }}</span>
        </div>
      </div>

      <div v-else>
        <div v-show="currentStep === 0" class="space-y-4">
          <div class="grid grid-cols-3 gap-x-4 gap-y-4">
            <div class="pr-2 xl:border-r border-slate-200">
              <p class="block text-sm font-bold text-slate-600 mb-2">{{ $t('common.due_date') }}</p>
              <div class="grid grid-cols-2 gap-2">
                <AtomsInputDate v-model="filter_due_date_start" class="w-full" :label="$t('common.from')"
                  :disabled="dueDateDisabled" />
                <AtomsInputDate v-model="filter_due_date_end" class="w-full" :label="$t('common.until')"
                  :disabled="dueDateDisabled" />
              </div>
            </div>
            <div class="pr-2 xl:border-r border-slate-200">
              <p class="block text-sm font-bold text-slate-600 mb-2">{{ $t('billing') }}</p>
              <div class="grid grid-cols-2 gap-2">
                <AtomsInputDate v-model="filter_date_start" class="w-full" :label="$t('common.from')"
                  :disabled="billingDateDisabled" />
                <AtomsInputDate v-model="filter_date_end" class="w-full" :label="$t('common.until')"
                  :disabled="billingDateDisabled" />
              </div>
            </div>
            <div>
              <p class="block text-sm font-bold text-slate-600 mb-2">{{ $t('contract_block.termination_end_date') }}</p>
              <div class="grid grid-cols-2 gap-2">
                <AtomsInputDate v-model="filter_termination_start" class="w-full" :label="$t('common.from')" />
                <AtomsInputDate v-model="filter_termination_end" class="w-full" :label="$t('common.until')" />
              </div>
            </div>
            <div class="pr-2 xl:border-r border-slate-200">
              <p class="block text-sm font-bold text-slate-600 mb-2">{{ $t('billing_block.pending_invoices') }}</p>
              <div class="grid grid-cols-2 gap-2">
                <div>
                  <label for="min_pending_invoices" class="block text-xs font-semibold text-slate-500 mb-1">
                    {{ $t('pricing_block.min') }}
                  </label>
                  <input id="min_pending_invoices" type="number" class="input w-full"
                    v-model.number="minPendingInvoices" placeholder="0">
                </div>
                <div>
                  <label for="max_pending_invoices" class="block text-xs font-semibold text-slate-500 mb-1">
                    {{ $t('pricing_block.max') }}
                  </label>
                  <input id="max_pending_invoices" type="number" class="input w-full"
                    v-model.number="maxPendingInvoices" placeholder="9999">
                </div>
              </div>
            </div>
          </div>

          <hr />

          <div class="grid grid-cols-2 gap-4">
            <SearchEntityInput :service="$ContractApiService" @select="onContractSelected"
              :title="`${$t('dashboard.search')} ${$t('contract')}`" :result_value="'holder_full_name'"
              class="mt-auto" />
            <div v-if="selectedAddedContracts?.length > 0">
              <label class="block text-sm font-medium text-slate-600 mb-2">
                {{ $t('contract_block.selected_contracts') }}
              </label>
              <div class="flex flex-wrap gap-2">
                <span v-for="contract in selectedAddedContracts" :key="contract.id"
                  class="group relative bg-slate-100 text-slate-800 px-3 py-1 rounded-full text-sm border border-slate-300 flex items-center gap-2">
                  <span>{{ contract.token }}</span>
                  <button @click="removeSelectedContract(contract)"
                    class="absolute right-0 top-0 h-4 w-4 bg-white rounded-full text-slate-500 opacity-0 hover:text-slate-700 hover:underline group-hover:opacity-100 transition-all duration-300">
                    <Icon name="fa6-solid:xmark"
                      class="text-red-500 text-sm m-auto opacity-0 group-hover:opacity-100" />
                  </button>
                </span>
              </div>
            </div>
            <span v-else></span>

            <SearchEntityInput :service="$InvoiceApiService" @select="onInvoiceSelected"
              :title="$t('search_block.search_invoice')" :result_value="'serie_final'" class="mt-auto" />
            <div v-if="selectedAddedInvoices?.length > 0">
              <label class="block text-sm font-medium text-slate-600 mb-2">
                {{ $t('billing_block.selected_invoices') }}
              </label>
              <div class="flex flex-wrap gap-2">
                <span v-for="invoice in selectedAddedInvoices" :key="invoice.id"
                  class="group relative bg-slate-100 text-slate-800 px-3 py-1 rounded-full text-sm border border-slate-300 flex items-center gap-2">
                  <span>{{ invoice.serie_final || invoice.token }}</span>
                  <button @click="removeSelectedInvoice(invoice)"
                    class="absolute right-0 top-0 h-4 w-4 bg-white rounded-full text-slate-500 opacity-0 hover:text-slate-700 hover:underline group-hover:opacity-100 transition-all duration-300">
                    <Icon name="fa6-solid:xmark"
                      class="text-red-500 text-sm m-auto opacity-0 group-hover:opacity-100" />
                  </button>
                </span>
              </div>
            </div>
            <span v-else></span>

            <div>
              <label class="block text-sm font-medium text-slate-600 mb-2">{{ $t('exploitation') }}</label>
              <v-select
                class="mr-1 block w-full [&_.vs__selected-options]:max-h-[50px] [&_.vs__selected-options]:overflow-y-auto"
                v-model="selectedExploitation" :options="exploitations" :disabled="exploitations?.length == 1"
                :loading="loadingExploitation" />
            </div>

            <div>
              <label class="block text-sm font-medium text-slate-600 mb-2">{{ $t('service_block.zone') }}</label>
              <v-select multiple
                class="mr-1 block w-full [&_.vs__selected-options]:max-h-[50px] [&_.vs__selected-options]:overflow-y-auto"
                v-model="selectedZones" :options="zones" :loading="loadingZonesIds" />
            </div>

            <div>
              <label class="block text-sm font-medium text-slate-600 mb-2">{{ $t('billing_block.contract_status')
              }}</label>
              <v-select multiple
                class="mr-1 block w-full [&_.vs__selected-options]:max-h-[50px] [&_.vs__selected-options]:overflow-y-auto"
                v-model="selectedContractStatuses" :options="contractStatuses" :loading="loadingContractStatuses" />
            </div>

            <div>
              <label class="block text-sm font-medium text-slate-600 mb-2">{{ $t('contract_block.client_type')
              }}</label>
              <v-select multiple
                class="mr-1 block w-full [&_.vs__selected-options]:max-h-[50px] [&_.vs__selected-options]:overflow-y-auto"
                v-model="selectedClientTypes" :options="clientTypes" :loading="loadingClientTypesIds" />
            </div>

            <div>
              <label class="block text-sm font-medium text-slate-600 mb-2">{{ $t('common.usage_type') }}</label>
              <v-select multiple
                class="mr-1 block w-full [&_.vs__selected-options]:max-h-[50px] [&_.vs__selected-options]:overflow-y-auto"
                v-model="selectedUseTypes" :options="useTypes" :loading="loadingUseTypesIds" />
            </div>

            <div>
              <label class="block text-sm font-medium text-slate-600 mb-2">{{ $t('common.payment_method') }}</label>
              <v-select multiple
                class="mr-1 block w-full [&_.vs__selected-options]:max-h-[50px] [&_.vs__selected-options]:overflow-y-auto"
                v-model="selectedPaymentTypes" :options="paymentTypes" :loading="loadingPaymentTypes" />
            </div>

            <div>
              <label class="block text-sm font-medium text-slate-600 mb-2">{{ $t('common.status') }}: {{ $t('invoice')
                }}</label>
              <div class="flex flex-col gap-2">
                <label class="inline-flex items-center">
                  <input type="radio" name="deliquency-invoice-kind" value="normal" v-model="invoiceKind"
                    class="h-4 w-4 border-gray-300 text-sky-600 focus:ring-sky-500" />
                  <span class="ml-2 text-sm text-gray-700">{{
                    $t('pricing_block.accounting_pricing_invoice_category_normal') }}</span>
                </label>
                <label class="inline-flex items-center">
                  <input type="radio" name="deliquency-invoice-kind" value="endowment" v-model="invoiceKind"
                    class="h-4 w-4 border-gray-300 text-sky-600 focus:ring-sky-500" />
                  <span class="ml-2 text-sm text-gray-700">{{ $t('contract_block.deliquency') }}</span>
                </label>
              </div>
            </div>

            <div v-if="selectedPaymentTypes.some(paymentType => paymentType.token === 'DIRECT_DEBIT')">
              <label class="block text-sm font-medium text-slate-600 mb-2">{{ $t('common.return') }}</label>
              <v-select multiple
                class="mr-1 block w-full [&_.vs__selected-options]:max-h-[50px] [&_.vs__selected-options]:overflow-y-auto"
                v-model="selectedRejectionReasons" :options="rejectionReasons" :loading="loadingRejectionReasons" />
            </div>
          </div>

          <div v-if="showAlert"
            class="bg-sky-100 text-sky-700 py-3 px-5 rounded-lg mb-3 flex items-center justify-between">
            <span>{{ $t('informative_block.info_show_all_data_no_filter') }}</span>
            <button @click="showAlert = false" class="text-sky-700 hover:text-sky-900 text-xl"
              :title="$t('common.hide')">&times;</button>
          </div>
        </div>

        <div v-show="currentStep === 1" class="space-y-4">
          <div v-if="!loading_contracts" class="mt-2 space-y-3">
            <div class="flex flex-col gap-3 sm:flex-row sm:items-center">
              <div class="relative min-w-0 flex-1">
                <div class="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3">
                  <Icon name="fa6-solid:magnifying-glass" class="text-slate-400" />
                </div>
                <input v-model="searchQuery" type="text"
                  :placeholder="`${$t('dashboard.search')} ${$t('contract')}, ${$t('invoice')}, ${$t('common.iban')}`"
                  class="h-10 w-full rounded-lg border border-slate-300 bg-white pl-10 pr-3 text-sm text-slate-800 placeholder:text-slate-400 focus:border-sky-500 focus:outline-none focus:ring-2 focus:ring-sky-100" />
              </div>
              <label class="inline-flex shrink-0 items-center">
                <input type="checkbox" v-model="showExcluded"
                  class="h-4 w-4 rounded border-slate-300 text-sky-600 focus:ring-sky-500 disabled:cursor-not-allowed disabled:opacity-40" />
                <span class="ml-2 text-sm text-slate-600">{{ $t('common.show') }} {{
                  $t('billing_block.excluded_multiple') }}</span>
              </label>
            </div>

            <div class="flex flex-wrap items-center justify-between gap-2 text-xs text-slate-500">
              <span>
                {{ filteredContracts.length }} {{ $t('common.contracts') }}
                <span v-if="totalExcludedContracts > 0 || countExcludedInvoices > 0">
                  · {{ totalExcludedContracts }} {{ $t('billing_block.excluded_multiple') }}
                  <span v-if="countExcludedInvoices > 0">, {{ countExcludedInvoices }} {{ $t('invoices') }}</span>
                </span>
              </span>
            </div>

            <div v-if="selectionState.contractsSelected || selectionState.invoicesSelected"
              class="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2">
              <p class="text-sm text-slate-700">
                <span class="font-semibold text-slate-900">{{ selectionState.contractsSelected +
                  selectionState.invoicesSelected }}</span>
                {{ $t('common.selected') }}
                <span class="text-slate-500">
                  · {{ selectionState.contractsSelected }} {{ $t('common.contracts') }}
                  · {{ selectionState.invoicesSelected }} {{ $t('invoices') }}
                </span>
              </p>
              <div class="flex flex-wrap items-center gap-2">
                <button type="button"
                  class="inline-flex items-center rounded-md border border-slate-800 bg-slate-800 px-3 py-1.5 text-sm font-medium text-white hover:bg-slate-700 disabled:cursor-not-allowed disabled:opacity-40"
                  :disabled="!selectionState.canExclude" @click="excludeSelected">
                  {{ $t('billing_block.exclude') }}
                </button>
                <button type="button"
                  class="inline-flex items-center rounded-md border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-40"
                  :disabled="!selectionState.canInclude" @click="includeSelected">
                  {{ $t('billing_block.include') }}
                </button>
                <button type="button" class="px-2 text-sm text-slate-500 hover:text-slate-800"
                  @click="clearResultSelection">
                  {{ $t('common.remove_selection') }}
                </button>
              </div>
            </div>

            <div class="overflow-hidden border border-slate-200">
              <div v-if="filteredContracts.length === 0" class="px-4 py-16 text-center text-sm text-slate-500">
                {{ $t('common.no_data_found') }}
              </div>
              <div v-else class="max-h-[58vh] overflow-auto">
                <div class="min-w-[960px]">
                  <div
                    class="grid grid-cols-[36px_20px_minmax(160px,1.15fr)_minmax(220px,1.7fr)_88px_120px_minmax(120px,0.7fr)] items-center gap-x-3 sticky top-0 z-10 border-b border-slate-200 bg-slate-50 px-3 py-2 text-[11px] font-semibold uppercase tracking-wide text-slate-500">
                    <input :ref="bindPageSelectAll" type="checkbox"
                      class="h-4 w-4 rounded border-slate-300 text-sky-600 focus:ring-sky-500 disabled:cursor-not-allowed disabled:opacity-40"
                      :checked="pageContractsAllSelected" :title="$t('common.select_all')"
                      @change="togglePageContracts" />
                    <span></span>
                    <span>{{ $t('contract') }}</span>
                    <span>{{ $t('contract_block.current_holder') }}</span>
                    <span class="text-right">{{ $t('invoices') }}</span>
                    <span class="text-right">{{ $t('common.amount') }}</span>
                    <span>{{ $t('common.status') }}</span>
                  </div>

                  <div v-for="contract in paginatedContracts" :key="contract.id"
                    class="border-b border-slate-100 last:border-b-0">
                    <div
                      class="grid grid-cols-[36px_20px_minmax(160px,1.15fr)_minmax(220px,1.7fr)_88px_120px_minmax(120px,0.7fr)] items-center gap-x-3 cursor-pointer px-3 py-2.5"
                      :class="{
                        'bg-sky-50': selectedContractIds.has(contract.id),
                        'bg-slate-50 opacity-70': isContractExcluded(contract) && !selectedContractIds.has(contract.id),
                        'hover:bg-slate-50': !selectedContractIds.has(contract.id) && !isContractExcluded(contract),
                      }" @click="toggleContract(contract.id)">
                      <div @click.stop>
                        <input type="checkbox"
                          class="h-4 w-4 rounded border-slate-300 text-sky-600 focus:ring-sky-500 disabled:cursor-not-allowed disabled:opacity-40"
                          :checked="selectedContractIds.has(contract.id)" :title="$t('common.select')"
                          @change="toggleSelectedContract(contract.id)" />
                      </div>
                      <Icon class="text-xs text-slate-400"
                        :name="isContractExpanded(contract.id) ? 'fa6-solid:chevron-down' : 'fa6-solid:chevron-right'" />
                      <div class="min-w-0">
                        <div class="flex items-center gap-2">
                          <button type="button"
                            class="truncate text-left text-sm font-medium text-sky-700 hover:text-sky-900 hover:underline"
                            :title="`${$t('common.show')} ${$t('common.details')}`"
                            @click.stop="showDetail('ContractRegion', contract.id)">
                            {{ contract.token }}
                          </button>
                          <AtomsVulnerabilityCheck
                            v-if="contract.holder_vulnerability_level && contract.holder_vulnerability_level > 0"
                            :vulnerability_level="contract.holder_vulnerability_level" :small="true" />
                          <span v-if="isContractExcluded(contract)"
                            class="rounded bg-slate-200 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-slate-600">
                            {{ $t('billing_block.excluded') }}
                          </span>
                        </div>
                        <p class="truncate text-xs text-slate-500">
                          <span>{{ contract.use_type_name || contract.use_type }}</span>
                          <span v-if="contract.client_type"> · {{ contract.client_type }}</span>
                          <span v-if="contract.category"> · {{ contract.category }}</span>
                          <span v-if="contract.debt_management"> · {{ contract.debt_management }}</span>
                        </p>
                      </div>
                      <div class="min-w-0">
                        <p class="truncate text-sm text-slate-800"
                          :title="contract.holder_full_name || contract.holder">
                          {{ contract.holder_full_name || contract.holder }}
                        </p>
                        <p class="truncate text-xs text-slate-500">
                          <span v-if="contract.holder_token">{{ contract.holder_token }}</span>
                          <span v-if="contract.holder_token && contract.supply_point"> · </span>
                          <span v-if="contract.supply_point">{{ contract.supply_point }}</span>
                        </p>
                      </div>
                      <span class="text-right text-sm tabular-nums text-slate-700">{{ contractInvoices(contract).length
                      }}</span>
                      <span class="text-right text-sm font-medium tabular-nums text-slate-800">{{
                        formatMoney(contractAmount(contract)) }} €</span>
                      <ColorBadge :color="contract.status_color || contract.status?.color"
                        :value="contract.status_name || contract.status?.name" />
                    </div>

                    <div v-if="isContractExpanded(contract.id)"
                      class="border-t border-slate-100 bg-slate-50/80 py-2 pl-12 pr-3">
                      <div
                        class="grid grid-cols-[36px_minmax(180px,1.5fr)_130px_120px_minmax(140px,1fr)_minmax(110px,0.7fr)] items-center gap-x-3 px-2 py-1 text-[11px] font-semibold uppercase tracking-wide text-slate-400">
                        <input type="checkbox"
                          class="h-4 w-4 rounded border-slate-300 text-sky-600 focus:ring-sky-500 disabled:cursor-not-allowed disabled:opacity-40"
                          :disabled="isContractExcluded(contract) || !getContractInvoices(contract).length"
                          :checked="allVisibleInvoicesSelected(contract)" :title="$t('common.select_all')"
                          @change="toggleVisibleInvoices(contract)" />
                        <span>{{ $t('invoice') }}</span>
                        <span>{{ $t('common.due_date') }}</span>
                        <span class="text-right">{{ $t('common.amount') }}</span>
                        <span>{{ $t('common.payment_method') }}</span>
                        <span>{{ $t('common.status') }}</span>
                      </div>
                      <p v-if="getContractInvoices(contract).length === 0" class="px-2 py-3 text-sm text-slate-500">
                        {{ $t('common.no_data_found') }}
                      </p>
                      <div v-for="invoice in getContractInvoices(contract)" :key="invoice.id"
                        class="grid grid-cols-[36px_minmax(180px,1.5fr)_130px_120px_minmax(140px,1fr)_minmax(110px,0.7fr)] items-center gap-x-3 rounded-md px-2 py-1.5"
                        :class="{
                          'bg-sky-50': selectedInvoiceIds.has(invoice.id),
                          'opacity-60': (isInvoiceExcluded(invoice) || isContractExcluded(contract)) && !selectedInvoiceIds.has(invoice.id),
                        }">
                        <input type="checkbox"
                          class="h-4 w-4 rounded border-slate-300 text-sky-600 focus:ring-sky-500 disabled:cursor-not-allowed disabled:opacity-40"
                          :disabled="isContractExcluded(contract)" :checked="selectedInvoiceIds.has(invoice.id)"
                          :title="$t('common.select')" @change="toggleSelectedInvoice(invoice.id)" />
                        <div class="flex min-w-0 items-center gap-2">
                          <button type="button"
                            class="truncate text-left text-sm text-sky-700 hover:text-sky-900 hover:underline"
                            :title="`${$t('common.show')} ${$t('common.details')}`"
                            @click.stop="showDetail('InvoiceRegion', invoice.id)">
                            {{ invoice.serie_final || invoice.number || invoice.token }}
                          </button>
                          <span v-if="isInvoiceExcluded(invoice) && !isContractExcluded(contract)"
                            class="shrink-0 rounded bg-slate-200 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-slate-600">
                            {{ $t('billing_block.excluded') }}
                          </span>
                        </div>
                        <span class="text-sm text-slate-600">
                          <Date :date="invoice.due_date" />
                        </span>
                        <span class="text-right text-sm tabular-nums text-slate-800">{{
                          formatMoney(invoiceAmount(invoice)) }} €</span>
                        <span class="truncate text-sm text-slate-600">{{ invoice.payment_type_final }}</span>
                        <ColorBadge :color="invoice.status_color" :value="invoice.status_name" />
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <div v-if="totalPages > 1" class="flex items-center justify-center gap-1.5 pb-1">
              <button type="button"
                class="inline-flex h-8 min-w-8 items-center justify-center rounded-md border border-slate-200 px-2 text-sm text-slate-600 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-40"
                @click="prevPage" :disabled="currentPage === 1" :title="$t('common.previous')">
                <Icon name="fa6-solid:chevron-left" />
              </button>
              <button v-if="visiblePages[0] > 1" type="button"
                class="inline-flex h-8 min-w-8 items-center justify-center rounded-md border border-slate-200 px-2 text-sm text-slate-600 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-40"
                @click="goToPage(1)">
                1
              </button>
              <span v-if="visiblePages[0] > 2" class="px-1 text-slate-400">...</span>
              <button v-for="page in visiblePages" :key="page" type="button"
                class="inline-flex h-8 min-w-8 items-center justify-center rounded-md border border-slate-200 px-2 text-sm text-slate-600 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-40"
                @click="goToPage(page)"
                :class="page === currentPage ? 'border-slate-800 bg-slate-800 text-white hover:bg-slate-800' : ''">
                {{ page }}
              </button>
              <span v-if="visiblePages[visiblePages.length - 1] < totalPages - 1" class="px-1 text-slate-400">...</span>
              <button v-if="visiblePages[visiblePages.length - 1] < totalPages" type="button"
                class="inline-flex h-8 min-w-8 items-center justify-center rounded-md border border-slate-200 px-2 text-sm text-slate-600 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-40"
                @click="goToPage(totalPages)">
                {{ totalPages }}
              </button>
              <button type="button"
                class="inline-flex h-8 min-w-8 items-center justify-center rounded-md border border-slate-200 px-2 text-sm text-slate-600 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-40"
                @click="nextPage" :disabled="currentPage === totalPages" :title="$t('common.next')">
                <Icon name="fa6-solid:chevron-right" />
              </button>
              <span class="ml-3 text-sm text-slate-500">
                {{ $t('common.page') }} {{ currentPage }} {{ $t('common.of') }} {{ totalPages }}
              </span>
            </div>
          </div>
          <div v-else class="mx-auto text-center p-5">
            <Icon name="fa:spinner" class="text-slate-600 max-auto items-center animate-spin" />
            <span class="ml-2">{{ $t('common.loading') }}</span>
          </div>
        </div>
      </div>
    </div>

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
              {{ totalSelectedInvoices }} ({{ totalInvoices }})
            </div>
            <div class="text-sm font-semibold text-slate-700">
              {{ $t('invoices') }}
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
          <span v-if="savingTaskId" class="text-sm text-slate-700 max-w-xs">
            {{ $t('informative_block.info_celery_you_can_exit') }}
          </span>
          <button v-if="currentStep > 0" @click="prevStep"
            class="flex items-center gap-2 rounded bg-gray-200 px-4 py-2 text-gray-700 transition-colors hover:bg-gray-300 disabled:opacity-50"
            :title="$t('billing_block.go_prev_step')">
            <Icon name="fa6-solid:chevron-left" /> {{ $t('common.previous') }}
          </button>
          <div class="flex space-x-4">
            <button v-if="currentStep == 0 && !filteringTaskId" @click="getDeliquencyData"
              class="button-default flex items-center gap-2" :title="$t('common.search')" :disabled="!allowSearch">
              {{ $t('common.search') }}
              <Icon name="fa6-solid:magnifying-glass" />
            </button>
            <AtomsProcessColorBadge class="w-fit flex items-center gap-x-2" v-if="currentStep == 0 && filteringTaskId"
              @refresh="refreshData" @error="onSearchTaskError" :value="t('common.loading')" :color="'blue'"
              :taskId="filteringTaskId" />
            <button v-if="currentStep < 1" @click="nextStep"
              class="flex items-center gap-2 rounded bg-sky-600 px-4 py-2 text-white transition-colors hover:bg-sky-700 disabled:cursor-not-allowed disabled:opacity-50"
              :title="$t('billing_block.go_next_step')" :disabled="contracts.length == 0 || !!filteringTaskId">
              {{ $t('common.next') }}
              <Icon name="fa6-solid:chevron-right" />
            </button>
            <button v-if="currentStep === 1 && !savingTaskId" @click="openConfirm"
              :disabled="saving || totalSelectedInvoices === 0"
              class="flex items-center gap-2 rounded bg-sky-600 px-4 py-2 text-white transition-colors hover:bg-sky-700 disabled:cursor-not-allowed disabled:opacity-50"
              :title="$t('common.save')">
              <Icon name="fa6-solid:floppy-disk" /> {{ $t('common.save') }}
            </button>
            <AtomsProcessColorBadge class="w-fit flex items-center gap-x-2" v-if="currentStep === 1 && savingTaskId"
              @refresh="onSaveTaskDone" @error="onSaveTaskError" :value="t('common.loading')" :color="'blue'"
              :taskId="savingTaskId" />
          </div>
        </div>
      </div>
    </div>

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
      </div>
    </div>

    <Teleport to="body">
      <div v-if="showConfirm">
        <div class="fixed inset-0 bg-black bg-opacity-50 z-[10000]" @click="closeConfirm" />
        <div class="fixed inset-0 z-[10001] flex items-center justify-center overflow-y-auto p-4" role="dialog"
          aria-modal="true" @click="closeConfirm">
          <div class="bg-white rounded-lg shadow-xl p-6 max-w-lg w-full relative" @click.stop>
            <button type="button" class="absolute top-4 right-4 text-gray-500 hover:text-gray-700"
              :aria-label="$t('common.cancel')" @click="closeConfirm">
              <Icon name="fa6-solid:xmark" class="text-xl" />
            </button>

            <i18n-t keypath="confirmation_text_block.confirm_deliquency_status" tag="p"
              class="pr-6 font-medium leading-relaxed text-slate-700">
              <template #status>
                <strong class="font-bold text-slate-900">{{ targetStatusLabel }}</strong>
              </template>
            </i18n-t>
            <p class="text-sm text-slate-500 mt-2">
              {{ $t('warning_block.warning_irreversible') }}
            </p>

            <div class="mt-4 grid grid-cols-3 gap-3 text-center">
              <div>
                <div class="text-lg font-bold text-sky-700">{{ activeContractsSummary.contractsCount }}</div>
                <div class="text-xs text-slate-500">{{ $t('common.contracts') }}</div>
              </div>
              <div>
                <div class="text-lg font-bold text-sky-700">{{ totalSelectedInvoices }}</div>
                <div class="text-xs text-slate-500">{{ $t('invoices') }}</div>
              </div>
              <div>
                <div class="text-lg font-bold text-sky-700">{{ formatMoney(activeContractsSummary.totalAmount) }} €
                </div>
                <div class="text-xs text-slate-500">{{ $t('common.amount') }}</div>
              </div>
            </div>

            <div class="mt-5 grid gap-2" :class="allowEndowmentTarget ? 'grid-cols-2' : 'grid-cols-1'">
              <label v-if="allowEndowmentTarget"
                class="flex cursor-pointer items-center gap-2.5 rounded-lg border border-slate-200 px-3 py-2.5 text-sm text-slate-700 transition-colors hover:border-slate-300 hover:bg-slate-50 has-[:checked]:border-sky-600 has-[:checked]:bg-sky-50 has-[:checked]:text-sky-950">
                <input type="radio" name="deliquency-target-status"
                  class="h-4 w-4 border-slate-300 text-sky-600"
                  :value="endowmentToken" v-model="targetStatusToken" />
                <span class="font-medium leading-snug">{{ $t('contract_block.endowment') }}</span>
              </label>
              <label
                class="flex cursor-pointer items-center gap-2.5 rounded-lg border border-slate-200 px-3 py-2.5 text-sm text-slate-700 transition-colors hover:border-slate-300 hover:bg-slate-50 has-[:checked]:border-sky-600 has-[:checked]:bg-sky-50 has-[:checked]:text-sky-950">
                <input type="radio" name="deliquency-target-status"
                  class="h-4 w-4 border-slate-300 text-sky-600"
                  :value="irrecoverableToken" v-model="targetStatusToken" />
                <span class="font-medium leading-snug">{{ $t('billing_block.irrecoverable_invoice') }}</span>
              </label>
            </div>

            <div class="flex justify-end gap-2 mt-6">
              <button type="button" class="button-default" @click="closeConfirm" :disabled="saving">
                {{ $t('common.cancel') }}
              </button>
              <button type="button" class="button-primary" @click="save"
                :disabled="saving || targetStatusToken == null">
                <Icon v-if="saving" name="fa6-solid:spinner" class="animate-spin" />
                {{ $t('common.confirm') }}
              </button>
            </div>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>
