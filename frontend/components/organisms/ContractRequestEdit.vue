<script setup>
import { ref, onMounted, computed } from 'vue';
import { add, format } from 'date-fns';
import { checkPermission } from '~/middleware/permission';
import { useToast } from 'vue-toastification';
import ChangeStatus from '~/components/molecules/ChangeStatus.vue';
import ContractRequestSetup from '~/components/molecules/ContractRequestSetup.vue';
import ContractRequestPersons from '~/components/molecules/ContractRequestPersons.vue';
import ContractRequestTermination from '~/components/molecules/ContractRequestTermination.vue';
import WizardStatusNav from '../molecules/WizardStatusNav.vue';
import StatusesNav from '~/components/atoms/StatusesNav.vue';
import ContractRequestAddressPayment from '../molecules/ContractRequestAddressPayment.vue';
import ContractRequestPriceRate from '../molecules/ContractRequestPriceRate.vue';
import ContractRequestOrderBilling from '../molecules/ContractRequestOrderBilling.vue';
import ContractRequestSummary from '../molecules/ContractRequestSummary.vue';
import ContractRequestTypeEditRegion from './ContractRequestTypeEditRegion.vue';
import ContractRequestProductsSupplyPoint from '../molecules/ContractRequestProductsSupplyPoint.vue';
import ContractRequestDocumentationRegion from './ContractRequestDocumentationRegion.vue';
import ContractDocumentsData from '../molecules/ContractDocumentsData.vue';
import H1 from '../atoms/H1.vue';
import AppLoading from '~/components/atoms/AppLoading.vue';
import { useSidebarStore } from '~/stores/useNavSideBar';

const { t } = useI18n()
const sidebarStore = useSidebarStore();
const route = useRoute()
const router = useRouter()
const toast = useToast();
const { $ConfiglistApiService, $ContractRequestApiService, $ContractRequestTypeApiService, $GeneralPaymentApiService, $ConfigProjectApiService, $ContractClausesApiService, $PersonApiService } = useNuxtApp();

const props = defineProps({
  request: Object,
});

const emit = defineEmits(['refresh']);

const objectPermissions = ref(null);

const useMultipleCompanies = ref(false);

const request = ref({}); // <--- ContractRequest object
const activeTab = ref(null);
const steps = ref(['1', '2', '3', '4', '5', '6', '7']);
const currentStep = ref(0);
const maxStep = ref(0);

const wizardSteps = computed(() => [
  {
    index: 0,
    number: '1',
    label: t('billing_block.step') + ' 1',
    title: t('contract_block.step_setup') || 'Configuració',
    description: t('contract_block.request_setup_title') || 'Tipus i Sol·licitant',
    icon: 'fa6-solid:gear'
  },
  {
    index: 1,
    number: '2',
    label: t('billing_block.step') + ' 2',
    title: t('contract_block.step_persons') || 'Persones',
    description: t('contract_block.request_persons_title') || 'Titular, Propietari i Inquilí',
    icon: 'fa6-solid:users'
  },
  {
    index: 2,
    number: '3',
    label: t('billing_block.step') + ' 3',
    title: t('contract_block.step_address_payment') || 'Pagament',
    description: `${t('address_block.addresses')} ${t('common.and')} ${t('billing_block.payment')}`,
    icon: 'fa6-solid:credit-card'
  },
  {
    index: 3,
    number: '4',
    label: t('billing_block.step') + ' 4',
    title: t('contract_block.step_rates') || 'Tarifes',
    description: t('contract_block.request_price_rate_title') || 'Tarifa i Variables',
    icon: 'fa6-solid:tags'
  },
  {
    index: 4,
    number: '5',
    label: t('billing_block.step') + ' 5',
    title: t('contract_block.step_orders_meters') || 'Ordres',
    description: t('contract_block.request_products_supply_point_title') || 'Comptador i Ordres',
    icon: 'fa6-solid:wrench'
  },
  {
    index: 5,
    number: '6',
    label: t('billing_block.step') + ' 6',
    title: t('contract_block.step_termination') || 'Situació actual',
    description: t('contract_block.current_situation') || 'Baixes i Situació actual',
    icon: 'fa6-solid:circle-minus'
  },
  {
    index: 6,
    number: '7',
    label: t('billing_block.step') + ' 7',
    title: t('contract_block.step_finalize') || 'Finalització',
    description: t('contract_block.step_finalize_desc') || 'Resum i Finalitzar',
    icon: 'fa6-solid:circle-check'
  }
]);

const loading = ref(true);
const saving = ref(false);
const stepLoading = ref(false);

const editingChangeStatus = ref(false);
const editingDocumentation = ref(false);
const showDocBar = ref(false);
const editingStepIndex = ref(null);
const editingStepTitle = ref('');
const showRegion = ref(false);
const toggleRegion = (force) => {
  showRegion.value = force !== undefined ? force : !showRegion.value;
  if (!showRegion.value) {
    editingChangeStatus.value = false;
    editingDocumentation.value = false;
    if (editingStepIndex.value !== null) {
      editingStepIndex.value = null;
      editingStepTitle.value = '';
      runValidation();
    }
  }
}

const editStepInRegion = (stepIndex, stepTitle) => {
  editingStepIndex.value = stepIndex;
  editingStepTitle.value = stepTitle;
  editingChangeStatus.value = false;
  editingDocumentation.value = false;
  showRegion.value = true;
};

const saveEditStep = async () => {
  if (editingStepIndex.value !== null) {
    try {
      await saveStep(editingStepIndex.value);
      toast.success(t('common.saved_successfully') || 'Dades desades correctament');
      await runValidation();
    } catch (err) {
      toast.error(t('common.error_saving') || 'Error al desar les dades');
    }
  }
};

const closeEditStep = async () => {
  editingStepIndex.value = null;
  editingStepTitle.value = '';
  showRegion.value = false;
  await runValidation();
};

const handleClickDocumentation = () => {
    editingDocumentation.value = true;
    showRegion.value = true;
}

const handleDocumentationChanged = (updatedRequest) => {
    request.value = updatedRequest;
    loadData();
    emit('refresh', false);
}

const handleDocBarUpdate = (updatedRequest) => {
    request.value = updatedRequest;
    emit('refresh', false);
}

const setupData = ref(null);
const terminationData = ref([]);
const personsData = ref(null);
const addressPaymentData = ref(null);
const pendingTermination = ref(true);
const priceRateAndCategoryData = ref(null);
const orderBillingData = ref(null);
const summaryData = ref(null);
const supplyPoint = ref(null)
const requestType = ref(null)
const usedPayment = ref(null);

const contractRequestStatuses = ref([]);
const contractRequestStatus = ref(null);
const showInfo = ref(true);

// "Canvi de nom": la sol·licitud reutilitza el wizard normal, però en finalitzar-la
// no s'ha de crear un Contract nou, sinó actualitzar el mateix contracte existent
// (mateix número/token), igual que fa una ContractSurrogation. Es detecta pel camp
// persistit `is_change_of_name` del ContractRequest (ja no pel `type`, que pot ser
// null), independentment de si estem creant-la ara mateix o reprenent-ne una ja
// existent des de l'edició.
const isChangeOfNameRequest = computed(() => request.value?.is_change_of_name === true || setupData.value?.is_change_of_name === true);

// "Mantenir el mateix codi de contracte": només vàlid en canvi de nom, i només quan hi ha
// exactament una ContractTerminationRequest vinculada (el backend ho valida i ho rebutja
// si no es compleix aquesta condició).
const keepSameCode = ref(false);
const canKeepSameCode = computed(() => terminationData.value.length === 1);
watch(canKeepSameCode, (canKeep) => {
  if (!canKeep) {
    keepSameCode.value = false;
  }
});

