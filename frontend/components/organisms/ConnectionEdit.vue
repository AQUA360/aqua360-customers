<script setup>
import { ref, onMounted, computed } from 'vue';
import { useToast } from 'vue-toastification';
import _ from 'lodash';
import { checkPermission } from '~/middleware/permission';
import ButtonSeleccio from '~/components/atoms/ButtonSeleccio.vue';
import ConnectionRequestData from '~/components/molecules/ConnectionRequestData.vue';

const { t } = useI18n();
const toast = useToast();
const objectPermissions = ref(null);

const { $ConfiglistApiService, $ConnectionApiService, $ExploitationApiService } = useNuxtApp();


//TODO: Redo and improve when possible
const props = defineProps({
  connection: Object,
  isSubRegion: false
});


const connection = ref(null);
const selectedConnectionCodeGis = ref('')
const latitude = ref(0)
const longitude = ref(0)

const address_data = ref({});
const addres_shown = ref({});

const loading = ref(true);
const token = ref(null);
const loadingGisData = ref(false);

// const editingChangeStatus = ref(false);
const showRegion = ref(false);
const showAddressForm = ref(false)
// const editPersonBank = ref(false)
// const editCompanyBank = ref(false)
const selectedExploitation = ref(null);
const exploitations = ref([]);

const emit = defineEmits(['saved']);

const toggleRegion = (force) => {
  showRegion.value = force !== undefined ? force : !showRegion.value;
  if (!force) {
    showAddressForm.value = false;
  }
}

const getExploitations = async () => {
  const result = await $ExploitationApiService.getData();
  exploitations.value = result.results.map(exploitation => {
    return {
      label: exploitation.name,
      code: exploitation.id,
      cities: exploitation.cities ? exploitation.cities.map(c => typeof c === 'object' ? c.id : c) : []
    }
  });

  if (!props.connection) {
    const savedExploitationId = localStorage.getItem('exploitation');
    if (savedExploitationId) {
      const found = exploitations.value.find(e => e.code == savedExploitationId);
      if (found) {
        selectedExploitation.value = found;
      }
    } else if (exploitations.value.length == 1) {
      selectedExploitation.value = {
        label: exploitations.value[0].label,
        code: exploitations.value[0].code
      };
    }
  }
}

const searchGisData = async () => {
  loadingGisData.value = true;

  // TODO: Implement the search
  setTimeout(() => {
    toast.warning('Connexió amb el GIS no configurada');
    loadingGisData.value = false;
  }, 1000);
}

const connectionData = ref(null);

const onAddBillingAddressSaved = async (a) => {
  if (a.closeTab) {

    addres_shown.value = {
      city: a.city?.label,
      postal_code: a.cp?.label,
      street: a.street_type.label + ' ' + a.street_name
    }

    let street_number = a.streetNumberType == 'SN' ? 'SN' : a.streetNumberNumber + (a.streetNumberSuffix ?? '')
    if (a.streetNumberType == 'R') {
      street_number += ' - ' + a.streetNumberEnd + (a.streetNumberEndSuffix ?? '')
    }
    addres_shown.value.street_number = street_number;

    let data = {
      address_street: a.streetId || null,
      address_street_number: a.streetNumberId || null,
      address_postal_code: a.cp?.code || null,
      address_city: a.city?.code || null,
      latitude: latitude.value || null,
      longitude: longitude.value || null,
      exploitation: a.exploitation || null
    }

    address_data.value = data;
    toggleRegion(false)
  }
};

const openLocationForm = async () => {
  showRegion.value = true;
  showAddressForm.value = true;
};

const currentCityId = computed(() => {
  const city = address_data.value?.address_city;
  if (!city) return null;
  return typeof city === 'object' ? city.id : city;
});

const showMunicipalityWarning = computed(() => {
  const cityId = currentCityId.value;
  if (!cityId || !selectedExploitation.value) return false;

  const exp = exploitations.value.find(e => e.code === selectedExploitation.value.code);
  if (!exp || !exp.cities) return false;

  return !exp.cities.includes(cityId);
});

