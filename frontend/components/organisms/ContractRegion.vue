<script setup>
// components/organisms/ClusterDetail.vue
import { ref, resolveDirective, watch, computed } from 'vue';
import { useRouter } from 'vue-router';
import { openAuthenticatedFileUrl } from '~/utils/open-authenticated-file';
import { formatDate } from '~/utils/date';
import { useI18n } from 'vue-i18n';
import { useToast } from 'vue-toastification';
import H1Region from '~/components/atoms/H1Region.vue';
import { useFixedObjectsStore } from '~/stores/useFixedObjects';
import ContractActionsDropdown from '~/components/molecules/ContractActionsDropdown.vue';
import ContractTabs from '~/components/organisms/ContractTabs.vue';
import { useSidebarStore } from '~/stores/useNavSideBar';
// Importar el component SupplyPointRegion per a la subregion
import ContractDetail from '../molecules/ContractDetail.vue';
import AddInvoiceBudget from '../molecules/AddInvoiceBudget.vue';
import PriceRateRegionDetail from './PriceRateRegionDetail.vue';
import MeterRegion from './MeterRegion.vue';
import PriceIntervalRegion from './PriceIntervalRegion.vue';
import { mergeContractModifications } from '~/utils/contractDataChangeDisplay';
import InvoiceRegion from './InvoiceRegion.vue';
import OrderRegion from './OrderRegion.vue';
import VulnerabilityRequestIndividualEdit from './VulnerabilityRequestIndividualEdit.vue';
import ProductRegion from './ProductRegion.vue';
import CommitmentDepositRegion from './CommitmentDepositRegion.vue';
import IncidentEdit from '../molecules/IncidentEdit.vue';
import IncidentRegion from './IncidentRegion.vue';
import CommunicationRegion from './CommunicationRegion.vue';
import CalendarTaskEdit from '../molecules/CalendarTaskEdit.vue';
import AdjustmentRegion from './AdjustmentRegion.vue';
import PiggyBankRegion from './PiggyBankRegion.vue';
import AddPiggyBankBalance from '../molecules/AddPiggyBankBalance.vue';
import AddReading from '../molecules/AddReading.vue';
import EstimatedBagRegion from './EstimatedBagRegion.vue';
import AddNewCall from '../molecules/AddNewCall.vue';
import AppLoading from '~/components/atoms/AppLoading.vue';
import TypedConfirmationModal from '../molecules/TypedConfirmationModal.vue';
import MassiveInvoiceDownload from './MassiveInvoiceDownload.vue';
import ContractClausesEdit from '../molecules/ContractClausesEdit.vue';
import { usePermissions } from '~/middleware/permission';


const { t } = useI18n();
const toast = useToast();
const sidebarStore = useSidebarStore();
const fixedObjectsStore = useFixedObjectsStore();
const props = defineProps({
  id: Number, // ID de l'element
  isSubRegion: {
    type: Boolean,
    default: false
  },
  isSubRegionOpen: Boolean
});
const { permissions, loading } = usePermissions();
const emit = defineEmits(['show-subregion', 'close-subregion', 'changed']);
const router = useRouter();
const { $ContractApiService, $LoggerApiService, $DocumentManagerApiService, $InvoiceApiService, $VulnerabilityRequestApiService, $ConfigProjectApiService } = useNuxtApp();
const pending = ref(true);
const error = ref(null);
const data = ref(null);
const reload = ref(false);
const activeTab = ref('observations');
const invoiceActiveTab = ref('invoice_invoices');
const SubRegion = ref(props.isSubRegionOpen);

const supplyCutAlert = computed(() => data.value?.supply_point_default?.supply_cut_alert || null);

const showConfirmationModal = ref(false);

const observationNumber = ref(0)
const callRegisterNumber = ref(0)
const incidentNumber = ref(0)
const changesNumber = ref(0)
const contractChangeNumber = ref(0)

const commitmentDepositsNumbers = ref(0)
const claimRequestNumbers = ref(0)
const bonVarChangesNumber = ref(0)
const communicationNumber = ref(0)
const orderNumber = ref(0)

const surrogations = ref([])
const tenant_changes = ref([])
const data_changes = ref([])
const members_change = ref([])
const contract_phones_logs = ref([])
const contract_logs = ref([])

