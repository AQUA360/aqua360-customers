<script setup>
import { ref, onMounted } from 'vue';

import H1 from '~/components/atoms/H1.vue';
import ButtonSeleccio from '~/components/atoms/ButtonSeleccio.vue';
import SupplyPointRequestSetup from '~/components/molecules/SupplyPointRequestSetup.vue';
import SupplyPointRequestPerson from '~/components/molecules/SupplyPointRequestPerson.vue';
import SupplyPointRequestData from '~/components/molecules/SupplyPointRequestData.vue';
import SupplyPointRequestSummary from '~/components/molecules/SupplyPointRequestSummary.vue';
import ChangeStatus from '~/components/molecules/ChangeStatus.vue';
import StatusesNav from '~/components/atoms/StatusesNav.vue';
import AppLoading from '~/components/atoms/AppLoading.vue';
import PersonSearch from '~/components/organisms/PersonSearch.vue';
import LocationSearch from '~/components/organisms/LocationSearch.vue';
import AddAddress from '~/components/molecules/AddAddress.vue';
import { ca, id } from 'date-fns/locale';

const { t }= useI18n();
const route = useRoute()
const router = useRouter()

const {$ConfiglistApiService, $SupplyPointRequestApiService} = useNuxtApp();

const props = defineProps({
  request: Object,
});

const emit = defineEmits(['refresh']);

const request = ref(null);

const steps = ref(['1', '2', '3', '4']);
const currentStep = ref(0);
const maxStep = ref(0);

const loading = ref(true);

const editingChangeStatus = ref(false);
const showRegion = ref(false);
const toggleRegion = (force) => {
  showRegion.value = force !== undefined ? force : !showRegion.value;
}

const supplyPointRequestStatuses = ref([]);
const supplyPointRequestStatus = ref(null);

const requestSetup = ref(null);
const requestPerson = ref(null);
const requestData = ref(null);

const save = async () => {

  if (request.value?.supply_point != null) {
    return;
  }

  if (currentStep.value == 0) {
    const setupData = getRequestData();
    if (setupData) {
      const data = await $SupplyPointRequestApiService.save(setupData);
      if (data.id != setupData.id) {
        setTimeout(() => {
          router.push(`/service/supplypoint-requests/edit/${data.id}?step=2`);
        }, 10);
      }
      request.value = data;
    }
  }
  else if (currentStep.value == 1) {
    const dataData = getRequestDataData();
    if (dataData) {
      const response = await $SupplyPointRequestApiService.save(dataData);
      request.value = response;
      emit('refresh', false);
    }
  }
  else if (currentStep.value == 2) {
    const personData = getRequestPersonData();
    if (personData) {
      const data = await $SupplyPointRequestApiService.save(personData);
      request.value = data;
    }
    emit('refresh', false);
  }
};

const refresh = () => {
  emit('refresh');
}

const getRequestData = () => {
  return {
    id: props.request?.id,
    is_active: true,
    token: requestSetup.value?.token || props.request?.token,
    exploitation_id: requestSetup.value?.exploitation_id || props.request?.exploitation?.id || null,
    connection_id: requestSetup.value?.connection_id || props.request?.connection?.id || null,
    cluster_id: requestSetup.value?.cluster_id || props.request?.cluster?.id || null,
    nozzle_id: requestSetup.value?.nozzle_id || props.request?.nozzle?.id || null,
    status_id: supplyPointRequestStatus.value?.id || null,
  }
}

const getRequestPersonData = () => {
  let data = {
    id: props.request?.id,
    is_active: true,
    token: props.request?.token,
    address_id: requestPerson.value?.address_id || null,
    person_id: requestPerson.value?.person_id || null,
    contract: requestPerson.value?.contract || null,
    cadastral: requestPerson.value?.cadastral || null,
  }
  if (requestPerson.value?.contract_delete) {
    data.contract = null;
    data.contract_delete = true;
  }
  return data;
}
const getRequestDataData = () => {
  return {
    id: props.request?.id,
    is_active: true,
    token: props.request?.token,
    meter_id: requestData.value?.meter_id || null,
    property_id: requestData.value?.property_id || null,
    type_id: requestData.value?.type_id || null,
    supply_type_id: requestData.value?.supply_type_id || null,
    source_id: requestData.value?.source_id || null,
    route_id: requestData.value?.route_id || null,
    position_id: requestData.value?.position_id || null,
    placement_id: requestData.value?.placement_id || null
  }
}

const loadData = async () => {
  if (props.request && props.request.status) {
    supplyPointRequestStatus.value = props.request.status;
    // Set maximum accessible step according to the process that has been done with the request
    if (props.request.meter || props.request.type || props.request.source || props.request.property) {
      maxStep.value = 1;
    }
    if (props.request.person || props.request.address || props.request.contract || ( props.request.documents && props.request.documents.length > 0)) {
      maxStep.value = 2;
    }
    if (props.request.person && props.request.address && props.request.contract && props.request.documents && props.request.documents.length > 0) {
      maxStep.value = 3;
    }
  }
  else {
    const defaultStatus = supplyPointRequestStatuses.value.find(s => s.is_default == true);
    if (defaultStatus) {
      supplyPointRequestStatus.value = defaultStatus;
    }
  }
}

