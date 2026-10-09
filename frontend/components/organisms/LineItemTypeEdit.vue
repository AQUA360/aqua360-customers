<script setup>
import { toRaw, ref, onMounted } from 'vue';
import { useI18n } from 'vue-i18n';

import _ from 'lodash';
import H1 from '~/components/atoms/H1.vue';
import { VariableCalculationDataTypeChoices, BillingPeriodDataTypeChoices, PriceDataTypeChoices } from '~/utils/pricing';
import AddPriceInterval from '../molecules/AddPriceInterval.vue';
import AddFixedVarPriceInterval from '../molecules/AddPriceVariable.vue';
import { is, se } from 'date-fns/locale';
import AdjustmentList from '~/components/molecules/AdjustmentList.vue';
import FormulaForm from '../molecules/FormulaForm.vue';
import { AdjustmentTypeChoices } from '~/utils/pricing';
import TranslatableNameField from '~/components/molecules/TranslatableNameField.vue';

const route = useRoute()
const props = defineProps({
  id: Number,
  isSubRegionOpen: {
    type: Boolean,
    default: false
  },
});
const emit = defineEmits(['changed']);

const { t } = useI18n();
const { $LineItemTypeApiService, $PriceIntervalApiService, $PriceVariableIntervalApiService, $TaxApiService, $BillingRangeApiService, $PriceRateApiService } = useNuxtApp();

const attemptedSave = ref(false);
const loading = ref(true);
const saving = ref(false);

const item = ref(null);
const token = ref(null);
const name = ref(null);
const translations = ref([]);
const price = ref(null);
const proportional_price = ref(null);
const operation = ref(null);
const is_prorated = ref(false);
const is_always_show = ref(true);

const is_positive = ref(true);

const br_id = ref(null);
const billing_range = ref({});
const pr_id = ref(null);
const price_rate = ref({});
const inpr = ref(null);
const inproduct = ref(false);
const adjustments = ref([]);

const formula = ref(null)

const selectedPriceVariable = ref(null)
const selectedPriceInterval = ref(null)
const selectedQuantity = ref(null)
const selectedBillingPeriod = ref(null)
const selectedTaxes = ref(null)
const selectedPriceType = ref(null)
const selectedBillingActive = ref(null)
const selectedBillingInactive = ref(null)
//Added later
/* const selectedBillingRange = ref(null) */

const variablePrices = ref([])
const priceIntervals = ref([])
const quantities = ref([])
const billingPeriods = ref([])
const taxes = ref([])
const priceTypes = ref([])


const showRegion = ref(false);
const isSubRegionOpen = ref(false);
const editingPriceInterval = ref(false);
const editingFixedVarPriceInterval = ref(false);
const showFormulaForm = ref(false);
const adjustmentChoices = ref(AdjustmentTypeChoices);

