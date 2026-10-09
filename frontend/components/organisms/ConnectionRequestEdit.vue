<script setup>
import { ref, onMounted } from 'vue';
import { format } from 'date-fns';
import { checkPermission } from '~/middleware/permission';
import { useToast } from 'vue-toastification';
import ChangeStatus from '~/components/molecules/ChangeStatus.vue';
import StatusesNav from '~/components/atoms/StatusesNav.vue';
import ConnectionRequestPerson from '~/components/molecules/ConnectionRequestPerson.vue';
import ConnectionRequestData from '~/components/molecules/ConnectionRequestData.vue';
import ConnectionRequestDetail from '~/components/molecules/ConnectionRequestDetail.vue';
import ConnectionRequestPayment from '../molecules/ConnectionRequestPayment.vue';
import AddAddress from '../molecules/AddAddress.vue';
import PersonBankSelect from '../molecules/PersonBankSelect.vue';
import CompanyBankSelect from '../molecules/CompanyBankSelect.vue';
import AddInvoiceBudget from '../molecules/AddInvoiceBudget.vue';
import InvoiceView from '~/components/organisms/InvoiceView.vue';
import OrderRegion from './OrderRegion.vue';

const { t } = useI18n();
const route = useRoute()
const router = useRouter()

const { $ConfiglistApiService, $ConnectionRequestApiService, $PersonAddressApiService, $GeneralPaymentApiService } = useNuxtApp();

const toast = useToast();
const objectPermissions = ref(null);

//TODO: Redo and improve when possible
const props = defineProps({
  request: Object,
});

const emit = defineEmits(['refresh']);

const request = ref(null);

const steps = ref(['1', '2', '3', '4']);
const currentStep = ref(0);
const maxStep = ref(0);

const loading = ref(true);
const stepLoading = ref(false);
const redoBudget = ref(false)

const order = ref(null);
const showOrderWarning = ref(false);

const editingChangeStatus = ref(false);
const showRegion = ref(false);
const addBillingAddressForm = ref(false)
const editPersonBank = ref(false)
const editCompanyBank = ref(false)

const toggleRegion = (force) => {
  showRegion.value = force !== undefined ? force : !showRegion.value;
  if (!force) {
    editingChangeStatus.value = false;
    showRegionDetailComponent.value = null
    regionDetailId.value = null
    editCompanyBank.value = false
    editPersonBank.value = false
  }
}

const requestPerson = ref(null);
const requestData = ref(null);

const connectionRequestStatuses = ref([]);
const connectionRequestStatus = ref(null);
const paymentMethod = ref(null);
const clientToken = ref(null)
const personBankId = ref(null)
const companyBankId = ref(null)

const reload = ref(false)

const save = async () => {

  console.log('save');
  // if (request.value?.connection != null) {
  //   return;
  // }

  if (currentStep.value == 0) {
    const personData = getRequestPersonData();
    if (personData) {

      if (personData.id == null) {
        const now = new Date();
        const token = format(now, 'yyyyMMddHHmmss');
        personData.token = token;
      }

      const data = await $ConnectionRequestApiService.save(personData);
      if (data.id != personData.id) {
        setTimeout(() => {
          router.push(`/service/connection-requests/edit/${data.id}?step=1`);
        }, 10);
      }
      request.value = data;
    }
  }
  else if (currentStep.value == 1) {
    const dataData = getRequestDataData();
    if (dataData) {
      const response = await $ConnectionRequestApiService.save(dataData);
      request.value = response;
      emit('refresh', false);
    }
  }
  else if (currentStep.value == 3) {
    const personData = getRequestPersonData();
    if (personData) {
      const data = await $ConnectionRequestApiService.save(personData);
      request.value = data;
    }
    emit('refresh', false);
  }
};

const getRequestPersonData = () => {
  let data = {
    id: props.request?.id,
    is_active: true,
    // token: props.request?.token,
    person: requestPerson.value?.person || null,
    company: requestPerson.value?.company || null,
    address_street: requestPerson.value?.address_street || null,
    address_street_number: requestPerson.value?.address_street_number || null,
    address_postal_code: requestPerson.value?.address_postal_code || null,
    address_city: requestPerson.value?.address_city || null,
    exploitation: requestPerson.value?.exploitation || null,
    latitude: requestPerson.value?.latitude || null,
    longitude: requestPerson.value?.longitude || null,
    blueprint: requestPerson.value?.blueprint || null,
  }
  if (requestPerson.value?.blueprint_delete) {
    data.blueprint = null;
    data.blueprint_delete = true;
  }
  return data;
}

