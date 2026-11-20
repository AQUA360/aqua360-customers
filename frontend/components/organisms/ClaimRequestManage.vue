<script setup>
import { ref, computed, onMounted } from 'vue';
import { useI18n } from 'vue-i18n';
import StatusesNav from '~/components/atoms/StatusesNav.vue';
import ClaimRequestManageLetter from './ClaimRequestManageLetter.vue';
import ClaimRequestManageVulnerability from './ClaimRequestManageVulnerability.vue';
import ClaimRequestManageSuspension from './ClaimRequestManageSuspension.vue';
import ClaimRequestManageCutSupply from './ClaimRequestManageCutSupply.vue';
import ClaimRequestManageRemoveMeter from './ClaimRequestManageRemoveMeter.vue';
import ClaimRequestManageCancelContract from './ClaimRequestManageCancelContract.vue';
import ClaimRequestContractSelectionRegion from './ClaimRequestContractSelectionRegion.vue';
import ClaimRequestContractListRegion from './ClaimRequestContractListRegion.vue';
import ClaimRequestInvoiceListRegion from './ClaimRequestInvoiceListRegion.vue';
import ClaimRequestOrdersRegion from './ClaimRequestOrdersRegion.vue';
import ClaimRequestTerminationsRegion from './ClaimRequestTerminationsRegion.vue';
import CommunicationProcessRegion from './CommunicationProcessRegion.vue';
import ClaimRequestPriceRateInvoice from '../molecules/ClaimRequestPriceRateInvoice.vue';
import WizardStatusNav from '../molecules/WizardStatusNav.vue';
import { useNuxtApp } from '#app';
import { useToast } from 'vue-toastification';
import ChangeStatus from '../molecules/ChangeStatus.vue';

const props = defineProps({
  request: Object
});

const { t, te } = useI18n();
const emit = defineEmits(['changed']);
const { $ClaimRequestApiService, $ConfiglistApiService } = useNuxtApp();
const toast = useToast();

// Log inicial per veure les dades que rebem
const stepsValue = ref([]);
const currentStep = ref(null);
const visualStep = ref(null); // Nou ref per la navegació visual
const selectedVulnerableContracts = ref([]);
const selectedCancelContracts = ref([]);
const selectedCutSupplyContracts = ref([]);
const selectedRemoveMeterContracts = ref([]);
const requestData = ref(props.request);

const claimStatuses = ref([]);

// Variables per gestionar les regions
const showRegion = ref(false);
const isSubRegionOpen = ref(false);
const showRegionDetailComponent = ref(null);
const regionDetailId = ref(null);
const showContractSelection = ref(false);
const showContractList = ref(false);
const showInvoiceList = ref(false);
// Canvia cada vegada que s'obre una llista: força a muntar-la de nou perquè no conservi
// un detall obert d'abans (la regió es pot tancar sense desmuntar-la)
const listKey = ref(0);
const showOrders = ref(false);
const showTerminations = ref(false);
const orders = ref([]);
const contracts = ref([]);
const currentOrderType = ref('');
const cutSupplyOrdersCount = ref(0);
const removeMeterOrdersCount = ref(0);
const loading = ref(false);
const generatingExpensesTaskId = computed(() => {
  return visualStep.value?.task_id;
});

const getClaimSteps = async () => {
  try {
    let fetchData = await $ClaimRequestApiService.getClaimStepsData(props.request.id);

    // Si ja tenim dades, preservem les dades específiques
    if (stepsValue.value.length > 0) {
      stepsValue.value = fetchData.map(newStep => {
        const existingStep = stepsValue.value.find(step => step.id === newStep.id);
        if (existingStep) {
          return {
            ...newStep,
            // Preservem les dades específiques del pas
            action_date_at: existingStep.action_date_at || newStep.action_date_at,
            // Afegim aquí altres camps que vulguem preservar
            color: existingStep.is_completed || step.end_step_date != null ? 'green' : (existingStep.id === currentStep.value?.id ? 'blue' : 'gray'),
            //color: 'green',
          };
        }
        return newStep;
      });
    } else {
      stepsValue.value = fetchData;
      stepsValue.value.forEach(step => {
        step.color = step.is_completed || step.end_step_date != null ? 'green' : (step.id === currentStep.value?.id ? 'blue' : 'gray');
      })
      stepsValue.value = stepsValue.value.filter((step, index, self) =>
        index === self.findIndex((t) => t.id === step.id)
      );
    }

    // Actualitzem el currentStep i visualStep
    currentStep.value = stepsValue.value.find(el => el.id == props.request.current_step.id);
    if (currentStep.value) {
      currentStep.value.color = "blue";
    }
    //visualStep.value = currentStep.value;
    visualStep.value = stepsValue.value.find(el => el.id == props.request.current_step.id);
  } catch (error) {
    console.error('Error loading steps:', error);
  }
};

