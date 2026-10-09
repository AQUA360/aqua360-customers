<script setup>
import { ref, onMounted, computed } from 'vue';
import { useToast } from 'vue-toastification';
import ReadingBatchCreate from '~/components/molecules/ReadingBatchCreate.vue';
import ReadingBatchSetup from '~/components/molecules/ReadingBatchSetup.vue';
import ReadingBatchSummary from '~/components/molecules/ReadingBatchSummary.vue';
import ReadingBatchReadingsSummary from '~/components/molecules/ReadingBatchReadingsSummary.vue';
import ReadingBatchRouteDownload from '~/components/molecules/ReadingBatchRouteDownload.vue';
import ReaderAlertRegion from '~/components/molecules/ReaderAlertRegion.vue';
import SmartMeteringReadingsDialog from '~/components/molecules/SmartMeteringReadingsDialog.vue';
import EstimateReadingsDialog from '~/components/molecules/EstimateReadingsDialog.vue';
import WizardStatusNav from '../molecules/WizardStatusNav.vue';
import StatusesNav from '~/components/atoms/StatusesNav.vue';

const { t } = useI18n()
const route = useRoute()
const router = useRouter()

const { $ConfiglistApiService, $ConfigProjectApiService, $ReadingBatchApiService, $SmartMeteringApiService, $apiManager } = useNuxtApp();
const toast = useToast();

const props = defineProps({
  id: Number,
  counters: Object,
  counters_pending: Object,
  activeStatus: Object,
  num_supplies: Number,
  num_contracts: Number,
  num_no_meters: Number,
  no_route_supply_points_count: Number,
  missing_billing_data: Object,
  allow_force_manual: false
});

const emit = defineEmits(['refresh']);

const steps = ref(['1', '2', '3', '4']);
const currentStep = ref(0);
const maxStep = ref(0);

const wizardSteps = computed(() => [
  {
    index: 0,
    number: '1',
    label: t('billing_block.step') + ' 1',
    title: t('billing_block.step_creation') || 'Creació',
    description: t('billing_block.step_creation_desc') || 'Crear Lot de Lectures',
    icon: 'fa6-solid:circle-plus'
  },
  {
    index: 1,
    number: '2',
    label: t('billing_block.step') + ' 2',
    title: t('billing_block.step_setup') || 'Configuració',
    description: t('billing_block.step_setup_desc') || 'Assignació de Rutes',
    icon: 'fa6-solid:gears'
  },
  {
    index: 2,
    number: '3',
    label: t('billing_block.step') + ' 3',
    title: t('billing_block.step_readings') || 'Lectures',
    description: t('billing_block.step_readings_desc') || 'Gestió de Lectures',
    icon: 'fa6-solid:gauge-high'
  },
  {
    index: 3,
    number: '4',
    label: t('billing_block.step') + ' 4',
    title: t('billing_block.step_finalize') || 'Resum',
    description: t('billing_block.step_finalize_desc') || 'Validació i Tancament',
    icon: 'fa6-solid:circle-check'
  }
]);

const loading = ref(true);
const nextStepLoading = ref(false);

const nextStepAllowed = ref(false);

const editingChangeStatus = ref(false);
const showRegion = ref(false);
const toggleRegion = (force) => {
  showRegion.value = force !== undefined ? force : !showRegion.value;
}

const showReaderAlertRegion = ref(false);
const closeAlertDetail = () => {
  toggleRegion(false);
  showReaderAlertRegion.value = false;
}
const onSetupShowSubregion = (payload) => {
  if (payload?.type === 'reader-alerts') {
    showReaderAlertRegion.value = true;
    toggleRegion(true);
  }
}

const setupData = ref(null);
const creationData = ref(null);
const defaultReadingDate = ref(null);
const smartMeteringMode = ref(false);
const smartMeteringPreview = ref(null);
const smartMeteringDate = ref(null);
const smartMeteringAssigned = ref(false);
const showSmartMeteringDialog = ref(false);
const smartMeteringSaving = ref(false);
const smartMeteringPreviewLoading = ref(false);
const smartMeteringPreviewTaskId = ref(null);

