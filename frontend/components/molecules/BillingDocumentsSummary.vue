<script setup>
import { ref, onMounted, watch, computed, onUnmounted } from 'vue';
import { useI18n } from 'vue-i18n';
import { useToast } from 'vue-toastification';
import debounce from 'lodash.debounce';
import _ from 'lodash';
import H1 from '~/components/atoms/H1.vue';
import MissingContractsDetail from './MissingContractsDetail.vue';
import BilledInvoicesCard from './BilledInvoicesCard.vue';
import BilledInvoicesDetail from './BilledInvoicesDetail.vue';
import PossibleNonBilledCard from './PossibleNonBilledCard.vue';
import InvoiceViewEdit from '~/components/organisms/InvoiceViewEdit.vue';
import ContractRegion from '~/components/organisms/ContractRegion.vue';
import { exportToXlsx } from '~/utils/xlsx-export';
import { getInvoiceDuration } from '~/utils/stats';

const { t } = useI18n();
const toast = useToast();
const { $apiManager, $InvoiceApiService, $BillingApiService, $ExploitationApiService  } = useNuxtApp();

const props = defineProps({
  task_id: String,
  queue_item_id: [String, Number],
  billing_id: Number,
  load_invoices: Boolean
});
const searchInput = ref('');

const emit = defineEmits(['success', 'show-detail']);

const pagination = ref({
  page: 1,
  perPage: 50,
  total: 0,
  totalPages: 0,
  previous: null,
  next: null,
  isFiltered: false
});

const error = ref(false);
const loadingInvoices = ref(false);
const loadingBilling = ref(true);
const progress = ref(0)
const batch_id = ref(0)
const invoices = ref([])
const counters = ref(null)

const pdfTaskIds = ref([]);
const pdfTasksInfo = ref({});
const pdfItvl = ref(null);
const queueStatus = ref(null);
const queueErrorMessage = ref(null);

const updateCards = ref(false)

const regenPdfTaskId = ref(null);
const regenPdfProgress = ref(0);
const regenPdfLoading = ref(false);
const regenPdfError = ref(false);
let regenPdfItvl = null;

const isRegenPdfRunning = computed(() => regenPdfLoading.value || (regenPdfTaskId.value && regenPdfProgress.value < 100 && !regenPdfError.value));

const regeneratePdfs = async () => {
  if (!confirm(t('billing_block.confirm_regenerate_pdfs'))) return;
  regenPdfLoading.value = true;
  regenPdfError.value = false;
  regenPdfProgress.value = 0;
  regenPdfTaskId.value = null;
  clearInterval(regenPdfItvl);
  try {
    const res = await $BillingApiService.regeneratePdfs(props.billing_id);
    regenPdfTaskId.value = res.task_id;
    regenPdfLoading.value = false;
    regenPdfItvl = setInterval(async () => {
      try {
        const status = await $BillingApiService.checkRegeneratePdfsTask(regenPdfTaskId.value);
        regenPdfProgress.value = status.percent || 0;
        if (status.state === 'SUCCESS') {
          regenPdfProgress.value = 100;
          clearInterval(regenPdfItvl);
        } else if (status.state === 'FAILURE') {
          regenPdfError.value = true;
          clearInterval(regenPdfItvl);
        }
      } catch (e) {
        regenPdfError.value = true;
        clearInterval(regenPdfItvl);
      }
    }, 2500);
  } catch (e) {
    regenPdfLoading.value = false;
    regenPdfError.value = true;
  }
};

const totalInvoicesOfBatch = computed(() => {
  if (counters.value && counters.value['total']) return counters.value['total'];
  if (numInvoices.value) return numInvoices.value;
  if (billing.value && billing.value.total_invoices) return billing.value.total_invoices;
  return 0;
});

const pdfProgress = computed(() => {
  const total = totalInvoicesOfBatch.value;
  if (!total) return 0;
  const completed = Object.values(pdfTasksInfo.value).reduce((sum, t) => sum + (t.current || 0), 0);
  return Math.min(Math.round((completed / total) * 100), 100);
});

const pdfError = computed(() => {
  return pdfTaskIds.value.some(id => pdfTasksInfo.value[id]?.state === 'FAILURE');
});