const getClaimStatuses = async () => {
  try {
    const response = await $ConfiglistApiService.getAll('claimrequest/claim-request-status');
    claimStatuses.value = response.results || [];
  } catch (error) {
    console.error('Error loading claim statuses:', error);
  }
};

const loadData = async () => {
  try {
    currentStep.value = stepsValue.value.find(el => el.id == props.request.current_step.id);
    if (currentStep.value) {
      currentStep.value.color = "blue";
    }
    // Inicialitzem el visualStep al currentStep
    //visualStep.value = currentStep.value;
    visualStep.value = stepsValue.value.find(el => el.id == props.request.current_step.id);

  } catch (error) {
    console.error('Error loading draft:', error);
  }
};

const loadOrders = async () => {
  try {
    const [cutSupplyResponse, removeMeterResponse] = await Promise.all([
      $ClaimRequestApiService.getClaimRequestOrders(props.request.id, 'cut_supply'),
      $ClaimRequestApiService.getClaimRequestOrders(props.request.id, 'remove_meter')
    ]);
    orders.value = cutSupplyResponse.results || [];
    cutSupplyOrdersCount.value = cutSupplyResponse.results?.length || 0;
    removeMeterOrdersCount.value = removeMeterResponse.results?.length || 0;
  } catch (error) {
    console.error('Error loading orders:', error);
  }
};

onMounted(async () => {
  await getClaimStatuses();
  await getClaimSteps();
  await loadData();
  await loadOrders(); // Carreguem les ordres inicialment

});

const formatMoneyWithCurrency = (amount) => {
  return new Intl.NumberFormat('ca-ES', {
    style: 'currency',
    currency: 'EUR'
  }).format(amount);
}

const handleStepChange = async (showLoading = true) => {
  // Actualitzem les dades del pas actual
  await updateStepData(currentStep.value.id);
  emit('changed', showLoading);
};

// Funció per actualitzar les dades d'un pas específic
const updateStepData = async (stepId) => {
  try {
    const response = await $ClaimRequestApiService.getClaimStepsData(props.request.id);
    const updatedStep = response.find(step => step.id === stepId);
    if (updatedStep) {
      // Actualitzem el pas a stepsValue preservant les dades específiques
      const index = stepsValue.value.findIndex(step => step.id === stepId);
      if (index !== -1) {
        const currentStep = stepsValue.value[index];
        stepsValue.value[index] = {
          ...updatedStep,
          // Preservem les dades específiques del pas
          action_date_at: currentStep.action_date_at || updatedStep.action_date_at,
          // Afegim aquí altres camps que vulguem preservar
          color: updatedStep.is_completed || updatedStep.end_step_date != null ? 'green' : (updatedStep.id === currentStep.value?.id ? 'blue' : 'gray'),
        };
      }
    }
  } catch (error) {
    console.error('Error updating step data:', error);
  }
};

// Mètodes per gestionar la navegació visual entre passos
const handlePreviousStep = async () => {
  if (!visualStep.value || !stepsValue.value?.length) return;

  // Trobar el pas actual a l'array de steps
  const currentStepInArray = stepsValue.value.find(step => step.id === visualStep.value.id);
  if (!currentStepInArray) return;

  // Trobar el pas anterior
  const previousStep = stepsValue.value.find(step => step.next_step_id === currentStepInArray.id);
  if (!previousStep) return;

  // Actualitzem el visualStep
  visualStep.value = previousStep;

  // Actualitzem les dades del pas anterior
  await updateStepData(previousStep.id);
};

const handleNextStep = async () => {
  if (!visualStep.value || !visualStep.value.next_step_id) return;

  // Trobar el següent pas
  const nextStep = stepsValue.value.find(step => step.id === visualStep.value.next_step_id);
  if (!nextStep) return;

  // Actualitzem el visualStep
  visualStep.value = nextStep;

  // Actualitzem les dades del següent pas
  await updateStepData(nextStep.id);
};