const allModifications = computed(() =>
  mergeContractModifications(data_changes.value, members_change.value, contract_phones_logs.value)
)

const expired_variables = ref(null)
const expired_bonifications = ref(null)
const invoices = ref([])
const general_invoices = ref([])
const invoicesLoading = ref(false)
const invoicesPagination = ref({
  page: 1,
  perPage: 50,
  total: 0,
  totalPages: 0,
  isFiltered: true,
})

const important_observations = ref([])
const show_important_observations = ref(false)
const new_call = ref(null)

const person_ids = ref([])
const terminatedStatusToken = ref(null)

const selectedCustomInvoice = ref(null);
const invoiceTypeToken = ref(null)

const isPinned = ref(false)
const isChecked = ref(false)
const username = ref(null)
const objectPermissions = ref(null);

const groupedPriceRates = computed(() => {
  if (!data.value || !data.value.show_price_rates) return {};
  return data.value.show_price_rates.reduce((acc, rate) => {
    let spToken = 'N/A';
    if (rate.supply_point && rate.supply_point.token) spToken = rate.supply_point.token;
    else if (rate.product && rate.product.supply_point && rate.product.supply_point.token) spToken = rate.product.supply_point.token;
    else if (rate.supply_point_token) spToken = rate.supply_point_token;
    else if (data.value && data.value.supply_point && data.value.supply_point.token) spToken = data.value.supply_point.token;
    else if (data.value && data.value.supply_point_default && data.value.supply_point_default.token) spToken = data.value.supply_point_default.token;
    else spToken = t('common.unknown') || 'Sense punt de subministrament';

    if (!acc[spToken]) {
      acc[spToken] = [];
    }
    acc[spToken].push(rate);
    return acc;
  }, {});
});

if (process.client) {
  username.value = localStorage.getItem('user_username') || '';
}

const updateObservationCount = (num) => {
  observationNumber.value = num;
}

const updateCallRegisterCount = (num) => {
  callRegisterNumber.value = num;
}

const updateIncidentCount = (num) => {
  incidentNumber.value = num;
}

const updateCommitmentDepositsNumbers = (num) => {
  commitmentDepositsNumbers.value = num;
}

const updateClaimRequestNumbers = (num) => {
  claimRequestNumbers.value = num;
}

const updateCommunicationCount = (num) => {
  communicationNumber.value = num;
}

const updateOrderCount = (num) => {
  orderNumber.value = num;
}

const updateBonificationVariableChangeCount = (num) => {
  bonVarChangesNumber.value = num;
}

const loadedTabs = ref(new Set(['observations'])); // Observations is active by default usually, but let's check activeTab init

const loadTabData = async (tab) => {
  if (loadedTabs.value.has(tab)) return;

  if (tab === 'invoices' && permissions?.value.permissions?.view_billing) {
    await loadInvoices();
  } else if (tab === 'dataChange') {
    await getMembersChange();
  } else if (tab === 'bonifications' || tab === 'variables') {
    await getExpiredVariables();
  }

  loadedTabs.value.add(tab);
}

const getPermissions = async () => {
  error.value = null;
  try {
    const data = await $ContractApiService.getPermissions();
    objectPermissions.value = data;
  } catch (err) {
    error.value = err;
  }
}