const getData = async () => {
  loading.value = true;

  if (props.id) {
    item.value = await $LineItemTypeApiService.getDetail(props.id);
    name.value = item.value.name;
    translations.value = Object.entries(item.value.name_translations || {}).map(([language, name]) => ({ language, name }));
    token.value = item.value.token;
    price.value = item.value.price;
    proportional_price.value = item.value.proportional_price;
    operation.value = item.value.operation;
    adjustments.value = item.value.adjustments;
    is_prorated.value = item.value.is_prorated;
    is_always_show.value = item.value.always_show;
    is_positive.value = item.value.is_positive;
    formula.value = item.value.formula;
    if (!selectedPriceVariable.value) {
      selectedPriceVariable.value = item.value?.price_variable ? { value: item.value?.price_variable?.id, label: item.value?.price_variable?.token } : null;
    }
    if (!selectedPriceInterval.value) {
      selectedPriceInterval.value = item.value?.price_interval ? { value: item.value?.price_interval?.id, label: item.value?.price_interval?.token } : null;
    }

    if (item.value?.quantity?.token) {
      selectedQuantity.value = { value: item.value?.quantity?.token, label: item.value?.quantity?.name };
    } else {
      selectedQuantity.value = { value: '-', label: t("common.no_quantity") };
    }
    if (item.value?.billing_period?.token) {
      selectedBillingPeriod.value = { value: item.value?.billing_period?.token, label: item.value?.billing_period?.name };
    } else {
      selectedBillingPeriod.value = { value: '-', label: t("common.punctual") };
    }
    selectedTaxes.value = { value: item.value?.tax?.token, label: item.value?.tax?.name };
    if (price.value != null) {
      selectedPriceType.value = { value: 'fixed', label: t('pricing_block.fixed') };
    } else if (proportional_price.value != null) {
      selectedPriceType.value = { value: 'prop', label: t('pricing_block.prop') };
    } else if (selectedPriceInterval.value) {
      selectedPriceType.value = { value: 'interval', label: t('common.range') };
    } else if (selectedPriceVariable.value) {
      selectedPriceType.value = { value: 'variable', label: t('pricing_block.variable_price') };
    } else if (formula.value) {
      selectedPriceType.value = { value: 'for', label: t('pricing_block.for') };
    } else {
      selectedPriceType.value = { value: '-', label: t("pricing_block.no_price_intervals") };
    }
  } else {
    item.value = {};
    selectedPriceType.value = { value: '-', label: t("pricing_block.no_price_intervals") };
    selectedQuantity.value = { value: '-', label: t("common.no_quantity") };
  }

  selectedBillingActive.value = item.value.active_choice;
  selectedBillingInactive.value = item.value.inactive_choice;

  getQuantites();
  getBillingPeriods();
  getTaxes();
  getVariablePriceIntervals();
  getPriceTypes();
  getPriceIntervals();

  loading.value = false;
}



const getQuantites = () => {
  quantities.value = []
  quantities.value = Object.keys(VariableCalculationDataTypeChoices).map(key => {
    return {
      value: key,
      label: t(VariableCalculationDataTypeChoices[key])
    }
  })
  quantities.value.unshift({ value: '-', label: t("common.no_quantity") })
}

const getBillingPeriods = () => {
  billingPeriods.value = []
  billingPeriods.value = Object.keys(BillingPeriodDataTypeChoices).map(key => {
    return {
      value: key,
      label: t(BillingPeriodDataTypeChoices[key])
    }
  })
  billingPeriods.value.unshift({ value: '-', label: t("common.punctual") })
}

const getTaxes = async () => {
  const response = await $TaxApiService.getAll();
  taxes.value = []
  response.results.forEach(tax => {
    taxes.value.push({
      value: tax.token,
      label: tax.name + " (" + tax.percent + "%)"
    })
  });
}

const getPriceTypes = () => {
  priceTypes.value = []
  priceTypes.value = Object.keys(PriceDataTypeChoices).map(key => {
    return {
      value: key,
      label: t(PriceDataTypeChoices[key])
    }
  })
  priceTypes.value.unshift({ value: '-', label: t("pricing_block.no_price_intervals") });
}

const getPriceIntervals = async () => {
  priceIntervals.value = []
  const response = await $PriceIntervalApiService.getAll();
  response.results.forEach(item => {
    priceIntervals.value.push({
      value: item.id,
      label: item.token
    })
  })

}

const getVariablePriceIntervals = async () => {
  variablePrices.value = []
  const response = await $PriceVariableIntervalApiService.getAll();
  response.results.forEach(item => {
    variablePrices.value.push({
      value: item.id,
      label: item.token
    })
  })
}

