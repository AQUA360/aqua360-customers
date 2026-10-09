<script setup>
import { ref, onMounted, computed, watch } from 'vue';
import { nextTick } from 'vue';
import { format, differenceInDays } from 'date-fns';
import { formatDate } from '~/utils/date';
import { useToast } from 'vue-toastification';
import { checkPermission } from '~/middleware/permission';
import ContractTerminationDetail from '~/components/molecules/ContractTerminationDetail.vue';
import ContractDetail from '~/components/molecules/ContractDetail.vue';
import H1 from '~/components/atoms/H1.vue';
import AppLoading from '~/components/atoms/AppLoading.vue';
import ButtonSeleccio from '~/components/atoms/ButtonSeleccio.vue';
import PersonSearch from '~/components/organisms/PersonSearch.vue';
import _ from 'lodash';
import ChangeStatus from '~/components/molecules/ChangeStatus.vue';
import StatusesNav from '~/components/atoms/StatusesNav.vue';
import ButtonOutline from '~/components/atoms/ButtonOutline.vue';
import OrderTypeDetail from '~/components/molecules/OrderTypeDetail.vue';
import OrderRegion from './OrderRegion.vue';
import AddInvoiceBudget from '../molecules/AddInvoiceBudget.vue';
import InvoiceView from './InvoiceView.vue';
import ReadingDetail from '../molecules/ReadingDetail.vue';
import WizardStatusNav from '../molecules/WizardStatusNav.vue';

const { t } = useI18n();
const route = useRoute()
const router = useRouter()
const toast = useToast();
const objectPermissions = ref(null);
const { $ConfiglistApiService, $ContractTerminationApiService, $ContractApiService, $OrderApiService, $ConfigProjectApiService, $SupplyPointApiService, $StatusApiService, $ReadingApiService } = useNuxtApp();

const props = defineProps({
  request: Object,
});

const emit = defineEmits(['refresh']);


const contract_request = ref({}); // <--- ContractRequest object

const flag = ref(false)
const steps = ref(['1', '2', '3']);
const currentStep = ref(0);
const maxStep = ref(0);

const wizardSteps = computed(() => [
  {
    index: 0,
    number: '1',
    label: t('billing_block.step') + ' 1',
    title: t('contract_block.step_termination_data') || 'Dades',
    description: t('contract_block.request_setup_title') || 'Sol·licitant i Motiu',
    icon: 'fa6-solid:circle-minus'
  },
  {
    index: 1,
    number: '2',
    label: t('billing_block.step') + ' 2',
    title: t('contract_block.step_termination_actions') || 'Accions',
    description: t('contract_block.step_termination_actions_desc') || 'Lectures i Ordres',
    icon: 'fa6-solid:wrench'
  },
  {
    index: 2,
    number: '3',
    label: t('billing_block.step') + ' 3',
    title: t('contract_block.step_finalize') || 'Finalització',
    description: t('contract_block.step_finalize_desc') || 'Resum i Finalitzar',
    icon: 'fa6-solid:circle-check'
  }
]);

const loading = ref(true);
const isBudget = ref(false)
const editingPerson = ref(false);
const editingBudget = ref(false)
const editingId = ref(null)
const editingChangeStatus = ref(false);
const showRegion = ref(false);
const toggleRegion = (force) => {
  showRegion.value = force !== undefined ? force : !showRegion.value;
  if (!showRegion.value) {
    closeAllRegions()
  }
}

const showRegionDetailComponent = ref(null);
const regionDetailId = ref(null);

const person = ref(null);
const contract = ref(null);

const terminationRequestStatuses = ref([]);
const terminationRequestStatus = ref(null);

const token_draft = ref(null);
const token_pending = ref(null);

const terminationTypes = ref([]);
const terminationType = ref(null);

const ordersRemoveMeter = ref([]);
const ordersReadMeter = ref([]);
const orderStatuses = ref([]);
const orderTypes = ref([]);
const orderTypeReadMeter = ref(null);

const last_reading_values = ref([]);
const supply_point = ref(null);
const supply_point_has_contracts = ref(false)
const statuses = ref([]);
const statusSelected = ref(null);

