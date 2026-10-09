<script setup>
import { toRaw, ref, onMounted } from 'vue';
import { useI18n } from 'vue-i18n';
import { nextTick } from 'vue';
import _ from 'lodash';
import { VariableCalculationConditionsDataTypeChoices, AdjustmentOperationDataTypeChoices } from '~/utils/pricing';
import PriceAdjustmentInterval from '../molecules/PriceAdjustmentInterval.vue';
import LineItemTypeDetail from '~/components/molecules/LineItemTypeDetail.vue';
import ConditionForm from '~/components/molecules/ConditionForm.vue';
import AdjustmentPreferenceChange from '../molecules/AdjustmentPreferenceChange.vue';
import FormulaForm from '../molecules/FormulaForm.vue';

const route = useRoute()
const props = defineProps({
  id: Number,
});

const { t } = useI18n();
const { $AdjustmentApiService, $PriceIntervalApiService, $PriceVariableIntervalApiService, $VariableTypeApiService, $LineItemTypeApiService, $PriceRateApiService, $AdjustmentIntervalStretchApiService, $AdjustmentConditionApiService } = useNuxtApp();

const attemptedSave = ref(false);
const loading = ref(true);
const saving = ref(false);

const line_item_type_id = ref(null);
const price_rate_id = ref(null);
const price_interval_id = ref(null);
const price_variable_id = ref(null);
const adjustment_id = ref(null);

const line_item_type = ref(null);
const price_rate = ref(null);

const item = ref({});
const conditions = ref([]);

const token = ref(null);
const name = ref(null);
const selectedOperation = ref(null);
const selectedVariableCalculation = ref(null);
const quantity = ref(null);
const formula = ref(null);
const selectedAdjustmentInterval = ref(null)
const selectedVariableContract = ref(null)

const operations = ref([])
const variableCalculations = ref([])
const adjustmentInterval = ref(null)
const variableContracts = ref([])

const editingPriceAdjustmentInterval = ref(false);

const showRegion = ref(false);
const isSubRegionOpen = ref(false);

const newIntervalStretchs = ref([]); // aquí guardem els intervals de stretchs que es creen, per posar el adjustment_id

const conditionToEdit = ref(null);

const tempIdCounter = ref(0); // Add this line to create a counter for temporary IDs

const isModifyingPreferences = ref(false)
const showFormulaForm = ref(false);
const preferenceComponent = ref(null);

const getData = async () => {
  loading.value = true;

  if (adjustment_id.value) {
    item.value = await $AdjustmentApiService.getDetail(adjustment_id.value);
    token.value = item.value.token;
    name.value = item.value.name;
    selectedOperation.value = { value: item.value.operation.token, label: item.value.operation.name };
    quantity.value = item.value.quantity;
    formula.value = item.value.formula;
    conditions.value = item.value.conditions;
    if (item.value.variable_calculation && item.value.variable_calculation.token) {
      selectedVariableCalculation.value = { value: item.value.variable_calculation.token, label: item.value.variable_calculation.name };
    } else {
      selectedVariableCalculation.value = { value: '-', label: t("pricing_block.no_variable_calc") };
    }
    if (item.value.adjustment_interval) {
      selectedAdjustmentInterval.value = { value: item.value.adjustment_interval.id, label: item.value.adjustment_interval.token };
    }
    if (item.value.variable_type) {
      selectedVariableContract.value = { value: item.value.variable_type.id, label: item.value.variable_type.name };
    } else {
      selectedVariableContract.value = { value: '-', label: t("pricing_block.no_variable_contract") };
    }
  } else {
    item.value = {};
  }

  getVariableCalculations();
  getAdjustmentOperations();
  getIntervals();
  getVariableContracts();
  getLineItemType();
  getPriceRate();

  loading.value = false;
}

const getIntervals = async () => {
  if (price_interval_id.value != "null" && price_interval_id.value != null) {
    const response = await $PriceIntervalApiService.getDetail(price_interval_id.value);
    adjustmentInterval.value = response;
  }
  if (price_variable_id.value != "null" && price_variable_id.value != null) {
    const response = await $PriceVariableIntervalApiService.getDetail(price_variable_id.value);
    adjustmentInterval.value = response;
  }
}

