<script setup>
import { ref, onMounted, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import { AdjustmentConditionOperationChoices } from '~/utils/adjustment-condition';
import { MessageConditionQuantityDefaultChoices } from '~/utils/messages';
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
  const response = await $VariableTypeApiService.getAll();
  // si no hi ha response.results retornar error
  if (!response) return;
  if (response.error) {
    console.error('error getAllVariableTypes', response.error);
    return;
  }
  if (!response.results) return;

  variables_types.value = response.results;

  getConditionQuantities();
  getConditionOperations();
  if (newCondition.value.quantity && newCondition.value.quantity.url && newCondition.value.quantity.url.length > 0) {
    getSelectData(newCondition.value.quantity.url, variables_types);
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
  conditionQuantities.value = Object.keys(MessageConditionQuantityDefaultChoices).map(key => {
    return {
      value: key,
      label: t(MessageConditionQuantityDefaultChoices[key][0]),
      url: MessageConditionQuantityDefaultChoices[key][1]
    }
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
  <H1Region>{{ $t('common.add') }} {{ t('pricing_block.condition') }}</H1Region>
  <form name="add_condition" class="mt-3" @submit.prevent="addCondition" autocomplete="off">

    <div class="mb-4">
      <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('common.name') }}</label>
      <input type="text" v-model="newCondition.name" class="input" autocomplete="off" />
    </div>
    <div class="grid grid-cols-2 gap-3">
      <div class="mb-4">
        <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('common.quantity') }}</label>
        <v-select class="block w-full mr-1 required" :model-value="newCondition.quantity" :options="conditionQuantities"
          @update:modelValue="updateSelect($event, 'quantity')" />
      </div>
      <div class="mb-4">
        <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('common.operation') }}</label>
        <select v-model="newCondition.operation" class="input" autocomplete="off">
          <option v-for="operation in conditionOperations" :key="operation" :value="operation">
            {{ AdjustmentConditionOperationChoices[operation] }}
          </option>
        </select>
      </div>
    </div>
    <div class="mb-4">
      <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('common.value') }} / {{ t('pricing_block.for') }}</label>
      <!-- <v-select v-if="newCondition.quantity && newCondition.quantity?.url?.length > 0" class="block w-full mr-1 required" :model-value="selectedToken" :options="typeOptions"
        @update:modelValue="updateSelect($event, 'formula')" /> -->
      <textarea v-model="newCondition.formula" class="input" autocomplete="off"></textarea>
    </div>
    <button type="submit" class="button-primary flex gap-3 items-center">
      <icon name="fa6-solid:floppy-disk"></icon><span>{{ t('common.save') }}</span>
    </button>
  </form>

  <hr class="my-6" />

  <div class="mb-3">
    <p class="text-lg font-semibold mb-2">{{ t('pricing_block.variables_formula') }}</p>
    <ul>
      <li class="mb-2 inline-block items-center mr-2">
        <abbr :title="t('pricing_block.adj_contacts')"
          class="inline-block bg-gray-100 text-gray-800 font-mono p-1 rounded no-underline">
          %contract.contacts
        </abbr>
      </li>
      <li class="mb-2 inline-block items-center mr-2">
        <abbr :title="t('billing_block.estimated_reading')"
          class="inline-block bg-gray-100 text-gray-800 font-mono p-1 rounded no-underline">
          %reading.is_estimated
        </abbr>
      </li>
    </ul>
    <!-- <ul>
      <li class="mb-2 inline-block items-center mr-2">
        <abbr class="inline-block bg-gray-100 text-gray-800 font-mono p-1 rounded no-underline">
          %supplypoint.type
        </abbr>
      </li>
    </ul> -->
  </div>

</template>