const supply_points = ref([]);

const previous_readings = ref({});

const getDaysSinceLastReading = (dateString) => {
  if (!dateString) return null;
  const readingDate = new Date(dateString);
  const today = new Date();
  readingDate.setHours(0, 0, 0, 0);
  today.setHours(0, 0, 0, 0);
  const diff = differenceInDays(today, readingDate);
  if (diff === 0) return t('common.today') || 'avui';
  if (diff === 1) return t('common.yesterday') || 'ahir';
  return `fa ${diff} dies`;
}

const loadPreviousReadings = async () => {
  if (!supply_points.value || supply_points.value.length === 0) return;
  for (const sp of supply_points.value) {
    try {
      const contract_ids = [props.request?.contract?.id] || [];
      const response = await $ReadingApiService.getAll('', [], 1, null, false, contract_ids, sp.id);
      if (response && response.results && response.results.length > 0) {
        previous_readings.value[sp.id] = response.results[0];
      } else {
        previous_readings.value[sp.id] = null;
      }
    } catch (error) {
      console.error('Error loading previous reading for supply point:', sp.id, error);
      previous_readings.value[sp.id] = null;
    }
  }
}

watch(() => supply_points.value, async (newVal) => {
  if (newVal && newVal.length > 0) {
    await loadPreviousReadings();
  }
}, { immediate: true, deep: true });

const loadData = async () => {
  try {
    token_draft.value = await $ConfigProjectApiService.get('contract_termination_draft');
    token_pending.value = await $ConfigProjectApiService.get('contract_termination_pending_status');

    const order_types = await $ConfiglistApiService.getAll('order/order-type');
    orderTypes.value = order_types.results;

    const order_statuses = await $ConfiglistApiService.getAll('order/order-status');
    orderStatuses.value = order_statuses.results;
    getOrder()
  } catch (error) {
    console.error('Error loading data:', error);
  }

  if (props.request && props.request.status) {
    terminationRequestStatus.value = props.request.status;
    supply_points.value = props.request.contract.supply_points;
    last_reading_values.value = props.request.contract_last_readings.map(item => ({
      'supply_point': item.supply_point,
      'meter': item.meter,
      'value': item.reading_value || null,
      'date': item.reading_date ? format(new Date(item.reading_date), 'yyyy-MM-dd') : format(new Date(), 'yyyy-MM-dd'),
      'leak_value': item.leak_value || null,
    }));
    /* last_reading_values.value = supply_points.value.map(item => ({
      'supply_point': item.id,
      'value': item.last_reading || null,
      'date': item.last_reading_at ? format(new Date(item.last_reading_at), 'yyyy-MM-dd') : format(new Date(), 'yyyy-MM-dd'),
      'leak_value': item.last_leak_reading || null,
    })); */
  }
  else {
    const defaultStatus = terminationRequestStatuses.value.find(s => s.is_default == true);
    if (defaultStatus) {
      terminationRequestStatus.value = defaultStatus;
    }
  }
  getSupplyPoint();
}

const finalStep = async () => {
  const toast = useToast();

  try {
    if (token_draft.value == terminationRequestStatus.value.token || token_pending.value == terminationRequestStatus.value.token) {
      if (confirm(t("confirmation_text_block.confirm_finalize_request"))) {

        let payload = {
          'status': statusSelected.value.value,
          'status_name': statusSelected.value.name,
        }
        /* for (const supply_point of supply_points.value) {
          //let statusSelected = statuses.value.find(s => s.token === supply_point.status_token) || statuses.value[0];
          if (!(supply_point.distinct_contracts > 1)) {
            let response = await $StatusApiService.save('supply-point', supply_point.id, payload, 'service');
            supply_point.value = response;
          }
        } */

        let response = await $ContractTerminationApiService.close(props.request ? props.request.id : route.query.contract, payload);

        if (response.id) {
          router.push('/contract/contract-terminations');

          toast.success(t("common.correct_finish"), {
            position: "top-right",
            timeout: 5000,
            closeButton: true,
            icon: true,
            hideProgressBar: false,
          });
        }
      }
    } else {
      router.push('/contract/contract-terminations');
    }
  } catch (error) {
    console.error(error);
  }
};

