<script setup>
import { ref, onMounted, watch, computed } from 'vue';
import { useI18n } from 'vue-i18n';
import _ from 'lodash';
import debounce from 'lodash.debounce';
import H1 from '~/components/atoms/H1.vue';
import InvoiceViewEdit from '~/components/organisms/InvoiceViewEdit.vue';
import MissingContractsDetail from './MissingContractsDetail.vue';
import ConsumptionAlertsDetail from './ConsumptionAlertsDetail.vue';
import BilledInvoicesCard from './BilledInvoicesCard.vue';
import BilledInvoicesDetail from './BilledInvoicesDetail.vue';
import PossibleNonBilledCard from './PossibleNonBilledCard.vue';
import ContractRegion from '~/components/organisms/ContractRegion.vue';
import ReadingBatchRegion from '~/components/organisms/ReadingBatchRegion.vue';
import { useToast } from 'vue-toastification';

const toast = useToast();


const { t, te } = useI18n();
const { $apiManager, $InvoiceApiService, $BillingApiService, $ConsumptionManagementApiService } = useNuxtApp();

const props = defineProps({
  task_id: String,
  queue_item_id: [String, Number],
  billing_id: Number,
  load_invoices: Boolean,
  isQueueBlocked: Boolean
});

const emit = defineEmits(['success', 'recalculate']);
const loadingBilling = ref(false);
const pagination = ref({
  page: 1,
  perPage: 50,
  total: 0,
  totalPages: 0,
  previous: null,
  next: null,
  isFiltered: false
});
const searchInput = ref('');

const error = ref(false);
const loadingInvoices = ref(false);
const progress = ref(0);
const batch_id = ref(0);
const invoices = ref([]);
const counters = ref(null);
const queueStatus = ref(null);
const queueErrorMessage = ref(null);
const taskFallbackPolls = ref(0);
const MAX_TASK_FALLBACK_POLLS = 90;

const reloading = ref(false);
const showReload = ref(false);

const numInvoices = ref(0)
const numSuccessInvoices = ref(0)
const numWarningInvoices = ref(0)
const numExcludedInvoices = ref(0)
const selectedInvoices = ref([])

const showingDetailId = ref(0)
const showHistoryId = ref(0)
const invoiceId = ref(0)
const subRegionEntity = ref('InvoiceRegion')
const contractId = ref(0)
const readingBatchId = ref(0)
const updateCards = ref(false)

const search_filter = ref('')
const title = ref('')

const sortBy = ref(null)
const sortDesc = ref(false)
const filterPossibleLeakComm = ref(false)

const billing = ref(null)

const warningInvoices = ref([])
const showInvoices = ref([])
const medianDuration = ref(0);
const numDateRangeWarnings = ref(0);

const consumptionAlertsCount = ref(0);
const loadingConsumptionAlerts = ref(false);

const alertLabel = (alert) => {
  if (!alert) return '';

  const blockKey = `billing_block.${alert}`;
  if (te(blockKey)) return t(blockKey);
  if (te(alert)) return t(alert);

  return alert;
};

const loadConsumptionAlerts = async () => {
  loadingConsumptionAlerts.value = true;
  try {
    const res = await $ConsumptionManagementApiService.getAll('', null, 1, null, false, 'history', props.billing_id);
    consumptionAlertsCount.value = res.count || 0;
  } catch (e) {
    console.error('Error loading consumption alerts:', e);
  } finally {
    loadingConsumptionAlerts.value = false;
  }
};

const loadingInfoMissingContracts = ref(false);
const infoMissingContracts = ref({})
const missingContracts = ref([])
const loadingMissingContracts = ref(false);
const missingRegionType = ref(null);

const billedInvoicesType = ref(null);

const readingBatchesList = computed(() => [
  ...(billing.value?.reading_batches || []),
  ...(billing.value?.missing_batch || [])
]);

let itvl = null;
const showRegion = ref(false);
const showSubRegion = ref(false);
const showRegionComponent = ref(null);
const toggleRegion = (force) => {
  showRegion.value = force !== undefined ? force : !showRegion.value;
  if (!force) {
    showRegionComponent.value = null;
    showSubRegion.value = false;
  }
}
const toggleSubRegion = (force) => {
  showSubRegion.value = force !== undefined ? force : !showSubRegion.value;
}

const openDetail = (filter, warningName) => {
  pagination.value.page = 1;
  showRegionComponent.value = 'BillingSummary';
  search_filter.value = ""
  title.value = '';
  filterPossibleLeakComm.value = false;
  switch (filter) {
    case 'all':
      // showReadings.value = readings.value;
      search_filter.value = ''
      break;
    case 'correct':
      title.value = 'correctes';
      search_filter.value = 'alert=null'
      break;
    case 'warning':
      if (warningName) {
        title.value = ": " + (t('billing_block.' + warningName) !== 'billing_block.' + warningName ? t('billing_block.' + warningName) : warningName);
        search_filter.value = 'alert=' + warningName
      } else {
        title.value = 'incorrectes';
        search_filter.value = 'alert=any'
      }
      break;
    case 'excluded':
      title.value = t('common.excluded');
      search_filter.value = 'is_excluded=true'
      break;
  }
  getData('', 1)
  showRegion.value = true;
};