// "Mantenir número de contracte" sempre es pot clicar: si encara no hi ha la baixa del
// contracte vigent, es mostra un popover per donar-lo de baixa. Si es fa la baixa, queda
// seleccionat "Mantenir"; si no, es manté "Crear número de contracte nou".
const terminationRef = ref(null);
const showKeepCodePopover = ref(false);
const keepCodeTerminating = ref(false);
const pendingKeepSameCode = ref(false);
const keepCodeActiveContract = computed(() => terminationRef.value?.activeContract ?? null);
const keepCodeCanTerminate = computed(() => terminationData.value.length === 0 && !!terminationRef.value?.canTerminate);
const keepSameCodeSelected = computed(() => keepSameCode.value === true || showKeepCodePopover.value);

const onKeepSameCodeClick = () => {
  if (canKeepSameCode.value) {
    keepSameCode.value = true;
    return;
  }
  showKeepCodePopover.value = true;
};

const cancelKeepCodePopover = () => {
  if (keepCodeTerminating.value) return;
  showKeepCodePopover.value = false;
  pendingKeepSameCode.value = false;
  keepSameCode.value = false;
};

const terminateToKeepSameCode = async () => {
  if (!keepCodeCanTerminate.value || keepCodeTerminating.value) return;
  keepCodeTerminating.value = true;
  pendingKeepSameCode.value = true;
  try {
    const done = await terminationRef.value.terminate({ skipConfirm: true });
    if (done) {
      // onContractTerminated ja l'haurà aplicat; per si de cas ho reforcem
      if (canKeepSameCode.value) keepSameCode.value = true;
      showKeepCodePopover.value = false;
    }
  } finally {
    pendingKeepSameCode.value = false;
    keepCodeTerminating.value = false;
  }
};

watch(keepSameCode, async (newVal) => {
  if (!request.value?.id || !isChangeOfNameRequest.value) return;
  try {
    const item_saved = await $ContractRequestApiService.save({ id: request.value.id, keep_same_code: newVal });
    request.value = item_saved;
  } catch (error) {
    console.error('Error saving keep_same_code:', error);
    const backendMessage = error.response?._data?.message || error.response?._data?.detail;
    toast.error(backendMessage || t('contract_block.validation_error_fallback'));
  }
});

// "Facturar període complert": la primera factura de l'abonat es factura com un període
// complert (sense prorratejar), en lloc del comportament per defecte.
const billFullPeriod = ref(false);

watch(billFullPeriod, async (newVal) => {
  if (!request.value?.id) return;
  try {
    const item_saved = await $ContractRequestApiService.save({ id: request.value.id, bill_full_period: newVal });
    request.value = item_saved;
  } catch (error) {
    console.error('Error saving bill_full_period:', error);
    const backendMessage = error.response?._data?.message || error.response?._data?.detail;
    toast.error(backendMessage || t('contract_block.validation_error_fallback'));
  }
});

const loadData = async () => {
  const currentRequest = request.value;
  if (currentRequest && currentRequest.status) {
    contractRequestStatus.value = currentRequest.status;
    // Estableix el pas màxim accessible segons el procés que s'ha fet amb la sol·licitud
    if (currentRequest.person || currentRequest.address_street || currentRequest.holder) {
      maxStep.value = 1;
      if (currentRequest.holder) {
        maxStep.value = 2;
        if (currentRequest.address_billing) {
          maxStep.value = 3;
          if (currentRequest.use_type || currentRequest.client_type || currentRequest.category || currentRequest?.price_rates?.length > 0) {
            maxStep.value = 4;
            if (currentRequest?.registration_price_rates?.length > 0) {
              maxStep.value = 5;
              if (currentRequest.contract_file_template || currentRequest.contract_file) {
                maxStep.value = 6;
              }
            }
          }
        }
      }
    }
    //pendingTermination.value = !(request?.value.supply_point_default?.contracts == null || request?.value.supply_point_default?.contracts?.length == 0)
    pendingTermination.value = currentRequest.supply_points.some(item => item.contracts.length > 0)
    if (currentRequest.contract_termination_requests) {
      terminationData.value = currentRequest.contract_termination_requests.map(t => t.id);
    }
    if (typeof currentRequest.keep_same_code === 'boolean') {
      keepSameCode.value = currentRequest.keep_same_code;
    }
    if (typeof currentRequest.bill_full_period === 'boolean') {
      billFullPeriod.value = currentRequest.bill_full_period;
    }

    if (currentStep.value > maxStep.value) {
      maxStep.value = currentStep.value;
    }
  }
  else {
    const defaultStatus = contractRequestStatuses.value.find(s => s.is_default == true);
    if (defaultStatus) {
      contractRequestStatus.value = defaultStatus;
    }
  }

  supplyPoint.value = currentRequest?.supply_point || null
}

watch(() => props.request, (newVal) => {
  if (newVal) {
    request.value = newVal;
    loadData();
  }
}, { immediate: true, deep: true });

const clickFinalDraft = async () => {
  try {
    save();
    await navigateTo('/contract/contract-requests/');
  }
  catch (error) {
    console.error(error);
  }
}

const validationResult = ref({ valid: null, errors: [], warnings: [] });
const isValidating = ref(false);
const showValidationModal = ref(false);
const validationModalErrors = ref([]);

const runValidation = async () => {
  if (!request.value?.id) return;
  isValidating.value = true;
  try {
    const res = await $ContractRequestApiService.validateData(request.value.id);
    let hasInitialReadingErrors = false;
    let hasInitialReadingWarnings = false;
    let errors = res.errors || [];
    const warnings = [];
    if (request.value.meter_mode === 'none') {
      // "Sense comptador": s'ignora l'error del backend que exigeix un comptador assignat.
      errors = errors.filter(err => !String(err).toLowerCase().includes('comptador'));
    }
    if (request.value.supply_points && request.value.supply_points.length > 0) {
      for (const sp of request.value.supply_points) {
        if (sp.meter_id && request.value.meter_mode !== 'none') {
          // El nom del camp que lliga la lectura amb la sol·licitud varia segons l'endpoint
          // que l'ha retornat: `contract_request` (creació de lectura) o `contract_request_id`
          // (detall/guardat de la sol·licitud). Es comproven els dos noms per robustesa.
          const readingContractRequestId = sp.last_meter_reading?.contract_request ?? sp.last_meter_reading?.contract_request_id;
          const hasInitial = sp.last_meter_reading &&
                             sp.last_meter_reading.is_initial &&
                             readingContractRequestId == request.value.id;
          if (!hasInitial) {
            const statusToken = sp.meter_status?.token || sp.meter_status_token || '';
            const statusName = sp.meter_status?.name || sp.meter_status_name || sp.meter_status || '';
            const tokenString = String(statusToken).toLowerCase();
            const nameString = String(statusName).toLowerCase();
            const isNewMeter = tokenString.includes('new') || tokenString.includes('nou') || tokenString.includes('nuevo') ||
                               nameString.includes('new') || nameString.includes('nou') || nameString.includes('nuevo') ||
                               (!sp.last_meter_reading);
            
            if (isNewMeter) {
              hasInitialReadingWarnings = true;
            } else {
              hasInitialReadingErrors = true;
            }
          }
        }
      }
    }
    if (hasInitialReadingErrors) {
      errors.push(t('warning_block.warning_missing_initial_reading'));
    }
    if (hasInitialReadingWarnings) {
      warnings.push(t('warning_block.warning_missing_initial_reading'));
    }
    validationResult.value = {
      valid: res.valid && !hasInitialReadingErrors,
      errors: errors,
      warnings: warnings
    };
  } catch (err) {
    console.error('Validation error:', err);
    validationResult.value = {
      valid: false,
      errors: [t('contract_block.validation_error_fallback') || 'S\'ha produït un error al validar les dades.'],
      warnings: []
    };
  } finally {
    isValidating.value = false;
  }
};

