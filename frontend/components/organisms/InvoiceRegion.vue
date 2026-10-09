<script setup>
import { ref, watch } from 'vue';
import { useRouter } from 'vue-router';
import { useI18n } from 'vue-i18n';
import { useToast } from 'vue-toastification';
import { openAuthenticatedFileUrl } from '~/utils/open-authenticated-file';
import H1Region from '~/components/atoms/H1Region.vue';
import OptionsDropdown from '~/components/molecules/OptionsDropdown.vue';
import DropdownOption from '~/components/atoms/DropdownOption.vue';
import InvoiceDetail from '../molecules/InvoiceDetail.vue';
import ContractRegion from './ContractRegion.vue';
import ContractRequestRegion from './ContractRequestRegion.vue';
import ExploitationRegion from './ExploitationRegion.vue';
import PaymentRegion from './PaymentRegion.vue';
import CommitmentDepositRegion from './CommitmentDepositRegion.vue';
import InvoiceLineItemDetailInvoice from '../molecules/InvoiceLineItemDetailInvoice.vue';
import LineItemTypeRegion from './LineItemTypeRegion.vue';
import PriceRateRegion from './PriceRateRegion.vue';
import SEPAManagementViewDocument from './SEPAManagementViewDocument.vue';
import InvoiceSurchargeDetail from '../molecules/InvoiceSurchargeDetail.vue';
import ChangeStatus from '../molecules/ChangeStatus.vue';
import ContractTerminationRegion from './ContractTerminationRegion.vue';
import IncidentEdit from '../molecules/IncidentEdit.vue';
import IncidentList from '../molecules/IncidentList.vue';
import IncidentRegion from './IncidentRegion.vue';
import InvoiceViewEdit from '../organisms/InvoiceViewEdit.vue';
import AddInvoiceBudget from '../molecules/AddInvoiceBudget.vue';
import InvoiceConsumptionDetail from '../molecules/InvoiceConsumptionDetail.vue';
import { usePermissions } from '~/middleware/permission';
import PersonBankSelect from '../molecules/PersonBankSelect.vue';
import InvoiceRegionModals from './InvoiceRegionModals.vue';
import SendInvoiceModal from '../molecules/SendInvoiceModal.vue';
import ModelLogs from '../molecules/ModelLogs.vue';
import AppLoading from '~/components/atoms/AppLoading.vue';
import InvoicePaymentDetail from '../molecules/InvoicePaymentDetail.vue';
import TypedConfirmationModal from '../molecules/TypedConfirmationModal.vue';

const { permissions, loading } = usePermissions();

const { t } = useI18n();
const toast = useToast();
const config = useRuntimeConfig();
const verifactuEnabled = config.public.verifactuEnabled;

const props = defineProps({
  id: Number, // ID de l'element
  isSubRegion: {
    type: Boolean,
    default: false
  },
  isSubRegionOpen: Boolean,
  isBudget: {
    type: Boolean,
    default: false
  },
});

const emit = defineEmits(['show-subregion', 'changed', 'close-subregion', 'update-id', 'pdf-generated']);
const router = useRouter();
const { $VerifactuApiService, $InvoiceApiService, $ConfigProjectApiService, $PersonApiService, $ContractApiService, $PaymentApiService, $ContractRequestApiService, $ConnectionRequestApiService, $ContractTerminationRequestApiService, $apiManager, $DocumentManagerApiService, $CommitmentDepositApiService } = useNuxtApp();
const pending = ref(true);
const error = ref(null);
const reloadLog = ref(false);
const data = ref(null);
const invoiceId = ref(props.id);

const objectPermissions = ref(null);
const status_confirmed_token = ref(null);
const status_paid_token = ref(null);
const status_pending_token = ref(null);
const status_returned_token = ref(null);
const status_irrecoverable_token = ref(null);
const status_endowment_token = ref(null);
const status_commitment_token = ref(null);
const status_canceled_token = ref(null);
const invoice_token = ref(null)
const origin_reading = ref(null)

const logNumber = ref(0)
const surchargeNumber = ref(0)
const messageNumber = ref(0)
const changeNumber = ref(0)
const commitmentDeposit = ref(null)

const service = ref(null);
const entity = ref(null);
const object_id = ref(null);

const activeTab = ref('payments');
const SubRegion = ref(props.isSubRegionOpen);

const persons = ref(null);
const localPersons = ref([]);

const allow_changes = ref(true); //NOT
const openDeleteConfirmation = ref(false);

// Modals component ref
const modalsRef = ref(null);

const updateLogCount = (num) => {
  logNumber.value = num;
}

const updateSurchargeCount = (num) => {
  surchargeNumber.value = num;
}

const updateMessageCount = (num) => {
  messageNumber.value = num;
}

const updateChangeCount = (num) => {
  changeNumber.value = num;
}

const getPermissions = async () => {
  error.value = null;
  try {
    const data = await $InvoiceApiService.getPermissions();
    objectPermissions.value = data;
  } catch (err) {
    error.value = err;
  }
}

