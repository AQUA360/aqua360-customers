<script setup>
import ContractInvalidAccountAlert from '~/components/molecules/ContractInvalidAccountAlert.vue';
import { useFixedObjectsStore } from '~/stores/useFixedObjects';
import { useToast } from 'vue-toastification';
import { openAuthenticatedFileUrl } from '~/utils/open-authenticated-file';
import { formatDateTime } from '~/utils/date';
import H1Region from '~/components/atoms/H1Region.vue';
import AppLoading from '~/components/atoms/AppLoading.vue';
import ContractDetail from '~/components/molecules/ContractDetail.vue';
import { checkPermission } from '~/middleware/permission';
import ContractActionsDropdown from '~/components/molecules/ContractActionsDropdown.vue';
import ContractTabs from '~/components/organisms/ContractTabs.vue';
import { mergeContractModifications } from '~/utils/contractDataChangeDisplay';

/* REGIONS */
import PersonRegion from '~/components/organisms/PersonRegion.vue';
import SupplyPointRegion from '~/components/organisms/SupplyPointRegion.vue';
import MeterRegion from '~/components/organisms/MeterRegion.vue';
import CommunicationRegion from '~/components/organisms/CommunicationRegion.vue';
import ProductRegion from '~/components/organisms/ProductRegion.vue';
import InvoiceRegion from '~/components/organisms/InvoiceRegion.vue';
import VulnerabilityRequestIndividualEdit from '~/components/organisms/VulnerabilityRequestIndividualEdit.vue';
import IncidentEdit from '~/components/molecules/IncidentEdit.vue';
import AddInvoiceBudget from '../molecules/AddInvoiceBudget.vue';
import AddFraud from '../molecules/AddFraud.vue';
import FraudRegion from './FraudRegion.vue';
import IncidentRegion from './IncidentRegion.vue';
import OrderRegion from './OrderRegion.vue';
import PriceRateRegionDetail from './PriceRateRegionDetail.vue';
import PriceIntervalRegion from './PriceIntervalRegion.vue';
import CalendarTaskEdit from '../molecules/CalendarTaskEdit.vue';
import PiggyBankRegion from './PiggyBankRegion.vue';
import ContractDebtRegion from './ContractDebtRegion.vue';
import EstimatedBagRegion from './EstimatedBagRegion.vue';
import AddReading from '../molecules/AddReading.vue';
import MassiveInvoiceDownload from './MassiveInvoiceDownload.vue';
import ContractClausesEdit from '../molecules/ContractClausesEdit.vue';
import { useContractInvoicesByPeriod } from '~/composables/useContractInvoicesByPeriod';

const { $ContractApiService, $InvoiceApiService, $LoggerApiService, $VulnerabilityRequestApiService, $ConfigProjectApiService } = useNuxtApp();
const fixedObjectsStore = useFixedObjectsStore();
const { t } = useI18n();
const toast = useToast();
const route = useRoute();
const router = useRouter();
const props = defineProps({
    id: Number,
    isSubRegion: {
        type: Boolean,
        default: false,
    },
});
const emit = defineEmits(['close']);

const firstReload = ref(true)
const reload = ref(false);
const passedId = ref(null);
const loading = ref(true);
const contract = ref(null);
const activeTab = ref('observations');

const observationNumber = ref(0);
const communicationNumber = ref(0);
const data_changes = ref([]);
const members_change = ref([]);
const contract_phones_logs = ref([]);
const contract_logs = ref([]);

const allModifications = computed(() =>
  mergeContractModifications(data_changes.value, members_change.value, contract_phones_logs.value)
);

const surrogations = ref([]);
const tenant_changes = ref([]);
const bonVarChangesNumber = ref(0);
const orderNumber = ref(0);

const objectPermissions = ref({});

const allowSelectSupplyPointFraud = ref(false);

const invoicesByPeriod = useContractInvoicesByPeriod(() => contract.value.id)
const general_invoices = ref([])
const invoiceTypeToken = ref(null)
const invoicesLoading = ref(false)
const person_ids = ref([])
const expired_variables = ref(null)
const expired_bonifications = ref(null)
const new_call = ref(null);
const call_register_number = ref(0);
const terminatedStatusToken = ref(null);
const selectedCustomInvoice = ref(null);

