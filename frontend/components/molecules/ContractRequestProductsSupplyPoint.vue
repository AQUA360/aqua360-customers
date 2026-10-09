<script setup>
// components/molecules/ContractRequestPriceRate.vue
import { ref, onMounted, watch } from 'vue';
import { useI18n } from 'vue-i18n';

import InputDocument from '~/components/atoms/InputDocument.vue';
import AddBonification from '~/components/molecules/AddBonification.vue';
import AddVariable from '~/components/molecules/AddVariable.vue';
import BonificationDetail from '~/components/molecules/BonificationDetail.vue';
import VariableDetail from '~/components/molecules/VariableDetail.vue';
import PriceRateSelectMultiple from '~/components/organisms/PriceRateSelectMultiple.vue';

const { $ContractRequestDocumentationApiService, $ConfigProjectApiService, $ConfiglistApiService, $PriceRateApiService, $BonificationApiService, $VariableApiService } = useNuxtApp();
const { t } = useI18n();

const props = defineProps({
  request: {
    type: Object,
    required: false
  }
});

const emit = defineEmits(['change', 'show-subregion']);

const showRegion = ref(false);
const showRegionComponent = ref(null);
const isSubRegionOpen = ref(false);

const selectedContractCategory = ref("");
const selectedContractUseType = ref("");
const selectedContractClientType = ref("");

const allPriceRates = ref([]);
const priceRates = ref([]);
const priceRateSelectedItems = ref([]);

const optionsContractCategories = ref([]);
const optionsContractUseTypes = ref([]);
const optionsContractClientTypes = ref([]);

const isLoadingContractCategories = ref(false);
const isLoadingContractUseTypes = ref(false);
const isLoadingContractClientType = ref(false);

const isLoadingDocuments = ref(false);

const loading = ref(true);

const documents = ref([]);
const bonificacions = ref([]);
const variables = ref([]);

const documentationTypeMandatoryTokens = ref([]);
const documentationTypeMandatoryAllChecked = ref(false);
const origin_supply_point_token = ref(null)


const openEditPriceRates = () => {
  closeAllRegions();
  showRegion.value = true;
  showRegionComponent.value = 'EditPriceRates';
}

const toggleRegion = (value) => {
  showRegion.value = value;
  if (value == false) {
    closeAllRegions();
    showRegionComponent.value = null;
  }
};


const closeAllRegions = () => {
  showRegionComponent.value = null;
  showRegion.value = false;
}

const emitChange = () => {
  let data = {
    registration_price_rates_ids: priceRateSelectedItems.value || null
  }

  emit('change', data);
}

const checkIfAllMandatoriesAreChecked = () => {
  documentationTypeMandatoryAllChecked.value = documentationTypeMandatoryTokens.value.every(token => {
    const doc = documents.value.find(doc => doc.type.token === token);
    return doc.checked;
  });
}

const loadDocuments = async () => {
  isLoadingDocuments.value = true;
  try {
    const data = await $ContractRequestDocumentationApiService.getAll('', { 'contract_request': props.request.id });
    if (data.results) {
      documents.value = data.results;
    }

    // mirem si tenim tots els documents tipus creats, si no els creem
    const docTypes = props.request?.type?.documentation_types || [];
    documentationTypeMandatoryTokens.value = [];
    for (const docType of docTypes) {
      if (docType.is_mandatory) {
        documentationTypeMandatoryTokens.value.push(docType.token);
      }

      const doc = documents.value.find(doc => doc.type.token === docType.token);

      if (!doc) {
        const newDoc = {
          contract_request: props.request.id,
          type: docType,
          checked: false
        };
        documents.value.push(newDoc);
      } else {
        doc.checked = true;
      }
    }

    // comprovem si tots els documents obligatoris estan marcats
    checkIfAllMandatoriesAreChecked();

  } catch (error) {
    console.error(`Error fetching documents:`, error);
  } finally {
    isLoadingDocuments.value = false;
  }
}

// Funció per carregar els tipus de contractació des de l'API
const loadContractCategories = async () => {
  isLoadingContractCategories.value = true;
  try {
    const data = await $ConfiglistApiService.getAll('contract/contract-category');
    if (data.results) {
      optionsContractCategories.value = data.results;
    }
  } catch (error) {
    console.error(`Error fetching contract categories:`, error);
  } finally {
    isLoadingContractCategories.value = false;
  }
}

// Funció per carregar els tipus de contractació des de l'API
const loadContractUseTypes = async () => {
  isLoadingContractUseTypes.value = true;
  try {
    const data = await $ConfiglistApiService.getAll('contract/contract-use-type');
    if (data.results) {
      optionsContractUseTypes.value = data.results;
    }
  } catch (error) {
    console.error(`Error fetching contract-use-type categories:`, error);
  } finally {
    isLoadingContractUseTypes.value = false;
  }
}

// Funció per carregar els tipus de contractació des de l'API
const loadContractClientTypes = async () => {
  isLoadingContractClientType.value = true;
  try {
    const data = await $ConfiglistApiService.getAll('contract/contract-client-type');
    if (data.results) {
      optionsContractClientTypes.value = data.results;
    }
  } catch (error) {
    console.error(`Error fetching contract-client-type categories:`, error);
  } finally {
    isLoadingContractClientType.value = false;
  }
}

const loadBonifications = async () => {
  const contract_request_id = props.request?.id || null;
  if (contract_request_id) {
    $BonificationApiService.getAll("", { 'contract_request': contract_request_id })
      .then((response) => {
        bonificacions.value = response.results;
      });
  }
}

