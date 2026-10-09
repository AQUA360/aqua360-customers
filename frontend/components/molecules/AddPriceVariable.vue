<script setup>
import { ref, resolveDirective, watch } from 'vue';
import { useRouter } from 'vue-router';
import { useI18n } from 'vue-i18n';
import H1Region from '~/components/atoms/H1Region.vue';
import AddPublication from './AddPublication.vue';
import EditFieldDialog from '~/components/molecules/EditFieldDialog.vue';
import _ from 'lodash';
import AddPriceIntervalStretch from './AddPriceIntervalStretch.vue';
import { is } from 'date-fns/locale';
import VarFixedPriceIntervalStretchesEdit from '../organisms/PriceVariableStretchesEdit.vue';


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
const { $PriceVariableIntervalApiService, $PriceVariableIntervalStretchApiService } = useNuxtApp();
const SubRegion = ref(props.isSubRegionOpen);

const token = ref('')
const line_item_types = ref([])
const priceIntervalStretches = ref([])
const selectedUnits = ref(null)

const newStretchId = ref(null)

const showRegion = ref(false);
const isSubRegionOpen = ref(false);

const showRegionDetailComponent = ref(null);

const attemptedSave = ref(false);
const saving = ref(false);


const getData = async () => {
  if (props.id != null && newStretchId.value == null) {
    const response = await $PriceVariableIntervalApiService.getDetail(props.id);
    token.value = response.token;
    selectedUnits.value = response.units;
    line_item_types.value = response.line_item_types;
    getPriceIntervalStretches();
  }else{
    const response = await $PriceVariableIntervalApiService.save({})
    newStretchId.value = response.id
    selectedUnits.value = 'm3';
  }
  
}

const getPriceIntervalStretches = async () => {
  const response = await $PriceVariableIntervalStretchApiService.getAll( '', [], 1, null, false, props.id);
  priceIntervalStretches.value = []
  response.results.forEach(item => {
    priceIntervalStretches.value.push(item)
  })
}


const save = async () => {
  if (isValid()) {
    saving.value = true;
    const selectedOptions = {
      id: props.id? props.id : newStretchId.value,
      token: token.value,
      units: selectedUnits.value,
    };
    
    let pr = null;
    pr = await $PriceVariableIntervalApiService.save(selectedOptions);

    emit('new-pr', pr);
  }
  else {
    attemptedSave.value = true;
    saving.value = false;
  }
}


const isValid = () => {
  if (token.value == '') return false;
  
  return true;
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


</script>

<template>
  <div class="region__content" :class="{ 'grid grid-cols-2': SubRegion && !isSubRegionOpen }">
    <div>
      <div class="flex justify-between items-center mb-2">
        <H1Region>{{ props.id > 0 ? $t('pricing_block.edit_variable_price_range') : $t('pricing_block.new_variable_price_range') }}</H1Region>
        <div v-if="line_item_types.length > 1" class="flex items-center gap-2 bg-orange-50 border border-orange-500 rounded-md p-1 text-orange-500 text-sm font-medium">
          <abbr :title="line_item_types.map(item => `${item.name} ${item.price_rate_name}`).join(', ')">
            {{ $t('common.applied_on') }} {{ line_item_types.length }} {{ $t('pricing_block.ranges') }}
          </abbr>
        </div>
      </div>
      <div class="row grid grid-cols-2 gap-3">
        <div class="mb-2">
          <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('common.identification') }}</label>
          <input type="text" v-model="token" class="input" :class="{ 'invalid': attemptedSave && token == '' }" />
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

      <!-- TODO PASS ID -->
      <VarFixedPriceIntervalStretchesEdit :id="props.id? props.id : newStretchId"/>

      <hr />
      <div class="flex flex-row-reverse mt-4">
        <button @click="save" :disabled="saving" class="button-primary">
          <Icon name="fa6-solid:floppy-disk" />&nbsp; {{ $t('common.save') }}
        </button>
      </div><!-- end contingut botons -->

    </div>
    
  </div><!-- end wrapper -->
</template>