const getRequestDataData = () => {
  return {
    id: props.request?.id,
    is_active: true,
    code_gis: requestData.value?.code_gis || null,
    flow_rate: requestData.value?.flow_rate || null,
    dma: requestData.value?.dma || null,
    type: requestData.value?.type || null,
    installation_type: requestData.value?.installation_type || null,
    use_type: requestData.value?.use_type || null,
    valve_type: requestData.value?.valve_type || null,
    diameter: requestData.value?.diameter || null,
    material: requestData.value?.material || null,
    tank: requestData.value?.tank || null,
    address_billing: requestData.value?.address_billing || null,
  }
}

const loadData = async () => {
  if (props.request && props.request.status) {
    connectionRequestStatus.value = props.request.status;
    // Set maximum accessible step according to the process that has been done with the request
    if (props.request.person || props.request.address_street) {
      maxStep.value = 1;
    }
    if (props.request.type || props.request.installation_type) {
      maxStep.value = 2;
    }
  }
  else {
    const defaultStatus = connectionRequestStatuses.value.find(s => s.is_default == true);
    if (defaultStatus) {
      connectionRequestStatus.value = defaultStatus;
    }
  }
}

const finalStep = async () => {
  try {
    console.log('finalStep');
    if (confirm(t("confirmation_text_block.confirm_finalize_request"))) {
      let response = await $ConnectionRequestApiService.closeRequest(props.request.id);
      if (response.id) router.push('/service/connections?id=' + response.id);
      else router.push('/service/connection-requests/?id=' + request.value.id);
    }

  }
  catch (error) {
    console.error(error);
  }
}

const dataChanged = (setupData) => {
  console.log('dataChanged', setupData);
  requestData.value = setupData;
  // save();
}
const personChanged = (personData, token) => {
  requestPerson.value = personData;
  clientToken.value = token
  save();
}