const save = async () => {
  attemptedSave.value = true;
  if (selectedBillingPeriod.value.value === '-') {
    selectedBillingPeriod.value.value = null;
  }
  if (selectedQuantity.value.value === '-') {
    selectedQuantity.value.value = null;
  }
  if (isValid()) {
    saving.value = true;

    const selectedOptions = {
      id: props?.id || null,
      name: name.value,
      name_translations: Object.fromEntries(translations.value.filter((row) => row.name).map((row) => [row.language, row.name])),
      price: selectedPriceType.value.value == 'fixed' ? price.value?.toString().replace(',', '.') : null,
      proportional_price: selectedPriceType.value.value == 'prop' ? proportional_price.value?.toString().replace(',', '.') : null,
      operation: operation?.value,
      formula: formula.value || null,
      price_interval_id: selectedPriceType.value.value == 'interval' ? selectedPriceInterval?.value?.value : null,
      quantity_token: selectedQuantity?.value?.value || null,
      billing_period_token: selectedBillingPeriod?.value.value || null,
      tax_token: selectedTaxes?.value.value || null,
      billing_range_id: parseInt(br_id?.value) || null,
      is_prorated: is_prorated.value,
      always_show: is_always_show.value,
      is_positive: is_positive.value,
      price_variable_id: selectedPriceType.value.value == 'variable' ? selectedPriceVariable?.value?.value : null,
      active_choice: selectedBillingActive.value,
      inactive_choice: selectedBillingInactive.value,
    };
    item.value = $LineItemTypeApiService.save(selectedOptions);
    if (br_id.value) {
      if (inpr.value) {
        return navigateTo({
          path: '/pricing/price-rates/',
          query: {
            action: 'showDetail',
            pr_id: pr_id.value
          }
        })
      } else if (inproduct.value) {
        return navigateTo({
          path: '/pricing/products/',
          query: {
            id: price_rate?.value.product?.id
          }
        })
      } else {
        return navigateTo({
          path: '/pricing/billing-ranges/',
          query: {
            action: 'showDetail',
            br_id: br_id.value
          }
        })
      }
    }
    else {
      return navigateTo('/pricing/line-item-types/')
    }
  }
  else {
    saving.value = false;
  }
}


const isValid = () => {
  if (name.value == '' || name.value == null) return false;
  if (!selectedTaxes?.value?.value) return false;
  if (!selectedPriceType?.value.value) return false;
  if ((price?.value?.toString() == '' || price.value == null) && selectedPriceType?.value.value == 'fixed') return false;
  if ((proportional_price?.value?.toString() || proportional_price.value == null) == '' && selectedPriceType?.value.value == 'prop') return false;
  if (!selectedPriceInterval?.value?.value && (selectedPriceType?.value?.value == 'interval')) return false;
  if (!selectedPriceVariable?.value?.value && (selectedPriceType?.value?.value == 'variable')) return false;
  /* if (!selectedQuantity?.value?.value && !(selectedPriceType?.value?.value == 'fixed' || selectedPriceType?.value?.value == 'for')) return false; */
  return true;
}

const updateSelect = (event, entity) => {
  switch (entity) {
    case 'fixed_price_interval':
      selectedPriceVariable.value = event;

      break;
    case 'price_interval':
      selectedPriceInterval.value = event;

      break;
    case 'quantity':
      selectedQuantity.value = event;
      break;
    case 'taxes':
      selectedTaxes.value = event;
      break;
    case 'billingPeriod':
      selectedBillingPeriod.value = event;
      break;
    case 'pricetype':
      selectedPriceType.value = event;
      price.value = null;
      proportional_price.value = null;
      selectedPriceVariable.value = null;
      selectedPriceInterval.value = null;
      formula.value = null;
      break;
  }
}

const createInterval = async () => {
  selectedPriceInterval.value = null
  openRegion('priceInterval')
}
const createFixedVarInterval = async () => {
  selectedPriceVariable.value = null
  openRegion('fixedVarPriceInterval')
}

const editInterval = async () => {
  openRegion('priceInterval')
}
const editFixeVarInterval = async () => {
  openRegion('fixedVarPriceInterval')
}

const newPriceInterval = (pr) => {
  selectedPriceInterval.value = {
    value: pr.id,
    label: pr.token
  }
  //getData()
  closeAllRegions();
}
const newFixeVarInterval = (pr) => {
  selectedPriceVariable.value = {
    value: pr.id,
    label: pr.token
  }
  //getData()
  closeAllRegions();
}

const openFormulaForm = () => {

  toggleFormulaForm();
};

const editFormula = (result) => {
  formula.value = result
  toggleFormulaForm();
};

const deleteItem = async () => {
  if (confirm(t('confirmation_text_block.confirm_delete'))) {
    saving.value = true;
    await $LineItemTypeApiService.doDelete(item.value.id);
    return navigateTo({
      path: '/pricing/price-rates/',
      query: {
        action: 'showDetail',
        pr_id: pr_id.value,
      }
    })
  }
}