const mapErrorToStep = (errorText) => {
  if (!errorText) return null;
  const err = errorText.toLowerCase();
  
  // Step 1: Setup
  if (err.includes('sol·licitant') || err.includes('solicitante') || err.includes('applicant') || err.includes('tipus de sol·licitud') || err.includes('tipo de solicitud') || err.includes('request type') || err.includes('proveïdora') || err.includes('proveedora') || err.includes('company')) {
    return { index: 0, name: t('contract_block.request_setup_title') || 'Selecció de Tipus, Sol·licitant i Punt de subministrament' };
  }
  
  // Step 3: Address & Payment (evaluated before Step 2 to avoid 'titular de la compta' mapping to Persons step)
  if (err.includes('pagament') || err.includes('pago') || err.includes('payment') || err.includes('iban') || err.includes('banc') || err.includes('bank') || err.includes('adreça') || err.includes('direccio') || err.includes('dirección') || err.includes('address') || err.includes('sepa') || err.includes('compte') || err.includes('compta') || err.includes('cuenta')) {
    return { index: 2, name: `${t('address_block.addresses')} ${t('common.and')} ${t('billing_block.payment')}` };
  }
  
  // Step 2: Persons
  if (err.includes('titular') || err.includes('holder') || err.includes('propietari') || err.includes('propietario') || err.includes('owner') || err.includes('llogater') || err.includes('inquilí') || err.includes('inquilino') || err.includes('tenant') || err.includes('persona')) {
    return { index: 1, name: t('contract_block.request_persons_title') || 'Selecció de Titular, Propietari i Inquilí' };
  }
  
  // Step 4: Price rate & Categories
  if (err.includes('tarifa') || err.includes('price_rate') || err.includes('variable') || err.includes('categoria') || err.includes('category') || err.includes('ús') || err.includes('uso') || err.includes('use') || err.includes('client') || err.includes('cliente')) {
    return { index: 3, name: t('contract_block.request_price_rate_title') || 'Selecció de Tarifa i Variables' };
  }
  
  // Step 5: Order & Billing / meter
  if (err.includes('comptador') || err.includes('contador') || err.includes('meter') || err.includes('boquilla') || err.includes('caliber') || err.includes('calibre') || err.includes('ordre') || err.includes('orden') || err.includes('order')) {
    return { index: 4, name: t('contract_block.request_products_supply_point_title') || 'Alta de Punt de subministrament' };
  }
  
  // Step 6: Termination / Current situation
  if (err.includes('baixa') || err.includes('baja') || err.includes('termination') || err.includes('situació') || err.includes('situacion') || err.includes('lectura') || err.includes('reading')) {
    return { index: 5, name: t('contract_block.current_situation') || 'Situació actual' };
  }
  
  return null;
};

const openValidationErrorsModal = (errors) => {
  validationModalErrors.value = Array.isArray(errors) ? errors : [errors];
  showValidationModal.value = true;
};

watch(currentStep, (newStep) => {
  if (newStep === 6) {
    runValidation();
  }
});

const clickFinalize = async () => {
  try {
    const confirmText = isChangeOfNameRequest.value
      ? (canKeepSameCode.value && keepSameCode.value
        ? t('confirmation_text_block.confirm_change_of_name_finalize')
        : t('confirmation_text_block.confirm_change_of_name_finalize_new_code'))
      : t("confirmation_text_block.confirm_request_finalize");
    if (confirm(confirmText)) {
      let response = isChangeOfNameRequest.value
        ? await $ContractRequestApiService.finalizeInPlace(request.value)
        : await $ContractRequestApiService.finalize(request.value);
      if (response.id) {
        toast.success(t('contract_block.contract_finalized_success') || 'Contracte finalitzat correctament');
        await navigateTo('/contract/contract-requests/?id=' + response.id);
      }
    }
  }
  catch (errorResponse) {
    console.error(errorResponse);
    if (errorResponse.response?.status === 400) {
      const data = errorResponse.response._data;
      openValidationErrorsModal(data.errors || data.message || [t('contract_block.validation_error_fallback')]);
    } else {
      toast.error(t('contract_block.unexpected_error') || 'S\'ha produït un error inesperat');
    }
  }
}

const onSetupChanged = (data) => {
  supplyPoint.value = data.supply_point || null
  requestType.value = data.type || null
  setupData.value = data;
  // save(); // no guardem a aquí, guardem al finalitzar el step
}
const onContractTerminated = async (data) => {
  if (!terminationData.value.includes(data.contract_termination_request)) {
    terminationData.value.push(data.contract_termination_request);
  }
  // Baixa feta des del popover de "Mantenir número de contracte": es selecciona abans de
  // desar perquè el save() ja enviï keep_same_code = true
  if (pendingKeepSameCode.value && canKeepSameCode.value) {
    keepSameCode.value = true;
  }
  await save();
}
const onPendingTermination = (data) => {
  pendingTermination.value = data;
}

const onPersonsChanged = (data) => {
  personsData.value = data;
  // save(); // no guardem a aquí, guardem al finalitzar el step
}



const onAddressPaymentChanged = async (data) => {
  if (!addressPaymentData.value) addressPaymentData.value = {};
  if (!addressPaymentData.value['payment']) addressPaymentData.value['payment'] = {};

  addressPaymentData.value['address_billing'] = data.address_billing;
  addressPaymentData.value['address_contact'] = data.address_contact;
  // Merge previous values with new data
  addressPaymentData.value['payment'] = {
    ...addressPaymentData.value['payment'],
    ...data.payment
  };

  // guardem el payment
  var payment = addressPaymentData.value?.payment || null;
  payment.mandate_token = request.value.token;
  payment.mandate_overwrite = data.mandate_id || null;
  var payment_type = addressPaymentData.value?.payment?.type || null;

  addressPaymentData.value['mandate_id'] = data.mandate_id || null;
  if (payment_type != null) {
    let payment_saved = await $GeneralPaymentApiService.save(payment);
    addressPaymentData.value.payment = payment_saved;
    usedPayment.value = payment_saved;
    addressPaymentData.value['mandate_id'] = addressPaymentData.value?.payment?.mandate_id || null;
  } else {
    usedPayment.value = request.value.payment;
  }

  addressPaymentData.value['remittance_date'] = data.remittance_date;

  // addressPaymentData.value['mandate_id'] = data.mandate_id;

  addressPaymentData.value['communication_type'] = data.communication_type;
  addressPaymentData.value['person_contact_email'] = data.person_contact_email;
  addressPaymentData.value['sms_phones'] = data.sms_phones;
  addressPaymentData.value['contacts'] = data.contacts;

  // save(); // no guardem a aquí, guardem al finalitzar el step
}

const onPriceRateChanged = (data) => {
  priceRateAndCategoryData.value = data;
  // save(); // no guardem a aquí, guardem al finalitzar el step
}

const onOrderBillingChanged = (data) => {
  orderBillingData.value = data;
  // request.value.order_types = data.order_types;

  // save(); // no guardem a aquí, guardem al finalitzar el step
}

const onSummaryChanged = (data) => {
  summaryData.value = data;
  save();
  loadData()
}


const nextStep = async () => {

  const notContractableToken = await $ConfigProjectApiService.get('supply_point_status_not_contractable_token');

  if (currentStep.value == 0 && supplyPoint.value && ((supplyPoint.value.status_token == notContractableToken) || (supplyPoint.value.status && supplyPoint.value.status.token == notContractableToken.token))) {
    confirm(t('warning_block.warning_non_contractable_supply_point'))
    return;
  }

  if (currentStep.value == 5 && pendingTermination.value) {
    if (!confirm(t('informative_block.info_confirm_request_supply_contracts'))) {
      return;
    }
  }

  if (currentStep.value === 0 && useMultipleCompanies.value) {
    const setup = setupData.value;
    if (!setup?.company) {
      toast.error(t('contract_block.company_required'));
      return;
    }
  }

  // Persones a l'habitatge: 0 o negatiu trenca la facturació (divisió per zero)
  if (currentStep.value === 0 && setupData.value?.total_persons_valid === false) {
    toast.error(t('contract_block.total_persons_min'));
    return;
  }

  stepLoading.value = true;
  try {
    await save();
    if (currentStep.value < steps.value.length - 1) {
      currentStep.value++;
    /* if (currentStep.value == 1 &&
      (request?.value.supply_point_default?.contracts == null || request?.value.supply_point_default?.contracts?.length == 0)) {
      currentStep.value++;
    } */
      if (currentStep.value > maxStep.value) {
        maxStep.value = currentStep.value;
      }
      await setUrlStep();
    }
  } catch (error) {
    console.error(error);
    const backendMessage = error.response?._data?.message || error.response?._data?.detail;
    toast.error(backendMessage || t('contract_block.validation_error_fallback') || 'S\'ha produït un error al desar les dades');
  } finally {
    stepLoading.value = false;
  }
};

