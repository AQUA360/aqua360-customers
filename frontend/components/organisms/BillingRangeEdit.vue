<script setup>
import { toRaw, ref, computed, onMounted } from 'vue';
import { useI18n } from 'vue-i18n';

import _ from 'lodash';
import H1 from '~/components/atoms/H1.vue';
import AddBillingRange from '../molecules/AddBillingRange.vue';
import AddPublication from '../molecules/AddPublication.vue';


const props = defineProps({
  id: Number,
  // When present, "Guardar"/"Cancel·lar" tornen a la tarifa d'origen (PriceRateRegion)
  // en lloc del llistat de rangs, mantenint-la activa via l'id a la URL.
  returnPriceRateId: {
    type: [Number, String],
    default: null,
  },
});

const { t } = useI18n();
const { $BillingRangeApiService, $PublicationApiService } = useNuxtApp();

const attemptedSave = ref(false);
const loading = ref(true);
const saving = ref(false);

const item = ref(null);
const token = ref(null);
const name = ref(null);
const startDate = ref(null)
const endDate = ref(null)
const priceRate = ref(null)

const publications = ref([])
const selectedPublication = ref(null)

const showRegion = ref(false);
const isSubRegionOpen = ref(false);
const editingPublication = ref(false);

// Punt de retorn: si venim d'una tarifa (PriceRateRegion), hi tornem mantenint-la
// activa (mateix patró d'`?id=` que ContractRegion); si no, al llistat de rangs.
const returnUrl = computed(() => {
  return props.returnPriceRateId
    ? `/pricing/price-rates/?id=${props.returnPriceRateId}`
    : '/pricing/billing-ranges/';
});

const goBack = () => {
  return navigateTo(returnUrl.value);
}

const handleSubRegionEvent = (event) => {
  isSubRegionOpen.value = event;
}


const getData = async () => {
  if (props.id != null) {
    const response = await $BillingRangeApiService.getDetail(props.id);
    token.value = response.token;
    name.value = response.name;
    priceRate.value = response.price_rate;
    selectedPublication.value = {value: response.publication?.id, label: response.publication?.name} || null
    startDate.value = response.start;
    endDate.value = response.end;
  }
  else {
    name.value = '';
    token.value =_.random(100000, 999999);
  }

  getPublications();
}

const getPublications = async (page = 1, search = '') => {
  const response = await $PublicationApiService.getAll(search, [] , page); 
  publications.value = []
  response.results.forEach(item => {
    publications.value.push({
      value: item.id,
      label: item.name
    })
  });

  let result = {
    items: publications.value,
    hasNextPage: response && response.next ? true : false
  }
  return result;
}

const createPublication = () => {
  selectedPublication.value = null
  openRegion('publication')
}

var autoSelect = ref(null)

const newPublication = async (new_publication) => {
  await getPublications();
  selectedPublication.value = {
    label: new_publication.name,
    code: new_publication.id
  }
  autoSelect.value = {
    label: new_publication.name,
    code: new_publication.id
  }
  closeAllRegions();
}

const updateSelect = (event, entity) => {
  switch (entity) {
    case 'publication':
      selectedPublication.value = event;
      break;
  }
}

const save = async () => {
  if (isValid()) {
    saving.value = true;
    const selectedOptions = {
      id: props.id,
      name: name.value,
      token: token.value,
      publication: selectedPublication?.value?.value || null,
      price_rate: priceRate?.value.id,
      start: startDate?.value,
      end: endDate?.value
    };

    let br = null;
    br = await $BillingRangeApiService.save(selectedOptions);

    return navigateTo(returnUrl.value)
  }
  else {
    attemptedSave.value = true;
    saving.value = false;
  }
}


const isValid = () => {
  if (name.value == '') return false;
  if (token.value == '') return false;
  return true;
}


const toggleRegion = (force) => {
  showRegion.value = force !== undefined ? force : !showRegion.value;
  if (showRegion.value == false) {
    isSubRegionOpen.value = false;
  }
}

const openRegion = (region) => {
  closeAllRegions();

  if (region == 'publication') {
    editingPublication.value = true;
  }
  showRegion.value = true;
};


const closeAllRegions = () => {
  editingPublication.value = false;
  showRegion.value = false;
};

onMounted(() => {
  getData()
});

</script>

<template>
  <div class="region__content">
    <div>
      <div class="row grid grid-cols-2 gap-3">
        <div class="mb-2">
          <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('common.code') }}</label>
          <input type="text" v-model="token" class="input" :class="{ 'invalid': attemptedSave && token == '' }" />
        </div>
      </div>

      <div class="row grid grid-cols-2 gap-3">
        <div class="mb-2">
          <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('common.name') }} *</label>
          <input required type="text" v-model="name" :class="{ 'invalid': attemptedSave && name == '' }"
            class="input" />
        </div>

        <div class="mb-2">
          <AtomsInfiniteScrollVueSelect :labelText="t('pricing_block.publication_detail')" :loadFunction="getPublications" :item="selectedPublication"
            @update:modelValue="updateSelect($event, 'publication')">
            <button class="w-9 h-9 border-gray-300 border rounded enabled:hover:bg-slate-200 transition-all duration-200"
              @click="createPublication">
            <Icon name="fa6-solid:plus" class="text-md text-slate-600" />
            </button>
          </AtomsInfiniteScrollVueSelect>
        </div>
      </div>
      <div class="row grid grid-cols-2 gap-3">
        
        <div class="mb-2">
          <AtomsInputDate v-model="startDate" :label="t('common.start_date')" class="mb-2"/>
        </div>
        <div class="mb-2">
          <AtomsInputDate v-model="endDate" :label="t('common.end_date')" class="mb-2"/>
        </div>
      </div>
      
      <hr />
      
      <hr />
      <div class="flex flex-row-reverse mt-4 gap-2">
        <button @click="save" :disabled="saving" class="button-primary">
          <Icon name="fa6-solid:floppy-disk" />&nbsp; {{ $t('common.save') }}
        </button>
        <button @click="goBack" :disabled="saving" type="button" class="button-default">
          <Icon name="fa6-solid:arrow-left" />&nbsp; {{ $t('common.go_back') }}
        </button>
      </div><!-- end contingut botons -->
      
    </div>

    <div role="region" id="right_page" class="fixed h-full border-l border-gray-100 top-0 right-0 transition-all duration-500 ease py-2 text-base bg-white z-10"
      :class="{ 'translate-x-0': showRegion, 'translate-x-[2000px]': !showRegion, 'w-[95%]': isSubRegionOpen, 'w-1/2': !isSubRegionOpen }">
      <div id="region_nav" class="mb-3 px-3">
        <button @click="toggleRegion(false)"
          class="px-2 py-1 text-sky-500 hover:bg-slate-200 rounded active:bg-slate-300">
          <Icon name="fa6-solid:angles-right" class="text-slate-500" /></button>
      </div>
      <div class="px-10">
        <MoleculesAddPublication :id="null" v-if="editingPublication" @new-publication="newPublication"></MoleculesAddPublication>
      </div>
    </div>
  </div><!-- end wrapper -->
</template>
