<script setup>
import { add, format } from 'date-fns';
import StatusesNav from '~/components/atoms/StatusesNav.vue';
import CommitmentDepositSetup from '../molecules/CommitmentDepositSetup.vue';
import CommitmentDepositInvoiceSummary from '../molecules/CommitmentDepositInvoiceSummary.vue';
import CommitmentDepositPayments from '../molecules/CommitmentDepositPayments.vue';
import CommitmentDepositFinalSummary from '../molecules/CommitmentDepositFinalSummary.vue';
import CommitmentDepositManage from '../molecules/CommitmentDepositManage.vue';
import SelectExistingCommitmentRequest from '../molecules/SelectExistingCommitmentRequest.vue';
import { checkPermission } from '~/middleware/permission';
import { useToast } from 'vue-toastification';
import AppLoading from '~/components/atoms/AppLoading.vue';

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const toast = useToast();
const { $ConfiglistApiService, $CommitmentDepositApiService, $ConfigProjectApiService, $PaymentCommitmentApiService, $PersonApiService, $InvoiceApiService, $ContractApiService } = useNuxtApp();

const objectPermissions = ref(null);

const props = defineProps({
  request: Object,
});

const emit = defineEmits(['refresh']);


const request = ref({});
const foundRequest = ref(false);

const steps = ref(['1', '2', '3', '4']);
const currentStep = ref(0);
const maxStep = ref(0);

const loading = ref(true);
const loadingSetupData = ref(false);

const editingChangeStatus = ref(false);
const showRegion = ref(false);
const toggleRegion = (force) => {
  showRegion.value = force !== undefined ? force : !showRegion.value;
}

const requestsFound = ref(null)

const setupData = ref(null);
const summaryData = ref(null);
const invoicesData = ref(null);
const paymentsData = ref(null);

const selectedInvoices = ref([])
const payments = ref([])
const holder = ref(null)
const contract = ref(null)

const selectedPayer = ref(null);
const payerOptions = ref([]);

const commitmentDepositStatuses = ref([]);
const commitmentDepositStatus = ref(null);

const splitPayments = ref(true)

const getSetupData = async (data) => {
  setupData.value = data;
  await save();
}

const getInvoicesData = async (data) => {
  invoicesData.value = data;
  selectedInvoices.value = invoicesData.value.invoices;
}

const getPaymentsData = async (data) => {
  paymentsData.value = data;
}

const clickFinalize = async () => {
  try {

    if (!confirm(t("confirmation_text_block.confirm_create"))) return
    let save_data = {
      step: '4',
      payments: paymentsData.value.payments,
      holder: payerOptions.value.find(payer => payer.id == selectedPayer.value),
      contract: contract.value,
      invoices: paymentsData.value.invoices,
      days_next_payment: paymentsData.value.days_next_payment,
      due_date_commitment: paymentsData.value.due_date_commitment,
      start_date_commitment: paymentsData.value.start_date_commitment,
      request: request.value || null,
    }

    let response = await $CommitmentDepositApiService.getData(save_data);
    return navigateTo('/billing/commitment-deposits/')
  }
  catch (error) {
    console.error(error);
  }
}


const nextStep = async () => {
  if (currentStep.value == 0 && selectedInvoices.value.length > 0) {
    if (invoicesData?.value?.ignored_invoices.length > 0) {
      //if invoicesData has ignored invoices, even if len 0 (meaning that invoicesData has already been used), do not set the next values
    } else {
      invoicesData.value = {
        invoices: selectedInvoices.value,
        ignored_invoices: [],
      }
    }
  }

  if (currentStep.value != 0 || (currentStep.value == 0 && foundRequest.value)) await save();
  if (currentStep.value < steps.value.length - 1) {
    currentStep.value++;
    if (currentStep.value > maxStep.value) {
      maxStep.value = currentStep.value;
    }
    setUrlStep();
  }
};

const previousStep = () => {
  save();
  if (currentStep.value > 0) {
    currentStep.value--;
  }
  setUrlStep();
};

