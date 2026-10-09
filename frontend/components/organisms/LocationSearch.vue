<script setup>
import { ref, watch, computed, onMounted } from 'vue';
import { useI18n } from 'vue-i18n';
import debounce from 'lodash.debounce';

const { t } = useI18n();
const { $StreetApiService, $ExploitationApiService } = useNuxtApp();

const cp = ref('');
const city = ref('');
const cities = ref([]);
const postalCodes = ref([]);
const streetQuery = ref('');
const streetResults = ref([]);
const selectedStreet = ref(null);
const streetNumberTypeRadio = ref('');
const streetNumberNumber = ref('');
const streetNumberEnd = ref('');
const streetNumberSuffix = ref('');
const streetNumberEndSuffix = ref('');
const latitude = ref('');
const longitude = ref('');

const blueprint = ref('');
const blueprintUploaded = ref(null);
const blueprintDelete = ref(false);

const streetNumberType = computed(() => {
  if (streetNumberTypeRadio.value === 'SN') {
    return 'SN';
  } else if (streetNumberEnd.value) {
    return 'R';
  } else if (streetNumberSuffix.value) {
    return 'S';
  } else {
    return 'N';
  }
});

const emits = defineEmits(['saved']);
const props = defineProps({
  selectedOptions: {
    type: Object,
    required: false,
  },
});

const fetchCitiesAndPostalCodes = async () => {
  try {
    const data = await $ExploitationApiService.getData();
    cities.value = data.results.map(exploitation => exploitation.cities).flat();
    postalCodes.value = cities.value.map(city => city.postal_codes).flat();

    if (cities.value.length === 1) {
      city.value = cities.value[0].id;
    }
    if (postalCodes.value.length === 1) {
      cp.value = postalCodes.value[0].id;
    }
  } catch (error) {
    console.error(error);
  }
};

const searchStreet = debounce(async () => {
  if (streetQuery.value) {
    const cityId = city.value;
    const data = await $StreetApiService.getAll(streetQuery.value, [], 1, null, false, cityId);
    streetResults.value = data.results;
  } else {
    streetResults.value = [];
  }
}, 300);

const selectStreet = (street) => {
  selectedStreet.value = street;
  streetQuery.value = `${street.type.abbreviation} ${street.name}`;
  streetResults.value = [];
};

const saveLocation = () => {
  var selectedOptionsEmit = {
    cp: cp.value,
    city: city.value,
    address_complete: props.selectedOptions?.address_complete ?? null,
    address_street: selectedStreet.value,
    address_street_type: selectedStreet.value.type.abbreviation,
    address_street_id: selectedStreet.value.id,
    address_street_number__number_type: streetNumberType.value,
    address_street_number__number: streetNumberNumber.value,
    address_street_number__number_end: streetNumberEnd.value,
    address_street_number__number_suffix: streetNumberSuffix.value,
    address_street_number__number_end_suffix: streetNumberEndSuffix.value,
    latitude: latitude.value,
    longitude: longitude.value,
    blueprint: blueprint.value,
    blueprint_delete: blueprintDelete.value
  };

  if( typeof selectedOptionsEmit.address_street_number__number_type == "Object" ) { // mirem que no li estiguem passant un Object per guardar.
    selectedOptionsEmit.address_street_number__number_type = selectedOptionsEmit.address_street_number__number_type?.type;
  }

  console.log('emit saved',selectedOptionsEmit);
  emits('saved', selectedOptionsEmit);
};

const handleBluePrintUpdate = (file) => {
  blueprint.value = file;
};

const handleBluePrintDelete = () => {
  blueprintDelete.value = true;
};

const modificarStreet = () => {
  props.selectedOptions.address_complete = null;
  selectedStreet.value = null;
  streetQuery.value = '';
};

onMounted(() => {
  fetchCitiesAndPostalCodes();

  if (props.selectedOptions?.city) city.value = props.selectedOptions.city;
  if (props.selectedOptions?.cp) cp.value = props.selectedOptions.cp;

  if (props.selectedOptions?.latitude) latitude.value = props.selectedOptions.latitude;
  if (props.selectedOptions?.longitude) longitude.value = props.selectedOptions.longitude;
  if (props.selectedOptions?.blueprintUploaded) blueprintUploaded.value = props.selectedOptions.blueprintUploaded;

  // Street & StreetType
  selectedStreet.value = props.selectedOptions?.address_street;

  // Number
  streetNumberType.value = props.selectedOptions?.address_street_number__number_type;
  streetNumberNumber.value = props.selectedOptions?.address_street_number__number;
  streetNumberEnd.value = props.selectedOptions?.address_street_number__number_end;
  streetNumberSuffix.value = props.selectedOptions?.address_street_number__number_suffix;
  streetNumberEndSuffix.value = props.selectedOptions?.address_street_number__number_end_suffix;
});

</script>