const getData = async (load = true) => {
  if (!objectPermissions.value?.can_view) {
    emit('close-subregion');
    return
  }
  if (load) pending.value = true;
  error.value = null;
  reloadLog.value = !reloadLog.value;
  try {
    origin_reading.value = await $ConfigProjectApiService.get('origin_reading_token');
    status_confirmed_token.value = await $ConfigProjectApiService.get('invoice_status_confirmed_token');
    status_paid_token.value = await $ConfigProjectApiService.get('invoice_status_paid_token');
    status_pending_token.value = await $ConfigProjectApiService.get('invoice_status_pending_token');
    status_irrecoverable_token.value = await $ConfigProjectApiService.get('invoice_status_irrecoverable_token');
    status_endowment_token.value = await $ConfigProjectApiService.get('invoice_status_endowment_token');
    status_commitment_token.value = await $ConfigProjectApiService.get('invoice_status_commitment_token');
    invoice_token.value = await $ConfigProjectApiService.get('invoice_type_invoice_token');
    status_canceled_token.value = await $ConfigProjectApiService.get('invoice_status_cancelled_token');
    const result = await $InvoiceApiService.getDetail(invoiceId.value);
    data.value = result;

    allow_changes.value = (data.value.remittances && data.value.remittances.some(remittance => !remittance.sent_at)) || (data.value.joined_payments && data.value.joined_payments.some(joined_payment => !joined_payment.allow_change));
    if (data.value.contract_request) {
      persons.value = [data.value.contract_request.holder, data.value.contract_request.tenant, data.value.contract_request.owner];
      service.value = $ContractRequestApiService;
      entity.value = 'contract_request';
      object_id.value = data.value.contract_request.id;
    } else if (data.value.contract) {
      persons.value = [data.value.contract.holder, data.value.contract.tenant, data.value.contract.owner];
      service.value = $ContractApiService;
      entity.value = 'contract';
      object_id.value = data.value.contract.id;
    } else if (data.value.connection_request) {
      persons.value = [data.value.connection_request.person];
      service.value = $ConnectionRequestApiService;
      entity.value = 'connection_request';
      object_id.value = data.value.connection_request.id;
    } else if (data.value.contract_termination_request) {
      persons.value = [data.value.contract_termination_request.person];
      service.value = $ContractTerminationRequestApiService;
      entity.value = 'contract_termination_request';
      object_id.value = data.value.contract_termination_request.id;
    }
    // Actualitzar comptadors
    updateSurchargeCount(data.value.child_invoices?.length || 0);
    updateMessageCount(data.value.messages?.length || 0);

    // Compromís de dipòsit al qual pertany la factura (relació M2M CommitmentDeposit.invoices, sense FK directa).
    commitmentDeposit.value = null;
    if (data.value.status?.token == status_commitment_token.value) {
      try {
        const cdResult = await $CommitmentDepositApiService.getByInvoice(invoiceId.value);
        commitmentDeposit.value = cdResult.results?.[0] || null;
      } catch (err) {
        console.error(err);
      }
    }

  } catch (err) {
    error.value = err;
  } finally {
    pending.value = false;
  }
}

const getPersonsData = async () => {
  try {

    if (data.value.contract) {
      if (data.value.contract.holder_id) {
        await getPersonData(data.value.contract.holder_id);
      }
      if (data.value.contract.tenant_id) {
        await getPersonData(data.value.contract.tenant_id);
      }
      if (data.value.contract.owner_id) {
        await getPersonData(data.value.contract.owner_id);
      }
    } else if (data.value.contract_request) {
      if (data.value.contract_request.holder_id) {
        await getPersonData(data.value.contract_request.holder_id);
      }
      if (data.value.contract_request.tenant_id) {
        await getPersonData(data.value.contract_request.tenant_id);
      }
      if (data.value.contract_request.owner_id) {
        await getPersonData(data.value.contract_request.owner_id);
      }
    } else if (data.value.connection_request) {
      if (data.value.connection_request.person) {
        await getPersonData(data.value.connection_request.person.id);
      }
    } else if (data.value.contract_termination_request) {
      if (data.value.contract_termination_request.contract.holder_id) {
        await getPersonData(data.value.contract_termination_request.contract.holder_id);
      }
    } else {
      if (data.value.customer_token_final) {
        await getPersonData(null, data.value.customer_token_final);
      }
    }
  } catch (err) {
    console.error(err);
  }
}

const getPersonData = async (person_id, customer_token_final = null) => {
  try {
    let data = null;
    if (person_id) {
      data = await $PersonApiService.getFullDetail(person_id);
    } else {
      data = await $PersonApiService.getFullDetailByToken(customer_token_final);
    }
    localPersons.value.push(data);
  } catch (err) {
    console.error(err);
  }
}

watch(() => props.id, async (newVal) => {
  invoiceId.value = newVal;
  if (!objectPermissions.value?.can_view) {
    emit('close-subregion');
    return
  }
  await getData();
  await getPersonsData();
  closeSubRegion();
});

watch(() => props.isSubRegionOpen, (newValue) => {
  SubRegion.value = newValue;
});

onMounted(async () => {
  await getPermissions();
  if (objectPermissions.value?.can_view) {
    await getData();
    await getPersonsData();
  } else {
    toast.error(t('common.no_permissions'));
    emit('close-subregion');
    return navigateTo('/');
  }
});

