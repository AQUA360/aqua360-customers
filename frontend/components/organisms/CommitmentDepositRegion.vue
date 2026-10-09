<script setup>
import { useRouter } from 'vue-router';
import H1Region from '~/components/atoms/H1Region.vue';
import AppLoading from '~/components/atoms/AppLoading.vue';
import OptionsDropdown from '~/components/molecules/OptionsDropdown.vue';
import DropdownOption from '~/components/atoms/DropdownOption.vue';
import CommitmentDepositDetail from '../molecules/CommitmentDepositDetail.vue';
import InvoiceMiniDetail from '../molecules/InvoiceMiniDetail.vue';
import InvoiceRegion from './InvoiceRegion.vue';
import ContractRegion from './ContractRegion.vue';
import PaymentCommitmentList from '../molecules/PaymentCommitmentList.vue';
import CommitmentDepositMovements from '../atoms/CommitmentDepositMovements.vue';
import AddCommitmentPayment from '../molecules/AddCommitmentPayment.vue';
import AddWalletCommitmentPayment from '../molecules/AddWalletCommitmentPayment.vue';
import PaymentCommitmentWalletList from '../molecules/PaymentCommitmentWalletList.vue';
import PaymentRegion from './PaymentRegion.vue';
import SEPAManagementViewDocument from './SEPAManagementViewDocument.vue';
import PayCommitmentInvoice from '../molecules/PayCommitmentInvoice.vue';
import IncidentEdit from '../molecules/IncidentEdit.vue';
import IncidentList from '../molecules/IncidentList.vue';
import IncidentRegion from './IncidentRegion.vue';
import ReturnCommimentPayment from '../molecules/ReturnCommimentPayment.vue';
import { usePermissions } from '~/middleware/permission';
import { useToast } from 'vue-toastification';
import { openAuthenticatedFileUrl } from '~/utils/open-authenticated-file';
const { t } = useI18n();
const toast = useToast();
const { permissions, loading } = usePermissions();
const props = defineProps({
  id: Number, // ID de l'element
  isSubRegion: false,
  isSubRegionOpen: Boolean
});

const emit = defineEmits(['show-subregion', 'changed', 'close-subregion']);

const router = useRouter();
const { $CommitmentDepositApiService, $ConfigProjectApiService, $PaymentApiService } = useNuxtApp();
const pending = ref(true);
const error = ref(null);
const data = ref(null);
const objectPermissions = ref(null);
const activeTab = ref('invoices');
const observationNumber = ref(0)
const paymentsNumber = ref(0)
const movementsNumber = ref(0)
const historyNumber = ref(0)
const walletNumber = ref(0)

const SubRegion = ref(props.isSubRegionOpen);
const showRegionDetailComponent = ref(null);
const regionDetailId = ref(null);

const cancelStatusDepositToken = ref(null)
const paidStatusDepositToken = ref(null)
const useDocumentToken = ref(false)

const openDateModal = ref(false);
const selectedPaymentDate = ref(null);
const selectedPaymentId = ref(null);
const allowChanges = ref(true)

const openPaymentProofModal = ref(false);
const selected_payment_proof_id = ref(null);
const selected_payment_proof_date = ref(null);
const payment_proof_observation = ref('');

const updateObservationCount = (num) => {
  observationNumber.value = num;
}

const updatePaymentsCount = (num) => {
  paymentsNumber.value = num;
}

const updateMovementsCount = (num) => {
  movementsNumber.value = num;
}

const updateHistoryCount = (num) => {
  historyNumber.value = num;
}

const updateWalletCount = (num) => {
  walletNumber.value = num;
}

watch(() => props.isSubRegionOpen, (newValue) => {
  SubRegion.value = newValue;
});

const getPermissions = async () => {
  error.value = null;
  try {
    const data = await $CommitmentDepositApiService.getPermissions();
    objectPermissions.value = data;
  } catch (err) {
    error.value = err;
  }
}