const isGeneratingPdfs = computed(() => {
  if (pdfTaskIds.value.length === 0) return false;
  return pdfTaskIds.value.some(id => {
    const task = pdfTasksInfo.value[id];
    return !task || task.state !== 'SUCCESS';
  });
});

const isMainTaskRunning = computed(() => {
  return props.task_id && progress.value < 100 && !error.value;
});

const isCommunicationBlocked = computed(() => {
  return isMainTaskRunning.value || isGeneratingPdfs.value;
});

const startPdfPolling = () => {
  clearInterval(pdfItvl.value);
  pdfTaskIds.value.forEach(id => {
    pdfTasksInfo.value[id] = { current: 0, state: 'PENDING' };
  });

  pdfItvl.value = setInterval(async () => {
    let allFinished = true;
    for (const id of pdfTaskIds.value) {
      const task = pdfTasksInfo.value[id];
      if (task && task.state === 'SUCCESS') continue;

      try {
        const res = await $apiManager.checkTask(id);
        if (res) {
          pdfTasksInfo.value[id] = {
            current: res.current || 0,
            state: res.state || 'PENDING'
          };
          if (res.state !== 'SUCCESS' && res.state !== 'FAILURE') {
            allFinished = false;
          }
        }
      } catch (e) {
        console.error("Error checking PDF task:", id, e);
      }
    }

    if (allFinished || pdfError.value) {
      clearInterval(pdfItvl.value);
    }
  }, 2000);
};

const totalExploitations = ref(0);

const numInvoices = ref(0)
const numDocuments = ref(0)
const totalQueueItems = ref(0)

const showingDetailId = ref(0)
const showingHistoryId = ref(0)
const invoiceId = ref(0)
const contractId = ref(0)
const subRegionEntity = ref('')
const exportingInvoices = ref(false)

const sortBy = ref('total_final')
const sortDesc = ref(false)
const filterPossibleLeakComm = ref(false)

const showInvoices = ref([])

const billing = ref(null)

const loadingInfoMissingContracts = ref(false);
const infoMissingContracts = ref({})
const missingContracts = ref([])
const loadingMissingContracts = ref(false);
const missingRegionType = ref(null);
const billedInvoicesType = ref(null);

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

const getData = async (query = null, page = 1) => {

  loadingInvoices.value = true;
  try {
    if (page === 1) {
      showInvoices.value = [] // Replace data on initial load
    }
    console.log("sortBy.value", sortBy.value)
    console.log("sortDesc.value", sortDesc.value)
    const result = await $InvoiceApiService.getBatchInvoices(props.billing_id, query, page, null, sortBy.value, sortDesc.value, filterPossibleLeakComm.value);

    if (page === 1) {
      showInvoices.value = result.results; // Replace data on initial load
    } else {
      showInvoices.value = [...showInvoices.value, ...result.results]; // Append data on subsequent loads
    }

    Object.assign(pagination.value, {
      total: result.count,
      totalPages: Math.ceil(result.count / pagination.value.perPage),
      previous: result.previous,
      next: result.next,
      isFiltered: false
    });

  } catch (err) {
    console.error(err);
  } finally {
    loadingInvoices.value = false;
  }
}

const getBilling = async () => {
  loadingBilling.value = true;
  try {
    const res = await $BillingApiService.getDetail(props.billing_id)
    billing.value = res
    console.log("billing.value")
    console.log(billing.value)
    getInfoMissingContracts();
  } catch (err) {
    console.error(err);
  } finally {
    loadingBilling.value = false;
  }
}

const getInfoMissingContracts = async (reload = false) => {
  if (reload) toggleRegion(false);
  loadingInfoMissingContracts.value = true;
  try {
    const res = await $BillingApiService.checkMissingContracts(billing.value.id)
    infoMissingContracts.value = res;
    const res_billing = await $BillingApiService.getDetail(props.billing_id)
    billing.value = res_billing
  } catch (e) {
    console.error("Error getting info missing contracts:", e);
  } finally {
    loadingInfoMissingContracts.value = false;
  }
}

const openDetail = (component) => {
  getData(searchInput.value, 1)
  showRegion.value = true;
  showRegionComponent.value = component;
};