const showRegionDetailComponent = ref(null);
const regionDetailId = ref(null);
const showRegion = ref(false);
const isSubRegionOpen = ref(false);

const isChecked = ref(false);
const username = ref(null);

if (process.client) {
    username.value = localStorage.getItem('user_username') || '';
}

const updateCommunicationCount = (num) => {
    communicationNumber.value = num;
}
const updateObservationCount = (num) => {
    observationNumber.value = num;
}
const updateOrderCount = (num) => {
    orderNumber.value = num;
}
const updateCallRegisterCount = (num) => {
    call_register_number.value = num;
}
const updateIncidentCount = (num) => {
    if (contract.value) contract.value.incidents = num;
}
const updateBonificationVariableChangeCount = (num) => {
    bonVarChangesNumber.value = num;
}

const supplyCutAlert = computed(() => contract.value?.supply_point_default?.supply_cut_alert || null);

const getContractData = async (load = true) => {
    loading.value = load;
    try {
        const data = await $ContractApiService.getPinnedContractData(passedId.value);
        contract.value = null;
        await nextTick();
        contract.value = data;

        selectedCustomInvoice.value = {
            id: contract.value.id,
            title: '',
            label: `${contract.value.token} - ${contract.value.holder.full_name} (${contract.value.holder.token})`,
            general_invoice: contract.value.general_invoice ? true : false,
            period_days: contract.value.billing_period_days || 0,
            entity: 'contract',
        };

        getChanges(data);
        getInvoices();
        getGeneralInvoices();
        getExpiredVariables();
        getPersonIds(data);
        reload.value = !reload.value;
        if (firstReload.value) {
            getPinnedContract()
        }
    } catch (error) {
        console.error(error);
    } finally {
        loading.value = false;
        firstReload.value = false;
    }
}

const getPinnedContract = async () => {
    try {
        let contract = await $ContractApiService.getPinnedContract(passedId.value);
        if (contract) {
            fixedObjectsStore.setCurrentPinnedContract(contract);
            isChecked.value = contract.user_checked.some(user => user.username === username.value);
        }
    } catch (error) {
        console.error(error);
    }
}

const getChanges = async (data) => {
    surrogations.value = data.surrogations?.reverse() || [];
    tenant_changes.value = data.tenant_changes?.reverse() || [];
    data_changes.value = data.data_changes?.reverse() || [];
}

const loadModificationLogs = async () => {
    members_change.value = [];
    contract_phones_logs.value = [];
    contract_logs.value = [];
    try {
        const [membersResult, phonesResult, logsResult] = await Promise.all([
            $LoggerApiService.getAll('contract-total-members', passedId.value),
            $LoggerApiService.getAll('contract-phones', passedId.value),
            $ContractApiService.getLogs(passedId.value),
        ]);
        members_change.value = membersResult.results || [];
        contract_phones_logs.value = phonesResult.results || [];
        contract_logs.value = Array.isArray(logsResult) ? logsResult : (logsResult?.results || []);
    } catch (error) {
        console.error(error);
    }
};

const getPersonIds = (data) => {
    if (data.holder && !person_ids.value.includes(data.holder.id)) {
        person_ids.value.push(data.holder.id)
    }
    if (data.tenant && !person_ids.value.includes(data.tenant.id)) {
        person_ids.value.push(data.tenant.id)
    }
    if (data.owner && !person_ids.value.includes(data.owner.id)) {
        person_ids.value.push(data.owner.id)
    }
    if (data.representatives && data.representatives.length > 0 && !person_ids.value.includes(data.representatives.map(representative => representative.person.id))) {
        person_ids.value.push(...data.representatives.map(representative => representative.person.id))
    }
}


const getInvoices = async () => {
    invoicesLoading.value = true;
    try {
        await invoicesByPeriod.load();
    } finally {
        invoicesLoading.value = false;
    }
}

