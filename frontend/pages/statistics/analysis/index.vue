<script setup>
import H1 from '~/components/atoms/H1.vue';
import Tabs from '~/components/atoms/Tabs.vue';
import { useToast } from 'vue-toastification';
import { usePermissions } from '~/middleware/permission';
import AppLoading from '~/components/atoms/AppLoading.vue';

const toast = useToast();
const { t } = useI18n();
const { permissions, loading: permissionsLoading } = usePermissions();

const {
  $StatisticsContractsApiService,
  $apiManager,
  $DocumentManagerApiService,
  $GeneralStatisticsApiService,
} = useNuxtApp();

const activeTab = ref('contracts');

const setActiveTab = (tab) => {
  activeTab.value = tab;
};

/** Fila amb tasca Celery activa (badge) */
const celeryRow = ref(null);
const loadingTaskId = ref(null);
const downloadingLabel = ref('');

const postingCsv = ref(false);
const postingInvoice = ref(false);
const postingPriceRates = ref(false);
const postingTermination = ref(false);

// Backend: POST /statistics/contracts/invoice-reading-summary/export/
// s'executa amb un `type_id` fix (sense cap selecció de l'usuari).
const INVOICE_READING_SUMMARY_TYPE_ID = 12;

const resetLoader = () => {
  clearInterval(taskInterval);
  celeryRow.value = null;
  loadingTaskId.value = null;
  downloadingLabel.value = '';
  taskProgress.value = 0;
};

const fallbackDownloadFilename = () => {
  switch (celeryRow.value) {
    case 'contracts_csv':
      return 'contracts.csv';
    case 'invoice_reading_summary':
      return 'contracts_readings.csv';
    case 'contracts_pricerates':
      return 'contracts_pricerates.csv';
    case 'termination_reading_invoice':
      return 'terminations_contracts_readings.csv';
    default:
      return 'export.csv';
  }
};

const startExportContractsCsv = async () => {
  if (!permissions.value?.permissions?.view_contract) {
    toast.error(t('common.no_permissions'));
    return;
  }

  postingCsv.value = true;
  downloadingLabel.value = t('statistics_block.contract_csv_export');

  try {
    const response = await $StatisticsContractsApiService.exportContracts({});

    if (response?.task_id) {
      loadingTaskId.value = response.task_id;
      celeryRow.value = 'contracts_csv';
    } else {
      toast.error(t('common.error_load'));
    }
  } catch (e) {
    /* toast via api-manager */
  } finally {
    postingCsv.value = false;
  }
};

const startExportInvoiceReadingSummary = async () => {
  if (!permissions.value?.permissions?.view_contract) {
    toast.error(t('common.no_permissions'));
    return;
  }

  postingInvoice.value = true;
  downloadingLabel.value = t('statistics_block.invoice_reading_summary_title');

  const payload = {
    name: t('statistics_block.invoice_reading_summary_report_name'),
    type_id: INVOICE_READING_SUMMARY_TYPE_ID,
  };

  try {
    const response =
      await $StatisticsContractsApiService.exportInvoiceReadingSummary(payload);

    if (response?.task_id) {
      loadingTaskId.value = response.task_id;
      celeryRow.value = 'invoice_reading_summary';
    } else {
      toast.error(t('common.error_load'));
    }
  } catch (e) {
    /* toast via api-manager */
  } finally {
    postingInvoice.value = false;
  }
};

const startExportPriceRates = async () => {
  if (!permissions.value?.permissions?.view_contract) {
    toast.error(t('common.no_permissions'));
    return;
  }

  postingPriceRates.value = true;
  downloadingLabel.value = t('statistics_block.pricerates_export_title');

  try {
    const exploitationId = localStorage.getItem('exploitation');
    const payload = {
      status: '2',
      name: t('statistics_block.pricerates_export_report_name'),
    };

    if (exploitationId) {
      payload.exploitation = Number(exploitationId);
    }

    const response = await $StatisticsContractsApiService.exportPriceRates(payload);

    if (response?.task_id) {
      loadingTaskId.value = response.task_id;
      celeryRow.value = 'contracts_pricerates';
    } else {
      toast.error(t('common.error_load'));
    }
  } catch (e) {
    /* toast via api-manager */
  } finally {
    postingPriceRates.value = false;
  }
};

