<script setup>
import { ref, watch } from 'vue';
import { useRouter } from 'vue-router';
import { useI18n } from 'vue-i18n';
import { format } from 'date-fns';
import { usePermissions } from '~/middleware/permission';
import AppLoading from '~/components/atoms/AppLoading.vue';
import { useToast } from 'vue-toastification';
import H1Region from '~/components/atoms/H1Region.vue';
import PaymentDetail from '../molecules/PaymentDetail.vue';
import InvoiceRegion from './InvoiceRegion.vue';
import OptionsDropdown from '~/components/molecules/OptionsDropdown.vue';
import DropdownOption from '~/components/atoms/DropdownOption.vue';
import ChangeStatus from '../molecules/ChangeStatus.vue';
import CommitmentDepositRegion from './CommitmentDepositRegion.vue';
import SEPAManagementViewDocument from './SEPAManagementViewDocument.vue';
import ContractRegion from './ContractRegion.vue';
import PaymentMovements from '../molecules/PaymentMovements.vue';
import { openAuthenticatedFileUrl } from '~/utils/open-authenticated-file';

const { t } = useI18n();
const { permissions, loading } = usePermissions();
const toast = useToast();
const props = defineProps({
  id: Number, // ID de l'element
  isSubRegion: false,
  isSubRegionOpen: Boolean
});

const emit = defineEmits(['show-subregion', 'changed', 'close-subregion', 'close']);
const router = useRouter();
const { $PaymentApiService, $ConfigProjectApiService, $ConfiglistApiService, $CommitmentDepositApiService, $PaymentCommitmentApiService } = useNuxtApp();
const pending = ref(true);
const error = ref(null);
const data = ref(null);
const SubRegion = ref(props.isSubRegionOpen);
const objectPermissions = ref(null);
const statusPaidToken = ref(false)
const statusExpiredToken = ref(false)
const statusLostToken = ref(false)
const statusCommitmentToken = ref(false)
const statusIrrecoverableToken = ref(false)
const statusReturnedToken = ref(false)
const statusSentToken = ref(false)

const openLiquidateModal = ref(false);
const selectedPaymentDate = ref(null);
const selectedPaymentMethod = ref(null);
const selectedPaymentAmount = ref(null);
const payment_types = ref([]);

const activeTab = ref('movements');
const logNumber = ref(0)
const movementsNumber = ref(0);

const allow_payment = ref(false);

const invoiceIssueDate = ref(null);
const paymentCommitment = ref(null);
const commitmentDeposit = ref(null);

const showRegionDetailComponent = ref(null);
const regionDetailId = ref(null);

const isPiggyBankAvailable = computed(() => {
  return (data?.value?.invoice && data?.value?.invoice?.contract_piggy_bank >= data?.value?.amount) ||
    (data?.value?.commitment_deposit && data?.value?.commitment_deposit?.contract_piggy_bank >= data?.value?.amount) ||
    (data?.value?.invoice && data?.value?.invoice?.person_piggy_bank >= data?.value?.amount) ||
    (data?.value?.commitment_deposit && data?.value?.commitment_deposit?.person_piggy_bank >= data?.value?.amount);
});
const isPiggyContract = computed(() => {
  return data?.value?.invoice?.contract_piggy_bank > 0;
});
const availableBalance = computed(() => {
  return (data?.value?.invoice && data?.value?.invoice?.contract_piggy_bank) ||
    (data?.value?.commitment_deposit && data?.value?.commitment_deposit?.contract_piggy_bank) || 
    (data?.value?.invoice && data?.value?.invoice?.person_piggy_bank) ||
    (data?.value?.commitment_deposit && data?.value?.commitment_deposit?.person_piggy_bank);
});

const updateLogCount = (num) => {
  logNumber.value = num;
}

const updateMovementsCount = (num) => {
  movementsNumber.value = num;
}