// Computed properties actualitzades
const isFirstStep = computed(() => {
  if (!visualStep.value || !stepsValue.value?.length) return false;
  // Un pas és el primer si no hi ha cap altre pas que el tingui com a next_step
  return !stepsValue.value.some(step => step.next_step_id === visualStep.value.id);
});

const isLastStep = computed(() => {
  if (!visualStep.value) return false;
  // Un pas és l'últim si no té next_step_id
  return !visualStep.value.next_step_id;
});

// Afegim una prop computada per saber si podem avançar
const canProceed = computed(() => {
  if (!visualStep.value) return false;
  if (visualStep.value.token === 'vulnerability_request' && requestData.value.vulnerable_pending_requests_count > 0) return false
  // Aquí podem afegir més validacions específiques segons el tipus de pas
  /*
  switch (visualStep.value.token) {
    case 'vulnerability_request':
      return selectedVulnerableContracts.value.length > 0;
    case 'cancel_contract':
      return selectedCancelContracts.value.length > 0;
    // Afegir més casos segons sigui necessari
    default:
      return true;
  }
      */
  return true;
});

// Afegim una prop computada per saber si estem al pas actual
const isCurrentStep = computed(() => {
  if (!visualStep.value || !currentStep.value) return false;
  return visualStep.value.id === currentStep.value.id;
});

const orderedSteps = computed(() => {
  if (!stepsValue.value?.length) return [];

  const first = stepsValue.value.find(step =>
    !stepsValue.value.some(s => s.next_step_id === step.id)
  );
  if (!first) return stepsValue.value;

  const ordered = [];
  let step = first;
  const visited = new Set();

  while (step && !visited.has(step.id)) {
    visited.add(step.id);
    ordered.push(step);
    step = step.next_step_id
      ? stepsValue.value.find(s => s.id === step.next_step_id)
      : null;
  }

  return ordered;
});

const translateStepName = (name) => {
  if (!name) return '';
  const blockKey = `billing_block.${name}`;
  const resBlock = te(blockKey) ? t(blockKey) : blockKey;
  if (resBlock !== blockKey) return resBlock;
  const resGlobal = te(name) ? t(name) : name;
  if (resGlobal !== name) return resGlobal;
  return name;
};

const getStepIcon = (token) => {
  const icons = {
    send_claim_letter: 'fa6-solid:envelope',
    vulnerability_request: 'fa6-solid:hand-holding-heart',
    suspension_alert: 'fa6-solid:triangle-exclamation',
    cut_supply: 'fa6-solid:scissors',
    remove_meter: 'fa6-solid:gauge-simple',
    cancel_contract: 'fa6-solid:file-circle-xmark',
  };
  return icons[token] || 'fa6-solid:circle';
};

const wizardSteps = computed(() =>
  orderedSteps.value.map((step, index) => ({
    index,
    label: `${t('billing_block.step')} ${index + 1}`,
    title: translateStepName(step.name),
    description: step.description || translateStepName(step.name),
    icon: getStepIcon(step.token),
  }))
);

const visualStepIndex = computed(() => {
  if (!visualStep.value) return 0;
  const index = orderedSteps.value.findIndex(step => step.id === visualStep.value.id);
  return index >= 0 ? index : 0;
});

const handleGetTaskData = async () => {
  if (!visualStep.value) return;

  const stepId = visualStep.value.id;
  visualStep.value.task_id = null;

  await updateStepData(stepId);

  // updateStepData substitueix l'objecte dins stepsValue, així que hem de
  // reapuntar les referències al nou objecte per refrescar la vista
  const reloadedStep = stepsValue.value.find(step => step.id === stepId);
  if (!reloadedStep) return;

  visualStep.value = reloadedStep;
  if (currentStep.value?.id === stepId) {
    currentStep.value = reloadedStep;
    currentStep.value.color = 'blue';
  }
}

const maxWorkflowStepIndex = computed(() => {
  if (!currentStep.value) return 0;
  const index = orderedSteps.value.findIndex(step => step.id === currentStep.value.id);
  return index >= 0 ? index : 0;
});

// Mètodes per gestionar les regions
const toggleRegion = (value) => {
  showRegion.value = value;
  if (!value) {
    showRegionDetailComponent.value = null;
    regionDetailId.value = null;
    isSubRegionOpen.value = false;
    showContractSelection.value = false;
  }
};