const counters = ref(null);
const countersSetup = ref(null);
const taskId = ref(null);
const assignReadingsTaskId = ref(null);
const estimateReadingsTaskId = ref(null);
const partialTaskErrors = ref([]);

const batch_id = ref(null);

const readingBatchStatuses = ref([]);
const readingBatchStatus = ref(null);

const pendingStatusToken = ref(null);
const pendingProcessingStatusToken = ref(null);
const processingStatusToken = ref(null);

let itvl = null;

const isAssigningReadings = computed(() => !!assignReadingsTaskId.value);
const isSmartMeteringBusy = computed(
  () => smartMeteringPreviewLoading.value || smartMeteringSaving.value || !!smartMeteringPreviewTaskId.value
);

/** Only blocks advancing from setup if there is truly nothing to read (all counters at 0 except pending ones). */
const hasSetupReadings = computed(() => {
  const counters = countersSetup.value || {};
  return Object.entries(counters).some(([key, value]) => key !== 'missing_readings' && Number(value) > 0);
});

const showEstimateAllDialog = ref(false);
const estimatingAllReadings = ref(false);

const loadingCreationData = ref(false);

/** Step 1 (setup) -> step 0 (creation): purely local, batch is still in its initial status. */
const backToCreation = async () => {
  if (currentStep.value !== 1) return;
  if (props.id) {
    loadingCreationData.value = true;
    try {
      creationData.value = await $ReadingBatchApiService.getDetail(props.id);
    } catch (error) {
      console.error(error);
      toast.error(error?.data?.error || error?.message || t('common.error'));
    } finally {
      loadingCreationData.value = false;
    }
  }
  currentStep.value = 0;
  setUrlStep();
};

const loadData = async () => {
  if (props.activeStatus) {
    readingBatchStatus.value = props.activeStatus;
    currentStep.value = 1;
    maxStep.value = 1;

    pendingProcessingStatusToken.value = await $ConfigProjectApiService.get('reading_batch_pending_processing_token');
    processingStatusToken.value = await $ConfigProjectApiService.get('reading_batch_processing_token');
    pendingStatusToken.value = await $ConfigProjectApiService.get('reading_batch_pending_token');

    countersSetup.value = props.counters_pending;
    if (props.no_route_supply_points_count !== undefined && countersSetup.value) {
      countersSetup.value.no_route_supply_points_count = props.no_route_supply_points_count;
    }

    if (readingBatchStatus.value.token == pendingProcessingStatusToken.value) {
      await refresh();
      currentStep.value = 2;
      maxStep.value = 2;
    }
    else if (readingBatchStatus.value.token == pendingStatusToken.value) {
      await refresh();

      currentStep.value = 1;
      maxStep.value = 1;
    }
    else if (props.counters && props.counters['total'] > 0 && readingBatchStatus.value.token != pendingStatusToken.value) {
      await refresh();
      counters.value = props.counters;
      currentStep.value = 3;
      maxStep.value = 3;
    }
  }
}

const clickFinalize = async () => {
  try {
    if (confirm(t("confirmation_text_block.confirm_validate_readings_batch"))) {
      try {
        const token = await $ConfigProjectApiService.get('batch_status_finish_token');
        // console.log(token)

        const data = {
          id: batch_id.value,
          status_token: token
        }
        const res = await $ReadingBatchApiService.update(data);
        await navigateTo(`/reading/reading-batches`)
      }
      catch (error) {
        console.log(error)
      }
    }
  }
  catch (error) {
    console.error(error);
  }
}

const onCreationDataChanged = (data) => {
  creationData.value = data;
}
const onSetupChanged = (data) => {
  setupData.value = data;
  if (data.reading_date) {
    defaultReadingDate.value = data.reading_date;
  }
}