const getGeneralInvoices = async () => {
    general_invoices.value = []
    try {
        if (!invoiceTypeToken.value) {
            invoiceTypeToken.value = await $ConfigProjectApiService.get('invoice_type_invoice_token');
        }
        const result = await $InvoiceApiService.getGeneralInvoicesFromContract(contract.value.id);
        general_invoices.value = result.results.filter(invoice => invoice.type_final == invoiceTypeToken.value);
    } catch (error) {
        console.error(error);
    }
}

// Update a single invoice's PDF document in-place so the "send" button reactivates
// without reloading the whole invoice list.
const onInvoicePdfGenerated = ({ id, invoice_file }) => {
    invoicesByPeriod.updateInvoiceFile({ id, invoice_file });
}

const getExpiredVariables = async () => {
    try {
        const result = await $LoggerApiService.getAll("contract-expired-bonifications-variables", contract.value.id);
        expired_variables.value = getLatestByToken(result.results);

        expired_bonifications.value = result.results.filter(item => item.expired_bonification)

    } catch (error) {
        console.log(error);
    }
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

/* DROPDOWN ACTIONS */

const dataChange = () => {
    let url = `/contract/contracts/${contract.value.id}/data-change`;
    router.push(url);
    emit('close');
    /* const newWindow = window.open(url, '_blank');
    if (newWindow) {
      newWindow.focus();
    } */
}

const surrogate = () => {
    let url = `/contract/contracts/${contract.value.id}/surrogate`;
    router.push(url);
    emit('close');
}

const tenantChange = () => {
    let url = `/contract/contracts/${contract.value.id}/change-tenant`;
    router.push(url);
    emit('close');
}

const terminate = () => {
    let url = `/contract/contract-terminations/add?contract=${contract.value.id}`;
    router.push(url);
    emit('close');
}

const changeBonifications = () => {
    let url = `/contract/contracts/${contract.value.id}/bonifications`;
    router.push(url);
    emit('close');
}

const changePriceRates = () => {
    let url = `/contract/contracts/${contract.value.id}/price-rates`;
    router.push(url);
    emit('close');
}

const pinObject = async () => {
    try {
        let save_date = {
            id: contract.value.id,
            is_pinned: false
        }
        fixedObjectsStore.clearCurrentPinnedContract();
        // As a region (NavTopPinned panel) just close it; as a full page leave it.
        if (props.isSubRegion) {
            emit('close');
        } else {
            router.push(`/contract/contracts/`);
        }
        await $ContractApiService.save(save_date)
    } catch (error) {
        console.error(error)
    }
}

// Full page only: it can be reached from the top bar link or a direct URL, so go back when
// there is an in-app previous page and fall back to the contract list otherwise.
const closeFullPage = () => {
    if (window.history.state?.back) {
        router.back();
    } else {
        router.push('/contract/contracts/');
    }
}

const checkObject = async () => {
    try {
        let save_date = {
            id: contract.value.id,
            is_checked: !isChecked.value
        }
        isChecked.value = !isChecked.value;
        await $ContractApiService.save(save_date)
    } catch (error) {
        console.error(error)
    }
}

const requestVulnerability = async () => {
    if (confirm(t('confirmation_text_block.confirm_create_vulnerability_request'))) {
        let save_data = {
            contract_id: contract.value.id,
        }
        try {
            let response = await $VulnerabilityRequestApiService.save(save_data);
            if (response) {
                getContractData(false);
                showDetail('VulnerabilityRequestRegion', response.id)
                toast.success(t('informative_block.info_all_vuln_requested') + ' ' + contract.value.token)
                //TODO: RELOAD VULNERABILITY REQUESTS COMPONENT
            } else {
                console.error("Error")
            }
        } catch (error) {
            console.error(error)
        }
    }
}

const newClaimRequest = async () => {
    emit('close');
    return navigateTo({
        path: '/billing/claim-managements/add',
        query: {
            contract_id: contract.value.id,
            contract_token: contract.value.token
        }
    })
}

const newCommunicationProcess = async () => {
    emit('close');
    return navigateTo({
        path: '/communication/process-communications/add',
        query: {
            contract_id: contract.value.id,
        }
    })
}

const cutSupplyPoint = () => {
    emit('close');
    return navigateTo({
        path: '/service/supply-cut/add',
        query: {
            action: 'CONTRACT',
            contract: contract.value.id
        }
    })
}

const showConfirmationModal = ref(false);

const showDeleteContractConfirmation = () => {
    showConfirmationModal.value = true;
}

const modifyReadings = () => {
    return router.push(`/contract/contracts/${contract.value.id}/reading-change`);
}

const toggleBillable = async () => {
    const txt = contract.value.block_billing ? t('contract_block.mark_as_billable') : t('contract_block.mark_as_unbillable')

    if (confirm(t('confirmation_text_block.confirm_base') + ' ' + txt.toLowerCase() + '?')) {
        const res = await $ContractApiService.toggleBillable(passedId.value);

        contract.value.block_billing = res.block_billing;
    }
}

const newFraud = () => {
    if (contract.value.supply_points.length == 1) {
        showDetail('AddFraud', contract.value.supply_points[0].id)
    } else {
        allowSelectSupplyPointFraud.value = true
    }
}


const startCall = async (item) => {
    console.log("item", item)
    new_call.value = {
        contact: item,
        contract: contract.value
    };
}

const handleNewCall = () => {
    new_call.value = null;
    handleChange();
}

const selectSupplyPointFraud = (supply_point) => {
    allowSelectSupplyPointFraud.value = false;
    showDetail('AddFraud', supply_point.id)
}

const getContractInCommitment = () => {
    emit('close');
    return navigateTo({
        path: '/billing/commitment-deposits/add',
        query: {
            contract_id: contract.value.id,
        }
    })
}

/* REGION */
const handleChange = async () => {
    let currentTab = activeTab.value;
    closeRegion();
    await getContractData(false);
    setActiveTab(null);
    await nextTick();
    setActiveTab(currentTab);
}

const handleNewFraud = async (item) => {
    handleChange()
    showDetail('FraudRegion', item.id)
}

const generateContract = async () => {
    const response = await $ContractApiService.getDocument(contract.value.id, true);
    await openAuthenticatedFileUrl(response.pdf_url);
}

const deleteContract = async () => {
    try {
        await $ContractApiService.doDelete(contract.value);
        fixedObjectsStore.clearCurrentPinnedContract();
        return navigateTo('/');
    } catch (error) {
        console.error(error);
    }
}

const showDetail = (component, id) => {
    showRegion.value = true;
    showRegionDetailComponent.value = component;
    regionDetailId.value = id;
    showRegion.value = true;
}

const closeRegion = () => {
    showRegion.value = false;
    showRegionDetailComponent.value = null;
    regionDetailId.value = null;
    isSubRegionOpen.value = false;
}

const handleSubRegionEvent = (event) => {
    isSubRegionOpen.value = event;
}

const manageGeneralInvoices = () => {
    let gen_id = contract.value.general_invoice?.id || '';
    return navigateTo(`/contract/contracts/${contract.value.id}/general-invoices/?id=${gen_id}`);
}

const newCommunication = () => {
    return navigateTo({
        path: '/communication/communications/add',
        query: {
            step: 1,
            contract_id: contract.value.id,
        }
    })
}

onMounted(async () => {
    objectPermissions.value = await checkPermission($ContractApiService);
    if (!objectPermissions.value.can_view) {
        toast.error(t('common.no_permissions'));
        return navigateTo('/');
    }
    if (route.params?.id) {
        passedId.value = route.params.id;
    }
    if (props.id) {
        passedId.value = props.id;
    }
    terminatedStatusToken.value = await $ConfigProjectApiService.get('contract_terminated_status');
    await getContractData()
});

const modificationLogsLoaded = ref(false);

const setActiveTab = (tab) => {
    activeTab.value = tab;
    if (tab === 'dataChange' && !modificationLogsLoaded.value) {
        loadModificationLogs().then(() => {
            modificationLogsLoaded.value = true;
        });
    }
};

</script>

<template>
  <div class="region__content h-full">
    <div v-if="loading" class="h-full min-h-[400px]">
      <AppLoading :text="$t('common.loading')" />
    </div>
    <div v-else-if="objectPermissions?.can_view" class="pr-2 relative pb-24 transition-all duration-500 ease"
      :class="{ 'h-full overflow-y-auto': !isSubRegion, 'mr-[48vw]': showRegion }">
        <TypedConfirmationModal v-model:open="showConfirmationModal"
            :message="t('confirmation_text_block.confirm_delete_contract')"
            :expected-phrase="t('confirmation_phrase_block.delete_contract')" @confirm="deleteContract" />

        <!-- Same header as ContractRegion so the pinned contract looks like the contract region -->
        <div class="flex justify-between relative">
            <div class="flex items-center mb-3 gap-5">
                <H1Region>{{ $t('contract') }}</H1Region>
                <!-- Reclamació oberta d'un tipus que bloqueja les ofertes comercials -->
                <span v-if="contract?.blocking_incident" class="text-xs px-2 py-1 rounded-full bg-red-100 text-red-700"
                    :title="contract.blocking_incident.name">
                    <Icon name="fa6-solid:ban" class="mr-1" />{{ $t('incident_block.commercial_block') }} ({{ contract.blocking_incident.token }})
                </span>
            </div>

            <div v-if="contract">
                <div class="flex items-center gap-0" style="margin-right: 40px;">
                    <button @click="pinObject" class="flex items-center justify-center px-4 py-[5px]"
                        :title="t('contract_block.unpin_contract')">
                        <Icon name="ic:sharp-push-pin" class="w-4 h-4 text-red-500 hover:bg-red-900" />
                    </button>
                    <button @click="checkObject" class="group flex items-center justify-center px-4 py-[5px]"
                        :title="isChecked ? t('contract_block.unfollow_contract') : t('contract_block.follow_contract')">
                        <Icon :name="isChecked ? 'fa6-solid:flag' : 'fa6-regular:flag'" class="w-3.5 h-3.5" :class="{
                            'text-red-500 group-hover:bg-red-900': isChecked,
                            'text-slate-500 group-hover:text-sky-500': !isChecked
                        }" />
                    </button>
                    <button v-if="!isSubRegion" @click="closeFullPage" :title="t('common.close')"
                        class="flex items-center justify-center px-4 py-[5px] text-slate-500 hover:text-sky-500">
                        <Icon name="fa6-solid:xmark" class="w-4 h-4" />
                    </button>
                </div>

                <ContractActionsDropdown v-if="objectPermissions.can_change" :contract="contract"
                    :canChange="objectPermissions.can_change" :terminatedStatusToken="terminatedStatusToken"
                    :personIds="person_ids" @show-detail="showDetail" @change="getContractData(false)"
                    @delete-click="showDeleteContractConfirmation" />
            </div>
        </div>

        <div v-if="contract">

            <div v-if="new_call" class="fixed inset-0 z-50 flex items-center justify-center">
                <div class="bg-white rounded-lg shadow-xl p-6 max-w-3xl w-full mx-4 my-auto relative">
                    <AddNewCall :data="new_call" @exit="handleNewCall" />
                </div>
            </div>

            <!-- If done otherwhise, black bg does not occupy the whole screen :C -->
            <div v-if="new_call"
                class="fixed inset-0 bg-black bg-opacity-50 h-[120vh] z-30 flex items-center justify-center">
            </div>

            <div v-if="allowSelectSupplyPointFraud"
                class="absolute inset-0 bg-white bg-opacity-50 z-50 flex items-center justify-center">
                <div class="bg-white p-6 rounded-lg shadow-lg max-w-2xl w-full mx-4">
                    <div class="flex justify-between items-center mb-4">
                        <h2 class="text-xl font-semibold text-slate-700">
                            {{ t('common.select') }} {{ t('supply_point') }}
                        </h2>
                        <button @click="allowSelectSupplyPointFraud = false"
                            class="text-slate-500 hover:text-slate-700">
                            <Icon name="fa6-solid:xmark" class="w-5 h-5" />
                        </button>
                    </div>
                    <div class="space-y-3">
                        <div v-for="supply_point in contract.supply_points" :key="supply_point.id" class="mb-3">
                            <button @click="selectSupplyPointFraud(supply_point)"
                                class="w-full bg-white rounded-lg shadow-sm border border-slate-200 hover:border-sky-500 hover:bg-sky-50 transition-colors duration-200">
                                <div class="p-4">
                                    <div class="flex items-center justify-between">
                                        <div class="flex items-center gap-2">
                                            <h2 class="text-slate-700">{{ supply_point.address_complete }}</h2>
                                            <p class="text-sm text-slate-500">{{ supply_point.token }}</p>
                                        </div>
                                        <Icon name="fa6-solid:chevron-right" class="text-slate-400" />
                                    </div>
                                </div>
                            </button>
                        </div>
                    </div>
                </div>
            </div>

            <div v-if="supplyCutAlert" role="alert" class="mb-2">
                <div class="flex items-center gap-3 w-full rounded-lg border border-amber-300 bg-amber-50 px-3 py-1 shadow-sm">
                    <div class="flex h-4 w-4 shrink-0 items-center justify-center text-amber-700">
                        <Icon name="fa6-solid:scissors" class="text-sm" />
                    </div>
                    <div class="min-w-0 flex-1 flex flex-wrap items-center gap-x-2 gap-y-1">
                        <span class="text-sm font-semibold text-amber-900 leading-snug">
                            {{ $t('service_block.supply_with_cut') }}
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

            <ContractInvalidAccountAlert :alert="contract?.invalid_account_payment_alert" />

            <ContractDetail :data="contract" :isSubRegion="isSubRegion" :isSubRegionOpen="isSubRegionOpen"
                :canChange="objectPermissions.can_change" :showDebtDetail="true" :showBailTab="true"
                @show-subregion="showDetail" @change="handleChange" @new-call="startCall"
                @update-active-tab="setActiveTab" />

            <ContractTabs
                :contract="contract"
                :isPinned="true"
                :canChange="objectPermissions.can_change"
                :isSubRegion="isSubRegion"
                :activeTab="activeTab"
                :observationNumber="observationNumber"
                :callRegisterNumber="call_register_number"
                :reload="reload"
                :incidentNumber="contract.incidents || 0"
                :communicationNumber="communicationNumber"
                :orderNumber="orderNumber"
                :bonVarChangesNumber="bonVarChangesNumber"
                :changesNumber="surrogations?.length || 0"
                :contractChangeNumber="allModifications.length + contract_logs.length"
                :surrogations="surrogations"
                :tenant_changes="tenant_changes"
                :data_changes="data_changes"
                :members_change="members_change"
                :all-modifications="allModifications"
                :contract_logs="contract_logs"
                :expired_variables="expired_variables"
                :expired_bonifications="expired_bonifications"
                :invoices-by-period="invoicesByPeriod"
                :invoices_count="contract ? contract.invoices_count : 0"
                :general_invoices="general_invoices"
                :invoicesLoading="invoicesLoading"
                :person_ids="person_ids"
                :permissions="objectPermissions"
                @show-detail="showDetail"
                @change="getContractData(false)"
                @update-active-tab="setActiveTab"
                @update:observation-count="updateObservationCount"
                @update:call-register-count="updateCallRegisterCount"
                @update:incident-count="updateIncidentCount"
                @update:communication-count="updateCommunicationCount"
                @update:order-count="updateOrderCount"
                @update:bonification-variable-change-count="updateBonificationVariableChangeCount" />
        </div>
    </div>
    <div v-if="showRegion == true" role="region" id="subregion"
        class="h-full border-l border-gray-100 transition-all duration-500 ease text-base bg-white flex flex-col overflow-hidden fixed top-0 right-0 w-[48vw] z-50"
        :class="{
            'translate-x-0': showRegion,
            'translate-x-full': !showRegion,
        }">
        <div id="region_nav" class="mb-3 px-3">
            <button @click="closeRegion" class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300">
                <Icon name="fa6-solid:angles-right" class="text-slate-500" />
            </button>
        </div>
        <div class="pl-10 flex-1 overflow-y-auto pb-24 pr-2">
            <PersonRegion v-if="showRegionDetailComponent === 'PersonRegion'"
                :id="parseInt(regionDetailId)" :isSubRegion="true" @close-subregion="closeRegion"
                @changed="handleChange">
            </PersonRegion>
            <SupplyPointRegion v-if="showRegionDetailComponent === 'SupplyPointRegion'"
                :id="parseInt(regionDetailId)" :isSubRegion="true" @close-subregion="closeRegion"
                @changed="handleChange"></SupplyPointRegion>
            <MeterRegion v-if="showRegionDetailComponent === 'MeterRegion'" :id="regionDetailId" :isSubRegion="true"
                @close-subregion="closeRegion" />
            <ProductRegion v-if="showRegionDetailComponent === 'ProductRegion'" :id="regionDetailId" :isSubRegion="true"
                @close-subregion="closeRegion" />
            <PriceRateRegionDetail v-if="showRegionDetailComponent === 'PriceRateRegion'" :id="parseInt(regionDetailId)"
                :isSubRegion="true" />
            <PriceIntervalRegion v-if="showRegionDetailComponent === 'PriceIntervalRegion'"
                :id="parseInt(regionDetailId)" :isSubRegion="true" />
            <IncidentRegion v-if="showRegionDetailComponent === 'IncidentRegion'"
                :id="parseInt(regionDetailId)" :isSubRegion="true" />
            <OrderRegion v-if="showRegionDetailComponent === 'OrderRegion'"
                :id="parseInt(regionDetailId)" :isSubRegion="true" />
            <InvoiceRegion v-if="showRegionDetailComponent === 'InvoiceRegion'"
                :id="regionDetailId" :isSubRegion="true" @update-id="(newId) => regionDetailId = newId"
                @changed="handleChange(false)" @pdf-generated="onInvoicePdfGenerated" />
            <VulnerabilityRequestIndividualEdit v-if="showRegionDetailComponent == 'VulnerabilityRequestRegion'"
                :vulnerability_id="parseInt(regionDetailId)" :isSubRegionOpen="isSubRegionOpen" />
            <IncidentEdit v-if="showRegionDetailComponent == 'IncidentEdit'" :contract_id="regionDetailId"
                @change="handleChange" />
            <CalendarTaskEdit v-if="showRegionDetailComponent === 'CalendarTaskEdit'" :id="regionDetailId"
                :object_id="contract.id" :object_service="$ContractApiService" @change="handleChange" />
            <AddFraud v-if="showRegionDetailComponent === 'AddFraud'" :supply_point_id="regionDetailId"
                :contract_id="contract.id" @changed="handleNewFraud" />
            <FraudRegion v-if="showRegionDetailComponent === 'FraudRegion'" :id="regionDetailId"
                :isSubRegion="true" @changed="handleChange" />
            <PiggyBankRegion v-if="showRegionDetailComponent === 'PiggyBankRegion'" :id="parseInt(regionDetailId)"
                :isSubRegion="true" @changed="handleChange" @show-subregion="handleSubRegionEvent" />
            <ContractDebtRegion v-if="showRegionDetailComponent === 'ContractDebtRegion'" :id="parseInt(regionDetailId)"
                :isSubRegion="true" @changed="getContractData(false)" @show-subregion="handleSubRegionEvent" />
            <EstimatedBagRegion v-if="showRegionDetailComponent === 'EstimatedBagRegion'" :id="parseInt(regionDetailId)"
                :isSubRegion="true" />
            <AddReading v-if="showRegionDetailComponent === 'AddReading'" :contract="contract"
                :contract_ids="[contract.id]" :isSubRegion="true" />
            <AddInvoiceBudget v-if="showRegionDetailComponent === 'AddInvoiceBudget'" :isSubRegion="true"
                :object_id="contract.id" :service="$ContractApiService" :entity="'custom'" :persons="[contract.holder]"
                :individual="true" :selectedCustom="selectedCustomInvoice" @change="handleChange"
                @show-subregion="handleSubRegionEvent" @close="closeRegion" />
            <MassiveInvoiceDownload v-if="showRegionDetailComponent === 'MassiveInvoiceDownload'"
                :contract_id="contract.id" />
            <ContractClausesEdit v-if="showRegionDetailComponent === 'ContractClausesEdit'" :contract="contract"
                @change="getContractData(false)" />
        </div>
    </div>
  </div>
</template>