const handleSubRegionEvent = (event) => {
  isSubRegionOpen.value = event;
};

const handleShowContractSelection = () => {
  showContractSelection.value = true;
  showRegion.value = true;
  showRegionDetailComponent.value = null;
  isSubRegionOpen.value = false;
  showContractList.value = false;
  showInvoiceList.value = false;
};

const handleShowCommunicationProcess = (processId) => {
  showRegion.value = true;
  showRegionDetailComponent.value = 'CommunicationProcessRegion';
  regionDetailId.value = processId;
  isSubRegionOpen.value = false;
  showContractSelection.value = false;
  showContractList.value = false;
  showInvoiceList.value = false;
}

const handleStatusChange = () => {
  showRegion.value = true;
  showRegionDetailComponent.value = 'StatusChangeRegion';
  isSubRegionOpen.value = false;
  showContractSelection.value = false;
  showContractList.value = false;
  showInvoiceList.value = false;
}

const handleShowContracts = (contractsList) => {
  contracts.value = contractsList;
  showRegion.value = true;
  showContractSelection.value = true;
  showRegionDetailComponent.value = null;
  isSubRegionOpen.value = true;
  showContractList.value = false;
  showInvoiceList.value = false;

  // Assegurem que els contractes seleccionats es mantenen
  if (visualStep.value?.token === 'vulnerability_request') {
    selectedVulnerableContracts.value = [...selectedVulnerableContracts.value];
  } else if (visualStep.value?.token === 'cancel_contract') {
    selectedCancelContracts.value = [...selectedCancelContracts.value];
  } else if (visualStep.value?.token === 'cut_supply') {
    selectedCutSupplyContracts.value = [...selectedCutSupplyContracts.value];
  } else if (visualStep.value?.token === 'remove_meter') {
    selectedRemoveMeterContracts.value = [...selectedRemoveMeterContracts.value];
  }
};

const handleShowOrders = async (orderType) => {
  try {
    currentOrderType.value = orderType;
    await loadOrders(); // Recarreguem les ordres abans de mostrar la regió
    showRegion.value = true;
    showRegionDetailComponent.value = 'OrdersRegion';
    isSubRegionOpen.value = false;
    showContractSelection.value = false;
    showContractList.value = false;
    showInvoiceList.value = false;
  } catch (error) {
    toast.error(t('Error al carregar les ordres'));
    console.error(error);
  }
};

const handleShowInvoiceList = () => {
  listKey.value++;
  showInvoiceList.value = true;
  showContractList.value = false;
  showRegion.value = true;
  showRegionDetailComponent.value = null;
  isSubRegionOpen.value = false;
  showContractSelection.value = false;
};

const handleShowContractList = () => {
  listKey.value++;
  showContractList.value = true;
  showInvoiceList.value = false;
  showRegion.value = true;
  showRegionDetailComponent.value = null;
  isSubRegionOpen.value = false;
  showContractSelection.value = false;
};

// Cada grup del resum creix en proporció al nombre de cel·les que té,
// perquè totes les cel·les facin la mateixa amplada
const summaryGroupStyle = (cells) => ({ flex: `${cells} 1 ${cells * 120}px` });

// Propietats computades per controlar la visibilitat dels comptadors
const showCutSupplyCounter = computed(() => {
  return stepsValue.value?.some(step => step.token === 'cut_supply');
});

const showRemoveMeterCounter = computed(() => {
  return stepsValue.value?.some(step => step.token === 'remove_meter');
});

// Funció per actualitzar les dades de la reclamació
const updateRequestData = async () => {
  try {
    const response = await $ClaimRequestApiService.getDetail(requestData.value.id);
    // Actualitzem només les dades necessàries sense canviar l'estructura
    requestData.value = {
      ...requestData.value,
      ...response,
      // Mantenim les dades específiques que no volem que es sobreescriguin
      current_step: requestData.value.current_step
    };
    emit('changed');
  } catch (error) {
    console.error('Error updating request data:', error);
    toast.error(t('common.error_save'));
  }
};

const handleRegionChange = async (showLoading = true) => {
  try {
    toggleRegion(false)
    handleContractChange(showLoading);
  } catch (error) {
    console.error('Error updating request data:', error);
    toast.error(t('common.error_save'));
  }
};