const getPermissions = async () => {
  error.value = null;
  try {
    const data = await $PaymentApiService.getPermissions();
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
  pending.value = load;
  error.value = null;
  statusPaidToken.value = await $ConfigProjectApiService.get('payment_status_paid_token');
  statusCommitmentToken.value = await $ConfigProjectApiService.get('payment_status_commitment_token');
  statusExpiredToken.value = await $ConfigProjectApiService.get('payment_status_expired_token');
  statusIrrecoverableToken.value = await $ConfigProjectApiService.get('payment_status_irrecoverable_token');
  statusReturnedToken.value = await $ConfigProjectApiService.get('payment_status_returned_token');
  statusSentToken.value = await $ConfigProjectApiService.get('payment_status_sent_token');

  try {
    const result = await $PaymentApiService.getDetail(props.id);
    data.value = result;

    if (data.value.invoice && data.value.invoice.issue_date) {
      invoiceIssueDate.value = format(data.value.invoice.issue_date, 'yyyy-MM-dd');
    }
    console.log("data.value.joined_payments", data.value.joined_payments);
    console.log("data.value.joined_payments.some(joined_payment => !joined_payment.allow_change)", data.value.joined_payments.some(joined_payment => !joined_payment.allow_change));
    // if any remittance is not sent, disable the payment
    allow_payment.value = !(data.value.remittances && data.value.remittances.some(remittance => !remittance.sent_at)) && !(data.value.joined_payments && data.value.joined_payments.some(joined_payment => !joined_payment.allow_change));

    // El compromís de dipòsit del pagament: no sempre ve informat directament (FK); si el pagament ve
    // d'una factura, cal cercar-lo per la factura (relació M2M CommitmentDeposit.invoices), igual que fa
    // InvoiceRegion.vue amb getByInvoice. Es mostra sempre que es trobi (igual que InvoiceDetail.vue),
    // independentment de si es pot identificar el fraccionament concret.
    commitmentDeposit.value = data.value.commitment_deposit || null;
    if (!commitmentDeposit.value && data.value.invoice) {
      try {
        const cdResult = await $CommitmentDepositApiService.getByInvoice(data.value.invoice.id);
        commitmentDeposit.value = cdResult.results?.[0] || null;
      } catch (err) {
        console.error(err);
      }
    }

    // Identifiquem a quin fraccionament (PaymentCommitment, is_guide) del compromís de dipòsit correspon aquest
    // pagament. No hi ha FK directa Payment->PaymentCommitment: quan es genera el pagament d'un fraccionament,
    // el backend copia el seu due_date al pagament (add_wallet_payment), així que es poden fer coincidir per
    // commitment_deposit + due_date (mateix criteri ja usat pel backend a payment_commitment_view.return_payment).
    // Si el pagament no ve d'un fraccionament (p. ex. és un pagament normal d'una factura del compromís, sense
    // passar per add_wallet_payment) no hi haurà cap coincidència exacta i paymentCommitment quedarà a null;
    // igualment es mostra la relació amb el compromís de dipòsit (commitmentDeposit) més amunt.
    paymentCommitment.value = null;
    if (commitmentDeposit.value && data.value.due_date) {
      try {
        const pcResult = await $PaymentCommitmentApiService.getByDeposit(commitmentDeposit.value.id, true);
        paymentCommitment.value = (pcResult.results || []).find(pc => pc.due_date === data.value.due_date) || null;
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
const getPaymentTypes = async () => {
  try {

    const response = await $ConfiglistApiService.getAll('contract/contract-payment-type');
    console.log("response payment types", response);
    response.results.forEach(payment_type => {
      if (payment_type.token != 'DIRECT_DEBIT' && payment_type.token != 'ELECTRONIC_INVOICE') {
        payment_types.value.push({
          id: payment_type.id,
          name: payment_type.name,
          token: payment_type.token
        });
      }
    });
    if (!isPiggyBankAvailable.value) {
      payment_types.value = payment_types.value.filter(payment_type => payment_type.token != 'BALANCE');
    } else {
      selectedPaymentAmount.value = data.value.amount;
      // selectedPaymentAmount.value = data.value.invoice ? data.value.invoice.left_to_pay : data.value.amount;
    }
    console.log("selectedPaymentAmount", selectedPaymentAmount.value);
  } catch (err) {
    console.error(err);
  }
}

const manualPayment = async () => {
  if (selectedPaymentDate.value && invoiceIssueDate.value && selectedPaymentDate.value < invoiceIssueDate.value) {
    toast.error(t('warning_block.warning_payment_date_before_invoice_issue_date'));
    selectedPaymentDate.value = invoiceIssueDate.value;
    return;
  }

  if (!confirm(t("confirmation_text_block.confirm_short_pay_payment"))) return
  try {
    let save_data = {
      id: props.id,
      payment_date: selectedPaymentDate.value,
      is_piggy_contract: isPiggyContract.value,
      payment_method: selectedPaymentMethod.value,
      amount: payment_types.value.find(payment_type => payment_type.id == selectedPaymentMethod.value).token == 'BALANCE' ? selectedPaymentAmount.value : null
    }

    let response = await $PaymentApiService.manualPayment(save_data)
    if (response) {
      openLiquidateModal.value = false
      getData(false)
      emit('close', true)
    }

  } catch (err) {
    console.error(err)
  }
}

watch(() => props.id, () => {
  if (!objectPermissions.value?.can_view) {
    emit('close-subregion');
    return
  }
  getData();
  closeSubRegion();
});

watch(() => props.isSubRegionOpen, (newValue) => {
  SubRegion.value = newValue;
});


onMounted(async () => {
  await getPermissions();
  if (objectPermissions.value?.can_view) {
    await getData();
    await getPaymentTypes();
  } else {
    toast.error(t('common.no_permissions'));
    emit('close-subregion');
  }
});

const updateSubRegion = function () {
  getData();
  closeSubRegion();
  emit('changed')
}

const openLiquidateMethod = () => {
  openLiquidateModal.value = true;
  selectedPaymentDate.value = format(new Date(), 'yyyy-MM-dd');
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
  showRegionDetailComponent.value = component;
  regionDetailId.value = id;
  showSubRegion();
}

const handleStatusChanged = () => {
  closeSubRegion();
  getData();
  emit('changed');
}

const setActiveTab = (tab) => {
  activeTab.value = tab;
}

const changeStatus = async function (status) {
  try {
    let save_data = {
      id: props.id,
      status_token: status
    }
    let result = await $PaymentApiService.save(save_data)
    updateSubRegion()
  } catch (er) {
    console.error(er)
  }
}

const includePayment = async function () {
  try {
    if (confirm(t("confirmation_text_block.confirm_include_payment"))) {
      let save_data = {
        id: props.id,
        is_excluded: false
      }
      let result = await $PaymentApiService.save(save_data)
      updateSubRegion()
    }
  } catch (er) {
    console.error(er)
  }
}

const individualPayment = async function (type) {
  if (type == 'DIRECT_DEBIT') {
    return navigateTo({
      path: '/billing/wallet-managements/manage',
      query: {
        action: 'idvMng',
        payment_id: props.id,
      }
    })
  } else if (type == 'ELECTRONIC_INVOICE') {
    return navigateTo({
      path: '/billing/wallet-managements/e-manage',
      query: {
        id: props.id,
      }
    })
  }
}


const regeneratePaymentDocument = async () => {
  try {
    const file = await $PaymentApiService.regeneratePDF(props.id);

    await openAuthenticatedFileUrl(file.pdf_url);

    toast.success(t('common.correct_save'));
    // Refresquem les dades ja que el back ha actualitzat el registre
    await getData(false);
  } catch (error) {
    console.error(error);
    toast.error(t('common.error'));
  }
}

let paymentDateCheckTimeout = null
watch(selectedPaymentDate, () => {
  if (paymentDateCheckTimeout) clearTimeout(paymentDateCheckTimeout)
  paymentDateCheckTimeout = setTimeout(() => {
    console.log("selectedPaymentDate", selectedPaymentDate.value);
    if (selectedPaymentDate.value && invoiceIssueDate.value && selectedPaymentDate.value < invoiceIssueDate.value) {
      toast.warning(t('warning_block.warning_payment_date_before_invoice_issue_date'));
      selectedPaymentDate.value = invoiceIssueDate.value;
    }
    paymentDateCheckTimeout = null
  }, 1000)
})

</script>

<template>
  <div class="region__content h-full">
    <div v-if="pending || loading">
      <AppLoading :text="$t('common.loading')" />
    </div>
    <div v-else-if="error">
      <p>Error: {{ error.message }}</p>
      <p><button @click="getData" class="underline text-sky-500 hover:no-underline">{{ $t('common.load_again')
      }}</button></p>
    </div>
    <div v-else-if="objectPermissions?.can_view" class="pr-2 relative pb-24 transition-all duration-500 ease"
      :class="{ 'h-full overflow-y-auto': !isSubRegion, 'mr-[47%]': SubRegion }">
      <div v-if="openLiquidateModal" class="fixed inset-0 z-50 flex items-center justify-center overflow-y-auto"
        @click="selectedPaymentDate = null; selectedPaymentMethod = null; openLiquidateModal = false">
        <div class="bg-white rounded-lg shadow-xl p-6 max-w-lg w-full mx-4 my-auto relative" @click.stop>
          <button @click="selectedPaymentDate = null; selectedPaymentMethod = null; openLiquidateModal = false"
            class="absolute top-4 right-4 text-gray-500 hover:text-gray-700">
            <Icon name="fa6-solid:xmark" class="text-xl" />
          </button>
          <div class="">
            <label class="block font-medium text-slate-500">{{ t('billing_block.payment_date') }}</label>
            <div class="pb-4 rounded-lg text-left max-h-[60vh] overflow-y-auto">
              <AtomsInputDate v-model="selectedPaymentDate" label="" class="mb-2"
                :invalid="selectedPaymentDate == null || selectedPaymentDate == ''" />
            </div>
            <label class="block font-medium text-slate-500">{{ $t('common.select') }} {{ t('common.payment_method')
            }}</label>
            <div class="max-w-xl my-2">
              <select v-model="selectedPaymentMethod" class="w-full text-base border border-gray-300 rounded p-2"
                id="payment_method">
                <option value="" selected="selected">-- {{ $t('common.select') }} {{ t('common.payment_method') }}
                </option>
                <option v-for="paymentType in payment_types" :value="paymentType.id" :key="paymentType.id">
                  {{ paymentType.name }}
                </option>
              </select>
              <div
                v-if="selectedPaymentMethod && payment_types.find(payment_type => payment_type.id == selectedPaymentMethod).token == 'BALANCE'"
                class="flex items-center justify-between gap-2 mt-2">
                <div>
                  <label class="block font-medium text-slate-500 mb-2">{{ t('common.liquidate') }}</label>
                  <input type="number" :disabled="true" v-model="selectedPaymentAmount" class="input">
                </div>
                <div class="flex self-end">
                  <div class="flex items-center gap-2 p-2 rounded border border-slate-300 w-fit">
                    <Icon name="fa6-solid:piggy-bank" class="text-slate-400" />
                    <span class="text-slate-500">
                      {{ t('contract_block.available_balance') }}
                    </span>
                    <span class="text-green-600 font-bold">
                      {{ formatMoneyWithCurrency(availableBalance) }}
                    </span>
                  </div>
                </div>
              </div>
            </div>
          </div>
          <div class="flex justify-end">
            <button v-if="data.payment_type_token == 'DIRECT_DEBIT'" class="button-default mr-5"
              @click="individualPayment('DIRECT_DEBIT')">
              {{ $t('common.continue') }} {{ $t('common.direct_debit') }}
            </button>
            <button class="button-primary" @click="manualPayment"
              :disabled="!selectedPaymentDate || !selectedPaymentMethod || selectedPaymentMethod == ''">
              {{ $t('common.save') }}
            </button>
          </div>
        </div>
      </div>
      <div v-if="openLiquidateModal"
        class="fixed inset-0 bg-black bg-opacity-50 h-[150vh] z-20 flex items-center justify-center">
      </div>


      <div class="flex justify-between relative">
        <H1Region class="mb-3">
          {{ $t('billing_block.payment') }}
          <!-- <span v-if="data.status.token == statusExpiredToken"
            class=" mx-5 px-2 border-l-2 border-red-500 bg-red-100 text-red-500 text-sm">
            {{ t("informative_block.info_payment_expired") }}
          </span> -->
          <span v-if="data.is_excluded"
            class=" mx-5 px-2 border-l-2 border-purple-500 bg-purple-100 text-purple-500 text-sm">
            {{ t("informative_block.info_payment_excluded") }}
          </span>
        </H1Region>
        <div v-if="objectPermissions?.can_change" class="relative">
          <OptionsDropdown v-if="!((data.status.token === statusPaidToken) || 
          (data.status.token === statusLostToken ||
          (data.status.token === statusCommitmentToken)
          ))"
            id="SupplyPointRegionOptions">
            <div v-if="!allow_payment">
              <div class="max-w-xs px-2">
                <span class="text-sm text-slate-500">{{ $t('informative_block.info_block_remittance') }}</span>
              </div>
              <hr class="my-2" />
            </div>
            <DropdownOption v-if="data.is_excluded" :name="t('billing_block.include')" @click="includePayment">
            </DropdownOption>
            <DropdownOption :disabled="!allow_payment" :name="t('billing_block.single_pay')"
              @click="openLiquidateMethod"></DropdownOption>
            <DropdownOption
              v-if="data.commitment_deposit" :disabled="!allow_payment"
              :name="t('common.generate') + ' ' + t('billing_block.payment')"
              @click="regeneratePaymentDocument">
              <Icon name="fa6-solid:file-pdf" class="display-inline mr-2" /> {{ t('common.generate') }} {{ t('billing_block.payment') }}
            </DropdownOption>
            <!-- <DropdownOption :name="t('Canviar estat')" @click="changeStatusRegion()"></DropdownOption> -->
          </OptionsDropdown>
        </div>
      </div>

      <div v-if="data" id="item_data" :data-rel=id>
        <PaymentDetail @show-detail="showDetail" @change="updateSubRegion()" :id="props.id" :data="data"
          :isSubRegion="isSubRegion" :isPayment="true" :canChange="objectPermissions?.can_change"
          :paymentCommitment="paymentCommitment" :commitmentDeposit="commitmentDeposit" />
        <AtomsTabs>
          <li class="me-2">
            <a href="#tab_log" @click.prevent="setActiveTab('log')"
              :class="{ 'text-sky-600 border-sky-600': activeTab === 'log', 'hover:text-gray-600 hover:border-gray-300': activeTab !== 'log' }">
              <Icon name="fa6-solid:list" class="display-inline mr-2" />
              {{ $t('common.history') }} ({{ logNumber || 0 }})
            </a>
          </li>
          <li class="me-2">
            <a href="#tab_movements" @click.prevent="setActiveTab('movements')"
              :class="{ 'text-sky-600 border-sky-600': activeTab === 'movements', 'hover:text-gray-600 hover:border-gray-300': activeTab !== 'movements' }">
              <Icon name="fa6-solid:list" class="display-inline mr-2" />
              {{ $t('common.movements') }} ({{ movementsNumber || 0 }})
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
        </AtomsTabs>
        <section v-show="activeTab === 'log'" role="tabpanel" id="tab_log"
          class="bg-white antialiased max-h-[50vh] overflow-y-auto">
          <MoleculesLogList v-if="data" entity="payment-status" parent_entity="payment" :id="props.id"
            @update:count="updateLogCount" :service="$LoggerApiService">
          </MoleculesLogList>
        </section>
        <section v-show="activeTab === 'movements'" role="tabpanel" id="tab_movements"
          class="bg-white antialiased max-h-[50vh] overflow-y-auto">
          <PaymentMovements v-if="data" :id="props.id" @update:count="updateMovementsCount" />
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
                  <span>{{ joined_payment.total_final ? formatMoneyWithCurrency(joined_payment.total_final) : '-' }}</span>
                </td>
                <td class="px-4 py-2">
                  <span>{{ joined_payment.payment_type }}</span>
                </td>
              </tr>
            </tbody>
          </table>

        </section>
      </div><!-- end if data -->
    </div><!-- end if pending -->

    <Teleport to="body">
      <div v-if="SubRegion == true" role="region" id="subregion"
        class="h-full border-l border-gray-100 transition-all duration-500 ease text-base bg-white flex flex-col overflow-hidden fixed top-0 right-0 w-[47%] z-10"
        :class="{ 'translate-x-0': SubRegion, 'translate-x-full': !SubRegion }">
        <div id="region_nav" class="mb-3 px-3">
          <button @click="closeSubRegion()" class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300">
            <Icon name="fa6-solid:angles-right" class="text-slate-500" />
          </button>
        </div>
        <div class="pl-10 flex-1 overflow-y-auto pb-24 pr-2">
          <ContractRegion v-if="showRegionDetailComponent === 'ContractRegion'" :id="regionDetailId"
            :isSubRegion="true" />
          <InvoiceRegion v-if="showRegionDetailComponent === 'InvoiceRegion'" :id="regionDetailId" :isSubRegion="true" @update-id="(newId) => regionDetailId = newId" />
          <PaymentRegion v-if="showRegionDetailComponent === 'PaymentRegion'" :id="regionDetailId" :isSubRegion="true"
            @changed="updateSubRegion()" />
          <CommitmentDepositRegion v-if="showRegionDetailComponent === 'CommitmentDepositRegion'" :id="regionDetailId"
            :isSubRegion="true" @changed="updateSubRegion()" />
          <SEPAManagementViewDocument v-if="showRegionDetailComponent === 'SEPADocumentRegion'" :document="regionDetailId"
            :isSubRegion="true" />
          <ChangeStatus v-if="showRegionDetailComponent === 'ChangeStatus'" entity="payment" parent_entity="payment"
            :id="props.id" :status="data.status?.id" module="billing" :reasonToken="statusIrrecoverableToken"
            @changed="handleStatusChanged" />
        </div>
      </div>
    </Teleport>
  </div><!-- end region__content -->
</template>
