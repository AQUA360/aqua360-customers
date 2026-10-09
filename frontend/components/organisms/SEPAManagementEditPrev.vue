<script setup>
import { ref, onMounted } from 'vue';
import { add, format } from 'date-fns';

import SEPAManagementSetup from '~/components/organisms/SEPAManagementSetup.vue';
import SEPAIndividualManagementSetup from './SEPAIndividualManagementSetup.vue';
import SEPAManagementSummary from './SEPAManagementSummary.vue';
import SEPAManagementViewDocument from './SEPAManagementViewDocument.vue';
import { checkPermission } from '~/middleware/permission';
import { useToast } from 'vue-toastification';

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const toast = useToast();
const objectPermissions = ref(null);
const { $ConfiglistApiService, $PaymentApiService } = useNuxtApp();

const emit = defineEmits(['refresh']);


const steps = ref(['1', '2', '3']);
const currentStep = ref(0);
const maxStep = ref(0);

const loading = ref(true);
const loading_step = ref(false)

const showRegion = ref(false);
const toggleRegion = (force) => {
  showRegion.value = force !== undefined ? force : !showRegion.value;
}

const payment_id = ref(null);
const is_commitment = ref(false)
const is_piggy_bank = ref(false)
const selectedPayments = ref([]);
const selectedPaymentsDel = ref([]);
const loadedPayments = ref([]);

const selectedOrigins = ref([]);
const selectedBank = ref(null)
const selectedSendDate = ref(null);
const startDate = ref(null);
const endDate = ref(null);
const sendDateInvoice = ref(null);

const loadingPayments = ref(false)
const paymentsSetup = ref(false);

const document_file = ref(null);
const paymentData = ref(null);
const exploitationId = ref(null);
const billingId = ref(null);

const paymentLines = ref([]);
const anomalies = ref([]);
const doc_id = ref(null);

const is_fetching = ref(false)

const clickFinalize = async () => {
  try {
    let conf_text = t("confirmation_text_block.confirm_exit") + "\n" + t("informative_block.info_payments_mark_paid")
    if (confirm(conf_text)) {

      let saveData = {
        payments: selectedPayments.value,
        sentPayments: true,
      }
      
      let data = await $PaymentApiService.getSEPADocData(saveData)
      if (route?.query?.is_commitment) {
        router.push('/billing/commitment-deposits')
      } else {
        router.push('/billing/invoice')
      }
    }
  }
  catch (error) {
    console.error(error);
  }
}

const onSetupChanged = async (data, origins, start_date, end_date, bank, fetching = false, commitment = null, piggy_bank = null, exploitation = null, billing = null, send_date = null, send_date_invoice = null) => {
  selectedPayments.value = data;
  selectedOrigins.value = origins;
  startDate.value = start_date;
  endDate.value = end_date;
  sendDateInvoice.value = send_date_invoice;
  selectedBank.value = bank
  if (send_date) selectedSendDate.value = send_date;
  if (is_commitment) {
    is_commitment.value = commitment
  }
  is_piggy_bank.value = piggy_bank

  exploitationId.value = exploitation;
  billingId.value = billing;

  paymentData.value = {
    origins: selectedOrigins.value,
    start_date: startDate.value,
    end_date: endDate.value,
    send_date: sendDateInvoice.value
  }
  loadingPayments.value = fetching;

  is_fetching.value = fetching
  if (fetching) {
    await save();
  }
  //  paymentsSetup.value = (data && data.length > 0 || selectedPayments.value.length > 0);
}

const onCheckPayments = async (data, data_del) => {
  selectedPayments.value = data;
  selectedPaymentsDel.value = data_del;

  await save();
}


const nextStep = async () => {
  loading_step.value = true
  is_fetching.value = false

  if (currentStep.value == 0 && selectedPayments.value.length == 0) {
    confirm(t('warning_block.warning_no_payments'))
    return;
  }

  await save(currentStep.value == 1);
  if (currentStep.value < steps.value.length - 1) {
    currentStep.value++;
    if (currentStep.value > maxStep.value) {
      maxStep.value = currentStep.value;
    }
    setUrlStep();
  }
  loading_step.value = false
};

const previousStep = () => {
  save();
  if (currentStep.value > 0) {
    currentStep.value--;
  }
  setUrlStep();
};


const setUrlStep = () => {
  router.replace({
    query: {
      ...route.query, // Keep existing query parameters
      step: currentStep.value + 1,
    }
  });
}


onMounted(async () => {
  objectPermissions.value = await checkPermission($PaymentApiService);
  if (!objectPermissions.value.can_change) {
    toast.error(t('common.no_permissions'));
    return navigateTo('/');
  }
  checkRouteQuery()
  router.replace({
    query: {
      ...route.query,
      step: 1,
    }
  });
  setUrlStep();
  loading.value = false;
});

const checkRouteQuery = () => {
  if (route.query?.action == 'idvMng') {
    if (route.query.payment_id) {
      payment_id.value = parseInt(route.query.payment_id)
      if (route.query.is_commitment) {
        is_commitment.value = true
      }
    }
  }
}