const openMissingRegion = async (type) => {
  missingRegionType.value = type;
  loadingMissingContracts.value = true;
  showRegionComponent.value = 'MissingContracts';
  showRegion.value = true;
  try {
    missingContracts.value = [];
    const res = await $BillingApiService.checkMissingContracts(props.billing_id, type)
    if (res) {
      missingContracts.value = res.results;
      console.log("missingContracts.value")
      console.log(missingContracts.value)
    }
  } catch (e) {
    console.error("Error getting missing contracts:", e);
  } finally {
    loadingMissingContracts.value = false;
  }
}

const openBilledInvoicesRegion = (type) => {
  billedInvoicesType.value = type;
  showRegionComponent.value = 'BilledInvoices';
  showRegion.value = true;
}

const sortInvoicesBy = (field) => {
  if (field === sortBy.value) {
    sortDesc.value = !sortDesc.value;
  } else {
    sortBy.value = field;
    sortDesc.value = false;
  }
  getData(searchInput.value, 1);
};

const togglePossibleLeakCommFilter = () => {
  filterPossibleLeakComm.value = !filterPossibleLeakComm.value;
  pagination.value.page = 1;
  getData(searchInput.value, 1);
};

const getData = async (query = null, page = 1) => {
  loadingInvoices.value = true;
  try {
    if (page === 1) {
      showInvoices.value = [] // Replace data on initial load
    }
    const result = await $InvoiceApiService.getBatchInvoices(
      props.billing_id,
      query,
      page,
      search_filter.value,
      sortBy.value,
      sortDesc.value,
      filterPossibleLeakComm.value
    );

    if (page === 1) {
      showInvoices.value = result.results;
    } else {
      showInvoices.value = [...showInvoices.value, ...result.results];
    }

    Object.assign(pagination.value, {
      total: result.count,
      totalPages: Math.ceil(result.count / pagination.value.perPage),
      previous: result.previous,
      next: result.next,
      isFiltered: false
    });

    if (result.date_range_median) medianDuration.value = result.date_range_median;

  } catch (err) {
    console.error(err);
  } finally {
    loadingInvoices.value = false;
  }
}

const loadMore = async () => {
  if (loadingInvoices.value || !pagination.value.next) return;

  pagination.value.page++;
  await getData(searchInput.value, pagination.value.page);
};

const handleSearch = () => {
  pagination.value.page = 1;
  debouncedGetData(searchInput.value);
}

const debouncedGetData = debounce((query) => {
  getData(query, pagination.value.page);
}, 300);


const onScroll = async (event) => {
  const { scrollTop, scrollHeight, clientHeight } = event.target;

  if (scrollTop + clientHeight >= scrollHeight - 20 && !loadingInvoices.value) {
    await loadMore();
  }
};

onBeforeRouteLeave((to, from) => {
  clearInterval(itvl)
});