const getData = async (load = true) => {
  if (!objectPermissions.value?.can_view) {
    toast.error(t('common.no_permissions'));
    emit('close-subregion');
    return;
  };
  if (load) pending.value = true;

  try {
    terminatedStatusToken.value = await $ConfigProjectApiService.get('contract_terminated_status');

    const result = await $ContractApiService.getDetail(props.id);
    data.value = result;

    important_observations.value = [...result.important_observations, ...result.person_important_observations];


    isPinned.value = result?.user_pinned?.username == username.value;
    isChecked.value = result?.user_checked?.some(user => user.username === username.value);

    surrogations.value = result.surrogations?.reverse() || [];
    tenant_changes.value = result.tenant_changes?.reverse() || [];
    data_changes.value = result.data_changes?.reverse() || [];
    contractChangeNumber.value = data_changes.value.length;
    if (activeTab.value === 'dataChange') {
      await getMembersChange();
    } else {
      getMembersChange();
    }

    observationNumber.value = result.observations_count || 0;
    callRegisterNumber.value = result.calls_count || 0;
    incidentNumber.value = result.incidents_count || result.incidents || 0;
    communicationNumber.value = result.communications_count || 0;
    orderNumber.value = result.orders_count || 0;
    bonVarChangesNumber.value = result.bon_var_changes_count || 0;

    changesNumber.value = result.surrogations_count || result.surrogations?.length || 0;

    // Defer these calls to loadTabData triggered by tab selection
    // getMembersChange();
    // getExpiredVariables();
    // if (permissions?.value.permissions?.view_billing) {
    //   loadInvoices();
    // }

    // Initial load for active tab if needed
    nextTick(() => {
      loadTabData(activeTab.value);
    });
    if (data.value.holder && !person_ids.value.includes(data.value.holder.id)) {
      person_ids.value.push(data.value.holder.id)
    }
    if (data.value.tenant && !person_ids.value.includes(data.value.tenant.id)) {
      person_ids.value.push(data.value.tenant.id)
    }
    if (data.value.owner && !person_ids.value.includes(data.value.owner.id)) {
      person_ids.value.push(data.value.owner.id)
    }
    if (data.value.representatives && data.value.representatives.length > 0 && !person_ids.value.includes(data.value.representatives.map(representative => representative.person.id))) {
      person_ids.value.push(...data.value.representatives.map(representative => representative.person.id))
    }
    selectedCustomInvoice.value = {
      id: props.id,
      title: '',
      label: `${data.value.token} - ${data.value.holder.full_name} (${data.value.holder.token})`,
      general_invoice: data.value.general_invoice ? true : false,
      period_days: data?.value?.billing_period_days || 0,
      entity: 'contract',
    }

  } catch (err) {
    console.error(err);
  } finally {
    pending.value = false;
  }
}

const getExpiredVariables = async () => {
  try {
    const result = await $LoggerApiService.getAll("contract-expired-bonifications-variables", props.id);
    expired_variables.value = getLatestByToken(result.results);
    expired_bonifications.value = result.results.filter(item => item.expired_bonification)
  } catch (error) {
    console.error(error);
  }
}

const loadInvoices = async () => {
  invoicesLoading.value = true;
  try {
    await Promise.all([getInvoices(), getGeneralInvoices()]);
  } finally {
    invoicesLoading.value = false;
  }
}

const getInvoices = async (page = 1) => {
  invoices.value = []
  try {
    const result = await $InvoiceApiService.getInvoicesFromContract(props.id, false, true, page);
    invoices.value = result.results;

    if (data.value.request_invoices.length > 0) {
      data.value.request_invoices.forEach(reqInvoice => {
        if (!invoices.value.some(inv => inv.id === reqInvoice.id)) {
          invoices.value.push(reqInvoice);
        }
      });
    }

    invoicesPagination.value.page = page;
    invoicesPagination.value.total = result.count || 0;
    invoicesPagination.value.totalPages = Math.ceil((result.count || 0) / invoicesPagination.value.perPage);
  } catch (error) {
    console.error(error);
  }
}

const onInvoicesPageChange = (newPage) => {
  getInvoices(newPage);
}

const getGeneralInvoices = async () => {
  general_invoices.value = []
  try {
    const result = await $InvoiceApiService.getGeneralInvoicesFromContract(props.id);
    general_invoices.value = result.results.filter(invoice => invoice.type_final == invoiceTypeToken.value);
    //general_invoices.value = result.results;

  } catch (error) {
    console.error(error);
  }
}

// Update a single invoice's PDF template in-place so the "send" button reactivates
// without reloading the whole invoice list.
const onInvoicePdfGenerated = ({ id, invoice_file_template }) => {
  const invoiceId = parseInt(id);
  [invoices.value, general_invoices.value].forEach(list => {
    const item = (list || []).find(inv => inv.id === invoiceId);
    if (item) item.invoice_file_template = invoice_file_template;
  });
}

const getLatestByToken = (items) => {
  return Object.values(
    items.reduce((acc, item) => {
      if (!acc[item.token] || new Date(item.updated_at) > new Date(acc[item.token].updated_at)) {
        acc[item.token] = item;
      }
      return acc;
    }, {})
  );
};

