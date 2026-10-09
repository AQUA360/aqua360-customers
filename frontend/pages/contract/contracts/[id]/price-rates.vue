<script setup>
// components/organisms/ClusterDetail.vue
import { ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import { checkPermission } from '~/middleware/permission';
import { useToast } from 'vue-toastification';
import AddBonification from '~/components/molecules/AddBonification.vue';
import AddVariable from '~/components/molecules/AddVariable.vue';
import PriceRateSelectMultiple from '~/components/organisms/PriceRateSelectMultiple.vue';
import _ from 'lodash';
import { openAuthenticatedFileUrl } from '~/utils/open-authenticated-file';
import { formatDate } from '~/utils/date';

const route = useRoute()
const router = useRouter()
const { $ContractApiService, $BonificationApiService, $ContractRequestTypeApiService, $ConfigProjectApiService, $VariableApiService, $PriceRateApiService, $ConfiglistApiService, $ExploitationApiService } = useNuxtApp();
const { t } = useI18n();
const toast = useToast();
const objectPermissions = ref(null);
const showRegion = ref(false);
const showRegionComponent = ref(null);
const isSubRegionOpen = ref(false);

const allSupplyPoints = ref([])

const id = ref(route.params.id)
const contract = ref(null)

const bonifications = ref([]);
const variables = ref([]);

const selectedContractCategory = ref("");
const selectedContractUseType = ref("");
const selectedContractClientType = ref("");

const selectedUseType = ref(null);
const selectedNewUseType = ref(null);
const selectedContractType = ref(null);
const approveUseTypeChange = ref(false);
const useTypeChangeDocument = ref(null);
const selectedUseTypeChangeDocType = ref('');
const docTypes = ref([]);
const loadingDocTypes = ref(false);
const downloadingCommunicationPdf = ref(false);

const origin_reading_token = ref(null)
const allPriceRates = ref([]);
const priceRates = ref([]);
const priceRateSelectedItems = ref([]);
const supplyPointPriceRate = ref(null)

const useTypeOptions = ref([]);
const contractTypeOptions = ref([]);

const optionsContractCategories = ref([]);
const optionsContractUseTypes = ref([]);
const optionsContractClientTypes = ref([]);

const isLoadingContractRequestType = ref(false);
const isLoadingUseType = ref(false);
const isLoadingContractCategories = ref(false);
const isLoadingContractUseTypes = ref(false);
const isLoadingContractClientType = ref(false);
const loading = ref(true);

const singlePriceRate = ref(false);
const usedSupplyPoints = ref([]);
const savingBopReference = ref(false);

const useMultipleCompanies = ref(false);
const providerCompanies = ref([]);
const loadingProviderCompanies = ref(false);
const selectedCompanyId = ref('');
const singleCompanyId = ref(null);

const getResolvedCompanyId = () => {
  if (singleCompanyId.value != null) {
    return singleCompanyId.value;
  }
  if (providerCompanies.value.length === 1) {
    return providerCompanies.value[0].id;
  }
  const raw = selectedCompanyId.value;
  if (raw !== null && raw !== undefined && raw !== '') {
    const n = Number(raw);
    return Number.isFinite(n) ? n : null;
  }
  return null;
};

const resolvedCompanyId = computed(() => getResolvedCompanyId());

const syncAutoCompanySelectionFromLists = () => {
  if (singleCompanyId.value != null) {
    selectedCompanyId.value = String(singleCompanyId.value);
    return;
  }
  if (providerCompanies.value.length === 1) {
    selectedCompanyId.value = String(providerCompanies.value[0].id);
  }
};

const loadTypeOptions = async () => {
  isLoadingUseType.value = true;
  isLoadingContractRequestType.value = true;
  try {
    const data = await $ContractRequestTypeApiService.getAll(
      '', [], 1, null, false, false, null, null, contract.value?.exploitation?.id || null
    );
    if (data.results) {
      contractTypeOptions.value = data.results;
    }
  } catch (error) {
    console.error(`Error fetching contract-request-type categories:`, error);
  } finally {
    isLoadingContractRequestType.value = false;
  }
  try {
    const data = await $ConfiglistApiService.getAll('contract/contract-use-type');
    if (data.results) {
      useTypeOptions.value = data.results;
    }
  } catch (error) {
    console.error(`Error fetching contract-use-type categories:`, error);
  } finally {
    isLoadingUseType.value = false;
  }
}

const loadCompanyOptionsData = async () => {
  loadingProviderCompanies.value = true;
  singleCompanyId.value = null;
  providerCompanies.value = [];
  const priorSelection = selectedCompanyId.value;
  try {
    const firstPage = await $ExploitationApiService.getCompanies('', 1, null, false);
    if (firstPage.count === 1 && firstPage.results?.length === 1) {
      singleCompanyId.value = firstPage.results[0].id;
    }

    const collected = [];
    let page = 1;
    let hasNext = true;
    while (hasNext && page < 200) {
      const data = await $ExploitationApiService.getCompanies('', page, null, false, { is_provider: true });
      collected.push(...(data.results || []));
      hasNext = !!data.next;
      page += 1;
    }
    providerCompanies.value = collected;

    syncAutoCompanySelectionFromLists();
    if (
      singleCompanyId.value == null &&
      providerCompanies.value.length !== 1 &&
      priorSelection !== ''
    ) {
      selectedCompanyId.value = priorSelection;
    }
  } catch (error) {
    console.error('Error loading companies:', error);
  } finally {
    loadingProviderCompanies.value = false;
  }
};

const requestTypePriceRates = computed(() => {
  const sourceType = selectedContractType.value ?? contract.value?.contract_request_type;
  const rates = sourceType?.price_rates ?? [];
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

const bopCandidates = computed(() =>
  (priceRates.value ?? []).filter((v) => v.id != null)
);

// Mateix criteri que get_contract_tarifa_bop() al backend: prioritza el número de BOE
// i cau a la data quan no està informat, perquè moltes publicacions encara no el tenen.
// La data es formata amb formatDate perquè coincideixi amb el valor de contract.tarifa_bop,
// que el backend ja retorna com a dd/mm/aaaa i es mostra just a sobre d'aquesta llista.
const getBopValue = (item) => {
  const publication = item?.price_rate?.billing_range_active?.publication;
  if (!publication) return null;
  const boeNumber = (publication.boe_number ?? '').toString().trim();
  if (boeNumber) return boeNumber;
  return publication.boe_date ? formatDate(publication.boe_date) : null;
};

const selectBopPriceRate = async (item) => {
  if (!item?.id || item.is_bop_reference || savingBopReference.value) return;
  savingBopReference.value = true;
  try {
    const updated = await $ContractApiService.setBopPriceRate(id.value, item.id);
    contract.value = updated;
    priceRates.value = updated.price_rates ?? priceRates.value;
    toast.success(t('contract_block.bop_tariff_updated'));
  } catch (error) {
    console.error(error);
    toast.error(t('contract_block.bop_tariff_update_error'));
  } finally {
    savingBopReference.value = false;
  }
};

const unrelatedForSupplyPoint = (supplyPointId) =>
  anomaliesPriceRates.value.filter((v) => v.supply_point.id == supplyPointId);

const missingForSupplyPoint = (supplyPointId) =>
  missingPriceRates.value.filter((v) => v.supply_point.id == supplyPointId);

const isUseTypeDifferentFromContract = computed(() => {
  const selectedId = selectedNewUseType.value?.id;
  if (selectedId == null || selectedId === '') return false;
  const currentId = selectedUseType.value?.id ?? contract.value?.use_type?.id;
  return selectedId != currentId;
});

const showUseTypeChangeNotSavedInfo = computed(() =>
  isUseTypeDifferentFromContract.value && !approveUseTypeChange.value
);

const isUseTypeChangeDocTypeRequired = computed(() => !!useTypeChangeDocument.value);

const getData = async function () {
  const response = await $ContractApiService.getDetail(id.value);
  contract.value = response
  allSupplyPoints.value = contract.value.supply_points
  selectedContractUseType.value = contract.value.use_type ? contract.value.use_type.id : "";
  selectedContractClientType.value = contract.value.client_type ? contract.value.client_type.id : "";
  selectedContractCategory.value = contract.value.category ? contract.value.category.id : "";
  priceRates.value = contract.value.price_rates ? contract.value.price_rates : [];
  singlePriceRate.value = contract.value.use_general_price_rates || false;
  usedSupplyPoints.value = contract.value.use_general_price_rates ? [contract.value.supply_point_default] : contract.value.supply_points;
  selectedContractType.value = contract.value?.contract_request_type ?? null;
  selectedUseType.value = contract.value?.use_type ?? null;
  selectedNewUseType.value = null;
  //priceRateSelectedItems.value = contract.value.price_rates ? contract.value.price_rates.map(v => v.id) : [];

  if (contract.value.company != null) {
    const c = contract.value.company;
    const cid = typeof c === 'object' && c !== null ? c.id : c;
    selectedCompanyId.value = cid != null ? String(cid) : '';
  } else {
    selectedCompanyId.value = '';
  }

  await loadTypeOptions();
  await loadDocTypes();
  selectedNewUseType.value = useTypeOptions.value.find((u) => u.id == selectedUseType.value?.id) ?? null;
  selectedContractType.value = contractTypeOptions.value.find((t) => t.id == selectedContractType.value?.id) ?? selectedContractType.value;
  await loadPriceRates();
  await loadContractCategories();
  await loadContractUseTypes();
  await loadContractClientTypes();
  if (useMultipleCompanies.value) {
    await loadCompanyOptionsData();
  }
  loading.value = false;
}

const loadDocTypes = async () => {
  loadingDocTypes.value = true;
  try {
    const data = await $ConfiglistApiService.getAll('contract/contract-documentation-type');
    docTypes.value = data.results || [];
  } catch (error) {
    console.error('Error fetching documentation types:', error);
  } finally {
    loadingDocTypes.value = false;
  }
}

const onDocumentUpdate = (file) => {
  useTypeChangeDocument.value = file || null;
}

const onDocumentDelete = () => {
  useTypeChangeDocument.value = null;
}

const handleSingularPriceRateChange = () => {
  usedSupplyPoints.value = singlePriceRate.value ? [contract.value.supply_point_default] : contract.value.supply_points;
  if (singlePriceRate.value) {
    priceRates.value = priceRates.value.filter(v => v.supply_point.id == contract.value.supply_point_default.id);
  }
}

const loadPriceRates = async () => {
  const dataResponse = await $PriceRateApiService.getAll('', [], 1, null, false, null, null, true, contract.value?.exploitation?.id);
  allPriceRates.value = dataResponse.results
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


const toggleRegion = (value) => {
  showRegion.value = value;
  if (value == false) {
    closeAllRegions();
    showRegionComponent.value = null;
  }
};
const loadBonifications = async () => {
  $BonificationApiService.getAll("", { 'contract': id.value })
    .then((response) => {
      bonifications.value = response.results;
    });
}
const loadVariables = async () => {
  $VariableApiService.getAll("", ['contract=' + id.value])
    .then((response) => {
      variables.value = response.results;
    });
}

const save = async () => {
  try {
    if (useMultipleCompanies.value && getResolvedCompanyId() == null) {
      toast.error(t('contract_block.company_required'));
      return;
    }
    if (approveUseTypeChange.value && useTypeChangeDocument.value && !selectedUseTypeChangeDocType.value) {
      toast.error(t('warning_block.doc_type_required_if_file'));
      return;
    }

    if (!confirm(t('confirmation_text_block.confirm_save'))) return;

    emitChange();
    router.push('/contract/contracts?id=' + id.value);
  }
  catch (error) {
    console.log(error)
  }
}

const openEditPriceRates = async (supplyPoint) => {
  priceRateSelectedItems.value = priceRates.value.filter(v => v.supply_point.id == supplyPoint.id).map(v => v.price_rate.id)
  supplyPointPriceRate.value = supplyPoint;
  await closeAllRegions();
  showRegion.value = true;
  showRegionComponent.value = 'EditPriceRates';
}

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

const closeAllRegions = () => {
  // Tanquem tots els components
  showRegionComponent.value = null;
  // Tanquem region
  showRegion.value = false;
};

onMounted(async () => {
  objectPermissions.value = await checkPermission($ContractApiService);
  if (!objectPermissions.value.can_change) {
    toast.error(t('common.no_permissions'));
    return navigateTo('/');
  }
  try {
    const multi = await $ConfigProjectApiService.get('use_multiple_companies');
    useMultipleCompanies.value = multi === true || multi === 'True' || multi === 'true';
  } catch {
    useMultipleCompanies.value = false;
  }
  origin_reading_token.value = await $ConfigProjectApiService.get('origin_reading_token');
  await getData()
});

const downloadCommunicationPdf = async () => {
  if (!isUseTypeDifferentFromContract.value) return;
  downloadingCommunicationPdf.value = true;
  try {
    const useTypeId = selectedNewUseType.value?.id;
    const contractTypeId = selectedContractType.value?.id;
    const response = await $ContractApiService.getCommunicationPdf(id.value, useTypeId, contractTypeId);
    if (response?.file_url) {
      await openAuthenticatedFileUrl(response.file_url);
    } else {
      toast.error(t('common.error_download'));
    }
  } catch (error) {
    console.error(error);
    toast.error(t('common.error_download'));
  } finally {
    downloadingCommunicationPdf.value = false;
  }
};

const emitChange = async () => {

  if (approveUseTypeChange.value && useTypeChangeDocument.value && isUseTypeDifferentFromContract.value && selectedUseTypeChangeDocType.value) {
    try {
      let document_save_data = {
        id: contract.value.id,
        file: useTypeChangeDocument.value,
        is_contract: false,
        contract_type: selectedUseTypeChangeDocType.value,
        text: null,
      }
      let response = await $ContractApiService.saveFile(document_save_data);
      if (response) {
        toast.success(t('common.document_saved'));
      } else {
        toast.error(t('common.error_saving'));
      }
    } catch (error) {
      console.error(error);
      toast.error(t('common.error_saving'));
    }
  }


  let data = {
    id: id.value,
    category_id: selectedContractCategory.value || null,
    use_type: selectedContractUseType.value || null,
    contract_use_type: selectedContractUseType.value || null,
    client_type: selectedContractClientType.value || null,
    contract_client_type: selectedContractClientType.value || null,
    price_rates_ids: priceRates.value || null,
    use_general_price_rates: singlePriceRate.value || false,
    use_type_id: selectedNewUseType.value?.id && isUseTypeDifferentFromContract.value ? selectedNewUseType.value?.id : null,
    contract_request_type_id: selectedContractType.value?.id && isUseTypeDifferentFromContract.value ? selectedContractType.value?.id : null,
  }

  // Si DIGITAL/BOTH, reenviar l'email perquè el backend no el buidi i forci PAPER
  const commType = contract.value?.communication_type;
  if (commType === 'DIGITAL' || commType === 'BOTH') {
    data.person_contact_email_id = contract.value?.person_contact_email?.id ?? null;
  }

  if (useMultipleCompanies.value) {
    const cid = getResolvedCompanyId();
    if (cid != null) {
      data.company_id = cid;
    }
  }

  const item_saved = await $ContractApiService.save(data)
}

watch(priceRateSelectedItems, async (newItems, oldItems) => {
  if (!loading.value && supplyPointPriceRate.value) {
    priceRates.value = supplyPointPriceRate.value ? priceRates.value.filter(v => v.supply_point.id != supplyPointPriceRate.value.id) : priceRates.value

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

watch([selectedContractCategory, priceRateSelectedItems, selectedContractClientType, selectedContractUseType, singlePriceRate], () => {
  //emitChange();
});

</script>

<template>
  <div v-if="objectPermissions?.can_change" id="wrapper" class="text-base p-4">
    <div class="grid grid-cols-3 gap-3">
      <div v-if="useMultipleCompanies" class="mb-4 col-span-3">
        <label for="contractPriceRatesCompany" class="flex text-sm font-medium text-gray-700 mb-3 gap-2">
          <Icon v-show="resolvedCompanyId != null" name="fa6-solid:circle-check" class="text-xl text-emerald-600" />
          <Icon v-show="resolvedCompanyId == null" name="fa6-solid:asterisk" class="text-lg text-slate-400" />
          <span>{{ $t('contract_block.water_provider_company') }}:</span>
        </label>
        <div class="max-w-md">
          <select id="contractPriceRatesCompany" v-model="selectedCompanyId" class="input h-9 w-full max-w-md"
            :disabled="loadingProviderCompanies">
            <option value="">{{ $t('common.select') }}…</option>
            <option v-for="c in providerCompanies" :key="c.id" :value="c.id">
              {{ c.name }}
            </option>
          </select>
          <div v-if="loadingProviderCompanies" class="mt-2 text-sm text-gray-500">
            {{ $t('common.loading') }}…
          </div>
        </div>
      </div>

      <!-- Selecció de CategoryUseType -->
      <div class="mb-4">
        <label for="contractUseType" class="flex text-sm font-medium text-gray-700 mb-3 gap-2">
          <Icon v-show="selectedContractUseType" name="fa6-solid:circle-check" class="text-xl text-emerald-600" />
          <Icon v-show="!selectedContractUseType" name="fa6-solid:asterisk" class="text-lg text-slate-400" />
          <span>{{ $t('common.usage_type') }}:</span>
        </label>

        <div>
          <div class="flex items-center">
            <select id="contractUseType" v-model="selectedContractUseType"
              class="w-full text-base border border-gray-300 rounded p-2" :disabled="isLoadingContractUseTypes">
              <option value="">{{ $t('common.no_usage_type') }}</option>
              <option v-for="item in optionsContractUseTypes" :key="item.id" :value="item.id">
                {{ item.name }}
              </option>
            </select>
          </div>

          <!-- Indicador de Carrega -->
          <div v-if="isLoadingContractUseTypes" class="mt-2 text-sm text-gray-500">
            {{ $t('common.loading') }} {{ $t('common.usage_type') }}...
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
              <option value="">{{ $t('contract_block.no_client_type') }}</option>
              <option v-for="item in optionsContractClientTypes" :key="item.id" :value="item.id">
                {{ item.name }}
              </option>
            </select>
          </div>

          <!-- Indicador de Carrega -->
          <div v-if="isLoadingContractClientType" class="mt-2 text-sm text-gray-500">
            {{ $t('common.loading') }} {{ $t('contract_block.client_type') }}...
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
              <option value="">{{ $t('contract_block.no_category') }}</option>
              <option v-for="category in optionsContractCategories" :key="category.id" :value="category.id">
                {{ category.name }}
              </option>
            </select>
          </div>

          <!-- Indicador de Carrega -->
          <div v-if="isLoadingContractCategories" class="mt-2 text-sm text-gray-500">
            {{ $t('common.loading') }} {{ $t('contract_block.categories') }}...
          </div>
        </div>
      </div>

      <div class="mb-4 flex items-center gap-2">
        <input type="checkbox" v-model="singlePriceRate" @change="handleSingularPriceRateChange" />
        <abbr :title="t('informative_block.single_price_rate_info')" class="flex items-center">
          <Icon name="fa6-solid:circle-info" class="text-slate-500" />
        </abbr>
        <span>{{ $t('informative_block.unique_price_rate_info') }}</span>
      </div>

      <div v-if="usedSupplyPoints && usedSupplyPoints?.length > 0" class="col-span-3">
        <div v-for="supply_point in usedSupplyPoints" :key="supply_point.id" class="mb-4">
          <label for="priceRate" class="flex text-sm font-medium text-gray-700 mb-3 gap-2">
            <Icon v-show="priceRates.length != 0" name="fa6-solid:circle-check" class="text-xl text-emerald-600" />
            <Icon v-show="priceRates.length == 0" name="fa6-solid:asterisk" class="text-lg text-pink-600" />
            <span>{{ $t('contract_block.consumption_pr_per_sp') }}
              {{ supply_point.token }} ({{priceRates.filter(v => v.supply_point.id == supply_point.id).length}})</span>
          </label>

          <div id="price_rate_templates" class="mb-3">
            <div class="pl-3 pr-3">
              <div class="mb-2 grid grid-cols-2 gap-3">
                <div v-for="item in priceRates.filter(v => v.supply_point.id == supply_point.id)" class="mb-1">
                  <Icon name="fa6-solid:cube" class="text-slate-500" /> &nbsp;<span class="font-semibold">{{
                    item.price_rate.product?.name || $t('pricing_block.no_product') }}</span> - {{ item.price_rate.name
                    }}
                </div>
              </div>
              <button name="" class="button-default-xs" @click="openEditPriceRates(supply_point)">
                <Icon name="fa-solid:plus" class="text-slate-500 mr-1" />
                {{ $t('common.modify') }} {{ t('price_rate') }}
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
                    {{ missing.price_rate?.product?.name ? `${missing.price_rate?.product?.name} - ` : '' }} {{
                      missing.price_rate.name }}
                  </div>
                </template>
              </div>
            </div>
          </div>



        </div>
      </div>

      <!-- BOP TARIFF -->
      <div v-if="!loading" class="col-span-3 border-t border-slate-200 pt-4 mt-2">
        <p class="text-sm font-medium text-gray-700 mb-2">
          {{ $t('contract_block.bop_tariff') }}
        </p>
        <p class="text-sm text-slate-600 mb-3">
          {{ $t('contract_block.bop_tariff_current') }}:
          <span class="font-semibold text-slate-900">
            {{ contract?.tarifa_bop || $t('contract_block.bop_tariff_no_date') }}
          </span>
        </p>

        <div v-if="bopCandidates.length > 0" class="space-y-2">
          <div v-for="item in bopCandidates" :key="`bop-${item.id}`"
            class="flex items-center justify-between gap-3 rounded border border-slate-200 px-3 py-2">
            <div class="min-w-0">
              <span class="font-semibold">{{ item.price_rate?.product?.name || $t('pricing_block.no_product') }}</span>
              - {{ item.price_rate?.name }}
              <span class="text-slate-500"> ({{ item.supply_point?.token }})</span>
              <div class="text-xs text-slate-500">
                {{ $t('contract_block.bop_tariff') }}: {{ getBopValue(item) || $t('contract_block.bop_tariff_no_date') }}
              </div>
            </div>
            <div class="shrink-0">
              <span v-if="item.is_bop_reference"
                class="inline-flex items-center gap-1 px-2 py-1 rounded-md text-xs font-medium bg-emerald-50 text-emerald-700 border border-emerald-300">
                <Icon name="fa6-solid:circle-check" />
                {{ $t('contract_block.bop_tariff_reference') }}
              </span>
              <button v-else type="button" class="button-default-xs" :disabled="savingBopReference"
                @click="selectBopPriceRate(item)">
                {{ $t('contract_block.bop_tariff_set_reference') }}
              </button>
            </div>
          </div>
        </div>
      </div>

      <!-- USE TYPE MODIFICATION -->

      <div v-if="!loading" class="col-span-3 border-t border-slate-200 pt-4 mt-2">
        <div class="rounded-xl bg-white overflow-visible">
          <div class="grid grid-cols-3 gap-3">
            <div class="col-span-2 flex items-start justify-between gap-6 px-3 py-2 bg-green-100/75 rounded">
              <div class="min-w-0">
                <!--  text-sm font-medium text-gray-700 mb-3 gap-2 -->
                <p class="text-sm font-medium text-gray-700 mb-2">
                  {{ $t('contract_block.current_use_type') }}
                </p>
                <p v-if="selectedUseType" class="text-lg font-semibold text-slate-900 tracking-tight leading-snug">
                  {{ selectedUseType.name }}
                </p>
                <p v-if="contract?.contract_request_type" class="mt-1.5 text-sm text-slate-500">
                  {{ $t('contract_block.current_contract_type') }}:
                  <span class="text-slate-800 font-medium">{{ contract.contract_request_type.name }}</span>
                </p>
              </div>
  
              <div class="flex items-center gap-3 shrink-0 pt-0.5 ">
                <label for="approveUseTypeChange" class="text-sm text-slate-600 cursor-pointer select-none">
                  {{ $t('contract_block.change_use_type') }}
                </label>
                <button id="approveUseTypeChange" type="button" @click="approveUseTypeChange = !approveUseTypeChange"
                  class="relative inline-flex h-5 w-9 items-center rounded-full transition-colors duration-200 focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-500/40 focus-visible:ring-offset-2"
                  :class="approveUseTypeChange ? 'bg-slate-800' : 'bg-slate-300'" role="switch"
                  :aria-checked="approveUseTypeChange">
                  <span class="inline-block h-3.5 w-3.5 transform rounded-full bg-white transition-transform duration-200"
                    :class="approveUseTypeChange ? 'translate-x-[18px]' : 'translate-x-0.5'" />
                </button>
              </div>
            </div>
          </div>

          <div v-if="showUseTypeChangeNotSavedInfo"
            class="grid grid-cols-[auto,1fr] items-start gap-2 bg-sky-50 border-l-4 border-sky-400 text-sky-800 px-4 py-2 rounded mt-2"
            role="status">
            <Icon name="fa6-solid:circle-info" class="text-sky-500 w-5 h-5 mt-0.5" />
            <p class="text-sm">
              {{ $t('informative_block.use_type_change_not_saved_unless_allowed') }}
            </p>
          </div>

          <Transition enter-active-class="transition duration-200 ease-out" enter-from-class="opacity-0"
            enter-to-class="opacity-100" leave-active-class="transition duration-150 ease-in"
            leave-from-class="opacity-100" leave-to-class="opacity-0">
            <div v-if="approveUseTypeChange"
              class="rounded py-4 px-2 space-y-4 overflow-visible">
              <div class="relative z-20 flex items-end gap-3 grid grid-cols-3 gap-x-2">
                <div class="flex-1 min-w-0">
                  <label for="newUseType" class="block text-sm font-medium text-gray-700">
                    {{ $t('common.usage_type') }}
                  </label>
                  <v-select id="newUseType" class="custom-select" v-model="selectedNewUseType" :options="useTypeOptions"
                    label="name" :placeholder="$t('common.no_usage_type')" :disabled="isLoadingUseType"
                    :clearable="false" append-to-body />
                </div>
                <div class="flex-1 min-w-0">
                  <label for="newContractType" class="block text-sm font-medium text-gray-700 mb-1.5">
                    {{ $t('contract_block.contracting_type') }}
                  </label>
                  <v-select id="newContractType" class="custom-select" v-model="selectedContractType"
                    :options="contractTypeOptions" label="name" :placeholder="$t('common.select')"
                    :disabled="isLoadingContractRequestType" :clearable="false" append-to-body />
                </div>
                <div>
                  <button type="button"
                    class="button-default whitespace-nowrap shrink-0 disabled:text-slate-300 disabled:border-slate-300 disabled:cursor-not-allowed disabled:bg-slate-50"
                    :disabled="!isUseTypeDifferentFromContract || downloadingCommunicationPdf"
                    @click="downloadCommunicationPdf">
                    <Icon :name="downloadingCommunicationPdf ? 'fa6-solid:spinner' : 'fa6-solid:file-pdf'" class="mr-1"
                      :class="{ 'animate-spin': downloadingCommunicationPdf }" />
                    {{ $t('contract_block.download_communication_pdf') }}
                  </button>
                </div>
              </div>
              <div class="py-2 border-t border-slate-200">
                <p class="text-sm font-medium text-gray-700 mb-3">
                  {{ $t('contract_block.use_type_change_document') }} ({{ $t('common.optional') }})
                </p>
                <div class="flex flex-row  gap-3 items-stretch items-start">
                  <div class="flex-1 min-w-0">
                    <label for="useTypeChangeDocType" class="block text-xs font-medium text-slate-600 mb-1.5">
                      {{ $t('common.doc_type') }}
                      <span v-if="isUseTypeChangeDocTypeRequired" class="text-red-500">*</span>
                    </label>
                    <select v-model="selectedUseTypeChangeDocType" id="useTypeChangeDocType"
                      class="w-full px-3 py-2.5 text-sm border rounded-lg bg-white shadow-sm transition-all"
                      :class="isUseTypeChangeDocTypeRequired && !selectedUseTypeChangeDocType ? 'border-red-400' : 'border-slate-300'"
                      :disabled="loadingDocTypes">
                      <option value="">{{ $t('common.select') }}...</option>
                      <option v-for="docType in docTypes" :value="docType.id" :key="docType.id">
                        {{ docType.list_name || docType.name }}
                      </option>
                    </select>
                    <p v-if="isUseTypeChangeDocTypeRequired && !selectedUseTypeChangeDocType"
                      class="mt-1 text-xs text-red-600">
                      {{ $t('warning_block.doc_type_required_if_file') }}
                    </p>
                  </div>
                  <div class="flex-1 min-w-0 items-start">
                    <label class="block text-xs font-medium text-slate-600 mb-1.5">
                      {{ $t('common.file') }}
                    </label>
                    <AtomsInputFile :name="'useTypeChangeDocFile'" :uploaded="useTypeChangeDocument" :fullWidth="true"
                      @update="onDocumentUpdate" @delete="onDocumentDelete" />
                  </div>
                </div>
              </div>
            </div>
          </Transition>
        </div>
      </div>

    </div>
    <div class="flex flex-row-reverse mt-4 h-fit">
      <button @click="save" class="button-primary">
        <Icon name="fa6-solid:floppy-disk" />&nbsp; {{ $t('common.save') }}
      </button>
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
        <AddBonification v-if="showRegionComponent == 'AddBonification'" :contract="contract"
          @new-item="onBonificationSaved" />
        <AddVariable v-if="showRegionComponent == 'AddVariable'" :contract="contract" @new-item="onVariableSaved" />
        <PriceRateSelectMultiple v-if="showRegionComponent === 'EditPriceRates'" v-model="priceRateSelectedItems"
          :filter="[origin_reading_token]" :exploitation_id="contract?.exploitation?.id" />
      </div>
    </div>
  </div>
</template>