const refresh = async () => {
  const data = await $ReadingBatchApiService.getSummary(props.id)
  console.log('data refresh', data)
  readingBatchStatus.value = data.status;
  countersSetup.value = data.counters_pending;
  if (data.no_route_supply_points_count !== undefined && countersSetup.value) {
    countersSetup.value.no_route_supply_points_count = data.no_route_supply_points_count;
  }
  taskId.value = data.task_id;
  assignReadingsTaskId.value = data.assign_readings_task_id;
  estimateReadingsTaskId.value = data.estimating_task_id;
  if (data.last_task_status === 'partial' && Array.isArray(data.last_task_errors)) {
    partialTaskErrors.value = data.last_task_errors;
  }
}

const waitForAssignTask = (taskId) => {
  partialTaskErrors.value = [];
  return new Promise((resolve, reject) => {
    const poll = async () => {
      try {
        const res = await $apiManager.checkTask(taskId);
        if (!res) {
          reject(new Error(t('common.error')));
          return;
        }
        if (res.state === 'SUCCESS') {
          if (res.result?.status === 'partial' && Array.isArray(res.result?.errors)) {
            partialTaskErrors.value = res.result.errors;
            toast.warning(t('billing_block.partial_processing_errors_title', { count: res.result.errors.length }));
          }
          resolve(res.result);
          return;
        }
        if (res.state === 'FAILURE') {
          reject(new Error(res.error || t('common.error')));
          return;
        }
        setTimeout(poll, 2000);
      } catch (error) {
        reject(error);
      }
    };
    poll();
  });
};

/** assign-readings must run when setup still has a source besides smart metering. */
const needsAssignReadingsFromSetup = (setup) => {
  if (!setup) return false;
  const hasReadingFiles = Array.isArray(setup.reading_files) && setup.reading_files.length > 0;
  const notBilled = setup.not_billed === true;
  const byDate = Boolean(setup.reading_date);
  return hasReadingFiles || notBilled || byDate;
};

const openSmartMeteringDialog = async (readingDate) => {
  const date = readingDate || setupData.value?.reading_date;
  if (!date) {
    toast.error(t('billing_block.reading_date'));
    return false;
  }

  smartMeteringPreviewLoading.value = true;
  try {
    smartMeteringMode.value = true;
    smartMeteringDate.value = date;
    smartMeteringAssigned.value = false;
    const response = await $SmartMeteringApiService.previewBatchReadings(props.id, {
      reading_date: date,
    });

    // Legacy sync payload (before Celery preview).
    if (response?.readings) {
      smartMeteringPreview.value = response;
      showSmartMeteringDialog.value = true;
      smartMeteringPreviewLoading.value = false;
      return true;
    }

    if (!response?.task_id) {
      throw new Error(t('common.error'));
    }

    // Progress bar via ProcessColorBadge; dialog opens on @refresh.
    smartMeteringPreviewTaskId.value = response.task_id;
    smartMeteringPreviewLoading.value = false;
    return true;
  } catch (error) {
    console.error(error);
    toast.error(error?.data?.error || error?.message || t('common.error'));
    smartMeteringPreviewLoading.value = false;
    return false;
  }
};

const onSmartMeteringPreviewTaskRefresh = async () => {
  const previewTaskId = smartMeteringPreviewTaskId.value;
  smartMeteringPreviewTaskId.value = null;
  if (!previewTaskId) {
    smartMeteringPreviewLoading.value = false;
    return;
  }

  try {
    const res = await $apiManager.checkTask(previewTaskId);
    if (res?.state === 'SUCCESS' && res.result) {
      smartMeteringPreview.value = res.result;
      showSmartMeteringDialog.value = true;
    } else if (res?.state === 'FAILURE') {
      toast.error(res.error || t('common.error'));
    }
  } catch (error) {
    console.error(error);
    toast.error(error?.data?.error || error?.message || t('common.error'));
  } finally {
    smartMeteringPreviewLoading.value = false;
  }
};