const loadData = async () => {
  if (props.load_invoices) {
    showReload.value = true
    try {
      const res = await $InvoiceApiService.getBatchInvoicesSummary(props.billing_id)
      counters.value = res.counters || res;
      updateCards.value = !updateCards.value
    } catch (e) {
      console.error("Error loading summary:", e);
    }
  }

  if (counters.value) {
    progress.value = 100;
    numInvoices.value = counters.value['total'] || 0;
    numWarningInvoices.value = counters.value['total_warnings'] || 0;
    numExcludedInvoices.value = counters.value['excluded'] || 0;
    warningInvoices.value = [];

    if (counters.value.date_range_median) {
      medianDuration.value = counters.value.date_range_median;
    }

    let summedWarnings = 0;
    for (let [key, value] of Object.entries(counters.value)) {
      if (key != 'total' && key != 'total_warnings' && key != 'total_correct' && key != 'date_range_median' && key != 'excluded') {
        if (key === 'date_range_above_margin_count') {
          key = 'warning_date_range';
          numDateRangeWarnings.value = value;
        }
        summedWarnings += value;

        if (value > 0) {
          warningInvoices.value.push({
            alert: key,
            count: value
          })
        }
      }
    }
    console.log("warningInvoices.value")
    console.log(warningInvoices.value)

    if (counters.value['total_warnings'] === undefined) {
      numWarningInvoices.value = summedWarnings;
      numSuccessInvoices.value = numInvoices.value - numWarningInvoices.value;
    } else {
      numSuccessInvoices.value = counters.value['total_correct'];
    }

    getInfoMissingContracts();

  } else if ((props.queue_item_id || props.task_id || props.billing_id) && !['completed', 'failed', 'skipped'].includes(queueStatus.value)) {
    error.value = false;
    queueErrorMessage.value = null;
    taskFallbackPolls.value = 0;
    clearInterval(itvl);

    itvl = setInterval(async () => {
      try {
        // Sempre que tenim billing_id (pràcticament sempre en aquest component) fem
        // servir /billing/billing-queue/?billing_id=<id>, que ja retorna `percent`/
        // `status` calculats i evita haver de consultar per separat `/task-progress/
        // <task_id>/` a cada tick (crida redundant i que no cal fer des del front).
        let queueRes = null;

        if (props.billing_id) {
          const queueList = await $apiManager.fetch(useRuntimeConfig().public.apiHost + `/billing/billing-queue/?billing_id=${props.billing_id}`, 'GET');
          if (queueList && Array.isArray(queueList)) {
            queueRes = [...queueList]
              .filter(i => ['pending', 'running', 'failed', 'skipped', 'completed'].includes(i.status))
              .sort((a, b) => new Date(b.created_at) - new Date(a.created_at))[0] || null;
          }
        } else if (props.queue_item_id) {
          queueRes = await $apiManager.fetch(useRuntimeConfig().public.apiHost + '/billing/billing-queue/' + props.queue_item_id + '/', 'GET');
        }

        if (queueRes) {
          queueStatus.value = queueRes.status;
          // Actualitzem sempre el comptador de factures processades amb el darrer valor
          // rebut, independentment de l'estat concret (`running`, `completed`...): la cua
          // pot seguir incrementant `invoices_processed`/`processed_items` encara que
          // l'status ja no sigui literalment 'running' en aquest tick.
          // Fem servir `||` i no `??`: per a alguns `task_type` el backend envia
          // `invoices_processed` sempre present però fixat a 0 (no `null`/`undefined`),
          // i el comptador real puja per `processed_items` — `??` mai hi cauria.
          if (queueRes.invoices_processed || queueRes.processed_items) {
            numInvoices.value = queueRes.invoices_processed || queueRes.processed_items || 0;
          }
          if (queueRes.status === 'pending') {
            progress.value = 0;
          } else if (queueRes.status === 'running') {
            progress.value = queueRes.percent || 0;
            if (queueRes.percent >= 100.0) {
              queueStatus.value = 'completed';
              clearInterval(itvl);
              progress.value = 100;
              showReload.value = true;
              reloading.value = false;
              emit('success');
              loadData();
            }
          } else if (queueRes.status === 'completed' || queueRes.percent >= 100.0) {
            queueStatus.value = 'completed';
            clearInterval(itvl);
            progress.value = 100;
            showReload.value = true;
            reloading.value = false;
            emit('success');
            loadData();
          } else if (queueRes.status === 'failed' || queueRes.status === 'skipped') {
            clearInterval(itvl);
            error.value = true;
            queueErrorMessage.value = queueRes.error_message;
            showReload.value = true;
            reloading.value = false;
          }
          return;
        }

        // Fallback: no s'ha trobat cap item de BillingQueue per aquest billing_id (p. ex.
        // lot antic/de prova sense entrada a la cua), però sí tenim un task_id directe des
        // del propi Billing per consultar-lo puntualment via /task-progress/.
        if (props.task_id) {
          const res = await $apiManager.checkTask(props.task_id)
          if (res) {
            progress.value = res.percent || 0
            numInvoices.value = res.current || 0

            if (res.state === 'SUCCESS') {
              showReload.value = true
              reloading.value = false
              clearInterval(itvl)
              emit('success')
              loadData();
            }
            else if (res.state === 'FAILURE' || res.state === 'REVOKED') {
              error.value = true;
              queueStatus.value = 'failed';
              queueErrorMessage.value = res.state === 'FAILURE' && typeof res.result === 'string' ? res.result : null;
              showReload.value = true;
              reloading.value = false
              clearInterval(itvl)
            }
            else if (['PENDING', 'STARTED', 'PROGRESS'].includes(res.state)) {
              taskFallbackPolls.value += 1;
              if (taskFallbackPolls.value >= MAX_TASK_FALLBACK_POLLS) {
                error.value = true;
                queueStatus.value = 'failed';
                queueErrorMessage.value = null;
                showReload.value = true;
                reloading.value = false;
                clearInterval(itvl);
              }
            }
          }
        } else {
          // No hi ha cap item de cua trobat ni task_id per consultar: donem per acabat.
          clearInterval(itvl);
        }
      }
      catch (e) {
        clearInterval(itvl)
      }
    }, 5000)
  }
};

const getBilling = async () => {
  loadingBilling.value = true;
  try {
    const res = await $BillingApiService.getDetail(props.billing_id)
    billing.value = res
    console.log("billing.value")
    console.log(billing.value)
  } catch (err) {
    console.error(err);
  } finally {
    loadingBilling.value = false;
  }
}

const linkedReadingBatchId = computed(() => {
  if (billing.value?.reading_batch) {
    return typeof billing.value.reading_batch === 'object' ? billing.value.reading_batch.id : billing.value.reading_batch;
  }
  if (billing.value?.reading_batches?.length > 0) {
    return billing.value.reading_batches[0].id;
  }
  if (billing.value?.og_billing?.id) return billing.value.og_billing.id;
  if (billing.value?.missing_batch?.length > 0) return billing.value.missing_batch[0].id;
  return null;
});

const openReadingBatch = () => {
  if (linkedReadingBatchId.value) {
    openRegion({ id: linkedReadingBatchId.value, entity: 'ReadingBatchRegion' });
  }
}