const getMembersChange = async () => {
  members_change.value = []
  contract_phones_logs.value = []
  contract_logs.value = []
  try {
    const [membersResult, phonesResult, logsResult] = await Promise.all([
      $LoggerApiService.getAll('contract-total-members', props.id),
      $LoggerApiService.getAll('contract-phones', props.id),
      $ContractApiService.getLogs(props.id),
    ]);
    members_change.value = membersResult.results || []
    contract_phones_logs.value = phonesResult.results || []
    contract_logs.value = Array.isArray(logsResult) ? logsResult : (logsResult?.results || [])
    // No sumar data_changes del getLogs (source=data_change): ja estan a allModifications
    const rawLogCount = contract_logs.value.filter((l) => l.source !== 'data_change').length
    contractChangeNumber.value = allModifications.value.length + rawLogCount
  } catch (error) {
    console.log(error);
  }
}

const surrogate = () => {
  return router.push(`/contract/contracts/${props.id}/surrogate`);
}

const tenantChange = () => {
  return router.push(`/contract/contracts/${props.id}/change-tenant`);
}

const terminate = () => {
  return router.push(`/contract/contract-terminations/add?contract=${props.id}`);
}

const changeBonifications = () => {
  return router.push(`/contract/contracts/${props.id}/bonifications`);
}

const changePriceRates = () => {
  return router.push(`/contract/contracts/${props.id}/price-rates`);
}

const dataChange = () => {
  return router.push(`/contract/contracts/${props.id}/data-change`);
}

const modifyReadings = () => {
  return router.push(`/contract/contracts/${props.id}/reading-change`);
}

const cutSupplyPoint = () => {
  return navigateTo({
    path: '/service/supply-cut/add',
    query: {
      action: 'CONTRACT',
      contract: props.id
    }
  })
}

const newCommunicationProcess = () => {
  return navigateTo({
    path: '/communication/process-communications/add',
    query: {
      contract_id: props.id,
    }
  })
}

const newCommunication = () => {
  return navigateTo({
    path: '/communication/communications/add',
    query: {
      step: 1,
      contract_id: props.id,
    }
  })
}

const toggleBillable = async () => {

  const txt = data.value.block_billing ? t('contract_block.mark_as_billable') : t('contract_block.mark_as_unbillable')

  if (confirm(t('confirmation_text_block.confirm_base') + ' ' + txt.toLowerCase() + '?')) {
    const res = await $ContractApiService.toggleBillable(props.id);

    data.value.block_billing = res.block_billing;
  }
}

const generateContract = async () => {
  const contract = await $ContractApiService.getDocument(props.id, true);
  await openAuthenticatedFileUrl(contract.pdf_url);
}

watch(() => props.id, async () => {
  // When the same ContractRegion instance is reused with a different id
  // (e.g. opening contracts from ReadingBatchSummary), clear lazy-loaded
  // tab state so invoices/etc. are fetched for the new contract.
  loadedTabs.value = new Set(['observations']);
  invoices.value = [];
  general_invoices.value = [];
  invoicesPagination.value = {
    page: 1,
    perPage: invoicesPagination.value.perPage || 50,
    total: 0,
    totalPages: 0,
    isFiltered: true,
  };
  members_change.value = [];
  contract_phones_logs.value = [];
  contract_logs.value = [];
  expired_variables.value = null;
  expired_bonifications.value = null;

  await getPermissions();
  if (objectPermissions.value?.can_view) {
    await getData();
    show_important_observations.value = important_observations.value.length > 0;
  } else {
    toast.error(t('common.no_permissions'));
    emit('close-subregion');
  }
  closeSubRegion();
});

watch(() => props.isSubRegionOpen, (newValue) => {
  SubRegion.value = newValue;
});

onMounted(async () => {
  await getPermissions();
  if (objectPermissions.value?.can_view) {
    invoiceTypeToken.value = await $ConfigProjectApiService.get('invoice_type_invoice_token');
    await getData();
    show_important_observations.value = important_observations.value.length > 0;
  } else {
    toast.error(t('common.no_permissions'));
    emit('close-subregion');
  }
});

const handleSubRegionEvent = (event) => {
  if (event || showRegionDetailComponent.value) {
    emit('show-subregion', true);
  } else {
    emit('show-subregion', false);
  }
}