const previousStep = async () => {
  stepLoading.value = true;
  try {
    await save();
    if (currentStep.value > 0) {
      currentStep.value--;
    }
    await setUrlStep();
  } finally {
    stepLoading.value = false;
  }
};


const moveToStep = async (index) => {
  await save();
  currentStep.value = index;
  await setUrlStep();
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
    await fetchConfigData('contract/contract-request-status', contractRequestStatuses);
  } catch (error) {
    console.error('Error loading draft:', error);
  }
  loading.value = false;

  loadData()
};

const setUrlStep = async () => {
  await router.replace({
    query: {
      ...route.query, // Keep existing query parameters
      step: currentStep.value + 1
    }
  });
  showInfo.value = true;
}

const handleSupplyPointChanged = (data) => {
  let changed_supply_point = request.value.supply_points.find(item => item.id == data.id);
  if (changed_supply_point) {
    changed_supply_point = data;
  }
  // change supply point in request
  request.value.supply_points = request.value.supply_points.map(item => item.id == data.id ? data : item);

  // Es torna a validar sempre que canviï un punt de subministrament (lectura desada o
  // comptador canviat), independentment de si estem al wizard principal (currentStep) o
  // editant el pas "Situació actual" des del panell lateral (editingStepIndex), per
  // desbloquejar el botó "Finalitzar" sense haver de sortir/tornar al pas.
  runValidation();
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
  objectPermissions.value = await checkPermission($ContractRequestApiService);
  if (!objectPermissions.value.can_change) {
    toast.error(t('common.no_permissions'));
    return navigateTo('/');
  }
  try {
    const multi = await $ConfigProjectApiService.get('use_multiple_companies');
    console.log('useMultipleCompanies', multi);
    useMultipleCompanies.value = multi === true || multi === 'True' || multi === 'true';
  } catch {
    useMultipleCompanies.value = false;
  }
  if (props.request) {
    request.value = props.request;
    activeTab.value = request.value.supply_point_default.id;
  }
  if (route.query.step) {
    currentStep.value = parseInt(route.query.step) - 1;
    maxStep.value = currentStep.value;
  }
  setUrlStep();
  getData();
  if (currentStep.value === 6) {
    runValidation();
  }
});

const saveStep = async (stepIndex) => {
  saving.value = true;
  try {
    if (stepIndex == 0) {
      // 1. Setup
      const data = setupData.value;
      if (!data) return;
      if (useMultipleCompanies.value && !data.company) {
        toast.error(t('contract_block.company_required'));
        return;
      }
      if (data.total_persons_valid === false) {
        toast.error(t('contract_block.total_persons_min'));
        return;
      }
      // console.log('save', 'setupData', setupData.value);

      let all_supply_point_ids = data.supply_point_ids;
      if (!all_supply_point_ids.includes(data.supply_point.id)) {
        all_supply_point_ids.push(data.supply_point.id);
      }
      const save = {
        id: request.value?.id || null,
        //token: request.value?.token || format(new Date(), 'yyyyMMddHHmmss'),
        type: data.type,
        person: data.person,
        supply_point_default: data.supply_point.id,
        supply_point_ids: all_supply_point_ids,
        total_persons: data.total_persons,
        bill_cut_reading: data.bill_cut_reading,
        registration_date: data.registration_date,
        language: data.language
      }
      if (data.is_change_of_name) {
        save.is_change_of_name = true;
      }
      if (data.company != null) {
        save.company = data.company;
      }
      if (data.copied_contract_data) {
        save.category = data.copied_contract_data.category;
        save.use_type = data.copied_contract_data.use_type;
        save.client_type = data.copied_contract_data.client_type;
        save.debt_management = data.copied_contract_data.debt_management;
        save.use_general_price_rates = data.copied_contract_data.use_general_price_rates;
        if (data.copied_contract_data.price_rates_ids && save.id) {
          save.price_rates_ids = data.copied_contract_data.price_rates_ids;
        }
      }
      activeTab.value = data.supply_point.id;

      const is_creating = !request.value.id;

      // accions a fer quan es crea un contract_request
      if (is_creating) {
        // status per defecte
        const defaultStatus = contractRequestStatuses.value.find(s => s.is_default == true);
        if (defaultStatus) {
          save.status = defaultStatus.id;
        }
      }

      if (typeof (request.value.holder) == "undefined" || request.value.holder == null) {
        save.holder = data.person;
        //save.holder = await $PersonApiService.getDetail(data.person);
      }

      let item_saved = await $ContractRequestApiService.save(save);
      request.value = item_saved;
      pendingTermination.value = request?.value.supply_points.some(item => item.contracts.length > 0)

      if (is_creating) {
        if (data.copied_contract_data?.price_rates_ids) {
          try {
            const updatePayload = {
              id: item_saved.id,
              price_rates_ids: data.copied_contract_data.price_rates_ids
            };
            item_saved = await $ContractRequestApiService.save(updatePayload);
            request.value = item_saved;
          } catch (err) {
            console.error('Error saving price rates on creation step:', err);
          }
        }
        // En aquest moment, agafem informació del tipus de contracte i li assignem ja al contract_request
        if (item_saved.type && item_saved.type.order_types) {

          // provisional clauses
          for (var i in item_saved.type.clause_templates) {
            var template = item_saved.type.clause_templates[i];
            var save_clause = {
              "token": item_saved.id + '/' + template.token,
              "title": template.title,
              "clause": template.clause,
              "contract_request": item_saved.id,
              "template": template.id
            }
            await $ContractClausesApiService.save(save_clause);
          } // endfor

          // save request provisional data

        }
      }

      if (!save.id && item_saved.id) {
        await navigateTo(`/contract/contract-requests/edit/${item_saved.id}?step=2`)
      }


    }
    else if (stepIndex == 1) {
      // 2. Persons
      // console.log('save', 'step 2', personsData.value);
      if (personsData.value) {

        const save = {
          id: request.value.id,
          holder: personsData.value.holder,
          owner: personsData.value.owner,
          tenant: personsData.value.tenant,
          representatives: personsData.value.representatives,
          cnaes_ids: personsData.value.cnaes,
        }

        await $ContractRequestApiService.save(save).then((item_saved) => {
          request.value = item_saved;
        });
      }
    }

    else if (stepIndex == 2) {
      // 3. Address and Payment
      if (addressPaymentData.value) {
        const save = {
          id: request.value.id,
          address_billing: addressPaymentData.value.address_billing,
          address_contact: addressPaymentData.value.address_contact,
          payment: addressPaymentData.value.payment?.id || null,
          communication_type: addressPaymentData.value.communication_type,
          person_contact_email: addressPaymentData.value.person_contact_email || null,
          sms_phones: addressPaymentData.value.sms_phones || [],
          contacts: addressPaymentData.value.contacts || [],
          remittance_date: addressPaymentData.value.remittance_date || null,
          mandate_id: addressPaymentData.value.mandate_id || null
        }
        const item_saved = await $ContractRequestApiService.save(save)
        request.value = item_saved;
      }
    }

    else if (stepIndex == 3) {
      // 4. Documents, Tarifa i Variables

      if (priceRateAndCategoryData.value) {
        const save = {
          id: request.value.id,
          price_rates_ids: priceRateAndCategoryData.value.price_rates_ids,
          category: priceRateAndCategoryData.value.category,
          use_type: priceRateAndCategoryData.value.use_type,
          client_type: priceRateAndCategoryData.value.client_type,
          use_general_price_rates: priceRateAndCategoryData.value.singlePriceRate,
        }

        const item_saved = await $ContractRequestApiService.save(save)

        request.value = item_saved;
      }
    }


    else if (stepIndex == 4) {
      // 5. Order and Billing
      if (orderBillingData.value) {
        const save = {
          id: request.value.id
        }

        if (orderBillingData.value.order_types) {
          const order_types_ids = orderBillingData.value.order_types.map((item) => item.value).join(',');
          save.order_types = order_types_ids;
        } else {
          save.order_types = "";
        }

        const registration_price_rates_ids = orderBillingData.value.registration_price_rates_ids;
        save.registration_price_rates_ids = registration_price_rates_ids;

        let item_response = await $ContractRequestApiService.save(save);
        request.value = item_response;
      }
    }

    else if (stepIndex == 5) {
      // 6. Baixa de contracte
      const data = {
        id: request.value.id,
        contract_termination_requests: terminationData.value
      }

      if (isChangeOfNameRequest.value) {
        data.keep_same_code = canKeepSameCode.value ? keepSameCode.value : false;
      }

      data.bill_full_period = billFullPeriod.value;

      // Si venim del pas anterior, aprofitem per guardar també les dades de facturació si n'hi ha
      if (orderBillingData.value) {
        data.registration_price_rates_ids = orderBillingData.value.registration_price_rates_ids;
      }

      // Es preserva la lectura inicial que ja coneixem al frontend (desada moments abans via
      // ContractRequestTermination) sempre que estigui lligada a aquesta mateixa sol·licitud.
      // El `last_meter_reading` que retorna aquest guardat reflecteix la darrera lectura
      // "activa" del comptador a nivell global, que pot pertànyer a una altra sol·licitud/
      // contracte diferent (comptador reutilitzat), de manera que no s'hi pot confiar per
      // decidir si la lectura inicial d'AQUESTA sol·licitud ja s'ha desat.
      const previousSupplyPoints = request.value.supply_points;
      const item_saved = await $ContractRequestApiService.save(data)
      if (item_saved.supply_points && previousSupplyPoints) {
        item_saved.supply_points = item_saved.supply_points.map(sp => {
          const prev = previousSupplyPoints.find(p => p.id == sp.id);
          const prevReadingContractRequestId = prev?.last_meter_reading?.contract_request ?? prev?.last_meter_reading?.contract_request_id;
          if (prev?.last_meter_reading?.is_initial && prevReadingContractRequestId == request.value.id) {
            return { ...sp, last_meter_reading: prev.last_meter_reading };
          }
          return sp;
        });
      }
      request.value = item_saved;
      pendingTermination.value = !(request?.value.supply_points.some(item => item.contracts.length == 0) || request?.value.supply_points.some(item => item.contracts == null))
    }

    else if (stepIndex == 6) {
      // 7. Summary
      if (summaryData.value) {
        const save = {
          id: request.value.id
        }

        // const contract_clauses_ids = summaryData.value.clauses.map((item) => item.id).join(',');
        // save.contract_clauses_ids = contract_clauses_ids;
        let item_response = await $ContractRequestApiService.save(save);
        request.value = item_response;
      }
    }
    
    // Ensure maxStep is at least stepIndex to prevent active step being greyed out
    if (stepIndex > maxStep.value) {
      maxStep.value = stepIndex;
    }
  } catch (error) {
    console.error(error);
    throw error;
  } finally {
    saving.value = false;
  }
}

