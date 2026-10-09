<script setup>
import { ref, onMounted, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import { AdjustmentConditionOperationChoices, AdjustmentConditionQuantityDefaultChoices } from '~/utils/adjustment-condition';
import H1Region from '../atoms/H1Region.vue';

const props = defineProps({
  condition: {
    type: Object,
    default: () => ({ name: '', quantity: '', operation: '', formula: '' })
  }
});
const emit = defineEmits(['save']);

const { t } = useI18n();
const { $VariableTypeApiService, $ConfiglistApiService } = useNuxtApp();

const selectedToken = ref(null);
const newCondition = ref({ ...props.condition });
const variables_types = ref([]);

const typeOptions = ref([])



const getData = async () => {
  const response = await $VariableTypeApiService.getAllUnpaginated();
  // si no hi ha response.results retornar error
  if (!response) return;
  if (response.error) {
    console.error('error getAllVariableTypes', response.error);
    return;
  }
  if (!response) return;

  variables_types.value = response;
  
  getConditionQuantities();
  getConditionOperations();
  if(newCondition.value.quantity && newCondition.value.quantity.url && newCondition.value.quantity.url.length > 0){
    getSelectData(newCondition.value.quantity.url, variables_types);
  }
}

const getSelectData = async () => {
  if (!newCondition.value.quantity.url || newCondition.value.quantity.url.length == 0) return;
  typeOptions.value = [];
  try{
    let data = await $ConfiglistApiService.getAll(newCondition.value.quantity.url);
    data.results?.forEach(item => {
      typeOptions.value.push({
        code: item.id,
        label: item.name,
        token: item.token
      })
    });
    //set conditionsOperation to only equal
    conditionOperations.value = ['eq'];
    newCondition.value.operation = "eq"
    if(newCondition.value.formula){
      selectedToken.value = typeOptions.value.filter(item => item.token === newCondition.value.formula)[0]
    }
  }catch(error){
    console.error(error);
  }
}

watch(() => props.condition, (newVal) => {
  newCondition.value = { ...newVal };
  getData()
}, { immediate: true });


const conditionOperations = ref([]);
const conditionQuantities = ref([]);

const getConditionOperations = () => {
  conditionOperations.value = Object.keys(AdjustmentConditionOperationChoices);
};

const getConditionQuantities = () => {
  conditionQuantities.value = Object.keys(AdjustmentConditionQuantityDefaultChoices).map(key => {
    return {
      value: key,
      label: t(AdjustmentConditionQuantityDefaultChoices[key][0]),
      url: AdjustmentConditionQuantityDefaultChoices[key][1]
    }
  });

  // s'haurien de recorrer les variables_types i afegir-les a conditionQuantities, de tal manera que quedi: `value: "variable." + variable.token, label: "Variable:" + variable.name`
  variables_types.value.forEach(variable => {
    conditionQuantities.value.push({
      value: `variable.${variable.token}`,
      label: `Variable: ${variable.name} (${variable.data_type})`,
      url: ''
    });
  });
};


const addCondition = () => {
  if (newCondition.value.name && newCondition.value.quantity && newCondition.value.operation) {
    emit('save', { ...newCondition.value });
    newCondition.value = { name: '', quantity: '', operation: '', formula: '' };
  }
};


const updateSelect = (event, entity) => {
  switch (entity) {
    case 'quantity':
      newCondition.value.quantity = event;
      if (event.url.length > 0) {
        getSelectData(event.url, variables_types);
      }else{
        getConditionOperations();
      }
      break;
    case 'operation':
      newCondition.value.operation = event;
      break;
    case 'formula':
      selectedToken.value = event;
      newCondition.value.formula = event.token;
      break;
  }
}

onMounted(() => {
  getData();
});
</script>

<template>
  <H1Region>{{ $t('common.add') }} {{ $t('pricing_block.new_condition') }}</H1Region>
  <form name="add_condition" class="mt-3" @submit.prevent="addCondition" autocomplete="off">

    <div class="mb-4">
      <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('common.name') }}</label>
      <input type="text" v-model="newCondition.name" class="input" autocomplete="off" />
    </div>
    <div class="grid grid-cols-2 gap-3">
      <div class="mb-4">
        <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('common.quantity') }}</label>
        <v-select class="block w-full mr-1 required" :model-value="newCondition.quantity" 
          :options="conditionQuantities" @update:modelValue="updateSelect($event, 'quantity')" />
      </div>
      <!-- <div class="mb-2">
          <AtomsInfiniteScrollVueSelect :labelText="t('common.quantity')" :loadFunction="getConditionQuantitiesScroll" :item="newCondition.quantity"
            @update:modelValue="updateSelect($event, 'quantity')">
          </AtomsInfiniteScrollVueSelect>
        </div> -->
      <div class="mb-4">
        <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('common.operation') }}</label>
        <select v-model="newCondition.operation" class="input" autocomplete="off">
          <option v-for="operation in conditionOperations" :key="operation" :value="operation">
            {{ t(AdjustmentConditionOperationChoices[operation]) }}
          </option>
        </select>
      </div>
    </div>
    <div class="mb-4">
      <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('common.value') }} / {{ t('pricing_block.for') }}</label>
      <v-select v-if="newCondition.quantity && newCondition.quantity?.url?.length > 0" class="block w-full mr-1 required" :model-value="selectedToken" :options="typeOptions"
        @update:modelValue="updateSelect($event, 'formula')" />
      <textarea v-else v-model="newCondition.formula" class="input" autocomplete="off"></textarea>
    </div>
    <button type="submit" class="button-primary flex gap-3 items-center">
      <icon name="fa6-solid:floppy-disk"></icon><span>{{ t('common.save') }}</span>
    </button>
  </form>
  
  <hr class="my-6" />
  <AtomsFormulaInfo />
  <!-- <div class="mb-3">
    <p class="text-lg font-semibold mb-2">{{ t('pricing_block.variables_formula') }}</p>
    <ul class="">
      <li v-for="v in variables_types" :key="v.token" class="mb-2 inline-block items-center mr-2">
        <span class="text-slate-500 text-sm">
          ({{ v.name }})
        </span>
        <abbr :title="`${v.name} (${v.data_type})`" class="inline-block bg-gray-100 text-gray-800 font-mono p-1 hover:bg-gray-200 rounded no-underline">
          %variable.{{ v.token }}
        </abbr>
      </li>
    </ul>
    <ul>
      <li class="mb-2 inline-block items-center mr-2">
        <abbr class="inline-block bg-gray-100 text-gray-800 font-mono p-1 rounded no-underline">
          %contract.persons
        </abbr>
      </li>
      <li class="mb-2 inline-block items-center mr-2">
        <abbr class="inline-block bg-gray-100 text-gray-800 font-mono p-1 rounded no-underline">
          %contract.use_type
        </abbr>
      </li>
      <li class="mb-2 inline-block items-center mr-2">
        <abbr class="inline-block bg-gray-100 text-gray-800 font-mono p-1 rounded no-underline">
          %contract.client_type
        </abbr>
      </li>
      <li class="mb-2 inline-block items-center mr-2">
        <abbr class="inline-block bg-gray-100 text-gray-800 font-mono p-1 rounded no-underline">
          %contract.client_type
        </abbr>
      </li>
    </ul>
    <ul>
      <li class="mb-2 inline-block items-center mr-2">
        <abbr class="inline-block bg-gray-100 text-gray-800 font-mono p-1 rounded no-underline">
          %supplypoint.type
        </abbr>
      </li>
    </ul>
  </div> -->

</template>