const fetchConfigData = async (entity, targetArray) => {
  try {
    const data = await $ConfiglistApiService.getAll(entity);
    targetArray.value = data.results;
  } catch (error) {
    console.error(`Error fetching ${entity}:`, error);
  }
}

const getData = async () => {
  loading.value = true;
  try {
    await fetchConfigData('billing/commitment-deposit-status', commitmentDepositStatuses);
    await loadData()

  } catch (error) {
    console.error('Error loading draft:', error);
  }
  loading.value = false;
};

const loadData = async () => {
  if (props.request) {
    try {
      let holder_instance = await $PersonApiService.getDetail(request.value.holder)
      let deposit_payments = await $PaymentCommitmentApiService.getByDeposit(request.value.id, true)

      contract.value = request.value.contract
      commitmentDepositStatus.value = request.value.status
      request.value = props.request;
      setupData.value = {
        loading_invoices: false,
        total_invoices: request.value.invoices.length,
        selected_person: holder_instance,
        selected_invoice: null,
        selected_contract: null,
      }
      invoicesData.value = {
        invoices: request.value.invoices,
        ignored_invoices: [],
      }
      paymentsData.value = {
        payments: [],
        remaining: 0,
        days_next_payment: request.value.days_next_payment,
        due_date_commitment: request.value.due_date,
      }
      payments.value = paymentsData.value.payments
      holder.value = holder_instance
      //selectedInvoices.value = request.value.invoices
      foundRequest.value = true;

    } catch (error) {
      console.error('Error loading draft:', error);
    }
  }
}

const setUrlStep = () => {
  router.replace({
    query: {
      ...route.query, // Keep existing query parameters
      step: currentStep.value + 1
    }
  });
}

onMounted(async () => {
  objectPermissions.value = await checkPermission($CommitmentDepositApiService);
  if (!objectPermissions.value.can_change) {
    toast.error(t('common.no_permissions'));
    return navigateTo('/');
  }

  await checkIfSplitPayments()

  if (route.query.step) {
    currentStep.value = parseInt(route.query.step) - 1;
    maxStep.value = currentStep.value;
  }
  if (selectedInvoices.value.length == 0) {
    currentStep.value = 0;
    maxStep.value = currentStep.value;
  }
  setUrlStep();
  getData();
  if (props.request) {
    request.value = props.request;
  }
  if (route.query.invoice_id) {
    let response = await $InvoiceApiService.getDetail(route.query.invoice_id)
    selectedInvoices.value = {
      'id': response.id,
      'token': response.token,
      'contract': response.contract.id,
    }
    setupData.value = {
      loading_invoices: false,
      total_invoices: 1,
      selected_invoice: selectedInvoices.value,
      selected_contract: null,
      selected_person: null
    }
    await save()
  }
  if (route.query.contract_id) {
    let response = await $ContractApiService.getDetail(route.query.contract_id)
    let contract_data = {
      id: response.id,
      token: response.token,
      holder_token: response.holder.token,
      holder_name: response.holder.name,
    }
    setupData.value = {
      loading_invoices: false,
      total_invoices: 0,
      selected_invoice: null,
      selected_contract: contract_data,
      selected_person: null
    }
    await save()
  }
});

const checkIfSplitPayments = async () => {
  splitPayments.value = await $ConfigProjectApiService.get('commitment_deposit_split');
  splitPayments.value = splitPayments.value.toLowerCase() == 'true' || splitPayments.value == true;

  if (!splitPayments.value) {
    steps.value = [1, 2, 3];
  }
}

