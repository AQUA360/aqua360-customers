<script setup>
import { ref, computed, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import { useToast } from 'vue-toastification';
import BankDetail from '../molecules/BankDetail.vue';
import ButtonSeleccio from '../atoms/ButtonSeleccio.vue';
import SelectPaymentType from '~/components/molecules/SelectPaymentType.vue';
import { openAuthenticatedFileUrl } from '~/utils/open-authenticated-file';
const { t } = useI18n();
const toast = useToast();

const props = defineProps({
  invoiceId: Number,
  data: Object,
  localPersons: Array,
  is_paid: Boolean
});

const emit = defineEmits(['refresh-data', 'open-person-bank-select', 'close-person-bank-select']);

const { $InvoiceApiService, $ConfiglistApiService, $PaymentApiService, $DocumentManagerApiService } = useNuxtApp();

const paymentTypeExcludeTokens = computed(() => [
  'BALANCE',
  'DIRECT_DEBIT',
  'ELECTRONIC_INVOICE',
  'CONFIRMING60',
  'CONFIRMING180',
  'TPV_ONLINE',
]);

const openLiquidateModal = ref(false);
const openDateModal = ref(false);
const openPaymentProofModal = ref(false);
const openChangePaymentMethodModal = ref(false);
const openReturnReasonModal = ref(false);
const openChangeAddressModal = ref(false);
const openChangeDatesModal = ref(false);

const returningInvoice = ref(false);

const liquidation_reasons = ref([]);
const return_reasons = ref([]);
const selected_liquidation_reason = ref(null);
const paymentTypeOptionsById = ref({});
const selected_payment_type = ref(null);

const onPaymentTypesLoaded = ({ byId }) => {
  paymentTypeOptionsById.value = byId;
  if (openChangePaymentMethodModal.value && !selected_payment_type.value && props.data.payment_type_token_final) {
    selected_payment_type.value = Object.values(byId)
      .find((payment_type) => payment_type.token == props.data.payment_type_token_final)?.id ?? null;
  }
};
const selected_payment_bank = ref(null);
const previous_payment_bank = ref(null);
const selected_return_reason = ref(null);
const add_invoice = ref(false);
// Paid total of a credit note: keep it as balance or return it (mutually exclusive, or none of them).
// Returning goes through the balance in the backend, so it also sends `return_paid_total`.
const return_paid_total = ref(true)
const return_paid_total_balance = ref(false)
watch(return_paid_total, (value) => {
  if (value) return_paid_total_balance.value = false
})
watch(return_paid_total_balance, (value) => {
  if (value) return_paid_total.value = false
})
const return_paid_total_balance_type = ref(null)
// Indica si, además de SEPA, también se devuelve el importe cobrado con saldo (BALANCE) a la hucha
const return_all = ref(false)
const return_date = ref(new Date().toISOString().split('T')[0])
const addressOptions = ref({});
const addressOptionsById = ref([]);
const selected_address = ref(null);
const accounting_office = ref(null);
const managing_body = ref(null);
const processing_unit = ref(null);
const selected_doc_payment_date = ref(null);
const selected_payment_proof_id = ref(null);
const selected_payment_proof_date = ref(null);
const selected_invoice_due_date = ref(null);
const selected_invoice_send_date = ref(null);
const payment_proof_observation = ref('');

const isAnyModalOpen = computed(() => {
  return openLiquidateModal.value || openDateModal.value || openPaymentProofModal.value ||
    openChangePaymentMethodModal.value || openReturnReasonModal.value || openChangeAddressModal.value || openChangeDatesModal.value;
});


const getLiquidationReasons = async () => {
  try {
    const data = await $ConfiglistApiService.getAll('billing/invoice-suppression-reason');
    liquidation_reasons.value = data.results;
  } catch (err) {
    console.error(err);
  }
};

const selectLiquidationReason = (reason) => {
  if (selected_liquidation_reason.value === reason) {
    selected_liquidation_reason.value = null;
    return;
  }
  selected_liquidation_reason.value = reason;
};

const openLiquidate = async () => {
  await getLiquidationReasons();
  openLiquidateModal.value = true;
};

const returnInvoice = async () => {
  if (!confirm(t("confirmation_text_block.confirm_return_invoice"))) return;
  returningInvoice.value = true;
  try {
    let save_data = {
      id: props.invoiceId,
      reason_id: selected_liquidation_reason.value,
      return_paid_total: return_paid_total.value || return_paid_total_balance.value,
      return_paid_total_balance: return_paid_total_balance.value,
      return_paid_total_balance_type: return_paid_total_balance.value ? return_paid_total_balance_type.value : null,
      return_paid_total_balance_type_iban: return_paid_total_balance.value ? selected_payment_bank.value : null
    };
    
    const response = await $InvoiceApiService.returnInvoice(save_data);
    if (response) {
      toast.success(t("billing_block.returned_invoice_long"));
      emit('refresh-data');
    }
    openLiquidateModal.value = false;
    selected_liquidation_reason.value = null;
  } catch (error) {
    console.error(error);
  } finally {
    returningInvoice.value = false;
  }
};

const getReturnReasons = async () => {
  try {
    const data = await $ConfiglistApiService.getAll('billing/reject-motive');
    return_reasons.value = [];
    data.results.forEach(reason => {
      return_reasons.value.push({
        value: reason.id,
        label: reason.name
      });
    });
  } catch (err) {
    console.error(err);
  }
};

const openReturnReason = async () => {
  return_date.value = new Date().toISOString().split('T')[0];
  return_all.value = !!props.data?.has_payments_piggy_bank;
  await getReturnReasons();
  openReturnReasonModal.value = true;
};

const generateReturnInvoice = async () => {
  if (!confirm(t("confirmation_text_block.confirm_apply"))) return;
  try {
    if (add_invoice.value) {
      let data = {
        invoice_return_id: props.invoiceId,
        main_return_reason: selected_return_reason?.value?.value
      };
      await $PaymentApiService.manageRejectionPayments(data);
    } else {
      let save_data = {
        id: props.invoiceId,
        return_all: return_all.value,
        return_reason: selected_return_reason?.value?.value,
        return_date: return_date.value,
      };
      await $InvoiceApiService.passToPending(save_data);
    }
  } catch (err) {
    console.error(err);
  } finally {
    openReturnReasonModal.value = false;
    selected_return_reason.value = null;
    return_date.value = new Date().toISOString().split('T')[0];
    add_invoice.value = false;
    return_all.value = false;
    emit('refresh-data');
  }
};

const openChangePaymentMethod = async () => {
  openChangePaymentMethodModal.value = true;
  if (props.data.payment_type) {
    selected_payment_type.value = props.data.payment_type;
  } else {
    selected_payment_type.value = null;
  }
  if (props.data.payment_bank_final) {
    previous_payment_bank.value = props.data.payment_bank_final;
  }
};

const openChangeDates = async () => {
  openChangeDatesModal.value = true;
  selected_invoice_due_date.value = props.data.due_date;
  selected_invoice_send_date.value = props.data.send_at.split('T')[0];
};

const openPersonBankSelect = () => {
  emit('open-person-bank-select');
};

const onPersonBankSelected = (bank) => {
  selected_payment_bank.value = bank;
  emit('close-person-bank-select');
};

const savePaymentMethod = async (refresh = true) => {
  if (!confirm(t("confirmation_text_block.confirm_modify"))) return false;
  try {
    let save_data = {
      id: props.invoiceId,
      payment_type_final: selected_payment_type.value,
      payment_bank_final: selected_payment_bank.value ? selected_payment_bank.value.iban : null
    };
    let response = await $InvoiceApiService.changePaymentMethod(save_data);
    if (response) {
      toast.success(t("common.correct_save"));
    }
    if (refresh) emit('refresh-data', false);
    return true;
  } catch (error) {
    console.error(error);
    return false;
  } finally {
    closeChangePaymentMethodModal();
  }
};

const closeChangePaymentMethodModal = () => {
  openChangePaymentMethodModal.value = false;
  selected_payment_type.value = null;
  selected_payment_bank.value = null;
  previous_payment_bank.value = null;
};

const openDateModalForPayment = async (dueDate) => {
  selected_doc_payment_date.value = dueDate;
  openDateModal.value = true;
};

const generatePaymentDoc = async () => {
  if (props.data.payment_type_token_final == 'DIRECT_DEBIT') {
    if (!selected_payment_type.value) {
      toast.warning(t("warning_block.warning_select_payment_method"));
      return;
    } else {
      const response = await savePaymentMethod(false);
      if (!response) return;
    }
  }
  try {
    const file = await $InvoiceApiService.downloadPaymentDoc(props.invoiceId, selected_doc_payment_date.value);
    await openAuthenticatedFileUrl(file.pdf_url);

    emit('refresh-data', false);
  } catch (error) {
    console.error(error);
  }
};

const openPaymentProof = (id, payment_date) => {
  selected_payment_proof_id.value = id;
  selected_payment_proof_date.value = payment_date;
  openPaymentProofModal.value = true;
};

const generatePaymentProofDoc = async () => {
  try {
    let save_data = {
      id: selected_payment_proof_id.value,
      date: selected_payment_proof_date.value,
      observation: payment_proof_observation.value
    };
    const file = await $PaymentApiService.generatePaymentProofDoc(save_data);
    await openAuthenticatedFileUrl(file.pdf_url);

    openPaymentProofModal.value = false;
    selected_payment_proof_id.value = null;
    selected_payment_proof_date.value = null;
    payment_proof_observation.value = '';
  } catch (error) {
    console.error(error);
  }
};

const saveChangeDates = async () => {
  try {
    let save_data = {
      id: props.invoiceId,
      due_date: selected_invoice_due_date.value,
      send_date: selected_invoice_send_date.value
    };
    const response = await $InvoiceApiService.changeDates(save_data);
    if (response) {
      toast.success(t("common.correct_save"));
    }
    emit('refresh-data', false);
  } catch (error) {
    console.error(error);
  } finally {
    closeChangeDatesModal();
  }
};

const openChangeAddress = async () => {
  openChangeAddressModal.value = true;
  addressOptions.value = {};
  for (const person of props.localPersons) {
    addressOptions.value[person.full_name] = [];
    person.addresses.forEach((person_address) => {
      addressOptions.value[person.full_name].push({
        value: person_address.id,
        label: person_address.address_complete
      });
    });

    if (person.addresses.length == 0) {
      addressOptions.value[person.full_name].push({
        value: "",
        label: `(${t("address_block.no_address")})`
      });
    }
  }

  Object.values(addressOptions.value).forEach(addressList => {
    addressList.forEach(address => {
      addressOptionsById.value[address.value] = address.label;
    });
  });
};

const saveAddress = async () => {
  try {
    let save_data = {
      id: props.invoiceId,
      address_final: selected_address.value ? selected_address.value : props.data.address_final,
      accounting_office_final: accounting_office.value ? accounting_office.value : props.data.accounting_office_final,
      managing_body_final: managing_body.value ? managing_body.value : props.data.managing_body_final,
      processing_unit_final: processing_unit.value ? processing_unit.value : props.data.processing_unit_final
    };
    const response = await $InvoiceApiService.changeAddress(save_data);
    if (response) {
      toast.success(t("common.correct_save"));
    }
    emit('refresh-data', false);
  } catch (error) {
    console.error(error);
  } finally {
    closeAddressModel();
  }
};

const closeAddressModel = () => {
  openChangeAddressModal.value = false;
  accounting_office.value = null;
  managing_body.value = null;
  processing_unit.value = null;
  selected_address.value = null;
  addressOptions.value = {};
};

const closeChangeDatesModal = () => {
  openChangeDatesModal.value = false;
  selected_invoice_due_date.value = null;
  selected_invoice_send_date.value = null;
};

defineExpose({
  openLiquidate,
  openReturnReason,
  openChangePaymentMethod,
  openDateModalForPayment,
  openPaymentProof,
  openChangeAddress,
  onPersonBankSelected,
  openChangeDates
});
</script>

<template>
  <div>
    <!-- Liquidate Modal -->
    <div v-if="openLiquidateModal" class="fixed inset-0 z-40 flex items-center justify-center overflow-y-auto">
      <div class="bg-white rounded-lg shadow-xl p-6 max-w-lg w-full mx-4 my-auto relative">
        <button @click="selected_liquidation_reason = null; openLiquidateModal = false"
          class="absolute top-4 right-4 text-gray-500 hover:text-gray-700">
          <Icon name="fa6-solid:xmark" class="text-xl" />
        </button>
        <div class="">
          <label class="block font-medium text-slate-500">{{ $t('common.select') }} {{ t('common.return_reason')
            }}</label>
          <div class="py-4 px-1 rounded-lg text-left max-h-[60vh] overflow-y-auto">
            <ul class="space-y-2">
              <li v-for="reason in liquidation_reasons" :key="reason.id" @click="selectLiquidationReason(reason.id)"
                class="text-slate-700 flex items-center gap-3 cursor-pointer border-b border-slate-200 py-1 rounded"
                :class="{ 'text-slate-800 italic bg-slate-100 ml-3': selected_liquidation_reason === reason.id }">
                <Icon name="fa6-solid:angles-right"
                  :class="selected_liquidation_reason === reason.id ? 'text-slate-600' : 'text-slate-400'" />
                {{ reason.name }}
              </li>
            </ul>
          </div>
          <!-- <label class="block font-medium text-slate-500">{{ $t('common.select') }} {{ t('common.payment_method')
          }}</label>
          <div class="max-w-xl my-2">
            <select v-model="selected_payment_type" class="w-full text-base border border-gray-300 rounded p-2"
              id="payment_method">
              <option value="" selected="selected">-- {{ $t('common.select') }} {{ t('common.payment_method') }}
              </option>
              <option v-for="paymentType in payment_types" :value="paymentType.id" :key="paymentType.id">
                {{ paymentType.name }}
              </option>
            </select>
          </div> -->
          <div v-if="props.is_paid" class="flex items-center gap-2">
            <label class="block font-medium text-slate-500" for="return_paid_total">{{ $t('common.return_paid_total')
              }}</label>
            <input type="checkbox" v-model="return_paid_total" id="return_paid_total" />
            <div class="flex items-center gap-2">
              <label class="block font-medium text-slate-500" for="return_paid_total_balance">{{
                $t('common.return_paid_total_balance')
              }}</label>
              <input type="checkbox" v-model="return_paid_total_balance" id="return_paid_total_balance" />
            </div>
          </div>
          <div v-if="props.is_paid && return_paid_total_balance" class="my-2">
            <!-- <label class="block font-medium text-slate-500" for="return_paid_total_balance">{{
              $t('common.return_paid_total_balance')
              }}</label>
            <input type="checkbox" v-model="return_paid_total_balance" id="return_paid_total_balance" /> -->
            <SelectPaymentType :disabled="!return_paid_total_balance" v-model="return_paid_total_balance_type"
              :exclude-tokens="paymentTypeExcludeTokens" select-wrapper-class="max-w-2xl" :model-as-number="true"
              @loaded="onPaymentTypesLoaded">
              <template #label>
                <span class="block text-sm font-medium text-slate-500 mb-2">{{
                  $t('billing_block.payment_method_return_balance') }}</span>
              </template>
            </SelectPaymentType>

            <div class="select_bank my-3 max-w-xl"
              v-if="paymentTypeOptionsById[return_paid_total_balance_type]?.token == 'BANK_TRANSFER'">
              <div v-if="selected_payment_bank" class="bg-green-100 p-4 rounded relative group">
                <div>
                  <BankDetail :item="selected_payment_bank" />
                </div>
                <button @click="openPersonBankSelect"
                  class="absolute cursor-pointer shadow-md border text-sm w-8 h-8 bg-white right-3 top-3 rounded-md text-slate-600 opacity-0 transition-all duration-300 group-hover:opacity-100">
                  <Icon name="fa6-solid:pencil" />
                </button>
              </div>

              <div v-else>
                <ButtonSeleccio @click="openPersonBankSelect" class="py-3">
                  <Icon name="fa6-regular:hand-pointer" class="text-slate-500" />
                  {{ $t('common.select') }} {{ $t('common.iban') }}
                </ButtonSeleccio>
                <div class="flex items-center gap-2 rounded bg-orange-50 border border-orange-200 p-2 mt-2">
                  <span class="text-sm text-orange-500 font-bold">
                    {{ $t('billing_block.select_bank_data') }}
                  </span>
                </div>
              </div>
            </div>
          </div>
          <div v-if="props.is_paid && return_paid_total" class="flex items-center gap-2">
          </div>
        </div>
        <div class="flex justify-end">
          <button class="button-primary flex items-center justify-center gap-2" @click="returnInvoice"
            :disabled="!selected_liquidation_reason || returningInvoice || (return_paid_total_balance && (!return_paid_total_balance_type || (!selected_payment_bank && paymentTypeOptionsById[return_paid_total_balance_type]?.token == 'BANK_TRANSFER')))">
            <Icon v-if="returningInvoice" name="fa6-solid:spinner" class="animate-spin" />
            <span v-if="!returningInvoice">{{ $t('billing_block.return') }}</span>
            <span v-else>{{ $t('common.processing') }}</span>
          </button>
        </div>
      </div>
    </div>

    <!-- Change Payment Method Modal -->
    <div v-if="openChangePaymentMethodModal"
      class="fixed inset-0 z-50 flex items-center justify-center overflow-y-auto">
      <div class="bg-white rounded-lg shadow-xl p-6 max-w-lg w-full mx-4 my-auto relative">
        <button @click="closeChangePaymentMethodModal" class="absolute top-4 right-4 text-gray-500 hover:text-gray-700">
          <Icon name="fa6-solid:xmark" class="text-xl" />
        </button>
        <div class="mb-5 mt-2 text-sm text-slate-500 bg-slate-50 rounded-md border border-slate-200 p-2">
          {{ $t('common.previous') }} {{ $t('common.payment_method') }}: {{ data.payment_type_final }}
          <p v-if="previous_payment_bank">
            &rarr; &nbsp;
            <AtomsIBAN :value="previous_payment_bank" />
          </p>
        </div>
        <div class="">
          <SelectPaymentType v-model="selected_payment_type" :exclude-tokens="[]" :model-as-number="true"
            select-class="w-full text-base border border-gray-300 rounded p-2" select-wrapper-class="max-w-xl my-2"
            @loaded="onPaymentTypesLoaded">
            <template #label>
              <label class="block font-medium text-slate-500">{{ $t('common.select') }} {{ t('common.payment_method')
                }}</label>
            </template>
          </SelectPaymentType>

          <div class="select_bank my-3 max-w-xl"
            v-if="paymentTypeOptionsById[selected_payment_type]?.token == 'DIRECT_DEBIT'">
            <div v-if="selected_payment_bank" class="bg-green-100 p-4 rounded relative group">
              <div>
                <BankDetail :item="selected_payment_bank" />
              </div>
              <button @click="openPersonBankSelect"
                class="absolute cursor-pointer shadow-md border text-sm w-8 h-8 bg-white right-3 top-3 rounded-md text-slate-600 opacity-0 transition-all duration-300 group-hover:opacity-100">
                <Icon name="fa6-solid:pencil" />
              </button>
            </div>

            <div v-else>
              <ButtonSeleccio @click="openPersonBankSelect" class="py-3">
                <Icon name="fa6-regular:hand-pointer" class="text-slate-500" />
                {{ $t('common.select') }} {{ $t('common.iban') }}
              </ButtonSeleccio>
              <div class="flex items-center gap-2 rounded bg-orange-50 border border-orange-200 p-2 mt-2">
                <span class="text-sm text-orange-500 font-bold">
                  {{ $t('billing_block.select_bank_data') }}
                </span>
              </div>
            </div>
          </div>
        </div>
        <div class="flex justify-end">
          <button class="button-primary" @click="savePaymentMethod" :disabled="!selected_payment_type ||
            (paymentTypeOptionsById[selected_payment_type]?.token == 'DIRECT_DEBIT' && !selected_payment_bank)">
            {{ $t('common.change') }}
          </button>
        </div>
      </div>
    </div>

    <!-- Date Modal -->
    <div v-if="openDateModal" class="fixed inset-0 z-50 flex items-center justify-center overflow-y-auto">
      <div class="bg-white rounded-lg shadow-xl p-6 max-w-lg w-full mx-4 my-auto relative">
        <button @click="selected_doc_payment_date = null; openDateModal = false"
          class="absolute top-4 right-4 text-gray-500 hover:text-gray-700">
          <Icon name="fa6-solid:xmark" class="text-xl" />
        </button>
        <div class="">
          <label class="block font-medium text-slate-500">{{ $t('common.select') }} {{ t('billing_block.payment_date')
            }}</label>
          <div class="py-4 pt-1 px-1 rounded-lg text-left max-h-[60vh] overflow-y-auto">
            <AtomsInputDate v-model="selected_doc_payment_date" :label="''" class="" />
          </div>
        </div>
        <div v-if="data.payment_type_token_final == 'DIRECT_DEBIT'">
          <SelectPaymentType v-model="selected_payment_type" :exclude-tokens="['DIRECT_DEBIT']" :model-as-number="true"
            select-class="w-full text-base border border-gray-300 rounded p-2" select-wrapper-class="max-w-xl my-2" />
          <p class="block font-medium text-slate-500 text-xs italic">
            {{ $t('informative_block.info_direct_debit_payment_method') }}
          </p>
        </div>
        <div class="flex justify-end">
          <button class="button-primary" @click="generatePaymentDoc"
            :disabled="!selected_doc_payment_date || selected_doc_payment_date == ''">
            {{ $t('common.generate') }}
          </button>
        </div>
      </div>
    </div>

    <!-- Return Reason Modal -->
    <div v-if="openReturnReasonModal" class="fixed inset-0 z-50 flex items-center justify-center overflow-y-auto">
      <div class="bg-white rounded-lg shadow-xl p-6 max-w-lg w-full mx-4 my-auto relative">
        <button
          @click="selected_return_reason = null; return_date = new Date().toISOString().split('T')[0]; openReturnReasonModal = false; add_invoice = false"
          class="absolute top-4 right-4 text-gray-500 hover:text-gray-700">
          <Icon name="fa6-solid:xmark" class="text-xl" />
        </button>
        <div class="">
          <label class="block font-medium text-slate-500">
            {{ $t('common.select') }} {{ t('common.devolution_type').toLowerCase() }}</label>
          <div class="py-4 px-1 rounded-lg text-left">
            <v-select id="return_reason" v-model="selected_return_reason" :options="return_reasons" class=""
              :placeholder="`${$t('common.select')} ${t('common.devolution_type').toLowerCase()}`" />
          </div>
          <div class="mt-3">
            <AtomsInputDate v-model="return_date" :label="$t('common.return_date')" class="mb-0" />
          </div>
          <div v-if="props.data?.has_payments_piggy_bank" class="flex items-center gap-2 mt-3">
            <input type="checkbox" v-model="return_all" id="return_all" />
            <label class="block font-medium text-slate-500" for="return_all">
              {{ $t('common.return_all_piggy_bank') }}
            </label>
          </div>
        </div>
        <div class="flex justify-end">
          <button class="button-primary" @click="generateReturnInvoice"
            :disabled="!selected_return_reason || selected_return_reason == '' || !return_date">
            {{ $t('common.confirm') }}
          </button>
        </div>
      </div>
    </div>

    <!-- Payment Proof Modal -->
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

    <!-- Invoice Dates Modal -->
    <div v-if="openChangeDatesModal" class="fixed inset-0 z-50 flex items-center justify-center overflow-y-auto">
      <div class="bg-white rounded-lg shadow-xl p-6 max-w-lg w-full mx-4 my-auto relative">
        <button @click="closeChangeDatesModal" class="absolute top-4 right-4 text-gray-500 hover:text-gray-700">
          <Icon name="fa6-solid:xmark" class="text-xl" />
        </button>
        <div>
          <label class="block font-medium text-slate-500">
            {{ $t('billing_block.invoice_dates') }}
          </label>
          <div class="gap-2">
            <div class="flex grid grid-cols-[1fr,2fr] items-center gap-2">
              <label class="text-xs text-slate-500 whitespace-nowrap">{{ $t('common.due_date') }}</label>
              <AtomsInputDate v-model="selected_invoice_due_date" class="w-full" />
            </div>
            <div class="flex grid grid-cols-[1fr,2fr] items-center gap-2">
              <label class="text-xs text-slate-500 whitespace-nowrap">{{ $t('common.send_date') }}</label>
              <AtomsInputDate v-model="selected_invoice_send_date" class="w-full" />
            </div>
          </div>
        </div>
        <div class="flex justify-end">
          <button class="button-primary" @click="saveChangeDates" :disabled="!selected_invoice_due_date">
            {{ $t('common.save') }}
          </button>
        </div>
      </div>
    </div>

    <!-- Change Address Modal -->
    <div v-if="openChangeAddressModal" class="fixed inset-0 z-50 flex items-center justify-center overflow-y-auto">
      <div class="bg-white rounded-lg shadow-xl p-6 max-w-lg w-full mx-4 my-auto relative">
        <button @click="closeAddressModel" class="absolute top-4 right-4 text-gray-500 hover:text-gray-700">
          <Icon name="fa6-solid:xmark" class="text-xl" />
        </button>
        <div class="my-2">
          <label class="block font-medium text-slate-500">
            {{ $t('address_block.select_address') }}
          </label>
          <select v-model="selected_address" class="w-full text-base border border-gray-300 rounded p-2" id="address">
            <option value="" selected="selected">--{{ $t('address_block.select_address') }}</option>
            <template v-for="(addresses, person) in addressOptions" :key="person">
              <optgroup :label="person">
                <option v-for="address in addresses" :value="address.value" :key="address.value">
                  {{ address.label }}
                </option>
              </optgroup>
            </template>
          </select>
          <hr class="my-2" />
          <details class="border border-slate-200 rounded-lg p-4 relative group mb-2">
            <summary class="text-slate-500">
              {{ $t('common.electronic_invoice_data') }}
            </summary>
            <div class="bg-slate-50 rounded-lg p-4">
              <div class="flex items-center gap-2 grid grid-cols-[1fr,1fr,10px,1fr] mb-2">
                <span>
                  {{ $t('billing_block.accounting_office') }}
                </span>
                <input type="text" v-if="props.data.accounting_office_final" :disabled="true"
                  v-model="props.data.accounting_office_final"
                  class="w-full text-base border border-gray-300 rounded p-2" />
                <span v-else class="text-slate-500 italic">
                  {{ $t('None') }}
                </span>
                &rarr;
                <input type="text" v-model="accounting_office"
                  class="w-full text-base border border-gray-300 rounded p-2" />
              </div>
              <div class="flex items-center gap-2 grid grid-cols-[1fr,1fr,10px,1fr] mb-2">
                <span>
                  {{ $t('billing_block.managing_body') }}
                </span>
                <input type="text" v-if="props.data.managing_body_final" :disabled="true"
                  v-model="props.data.managing_body_final"
                  class="w-full text-base border border-gray-300 rounded p-2" />
                <span v-else class="text-slate-500 italic">
                  {{ $t('None') }}
                </span>
                &rarr;
                <input type="text" v-model="managing_body"
                  class="w-full text-base border border-gray-300 rounded p-2" />
              </div>
              <div class="flex items-center gap-2 grid grid-cols-[1fr,1fr,10px,1fr]">
                <span>
                  {{ $t('billing_block.processing_unit') }}
                </span>
                <input type="text" v-if="props.data.processing_unit_final" :disabled="true"
                  v-model="props.data.processing_unit_final"
                  class="w-full text-base border border-gray-300 rounded p-2" />
                <span v-else class="text-slate-500 italic">
                  {{ $t('None') }}
                </span>
                &rarr;
                <input type="text" v-model="processing_unit"
                  class="w-full text-base border border-gray-300 rounded p-2" />
              </div>
            </div>
          </details>
        </div>
        <div class="flex justify-end">
          <button class="button-primary" @click="saveAddress"
            :disabled="(selected_address == null || selected_address == '') && (accounting_office == null || accounting_office == '') && (managing_body == null || managing_body == '') && (processing_unit == null || processing_unit == '')">
            {{ $t('common.save') }}
          </button>
        </div>
      </div>
    </div>

    <!-- Modal Backdrop -->
    <div v-if="isAnyModalOpen"
      class="fixed inset-0 bg-black bg-opacity-50 h-[150vh] z-20 flex items-center justify-center">
    </div>
  </div>
</template>