const finalStep = async() => {
  try {
    if (confirm(t("confirmation_text_block.confirm_finish_request") + " " + t("info_must_accept_first"))) {
      let response = await $SupplyPointRequestApiService.closeRequest(props.request.id);
      if (response.id) router.push('/service/supplypoints?id=' + response.id);
    }

  }
  catch (error) {
    console.error(error);
  }
}

const setupChanged = (setupData) => {
  requestSetup.value = setupData;
}
const dataChanged = (setupData) => {
  requestData.value = setupData;
  save();
}
const personChanged = (personData) => {
  requestPerson.value = personData;
  save();
}

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
    const data = await $ConfiglistApiService.getAll('service/' + entity);
    targetArray.value = data.results;
  } catch (error) {
    console.error(`Error fetching ${entity}:`, error);
  }
}

const getData = async () => {
  loading.value = true;
  try {
    await fetchConfigData('supply-point-request-status', supplyPointRequestStatuses);
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

const handleClickChangeStatus = () => {
  editingChangeStatus.value = true;
  showRegion.value = true;
}
const handleStatusChanged = () => {
  editingChangeStatus.value = false;
  showRegion.value = false;
  emit('refresh',true)
}

onMounted(() => {
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

watch(() => props.request, (newVal) => {
  if (newVal.person || newVal.address) {
  }
}); 

</script>

<template>
  <div id="wrapper" class="text-base">
    <div class="border-gray-300 mb-2">
      <div class="flex space-x-4 justify-between">
        <div class="buttons flex gap-4 ml-4">
          <button v-for="(step, index) in steps" :disabled="index > maxStep"
            class="px-4 py-2 rounded-full focus:outline-none" :class="{
              'bg-blue-500 text-white': currentStep === index,
              'bg-gray-200 text-gray-600 cursor-not-allowed': index > maxStep,
              'bg-blue-100 text-blue-500': maxStep >= index }"
            @click="currentStep = index; setUrlStep()"> Pas {{ step }}
          </button>
        </div>
        <div>
          <StatusesNav v-if="supplyPointRequestStatus" :active="supplyPointRequestStatus" :statuses="supplyPointRequestStatuses"></StatusesNav>
        </div>
      </div>
    </div>

    <!-- Contingut del Pas Actual -->
    <div v-if="loading">
      <AppLoading :text="$t('common.loading')" />
    </div>
    <div v-else class="border border-gray-300 rounded-b p-4 bg-white">

      <div v-if="currentStep === 0" class="tab-content mb-6">
        <SupplyPointRequestSetup :request="request" @change-setup="setupChanged"/>
      </div>

      <div v-if="currentStep === 1" class="tab-content mb-6">
        <SupplyPointRequestData :request="request" @change-data="dataChanged"/>
      </div>
      
      <div v-if="currentStep === 2" class="tab-content mb-6">
        <SupplyPointRequestPerson :request="request" @change-person="personChanged" @refresh="refresh"/>
      </div>

      <div v-if="currentStep === 3" class="tab-content mb-6">
        <SupplyPointRequestSummary  :request="request" @clickChangeStatus="handleClickChangeStatus"></SupplyPointRequestSummary>
      </div>

      <hr />

      <!-- Botons de navegació -->
      <div class="flex justify-between mt-4">
        <button @click="previousStep" :disabled="currentStep === 0"
          class="px-4 py-2 bg-gray-500 text-white rounded hover:bg-gray-600"
          :class="{ 'opacity-0 cursor-not-allowed': currentStep === 0 }">
          &larr;&nbsp; {{ $t('common.previous') }}
        </button>
        <button v-if="currentStep !== steps.length - 1" @click="nextStep"
          class="px-4 py-2 bg-green-500 text-white rounded hover:bg-green-600">
          {{ $t('common.next') }} &nbsp;&rarr;
        </button>
        <button v-else :disabled="request.supply_point != null" @click="finalStep" class="px-4 py-2 bg-green-500 text-white rounded disabled:opacity-50 enabled:hover:bg-green-600 font-bold">
          <Icon name="fa6-solid:circle-check"/>&nbsp; {{ $t('common.finish') }}</button>
      </div><!-- end contingut botons -->

    </div><!--end contingut pas actual -->

    <!-- Regió Dreta per l'edició/creació de Persona/Adreça -->
    <div role="region" id="right_page"
      class="fixed h-full border-l border-gray-100 top-0 right-0 transition-all duration-500 ease py-2 text-base bg-white w-1/2 z-20"
      :class="{ 'translate-x-0': showRegion, 'translate-x-[2000px]': !showRegion }">
      <div id="region_nav" class="mb-3 px-3">
        <button @click="toggleRegion(false)"
          class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300"><Icon name="fa6-solid:angles-right"
            class="text-slate-500" /></button>
      </div>
      <div class="px-10">
        <ChangeStatus v-if="editingChangeStatus" entity="supply-point-request" parent_entity="supplypoint_request"
          :id="request?.id" :status="request?.status?.id" module="service"
          @changed="handleStatusChanged" />
      </div>
    </div>
  </div>
</template>