const onOpenSmartMetering = async ({ reading_date }) => {
  defaultReadingDate.value = reading_date;
  await openSmartMeteringDialog(reading_date);
};

const handleSmartMeteringClose = () => {
  if (smartMeteringSaving.value) return;
  showSmartMeteringDialog.value = false;
};

const handleSmartMeteringSave = async () => {
  smartMeteringSaving.value = true;
  try {
    const results = await $SmartMeteringApiService.assignBatchReadings(props.id, {
      reading_date: smartMeteringDate.value,
      preview: smartMeteringPreview.value,
    });
    if (!results?.task_id) {
      throw new Error(t('common.error'));
    }

    showSmartMeteringDialog.value = false;

    // Poll locally: do not set assignReadingsTaskId or ProcessColorBadge will
    // also advance the wizard via fullRefresh() on SUCCESS (double step jump).
    const counters = await waitForAssignTask(results.task_id);
    countersSetup.value = counters;
    smartMeteringAssigned.value = true;
    await refresh();
    toast.success(t('common.correct_save'));
  } catch (error) {
    console.error(error);
    assignReadingsTaskId.value = null;
    toast.error(error?.data?.error || error?.message || t('common.error'));
  } finally {
    smartMeteringSaving.value = false;
  }
};

const openEstimateAllDialog = () => {
  showEstimateAllDialog.value = true;
};

const handleEstimateAllClose = () => {
  if (estimatingAllReadings.value) return;
  showEstimateAllDialog.value = false;
};

const handleEstimateAllConfirm = async (params) => {
  estimatingAllReadings.value = true;
  try {
    const payload = { supply_points: 'all', ...params };
    const response = await $ReadingBatchApiService.estimateReadings(props.id, payload);
    if (response?.task_id) {
      await waitForAssignTask(response.task_id);
    }
    await refresh();
    showEstimateAllDialog.value = false;
    toast.success(t('billing_block.correct_estimates'));
  } catch (error) {
    console.error(error);
    toast.error(error?.data?.error || error?.message || t('common.error'));
  } finally {
    estimatingAllReadings.value = false;
  }
};

const nextStep = async (doSave = true) => {
  nextStepLoading.value = true;

  try {
    if (doSave) {
      // console.log('nextStep', currentStep.value);
      if (currentStep.value == 0) {
        if (!confirm(t('confirmation_text_block.confirm_generate_reading_batch'))) {
          return;
        }
      }
      if (currentStep.value == 1) {
        const originType = setupData.value?.origin_type;
        if (!originType) {
          toast.error(t('reading_block.no_readings_detected_warning') || t('common.error'));
          return;
        }
        // Només l'origen "Lecturapp" (APP) depèn de tenir lectures assignades; la resta d'orígens
        // (fitxer, data, no facturat, facturació pendent) sempre poden avançar un cop seleccionats.
        if (originType === 'APP' && !hasSetupReadings.value && !setupData.value?.reading_date) {
          toast.error(t('reading_block.no_readings_detected_warning') || t('common.error'));
          return;
        }
        if (countersSetup.value?.['assigned_readings'] > 0 && !smartMeteringAssigned.value) {
          if (!confirm(t('confirmation_text_block.confirm_assign_reading_batch'))) {
            return;
          }
        }
      }
      if (currentStep.value == 2) {
        if (!confirm(t('confirmation_text_block.confirm_process_readings'))) {
          return;
        }
      }
      const skipAssignSave =
        currentStep.value === 1
        && smartMeteringAssigned.value
        && !needsAssignReadingsFromSetup(setupData.value);
      if (!skipAssignSave) {
        await save();
        if (assignReadingsTaskId.value) return;
      }
    }

    if (currentStep.value < steps.value.length - 1) {
      currentStep.value++;
      if (currentStep.value > maxStep.value) {
        maxStep.value = currentStep.value;
      }
      setUrlStep();
    }
  } catch (error) {
    console.error(error);
    toast.error(error?.data?.error || error?.message || t('common.error'));
  } finally {
    nextStepLoading.value = false;
  }
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
    await fetchConfigData('billing/reading-batch-status', readingBatchStatuses);
  } catch (error) {
    console.error('Error loading draft:', error);
  }
  loading.value = false;

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

