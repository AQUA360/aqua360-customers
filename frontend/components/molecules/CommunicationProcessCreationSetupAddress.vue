<script setup>
import SearchEntityInput from './SearchEntityInput.vue';

const props = defineProps({
  address_data: Object,
})

const { t } = useI18n();
const emit = defineEmits(['change'])
const { $ConfiglistApiService, $StreetApiService, $AddressApiService } = useNuxtApp();

const streets = ref([])
const cities = ref([])
const provinces = ref([])
const numbers = ref([])

const selectedStreet = ref(null)
const selectedCity = ref(null)
const postalCode = ref(null)
const selectedProvince = ref(null)
const selectedAddresses = ref([])
const selectedNumbers = ref(null)

const loadingStreets = ref(false)
const loadingCities = ref(false)
const loadingProvinces = ref(false)
const loadingNumbers = ref(false)

const contract_filter_data = ref({})

const fetchConfigData = async (service, entity, targetArray, loading) => {
  try {
    loading.value = true;
    const data = await $ConfiglistApiService.getAll(service + '/' + entity);
    targetArray.value = [];

    if (data.results) {
      data.results.forEach(data => {
        targetArray.value.push({
          label: data.name ? data.name : data.title ? data.title : data.token,
          code: data.id
        })
      });
    }
  } catch (error) {
    console.error(`Error fetching ${entity}:`, error);
  } finally {
    loading.value = false;
  }
}

const loadSelectData = async () => {
  await fetchConfigData('coredata', 'city', cities, loadingCities);
  await fetchConfigData('coredata', 'province', provinces, loadingProvinces);
}

const getStreets = async (page = 1, search = '') => {
  let response = null;
  loadingStreets.value = true;
  try {
    const cityId = selectedCity.value ? selectedCity.value.code : null;
    response = await $StreetApiService.getAll(search, [], page, null, false, cityId);

    const items = response.results.map(item => ({
      value: item.id,
      label: item.type_abbreviation + ' - ' + item.name
    }));

    streets.value = items;

    return {
      items: items,
      hasNextPage: response && response.next ? true : false
    };
  } catch (error) {
    console.error(`Error fetching streets:`, error);
    return {
      items: [],
      hasNextPage: false
    };
  } finally {
    loadingStreets.value = false;
  }
}

const onAddressSelected = async (event) => {
  selectedStreet.value = null
  selectedCity.value = null
  postalCode.value = null
  selectedProvince.value = null
  selectedNumbers.value = null
  if (selectedAddresses.value.includes(event)) {
    selectedAddresses.value = selectedAddresses.value.filter(a => a.id !== event.id)
  }
  else {
    selectedAddresses.value.push(event)
  }
  await emitChange()
}

const removeSelectedAddress = (address) => {
  selectedAddresses.value = selectedAddresses.value.filter(a => a.id !== address.id)
  emitChange()
}

const updateSelect = (event, entity) => {
  switch (entity) {
    case 'street':
      selectedNumbers.value = null
      selectedStreet.value = event;
      emitChange()
      break;
    case 'number':
      selectedNumbers.value = event;
      emitChange()
      break;
  }
}

const loadProvinceCities = async () => {
  if (selectedProvince.value) {
    cities.value = []
    console.log(selectedProvince.value)
    const response = await $AddressApiService.getCitiesByProvince(selectedProvince.value.code)
    response.results.forEach(item => {
      cities.value.push({
        code: item.id,
        label: item.name
      })
    });
    if (selectedCity.value && !cities.value.includes(selectedCity.value)) {
      selectedCity.value = null
      await getStreets(1)
    }
  }
}

const loadNumbers = async (page) => {
  let response = null;
  loadingNumbers.value = true;
  if (selectedStreet.value && selectedStreet.value.value) {
    try {
      const streetId = selectedStreet.value ? selectedStreet.value.value : null;
      response = await $StreetApiService.getStreetNumber(streetId, page)
      console.log(response)
      const items = response.results.map(item => ({
        value: item.id,
        label: `${t('common.type')}: ${item.number_type?.type}   ${t('common.short_number')}: ${item.number ? item.number : '/'}   ${t('address_block.short_end_number')}: ${item.number_suffix ? item.number_suffix : '/'}   ${t('address_block.suffix')}: ${item.number_end ? item.number_end : '/'}   ${t('address_block.final_suffix')}: ${item.number_end_suffix ? item.number_end_suffix : '/'}`
      }));

      numbers.value = items;

      return {
        items: items,
        hasNextPage: response && response.next ? true : false
      };
    } catch (error) {
      console.error(`Error fetching streets:`, error);
      return {
        items: [],
        hasNextPage: false
      };
    } finally {
      loadingNumbers.value = false;
    }
  }
}