const getStatuses = async () => {
  try {
    let noncontractable_token = null;
    let pending_contract = null;
    try {
      noncontractable_token = localStorage.getItem('supply_point_status_not_contractable_token').replaceAll('"', '');
      pending_contract = localStorage.getItem('supply_point_pending_contract').replaceAll('"', '');
    } catch (error) {
      console.log(error);
    }
    const data = await $StatusApiService.getAll('supply-point-status', 'service')
      .then(response => {
        const statusesArray = response.results;
        return statusesArray.filter(item => {
          if (noncontractable_token && pending_contract) {
            return item.token === noncontractable_token || item.token === pending_contract
          }
          return item
        });
      });

    //save statuses with id as value and name as label
    data.forEach(item => {
      statuses.value.push({
        value: item.id,
        label: item.name
      })
    })

  } catch (error) {
    console.error(error);
  }
};


const closeAllRegions = () => {
  // tanquem tots els components
  editingPerson.value = false;
  editingBudget.value = false
  editingId.value = null
  showRegionDetailComponent.value = null
  regionDetailId.value = null
  isSubRegionOpen.value = false;
  // tanquem region
  showRegion.value = false;
};

const getSupplyPoint = async () => {
  if (!props.request?.contract?.supply_point_default?.id) return;
  try {
    const result = await $SupplyPointApiService.getDetail(props.request.contract.supply_point_default.id);
    supply_point.value = result;
    const distinctContracts = [
      ...new Set(supply_point.value.contracts.map((c) => c.id)),
    ];
    supply_point_has_contracts.value = distinctContracts.length > 1;
    statusSelected.value = statuses.value.find(s => s.token === supply_point.value.status?.token) || statuses.value[0];
  } catch (err) {
    console.log(err);
  } finally {
    loading.value = false;
  }
}


const openPersonForm = () => {
  closeAllRegions();
  editingPerson.value = true;
  showRegion.value = true;
};

const openBudgetForm = async (component, id) => {
  await closeAllRegions();
  showRegionDetailComponent.value = component;
  regionDetailId.value = id;
  showRegion.value = true;
};

const generateWorkOrder = async (type, supply_point_id) => {
  await createOrdersMeter(type, supply_point_id);
  loadData();
};

const createOrdersMeter = async (type, supply_point_id) => {
  const defaultOrderStatus = orderStatuses.value.find(s => s.is_default == true);

  orderTypeReadMeter.value = null;
  if (type === 'remove_meter') {
    const order_type_token = await $ConfigProjectApiService.get('order_type_remove_meter_token');
    orderTypeReadMeter.value = orderTypes.value.find(item => item.token == order_type_token);
  }
  else if (type === 'read_meter') {
    const order_type_token = await $ConfigProjectApiService.get('order_type_read_meter_token');
    orderTypeReadMeter.value = orderTypes.value.find(item => item.token == order_type_token);
  }

  const order_data = {
    token: format(new Date(), 'yyyyMMddHHmmss'),
    contract_termination_request: props.request ? props.request.id : route.query.contract,
    supply_point: supply_point_id,
    type: orderTypeReadMeter.value.id,
    status: defaultOrderStatus.id || orderStatuses.value[0].id,
    requested_at: format(new Date(), 'yyyy-MM-dd HH:mm:ss')
  }

  const order_saved = await $OrderApiService.save(order_data);
  return order_saved;
}

const clickDeleteOrder = async (id) => {
  if (id) {
    await $OrderApiService.deleteItem(id);
    loadData();
  }
}

const getOrder = async () => {
  try {
    const order_response = await $OrderApiService.getFilterContractTermination(props.request ? props.request.id : route.query.contract);
    ordersRemoveMeter.value = order_response.filter(item => item.type.token == 'remove_meter');
    ordersReadMeter.value = order_response.filter(item => item.type.token == 'read_meter');
  } catch (err) {
    error.value = err;
  } finally {
    loading.value = false;
  }
};