onBeforeRouteLeave((to, from) => {
  clearInterval(itvl)
});

const fullRefresh = async (next_step = true) => {
  await refresh();
  if (next_step) {
    nextStep(false);
  }
};

/** Refresh counters when assign task completes; do not advance wizard (save/nextStep handle that). */
const onAssignReadingsTaskRefresh = async () => {
  await refresh();
};

onMounted(() => {
  batch_id.value = props.id;
  // if (props.counters) {
  //   counters.value = props.counters;
  //   currentStep.value = 1;
  //   maxStep.value = 1;
  // }
  if (taskId.value) {
    currentStep.value = 3;
    maxStep.value = 3;
  }
  else {
    if (route.query.step) {
      currentStep.value = parseInt(route.query.step) - 1;
      maxStep.value = currentStep.value;
    }
  }
  // console.log('num_supplies', props.num_supplies) 
  setUrlStep();
  getData();
});

const save = async () => {
  if (currentStep.value == 0) {
    // 1. Creation
    const data = creationData.value;
    if (!data) return;

    if (props.id) {
      // Editing an already-created batch: update it in place instead of creating a new one.
      data.id = props.id;
      await $ReadingBatchApiService.update(data);
      batch_id.value = props.id;
    } else {
      const results = await $ReadingBatchApiService.create(data);
      await navigateTo(`/reading/reading-batches/edit/${results.id}?step=2`)
    }
  }
  else if (currentStep.value == 1) {
    let data = setupData.value;
    if (!data) data = {};
    data.id = props.id;

    smartMeteringMode.value = false;
    smartMeteringPreview.value = null;
    const hadSmartMetering = smartMeteringAssigned.value;
    smartMeteringAssigned.value = false;
    const results = await $ReadingBatchApiService.assignReadings(data);
    if (results.task_id) {
      assignReadingsTaskId.value = results.task_id;
      try {
        countersSetup.value = await waitForAssignTask(results.task_id);
      } catch (error) {
        if (hadSmartMetering) {
          smartMeteringAssigned.value = true;
        }
        throw error;
      } finally {
        assignReadingsTaskId.value = null;
      }
    } else {
      countersSetup.value = results;
    }
    await refresh();
  }
  else if (currentStep.value == 2) {
    const data = {
      id: props.id
    }

    const results = await $ReadingBatchApiService.generateSummary(data);
    taskId.value = results.task_id;
    await refresh();

  }
  else if (currentStep.value == 2) {
    if (confirm(t("confirmation_text_block.confirm_validate_readings_batch"))) {
      await navigateTo(`/reading/reading-batches`)
    }
  }
} // end save function

const allowContinue = (allow) => {
  nextStepAllowed.value = allow;
}

const previousStepLoading = ref(false);
const revertTaskId = ref(null);
const revertTargetStep = ref(null);
const showBlockedRevertModal = ref(false);
const blockedRevertReadingIds = ref([]);
const blockedRevertMessage = ref('');