const getData = async () => {
  if (!objectPermissions.value?.can_view) {
    emit('close-subregion');
    return
  }
  pending.value = true;
  error.value = null;
  try {
    const result = await $CommitmentDepositApiService.getDetail(props.id);
    data.value = result;
    allowChanges.value = !(data.value.joined_payments && data.value.joined_payments.some(joined_payment => !joined_payment.allow_change)) && !(data.value.remittances && data.value.remittances.some(remittance => !remittance.sent_at));
  } catch (err) {
    error.value = err;
  } finally {
    pending.value = false;
  }
}

const cancelDeposit = async () => {
  if (!confirm(t("confirmation_text_block.confirm_cancel"))) return
  let save_data = {
    id: props.id,
    status_token: cancelStatusDepositToken.value,
  }
  await $CommitmentDepositApiService.save(save_data);
  refresh(true)
}

const manageInvoices = async () => {
  await router.push('/billing/commitment-deposits/edit/' + props.id)
}

const getCommitmentDocument = async () => {
  try {

    const file = await $CommitmentDepositApiService.getCommitmentFile(props.id);

    //when downloading, allow user to select download folder instead of default download folder
    const link = document.createElement('a');
    const file_url = URL.createObjectURL(file);
    link.href = file_url
    link.download = t('claim_block.debt_acknowledgment').replace(/ /g, '_') + '_' + data.value.token + '.pdf';

    link.click();

    setTimeout(() => {
      window.URL.revokeObjectURL(file_url);
    }, 250);

  } catch (error) {
    console.log(error)
  }
}

const openModalDate = (paymentId, paymentDate) => {
  selectedPaymentId.value = paymentId;
  selectedPaymentDate.value = paymentDate;
  openDateModal.value = true;
}

const paymentProofModal = (id, date) => {
  selected_payment_proof_id.value = id;
  selected_payment_proof_date.value = date;
  openPaymentProofModal.value = true;
}

const generatePaymentDoc = async () => {
  try {
    const file = await $PaymentApiService.regeneratePDF(selectedPaymentId.value, selectedPaymentDate.value);
    await openAuthenticatedFileUrl(file.pdf_url);
    toast.success(t('common.correct_save'));

    openDateModal.value = false
    selectedPaymentId.value = null;
    selectedPaymentDate.value = null;

    // Refresquem les dades ja que el back ha actualitzat el registre
    await getData(false);
  } catch (error) {
    console.error(error);
    toast.error(t('common.error'));
  }
}

const generatePaymentProofDoc = async () => {
  try {
    let save_data = {
      id: selected_payment_proof_id.value,
      date: selected_payment_proof_date.value,
      observation: payment_proof_observation.value
    }
    const file = await $PaymentApiService.generatePaymentProofDoc(save_data);
    await openAuthenticatedFileUrl(file.pdf_url);
    openPaymentProofModal.value = false;
    selected_payment_proof_id.value = null;
    selected_payment_proof_date.value = null;
    payment_proof_observation.value = '';
  } catch (error) {
    console.error(error)
  }
}

const saveBalance = async () => {
  if (!confirm(t("confirmation_text_block.confirm_apply"))) return
  try {
    const response = await $CommitmentDepositApiService.saveBalance(props.id);
    if (response) {
      toast.success(t("common.correct_save"))
      refresh(true)
    }
  } catch (error) {
    console.error(error)
  }
}


