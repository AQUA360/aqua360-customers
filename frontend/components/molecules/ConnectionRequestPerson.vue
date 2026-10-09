<script setup>
import { ref, onMounted } from 'vue';

import ButtonSeleccio from '~/components/atoms/ButtonSeleccio.vue';
import PersonSearch from '~/components/organisms/PersonSearch.vue';
import CompanySearch from '~/components/organisms/CompanySearch.vue';

const { $AddressHelper } = useNuxtApp();
const { t } = useI18n();

const props = defineProps({
  request: Object
});

const emit = defineEmits(['change-person']);

const showRegion = ref(false);
const isSubRegionOpen = ref(false);
const editingPerson = ref(false);
const editingCompany = ref(false);
const editingLocation = ref(false);

const selectedClient = ref('CLIENT');
const selectedPerson = ref(null);
const selectedCompany = ref(null);
const dataToLoad = ref(null);

const latitude = ref(0)
const longitude = ref(0)

const address_data = ref({});

const blueprint = ref('');
const blueprintUploaded = ref(null);
const blueprintDelete = ref(false);

const handleUpdateAddressData = (updatedValue) => {
  address_data.value = updatedValue;
  if (updatedValue.closeTab) {
    closeAllRegions();
    emitChange();
  }
};

const closeAllRegions = () => {
  // tanquem tots els components
  editingPerson.value = false;
  editingCompany.value = false;
  editingLocation.value = false;

  // tanquem region
  showRegion.value = false;
};

const emitChange = () => {

  let data = {
    person: selectedPerson.value?.id || null,
    company: selectedCompany.value?.id || null,
    address_street: address_data.value?.streetId || null,
    address_street_number: address_data.value?.streetNumberId || null,
    address_postal_code: address_data.value?.cp?.code || null,
    address_city: address_data.value?.city?.code || null,
    latitude: latitude.value || null,
    longitude: longitude.value || null,
    blueprint: blueprint.value || null,
    blueprint_delete: blueprintDelete.value || null,
    exploitation: address_data.value?.exploitation || null
  }
  let token = selectedPerson.value? selectedPerson.value.token: selectedCompany.value.vat

  emit('change-person', data, token);
}

const openPersonForm = () => {
  closeAllRegions();
  editingPerson.value = true;
  showRegion.value = true;
};

const openCompanyForm = () => {
  closeAllRegions();
  editingCompany.value = true;
  showRegion.value = true;
};

const openLocationForm = () => {

  if (props.request && props.request.property && !props.request.address) {
    dataToLoad.value = {
      city: props.request.property.address_city,
      province: props.request.property.address_city?.province,
      country: props.request.property.address_city?.province?.country,
      postal_code: props.request.property.address_postal_code?.code,
      street: props.request.property.address_street,
      street_number: props.request.property.address_street_number
    }
  }

  closeAllRegions();
  editingLocation.value = true;
  showRegion.value = true;
};

const clearAddress = () => {
  address_data.value = null;
  props.request.address_city = null;
  props.request.address_postal_code = null;
  props.request.address_street = null;
  props.request.address_street_number = null;
  
  closeAllRegions();
};

const handleBluePrintUpdate = async (file) => {
  blueprint.value = file;
  emitChange();
};

const handleBluePrintDelete = async (item) => {
  blueprintDelete.value = true;
  emitChange();
};


const fetchPerson = async (item) => {
  selectedPerson.value = item;
  selectedCompany.value = null;
  emitChange()
  closeAllRegions();
};

const fetchCompany = async (item) => {
  selectedCompany.value = item;
  selectedPerson.value = null;
  emitChange()
  closeAllRegions();
};

const loadData = async () => {
  if (props.request) {
    if (props.request.person) {
      selectedPerson.value = props.request.person;
      selectedClient.value = 'CLIENT'
    }
    // if (props.request.company) {
    //   selectedCompany.value = props.request.company;
    //   selectedClient.value = 'COMPANY'
    // }
    latitude.value = props.request.latitude;
    longitude.value = props.request.longitude;
    blueprintUploaded.value = props.request.blueprint;
  }
};

onMounted(() => {
  loadData();
});

watch(() => props.request, (newVal) => {
  loadData()
});

</script>