const save = async () => {
  if (currentStep.value == 0) {
    setupData.value.loading_invoices = true;
    if (!foundRequest.value) {
      payerOptions.value = [];
      selectedPayer.value = null;
      loadingSetupData.value = true;
      if (setupData.value.selected_contract ||
        setupData.value.selected_person) {
        let save_data = {
          step: '1',
          selected_contract: setupData.value.selected_contract,
          //selected_person: setupData.value.selected_person
        }

        let response = await $CommitmentDepositApiService.getData(save_data);
        selectedInvoices.value = response.invoices;
        holder.value = response.holder
        contract.value = response.contract
        requestsFound.value = response.deposits
        payerOptions.value.push(response.holder);
        if (response.tenant) payerOptions.value.push(response.tenant);
        if (response.owner) payerOptions.value.push(response.owner);
      } else if (setupData.value.selected_invoice) {
        let save_data = {
          step: '1',
          selected_contract: setupData.value.selected_contract,
          selected_invoice: setupData.value.selected_invoice
          //selected_person: setupData.value.selected_person
        }
        selectedInvoices.value = [setupData.value.selected_invoice]
        let response = await $CommitmentDepositApiService.getData(save_data);
        selectedInvoices.value = response.invoices;
        holder.value = response.holder
        contract.value = response.contract
        requestsFound.value = response.deposits
        payerOptions.value.push(response.holder);
        if (response.tenant) payerOptions.value.push(response.tenant);
        if (response.owner) payerOptions.value.push(response.owner);
        /* holder.value = {
          token: setupData.value.selected_invoice.customer_token_final,
          name: setupData.value.selected_invoice.customer_final
        }
        console.log("setupData.value.selected_invoice")
        console.log(setupData.value.selected_invoice)
        contract.value = {
          id :setupData.value.selected_invoice.contract,
          token: setupData.value.selected_invoice.contract_token
        }
        console.log("contract.value")
        console.log(contract.value) */
      } else {
        selectedInvoices.value = []
        holder.value = null
        contract.value = null
      }
      if (holder.value) {
        selectedPayer.value = holder.value.id;
      }
      loadingSetupData.value = false;
    } else {
      let save_data = {
        step: '1',
        invoices: invoicesData.value.invoices.map(x => x.id),
        found_request: true,
      }
      let response = await $CommitmentDepositApiService.getData(save_data);
      invoicesData.value.invoices = response.invoices;
      selectedInvoices.value = response.invoices.concat(request.value.invoices);
    }
    setupData.value.loading_invoices = false;
    setupData.value.total_invoices = selectedInvoices.value.length;

  } else if (currentStep.value == 1) {
    let remaining_invoices = invoicesData.value.invoices.filter(invoice => !invoicesData.value.ignored_invoices.includes(invoice))
    paymentsData.value = {
      invoices: remaining_invoices,
      holder: payerOptions.value.find(payer => payer.id == selectedPayer.value),
      contract: contract.value,
      remaining: paymentsData?.value?.remaining ? paymentsData.value.remaining : 0,
      payments: paymentsData?.value?.payments ? paymentsData.value.payments : [],
      days_next_payment: paymentsData?.value?.days_next_payment ? paymentsData.value.days_next_payment : 30,
      due_date_commitment: paymentsData?.value?.due_date_commitment ? paymentsData.value.due_date_commitment : (format(new Date(), 'yyyy-MM-dd')).toString(),
      start_date_commitment: paymentsData?.value?.start_date_commitment ? paymentsData.value.start_date_commitment : (format(new Date(), 'yyyy-MM-dd')).toString(),
    }
  } else if (currentStep.value == 2) {
    payments.value = paymentsData.value.payments
    summaryData.value = {
      payments: paymentsData.value.payments,
      holder: payerOptions.value.find(payer => payer.id == selectedPayer.value),
      contract: contract.value,
      invoices: paymentsData.value.invoices,
    }
  }
} // end save function

</script>