const startExportTerminationReadingInvoice = async () => {
  if (!permissions.value?.permissions?.view_contract) {
    toast.error(t('common.no_permissions'));
    return;
  }

  postingTermination.value = true;
  downloadingLabel.value = t('statistics_block.termination_reading_invoice_title');

  try {
    const payload = {
      name: t('statistics_block.termination_reading_invoice_report_name'),
    };

    const response =
      await $StatisticsContractsApiService.exportTerminationReadingInvoice(payload);

    if (response?.task_id) {
      loadingTaskId.value = response.task_id;
      celeryRow.value = 'termination_reading_invoice';
    } else {
      toast.error(t('common.error_load'));
    }
  } catch (e) {
    /* toast via api-manager */
  } finally {
    postingTermination.value = false;
  }
};

const downloadAfterTask = async () => {
  if (!loadingTaskId.value) {
    return;
  }
  try {
    const response = await $apiManager.checkTask(loadingTaskId.value);
    if (response?.state !== 'SUCCESS') {
      resetLoader();
      return;
    }
    const result = response?.result;
    const documentId = result?.document_id;

    if (documentId) {
      const file = await $DocumentManagerApiService.viewDocument(documentId);
      const link = document.createElement('a');
      const fileUrl = URL.createObjectURL(file);
      link.href = fileUrl;
      link.download = result?.filename || fallbackDownloadFilename();

      link.click();

      setTimeout(() => {
        window.URL.revokeObjectURL(fileUrl);
      }, 250);

      toast.success(t('common.correct_download'));
    }
  } catch (e) {
    console.error(e);
  } finally {
    resetLoader();
  }
};

const summaryConsumption = ref({ grouped: [], totals: null });
const summaryBilling = ref({ grouped: [], totals: null });

const loadingConsumption = ref(false);
const loadingBilling = ref(false);

// Filtre "contractes actius i facturables", activat per defecte a totes dues taules
// (es pot desmarcar per veure el resum sense aquesta restricció).
const consumptionActiveBillableOnly = ref(true);
const billingActiveBillableOnly = ref(true);

const updateDailyLoading = ref(false);
const updateBillingBackfillLoading = ref(false);
const taskProgress = ref(0);
let taskInterval = null;

const startTaskPolling = (taskId, onSuccess) => {
  taskProgress.value = 0;
  clearInterval(taskInterval);
  let pendingPolls = 0;
  const MAX_POLLS = 90;
  taskInterval = setInterval(async () => {
    try {
      const res = await $apiManager.checkTask(taskId);
      if (!res) return;
      taskProgress.value = res.percent || 0;
      if (res.state === 'SUCCESS') {
        clearInterval(taskInterval);
        taskProgress.value = 100;
        onSuccess();
      } else if (res.state === 'FAILURE') {
        clearInterval(taskInterval);
        toast.error(t('common.error_load'));
        resetLoader();
      } else {
        pendingPolls++;
        if (pendingPolls >= MAX_POLLS) {
          clearInterval(taskInterval);
          toast.error(t('common.error_load'));
          resetLoader();
        }
      }
    } catch (e) {
      clearInterval(taskInterval);
      resetLoader();
    }
  }, 2000);
};

onUnmounted(() => clearInterval(taskInterval));

const fetchConsumptionSummary = async () => {
  loadingConsumption.value = true;
  try {
    const params = consumptionActiveBillableOnly.value ? { active: true, is_billable: true } : {};
    const consumption = await $GeneralStatisticsApiService.getSummaryConsumptionByUse(params);
    summaryConsumption.value = consumption || { grouped: [], totals: null };
  } catch (e) {
    console.error('Error fetching consumption summary:', e);
  } finally {
    loadingConsumption.value = false;
  }
};

