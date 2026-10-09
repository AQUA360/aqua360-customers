<script setup>
import { ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import H1Region from '~/components/atoms/H1Region.vue';
import _ from 'lodash';


const { t } = useI18n();

const props = defineProps({
  adjustment_id: {
    type: Number,
    default: null
  },
  adjustment_interval_id: {
    type: Number,
    default: null
  },
  isSubRegion: false,
  isSubRegionOpen: Boolean,
  operation: {
    type: Object,
    default: null
  },
  is_variable: false
});

const emit = defineEmits(['show-subregion', 'new-pr', 'saved','new-interval-stretch']);
const { $PriceIntervalApiService, $PriceVariableIntervalApiService, $PriceVariableIntervalStretchApiService, $PriceIntervalStretchApiService, $AdjustmentIntervalStretchApiService } = useNuxtApp();
const SubRegion = ref(props.isSubRegionOpen);

const token = ref('')
const priceIntervalStretches = ref([])

const coefficients = ref([]) 
const formules = ref([]) 
const newStretchId = ref(null)
const isSubRegionOpen = ref(false); 

const attemptedSave = ref(false);
const saving = ref(false);

const getData = async () => {
  if (props.adjustment_interval_id != null && newStretchId.value == null) {
    if (props.is_variable) {
      const response = await $PriceVariableIntervalApiService.getDetail(props.adjustment_interval_id);
      token.value = response.token;
      coefficients.value = []
      formules.value = []
      getPriceVariableStretches();
    } else {
      const response = await $PriceIntervalApiService.getDetail(props.adjustment_interval_id);
      token.value = response.token;
      coefficients.value = []
      formules.value = []
      getPriceIntervalStretches();
    }

  } else {
    const response = await $PriceIntervalApiService.save({})
    newStretchId.value = response.id
  }

}

const getPriceIntervalStretches = async () => {
  const response = await $PriceIntervalStretchApiService.getAll('', [], 1, null, false, props.adjustment_interval_id);
  priceIntervalStretches.value = []
  response.results.forEach(item => {
    priceIntervalStretches.value.push(item)
  })
  for (let i = 0; i < priceIntervalStretches.value.length; i++) {
    getCoefficients(priceIntervalStretches.value[i].id);
  }
}

const getPriceVariableStretches = async () => {
  const response = await $PriceVariableIntervalStretchApiService.getAll('', [], 1, null, false, props.adjustment_interval_id);
  priceIntervalStretches.value = []
  response.results.forEach(item => {
    priceIntervalStretches.value.push(item)
  })
  for (let i = 0; i < priceIntervalStretches.value.length; i++) {
    getCoefficients(priceIntervalStretches.value[i].id);
  }
}

const getCoefficients = async (id) => {
  let data = null;
  let interval_stretch_id = id
  const response = await $AdjustmentIntervalStretchApiService.getAll('', [], 1, null, false, props.adjustment_id, props.is_variable ? null : interval_stretch_id, props.is_variable ? interval_stretch_id : null);
  data = response.results;
  console.log("coefficient data");
  console.log(data);
  if (response.results.length > 0) {
    coefficients.value.push({
      id: data[0].id,
      price_interval_stretch: interval_stretch_id,
      value: data[0].coefficient,
      formula: data[0].formula,
      adjustment: data[0].adjustment?.id ? data[0].adjustment?.id : null
    })
  } else {
    coefficients.value.push({
      id: null,
      price_interval_stretch: interval_stretch_id,
      value: props.operation.value == 'ptg'? 1 : 0,
      formula: props.operation.value == 'ptg'? '1' : '',
      adjustment: props.adjustment_id ? props.adjustment_id : null
    })
  }

}

watch(() => props.adjustment_interval_id, () => {
  getData();
});

watch(() => props.operation, () => {
  getData();
});


const save = async () => {
  saving.value = true;
  for( var i in coefficients.value) {
    var coef = coefficients.value[i];
    var is_new = coef.id == null ? true : false;

    var response = await $AdjustmentIntervalStretchApiService.save({
      id: coef.id,
      coefficient: coef.value,
      formula: coef.formula,
      price_interval_stretch: props.is_variable ? null : coef.price_interval_stretch,
      price_variable_stretch: props.is_variable ? coef.price_interval_stretch : null,
      adjustment: props.adjustment_id ? props.adjustment_id : null
    })
    
    coefficients.value[i].id = response.id;
    
    if(is_new) {
      // passem el new-interval-stretch al pare perquè ell li posarà la id adjustment
      emit('new-interval-stretch', response.id)
    }
  } // end for

  saving.value = false;
  emit('saved');
}


onMounted(() => {
  isSubRegionOpen.value = props.isSubRegionOpen
});

getData();

</script>

<template>
  <div class="region__content" :class="{ 'grid grid-cols-2': SubRegion && !isSubRegionOpen }">
    <div>
      <div class="flex justify-between items-center mb-2">
        <H1Region>{{ props.adjustment_interval_id > 0 ? `${$t('common.modify')} ${t('pricing_block.price_interval')}` : $t('pricing_block.new_price_interval') }}</H1Region>
      </div>
      <div class="row grid grid-cols-2 gap-3">
        <div class="mb-2">
          <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('common.identification') }}</label>
          <input type="text" v-model="token" class="input" :class="{ 'invalid': attemptedSave && token == '' }" />
        </div>
      </div>

      <hr />

      <div v-if="operation" class="my-4 ">
        <p v-if="operation.value == 'ptg'" class="pb-3">{{ t('common.operation') + ': ' + operation.label }}<br />
          <em>{{ $t('informative_block.info_adjustment_ptg') }}</em>
        </p>
        <p v-else-if="operation.value == 'ext'" class="pb-3">{{ t('common.operation') + ': ' + operation.label }}<br />
          <em>{{ $t('informative_block.info_adjustment_ext') }}</em>
        </p>
        <p v-else class="pb-3">{{ t('common.operation') + ': ' + operation.label }}</p>

        <AtomsFormulaInfo v-if="operation.value == 'ext' || operation.value == 'var' || operation.value == 'set'" :onlyNumeric=true />

        <div v-if="operation.value == 'ptg' && priceIntervalStretches.length != 0" 
            class="rounded-md border border-gray-300 divide-y bg-white">
          <div class="grid grid-cols-[50px,1fr,60px,1fr,1fr,1fr] gap-3 text-center border-b items-center bg-sky-50">
            <span class="border-r py-2 px-2 text-slate-600">{{ t('pricing_block.stretch') }}</span>
            <span class="border-r py-2 px-2 text-slate-600">{{ t('common.name') }}</span>
            <span class="border-r py-2 px-2 text-slate-600">{{ t('common.limit') }}</span>
            <span class="border-r py-2 px-2 text-slate-600">{{ t('pricing_block.fixed_price') }}</span>
            <span class="border-r py-2 px-2 text-slate-600">{{ t('pricing_block.short_proportional_price') }}</span>
            <span class="border-r py-2 px-2 text-slate-600">{{ t('pricing_block.short_coefficient') }}</span>
          </div>
          <div v-for="item in priceIntervalStretches" :key="item.id"
            class="grid grid-cols-[50px,1fr,60px,1fr,1fr,1fr] gap-3 text-center border-b items-center bg-sky-50">
            <span class="py-2 border-r">{{ item.stretch }} {{ item.id }}</span>
            <span class="py-2 border-r">{{ item.name_stretch }}</span>
            <span class="py-2 border-r">{{ item.end_stretch }}</span>
            <span class="py-2 border-r">{{ item.price }}</span>
            <span class="py-2 border-r">{{ item.proportional_price }}</span>
            <span class="p-1">
              <span v-for="coefficient in coefficients" :key="coefficient.id">
                <input type="text" v-model="coefficient.formula" v-if="coefficient.price_interval_stretch == item.id"
                  class="input" />
              </span>
            </span>
          </div>
        </div>

        <div v-if="(operation.value == 'ext' || operation.value == 'var' || operation.value == 'set') && priceIntervalStretches.length != 0" 
            class="rounded-md border border-gray-300 divide-y bg-white">
          <div class="grid grid-cols-[50px,1fr,50px,1fr,100px,100px] gap-3 text-center border-b items-center bg-sky-50">
            <span class="border-r py-2 px-2 text-slate-600">{{ t('pricing_block.stretch') }}</span>
            <span class="border-r py-2 px-2 text-slate-600">{{ t('common.name') }}</span>
            <span class="border-r py-2 px-2 text-slate-600">{{ t('common.limit') }}</span>
            <span class="border-r py-2 flex gap-2 items-center text-slate-600"><span>{{ t('pricing_block.modifier') }}</span></span>
            <span class="border-r py-2 px-2 text-slate-600">{{ t('pricing_block.fixed_price') }}</span>
            <span class="border-r py-2 px-2 text-slate-600">{{ t('pricing_block.short_proportional_price') }}</span>
          </div>
          <div v-for="item in priceIntervalStretches" :key="item.id"
            class="grid grid-cols-[50px,1fr,50px,1fr,100px,100px] gap-2 text-center border-b items-center bg-sky-50">
            <span class="py-2 border-r">{{ item.stretch }}</span>
            <span class="py-2 border-r">{{ item.name_stretch }}</span>
            <span class="py-2 border-r">{{ item.end_stretch }}</span>
            <span class="p-1 border-r">
              <span><span v-for="coefficient in coefficients" :key="coefficient.id"><input type="text" v-model="coefficient.formula" v-if="coefficient.price_interval_stretch == item.id"
                  class="input" /></span>
              </span>
            </span>
            <span class="py-2 border-r">{{ item.price }}</span>
            <span class="py-2 border-r">{{ item.proportional_price }}</span>
          </div>
        </div>


      </div>
      <div v-else>
        <div class="flex justify-center items-center h-32">
          <span>{{ t('pricing_block.operation_error') }}</span>
        </div>
      </div>

      <hr />
      <div class="flex flex-row-reverse mt-4">
        <button @click="save" :disabled="saving" class="button-primary">
          <Icon name="fa6-solid:floppy-disk" />&nbsp; 
          <span v-if="saving">{{ $t('common.loading') }}...</span>
          <span v-else>{{ $t('common.save') }}</span>
        </button>
      </div><!-- end contingut botons -->

    </div>
  </div><!-- end wrapper -->
</template>