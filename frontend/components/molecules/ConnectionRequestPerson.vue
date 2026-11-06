<script setup>
import { ref, computed, onMounted } from 'vue';

import ButtonSeleccio from '~/components/atoms/ButtonSeleccio.vue';
import PersonSearch from '~/components/organisms/PersonSearch.vue';
import CompanySearch from '~/components/organisms/CompanySearch.vue';
import ConnectionRequestDocumentsData from '~/components/molecules/ConnectionRequestDocumentsData.vue';

const { $AddressHelper, $ConfiglistApiService } = useNuxtApp();
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
const editingRepresentative = ref(false);

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

// Dades del sol·licitant i del representant (l'adreça i els contactes són els de la fitxa de la persona)
const requesterType = ref(null);
const propertyCondition = ref(null);
const selectedRepresentative = ref(null);
const representativeType = ref(null);

// Dades de l'emplaçament que no són de l'adreça normalitzada
const emptyLocation = () => ({
  address_building: null,
  address_stair: null,
  address_floor: null,
  address_door: null,
  cadastral: null,
  scope: null,
  polygon: null,
  parcel: null,
  building_type: null,
});
const location = ref(emptyLocation());

const buildingTypes = ref([]);
const representativeTypes = ref([]);

const inputClass = 'block w-full py-2 px-3 border border-gray-300 bg-white rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm disabled:bg-slate-100';

const formKey = (key) => `service_block.connection_request_form.${key}`;
const toOptions = (group, values) => values.map(value => ({ value, label: t(formKey(`${group}.${value}`)) }));
const requesterTypeOptions = computed(() => toOptions('requester_types', ['natural_person', 'legal_person', 'owners_community', 'joint_ownership']));
const propertyConditionOptions = computed(() => toOptions('property_conditions', ['owner', 'right_of_use']));
const scopeOptions = computed(() => toOptions('scopes', ['urban', 'rural']));
const optionLabel = (options, value) => options.find(o => o.value === value)?.label || value;

// Les dades completes (adreces i contactes) venen de la sol·licitud desada.
const requestPerson = computed(() => props.request?.person?.id && props.request.person.id === selectedPerson.value?.id ? props.request.person : null);
const requestRepresentative = computed(() => props.request?.representative?.id && props.request.representative.id === selectedRepresentative.value?.id ? props.request.representative : null);
const personAddresses = (person) => (person?.addresses || []).filter(a => a.is_active !== false).sort((a, b) => Number(b.is_billing) - Number(a.is_billing));
const buildingTypeName = computed(() => buildingTypes.value.find(b => b.id === location.value.building_type)?.name || props.request?.building_type?.name);
const hasLocationExtra = computed(() => Object.values(location.value).some(v => v !== null && v !== ''));

const fetchCatalogs = async () => {
  try {
    const [buildings, representatives] = await Promise.all([
      $ConfiglistApiService.getAll('service/connection-request-building-type'),
      $ConfiglistApiService.getAll('service/connection-request-representative-type'),
    ]);
    buildingTypes.value = (buildings.results || []).filter(i => i.is_active !== false);
    representativeTypes.value = (representatives.results || []).filter(i => i.is_active !== false);
  } catch (error) {
    console.error('Error fetching connection request catalogs:', error);
  }
};

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
  editingRepresentative.value = false;

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
    exploitation: address_data.value?.exploitation || null,
    requester_type: requesterType.value || null,
    property_condition: propertyCondition.value || null,
    representative: selectedRepresentative.value?.id || null,
    representative_type: representativeType.value || null,
    ...location.value,
  }
  // els camps buits no s'envien: es demana explícitament que es buidin
  data.clear_fields = ['requester_type', 'property_condition', 'representative', 'representative_type', ...Object.keys(location.value)]
    .filter(key => data[key] === null || data[key] === '')
    .join(',');
  let token = selectedPerson.value?.token || selectedCompany.value?.vat || null

  emit('change-person', data, token);
}

const openPersonForm = () => {
  closeAllRegions();
  editingPerson.value = true;
  showRegion.value = true;
};

const openRepresentativeForm = () => {
  closeAllRegions();
  editingRepresentative.value = true;
  showRegion.value = true;
};

const fetchRepresentative = async (item) => {
  selectedRepresentative.value = item;
  emitChange();
  closeAllRegions();
};

const removeRepresentative = () => {
  selectedRepresentative.value = null;
  representativeType.value = null;
  emitChange();
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

    requesterType.value = props.request.requester_type || null;
    propertyCondition.value = props.request.property_condition || null;
    selectedRepresentative.value = props.request.representative || null;
    representativeType.value = props.request.representative_type?.id || null;
    const loc = emptyLocation();
    for (const key of Object.keys(loc)) {
      loc[key] = props.request[key] ?? null;
    }
    loc.building_type = props.request.building_type?.id || null;
    location.value = loc;
  }
};