const nextStep = async () => {
  await save();

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

    contract.value = props.request?.contract || await $ContractApiService.getDetail(route.query.contract);

    person.value = props.request?.person || contract.value.holder

    terminationTypes.value = []
    let data = [];
    data = await $ConfiglistApiService.getAll('contract/contract-termination-request-type');
    data.results?.forEach(type => {
      terminationTypes.value.push({
        code: type.id,
        label: type.name || type.token
      })
    });

    await fetchConfigData('contract/contract-termination-request-status', terminationRequestStatuses);

    if (props.request?.status) {
      terminationRequestStatus.value = props.request.status;
    }
    if (props.request?.type) {
      terminationType.value = {
        code: props.request.type.id,
        label: props.request.type.name
      }
    }

    if (props.request?.invoices?.length > 0) {
      currentStep.value = 2;
      setUrlStep();
    }

  } catch (error) {
    console.error('Error loading draft:', error);
  }
  loading.value = false;

  loadData()
};

const fetchPerson = async (item) => {
  person.value = item;
  closeAllRegions();
};

const clickGuardarLectura = async (id) => {
  const toast = useToast();
  const save_data = {
    id: contract_request.value.id,
    last_reading: parseInt(last_reading_values.value.find(item => item.supply_point == id).value),
    last_reading_at: last_reading_values.value.find(item => item.supply_point == id).date,
    last_leak_reading: parseInt(last_reading_values.value.find(item => item.supply_point == id).leak_value),
    supply_point_id: id
  }
  try {
    contract_request.value = await $ContractTerminationApiService.save(save_data)
    toast.success(t("billing_block.correct_manual_reading"), {
      position: "top-right",
      timeout: 2500,
      closeButton: true,
      icon: true,
      hideProgressBar: false,
    });
  } catch (error) {
    console.log(error)
  }
}

const updateSelect = async (ev) => {
  statusSelected.value = ev;
};

const moveToStep = (index) => {
  currentStep.value = index;
  setUrlStep();
};

const setUrlStep = () => {

  router.replace({
    query: {
      ...route.query,
      step: currentStep.value + 1
    }
  });

}

const updateType = (e) => {
  terminationType.value = e;
}
const handleClickChangeStatus = () => {
  editingChangeStatus.value = true;
  showRegion.value = true;
}
const handleStatusChanged = () => {
  editingChangeStatus.value = false;
  showRegion.value = false;
  emit('refresh', true)
}


onMounted(async () => {
  objectPermissions.value = await checkPermission($ContractTerminationApiService);
  if (!objectPermissions.value.can_change) {
    toast.error(t('common.no_permissions'));
    return navigateTo('/');
  }
  if (route.query.step) {
    currentStep.value = parseInt(route.query.step) - 1;
    maxStep.value = currentStep.value;
  }
  setUrlStep();
  getData();
  getStatuses();
  if (props.request) {
    contract_request.value = props.request;
    supply_points.value = contract_request.value.contract.supply_points;
    last_reading_values.value = contract_request.value.contract_last_readings.map(item => ({
      'supply_point': item.supply_point,
      'meter': item.meter,
      'value': item.reading_value || null,
      'date': item.reading_date ? format(new Date(item.reading_date), 'yyyy-MM-dd') : format(new Date(), 'yyyy-MM-dd'),
      'leak_value': item.leak_value || null,
    }));
    console.log('last_reading_values.value', last_reading_values.value);

    if (contract_request.value.type != null) {
      maxStep.value = 2;
    }
  }
});