<template>
  <div>
    <h2 class="text-xl font-semibold mb-4">{{ t('common.select') }} {{ t('service_block.connection_location') }}</h2>

    <div v-if="selectedOptions && selectedOptions.address_complete" class="p-3 px-2 bg-blue-50 leading-6">
      {{ selectedOptions.address_complete }}<br />
      {{ selectedOptions?.cp_code }} {{ selectedOptions?.city_name }}
      <br /><button @click="modificarStreet" class="underline text-sky-500">{{ $t('common.modify') }}</button>
    </div>
    <div v-else>

      <div class="row grid grid-cols-[1fr,150px] gap-3">
        <div class="mb-4">
          <label class="block text-sm font-medium text-gray-700 mb-2">{{ t('address_block.municipality') }}</label>
          <select v-model="city"
            class="block w-full py-2 px-3 border border-gray-300 bg-white rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm">
            <option v-for="cityOption in cities" :key="cityOption.id" :value="cityOption.id">
              {{ cityOption.name }}
            </option>
          </select>
        </div>

        <div class="mb-4">
          <label class="block text-sm font-medium text-gray-700 mb-2">{{ t('address_block.postal_code') }}</label>
          <select v-model="cp"
            class="block w-full py-2 px-3 border border-gray-300 bg-white rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm">
            <option v-for="postalCode in postalCodes" :key="postalCode.id" :value="postalCode.id">
              {{ postalCode.code }}
            </option>
          </select>
        </div>
      </div>

      <div class="mb-4">
        <label for="street" class="block text-sm font-medium text-gray-700 mb-2">{{ t('address_block.street') }}</label>
        <input id="street_select" type="text" v-model="streetQuery" @input="searchStreet" :disabled="selectedStreet" 
          autocomplete="street_select"
          :class="{ 'bg-green-100': selectedStreet, 'bg-white': !selectedStreet }"
          class="block w-full py-2 px-3 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm"
          :placeholder="`${t('dashboard.search')} ${t('address_block.street')}`" 
           name="street_select" />
        <ul class="mt-4 border border-gray-300 rounded-md divide-y divide-gray-200" v-if="streetResults.length > 0">
          <li v-for="result in streetResults" :key="result.id" @click="selectStreet(result)"
            class="px-4 py-2 cursor-pointer hover:bg-gray-100">
            {{ result.type?.abbreviation }} {{ result.name }}
          </li>
        </ul>
      </div>

      <div v-if="selectedStreet" class="mb-4">
        <label class="block text-sm font-medium text-gray-700 mb-2">{{ t('address_block.street_number') }}</label>
        <div class="flex items-center mb-2">
          <label class="mr-4">
            <input type="radio" v-model="streetNumberTypeRadio" value="SN" /> {{ t('address_block.no_number') }}
          </label>
          <label>
            <input type="radio" v-model="streetNumberTypeRadio" value="" /> {{ t('common.number') }}
          </label>
        </div>
        <div v-if="streetNumberTypeRadio !== 'SN'" class="grid grid-cols-4 gap-4">
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-2">{{ t('common.number') }}</label>
            <input type="text" v-model="streetNumberNumber"
              class="block w-full py-2 px-3 border border-gray-300 bg-white rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm" />
          </div>
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-2">{{ t('address_block.suffix') }}</label>
            <input type="text" v-model="streetNumberSuffix"
              class="block w-full py-2 px-3 border border-gray-300 bg-white rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm" />
          </div>
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-2">{{ t('address_block.end_number') }}</label>
            <input type="text" v-model="streetNumberEnd"
            class="block w-full py-2 px-3 border border-gray-300 bg-white rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm" />
          </div>
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-2">{{ t('address_block.suffix') }}</label>
            <input type="text" v-model="streetNumberEndSuffix"
              class="block w-full py-2 px-3 border border-gray-300 bg-white rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm" />
          </div>
        </div>
      </div>

    </div>

    <hr class="mb-3" />

    <div class="row grid grid-cols-2 gap-3">
      <div class="mb-4">
        <label class="block text-sm font-medium text-gray-700 mb-2">{{ t('common.latitude') }}</label>
        <input type="text" v-model="latitude"
          class="block w-full py-2 px-3 border border-gray-300 bg-white rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm" />
      </div>

      <div class="mb-4">
        <label class="block text-sm font-medium text-gray-700 mb-2">{{ t('common.longitude') }}</label>
        <input type="text" v-model="longitude"
          class="block w-full py-2 px-3 border border-gray-300 bg-white rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm" />
      </div>
    </div>

    <hr class="mb-3" />


    <div class="mb-4">
      <label for="blueprint" class="block text-sm font-medium text-gray-700">{{ t('service_block.blueprint') }} ({{ t('common.optional')
        }})</label>
      
      <AtomsInputFile @update="handleBluePrintUpdate" @delete="handleBluePrintDelete" :name="'blueprintFile'" :uploaded="blueprintUploaded" />
    </div>


    <hr class="mb-3" />

    <button @click="saveLocation" class="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600">{{ t('common.save') }}</button>
  </div>
</template>

<style scoped>
.disabled-input {
  background-color: #d4edda;
  cursor: not-allowed;
}
</style>