const save = async () => {
  if (!props.connection && !selectedExploitation.value) {
    toast.error(t('service_block.exploitation_required'));
    return;
  }

  const data = getConnectionData();
  try {
    let response = await $ConnectionApiService.save(data);
    if (props.isSubRegion) {
      emit('saved', response);
      return;
    }
    return navigateTo('/service/connections');
  }
  catch(e) {
    console.error(e)
  }

};

const updateSelect = (ev) => {
  selectedExploitation.value = ev;
};

const convertToCluster = async () => {

  let text = t('service_block.convert_to_cluster_confirmation');

  if (connection.value?.supply_points?.length > 0) {
    text += '\n\n' + t('service_block.convert_to_cluster_confirmation_supply_points');
  }

  if (confirm(text)) {
    try {
      let response = await $ConnectionApiService.convertToCluster(connection.value.id);
      console.log(response);
      toast.success(t('common.correct_save'));
      return navigateTo(`/service/connections?action=showDetail&id=${connection.value.id}`);
    }
    catch(e) {
      toast.error(t('service_block.convert_to_cluster_error'));
      console.error(e)
    }
  }
};

const getConnectionData = () => {


  let address_city = null;
  if (props.connection?.id && address_data.value?.address_city && address_data.value?.address_city?.id) {
    address_city = address_data.value?.address_city?.id;
  } else {
    address_city = address_data.value?.address_city;
  }

  let exploitation = null;
  if (selectedExploitation.value && selectedExploitation.value?.code) {
    exploitation = selectedExploitation.value?.code;
  } else if (connection.value?.exploitation) {
    exploitation = connection.value?.exploitation?.id? connection.value?.exploitation?.id : connection.value?.exploitation;
  }

  return {
    id: props.connection?.id || null,
    token: token.value || _.random(10000, 99999),
    is_active: true,
    code_gis: selectedConnectionCodeGis.value || null,
    flow_rate: connectionData.value?.flow_rate || null,
    dma: connectionData.value?.dma || null,
    type: connectionData.value?.type || null,
    installation_type: connectionData.value?.installation_type || null,
    use_type: connectionData.value?.use_type || null,
    valve_type: connectionData.value?.valve_type || null,
    diameter: connectionData.value?.diameter || null,
    material: connectionData.value?.material || null,
    tank: connectionData.value?.tank || null,
    address_street: address_data.value?.address_street? 
    address_data.value?.address_street?.id?  address_data.value?.address_street?.id : address_data.value?.address_street : null,
    address_street_number: address_data.value?.address_street_number? 
    address_data.value?.address_street_number?.id?  address_data.value?.address_street_number?.id : address_data.value?.address_street_number : null,
    address_postal_code: address_data.value?.address_postal_code? 
    address_data.value?.address_postal_code?.id?  address_data.value?.address_postal_code?.id : address_data.value?.address_postal_code : null,
    address_city: address_city || null,
    latitude: latitude.value || null,
    longitude: longitude.value || null,
    exploitation: exploitation || null,
    supply_type: connectionData.value?.supply_type || null
  }
}

const dataChanged = (setupData) => {
  connectionData.value = setupData;
}