const save = async () => {
  if ((currentStep.value == 0) || (currentStep.value == 1)) {
    const data = {
      id: props.request?.id || 0,
      token: props.request?.token || contract?.value?.token,
      contract: contract.value?.id || props.request?.contract,
      person: person.value?.id || props.request?.person,
      type: terminationType.value?.code || props.request?.type,
      status: terminationRequestStatus.value?.id || props.request?.status,
      requested_at: props.request?.requested_at || format(new Date(), 'yyyy-MM-dd HH:mm:ss'),
    }

    if (data) {
      $ContractTerminationApiService.save(data).then((item_saved) => {
        contract_request.value = { ...item_saved };
        supply_points.value = item_saved.contract.supply_points;
        last_reading_values.value = contract_request.value.contract_last_readings.map(item => ({
          'supply_point': item.supply_point,
          'meter': item.meter,
          'value': item.reading_value || null,
          'date': item.reading_date ? format(new Date(item.reading_date), 'yyyy-MM-dd') : format(new Date(), 'yyyy-MM-dd'),
          'leak_value': item.leak_value || null,
        }));
        if (!save.id && item_saved.id) {
          router.push(`/contract/contract-terminations/edit/${item_saved.id}?step=2`);
        }
      });
    }

    /* for (const supply_point of supply_points.value) {
      let statusSelected = statuses.value.find(s => s.token === supply_point.status_token) || statuses.value[0];
      let payload = {
        'status': statusSelected.value,
        'status_name': statusSelected.name,
      }
      if (!supply_point.distinct_contracts > 1) {
        let response = await $StatusApiService.save('supply-point', supply_point.id, payload, 'service');
        supply_point = response;
      }
    } */
  }
};

const isSubRegionOpen = ref(false);
const handleSubRegionEvent = (event) => {
  isSubRegionOpen.value = event;
}

watch(() => props.request, async () => {
  contract_request.value = props.request;
  await getData();
}, { immediate: true, deep: true });

</script>