<template>
  <div v-if="objectPermissions?.can_change" class="text-base">


    <div class="mb-2">
      <div class="flex space-x-4 justify-between">
        <div class="buttons flex gap-4 ml-4">
          <button v-for="(step, index) in steps" :disabled="index > maxStep"
            class="px-4 py-2 rounded-full focus:outline-none" :class="{
              'bg-blue-500 text-white': currentStep === index,
              'bg-gray-200 text-gray-600 cursor-not-allowed': index > maxStep,
              'bg-blue-100 text-blue-500': maxStep >= index
            }" @click="currentStep = index; setUrlStep()"> {{ t('billing_block.step') }} {{ step }}
          </button>
        </div>
        <div>
          <!-- OPTIONAL -->
          <StatusesNav v-if="commitmentDepositStatus" :active="commitmentDepositStatus"
            :statuses="commitmentDepositStatuses" />
        </div>
      </div>
    </div>

    <!-- Contingut del Pas Actual -->
    <div v-if="loading">
      <AppLoading :text="$t('common.loading')" />
    </div>
    <div v-else class="border border-gray-300 rounded-b p-4 bg-white">

      <div v-if="currentStep === 0" class="tab-content mb-6 relative">
        <!-- SETUP SCREEN -->
        <Teleport v-if="requestsFound && requestsFound.length > 0" to="body">
          <div @click="requestsFound = null"
            class="fixed inset-0 text-sm flex items-center justify-center bg-black bg-opacity-50 z-30">
            <SelectExistingCommitmentRequest @click.stop :requests="requestsFound" @close="requestsFound = null" />
          </div>
        </Teleport>

        <CommitmentDepositManage v-if="foundRequest" @change="getInvoicesData" :request="request" :holder="holder"
          :payments="payments" :contract="contract" />
        <CommitmentDepositSetup v-else @change="getSetupData" :data="setupData" />

        <div class="max-w-xl px-5">
          <div class="flex flex-col justify-between h-full">
            <label class="mb-2 block text-sm font-medium text-slate-600">
              {{ $t('contract_block.payer') }} *
            </label>
            <!-- <v-select class="block w-full custom-select" v-model="selectedPayer"
              :options="payerOptions" :clearable="false" /> -->
            <select id="payment_method" v-model="selectedPayer" class="w-full text-base border border-gray-300 rounded p-2"
              :disabled="payerOptions.length <= 1 || loadingSetupData" @change="onSelectPayerChange">
              <option v-if="loadingSetupData" :value="null">-- {{ t('common.loading') }} --</option>
              <option v-if="!loadingSetupData" :value="null">-- {{ t('common.select_payment_method') }} --</option>
              <option v-if="!loadingSetupData" v-for="payer in payerOptions" :key="payer.id" :value="payer.id">
                {{ payer.name }} {{ payer.token }}
              </option>
            </select>
          </div>
        </div>

      </div>

      <div v-if="currentStep === 1" class="tab-content mb-6">
        <div id="wrapper" class="text-base">
          <!-- INFO SCREEN -->
          <CommitmentDepositInvoiceSummary @change="getInvoicesData" :data="invoicesData" />
        </div>
      </div>

      <div v-if="currentStep === 2" class="tab-content mb-6">
        <div id="wrapper" class="text-base">
          <!-- PAYMENTS SCREEN -->
          <CommitmentDepositPayments @change="getPaymentsData" :data="paymentsData" :request="request" :is_split="splitPayments" />
        </div>
      </div>

      <div v-if="currentStep === 3" class="tab-content mb-6">
        <div id="wrapper" class="text-base">
          <!-- FINAL SUMMARY SCREEN -->
          <CommitmentDepositFinalSummary :data="summaryData" :request="request" />
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
        <button v-if="currentStep !== steps.length - 1" @click="nextStep" :disabled="selectedInvoices.length == 0
          || (invoicesData?.invoices && invoicesData?.invoices?.length == invoicesData?.ignored_invoices?.length)
          || (currentStep == 2 && (paymentsData.remaining != 0 || paymentsData.payments.length == 0))
          || (invoicesData?.disable)"
          class="px-4 py-2 bg-green-500 text-white rounded enabled:hover:bg-green-600 disabled:opacity-70">
          {{ $t('common.next') }} &nbsp;&rarr;
        </button>
        <div v-else class="flex flex-row-reverse gap-3">
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