/** Only allowed from step 4 (anomaly review): revert batch status so readings can be reloaded/fixed. */
const previousStep = async () => {
  if (currentStep.value !== 3) return;
  if (!confirm(t('confirmation_text_block.confirm_revert_reading_batch') || t('confirmation_text_block.confirm_generate_reading_batch'))) {
    return;
  }
  revertTargetStep.value = currentStep.value - 1;
  previousStepLoading.value = true;
  try {
    const res = await $ReadingBatchApiService.revert(batch_id.value);
    if (res?.unlinked_draft_invoice_ids?.length > 0) {
      toast.warning(t('billing_block.revert_unlinked_draft_invoices', { count: res.unlinked_draft_invoice_ids.length }) || `${res.unlinked_draft_invoice_ids.length} factures esborrany desvinculades`);
    }
    if (res?.task_id) {
      revertTaskId.value = res.task_id;
    } else {
      await onRevertTaskDone();
    }
  } catch (error) {
    console.error(error);
    const status = error?.response?.status;
    const data = error?.response?._data;
    if (status === 409) {
      blockedRevertReadingIds.value = data?.blocked_reading_ids || [];
      blockedRevertMessage.value = data?.error || t('billing_block.revert_blocked_final_invoice');
      showBlockedRevertModal.value = true;
    } else if (status === 404) {
      toast.error(data?.error || t('billing_block.reading_batch_not_found'));
    } else {
      toast.error(data?.error || error?.message || t('common.error'));
    }
  } finally {
    previousStepLoading.value = false;
  }
};

const onRevertTaskDone = async () => {
  revertTaskId.value = null;
  taskId.value = null;
  counters.value = null;
  if (revertTargetStep.value === 1) {
    smartMeteringAssigned.value = false;
  }
  await refresh();
  currentStep.value = revertTargetStep.value ?? 2;
  maxStep.value = currentStep.value;
  revertTargetStep.value = null;
  setUrlStep();
};

watch(() => props.activeStatus, (newVal) => {
  // console.log('activeStatus', newVal)
  readingBatchStatus.value = newVal;
})
</script>