const openBilledInvoicesRegion = (type) => {
  billedInvoicesType.value = type;
  showRegionComponent.value = 'BilledInvoices';
  showRegion.value = true;
}

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
  clearInterval(pdfItvl.value)
});

onUnmounted(() => {
  clearInterval(itvl)
  clearInterval(pdfItvl.value)
  clearInterval(regenPdfItvl)
});

const loadData = async () => {
  if (props.load_invoices) {
    // const res = await $InvoiceApiService.getBatchInvoices(props.billing_id)
    const res = await $InvoiceApiService.getBatchInvoicesSummary(props.billing_id)
    counters.value = res.counters;
  }
  updateCards.value = !updateCards.value

  if (counters.value) {
    progress.value = 100;
    numInvoices.value = counters.value['total'];
    totalQueueItems.value = counters.value['total'];
    numDocuments.value = counters.value['total'];
  } else if ((props.queue_item_id || props.task_id) && queueStatus.value !== 'completed' && queueStatus.value !== 'failed') {
    error.value = false;
    queueErrorMessage.value = null;
    clearInterval(itvl);
    let currentQueueItemId = props.queue_item_id;
    let currentTaskId = props.task_id;

    itvl = setInterval(async () => {
      try {
        if (currentQueueItemId) {
          const queueRes = await $apiManager.fetch(useRuntimeConfig().public.apiHost + '/billing/billing-queue/' + currentQueueItemId + '/', 'GET');
          if (queueRes) {
            queueStatus.value = queueRes.status;
            if (queueRes.status === 'pending') {
              progress.value = 0;
            } else if (queueRes.status === 'running') {
              progress.value = queueRes.percent || 0;
              numInvoices.value = queueRes.invoices_processed ?? queueRes.processed_items ?? 0;
              numDocuments.value = queueRes.documents_generated ?? 0;
              totalQueueItems.value = queueRes.total_items ?? 0;
              if (queueRes.percent >= 100.0) {
                queueStatus.value = 'completed';
                clearInterval(itvl);
                progress.value = 100;
                numDocuments.value = queueRes.documents_generated ?? numDocuments.value;
                totalQueueItems.value = queueRes.total_items ?? totalQueueItems.value;
                if (queueRes.result) {
                  batch_id.value = queueRes.result.id;
                  counters.value = queueRes.result.counters;
                  pdfTaskIds.value = queueRes.result.pdf_task_ids || [];
                }
                emit('success');
                loadData();
                if (pdfTaskIds.value.length > 0) {
                  startPdfPolling();
                }
                return;
              }
            } else if (queueRes.status === 'completed' || queueRes.percent >= 100.0) {
              queueStatus.value = 'completed';
              clearInterval(itvl);
              progress.value = 100;
              numDocuments.value = queueRes.documents_generated ?? numDocuments.value;
              totalQueueItems.value = queueRes.total_items ?? totalQueueItems.value;
              if (queueRes.result) {
                batch_id.value = queueRes.result.id;
                counters.value = queueRes.result.counters;
                pdfTaskIds.value = queueRes.result.pdf_task_ids || [];
              }
              emit('success');
              loadData();
              if (pdfTaskIds.value.length > 0) {
                startPdfPolling();
              }
              return;
            } else if (queueRes.status === 'failed') {
              queueStatus.value = 'failed';
              clearInterval(itvl);
              error.value = true;
              queueErrorMessage.value = queueRes.error_message;
              return;
            }
          }
        } else if (currentTaskId) {
          const res = await $apiManager.checkTask(currentTaskId)
          if (res) {
            progress.value = res.percent || 0
            numInvoices.value = res.current || 0

            if (res.state === 'SUCCESS') {
              clearInterval(itvl)
              batch_id.value = res.result?.id;
              counters.value = res.result?.counters;
              pdfTaskIds.value = res.result?.pdf_task_ids || [];
              emit('success')
              loadData();
              if (pdfTaskIds.value.length > 0) {
                startPdfPolling();
              }
            }
            else if (res.state === 'FAILURE') {
              error.value = true;
              clearInterval(itvl)
            }
          }
        }
      }
      catch (e) {
        clearInterval(itvl)
      }
    }, 5000)
  }

  try{
    const res_exploitations = await $ExploitationApiService.getData();
    totalExploitations.value = res_exploitations.count;
  } catch (e) {
    console.error("Error getting exploitations:", e);
  }
};