const nextStep = async () => {

  if (currentStep.value == 1 && maxStep.value <= 1 && showOrderWarning.value) {
    if (!confirm(t("warning_block.warning_continue_without_order"))) {
      return;
    }
  }

  stepLoading.value = true;
  try {
    await save();
    if (currentStep.value < steps.value.length - 1) {
      currentStep.value++;
      if (currentStep.value > maxStep.value) {
        maxStep.value = currentStep.value;
      }
      await setUrlStep();
    }
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

const fetchConfigData = async (entity, targetArray) => {
  try {
    const data = await $ConfiglistApiService.getAll('service/' + entity);
    targetArray.value = data.results;
  } catch (error) {
    console.error(`Error fetching ${entity}:`, error);
  }
}

const getData = async () => {
  loading.value = true;
  if (props.request) {
    clientToken.value = props.request.company ? props.request.company.vat : props.request.person?.token
  }
  try {
    await fetchConfigData('connection-request-status', connectionRequestStatuses);
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
}

const handleClickChangeStatus = () => {
  toggleRegion(false)
  editingChangeStatus.value = true;
  showRegion.value = true;
}
const handleStatusChanged = (refresh = true) => {
  console.log('handleStatusChanged', refresh);
  editingChangeStatus.value = false;
  showRegion.value = false;
  emit('refresh', refresh)
}

const openAddBillingAddressForm = () => {
  toggleRegion(false)
  addBillingAddressForm.value = true
  showRegion.value = true;
};

const openPersonBankSelect = (toggle) => {
  toggleRegion(false)
  editPersonBank.value = toggle;
  editCompanyBank.value = !toggle;
  showRegion.value = true;
};

const onAddBillingAddressSaved = async (address) => {
  console.log('onAddBillingAddressSaved', address);
  var person_address = {
    person: request.value.person.id,
    address: address.id,
    is_billing: true,
  }

  var person_address = await $PersonAddressApiService.save(person_address);
  emit('refresh', true)
  addBillingAddressForm.value = false
  toggleRegion(false)
};

const reloadData = async () => {
  console.log('reloadData');
  reload.value = true
  await emit('refresh', false)
  reload.value = false
}

const handleAddressBillingChange = async (address) => {
  try {
    let save_data = {
      id: props.request.id,
      address_billing: address
    }
    const data = await $ConnectionRequestApiService.save(save_data);
  } catch (error) {
    console.error(error)
  }
}

const handlePaymentMethodSelected = async (type_id, type, eData, iban_id = null) => {
  if (type_id && type) {
    paymentMethod.value = { id: type_id, name: type };
  } else {
    paymentMethod.value = { id: props.request.payment?.type?.id, name: props.request.payment?.type?.name }
  }
  if (paymentMethod.value?.name) {
    let genPay = {
      id: props.request.payment ? props.request.payment.id : null,
      token: clientToken.value,
      type: paymentMethod.value.id,
      dir3: eData?.dir3 || null,
      accounting_office: eData?.accounting_office || null,
      managing_body: eData?.managing_body || null,
      processing_unit: eData?.processing_unit || null,
      command: eData?.command || null,
      record: eData?.record || null,
      iban_id: personBankId.value || null,
      company_iban_id: companyBankId.value || null,
      mandate_token: props.request ? props.request.token : clientToken.value,
    }
    let general_payment = await $GeneralPaymentApiService.save(genPay);
    //let pay_id = iban_id ? iban_id : general_payment.id
    let save_data = {
      id: props.request.id,
      payment: general_payment.id || null,
      payment_type: paymentMethod.value ? paymentMethod.value.id : props.request.payment?.type?.id,
    }
    try {
      const data = await $ConnectionRequestApiService.save(save_data);
      //emit('refresh', true)
      request.value = data;
    } catch (error) {
      console.error(error)
    }
  }

}

const isSubRegionOpen = ref(false);

const handleSubRegionEvent = (event) => {
  isSubRegionOpen.value = event;
}

const onCurrentOrder = (res) => {
  console.log('onCurrentOrder', res);
  order.value = res.order;
  showOrderWarning.value = res.warning;
}

const onPersonBankSelected = async (bank) => {
  console.log('onPersonBankSelected', bank);
  personBankId.value = bank.id
  handlePaymentMethodSelected(null, null, null, personBankId.value)
};

const onCompanyBankSelected = async (bank) => {
  companyBankId.value = bank.id
  handlePaymentMethodSelected(null, null, null, companyBankId.value)
};

const showRegionDetailComponent = ref(null);
const regionDetailId = ref(null);

const showDetail = (component, id, redo_budget = false) => {
  console.log('showDetail', component, id, redo_budget);
  toggleRegion(false)
  showRegionDetailComponent.value = component
  regionDetailId.value = id;
  redoBudget.value = redo_budget
  toggleRegion(true)
  emit('refresh', false)
}

onMounted(async () => {
  objectPermissions.value = await checkPermission($ConnectionRequestApiService);
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
  if (props.request) {
    request.value = props.request;
  }
});

watch(() => props.request, async (newVal) => {
  request.value = props.request
}, { deep: true });

</script>

<template>
  <div v-if="objectPermissions?.can_change" id="wrapper" class="text-base">
    <div class="border-gray-300 mb-2">
      <div class="flex space-x-4 justify-between">
        <div class="buttons flex gap-4 ml-4">
          <button v-for="(step, index) in steps" :disabled="index > maxStep || stepLoading"
            class="px-4 py-2 rounded-full focus:outline-none" :class="{
              'bg-blue-500 text-white': currentStep === index,
              'bg-gray-200 text-gray-600 cursor-not-allowed': index > maxStep,
              'bg-blue-100 text-blue-500': maxStep >= index,
              'opacity-50 cursor-not-allowed': stepLoading
            }" @click="currentStep = index; setUrlStep()"> Pas {{ step
            }}
          </button>
        </div>
        <div>
          <StatusesNav v-if="connectionRequestStatus" :active="connectionRequestStatus"
            :statuses="connectionRequestStatuses"></StatusesNav>
        </div>
      </div>
    </div>

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
        <ConnectionRequestPerson :request="request" @change-person="personChanged" />
      </div>

      <div v-if="currentStep === 1 && request" class="tab-content mb-6">
        <ConnectionRequestData :request="request" @change-data="dataChanged" @current-order="onCurrentOrder" @show-detail="showDetail" />
      </div>

      <div v-if="currentStep === 2 && request" class="tab-content mb-6">
        <div id="wrapper" class="text-base">
          <h2 class="text-xl font-semibold mb-4">
            {{ t('billing_block.step') }} {{ currentStep + 1 }}: {{ t('common.select') }} {{ t('billing_block.payment') }}
          </h2>
          <ConnectionRequestPayment :id=request.id :request="request" @clickCreateBilling="openAddBillingAddressForm"
            @clickChangeAddressBilling="handleAddressBillingChange" @bankSelect="openPersonBankSelect"
            @paymentMethodSelected="handlePaymentMethodSelected" @invoice-detail="showDetail" />
        </div>
      </div>

      <div v-if="currentStep === 3 && request" class="tab-content mb-6">
        <div id="wrapper" class="text-base">
          <h2 class="text-xl font-semibold mb-4">
            {{ t('billing_block.step') }} {{ currentStep + 1 }}:
            {{ t('billing_block.validation_and_costs') }}</h2>
          <!-- Contingut del pas 3 -->
          <ConnectionRequestDetail @show-detail="showDetail" :id=request.id 
          @clickChangeStatus="handleClickChangeStatus" :reload="reload" />
        </div>
      </div>

      <hr />

      <!-- Botons de navegació -->
      <div class="flex justify-between mt-4">
        <button @click="previousStep" :disabled="currentStep === 0 || stepLoading"
          class="px-4 py-2 bg-gray-500 text-white rounded hover:bg-gray-600"
          :class="{ 'opacity-0 cursor-not-allowed': currentStep === 0 }">
          &larr;&nbsp; {{ $t('common.previous') }}
        </button>
        <button v-if="currentStep !== steps.length - 1" @click="nextStep"
          :disabled="stepLoading"
          class="px-4 py-2 bg-green-500 text-white rounded enabled:hover:bg-green-600 disabled:opacity-70">
          <span v-if="stepLoading" class="inline-block mr-2">
            <Icon name="fa6-solid:spinner" class="w-4 h-4 animate-spin" />
          </span>
          {{ $t('common.next') }} &nbsp;<span v-if="!stepLoading">&rarr;</span>
        </button>
        <button v-else :disabled="request.connection != null" @click="finalStep"
          class="px-4 py-2 bg-green-500 text-white rounded disabled:opacity-50 enabled:hover:bg-green-600 font-bold">
          <Icon name="fa6-solid:circle-check" />&nbsp; {{ $t('common.finish') }}
        </button>
      </div><!-- end contingut botons -->

    </div><!--end contingut pas actual -->

    <!-- Regió Dreta per l'edició/creació de Persona/Adreça -->
    <div role="region" id="right_page"
      class="fixed h-full border-l border-gray-100 top-0 right-0 transition-all duration-500 ease py-2 text-base bg-white w-1/2 z-20"
      :class="{
        'translate-x-0': showRegion,
        'translate-x-full': !showRegion,
        'w-[95%]': isSubRegionOpen,
        'w-1/2': !isSubRegionOpen
      }">
      <div id="region_nav" class="mb-3 px-3">
        <button @click="toggleRegion(false)" class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300">
          <Icon name="fa6-solid:angles-right" class="text-slate-500" />
        </button>
      </div>
      <div class="px-10">
        <ChangeStatus v-if="editingChangeStatus" entity="connection-request" parent_entity="connection_request"
          :id="request?.id" :status="request?.status?.id" module="service" @changed="handleStatusChanged" />
        <AddAddress v-if="addBillingAddressForm" @new-address="onAddBillingAddressSaved" />
        <OrderRegion v-if="showRegionDetailComponent == 'OrderRegion'" :id="regionDetailId" 
        @show-subregion="handleSubRegionEvent" @changed="handleStatusChanged(false)" />
        <PersonBankSelect v-if="editPersonBank" :title="`${$t('common.select')} ${$t('common.iban')}`" :persons="[request.person]"
          @selected-item="onPersonBankSelected" />
        <CompanyBankSelect v-if="editCompanyBank" :title="`${$t('common.select')} ${$t('common.iban')}`" :company="request.company"
          @selected-item="onCompanyBankSelected" />
        <AddInvoiceBudget v-if="showRegionDetailComponent == 'AddInvoiceContract'" :object_id="request.id"
          :service="$ConnectionRequestApiService" :entity="'connection_request'" :company="request.company"
          :persons="[request.person]" @change="reloadData()" @show-subregion="handleSubRegionEvent" :is_connection="true" />
        <InvoiceView v-if="showRegionDetailComponent == 'InvoiceView'" :id="regionDetailId" />
      </div>
    </div>
  </div>
</template>