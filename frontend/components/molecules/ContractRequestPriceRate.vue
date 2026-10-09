<script setup>
// components/molecules/ContractRequestPriceRate.vue
import { ref, onMounted, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import VulnerabilityRequestIndividualEdit from '../organisms/VulnerabilityRequestIndividualEdit.vue';
import InputDocument from '~/components/atoms/InputDocument.vue';
import AddBonification from '~/components/molecules/AddBonification.vue';
import AddVariable from '~/components/molecules/AddVariable.vue';
import { useStandaloneVariableTypes } from '~/composables/useStandaloneVariableTypes';
import BonificationDetail from '~/components/molecules/BonificationDetail.vue';
import VariableDetail from '~/components/molecules/VariableDetail.vue';
import PriceRateSelectMultiple from '~/components/organisms/PriceRateSelectMultiple.vue';

const { $ContractRequestDocumentationApiService, $ConfiglistApiService, $PersonApiService, $PriceRateApiService, $BonificationApiService, $VariableApiService, $ConfigProjectApiService, $VulnerabilityRequestApiService } = useNuxtApp();
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
const editVariable = ref(null);

const selectedContractCategory = ref("");
const selectedContractUseType = ref("");
const selectedContractClientType = ref("");

const allPriceRates = ref([]);
const priceRates = ref([]);
const priceRateSelectedItems = ref([]);
const supplyPointPriceRate = ref(null)

const optionsContractCategories = ref([]);
const optionsContractUseTypes = ref([]);
const optionsContractClientTypes = ref([]);

const isLoadingContractCategories = ref(false);
const isLoadingContractUseTypes = ref(false);
const isLoadingContractClientType = ref(false);

const isLoadingDocuments = ref(false);

const loading = ref(true);
const holder = ref(null);

const documents = ref([]);
const bonificacions = ref([]);
const variables = ref([]);

const documentationTypeMandatoryTokens = ref([]);
const documentationTypeMandatoryAllChecked = ref(false);

const origin_contract_token = ref(null)
const origin_reading_token = ref(null)

const vulnerabilityRequest = ref(false)
const vulnerabilityRequestId = ref(null)

const singlePriceRate = ref(false);
const usedSupplyPoints = ref([]);

const requestTypePriceRates = computed(() => {
  const rates = props.request?.type?.price_rates ?? [];
  return rates.map((pr) => {
    if (pr && typeof pr === 'object') {
      return allPriceRates.value.find((r) => r.id == pr.id) || pr;
    }
    return allPriceRates.value.find((r) => r.id == pr) || { id: pr, name: String(pr) };
  }).filter(Boolean);
});

const requestTypePriceRateIds = computed(() =>
  requestTypePriceRates.value.map((pr) => pr.id)
);

const anomaliesPriceRates = computed(() => {
  const typeIds = requestTypePriceRateIds.value;
  return (priceRates.value ?? []).filter((pr) => {
    const prId = pr?.price_rate?.id;
    return prId && !typeIds.some((id) => id == prId);
  });
});

const missingPriceRates = computed(() => {
  const typeRates = requestTypePriceRates.value;
  if (!typeRates.length) return [];

  const missing = [];
  for (const supplyPoint of usedSupplyPoints.value ?? []) {
    const selectedIds = (priceRates.value ?? [])
      .filter((v) => v.supply_point.id == supplyPoint.id)
      .map((v) => v.price_rate?.id);
    for (const typePr of typeRates) {
      if (!selectedIds.some((id) => id == typePr.id)) {
        missing.push({
          price_rate: typePr,
          supply_point: supplyPoint
        });
      }
    }
  }
  return missing;
});

const unrelatedForSupplyPoint = (supplyPointId) =>
  anomaliesPriceRates.value.filter((v) => v.supply_point.id == supplyPointId);

const missingForSupplyPoint = (supplyPointId) =>
  missingPriceRates.value.filter((v) => v.supply_point.id == supplyPointId);

const openAddBonification = () => {
  closeAllRegions();
  showRegion.value = true;
  showRegionComponent.value = 'AddBonification';
}

// Només es poden afegir soles les variables personalitzades (no vinculades a cap
// bonificació): si no n'hi ha cap, les variables només entren via bonificacions.
const { standaloneVariableTypes, fetchStandaloneVariableTypes } = useStandaloneVariableTypes();
onMounted(fetchStandaloneVariableTypes);

const openAddVariable = () => {
  closeAllRegions();
  showRegion.value = true;
  showRegionComponent.value = 'AddVariable';
  editVariable.value = null;
}

/** El llapis d'una variable obre el mateix formulari, amb la variable carregada. */
const onEditVariable = (variable) => {
  closeAllRegions();
  showRegion.value = true;
  showRegionComponent.value = 'AddVariable';
  editVariable.value = variable;
}

const openEditPriceRates = async (supplyPoint) => {
  priceRateSelectedItems.value = priceRates.value.filter(v => v.supply_point.id == supplyPoint.id).map(v => v.price_rate.id)
  supplyPointPriceRate.value = supplyPoint;
  await closeAllRegions();
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
  // Tanquem tots els components
  showRegionComponent.value = null;
  // Tanquem region
  showRegion.value = false;
}

const emitChange = () => {
  let data = {
    category: selectedContractCategory.value || null,
    use_type: selectedContractUseType.value || null,
    client_type: selectedContractClientType.value || null,
    price_rates_ids: priceRates.value || null,
    singlePriceRate: singlePriceRate.value || false
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
  const dataResponse = await $PriceRateApiService.getAll('', [], 1, null, false, null, null, true, props.request?.type?.exploitation);
  allPriceRates.value = dataResponse.results
}

const loadData = async () => {
  if (props.request) {
    // Assigna les dades del request si estan disponibles
    selectedContractCategory.value = props.request.category?.id || "";
    selectedContractUseType.value = props.request.use_type?.id || "";
    selectedContractClientType.value = props.request.client_type?.id || "";
    priceRates.value = props.request.price_rates || [];
    singlePriceRate.value = props.request.use_general_price_rates || false;
    usedSupplyPoints.value = props.request.use_general_price_rates? [props.request.supply_point_default] : props.request.supply_points;
    holder.value = await $PersonApiService.getDetail(props.request.holder);
    //priceRateSelectedItems.value = props.request.price_rates? props.request.price_rates.map(v => v.price_rate.id) : [];
  }
}

const handleSingularPriceRateChange = () => {
  usedSupplyPoints.value = singlePriceRate.value? [props.request.supply_point_default] : props.request.supply_points;
}

const getVulnerabilityRequest = async () => {
  showRegion.value = false;
  try {
    const response = await $VulnerabilityRequestApiService.getAll('', [], 1, null, false, null, null, null, props.request.id);
    vulnerabilityRequest.value = response.count > 0
    if (response.count > 0) {
      vulnerabilityRequestId.value = response.results[0].id
    }
  } catch (error) {
    console.error('Error loading draft:', error);
  }
}

const createVulnerabilityRequest = async () => {
  if (!confirm(t('confirmation_text_block.confirm_create_vulnerability_request'))) return;
  try {
    let response = await $VulnerabilityRequestApiService.save({
      contract_request_id: props.request.id
    });
    if (response) {
      await getVulnerabilityRequest()
      openVulnerabilityRequest()
    }
  } catch (error) {
    toast.error(t('common.error_save'));
    console.error(error);
  }
}

const openVulnerabilityRequest = function () {
  showRegion.value = true;
  showRegionComponent.value = 'VulnerabilityRequestRegion';
}

onMounted(async () => {
  origin_contract_token.value = await $ConfigProjectApiService.get('origin_contract_token');
  origin_reading_token.value = await $ConfigProjectApiService.get('origin_reading_token');
  await loadDocuments();
  await loadContractCategories();
  await loadContractUseTypes();
  await loadContractClientTypes();
  await loadBonifications();
  await loadVariables();
  await loadPriceRates();
  await loadData();
  await getVulnerabilityRequest()
  loading.value = false;
});

const onBonificationSaved = (item) => {
  loadBonifications();
  loadVariables();
  toggleRegion(false);
}

const onDeleteBonification = () => {
  loadBonifications();
  loadVariables();
}

const onVariableSaved = (item) => {
  loadBonifications();
  loadVariables();
  toggleRegion(false);
}

const onDocumentChecked = async (data) => {
  const doc = documents.value.find(doc => doc.type.token === data.type);
  doc.checked = data.checked;
  if (doc.checked == true) {
    const docResponse = await $ContractRequestDocumentationApiService.save({
      contract_request: props.request.id,
      type: doc.type.id
    });
    doc.id = docResponse.id;
  } else if (doc.id) {
    $ContractRequestDocumentationApiService.doDelete(doc);
  }

  // comprovem si tots els documents obligatoris estan marcats
  checkIfAllMandatoriesAreChecked();
}

const onDocumentUpdate = (doc) => {
  console.log('onDocumentUpdate', doc);
  // TODO: Implementar
}

const onDocumentDelete = (doc) => {
  console.log('onDocumentDelete', doc);
  // TODO: Implementar
}

const handleSubRegionEvent = (event) => {
  isSubRegionOpen.value = event;
}

watch(priceRateSelectedItems, async (newItems, oldItems) => {
  if (!loading.value) {
    priceRates.value = priceRates.value.filter(v => v.supply_point.id != supplyPointPriceRate.value.id)
    newItems.forEach(id => {
      const item = allPriceRates.value.find(pr => pr.id == id);
      if (item) {
        let new_item = {
          price_rate: item,
          supply_point: supplyPointPriceRate.value
        }
        priceRates.value.push(new_item);
      }
    });
  }
});

// Observa canvis en la sol·licitud per recarregar les dades si cal
watch(() => props.request, (newVal) => {
  loadData();
});

// Observa canvis en selectors per emetre l'esdeveniment
watch([selectedContractCategory, priceRateSelectedItems, selectedContractClientType, selectedContractUseType, singlePriceRate], () => {
  emitChange();
});
</script>
<template>
  <div id="wrapper" class="text-base">
    <!-- Títol del Component -->
    <h2 class="text-xl font-semibold mb-4">{{ $t('contract_block.request_price_rate_title') }}</h2>

    <div v-if="holder && holder.vulnerability_level > 1" class="bg-orange-50 border-l-4 border-orange-400 px-4 py-2 mb-4">
      <div class="grid grid-cols-[auto,1fr] gap-2">
        <div class="m-auto">
          <AtomsVulnerabilityCheck :vulnerability_level="holder.vulnerability_level" :small="true" />
        </div>
        <div class="ml-3">
          <p class="text-sm text-orange-700">
            {{ $t('informative_block.info_vulnerable_or_pending') }}
          </p>
          <p class="text-sm text-orange-700">
            {{ $t('informative_block.info_request_vulnerable') }}
          </p>
        </div>
      </div>
    </div>

    <!-- Documentació -->
    <div class="mb-4" v-if="request.type?.documentation_types">
      <label class="flex text-sm font-medium text-gray-700 mb-3 gap-2">
        <Icon v-show="documentationTypeMandatoryAllChecked" name="fa6-solid:circle-check"
          class="text-xl text-emerald-600" />
        <Icon v-show="!documentationTypeMandatoryAllChecked" name="fa6-solid:asterisk" class="text-lg text-pink-600" />
        <span>{{ $t('common.documentation') }}:</span>
      </label>

      <div>
        <div v-for="docType in request.type?.documentation_types" :key="docType.id" class="flex items-center gap-3">
          <InputDocument :doc_type="docType" @document-checked="onDocumentChecked" @document-update="onDocumentUpdate"
            @document-delete="onDocumentDelete"
            :is_checked="documents.find(doc => doc.type.token === docType.token)?.checked || false" />

        </div>
      </div>
    </div>
    <!-- /end Documentació -->


    <div class="grid grid-cols-3 gap-3">
      <!-- Selecció de CategoryUseType -->
      <div class="mb-4">
        <label for="contractUseType" class="flex text-sm font-medium text-gray-700 mb-3 gap-2">
          <Icon v-show="selectedContractUseType" name="fa6-solid:circle-check" class="text-xl text-emerald-600" />
          <Icon v-show="!selectedContractUseType" name="fa6-solid:asterisk" class="text-lg text-slate-400" />
          <span>{{ $t('common.usage_type') }}</span>
        </label>

        <div>
          <div class="flex items-center">
            <select id="contractUseType" v-model="selectedContractUseType"
              class="w-full text-base border border-gray-300 rounded p-2" :disabled="isLoadingContractUseTypes">
              <option value="">--{{ $t('common.no_usage_type') }}</option>
              <option v-for="item in optionsContractUseTypes" :key="item.id" :value="item.id">
                {{ item.name }}
              </option>
            </select>
          </div>

          <!-- Indicador de Carrega -->
          <div v-if="isLoadingContractUseTypes" class="mt-2 text-sm text-gray-500">
            {{ $t('common.loading') }}...
          </div>
        </div>
      </div>
      <!-- /end Selecció de CategoryUseType -->

      <!-- Selecció de ClientType -->
      <div class="mb-4">
        <label for="contractClientType" class="flex text-sm font-medium text-gray-700 mb-3 gap-2">
          <Icon v-show="selectedContractClientType" name="fa6-solid:circle-check" class="text-xl text-emerald-600" />
          <Icon v-show="!selectedContractClientType" name="fa6-solid:asterisk" class="text-lg text-slate-400" />
          <span>{{ $t('contract_block.client_type') }}:</span>
        </label>

        <div>
          <div class="flex items-center">
            <select id="contractClientType" v-model="selectedContractClientType"
              class="w-full text-base border border-gray-300 rounded p-2" :disabled="isLoadingContractClientType">
              <option value="">--{{ $t('contract_block.no_client_type') }}</option>
              <option v-for="item in optionsContractClientTypes" :key="item.id" :value="item.id">
                {{ item.name }}
              </option>
            </select>
          </div>

          <!-- Indicador de Carrega -->
          <div v-if="isLoadingContractClientType" class="mt-2 text-sm text-gray-500">
            {{ $t('common.loading') }}...
          </div>
        </div>
      </div>
      <!-- /end Selecció de ClientType -->

      <!-- Selecció de Categoria de Contracte -->
      <div class="mb-4">
        <label for="contractCategory" class="flex text-sm font-medium text-gray-700 mb-3 gap-2">
          <Icon v-show="selectedContractCategory" name="fa6-solid:circle-check" class="text-xl text-emerald-600" />
          <Icon v-show="!selectedContractCategory" name="fa6-solid:asterisk" class="text-lg text-slate-400" />
          <span>{{ $t('contract_block.category') }}:</span>
        </label>

        <div>
          <div class="flex items-center">
            <select id="contractCategory" v-model="selectedContractCategory"
              class="w-full text-base border border-gray-300 rounded p-2" :disabled="isLoadingContractCategories">
              <option value="">--{{ $t('contract_block.no_category') }}</option>
              <option v-for="category in optionsContractCategories" :key="category.id" :value="category.id">
                {{ category.name }}
              </option>
            </select>
          </div>

          <!-- Indicador de Carrega -->
          <div v-if="isLoadingContractCategories" class="mt-2 text-sm text-gray-500">
            {{ $t('common.loading') }}...
          </div>
        </div>
      </div>
      <!-- /end Selecció de Categoria de Contracte -->

      <div v-if="request.supply_points.length > 1" class="mb-4 flex items-center gap-2">
        <input type="checkbox" v-model="singlePriceRate" @change="handleSingularPriceRateChange" />
        <abbr :title="t('informative_block.single_price_rate_info')"
        class="flex items-center">
          <Icon name="fa6-solid:circle-info" class="text-slate-500" />
        </abbr>
        <span>{{ $t('informative_block.unique_price_rate_info') }}</span>
      </div>

      <!-- Selecció de Tarifa de Preus -->
      <div v-for="supply_point in usedSupplyPoints" :key="supply_point.id" class="mb-4 col-span-3">
        <label for="priceRate" class="flex text-sm font-medium text-gray-700 mb-3 gap-2">
          <Icon v-show="priceRates.length != 0" name="fa6-solid:circle-check" class="text-xl text-emerald-600" />
          <Icon v-show="priceRates.length == 0" name="fa6-solid:asterisk" class="text-lg text-pink-600" />
          <span>{{ $t('contract_block.consumption_pr_per_sp') }} 
            {{ supply_point.token }} ({{ priceRates.filter(v => v.supply_point.id == supply_point.id).length}})</span>
        </label>

        <div id="price_rate_templates" class="mb-3 grid grid-cols-[2fr,1fr]">
          <div class="pl-3 pr-3">
            <div class="mb-2 grid grid-cols-2 gap-3">
              <div v-for="item in priceRates.filter(v => v.supply_point.id == supply_point.id)" class="mb-1">
                <Icon name="fa6-solid:cube" class="text-slate-500" /> &nbsp;<span class="font-semibold">{{
                  item.price_rate.product?.name || t('pricing_block.no_product') }}</span> - {{ item.price_rate.name }}
              </div>
            </div>
            <button name="" class="button-default-xs" @click="openEditPriceRates(supply_point)">
              <Icon name="fa-solid:plus" class="text-slate-500 mr-1" />
              {{ $t('common.modify') }} {{ t('common.products') }}/{{ t('common.price_rates') }}
            </button>
          </div>
        </div>
        <div class="mt-1"
          v-if="unrelatedForSupplyPoint(supply_point.id).length > 0 || missingForSupplyPoint(supply_point.id).length > 0">
          <div
            class="grid grid-cols-[auto,1fr] items-center gap-2 bg-orange-50 border-l-4 border-orange-400 text-orange-700 px-4 py-1 rounded relative"
            role="alert">
            <Icon name="fa6-solid:triangle-exclamation" class="text-orange-400 w-5 h-5" />
            <div>
              <p>
                <strong class="font-bold">{{ t('common.caution') }}</strong>
              </p>
              <template v-if="unrelatedForSupplyPoint(supply_point.id).length > 0">
                <p class="mb-1">
                  {{ t('warning_block.unrelated_price_rates_warning') }}
                </p>
                <div v-for="anomaly in unrelatedForSupplyPoint(supply_point.id)"
                  :key="`unrelated-${anomaly.price_rate?.id}`"
                  class="inline-flex items-center px-2 py-1 mx-1 rounded-md text-xs font-medium bg-white bg-opacity-60 border border-orange-500 text-slate-700 border border-orange-400">
                  {{ anomaly.price_rate.name }}
                </div>
              </template>
              <template v-if="missingForSupplyPoint(supply_point.id).length > 0">
                <p class="mb-1" :class="{ 'mt-2': unrelatedForSupplyPoint(supply_point.id).length > 0 }">
                  {{ t('warning_block.missing_price_rates_warning') }}
                </p>
                <div v-for="missing in missingForSupplyPoint(supply_point.id)"
                  :key="`missing-${missing.price_rate?.id}`"
                  class="inline-flex items-center px-2 py-1 mx-1 rounded-md text-xs font-medium bg-white bg-opacity-60 border border-orange-500 text-slate-700 border border-orange-400">
                  {{ missing.price_rate?.product?.name ? `${missing.price_rate?.product?.name} - ` : '' }} {{ missing.price_rate.name }}
                </div>
              </template>
            </div>
          </div>
        </div>
      </div>

      <!-- /end Selecció de Tarifa de Preus -->
    </div><!-- end grid-cols-2 -->

    <div class="grid grid-cols-3 gap-3">
      <!-- VULNERABLE REQUEST -->
      <div class="mt-2 mb-4">
        <label for="vulnerability" class="flex text-sm font-medium text-gray-700 mb-3 gap-2">
          <Icon v-show="vulnerabilityRequest" name="fa6-solid:circle-check" class="text-xl text-emerald-600" />
          <Icon v-show="!vulnerabilityRequest" name="fa6-solid:asterisk" class="text-lg text-slate-400" />
          <span>{{ $t('vulnerability_request') }}:</span>
        </label>
        <div class="mb-2">
          <div class="flex gap-3">
            <button v-if="vulnerabilityRequest && vulnerabilityRequestId" @click="openVulnerabilityRequest"
              class="button-default flex items-center gap-2">
              <span>{{ $t('common.show') }} {{ t('vulnerability_request') }}</span>

            </button>
            <button v-else @click="createVulnerabilityRequest" class="button-default flex items-center gap-2">
              <Icon name="fa-solid:plus" class="text-slate-500 mr-1" />
              <span>{{ $t('contract_block.new_vulnerability_req') }}</span>
            </button>

          </div>
        </div>
      </div>
      <!-- Selecció de Bonificacions -->
      <div class="mb-4">
        <label class="flex text-sm font-medium text-gray-700 mb-3 gap-2">
          <Icon v-show="bonificacions.length > 0" name="fa6-solid:circle-check" class="text-xl text-emerald-600" />
          <Icon v-show="bonificacions.length == 0" name="fa6-solid:asterisk" class="text-lg text-slate-400" />
          <span>{{ $t('bonifications') }}:</span>
        </label>

        <div>
          <div class="flex items-center gap-3">
            <button name="" class="button-default-xs" @click="openAddBonification">
              <Icon name="fa-solid:plus" class="text-slate-500 mr-1" />
              {{ $t('common.add') }} {{ t('contract_block.bonification') }}
            </button>
          </div>
          <div v-if="bonificacions" class="mt-2">
            <BonificationDetail v-for="bonification in bonificacions" :key="bonification.id" :item="bonification"
              @delete="onDeleteBonification" class="mb-2 text-slate-slate bg-green-100" />
          </div>

        </div>
      </div>
      <!-- /end Selecció de Bonificacions -->

      <!-- Selecció de Variables -->
      <div class="mb-4">
        <label class="flex text-sm font-medium text-gray-700 mb-3 gap-2">
          <Icon v-show="variables.length > 0" name="fa6-solid:circle-check" class="text-xl text-emerald-600" />
          <Icon v-show="variables.length == 0" name="fa6-solid:asterisk" class="text-lg text-slate-400" />
          <span>{{ $t('variables') }}:</span>
        </label>

        <div>
          <button v-if="standaloneVariableTypes.length > 0" name="" class="button-default-xs" @click="openAddVariable">
            <Icon name="fa-solid:plus" class="text-slate-500 mr-1" />
            {{ $t('common.add') }} {{ t('pricing_block.variable') }}
          </button>

          <div v-if="variables">
            <div v-for="variable in variables" :key="variable.id" class="mt-2 text-sm bg-green-100 p-2">
              <VariableDetail :item="variable" class="bg-green-100" :editButton="true"
                @delete="onDeleteBonification" @edit="onEditVariable(variable)" />
            </div>
          </div>

        </div>
        <!-- /end Selecció de Bonificacions -->
      </div>

    </div><!-- end grid-cols-2 -->

   

    <!-- Regió lateral per formularis -->
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
          @new-item="onVariableSaved" :variable="editVariable" />
        <PriceRateSelectMultiple v-if="showRegionComponent === 'EditPriceRates'" v-model="priceRateSelectedItems"
          :filter="[origin_reading_token]" :exploitation_id="request?.type?.exploitation" />
        <VulnerabilityRequestIndividualEdit v-if="showRegionComponent == 'VulnerabilityRequestRegion'"
          :vulnerability_id="parseInt(vulnerabilityRequestId)" @change="getVulnerabilityRequest"
          :isSubRegionOpen="isSubRegionOpen" :isSubRegion="true" />
      </div>
    </div>
    <!-- /end Regió lateral per formularis -->
  </div>
</template>
