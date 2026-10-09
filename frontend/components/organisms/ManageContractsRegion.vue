<script setup>
import { ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import { useToast } from 'vue-toastification';
import H1Region from '~/components/atoms/H1Region.vue';
import AddVariable from '../molecules/AddVariable.vue';
import VariableDetail from '~/components/molecules/VariableDetail.vue';
import ManageContractsView from './ManageContractsView.vue';
import ContractRegion from './ContractRegion.vue';
import AppLoading from '~/components/atoms/AppLoading.vue';

const { t } = useI18n();
const toast = useToast();

const emit = defineEmits(['close', 'changed']);
const { $ContractApiService, $ConfiglistApiService, $PriceRateApiService } = useNuxtApp();

const pending = ref(true);
const loading = ref(true);
const loading_contracts = ref(false)
const view_data = ref({})

const attemptedSaved = ref(false)
const showSummary = ref(false)
const error = ref(null);

const contracts = ref([])
const contract_ids = ref([])
const total_contracts = ref(0);

const variables = ref([]);
const bonifications = ref([]);
const client_types = ref([]);
const use_types = ref([]);
const categories = ref([]);
const products = ref([])
const price_rates = ref([])

const selected_variables = ref([]);
const selected_bonifications = ref([]);
const selected_client_types = ref([]);
const selected_use_types = ref([]);
const selected_categories = ref([]);
const selected_products = ref([]);
const selected_price_rates = ref([]);

const var_type_ids = ref([])
const bonification_ids = ref([])
const client_type_ids = ref([])
const category_ids = ref([])
const use_type_ids = ref([])
const product_ids = ref([])
const price_rate_ids = ref([])
const var_saved = ref([])

const operation = ref('OFF');

const SubRegion = ref(false);

const getData = async () => {
  error.value = null;
  try {
    if (operation.value == 'OFF') {
      loading_contracts.value = true;
      view_data.value = {
        variable_type_ids: var_type_ids.value,
        bonification_type_ids: bonification_ids.value,
        client_type_ids: client_type_ids.value,
        category_ids: category_ids.value,
        use_type_ids: use_type_ids.value,
        product_ids: product_ids.value,
      }
      let response = await $ContractApiService.getAll(
        '', [], 1, null, false,
        var_type_ids.value, bonification_ids.value, client_type_ids.value,
        use_type_ids.value, category_ids.value, product_ids.value);
      contracts.value = response.results;
      total_contracts.value = response.count;
    }
    if (operation.value == 'ADD') {
      view_data.value = {
        client_type_ids: client_type_ids.value,
        category_ids: category_ids.value,
        use_type_ids: use_type_ids.value,
      }
      let response = await $ContractApiService.getAll(
        '', [], 1, null, false,
        [], [], client_type_ids.value,
        use_type_ids.value, category_ids.value, []);
      contracts.value = response.results;
      total_contracts.value = response.count;
    }
  } catch (err) {
    error.value = err;
  } finally {
    pending.value = false;
    loading_contracts.value = false;
  }
}

const getVariables = async () => {
  loading.value = true;
  try {
    const response = await $ConfiglistApiService.getAll('contract/variable-type');
    variables.value = [];
    response.results.forEach(function (item) {
      variables.value.push({
        label: item.name,
        code: item.id
      })
    })
  } catch (error) {
    console.error(error);
  } finally {
    loading.value = false;
  }
}

const getBonifications = async () => {
  loading.value = true;
  try {
    const response = await $ConfiglistApiService.getAll('contract/bonification-type');
    bonifications.value = [];
    response.results.forEach(function (item) {
      bonifications.value.push({
        label: item.name,
        code: item.id
      })
    })
  } catch (error) {
    console.error(error);
  } finally {
    loading.value = false;
  }
}

const getClientTypes = async () => {
  loading.value = true;
  try {
    const response = await $ConfiglistApiService.getAll('contract/contract-client-type');
    client_types.value = [];
    response.results.forEach(function (item) {
      client_types.value.push({
        label: item.name,
        code: item.id
      })
    })
  } catch (error) {
    console.error(error);
  } finally {
    loading.value = false;
  }
}

const getCategories = async () => {
  loading.value = true;
  try {
    const response = await $ConfiglistApiService.getAll('contract/contract-category');
    categories.value = [];
    response.results.forEach(function (item) {
      categories.value.push({
        label: item.name,
        code: item.id
      })
    })
  } catch (error) {
    console.error(error);
  } finally {
    loading.value = false;
  }
}

const getUseTypes = async () => {
  loading.value = true;
  try {
    const response = await $ConfiglistApiService.getAll('contract/contract-use-type');
    use_types.value = [];
    response.results.forEach(function (item) {
      use_types.value.push({
        label: item.name,
        code: item.id
      })
    })
  } catch (error) {
    console.error(error);
  } finally {
    loading.value = false;
  }
}

const getProducts = async () => {
  loading.value = true;
  try {
    const response = await $ConfiglistApiService.getAll('pricing/product');
    products.value = [];
    response.results.forEach(function (item) {
      products.value.push({
        label: item.name,
        code: item.id
      })
    })
  } catch (error) {
    console.error(error);
  } finally {
    loading.value = false;
  }
}

const getPriceRates = async () => {
  const response = await $PriceRateApiService.getAll('', [], 1, null, false, product_ids.value);
  price_rates.value = [];
  const validPriceRateIds = new Set();
  response.results.forEach(function (item) {
    price_rates.value.push({
      label: item.name,
      code: item.id
    })
    validPriceRateIds.add(item.id);
  })
  selected_price_rates.value = selected_price_rates.value.filter((rate) =>
    validPriceRateIds.has(rate.code)
  );
  /* price_rate_ids.value = price_rate_ids.value.filter((id) =>
    validPriceRateIds.has(id)
  ); */
  
}

const updateSelect = (event, entity) => {
  switch (entity) {
    case 'client_type':
      selected_client_types.value = event;
      break;
    case 'category':
      selected_categories.value = event;
      break;
    case 'use_type':
      selected_use_types.value = event;
      break;
    case 'variable':
      selected_variables.value = event;
      break;
    case 'bonification':
      selected_bonifications.value = event;
      break;
    case 'product':
      selected_products.value = event;
      break;
    case 'price_rate':
      selected_price_rates.value = event;
      break;
  }
}

const onVariableSaved = (item) => {
  var_type_ids.value.push(item.type.id)
  let saved_item = item.type
  
  saved_item.start_at = item.start_at
  saved_item.end_at = item.end_at
  saved_item.value = "True"
  var_saved.value.push(saved_item)
  
  closeAllRegions();
}

const onDeleteBonification = () => {
}

const obtainContractIds = async () => {
  attemptedSaved.value = true
  if(!isValid()) return
  
  try {
    const save_options = {
      variable_type_ids: var_type_ids.value,
      bonification_type_ids: bonification_ids.value,
      client_type_ids: client_type_ids.value,
      category_ids: category_ids.value,
      use_type_ids: use_type_ids.value,
      product_ids: product_ids.value,
      price_rate_ids: price_rate_ids.value,
      operation: operation.value,
      saved_vars: var_saved.value,
      saving: false,
    }

    let response = await $ContractApiService.manageMassively(save_options);
    contract_ids.value = {
      contract_ids: response.contract_ids,
      debt_management: response.total_contracts_debt_management,
    }
    showSummary.value = true
    await nextTick()
    
  }
  catch (error) {
    console.error(error)
  }
}

const save = async (saving) => {
  if(!saving) {
    showSummary.value = false
    return
  }
  showSummary.value = false
  if(!isValid()) return
  try {
    const save_options = {
      variable_type_ids: var_type_ids.value,
      bonification_type_ids: bonification_ids.value,
      client_type_ids: client_type_ids.value,
      category_ids: category_ids.value,
      use_type_ids: use_type_ids.value,
      product_ids: product_ids.value,
      price_rate_ids: price_rate_ids.value,
      operation: operation.value,
      saved_vars: var_saved.value,
    }

    let response = await $ContractApiService.manageMassively(save_options);

    await nextTick()
    successMessage()
    emit('close')
  }
  catch (error) {
    console.log(error)
  }
}

const isValid = () => {
  if (total_contracts.value == 0) {
    toast.error(t('Cal seleccionar mínim un contracte per a la gestió'))
    return false
  }
  if (operation.value == "OFF" && selected_variables.value.length == 0 && selected_bonifications.value.length == 0 && selected_products.value.length == 0) return false
  if (operation.value == "ADD" && selected_products.value.length == 0 && selected_price_rates.value.length == 0 && var_saved.value.length == 0) return false
  return true
}

const successMessage = () => {
  let text = t('common.correct_finish')
  if (total_contracts.value > 0) {
    text = text + ': ' + total_contracts.value + ' ' + t('contract_block.affected_contracts')
  }

  toast.success(text, {
    position: "top-right",
    timeout: 5000,
    closeOnClick: true,
    pauseOnFocusLoss: false,
    pauseOnHover: true,
    draggable: true,
    draggablePercent: 0.6,
    showCloseButtonOnHover: false,
    hideProgressBar: false,
    closeButton: 'button',
    icon: true,
    rtl: false,
  });
}

onMounted(() => {
  getVariables()
  getBonifications()
  getClientTypes()
  getCategories()
  getUseTypes()
  getProducts()
  getPriceRates()
  getData();
});


const showRegionDetailComponent = ref(null);
const regionDetailId = ref(null);

const showRegion = ref(false);
const showRegionComponent = ref(null);
const editVariable = ref(null);

const openAddVariable = () => {
  closeAllRegions();
  showRegion.value = true;
  showRegionComponent.value = 'AddVariable';
  editVariable.value = null;
}

const closeAllRegions = () => {
  showRegionComponent.value = null;
  showRegion.value = false;
};


const updateSubRegion = function () {
  getData();
  closeAllRegions();
  nextTick()
  emit('changed')
}

watch([
  selected_variables,
  selected_categories,
  selected_client_types,
  selected_use_types,
  selected_bonifications,
  selected_products,
  selected_price_rates,
], async () => {
  var_type_ids.value = selected_variables.value.map(el => el.code)
  bonification_ids.value = selected_bonifications.value.map(el => el.code)
  client_type_ids.value = selected_client_types.value.map(el => el.code)
  category_ids.value = selected_categories.value.map(el => el.code)
  use_type_ids.value = selected_use_types.value.map(el => el.code)
  product_ids.value = selected_products.value.map(el => el.code)
  price_rate_ids.value = selected_price_rates.value.map(el => el.code)
  await getData();
});

watch(() => selected_products.value, async (newValue, oldValue) => {
  getPriceRates()
})

watch(() => operation.value, () => {
  attemptedSaved.value = false
  selected_variables.value = []
  selected_bonifications.value = []
  selected_products.value = []
  selected_price_rates.value = []
})

</script>

<template>
  <Teleport to="body">
    <div v-if="showSummary" @click="showSummary = false"
    class="fixed inset-0 text-sm flex items-center justify-center bg-black bg-opacity-50 z-30">
      <ManageContractsView v-if="showSummary" :contract_ids="contract_ids" :value="view_data"
      class="p-4 bg-white shadow-lg rounded-lg" @save="save" @click.stop />
    </div>
  </Teleport>
  <div class="region__content">
    <div v-if="pending" class="h-full min-h-[400px]">
      <AppLoading :text="$t('common.loading')" />
    </div>
    <div v-else-if="error">
      <p>Error: {{ error.message }}</p>
      <p><button @click="getData" class="underline text-sky-500 hover:no-underline">{{ $t('common.load_again')
          }}</button></p>
    </div>
    <div v-else class="transition-all duration-500 ease" :class="{ 'mr-[95%]': showRegion }">
      <div class="flex justify-between relative">
        <H1Region class="mb-3">
          {{ $t('contract_block.mng_contracts') }}
        </H1Region>
      </div>

      <div id="conditionals" class="grid grid-cols-2 gap-3">
        <div>
          <label class="block mb-2 text-sm font-medium text-gray-700">
            {{ $t('contract_block.client_type') }}
          </label>
          <v-select multiple class="block w-full mr-1 custom-select" :model-value="selected_client_types"
            @update:modelValue="updateSelect($event, 'client_type')" :options="client_types" :loading="loading" />
        </div>
        <div>
          <label class="block mb-2 text-sm font-medium text-gray-700">
            {{ $t('contract_block.category') }}
          </label>
          <v-select multiple class="block w-full mr-1 custom-select" :model-value="selected_categories"
            @update:modelValue="updateSelect($event, 'category')" :options="categories" :loading="loading" />
        </div>
        <div>
          <label class="block mb-2 text-sm font-medium text-gray-700">
            {{ $t('common.usage_type') }}
          </label>
          <v-select multiple class="block w-full mr-1 custom-select" :model-value="selected_use_types"
            @update:modelValue="updateSelect($event, 'use_type')" :options="use_types" :loading="loading" />
        </div>

      </div>


      <div id="options" class="bg-slate-100 rounded-md px-4 py-2 my-3 w-max">
        <div class="flex items-center p-2">
          <label class="mr-4 flex items-center">
            <input type="radio" v-model="operation" value="ADD" @change="fieldChanged" /> 
            <span class="px-2 flex items-center font-semibold">
              {{ t('common.add') }}
            </span>
          </label>
          <label class="flex items-center">
            <input type="radio" v-model="operation" value="OFF" @change="fieldChanged" /> 
            <span class="px-2 flex items-center font-semibold">
              {{ t('common.delete')}}
            </span>
          </label>
        </div>
      </div>

      <div v-if="operation == 'OFF'" id="items" class="grid grid-cols-2 gap-3">
        <div v-if="selected_variables.length > 0"
          class="bg-sky-100 text-sky-700 py-3 px-5 rounded-lg mb-3 flex items-center justify-between col-span-2 mx-5">
          <span>
            {{ $t('Les bonificacions relacionades amb aquestes variables també seran tretes') }}</span>
        </div>
        <div>
          <label class="block mb-2 text-sm font-medium text-gray-700">
            {{ $t('variables') }}
          </label>
          <v-select multiple class="block w-full mr-1 custom-select" :model-value="selected_variables"
            @update:modelValue="updateSelect($event, 'variable')" :options="variables" :loading="loading" 
            :class="{'invalid': attemptedSaved && selected_variables.length == 0 && selected_bonifications.length == 0 && selected_products.length == 0 }" />
        </div>
        <div>
          <label class="block mb-2 text-sm font-medium text-gray-700">
            {{ $t('bonifications') }}
          </label>
          <v-select multiple class="block w-full mr-1 custom-select" :model-value="selected_bonifications"
            @update:modelValue="updateSelect($event, 'bonification')" :options="bonifications" :loading="loading" 
            :class="{'invalid': attemptedSaved && selected_variables.length == 0 && selected_bonifications.length == 0 && selected_products.length == 0 }" />
        </div>
        <div>
          <label class="block mb-2 text-sm font-medium text-gray-700">
            {{ $t('common.products') }}
          </label>
          <v-select multiple class="block w-full mr-1 custom-select" :model-value="selected_products"
            @update:modelValue="updateSelect($event, 'product')" :options="products" :loading="loading" 
            :class="{'invalid': attemptedSaved && selected_variables.length == 0 && selected_bonifications.length == 0 && selected_products.length == 0 }" />
        </div>
      </div>

      <div v-if="operation == 'ADD'" id="items" class="grid grid-cols-2 gap-3">
        <!-- <div>
          <label class="block mb-2 text-sm font-medium text-gray-700">
            {{ $t('Variables') }}
          </label>
          <div>
            <button name="" class="button-default-xs" @click="openAddVariable"
            :class="{'invalid': attemptedSaved && selected_variables.length == 0 && selected_bonifications.length == 0 && selected_products.length == 0 && var_saved?.length == 0}">
              <Icon name="fa-solid:plus" class="text-slate-500 mr-1" />
              {{ $t('Afegir variable') }}
            </button>

            <div v-if="var_saved">
              <div v-for="variable in var_saved" :key="variable.id" class="mt-2 text-sm bg-green-100 p-2">
                <VariableDetail :item="variable" class="bg-green-100" @delete="onDeleteBonification"/>
              </div>
            </div>

          </div>
        </div> -->
        <!-- <div>
          <label class="block mb-2 text-sm font-medium text-gray-700">
            {{ $t('Bonificacions') }}
          </label>
        </div> -->
        <div>
          <label class="block mb-2 text-sm font-medium text-gray-700">
            {{ $t('common.products') }}
          </label>
          <v-select multiple class="block w-full mr-1 custom-select" :model-value="selected_products"
            @update:modelValue="updateSelect($event, 'product')" :options="products" :loading="loading" 
            :class="{'invalid': attemptedSaved && selected_variables.length == 0 && selected_bonifications.length == 0 && selected_products.length == 0 && var_saved?.length == 0}" />
        </div>
        <div v-if="selected_products.length > 0">
          <label class="block mb-2 text-sm font-medium text-gray-700">
            {{ $t('common.price_rates') }}
          </label>
          <v-select multiple class="block w-full mr-1 custom-select" :model-value="selected_price_rates"
            @update:modelValue="updateSelect($event, 'price_rate')" :options="price_rates" :loading="loading" 
            :class="{'invalid': attemptedSaved && selected_products.length == 0 && selected_price_rates.length == 0 && var_saved?.length == 0}" />
        </div>
      </div>

      <hr class="my-2" />

      <div class="border border-slate p-2 rounded-md w-[350px]">
        <div class="flex justify-between items-center">
          <span>
            {{ t('contract_block.affected_contracts') }}
          </span>
          <div class="flex items-center gap-2 bg-slate-200 px-2 py-1 rounded-md">
            <span v-if="loading_contracts">
              <Icon name="fa6-solid:spinner" class="animate-spin text-lg text-slate-500" />
            </span>
            <span v-else>
              {{ total_contracts }}
            </span>
          </div>
        </div>
      </div>

      <hr class="my-2" />

      <div class="flex flex-row-reverse mt-4">
        <button @click="obtainContractIds" :disabled="false" class="button-success">
          <Icon name="fa6-solid:floppy-disk" />&nbsp; {{ $t('common.save') }}
        </button>
      </div>

    </div>

    <div v-if="showRegion == true" role="region" id="subregion"
      class="fixed h-full border-l border-gray-100 top-0 right-0 transition-transform duration-500 ease py-2 text-base bg-white z-10 w-[95%] overflow-y-auto overflow-x-hidden"
      :class="{ 'translate-x-0': showRegion, 'translate-x-full': !showRegion }">
      <div id="region_nav" class="mb-3 px-3">
        <button @click="closeAllRegions()" class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300">
          <Icon name="fa6-solid:angles-right" class="text-slate-500" />
        </button>
      </div>
      <div class="px-10">
        <AddVariable v-if="showRegionComponent == 'AddVariable'" 
        @new-item="onVariableSaved" :multiple="true" />

      </div>
    </div>
  </div><!-- end region__content -->
</template>