const getPriceRate = async () => {
  const response = await $PriceRateApiService.getDetail(parseInt(price_rate_id.value));
  price_rate.value = response;
}

const getVariableContracts = async () => {
  const response = await $VariableTypeApiService.getAllUnpaginated();
  variableContracts.value = []
  response.forEach(item => {
    variableContracts.value.push({
      value: item.id,
      label: item.name
    })
  })
  variableContracts.value.unshift({ value: '-', label: t("pricing_block.no_variable_contract") });
}


const getAdjustmentOperations = () => {
  operations.value = []
  operations.value = Object.keys(AdjustmentOperationDataTypeChoices).map(key => {
    return {
      value: key,
      label: t(AdjustmentOperationDataTypeChoices[key])
    }
  })
}

const getLineItemType = async () => {
  const response = await $LineItemTypeApiService.getDetail(line_item_type_id.value);
  line_item_type.value = response;
}

const getVariableCalculations = () => {
  variableCalculations.value = []
  variableCalculations.value = Object.keys(VariableCalculationConditionsDataTypeChoices).map(key => {
    return {
      value: key,
      label: t(VariableCalculationConditionsDataTypeChoices[key])
    }
  })
  variableCalculations.value.unshift({ value: '-', label: t("pricing_block.no_variable_calc") });
}

const editAdjustmentInterval = async () => {
  openRegion('priceAdjustmentInterval')
}

const save = async () => {
  attemptedSave.value = true;
  saving.value = true;

  if (quantity.value == null || quantity.value == '') {
    quantity.value = null;
  }
  if (selectedVariableContract?.value?.value == '-' || selectedVariableContract.value?.value == null) {
    selectedVariableContract.value = null;
  }
  try {
    if (isValid()) {
      const selectedOptions = {
        id: adjustment_id?.value || null,
        name: name.value,
        adjustment_interval:selectedAdjustmentInterval?.value?.value || null,
        variable_type: selectedVariableContract?.value?.value || null,
        quantity: quantity.value,
        formula: formula.value,
        operation_token: selectedOperation.value?.value,
        variable_calculation_token: selectedVariableCalculation.value ? selectedVariableCalculation?.value?.value : null,
        line_item_type_id: line_item_type_id?.value || null,
      };

      item.value = await $AdjustmentApiService.save(selectedOptions);

      // si hi ha intervals per posar la id, li possem el adjustment_id
      for (var i in newIntervalStretchs.value) {
        const interval_stretch_id = newIntervalStretchs.value[i];
        await $AdjustmentIntervalStretchApiService.save({
          id: interval_stretch_id,
          adjustment: item.value.id
        })
      }

      // si hi ha condition's per guardar, li possem l'adjustment_id

      for (var i in conditions.value) {
        const condition = conditions.value[i];
        condition.adjustment = item.value.id;
        if (typeof condition.id === 'string' && condition.id.startsWith('temp-')) {
          delete condition.id; // Remove temporary ID before saving
        }
        await $AdjustmentConditionApiService.save(condition);
      }

      //return navigateTo('/pricing/products/')
      return navigateTo({
        path: '/pricing/products/',
        query: {
          action: 'showDetail',
          id: price_rate.value.product.id,
          price_rate_id: price_rate.value.id
        }
      })
    } else {
      console.error('Formulari no vàlid');
    }
  } catch (error) {
    console.error('Error en el formulari:', error);
  } finally {
    attemptedSave.value = false;
    saving.value = false;
  }

}

const isValid = () => {
  if (selectedOperation.value == '' || selectedOperation.value == null) return false;
  return true;
}

