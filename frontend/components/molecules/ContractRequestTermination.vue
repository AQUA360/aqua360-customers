<script setup>
// components/molecules/ContractRequestContract.vue
import _ from 'lodash';
import { format, differenceInDays } from 'date-fns';
import { ref, computed, onMounted, onBeforeUnmount, watch } from 'vue';
import { formatDate } from '~/utils/date';
import { useI18n } from 'vue-i18n';
import { useToast } from 'vue-toastification';
import H1 from '~/components/atoms/H1.vue';
import OrderTypeDetail from '~/components/molecules/OrderTypeDetail.vue';
import ReadingDetail from '../molecules/ReadingDetail.vue';
import MeterDetail from '../molecules/MeterDetail.vue';
import ButtonSeleccio from '../atoms/ButtonSeleccio.vue';
import AddMeters from '../molecules/AddMeters.vue';
import MeterEdit from '../organisms/MeterEdit.vue';
import ContractTerminationRegion from '../organisms/ContractTerminationRegion.vue';
import { checkPermission } from '~/middleware/permission';

const { $ReadingApiService, $ConfiglistApiService, $ConfigProjectApiService, $ContractTerminationApiService, $OrderApiService, $SupplyPointApiService, $MeterApiService, $ContractRequestApiService, $SmartMeteringApiService } = useNuxtApp();
const { t, te } = useI18n();
const toast = useToast();
const props = defineProps({
  request: {
    type: Object,
    required: false
  },
  supply_point: {
    type: Object,
    required: false
  },
  keepSameCode: {
    type: Boolean,
    default: false
  },
  isChangeOfNameRequest: {
    type: Boolean,
    default: false
  },
  billFullPeriod: {
    type: Boolean,
    default: false
  }
});

const emit = defineEmits(['contract-terminated', 'show-subregion', 'on-pending-termination', 'change-sp']);

const loading = ref(true);
const loading_termination = ref(false);
const saving = ref(false);
const last_reading_values = ref([]);
const last_reading_value = ref(props.supply_point.is_telecontrol ? _.random(1000, 9999) : "");
const last_reading_date = ref(format(new Date(), 'yyyy-MM-dd'));
const showRegion = ref(false);
const isSubRegionOpen = ref(false);
// Subregions details
const activeContract = ref(null);

const contractActiveToken = ref(null);
const orderStatuses = ref([]);
const orderTypes = ref([]);
const orderTypeReadMeter = ref(null);
const showInfo = ref(true);

const contracts = ref([]);

const termination_request = ref({});

const selectedMeter = ref(null);
const selectedMeters = ref([]);
const billCutReading = ref(true);

const meterData = ref(null);
const loadingMeterData = ref(false);

const previous_readings = ref({});