onMounted(() => {
  fetchCatalogs();
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

    <div v-if="selectedPerson" class="mb-6 max-w-3xl">
      <div class="grid grid-cols-2 gap-3 mb-3">
        <div>
          <label for="requester_type" class="block text-sm font-medium text-gray-700 mb-2">{{ $t(formKey('requester_type')) }}</label>
          <select id="requester_type" v-model="requesterType" @change="emitChange" :class="inputClass">
            <option :value="null">-</option>
            <option v-for="o in requesterTypeOptions" :key="o.value" :value="o.value">{{ o.label }}</option>
          </select>
        </div>
        <div>
          <label for="property_condition" class="block text-sm font-medium text-gray-700 mb-2">{{ $t(formKey('property_condition')) }}</label>
          <select id="property_condition" v-model="propertyCondition" @change="emitChange" :class="inputClass">
            <option :value="null">-</option>
            <option v-for="o in propertyConditionOptions" :key="o.value" :value="o.value">{{ o.label }}</option>
          </select>
        </div>
      </div>

      <div v-if="requestPerson" class="border rounded p-3 bg-slate-50 text-sm">
        <p class="font-medium text-gray-700">{{ $t(formKey('notification_address')) }}:</p>
        <ul class="px-3 mb-2">
          <li v-for="a in personAddresses(requestPerson)" :key="a.id">{{ a.address_complete }}</li>
          <li v-if="!personAddresses(requestPerson).length" class="text-slate-500">{{ $t(formKey('no_address')) }}</li>
        </ul>
        <p class="font-medium text-gray-700">{{ $t(formKey('contacts')) }}:</p>
        <ul class="px-3 mb-2">
          <li v-for="c in requestPerson.contacts" :key="c.id">
            <span v-if="c.role" class="text-slate-500">{{ c.role }}: </span>{{ [c.phone, c.email].filter(Boolean).join(' · ') }}
          </li>
          <li v-if="!requestPerson.contacts?.length" class="text-slate-500">{{ $t(formKey('no_contacts')) }}</li>
        </ul>
        <p class="text-xs text-slate-500">{{ $t(formKey('person_data_hint')) }}</p>
      </div>
    </div>

    <div class="mb-4">
      <label class="flex text-sm font-medium text-gray-700 mb-3 gap-2">
        <Icon v-show="selectedRepresentative" name="fa6-solid:circle-check" class="text-xl text-emerald-600" />
        <span>{{ $t(formKey('representative_optional')) }}:</span>
      </label>
      <div v-if="selectedRepresentative" class="max-w-3xl">
        <div class="bg-green-100 p-4 rounded relative max-w-xl group mb-3">
          <p class="font-semibold">{{ selectedRepresentative.name }} {{ selectedRepresentative.surname }}<br />
            <span class="text-sm text-gray-500">{{ selectedRepresentative.token }}</span>
          </p>
          <p v-if="requestRepresentative?.contacts?.length" class="text-sm">
            <span v-for="c in requestRepresentative.contacts" :key="c.id" class="block">{{ [c.phone, c.email].filter(Boolean).join(' · ') }}</span>
          </p>
          <button @click="openRepresentativeForm"
            class="absolute cursor-pointer shadow-md border text-sm w-8 h-8 bg-white right-3 top-3 rounded-md text-slate-600 opacity-0 transition-all duration-300 group-hover:opacity-100">
            <Icon name="fa6-solid:pencil" />
          </button>
          <button @click="removeRepresentative" :title="$t(formKey('remove_representative'))"
            class="absolute cursor-pointer shadow-md border text-sm w-8 h-8 bg-white right-14 top-3 rounded-md text-red-600 opacity-0 transition-all duration-300 group-hover:opacity-100 flex items-center justify-center">
            <Icon name="fa6-solid:xmark" />
          </button>
        </div>
        <div class="max-w-xs">
          <label for="representative_type" class="block text-sm font-medium text-gray-700 mb-2">{{ $t(formKey('representative_type')) }}</label>
          <select id="representative_type" v-model="representativeType" @change="emitChange" :class="inputClass">
            <option :value="null">-</option>
            <option v-for="r in representativeTypes" :key="r.id" :value="r.id">{{ r.name }}</option>
          </select>
        </div>
      </div>
      <div v-else>
        <ButtonSeleccio @click="openRepresentativeForm" :disabled="!selectedPerson">
          {{ $t(formKey('select_representative')) }}</ButtonSeleccio>
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
          <span v-if="hasLocationExtra"><br />
            <span v-if="location.address_building">{{ $t(formKey('building')) }}: {{ location.address_building }} </span>
            <span v-if="location.address_stair">{{ $t(formKey('stair')) }}: {{ location.address_stair }} </span>
            <span v-if="location.address_floor">{{ $t(formKey('floor')) }}: {{ location.address_floor }} </span>
            <span v-if="location.address_door">{{ $t(formKey('door')) }}: {{ location.address_door }}</span>
            <span v-if="location.cadastral" class="block">{{ $t(formKey('cadastral')) }}: {{ location.cadastral }}</span>
            <span v-if="location.scope || location.polygon || location.parcel" class="block">
              <template v-if="location.scope">{{ $t(formKey('scope')) }}: {{ optionLabel(scopeOptions, location.scope) }} </template>
              <template v-if="location.polygon">{{ $t(formKey('polygon')) }}: {{ location.polygon }} </template>
              <template v-if="location.parcel">{{ $t(formKey('parcel')) }}: {{ location.parcel }}</template>
            </span>
            <span v-if="buildingTypeName" class="block">{{ $t(formKey('building_type')) }}: {{ buildingTypeName }}</span>
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
    <div v-if="request?.id" class="mb-4">
      <label class="flex text-sm font-medium text-gray-700 mb-1 gap-2">
        <span>{{ $t(formKey('documents')) }}:</span>
      </label>
      <p class="text-xs text-slate-500 mb-2">{{ $t(formKey('documents_hint')) }}</p>
      <ConnectionRequestDocumentsData :request="request" />
    </div>

    <div role="region" id="right_page"
      class="fixed h-full border-l border-gray-100 top-0 right-0 transition-all duration-500 ease py-2 text-base bg-white z-10 overflow-x-hidden"
      :class="{ 'translate-x-0': showRegion, 'translate-x-full': !showRegion, 'w-[95%]': isSubRegionOpen, 'w-1/2': !isSubRegionOpen }">
      <div id="region_nav" class="mb-3 px-3">
        <button @click="showRegion = false" class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300">
          <Icon name="fa6-solid:angles-right" class="text-slate-500" />
        </button>
      </div>
      <div class="px-10">
        <PersonSearch v-if="editingPerson" @saved="fetchPerson" />
        <PersonSearch v-if="editingRepresentative" :personLabel="formKey('representative')" @saved="fetchRepresentative" />
        <CompanySearch v-if="editingCompany" @saved="fetchCompany" />

        <MoleculesAddPartialAddress v-if="editingLocation" :data="request" :is_form="true"
          @valueChanged="handleUpdateAddressData">
          <div class="col-span-2">
            <div class="row grid grid-cols-4 gap-3">
              <div v-for="key in ['address_building', 'address_stair', 'address_floor', 'address_door']" :key="key" class="mb-4">
                <label class="block text-sm font-medium text-gray-700 mb-2">{{ $t(formKey(key.replace('address_', ''))) }}</label>
                <input type="text" maxlength="50" v-model="location[key]" :class="inputClass" />
              </div>
            </div>
            <div class="row grid grid-cols-2 gap-3">
              <div class="mb-4">
                <label class="block text-sm font-medium text-gray-700 mb-2">{{ $t(formKey('cadastral')) }}</label>
                <input type="text" maxlength="255" v-model="location.cadastral" :class="inputClass" />
              </div>
              <div class="mb-4">
                <label class="block text-sm font-medium text-gray-700 mb-2">{{ $t(formKey('building_type')) }}</label>
                <select v-model="location.building_type" :class="inputClass">
                  <option :value="null">-</option>
                  <option v-for="b in buildingTypes" :key="b.id" :value="b.id">{{ b.name }}</option>
                </select>
              </div>
            </div>
            <div class="row grid grid-cols-3 gap-3">
              <div class="mb-4">
                <label class="block text-sm font-medium text-gray-700 mb-2">{{ $t(formKey('scope')) }}</label>
                <select v-model="location.scope" :class="inputClass">
                  <option :value="null">-</option>
                  <option v-for="o in scopeOptions" :key="o.value" :value="o.value">{{ o.label }}</option>
                </select>
              </div>
              <div class="mb-4">
                <label class="block text-sm font-medium text-gray-700 mb-2">{{ $t(formKey('polygon')) }}</label>
                <input type="text" maxlength="50" v-model="location.polygon" :class="inputClass" />
              </div>
              <div class="mb-4">
                <label class="block text-sm font-medium text-gray-700 mb-2">{{ $t(formKey('parcel')) }}</label>
                <input type="text" maxlength="50" v-model="location.parcel" :class="inputClass" />
              </div>
            </div>

            <hr class="mb-3" />

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