const getInfoMissingContracts = async (reload = false) => {
  if (reload) {
    loadData();
    getData(searchInput.value, 1);
    if (showRegion.value && showRegionComponent.value === 'MissingContracts') {
      openMissingRegion(missingRegionType.value);
    }
  }
  loadingInfoMissingContracts.value = true;
  try {
    const res = await $BillingApiService.checkMissingContracts(props.billing_id)
    infoMissingContracts.value = res;
  } catch (e) {
    console.error("Error getting info missing contracts:", e);
  } finally {
    loadingInfoMissingContracts.value = false;
  }
}

const regenerate = async () => {
  try {
    if (confirm(t('confirmation_text_block.confirm_recalculate_invoices'))) {
      reloading.value = true
      counters.value = null;
      warningInvoices.value = [];
      invoices.value = [];
      progress.value = 0;
      numInvoices.value = 0;
      numSuccessInvoices.value = 0;
      numWarningInvoices.value = 0;
      const res = await $BillingApiService.recalculate(props.billing_id);
      emit('recalculate', res);
    }
  }
  catch (e) {
    console.log(e)
    reloading.value = false
  }
}

const isQueueFailed = computed(() => queueStatus.value === 'failed' || queueStatus.value === 'skipped');
const restartingQueue = ref(false);

/**
 * Resol l'id de l'item de BillingQueue a rellançar: el propi `queue_item_id` si el tenim,
 * o si només disposem del `task_id` (flux antic), el busquem pel `billing_id` filtrant per
 * evitar el límit dels últims 10 items globals.
 */
const resolveFailedQueueItemId = async () => {
  if (props.queue_item_id) return props.queue_item_id;
  try {
    const queueList = await $apiManager.fetch(useRuntimeConfig().public.apiHost + `/billing/billing-queue/?billing_id=${props.billing_id}`, 'GET');
    if (queueList && Array.isArray(queueList)) {
      const item = [...queueList]
        .filter(i => ['failed', 'skipped'].includes(i.status))
        .sort((a, b) => new Date(b.created_at) - new Date(a.created_at))[0];
      return item?.id || null;
    }
  } catch (e) {
    console.error('Error resolving failed queue item:', e);
  }
  return null;
}

/**
 * Rellança la mateixa tasca de la cua (BillingQueue) que ha quedat en estat failed/skipped.
 * Si no hi ha cap item de cua per aquest billing (p. ex. lot antic/de prova sense entrada
 * a BillingQueue, amb `task_id` guardat directament a `Billing`), no hi ha res a "reiniciar"
 * a la cua: en aquest cas es fa un recàlcul complet (mateixa acció que "Recalcular factures").
 */
const restartQueueTask = async () => {
  restartingQueue.value = true;
  try {
    const targetQueueItemId = await resolveFailedQueueItemId();
    if (!targetQueueItemId) {
      await regenerate();
      return;
    }
    await $BillingApiService.sendBillingQueueAction(targetQueueItemId, 'restart');
    error.value = false;
    queueStatus.value = null;
    queueErrorMessage.value = null;
    showReload.value = false;
    progress.value = 0;
    loadData();
  } catch (e) {
    console.error('Error restarting queue task:', e);
    toast.error(t('billing_block.error_queue_action') || 'Error en gestionar la tasca.');
  } finally {
    restartingQueue.value = false;
  }
}

const openRegion = (e) => {
  console.log(e)
  if (typeof e === 'object') {
    if (e.entity === 'ContractRegion') {
      contractId.value = e.id;
      subRegionEntity.value = 'ContractRegion';
    } else if (e.entity === 'ReadingBatchRegion') {
      readingBatchId.value = e.id;
      subRegionEntity.value = 'ReadingBatchRegion';
    } else {
      invoiceId.value = e.id;
      subRegionEntity.value = 'InvoiceRegion';
    }
  } else {
    invoiceId.value = e;
    subRegionEntity.value = 'InvoiceRegion';
  }
  showSubRegion.value = true;
}
const onShowDetail = (id) => {
  showingDetailId.value = id;
}
const onShowHistory = (id) => {
  showHistoryId.value = id;
}

const handleInvoiceExcluded = () => {
  loadData();
  getData(searchInput.value, 1);
}

const handleSelect = (id) => {
  if (selectedInvoices.value.includes(id)) {
    selectedInvoices.value = selectedInvoices.value.filter(i => i !== id)
  } else {
    selectedInvoices.value.push(id)
  }
}

const selectAll = () => {
  if (selectedInvoices.value.length === showInvoices.value.length && showInvoices.value.length > 0) {
    selectedInvoices.value = []
  } else {
    selectedInvoices.value = showInvoices.value.map(i => i.id)
  }
}

const massExclude = async () => {
  if (selectedInvoices.value.length === 0) return;

  const reinclude = search_filter.value === 'is_excluded=true';
  const confirmMsg = reinclude
    ? t("confirmation_text_block.confirm_include_invoice")
    : t("confirmation_text_block.confirm_exclude_mass");
  const successMsg = reinclude
    ? t("billing_block.correct_include_invoice")
    : t("billing_block.correct_exclude_mass");

  try {
    if (confirm(confirmMsg)) {
      loadingInvoices.value = true;
      await $InvoiceApiService.excludeInvoice({ invoice_ids: selectedInvoices.value });
      toast.success(successMsg);
      selectedInvoices.value = [];
      loadData();
      getData(searchInput.value, 1);
    }
  } catch (error) {
    console.error(error);
    toast.error(t("billing_block.error_exclude_mass"));
  } finally {
    loadingInvoices.value = false;
  }
}