const save = async () => {
  await saveStep(currentStep.value);
} // end save function

</script>

<template>
  <div v-if="objectPermissions?.can_change" class="text-base relative" :class="currentStep >= 2 ? 'pb-14' : ''"  >
    <!-- Header: Status Navigation & Quick Overview -->
    <div class="flex justify-between items-center mb-6 px-1">
      <div class="flex items-center gap-3">
        <h2 class="text-xl font-bold text-gray-800 tracking-tight">
          {{ t('contract_block.contract_registration') }} - {{ request?.token }}
        </h2>
      </div>
      <div>
        <StatusesNav v-if="contractRequestStatus" :active="contractRequestStatus" :statuses="contractRequestStatuses">
        </StatusesNav>
      </div>
    </div>

    <WizardStatusNav
      :steps="wizardSteps"
      :current-step="currentStep"
      :max-step="maxStep"
      :disabled="saving || stepLoading"
      navigable
      line-inset="4%"
      :progress-percent="92"
      step-info-max-width="max-w-[130px]"
      @step-click="moveToStep"
    />

    <!-- Contingut del Pas Actual -->
    <div v-if="loading">
      <AppLoading :text="$t('common.loading')" />
    </div>
    <div v-else class="border border-gray-300 rounded-b p-4 bg-white">

      <div v-if="currentStep === 0" class="tab-content mb-6">
        <ContractRequestSetup :request="request" :require-company="useMultipleCompanies"
          :prefill-contract-id="!request?.id ? route.query.contract_id : null" @change="onSetupChanged" />
      </div>

      <div v-if="currentStep === 1" class="tab-content mb-6">
        <div id="wrapper" class="text-base">
          <!-- Contingut del pas 2 -->
          <ContractRequestPersons :request=request @change="onPersonsChanged" />
        </div>
      </div>

      <div v-if="currentStep === 2" class="tab-content mb-6">
        <div id="wrapper" class="text-base">
          <!-- Contingut del pas 3 -->
          <h2 class="text-xl font-semibold mb-4">
            {{ $t('address_block.addresses') }} {{ $t('common.and') }} {{ $t('billing_block.payment') }}
          </h2>
          <ContractRequestAddressPayment :request=request :usedPayment=usedPayment @change="onAddressPaymentChanged" />
        </div>
      </div>

      <div v-if="currentStep === 3" class="tab-content mb-6">
        <div id="wrapper" class="text-base">
          <!-- Contingut del pas 4 -->
          <ContractRequestPriceRate :request=request @change="onPriceRateChanged" />
        </div>
      </div>

      <div v-if="currentStep === 4" class="tab-content mb-6">
        <div id="wrapper" class="text-base">
          <!-- Contingut del pas 5 -->
          <ContractRequestOrderBilling :request=request @change="onOrderBillingChanged" />
        </div>
      </div>

      <div v-if="currentStep === 5" class="tab-content mb-6">
        <div v-if="request && request.id" id="wrapper" class="text-base">
          <div class="flex justify-between items-center">
            <h2 class="text-xl font-semibold mb-1">{{ t('contract_block.current_situation') }}</h2>
            <div v-if="request.pending_orders.length > 0 && showInfo"
              class="flex justify-between items-center gap-2 text-sm text-orange-700 bg-orange-50 rounded-md border border-orange-700 px-4 py-2 py-1 font-semibold w-[400px]">
              <div>
                <p class="">
                  {{ t("dashboard.pending_orders") }}
                </p>
                <ul class="list-disc list-inside ml-2">
                  <li v-for="order in request.orders.filter(order => request.pending_orders.includes(order.id))"
                    :key="order.id">
                    <span>
                      {{ order.type.name }}
                    </span>
                  </li>
                </ul>
              </div>
              <button @click="showInfo = false" class="hover:text-orange-900 text-xl">&times;</button>
            </div>
          </div>

          <fieldset v-if="isChangeOfNameRequest" class="mb-4 border px-4 py-3 bg-sky-50 rounded-md">
            <legend class="px-3 font-semibold bg-white shadow rounded-md">{{ t('contract_block.keep_same_code_title') }}</legend>
            <div class="flex items-center gap-4">
              <div class="relative flex-1">
                <button type="button" role="radio" :aria-checked="keepSameCodeSelected" @click="onKeepSameCodeClick"
                  class="w-full text-left px-4 py-3 rounded-lg border-2 transition-all duration-150"
                  :class="keepSameCodeSelected
                    ? 'border-sky-500 bg-sky-50 ring-1 ring-sky-500'
                    : 'border-gray-200 bg-white hover:border-gray-300'">
                  <div class="flex items-center gap-2">
                    <Icon :name="keepSameCodeSelected ? 'fa6-solid:circle-check' : 'fa6-regular:circle'"
                      :class="keepSameCodeSelected ? 'text-sky-500' : 'text-gray-300'" />
                    <span class="font-semibold text-sm text-gray-800">{{ t('contract_block.keep_same_code_option') }}</span>
                  </div>
                </button>

                <!-- Popover: cal donar de baixa el contracte vigent per poder mantenir el número -->
                <template v-if="showKeepCodePopover">
                  <div class="fixed inset-0 z-30" @click="cancelKeepCodePopover"></div>
                  <div role="dialog"
                    class="absolute left-0 top-full mt-2 z-40 w-full min-w-[18rem] max-w-md bg-white border border-amber-200 rounded-lg shadow-xl p-4 text-sm">
                    <div class="absolute -top-2 left-6 w-4 h-4 bg-white border-l border-t border-amber-200 rotate-45"></div>
                    <div class="flex items-start gap-2">
                      <Icon name="fa6-solid:triangle-exclamation" class="text-amber-500 mt-0.5 shrink-0" />
                      <div class="flex flex-col gap-1">
                        <span class="font-semibold text-slate-800">{{ t('contract_block.keep_same_code_requires_termination') }}</span>
                        <span v-if="terminationData.length > 1" class="text-slate-600">
                          {{ t('contract_block.keep_same_code_disabled_info') }}
                        </span>
                        <template v-else>
                          <span v-if="keepCodeActiveContract" class="text-slate-600">
                            {{ t('contract_block.keep_same_code_terminate_info', { contract: keepCodeActiveContract.token, holder: keepCodeActiveContract.holder_full_name || '' }) }}
                          </span>
                          <span v-else class="text-slate-600">{{ t('contract_block.no_active_contract') }}</span>
                          <span v-if="keepCodeActiveContract && !keepCodeCanTerminate && !keepCodeTerminating"
                            class="text-slate-500 italic">
                            {{ t('contract_block.keep_same_code_terminate_unavailable') }}
                          </span>
                        </template>
                      </div>
                    </div>
                    <div class="flex justify-end gap-2 mt-3">
                      <button type="button" class="button-default" :disabled="keepCodeTerminating"
                        @click="cancelKeepCodePopover">
                        {{ t('common.cancel') }}
                      </button>
                      <button v-if="terminationData.length <= 1 && keepCodeActiveContract" type="button"
                        class="button-primary font-bold flex items-center gap-2"
                        :disabled="!keepCodeCanTerminate || keepCodeTerminating" @click="terminateToKeepSameCode">
                        <Icon v-if="keepCodeTerminating" name="fa6-solid:spinner" class="animate-spin" />
                        {{ t('contract_block.terminate_current_contract') }}
                      </button>
                    </div>
                  </div>
                </template>
              </div>
              <button type="button" role="radio" :aria-checked="!keepSameCodeSelected"
                @click="showKeepCodePopover ? cancelKeepCodePopover() : (keepSameCode = false)"
                class="flex-1 text-left px-4 py-3 rounded-lg border-2 transition-all duration-150"
                :class="!keepSameCodeSelected
                  ? 'border-sky-500 bg-sky-50 ring-1 ring-sky-500'
                  : 'border-gray-200 bg-white hover:border-gray-300'">
                <div class="flex items-center gap-2">
                  <Icon :name="!keepSameCodeSelected ? 'fa6-solid:circle-check' : 'fa6-regular:circle'"
                    :class="!keepSameCodeSelected ? 'text-sky-500' : 'text-gray-300'" />
                  <span class="font-semibold text-sm text-gray-800">{{ t('contract_block.new_code_option') }}</span>
                </div>
              </button>
            </div>
            <p v-if="terminationData.length > 1" class="text-sm text-slate-500 italic mt-2">
              {{ t('contract_block.keep_same_code_disabled_info') }}
            </p>
          </fieldset>

          <label class="flex items-center gap-2 mb-4 text-sm font-medium text-gray-700">
            <input v-model="billFullPeriod" type="checkbox" id="billFullPeriod" name="billFullPeriod" class="checkbox" />
            {{ t('contract_block.bill_full_period') }}
          </label>

          <AtomsTabs>
            <li v-for="supply_point in request.supply_points" :key="supply_point.id">
              <!-- <ContractRequestTermination
                :supply_point="supply_point" @on-pending-termination="onPendingTermination"
                @contract-terminated="onContractTerminated" /> -->
              <a href="#tab_termination" @click.prevent="activeTab = supply_point.id"
                :class="{ 'text-sky-600 border-sky-600': activeTab === supply_point.id, 'hover:text-gray-600 hover:border-gray-300': activeTab !== supply_point.id }">
                <Icon name="fa6-solid:street-view" class="display-inline mr-2" />
                {{ supply_point.token }} - {{ supply_point.address_complete }}
              </a>
            </li>
          </AtomsTabs>
          <div v-if="activeTab">
            <ContractRequestTermination ref="terminationRef" :request="request"
              :supply_point="request.supply_points.find(item => item.id == activeTab)"
              :keep-same-code="isChangeOfNameRequest && canKeepSameCode && keepSameCode"
              :is-change-of-name-request="isChangeOfNameRequest"
              :bill-full-period="billFullPeriod"
              @on-pending-termination="onPendingTermination" @contract-terminated="onContractTerminated"
              @change-sp="handleSupplyPointChanged" />
          </div>
        </div>
        <div v-else>
          <AppLoading :text="$t('common.loading')" />
        </div>
      </div>

      <div v-if="currentStep === 6" class="tab-content mb-6">
        <div id="wrapper" class="text-base">
          <!-- Banner informatiu "Canvi de nom": només es mostra quan s'ha triat "Mantenir número
               de contracte", ja que és l'única opció on no es crearà cap contracte nou -->
          <div v-if="isChangeOfNameRequest && canKeepSameCode && keepSameCode" class="mb-4 p-4 border border-sky-200 bg-sky-50 text-sky-800 rounded-lg flex items-center gap-3">
            <Icon name="fa6-solid:id-card" class="text-sky-500 text-lg" />
            <span>{{ t('contract_block.change_of_name_finalize_info') }}</span>
          </div>

          <!-- Banner de validació premium -->
          <div v-if="isValidating" class="mb-4 p-4 border border-blue-200 bg-blue-50 text-blue-800 rounded-lg flex items-center gap-3">
            <Icon name="fa6-solid:spinner" class="animate-spin text-lg" />
            <span>{{ t('common.validating_data') || 'Validant les dades de la sol·licitud...' }}</span>
          </div>
          
          <!-- Warnings block -->
          <div v-if="!isValidating && validationResult.warnings && validationResult.warnings.length > 0" class="mb-4 p-4 border border-amber-200 bg-amber-50 text-amber-800 rounded-lg">
            <div class="flex items-center gap-3 mb-2">
              <Icon name="fa6-solid:circle-exclamation" class="text-amber-500 text-lg" />
              <h4 class="font-bold">{{ t('common.warning') || 'Avís' }}</h4>
            </div>
            <ul class="space-y-2 text-sm pl-2">
              <li v-for="warn in validationResult.warnings" :key="warn" class="flex flex-wrap items-center justify-between gap-2 pb-1.5 border-b border-amber-200/30 last:border-0 last:pb-0">
                <span class="flex-grow">{{ warn }}</span>
                <span v-if="mapErrorToStep(warn)" class="inline-flex gap-2">
                  <button 
                    @click="editStepInRegion(mapErrorToStep(warn).index, mapErrorToStep(warn).name)"
                    class="px-2.5 py-1 bg-blue-100 hover:bg-blue-200 text-blue-800 text-xs font-semibold rounded border border-blue-200 flex items-center gap-1.5 transition-all duration-150 active:scale-95"
                    title="Modificar en panell lateral"
                  >
                    <Icon name="fa6-solid:pen-to-square" class="text-[10px]" />
                    {{ t('common.edit') || 'Modificar' }}
                  </button>
                  <button 
                    @click="moveToStep(mapErrorToStep(warn).index)"
                    class="px-2.5 py-1 bg-amber-100 hover:bg-amber-200 text-amber-800 text-xs font-semibold rounded border border-amber-200 flex items-center gap-1.5 transition-all duration-150 active:scale-95"
                    title="Anar al pas corresponent"
                  >
                    <Icon name="fa6-solid:circle-arrow-right" class="text-[10px]" />
                    {{ mapErrorToStep(warn).name }}
                  </button>
                </span>
              </li>
            </ul>
          </div>

          <div v-if="!isValidating && validationResult.valid === true" class="mb-4 p-4 border border-emerald-200 bg-emerald-50 text-emerald-800 rounded-lg flex items-center gap-3">
            <Icon name="fa6-solid:circle-check" class="text-emerald-500 text-lg" />
            <div>
              <h4 class="font-bold">{{ t('contract_block.validation_success_title') }}</h4>
              <p class="text-sm">{{ t('contract_block.validation_success_msg') }}</p>
            </div>
          </div>
          <div v-else-if="validationResult.valid === false" class="mb-4 p-4 border border-red-200 bg-red-50 text-red-800 rounded-lg">
            <div class="flex items-center gap-3 mb-2">
              <Icon name="fa6-solid:circle-exclamation" class="text-red-500 text-lg" />
              <h4 class="font-bold">{{ t('contract_block.validation_error_title') }}</h4>
            </div>
            <p class="text-sm mb-2">{{ t('contract_block.validation_error_msg') }}</p>
            <ul class="space-y-2 text-sm pl-2">
              <li v-for="err in validationResult.errors" :key="err" class="flex flex-wrap items-center justify-between gap-2 pb-1.5 border-b border-red-200/30 last:border-0 last:pb-0">
                <span class="flex-grow">{{ err }}</span>
                <span v-if="mapErrorToStep(err)" class="inline-flex gap-2">
                  <button 
                    @click="editStepInRegion(mapErrorToStep(err).index, mapErrorToStep(err).name)"
                    class="px-2.5 py-1 bg-blue-100 hover:bg-blue-200 text-blue-800 text-xs font-semibold rounded border border-blue-200 flex items-center gap-1.5 transition-all duration-150 active:scale-95"
                    title="Modificar en panell lateral"
                  >
                    <Icon name="fa6-solid:pen-to-square" class="text-[10px]" />
                    {{ t('common.edit') || 'Modificar' }}
                  </button>
                  <button 
                    @click="moveToStep(mapErrorToStep(err).index)"
                    class="px-2.5 py-1 bg-red-100 hover:bg-red-200 text-red-800 text-xs font-semibold rounded border border-red-200 flex items-center gap-1.5 transition-all duration-150 active:scale-95"
                    title="Anar al pas corresponent"
                  >
                    <Icon name="fa6-solid:circle-arrow-right" class="text-[10px]" />
                    {{ mapErrorToStep(err).name }}
                  </button>
                </span>
              </li>
            </ul>
          </div>

          <!-- Contingut del pas 7 -->
          <ContractRequestSummary :request=request @change="onSummaryChanged" />
        </div>
      </div>

      <hr />
      <!-- Botons de navegació -->
      <div class="flex justify-between mt-4">
        <button @click="previousStep" :disabled="currentStep === 0 || saving || stepLoading"
          class="px-4 py-2 bg-gray-500 text-white rounded hover:bg-gray-600"
          :class="{ 'opacity-0 cursor-not-allowed': currentStep === 0 }">
          &larr;&nbsp; {{ $t('common.previous') }}
        </button>
        <!-- Documentation Button for steps >= 2 (Step 3) -->
        <button v-if="currentStep >= 2 && request?.type?.documentation_types?.length > 0" @click="handleClickDocumentation" :disabled="saving || stepLoading"
          class="px-4 py-2 bg-slate-50 text-slate-700 border border-slate-300 rounded hover:bg-slate-100 flex items-center gap-2">
          <Icon name="fa6-solid:file-circle-plus" /> {{ $t('common.add_documentation') }}
        </button>
        <button v-if="currentStep !== steps.length - 1" @click="nextStep"
          :disabled="(currentStep == 0 && (supplyPoint == null || requestType == null)) || saving || stepLoading"
          class="px-4 py-2 bg-green-500 text-white rounded enabled:hover:bg-green-600 disabled:opacity-70">
          <span v-if="saving || stepLoading" class="inline-block mr-2">
            <Icon name="fa6-solid:spinner" class="w-4 h-4 animate-spin" />
          </span>
          {{ $t('common.next') }} &nbsp;<span v-if="!saving && !stepLoading">&rarr;</span>
        </button>
        <div v-else class="flex gap-3">
          <button @click="clickFinalDraft" :disabled="saving"
            class="px-4 py-2 bg-gray-500 text-white rounded disabled:opacity-50 enabled:hover:bg-gray-600 font-bold flex items-center">
            <Icon name="fa6-solid:floppy-disk" />&nbsp; {{ $t('common.save_draft') }}
          </button>
          <button @click="clickFinalize" :disabled="saving || isValidating || validationResult.valid === false"
            class="px-4 py-2 bg-green-500 text-white rounded disabled:opacity-50 enabled:hover:bg-green-600 font-bold flex items-center">
            <Icon name="fa6-solid:circle-check" />&nbsp; {{ isChangeOfNameRequest ? t('contract_block.apply_change_of_name') : $t('common.finish') }}
          </button>
        </div>

        
      </div><!-- end contingut botons -->

      <!-- Barra inferior de Documentació -->
      <div v-if="request?.id && currentStep >= 2"
        class="fixed bottom-0 right-0 z-[90] border-t-2 border-slate-200 bg-white shadow-[0_-4px_16px_rgba(0,0,0,0.08)] transition-all duration-300 ease-in-out"
        :class="showDocBar ? 'h-[40vh]' : 'h-12'"
        :style="{ left: sidebarStore.sidebarWidth + 'px' }">
        <button
          class="w-full h-12 flex items-center justify-between px-5 text-sm font-semibold text-slate-600 hover:bg-slate-50 transition-colors"
          @click="showDocBar = !showDocBar">
          <div class="flex items-center gap-2">
            <Icon name="fa6-solid:file-lines" class="text-sky-500" />
            <span>{{ $t('common.documentation') }}</span>
            <span v-if="request?.documentation_files?.length"
              class="inline-flex items-center justify-center w-5 h-5 rounded-full bg-sky-100 text-sky-700 text-xs font-bold">
              {{ request.documentation_files.filter(d => d.is_active !== false).length }}
            </span>
          </div>
          <Icon :name="showDocBar ? 'fa6-solid:chevron-down' : 'fa6-solid:chevron-up'" class="text-slate-400 text-xs" />
        </button>
        <div v-if="showDocBar" class="h-[calc(100%-3rem)] overflow-y-auto px-6 py-4">
          <ContractDocumentsData :contract="request" :is_request="true" @update-item="handleDocBarUpdate" @refresh="() => emit('refresh', false)" />
        </div>
      </div>

    </div><!--end contingut pas actual -->

    <!-- Teleport Modal per Errors de Validació (Fallback) -->
    <Teleport to="body">
      <Transition
        enter-active-class="transition-all duration-200 ease-out"
        enter-from-class="opacity-0 scale-95"
        enter-to-class="opacity-100 scale-100"
        leave-active-class="transition-all duration-150 ease-in"
        leave-from-class="opacity-100 scale-100"
        leave-to-class="opacity-0 scale-95"
      >
        <div
          v-if="showValidationModal"
          class="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-[150] p-4"
          @click.self="showValidationModal = false"
        >
          <div class="bg-white rounded-lg p-6 max-w-md w-full shadow-2xl">
            <div class="flex items-center gap-3 mb-4">
              <div class="w-10 h-10 rounded-lg bg-red-100 flex items-center justify-center flex-shrink-0">
                <Icon name="fa6-solid:circle-xmark" class="text-red-600 text-lg" />
              </div>
              <h3 class="text-lg font-semibold text-gray-900">{{ t('contract_block.validation_error_title') }}</h3>
            </div>
            <p class="text-gray-600 mb-4 text-sm">
              {{ t('contract_block.validation_error_modal_msg') }}
            </p>
            <ul class="list-none text-sm text-red-700 bg-red-50/50 p-4 rounded-md border border-red-100 mb-6 space-y-2 max-h-[300px] overflow-y-auto pr-1">
              <li v-for="err in validationModalErrors" :key="err" class="flex flex-col gap-1.5 pb-2 border-b border-red-200/30 last:border-b-0 last:pb-0">
                <div class="flex items-start gap-1.5">
                  <span class="inline-block w-1.5 h-1.5 rounded-full bg-red-400 mt-1.5 flex-shrink-0"></span>
                  <span class="flex-grow font-medium">{{ err }}</span>
                </div>
                <div v-if="mapErrorToStep(err)" class="pl-3 flex gap-2">
                  <button 
                    @click="showValidationModal = false; editStepInRegion(mapErrorToStep(err).index, mapErrorToStep(err).name)"
                    class="px-2 py-0.5 bg-blue-100 hover:bg-blue-200 text-blue-800 text-xs font-semibold rounded border border-blue-200 flex items-center gap-1 transition-all duration-150 active:scale-95 inline-flex"
                    title="Modificar en panell lateral"
                  >
                    <Icon name="fa6-solid:pen-to-square" class="text-[10px]" />
                    {{ t('common.edit') || 'Modificar' }}
                  </button>
                  <button 
                    @click="showValidationModal = false; moveToStep(mapErrorToStep(err).index)"
                    class="px-2 py-0.5 bg-red-100 hover:bg-red-200 text-red-800 text-xs font-semibold rounded border border-red-200 flex items-center gap-1 transition-all duration-150 active:scale-95 inline-flex"
                    title="Anar al pas corresponent"
                  >
                    <Icon name="fa6-solid:circle-arrow-right" class="text-[10px]" />
                    {{ mapErrorToStep(err).name }}
                  </button>
                </div>
              </li>
            </ul>
            
            <div class="flex">
              <button
                @click="showValidationModal = false"
                class="w-full px-4 py-2 bg-red-600 text-white rounded-md hover:bg-red-700 font-medium text-sm transition-all duration-150 shadow-sm"
              >
                {{ t('common.close') || 'Tancar' }}
              </button>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>

    <!-- Regió Dreta per l'edició/creació de ContractRequestEdit -->
    <div role="region" id="right_page"
      class="fixed h-full border-l border-gray-100 top-0 right-0 transition-all duration-500 ease py-2 text-base bg-white z-[100] overflow-x-hidden"
      :class="{ 
        'translate-x-0': showRegion, 
        'translate-x-[2000px]': !showRegion,
        'w-1/2': editingStepIndex === null,
        'w-2/3 shadow-2xl': editingStepIndex !== null
      }">
      <div id="region_nav" class="mb-3 px-3">
        <button @click="toggleRegion(false)" class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300">
          <Icon name="fa6-solid:angles-right" class="text-slate-500" />
        </button>
      </div>
      <div class="px-10 h-full">
        <ChangeStatus v-if="editingChangeStatus" entity="connection-request" parent_entity="connection_request"
          :id="request?.id" :status="request?.status?.id" module="service" @changed="handleStatusChanged" />
        <ContractRequestDocumentationRegion v-if="editingDocumentation" :request="request" @change="handleDocumentationChanged" @close="toggleRegion(false)" />
        
        <!-- Step editing components in right panel -->
        <div v-if="editingStepIndex !== null" class="flex flex-col h-[calc(100%-60px)] justify-between">
          <div class="flex-grow overflow-y-auto pb-4 pr-2">
            <div class="mb-6 pb-4 border-b border-slate-100 flex items-center justify-between">
              <h3 class="text-lg font-bold text-slate-800">{{ editingStepTitle }}</h3>
              <span class="text-xs font-semibold px-2 py-1 bg-blue-50 text-blue-700 rounded-full border border-blue-100">
                {{ t('billing_block.step') }} {{ editingStepIndex + 1 }}
              </span>
            </div>
            
            <div v-if="editingStepIndex === 0" key="edit-setup">
              <ContractRequestSetup :request="request" :require-company="useMultipleCompanies"
          :prefill-contract-id="!request?.id ? route.query.contract_id : null" @change="onSetupChanged" />
            </div>
            <div v-else-if="editingStepIndex === 1" key="edit-persons">
              <ContractRequestPersons :request="request" @change="onPersonsChanged" />
            </div>
            <div v-else-if="editingStepIndex === 2" key="edit-payment">
              <ContractRequestAddressPayment :request="request" :usedPayment="usedPayment" @change="onAddressPaymentChanged" />
            </div>
            <div v-else-if="editingStepIndex === 3" key="edit-rates">
              <ContractRequestPriceRate :request="request" @change="onPriceRateChanged" />
            </div>
            <div v-else-if="editingStepIndex === 4" key="edit-orders">
              <ContractRequestOrderBilling :request="request" @change="onOrderBillingChanged" />
            </div>
            <div v-else-if="editingStepIndex === 5" key="edit-termination">
              <div v-if="request && request.id">
                <AtomsTabs class="mb-4">
                  <li v-for="supply_point in request.supply_points" :key="supply_point.id">
                    <a href="#tab_termination" @click.prevent="activeTab = supply_point.id"
                      :class="{ 'text-sky-600 border-sky-600': activeTab === supply_point.id, 'hover:text-gray-600 hover:border-gray-300': activeTab !== supply_point.id }">
                      <Icon name="fa6-solid:street-view" class="display-inline mr-2" />
                      {{ supply_point.token }}
                    </a>
                  </li>
                </AtomsTabs>
                <div v-if="activeTab">
                  <ContractRequestTermination :request="request"
                    :supply_point="request.supply_points.find(item => item.id == activeTab)"
                    :keep-same-code="isChangeOfNameRequest && canKeepSameCode && keepSameCode"
                    :is-change-of-name-request="isChangeOfNameRequest"
                    @on-pending-termination="onPendingTermination" @contract-terminated="onContractTerminated"
                    @change-sp="handleSupplyPointChanged" />
                </div>
              </div>
              <div v-else>
                <AppLoading :text="$t('common.loading')" />
              </div>
            </div>
          </div>
          
          <!-- Actions at the bottom of the panel -->
          <div class="border-t border-slate-100 pt-4 flex justify-end gap-3 bg-white mt-auto pb-4">
            <button @click="closeEditStep" class="px-4 py-2 border border-slate-300 text-slate-700 bg-white rounded hover:bg-slate-50 transition-all duration-150 font-semibold text-sm">
              {{ t('common.close') || 'Tancar' }}
            </button>
            <button @click="saveEditStep" :disabled="saving" class="px-4 py-2 bg-emerald-600 text-white rounded hover:bg-emerald-700 transition-all duration-150 flex items-center gap-2 font-bold text-sm shadow-sm disabled:opacity-50">
              <Icon v-if="saving" name="fa6-solid:spinner" class="animate-spin" />
              <Icon v-else name="fa6-solid:floppy-disk" />
              {{ t('common.save') || 'Guardar' }}
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>