const liquidateAll = async () => {
  if (!confirm(t("confirmation_text_block.confirm_liquidate_all"))) return
  await $CommitmentDepositApiService.liquidateAll(props.id)
  refresh(true)
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

const showDetail = function (component, id) {
  showRegionDetailComponent.value = component
  regionDetailId.value = id;
  showSubRegion();
}

const refresh = async (close = true) => {
  await getData()
  if (close) closeSubRegion()
  emit('changed')
}

const setActiveTab = (tab) => {
  activeTab.value = tab;
}

watch(() => props.id, () => {
  getData();
});

onMounted(async () => {
  await getPermissions();
  if (objectPermissions.value?.can_view) {
    cancelStatusDepositToken.value = await $ConfigProjectApiService.get('commitment_deposit_status_cancelled_token')
    paidStatusDepositToken.value = await $ConfigProjectApiService.get('commitment_deposit_status_paid_token')
    useDocumentToken.value = await $ConfigProjectApiService.get('commitment_deposit_document')
    getData();
  } else {
    toast.error(t('common.no_permissions'));
    emit('close-subregion');
  }
});

</script>

<template>
  <div class="region__content h-full">
    <div v-if="pending || loading">
      <AppLoading :text="$t('common.loading')" />
    </div>
    <div v-else-if="error">
      <p>{{ $t('common.error') }}: {{ error.message }}</p>
      <p><button @click="getData" class="underline text-sky-500 hover:no-underline">{{ $t('common.load_again')
      }}</button></p>
    </div>
    <div v-else-if="objectPermissions?.can_view" class="pr-2 relative pb-24 flex-1 min-h-0 transition-all duration-500 ease"
      :class="{ 'h-full overflow-y-auto': !isSubRegion, 'mr-[48vw]': SubRegion }">
      <div v-if="openDateModal" class="fixed inset-0 z-50 flex items-center justify-center overflow-y-auto">
        <div class="bg-white rounded-lg shadow-xl p-6 max-w-lg w-full mx-4 my-auto relative">
          <button @click="selectedPaymentDate = null; openDateModal = false"
            class="absolute top-4 right-4 text-gray-500 hover:text-gray-700">
            <Icon name="fa6-solid:xmark" class="text-xl" />
          </button>
          <div class="">
            <label class="block font-medium text-slate-500">{{ $t('common.select') }} {{ t('billing_block.payment_date')
              }}</label>
            <div class="py-4 px-1 rounded-lg text-left max-h-[60vh] overflow-y-auto">
              <AtomsInputDate v-model="selectedPaymentDate" :label="''" class="" />
            </div>
          </div>
          <div class="flex justify-end">
            <button class="button-primary" @click="generatePaymentDoc"
              :disabled="!selectedPaymentDate || selectedPaymentDate == ''">
              {{ $t('common.generate') }}
            </button>
          </div>
        </div>
      </div>
      <div v-if="openPaymentProofModal" class="fixed inset-0 z-50 flex items-center justify-center overflow-y-auto">
        <div class="bg-white rounded-lg shadow-xl p-6 max-w-lg w-full mx-4 my-auto relative">
          <button
            @click="selected_payment_proof_id = null; selected_payment_proof_date = null; payment_proof_observation = ''; openPaymentProofModal = false"
            class="absolute top-4 right-4 text-gray-500 hover:text-gray-700">
            <Icon name="fa6-solid:xmark" class="text-xl" />
          </button>
          <div class="">
            <label class="block font-medium text-slate-500">{{ $t('common.select') }} {{ t('billing_block.payment_date')
              }}</label>
            <div class="py-4 px-1 rounded-lg text-left max-h-[60vh] overflow-y-auto">
              <AtomsInputDate v-model="selected_payment_proof_date" :label="''" class="" />
            </div>
          </div>
          <div class="">
            <label class="block font-medium text-slate-500">{{ t('common.observation') }}</label>
            <div class="py-4 px-1 rounded-lg text-left max-h-[60vh] overflow-y-auto">
              <textarea name="observation" id="observation" cols="30" rows="2" v-model="payment_proof_observation"
                class="w-full border border-slate-300 rounded-md p-2 focus:outline-none focus:border-primary"></textarea>
            </div>
          </div>
          <div class="flex justify-end">
            <button class="button-primary" @click="generatePaymentProofDoc"
              :disabled="!selected_payment_proof_id || selected_payment_proof_id == '' || !selected_payment_proof_date || selected_payment_proof_date == ''">
              {{ $t('common.generate') }}
            </button>
          </div>
        </div>
      </div>
      <div v-if="openDateModal || openPaymentProofModal"
        class="fixed inset-0 bg-black bg-opacity-50 h-[150vh] z-20 flex items-center justify-center">
      </div>
      <div class="flex justify-between relative mb-3">
        <H1Region class="">{{ $t('commitment_deposit') }}</H1Region>
        <OptionsDropdown v-if="objectPermissions?.can_change" id="CommitmentDepositRegionOptions">
          <DropdownOption :disabled="data.status.token == paidStatusDepositToken" name="Afegir factures"
            @click="manageInvoices">
            <Icon name="fa6-solid:file-invoice" class="display-inline mr-2" /> {{ t('common.add') }} {{ t('invoices') }}
          </DropdownOption>
          <DropdownOption :disabled="!useDocumentToken"
            :name="t('common.download') + ' ' + t('claim_block.short_debt_acknowledgment')"
            @click="getCommitmentDocument">
            <Icon name="fa6-solid:download" class="display-inline mr-2" /> {{ t('common.download') }} {{
              t('claim_block.short_debt_acknowledgment') }}
          </DropdownOption>
          <DropdownOption
            :disabled="data.status.token == paidStatusDepositToken || data.status.token == cancelStatusDepositToken || !allowChanges || data.total_pending_payments == 0"
            :name="t('common.requesting') + ' ' + t('billing_block.payment')"
            @click="showDetail('AddWalletDepositPaymentRegion', props.id)">
            <Icon name="fa6-solid:file-export" class="display-inline mr-2" /> {{ t('common.requesting') }} {{
              t('billing_block.payment') }}
          </DropdownOption>
          <DropdownOption
            :disabled="data.status.token == paidStatusDepositToken || data.status.token == cancelStatusDepositToken || !allowChanges || data.total_pending_payments == 0"
            :name="`${t('common.introduce')} ${t('billing_block.payment')}`" @click="showDetail('AddDepositPaymentRegion', props.id)">
            <Icon name="fa6-solid:money-bill-transfer" class="display-inline mr-2" /> {{ t('common.introduce') }} {{
              t('billing_block.payment') }}
          </DropdownOption>
          <DropdownOption :disabled="!data.usable_remaining"
            :name="t('common.liquidate') + ' ' + t('billing_block.payment')"
            @click="showDetail('LiquidateDepositPaymentRegion', props.id)">
            <Icon name="fa6-solid:coins" class="display-inline mr-2" /> {{ t('common.liquidate') }} {{
              t('billing_block.payment') }}
          </DropdownOption>
          <DropdownOption :disabled="(data.remaining_to_share != data.total_pending_invoices)"
            :name="t('common.liquidate') + ' ' + t('billing_block.payment') + ' ' + t('common.all')"
            @click="liquidateAll">
            <Icon name="fa6-solid:coins" class="display-inline mr-2" /> {{ t('common.liquidate') }} {{ t('common.all')
            }}
          </DropdownOption>
          <DropdownOption :name="t('common.return_action') + ' ' + t('billing_block.payment')"
            @click="showDetail('ReturnCommitmentPaymentRegion', props.id)" :disabled="!allowChanges">
            <Icon name="fa6-solid:arrow-rotate-left" class="display-inline mr-2" /> {{ t('common.return_action') }} {{
              t('billing_block.payment') }}
          </DropdownOption>
          <DropdownOption :name="t('customer_service_block.new_incident')"
            @click="showDetail('IncidentEdit', props.id)">
            <Icon name="fa6-solid:bug" class="display-inline mr-2" /> {{ t('customer_service_block.new_incident') }}
          </DropdownOption>
          <DropdownOption
            :disabled="data.status.token != cancelStatusDepositToken || data.remaining_to_share == 0 || !allowChanges"
            :name="t('contract_block.save_balance')" @click="saveBalance">
            <Icon name="fa6-solid:circle-xmark" class="display-inline mr-2" /> {{ t('contract_block.save_balance') }}
          </DropdownOption>
          <DropdownOption :disabled="data.status.token == paidStatusDepositToken || !allowChanges"
            :name="t('common.cancel') + ' ' + t('claim_block.commitment')" @click="cancelDeposit">
            <Icon name="fa6-solid:circle-xmark" class="display-inline mr-2" /> {{ t('common.cancel') }} {{
              t('claim_block.commitment') }}
          </DropdownOption>
        </OptionsDropdown>
      </div>

      <div v-if="data" id="item_data" :data-rel=id>
        <div v-if="data.usable_remaining && data.status.token != cancelStatusDepositToken"
          class="mb-4 bg-orange-50 border-l-4 border-orange-400">
          <p class="text-orange-500 ml-2 font-semibold">
            {{ $t("informative_block.info_commitment_liquidable") }}
          </p>
        </div>
        <CommitmentDepositDetail :id="props.id" :data="data" @show-detail="showDetail" :isSubRegion="isSubRegion" />
      </div>

      <AtomsTabs>

        <li class="me-2">
          <a href="#tab_invoices" @click.prevent="setActiveTab('invoices')"
            :class="{ 'text-sky-600 border-sky-600': activeTab === 'invoices', 'hover:text-gray-600 hover:border-gray-300': activeTab !== 'invoices' }"
            aria-current="page">
            <Icon name="fa6-solid:file-invoice" class="display-inline mr-2" />
            {{ $t("invoices") }} ({{ data.invoices?.length || 0 }})
          </a>
        </li>
        <li class="me-2">
          <a href="#tab_movements" @click.prevent="setActiveTab('movements')"
            :class="{ 'text-sky-600 border-sky-600': activeTab === 'movements', 'hover:text-gray-600 hover:border-gray-300': activeTab !== 'movements' }">
            <Icon name="fa6-solid:credit-card" class="display-inline mr-2" />
            {{ $t("claim_block.fractions_paid") }} ({{ paymentsNumber || 0 }})
          </a>
        </li>
        <li class="me-2">
          <a href="#tab_payments" @click.prevent="setActiveTab('payments')"
            :class="{ 'text-sky-600 border-sky-600': activeTab === 'payments', 'hover:text-gray-600 hover:border-gray-300': activeTab !== 'payments' }">
            <Icon name="fa6-solid:credit-card" class="display-inline mr-2" />
            {{ $t("claim_block.fractions") }} ({{ movementsNumber || 0 }})
          </a>
        </li>
        <li class="me-2">
          <a href="#tab_wallet" @click.prevent="setActiveTab('wallet')"
            :class="{ 'text-sky-600 border-sky-600': activeTab === 'wallet', 'hover:text-gray-600 hover:border-gray-300': activeTab !== 'wallet' }"
            aria-current="page">
            <Icon name="fa6-solid:briefcase" class="display-inline mr-2" />
            {{ $t("claim_block.wallet_mov") }} ({{ walletNumber || 0 }})
          </a>
        </li>
        <li class="me-2">
          <a href="#tab_remittances" @click.prevent="setActiveTab('remittances')"
            :class="{ 'text-sky-600 border-sky-600': activeTab === 'remittances', 'hover:text-gray-600 hover:border-gray-300': activeTab !== 'remittances' }">
            <Icon name="fa6-solid:list" class="display-inline mr-2" />
            {{ $t('common.remittances') }} ({{ data.remittances?.length || 0 }})
          </a>
        </li>
        <li class="me-2">
          <a href="#tab_joined_payments" @click.prevent="setActiveTab('joined_payments')"
            :class="{ 'text-sky-600 border-sky-600': activeTab === 'joined_payments', 'hover:text-gray-600 hover:border-gray-300': activeTab !== 'joined_payments' }">
            <Icon name="fa6-solid:list" class="display-inline mr-2" />
            {{ $t('billing_block.joined_payments') }} ({{ data.joined_payments?.length || 0 }})
          </a>
        </li>
        <li class="me-2">
          <a href="#tab_incident" @click.prevent="setActiveTab('incident')"
            :class="{ 'text-sky-600 border-sky-600': activeTab === 'incident', 'hover:text-gray-600 hover:border-gray-300': activeTab !== 'incident' }"
            aria-current="page">
            <Icon name="fa6-solid:bug" class="display-inline mr-2" />
            {{ $t("common.incidents") }} ({{ data.incidents || 0 }})
          </a>
        </li>
        <li class="me-2">
          <a href="#tab_history" @click.prevent="setActiveTab('history')"
            :class="{ 'text-sky-600 border-sky-600': activeTab === 'history', 'hover:text-gray-600 hover:border-gray-300': activeTab !== 'history' }"
            aria-current="page">
            <Icon name="fa6-solid:list" class="display-inline mr-2" />
            {{ $t("common.history") }} ({{ historyNumber || 0 }})
          </a>
        </li>
        <li class="me-2">
          <a href="#tab_observations" @click.prevent="setActiveTab('observations')"
            :class="{ 'text-sky-600 border-sky-600': activeTab === 'observations', 'hover:text-gray-600 hover:border-gray-300': activeTab !== 'observations' }"
            aria-current="page">
            <Icon name="fa6-solid:note-sticky" class="display-inline mr-2" /> {{ $t('common.observations') }} ({{
              observationNumber }})
          </a>
        </li>

      </AtomsTabs>

      <section v-show="activeTab === 'observations'" role="tabpanel" id="tab_observations" class="bg-white antialiased">
        <MoleculesObservationList v-if="data" @update:observation-count="updateObservationCount"
          parent_entity="commitment_deposit" url_entity="commitment-deposit" :id="props.id" module="billing">
        </MoleculesObservationList>
      </section>

      <section v-show="activeTab === 'payments'" role="tabpanel" id="tab_payments" class="bg-white antialiased p-1">
        <PaymentCommitmentList :id="props.id" @show-detail="showDetail" :isGuide="true"
          @update:count="updateMovementsCount" />
      </section>

      <section v-show="activeTab === 'incident'" role="tabpanel" id="tab_incident" class="bg-white antialiased p-1">
        <IncidentList :commitment_id="props.id" @show-detail="showDetail" :isSubRegion="isSubRegion" />
      </section>

      <section v-show="activeTab === 'wallet'" role="tabpanel" id="tab_wallet" class="bg-white antialiased p-1">
        <PaymentCommitmentWalletList :id="props.id" @show-detail="showDetail" @update:count="updateWalletCount" :allowChanges="allowChanges"
          :isSubRegion="isSubRegion" @open-date-modal="openModalDate" @generate-payment-proof="paymentProofModal" />
      </section>

      <section v-show="activeTab === 'movements'" role="tabpanel" id="tab_movements" class="bg-white antialiased p-1">
        <PaymentCommitmentList :id="props.id" @show-detail="showDetail" @update:count="updatePaymentsCount" />
      </section>

      <section v-show="activeTab === 'history'" role="tabpanel" id="tab_history"
        class="bg-white antialiased p-1 h-[50vh] overflow-y-auto">
        <CommitmentDepositMovements :id="props.id" @update:count="updateHistoryCount" />
      </section>

      <section v-show="activeTab === 'invoices'" role="tabpanel" id="tab_invoices" class="bg-white antialiased p-1">
        <InvoiceMiniDetail v-if="data.invoices && data.invoices.length != 0" :item="data.invoices"
          @show-detail="showDetail" :is_info="true" :isSubRegion="isSubRegion" :show_payments="true" />
        <div v-else class="p-2">
          <div class="footering text-slate-500 p-2">
            {{ t('common.no_data_found') }}
          </div>
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
              <td class="py-3 text-center text-slate-400">{{ $t('common.no_records') }}</td>
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
      <section v-show="activeTab === 'joined_payments'" role="tabpanel" id="tab_joined_payments"
        class="bg-white antialiased max-h-[50vh] overflow-y-auto">
        <table class="w-full text-sm">
          <thead class="bg-slate-50 sticky top-0 border-b border-slate-100 z-[1]">
            <tr>
              <th class="px-4 py-2 text-left font-medium text-slate-500 w-2/12">{{
                $t('billing_block.joined_payment') }}</th>
              <th class="px-4 py-2 text-left font-medium text-slate-500 w-2/12">{{ $t('billing_block.payment')
              }}</th>
              <th class="px-4 py-2 text-left font-medium text-slate-500 w-2/12">{{ $t('common.status')
              }}</th>
              <th class="px-4 py-2 text-left font-medium text-slate-500 w-2/12">{{ $t('common.amount')
              }}</th>
              <th class="px-4 py-2 text-left font-medium text-slate-500 w-4/12">{{
                $t('common.payment_method')
              }}</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-slate-50">
            <tr v-if="!data.joined_payments || !data.joined_payments.length">
              <td class="py-3 text-center text-slate-400">{{ $t('common.no_records') }}</td>
            </tr>
            <tr v-for="joined_payment in data.joined_payments" :key="joined_payment.id" class="hover:bg-slate-50/50">
              <td class="px-4 py-2 flex items-center gap-x-2">
                <span>{{ joined_payment.token }}</span>
                <AtomsRedirectButton :id="joined_payment.id" :path="'/billing/joined-payments/'" />
              </td>
              <td class="px-4 py-2">
                <span>{{ joined_payment.payment_date ? formatDate(joined_payment.payment_date) : '-' }}</span>
              </td>
              <td class="px-4 py-2">
                <AtomsColorBadge :value="joined_payment.status_name" :color="joined_payment.status_color" />
              </td>
              <td class="px-4 py-2">
                <span>{{ joined_payment.total_final ? formatMoneyWithCurrency(joined_payment.total_final) : '-'
                  }}</span>
              </td>
              <td class="px-4 py-2">
                <span>{{ joined_payment.payment_type }}</span>
              </td>
            </tr>
          </tbody>
        </table>

      </section>

    </div><!-- end if pending -->

    <div v-if="SubRegion == true" role="region" id="subregion"
      class="h-full border-l border-gray-100 transition-all duration-500 ease text-base bg-white flex flex-col overflow-hidden fixed top-0 right-0 w-[48vw] z-50"
      :class="{ 'translate-x-0': SubRegion, 'translate-x-full': !SubRegion }">
      <div id="region_nav" class="mb-3 px-3">
        <button @click="closeSubRegion()" class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300">
          <Icon name="fa6-solid:angles-right" class="text-slate-500" />
        </button>
      </div>
      <div class="pl-10 flex-1 overflow-y-auto pb-24 pr-2">
        <InvoiceRegion v-if="showRegionDetailComponent === 'InvoiceRegion'" :id="regionDetailId" :isSubRegion="true"
          @update-id="(newId) => regionDetailId = newId" />
        <PaymentRegion v-if="showRegionDetailComponent === 'PaymentRegion'" :id="regionDetailId" :isSubRegion="true" />
        <ContractRegion v-if="showRegionDetailComponent === 'ContractRegion'" :id="regionDetailId"
          :isSubRegion="true" />
        <IncidentRegion v-if="showRegionDetailComponent == 'IncidentRegion'" :id="regionDetailId" :isSubRegion="true" />
        <AddCommitmentPayment v-if="showRegionDetailComponent === 'AddDepositPaymentRegion'" :id="regionDetailId"
          @change="refresh" />
        <SEPAManagementViewDocument v-if="showRegionDetailComponent === 'SEPADocumentRegion'" :document="regionDetailId"
          :isSubRegion="true" />
        <AddWalletCommitmentPayment v-if="showRegionDetailComponent === 'AddWalletDepositPaymentRegion'"
          :id="parseInt(regionDetailId)" @change="refresh" />
        <PayCommitmentInvoice v-if="showRegionDetailComponent === 'LiquidateDepositPaymentRegion'" :id="regionDetailId"
          :item="data.invoices" @change="refresh" />
        <IncidentEdit v-if="showRegionDetailComponent == 'IncidentEdit'" :commitment_id="regionDetailId"
          @change="refresh" />
        <ReturnCommimentPayment v-if="showRegionDetailComponent === 'ReturnCommitmentPaymentRegion'"
          :id="regionDetailId" @change="refresh" />
      </div>
    </div>
  </div>
</template>