const handleGenerateExpenses = async (data) => {
  try {
    const response = await $ClaimRequestApiService.generateExpenses(data);
    visualStep.value.task_id = response.task_id;
  } catch (error) {
    console.error('Error generating expenses:', error);
    toast.error(t('common.error_save'));
  }
};

const handleContractChange = async (showLoading = true) => {
  try {
    // Actualitzem les dades de la reclamació
    const response = await $ClaimRequestApiService.getDetail(requestData.value.id);
    requestData.value = {
      ...requestData.value,
      ...response,
      // Mantenim les dades específiques que no volem que es sobreescriguin
      current_step: requestData.value.current_step
    };
    // Notifiquem el canvi al pare
    emit('changed', showLoading);
  } catch (error) {
    console.error('Error updating request data:', error);
    toast.error(t('common.error_save'));
  }
};

// Afegim una prop computada per obtenir el nombre d'ordres
const ordersCount = computed(() => orders.value.length);

const handleContractSelection = (selectedContracts) => {
  if (visualStep.value?.token === 'vulnerable_request') {
    selectedVulnerableContracts.value = [...selectedContracts];
  } else if (visualStep.value?.token === 'cancel_contract') {
    selectedCancelContracts.value = [...selectedContracts];
  }
};

// Afegim una prop computada per obtenir el nombre de baixes
const terminationsCount = computed(() => requestData.value?.contract_termination_requests?.length || 0);

const handleShowTerminations = () => {
  showRegion.value = true;
  showRegionDetailComponent.value = 'TerminationsRegion';
  isSubRegionOpen.value = true;
  showContractSelection.value = false;
  showContractList.value = false;
  showInvoiceList.value = false;
  showOrders.value = false;
};

const handleFinishStep = async () => {
  if (!visualStep.value) return;

  try {
    loading.value = true;

    // Obtenim la data actual en format YYYY-MM-DD
    const today = new Date().toISOString().split('T')[0];

    // Guardem el canvi
    await $ClaimRequestApiService.save({
      id: props.request.id,
      is_completed: true,
      current_step: visualStep.value.next_step_id ? visualStep.value.next_step_id : visualStep.value.id,
      end_step_date: new Date().toISOString().split('T')[0]
    });

    // Actualitzem l'estat local
    const nextStep = stepsValue.value.find(step => step.id === visualStep.value.next_step_id);
    if (nextStep) {
      currentStep.value = nextStep;
      currentStep.value.color = "blue";
      visualStep.value = nextStep;

      // Actualitzem les dades del pas actualitzat
      await updateStepData(nextStep.id);
    }

    // Notifiquem el canvi
    emit('changed');
    toast.success(t('common.correct_finish'));
  } catch (error) {
    toast.error(t('common.error_save'));
    console.error(error);
  } finally {
    loading.value = false;
  }
};

</script>