// Alguns registres antics guarden el token ('reading_alert_zero') al camp
// alert/alert_notes en lloc del nom llegible; el traduïm igual que StatusesNav.vue.
const translateReadingAlert = (alertStr) => {
  if (!alertStr) return '';
  if (alertStr.startsWith('reading_alert_')) {
    const key = `billing_block.${alertStr}`;
    return te(key) ? t(key) : alertStr;
  }
  return alertStr;
}

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
  const supplyPointsList = termination_request.value?.contract?.supply_points;
  if (!supplyPointsList || supplyPointsList.length === 0) return;
  for (const sp of supplyPointsList) {
    try {
      const response = await $ReadingApiService.getAll('', [], 1, null, false, [], sp.id);
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

watch(() => termination_request.value?.contract?.supply_points, async (newVal) => {
  if (newVal && newVal.length > 0) {
    await loadPreviousReadings();
  }
}, { immediate: true, deep: true });

const fetchMeterData = async () => {
  if (!selectedMeter.value) {
    meterData.value = null;
    return;
  }
  loadingMeterData.value = true;
  try {
    meterData.value = await $MeterApiService.getDetail(selectedMeter.value);
  } catch (error) {
    console.error('Error fetching meter details:', error);
  } finally {
    loadingMeterData.value = false;
  }
}

watch(selectedMeter, fetchMeterData, { immediate: true });
watch(selectedMeter, () => { editingInitialReading.value = false; });

const meterPermissions = ref(null);
const continueWithoutMeter = ref(false); // Comptador fictici (Aforament / Incendis)
const withoutMeter = ref(false);         // Sense comptador
const meter_calibers = ref([]);
const selected_meter_caliber = ref(null);
const loading_calibers = ref(false);

const request_reading = ref(0)
const last_reading = ref(null)
const last_is_initial = ref(false)
// Permet modificar una lectura inicial ja desada (a mà o triada d'entre les del comptador)
const editingInitialReading = ref(false)
const initialReadingLocked = computed(() => last_is_initial.value && !editingInitialReading.value)

const startEditInitialReading = () => {
  request_reading.value = last_reading.value?.reading_value ?? request_reading.value;
  editingInitialReading.value = true;
}

const cancelEditInitialReading = () => {
  request_reading.value = last_reading.value?.reading_value ?? request_reading.value;
  editingInitialReading.value = false;
}

const fetchingSmartMetering = ref({});
const smartMeteringResult = ref({});
const smartMeteringPendingSave = ref({});

const isSmartMeteringSupplyPoint = (supplyPoint) => {
  return Boolean(supplyPoint?.is_telecontrol && supplyPoint?.meter_code);
};

const fetchCutReadingFromSmartMetering = async (supplyPoint) => {
  const readingEntry = last_reading_values.value.find((item) => item.supply_point === supplyPoint.id);
  if (!readingEntry?.date) {
    toast.error(t('billing_block.reading_date'));
    return;
  }

  fetchingSmartMetering.value = {
    ...fetchingSmartMetering.value,
    [supplyPoint.id]: true,
  };
  smartMeteringResult.value = {
    ...smartMeteringResult.value,
    [supplyPoint.id]: null,
  };
  smartMeteringPendingSave.value = {
    ...smartMeteringPendingSave.value,
    [supplyPoint.id]: false,
  };

  try {
    const response = await $SmartMeteringApiService.getMeterReading({
      meter: supplyPoint.meter_code,
      date: readingEntry.date,
      margin: 5,
    });

    if (response?.found && response.reading_value != null) {
      readingEntry.value = response.reading_value;
      if (response.reading_date) {
        readingEntry.date = format(new Date(response.reading_date), 'yyyy-MM-dd');
      }
      smartMeteringResult.value = {
        ...smartMeteringResult.value,
        [supplyPoint.id]: 'found',
      };
      smartMeteringPendingSave.value = {
        ...smartMeteringPendingSave.value,
        [supplyPoint.id]: true,
      };
      toast.success(
        t('billing_block.smart_metering_reading_found', {
          value: response.reading_value,
          date: response.reading_date ? formatDate(response.reading_date) : readingEntry.date,
        })
      );
    } else {
      smartMeteringResult.value = {
        ...smartMeteringResult.value,
        [supplyPoint.id]: 'not_found',
      };
      toast.warning(t('billing_block.smart_metering_reading_not_found'));
    }
  } catch (error) {
    console.error('Error fetching smart metering cut reading:', error);
    smartMeteringResult.value = {
      ...smartMeteringResult.value,
      [supplyPoint.id]: 'error',
    };
    toast.error(error?.data?.error || t('billing_block.smart_metering_fetch_error'));
  } finally {
    fetchingSmartMetering.value = {
      ...fetchingSmartMetering.value,
      [supplyPoint.id]: false,
    };
  }
};

const getMeterPermissions = async () => {
  const data = await checkPermission($MeterApiService);
  meterPermissions.value = data;
}

const getCalibers = async () => {
  loading_calibers.value = true;
  try {
    let calibers = await $ConfiglistApiService.getAll('service/meter-caliber');
    meter_calibers.value = [];
    calibers.results.forEach(caliber => {
      meter_calibers.value.push({
        label: caliber.name,
        code: caliber.id
      })
    });
    selected_meter_caliber.value = meter_calibers.value[0];
  } catch (error) {
    console.error('Error fetching meter calibers:', error);
  }
  loading_calibers.value = false;
}

const saveMeterMode = async (mode) => {
  try {
    await $ContractRequestApiService.updateCaliber({
      id: props.request.id,
      meter_mode: mode,
      requested_meter_caliber: mode === 'fictional' ? (selected_meter_caliber.value?.code ?? null) : null
    });
  } catch (error) {
    console.error('Error saving meter mode:', error);
  }
}

const toggleContinueWithoutMeter = async () => {
  continueWithoutMeter.value = !continueWithoutMeter.value;
  if (continueWithoutMeter.value) {
    withoutMeter.value = false;
    if (meter_calibers.value.length === 0) {
      await getCalibers();
    }
    await saveMeterMode('fictional');
  } else {
    await saveMeterMode('real');
  }
}

const toggleWithoutMeter = async () => {
  withoutMeter.value = !withoutMeter.value;
  if (withoutMeter.value) {
    continueWithoutMeter.value = false;
    await saveMeterMode('none');
  } else {
    await saveMeterMode('real');
  }
}

const handleMeterCaliberChange = async (caliber) => {
  selected_meter_caliber.value = caliber;
  
  try {
    await $ContractRequestApiService.updateCaliber({ id: props.request.id, requested_meter_caliber: caliber?.code });
  } catch (error) {
    console.error('Error updating meter caliber:', error);
  }
}

// Inicialitza/sincronitza last_reading_values a partir de termination_request.value,
// assegurant que sempre hi hagi una entrada per cada supply_point del contracte
// (necessari perquè el template hi fa .find(...).value sense comprovar null).
const syncLastReadingValues = () => {
  const readingsMap = new Map();
  if (termination_request.value?.contract?.last_readings) {
    termination_request.value.contract.last_readings.forEach(item => {
      readingsMap.set(item.supply_point, {
        supply_point: item.supply_point,
        meter: item.meter,
        value: item.reading_value || null,
        leak_value: item.leak_value || null,
        date: item.reading_date ? format(new Date(item.reading_date), 'yyyy-MM-dd') : format(new Date(), 'yyyy-MM-dd'),
      });
    });
  }

  // Ensure all supply points have entries, even if they don't have readings yet
  if (termination_request.value?.contract?.supply_points) {
    termination_request.value.contract.supply_points.forEach(supply_point => {
      if (!readingsMap.has(supply_point.id)) {
        readingsMap.set(supply_point.id, {
          supply_point: supply_point.id,
          meter: supply_point.meter_id || null,
          value: null,
          leak_value: null,
          date: format(new Date(), 'yyyy-MM-dd'),
        });
      }
    });
  }

  last_reading_values.value = Array.from(readingsMap.values());
}

// Funció per carregar les dades de la sol·licitud existent
const loadData = async () => {
  // console.log("last_reading")
  // console.log(props.request.supply_point_default)
  // console.log(last_reading_value.value)
  contracts.value = []
  contractActiveToken.value = await $ConfigProjectApiService.get('contract_active_token');

  // Carreguem els tipus d'ordre i agafem concretament la de llegir comptador
  const order_types = await $ConfiglistApiService.getAll('order/order-type');
  orderTypes.value = order_types.results;
  const order_type_read_meter_token = await $ConfigProjectApiService.get('order_type_read_meter_token');
  orderTypeReadMeter.value = order_types.results.find(item => item.token == order_type_read_meter_token);

  // carreguem els status de orders
  const order_statuses = await $ConfiglistApiService.getAll('order/order-status');
  orderStatuses.value = order_statuses.results;

  // agafem el contracte actiu
  if (props.supply_point && props.supply_point.contracts && props.supply_point.contracts.length > 0) {
    activeContract.value = props.supply_point.contracts.find(item => item.status_token == contractActiveToken.value);
    // if active contract is being terminated or there's no active contract
    if (activeContract.value == null || (activeContract.value && props.request?.contract_termination_requests?.length > 0)) {
      emit('on-pending-termination', false);
    }
  }
  else {
    emit('on-pending-termination', false);
  }

  termination_request.value = props.request?.contract_termination_requests?.length > 0 ? props.request.contract_termination_requests.find(item => item.contract.id == activeContract?.value?.id) : null;

  if (termination_request.value) {
    console.log('termination_request.value', termination_request.value);
    billCutReading.value = termination_request.value.bill_cut_reading || false;
    syncLastReadingValues();
  }

  if (termination_request.value && termination_request.value.last_reading_at) {
    last_reading_value.value = termination_request.value.last_reading;
    last_reading_date.value = format(new Date(termination_request.value.last_reading_at), 'yyyy-MM-dd');
  }
  if (props.supply_point?.contracts) {
    const distinctContractsMap = new Map();
    contracts.value = props.supply_point.contracts.filter((contract) => {
      const contractString = JSON.stringify(contract);
      if (!distinctContractsMap.has(contractString)) {
        distinctContractsMap.set(contractString, true);
        return true;
      }
      return false;
    });
  }

  // Restore meter mode from saved request
  const meterMode = props.request?.meter_mode;
  continueWithoutMeter.value = meterMode === 'fictional';
  withoutMeter.value = meterMode === 'none';
  if (continueWithoutMeter.value && meter_calibers.value.length === 0) {
    await getCalibers();
  }

  console.log('props.supply_point', props.supply_point);
  selectedMeter.value = props.supply_point.meter_id;
  if (selectedMeter.value) {
    selectedMeters.value.push({ id: selectedMeter.value });
    if (props.supply_point.last_meter_reading) {
      last_reading.value = props.supply_point.last_meter_reading;
      request_reading.value = props.supply_point.last_meter_reading.reading_value;
      const lmrContractRequestId = props.supply_point.last_meter_reading.contract_request ?? props.supply_point.last_meter_reading.contract_request_id;
      last_is_initial.value = props.supply_point.last_meter_reading.is_initial && lmrContractRequestId == props.request.id;
    } else {
      last_reading.value = null;
      request_reading.value = 0;
      last_is_initial.value = false;
    }
  }
  fetchTransferableReading();
  await new Promise(resolve => setTimeout(resolve, 500));
  loading.value = false;
}

/* const updateReading = async () => {
  last_reading_value.value += _.random(0, 20);
  last_reading_date.value = format(new Date(), 'yyyy-MM-dd')
} */


const createOrderReadMeter = async (id) => {
  const defaultOrderStatus = orderStatuses.value.find(s => s.is_default == true);
  // creem un order del tipus lectura, si cal després l'usuari l'eliminarà
  const order_data = {
    token: format(new Date(), 'yyyyMMddHHmmss'),
    contract: activeContract.value.id,
    contract_termination_request: termination_request.value.id,
    supply_point: id,
    type: orderTypeReadMeter.value.id,
    status: defaultOrderStatus.id || orderStatuses.value[0].id,
    requested_at: format(new Date(), 'yyyy-MM-dd HH:mm:ss')
  }

  const order_saved = await $OrderApiService.save(order_data);
  return order_saved;
}

// `skipConfirm`: quan la baixa es llança des d'una altra pantalla que ja ha demanat
// confirmació (p. ex. el popover de "Mantenir número de contracte"). Retorna true si s'ha fet.
const terminate = async ({ skipConfirm = false } = {}) => {

  if (!skipConfirm && !confirm(t("confirmation_text_block.confirm_terminate")))
    return false;
  // Disable actions while terminating
  loading_termination.value = true;
  saving.value = true;
  try {

  const types = await $ConfiglistApiService.getAll('contract/contract-termination-request-type');
  const termination_statuses = await $ConfiglistApiService.getAll('contract/contract-termination-request-status');

  const holderChangeTypeToken = await $ConfigProjectApiService.get('termination_type_holder_change');
  const type = types.results.find(t => t.token == holderChangeTypeToken)

  const defaultTerminationStatus = termination_statuses.results.find(s => s.is_default == true);

  const data = {
    token: _.random(10000, 99999),
    contract: activeContract.value.id,
    person: activeContract.value.holder_id,
    type: type.id,
    status: defaultTerminationStatus.id || termination_statuses.results[0].id,
    requested_at: format(new Date(), 'yyyy-MM-dd HH:mm:ss'),
    bill_cut_reading: billCutReading.value
  }

  termination_request.value = await $ContractTerminationApiService.save(data);
  syncLastReadingValues();
  emit('contract-terminated', { contract_termination_request: termination_request.value.id });
  return true;
  } catch (error) {
    console.error('Error terminating contract:', error);
    toast.error(t('contract_block.unexpected_error'));
    return false;
  } finally {
    loading_termination.value = false;
    saving.value = false;
  }
}

// Es pot donar de baixa el contracte actiu des de fora (mateixes condicions que el botó de la card)
const canTerminate = computed(() => activeContract.value != null && termination_request.value == null
  && !loading.value && !loading_termination.value && !saving.value
  && !!(selectedMeter.value || continueWithoutMeter.value || withoutMeter.value));

defineExpose({ terminate, canTerminate, activeContract });

const clickGenerarOrdreLectura = async (id) => {
  saving.value = true;
  try {
    const order_saved = await createOrderReadMeter(id);
    emit('contract-terminated', { contract_termination_request: termination_request.value.id });
  } finally {
    saving.value = false;
  }
}

const clickDeleteOrder = async (id) => {
  if (id) {
    saving.value = true;
    try {
      await $OrderApiService.deleteItem(id);
      emit('contract-terminated', { contract_termination_request: termination_request.value.id });
    } finally {
      saving.value = false;
    }
  }
}

const setMeter = async (meter) => {
  console.log('meter', meter);
  if ((meter.supply_point || meter.supply_point == "") && !meter.is_general) {
    if (!confirm(t("confirmation_text_block.confirm_assign_meter_with_sp"))) return;
  }
  if (meter.id == selectedMeter.value) {
    selectedMeter.value = props.supply_point.meter_id;
    selectedMeters.value = [{ id: props.supply_point.meter_id }];
  } else {
    selectedMeter.value = meter.id;
    selectedMeters.value = [meter];
    last_reading.value = meter.last_reading || null;
    last_is_initial.value = meter.last_reading ? (meter.last_reading.is_initial && (meter.last_reading.contract_request ?? meter.last_reading.contract_request_id) == props.request.id) : false;
    request_reading.value = meter.last_reading ? meter.last_reading.reading_value : 0;
  }
  let save_data = {
    supply_point_id: props.supply_point.id,
    meter_id: selectedMeter.value
  }
  saving.value = true;
  try {
    let response = await $SupplyPointApiService.updateMeter(save_data);
    if (response) {
      emit('change-sp', response);
      toast.success(t("service_block.meter_assign_to_sp"), {
        position: "top-right",
        timeout: 2500,
        closeButton: true,
        icon: true,
        hideProgressBar: false,
      });
    }
  } finally {
    saving.value = false;
  }
}

const handleMeterCreated = async (meter) => {
  const pendingFictionalReading = continueWithoutMeter.value && last_is_initial.value ? request_reading.value : null;

  selectedMeter.value = meter.id;
  selectedMeters.value = [meter];
  last_reading.value = meter.last_reading || null;
  last_is_initial.value = meter.last_reading ? (meter.last_reading.is_initial && meter.last_reading.contract_request == props.request.id) : false;
  request_reading.value = meter.last_reading ? meter.last_reading.reading_value : 0;
  continueWithoutMeter.value = false;
  closeRegion();
  try {
    saving.value = true;
    let save_data = {
      supply_point_id: props.supply_point.id,
      meter_id: meter.id
    }
    let response = await $SupplyPointApiService.updateMeter(save_data);
    if (response) {
      emit('change-sp', response);
      toast.success(t("informative_block.info_created_meter"), {
        position: "top-right",
        timeout: 2500,
        closeButton: true,
        icon: true,
        hideProgressBar: false,
      });
    }
    if (pendingFictionalReading !== null) {
      const reading_response = await $ReadingApiService.saveRequestReading({
        contract_request_id: props.request.id,
        meter_id: meter.id,
        reading_value: pendingFictionalReading,
        meter_mode: 'real',
      });
      if (reading_response) {
        last_reading.value = reading_response.reading;
        last_is_initial.value = true;
        request_reading.value = pendingFictionalReading;
      }
    }
  } catch (error) {
    console.log(error);
  } finally {
    saving.value = false;
  }
}

const clickGuardarLectura = async (id, meter_id) => {
  const reading_entry = last_reading_values.value.find(item => item.meter == meter_id);
  const save_data = {
    id: termination_request.value.id,
    last_reading: reading_entry.value,
    last_reading_at: reading_entry.date,
    last_leak_reading: reading_entry.leak_value || null,
    supply_point_id: id,
    meter_id: meter_id
  }
  console.log('save_data', save_data);
  try {
    saving.value = true;
    termination_request.value = await $ContractTerminationApiService.save(save_data)
    syncLastReadingValues();
    smartMeteringPendingSave.value = {
      ...smartMeteringPendingSave.value,
      [id]: false,
    };
    toast.success(t("billing_block.correct_manual_reading"), {
      position: "top-right",
      timeout: 2500,
      closeButton: true,
      icon: true,
      hideProgressBar: false,
    });

    // "Mantenir número de contracte" + "Passar el consum al nou contracte d'alta": la
    // lectura de tall que s'acaba de desar a la baixa es reaprofita com a lectura inicial
    // del nou contracte (mateix punt de subministrament/comptador), ja que és la que es
    // facturarà al nou contractant.
    if (props.keepSameCode && !billCutReading.value && id == props.supply_point.id) {
      await saveTransferredInitialReading(reading_entry, meter_id);
    }
  } catch (error) {
    console.log(error)
  } finally {
    saving.value = false;
  }

  //emit('contract-terminated', { contract_termination_request: termination_request.value.id });
}

const saveTransferredInitialReading = async (reading_entry, meter_id) => {
  try {
    const save_data = {
      contract_request_id: props.request.id,
      meter_id: meter_id,
      reading_value: reading_entry.value,
      reading_date: reading_entry.date,
      leak_value: reading_entry.leak_value || null,
      meter_mode: 'real',
    }
    const response = await $ReadingApiService.saveRequestReading(save_data);
    if (response) {
      last_reading.value = response.reading;
      last_is_initial.value = true;
      request_reading.value = reading_entry.value;
      emit('change-sp', { ...props.supply_point, last_meter_reading: response.reading });
    }
  } catch (error) {
    console.error('Error transferring reading to new contract as initial reading:', error);
  }
}


// Estat de cada card del resum (check verd = bloc complet).
const meterCardDone = computed(() => !!(selectedMeter.value || continueWithoutMeter.value || withoutMeter.value));
const readingCardDone = computed(() => withoutMeter.value || last_is_initial.value);
const contractCardDone = computed(() => activeContract.value == null || !!termination_request.value);

const showRegionComponent = ref(null);
const regionDetailId = ref(null);

const showDetail = (component, id) => {
  showRegionComponent.value = component;
  regionDetailId.value = id;
  showRegion.value = true;
  if (component === 'CreateMeter') {
    isSubRegionOpen.value = true;
  }
}

const closeRegion = () => {
  showRegionComponent.value = null;
  isSubRegionOpen.value = false;
  regionDetailId.value = null;
  showRegion.value = false;
}

const handleSubRegionEvent = (show) => {
  isSubRegionOpen.value = show;
}

const saveRequestReading = async () => {
  saving.value = true;
  try {
    let save_data = {
      contract_request_id: props.request.id,
      meter_id: selectedMeter.value || null,
      reading_value: request_reading.value,
      meter_mode: continueWithoutMeter.value ? 'fictional' : 'real',
    }
    const response = await $ReadingApiService.saveRequestReading(save_data);
    if (response) {
      last_reading.value = response.reading;
      last_is_initial.value = true;
      editingInitialReading.value = false;
      // Es notifica al component pare perquè actualitzi les seves dades del punt de
      // subministrament (last_meter_reading) i pugui revalidar el pas de finalització.
      emit('change-sp', { ...props.supply_point, last_meter_reading: response.reading });
    }
  } catch (error) {
    console.log(error)
  } finally {
    saving.value = false;
  }
}

// Fa servir una lectura ja entrada al comptador com a lectura inicial de l'alta. Es crea
// una lectura inicial nova amb el mateix valor/data/fuita (la lectura original es manté
// al seu contracte, que encara la pot haver de facturar).
// Caixa de confirmació (en lloc del confirm() del navegador) per marcar una lectura com a
// inicial: mostra les lectures posteriors que passaran a ser del contracte nou
const initialReadingConfirm = ref(null); // { reading, newerReadings, resolve }
const askInitialReadingConfirm = (reading, newerReadings) => new Promise((resolve) => {
  initialReadingConfirm.value = { reading, newerReadings, resolve };
});
const closeInitialReadingConfirm = (accepted) => {
  const pending = initialReadingConfirm.value;
  initialReadingConfirm.value = null;
  pending?.resolve(accepted);
};

const onInitialReadingConfirmKey = (event) => {
  if (event.key === 'Escape') {
    event.preventDefault();
    closeInitialReadingConfirm(false);
  }
};
watch(initialReadingConfirm, (value) => {
  if (value) window.addEventListener('keydown', onInitialReadingConfirmKey);
  else window.removeEventListener('keydown', onInitialReadingConfirmKey);
});
onBeforeUnmount(() => {
  window.removeEventListener('keydown', onInitialReadingConfirmKey);
  if (initialReadingConfirm.value) closeInitialReadingConfirm(false);
});

// `newerReadings`: lectures del comptador posteriors a la triada; passaran a ser del contracte nou
const markAsInitialReading = async (reading, newerReadings = []) => {
  if (!reading || reading.reading_value == null || !selectedMeter.value) return;
  if (!await askInitialReadingConfirm(reading, newerReadings)) return;

  saving.value = true;
  try {
    const response = await $ReadingApiService.saveRequestReading({
      contract_request_id: props.request.id,
      meter_id: selectedMeter.value,
      reading_value: reading.reading_value,
      reading_date: reading.reading_date || null,
      leak_value: reading.leak_value || null,
      meter_mode: 'real',
    });
    if (response) {
      last_reading.value = response.reading;
      last_is_initial.value = true;
      request_reading.value = response.reading.reading_value;
      editingInitialReading.value = false;
      emit('change-sp', { ...props.supply_point, last_meter_reading: response.reading });
      toast.success(t('contract_block.marked_as_initial_reading'));
      if (newerReadings.length > 0) {
        toast.warning(t('contract_block.newer_readings_moved', { count: newerReadings.length }), { timeout: 10000 });
      }
      if (showRegionComponent.value === 'InitialReadingSelect') {
        closeRegion();
      }
    }
  } catch (error) {
    console.error('Error marking reading as initial:', error);
    const backendMessage = error.response?._data?.error || error.data?.error;
    toast.error(backendMessage || t('contract_block.validation_error_fallback'));
  } finally {
    saving.value = false;
  }
}

// "Facturar període complert": si el contracte anterior té una lectura encara no facturada,
// es pot fer servir com a lectura inicial de l'alta (es traspassa d'un contracte a l'altre)
// en lloc de crear-ne una de nova.
const transferable_reading = ref(null);
let transferableReadingRequestId = 0;

const fetchTransferableReading = async () => {
  const requestId = ++transferableReadingRequestId;
  if (!props.billFullPeriod || !selectedMeter.value || continueWithoutMeter.value || withoutMeter.value || last_is_initial.value) {
    transferable_reading.value = null;
    return;
  }
  try {
    const response = await $ReadingApiService.getRequestTransferableReading(props.request.id, props.supply_point.id, selectedMeter.value);
    if (requestId === transferableReadingRequestId) {
      transferable_reading.value = response?.reading || null;
    }
  } catch (error) {
    console.error('Error fetching transferable reading:', error);
    if (requestId === transferableReadingRequestId) {
      transferable_reading.value = null;
    }
  }
}

watch([() => props.billFullPeriod, selectedMeter, last_is_initial, continueWithoutMeter, withoutMeter], fetchTransferableReading);

const useTransferableReading = async () => {
  if (!transferable_reading.value) return;
  if (!confirm(t('confirmation_text_block.confirm_use_transferable_reading'))) return;
  saving.value = true;
  try {
    const response = await $ReadingApiService.transferRequestReading({
      contract_request_id: props.request.id,
      reading_id: transferable_reading.value.id,
    });
    if (response) {
      last_reading.value = response.reading;
      last_is_initial.value = true;
      request_reading.value = response.reading.reading_value;
      transferable_reading.value = null;
      emit('change-sp', { ...props.supply_point, last_meter_reading: response.reading });
    }
  } catch (error) {
    console.error('Error transferring reading as initial reading:', error);
    const backendMessage = error.response?._data?.error || error.data?.error;
    toast.error(backendMessage || t('contract_block.validation_error_fallback'));
    fetchTransferableReading();
  } finally {
    saving.value = false;
  }
}

// onMounted
onMounted(async () => {
  await getMeterPermissions();
  loadData();
});

watch(() => props.supply_point, (newVal, oldVal) => {
  if (newVal.id != oldVal.id) {
    loading.value = true;
    loadData();
  }
});

// Observa canvis en la sol·licitud per recarregar les dades si cal
watch(() => props.request, (newVal) => {
  loadData();
});

watch(billCutReading, async (newVal) => {
  if (termination_request.value) {
    saving.value = true;
    try {
      const data = {
        id: termination_request.value.id,
        bill_cut_reading: newVal
      }
      termination_request.value = await $ContractTerminationApiService.save(data);
      syncLastReadingValues();
    } catch (error) {
      console.error(error);
    } finally {
      saving.value = false;
    }
  }
});

</script>

<template>
  <div id="wrapper" class="text-base">

    <div v-if="loading" class="flex justify-center items-center my-5">
      <Icon name="fa6-solid:spinner" class="animate-spin text-slate-500" />
      <span class="ml-2 font-semibold">{{ $t('common.loading') }}...</span>
    </div>
    <div v-else class="py-1">

      <div class="flex justify-between">
        <!-- <H1 class="mb-3">{{ t('Situació actual') }}:</H1> -->
        <span></span>
        <div v-if="contracts.length > 1 && showInfo"
          class="flex gap-2 text-sm text-yellow-700 bg-yellow-50 rounded-md border border-yellow-700 px-4 py-2 font-semibold w-[400px]">
          <span class="">
            {{ t("informative_block.info_terminate_contracts_request") }}
          </span>
          <button @click="showInfo = false" class="hover:text-yellow-900 text-xl">&times;</button>
        </div>
      </div>
      <!-- Resum de la situació actual en cards -->
      <div class="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-4 items-stretch">

        <!-- Card: Comptador -->
        <section class="flex flex-col bg-white border border-gray-200 rounded-lg shadow-sm overflow-hidden">
          <header class="flex items-center justify-between gap-2 px-4 py-3 border-b border-gray-100 bg-slate-50">
            <div class="flex items-center gap-2 font-semibold text-slate-800">
              <Icon name="fa6-solid:gauge-high" class="text-sky-500" />
              {{ t('meter') }}
            </div>
            <Icon v-if="meterCardDone" name="fa6-solid:circle-check" class="text-emerald-600" />
            <Icon v-else name="fa6-solid:circle-exclamation" class="text-amber-500" />
          </header>

          <div class="flex-1 p-4 flex flex-col gap-3 text-sm">
            <div v-if="withoutMeter" class="flex flex-col gap-1">
              <span class="inline-flex items-center gap-1 w-fit bg-slate-100 text-slate-700 px-2 py-1 rounded border border-slate-200 font-medium">
                <Icon name="fa6-solid:ban" /> {{ t('contract_block.without_meter') }}
              </span>
              <p class="text-slate-500 italic">{{ t('contract_block.without_meter_info') }}</p>
            </div>
            <div v-else-if="continueWithoutMeter" class="flex flex-col gap-2">
              <span class="inline-flex items-center gap-1 w-fit bg-blue-50 text-blue-700 px-2 py-1 rounded border border-blue-100 font-medium">
                <Icon name="my-icon:well-drop-icon" class="w-3 h-3" /> {{ t('contract_block.fictional_meter') }}
              </span>
              <div class="flex items-center gap-2">
                <label class="font-medium text-slate-600 whitespace-nowrap">{{ $t('service_block.caliber') }}:</label>
                <div class="flex-1 min-w-0">
                  <v-select
                    class="required"
                    :disabled="loading_calibers || meter_calibers.length == 0"
                    :model-value="selected_meter_caliber"
                    @update:modelValue="handleMeterCaliberChange"
                    :options="meter_calibers">
                    <template #no-options="{ search, searching, loading }">
                      {{ t('common.no_records') }}
                    </template>
                  </v-select>
                </div>
              </div>
            </div>
            <div v-else-if="selectedMeter" class="flex flex-col gap-1">
              <span class="text-lg font-bold text-slate-800">{{ meterData?.code || supply_point?.meter_code }}</span>
              <span v-if="meterData?.status?.name || supply_point?.meter_status?.name || supply_point?.meter_status"
                class="w-fit bg-gray-50 px-2 py-0.5 rounded border border-gray-200 text-slate-600">
                {{ meterData?.status?.name || supply_point?.meter_status?.name || supply_point?.meter_status }}
              </span>
              <span v-if="selectedMeter != request.supply_point_default.meter_id" class="text-xs text-sky-700 font-medium">
                {{ t('service_block.selected_meter') }}
              </span>
            </div>
            <p v-else class="text-slate-500">{{ t('service_block.no_meter') }}</p>

            <p class="text-xs text-slate-500 truncate" :title="supply_point?.address_complete">
              <Icon name="fa6-solid:street-view" class="mr-1" />{{ supply_point?.address_complete }}
            </p>

            <div v-if="request" class="mt-auto flex flex-wrap gap-2 pt-2">
              <button
                class="button-default"
                :class="{ 'ring-2 ring-sky-500 bg-sky-50': continueWithoutMeter }"
                @click="toggleContinueWithoutMeter"
                :disabled="loading || saving || loading_termination">
                <Icon name="my-icon:well-drop-icon" class="w-3 h-3 mr-1 text-blue-500" />
                {{ t('contract_block.fictional_meter') }}
              </button>
              <button
                class="button-default"
                :class="{ 'ring-2 ring-slate-500 bg-slate-50': withoutMeter }"
                @click="toggleWithoutMeter"
                :disabled="loading || saving || loading_termination">
                <Icon name="fa6-solid:ban" class="mr-1 text-slate-500" />
                {{ t('contract_block.without_meter') }}
              </button>
              <button v-if="meterPermissions?.can_change" class="button-primary" @click="showDetail('CreateMeter', null)" :disabled="loading || saving || loading_termination || continueWithoutMeter">
                {{ t('service_block.new_meter') }}
              </button>
              <button class="button-primary" @click="showDetail('AddMeter', null)" :disabled="loading || saving || loading_termination || continueWithoutMeter">
                {{ selectedMeter ? t('billing_block.change_meter') : (t('common.select') + ' ' + t('meter')) }}
              </button>
            </div>
          </div>

          <footer class="px-4 py-2 border-t border-gray-100 flex justify-end">
            <button type="button" class="text-sm font-semibold text-sky-600 hover:underline" @click="showDetail('MeterInfo', selectedMeter)">
              {{ t('contract_block.more_info') }}
            </button>
          </footer>
        </section>

        <!-- Card: Lectura inicial -->
        <section class="flex flex-col bg-white border rounded-lg shadow-sm overflow-hidden"
          :class="continueWithoutMeter ? 'border-orange-200' : 'border-gray-200'">
          <header class="flex items-center justify-between gap-2 px-4 py-3 border-b border-gray-100"
            :class="continueWithoutMeter ? 'bg-orange-50' : 'bg-slate-50'">
            <div class="flex items-center gap-2 font-semibold text-slate-800">
              <Icon name="fa6-solid:file-pen" :class="continueWithoutMeter ? 'text-orange-500' : 'text-blue-500'" />
              {{ t('contract_block.initial_reading') }}
            </div>
            <Icon v-if="readingCardDone" name="fa6-solid:circle-check" class="text-emerald-600" />
            <Icon v-else name="fa6-solid:circle-exclamation" class="text-amber-500" />
          </header>

          <div class="flex-1 p-4 flex flex-col gap-3 text-sm">
            <p v-if="withoutMeter" class="text-slate-500 italic">{{ t('contract_block.without_meter_info') }}</p>
            <p v-else-if="!selectedMeter && !continueWithoutMeter" class="text-slate-500">{{ t('service_block.no_meter') }}</p>
            <template v-else>
              <div v-if="last_is_initial" class="flex flex-col gap-1">
                <div class="flex items-center gap-2 text-green-700 font-bold flex-wrap">
                  <Icon name="fa6-solid:circle-check" />
                  {{ t('billing_block.initial_reading') }}
                  <span v-if="last_reading" class="text-lg font-bold text-slate-800">{{ last_reading.reading_value }}</span>
                  <span v-if="last_reading?.reading_date" class="font-normal text-slate-500">({{ formatDate(last_reading.reading_date) }})</span>
                </div>
                <div v-if="!editingInitialReading" class="flex flex-wrap items-center gap-2 mt-1">
                  <button type="button" class="button-default-xs" :disabled="loading || saving" @click="startEditInitialReading">
                    <Icon name="fa6-solid:pencil" class="text-slate-500 mr-1" />
                    {{ t('common.edit') }}
                  </button>
                  <button v-if="selectedMeter" type="button" class="text-xs font-semibold text-sky-600 hover:underline"
                    :disabled="loading || saving" @click="showDetail('InitialReadingSelect', selectedMeter)">
                    {{ t('contract_block.choose_existing_reading') }}
                  </button>
                </div>
              </div>
              <div v-else-if="selectedMeter" class="flex flex-col gap-0.5">
                <span class="text-xs uppercase tracking-wide text-slate-500 font-semibold">{{ t("billing_block.last_reading") }}</span>
                <div v-if="last_reading" class="flex items-center gap-x-2 flex-wrap">
                  <span class="text-lg text-slate-800 font-bold">{{ last_reading.reading_value }}</span>
                  <span v-if="last_reading.reading_date" class="text-slate-500">({{ formatDate(last_reading.reading_date) }})</span>
                  <span v-if="last_reading.alert" class="relative inline-flex group">
                    <Icon name="fa6-solid:triangle-exclamation" class="text-red-500 w-4 h-4 cursor-help" />
                    <span
                      class="pointer-events-none absolute bottom-full left-1/2 z-20 mb-2 hidden -translate-x-1/2 whitespace-nowrap rounded bg-slate-800 px-2 py-1 text-xs font-normal text-white shadow-lg group-hover:block">
                      {{ translateReadingAlert(last_reading.alert_notes || last_reading.alert) }}
                    </span>
                  </span>
                </div>
                <div v-else class="text-slate-500">{{ t('common.no_records') }}</div>
                <div class="flex flex-wrap items-center gap-2 mt-1">
                  <button v-if="last_reading && last_reading.reading_value != null" type="button" class="button-default-xs"
                    :disabled="loading || saving" @click="markAsInitialReading(last_reading)">
                    <Icon name="fa6-solid:flag-checkered" class="text-emerald-600 mr-1" />
                    {{ t('contract_block.mark_as_initial_reading') }}
                  </button>
                  <button type="button" class="text-xs font-semibold text-sky-600 hover:underline"
                    :disabled="loading || saving" @click="showDetail('InitialReadingSelect', selectedMeter)">
                    {{ t('contract_block.choose_existing_reading') }}
                  </button>
                </div>
              </div>

              <div v-if="!initialReadingLocked" class="flex items-center gap-2">
                <input
                  type="number"
                  v-model="request_reading"
                  class="input w-full"
                  inputmode="decimal"
                  :disabled="loading || saving"
                  :placeholder="t('reading')"
                />
                <button
                  class="button-primary"
                  @click="saveRequestReading"
                  :disabled="loading || saving"
                >
                  {{ t('common.save') }}
                </button>
                <button v-if="editingInitialReading" type="button" class="button-default"
                  :disabled="loading || saving" @click="cancelEditInitialReading">
                  {{ t('common.cancel') }}
                </button>
              </div>

              <div v-if="transferable_reading && !last_is_initial && !continueWithoutMeter"
                class="flex flex-col md:flex-row md:items-center justify-between gap-2 bg-amber-50 border border-amber-300 rounded-md px-3 py-2 text-sm text-amber-800">
                <div class="flex items-start gap-2">
                  <Icon name="fa6-solid:triangle-exclamation" class="mt-0.5 shrink-0 text-amber-500" />
                  <span>{{ t('contract_block.transferable_reading_warning', {
                    contract: transferable_reading.contract,
                    value: transferable_reading.reading_value,
                    date: formatDate(transferable_reading.reading_date)
                  }) }}</span>
                </div>
                <button type="button" class="button-default shrink-0" @click="useTransferableReading"
                  :disabled="loading || saving">
                  {{ t('contract_block.use_as_initial_reading') }}
                </button>
              </div>

              <div v-if="continueWithoutMeter" class="flex items-start gap-2 bg-orange-100 border border-orange-300 rounded-md px-3 py-2 text-sm text-orange-800">
                <Icon name="fa6-solid:triangle-exclamation" class="mt-0.5 shrink-0 text-orange-500" />
                <span>{{ t('contract_block.fictional_meter_reading_info') }}</span>
              </div>
            </template>
          </div>

          <footer class="px-4 py-2 border-t border-gray-100 flex justify-end">
            <button type="button" class="text-sm font-semibold text-sky-600 hover:underline disabled:text-slate-400 disabled:no-underline"
              :disabled="!selectedMeter" @click="showDetail('ReadingDetail', selectedMeter)">
              {{ t('contract_block.more_info') }}
            </button>
          </footer>
        </section>

        <!-- Card: Contracte actiu -->
        <section class="flex flex-col bg-white border border-gray-200 rounded-lg shadow-sm overflow-hidden">
          <header class="flex items-center justify-between gap-2 px-4 py-3 border-b border-gray-100 bg-slate-50">
            <div class="flex items-center gap-2 font-semibold text-slate-800">
              <Icon name="fa6-solid:file-contract" class="text-sky-500" />
              {{ t('contract_block.active_contract') }}
            </div>
            <Icon v-if="contractCardDone" name="fa6-solid:circle-check" class="text-emerald-600" />
            <Icon v-else name="fa6-solid:circle-exclamation" class="text-amber-500" />
          </header>

          <div class="flex-1 p-4 flex flex-col gap-3 text-sm">
            <template v-if="activeContract == null">
              <p class="text-slate-600">{{ t('contract_block.no_active_contract') }}</p>
              <p v-if="contracts != null && contracts.length == 0" class="text-slate-500 italic">
                {{ t('informative_block.info_supply_not_contracted') }}
              </p>
            </template>
            <template v-else>
              <div class="flex flex-col gap-1">
                <span class="text-lg font-bold text-slate-800">{{ activeContract.token }}</span>
                <span class="text-slate-600">{{ activeContract.holder_full_name }}</span>
              </div>
              <span v-if="termination_request"
                class="inline-flex items-center gap-1 w-fit bg-emerald-50 text-emerald-700 px-2 py-1 rounded border border-emerald-200 font-medium">
                <Icon name="fa6-solid:circle-check" /> {{ t('contract_block.termination_requested') }}
              </span>
              <span v-else
                class="inline-flex items-center gap-1 w-fit bg-amber-50 text-amber-700 px-2 py-1 rounded border border-amber-200 font-medium">
                <Icon name="fa6-solid:triangle-exclamation" /> {{ t('contract_block.pending_termination') }}
              </span>

              <div class="mt-auto pt-2 flex flex-wrap gap-2">
                <button v-if="termination_request == null"
                  :disabled="loading || loading_termination || saving || (!selectedMeter && !continueWithoutMeter && !withoutMeter)"
                  @click="terminate" class="button-primary font-bold">
                  <Icon v-if="loading_termination" name="fa6-solid:spinner" class="animate-spin mr-2" />
                  {{ loading_termination ? $t('common.loading') + '...' : $t('common.terminate') }}
                </button>
                <button v-else class="button-default flex items-center gap-x-2"
                  @click="showDetail('ContractTerminationRegion', termination_request.id)">
                  <Icon name="fa6-solid:eye" class="text-slate-500" />
                  {{ t('contract_termination_request') }}
                </button>
              </div>
            </template>
          </div>

          <footer class="px-4 py-2 border-t border-gray-100 flex justify-end">
            <button type="button" class="text-sm font-semibold text-sky-600 hover:underline disabled:text-slate-400 disabled:no-underline"
              :disabled="!activeContract" @click="showDetail('ActiveContractInfo', activeContract?.id)">
              {{ t('contract_block.more_info') }}
            </button>
          </footer>
        </section>
      </div>

      <!-- Dades de la baixa (lectura de tall i ordres): formulari complet a sota de les cards -->
      <div v-if="activeContract && termination_request" key="termination-container" class="mb-4 w-full">
            <fieldset v-if="isChangeOfNameRequest" class="mb-4 border px-3 py-2 bg-sky-50">
              <legend class="px-3 font-semibold bg-white shadow">{{ t('contract_block.bill_cut_reading_choice_title') }}</legend>
              <div class="flex items-center gap-4">
                <button type="button" role="radio" :aria-checked="billCutReading === true" :disabled="saving"
                  @click="billCutReading = true"
                  class="flex-1 text-left px-4 py-3 rounded-lg border-2 transition-all duration-150"
                  :class="billCutReading === true
                    ? 'border-sky-500 bg-sky-50 ring-1 ring-sky-500'
                    : 'border-gray-200 bg-white hover:border-gray-300'">
                  <div class="flex items-center gap-2">
                    <Icon :name="billCutReading === true ? 'fa6-solid:circle-check' : 'fa6-regular:circle'"
                      :class="billCutReading === true ? 'text-sky-500' : 'text-gray-300'" />
                    <span class="font-semibold text-sm text-gray-800">{{ t('contract_block.bill_cut_reading_to_termination') }}</span>
                  </div>
                </button>
                <button type="button" role="radio" :aria-checked="billCutReading !== true" :disabled="saving"
                  @click="billCutReading = false"
                  class="flex-1 text-left px-4 py-3 rounded-lg border-2 transition-all duration-150"
                  :class="billCutReading !== true
                    ? 'border-sky-500 bg-sky-50 ring-1 ring-sky-500'
                    : 'border-gray-200 bg-white hover:border-gray-300'">
                  <div class="flex items-center gap-2">
                    <Icon :name="billCutReading !== true ? 'fa6-solid:circle-check' : 'fa6-regular:circle'"
                      :class="billCutReading !== true ? 'text-sky-500' : 'text-gray-300'" />
                    <span class="font-semibold text-sm text-gray-800">{{ t('contract_block.bill_cut_reading_to_new_contract') }}</span>
                  </div>
                </button>
              </div>
              <p v-if="!keepSameCode" class="text-sm text-slate-500 italic mt-2">
                {{ billCutReading ? t('informative_block.info_bill_cut_reading_to_termination_holder') : t('informative_block.info_no_bill_cut_reading') }}
              </p>
              <p v-else class="text-sm text-slate-500 italic mt-2">
                {{ t('contract_block.keep_same_code_bill_cut_forced_info') }}
              </p>
            </fieldset>

            <fieldset id="ordre_treball__box" class="mb-3 border px-3 py-2 bg-sky-50 grid grid-cols-2 gap-2">
              <legend class="px-3 font-semibold bg-white shadow">
                <h3>{{ t('billing_block.last_reading') }}</h3>
              </legend>
              <div v-for="supply_point in termination_request.contract.supply_points" :key="supply_point.id"
                class="p-2 border rounded">
                <span class="mb-1">
                  <p class="text-sm text-slate-600">{{ $t('supply_point') }} {{ supply_point.token }}</p>
                </span>

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
                          <span v-if="previous_readings[supply_point.id].alert" class="relative inline-flex group">
                            <Icon name="fa6-solid:triangle-exclamation" class="text-red-500 w-4 h-4 cursor-help" />
                            <span
                              class="pointer-events-none absolute bottom-full left-1/2 z-20 mb-2 hidden -translate-x-1/2 whitespace-nowrap rounded bg-slate-800 px-2 py-1 text-xs font-normal text-white shadow-lg group-hover:block">
                              {{ translateReadingAlert(previous_readings[supply_point.id].alert_notes || previous_readings[supply_point.id].alert) }}
                            </span>
                          </span>
                        </div>
                        <div v-else class="text-sm font-semibold text-slate-400">
                          {{ t('common.no_records') }}
                        </div>
                        <span class="text-xs text-slate-500 block mt-0.5 font-medium">
                          {{ supply_point?.is_telecontrol ? t('informative_block.info_supply_telecontrol') : t('informative_block.info_supply_no_telecontrol') }}
                        </span>
                      </div>
                    </div>
                    <button type="button" @click="showDetail('ReadingDetail', supply_point.meter_id)" class="button-default shadow-sm hover:scale-105 transition-all" :disabled="saving || loading_termination">
                      <Icon name="fa6-solid:eye" />
                    </button>
                  </div>
                </div>

                <div class="border border-orange-300 bg-orange-50/60 rounded-md px-3 pt-2 pb-2 mb-2">
                <div class="flex items-center gap-2 mb-1">
                  <Icon name="fa6-solid:scissors" class="text-orange-600" />
                  <span class="text-sm font-bold uppercase tracking-wide text-orange-700">{{ t('billing_block.cut_reading') }}</span>
                </div>
                <p class="text-xs text-slate-600 mb-2">{{ t('billing_block.cut_reading_info') }}</p>
                <div class="grid grid-cols-[100px,100px,120px,1fr] gap-4">
                  <div class="">
                    <label class="block text-sm font-medium text-slate-600 mb-2">{{ t('common.value') }}</label>
                    <input type="text"
                      v-model="last_reading_values.find(item => item.supply_point == supply_point.id).value"
                      class="input" :disabled="saving || loading_termination" />
                  </div>
                  <div class="mb-2">
                    <label class="block text-sm font-medium text-slate-600 mb-2">{{ t('billing_block.leak') }}</label>
                    <input type="text"
                      v-model="last_reading_values.find(item => item.supply_point == supply_point.id).leak_value"
                      class="input" :disabled="saving || loading_termination" />
                  </div>
                  <div class="">
                    <AtomsInputDate
                      v-model="last_reading_values.find(item => item.supply_point == supply_point.id).date"
                      :label="t('common.date')" class="" />
                  </div>
                  <!-- MAI UTILITZAT I AQUESTES LECTURES SEMPRE SON MANUALS -->
                  <!-- <div v-if="supply_point?.is_telecontrol" class="">
                    <button @click="updateReading" class="button-primary mt-6" :disabled="saving || loading_termination">
                      {{ $t('common.update') }} {{ t('service_block.telecontrol') }}</button>
                  </div> -->
                  <div class="flex flex-col">
                    <div class="flex items-end gap-2 mt-6 flex-wrap">
                      <button @click="clickGuardarLectura(supply_point.id, supply_point.meter_id)"
                        class="button-primary transition-all"
                        :class="smartMeteringPendingSave[supply_point.id]
                          ? 'ring-2 ring-amber-400 ring-offset-2 shadow-md animate-pulse'
                          : ''"
                        :disabled="saving || loading_termination">
                        {{ t('billing_block.save_cut_reading') }}
                      </button>
                      <button
                        v-if="isSmartMeteringSupplyPoint(supply_point)"
                        type="button"
                        @click="fetchCutReadingFromSmartMetering(supply_point)"
                        class="button-default"
                        :disabled="saving || loading_termination || fetchingSmartMetering[supply_point.id]"
                      >
                        <Icon
                          v-if="fetchingSmartMetering[supply_point.id]"
                          name="fa6-solid:spinner"
                          class="animate-spin mr-1"
                        />
                        <Icon v-else name="fa6-solid:satellite-dish" class="mr-1 text-sky-500" />
                        {{ t('billing_block.fetch_cut_reading_smart_metering') }}
                      </button>
                    </div>
                    <div
                      v-if="smartMeteringResult[supply_point.id] === 'found'"
                      class="mt-2"
                    >
                      <p class="text-sm font-medium text-green-700">
                        {{ t('billing_block.smart_metering_reading_found', {
                          value: last_reading_values.find(item => item.supply_point == supply_point.id)?.value,
                          date: formatDate(last_reading_values.find(item => item.supply_point == supply_point.id)?.date)
                        }) }}
                      </p>
                      <p
                        v-if="smartMeteringPendingSave[supply_point.id]"
                        class="mt-1 text-sm font-medium text-amber-700 flex items-start gap-1.5"
                      >
                        <Icon name="fa6-solid:circle-exclamation" class="mt-0.5 shrink-0" />
                        <span>{{ t('billing_block.smart_metering_reading_not_saved') }}</span>
                      </p>
                    </div>
                    <p
                      v-else-if="smartMeteringResult[supply_point.id] === 'not_found'"
                      class="mt-2 text-sm font-medium text-amber-700"
                    >
                      {{ t('billing_block.smart_metering_reading_not_found') }}
                    </p>
                    <p
                      v-else-if="smartMeteringResult[supply_point.id] === 'error'"
                      class="mt-2 text-sm font-medium text-red-700"
                    >
                      {{ t('billing_block.smart_metering_fetch_error') }}
                    </p>
                  </div>
                </div>
                </div>
                <div>

                </div>

                <div class="mb-2" v-if="!supply_point?.is_telecontrol">
                  <hr />
                  <p class="my-2">{{ t('common.work_order') }}:</p>
                  <div
                    v-if="termination_request.orders?.filter(item => item.supply_point_id == supply_point.id).length > 0">
                    <div
                      v-for="order in termination_request.orders?.filter(item => item.supply_point_id == supply_point.id)"
                      class="flex items-center justify-between max-w-xl bg-green-100 py-1 px-2 mb-2">
                      <OrderTypeDetail :data="order.type" />
                      <button @click="clickDeleteOrder(order.id)" class="text-slate-500 ml-2">
                        <Icon name="fa6-solid:trash" />
                      </button>
                    </div>
                  </div>
                  <button v-else @click="clickGenerarOrdreLectura(supply_point.id)" class="button-primary" :disabled="saving || loading_termination">
                    {{ t('common.generate') }} {{ t('common.work_order') }}: {{ t('order_block.meter_reading') }}
                  </button>
                </div>
              </div>
            </fieldset>
      </div>

        <!-- <ContractTerminationEdit /> -->


      <!-- Regió lateral per formularis -->
      <div role="region" id="right_page"
        class="fixed h-full border-l border-gray-100 top-0 right-0 transition-all duration-500 ease py-2 text-base bg-white z-10 overflow-x-hidden"
        :class="{
          'translate-x-0': showRegion,
          'translate-x-full': !showRegion,
          'w-[95%]': isSubRegionOpen,
          'w-1/2': !isSubRegionOpen
        }">
        <div id="region_nav" class="mb-1 px-3">
          <button @click="closeRegion()" class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300">
            <Icon name="fa6-solid:angles-right" class="text-slate-500" />
          </button>
        </div>
        <div class="px-10 pb-10">
          <div v-if="showRegionComponent === 'MeterInfo'">
            <h2 class="text-xl font-semibold mb-4 flex items-center gap-2">
              <Icon name="fa6-solid:gauge-high" class="text-sky-500" />
              {{ t('meter') }}
            </h2>
            <fieldset v-if="selectedMeter && !continueWithoutMeter && !withoutMeter" class="mb-3 border px-3 py-2 bg-sky-50 rounded-md">
              <legend class="px-3 font-semibold bg-white shadow rounded-md">
                {{ selectedMeter == request.supply_point_default.meter_id ?
                  t('service_block.current_meter') : t('service_block.selected_meter') }}
              </legend>
              <MeterDetail :id="selectedMeter" />
            </fieldset>
            <p v-else-if="withoutMeter" class="text-slate-500 italic">{{ t('contract_block.without_meter_info') }}</p>
            <p v-else-if="continueWithoutMeter" class="text-slate-500 italic">{{ t('contract_block.fictional_meter_reading_info') }}</p>
            <p v-else class="text-slate-500">{{ t('service_block.no_meter') }}</p>

            <div v-if="contracts && contracts.length > 0" class="mt-8 border-t pt-6">
              <div class="mb-3">
                <h3 class="text-lg font-semibold text-slate-700 flex items-center gap-2">
                  <Icon name="fa6-solid:clock-rotate-left" class="text-slate-400" />
                  {{ t('contract_block.contracts_history') }}
                </h3>
              </div>

              <div class="my-4 rounded-md border border-gray-300 divide-y bg-white overflow-hidden">
                <div class="group grid grid-cols-[120px,1fr,1fr,1fr] divide-x text-sm leading-4 bg-slate-50 font-medium">
                  <span class="p-3 text-slate-600"> {{ t('common.status') }} </span>
                  <span class="p-3 text-slate-600 flex items-center"> {{ t('common.code') }} </span>
                  <span class="p-3 text-slate-600 flex items-center"> {{ t("contract_block.holder") }} </span>
                  <span class="p-3 text-slate-600 flex items-center"> {{ t("common.creation_date") }} </span>
                </div>
                <div v-for="item in contracts" :key="item.id"
                  class="group grid grid-cols-[120px,1fr,1fr,1fr] divide-x text-sm leading-4 transition-all duration-100 hover:bg-slate-50">
                  <div class="footering text-slate-500 p-2 w-full">
                    <AtomsColorBadge :value="item.status_name" :color="item.status_color" />
                  </div>
                  <div class="footering text-slate-500 p-3 w-full">
                    <span>{{ item.token }}</span>
                  </div>
                  <div class="footering text-slate-500 p-3 w-full">
                    <span>{{ item.holder_full_name }}</span>
                  </div>
                  <div class="footering text-slate-500 p-3 w-full">
                    <span>{{ formatDate(item.created_at) }}</span>
                  </div>
                </div>
              </div>
            </div>
            <div v-else-if="contracts != null" class="mt-8 border-t pt-6">
               <em class="text-slate-500">{{ t('informative_block.info_supply_not_contracted') }}</em>
            </div>
          </div>
          <div v-if="showRegionComponent === 'ActiveContractInfo'">
            <h2 class="text-xl font-semibold mb-4 flex items-center gap-2">
              <Icon name="fa6-solid:file-contract" class="text-sky-500" />
              {{ t('contract_block.active_contract') }}
            </h2>
            <MoleculesContractDetail v-if="regionDetailId" :isSubRegion="true" :id="regionDetailId" />
          </div>
          <ReadingDetail v-if="showRegionComponent == 'ReadingDetail'" :meter_id="regionDetailId" :isSubRegion="true" />
          <div v-if="showRegionComponent === 'InitialReadingSelect'">
            <h2 class="text-xl font-semibold mb-2 flex items-center gap-2">
              <Icon name="fa6-solid:flag-checkered" class="text-emerald-600" />
              {{ t('contract_block.mark_as_initial_reading') }}
            </h2>
            <ReadingDetail :meter_id="regionDetailId" :isSubRegion="true" :selectable-as-initial="true"
              :selecting-disabled="saving" @select-initial="markAsInitialReading" />
          </div>
          <AddMeters v-if="showRegionComponent === 'AddMeter'" :selected_items="selectedMeters" :multiple=false
            :show="true" :all-statuses="true" @item-clicked="setMeter"></AddMeters>
          <MeterEdit v-if="showRegionComponent === 'CreateMeter'" :supply_point="supply_point" :isSubRegion="true"
            @created="handleMeterCreated" />
          <ContractTerminationRegion v-if="showRegionComponent === 'ContractTerminationRegion'" :id="regionDetailId"
            @show-subregion="handleSubRegionEvent" :isSubRegionOpen="isSubRegionOpen" />
        </div>
      </div><!-- /end Regió lateral per formularis -->
    </div>

    <!-- Confirmació de lectura inicial: lectures posteriors que passaran al contracte nou -->
    <Teleport to="body">
      <div v-if="initialReadingConfirm">
        <div class="fixed inset-0 bg-black bg-opacity-50 z-[60]" @click="closeInitialReadingConfirm(false)" />
        <div class="fixed inset-0 z-[70] flex items-center justify-center overflow-y-auto p-4" role="dialog"
          aria-modal="true" @click="closeInitialReadingConfirm(false)">
          <div class="bg-white rounded-lg shadow-xl p-6 w-full relative"
            :class="initialReadingConfirm.newerReadings.length > 0 ? 'max-w-2xl' : 'max-w-md'" @click.stop>
            <button type="button" class="absolute top-4 right-4 text-gray-500 hover:text-gray-700"
              :aria-label="t('common.cancel')" @click="closeInitialReadingConfirm(false)">
              <Icon name="fa6-solid:xmark" class="text-xl" />
            </button>

            <h3 class="text-lg font-bold text-slate-800 mb-3 pr-8 flex items-center gap-2">
              <Icon name="fa6-solid:flag-checkered" class="text-emerald-600" />
              {{ t('contract_block.mark_as_initial_reading') }}
            </h3>

            <div class="flex items-center gap-4 rounded-md border border-emerald-200 bg-emerald-50 px-4 py-3 mb-3">
              <div class="flex flex-col">
                <span class="text-xs uppercase font-semibold text-emerald-700">{{ t('reading') }}</span>
                <span class="text-xl font-bold text-slate-800">{{ parseInt(initialReadingConfirm.reading.reading_value) }}</span>
              </div>
              <div class="flex flex-col">
                <span class="text-xs uppercase font-semibold text-emerald-700">{{ t('common.date') }}</span>
                <span class="text-slate-800">{{ initialReadingConfirm.reading.reading_date ? formatDate(initialReadingConfirm.reading.reading_date) : '-' }}</span>
              </div>
            </div>
            <p class="text-slate-600 text-sm mb-3">
              {{ t('contract_block.confirm_mark_as_initial_reading', {
                value: parseInt(initialReadingConfirm.reading.reading_value),
                date: initialReadingConfirm.reading.reading_date ? formatDate(initialReadingConfirm.reading.reading_date) : '-',
              }) }}
            </p>

            <p v-if="initialReadingConfirm.reading.is_billed"
              class="flex items-start gap-2 text-sm text-sky-800 bg-sky-50 border border-sky-200 rounded-md px-3 py-2 mb-3">
              <Icon name="fa6-solid:copy" class="text-sky-500 mt-0.5 shrink-0" />
              {{ t('contract_block.billed_reading_duplicated_info') }}
            </p>

            <div v-if="initialReadingConfirm.newerReadings.length > 0"
              class="rounded-md border border-amber-200 bg-amber-50 p-3 mb-3">
              <p class="flex items-start gap-2 text-sm font-semibold text-amber-800 mb-1">
                <Icon name="fa6-solid:triangle-exclamation" class="text-amber-500 mt-0.5 shrink-0" />
                {{ t('contract_block.newer_readings_move_warning', { count: initialReadingConfirm.newerReadings.length }) }}
              </p>
              <p class="text-xs text-amber-700 mb-2 ml-6">{{ t('contract_block.older_initial_reading_info') }}</p>
              <div class="max-h-64 overflow-y-auto rounded border border-amber-200 bg-white">
                <table class="min-w-full text-sm text-slate-800">
                  <thead class="sticky top-0 bg-amber-100 text-left">
                    <tr>
                      <th class="px-2 py-1">{{ t('common.date') }}</th>
                      <th class="px-2 py-1">{{ t('reading') }}</th>
                      <th class="px-2 py-1">{{ t('billing_block.consumption') }}</th>
                      <th class="px-2 py-1">{{ t('billing_block.reading_batch') }}</th>
                      <th class="px-2 py-1">{{ t('contract') }}</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="item in initialReadingConfirm.newerReadings" :key="item.id" class="border-t border-amber-100">
                      <td class="px-2 py-1 whitespace-nowrap">{{ item.reading_date ? formatDate(item.reading_date) : '-' }}</td>
                      <td class="px-2 py-1">
                        {{ parseInt(item.reading_value) }}
                        <span v-if="item.is_estimated" class="ml-1 text-xs text-yellow-700">({{ t('billing_block.estimated') }})</span>
                      </td>
                      <td class="px-2 py-1">{{ item.calculated_value != null ? parseInt(item.calculated_value) : '-' }}</td>
                      <td class="px-2 py-1">{{ item.batch ? item.batch.name : '-' }}</td>
                      <td class="px-2 py-1 whitespace-nowrap">
                        <span class="text-slate-500">{{ item.contract?.token || '-' }}</span>
                        <Icon name="fa6-solid:arrow-right" class="mx-1 text-amber-500 text-xs" />
                        <span class="font-semibold text-emerald-700">{{ t('contract_block.new_contract') }}</span>
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>

            <div class="flex justify-end gap-2 mt-4">
              <button type="button" class="button-default" @click="closeInitialReadingConfirm(false)">
                {{ t('common.cancel') }}
              </button>
              <button type="button" class="button-primary font-bold flex items-center gap-2"
                @click="closeInitialReadingConfirm(true)">
                <Icon name="fa6-solid:flag-checkered" />
                {{ t('contract_block.mark_as_initial_short') }}
              </button>
            </div>
          </div>
        </div>
      </div>
    </Teleport>

  </div><!-- /end #wrapper -->
</template>