const closeSubRegion = function () {
  SubRegion.value = false;
  showRegionDetailComponent.value = null;
  emit('show-subregion', false);
}


const showSubRegion = function () {
  SubRegion.value = true;
  emit('show-subregion', true);
}

// subregions details
const showRegionDetailComponent = ref(null);
const regionDetailId = ref(null);

const showDetail = function (component, id) {
  showRegionDetailComponent.value = component.id ? component.component : component;
  regionDetailId.value = component.id ? component.id : id;
  showSubRegion();
}

const requestVulnerability = async () => {

  if (confirm(t('confirmation_text_block.confirm_create_vulnerability_request'))) {
    let save_data = {
      contract_id: props.id,
    }
    try {
      let response = await $VulnerabilityRequestApiService.save(save_data);
      if (response) {
        toast.success(t('informative_block.info_all_vuln_requested') + ' ' + data.value.token)
        return navigateTo({
          path: '/billing/vulnerability-requests',
          query: {
            id: response.id
          }
        })
      } else {
        console.error(t('common.error'));
      }
    } catch (error) {
      console.error(error.message)
    }
  }
}

const pinObject = async () => {
  try {
    let save_date = {
      id: props.id,
      is_pinned: !isPinned.value

    }
    if (save_date.is_pinned) {
      fixedObjectsStore.setCurrentPinnedContractId(props.id);
    } else {
      fixedObjectsStore.clearCurrentPinnedContract();
    }
    isPinned.value = !isPinned.value;
    if (isPinned.value) isChecked.value = true;
    let contract = await $ContractApiService.save(save_date)
    if (isPinned.value) {
      save_date.is_checked = true;
      data.value.is_checked = true;
      await nextTick();
      return router.push(`/contract/contracts/${props.id}/pinned/`);
    }
    handleChange()
  } catch (err) {
    console.error(err)
  }
}

const checkObject = async () => {
  try {
    let save_date = {
      id: props.id,
      is_checked: !data.value.is_checked
    }
    data.value.is_checked = !data.value.is_checked;
    let contract = await $ContractApiService.save(save_date)
    handleChange()
  } catch (err) {
    console.error(err)
  }
}

const startCall = async (item) => {
  new_call.value = {
    contact: item,
    contract: data.value
  };
}


const newClaimRequest = async () => {
  return navigateTo({
    path: '/billing/claim-managements/add',
    query: {
      contract_id: props.id,
      contract_token: data.value.token
    }
  })
}

const handleNewCall = () => {
  new_call.value = null;
  handleChange(false);
}

const handleChange = async (close = true) => {
  let currentTab = activeTab.value;
  if (close) closeSubRegion();
  setActiveTab(null);
  await getData(false);
  reload.value = !reload.value;
  setActiveTab(currentTab);
  emit('changed');
}

const showPinnedContract = () => {
  sidebarStore.togglePinnedContract();
}

const updateItem = (item) => {
  data.value = item;
}


const showDeleteContractConfirmation = () => {
  showConfirmationModal.value = true;
}

const deleteContract = async () => {
  // if (!confirm(`${t('confirmation_text_block.confirm_delete')} ${t('warning_block.warning_can_not_undo')}`)) return
  try {
    await $ContractApiService.doDelete(data.value);
    emit('changed', true);
  } catch (error) {
    console.error(error);
  }
}

const manageGeneralInvoices = () => {
  let gen_id = data.value.general_invoice || '';
  return navigateTo(`/contract/contracts/${props.id}/general-invoices/?id=${gen_id}`);
}
const setActiveTab = (tab) => {
  activeTab.value = tab;
  if (tab) loadTabData(tab);
}

const setInvoiceActiveTab = (tab) => {
  invoiceActiveTab.value = tab;
}

const addWalletBalance = () => {
  showDetail('AddPiggyBankBalance', props.id);
}


</script>

