<script setup>
import { ref, resolveDirective, watch } from 'vue';
import { useRouter } from 'vue-router';
import { useI18n } from 'vue-i18n';
import H1Region from '~/components/atoms/H1Region.vue';
import AddPublication from './AddPublication.vue';
import { UnitsDataTypeChoices } from '~/utils/pricing';
import _ from 'lodash';


const { t } = useI18n();

const props = defineProps({
  id: Number, // ID de l'element
  isSubRegion: false,
  isSubRegionOpen: Boolean
});

const emit = defineEmits(['show-subregion', 'new-stretch']);
const { $PriceIntervalStretchApiService } = useNuxtApp();
const SubRegion = ref(props.isSubRegionOpen);

const token = ref('')
const fixedPrice = ref(null)
const proportionalPrice = ref(null)
const startStretch = ref(null)
const endStretch = ref(null)

const units = ref([])
const selectedUnit = ref(null)

const isSubRegionOpen = ref(false);

const showRegionDetailComponent = ref(null);
const regionDetailId = ref(null);

const attemptedSave = ref(false);
const saving = ref(false);


const getData = async () => {
  if (props.id != null) {
    const response = await $PriceIntervalStretchApiService.getDetail(props.id);
    token.value = null;
    token.value = response.token;
    fixedPrice.value = null;
    fixedPrice.value = response.price;
    proportionalPrice.value = null;
    proportionalPrice.value = response.proportional_price;
    startStretch.value = null;
    startStretch.value = response.start_stretch;
    endStretch.value = null;
    endStretch.value = response.end_stretch;
    
  }
  
  getUnits();
}

const getUnits = async () => {
  units.value = []
  units.value = Object.keys(UnitsDataTypeChoices).map(key => {
    return {
      value: key,
      label: t(UnitsDataTypeChoices[key])
    }
  })
}


const save = async () => {
  if (isValid()) {
    saving.value = true;
    const selectedOptions = {
      token: token.value,
      price: fixedPrice?.value?.toString().replace(',','.') || null,
      proportional_price: proportionalPrice?.value?.toString().replace(',','.') || null,
      units: selectedUnit?.value?.value || null,
      start_stretch: startStretch?.value || null,
      end_stretch: endStretch?.value || null
    };
    let stretch = null;
    stretch = await $PriceIntervalStretchApiService.save(selectedOptions);

    emit('new-stretch', stretch);
  }
  else {
    attemptedSave.value = true;
    saving.value = false;
  }
}


const updateSelect = (event, entity) => {
  switch (entity) {
    case 'units':
      selectedUnit.value = event;
      break;
  }
}

const isValid = () => {
  if (token.value == '') return false;
  if ((proportionalPrice && !fixedPrice) || (!proportionalPrice && fixedPrice)) return false;
  return true;
}

watch(() => props.id, () => {
  getData();
  closeSubRegion();
});

onMounted(() => {
  getData()
});

watch(() => props.isSubRegionOpen, (newValue) => {
  SubRegion.value = newValue;
});

getData();


const closeSubRegion = function () {
  SubRegion.value = false;
  showRegionDetailComponent.value = null;
  emit('show-subregion', false);
}


</script>

<template>
  
  <div class="region__content">
    <div class="transition-all duration-500 ease" :class="{ 'mr-[50%]': SubRegion }">
      <div class="flex justify-between items-center mb-2">
        <H1Region>{{ props.id > 0 ?  `${$t('common.modify')} ${t('common.range')}` : $t('pricing_block.new_billing_range') }}</H1Region>
      </div>
      <div class="row grid grid-cols-2 gap-3">
        <div class="mb-2">
          <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('common.identification') }}</label>
          <input type="text" v-model="token" class="input" :class="{ 'invalid': attemptedSave && token == '' }" />
        </div>
       
      </div>

      <div class="row grid grid-cols-2 gap-3">
        <div class="mb-2">
          <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('pricing_block.stretch_start') }}</label>
          <input type="number" v-model="startStretch" class="input" />
        </div>
        <div class="mb-2">
          <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('pricing_block.stretch_end') }}</label>
          <input type="number" v-model="endStretch" class="input" :class="{ 'invalid': attemptedSave && endStretch == '' }"/>
        </div>
      </div>

      <hr />
      <div class="row grid grid-cols-2 gap-3">
        <div class="mb-2">
          <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('pricing_block.fixed_price') }}</label>
          <input type="number" v-model="fixedPrice" :disabled="proportionalPrice || proportionalPrice>0" class="input" />
        </div>
        <div class="mb-2">
          <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('pricing_block.proportional_price') }}</label>
          <input type="number" :disabled="fixedPrice || fixedPrice>0" v-model="proportionalPrice" class="input" />
        </div>
        
      </div>
      <div class="row grid grid-cols-2 gap-3">
        <div class="mb-4">
          <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('common.units') }}</label>
          <v-select class="block w-full mr-1 required" :model-value="selectedUnit"
            @update:modelValue="updateSelect($event, 'units')" :options="units" />
        </div>
      </div>
      
      <hr />
      <div class="flex flex-row-reverse mt-4">
        <button @click="save" :disabled="saving" class="button-primary">
          <Icon name="fa6-solid:floppy-disk" />&nbsp; {{ $t('common.save') }}
        </button>
      </div><!-- end contingut botons -->

    </div>
    <div v-if="SubRegion == true" role="region" id="subregion"
      class="fixed h-full border-l border-gray-100 top-0 right-0 transition-transform duration-500 ease py-2 text-base bg-white z-10 w-[50%] overflow-y-auto overflow-x-hidden"
      :class="{ 'translate-x-0': SubRegion, 'translate-x-full': !SubRegion }">
      <div id="region_nav" class="mb-3 px-3">
        <button @click="closeSubRegion()" class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300">
          <Icon name="fa6-solid:angles-right" class="text-slate-500" />
        </button>
      </div>
      <div class="px-10">
        <AddPublication :id="null" v-if="showRegionDetailComponent === 'PublicationRegion'"
          :isSubRegionOpen="isSubRegionOpen" @show-subregion="handleSubRegionEvent" :object="regionDetailId"
          @new-publication="newPublication" />
      </div>
    </div>
  </div><!-- end wrapper -->
</template>