const fetchBillingSummary = async () => {
  loadingBilling.value = true;
  try {
    const params = billingActiveBillableOnly.value ? { active: true, is_billable: true } : {};
    const billing = await $GeneralStatisticsApiService.getSummaryBillingByUse(params);
    summaryBilling.value = billing || { grouped: [], totals: null };
  } catch (e) {
    console.error('Error fetching billing summary:', e);
  } finally {
    loadingBilling.value = false;
  }
};

const fetchSummaries = async () => {
  await Promise.allSettled([
    fetchConsumptionSummary(),
    fetchBillingSummary(),
  ]);
};

const runUpdateDailyConsumption = async () => {
  updateDailyLoading.value = true;
  try {
    const response = await $GeneralStatisticsApiService.updateDailyConsumption();
    if (response?.task_id) {
      loadingTaskId.value = response.task_id;
      celeryRow.value = 'update_daily';
      downloadingLabel.value = t('statistics_block.update_daily_consumption_title');
      toast.success(t('statistics_block.process_started'));
      startTaskPolling(response.task_id, handleTaskSuccess);
    }
  } catch (e) {
    /* toast via api-manager */
  } finally {
    updateDailyLoading.value = false;
  }
};

const runUpdateBillingBackfill = async () => {
  updateBillingBackfillLoading.value = true;
  try {
    const response = await $GeneralStatisticsApiService.updateBillingBackfill();
    if (response?.task_id) {
      loadingTaskId.value = response.task_id;
      celeryRow.value = 'update_billing_backfill';
      downloadingLabel.value = t('statistics_block.update_billing_backfill_title');
      toast.success(t('statistics_block.process_started'));
      startTaskPolling(response.task_id, handleTaskSuccess);
    }
  } catch (e) {
    /* toast via api-manager */
  } finally {
    updateBillingBackfillLoading.value = false;
  }
};