<template>
  <div class="text-base">
    <!-- Header: Status Navigation & Quick Overview -->
    <div class="flex justify-between items-start mb-6 px-1">
      <div class="flex items-center gap-3">
        <h2 class="text-xl font-bold text-gray-800 tracking-tight">
          {{ t('billing_block.reading_batch_wizard_title') || 'Gestió de Lots de Lectura' }}
        </h2>
        <span v-if="props.id" class="text-sm text-slate-500 bg-slate-100 px-2.5 py-1 rounded-full font-medium">
          ID: #{{ props.id }}
        </span>
      </div>
      <ReadingBatchRouteDownload
        v-if="currentStep !== 0 && (props.id || batch_id)"
        :batch_id="props.id || batch_id"
      />
    </div>

    <WizardStatusNav
      :steps="wizardSteps"
      :current-step="currentStep"
      :max-step="maxStep"
      disabled
    />

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
        <div v-if="loadingCreationData" class="flex justify-center items-center py-6">
          <Icon name="fa6-solid:spinner" class="animate-spin text-2xl text-slate-500" />
          <span class="ml-2">{{ $t('common.loading') }}...</span>
        </div>
        <ReadingBatchCreate v-else :initial-data="creationData" @change="onCreationDataChanged" />
      </div>
      <div v-if="currentStep === 1" class="tab-content mb-6">
        <AtomsPartialErrorsBanner :errors="partialTaskErrors" />
        <ReadingBatchSetup :num_supplies="num_supplies" :num_contracts="num_contracts" :num_no_meters="num_no_meters"
          :counters="countersSetup" @change="onSetupChanged" :missing_billing_data="missing_billing_data"
          :batch_id="props.id"
          :smart-metering-loading="isSmartMeteringBusy"
          :smart-metering-task-id="smartMeteringPreviewTaskId"
          @open-smart-metering="onOpenSmartMetering"
          @smart-metering-preview-refresh="onSmartMeteringPreviewTaskRefresh"
          @show-subregion="onSetupShowSubregion" />
      </div>

      <div v-if="currentStep === 2" class="tab-content mb-6">
        <div id="wrapper" class="text-base">
          <AtomsPartialErrorsBanner :errors="partialTaskErrors" />
          <ReadingBatchReadingsSummary :counters="countersSetup" :batch_id="props.id"
            :estimateReadingsTaskId="estimateReadingsTaskId" :defaultReadingDate="defaultReadingDate" @refresh="refresh"
            @allowContinue="allowContinue" :allow_force_manual="props.allow_force_manual"
            @show-subregion="onSetupShowSubregion" />
        </div>
      </div>
      <div v-if="currentStep === 3" class="tab-content mb-6">
        <div id="wrapper" class="text-base">
          <ReadingBatchSummary :taskId="taskId" :counters="counters" :batch_id="props.id" :counters_pending="countersSetup" />
        </div>
      </div>

      <!-- Botons de navegació -->
      <div class="flex justify-between mt-4">
        <div>
          <button v-if="currentStep === 3 && !revertTaskId" @click="previousStep" :disabled="previousStepLoading"
            class="px-4 py-2 bg-white text-slate-600 border border-gray-300 rounded enabled:hover:bg-slate-100 disabled:opacity-70 disabled:cursor-not-allowed flex items-center">
            <Icon v-if="previousStepLoading" name="fa6-solid:spinner" class="animate-spin mr-2" />
            <Icon v-else name="fa6-solid:arrow-left" class="mr-2" />
            {{ previousStepLoading ? $t('common.processing') : $t('common.previous') }}
          </button>
          <button v-if="currentStep === 1" @click="backToCreation" :disabled="loadingCreationData"
            class="px-4 py-2 bg-white text-slate-600 border border-gray-300 rounded enabled:hover:bg-slate-100 disabled:opacity-70 disabled:cursor-not-allowed flex items-center">
            <Icon v-if="loadingCreationData" name="fa6-solid:spinner" class="animate-spin mr-2" />
            <Icon v-else name="fa6-solid:arrow-left" class="mr-2" />
            {{ loadingCreationData ? $t('common.processing') : $t('common.previous') }}
          </button>
          <AtomsProcessColorBadge v-if="revertTaskId" class="w-fit flex items-center" @refresh="onRevertTaskDone"
            :value="t('billing_block.reverting_reading_batch') || 'Revertint lot...'" :color="'blue'" :taskId="revertTaskId" />
        </div>
        <div class="flex flex-row gap-2">
          <AtomsProcessColorBadge class="w-fit flex items-center" v-if="isAssigningReadings" @refresh="onAssignReadingsTaskRefresh"
            :value="t('common.loading')" :color="'blue'" :taskId="assignReadingsTaskId" />
          <button v-if="currentStep === 1" @click="openEstimateAllDialog"
            :disabled="nextStepLoading || isAssigningReadings || isSmartMeteringBusy"
            class="px-4 py-2 bg-white text-slate-600 border border-gray-300 rounded enabled:hover:bg-slate-100 disabled:opacity-70 disabled:cursor-not-allowed flex items-center">
            <Icon name="fa6-solid:wand-magic-sparkles" class="mr-2" />
            {{ t('billing_block.estimate_readings') }}
          </button>
          <button v-if="currentStep !== steps.length - 1" @click="nextStep"
            :disabled="nextStepLoading || nextStepAllowed || isAssigningReadings || isSmartMeteringBusy"
            class="px-4 py-2 bg-green-500 text-white rounded enabled:hover:bg-green-600 disabled:opacity-70 disabled:cursor-not-allowed flex items-center">
            <Icon v-if="nextStepLoading || isSmartMeteringBusy" name="fa6-solid:spinner" class="animate-spin mr-2" />
            {{ nextStepLoading || isSmartMeteringBusy ? $t('common.processing') : $t('common.next') }} &nbsp;&rarr;
          </button>
          <div v-else class="flex gap-3">
            <button @click="clickFinalize"
              class="px-4 py-2 bg-green-500 text-white rounded disabled:opacity-50 enabled:hover:bg-green-600 font-bold flex items-center">
              <Icon name="fa6-solid:circle-check" />&nbsp; {{ $t('common.finish') }}
            </button>
          </div>
        </div>
      </div><!-- end contingut botons -->

    </div><!--end contingut pas actual -->

    <SmartMeteringReadingsDialog
      :show="showSmartMeteringDialog"
      :preview="smartMeteringPreview"
      :loading="smartMeteringSaving"
      @close="handleSmartMeteringClose"
      @save="handleSmartMeteringSave"
    />

    <EstimateReadingsDialog
      :show="showEstimateAllDialog"
      :default-reading-date="defaultReadingDate || setupData?.reading_date"
      :loading="estimatingAllReadings"
      @close="handleEstimateAllClose"
      @confirm="handleEstimateAllConfirm"
    />

    <!-- Modal d'error: revert bloquejat per factura definitiva vinculada -->
    <div v-if="showBlockedRevertModal">
      <div class="fixed inset-0 bg-black bg-opacity-50 z-40" @click="showBlockedRevertModal = false"></div>
      <div class="fixed inset-0 z-50 flex items-center justify-center overflow-y-auto pointer-events-none">
        <div class="bg-white rounded-lg shadow-xl p-6 max-w-md w-full mx-4 my-auto relative pointer-events-auto">
          <button @click="showBlockedRevertModal = false" class="absolute top-4 right-4 text-gray-500 hover:text-gray-700">
            <Icon name="fa6-solid:xmark" class="text-xl" />
          </button>
          <div class="flex items-center gap-2 mb-4 text-red-600">
            <Icon name="fa6-solid:triangle-exclamation" class="text-xl" />
            <h3 class="text-lg font-bold">{{ $t('billing_block.revert_blocked_title') || 'No es pot revertir el lot' }}</h3>
          </div>
          <p class="text-slate-600 text-sm mb-4">{{ blockedRevertMessage }}</p>
          <div v-if="blockedRevertReadingIds.length > 0" class="bg-slate-50 border border-slate-200 rounded p-3 max-h-48 overflow-y-auto">
            <span class="block text-xs font-bold text-slate-500 uppercase mb-2">{{ $t('billing_block.blocked_reading_ids') || 'Lectures bloquejades' }}</span>
            <div class="flex flex-wrap gap-1.5">
              <span v-for="id in blockedRevertReadingIds" :key="id" class="text-xs font-mono bg-red-50 text-red-700 border border-red-100 rounded px-1.5 py-0.5">#{{ id }}</span>
            </div>
          </div>
          <div class="flex justify-end mt-6">
            <button @click="showBlockedRevertModal = false" class="button-primary">{{ $t('common.close') }}</button>
          </div>
        </div>
      </div>
    </div>

    <!-- Regió Dreta per l'edició/creació de ContractRequestEdit -->
    <div role="region" id="right_page"
      class="fixed h-full border-l border-gray-100 top-0 right-0 transition-all duration-500 ease py-2 text-base bg-white z-20"
      :class="{
        'translate-x-0': showRegion,
        'translate-x-[2000px]': !showRegion,
        'w-[90%]': showReaderAlertRegion,
        'w-1/2': !showReaderAlertRegion
      }">
      <div id="region_nav" class="mb-3 px-3">
        <button @click="closeAlertDetail" class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300">
          <Icon name="fa6-solid:angles-right" class="text-slate-500" />
        </button>
      </div>
      <div class="px-10">
        <ReaderAlertRegion v-if="showReaderAlertRegion" :batch_id="props.id"
          :breakdown="countersSetup?.reader_alert_breakdown || {}" />
        <!-- <ChangeStatus v-if="editingChangeStatus" entity="connection-request" parent_entity="connection_request"
          :id="request?.id" :status="request?.status?.id" module="service" @changed="handleStatusChanged" /> -->
      </div>
    </div>
  </div>
</template>