onMounted(async() => {
  objectPermissions.value = await checkPermission($ConnectionApiService);
  await getExploitations();
  if (!objectPermissions.value.can_change) {
    toast.error(t('common.no_permissions'));
    return navigateTo('/');
  }
  if (props.connection) {
    token.value = props.connection?.token;
    connection.value = props.connection;
    selectedConnectionCodeGis.value = connection.value?.code_gis;
    latitude.value = connection.value?.latitude;
    longitude.value = connection.value?.longitude;
    address_data.value = {
      address_street: connection.value?.address_street,
      address_street_number: connection.value?.address_street_number,
      address_postal_code: connection.value?.address_postal_code,
      address_city: connection.value?.address_city,
      exploitation: connection.value?.exploitation
    }
    addres_shown.value = {
      street: connection.value?.address_street?.type?.abbreviation + ' ' + connection.value?.address_street?.name,
      postal_code: connection.value?.address_postal_code?.code,
      city: connection.value?.address_city?.name,
      address_complete: connection.value?.address_complete
    }

    selectedExploitation.value = {
      label: connection.value?.exploitation?.name,
      code: connection.value?.exploitation?.id
    }

    // let street_number = connection.value?.address_street?.street_number == 'SN' ? 'SN' : a.streetNumberNumber + (a.streetNumberSuffix ?? '')
    // if (a.streetNumberType == 'R') {
    //   street_number += ' - ' + a.streetNumberEnd + (a.streetNumberEndSuffix ?? '')
    // }
    // addres_shown.value.street_number = street_number;
  }
  else {
    token.value = _.random(10000, 99999);
  }
  loading.value = false;
});

watch(() => props.connection, async (newVal) => {
  connection.value = props.connection
}, { deep: true });

</script>