<template>
  <div id="wrapper" class="text-base">
    <h2 class="text-xl font-semibold mb-4">{{ $t('service_block.select_connection_request_requester') }}</h2>



    <div class="mb-4">
      <label for="person" class="flex text-sm font-medium text-gray-700 mb-3 gap-2">
        <Icon name="fa6-solid:circle-check" v-show="selectedPerson || selectedCompany" class="text-xl text-emerald-600" />
        <Icon v-show="!selectedPerson && !selectedCompany" name="fa6-solid:asterisk" class="text-lg text-slate-400" />
        <span>{{ $t('common.requester') }}:</span>
      </label>

      <!-- <div class="flex items-center gap-5 my-3 px-5">
        <label class="flex items-center">
          <input type="radio" value="COMPANY" v-model="selectedClient" class="mr-2">
          {{ $t('company') }}
        </label>
        <label class="flex items-center">
          <input type="radio" value="CLIENT" v-model="selectedClient" class="mr-2">
          {{ $t('common.particular') }}
        </label>

      </div> -->

      <div v-if="selectedClient == 'CLIENT'">
        <div v-if="selectedPerson" class="bg-green-100 p-4 rounded relative max-w-xl group">
          <p class="font-semibold">{{ selectedPerson.name }} {{ selectedPerson.surname }}<br />
            <span class="text-sm text-gray-500">{{ selectedPerson.token }}</span>
          </p>
          <button @click="openPersonForm"
            class="absolute cursor-pointer shadow-md border text-sm w-8 h-8 bg-white right-3 top-3 rounded-md text-slate-600 opacity-0 transition-all duration-300 group-hover:opacity-100">
            <Icon name="fa6-solid:pencil" />
          </button>
        </div>
        <div v-else>
          <ButtonSeleccio @click="openPersonForm">{{ $t('common.select') }} {{ $t('common.or') }} {{ $t('common.add') }} {{ $t('person') }}</ButtonSeleccio>
        </div>
      </div>
      <div v-if="selectedClient == 'COMPANY'">
        <div v-if="selectedCompany" class="bg-green-100 p-4 rounded relative max-w-xl group">
          <p class="font-semibold">{{ selectedCompany.name }}<br />
            <span class="text-sm text-gray-500">{{ selectedCompany.vat }}</span>
          </p>
          <button @click="openCompanyForm"
            class="absolute cursor-pointer shadow-md border text-sm w-8 h-8 bg-white right-3 top-3 rounded-md text-slate-600 opacity-0 transition-all duration-300 group-hover:opacity-100">
            <Icon name="fa6-solid:pencil" />
          </button>
        </div>
        <div v-else>
          <ButtonSeleccio @click="openCompanyForm">{{ $t('common.select') }} {{ $t('common.or') }} {{ $t('common.add') }} {{ t('company') }}</ButtonSeleccio>
        </div>
      </div>
    </div>

    <div class="mb-4">
      <label for="location" class="flex text-sm font-medium text-gray-700 mb-3 gap-2">
        <Icon v-show="request?.address_street" name="fa6-solid:circle-check" class="text-xl text-emerald-600" />
        <Icon v-show="!request?.address_street" name="fa6-solid:asterisk" class="text-lg text-slate-400" />
        <span>{{ $t('service_block.connection_location') }}:</span>
      </label>

      <div v-if="request?.address_street" class="relative bg-green-100 p-4 rounded max-w-xl group">
        <p v-if="request?.address_street">
          <span>{{ $AddressHelper.getStreetString(request) }}, {{
            $AddressHelper.getNumberString(request.address_street_number) }}</span><br />
          <span>{{ request.address_postal_code?.code }}</span> - <span>{{ request.address_city?.name
            }}</span>
          <span v-if="request?.latitude && request?.longitude"><br />
            <a :href="`https://maps.google.com/?q=${request.latitude},${request.longitude}`"
              class="text-sky-500 underline" target="_blank">{{ request.latitude }}, {{
                request.longitude }}</a>
          </span>
          <span v-if="request?.blueprint"><br />
            <a :href="request.blueprint" class="text-sky-500 underline" target="_blank">
              <Icon name="fa6-regular:file" class="" /> &nbsp;{{ $t('service_block.blueprint') }}
            </a>
          </span>
        </p>
        <p v-else>
          {{t("common.loading")}}...<br />
        </p>
        <button @click="openLocationForm"
          class="absolute cursor-pointer shadow-md border text-sm w-8 h-8 bg-white right-3 top-3 rounded-md text-slate-600 opacity-0 transition-all duration-300 group-hover:opacity-100">
          <Icon name="fa6-solid:pencil" />
        </button>
        
        <button
          @click="clearAddress"
          class="absolute cursor-pointer shadow-md border text-sm w-8 h-8 bg-white 
                right-14 top-3 rounded-md text-red-600 opacity-0 transition-all 
                duration-300 group-hover:opacity-100 flex items-center justify-center">
          <Icon name="fa6-solid:xmark" />
        </button>

      </div>
      <div v-else>
        <ButtonSeleccio @click="openLocationForm" :disabled="!selectedPerson && !selectedCompany">
          {{ $t('service_block.select_location') }}</ButtonSeleccio>
      </div>
    </div>



    <div role="region" id="right_page"
      class="fixed h-full border-l border-gray-100 top-0 right-0 transition-all duration-500 ease py-2 text-base bg-white z-10 overflow-x-hidden"
      :class="{ 'translate-x-0': showRegion, 'translate-x-[2000px]': !showRegion, 'w-[95%]': isSubRegionOpen, 'w-1/2': !isSubRegionOpen }">
      <div id="region_nav" class="mb-3 px-3">
        <button @click="showRegion = false" class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300">
          <Icon name="fa6-solid:angles-right" class="text-slate-500" />
        </button>
      </div>
      <div class="px-10">
        <PersonSearch v-if="editingPerson" @saved="fetchPerson" />
        <CompanySearch v-if="editingCompany" @saved="fetchCompany" />

        <MoleculesAddPartialAddress v-if="editingLocation" :data="request" :is_form="true"
          @valueChanged="handleUpdateAddressData">
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

            <hr class="mb-3" />


            <div class="mb-4">
              <label for="blueprint" class="block text-sm font-medium text-gray-700">{{ t('service_block.blueprint') }} ({{ t('common.optional')
                }})</label>

              <AtomsInputFile @update="handleBluePrintUpdate" @delete="handleBluePrintDelete" :name="'blueprintFile'"
                :uploaded="blueprintUploaded" />
            </div>
          </div>
        </MoleculesAddPartialAddress>
      </div>
    </div>
  </div>
</template>