const loadVariables = async () => {
  const contract_request_id = props.request?.id || null;
  if (contract_request_id) {
    $VariableApiService.getAll("", ['contract_request=' + contract_request_id])
      .then((response) => {
        variables.value = response.results;
      });
  }
}

const loadPriceRates = async () => {
  const dataResponse = await $PriceRateApiService.getAll();
  allPriceRates.value = dataResponse.results
}

const loadData = async () => {
  if (props.request) {
    const contract_supply_point = [];
    try {
      const price_rate = await $PriceRateApiService.getAll('', [], 1, null, false, null, ['subministrament']);
      contract_supply_point.value = price_rate.results;
    } catch (e) {
      console.error(e)
    }
    selectedContractCategory.value = props.request.category?.id || "";
    selectedContractUseType.value = props.request.use_type?.id || "";
    selectedContractClientType.value = props.request.client_type?.id || "";
    priceRates.value = props.request.registration_price_rates.filter(v => v.product?.origin_token == 'subministrament')|| null;
    if(priceRates.value.length === 0){
      priceRates.value = contract_supply_point.value;
    }
    priceRateSelectedItems.value = props.request.registration_price_rates?.filter(v => v.product?.origin_token == 'subministrament').map(v => v.id) || null;
    if(priceRateSelectedItems.value.length === 0){
      priceRateSelectedItems.value = contract_supply_point.value.map(v => v.id);
    }
  }
}

onMounted(async () => {
  origin_supply_point_token.value = await $ConfigProjectApiService.get('origin_supply_token');
  await loadDocuments();
  await loadContractCategories();
  await loadContractUseTypes();
  await loadContractClientTypes();
  await loadBonifications();
  await loadVariables();
  await loadPriceRates();
  await loadData();

  loading.value = false;
});

const onBonificationSaved = (item) => {
  loadBonifications();
  loadVariables();
  toggleRegion(false);
}


const onVariableSaved = (item) => {
  loadBonifications();
  loadVariables();
  toggleRegion(false);
}



watch(priceRateSelectedItems, async (newItems, oldItems) => {
  if (!loading.value) {
    priceRates.value = [];

    newItems.forEach(id => {
      const item = allPriceRates.value.find(pr => pr.id == id);
      if (item) {
        priceRates.value.push(item);
      }
    });
  }
});

// Observa canvis en la sol·licitud per recarregar les dades si cal
watch(() => props.request, (newVal) => {
  loadData();
});

// Observa canvis en selectors per emetre l'esdeveniment
watch([priceRateSelectedItems], () => {
  emitChange();
});
</script>
<template>
  <div id="wrapper" class="text-base">
    <h2 class="text-xl font-semibold mb-4">{{ $t('contract_block.request_products_supply_point_title') }}</h2>

    <div class="grid grid-cols-3 gap-3">
      <div>
        <em>{{ t('informative_block.info_supply_not_contracted') }}</em>
      </div>

      <div class="mb-4 col-span-3">
        <label for="priceRate" class="flex text-sm font-medium text-gray-700 mb-3 gap-2">
          <Icon v-show="priceRates.length != 0" name="fa6-solid:circle-check" class="text-xl text-emerald-600" />
          <Icon v-show="priceRates.length == 0" name="fa6-solid:asterisk" class="text-lg text-pink-600" />
          <span>{{ $t('common.products') }} ({{ priceRates.length }})</span>
        </label>

        <div id="price_rate_templates" class="mb-3">
          <div class="pl-3 pr-3">
            <div class="mb-2 grid grid-cols-2 gap-3">
              <div v-for="item in priceRates" class="mb-1">
                <Icon name="fa6-solid:cube" class="text-slate-500" /> &nbsp;<span class="font-semibold">{{
                  item.product?.name || t('pricing_block.no_product') }}</span> - {{ item.name }}
              </div>
            </div>
            <button name="" class="button-default-xs" @click="openEditPriceRates">
              <Icon name="fa-solid:plus" class="text-slate-500 mr-1" />
              {{ $t('common.modify') }} {{ t('common.products') }}/{{ t('common.price_rates') }}
            </button>
          </div>
        </div>
      </div>
    </div>

    <div role="region" id="right_page"
      class="fixed h-full border-l border-gray-100 top-0 right-0 transition-transform duration-500 ease py-2 text-base bg-white z-10"
      :class="{
        'translate-x-0': showRegion,
        'translate-x-full': !showRegion,
        'w-[95%]': isSubRegionOpen,
        'w-1/2': !isSubRegionOpen
      }">
      <div id="region_nav" class="mb-3 px-3 flex justify-start">
        <button @click="showRegion = false"
          class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300 rounded" aria-label="Tancar formulari">
          <Icon name="fa6-solid:angles-right" class="text-slate-500" />
        </button>
      </div>
      <div class="px-10">
        <!-- Components per afegir informació -->
        <AddBonification v-if="showRegionComponent == 'AddBonification'" :contract_request="request"
          @new-item="onBonificationSaved" />
        <AddVariable v-if="showRegionComponent == 'AddVariable'" :contract_request="request"
          @new-item="onVariableSaved" :variable="null" />
        <PriceRateSelectMultiple v-if="showRegionComponent === 'EditPriceRates'" v-model="priceRateSelectedItems"
          :filter="[origin_supply_point_token]" />
      </div>
    </div>
    <!-- /end Regió lateral per formularis -->
  </div>
</template>