<template>
  <div v-if="objectPermissions?.can_change" id="wrapper" class="text-base">

    <div v-if="loading">
      <div class="rounded-b p-4 bg-white" :class="{'border border-gray-300': !isSubRegion}">
        <div class="flex justify-center items-center">
          <Icon name="fa6-solid:spinner" class="animate-spin text-2xl text-slate-500" />
          <span class="ml-2">{{ $t('common.loading') }}...</span>
        </div>
      </div>
    </div>
    <div v-else class="rounded-b p-4 bg-white" :class="{'border border-gray-300': !isSubRegion}">
      <div class="tab-content mb-6">
        <div class="grid grid-cols-2 gap-4">
          <div class="mb-4">
            <label for="code_gis" class="block text-sm font-medium text-gray-700 mb-2">{{ $t('service_block.gis_code') }}</label>
            <div class="flex">
              <input type="text" v-model="selectedConnectionCodeGis"
                class="block w-full py-2 px-3 border border-r-none border-gray-300 bg-white rounded-l-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm" />
              <button
                class="w-9 h-9 border-gray-300 mr-1 border rounded-r text-slate-600 enabled:hover:bg-slate-200 disabled:bg-slate-200 disabled:text-slate-400 transition-all duration-200 flex items-center justify-center"
                @click="searchGisData">
                <Icon v-if="!loadingGisData" name="fa6-solid:magnifying-glass" class="text-md" />
                <Icon v-else name="fa6-solid:spinner" class="animate-spin text-md" />
              </button>
            </div>
          </div>
          <div class="mb-4">
            <label for="code_gis" class="block text-sm font-medium text-gray-700 mb-2">{{ $t('common.identification') }}</label>
            <div class="flex">
              <input type="text" v-model="token"
                class="block w-full py-2 px-3 border border-r-none border-gray-300 bg-white rounded-l-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm" />
            </div>
          </div>
          <div class="mb-4">
            <label for="connection-type" class="block text-sm font-medium text-gray-700 mb-2">{{ $t('common.exploitation') }}</label>
            <v-select :loading="loading" class="block w-full mr-1 required" :model-value="selectedExploitation" :disabled="loading"
              @update:modelValue="updateSelect($event)" :options="exploitations" />
          </div>
          <div v-if="connection && connection.id && connection.installation_type && connection.installation_type.token == 'individual'" class="mb-4">
            <label for="connection-type" class="block text-sm font-medium text-gray-700 mb-2">{{ $t('service_block.installation_type') }}</label>
            <button @click="convertToCluster" class="button-primary">
              <Icon name="fa6-solid:list" />&nbsp; {{ t('service_block.convert_to_cluster') }}
            </button>
          </div>
          <div v-if="showMunicipalityWarning" class="col-span-2 p-3 mb-4 text-amber-800 bg-amber-50 rounded-md border border-amber-200 flex items-center gap-2">
            <Icon name="fa6-solid:triangle-exclamation" class="text-amber-500 text-lg flex-shrink-0" />
            <span>{{ t('service_block.exploitation_municipality_warning') }}</span>
          </div>
        </div>
        <div class="mb-4 max-w-lg">
          <label for="location" class="flex text-sm font-medium text-gray-700 mb-3 gap-2">
            <Icon v-show="address_data?.address_street" name="fa6-solid:circle-check" class="text-xl text-emerald-600" />
            <Icon v-show="!address_data?.address_street" name="fa6-solid:asterisk" class="text-lg text-slate-400" />
            <span>{{ $t('service_block.connection_location') }}:</span>
          </label>

          <div v-if="addres_shown?.street" class="relative bg-green-100 p-4 rounded max-w-xl group">
            <p>
              <span v-if="addres_shown.address_complete">{{ addres_shown.address_complete }}</span>
              <span v-else>{{ addres_shown.street }}, {{ addres_shown.street_number }}</span><br />
              <span>{{ addres_shown.postal_code }}</span> - <span>{{ addres_shown.city }}</span>
              <span v-if="latitude && longitude"><br />
                <a :href="`https://maps.google.com/?q=${latitude},${longitude}`"
                  class="text-sky-500 underline" target="_blank">{{ latitude }}, {{
                    longitude }}</a>
              </span>
            </p>
            <button @click="openLocationForm"
              class="absolute cursor-pointer shadow-md border text-sm w-8 h-8 bg-white right-3 top-3 rounded-md text-slate-600 opacity-0 transition-all duration-300 group-hover:opacity-100">
              <Icon name="fa6-solid:pencil" />
            </button>
          </div>
          <div v-else>
            <ButtonSeleccio @click="openLocationForm">
              {{ $t('common.select') }} {{ $t('address_block.location') }} </ButtonSeleccio>
          </div>
        </div>
      </div>

      <ConnectionRequestData :request="connection" :hideOrder="true" @change-data="dataChanged" />
    </div>

    <div class="col-span-3 flex flex-row-reverse mt-4">
      <button @click="save" class="button-primary">
        <Icon name="fa6-solid:floppy-disk" />&nbsp; {{ t('common.save') }}
      </button>
    </div>

  </div>

  <!-- Regió Dreta per l'edició/creació de Persona/Adreça -->
  <div role="region" id="right_page"
    class="fixed h-full border-l border-gray-100 top-0 right-0 transition-all duration-500 ease py-2 text-base bg-white w-1/2 z-20 overflow-x-hidden"
    :class="{ 'translate-x-0': showRegion, 'translate-x-[2000px]': !showRegion }">
    <div id="region_nav" class="mb-3 px-3">
      <button @click="toggleRegion(false)" class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300">
        <Icon name="fa6-solid:angles-right" class="text-slate-500" />
      </button>
    </div>
    <div class="px-10">
      <MoleculesAddPartialAddress v-if="showAddressForm" :data="connection" :is_form="true"
        @valueChanged="onAddBillingAddressSaved">
        <div class="col-span-2">
          <div class="row grid grid-cols-2 gap-3">
            <div class="mb-4">
              <label class="block text-sm font-medium text-gray-700 mb-2">{{ t('common.latitude') }}</label>
              <input v-numeric-only v-model="latitude"
                class="block w-full py-2 px-3 border border-gray-300 bg-white rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm" />
            </div>

            <div class="mb-4">
              <label class="block text-sm font-medium text-gray-700 mb-2">{{ t('common.longitude') }}</label>
              <input v-numeric-only v-model="longitude"
                class="block w-full py-2 px-3 border border-gray-300 bg-white rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm" />
            </div>
          </div>
        </div>
      </MoleculesAddPartialAddress>
    </div>
  </div>
</template>