<template>
  <div class="wrapper text-base max-w-full mb-20">
    <!-- Panell de resum -->
    <Teleport defer to="#claim-request-header-actions">
      <div class="flex items-center gap-2">
        <button @click="handleStatusChange"
          class="h-8 w-8 border border-slate-200 rounded-full opacity-70 hover:opacity-100 hover:border-slate-300 hover:bg-slate-50 transition-all duration-200">
          <Icon name="fa6-solid:pencil" class="text-slate-500" />
        </button>
        <StatusesNav :active="requestData.status" :statuses="[requestData.status]" />
      </div>
    </Teleport>

    <!-- Resum: un grup per tema (títol + franja de cel·les). Cada grup creix segons el nombre de
         cel·les, perquè totes les cel·les facin la mateixa amplada i la fila ompli tota la pàgina. -->
    <div class="mb-4 flex flex-wrap gap-x-4 gap-y-3">
      <section :style="summaryGroupStyle(3)">
        <p class="mb-1.5 text-[11px] font-semibold uppercase tracking-wide text-slate-400">
          {{ $t('billing_block.payments') }}
        </p>
        <div class="flex divide-x divide-slate-200 overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
          <AtomsSummaryStatCard :value="requestData.pending_payments_count"
            :label="$t('billing_block.pending_payments')" />
          <AtomsSummaryStatCard :value="requestData.paid_payments_count" :label="$t('reports_block.paid_payments')" />
          <AtomsSummaryStatCard :value="formatMoneyWithCurrency(requestData.amount)" :label="$t('common.amount')" />
        </div>
      </section>

      <section :style="summaryGroupStyle(visualStep?.token === 'cancel_contract' ? 4 : 3)">
        <p class="mb-1.5 text-[11px] font-semibold uppercase tracking-wide text-slate-400">
          {{ $t('billing_block.contracts_and_invoices') }}
        </p>
        <div class="flex divide-x divide-slate-200 overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
          <AtomsSummaryStatCard clickable @click="handleShowContractList"
            :value="requestData.total_contracts - requestData.excluded_contracts_count"
            :label="$t('contract_block.affected_contracts')" :title="$t('contract_block.manage_contracts')" />
          <AtomsSummaryStatCard v-if="visualStep?.token === 'cancel_contract'" clickable
            @click="handleShowTerminations" :value="terminationsCount" :label="$t('common.contract_terminations')"
            :title="`${$t('common.show')} ${$t('common.contract_terminations')}`" />
          <AtomsSummaryStatCard clickable @click="handleShowInvoiceList" :value="requestData.affected_invoices_count"
            :label="$t('billing_block.affected_invoices_title')"
            :title="`${$t('common.show')} ${$t('billing_block.affected_invoices_title')}`" />
          <AtomsSummaryStatCard :value="requestData.excluded_invoices_count"
            :label="$t('billing_block.excluded_invoices')" />
        </div>
      </section>

      <section v-if="requestData.vulnerable_requests_count > 0" :style="summaryGroupStyle(3)">
        <p class="mb-1.5 text-[11px] font-semibold uppercase tracking-wide text-slate-400">
          {{ $t('contract_block.vulnerability') }}
        </p>
        <div class="flex divide-x divide-slate-200 overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
          <AtomsSummaryStatCard :value="requestData.vulnerable_requests_count" :label="$t('common.vulnerable_reqs')" />
          <AtomsSummaryStatCard :value="requestData.vulnerable_accepted_requests_count"
            :label="$t('common.accepted_requests')" />
          <AtomsSummaryStatCard :value="requestData.vulnerable_pending_requests_count"
            :label="$t('common.pending_requests')" />
        </div>
      </section>

      <section v-if="showCutSupplyCounter || showRemoveMeterCounter"
        :style="summaryGroupStyle((showCutSupplyCounter ? 1 : 0) + (showRemoveMeterCounter ? 1 : 0))">
        <p class="mb-1.5 text-[11px] font-semibold uppercase tracking-wide text-slate-400">
          {{ $t('common.orders') }}
        </p>
        <div class="flex divide-x divide-slate-200 overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
          <AtomsSummaryStatCard v-if="showCutSupplyCounter" clickable @click="handleShowOrders('cut_supply')"
            :value="cutSupplyOrdersCount" :label="$t('order_block.cut_orders')"
            :title="`${$t('common.show')} ${$t('order_block.cut_orders')}`" />
          <AtomsSummaryStatCard v-if="showRemoveMeterCounter" clickable @click="handleShowOrders('remove_meter')"
            :value="removeMeterOrdersCount" :label="$t('order_block.remove_orders')"
            :title="`${$t('common.show')} ${$t('order_block.remove_orders')}`" />
        </div>
      </section>
    </div>

    <WizardStatusNav v-if="wizardSteps.length && visualStep" :steps="wizardSteps" :current-step="visualStepIndex"
      :max-step="maxWorkflowStepIndex" disabled :show-description="false" />

    <div class="border border-slate-200 rounded-xl py-3 px-4 bg-white">

      <!-- Components específics per cada pas -->
      <ClaimRequestManageLetter v-if="visualStep?.token === 'send_claim_letter'" :request="requestData"
        :step="visualStep" :is-first-step="isFirstStep" :is-last-step="isLastStep" @changed="handleStepChange"
        @previous-step="handlePreviousStep" @show-letter="handleShowCommunicationProcess" @next-step="handleNextStep">
        <template #footer>
        </template>
      </ClaimRequestManageLetter>

      <ClaimRequestManageVulnerability v-if="visualStep?.token === 'vulnerability_request'" :request="requestData"
        :step="visualStep" :selectedVulnerableContracts="selectedVulnerableContracts" :is-first-step="isFirstStep"
        :is-last-step="isLastStep" @update:selectedVulnerableContracts="selectedVulnerableContracts = $event"
        @show-contract-selection="handleShowContractSelection" @changed="handleStepChange"
        @previous-step="handlePreviousStep" @next-step="handleNextStep">
        <template #footer>
        </template>
      </ClaimRequestManageVulnerability>

      <ClaimRequestManageSuspension v-if="visualStep?.token === 'suspension_alert'" :request="requestData"
        :step="visualStep" :is-first-step="isFirstStep" :is-last-step="isLastStep" @changed="handleStepChange"
        @show-letter="handleShowCommunicationProcess" @previous-step="handlePreviousStep" @next-step="handleNextStep">
        <template #footer>
        </template>
      </ClaimRequestManageSuspension>

      <ClaimRequestManageCutSupply v-if="visualStep?.token === 'cut_supply'" :request="requestData" :step="visualStep"
        :is-first-step="isFirstStep" :is-last-step="isLastStep" :orders-count="ordersCount"
        :selectedContracts="selectedCutSupplyContracts" @changed="handleStepChange" @previous-step="handlePreviousStep"
        @next-step="handleNextStep" @show-contracts="handleShowContracts"
        @update:selectedContracts="selectedCutSupplyContracts = $event" @show-orders="handleShowOrders">
        <template #footer>
        </template>
      </ClaimRequestManageCutSupply>

      <ClaimRequestManageRemoveMeter v-if="visualStep?.token === 'remove_meter'" :request="requestData"
        :step="visualStep" :is-first-step="isFirstStep" :is-last-step="isLastStep"
        :orders-count="removeMeterOrdersCount" :selectedContracts="selectedRemoveMeterContracts"
        @changed="handleStepChange" @previous-step="handlePreviousStep" @next-step="handleNextStep"
        @update:selectedContracts="selectedRemoveMeterContracts = $event" @show-contracts="handleShowContracts"
        @show-orders="handleShowOrders">
        <template #footer>
        </template>
      </ClaimRequestManageRemoveMeter>

      <ClaimRequestManageCancelContract v-if="visualStep?.token === 'cancel_contract'" :request="requestData"
        :step="visualStep" :is-first-step="isFirstStep" :is-last-step="isLastStep"
        :selectedContracts="selectedCancelContracts" @changed="handleStepChange" @previous-step="handlePreviousStep"
        @next-step="handleNextStep" @show-contracts="handleShowContracts"
        @update:selectedContracts="selectedCancelContracts = $event" @show-terminations="handleShowTerminations">
        <template #footer>
        </template>
      </ClaimRequestManageCancelContract>
      <div v-if="visualStep?.price_rates?.length > 0" class="mt-5">
        <ClaimRequestPriceRateInvoice :request="requestData" :generate-task-id="generatingExpensesTaskId"
          :step="visualStep" @generate-expenses="handleGenerateExpenses" @get-task-data="handleGetTaskData" />
      </div>
    </div>

    <!-- Barra de navegació fixada al footer -->
    <div class="fixed right-0 bottom-0 z-[20] border-t border-gray-200 py-4 px-4 shadow-lg bg-[#FAE2DA]"
      style="width: calc(100% - 250px)">
      <div class="mx-auto flex justify-between items-center px-4">
        <div class="flex space-x-4 mr-auto">
          <button v-if="!isFirstStep" @click="handlePreviousStep" class="button-secondary flex items-center gap-2"
            :title="$t('billing_block.go_prev_step')">
            <Icon name="fa6-solid:chevron-left" />
            {{ $t('common.previous') }}
          </button>
          <!-- <button 
            @click="handleStatusChange" 
            class="button-default bg-white flex items-center gap-2 opacity-60 hover:opacity-100 transition-all duration-200"
            :disabled="loading"
            :title="t('Canviar l\'estat de la gestió')"
          >
            {{ $t('Canviar l\'estat de la gestió') }}
          </button> -->
        </div>
        <div class="flex space-x-4 ml-auto">

          <button v-if="isCurrentStep" @click="handleFinishStep" class="button-success flex items-center gap-2"
            :disabled="loading || !canProceed"
            :title="!canProceed ? $t('warning_block.warning_can_not_finish_step') : `${$t('common.finish')} ${$t('billing_block.step')}`">
            <Icon v-if="!loading" name="fa6-solid:check" />
            <Icon v-else name="fa:spinner" class="animate-spin" />
            {{ $t('common.finish') }} {{ $t('billing_block.step') }}
          </button>
          <button v-if="!isLastStep" @click="handleNextStep" class="button-primary flex items-center gap-2"
            :title="$t('billing_block.go_next_step')">
            {{ $t('common.next') }}
            <Icon name="fa6-solid:chevron-right" />
          </button>
        </div>
      </div>
    </div>

    <div role="region" id="right_page"
      class="fixed h-full border-l border-slate-100 top-0 right-0 transition-all duration-500 ease py-2 text-base bg-white z-[100]"
      :class="{ 'translate-x-0': showRegion, 'translate-x-[2000px]': !showRegion, 'w-[95%]': isSubRegionOpen, 'w-[55%]': !isSubRegionOpen }">
      <div id="region_nav" class="mb-3 px-3">
        <button @click="toggleRegion(false)" class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300">
          <Icon name="fa6-solid:angles-right" class="text-slate-500" />
        </button>
      </div>
      <div class="px-10">
        <ClaimRequestContractSelectionRegion
          v-if="showContractSelection && visualStep?.token === 'vulnerability_request'" :request="requestData"
          :selectedContracts="selectedVulnerableContracts" :title="('claim_block.select_vulnerable_contracts')"
          highlightColor="bg-yellow-300" :isVulnerabilityContext="true"
          @update:selectedContracts="selectedVulnerableContracts = $event" @close="toggleRegion(false)" />
        <ClaimRequestContractSelectionRegion v-if="showContractSelection && visualStep?.token === 'cancel_contract'"
          :request="requestData" :selectedContracts="selectedCancelContracts"
          :title="('claim_block.select_cancel_contracts')" highlightColor="bg-red-100" :isVulnerabilityContext="false"
          @update:selectedContracts="selectedCancelContracts = $event" @close="toggleRegion(false)" />
        <ClaimRequestContractSelectionRegion v-if="showContractSelection && visualStep?.token === 'cut_supply'"
          :request="requestData" :selectedContracts="selectedCutSupplyContracts"
          :title="('claim_block.select_cut_contracts')" highlightColor="bg-red-100" :isVulnerabilityContext="false"
          @update:selectedContracts="selectedCutSupplyContracts = $event" @close="toggleRegion(false)" />
        <ClaimRequestContractSelectionRegion v-if="showContractSelection && visualStep?.token === 'remove_meter'"
          :request="requestData" :selectedContracts="selectedRemoveMeterContracts"
          :title="('claim_block.select_remove_contracts')" highlightColor="bg-red-100" :isVulnerabilityContext="false"
          @update:selectedContracts="selectedRemoveMeterContracts = $event" @close="toggleRegion(false)" />
        <ClaimRequestContractListRegion v-if="showContractList" :key="listKey" :request="requestData" :contracts="contracts"
          @show-detail="handleSubRegionEvent" @close="toggleRegion(false)" @change="handleContractChange" />
        <ClaimRequestInvoiceListRegion v-if="showInvoiceList" :key="listKey" :request="requestData"
          @show-detail="handleSubRegionEvent" @close="toggleRegion(false)" />
        <ClaimRequestOrdersRegion v-if="showRegionDetailComponent === 'OrdersRegion'"
          @show-subregion="handleSubRegionEvent" :request="requestData" :orderType="currentOrderType"
          @close="toggleRegion(false)" />
        <ClaimRequestTerminationsRegion v-if="showRegionDetailComponent === 'TerminationsRegion'" :request="requestData"
          @close="toggleRegion(false)" />
        <ChangeStatus v-if="showRegionDetailComponent === 'StatusChangeRegion'" entity="claim-request"
          parent_entity="claim_request" :id="requestData?.id" :status="requestData?.status?.id"
          @changed="handleRegionChange(false)" :module="'claimrequest'" :has_observation="false" />
        <CommunicationProcessRegion v-if="showRegionDetailComponent === 'CommunicationProcessRegion'"
          :id="regionDetailId" @change="handleContractChange(false)" @show-subregion="handleSubRegionEvent" />
      </div>
    </div>

  </div>
</template>

<style scoped lang="postcss">
.wrapper {
  padding-bottom: 80px;
  /* Espai per la barra de navegació fixada */
}

.button-primary {
  @apply bg-sky-600 text-white px-4 py-2 rounded hover:bg-sky-700 transition-colors;
}

.button-secondary {
  @apply bg-gray-200 text-gray-700 px-4 py-2 rounded hover:bg-gray-300 transition-colors;
}

.button-success {
  @apply bg-green-600 text-white px-4 py-2 rounded hover:bg-green-700 transition-colors;
}
</style>