onMounted(() => {
  loadData();
  getBilling();
  loadConsumptionAlerts();
});

watch([() => props.task_id, () => props.queue_item_id], () => {
  progress.value = 0;
  invoices.value = [];
  queueStatus.value = null;
  queueErrorMessage.value = null;
  loadData();
})
watch(() => props.load_invoices, (newValue) => {
  if (newValue) {
    loadData();
  }
})


</script>

<template>
  <div id="wrapper" class="text-base">
    <div class="mb-2">
      <h2 class="mb-1 text-xl font-semibold">{{ $t('billing_block.prev_invoices') }}</h2>
      <div class="flex gap-2">
        <button v-if="showReload" :disabled="reloading || props.isQueueBlocked"
          class="flex items-center gap-2 rounded-md px-3 py-1.5 border transition-all enabled:bg-sky-50 enabled:border-sky-200 enabled:text-sky-700 enabled:hover:bg-sky-100 enabled:hover:border-sky-300 disabled:opacity-50 shadow-sm text-sm font-medium group"
          @click="regenerate" :title="t('billing_block.recalc_invoices')">
          <Icon name="fa6-solid:rotate-right" :class="reloading ? 'animate-spin' : ''"
            class="w-3.5 h-3.5 text-sky-500" />
          {{ t('billing_block.recalc_invoices') }}
        </button>

        <button v-if="isQueueFailed" :disabled="restartingQueue"
          class="flex items-center gap-2 rounded-md px-3 py-1.5 border transition-all enabled:bg-red-50 enabled:border-red-200 enabled:text-red-700 enabled:hover:bg-red-100 enabled:hover:border-red-300 disabled:opacity-50 shadow-sm text-sm font-medium group"
          @click="restartQueueTask" :title="t('common.restart')">
          <Icon :name="restartingQueue ? 'fa6-solid:spinner' : 'fa6-solid:rotate-right'"
            :class="{ 'animate-spin': restartingQueue }" class="w-3.5 h-3.5 text-red-500" />
          {{ t('common.restart') }}
        </button>

        <button v-if="linkedReadingBatchId"
          class="flex items-center gap-2 rounded-md px-3 py-1.5 border transition-all bg-emerald-50 border-emerald-200 text-emerald-700 hover:bg-emerald-100 hover:border-emerald-300 shadow-sm text-sm font-medium group"
          @click="openReadingBatch" :title="t('billing_block.modify_wrong_readings')">
          <Icon name="fa6-solid:file-pen" class="w-3.5 h-3.5 text-emerald-500" />
          {{ t('billing_block.modify_wrong_readings') }}
        </button>
      </div>
    </div>

    <div class="mb-4 grid grid-cols-3 gap-x-2">
      <div class="footering border border-gray-300 rounded-md bg-white max-w-md">
        <AtomsProgressBar :progress="progress" :error="error" />
        <div v-if="queueStatus === 'pending'" class="px-4 py-2 text-sm text-slate-500 italic">
          {{ $t('waiting_in_queue') }}
        </div>
        <div v-if="isQueueFailed"
          class="px-4 py-2 border-t border-red-100 bg-red-50 flex items-center justify-between gap-2">
          <span class="inline-flex items-center gap-1 text-sm font-semibold text-red-700 shrink-0">
            <Icon name="fa6-solid:circle-exclamation" />
            {{ t('failed') }}
          </span>
          <span v-if="queueErrorMessage" class="text-sm text-red-600 font-medium truncate">
            {{ queueErrorMessage }}
          </span>
          <button type="button" :disabled="restartingQueue" @click="restartQueueTask"
            class="shrink-0 flex items-center gap-1 rounded px-2 py-1 border border-red-300 bg-white text-red-700 hover:bg-red-100 disabled:opacity-50 text-xs font-semibold"
            :title="t('common.restart')">
            <Icon :name="restartingQueue ? 'fa6-solid:spinner' : 'fa6-solid:rotate-right'"
              :class="{ 'animate-spin': restartingQueue }" />
            {{ t('common.restart') }}
          </button>
        </div>
        <ul class="divide-y divide-gray-200">
          <li class="flex justify-between items-center p-4 relative group">
            <span class="font-bold">{{ t('num_invoices') }}:</span>
            <span
              class="inline-flex items-center bg-slate-300 text-slate-700 text-sm rounded-full px-2 py-1 ml-2 mr-5">{{
                numInvoices }}</span>
            <div
              class="w-10 cursor-pointer opacity-0 group-hover:opacity-100 transition-all duration-150 bg-gradient-to-r from-transparent to-slate-300 h-full rounded-t-md absolute top-0 right-0 flex items-center justify-center"
              @click="openDetail('all')" :title="t('common.view_details')">
              <Icon name="fa6-solid:eye" class="w-4 h-4 text-slate-500" />
            </div>
          </li>
          <li class="flex justify-between items-center p-4 relative group">
            <span class="font-bold">{{ t('common.correct') }}:</span>
            <span
              class="inline-flex items-center bg-green-300 text-slate-700 text-sm rounded-full px-2 py-1 ml-2 mr-5">{{
                numSuccessInvoices }}</span>
            <div
              class="w-10 cursor-pointer opacity-0 group-hover:opacity-100 transition-all duration-150 bg-gradient-to-r from-transparent to-slate-300 h-full absolute top-0 right-0 flex items-center justify-center"
              @click="openDetail('correct')" :title="t('common.view_details')">
              <Icon name="fa6-solid:eye" class="w-4 h-4 text-slate-500" />
            </div>
          </li>
          <li>
            <div class="flex relative group justify-between items-center p-4">
              <span class="font-bold">{{ t('common.warnings') }}:</span>
              <span
                class="inline-flex items-center bg-yellow-400 text-slate-700 text-sm rounded-full px-2 py-1 ml-2 mr-5">{{
                  numWarningInvoices }}</span>
              <div v-if="numWarningInvoices != 0"
                class="w-10 cursor-pointer opacity-0 group-hover:opacity-100 transition-all duration-150 bg-gradient-to-r from-transparent to-slate-300 h-full absolute top-0 right-0 flex items-center justify-center"
                @click="openDetail('warning')" :title="t('common.view_details')">
                <Icon name="fa6-solid:eye" class="w-4 h-4 text-slate-500" />
              </div>
            </div>
            <div v-for="warning in warningInvoices">
              <div class="flex justify-between items-center py-3 px-4 relative group">
                <span class="pl-5 text-sm font-semibold">{{ alertLabel(warning.alert) }}</span>
                <span
                  class="inline-flex items-center bg-yellow-400 text-slate-700 text-sm rounded-full px-2 py-1 ml-2 mr-5">{{
                    warning.count }}</span>
                <div
                  class="w-10 cursor-pointer opacity-0 group-hover:opacity-100 transition-all duration-150 bg-gradient-to-r from-transparent to-slate-300 h-full absolute top-0 right-0 flex items-center justify-center"
                  @click="openDetail('warning', warning.alert)" :title="t('common.view_details')">
                  <Icon name="fa6-solid:eye" class="w-4 h-4 text-slate-500" />
                </div>
              </div>
            </div>
          </li>
          <li class="flex justify-between items-center p-4 relative group">
            <span class="font-bold">{{ t('common.excluded') }}:</span>
            <span
              class="inline-flex items-center bg-slate-200 text-slate-700 text-sm rounded-full px-2 py-1 ml-2 mr-5">{{
                numExcludedInvoices }}</span>
            <div
              class="w-10 cursor-pointer opacity-0 group-hover:opacity-100 transition-all duration-150 bg-gradient-to-r from-transparent to-slate-300 h-full absolute top-0 right-0 flex items-center justify-center"
              @click="openDetail('excluded')" :title="t('common.view_details')">
              <Icon name="fa6-solid:eye" class="w-4 h-4 text-slate-500" />
            </div>
          </li>
        </ul>
      </div>

      <BilledInvoicesCard :billing_id="props.billing_id" :is_finished="false" :update_cards="updateCards"
        @open-billed-invoices="openBilledInvoicesRegion" />

      <div class="flex justify-end">
        <div v-if="!loadingBilling" class="flex flex-col gap-2 w-full max-w-md">
          <button v-if="consumptionAlertsCount > 0"
            @click="showRegionComponent = 'ConsumptionAlerts'; showRegion = true"
            class="flex items-center justify-between gap-3 m-1 w-full rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800 hover:bg-amber-100 transition-colors shadow-sm text-left">
            <div class="flex items-center gap-2">
              <Icon name="fa6-solid:triangle-exclamation" class="w-4 h-4 text-amber-500 shrink-0" />
              <span class="font-medium">{{ $t('billing_block.consumption_alerts_warning') }}</span>
            </div>
            <div class="flex items-center gap-2 shrink-0">
              <span
                class="inline-flex items-center justify-center rounded-full bg-amber-200 px-2 py-0.5 text-xs font-bold text-amber-800">
                {{ consumptionAlertsCount }}
              </span>
              <Icon name="fa6-solid:eye" class="w-3.5 h-3.5 text-amber-600" />
            </div>
          </button>
          <div v-else-if="loadingConsumptionAlerts"
            class="m-1 flex items-center gap-2 rounded-lg border border-slate-100 bg-slate-50 px-4 py-3 text-sm text-slate-400">
            <Icon name="fa6-solid:spinner" class="animate-spin w-3 h-3" />
            <span>{{ $t('common.loading') }}...</span>
          </div>

          <PossibleNonBilledCard :billing="billing" :info="infoMissingContracts"
            :loading="loadingInfoMissingContracts" :reading-batches="readingBatchesList"
            @open-missing-region="openMissingRegion" />

        </div>
        <div v-else class="w-full max-w-md mx-1 border border-gray-300 rounded-md bg-white h-fit">
          <AtomsAppLoading />
        </div>
      </div>

    </div>
    <div role="region"
      class="fixed h-full border-l border-gray-100 top-0 right-0 transition-all duration-500 ease py-2 text-base bg-white  z-20 overflow-hidden"
      :class="{ 'translate-x-0': showRegion, 'translate-x-[2000px]': !showRegion, 'w-[90%]': showRegionComponent === 'BillingSummary', 'w-[75%]': showRegionComponent != 'BillingSummary' }">
      <div id="region_nav" class="mb-3 px-3">
        <button @click="toggleRegion(false)" class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300">
          <Icon name="fa6-solid:angles-right" class="text-slate-500" />
        </button>
      </div>
      <div v-if="showRegionComponent === 'BillingSummary'" class="px-10 flex flex-col h-full">
        <!-- Added h-full here -->
        <H1>{{ t('invoices') }} {{ title }}</H1>
        <span class="input-group flex flex-start items-center gap-2 w-80">
          <Icon name="fa6-solid:magnifying-glass" class="text-slate-500" />
          <input v-model="searchInput" @input="handleSearch" id="searchInput" type="text" name="search"
            :placeholder="$t('dashboard.search')"
            class="w-full p-1 rounded-md focus:outline-none focus-visible:border-0" autocomplete="off" />
        </span>
        <div class="flex justify-between items-center mt-4 mb-2">
          <div v-if="medianDuration > 0" class="text-sm text-slate-600 italic">
            {{ t('common.median') }}: <span class="font-bold font-mono">{{ medianDuration }} {{ t('common.days')
              }}</span>
          </div>
          <div v-else></div>
          <div v-if="selectedInvoices.length > 0">
            <button @click="massExclude"
              class="px-3 py-1.5 bg-rose-500 text-white rounded-md hover:bg-rose-600 transition-colors flex items-center gap-2 text-sm font-semibold shadow-sm">
              <Icon name="fa6-solid:trash-can" />
              {{ t('common.exclude') }} ({{ selectedInvoices.length }})
            </button>
          </div>
        </div>
        <div class="my-2">
          <button type="button" @click="togglePossibleLeakCommFilter"
            class="inline-flex items-center gap-2 rounded-md border px-2 py-1 text-xs font-medium transition-colors"
            :class="filterPossibleLeakComm
              ? 'border-orange-400 bg-orange-100 text-orange-800'
              : 'border-orange-200 bg-orange-50 text-orange-700 hover:bg-orange-100'">
            <input type="checkbox" :checked="filterPossibleLeakComm" tabindex="-1"
              class="pointer-events-none w-3.5 h-3.5 rounded border-orange-300 text-orange-500 focus:ring-0" />
            {{ t('billing_block.legend_possible_leak_comm') }}
          </button>
        </div>
        <div
          class="grid grid-cols-[40px_minmax(0,1.5fr)_minmax(0,1fr)_minmax(0,1fr)_minmax(0,1fr)_minmax(0,1fr)_minmax(0,1fr)_minmax(0,1fr)_100px_260px] gap-2 px-4 border-b border-gray-400 items-center shrink-0 overflow-y-hidden [scrollbar-gutter:stable]">
          <div class="p-3 flex items-center justify-center">
            <input type="checkbox" :checked="selectedInvoices.length === showInvoices.length && showInvoices.length > 0"
              @change="selectAll" class="w-4 h-4 rounded border-gray-300 text-sky-600 focus:ring-sky-500" />
          </div>
          <button type="button" @click="sortInvoicesBy('customer_final')"
            class="p-3 font-bold flex items-center gap-2 text-start hover:bg-slate-50 rounded min-w-0">
            <Icon class="shrink-0"
              :name="sortBy !== 'customer_final' ? 'fa6-solid:sort' : sortDesc ? 'fa6-solid:sort-up' : 'fa6-solid:sort-down'" />
            <span class="truncate" :title="t('common.client')">{{ t('common.client') }}</span>
          </button>
          <button type="button" @click="sortInvoicesBy('contract__token')"
            class="p-3 font-bold flex items-center gap-2 text-start hover:bg-slate-50 rounded min-w-0">
            <Icon class="shrink-0"
              :name="sortBy !== 'contract__token' ? 'fa6-solid:sort' : sortDesc ? 'fa6-solid:sort-up' : 'fa6-solid:sort-down'" />
            <span class="truncate" :title="t('contract')">{{ t('contract') }}</span>
          </button>
          <button type="button" @click="sortInvoicesBy('use_type_final')"
            class="p-3 font-bold flex items-center gap-2 text-start hover:bg-slate-50 rounded min-w-0">
            <Icon class="shrink-0"
              :name="sortBy !== 'use_type_final' ? 'fa6-solid:sort' : sortDesc ? 'fa6-solid:sort-up' : 'fa6-solid:sort-down'" />
            <span class="truncate" :title="t('common.use_type')">{{ t('common.use_type') }}</span>
          </button>
          <button type="button" @click="sortInvoicesBy('payment_type_final')"
            class="p-3 font-bold flex items-center gap-2 text-start hover:bg-slate-50 rounded min-w-0">
            <Icon class="shrink-0"
              :name="sortBy !== 'payment_type_final' ? 'fa6-solid:sort' : sortDesc ? 'fa6-solid:sort-up' : 'fa6-solid:sort-down'" />
            <span class="truncate" :title="t('billing_block.payment')">{{ t('billing_block.payment') }}</span>
          </button>
          <button type="button" @click="sortInvoicesBy('total_final')"
            class="p-3 font-bold flex items-center gap-2 text-start hover:bg-slate-50 rounded min-w-0">
            <Icon class="shrink-0"
              :name="sortBy !== 'total_final' ? 'fa6-solid:sort' : sortDesc ? 'fa6-solid:sort-up' : 'fa6-solid:sort-down'" />
            <span class="truncate" :title="t('billing_block.total_invoice')">{{ t('billing_block.total_invoice') }}</span>
          </button>
          <button type="button" @click="sortInvoicesBy('left_to_pay')"
            class="p-3 font-bold flex items-center gap-2 text-start hover:bg-slate-50 rounded min-w-0">
            <Icon class="shrink-0"
              :name="sortBy !== 'left_to_pay' ? 'fa6-solid:sort' : sortDesc ? 'fa6-solid:sort-up' : 'fa6-solid:sort-down'" />
            <span class="truncate" :title="t('billing_block.total_to_pay')">{{ t('billing_block.total_to_pay') }}</span>
          </button>
          <button type="button" @click="sortInvoicesBy('consumption')"
            class="p-3 font-bold flex items-center gap-2 text-start hover:bg-slate-50 rounded min-w-0">
            <Icon class="shrink-0"
              :name="sortBy !== 'consumption' ? 'fa6-solid:sort' : sortDesc ? 'fa6-solid:sort-up' : 'fa6-solid:sort-down'" />
            <span class="truncate" :title="t('consumption')">{{ t('consumption') }}</span>
          </button>
          <button type="button" @click="sortInvoicesBy('consumption_days')"
            class="p-3 font-bold flex items-center gap-2 text-start hover:bg-slate-50 rounded min-w-0">
            <Icon class="shrink-0"
              :name="sortBy !== 'consumption_days' ? 'fa6-solid:sort' : sortDesc ? 'fa6-solid:sort-up' : 'fa6-solid:sort-down'" />
            <span class="truncate" :title="t('billing_block.date_range_number_days')">{{ t('billing_block.date_range_number_days') }}</span>
          </button>
          <span class="p-3 font-bold"></span>
        </div>
        <div class="overflow-y-auto [scrollbar-gutter:stable] flex-grow pb-10" @scroll="onScroll">
          <div v-for="invoice in showInvoices" :key="invoice.id">
            <AtomsInvoiceEdit @show-edit="onShowDetail" @show-history="onShowHistory" @open-region="openRegion"
              @excluded="handleInvoiceExcluded" @selected="handleSelect"
              :isSelected="selectedInvoices.includes(invoice.id)" :invoice="invoice"
              :showDetail="showingDetailId == invoice.id" :showHistory="showHistoryId == invoice.id"
              :medianDuration="medianDuration" />
          </div>
          <div v-if="loadingInvoices" class="text-center py-4">{{ t('common.loading') }}...</div>
        </div>
      </div>
      <div v-if="showRegionComponent === 'MissingContracts'" class="px-10 flex flex-col h-full">
        <MissingContractsDetail :loading="loadingMissingContracts" :missingContracts="missingContracts"
          :startDate="infoMissingContracts.start_date" :endDate="infoMissingContracts.end_date"
          :type="missingRegionType" :billingId="props.billing_id" @reload="getInfoMissingContracts(true)" />
      </div>
      <div v-if="showRegionComponent === 'BilledInvoices'" class="px-10 flex flex-col h-full">
        <BilledInvoicesDetail :billingId="props.billing_id" :type="billedInvoicesType" @reload="loadData" />
      </div>
      <div v-if="showRegionComponent === 'ConsumptionAlerts'" class="px-10 flex flex-col h-full">
        <ConsumptionAlertsDetail :billingId="props.billing_id" />
      </div>
    </div>
    <div role="region" id="right_over_page"
      class="fixed h-full border-l border-gray-100 top-0 right-0 transition-all duration-500 ease py-2 text-base bg-white w-[75%] z-30 shadow"
      :class="{ 'translate-x-0': showSubRegion, 'translate-x-[2000px]': !showSubRegion }">
      <div id="region_nav" class="mb-3 px-3">
        <button @click="toggleSubRegion(false)" class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300">
          <Icon name="fa6-solid:angles-right" class="text-slate-500" />
        </button>
      </div>
      <div class="px-10 overflow-y-auto h-full">
        <InvoiceViewEdit v-if="subRegionEntity === 'InvoiceRegion' && invoiceId != 0" :id="invoiceId"
          :isSubRegion="true" />
        <ContractRegion v-if="subRegionEntity === 'ContractRegion' && contractId != 0" :id="contractId"
          :isSubRegion="true" @show-subregion="toggleSubRegion(true)" />
        <ReadingBatchRegion v-if="subRegionEntity === 'ReadingBatchRegion' && readingBatchId != 0" :id="readingBatchId"
          :isSubRegion="true" />
      </div>
    </div>
  </div>
</template>