const formatNumber = (num) => {
  if (num == null) return '0,00';
  return Number(num).toLocaleString('ca-ES', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
};

const handleTaskSuccess = async () => {
  if (!loadingTaskId.value) return;

  if (celeryRow.value === 'update_daily' || celeryRow.value === 'update_billing_backfill') {
    toast.success(t('common.correct_finish'));
    resetLoader();
    // Refresquem els resums per si han canviat
    fetchSummaries();
  } else {
    // Casos d'exportació (CSV)
    await downloadAfterTask();
  }
};

watch(activeTab, (newTab) => {
  if (newTab === 'consumption' && summaryConsumption.value.grouped.length === 0) {
    fetchSummaries();
  }
}, { immediate: true });

const initPage = async () => {
  if (!permissions.value?.permissions?.view_contract) {
    toast.error(t('common.no_permissions'));
    await navigateTo('/');
    return;
  }
};

watch(
  permissionsLoading,
  async (loading) => {
    if (loading) {
      return;
    }
    await initPage();
  },
  { immediate: true }
);
</script>

<template>
  <div id="wrapper" class="text-base">
    <H1 class="mb-4">{{ t('statistics_block.analysis_title') }}</H1>

    <Tabs>
      <li class="me-2">
        <a
          href="#tab_contracts"
          @click.prevent="setActiveTab('contracts')"
          :class="{
            'text-sky-600 border-sky-600': activeTab === 'contracts',
            'hover:text-gray-600 hover:border-gray-300': activeTab !== 'contracts',
          }"
        >
          <Icon name="fa6-solid:file-contract" class="display-inline mr-2" />
          {{ t('statistics_block.tab_contracts') }}
        </a>
      </li>
      <li class="me-2">
        <a
          href="#tab_consumption"
          @click.prevent="setActiveTab('consumption')"
          :class="{
            'text-sky-600 border-sky-600': activeTab === 'consumption',
            'hover:text-gray-600 hover:border-gray-300': activeTab !== 'consumption',
          }"
        >
          <Icon name="fa6-solid:droplet" class="display-inline mr-2" />
          {{ t('statistics_block.tab_consumption') }}
        </a>
      </li>
      <li class="me-2">
        <a
          href="#tab_terminations"
          @click.prevent="setActiveTab('terminations')"
          :class="{
            'text-sky-600 border-sky-600': activeTab === 'terminations',
            'hover:text-gray-600 hover:border-gray-300': activeTab !== 'terminations',
          }"
        >
          <Icon name="fa6-solid:file-circle-xmark" class="display-inline mr-2" />
          {{ t('statistics_block.tab_terminations') }}
        </a>
      </li>
    </Tabs>

    <div class="mt-4 mb-10">
      <section
        v-show="activeTab === 'contracts'"
        role="tabpanel"
        id="tab_contracts"
        class="bg-white antialiased max-w-4xl"
      >
        <ul class="divide-y divide-slate-200 px-2 border border-slate-200 rounded-md">
          <li>
            <div class="my-2 px-2 flex flex-col gap-2 sm:flex-row sm:justify-between sm:items-center">
              <div class="min-w-0">
                <span class="font-medium text-slate-800">{{ t('statistics_block.contract_csv_export') }}</span>
                <p class="text-sm text-slate-600 mt-1">
                  {{ t('statistics_block.contract_csv_help') }}
                </p>
              </div>
              <div class="flex shrink-0 items-center gap-3">
                <button
                  v-if="celeryRow !== 'contracts_csv'"
                  type="button"
                  class="button-secondary"
                  :disabled="!!loadingTaskId || postingCsv"
                  @click="startExportContractsCsv"
                >
                  <Icon v-if="postingCsv" name="fa6-solid:spinner" class="mr-2 animate-spin" />
                  <Icon v-else name="fa6-solid:file-csv" class="mr-2" />
                  {{ t('common.download') }}
                </button>
                <AtomsProcessColorBadge
                  v-else
                  class="w-fit py-3"
                  :value="`${t('common.loading')} ${downloadingLabel.toLowerCase()}`"
                  color="green"
                  :task-id="loadingTaskId"
                  @refresh="handleTaskSuccess"
                />
              </div>
            </div>
          </li>

          <li>
            <div class="my-2 px-2 flex flex-col gap-3 sm:flex-row sm:justify-between sm:items-start">
              <div class="min-w-0 flex-1">
                <span class="font-medium text-slate-800">{{
                  t('statistics_block.invoice_reading_summary_title')
                }}</span>
                <p class="text-sm text-slate-600 mt-1">
                  {{ t('statistics_block.invoice_reading_summary_help') }}
                </p>
              </div>
              <div class="flex shrink-0 items-center gap-3 sm:pt-1">
                <button
                  v-if="celeryRow !== 'invoice_reading_summary'"
                  type="button"
                  class="button-secondary"
                  :disabled="!!loadingTaskId || postingInvoice"
                  @click="startExportInvoiceReadingSummary"
                >
                  <Icon v-if="postingInvoice" name="fa6-solid:spinner" class="mr-2 animate-spin" />
                  <Icon v-else name="fa6-solid:file-excel" class="mr-2" />
                  {{ t('common.download') }}
                </button>
                <AtomsProcessColorBadge
                  v-else
                  class="w-fit py-3"
                  :value="`${t('common.loading')} ${downloadingLabel.toLowerCase()}`"
                  color="green"
                  :task-id="loadingTaskId"
                  @refresh="handleTaskSuccess"
                />
              </div>
            </div>
          </li>

          <li>
            <div class="my-2 px-2 flex flex-col gap-3 sm:flex-row sm:justify-between sm:items-start">
              <div class="min-w-0 flex-1">
                <span class="font-medium text-slate-800">{{
                  t('statistics_block.pricerates_export_title')
                }}</span>
                <p class="text-sm text-slate-600 mt-1">
                  {{ t('statistics_block.pricerates_export_help') }}
                </p>
              </div>
              <div class="flex shrink-0 items-center gap-3 sm:pt-1">
                <button
                  v-if="celeryRow !== 'contracts_pricerates'"
                  type="button"
                  class="button-secondary"
                  :disabled="!!loadingTaskId || postingPriceRates"
                  @click="startExportPriceRates"
                >
                  <Icon v-if="postingPriceRates" name="fa6-solid:spinner" class="mr-2 animate-spin" />
                  <Icon v-else name="fa6-solid:file-excel" class="mr-2" />
                  {{ t('common.download') }}
                </button>
                <AtomsProcessColorBadge
                  v-else
                  class="w-fit py-3"
                  :value="`${t('common.loading')} ${downloadingLabel.toLowerCase()}`"
                  color="green"
                  :task-id="loadingTaskId"
                  @refresh="handleTaskSuccess"
                />
              </div>
            </div>
          </li>
        </ul>
      </section>
      <section
        v-show="activeTab === 'consumption'"
        role="tabpanel"
        id="tab_consumption"
        class="bg-white antialiased max-w-7xl"
      >
        <div class="grid grid-cols-1 gap-6">
          <div class="bg-white border border-slate-200 rounded-md p-4">
            <div class="flex justify-between items-center mb-4">
              <h2 class="text-lg font-semibold text-slate-800">{{ t('common.actions') }}</h2>
            </div>
            <ul class="divide-y divide-slate-200">
              <li class="py-4">
                <div class="flex flex-col gap-2 sm:flex-row sm:justify-between sm:items-center">
                  <div class="min-w-0">
                    <span class="font-medium text-slate-800">{{ t('statistics_block.update_daily_consumption_title') }}</span>
                    <p class="text-sm text-slate-600 mt-1">
                      {{ t('statistics_block.update_daily_consumption_help') }}
                    </p>
                  </div>
                  <div class="shrink-0 mt-2 sm:mt-0">
                    <button
                      type="button"
                      class="relative overflow-hidden min-w-[160px] button-primary"
                      :disabled="!!loadingTaskId || updateDailyLoading"
                      @click="runUpdateDailyConsumption"
                    >
                      <span
                        v-if="celeryRow === 'update_daily'"
                        class="absolute inset-y-0 left-0 bg-white/20 transition-all duration-500 ease-out"
                        :style="{ width: taskProgress + '%' }"
                      />
                      <span class="relative flex items-center justify-center gap-2">
                        <Icon v-if="updateDailyLoading || celeryRow === 'update_daily'" name="fa6-solid:spinner" class="animate-spin" />
                        <Icon v-else name="fa6-solid:rotate" />
                        <span v-if="celeryRow === 'update_daily'">{{ taskProgress }}%</span>
                        <span v-else>{{ t('common.recalculate') }}</span>
                      </span>
                    </button>
                  </div>
                </div>
              </li>
              <li class="py-4">
                <div class="flex flex-col gap-2 sm:flex-row sm:justify-between sm:items-center">
                  <div class="min-w-0">
                    <span class="font-medium text-slate-800">{{ t('statistics_block.update_billing_backfill_title') }}</span>
                    <p class="text-sm text-slate-600 mt-1">
                      {{ t('statistics_block.update_billing_backfill_help') }}
                    </p>
                  </div>
                  <div class="shrink-0 mt-2 sm:mt-0">
                    <button
                      type="button"
                      class="relative overflow-hidden min-w-[160px] button-primary"
                      :disabled="!!loadingTaskId || updateBillingBackfillLoading"
                      @click="runUpdateBillingBackfill"
                    >
                      <span
                        v-if="celeryRow === 'update_billing_backfill'"
                        class="absolute inset-y-0 left-0 bg-white/20 transition-all duration-500 ease-out"
                        :style="{ width: taskProgress + '%' }"
                      />
                      <span class="relative flex items-center justify-center gap-2">
                        <Icon v-if="updateBillingBackfillLoading || celeryRow === 'update_billing_backfill'" name="fa6-solid:spinner" class="animate-spin" />
                        <Icon v-else name="fa6-solid:rotate" />
                        <span v-if="celeryRow === 'update_billing_backfill'">{{ taskProgress }}%</span>
                        <span v-else>{{ t('common.recalculate') }}</span>
                      </span>
                    </button>
                  </div>
                </div>
              </li>
            </ul>
          </div>

          <div class="bg-white border border-slate-200 rounded-md p-4 overflow-hidden">
            <div class="flex justify-between items-center mb-4 gap-3">
              <h2 class="text-lg font-semibold text-slate-800">{{ t('statistics_block.summary_consumption_by_use_title') }}</h2>
              <div class="flex items-center gap-3 shrink-0">
                <label class="flex items-center gap-2 text-sm text-slate-600">
                  <input type="checkbox" v-model="consumptionActiveBillableOnly" @change="fetchConsumptionSummary" class="checkbox" />
                  {{ t('statistics_block.filter_active_billable_contracts') }}
                </label>
                <button
                  type="button"
                  class="button-secondary"
                  :disabled="loadingConsumption"
                  @click="fetchConsumptionSummary"
                >
                  <Icon v-if="loadingConsumption" name="fa6-solid:spinner" class="mr-2 animate-spin" />
                  <Icon v-else name="fa6-solid:rotate-right" class="mr-2" />
                  {{ t('common.update') }}
                </button>
              </div>
            </div>
            <div v-if="loadingConsumption" class="flex justify-center py-8">
              <AppLoading />
            </div>
            <div v-else class="overflow-x-auto">
              <table class="min-w-full divide-y divide-slate-200">
                <thead class="bg-slate-50">
                  <tr>
                    <th scope="col" class="px-3 py-3 text-left text-xs font-semibold text-slate-600 uppercase tracking-wider">{{ t('pricing_block.adj_use_type') }}</th>
                    <th scope="col" class="px-3 py-3 text-right text-xs font-semibold text-slate-600 uppercase tracking-wider">{{ t('statistics_block.total_contracts') }}</th>
                    <th scope="col" class="px-3 py-3 text-right text-xs font-semibold text-slate-600 uppercase tracking-wider">{{ t('statistics_block.avg_daily_consumption_per_contract') }} (m³)</th>
                    <th scope="col" class="px-3 py-3 text-right text-xs font-semibold text-slate-600 uppercase tracking-wider">{{ t('statistics_block.total_daily_consumption') }} (m³)</th>
                    <th scope="col" class="px-3 py-3 text-right text-xs font-semibold text-slate-600 uppercase tracking-wider">{{ t('statistics_block.total_period_consumption') }} (m³)</th>
                  </tr>
                </thead>
                <tbody class="bg-white divide-y divide-slate-200">
                  <tr v-for="item in summaryConsumption.grouped" :key="item.id">
                    <td class="px-3 py-4 whitespace-nowrap text-sm font-medium text-slate-900">{{ item.name }}</td>
                    <td class="px-3 py-4 whitespace-nowrap text-sm text-slate-600 text-right">{{ item.total_contracts }}</td>
                    <td class="px-3 py-4 whitespace-nowrap text-sm text-slate-600 text-right">{{ formatNumber(item.avg_daily_per_contract) }}</td>
                    <td class="px-3 py-4 whitespace-nowrap text-sm text-slate-600 text-right">{{ formatNumber(item.total_daily_consumption) }}</td>
                    <td class="px-3 py-4 whitespace-nowrap text-sm text-slate-600 text-right">{{ formatNumber(item.total_period_consumption) }}</td>
                  </tr>
                  <!-- Total row -->
                  <tr v-if="summaryConsumption.totals" class="bg-slate-50 border-t-2 border-slate-200">
                    <td class="px-3 py-4 whitespace-nowrap text-sm font-bold text-slate-900">{{ t('common.total') }}</td>
                    <td class="px-3 py-4 whitespace-nowrap text-sm font-bold text-slate-900 text-right">{{ summaryConsumption.totals.total_contracts }}</td>
                    <td class="px-3 py-4 whitespace-nowrap text-sm font-bold text-slate-900 text-right">{{ formatNumber(summaryConsumption.totals.avg_daily_per_contract) }}</td>
                    <td class="px-3 py-4 whitespace-nowrap text-sm font-bold text-slate-900 text-right">{{ formatNumber(summaryConsumption.totals.total_daily_consumption) }}</td>
                    <td class="px-3 py-4 whitespace-nowrap text-sm font-bold text-slate-900 text-right">{{ formatNumber(summaryConsumption.totals.total_period_consumption) }}</td>
                  </tr>
                  <tr v-show="summaryConsumption.grouped.length === 0">
                    <td colspan="5" class="px-3 py-8 text-center text-sm text-slate-500">{{ t('common.no_results') }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>

          <div class="bg-white border border-slate-200 rounded-md p-4 overflow-hidden">
            <div class="flex justify-between items-center mb-4 gap-3">
              <h2 class="text-lg font-semibold text-slate-800">{{ t('statistics_block.summary_billing_by_use_title') }}</h2>
              <div class="flex items-center gap-3 shrink-0">
                <label class="flex items-center gap-2 text-sm text-slate-600">
                  <input type="checkbox" v-model="billingActiveBillableOnly" @change="fetchBillingSummary" class="checkbox" />
                  {{ t('statistics_block.filter_active_billable_contracts') }}
                </label>
                <button
                  type="button"
                  class="button-secondary"
                  :disabled="loadingBilling"
                  @click="fetchBillingSummary"
                >
                  <Icon v-if="loadingBilling" name="fa6-solid:spinner" class="mr-2 animate-spin" />
                  <Icon v-else name="fa6-solid:rotate-right" class="mr-2" />
                  {{ t('common.update') }}
                </button>
              </div>
            </div>
            <div v-if="loadingBilling" class="flex justify-center py-8">
              <AppLoading />
            </div>
            <div v-else class="overflow-x-auto">
              <table class="min-w-full divide-y divide-slate-200">
                <thead class="bg-slate-50">
                  <tr>
                    <th scope="col" class="px-3 py-3 text-left text-xs font-semibold text-slate-600 uppercase tracking-wider">{{ t('pricing_block.adj_use_type') }}</th>
                    <th scope="col" class="px-3 py-3 text-right text-xs font-semibold text-slate-600 uppercase tracking-wider">{{ t('statistics_block.total_bills') }}</th>
                    <th scope="col" class="px-3 py-3 text-right text-xs font-semibold text-slate-600 uppercase tracking-wider">{{ t('statistics_block.total_billed_amount') }} (€)</th>
                    <th scope="col" class="px-3 py-3 text-right text-xs font-semibold text-slate-600 uppercase tracking-wider">{{ t('statistics_block.avg_amount_per_bill') }} (€)</th>
                    <th scope="col" class="px-3 py-3 text-right text-xs font-semibold text-slate-600 uppercase tracking-wider">{{ t('statistics_block.total_billed_consumption') }} (m³)</th>
                    <th scope="col" class="px-3 py-3 text-right text-xs font-semibold text-slate-600 uppercase tracking-wider">{{ t('statistics_block.avg_billed_daily_consumption') }} (m³)</th>
                  </tr>
                </thead>
                <tbody class="bg-white divide-y divide-slate-200">
                  <tr v-for="item in summaryBilling.grouped" :key="item.id">
                    <td class="px-3 py-4 whitespace-nowrap text-sm font-medium text-slate-900">{{ item.name }}</td>
                    <td class="px-3 py-4 whitespace-nowrap text-sm text-slate-600 text-right">{{ item.total_invoices }}</td>
                    <td class="px-3 py-4 whitespace-nowrap text-sm text-slate-600 text-right">{{ formatNumber(item.total_amount) }}</td>
                    <td class="px-3 py-4 whitespace-nowrap text-sm text-slate-600 text-right">{{ formatNumber(item.avg_amount_per_invoice) }}</td>
                    <td class="px-3 py-4 whitespace-nowrap text-sm text-slate-600 text-right">{{ formatNumber(item.total_consumption_invoiced) }}</td>
                    <td class="px-3 py-4 whitespace-nowrap text-sm text-slate-600 text-right">{{ formatNumber(item.avg_daily_consumption_invoiced) }}</td>
                  </tr>
                  <!-- Total row -->
                  <tr v-if="summaryBilling.totals" class="bg-slate-50 border-t-2 border-slate-200">
                    <td class="px-3 py-4 whitespace-nowrap text-sm font-bold text-slate-900">{{ t('common.total') }}</td>
                    <td class="px-3 py-4 whitespace-nowrap text-sm font-bold text-slate-900 text-right">{{ summaryBilling.totals.total_invoices }}</td>
                    <td class="px-3 py-4 whitespace-nowrap text-sm font-bold text-slate-900 text-right">{{ formatNumber(summaryBilling.totals.total_amount) }}</td>
                    <td class="px-3 py-4 whitespace-nowrap text-sm font-bold text-slate-900 text-right">{{ formatNumber(summaryBilling.totals.avg_amount_per_invoice) }}</td>
                    <td class="px-3 py-4 whitespace-nowrap text-sm font-bold text-slate-900 text-right">{{ formatNumber(summaryBilling.totals.total_consumption_invoiced) }}</td>
                    <td class="px-3 py-4 whitespace-nowrap text-sm font-bold text-slate-900 text-right">{{ formatNumber(summaryBilling.totals.avg_daily_consumption_invoiced) }}</td>
                  </tr>
                  <tr v-show="summaryBilling.grouped.length === 0">
                    <td colspan="6" class="px-3 py-8 text-center text-sm text-slate-500">{{ t('common.no_results') }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </section>

      <section
        v-show="activeTab === 'terminations'"
        role="tabpanel"
        id="tab_terminations"
        class="bg-white antialiased max-w-4xl"
      >
        <ul class="divide-y divide-slate-200 px-2 border border-slate-200 rounded-md">
          <li>
            <div class="my-2 px-2 flex flex-col gap-3 sm:flex-row sm:justify-between sm:items-start">
              <div class="min-w-0 flex-1">
                <span class="font-medium text-slate-800">{{
                  t('statistics_block.termination_reading_invoice_title')
                }}</span>
                <p class="text-sm text-slate-600 mt-1">
                  {{ t('statistics_block.termination_reading_invoice_help') }}
                </p>
              </div>
              <div class="flex shrink-0 items-center gap-3 sm:pt-1">
                <button
                  v-if="celeryRow !== 'termination_reading_invoice'"
                  type="button"
                  class="button-secondary"
                  :disabled="!!loadingTaskId || postingTermination"
                  @click="startExportTerminationReadingInvoice"
                >
                  <Icon v-if="postingTermination" name="fa6-solid:spinner" class="mr-2 animate-spin" />
                  <Icon v-else name="fa6-solid:file-excel" class="mr-2" />
                  {{ t('common.download') }}
                </button>
                <AtomsProcessColorBadge
                  v-else
                  class="w-fit py-3"
                  :value="`${t('common.loading')} ${downloadingLabel.toLowerCase()}`"
                  color="green"
                  :task-id="loadingTaskId"
                  @refresh="handleTaskSuccess"
                />
              </div>
            </div>
          </li>
        </ul>
      </section>
    </div>
  </div>
</template>