const toggleFormulaForm = () => {
  showFormulaForm.value = !showFormulaForm.value;
  showRegion.value = !showRegion.value;
};

const toggleRegion = (force) => {
  showRegion.value = force !== undefined ? force : !showRegion.value;
  showFormulaForm.value = false;
  if (showRegion.value == false) {
    isSubRegionOpen.value = false;
  }
  closeAllRegions();
  //getData();
}

const openRegion = (region) => {
  closeAllRegions();
  if (region == 'priceInterval') {
    editingPriceInterval.value = true;
  } else if (region == 'fixedVarPriceInterval') {
    editingFixedVarPriceInterval.value = true;
  }
  showRegion.value = true;
};


const closeAllRegions = () => {
  editingPriceInterval.value = false;
  editingFixedVarPriceInterval.value = false;

  showRegion.value = false;
};

const getPriceRate = async () => {
  if (pr_id.value) {
    const response = await $PriceRateApiService.getDetail(pr_id.value);
    price_rate.value = response;
  }
}

const getBillingRange = () => {
  if (br_id.value) {
    $BillingRangeApiService.getDetail(br_id.value).then((response) => {
      billing_range.value = response;
    });
  }
}

const showAdjustmentDetail = function (component, id) {
}


const editAdjustment = async (id, new_tab) => {
  if (!props.id) {
    alert($t("warning_block.warning_save_adj_no_price_rate"));
    return false;
  }

  if (new_tab) {
    const url = new URL('/pricing/adjustments/add', window.location.origin);
    url.searchParams.set('adjustment_id', id);
    url.searchParams.set('line_item_type_id', props.id);
    url.searchParams.set('interval_id', selectedPriceInterval?.value?.value || null);
    url.searchParams.set('variable_id', selectedPriceVariable?.value?.value || null);
    url.searchParams.set('price_rate_id', price_rate.value.id);
    window.open(url.toString(), '_blank');
  } else {
    return navigateTo({
      path: '/pricing/adjustments/add',
      query: {
        adjustment_id: id,
        line_item_type_id: props.id,
        interval_id: selectedPriceInterval?.value?.value || null,
        variable_id: selectedPriceVariable?.value?.value || null,
        price_rate_id: price_rate.value.id,
      }
    })
  }
}

const createAdjustment = async () => {
  if (!props.id) {
    alert($t("warning_block.warning_save_adj_no_price_rate"));
    return false;
  }

  /* let newUrl = new URL('/pricing/adjustments/add', window.location.origin);
  newUrl.searchParams.set('line_item_type_id', props.id);
  newUrl.searchParams.set('interval_id', selectedPriceInterval?.value?.value || null);
  newUrl.searchParams.set('price_rate_id', price_rate.value.id);
  window.open(newUrl.toString(), '_blank'); */

  return navigateTo({
    path: '/pricing/adjustments/add',
    query: {
      line_item_type_id: props.id,
      interval_id: selectedPriceInterval?.value?.value || null,
      variable_id: selectedPriceVariable?.value?.value || null,
      price_rate_id: price_rate.value.id
    }
  })
}