const updateSelect = (event, entity) => {
  switch (entity) {
    case 'operation':
      selectedOperation.value = event;
      selectedVariableContract.value = null;
      quantity.value = null;
      formula.value = null;
      break;
    case 'varcalc':
      selectedVariableCalculation.value = event;
      break;
    case 'interval':
      selectedAdjustmentInterval.value = event;
      break;
    case 'varcont':
      selectedVariableContract.value = event;
      quantity.value = null;
      break;
  }
}

const deleteItem = async () => {
  if (confirm(t('confirmation_text_block.confirm_delete'))) {
    saving.value = true;
    await $AdjustmentApiService.doDelete(adjustment_id.value);
    return navigateTo({
      path: '/pricing/products/',
      query: {
        action: 'showDetail',
        id: price_rate.value.product.id,
        price_rate_id: price_rate.value.id
      }
    })
  }
}

const openRegion = (region) => {
  closeAllRegions();
  if (region == 'priceAdjustmentInterval') {
    editingPriceAdjustmentInterval.value = true;
  } else if (region == 'conditionForm') {
    showConditionForm.value = true;
  } else if (region == 'AdjustmentPreferences'){
    isModifyingPreferences.value = true
  } else if (region == 'formulaForm') {
    showFormulaForm.value = true;
  }
  showRegion.value = true;
};

const toggleRegion = (force) => {
  showRegion.value = force !== undefined ? force : !showRegion.value;
  if (showRegion.value == false) {
    isSubRegionOpen.value = false;
    showFormulaForm.value = false;
    showConditionForm.value = false;
    isModifyingPreferences.value = false;
    editingPriceAdjustmentInterval.value = false;
  }
}

const closeAllRegions = () => {
  editingPriceAdjustmentInterval.value = false;
  showConditionForm.value = false;
  showFormulaForm.value = false;
  isModifyingPreferences.value = false;
  editingPriceAdjustmentInterval.value = false;
  showRegion.value = false;
};

const updatePage = () => {
  getData()
  closeAllRegions();

  const originalAdjustmentId = adjustment_id.value; // Store the original value
  adjustment_id.value = null;
  nextTick(() => {
    adjustment_id.value = originalAdjustmentId
  })
}

const editFormula = (form) => {
  formula.value = form;
  toggleRegion(false);
};

onMounted(() => {
  line_item_type_id.value = route.query.line_item_type_id;
  price_interval_id.value = route.query.interval_id;
  price_variable_id.value = route.query.variable_id;
  price_rate_id.value = route.query.price_rate_id;
  if (route.query.adjustment_id) {
    adjustment_id.value = route.query.adjustment_id ? parseInt(route.query.adjustment_id) : null;
  }
  getData()
});


const onNewIntervalStretch = (id) => {
  newIntervalStretchs.value.push(id);
}

const showConditionForm = ref(false);

const toggleConditionForm = () => {
  showConditionForm.value = !showConditionForm.value;
  openRegion('conditionForm');
};

const newCondition = () => {
  conditionToEdit.value = { id: `temp-${tempIdCounter.value++}` }; // Assign a temporary ID
  toggleConditionForm();
};

const editCondition = (condition) => {
  conditionToEdit.value = condition;
  toggleConditionForm();
};

const saveCondition = (condition) => {
  const index = conditions.value.findIndex(c => c.id === condition.id);
  if (index !== -1) {
    conditions.value[index] = condition;
  } else {
    conditions.value.push(condition);
  }
  closeAllRegions();
};

const deleteCondition = async (condition) => {
  const index = conditions.value.findIndex(c => c.id === condition.id);
  if (index !== -1) {
    const c = conditions.value[index];
    if (!isNaN(c.id)) {
      try {
        await $AdjustmentConditionApiService.doDelete(c);
      } catch (error) {
        console.error('Error deleting condition:', error);
        return;
      }
    }
    conditions.value.splice(index, 1);
  }
}

const changePreferencePosition = () => {
      isModifyingPreferences.value = !isModifyingPreferences.value;

      /* if (isModifyingPreferences.value) {
        setTimeout(() => {
          window.scrollTo({ top: document.body.scrollHeight, behavior: 'smooth' });
        }, 100);
      } */
    };

