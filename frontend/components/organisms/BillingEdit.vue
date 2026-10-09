<script setup>
import { ref, onMounted, onUnmounted, computed } from 'vue';
import { useToast } from 'vue-toastification';
import BillingSetup from '~/components/molecules/BillingSetup.vue';
import BillingSummary from '~/components/molecules/BillingSummary.vue';
import BillingDocumentsSummary from '~/components/molecules/BillingDocumentsSummary.vue';
import BillingInvoicesSummary from '~/components/molecules/BillingInvoicesSummary.vue';
import CommunicationProcessRegion from './CommunicationProcessRegion.vue';
import AppLoading from '~/components/atoms/AppLoading.vue';

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const toast = useToast()

const { $StatusApiService, $BillingBatchApiService, $ConfigProjectApiService, $BillingApiService } = useNuxtApp();

const props = defineProps({
  billing: Object,
  task_id: String,
  invoices: Array
});

const emit = defineEmits(['refresh']);

const steps = ref(['1', '2', '3', '4']);
const currentStep = ref(0);
const maxStep = ref(0);

const loading = ref(true);
const disableNextStep = ref(true)

const textSeeSummary = ref(true)

const statusProcessingToken = ref(null);
const statusPendingToken = ref(null);
const statusProcessingDocumentsToken = ref(null);
const statusProcessedToken = ref(null);

const showDialog = ref(false);
const canClose = ref(false);

const issue_date = ref(new Date().toISOString().split('T')[0]);
const end_at = ref(new Date(Date.now() + 60 * 24 * 60 * 60 * 1000).toISOString().split('T')[0]);
const send_at = ref(new Date(Date.now() + 7 * 24 * 60 * 60 * 1000).toISOString().split('T')[0]);

const loadInvoices = ref(false);

const statuses = ref([]);
const status = ref(null);
const setupData = ref(null);

const invoices = ref([]);
const task_id = ref(null);
const queue_item_id = ref(null);
const isQueueBlocked = ref(false);
const queueInterval = ref(null);
const activeQueueItem = ref(null);
const fullQueueList = ref([]);
const showPendingList = ref(true);
const showFinishedList = ref(false);

const runningTasks = computed(() => {
  return fullQueueList.value.filter(item => item.status === 'running');
});

const pendingTasks = computed(() => {
  return fullQueueList.value.filter(item => item.status === 'pending');
});

const finishedTasks = computed(() => {
  return fullQueueList.value.filter(item => ['completed', 'failed', 'skipped'].includes(item.status));
});

const checkQueueStatus = async () => {
  try {
    const queueList = await $BillingApiService.getBillingQueue();
    if (queueList && Array.isArray(queueList)) {
      fullQueueList.value = queueList;
      
      const activeItem = queueList.find(
        item => ['pending', 'running'].includes(item.status)
      );
      activeQueueItem.value = activeItem;

      const activeItemForThisLot = queueList.find(
        item => item.billing_id === props.billing.id && ['pending', 'running'].includes(item.status)
      );

      if (activeItemForThisLot) {
        isQueueBlocked.value = true;
        if (currentStep.value !== 0) {
          disableNextStep.value = true;
        }
        if (!queue_item_id.value) {
          queue_item_id.value = activeItemForThisLot.id;
        }
        if (activeItemForThisLot.task_id && !task_id.value) {
          task_id.value = activeItemForThisLot.task_id;
        }
      } else {
        isQueueBlocked.value = false;
        disableNextStep.value = false;
      }
    }
  } catch (err) {
    console.error("Error checking billing queue:", err);
  }
};

const queueActionLoadingId = ref(null);

const queueActionConfirmMessages = {
  kill: 'confirmation_text_block.confirm_kill_queue_task',
  skip: 'confirmation_text_block.confirm_skip_queue_task',
  restart: 'confirmation_text_block.confirm_restart_queue_task',
};