const loadData = async (contractData) => {
  if (contractData?.street) selectedStreet.value = streets.value.filter(s => contractData?.street === s.value)
  if (contractData?.city) selectedCity.value = cities.value.filter(c => contractData?.city === c.code)
  if (contractData?.province) selectedProvince.value = provinces.value.filter(p => contractData?.province === p.code)
  if (contractData?.postal_code) postalCode.value = contractData?.postal_code
  if (contractData?.addresses) selectedAddresses.value = contractData?.addresses
  if (contractData?.numbers) selectedNumbers.value = numbers.value.filter(n => contractData?.numbers === n.value)
}


const emitChange = () => {
  contract_filter_data.value = {
    street: selectedStreet.value ? selectedStreet.value.value : null,
    postal_code: postalCode.value,
    numbers: selectedNumbers.value ? selectedNumbers.value.value : null,
    city: selectedCity.value ? selectedCity.value.code : null,
    province: selectedProvince.value ? selectedProvince.value.code : null,
    addresses: selectedAddresses.value
  }
  emit('change', contract_filter_data.value)
}

onMounted(async () => {
  await loadSelectData()
  await loadData(props.address_data)
})

watch(selectedStreet, async () => {
  await loadNumbers(1)
  if (selectedNumbers.value && !numbers.value.includes(selectedNumbers.value)) {
    selectedNumbers.value = null
  }
})

watch(selectedProvince, async () => {
  await loadProvinceCities()
})

watch(selectedCity, async () => {
  await getStreets(1)
  if (selectedStreet.value && !streets.value.includes(selectedStreet.value)) {
    selectedStreet.value = null
  }
})

watch([
  postalCode,
  selectedCity,
  selectedProvince,
], async () => {
  if (selectedAddresses.value.length > 0) {
    if (postalCode.value || selectedCity.value || selectedProvince.value) {
      selectedAddresses.value = []
    }
  }
  await emitChange()
}, { deep: true });

watch(props.address_data, async (newVal) => {
  await loadData(newVal)
}, { deep: true });

</script>

<template>
  <div class="py-3 bg-white rounded-lg shadow-sm">

    <div class="grid grid-cols-2 gap-4">

      <SearchEntityInput :service="$AddressApiService" @select="onAddressSelected"
        :title="$t('search_block.search_address')" :result_value="'address_complete'" class="mt-auto" />

      <div v-if="selectedAddresses?.length > 0" class="mb-2">
        <label class="block text-sm font-medium text-slate-600 mb-2">{{ $t('customer_service_block.selected_addresses') }}</label>
        <div class="flex flex-wrap gap-2 ">
          <span v-for="address in selectedAddresses" :key="address.id"
            class="group relative bg-slate-100 text-slate-800 px-3 py-1 rounded-full text-sm border border-slate-300 flex items-center gap-2">
            <span>
              {{ address.address_complete }}
            </span>
            <button @click="removeSelectedAddress(address)"
              class="absolute right-0 top-0 h-4 w-4 bg-white rounded-full text-slate-500 opacity-0 hover:text-slate-700 hover:underline group-hover:opacity-100 transition-all duration-300">
              <Icon name="fa6-solid:xmark"
                class="text-red-500 text-sm m-auto opacity-0 group-hover:opacity-100 m-auto" />
            </button>
          </span>
        </div>
      </div>
      <span v-else></span>

      <div>
        <label class="block text-sm font-medium text-slate-600 mb-2">{{ $t('address_block.province') }}</label>
        <v-select class="block w-full mr-1 custom-select" v-model="selectedProvince" :options="provinces"
          :loading="loadingProvinces" />
      </div>

      <div>
        <label class="block text-sm font-medium text-slate-600 mb-2">{{ $t('address_block.city') }}</label>
        <v-select class="block w-full mr-1 custom-select" v-model="selectedCity" :options="cities"
          :loading="loadingCities" />
      </div>

      <AtomsInfiniteScrollVueSelect :labelText="t('address_block.street')" :loadFunction="getStreets" :item="selectedStreet"
        @update:modelValue="updateSelect($event, 'street')">
        <!-- <button class="w-9 h-9 border-gray-300 border rounded enabled:hover:bg-slate-200 transition-all duration-200"
          @click="createStreet">
          <Icon name="fa6-solid:plus" class="text-md text-slate-600" />
        </button> -->
      </AtomsInfiniteScrollVueSelect>

      <!-- <AtomsInfiniteScrollVueSelect :labelText="t('Núm.')" :loadFunction="loadNumbers" :item="selectedNumbers"
        @update:modelValue="updateSelect($event, 'number')">
      </AtomsInfiniteScrollVueSelect> -->

      <div class="mb-6">
        <label class="block text-sm font-medium text-slate-600 mb-2">{{ $t('address_block.postal_code') }}</label>
        <input class="input mt-1" type="text" v-model="postalCode" />
      </div>


    </div>
  </div>
</template>

<style scoped>
.grid {
  transition: all 0.3s ease;
}
</style>