watch( quantity, (newVal) => {
  if (newVal){
    selectedVariableContract.value = null;
  }
})

</script>

<template>
  <div class="wrapper text-base max-w-full">
    <div v-if="loading">
      <div class="border border-gray-300 rounded p-4 bg-white">
        <div class="flex justify-center items-center">
          <Icon name="fa6-solid:spinner" class="animate-spin text-2xl text-slate-500" />
          <span class="ml-2">{{ $t('common.loading') }}...</span>
        </div>
      </div>
    </div>
    <div v-else>
      <fieldset class="border border-gray-300 rounded p-4 bg-gray-50 mb-3">
        <legend class="px-2 font-medium text-slate-800">{{ $t('common.conditionals') }}:</legend>

        <AtomsAdjustmentConditionDetail v-for="condition in conditions" :key="condition.id" :item="condition"
          @edit="editCondition" @delete="deleteCondition" />

        <div v-if="conditions && conditions.length == 0"><em>{{ $t('common.no_conditions') }}</em></div>
        <button class="py-1 px-2 mt-3 hover:bg-white" @click="newCondition">
          <icon name="fa6-solid:plus"></icon> <span>{{ $t('common.add') }} {{ $t('pricing_block.condition') }}</span>
        </button>
      </fieldset>

      <div class="border border-gray-300 rounded p-4 bg-white">
        <div class="row grid grid-cols-2 gap-3">
          <!-- <div class="mb-4">
            <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('common.identificator') }}</label>
            <input type="text" v-model="token" class="input"
              :class="{ 'invalid': attemptedSave && (token == '' || attemptedSave && token == null) }" />
          </div> -->

          <div class="mb-4">
            <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('common.name') }}</label>
            <input type="text" v-model="name" class="input"
              :class="{ 'invalid': attemptedSave && name == '' || attemptedSave && name == null }" />
          </div>

        </div>

        <div class="row grid grid-cols-2 gap-3 ">
          <div class="mb-4">
            <div class="flex items-center gap-x-2">
              <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('common.operation') }}:</label>
              <abbr v-if="selectedOperation?.value == 'var'" :title="t('informative_block.info_operation_var')">
                <Icon name="fa6-solid:circle-info" class="text-slate-500" />
              </abbr>
            </div>
            <v-select class="block w-full mr-1 required" :model-value="selectedOperation" :options="operations"
              @update:modelValue="updateSelect($event, 'operation')" />
          </div>
          <div class="mb-4" :class="{
            'grid grid-cols-2 gap-3 items-center': selectedOperation?.value == 'set',
          }">
            <div v-if="selectedOperation?.value != 'var' && selectedOperation?.value != 'ext' && selectedOperation?.value != 'min' && selectedOperation?.value != 'max' && selectedOperation?.value != 'ptg'">
              <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('common.quantity') }} / {{ t('common.price') }}</label>
              <input type="text" v-model="quantity" class="input" />
            </div>
            <div v-if="selectedOperation?.value == 'var' || selectedOperation?.value == 'set'">
              <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('pricing_block.variable_contract') }}</label>
              <v-select class="block w-full mr-1 required" :model-value="selectedVariableContract"
                :options="variableContracts" @update:modelValue="updateSelect($event, 'varcont')" />
            </div>
            <div v-if="selectedOperation?.value == 'min' || selectedOperation?.value == 'max' || selectedOperation?.value == 'ptg'">
              <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('pricing_block.for') }}</label>
              <div class="flex items-center gap-x-2">
                <button
                  class="w-9 h-9 border-gray-300 mr-1 border rounded text-slate-600 enabled:hover:bg-slate-200 disabled:bg-slate-200 disabled:text-slate-400 transition-all duration-200"
                  @click="openRegion('formulaForm')">
                  <Icon class="text-md" name="fa6-solid:pencil" />
                </button>
                <span
                  class="block w-full py-2 px-3 border border-gray-300 bg-slate-100 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm">
                  {{ formula ? formula : t("pricing_block.no_formula") }}</span>
              </div>
            </div>
          </div>
        </div>

        <div class="row grid grid-cols-2 gap-3 ">
          <div class="mb-4">
            <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('pricing_block.variable_calc') }}</label>
            <v-select class="block w-full mr-1 required" :model-value="selectedVariableCalculation"
              :options="variableCalculations" @update:modelValue="updateSelect($event, 'varcalc')" />
          </div>

          <div v-if="adjustmentInterval" class="mb-4">
            <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('pricing_block.range_adjustment') }}</label>
            <div class="flex">
              <button
                class="w-9 h-9 border-gray-300 mr-1 border rounded text-slate-600 enabled:hover:bg-slate-200 disabled:bg-slate-200 disabled:text-slate-400 transition-all duration-200"
                @click="editAdjustmentInterval" :disabled="adjustmentInterval == null">
                <Icon class="text-md" name="fa6-solid:pencil" />
              </button>
              <span
                class="block w-full py-2 px-3 border border-gray-300 bg-slate-100 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm">
                {{ adjustmentInterval?.token }}</span>
            </div>
          </div>


        </div>

        <hr class="mb-2 col-span-2" />
        <div class="flex justify-between items-center mb-2">
          <button v-if="item && item.line_item_type" class="button-default mx-2 mt-4" @click="openRegion('AdjustmentPreferences')">
            {{ t("common.modify") }} {{ t("common.preferences") }}
          </button>

          <div class="col-span-2 flex flex-row-reverse mt-4">
            <button v-if="adjustment_id != null" @click="deleteItem" :disabled="saving" class="button-default mx-5">
              &nbsp; {{ $t('common.delete') }}
            </button>
            <button @click="save" :disabled="saving" class="button-primary">
              <Icon name="fa6-solid:floppy-disk" />&nbsp; {{
                $t('common.save') }}
            </button>
          </div><!-- end contingut botons -->

        </div>
      </div>
    </div>


    <div v-if="adjustment_id !== null" class="border border-gray-300 py-2 rounded mt-4 bg-sky-50">
      <LineItemTypeDetail v-if="item && item.line_item_type" :id="item.line_item_type" 
      :in_detail="true" :price_rate_id="parseInt(price_rate_id)" :in_adjustment="true" />
    </div>

    <!-- <div v-if="isModifyingPreferences" class="flex justify-center mt-3">
      <div class="border round w-[80%]">
        <AdjustmentPreferenceChange v-if="item && item.line_item_type" :id="item.line_item_type" :in_detail="true"
          @change="getData" />
      </div>
    </div> -->



    <div role="region" id="right_page"
      class="fixed h-full border-l border-gray-100 top-0 right-0 transition-all duration-500 ease py-2 text-base bg-white z-10"
      :class="{ 'translate-x-0': showRegion, 'translate-x-[2000px]': !showRegion, 'w-[95%]': isSubRegionOpen, 'w-1/2': !isSubRegionOpen }">
      <div id="region_nav" class="mb-3 px-3">
        <button @click="toggleRegion(false)" class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300">
          <Icon name="fa6-solid:angles-right" class="text-slate-500" />
        </button>
      </div>
      <div class="px-10">
        <PriceAdjustmentInterval v-if="editingPriceAdjustmentInterval" :adjustment_id="adjustment_id"
          :adjustment_interval_id="adjustmentInterval?.id" :isSubRegionOpen="isSubRegionOpen" :is_variable="price_variable_id != null && price_variable_id != 'null'"
          :operation="selectedOperation" @new-interval-stretch="onNewIntervalStretch" @saved="closeAllRegions" />
        <ConditionForm v-if="showConditionForm" :condition="conditionToEdit" @save="saveCondition" />
        <AdjustmentPreferenceChange v-if="isModifyingPreferences" :id="item.line_item_type" :in_detail="true"
          @change="updatePage()" />
        <FormulaForm v-if="showFormulaForm" :formula="formula" @save="editFormula" />
      </div>
    </div>
  </div>
</template>