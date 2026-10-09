<script setup>
import { ref, resolveDirective, watch } from 'vue';
import { useRouter } from 'vue-router';
import { useI18n } from 'vue-i18n';
import H1Region from '~/components/atoms/H1Region.vue';
import debounce from 'lodash.debounce';
import AddPublication from './AddPublication.vue';
import EditFieldDialog from '~/components/molecules/EditFieldDialog.vue';
import _ from 'lodash';
import AddPriceIntervalStretch from './AddPriceIntervalStretch.vue';
import priceIntervalStretchApi from '~/plugins/api/pricing/price-interval-stretch-api';
import { is } from 'date-fns/locale';
import PriceIntervalStretchesEdit from '../organisms/PriceIntervalStretchesEdit.vue';


const { t } = useI18n();

const props = defineProps({
  id: {
    type:Number,
    default:null
   }, // ID de l'element
  isSubRegion: false,
  isSubRegionOpen: Boolean
});

const emit = defineEmits(['show-subregion', 'new-pr', 'changed']);
const { $PriceIntervalApiService, $PriceIntervalStretchApiService } = useNuxtApp();
const SubRegion = ref(props.isSubRegionOpen);

const token = ref('')
const priceIntervalStretches = ref([])
const selectedUnits = ref(null)

const newStretchId = ref(null)

const selectedStretch = ref(null)

const showRegion = ref(false);
const isSubRegionOpen = ref(false);
const editingIntervalStretch = ref(false);

const showRegionDetailComponent = ref(null);
const regionDetailId = ref(null);

const attemptedSave = ref(false);
const saving = ref(false);


const getData = async () => {
  if (props.id != null && newStretchId.value == null) {
    const response = await $PriceIntervalApiService.getDetail(props.id);
    token.value = response.token;
    selectedUnits.value = response.units;
    getPriceIntervalStretches();
  }else{
    const response = await $PriceIntervalApiService.save({})
    newStretchId.value = response.id
    selectedUnits.value = 'm3';
  }
  
}

const getPriceIntervalStretches = async () => {
  const response = await $PriceIntervalStretchApiService.getAll( '', [], 1, null, false, props.id);
  priceIntervalStretches.value = []
  response.results.forEach(item => {
    priceIntervalStretches.value.push(item)
  })
}

const save = debounce(async (isSaving) => {
  if (isValid()) {
    saving.value = true;
    const selectedOptions = {
      id: props.id? props.id : newStretchId.value,
      token: token.value,
      units: selectedUnits.value,
    };
    
    let pr = null;
    pr = await $PriceIntervalApiService.save(selectedOptions);

    if (isSaving) {
      emit('new-pr', pr);
    }
    saving.value = false;
  }
  else {
    attemptedSave.value = true;
    saving.value = false;
  }
},200)


const isValid = () => {
  if (token.value == '') return false;
  
  return true;
}

const newStretch = async (new_stretch) => {
  
  if(props.id){
    new_stretch.price_interval = props.id
    await $PriceIntervalStretchApiService.save(new_stretch)
  }else{
    priceIntervalStretches.value.push(new_stretch)
  }
  
  closeAllRegions()
  getData()
}


const openRegion = (region) => {
  closeAllRegions();

  if (region == 'StretchRegion') {
    editingIntervalStretch.value = true;
  }
  showRegion.value = true;
};

const closeAllRegions = () => {
  editingIntervalStretch.value = false;

  showRegion.value = false;
};

const handleSubRegionEvent = (event) => {
  isSubRegionOpen.value = event;
}

const handleRefreshList = () => {
  getData();
  emit('changed');
}
const handleChanged = () => {
  emit('changed');
}

watch(() => props.id, () => {
  getData();
  closeSubRegion();
});

watch(() => props.isSubRegionOpen, (newValue) => {
  SubRegion.value = newValue;
});

onMounted(() => {
  isSubRegionOpen.value = props.isSubRegionOpen
});

getData();


const closeSubRegion = function () {
  SubRegion.value = false;
  showRegionDetailComponent.value = null;
  emit('show-subregion', false);
}

const toggleRegion = (force) => {
  
  showRegion.value = force !== undefined ? force : !showRegion.value;
  if (showRegion.value == false) {
    isSubRegionOpen.value = false;
  }
}

</script>

<template>
  <div class="region__content" :class="{ 'grid grid-cols-2': SubRegion && !isSubRegionOpen }">
    <div>
      <div class="flex justify-between items-center mb-2">
        <H1Region>{{ props.id > 0 ? $t('pricing_block.edit_price_interval') : $t('pricing_block.new_price_interval') }}</H1Region>
      </div>
      <div class="row grid grid-cols-2 gap-3">
        <div class="mb-2">
          <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('common.identificator') }}</label>
          <input type="text" v-model="token" class="input" @change="save(false)"
          :class="{ 'invalid': attemptedSave && token == '' }" />
        </div>
        <div class="mb-2 px-5">
          <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('pricing_block.select_units') }}</label>
          <div class="flex items-center gap-5 mt-3">
            <label class="flex items-center">
              <input type="radio" value="m3" v-model="selectedUnits" class="mr-2">
              m3
            </label>
            <label class="flex items-center">
              <input type="radio" value="dm_met" v-model="selectedUnits" class="mr-2">
              {{ $t('service_block.meter_caliber') }}
            </label>
            <label class="flex items-center">
              <input type="radio" value="dm_con" v-model="selectedUnits" class="mr-2">
              {{ $t('service_block.connection_caliber') }}
            </label>
          </div>
        </div>
      </div>

      <hr />

      <PriceIntervalStretchesEdit :id="props.id? props.id : newStretchId"/>

      <hr />
      <div class="flex flex-row-reverse mt-4">
        <button @click="save(true)" :disabled="saving" class="button-primary">
          <Icon name="fa6-solid:floppy-disk" />&nbsp; {{ $t('common.save') }}
        </button>
      </div><!-- end contingut botons -->

    </div>
    <div role="region" id="right_page"
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
      <div class="px-10">
        <AddPriceIntervalStretch :id="selectedStretch" v-if="editingIntervalStretch"
          :isSubRegionOpen="isSubRegionOpen" @show-subregion="handleSubRegionEvent" :object="regionDetailId"
          @new-stretch="newStretch" />
      </div>
    </div>
  </div><!-- end wrapper -->
</template>