onMounted(() => {
  pr_id.value = route.query.pr_id;
  getPriceRate();

  br_id.value = route.query.br_id;
  getBillingRange();

  if (route.query.inpr) {
    inpr.value = route.query.inpr;
  }

  inproduct.value = route.query.inprod ? route.query.inprod : false;

  getData()
});

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
      <div class="border border-gray-300 rounded p-4 bg-sky-50 mb-3">
        <div class="grid grid-cols-2 gap-3" style="grid-template-columns: 30% 70%;">
  
          <div>
            <AtomsFieldDetail v-if="price_rate" :label="$t('product') + ':'" :value="price_rate.product?.name" />
            <AtomsFieldDetail v-if="price_rate" :label="$t('price_rate') + ':'" :value="price_rate.token" />
            <AtomsFieldDetail :label="$t('ident') + ':'" :value="token" />
      
          </div>
          <div>
            <AtomsFieldDetail v-if="billing_range" :label="$t('common.range') + ':'" :value="null" class="col-span-2">
              <span>{{ billing_range?.name }}</span><br />
              <span>{{ billing_range.publication?.name }}</span><br />
              <span>{{ formatDate(billing_range.start) }}</span> <span v-if="billing_range.end"> - {{ formatDate(billing_range.end) }}</span>
            </AtomsFieldDetail>
          </div>
        </div>
      </div>
      <div class="border border-gray-300 rounded p-4 bg-white mb-4">
        <div class="row grid grid-cols-2 gap-3">
          <div class="mb-4">
            <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('common.name') }}</label>
            <input type="text" v-model="name" class="input"
              :class="{ 'invalid': attemptedSave && name == '' || attemptedSave && name == null }" />
          </div>

          <TranslatableNameField v-model="translations" class="col-span-2" />

          <div class="mb-4">
            <div class="flex items-center mt-8">
              <input v-model="is_positive" type="checkbox" :checked="is_positive" class="checkbox" />
              <label for="is_positive" class="ml-2">{{ t('pricing_block.is_positive') }}</label>
            </div>
          </div>


          <!-- <div v-if="token" class="mb-4">
            <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('common.identificator') }}</label>
            <input type="text" v-model="token" class="input" :disabled="true" />
          </div> -->
        </div>

        <div class="row grid grid-cols-2 gap-3">
          <div class="mb-4">
            <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('common.price') }}</label>
            <v-select class="block w-full mr-1 required" :model-value="selectedPriceType" :options="priceTypes"
              :class="{ 'invalid': attemptedSave && (selectedPriceType?.value?.value == '-') }"
              @update:modelValue="updateSelect($event, 'pricetype')" />
          </div>

          <div v-if="selectedPriceType?.value == 'fixed'" class="mb-4">
            <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('pricing_block.fixed_price') }}</label>
            <input type="float" v-model="price" class="input" />
          </div>

          <div v-else-if="selectedPriceType?.value == 'prop'" class="mb-4">
            <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('pricing_block.proportional_price')
              }}</label>
            <input type="float" v-model="proportional_price" class="input" />
          </div>

          <div v-else-if="selectedPriceType?.value == 'interval'" class="mb-4">
            <div class="field">
              <div class="flex">
                <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('pricing_block.price_interval')
                  }}</label>
              </div>
            </div>
            <div class="flex">
              <v-select class="block w-full mr-1 required" :disable="priceIntervals"
                :model-value="selectedPriceInterval" @update:modelValue="updateSelect($event, 'price_interval')"
                :options="priceIntervals" />
              <button
                class="w-9 h-9 border-gray-300 mr-1 border rounded text-slate-600 enabled:hover:bg-slate-200 disabled:bg-slate-200 disabled:text-slate-400 transition-all duration-200"
                @click="editInterval" :disabled="selectedPriceInterval == null">
                <Icon class="text-md" name="fa6-solid:pencil" />
              </button>
              <button
                class="w-9 h-9 border-gray-300 border rounded enabled:hover:bg-slate-200 transition-all duration-200"
                @click="createInterval">
                <Icon name="fa6-solid:plus" class="text-md text-slate-600" />
              </button>
            </div>
          </div>

          <div v-else-if="selectedPriceType?.value == 'variable'" class="mb-4">
            <div class="field">
              <div class="flex">
                <label class="block text-sm font-medium text-slate-500 mb-2">{{
                  t('pricing_block.fixed_var_price_interval')
                  }}</label>
              </div>
            </div>
            <div class="flex">
              <v-select class="block w-full mr-1 required" :model-value="selectedPriceVariable"
                @update:modelValue="updateSelect($event, 'fixed_price_interval')" :options="variablePrices" />
              <button
                class="w-9 h-9 border-gray-300 mr-1 border rounded text-slate-600 enabled:hover:bg-slate-200 disabled:bg-slate-200 disabled:text-slate-400 transition-all duration-200"
                @click="editFixeVarInterval" :disabled="selectedPriceVariable == null">
                <Icon class="text-md" name="fa6-solid:pencil" />
              </button>
              <button
                class="w-9 h-9 border-gray-300 border rounded enabled:hover:bg-slate-200 transition-all duration-200"
                @click="createFixedVarInterval">
                <Icon name="fa6-solid:plus" class="text-md text-slate-600" />
              </button>
            </div>
          </div>


          <div v-else-if="selectedPriceType?.value == 'for'" class="mb-4">
            <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('pricing_block.for') }}</label>
            <div class="flex">
              <button
                class="w-9 h-9 border-gray-300 mr-1 border rounded text-slate-600 enabled:hover:bg-slate-200 disabled:bg-slate-200 disabled:text-slate-400 transition-all duration-200"
                @click="openFormulaForm">
                <Icon class="text-md" name="fa6-solid:pencil" />
              </button>
              <span
                class="block w-full py-2 px-3 border border-gray-300 bg-slate-100 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm">
                {{ formula ? formula : t("pricing_block.no_formula") }}</span>
            </div>
          </div>
        </div>


        <div class="row grid grid-cols-2 gap-3 ">

          <div class="mb-4">
            <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('pricing_block.quantity_obtaining')
              }}</label>
            <v-select class="block w-full mr-1 required" :model-value="selectedQuantity" :options="quantities"
              :class="{ 'invalid': attemptedSave && (!selectedQuantity && (selectedPriceType.value !== 'fixed')) }"
              @update:modelValue="updateSelect($event, 'quantity')" />
          </div>

          <div class="mb-4">
            <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('common.tax') }}</label>
            <v-select class="block w-full mr-1 required" :model-value="selectedTaxes" :options="taxes"
              :class="{ 'invalid': attemptedSave && !selectedTaxes }"
              @update:modelValue="updateSelect($event, 'taxes')" />
          </div>
        </div>

        <div class="row grid grid-cols-2 gap-3">
          <div class="mb-4">
            <div class="flex items-center mb-4">
              <!-- :disabled="selectedQuantity?.value !== 'dies_consum'" -->
              <input v-model="is_prorated" type="checkbox" 
                :checked="is_prorated && (selectedQuantity?.value === 'dies_consum')"
                id="is_prorated" name="is_prorated"
                class="checkbox" />
              <label for="is_prorated" class="ml-2">{{ t('pricing_block.prorated') }}</label>
            </div>
            <div class="flex items-center mb-4">
              <input v-model="is_always_show" type="checkbox" :checked="is_always_show" id="is_always_show "
                name="is_always_show " class="checkbox" />
              <label for="is_always_show " class="ml-2">{{ t('pricing_block.always_show_line_item') }}</label>
            </div>
          </div>


          <div class="mb-4">
            <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('billing_block.billing_period') }}</label>
            <v-select class="block w-full mr-1 required" :model-value="selectedBillingPeriod" :options="billingPeriods"
              :class="{ 'invalid': attemptedSave && !selectedBillingPeriod }"
              @update:modelValue="updateSelect($event, 'billingPeriod')" />
          </div>

          <div class="mb-4" :class="{ 'opacity-50': !price_rate.product?.billing_active }">
            <div class="text-sm font-medium text-slate-500 mb-2">{{ t('pricing_block.billing_registration') }}</div>
            <div class="flex gap-3">
              <div v-for="(choice, key) in adjustmentChoices" :key="key"
                @click="price_rate.product?.billing_active ? selectedBillingActive = key : null"
                class="flex items-center gap-2 px-3 py-1.5 rounded-md transition-all duration-200" :class="[
                  selectedBillingActive === key
                    ? 'bg-sky-50 ring-1 ring-sky-600'
                    : 'hover:bg-gray-50',
                  price_rate.product?.billing_active ? 'cursor-pointer' : 'cursor-not-allowed'
                ]">
                <div class="w-3.5 h-3.5 rounded-sm border-2 flex items-center justify-center shrink-0" :class="[
                  selectedBillingActive === key
                    ? 'border-sky-600 bg-sky-600'
                    : 'border-gray-300'
                ]">
                  <Icon v-if="selectedBillingActive === key" name="fa6-solid:check" class="text-white" />
                </div>
                <span class="text-xs font-medium" :class="[
                  selectedBillingActive === key
                    ? 'text-sky-700'
                    : 'text-gray-600'
                ]">
                  {{ t(choice) }}
                </span>
              </div>
            </div>
          </div>
          <div class="mb-4" :class="{ 'opacity-50': !price_rate.product?.billing_inactive }">
            <div class="text-sm font-medium text-slate-500 mb-2">{{ t('pricing_block.billing_termination') }}</div>
            <div class="flex gap-3">
              <div v-for="(choice, key) in adjustmentChoices" :key="key"
                @click="price_rate.product?.billing_inactive ? selectedBillingInactive = key : null"
                class="flex items-center gap-2 px-3 py-1.5 rounded-md transition-all duration-200" :class="[
                  selectedBillingInactive === key
                    ? 'bg-sky-50 ring-1 ring-sky-600'
                    : 'hover:bg-gray-50',
                  price_rate.product?.billing_inactive ? 'cursor-pointer' : 'cursor-not-allowed'
                ]">
                <div class="w-3.5 h-3.5 rounded-sm border-2 flex items-center justify-center shrink-0" :class="[
                  selectedBillingInactive === key
                    ? 'border-sky-600 bg-sky-600'
                    : 'border-gray-300'
                ]">
                  <Icon v-if="selectedBillingInactive === key" name="fa6-solid:check" class="text-white" />
                </div>
                <span class="text-xs font-medium" :class="[
                  selectedBillingInactive === key
                    ? 'text-sky-700'
                    : 'text-gray-600'
                ]">
                  {{ t(choice) }}
                </span>
              </div>
            </div>
          </div>
        </div>

        <hr class="mb-2 col-span-2" />
        <div class="col-span-2 flex flex-row-reverse mt-4">
          <button @click="save" :disabled="saving" class="button-primary">
            <Icon name="fa6-solid:floppy-disk" />&nbsp; {{
              $t('common.save') }}
          </button>
          <button v-if="id != null" @click="deleteItem" :disabled="saving" class="button-delete mr-5">
            <Icon name="fa6-solid:trash" />&nbsp; {{ $t('common.delete') }}
          </button>
        </div><!-- end contingut botons -->
      </div>

      <div class="border border-gray-300 rounded p-3 bg-sky-50 mb-3 bg-sky-50">
        <AdjustmentList v-if="adjustments.length > 0" :isContractSubregion="props.isContractSubregion"
          :adjustments="adjustments" :price_rate_id="price_rate?.id" :isSubRegion="true" :in_detail="true"
          :hideActions="false" @show-detail="showAdjustmentDetail" @edit-adjustment="editAdjustment"
          @create-adjustment="createAdjustment" />
        <div v-else>
          <p>
            {{ $t('common.no_records') }}
          </p>
          <button v-if="props.id"
            class="px-3 rounded border border-slate-400 py-1 mt-3 hover:bg-slate-200 items-center flex gap-1"
            @click="createAdjustment">
            <Icon name="fa6-solid:plus" />&nbsp;
            <span>
              {{ $t('common.add') }} {{ $t('pricing_block.adjustment_detail') }}
            </span>
          </button>
        </div>
      </div>

    </div><!-- end else -->

    <div role="region" id="right_page"
      class="fixed h-full border-l border-gray-100 top-0 right-0 transition-all duration-500 ease py-2 text-base bg-white z-10"
      :class="{ 'translate-x-0': showRegion, 'translate-x-[2000px]': !showRegion, 'w-[95%]': isSubRegionOpen, 'w-1/2': !isSubRegionOpen }">
      <div id="region_nav" class="mb-3 px-3">
        <button @click="toggleRegion(false)" class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300">
          <Icon name="fa6-solid:angles-right" class="text-slate-500" />
        </button>
      </div>
      <div class="px-10">
        <!-- subregions -->
        <AddPriceInterval v-if="editingPriceInterval" :id="selectedPriceInterval?.value || null"
          :isSubRegionOpen="isSubRegionOpen" @new-pr="newPriceInterval" />
        <AddFixedVarPriceInterval v-if="editingFixedVarPriceInterval" :id="selectedPriceVariable?.value || null"
          :isSubRegionOpen="isSubRegionOpen" @new-pr="newFixeVarInterval" />
        <FormulaForm v-if="showFormulaForm" :formula="formula" @save="editFormula" />
      </div>
    </div>


  </div>
</template>