<template>
  <div class="region__content h-full">
    <div v-if="pending || loading" class="h-full min-h-[400px]">
      <AppLoading :text="$t('common.loading')" />
    </div>
    <div v-else-if="error"
      class="flex flex-col items-center justify-center h-full min-h-[400px] text-center p-6 bg-red-50 rounded-xl m-4 border border-red-100">
      <Icon name="fa6-solid:circle-exclamation" class="text-red-400 text-5xl mb-4" />
      <p class="text-red-800 font-semibold mb-2">Error: {{ error.message }}</p>
      <button @click="getData"
        class="bg-white px-6 py-2 rounded-full shadow-sm border border-red-200 text-red-600 hover:bg-red-50 transition-colors font-medium">
        {{ $t('common.load_again') }}
      </button>
    </div>
    <div v-else-if="objectPermissions?.can_view" class="pr-2 relative pb-24 transition-all duration-500 ease"
      :class="{ 'h-full overflow-y-auto': !isSubRegion, 'mr-[48vw]': SubRegion }">
      <div v-if="show_important_observations"
        class="fixed inset-0 z-50 flex items-center justify-center overflow-y-auto">
        <div class="bg-white rounded-lg shadow-xl p-6 max-w-lg w-full mx-4 my-auto relative">
          <button @click="show_important_observations = false"
            class="absolute top-4 right-4 text-gray-500 hover:text-gray-700">
            <Icon name="fa6-solid:xmark" class="text-xl" />
          </button>
          <div class="text-center">
            <div class="mb-4">
              <Icon name="fa6-solid:circle-exclamation" class="text-yellow-500 text-4xl mb-3" />
              <!-- <h2 class="text-xl font-bold text-gray-800 mb-2">{{ $t('Observacions importants') }}</h2> -->
            </div>
            <div class="bg-yellow-50 p-4 rounded-lg text-left max-h-[60vh] overflow-y-auto">
              <ul class="list-disc list-inside space-y-2">
                <li v-for="observation in important_observations" :key="observation.id" class="text-gray-700">
                  {{ observation.observation }}
                </li>
              </ul>
            </div>
          </div>
        </div>
      </div>


      <TypedConfirmationModal v-model:open="showConfirmationModal"
        :message="t('confirmation_text_block.confirm_delete_contract')"
        :expected-phrase="t('confirmation_phrase_block.delete_contract')" @confirm="deleteContract" />

      <div v-if="new_call" class="fixed inset-0 z-50 flex items-center justify-center">
        <div class="bg-white rounded-lg shadow-xl p-6 max-w-lg w-full mx-4 my-auto relative">
          <AddNewCall :data="new_call" @exit="handleNewCall" />
        </div>
      </div>

      <!-- If done otherwhise, black bg does not occupy the whole screen :C -->
      <div v-if="show_important_observations || new_call"
        class="fixed inset-0 bg-black bg-opacity-50 h-[120vh] z-30 flex items-center justify-center">
      </div>


      <div class="flex justify-between relative">
        <div class="flex items-center mb-3 gap-5">
          <H1Region class="">{{ $t('contract') }}</H1Region>
        </div>

        <div>
          <div class="flex items-center gap-0" style="margin-right: 40px;">
            <button v-if="isPinned" class="group" @click="showPinnedContract">
              <kbd
                class="px-1 py-1.5 text-xs font-light text-slate-400 bg-white group-hover:bg-slate-100 border border-gray-200 rounded-lg">
                Ctrl p</kbd>
            </button>
            <button @click="pinObject" class="flex items-center justify-center px-4 py-[5px]">
              <Icon name="ic:sharp-push-pin" class="w-4 h-4" :class="{
                'text-red-500 hover:bg-red-900': isPinned,
                'text-slate-500 hover:text-sky-500': !isPinned
              }" />
            </button>

            <button @click="checkObject" class="group flex items-center justify-center px-4 py-[5px]">
              <Icon :name="isChecked ? 'fa6-solid:flag' : 'fa6-regular:flag'" class="w-3.5 h-3.5" :class="{
                'text-red-500 group-hover:bg-red-900': isChecked,
                'text-slate-500 group-hover:text-sky-500': !isChecked
              }" />
            </button>
          </div>

          <ContractActionsDropdown v-if="objectPermissions?.can_change" :contract="data" :canChange="objectPermissions?.can_change"
            :terminatedStatusToken="terminatedStatusToken" :personIds="person_ids"
            @show-detail="showDetail" @change="handleChange"
            @delete-click="showDeleteContractConfirmation" />
        </div>
      </div>

      <div v-if="data" id="item_data" :data-rel=id>

        <div v-if="supplyCutAlert" role="alert" class="mb-2">
          <div class="flex items-center gap-3 w-full rounded-lg border border-amber-300 bg-amber-50 px-3 py-1 shadow-sm">
            <div class="flex h-4 w-4 shrink-0 items-center justify-center text-amber-700">
              <Icon name="fa6-solid:scissors" class="text-sm" />
            </div>
            <div class="min-w-0 flex-1 flex flex-wrap items-center gap-x-2 gap-y-1">
              <span class="text-sm font-semibold text-amber-900 leading-snug">
                {{ $t('service_block.supply_cut_notice') }}
              </span>
              <span class="text-sm text-amber-800 leading-snug">
                {{ supplyCutAlert.status_name }}
                ({{ supplyCutAlert.temporary ? $t('service_block.cut_temporary') : $t('service_block.cut_indefinite') }})
              </span>
              <span v-if="supplyCutAlert.date_end" class="text-sm text-amber-800 leading-snug">
                &middot; {{ $t('service_block.until') }} {{ formatDateTime(supplyCutAlert.date_end) }}
              </span>
            </div>
          </div>
        </div>

        <ContractDetail :data="data" @show-subregion="showDetail" :isSubRegion="isSubRegion"
          :canChange="objectPermissions?.can_change" :isSubRegionOpen="isSubRegionOpen" @change="handleChange"
          :showImportantObservations="false" @new-call="startCall" />

        <ContractTabs
          :contract="data"
          :isPinned="false"
          :isSubRegion="isSubRegion"
          :activeTab="activeTab"
          :observationNumber="observationNumber"
          :callRegisterNumber="callRegisterNumber"
          :reload="reload"
          :incidentNumber="incidentNumber"
          :communicationNumber="communicationNumber"
          :orderNumber="orderNumber"
          :bonVarChangesNumber="bonVarChangesNumber"
          :changesNumber="changesNumber"
          :contractChangeNumber="contractChangeNumber"
          :surrogations="surrogations"
          :tenant_changes="tenant_changes"
          :data_changes="data_changes"
          :members_change="members_change"
          :all-modifications="allModifications"
          :contract_logs="contract_logs"
          :expired_variables="expired_variables"
          :expired_bonifications="expired_bonifications"
          :invoices="invoices"
          :invoices_count="data ? data.invoices_count : 0"
          :general_invoices="general_invoices"
          :invoicesLoading="invoicesLoading"
          :invoicesPagination="invoicesPagination"
          :person_ids="person_ids"
          :permissions="permissions"
          :canChange="objectPermissions?.can_change"
          @show-detail="showDetail"
          @change="handleChange(false)"
          @update-active-tab="setActiveTab"
          @update:observation-count="updateObservationCount"
          @update:call-register-count="updateCallRegisterCount"
          @update:incident-count="updateIncidentCount"
          @update:communication-count="updateCommunicationCount"
          @update:order-count="updateOrderCount"
          @update:bonification-variable-change-count="updateBonificationVariableChangeCount"
          @update-invoices-page="onInvoicesPageChange" />
      </div><!-- end if data -->
    </div><!-- end if pending -->

    <div v-if="SubRegion == true" role="region" id="subregion"
      class="h-full border-l border-gray-100 text-base bg-white flex flex-col overflow-hidden fixed top-0 w-[48vw] z-50 transition-[right] duration-500 ease"
      :class="SubRegion ? 'right-0' : 'right-[-48vw]'">
      <div id="region_nav" class="mb-3 px-3">
        <button @click="closeSubRegion()" class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300">
          <Icon name="fa6-solid:angles-right" class="text-slate-500" />
        </button>
      </div>
      <div class="pl-10 flex-1 overflow-y-auto pb-24 pr-2">
        <OrganismsPersonRegion v-if="showRegionDetailComponent === 'PersonRegion'" :id="regionDetailId"
          :isSubRegion="true" @close-subregion="closeSubRegion" />
        <OrganismsSupplyPointRegion v-if="showRegionDetailComponent === 'SupplyPointRegion'"
          :id="parseInt(regionDetailId)" :isSubRegion="true" @close-subregion="closeSubRegion" />
        <MeterRegion v-if="showRegionDetailComponent === 'MeterRegion'" :id="regionDetailId" :isSubRegion="true"
          @close-subregion="closeSubRegion" />
        <ProductRegion v-if="showRegionDetailComponent === 'ProductRegion'" :id="regionDetailId" :isSubRegion="true"
          @close-subregion="closeSubRegion" />
        <PriceRateRegionDetail v-if="showRegionDetailComponent === 'PriceRateRegion'" :id="parseInt(regionDetailId)"
          :isSubRegion="true" @close="closeSubRegion" />
        <PriceIntervalRegion v-if="showRegionDetailComponent === 'PriceIntervalRegion'" :id="parseInt(regionDetailId)"
          :isSubRegion="true" />
        <IncidentRegion v-if="showRegionDetailComponent === 'IncidentRegion'" :id="parseInt(regionDetailId)"
          :isSubRegion="true" />
        <OrderRegion v-if="showRegionDetailComponent === 'OrderRegion'" :id="parseInt(regionDetailId)"
          :isSubRegion="true" />
        <CommunicationRegion v-if="showRegionDetailComponent === 'CommunicationRegion'" :id="parseInt(regionDetailId)"
          :isSubRegion="true" @show-subregion="handleSubRegionEvent" @changed="handleChange" />
        <CommitmentDepositRegion v-if="showRegionDetailComponent === 'CommitmentDepositRegion'"
          :id="parseInt(regionDetailId)" :isSubRegion="true" />
        <InvoiceRegion v-if="showRegionDetailComponent === 'InvoiceRegion'" :id="regionDetailId" :isSubRegion="true"
          @update-id="(newId) => regionDetailId = newId" @changed="handleChange(false)"
          @pdf-generated="onInvoicePdfGenerated" />
        <VulnerabilityRequestIndividualEdit v-if="showRegionDetailComponent == 'VulnerabilityRequestRegion'"
          :vulnerability_id="parseInt(regionDetailId)" :isSubRegionOpen="isSubRegionOpen" :isSubRegion="true" />
        <IncidentEdit v-if="showRegionDetailComponent == 'IncidentEdit'" :contract_id="regionDetailId"
          @change="handleChange" />
        <CalendarTaskEdit v-if="showRegionDetailComponent === 'CalendarTaskEdit'" :id="regionDetailId"
          :object_id="props.id" :object_service="$ContractApiService" @change="handleChange" />
        <AdjustmentRegion v-if="showRegionDetailComponent === 'AdjustmentRegion'" :id="parseInt(regionDetailId)"
          :isSubRegion="true" />
        <PiggyBankRegion v-if="showRegionDetailComponent === 'PiggyBankRegion'" :id="parseInt(regionDetailId)"
          :isSubRegion="true" :canChange="objectPermissions?.can_change" @changed="handleChange(false)" />
        <AddPiggyBankBalance v-if="showRegionDetailComponent === 'AddPiggyBankBalance'"
          :contractId="parseInt(regionDetailId)" :data="data.piggy_bank" @change="handleChange"
          @close="closeSubRegion" />
        <AddReading v-if="showRegionDetailComponent === 'AddReading'" :contract="data" :contract_ids="[props.id]"
          :isSubRegion="true" />
        <EstimatedBagRegion v-if="showRegionDetailComponent === 'EstimatedBagRegion'" :id="parseInt(regionDetailId)"
          :isSubRegion="true" />
        <AddInvoiceBudget v-if="showRegionDetailComponent === 'AddInvoiceBudget'" :isSubRegion="true"
          :object_id="props.id" :service="$ContractApiService" :entity="'custom'" :persons="[data.holder]"
          :individual="true" :selectedCustom="selectedCustomInvoice" @change="handleChange"
          @show-subregion="handleSubRegionEvent" @close="closeSubRegion" />
        <MassiveInvoiceDownload v-if="showRegionDetailComponent === 'MassiveInvoiceDownload'"
        :contract_id="parseInt(props.id)" />
        <ContractClausesEdit v-if="showRegionDetailComponent === 'ContractClausesEdit'" :contract="data"
          @change="handleChange(false)" />
      </div>
    </div>
  </div><!-- end region__content -->
</template>