const setActiveTab = (tab) => {
  activeTab.value = tab;
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

const showRegionDetailComponent = ref(null);
const regionDetailId = ref(null);
const forceToken = ref(null);

const showDetail = function (component, id) {
  showRegionDetailComponent.value = component;
  regionDetailId.value = id;
  showSubRegion();
}

const openPersonBankSelect = function () {
  showRegionDetailComponent.value = 'PersonBankSelect';
}

const changeStatus = async (status, delete_payments = false) => {
  if (!confirm(t("confirmation_text_block.confirm_change_status"))) return
  try {
    let save_data = {
      id: invoiceId.value,
      status_token: status,
      delete_payments: delete_payments
    };
    await $InvoiceApiService.save(save_data).then(() => {
      getData();
    });
    await nextTick()
    emit('changed');
  } catch (e) {
    console.error(e)
  }
}

const showInvoice = () => {
  const url = new URL('/billing/invoice/view/' + invoiceId.value, window.location.origin);
  window.open(url.toString(), '_blank');
}

const notifyVerifactuInvoice = async () => {
  if (!confirm(t("confirmation_text_block.confirm_notify_verifactu"))) return
  try {
    let response = await $VerifactuApiService.notifyVerifactuInvoice(invoiceId.value);
    if (response) {
      toast.success(t("billing_block.correct_notify_verifactu"))
      getData(false)
    }
  } catch (error) {
    console.error(error)
  }
}


const getInvoiceInCommitment = () => {
  return navigateTo({
    path: '/billing/commitment-deposits/add',
    query: {
      invoice_id: invoiceId.value,
    }
  })
}

const confirmInvoice = async () => {
  if (confirm(t("confirmation_text_block.confirm_confirm_invoice"))) {
    try {
      let save_data = {
        id: invoiceId.value,
        status_token: status_confirmed_token.value
      };
      await $InvoiceApiService.save(save_data).then(() => {
        getData();
      });
      await nextTick()
      emit('changed');
    } catch (e) {
      console.error(e)
    }
  }
}

const budgetToInvoice = async () => {
  try {
    let invoice_generation = {
      entity: "invoice",
      object_id: invoiceId.value,
      is_budget: false,
    }

    let response = await $InvoiceApiService.generateInvoiceBudget(invoice_generation);
    if (response) {
      toast.success(t("billing_block.generated_invoice"))
      getData(false)
    }
  } catch (error) {
    console.error(error)
  }
}

const deleteBudget = async () => {
  try {
    await $InvoiceApiService.deleteInvoiceBudget(invoiceId.value).then(() => {
      toast.success(t("common.deleted_successfully"))
      emit('changed');
      closeSubRegion();
      emit('close-subregion');
    });
  } catch (e) {
    console.error(e)
    toast.error(t("common.delete_failed"))
  } finally {
    openDeleteConfirmation.value = false;
  }
}

const reGenerateInvoice = async () => {
  try {
    const response = await $InvoiceApiService.downloadInvoice(invoiceId.value);
    downloadDocument(response.document_id)
    await getData(false)
    emit('pdf-generated', { id: invoiceId.value, invoice_file_template: data.value?.invoice_file_template });
  } catch (error) {
    console.error(error)
  }
}

const sendModalOpen = ref(false);

const openSendModal = () => {
  if (!data.value?.invoice_file_template) {
    toast.warning(t('billing_block.invoice_no_document'));
    return;
  }
  sendModalOpen.value = true;
}

const generateElectronicInvoice = async () => {
  try {
    const response = await $InvoiceApiService.generateElectronicInvoice(invoiceId.value);
    await openAuthenticatedFileUrl(response.file_url, false);
  } catch (error) {
    console.error(error)
  }
}

const downloadDocument = async (invoice_file) => {
  try {
    const file = await $DocumentManagerApiService.viewDocument(invoice_file);

    const link = document.createElement('a');
    const file_url = URL.createObjectURL(file);
    link.href = file_url;
    link.download = `${data.value.serie_final.replace('/', '_')}.pdf`;

    link.click();

    setTimeout(() => {
      window.URL.revokeObjectURL(file_url);
    }, 250);

  } catch (error) {
    console.error(error)
  }
}

const onPersonBankSelected = function (bank) {
  if (modalsRef.value) {
    modalsRef.value.onPersonBankSelected(bank);
  }
}

const passToPending = async () => {

  if (!confirm(t("confirmation_text_block.confirm_pass_pending"))) return

  let return_all = true;
  /* let return_all = false;
  if (data.value.has_payments_piggy_bank) {
    if (data.value.left_to_pay == 0 && data.value.total_final > 0) {
      return_all = true;
    } else {
      return_all = confirm(t("confirmation_text_block.confirm_return_all_piggy_bank"));
    }
  } else {
    if (data.value.total_payments > 1) {
      return_all = true
    }
  } */

  try {
    let save_data = {
      id: invoiceId.value,
      return_all: return_all,
      return_reason: null
    }
    let response = await $InvoiceApiService.passToPending(save_data);
    if (response) {
      toast.success(t("billing_block.correct_pass_pending"))
      updateSubRegion(true)
    }
  } catch (error) {
    console.error(error)
  }
}

const updateSubRegion = function (close = true) {
  getData(close);
  if (close) {
    closeSubRegion();
  }
  nextTick()
  emit('changed')
}

const openVerifactuInvoice = (url) => {
  window.open(url, '_blank');
}

const showHistory = () => {
  showDetail('InvoiceLogs', invoiceId.value);
}

const newCommunication = () => {
  return navigateTo({
    path: '/communication/communications/add',
    query: {
      step: 1,
      contract_id: data.value.contract.id,
    }
  })
}
const handleRecalculate = async () => {
  try {
    if (confirm(t("confirmation_text_block.confirm_recalculate_smart"))) {
      const response = await $InvoiceApiService.recalculateSmart(invoiceId.value);
      if (response) {
        toast.success(t("billing_block.correct_recalculate_smart"));
        if (response.id && response.id !== invoiceId.value) {
          invoiceId.value = response.id;
          emit('update-id', response.id);
        }
        getData(false);
        emit('changed');
      }
    }
  } catch (error) {
    console.error(error);
    toast.error(t("billing_block.error_recalculate_smart"));
  }
}

const handleRefactor = async () => {
  showDetail('AddNewInvoiceBudget', invoiceId.value);
}
</script>

<template>
  <div v-if="!loading" class="region__content h-full">
    <div v-if="pending || loading">
      <AppLoading :text="$t('common.loading')" />
    </div>
    <div v-else-if="error">
      <p>Error: {{ error.message }}</p>
      <p><button @click="getData" class="underline text-sky-500 hover:no-underline">{{ $t('common.load_again')
          }}</button></p>
    </div>
    <div v-else-if="objectPermissions?.can_view" class="pr-2 relative pb-24 transition-all duration-500 ease"
      :class="{ 'h-full overflow-y-auto': !isSubRegion, 'mr-[48vw]': SubRegion && showRegionDetailComponent != 'PersonBankSelect' }">
      <!-- Modals Component -->
      <TypedConfirmationModal v-model:open="openDeleteConfirmation"
        :message="data.type.token != invoice_token ? t('confirmation_text_block.confirm_delete_budget') : t('confirmation_text_block.confirm_delete_pre_invoice')"
        :expected-phrase="data.type.token != invoice_token ? t('confirmation_phrase_block.delete_budget') : t('confirmation_phrase_block.delete_pre_invoice')" @confirm="deleteBudget" />
      <InvoiceRegionModals class="overflow-x-hidden" ref="modalsRef" :invoice-id="invoiceId" :data="data"
        :local-persons="localPersons" @refresh-data="getData"
        @open-person-bank-select="showRegionDetailComponent = 'PersonBankSelect'"
        @close-person-bank-select="closeSubRegion" :is_paid="data.status?.token == status_paid_token" />

      <SendInvoiceModal :show="sendModalOpen" :invoice="data" :contract="data.contract || null"
        @close="sendModalOpen = false" />

      <div class="flex justify-between relative">
        <H1Region class="mb-3">
          {{ data.type.token == invoice_token ? $t('invoice') : $t('common.budget_detail') }}
          <span v-if="data.is_late" class="mx-5 px-2 bg-red-100 text-red-500 text-sm">
            {{ t("billing_block.expired_invoice") }}
          </span>
          <span v-if="verifactuEnabled && data.type.token == invoice_token && !data.verifactu_invoice"
            class="mx-5 px-2 rounded border border-orange-500 text-orange-500 bg-orange-100 text-sm">
            {{ t("billing_block.unverified_invoice") }}
          </span>
          <span
            v-else-if="verifactuEnabled && data.type.token == invoice_token && data.verifactu_invoice && (data.verifactu_invoice.response_status == 'Correcto' || data.verifactu_invoice.response_status == 'AceptadoConErrores')">
            <a :href="data.verifactu_invoice.verifactu_qr" target="_blank" class="cursor-pointer ml-6">
              <img src="/verifactu-logo.png" alt="Verifactu" class="h-5 inline-block mb-2" />
              <Icon name="material-symbols:qr-code" class="display-inline ml-1" />
            </a>
          </span>
          <span v-else-if="verifactuEnabled && data.verifactu_invoice"
            class="mx-5 px-2 rounded border border-red-500 text-red-500 bg-red-100 text-sm">
            {{ t("billing_block.error_verifying_invoice") }}
          </span>
        </H1Region>
        <OptionsDropdown v-if="objectPermissions?.can_change && !(isSubRegion && SubRegion)"
          id="ConnectionRequestRegionOptions">
          <div v-if="allow_changes">
            <div class="max-w-xs px-2">
              <span class="text-sm text-slate-500">{{ $t('informative_block.info_block_remittance') }}</span>
            </div>
            <hr class="my-2" />
          </div>
          <DropdownOption :name="data.type.token == invoice_token ?
            `${$t('common.check')} ${t('invoice').toLowerCase()}` :
            `${$t('common.check')} ${t('common.budget_detail').toLowerCase()}`" @click="showInvoice">
            <Icon name="fa6-solid:eye" class="display-inline mr-2" /> {{ data.type.token == invoice_token ?
              `${$t('common.check')} ${t('invoice').toLowerCase()}` :
              `${$t('common.check')} ${t('common.budget_detail').toLowerCase()}` }}
          </DropdownOption>
          <DropdownOption v-if="data.status?.token == status_pending_token" :name="data.type.token == invoice_token ?
            `${$t('common.modify')} ${t('invoice').toLowerCase()}` :
            `${$t('common.modify')} ${t('common.budget_detail').toLowerCase()}`"
            @click="showDetail('AddInvoiceBudget', data.id)">
            <Icon name="fa6-solid:pencil" class="display-inline mr-2" /> {{ data.type.token == invoice_token ?
              `${$t('common.modify')} ${t('invoice').toLowerCase()}` :
              `${$t('common.modify')} ${t('common.budget_detail').toLowerCase()}` }}
          </DropdownOption>
          <DropdownOption v-if="data.status?.token != status_canceled_token"
            :name="`${$t('customer_service_block.new_incident')}`" @click="showDetail('IncidentEdit', data.id)">
            <Icon name="fa6-solid:bug" class="display-inline mr-2" /> {{ $t('customer_service_block.new_incident') }}
          </DropdownOption>
          <DropdownOption v-if="data.status?.token != status_canceled_token && data.contract"
            :name="`${$t('common.send_communication')}`" @click="newCommunication">
            <Icon name="fa6-solid:share-from-square" class="display-inline mr-2" /> {{ $t('common.send_communication') }}
          </DropdownOption>
          <DropdownOption v-if="data.status?.token != status_pending_token"
            :name="`${t('common.generate')} ${t('invoice').toLowerCase()}`" @click="reGenerateInvoice">
            <Icon name="fa6-solid:file-pdf" class="display-inline mr-2" /> {{ `${t('common.generate')}
            ${t('invoice').toLowerCase()}` }}
          </DropdownOption>
          <DropdownOption v-if="data.status?.token != status_canceled_token"
            :name="`${t('common.send')} ${t('invoice').toLowerCase()}`" @click="openSendModal">
            <Icon name="fa6-solid:envelope" class="display-inline mr-2" /> {{ `${t('common.send')}
            ${t('invoice').toLowerCase()}` }}
          </DropdownOption>
          <DropdownOption v-if="data.status?.token != status_pending_token" :disabled="!data.accounting_office_final"
            :name="`${t('common.generate')} ${t('common.electronic_invoice').toLowerCase()}`"
            @click="generateElectronicInvoice">
            <Icon name="fa6-solid:file" class="display-inline mr-2" /> {{ `${t('common.generate')}
            ${t('common.electronic_invoice').toLowerCase()}` }}
          </DropdownOption>
          <DropdownOption
            v-if="data.status?.token != status_pending_token && data.status?.token != status_canceled_token"
            :disabled="allow_changes"
            :name="`${t('common.generate')} ${t('billing_block.payment').toLowerCase()}`"
            @click="modalsRef?.openDateModalForPayment(data.due_date)">
            <Icon name="fa6-solid:credit-card" class="display-inline mr-2" /> {{ `${t('common.generate')}
            ${t('billing_block.payment').toLowerCase()}` }}
          </DropdownOption>
          <!-- :disabled="data.status?.token == status_paid_token" -->
          <DropdownOption v-if="data.status?.token != status_canceled_token" :disabled="allow_changes ||
          (data.status?.token == status_paid_token && data.payment_type_token_final == 'BALANCE')"
            :name="`${t('common.change')} ${t('common.payment_method').toLowerCase()}`"
            @click="modalsRef?.openChangePaymentMethod()">
            <Icon name="fa6-solid:wallet" class="display-inline mr-2" /> {{ `${t('common.change')}
            ${t('common.payment_method').toLowerCase()}` }}
          </DropdownOption>
          <DropdownOption v-if="data.status?.token != status_canceled_token" :disabled="allow_changes"
            :name="`${t('common.change')} ${t('address_block.address').toLowerCase()}`"
            @click="modalsRef?.openChangeAddress()">
            <Icon name="fa6-solid:location-dot" class="display-inline mr-2" /> {{ `${t('common.change')}
            ${t('address_block.address').toLowerCase()}` }}
          </DropdownOption>
          <DropdownOption v-if="data.status?.token != status_canceled_token" :disabled="allow_changes"
            :name="`${t('common.change')} ${t('date.dates').toLowerCase()}`" @click="modalsRef?.openChangeDates()">
            <Icon name="fa6-solid:calendar-days" class="display-inline mr-2" /> {{ `${t('common.change')}
            ${t('date.dates').toLowerCase()}` }}
          </DropdownOption>
          <DropdownOption v-if="data.status?.token != status_canceled_token"
            :disabled="data.status?.token != status_paid_token || data.payment_type_token_final != 'DIRECT_DEBIT' || allow_changes"
            :name="`${t('common.generate')} ${t('common.return').toLowerCase()}`"
            @click="modalsRef?.openReturnReason()">
            <Icon name="fa6-solid:rotate-left" class="display-inline mr-2" /> {{ `${t('common.generate')}
            ${t('common.return').toLowerCase()}` }}
          </DropdownOption>
          <DropdownOption v-if="data.status?.token == status_pending_token" :disabled="data.refactor_invoice || allow_changes"
            :name="t('common.recalculate')" @click="handleRecalculate">
            <Icon name="fa6-solid:arrows-rotate" class="display-inline mr-2" /> {{ t('common.recalculate') }}
          </DropdownOption>
          <DropdownOption v-else :disabled="data.refactor_invoice || allow_changes"
            :name="t('billing_block.refactor')" @click="handleRefactor">
            <Icon name="fa6-solid:arrows-rotate" class="display-inline mr-2" /> {{ t('billing_block.refactor') }}
          </DropdownOption>
          <div v-if="data.type.token == invoice_token && data.status?.token != status_canceled_token">

            <DropdownOption v-if="data.status?.token == status_pending_token"
              :name="`${t('common.confirm')} ${t('invoice').toLowerCase()}`" @click="confirmInvoice">
              <Icon name="fa6-solid:check" class="display-inline mr-2" /> {{ `${t('common.confirm')}
              ${t('invoice').toLowerCase()}` }}
            </DropdownOption>
            <DropdownOption
              :disabled="data.status?.token == status_pending_token || data.status?.token == status_canceled_token || data.return_invoice != null || data.returned_invoice != null || allow_changes"
              :name="`${t('billing_block.return')} ${t('invoice').toLowerCase()}`" @click="modalsRef?.openLiquidate()">
              <Icon name="fa6-solid:arrow-left" class="display-inline mr-2" /> {{ `${t('billing_block.return')}
              ${t('invoice').toLowerCase()}` }}
            </DropdownOption>
            <DropdownOption v-if="data.status?.token != status_pending_token && data.status?.token != status_paid_token
              && data.status?.token != status_endowment_token
              && data.status?.token != status_commitment_token" :disabled="allow_changes" :name="`${$t('claim_block.new_commitment_deposit')}`"
              @click="getInvoiceInCommitment">
              <Icon name="fa6-solid:hand-holding-dollar" class="display-inline mr-2" /> {{
                $t('claim_block.new_commitment_deposit') }}
            </DropdownOption>
            <hr v-if="data.status?.token != status_irrecoverable_token && data.status?.token != status_paid_token"
              class="my-2" />
            <DropdownOption v-if="data.status?.token == status_paid_token"
              :disabled="data.payment_type_token_final == 'DIRECT_DEBIT' || allow_changes" :name="`${$t('billing_block.pass_pending')}`"
              @click="passToPending">
              <Icon name="fa6-solid:arrow-right" class="display-inline mr-2" /> {{ $t('billing_block.pass_pending') }}
            </DropdownOption>
            <!-- <DropdownOption v-if="data.status?.token != status_pending_token"
              :name="`${$t('common.cancel')} ${t('invoice').toLowerCase()}`"
              @click="changeStatus(status_canceled_token, true)">
              <Icon name="fa6-solid:xmark" class="display-inline mr-2" /> {{ `${$t('common.cancel')} ${t('invoice').toLowerCase()}` }}
            </DropdownOption> -->
            <DropdownOption
              v-if="data.status?.token != status_paid_token && data.status?.token != status_irrecoverable_token" :disabled="allow_changes"
              :name="`${$t('billing_block.irrecoverable_invoice')}`" @click="changeStatus(status_irrecoverable_token)">
              <Icon name="fa6-solid:circle-xmark" class="display-inline mr-2" /> {{
                $t('billing_block.irrecoverable_invoice') }}
            </DropdownOption>
            <DropdownOption
              v-if="data.status?.token != status_paid_token && data.status?.token != status_endowment_token && data.status?.token != status_irrecoverable_token"
              :disabled="allow_changes" :name="`${$t('contract_block.endowment_long')}`" @click="changeStatus(status_endowment_token)">
              <Icon name="fa6-solid:hand-holding-dollar" class="display-inline mr-2" /> {{
                $t('contract_block.endowment_long') }}
            </DropdownOption>
            <DropdownOption v-if="data.status?.token == status_endowment_token" :name="`${$t('billing_block.unendow')}`"
              :disabled="allow_changes" @click="changeStatus(status_confirmed_token)">
              <Icon name="fa6-solid:hand-holding-dollar" class="display-inline mr-2" /> {{ $t('billing_block.unendow')
              }}
            </DropdownOption>
            <hr v-if="verifactuEnabled && data.type.token == invoice_token && !data.verifactu_invoice" />
            <DropdownOption v-if="verifactuEnabled && data.type.token == invoice_token && !data.verifactu_invoice"
              :name="`${$t('billing_block.notify_verifactu')}`" @click="notifyVerifactuInvoice">
              <img src="/agencia-tributaria-logo.png" alt="Agencia Tributaria" class="h-4 inline-block mr-2 mb-1" /> {{
                $t('billing_block.notify_verifactu') }}
            </DropdownOption>
            <hr />
            <DropdownOption :name="t('common.history_changes')" @click="showHistory">
              <Icon name="fa6-solid:clock-rotate-left" class="display-inline mr-2" /> {{ t('common.history_changes') }}
            </DropdownOption>

          </div>
          <div v-else-if="data.type.token != invoice_token && data.status?.token != status_canceled_token">
            <DropdownOption v-if="!data.invoice_budget" :name="`${$t('billing_block.to_invoice')}`"
              @click="budgetToInvoice">
              <Icon name="fa6-solid:file-invoice" class="display-inline mr-2" /> {{ $t('billing_block.to_invoice') }}
            </DropdownOption>
            <!-- <DropdownOption v-if="!data.invoice_budget"
              :name="`${$t('billing_block.delete_budget')}`" @click="deleteBudget" class="text-red-500">
              <Icon name="fa6-solid:trash" class="display-inline mr-2" /> {{ $t('billing_block.delete_budget') }}
            </DropdownOption> -->
          </div>
          <hr />
          <DropdownOption :disabled="!(data.status?.token == status_pending_token || data.type.token != invoice_token) || !objectPermissions?.can_change"
            :name="data.type.token != invoice_token ? `${$t('billing_block.delete_budget')}` : `${$t('billing_block.delete_pre_invoice')}`" @click="openDeleteConfirmation = true" class="text-red-500">
            <Icon name="fa6-solid:trash" class="display-inline mr-2" /> 
            {{ data.type.token != invoice_token ? `${$t('billing_block.delete_budget')}` : `${$t('billing_block.delete_pre_invoice')}` }}
          </DropdownOption>
        </OptionsDropdown>
      </div>

      <div v-if="data" id="item_data" :data-rel=id>
        <InvoiceDetail @show-detail="showDetail" :id="invoiceId" :data="data" :isSubRegion="isSubRegion"
          :isBudget="isBudget" :commitmentDeposit="commitmentDeposit"></InvoiceDetail>
        <AtomsTabs class="py-2">
          <li class="me-2 ">
            <a href="#tab_payments" @click.prevent="setActiveTab('payments')"
              :class="{ 'text-sky-600 border-sky-600': activeTab === 'payments', 'hover:text-gray-600 hover:border-gray-300': activeTab !== 'payments' }">
              <Icon name="fa6-solid:credit-card" class="display-inline mr-2" /> {{ $t("billing_block.payments") }}
            </a>
          </li>
          <li class="me-2 ">
            <a href="#tab_remittances" @click.prevent="setActiveTab('remittances')"
              :class="{ 'text-sky-600 border-sky-600': activeTab === 'remittances', 'hover:text-gray-600 hover:border-gray-300': activeTab !== 'remittances' }">
              <Icon name="fa6-solid:file-export" class="display-inline mr-2" /> {{ $t("common.remittances") }}
            </a>
          </li>


          <li v-if="data.origin?.token === origin_reading" class="me-2">
            <a href="#tab_consumption" @click.prevent="setActiveTab('consumption')"
              :class="{ 'text-sky-600 border-sky-600': activeTab === 'consumption', 'hover:text-gray-600 hover:border-gray-300': activeTab !== 'consumption' }">
              <Icon name="fa6-solid:droplet" class="display-inline mr-2" /> {{ $t("billing_block.info_consumption") }}
            </a>
          </li>

          <li class="me-2">
            <a href="#tab_invoice_line_items" @click.prevent="setActiveTab('invoice_line_items')"
              :class="{ 'text-sky-600 border-sky-600': activeTab === 'invoice_line_items', 'hover:text-gray-600 hover:border-gray-300': activeTab !== 'invoice_line_items' }">
              <Icon name="fa6-solid:tags" class="display-inline mr-2" /> {{ $t("pricing_block.line_items") }}
            </a>
          </li>
          <li class="me-2">
            <a href="#tab_company_invoice" @click.prevent="setActiveTab('company_invoice')"
              :class="{ 'text-sky-600 border-sky-600': activeTab === 'company_invoice', 'hover:text-gray-600 hover:border-gray-300': activeTab !== 'company_invoice' }">
              <Icon name="fa6-solid:building" class="display-inline mr-2" /> {{ $t("billing_block.recapture") }}
            </a>
          </li>
          <li class="me-2">
            <a href="#tab_surcharge" @click.prevent="setActiveTab('surcharge')"
              :class="{ 'text-sky-600 border-sky-600': activeTab === 'surcharge', 'hover:text-gray-600 hover:border-gray-300': activeTab !== 'surcharge' }">
              <Icon name="fa6-solid:money-bill-wave" class="display-inline mr-2" />
              {{ $t("billing_block.surcharges") }} ({{ data.child_invoices?.length + (data?.parent_invoice ? 1 : 0) }})
            </a>
          </li>
          <li class="me-2">
            <a href="#tab_messages" @click.prevent="setActiveTab('messages')"
              :class="{ 'text-sky-600 border-sky-600': activeTab === 'messages', 'hover:text-gray-600 hover:border-gray-300': activeTab !== 'messages' }">
              <Icon name="fa6-solid:message" class="display-inline mr-2" /> {{ $t("messages") }} ({{ messageNumber }})
            </a>
          </li>
          <li class="me-2">
            <a href="#tab_status_change" @click.prevent="setActiveTab('status_change')"
              :class="{ 'text-sky-600 border-sky-600': activeTab === 'status_change', 'hover:text-gray-600 hover:border-gray-300': activeTab !== 'status_change' }">
              <Icon name="fa6-solid:person-walking-arrow-right" class="display-inline mr-2" /> {{
                $t("common.status_change") }}
              ({{ logNumber }})
            </a>
          </li>
          <li class="me-2">
            <a href="#tab_data_change" @click.prevent="setActiveTab('data_change')"
              :class="{ 'text-sky-600 border-sky-600': activeTab === 'data_change', 'hover:text-gray-600 hover:border-gray-300': activeTab !== 'data_change' }">
              <Icon name="fa6-solid:arrows-rotate" class="display-inline mr-2" /> {{
                $t("common.modifications") }}
              ({{ changeNumber }})
            </a>
          </li>

          <li class="me-2 ">
            <a href="#tab_incident" @click.prevent="setActiveTab('incident')"
              :class="{ 'text-sky-600 border-sky-600': activeTab === 'incident', 'hover:text-gray-600 hover:border-gray-300': activeTab !== 'incident' }">
              <Icon name="fa6-solid:bug" class="display-inline mr-2" /> {{ $t("common.incidents") }}
            </a>
          </li>

        </AtomsTabs>

        <div id="invoice_tabpanels">
          <!-- panells -->

          <section v-show="activeTab === 'status_change'" role="tabpanel" id="tab_status_change"
            class="bg-white antialiased">
            <MoleculesLogList v-if="data" entity="invoice-status" parent_entity="invoice" :id="invoiceId"
              @update:count="updateLogCount" :service="$LoggerApiService">
            </MoleculesLogList>
          </section>

          <section v-show="activeTab === 'data_change'" role="tabpanel" id="tab_data_change"
            class="bg-white antialiased">
            <MoleculesInvoiceDataLog :reload="reloadLog" :id="invoiceId" @update:count="updateChangeCount" />
          </section>

          <section v-show="activeTab === 'incident'" role="tabpanel" id="tab_incident" class="bg-white antialiased">
            <IncidentList :invoice_id="invoiceId" @show-detail="showDetail" :isSubRegion="isSubRegion" />
          </section>

          <section v-show="activeTab === 'consumption'" role="tabpanel" id="tab_consumption"
            class="bg-white antialiased">
            <InvoiceConsumptionDetail :data="data" :isSubRegion="isSubRegion" @show-detail="showDetail" />
          </section>

          <section v-show="activeTab === 'payments'" role="tabpanel" id="tab_payments" class="bg-white antialiased">
            <div class="mt-2">
              <InvoicePaymentDetail :invoice_id="invoiceId" @show-detail="showDetail" :isSubRegion="isSubRegion"
                @generate-payment-proof="(id, payment_date) => modalsRef?.openPaymentProof(id, payment_date)" />
            </div>
          </section>

          <section v-show="activeTab === 'invoice_line_items'" role="tabpanel" id="tab_invoice_line_items"
            class="bg-white antialiased">
            <div class="mt-2">
              <InvoiceLineItemDetailInvoice :invoice_id="invoiceId" @show-detail="showDetail"
                :isSubRegion="isSubRegion" />
            </div>
          </section>

          <section v-show="activeTab === 'company_invoice'" role="tabpanel" id="tab_company_invoice"
            class="bg-white antialiased">
            <div class="mt-2">
              <InvoiceLineItemDetailInvoice :invoice_id="invoiceId" :by_company="true" @show-detail="showDetail"
                :isSubRegion="isSubRegion" />
            </div>
          </section>

          <section v-show="activeTab === 'surcharge'" role="tabpanel" id="tab_surcharge" class="bg-white antialiased">
            <div class="mt-2">
              <InvoiceSurchargeDetail :item="data" @show-region="showDetail" :isSubRegion="isSubRegion" />
            </div>
          </section>

          <section v-show="activeTab === 'messages'" role="tabpanel" id="tab_messages" class="bg-white antialiased">
            <div class="mt-2">
              <span class="footering text-sm text-slate-500">
                {{ t('common.no_records') }}
              </span>
            </div>
          </section>

          <section v-show="activeTab === 'remittances'" role="tabpanel" id="tab_remittances"
            class="bg-white antialiased max-h-[50vh] overflow-y-auto">
            <table class="w-full text-sm">
              <thead class="bg-slate-50 sticky top-0 border-b border-slate-100 z-[1]">
                <tr>
                  <th class="px-4 py-2 text-left font-medium text-slate-500 w-6/12">{{
                    $t('common.remittance') }}</th>
                  <th class="px-4 py-2 text-left font-medium text-slate-500 w-3/12">{{ $t('customer_service_block.sent')
                    }}</th>
                  <th class="px-4 py-2 text-right font-medium text-slate-500 w-3/12">{{
                    $t('customer_service_block.sent_by')
                    }}</th>
                </tr>
              </thead>
              <tbody class="divide-y divide-slate-50">
                <tr v-if="!data.remittances || !data.remittances.length">
                  <td class="px-1 py-3 text-center text-slate-400 italic">{{ $t('common.no_records') }}</td>
                </tr>
                <tr v-for="remittance in data.remittances" :key="remittance.id" class="hover:bg-slate-50/50">
                  <td class="px-4 py-2 flex items-center gap-x-2">
                    <span>{{ remittance.token }}</span>
                    <AtomsRedirectButton :id="remittance.id" :path="'/billing/sepa/'" />
                  </td>
                  <td class="px-4 py-2">
                    <span>{{ remittance.sent_at ? formatDate(remittance.sent_at) : '-' }}</span>
                  </td>
                  <td class="px-4 py-2 text-right font-medium">
                    {{ remittance.sent_by ? remittance.sent_by : '-' }}
                  </td>
                </tr>
              </tbody>
            </table>

          </section>

        </div>

      </div><!-- end if data -->
    </div><!-- end if pending -->

    <Teleport to="body">
      <div v-if="SubRegion == true && showRegionDetailComponent != 'PersonBankSelect'" role="region" id="subregion"
        class="h-full border-l border-gray-100 transition-all duration-500 ease text-base bg-white flex flex-col overflow-hidden shadow-2xl fixed top-0 right-0 w-[48vw] z-50"
        :class="{
          'translate-x-0': SubRegion,
          'translate-x-full': !SubRegion,
        }">
        <div id="region_nav" class="mb-3 px-3">
          <button @click="closeSubRegion()" class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300">
            <Icon name="fa6-solid:angles-right" class="text-slate-500" />
          </button>
        </div>
        <div class="pl-10 flex-1 overflow-y-auto pb-24 pr-2">
          <ContractRegion v-if="showRegionDetailComponent === 'ContractRegion'" :id="regionDetailId"
            :isSubRegion="true" />
          <ContractRequestRegion v-if="showRegionDetailComponent === 'ContractRequestRegion'" :id="regionDetailId"
            :isSubRegion="true" />
          <ExploitationRegion v-if="showRegionDetailComponent === 'ExploitationRegion'" :id="regionDetailId"
            :isSubRegion="true" />
          <ContractTerminationRegion v-if="showRegionDetailComponent === 'ContractTerminationRegion'" :id="regionDetailId"
            :isSubRegion="true" />
          <OrganismsCompanyRegion v-if="showRegionDetailComponent === 'CompanyRegion'" :id="regionDetailId"
            :isSubRegion="true" />
          <PaymentRegion v-if="showRegionDetailComponent === 'PaymentRegion'" :id="regionDetailId" :isSubRegion="true"
            @changed="updateSubRegion()" @close="updateSubRegion" />
          <CommitmentDepositRegion v-if="showRegionDetailComponent === 'CommitmentDepositRegion'" :id="regionDetailId"
            :isSubRegion="true" @changed="updateSubRegion()" />
          <LineItemTypeRegion v-if="showRegionDetailComponent === 'LineItemTypeRegion'" :id="regionDetailId"
            :isSubRegion="true" />
          <PriceRateRegion v-if="showRegionDetailComponent === 'PriceRateRegion'" :id="regionDetailId"
            :isSubRegion="true" />
          <InvoiceRegion v-if="showRegionDetailComponent === 'InvoiceRegion'" :id="regionDetailId" :isSubRegion="true" />
          <OrganismsProductRegion v-if="showRegionDetailComponent === 'ProductRegion'" :id="regionDetailId"
            :isSubRegion="true" />
          <SEPAManagementViewDocument v-if="showRegionDetailComponent === 'SEPADocumentRegion'" :document="regionDetailId"
            :isSubRegion="true" />
          <ChangeStatus v-if="showRegionDetailComponent === 'ChangeStatus'" entity="invoice" parent_entity="invoice"
            :id="invoiceId" :status="data.status?.id" module="billing" :reasonToken="status_irrecoverable_token"
            @changed="updateSubRegion" :forceToken="forceToken" />
          <IncidentEdit v-if="showRegionDetailComponent == 'IncidentEdit'" :invoice_id="regionDetailId"
            @change="updateSubRegion()" />
          <IncidentRegion v-if="showRegionDetailComponent === 'IncidentRegion'" :id="parseInt(regionDetailId)"
            :isSubRegion="true" />
          <AddInvoiceBudget v-if="showRegionDetailComponent == 'AddNewInvoiceBudget'" :object_id="object_id"
            :in_invoice="data" :service="service" :entity="entity" :persons="persons" @change="updateSubRegion"
            :isSubRegion="true" :isSubSubRegion="true" :reset="true" @close="closeSubRegion" />
          <InvoiceViewEdit v-if="showRegionDetailComponent === 'AddInvoiceBudget'" :id="data.id"
            @changed="updateSubRegion(false)" :allowLineItemTypeManual="true" :isSubRegion="true" />
          <ModelLogs v-if="showRegionDetailComponent === 'InvoiceLogs'" :object_id="regionDetailId"
            :object_token="data?.serie_final" :service="$InvoiceApiService"
            :title="`${t('common.history_changes')} ${data?.serie_final || ''}`" />
        </div>
      </div>
    </Teleport>
  </div><!-- end region__content -->


  <Teleport to="body">
    <div v-if="showRegionDetailComponent == 'PersonBankSelect'" role="region" id="right_page"
      class="fixed top-0 right-0 w-[95%] h-[100vh] border-l border-gray-100 transition-all duration-500 ease py-2 text-base bg-white overflow-y-auto overflow-x-hidden z-[100]"
      :class="{
        'translate-x-0': showRegionDetailComponent == 'PersonBankSelect',
        'translate-x-full': showRegionDetailComponent != 'PersonBankSelect',
      }">
      <div id="region_nav" class="mb-3 px-3">
        <button @click="closeSubRegion()" class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300">
          <Icon name="fa6-solid:angles-right" class="text-slate-500" />
        </button>
      </div>
      <div class="px-10">
        <PersonBankSelect :title="`${$t('common.select')} ${$t('common.iban')}`" :persons="localPersons"
          @selected-item="onPersonBankSelected" />
      </div>
    </div>
  </Teleport>
</template>
