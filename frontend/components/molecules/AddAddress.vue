<script setup>
import { ref, computed, onMounted, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import { useToast } from 'vue-toastification';
import _ from 'lodash';

import H1 from '~/components/atoms/H1.vue';
import CatastroRegion from '~/components/organisms/CatastroRegion.vue';
import StreetPicker from '~/components/molecules/StreetPicker.vue';
import AppLoading from '~/components/atoms/AppLoading.vue';

const { t } = useI18n();
const { $AddressApiService, $StreetApiService, $CatastroApiService, $ExploitationApiService } = useNuxtApp();
const toast = useToast();

const isLoading = ref(true);

var exploitations = null

const streetQuery = ref('');
const selectedStreet = ref(null);
const selectedStreetId = ref(null);

const creating_street = ref(false);
const selectedItem = ref([]);

const postal_code = ref('')
const country = ref(null)
const province = ref(null)
const city = ref(null)
const street_type = ref(null)
const street_name = ref('')
const streetNumberTypeRadio = ref('');
const streetNumberNumber = ref('');
const streetNumberEnd = ref('');
const streetNumberSuffix = ref('');
const streetNumberEndSuffix = ref('');
const floor = ref('');
const door = ref('');
const stair = ref('');
const building = ref('');
const address_extra = ref('');

const defaultCountry = ref(null)
const defaultProvince = ref(null)
const defaultCity = ref(null)
const countries = ref([])
const provinces = ref([])
const cities = ref([])
const street_types = ref([])

const attemptedSave = ref(false);

const loading_countries = ref(true);
const loading_provinces = ref(true);
const loading_cities = ref(true);
const loading_street_types = ref(true);
const saving = ref(false);
const loading = ref(true);

const isCadastreOpen = ref(false);
const cadastreResults = ref([]);
const isDefaultCountry = ref(true);

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

const isManualCity = computed(() => {
  if (!isDefaultCountry.value) return true;
  const specialCodes = ['98', '99', 98, 99];
  return province.value && specialCodes.includes(province.value.code);
});

const showRegion = ref(false);

const toggleRegion = (force) => {
  showRegion.value = force !== undefined ? force : !showRegion.value;
  if (showRegion.value == false) {
    isSubRegionOpen.value = false;
  }
  emit('show-subregion', showRegion.value);
}

const props = defineProps({
  selectedAddress: Object,
  isSubRegion: {
    type: Boolean,
    default: false
  },
  isSubRegionOpen: {
    type: Boolean,
    default: false
  },
  //If set to True we only load Countries, Provinces and Cities which are included in the Exploitations
  onlyExploitation: false, 
});

const emit = defineEmits(['new-address', 'show-subregion']);


// set-up

const setDefaultExploitationCity = async () => {
  try {
    const exploitation_id = localStorage.getItem('exploitation') || 1;
    const exploitation = await $ExploitationApiService.getDetail(exploitation_id);
    if (exploitation?.cities?.length > 0) {
      const firstCity = exploitation.cities[0];
      if (firstCity.province?.country) {
        isDefaultCountry.value = firstCity.province.country.iso_code === 'ES';
        country.value = {
          label: firstCity.province.country.name,
          code: firstCity.province.country.id,
          iso_code: firstCity.province.country.iso_code
        };
      }
      if (firstCity.province) {
        province.value = {
          label: firstCity.province.name,
          code: firstCity.province.id
        };
      }
      await getCities();
      city.value = {
        label: firstCity.name,
        code: firstCity.id,
        postal_code: firstCity.postal_codes?.[0]?.code
      };
      if (city.value?.postal_code) {
        postal_code.value = city.value.postal_code;
      }
    }
  } catch (error) {
    console.error('Error fetching default exploitation city:', error);
  }
}

const getData = async () => {
  loading.value = true;
  await getExploitations();
  await getCountries();
  await getProvinces();
  await getCities();
  await getStreetTypes();

  if (props.selectedAddress) {
    await assignValues()
  } else {
    await resetValues();
  }
  loading.value = false;
};

const setAddress = function (item) {
  isCadastreOpen.value = false;
  toggleRegion(false);
  street_name.value = item.dir.nv;
  street_type.value = { label: item.dir.tv };
  if (item.loine?.cp) {
    postal_code.value = item.loine.cp;
  }
  creating_street.value = true;
}

const resetValues = async () => {
  country.value = null;
  province.value = null;
  city.value = null;
  postal_code.value = null;
  street_type.value = null;
  street_name.value = '';
  streetQuery.value = '';
  selectedStreet.value = null;
  selectedStreetId.value = null;
  creating_street.value = false;
  streetNumberTypeRadio.value = '';
  streetNumberNumber.value = '';
  streetNumberEnd.value = '';
  streetNumberSuffix.value = '';
  streetNumberEndSuffix.value = '';
  floor.value = '';
  door.value = '';
  stair.value = '';
  building.value = '';
  address_extra.value = '';
  await setDefaultExploitationCity();
}

const assignValues = async () => {
  if (props.selectedAddress.country != null) {
    if (props.selectedAddress.country?.id != null && props.selectedAddress.country?.id != '' && props.selectedAddress.country?.id != undefined) {
      country.value = countries.value.find(country => country.code == props.selectedAddress.country?.id);
    } else {
      country.value = countries.value.find(country => country.code == props.selectedAddress.country);
    }
    if (provinces.value.length == 0) await getProvinces()
    if (props.selectedAddress.province != null) {
      province.value = {
        code: props.selectedAddress.province?.id ? props.selectedAddress.province?.id : props.selectedAddress.province,
        label: props.selectedAddress.province_name? props.selectedAddress.province_name : props.selectedAddress.province.name
      }
      await getCities()
      if (props.selectedAddress.city != null) {
        if (typeof props.selectedAddress.city === 'string') {
          city.value = props.selectedAddress.city;
        } else {
          city.value = {
            code: props.selectedAddress.city?.id ? props.selectedAddress.city?.id : props.selectedAddress.city,
            label: props.selectedAddress.city_name ? props.selectedAddress.city_name : props.selectedAddress.city.name
          }
        }
      }
    }
  }
  postal_code.value = props.selectedAddress.postal_code;
  if (props.selectedAddress.street?.type?.id != null && props.selectedAddress.street?.type?.id != '' && props.selectedAddress.street?.type?.id != undefined) {
    street_type.value = street_types.value.find(street_type => street_type.code == props.selectedAddress.street?.type?.id);
  } else {
    street_type.value = street_types.value.find(street_type => street_type.code == props.selectedAddress.street_type);
  }
  if (props.selectedAddress.street?.name != null && props.selectedAddress.street?.name != '' && props.selectedAddress.street?.name != undefined) {
    street_name.value = props.selectedAddress.street?.name;
  } else {
    street_name.value = props.selectedAddress.street_name;
  }
  
  if (props.selectedAddress.street?.id) {
    selectedStreet.value = props.selectedAddress.street;
    selectedStreetId.value = props.selectedAddress.street.id;
    streetQuery.value = props.selectedAddress.street.name;
    creating_street.value = false;
  } else if (props.selectedAddress.street) {
    selectedStreet.value = await $StreetApiService.getDetail(props.selectedAddress.street);
    selectedStreetId.value = props.selectedAddress.street;
    streetQuery.value = props.selectedAddress.street_name || selectedStreet.value?.name;
    creating_street.value = false;
  } else {
    selectedStreet.value = null;
    selectedStreetId.value = null;
    streetQuery.value = '';
    creating_street.value = !!props.selectedAddress.street_name;
  }
  
  if (props.selectedAddress.street_number != null) {
    if (props.selectedAddress.street_number?.id != null && props.selectedAddress.street_number?.id != '' && props.selectedAddress.street_number?.id != undefined) {
      streetNumberNumber.value = props.selectedAddress.street_number.number;
      streetNumberEnd.value = props.selectedAddress.street_number.number_end;
      streetNumberSuffix.value = props.selectedAddress.street_number.number_suffix;
      streetNumberEndSuffix.value = props.selectedAddress.street_number.number_end_suffix;
    } else {
      streetNumberNumber.value = props.selectedAddress.street_number;
      streetNumberEnd.value = props.selectedAddress.number_end;
      streetNumberSuffix.value = props.selectedAddress.number_suffix;
      streetNumberEndSuffix.value = props.selectedAddress.number_end_suffix;
      
    }
    if (props.selectedAddress.street_number.number_type != null) {
      streetNumberType.value = props.selectedAddress.street_number.number_type.type;
      if (props.selectedAddress.street_number.number_type.type == 'SN') {
        streetNumberTypeRadio.value = props.selectedAddress.street_number.number_type.type;
      }
    }
  }

  floor.value = props.selectedAddress.floor;
  door.value = props.selectedAddress.door;
  stair.value = props.selectedAddress.stair;
  building.value = props.selectedAddress.building;
  address_extra.value = props.selectedAddress.address_extra;
}


const getStreetTypes = async () => {
  loading_street_types.value = true;

  street_types.value = [];

  const result = await $StreetApiService.getStreetTypes();

  street_types.value = [];

  result.results.forEach(street_type => {
    street_types.value.push({
      label: street_type.name ? `${street_type.abbreviation} - ${street_type.name}` : street_type.abbreviation,
      code: street_type.id,
      abbreviation: street_type.abbreviation,
      name: street_type.name
    })
  });
  loading_street_types.value = false;
};

const getExploitations = async () => {
  exploitations = await $ExploitationApiService.getData();
}

const getCountries = async () => {
  loading_countries.value = true;
  
  countries.value = [];
  country.value = null;

  if (props.onlyExploitation && exploitations) {
    let countriesMap = new Map();
    exploitations.results.forEach(exploitation => {
      exploitation.cities.forEach(city => {
        let cityCountry = city.province.country 
        countriesMap.set(cityCountry.id, {label: cityCountry.name, code: cityCountry.id, iso_code: cityCountry.iso_code});
        if (cityCountry.is_default) {
          defaultCountry.value = { label: cityCountry.name, code: cityCountry.id, iso_code: cityCountry.iso_code }
        }
      });
    });
    countriesMap.forEach((value, key) => {
      countries.value.push(value)
    });
    
    // Set default country from the first exploitation's first city if it's not already set
    if (!props.selectedAddress && countries.value.length > 0) {
      country.value = countries.value[0];
    } else {
      country.value = defaultCountry.value;
    }
  }
  else {
    const result = await $AddressApiService.getCountries();
    result.results.forEach(country => {
      if (country.name != '' && country.iso_code != '') {
        countries.value.push({
          label: country.name,
          code: country.id,
          iso_code: country.iso_code
        })
      }
      if (country.is_default) {
        defaultCountry.value = { label: country.name, code: country.id, iso_code: country.iso_code }
      }
    });
    country.value = defaultCountry.value
  }
  loading_countries.value = false;
};

const getProvinces = async () => {
  loading_provinces.value = true;
  provinces.value = [];
  province.value = null;

  if (props.onlyExploitation && exploitations) {
    let provincesMap = new Map();
    exploitations.results.forEach(exploitation => {
      exploitation.cities.forEach(city => {
        let cityProvince = city.province
        provincesMap.set(cityProvince.id, {label: cityProvince.name, code: cityProvince.id});
        if (cityProvince.is_default) {
          defaultProvince.value = { label: cityProvince.name, code: cityProvince.id}
        }
      });
    });
    provincesMap.forEach((value, key) => {
      provinces.value.push(value)
    });
    
    // Set default province from the first exploitation's first city if it's not already set
    if (!props.selectedAddress && provinces.value.length > 0) {
      province.value = provinces.value[0];
    } else {
      province.value = defaultProvince.value;
    }
  }
  else {
    if (!country.value || !country.value.code) {
      loading_provinces.value = false;
      return;
    }
    const result = await $AddressApiService.getProvinces(country.value.code);

    result.results.forEach(province => {
      provinces.value.push({
        label: province.name,
        code: province.id
      })
      if (province.is_default) {
        defaultProvince.value = { label: province.name, code: province.id }
      }
    });
    if(country.value == defaultCountry.value){
      province.value = defaultProvince.value
    }
  }
  loading_provinces.value = false;
};

const getCities = async () => {
  loading_cities.value = true;
  cities.value = [];
  city.value = null;
  if (props.onlyExploitation && exploitations) {
    let citiesMap = new Map();
    exploitations.results.forEach(exploitation => {
      exploitation.cities.forEach(city => {
        const pCode = city.postal_codes?.[0]?.code;
        citiesMap.set(city.id, {label: city.name, code: city.id, postal_code: pCode});
        if (city.is_default) {
          defaultCity.value = { label: city.name, code: city.id, postal_code: pCode}
        }
      });
    });
    citiesMap.forEach((value, key) => {
      cities.value.push(value)
    });
    
    // Set default city from the first exploitation's first city if it's not already set
    if (!props.selectedAddress && cities.value.length > 0) {
      city.value = cities.value[0];
      if (city.value?.postal_code) {
        postal_code.value = city.value.postal_code;
      }
    } else {
      city.value = defaultCity.value;
      if (city.value?.postal_code) {
        postal_code.value = city.value.postal_code;
      }
    }
  }
  else {
    const specialCodes = ['98', '99', 98, 99];
    if (province.value?.code && specialCodes.includes(province.value.code)) {
      loading_cities.value = false;
      return;
    }
    const result = await $AddressApiService.getCitiesByProvince(province.value?.code);
    result.results.forEach(city => {
      cities.value.push({
        label: city.name,
        code: city.id,
        postal_code: city.postal_codes?.[0]?.code
      })
      if (city.is_default) {
        defaultCity.value = { label: city.name, code: city.id, postal_code: city.postal_codes?.[0]?.code }
      }
    });
    if(country.value == defaultCountry.value){
      city.value = defaultCity.value
      if (city.value?.postal_code) {
        postal_code.value = city.value.postal_code;
      }
    }
  }
  loading_cities.value = false;
};

// street logic

// Pont amb StreetPicker.vue (v-model: { street, creating, name, type })
const streetModel = computed({
  get: () => ({
    street: selectedStreetId.value ? { ...(selectedStreet.value || {}), id: selectedStreetId.value, name: selectedStreet.value?.name || streetQuery.value } : null,
    creating: creating_street.value || isManualCity.value,
    name: street_name.value || '',
    type: street_type.value,
  }),
  set: (value) => {
    selectedStreet.value = value.street;
    selectedStreetId.value = value.street?.id ?? null;
    creating_street.value = value.creating || isManualCity.value;
    street_name.value = value.name || '';
    street_type.value = value.type;
    streetQuery.value = value.street?.name || value.name || '';
  }
});

const streetSearchCityId = computed(() => {
  if (isManualCity.value || !city.value) return null;
  return typeof city.value === 'object' ? city.value.code : city.value;
});

const onStreetSelected = (street) => {
  if (street.postal_code) {
    postal_code.value = street.postal_code;
  }
};

// saving

const save = async () => {
  if (isValid()) {

    saving.value = true;

    const abbreviation = street_type.value?.abbreviation || street_type.value?.label || street_type.value;
    const streetName = creating_street.value ? street_name.value : selectedStreet.value.name;

    const selectedOptions = {
      // id: props.selectedAddress?.id || null,
      id: null,
      temp_id: props.selectedAddress?.temp_id || null,
      postal_code: postal_code.value,
      street_number: {
        number_type: {
          type: streetNumberType.value,

        },
        number_type_type: streetNumberType.value,
      },
      country: country.value.code,
      province: isDefaultCountry.value ? province.value?.code : null,
      province_name: isDefaultCountry.value ? province.value?.label : null,
      city: !isManualCity.value ? city.value.code : city.value,
      city_name: !isManualCity.value ? city.value.label : city.value,
      floor: floor.value,
      door: door.value,
      stair: stair.value,
      building: building.value,
      address_extra: address_extra.value,
      address_complete: `${abbreviation} ${streetName}, ${streetNumberType.value === 'SN' ? 'S/N' : streetNumberNumber.value}`
    };

    if (creating_street.value) {
      selectedOptions.street = {
        type: {
          abbreviation: abbreviation
        },
        type_abbreviation: abbreviation,
        name: street_name.value,
        city: !isManualCity.value ? city.value.code : city.value
      };
    }
    else {
      selectedOptions.street = {
        type: {
          abbreviation: abbreviation
        },
        type_abbreviation: abbreviation,
        name: selectedStreet.value.name,
        street_id: selectedStreetId.value
      };
    }

    if (streetNumberType.value != 'SN') {
      selectedOptions.street_number.number = streetNumberNumber.value || null,
        selectedOptions.street_number.number_end = streetNumberEnd.value || null,
        selectedOptions.street_number.number_suffix = streetNumberSuffix.value || null,
        selectedOptions.street_number.number_end_suffix = streetNumberEndSuffix.value || null
    }

    try {
      let savedAddress;
      if (selectedOptions.id) {
        savedAddress = await $AddressApiService.updateAddress(selectedOptions);
      } else {
        savedAddress = await $AddressApiService.createAddress(selectedOptions);
      }
      
      // Instead of calling the API, we emit the address object to the parent
      // The parent will include this in its own save/update call
      finishAndClose(savedAddress);
    } catch (error) {
      console.error('Error saving address:', error);
      toast.error(t('address_block.error_saving_address') || 'Error al guardar la dirección.');
    } finally {
      saving.value = false;
    }
  }
  else {
    attemptedSave.value = true;
  }
}

const finishAndClose = (address) => {
  saving.value = false;
  emit('new-address', address);
}

const isValid = () => {
  if (city.value == null || city.value === '') return false;
  if (isDefaultCountry.value && province.value == null) return false;
  if (country.value == null) return false;
  if (selectedStreetId.value == null && !creating_street.value) return false;
  if (creating_street.value && (!street_name.value || street_name.value.trim() === '')) return false;
  if (creating_street.value && !street_type.value) return false;
  return true;
}


const showCadastre = async (searchText = null) => {
  if (!city.value || !province.value) {
    toast.warning(t('address_block.error_required_municipality') || 'Por favor, seleccione un municipio.');
    return;
  }

  const prov = typeof province.value === 'object' ? province.value.label : province.value;
  const mun = typeof city.value === 'object' ? city.value.label : city.value;
  const searchName = searchText || street_name.value || streetQuery.value || '';

  try {
    // Intento búsqueda exacta
    let result = await $CatastroApiService.getData(prov, mun, '', searchName);
    let hasData = result?.consulta_callejeroResult?.callejero != null;

    // Si no hay datos, búsqueda más permisiva
    if (!hasData) {
      const words = searchName.split(' ').filter(w => w.length > 2);
      for (const word of words) {
        result = await $CatastroApiService.getData(prov, mun, '', '');
        if (result?.consulta_callejeroResult?.callejero) {
          hasData = true;
          break;
        }
      }
    }

    if (hasData) {
      cadastreResults.value = result?.consulta_callejeroResult?.callejero || [];
      isCadastreOpen.value = true;
      toggleRegion(true);
      creating_street.value = true;
    } else {
      toast.info(t('address_block.no_cadastre_found') || 'No se han encontrado datos en el catastro para esta dirección.');
    }
  } catch (err) {
    console.error('Error checking cadastre:', err);
    toast.error(t('address_block.catastro_api_error') || 'Error al consultar el catastro.');
  }
}

const isSubRegionOpen = ref(false);
const handleSubRegionEvent = (event) => {
  isSubRegionOpen.value = event;
}
// logic

const updateSelected = (e) => {
  if (e.entity == 'country') {
    country.value = e.id;
    if (e.id.iso_code == 'ES') {
      isDefaultCountry.value = true;
      creating_street.value = false;
    }
    else {
      isDefaultCountry.value = false;
      creating_street.value = true;
    }
    getProvinces();
  }
  else if (e.entity == 'province') {
    province.value = e.id;
    const specialCodes = ['98', '99', 98, 99];
    if (e.id && specialCodes.includes(e.id.code)) {
      creating_street.value = true;
    } else {
      creating_street.value = false;
    }
    getCities();
  }
  else if (e.entity == 'city') {
    city.value = e.id;
    postal_code.value = e.id?.postal_code || '';
  }
  else if (e.entity == 'street_type') {
    street_type.value = e.id;
  }
}

watch(() => props.selectedAddress, () => {
  if (props.selectedAddress == null) resetValues();
  else assignValues()
});


watch(isDefaultCountry, () => {
  city.value = null;
  province.value = null;
});

onMounted(() => {
  getData()
});

</script>

<template>
  <div id="wrapper" class="text-base" :class="{ 'grid grid-cols-2 mt-4 gap-x-10': isSubRegion && showRegion }">
    <div class="flex justify-between items-center mb-2" :class="{ 'grid grid-cols-2': isSubRegion && !showRegion }">
      <H1>{{ $t('address_block.select_address') }}</H1>
    </div>
    <div v-if="loading">
      <AppLoading :text="$t('common.loading')" />
    </div>
    <div v-else class="row grid grid-cols-2 gap-3">
      <div class="mb-2">
        <div class="flex">
          <label for="country" class="block text-sm font-medium text-slate-500 mb-2">{{ $t('address_block.country') }} *</label>
        </div>
        <v-select class="block w-full mr-2 required" :class="{ 'invalid': attemptedSave && country == null }"
          :disabled="loading_countries || countries.length == 0" :model-value="country"
          @update:modelValue="updateSelected({ entity: 'country', id: $event })" :options="countries"></v-select>
      </div>
      <div v-if="isDefaultCountry" class="mb-2">
        <div class="flex">
          <label for="province" class="block text-sm font-medium text-slate-500 mb-2">{{ $t('address_block.province') }} *</label>
        </div>
        <v-select class="block w-full mr-2 required"
          :class="{ 'invalid': attemptedSave && province == null }"
          :disabled="loading_provinces || provinces.length == 0" :model-value="province"
          @update:modelValue="updateSelected({ entity: 'province', id: $event })" :options="provinces"></v-select>
      </div>
      <div class="mb-2">
        <div class="flex">
          <label for="city" class="block text-sm font-medium text-slate-500 mb-2">{{ $t('address_block.city') }} *</label>
        </div>
        <v-select v-if="!isManualCity" class="block w-full mr-2 required"
          :class="{ 'invalid': attemptedSave && city == null }" :disabled="loading_cities || cities.length == 0"
          :model-value="city" @update:modelValue="updateSelected({ entity: 'city', id: $event })"
          :options="cities"></v-select>
        <input v-else type="text" v-model="city" class="input"
          :class="{ 'invalid': attemptedSave && (city == '' || city == null) }">
        </input>
      </div>
      <div class="mb-2">
        <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('address_block.postal_code') }} *</label>
        <input maxlength="10" type="text" v-model="postal_code" v-numeric-only
          :class="{ 'invalid': attemptedSave && postal_code == '' }" class="input" />
      </div>
      <hr class="mb-2 col-span-2" />

      <div class="mb-4 col-span-2">
        <div class="field">
          <div class="flex">
            <label class="pt-2 text-slate-500 mb-2">{{ creating_street ? $t('address_block.new_street') :
              $t('address_block.select_street') }}</label>
          </div>
        </div>
        <StreetPicker v-model="streetModel" :street-types="street_types" :loading-street-types="loading_street_types"
          :city-id="streetSearchCityId" :attempted-save="attemptedSave"
          :can-search="!isManualCity" :can-cadastre="isDefaultCountry" :type-taggable="true"
          @street-selected="onStreetSelected" @cadastre="showCadastre" />
      </div>

      <div v-if="selectedStreetId != null || ((creating_street || isManualCity) && street_name)" class="mb-4 col-span-2">
        <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('address_block.street_number') }}</label>
        <div class="flex items-center mb-2">
          <label class="mr-4">
            <input type="radio" v-model="streetNumberTypeRadio" value="SN" /> {{ t('address_block.no_number') }}
          </label>
          <label>
            <input type="radio" v-model="streetNumberTypeRadio" value="" /> {{ t('common.number') }}
          </label>
        </div>
        <div v-if="streetNumberTypeRadio !== 'SN'" class="grid grid-cols-4 gap-4 mb-2">
          <div>
            <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('common.number') }}</label>
            <input v-numeric-only type="text" v-model="streetNumberNumber" class="input" />
          </div>
          <div>
            <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('address_block.suffix') }}</label>
            <input type="text" maxlength="10" v-model="streetNumberSuffix" class="input" />
          </div>
          <div>
            <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('address_block.end_number') }}</label>
            <input v-numeric-only type="text" v-model="streetNumberEnd" class="input" />
          </div>
          <div>
            <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('address_block.suffix') }}</label>
            <input type="text" maxlength="10" v-model="streetNumberEndSuffix" class="input" />
          </div>
        </div>

        <div class="grid grid-cols-4 gap-4">
          <div>
            <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('address_block.floor') }}</label>
            <input maxlength="10" type="text" v-model="floor" class="input" />
          </div>
          <div>
            <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('address_block.door') }}</label>
            <input maxlength="10" type="text" v-model="door" class="input" />
          </div>
          <div>
            <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('address_block.stair') }}</label>
            <input maxlength="10" type="text" v-model="stair" class="input" />
          </div>
          <div>
            <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('address_block.building') }}</label>
            <input maxlength="50" type="text" v-model="building" class="input" />
          </div>
        </div>

        <div class="grid grid-cols-4 gap-4">
          <div>
            <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('address_block.address_extra') }}</label>
            <input type="text" v-model="address_extra" class="input" />
          </div>
        </div>
      </div>
    </div>
    <slot></slot>
    <div class="flex flex-row-reverse mt-4">
      <button @click="save" :disabled="saving" class="button-primary">
        <Icon name="fa6-solid:floppy-disk" />&nbsp; {{ $t('common.save')
        }}
      </button>
    </div><!-- end contingut botons -->
    <div v-if="isSubRegion && showRegion">
      <div v-if="isCadastreOpen" class="px-2">
        <CatastroRegion :isSubRegionOpen="isSubRegionOpen" :selectedItem="selectedItem" :province="province"
          :city="city" :streetName="street_name" :cadastreData="cadastreResults" @show-subregion="handleSubRegionEvent" @item-clicked="setAddress"></CatastroRegion>
      </div>
    </div>
    <div v-if="!isSubRegion" role="region" id="right_page_address"
      class="fixed h-full border-l border-gray-100 top-0 right-0 transition-transform duration-500 ease py-2 text-base bg-white z-10 w-[95%] overflow-y-auto overflow-x-hidden"
        :class="{
          'translate-x-0': showRegion,
          'translate-x-full': !showRegion,
          'w-1/2': !isSubRegionOpen
        }">
      <div id="region_nav" class="mb-3 px-3">
        <button @click="toggleRegion(false)" class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300">
          <Icon name="fa6-solid:angles-right" class="text-slate-500" />
        </button>
      </div>
      <div v-if="isCadastreOpen" class="px-10">
        <CatastroRegion :isSubRegionOpen="isSubRegionOpen" :selectedItem="selectedItem" :province="province"
          :city="city" :streetName="street_name" :cadastreData="cadastreResults" @show-subregion="handleSubRegionEvent" @item-clicked="setAddress"></CatastroRegion>
      </div>
    </div>
  </div>
</template>

<style>
div#right_page {
    box-shadow: rgba(15, 15, 15, 0.04) 0px 0px 0px 1px, rgba(15, 15, 15, 0.03) 0px 3px 6px, rgba(15, 15, 15, 0.06) 0px 9px 24px;
}

.vs--disabled .vs__actions {
  opacity: 0;
}
</style>