const sendQueueAction = async (item, action) => {
  if (!confirm(t(queueActionConfirmMessages[action]))) return;
  queueActionLoadingId.value = item.id;
  try {
    await $BillingApiService.sendBillingQueueAction(item.id, action);
    await checkQueueStatus();
  } catch (err) {
    console.error(`Error sending '${action}' to billing queue item ${item.id}:`, err);
    toast.error(t('billing_block.error_queue_action') || 'Error en gestionar la tasca.');
  } finally {
    queueActionLoadingId.value = null;
  }
};

const showRegionDetailComponent = ref(null)
const regionDetailId = ref(null)
const showRegion = ref(false)
const isSubRegionOpen = ref(false)

const loadData = async () => {
  if (props.billing.total_readings && props.billing.total_readings > 0) disableNextStep.value = false;
  task_id.value = props.task_id;
  if (props.billing.status?.token == statusProcessingToken.value || props.billing.status?.token == statusPendingToken.value) {
    currentStep.value = 1;
    maxStep.value = 1;
    if (props.billing.status?.token == statusPendingToken.value) {
      loadInvoices.value = true
      textSeeSummary.value = true
    }
  }
  if (props.billing.status?.token == statusProcessingDocumentsToken.value || props.billing.status?.token == statusProcessedToken.value) {
    currentStep.value = 3;
    maxStep.value = 3;
    if (props.billing.status?.token == statusProcessedToken.value) {
      loadInvoices.value = true
    }
  }

  loading.value = false;
  setUrlStep();
}


const openDialog = () => {
  if (!showDialog.value) {
    canClose.value = false;
    showDialog.value = true;
    setTimeout(() => {
      canClose.value = true;
    }, 1)
  }
}

const clickOutside = () => {
  if (canClose.value) {
    showDialog.value = false;
    canClose.value = false;
  }
}

const onReadingsAssigned = () => {
  disableNextStep.value = false;
}

const getStatusTokens = async () => {
  statusProcessingToken.value = await $ConfigProjectApiService.get('billing_batch_processing')
  statusPendingToken.value = await $ConfigProjectApiService.get('billing_batch_pending')
  statusProcessingDocumentsToken.value = await $ConfigProjectApiService.get('billing_batch_processing_documents')
  statusProcessedToken.value = await $ConfigProjectApiService.get('billing_batch_processed')
}

const activeStatus = computed(() => {
  if (currentStep.value === 2) {
    return statuses.value.find(s => s.token === 'resum');
  }
  return status.value;
});

const setStatus = (token) => {
  status.value = statuses.value.find(s => s.token == token)
}

const previousStep = () => {
  currentStep.value--;
  setUrlStep();
}

const onSetupChanged = (data) => {
  setupData.value = data;
}

// billing-batch/summary

const nextStep = async () => {
  if (currentStep.value == 0) {
    if (confirm(t('confirmation_text_block.confirm_generate_batch'))) {
      await save();
      disableNextStep.value = true;
      setStatus(statusProcessingToken.value)
      next()
    }
  }
  else if (currentStep.value == 1) {
    next()
  }
    else if (currentStep.value == 2) {
      openDialog();
    }
};

const clickFinalize = () => {
  navigateTo('/billing/invoice?billing=' + props.billing.id);
}