const sortInvoicesBy = (field) => {
  if (field == sortBy.value) {
    sortDesc.value = !sortDesc.value;
  } else {
    sortBy.value = field;
    sortDesc.value = false;
  }
  getData(searchInput.value, 1)
}

const togglePossibleLeakCommFilter = () => {
  filterPossibleLeakComm.value = !filterPossibleLeakComm.value;
  pagination.value.page = 1;
  getData(searchInput.value, 1)
}

const newCommunicationProcess = () => {
  return navigateTo('/communication/process-communications/add?billing_id=' + props.billing_id);
}

const openRegion = (e) => {
  if (typeof e === 'object' && e !== null) {
    if (e.entity === 'ContractRegion') {
      contractId.value = e.id;
      subRegionEntity.value = 'ContractRegion';
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

const invoiceUseType = (invoice) => {
  const useType = invoice?.use_type_final;
  if (!useType) return '';
  if (typeof useType === 'string') return useType;
  return useType.name || '';
};

const toNumberOrEmpty = (value) => {
  if (value === null || value === undefined || value === '') return '';
  const n = Number(value);
  return Number.isFinite(n) ? n : value;
};

const fetchAllInvoices = async () => {
  const all = [];
  let page = 1;
  while (page <= 200) {
    const result = await $InvoiceApiService.getBatchInvoices(
      props.billing_id,
      searchInput.value,
      page,
      null,
      sortBy.value,
      sortDesc.value,
      filterPossibleLeakComm.value
    );
    const batch = result?.results || [];
    all.push(...batch);
    if (!result?.next || batch.length === 0) break;
    page += 1;
  }
  return all;
};

const exportInvoicesXlsx = async () => {
  if (exportingInvoices.value) return;
  exportingInvoices.value = true;
  try {
    const rows = await fetchAllInvoices();
    const indexed = rows.map((row, index) => ({ ...row, _row: index + 1 }));
    exportToXlsx(
      indexed,
      [
        { header: '#', value: (row) => row._row },
        { header: t('common.client'), value: (row) => row.customer_final || '' },
        { header: t('contract'), value: (row) => row.contract_token || '' },
        { header: t('common.use_type'), value: (row) => invoiceUseType(row) },
        { header: t('billing_block.payment'), value: (row) => row.payment_type_final || '' },
        { header: t('billing_block.total_invoice'), value: (row) => toNumberOrEmpty(row.total_final) },
        { header: t('billing_block.total_to_pay'), value: (row) => toNumberOrEmpty(row.left_to_pay) },
        { header: t('billing_block.date_range_number_days'), value: (row) => getInvoiceDuration(row) ?? '' },
      ],
      `factures_${billing.value?.token || props.billing_id}`,
      t('invoices')
    );
  } catch (err) {
    console.error(err);
    toast.error(t('common.error_download'));
  } finally {
    exportingInvoices.value = false;
  }
};
const onShowDetail = (id) => {
  showingDetailId.value = id;
}

const onShowHistory = (id) => {
  showingHistoryId.value = id;
}

const detailComponent = ref(null)
const detailId = ref(null)

const showDetail = (region, id) => {
  emit('show-detail', region, id)
}

onMounted(() => {
  loadData();
  getBilling()
});

watch([() => props.task_id, () => props.queue_item_id], () => {
  progress.value = 0;
  invoices.value = [];
  pdfTaskIds.value = [];
  clearInterval(pdfItvl.value);
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
    <h2 class="text-xl font-semibold mb-4">{{ $t('common.generate_final_docs') }}</h2>

    <div class="mb-4 grid grid-cols-3 gap-x-2">
      <div class="footering border border-gray-300 rounded-md bg-white max-w-md h-fit p-4 space-y-4">
        <div>
          <h3 class="text-sm font-semibold text-slate-700 mb-1">
            {{ t('billing_block.phase_confirm_billing_data') }}
          </h3>
          <AtomsProgressBar :progress="progress" :error="error" />
          <div v-if="queueStatus === 'pending'" class="py-1 text-sm text-slate-500 italic">
            {{ $t('waiting_in_queue') }}
          </div>
          <div v-if="queueErrorMessage" class="py-1 text-sm text-red-600 font-medium bg-red-50">
            {{ queueErrorMessage }}
          </div>
        </div>

        <div v-if="pdfTaskIds.length > 0">
          <h3 class="text-sm font-semibold text-slate-700 mb-1">
            {{ t('billing_block.phase_pdf_generation') }}
          </h3>
          <AtomsProgressBar :progress="pdfProgress" :error="pdfError" />
        </div>

        <div class="border-t border-slate-200 pt-3">
          <h3 class="text-sm font-semibold text-slate-700 mb-2">{{ t('billing_block.regenerate_pdfs') }}</h3>
          <button
            type="button"
            class="relative overflow-hidden flex items-center gap-2 rounded-md px-4 py-2 text-sm font-medium transition-all disabled:opacity-50"
            :class="regenPdfError ? 'bg-red-500 text-white' : 'bg-sky-500 text-white hover:bg-sky-600'"
            :disabled="isRegenPdfRunning"
            @click="regeneratePdfs">
            <span
              v-if="isRegenPdfRunning && regenPdfTaskId"
              class="absolute inset-y-0 left-0 bg-white/20 transition-all duration-500 ease-out"
              :style="{ width: regenPdfProgress + '%' }" />
            <span class="relative flex items-center gap-2">
              <Icon
                :name="regenPdfLoading ? 'fa6-solid:spinner' : regenPdfError ? 'fa6-solid:triangle-exclamation' : 'fa6-solid:file-pdf'"
                :class="{ 'animate-spin': regenPdfLoading }" />
              <span v-if="isRegenPdfRunning && regenPdfTaskId">{{ Math.round(regenPdfProgress) }}%</span>
              <span v-else-if="regenPdfError">{{ t('common.error') }}</span>
              <span v-else>{{ t('billing_block.regenerate_pdfs') }}</span>
            </span>
          </button>
        </div>

        <ul class="divide-y divide-gray-200 border-t border-gray-200 pt-2">
          <li class="flex justify-between items-center py-4 relative group">
            <span class="font-bold">{{ t('billing_block.processed_invoices') }}:</span>
            <span
              class="inline-flex items-center bg-green-300 text-slate-700 text-sm rounded-full px-2 py-1 ml-2 mr-5">{{
                totalQueueItems ? `${numInvoices} / ${totalQueueItems}` : numInvoices }}</span>
            <div
              class="w-10 cursor-pointer opacity-0 group-hover:opacity-100 transition-all duration-150 bg-gradient-to-r from-transparent to-slate-300 h-full absolute top-0 right-0 flex items-center justify-center"
              @click="openDetail('BillingSummary')">
              <Icon name="fa6-solid:eye" class="w-4 h-4 text-slate-500" />
            </div>
          </li>
          <li v-if="totalQueueItems" class="flex justify-between items-center py-4 relative group">
            <span class="font-bold">{{ t('billing_block.documents_generated') }}:</span>
            <span
              class="inline-flex items-center bg-sky-300 text-slate-700 text-sm rounded-full px-2 py-1 ml-2 mr-5">{{
                `${numDocuments} / ${totalQueueItems}` }}</span>
          </li>
          <li v-if="!loadingBilling && billing">
            <div v-if="!billing.communication_process" class="flex justify-between items-center py-4 relative group">
              <span class="font-bold">{{ t('customer_service_block.generate_comms_process') }}</span>
              <div
                class="w-10 transition-all duration-150 h-full absolute top-0 right-0 flex items-center justify-center"
                :class="isCommunicationBlocked ? 'cursor-not-allowed opacity-30 pointer-events-none bg-slate-100' : 'cursor-pointer opacity-0 group-hover:opacity-100 bg-gradient-to-r from-transparent to-slate-300'"
                @click="!isCommunicationBlocked && newCommunicationProcess()">
                <Icon name="fa6-solid:envelopes-bulk" class="w-4 h-4 text-slate-500" />
              </div>
            </div>
            <div v-else>
              <div class="flex justify-between items-center p-4 relative group">
                <div class="w-full">
                  <span class="font-bold">{{ t('customer_service_block.check_comms_process') }}</span>
                  <div class="py-2">
                    <div class="flex items-center justify-between gap-2 text-slate-400">
                      {{ t('common.comms') }}:
                      <span class="font-semibold text-slate-500">
                        {{ billing.communication_process.total_communications }}
                      </span>
                    </div>

                    <div class="flex items-center justify-between gap-2 text-slate-400">
                      {{ t('customer_service_block.sent_comms') }}:
                      <span class="font-semibold text-sky-500">
                        {{ billing.communication_process.total_sent_communications }}
                      </span>
                    </div>

                    <div class="flex items-center justify-between gap-2 text-slate-400">
                      <p>
                        {{ t('common.description') }}:
                      </p>
                      <abbr :title="billing.communication_process.description"
                        class="font-semibold text-slate-500 truncate">
                        {{ billing.communication_process.description }}
                      </abbr>
                    </div>

                  </div>
                </div>
                <div
                  class="w-10 cursor-pointer opacity-0 group-hover:opacity-100 transition-all duration-150 bg-gradient-to-r from-transparent to-slate-300 h-full absolute top-0 right-0 flex items-center justify-center"
                  @click="showDetail('CommunicationProcessRegion', billing.communication_process.id)">
                  <Icon name="fa6-solid:eye" class="w-4 h-4 text-slate-500" />
                </div>
              </div>


            </div>
          </li>
        </ul>
      </div>

      <BilledInvoicesCard :billing_id="props.billing_id" :is_finished="true" :update_cards="updateCards"
        @open-billed-invoices="openBilledInvoicesRegion" />

      <div v-if="!loadingBilling" class="flex justify-end">
        <PossibleNonBilledCard :billing="billing" :info="infoMissingContracts"
          :loading="loadingInfoMissingContracts" :show-location-breakdown="totalExploitations > 1"
          :reading-batches="billing?.missing_batch || []"
          reading-batches-title-key="billing_block.generated_reading_batches"
          @open-missing-region="openMissingRegion" />

      </div>
      <div v-else class="w-full max-w-md mx-1 border border-gray-300 rounded-md bg-white h-fit">
          <AtomsAppLoading />
        </div>

    </div>
    <div role="region"
      class="fixed h-full border-l border-gray-100 top-0 right-0 transition-all duration-500 ease py-2 text-base bg-white w-[90%] z-20 overflow-hidden"
      :class="{ 'translate-x-0': showRegion, 'translate-x-[2000px]': !showRegion, 'w-[90%]': showRegionComponent === 'BillingSummary', 'w-[75%]': showRegionComponent != 'BillingSummary' }">
      <div id="region_nav" class="mb-3 px-3">
        <button @click="toggleRegion(false)" class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300">
          <Icon name="fa6-solid:angles-right" class="text-slate-500" />
        </button>
      </div>
      <div v-if="showRegionComponent === 'BillingSummary'" class="px-10 flex flex-col h-full">
        <!-- Added h-full here -->
        <H1>{{ t('invoices') }}</H1>
        <div class="flex items-center justify-between gap-3">
          <span class="input-group flex flex-start items-center gap-2 w-80">
            <Icon name="fa6-solid:magnifying-glass" class="text-slate-500" />
            <input v-model="searchInput" @input="handleSearch" id="searchInput" type="text" name="search"
              :placeholder="$t('dashboard.search')"
              class="w-full p-1 rounded-md focus:outline-none focus-visible:border-0" autocomplete="off" />
          </span>
          <button type="button" class="button-secondary shrink-0" :disabled="exportingInvoices"
            @click="exportInvoicesXlsx">
            <Icon :name="exportingInvoices ? 'fa6-solid:spinner' : 'fa6-solid:file-excel'"
              :class="{ 'animate-spin': exportingInvoices }" />
            <span class="ml-1">{{ exportingInvoices ? `${t('common.loading')}...` : `${t('common.download')} XLSX` }}</span>
          </button>
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
          class="grid grid-cols-[48px_minmax(0,1.5fr)_minmax(0,1fr)_minmax(0,1fr)_minmax(0,1fr)_minmax(0,1fr)_minmax(0,1fr)_minmax(0,1fr)_100px_260px] gap-2 px-4 border-b border-gray-400 items-center shrink-0 overflow-y-hidden [scrollbar-gutter:stable]">
          <span></span>
          <span class="p-3 font-bold truncate">{{ t('common.client') }}</span>
          <span class="p-3 font-bold truncate">{{ t('contract') }}</span>
          <span class="p-3 font-bold truncate">{{ t('common.use_type') }}</span>
          <span class="p-3 font-bold truncate">{{ t('billing_block.payment') }}</span>
          <button type="button" @click="sortInvoicesBy('total_final')" class="p-3 font-bold flex items-center gap-2 text-start hover:bg-slate-50 rounded min-w-0">
            <Icon class="shrink-0" :name="sortBy != 'total_final' ? 'fa6-solid:sort' : sortDesc ? 'fa6-solid:sort-up' : 'fa6-solid:sort-down'" />
            <span class="truncate" :title="t('billing_block.total_invoice')">{{ t('billing_block.total_invoice') }}</span>
          </button>
          <button type="button" @click="sortInvoicesBy('left_to_pay')" class="p-3 font-bold flex items-center gap-2 text-start hover:bg-slate-50 rounded min-w-0">
            <Icon class="shrink-0" :name="sortBy != 'left_to_pay' ? 'fa6-solid:sort' : sortDesc ? 'fa6-solid:sort-up' : 'fa6-solid:sort-down'" />
            <span class="truncate" :title="t('billing_block.total_to_pay')">{{ t('billing_block.total_to_pay') }}</span>
          </button>
          <button type="button" @click="sortInvoicesBy('consumption')" class="p-3 font-bold flex items-center gap-2 text-start hover:bg-slate-50 rounded min-w-0">
            <Icon class="shrink-0" :name="sortBy != 'consumption' ? 'fa6-solid:sort' : sortDesc ? 'fa6-solid:sort-up' : 'fa6-solid:sort-down'" />
            <span class="truncate" :title="t('consumption')">{{ t('consumption') }}</span>
          </button>
          <button type="button" @click="sortInvoicesBy('consumption_days')" class="p-3 font-bold flex items-center gap-2 text-start hover:bg-slate-50 rounded min-w-0">
            <Icon class="shrink-0" :name="sortBy != 'consumption_days' ? 'fa6-solid:sort' : sortDesc ? 'fa6-solid:sort-up' : 'fa6-solid:sort-down'" />
            <span class="truncate" :title="t('billing_block.date_range_number_days')">{{ t('billing_block.date_range_number_days') }}</span>
          </button>
          <span class="p-3 font-bold"></span>
        </div>
        <div class="overflow-y-auto [scrollbar-gutter:stable] flex-grow pb-10" @scroll="onScroll">
          <div v-if="loadingInvoices && showInvoices.length === 0" class="py-16 text-center text-slate-500">
            {{ t('common.loading') }}...
          </div>
          <div v-for="(invoice, index) in showInvoices" :key="invoice.id">
            <AtomsInvoiceEdit @show-edit="onShowDetail" @show-history="onShowHistory" @open-region="openRegion"
              :invoice="invoice" :rowIndex="index + 1" :showCheckbox="false"
              :showDetail="showingDetailId == invoice.id"
              :showHistory="showingHistoryId == invoice.id" :finalized="true" :allowEdit="false" />
          </div>
          <div v-if="loadingInvoices && showInvoices.length > 0" class="py-4 text-center text-slate-500">
            {{ t('common.loading') }}...
          </div>
        </div>
      </div>
      <div v-if="showRegionComponent === 'MissingContracts'" class="px-10 flex flex-col h-full">
        <MissingContractsDetail :loading="loadingMissingContracts" :missingContracts="missingContracts"
          :startDate="infoMissingContracts.start_date" :endDate="infoMissingContracts.end_date"
          :type="missingRegionType" :billingId="billing.id" @reload="getInfoMissingContracts(true)" />
      </div>
      <div v-if="showRegionComponent === 'BilledInvoices'" class="px-10 flex flex-col h-full">
        <BilledInvoicesDetail :billingId="props.billing_id" :type="billedInvoicesType" :isFinished="true"
          @reload="loadData" />
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
      </div>
    </div>
  </div>
</template>