const save = async (create_document = false) => {
  if (currentStep.value == 0) {
    let saveData = {
      payments: selectedPayments.value,
      data: paymentData.value,
      saveFile: false,
      doc_id: doc_id.value,
      bank_id: selectedBank.value,
      sentPayments: false,
      is_massive: is_fetching.value,
      is_commitment: is_commitment.value,
      is_piggy_bank: is_piggy_bank.value,
      exploitation_id: exploitationId.value,
      billing_id: billingId.value,
      send_date: selectedSendDate.value,
    }
    let data = await $PaymentApiService.getSEPADocData(saveData);
    anomalies.value = data.anomalies;
    paymentLines.value = data.document_data;
    doc_id.value = data.doc_id;
    selectedPayments.value = data.payment_ids;
    loadedPayments.value = data.payments;
    loadingPayments.value = false;
  }
  else if (currentStep.value == 1) {
    let saveData = {
      payments: selectedPayments.value,
      data: paymentData.value,
      saveFile: create_document,
      doc_id: doc_id.value,
      bank_id: selectedBank.value,
      payments_del: selectedPaymentsDel.value,
      sentPayments: false,
      exploitation_id: exploitationId.value,
      billing_id: billingId.value,
      send_date: selectedSendDate.value,
    }
    let data = await $PaymentApiService.getSEPADocData(saveData);
    anomalies.value = data.anomalies;
    paymentLines.value = data.document_data;
    loadedPayments.value = data.payments;
    if (data.payments_del) {
      selectedPaymentsDel.value = data.payments_del;
    }
    doc_id.value = data.doc_id;
    document_file.value = data.document_file;
  }

} 
</script>

<template>
  <div v-if="objectPermissions?.can_change" class="text-base">
    <div class="mb-2">
      <div class="flex space-x-4 justify-between">
        <div class="buttons flex gap-4 ml-4">
          <button v-for="(step, index) in steps" :disabled="index != currentStep"
            class="px-4 py-2 rounded-full focus:outline-none" :class="{
              'bg-blue-500 text-white': currentStep === index,
              'bg-gray-200 text-gray-600 cursor-not-allowed': currentStep !== index,
            }" @click="currentStep = index; setUrlStep()"> {{ t("billing_block.step") }} {{ step }}
          </button>
        </div>

      </div>
    </div>

    <!-- Contingut del Pas Actual -->
    <div v-if="loading">
      <div class="border border-gray-300 rounded-b p-4 bg-white">
        <div class="flex justify-center items-center">
          <Icon name="fa6-solid:spinner" class="animate-spin text-2xl text-slate-500" />
          <span class="ml-2">{{ $t('common.loading') }}...</span>
        </div>
      </div>
    </div>
    <div v-else class="border border-gray-300 rounded-b p-4 bg-white">
      
      <div v-if="currentStep === 0" class="tab-content mb-6">
        <!-- <MoleculesAddSEPAManagement  @change="onSetupChanged"/> -->
        <SEPAIndividualManagementSetup v-if="payment_id" @changed="onSetupChanged" />
        <SEPAManagementSetup v-else @changed="onSetupChanged" :payments="selectedPayments" :loading="loadingPayments" />
      </div>

      <div v-if="currentStep === 1" class="tab-content mb-6">
        <div id="wrapper" class="text-base">
          <SEPAManagementSummary :anomalies="anomalies" :loadedPayments="loadedPayments"
            :selectedPayments="selectedPayments" :selectedPaymentsDel="selectedPaymentsDel" 
             @changed="onCheckPayments" />
        </div>
      </div>

      <div v-if="currentStep === 2" class="tab-content mb-6">
        <div id="wrapper" class="text-base">
          <SEPAManagementViewDocument :document="document_file" />
        </div>
      </div>


      <hr />
      <!-- Botons de navegació -->
      <div class="flex justify-between mt-4">
        <button @click="previousStep" :disabled="currentStep === 0"
          class="px-4 py-2 bg-gray-500 text-white rounded hover:bg-gray-600"
          :class="{ 'opacity-0 cursor-not-allowed': currentStep === 0 }">
          &larr;&nbsp; {{ $t('common.previous') }}
        </button>
        <button v-if="currentStep !== steps.length - 1" @click="nextStep"
          :disabled="(currentStep == 0 && (selectedPayments == null || selectedPayments?.length == 0 || selectedBank == null))"
          class="px-4 py-2 bg-green-500 text-white rounded enabled:hover:bg-green-600 disabled:opacity-70">
          <Icon name="fa:spinner" class="text-white mr-2 items-center animate-spin" v-if="loading_step" />
          {{ $t('common.next') }} &nbsp;&rarr;
        </button>
        <div v-else class="flex gap-3">
          <button @click="clickFinalize"
            class="px-4 py-2 bg-green-500 text-white rounded disabled:opacity-50 enabled:hover:bg-green-600 font-bold flex items-center">
            <Icon name="fa6-solid:circle-check" />&nbsp; {{ $t('common.finish') }}
          </button>
        </div>
      </div><!-- end contingut botons -->

    </div><!--end contingut pas actual -->

    <!-- Regió Dreta per l'edició/creació de ContractRequestEdit -->
    <div role="region" id="right_page"
      class="fixed h-full border-l border-gray-100 top-0 right-0 transition-all duration-500 ease py-2 text-base bg-white w-1/2 z-20"
      :class="{ 'translate-x-0': showRegion, 'translate-x-[2000px]': !showRegion }">
      <div id="region_nav" class="mb-3 px-3">
        <button @click="toggleRegion(false)" class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300">
          <Icon name="fa6-solid:angles-right" class="text-slate-500" />
        </button>
      </div>
      <div class="px-10">

      </div>
    </div>
  </div>
</template>