const clickPdf = async () => {
  $BillingApiService.getBatchPdf(props.billing.id).then(response => response.arrayBuffer())
    .then(buffer => {
      const blob = new Blob([buffer], { type: 'application/pdf' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `billing_${new Date().toLocaleString('default', { month: '2-digit', year: '2-digit' }).replace(/\//g, '_')}.pdf`;
      a.click();
    })
}

const next = () => {
  if (currentStep.value < steps.value.length - 1) {
    currentStep.value++;
    if (currentStep.value > maxStep.value) {
      maxStep.value = currentStep.value;
    }
    setUrlStep();
  }
}

const getData = async () => {
  loading.value = true;
  await getStatusTokens()
  const data = await $StatusApiService.getAll('billing-status', 'billing')
  statuses.value = [...data.results];

  // Inyectamos el paso de "Resum" manualmente para que aparezca en el NAV
  const pendingIndex = statuses.value.findIndex(s => s.token == statusPendingToken.value);
  if (pendingIndex > -1) {
    statuses.value.splice(pendingIndex + 1, 0, {
      id: 'resum',
      token: 'resum',
      name: t('billing_block.step_summary'),
      color: 'blue'
    });
  }

  loadData()
};

const setUrlStep = () => {
  router.replace({
    query: {
      ...route.query, // Keep existing query parameters
      step: currentStep.value + 1
    }
  });
}
const recalculate = (res) => {
  disableNextStep.value = true
  setStatus(statusProcessingToken.value)
  loadInvoices.value = false
  task_id.value = res?.task_id || null
  queue_item_id.value = res?.queue_item_id || null
}

const success = () => {
  disableNextStep.value = false
  setStatus(statusPendingToken.value)
  loadInvoices.value = true
  textSeeSummary.value = true
}

const showDetail = (region, id) => {
  showRegionDetailComponent.value = region;
  regionDetailId.value = id;
  toggleRegion(true)
}

const toggleRegion = (force) => {
  showRegion.value = force !== undefined ? force : !showRegion.value;
  if (!force) {
    showRegionDetailComponent.value = null;
    regionDetailId.value = null;
  }
}

const handleSubRegionEvent = (event) => {
  isSubRegionOpen.value = event;
};

watch(showDialog, (val) => {
  if (!val) {
    canClose.value = false;
  }
});

onMounted(() => {
  status.value = props.billing.status;
  if ((props.invoices && props.invoices.length > 0) || props.task_id) {
    // task_id.value=props.task_id
    // currentStep.value = 1;
    // maxStep.value = 1;
    // invoices.value = props.invoices;
  }
  else {
    if (route.query.step) {
      currentStep.value = parseInt(route.query.step) - 1;
      maxStep.value = currentStep.value;
    }
  }
  setUrlStep();
  getData();
  checkQueueStatus();
  queueInterval.value = setInterval(checkQueueStatus, 5000);
});

onUnmounted(() => {
  clearInterval(queueInterval.value);
});

const save = async () => {
  if (currentStep.value == 0) {
    // 1. Setup
    let data = setupData.value || {};

    data['billing'] = props.billing.id
    if (!data) return;

    const results = await $BillingBatchApiService.generateSummary(data);
    queue_item_id.value = results['queue_item_id']
    task_id.value = results['task_id']

  }
  else if (currentStep.value == 1) {

    // const results = await $BillingBatchApiService.generateDocuments(props.billing.id);
    // console.log(results)
    // task_id.value = results['task_id']

    // console.log('save', 'step 1', invoices);
  }
  else if (currentStep.value == 2) {
    let date_data = {
      'issue_date': issue_date.value,
      'end_date': end_at.value,
      'send_date': send_at.value,
      'invoice_ids': props.invoices ? props.invoices.map(i => i.id) : [],
      'context': {}
    }
    const results = await $BillingBatchApiService.generateDocuments(props.billing.id, date_data);
    loadInvoices.value = false
    queue_item_id.value = results['queue_item_id']
    task_id.value = results['task_id']
  }
} // end save function

const validateBatch = async () => {
  if (confirm(t('confirmation_text_block.confirm_validate_batch'))) {
    await save();
    setStatus(statusProcessingDocumentsToken.value)
    next()
    showDialog.value = false;
  }
}

const cancelBilling = async () => {
  if (!confirm(t("confirmation_text_block.confirm_cancel"))) return
  try {
    await $BillingApiService.cancel(props.billing.id);
    toast.success(t("common.saved_successfully") || "Saved successfully");
    router.push('/billing/billing/');
  } catch (err) {
    console.error(err);
    toast.error(t("common.error") || "Error");
  }
}

</script>

<template>
  <div class="text-base">
    <div class="mb-2 flex space-x-4 justify-between">
      <AtomsStatusesNav v-if="statuses && statuses.length > 0" :statuses="statuses" :active="activeStatus" class="pr-10" />
    </div>

    <!-- Contingut del Pas Actual -->
    <div v-if="loading">
      <AppLoading :text="$t('common.loading')" />
    </div>
    <div v-else class="border border-gray-300 rounded-b p-4 bg-white">

      <!-- Cua de Processos de Facturació -->
      <div v-if="fullQueueList.length > 0" class="mb-6 border border-slate-200 rounded-md bg-slate-50 p-4">
        <h3 class="text-sm font-bold text-slate-700 uppercase tracking-wider mb-3 flex items-center gap-2">
          <Icon name="fa6-solid:list-check" class="text-sky-600" />
          {{ $t('billing_queue_title') }}
        </h3>

        <!-- Processos Actius -->
        <div v-if="runningTasks.length > 0" class="mb-4">
          <div class="space-y-3 mt-2">
            <div v-for="item in runningTasks" :key="item.id" class="p-3 border border-amber-200 bg-amber-50/70 rounded-md">
              <div class="flex justify-between items-start mb-1 text-sm">
                <span class="font-semibold text-amber-900">
                  {{ item.billing_name || 'Lot ' + item.billing_id }}
                  <span class="text-xs font-normal text-slate-500">({{ item.task_type_display }})</span>
                </span>
                <span class="text-xs font-bold px-2 py-0.5 rounded bg-amber-500 text-amber-800">
                  {{ $t('running') }}
                </span>
              </div>
              <div class="text-xs text-amber-800 mb-1">
                <span>{{ item.processed_items }} / {{ item.total_items }} ({{ item.percent }}%)</span>
              </div>
              <AtomsProgressBar :progress="item.percent" :error="false" />
              <div class="flex justify-end gap-2 mt-2">
                <button type="button" :disabled="queueActionLoadingId === item.id" @click="sendQueueAction(item, 'restart')"
                  class="text-xs px-2 py-1 rounded border border-sky-300 text-sky-700 bg-white hover:bg-sky-50 flex items-center gap-1 disabled:opacity-50">
                  <Icon :name="queueActionLoadingId === item.id ? 'fa6-solid:spinner' : 'fa6-solid:rotate-right'" :class="{ 'animate-spin': queueActionLoadingId === item.id }" />
                  {{ $t('common.restart') || 'Reiniciar' }}
                </button>
                <button type="button" :disabled="queueActionLoadingId === item.id" @click="sendQueueAction(item, 'skip')"
                  class="text-xs px-2 py-1 rounded border border-slate-300 text-slate-600 bg-white hover:bg-slate-100 flex items-center gap-1 disabled:opacity-50">
                  <Icon name="fa6-solid:forward" />
                  {{ $t('common.skip') || 'Saltar' }}
                </button>
                <button type="button" :disabled="queueActionLoadingId === item.id" @click="sendQueueAction(item, 'kill')"
                  class="text-xs px-2 py-1 rounded border border-red-300 text-red-700 bg-white hover:bg-red-50 flex items-center gap-1 disabled:opacity-50">
                  <Icon name="fa6-solid:ban" />
                  {{ $t('common.kill_task') || 'Matar tasca' }}
                </button>
              </div>
            </div>
          </div>
        </div>

        <!-- Processos Pendents -->
        <div v-if="pendingTasks.length > 0" class="mb-4">
          <button type="button" @click="showPendingList = !showPendingList" class="w-full flex justify-between items-center py-1.5 text-xs font-semibold text-slate-500 uppercase hover:text-slate-800 transition-colors focus:outline-none">
            <span>{{ $t('queued_processes') }} ({{ pendingTasks.length }})</span>
            <Icon :name="showPendingList ? 'fa6-solid:chevron-down' : 'fa6-solid:chevron-right'" />
          </button>
          
          <div v-if="showPendingList" class="space-y-3 mt-2">
            <div v-for="item in pendingTasks" :key="item.id" class="p-3 border border-amber-200 bg-amber-50/70 rounded-md">
              <div class="flex justify-between items-start mb-1 text-sm">
                <span class="font-semibold text-amber-900">
                  {{ item.billing_name || 'Lot ' + item.billing_id }}
                  <span class="text-xs font-normal text-slate-500">({{ item.task_type_display }})</span>
                </span>
                <span class="text-xs font-bold px-2 py-0.5 rounded bg-slate-200 text-slate-700">
                  {{ $t('queued_pending') }}
                </span>
              </div>
              <div class="text-xs text-amber-800 mb-1">
                <span>{{ $t('waiting_in_queue_turn') }}</span>
              </div>
            </div>
          </div>
        </div>

        <!-- Historial de Processos Finalitzats -->
        <div v-if="finishedTasks.length > 0">
          <button type="button" @click="showFinishedList = !showFinishedList" class="w-full flex justify-between items-center py-1.5 text-xs font-semibold text-slate-500 uppercase hover:text-slate-800 transition-colors focus:outline-none">
            <span>{{ $t('last_finished_processes') }} ({{ finishedTasks.length }})</span>
            <Icon :name="showFinishedList ? 'fa6-solid:chevron-down' : 'fa6-solid:chevron-right'" />
          </button>
          
          <div v-if="showFinishedList" class="max-h-60 overflow-y-auto divide-y divide-slate-200 bg-white rounded-md border border-slate-200 mt-2">
            <div v-for="item in finishedTasks" :key="item.id" class="p-3 flex justify-between items-center text-sm">
              <div class="min-w-0">
                <p class="font-medium text-slate-700 truncate">
                  {{ item.billing_name || 'Lot ' + item.billing_id }}
                  <span class="text-xs font-normal text-slate-400">({{ item.task_type_display }})</span>
                </p>
                <p v-if="item.status === 'failed' && item.error_message" class="text-xs text-red-600 mt-1 italic">
                  Error: {{ item.error_message }}
                </p>
              </div>
              <div class="flex items-center gap-3 shrink-0">
                <span class="text-xs text-slate-400">
                  {{ item.completed_at ? new Date(item.completed_at).toLocaleString() : '' }}
                </span>
                <span class="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-semibold"
                  :class="item.status === 'completed' ? 'bg-green-100 text-green-800' : item.status === 'skipped' ? 'bg-slate-200 text-slate-700' : 'bg-red-100 text-red-800'">
                  <Icon :name="item.status === 'completed' ? 'fa6-solid:circle-check' : item.status === 'skipped' ? 'fa6-solid:forward' : 'fa6-solid:circle-xmark'" />
                  {{ item.status === 'completed' ? $t('correct') : item.status === 'skipped' ? $t('common.skip') : $t('failed') }}
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div v-if="currentStep === 0" class="tab-content mb-6">
        <BillingSetup :billing="props.billing" @change="onSetupChanged" @readings-assigned="onReadingsAssigned" />
      </div>

      <div v-if="currentStep === 1" class="tab-content mb-6">
        <div id="wrapper" class="text-base">
          <BillingSummary @success="success" @recalculate="recalculate" :task_id="task_id" :queue_item_id="queue_item_id" :load_invoices="loadInvoices"
            :billing_id="props.billing ? props.billing.id : null" :isQueueBlocked="isQueueBlocked" />
        </div>
      </div>
      <div v-if="currentStep === 2" class="tab-content mb-6">
        <div id="wrapper" class="text-base">
          <BillingInvoicesSummary :billing_id="props.billing ? props.billing.id : null" :billing_name="props.billing ? props.billing.token : null" />
        </div>
      </div>
      <div v-if="currentStep === 3" class="tab-content mb-6">
        <div id="wrapper" class="text-base">
          <BillingDocumentsSummary @success="setStatus(statusProcessedToken)" :task_id="task_id" :queue_item_id="queue_item_id"
            :load_invoices="loadInvoices" :billing_id="props.billing ? props.billing.id : null"
            @show-detail="showDetail" />
        </div>
      </div>

      <!-- Botons de navegació -->
      <div class="flex justify-between mt-4">
        <div class="flex gap-3">
          <button 
            v-if="status?.token !== '-1'" 
            @click="cancelBilling"
            class="px-4 py-2 bg-red-600 text-white rounded hover:bg-red-700 transition-colors flex items-center"
          >
            <Icon name="fa6-solid:circle-xmark" class="mr-2" />
            {{ $t('common.cancel') }} {{ $t('billing') }}
          </button>
          <button 
            v-if="currentStep > 1" 
            @click="previousStep"
            class="px-4 py-2 bg-slate-500 text-white rounded hover:bg-slate-600 transition-colors flex items-center"
          >
            <Icon name="fa6-solid:circle-chevron-left" class="mr-2" />
            {{ $t('common.previous') }}
          </button>
        </div>
        <button v-if="currentStep == 1 && textSeeSummary" @click="nextStep" :disabled="disableNextStep || isQueueBlocked"
          class="px-4 py-2 bg-green-500 text-white rounded enabled:hover:bg-green-600 disabled:opacity-70">
          {{ $t('common.see_summary') }} &nbsp;&rarr;
        </button>
        <button v-else-if="currentStep !== steps.length - 1" @click.stop="nextStep" :disabled="disableNextStep || (currentStep !== 0 && isQueueBlocked)"
          class="px-4 py-2 bg-green-500 text-white rounded enabled:hover:bg-green-600 disabled:opacity-70">
          {{ $t('common.next') }} &nbsp;&rarr;
        </button>
        <div v-else class="flex gap-3">
          <!-- <button @click="clickPdf" class="button-default">
            <Icon name="fa6-solid:file-pdf" />&nbsp; {{ $t('Descarregar pdf') }}
          </button> -->
          <button @click="clickFinalize" :disabled="isQueueBlocked"
            class="px-4 py-2 bg-green-500 text-white rounded disabled:opacity-50 enabled:hover:bg-green-600 font-bold flex items-center">
            <Icon name="fa6-solid:circle-check" />&nbsp; {{ $t('common.check') }} {{ $t('invoices') }}
          </button>
        </div>
      </div><!-- end contingut botons -->

    </div><!--end contingut pas actual -->

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
        <CommunicationProcessRegion v-if="showRegionDetailComponent === 'CommunicationProcessRegion'" :id="regionDetailId"
          :isSubRegionOpen="isSubRegionOpen" @show-subregion="handleSubRegionEvent" />
      </div>
    </div>

    <Transition enter-active-class="transition duration-300 ease-out" enter-from-class="transform scale-95 opacity-0"
      enter-to-class="transform scale-100 opacity-100" leave-active-class="transition duration-200 ease-in"
      leave-from-class="transform scale-100 opacity-100" leave-to-class="transform scale-95 opacity-0">
      <div v-if="showDialog" v-click-outside="clickOutside"
        class="w-1/4 h-50 bg-white z-50 fixed top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2 rounded-md shadow-md">
        <div class="flex justify-between items-center p-4">
          <h2 class="text-xl font-semibold">{{ $t('common.validate') }}</h2>
          <button @click="showDialog = false" class="hover:text-slate-700 p-2">
            <Icon name="fa6-solid:xmark" />
          </button>
        </div>
        <div class="p-4">
          <div class="mb-4">
            <div class="mb-2 grid grid-cols-[150px,1fr]">
              <span class="text-slate-400 mt-4">
                {{ t('billing_block.sel_issue_date') }}
              </span>
              <AtomsInputDate v-model="issue_date" class="no-border mr-2" />
            </div>
          </div>
          <div class="mb-4">
            <div class="mb-2 grid grid-cols-[150px,1fr]">
              <span class="text-slate-400 mt-4">
                {{ t('common.due_date') }}
              </span>
              <AtomsInputDate v-model="end_at" class="no-border mr-2" />
            </div>
          </div>
          <div class="mb-4">
            <div class="mb-2 grid grid-cols-[150px,1fr]">
              <span class="text-slate-400 mt-4">
                {{ t('common.send_date') }} ({{ t('common.remittance') }})
              </span>
              <AtomsInputDate v-model="send_at" class="no-border mr-2" />
            </div>
          </div>
          <div class="flex justify-end">
            <button class="button-primary" @click="validateBatch">
              <Icon name="fa6-solid:check" class="mr-2" />
              {{ $t('common.validate') }}
            </button>
          </div>
        </div>
      </div>
    </Transition>

  </div>
</template>