<template>
  <div v-if="objectPermissions?.can_change" class="text-base">
    <!-- Header: Status Navigation & Quick Overview -->
    <div class="flex justify-between items-center mb-6 px-1">
      <div class="flex items-center gap-3">
        <h2 class="text-xl font-bold text-gray-800 tracking-tight">
          {{ t('contract_block.termination_wizard_title') || 'Baixa de Contracte' }}: {{ request?.contract?.token }}
        </h2>
        <span class="text-sm text-slate-500 bg-slate-100 px-2.5 py-1 rounded-full font-medium">
          ID: #{{ request?.id }}
        </span>
      </div>
      <div>
        <StatusesNav v-if="terminationRequestStatus" :active="terminationRequestStatus" :statuses="terminationRequestStatuses">
        </StatusesNav>
      </div>
    </div>

    <WizardStatusNav
      :steps="wizardSteps"
      :current-step="currentStep"
      :max-step="maxStep"
      navigable
      lock-future-steps-only
      @step-click="moveToStep"
    />

    <!-- Contingut del Pas Actual -->
    <div v-if="loading">
      <AppLoading :text="$t('common.loading')" />
    </div>
    <div v-else class="border border-gray-300 rounded-b p-4 bg-white">

      <div v-if="currentStep === 0" class="tab-content mb-6">
        <H1 class="mb-4"> {{ $t('contract_block.termination_data') }}</H1>

        <fieldset id="contract__box" v-if="contract" class="mb-3 border px-3 py-2 bg-sky-50">
          <legend class="px-3 font-semibold bg-white shadow">{{ t("contract") }}</legend>
          <ContractDetail :data="contract" :isSubRegion="true" />
        </fieldset>
        <div class="mb-4">
          <label for="person" class="flex text-sm font-medium text-gray-700 mb-3 gap-2">
            <Icon v-show="person" name="fa6-solid:circle-check" class="text-xl text-emerald-600" />
            <Icon v-show="!person" name="fa6-solid:asterisk" class="text-lg text-slate-400" />
            <span>{{ $t('common.requester') }}</span>
          </label>

          <div v-if="person" class="bg-green-100 p-4 rounded relative max-w-xl group">
            <p class="font-semibold">{{ person.full_name }}<br />
              <span class="text-sm text-gray-500">{{ person.token }}</span>
            </p>
            <button @click="openPersonForm"
              class="absolute cursor-pointer shadow-md border text-sm w-8 h-8 bg-white right-3 top-3 rounded-md text-slate-600 opacity-0 transition-all duration-300 group-hover:opacity-100">
              <Icon name="fa6-solid:pencil" />
            </button>
          </div>
          <div v-else class="max-w-xl">
            <ButtonSeleccio @click="openPersonForm">{{ $t('common.select') }} {{ $t('common.requester') }}</ButtonSeleccio>
          </div>
        </div>

        <div class="max-w-xl mb-2">
          <div class="flex">
            <label for="source" class="block text-sm font-medium text-slate-500 mb-2">
              {{ $t('order_block.reason') }}</label>
          </div>
          <v-select class="block w-full mr-2 required" :disabled="terminationTypes.length == 0"
            :model-value="terminationType" @update:modelValue="updateType" :options="terminationTypes" />
        </div>
      </div>

      <div v-if="currentStep === 1" class="tab-content mb-6">
        <fieldset id="ot__box" v-if="contract" class="mb-3 border px-3 py-2 bg-sky-50 w-full grid grid-cols-2 gap-2">
          <legend class="px-3 font-semibold bg-white shadow">{{ t("common.actions") }}</legend>
          <div v-for="supply_point in supply_points" :key="supply_point.id" class="p-2 border-r">
            <div>
              <p class="text-sm text-slate-600">{{ $t('supply_point') }} {{ supply_point.token }}</p>
              <div>
                <div class="my-2">
                <div class="bg-blue-50/70 border-l-4 border-blue-500 p-3.5 rounded-r-xl shadow-sm flex items-center justify-between gap-3">
                  <div class="flex items-center gap-3">
                    <div class="p-2 bg-blue-100/80 rounded-xl text-blue-600">
                      <Icon name="fa6-solid:gauge-high" class="w-5 h-5" />
                    </div>
                    <div>
                      <span class="block text-[10px] uppercase tracking-wider text-blue-600 font-bold mb-0.5">
                        {{ t('billing_block.last_reading') }}
                      </span>
                      <div v-if="previous_readings[supply_point.id]" class="text-base font-extrabold text-slate-800 flex items-baseline gap-1.5 flex-wrap">
                        {{ previous_readings[supply_point.id].reading_value }}
                        <span class="text-xs font-normal text-slate-500">
                          ({{ formatDate(previous_readings[supply_point.id].reading_date) }}) - {{ getDaysSinceLastReading(previous_readings[supply_point.id].reading_date) }}
                        </span>
                      </div>
                      <div v-else class="text-sm font-semibold text-slate-400">
                        {{ t('common.no_records') }}
                      </div>
                      <div v-if="previous_readings[supply_point.id]?.invoice" class="mt-1 flex items-center gap-1 text-xs font-semibold text-amber-700 bg-amber-50 border border-amber-300 rounded px-2 py-0.5 w-fit">
                        <Icon name="fa6-solid:triangle-exclamation" class="text-amber-500" />
                        {{ t('billing_block.last_reading_already_invoiced') || 'La última lectura ja està facturada' }}
                        <span class="font-normal text-amber-600">({{ previous_readings[supply_point.id].invoice.serie_final }})</span>
                      </div>
                      <span class="text-xs text-slate-500 block mt-0.5 font-medium">
                        {{ supply_point.is_telecontrol ? t('informative_block.info_supply_telecontrol') : t('informative_block.info_supply_no_telecontrol') }}
                      </span>
                    </div>
                  </div>
                  <button type="button" @click="openBudgetForm('ReadingDetail', supply_point.id)" class="button-default shadow-sm hover:scale-105 transition-all">
                    <Icon name="fa6-solid:eye" />
                  </button>
                </div>
              </div>
                <div v-if="last_reading_values.find(item => item.supply_point == supply_point.id)"
                  class="border border-orange-300 bg-orange-50/60 rounded-md px-3 pt-2 mb-2">
                <div class="flex items-center gap-2 mb-1">
                  <Icon name="fa6-solid:scissors" class="text-orange-600" />
                  <span class="text-sm font-bold uppercase tracking-wide text-orange-700">{{ t('billing_block.cut_reading') }}</span>
                </div>
                <p class="text-xs text-slate-600 mb-2">{{ t('billing_block.cut_reading_info') }}</p>
                <div class="grid grid-cols-[100px,100px,120px,1fr] gap-4">
                  <div class="mb-2">
                    <label class="block text-sm font-medium text-slate-600 mb-2">{{ t('common.value') }}</label>
                    <input type="text"
                      v-model="last_reading_values.find(item => item.supply_point == supply_point.id).value"
                      class="input" />
                  </div>
                  <div class="mb-2">
                    <label class="block text-sm font-medium text-slate-600 mb-2">{{ t('billing_block.leak') }}</label>
                    <input type="text"
                      v-model="last_reading_values.find(item => item.supply_point == supply_point.id).leak_value"
                      class="input" />
                  </div>
                  <div class="mb-2">
                    <AtomsInputDate
                      v-model="last_reading_values.find(item => item.supply_point == supply_point.id).date"
                      :label="t('common.date')" class="mb-2" />
                  </div>
                  <!-- <div v-if="supply_point.is_telecontrol" class="mb-2">
                    <button @click="updateReading" class="button-primary mt-6">
                      {{ $t('common.update') }} {{ $t('service_block.telecontrol') }}
                    </button>
                  </div> -->
                  <div class="mb-2 flex items-center gap-1 mt-2">
                    <button @click="clickGuardarLectura(supply_point.id)" class="button-primary">
                      {{ $t('billing_block.save_cut_reading') }}</button>

                  </div>
                </div>
                </div>

                <div class="mb-2" v-if="supply_point && !supply_point.is_telecontrol">
                  <div v-if="ordersReadMeter && ordersReadMeter.find(item => item.supply_point.id == supply_point.id)"
                    class="flex items-center justify-between max-w-xl bg-green-100 py-1 px-2 my-2">
                    <OrderTypeDetail :data="ordersReadMeter.find(item => item.supply_point.id == supply_point.id).type"
                      :order="ordersReadMeter.find(item => item.supply_point.id == supply_point.id)"
                      @show-detail="openBudgetForm('OrderRegion', ordersReadMeter.find(item => item.supply_point.id == supply_point.id).id)" />
                    <button
                      @click="clickDeleteOrder(ordersReadMeter.find(item => item.supply_point.id == supply_point.id).id)"
                      class="text-slate-500 ml-2">
                      <Icon name="fa6-solid:trash" />
                    </button>
                  </div>

                  <ButtonOutline v-else class="my-2" @click="generateWorkOrder('read_meter', supply_point.id)">
                    {{ t('common.generate') }} {{ t('common.work_order') }}: {{ t('order_block.meter_reading') }}
                  </ButtonOutline>
                </div>
              </div>


              <!-- <div class="flex justify-between items-center">
                <span class="text-sm text-gray-500">
                  {{ $t('Retirada de comptador') }}
                </span>
              </div> -->

              <div v-if="ordersRemoveMeter && ordersRemoveMeter.find(item => item.supply_point.id == supply_point.id)"
                class="flex items-center justify-between max-w-xl bg-green-100 py-1 px-2 mb-2">
                <OrderTypeDetail :data="ordersRemoveMeter.find(item => item.supply_point.id == supply_point.id).type"
                  :order="ordersRemoveMeter.find(item => item.supply_point.id == supply_point.id)"
                  @show-detail="openBudgetForm('OrderRegion', ordersRemoveMeter.find(item => item.supply_point.id == supply_point.id).id)" />
                <button
                  @click="clickDeleteOrder(ordersRemoveMeter.find(item => item.supply_point.id == supply_point.id).id)"
                  class="text-slate-500 ml-2">
                  <Icon name="fa6-solid:trash" />
                </button>
              </div>
              <ButtonOutline v-else class="my-3" @click="generateWorkOrder('remove_meter', supply_point.id)">{{
                $t('common.generate') }} {{ $t('common.work_order') }}: {{ $t('order_block.remove_meter') }}
              </ButtonOutline>
              <hr class="my-2 border-gray-300">
            </div>

            <div class=" py-4 pr-4 rounded-lg">
              <div>
                <span class="text-sm text-gray-500 " :class="{ 'line-through': supply_point.distinct_contracts > 1 }">
                  {{ $t('service_block.change_supply_status') }}
                </span>
              </div>
              <div v-if="supply_point.distinct_contracts > 1">
                <span class="text-xs text-gray-500 px-5 italic">
                  {{ $t('informative_block.info_supply_more_contracts') }}
                </span>
              </div>
              <div class="grid grid-cols-[auto,1fr] gap-2 items-center">
                <div class="flex items-center justify-between">
                  <AtomsColorBadge :value="supply_point?.status_name" :color="supply_point?.status_color"
                    class="mr-2" />
                  <span class=" pl-3 text-xl text-slate-500 font-black">&rarr;</span>
                </div>
                <v-select :disabled="supply_point.distinct_contracts > 1" :model-value="statusSelected"
                  @update:modelValue="updateSelect($event)" class="ml-4  sm:text-sm" aria-label="Select status"
                  :options="statuses" />
              </div>
            </div>
          </div>

        </fieldset>
      </div>

      <div v-if="currentStep === 2" class="tab-content mb-6">
        <ContractTerminationDetail @clickChangeStatus="handleClickChangeStatus" :termination="contract_request"
          :showQuickFinalize="false" @show-subregion="openBudgetForm" />
      </div>
      <hr />
      <!-- Botons de navegació -->
      <div class="flex justify-between mt-4">
        <button @click="previousStep" :disabled="currentStep === 0"
          class="px-4 py-2 bg-gray-500 text-white rounded hover:bg-gray-600"
          :class="{ 'opacity-0 cursor-not-allowed': currentStep === 0 }">
          &larr;&nbsp; {{ $t('common.previous') }}
        </button>
        <button v-if="currentStep !== steps.length - 1"
          :disabled="(currentStep == 0 && terminationType == null) || (currentStep == 1 && !supply_point_has_contracts && !statusSelected)"
          @click="nextStep"
          class="px-4 py-2 bg-green-500 text-white rounded enabled:hover:bg-green-600 disabled:opacity-70">
          {{ $t('common.next') }} &nbsp;&rarr;
        </button>
        <button v-else :disabled="request?.connection != null" @click="finalStep"
          class="px-4 py-2 bg-green-500 text-white rounded disabled:opacity-50 enabled:hover:bg-green-600 font-bold">
          <Icon name="fa6-solid:circle-check" />&nbsp; {{ $t('common.finish') }}
        </button>
      </div><!-- end contingut botons -->

    </div><!--end contingut pas actual -->

    <!-- Regió Dreta per l'edició/creació -->
    <div role="region" id="right_page"
      class="fixed h-full border-l border-gray-100 top-0 right-0 transition-all duration-500 ease py-2 text-base bg-white w-1/2 z-20 overflow-x-hidden"
      :class="{ 'translate-x-0': showRegion, 'translate-x-[2000px]': !showRegion, 'w-[95%]': isSubRegionOpen, 'w-1/2': !isSubRegionOpen }">
      <div id="region_nav" class="mb-3 px-3">
        <button @click="toggleRegion(false)" class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300">
          <Icon name="fa6-solid:angles-right" class="text-slate-500" />
        </button>
      </div>
      <div class="px-10">
        <ChangeStatus v-if="editingChangeStatus" entity="contract-termination-request"
          parent_entity="connection_termination_request" :id="request?.id" :status="request?.status?.id"
          module="contract" @changed="handleStatusChanged" />
        <PersonSearch v-if="editingPerson" @saved="fetchPerson" />
        <InvoiceView v-if="showRegionDetailComponent == 'InvoiceView'" :id="regionDetailId" />
        <ReadingDetail v-if="showRegionDetailComponent == 'ReadingDetail'" :supply_point_id="regionDetailId"
          :isSubRegion="true" class="mt-10" />
        <OrderRegion v-if="showRegionDetailComponent === 'OrderRegion'" :id="regionDetailId"
          :isSubRegion="isSubRegionOpen" @show-subregion="handleSubRegionEvent" @changed="handleStatusChanged" />
        <AddInvoiceBudget v-if="showRegionDetailComponent == 'AddInvoiceContract'" :object_id="props.request?.id"
          :service="$ContractTerminationApiService" :entity="'contract_termination_request'"
          :persons="props.request?.contract?.holder ? [props.request.contract.holder] : []" @change="emit('refresh', true)" @show-subregion="handleSubRegionEvent" />
      </div>
    </div>
  </div>
</template>