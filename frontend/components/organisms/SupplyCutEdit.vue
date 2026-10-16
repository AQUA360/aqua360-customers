<script setup>
import { toRaw, ref, computed, onMounted, watch, watchEffect } from 'vue';
import { useI18n } from 'vue-i18n';
import { useToast } from 'vue-toastification';
import H1 from '~/components/atoms/H1.vue';
import _ from 'lodash';
import AddSupplyPoints from '~/components/molecules/AddSupplyPoints.vue';
import AddContracts from '../molecules/AddContracts.vue';
import SupplyPointDetail from '../molecules/SupplyPointDetail.vue';
import ContractDetail from '../molecules/ContractDetail.vue';
import SupplyPointRegion from '../organisms/SupplyPointRegion.vue';
import ContractRegion from '../organisms/ContractRegion.vue';
import SupplyCutContractListRegion from '../organisms/SupplyCutContractListRegion.vue';
import SupplyCutSupplyListRegion from '../organisms/SupplyCutSupplyListRegion.vue';
import { checkPermission } from '~/middleware/permission';
import AppLoading from '~/components/atoms/AppLoading.vue';
const props = defineProps({
  contract: {
    type: Object,
    required: false,
  },
  supply_point: {
    type: Object,
    required: false,
  },
});

const { t } = useI18n();
const toast = useToast();
const route = useRoute();
const router = useRouter();
const { $SupplyCutApiService, $StreetApiService, $SupplyPointApiService, $ContractApiService } = useNuxtApp();
const objectPermissions = ref(null);
// Reactive state
const attemptedSave = ref(false);
const loading = ref(true);
const fetchingData = ref(false);
const saving = ref(false);

const selectedOriginType = ref(route.query.action ? route.query.action : 'ST'); // 'ST', 'SP', 'CONTRACT'
const selectedSupplyPoints = ref([]);
const supply_point_ids = ref([]);
const contract_ids = ref([]);
const selectedContract = ref([]);
const selectedStreets = ref([]);
const selectedNumbers = ref([]);
const selectedCause = ref(null);

const streets = ref([]);
const streetNumbers = ref([]);
const causes = ref([]);

const showRegion = ref(false);
const isSubRegionOpen = ref(false);

const affectedContracts = ref([]);
const affectedSupplyPoints = ref([]);
const date_start = ref(null);
const date_end = ref(null);

const getCauses = async () => {
  try {
    const result = await $SupplyCutApiService.getCauses();
    causes.value = result
      .filter((item) => item.token !== 'Accidental' && item.token !== 'Planificada')
      .map((item) => ({
        label: item.name,
        code: item.id,
      }));
  } catch (error) {
    console.error('Error fetching causes:', error);
  }
};

const STREET_PAGE_LIMIT = 20; // 20 x 50 (PAGE_SIZE) = 1000 streets

// Carrega totes les pàgines d'un endpoint paginat sense aigua seqüencial: es llegeix la
// pàgina 1, es calcula quantes pàgines calen amb el count i la resta es llança en
// paral·lel amb Promise.all. Si es perden pàgines, es completa al final de manera
// seqüencial fins al límit.
const fetchAllPages = async (fetchPage, maxPages = STREET_PAGE_LIMIT) => {
  const first = await fetchPage(1);
  const firstBatch = first?.results || [];
  const count = first?.count ?? firstBatch.length;
  const pageSize = firstBatch.length;
  const pagesNeeded = pageSize > 0 ? Math.min(Math.ceil(count / pageSize), maxPages) : 1;

  const rest = await Promise.all(
    Array.from({ length: Math.max(pagesNeeded - 1, 0) }, (_, index) => fetchPage(index + 2))
  );
  const results = firstBatch.concat(...rest.map((page) => page?.results || []));

  for (let page = pagesNeeded + 1; page <= maxPages && results.length < count; page++) {
    const batch = (await fetchPage(page))?.results || [];
    if (batch.length === 0) break;
    results.push(...batch);
  }
  return results;
};

const getStreets = async () => {
  try {
    const results = await fetchAllPages((page) => $StreetApiService.getAll('', [], page));
    streets.value = results.map((item) => ({
      label: item.name,
      code: item.id,
    }));
  } catch (error) {
    console.error('Error fetching streets:', error);
  }
};

const getStreetNumber = async () => {
  try {
    streetNumbers.value = [];
    const selected = selectedStreets.value || [];
    // Un request per carrer, tots en paral·lel.
    const perStreet = await Promise.all(
      selected.map(async (street) => {
        const numbers = await fetchAllPages((page) => $StreetApiService.getStreetNumber(street.code, page));
        return numbers.map((element) => ({
          // Amb més d'un carrer, el número sol no prou: es prefixa el nom del carrer.
          label: (selected.length > 1 ? street.label + ' - ' : '') + getNumber(element),
          code: element.id,
        }));
      })
    );
    streetNumbers.value = perStreet.flat();
  } catch (error) {
    console.error('Error fetching street number:', error);
  }
};

const getNumber = (element) => {
  let result = ""
  if (element.number) {
    result += element.number;
    if (element.number_suffix) {
      result += " " + element.number_suffix;
    }
    if (element.number_end) {
      result += " - " + element.number_end;
      if (element.number_end_suffix) {
        result += "  " + element.number_end_suffix;
      }
    }
    else if (element.number_end_suffix) {
      result += " -  " + element.number_end_suffix;
    }
  } else {
    result += t("address_block.no_number");
  }
  return result;
};

const getAffectedSupplyPoints = async () => {
  fetchingData.value = true;

  try {
    if (
      selectedStreets.value.length === 0 &&
      (supply_point_ids.value?.length ?? 0) == 0 &&
      (contract_ids.value?.length ?? 0) == 0) {
      return;
    }
    let number_ids = [];
    if (selectedNumbers?.value?.length > 0) {
      number_ids = selectedNumbers.value.map((number) => number.code);
    }
    let search_data = {
      selected_streets: selectedStreets.value.length > 0
        ? selectedStreets.value.map((street) => street.code)
        : null,
      selected_numbers: number_ids.length > 0 ? number_ids : null,
      supply_point_ids: supply_point_ids.value.length > 0 ? supply_point_ids.value : null,
      contract_ids: contract_ids.value.length > 0 ? contract_ids.value : null,
    }
    const result = await $SupplyPointApiService.getByStreet(
      search_data
    );
    affectedSupplyPoints.value = result.supply_points
    affectedContracts.value = result.contracts
    supply_point_ids.value = affectedSupplyPoints.value.map(sp => sp.id)
    contract_ids.value = affectedContracts.value.map(c => c.id)
    
  } catch (error) {
    console.error('Error fetching supply points:', error);
  } finally {
    fetchingData.value = false;
  }
};


const save = async () => {
  attemptedSave.value = true;
  if (!isValid()) {
    toast.error(t("warning_block.warning_valid_dates"));
    return;
  }

  saving.value = true;
  if (confirm(t('confirmation_text_block.confirm_supply_cut') + date_start.value + "/" + (date_end.value ? date_end.value : "-"))) {
    try {
      await $SupplyCutApiService.save({
        token: _.random(10000, 99999) + '-' + date_start.value.replaceAll('-', ''),
        supply_points: supply_point_ids.value,
        contract_ids: contract_ids.value,
        date_start: date_start.value,
        date_end: date_end.value ? date_end.value : null,
        cause_id: selectedCause.value.code,
      });
      navigateTo('/service/supply-cut/');
    } catch (error) {
      console.error('Error saving supply cuts:', error);
    } finally {
      saving.value = false;
    }
  }
};

const isValid = () => {
  if (date_start.value == null) return false
  if (selectedCause.value == null) return false
  return true;
};


const onSupplyPointSelected = async (item) => {
  const index = selectedSupplyPoints.value.findIndex((sp) => sp.id === item.id);
  if (index > -1) {
    selectedSupplyPoints.value.splice(index, 1);
  } else {
    selectedSupplyPoints.value.push(item);
  }
  affectedSupplyPoints.value = [...selectedSupplyPoints.value];
  supply_point_ids.value = affectedSupplyPoints.value.map(sp => sp.id);
  contract_ids.value = affectedSupplyPoints.value.map(sp => sp.contracts.map(c => c.id)).flat();
  await getAffectedSupplyPoints()
};

const onContractSelected = async (item) => {
  selectedContract.value = [item];
  supply_point_ids.value = item.supply_point_ids || []
  contract_ids.value = [item.id]
  await getAffectedSupplyPoints()
  closeAllRegions();
};

const updateSelect = (ev, entity) => {
  if (entity === 'street') {
    selectedStreets.value = ev || [];
    // Els números són de l'antic carrer: es netegen per no filtrar amb ids que no
    // pertanyen a cap dels carrers seleccionats.
    selectedNumbers.value = [];
    getStreetNumber()
  }
  else if (entity === 'number') {
    selectedNumbers.value = ev;
    supply_point_ids.value = []
    contract_ids.value = []
    getAffectedSupplyPoints();
  }
  else if (entity === 'cause') {
    selectedCause.value = ev;
  }
};

const excludeContract = (contr) => {
  contract_ids.value = contract_ids.value.filter(id => id !== contr.id);
  supply_point_ids.value = supply_point_ids.value.filter(id => !contr.supply_point_ids.includes(id));
  if (selectedSupplyPoints.value.length > 0) {
    selectedSupplyPoints.value = supply_point_ids.value.map(id => ({id: id}))
  }
  getAffectedSupplyPoints();
}

const excludeSupplyPoint = (supply_point) => {
  supply_point_ids.value = supply_point_ids.value.filter(id => id !== supply_point.id);
  contract_ids.value = contract_ids.value.filter(id => !supply_point.contracts.map(c => c.id).includes(id));
  if (selectedContract.value.length > 0) {
    selectedContract.value = contract_ids.value.map(id => ({id: id}))
  }
  getAffectedSupplyPoints();
}

const toggleRegion = (force) => {
  showRegion.value = force !== undefined ? force : !showRegion.value;
  if (!showRegion.value) {
    isSubRegionOpen.value = false;
  }
};

const handleSubRegionEvent = (event) => {
  isSubRegionOpen.value = event;
};


const showRegionDetailComponent = ref(null);
const showRegionDetailId = ref(null);
const showDetail = (component, id) => {
  closeAllRegions()
  showRegionDetailComponent.value = component;
  showRegionDetailId.value = id;
  showRegion.value = true;
}

const closeAllRegions = () => {
  showRegionDetailComponent.value = null;
  showRegionDetailId.value = null;
  showRegion.value = false;
};

onMounted(async () => {
  objectPermissions.value = await checkPermission($SupplyCutApiService);
  if (!objectPermissions.value.can_change) {
    toast.error(t('common.no_permissions'));
    return navigateTo('/');
  }
  getStreets();
  getCauses();
  if (route.query?.action == 'CONTRACT') {
    getContractFromRoute()
  } else if (route.query?.action == 'SP') {
    getSupplyPointFromRoute()
  }
  loading.value = false;
});

const getContractFromRoute = async () => {
  let contractId = route.query.contract
  selectedContract.value = [{ id: parseInt(contractId) }]
  contract_ids.value = [parseInt(contractId)]
  try {
    const result = await $ContractApiService.getDetail(contractId)
    affectedSupplyPoints.value = result.supply_points
    supply_point_ids.value = result.supply_point_ids
  } catch (error) {
    console.error('Error fetching contract:', error);
  }
}

const getSupplyPointFromRoute = async () => {
  let supplyPointId = route.query.supply_point
  selectedSupplyPoints.value = [{ id: parseInt(supplyPointId) }]
  supply_point_ids.value = [parseInt(supplyPointId)]
  try {
    const result = await $SupplyPointApiService.getDetail(supplyPointId)
    affectedContracts.value = result.contracts
    contract_ids.value = result.contracts.map(c => c.id)
  } catch (error) {
    console.error('Error fetching supply point:', error);
  }
}


watch(selectedStreets, () => {
  getAffectedSupplyPoints();
}, { immediate: true, deep: true });

watch(selectedOriginType, () => {
  selectedContract.value = [];
  selectedSupplyPoints.value = [];
  selectedStreets.value = [];
  selectedNumbers.value = [];
  affectedSupplyPoints.value = [];
  affectedContracts.value = [];
  supply_point_ids.value = [];
  contract_ids.value = [];
  resetBulkState();
})


const dateIntervalError = (event) => {
  toast.error(event)
  date_end.value = null
}

// ---------------------------------------------------------------------------
// Bulk planning: paste/upload a flat list of identifiers (strict single type
// taken from the radio above) and create ONE supply cut over every resolved
// supply point. Lives inside this screen; the pickers above stay available.
// ---------------------------------------------------------------------------
const stage = ref('input'); // 'input' | 'preview'
const identifiersText = ref('');
const bulkFileInput = ref(null);
const bulkFileName = ref('');
const preview = ref(null);
const previewing = ref(false);
const bulkSaving = ref(false);
const overrideConflicts = ref(false);

const MAX_IDENTIFIERS = 5000;

const bulkIdentifierType = computed(() => {
  if (selectedOriginType.value === 'CONTRACT') return 'contract_token';
  if (selectedOriginType.value === 'SP') return 'supply_point_id';
  return 'street_id';
});

const parsedIdentifiers = computed(() => {
  const parts = identifiersText.value.split(/[\n\r,;]+/);
  const seen = new Set();
  const result = [];
  for (const part of parts) {
    const value = part.trim();
    if (!value || seen.has(value)) continue;
    seen.add(value);
    result.push(value);
  }
  return result;
});

const parsedCount = computed(() => parsedIdentifiers.value.length);
const overCap = computed(() => parsedCount.value > MAX_IDENTIFIERS);
const hasBulkInput = computed(() => parsedCount.value > 0);

const isValidBulk = computed(() => {
  if (parsedCount.value === 0) return false;
  if (overCap.value) return false;
  if (!selectedCause.value) return false;
  if (!date_start.value) return false;
  return true;
});

const canCreateBulk = computed(() => {
  if (!preview.value) return false;
  if ((preview.value.stats?.resolved ?? 0) === 0) return false;
  if ((preview.value.stats?.conflicts ?? 0) > 0 && !overrideConflicts.value) return false;
  return true;
});

const handleBulkFileChange = (event) => {
  const file = event.target.files?.[0] ?? null;
  if (!file) return;
  bulkFileName.value = file.name;
  const reader = new FileReader();
  reader.onload = () => {
    identifiersText.value = String(reader.result ?? '');
  };
  reader.readAsText(file);
};

const clearBulkFile = () => {
  bulkFileName.value = '';
  if (bulkFileInput.value) bulkFileInput.value.value = '';
};

const resetBulkState = () => {
  stage.value = 'input';
  identifiersText.value = '';
  clearBulkFile();
  preview.value = null;
  overrideConflicts.value = false;
};

const handlePreview = async () => {
  // Reuse the form's existing validation styling (attemptedSave drives the
  // red `invalid` class on Start Date and Cause): the button is clickable as
  // soon as the textarea has content, but the preview never runs until every
  // mandatory top field is filled.
  attemptedSave.value = true;
  if (!isValidBulk.value || previewing.value) return;
  previewing.value = true;
  try {
    preview.value = await $SupplyCutApiService.bulkPlanPreview({
      identifier_type: bulkIdentifierType.value,
      identifiers: parsedIdentifiers.value,
    });
    overrideConflicts.value = false;
    stage.value = 'preview';
  } catch (error) {
    console.error('Error previewing bulk plan:', error);
    toast.error(error?.data?.error || error?.message || t('common.error_save'));
  } finally {
    previewing.value = false;
  }
};

const handleBulkBack = () => {
  stage.value = 'input';
  preview.value = null;
  overrideConflicts.value = false;
};

const handleBulkCreate = async () => {
  if (!canCreateBulk.value || bulkSaving.value) return;
  bulkSaving.value = true;
  try {
    const result = await $SupplyCutApiService.bulkPlanCreate({
      identifier_type: bulkIdentifierType.value,
      identifiers: parsedIdentifiers.value,
      cause_id: selectedCause.value.code,
      date_start: date_start.value,
      date_end: date_end.value ? date_end.value : null,
      override_conflicts: overrideConflicts.value,
    });
    toast.success(t('service_block.bulk_plan_created', { count: result.resolved_count }));
    navigateTo('/service/supply-cut/');
  } catch (error) {
    console.error('Error creating bulk plan:', error);
    toast.error(error?.data?.error || error?.message || t('common.error_save'));
  } finally {
    bulkSaving.value = false;
  }
};

// Secondary fallback link inside the bulk dropzone: opens the same picker the
// legacy dropzone opened, so deep-linked/selected flows keep working.
const showDetailForCurrentType = () => {
  if (bulkIdentifierType.value === 'contract_token') showDetail('ContractForm', null);
  else if (bulkIdentifierType.value === 'supply_point_id') showDetail('SupplyPointForm', null);
  else showDetail('SupplyPointForm', null);
};
</script>

<template>
  <div v-if="objectPermissions?.can_change" id="wrapper" class="text-base p-4 max-w-full">
    <div v-if="loading">
      <AppLoading :text="$t('common.loading')" />
    </div>
    <div v-else-if="stage === 'input'" class="border border-gray-300 rounded p-4 bg-white">
      <div class="bg-white border border-slate-200 rounded rounded-lg p-4 space-y-4 w-[50%] mt-2 mb-5">
        <div>
          <span class="text-gray-600 font-medium">{{ $t('service_block.supply_cut_date_long') }}</span>
          <div class="grid grid-cols-2 gap-4 mt-2">
            <AtomsInputDateTime v-model="date_start" class="w-full" required :invalid="attemptedSave && !date_start"
              :label="$t('service_block.cut_date_expected_start')" :placeholder="$t('common.start')" />
            <div>
              <AtomsInputDateTime v-model="date_end" class="w-full" :label="$t('service_block.cut_date_expected_end')"
                :placeholder="$t('common.end')" :startDate="date_start" @date-interval-error="dateIntervalError" />
              <span class="text-slate-400 text-sm">{{ $t('service_block.supply_cut_open_hint') }}</span>
            </div>
          </div>
        </div>

        <!-- Cause Selection -->
        <div>
          <span class="text-gray-600 font-medium">{{ $t('order_block.reason') }}</span>
          <v-select class="w-full mt-2" :model-value="selectedCause" :disabled="loading"
            :class="{ 'invalid': attemptedSave && !selectedCause }" @update:modelValue="updateSelect($event, 'cause')"
            :options="causes" />
        </div>
      </div>

      <div class="">

        <div class="mb-4">
          <span>
            {{ }}
          </span>
          <div class="flex gap-4 py-2">
            <label class="flex items-center">
              <input type="radio" value="CONTRACT" v-model="selectedOriginType" class="mr-2">
              {{ $t('contract') }}
            </label>
            <label class="flex items-center">
              <input type="radio" value="SP" v-model="selectedOriginType" class="mr-2">
              {{ $t('supply_point') }}
            </label>
            <label class="flex items-center">
              <input type="radio" value="ST" v-model="selectedOriginType" class="mr-2">
              {{ $t('address_block.street') }}
            </label>
          </div>
        </div>

        <!-- Bulk input: the upgraded dropzone. Paste/upload a flat list of ids
             for the type selected above; the pickers below stay available. -->
        <div class="border-2 border-dashed rounded p-4 mb-4 bg-gray-50">
          <div class="flex items-center justify-between mb-2">
            <span class="text-gray-600 font-medium">{{ $t('service_block.bulk_plan_identifiers_label') }}</span>
            <span class="text-sm" :class="overCap ? 'text-red-600 font-semibold' : 'text-slate-500'">
              {{ $t('service_block.bulk_plan_count', { count: parsedCount, max: MAX_IDENTIFIERS }) }}
            </span>
          </div>
          <p class="text-slate-400 text-sm mb-2">{{ $t('service_block.bulk_plan_identifiers_hint') }}</p>
          <textarea v-model="identifiersText" rows="6"
            class="w-full p-2 border border-gray-300 rounded-md font-mono text-sm bg-white focus:outline-none"
            :placeholder="$t('service_block.bulk_plan_identifiers_placeholder')" />

          <div class="flex items-center gap-3 mt-2 flex-wrap">
            <input ref="bulkFileInput" type="file" accept=".csv,.txt" class="hidden" @change="handleBulkFileChange" />
            <button type="button" class="button-secondary" @click="bulkFileInput?.click()">
              <Icon name="fa6-solid:upload" /> &nbsp; {{ $t('service_block.bulk_plan_upload_file') }}
            </button>
            <!-- Legacy manual selection: a first-class alternative, not an afterthought.
                 Street mode keeps its street v-select below, so no button is needed there. -->
            <button v-if="bulkIdentifierType !== 'street_id'" type="button" class="button-default"
              @click="showDetailForCurrentType()">
              <Icon name="fa6-solid:list" /> &nbsp; {{ $t('service_block.bulk_plan_or_select') }}
            </button>
            <span v-if="bulkFileName" class="text-sm text-slate-600 flex items-center gap-2">
              {{ bulkFileName }}
              <button type="button" class="text-slate-400 hover:text-slate-600" @click="clearBulkFile">
                <Icon name="fa6-solid:xmark" />
              </button>
            </span>
          </div>
          <p class="text-slate-400 text-sm mt-1">{{ $t('service_block.bulk_plan_file_hint') }}</p>
        </div>


        <!-- BY CONTRACT -->
        <div v-if="selectedOriginType == 'CONTRACT'">


          <div v-if="selectedContract.length > 0">

            <div class="mx-4 mt-10 mb-5 w-[400px]">
              <div v-if="!fetchingData">
                <div v-if="supply_point_ids.length > 0"
                  class="bg-white shadow-md rounded-lg p-4 border border-gray-200">
                  <div class="flex items-center justify-between">
                    <p class="text-gray-600 text-sm font-medium">
                      {{ t('service_block.affected_sp') }}
                      <span class="font-semibold text-gray-800">{{ supply_point_ids.length }}</span>
                    </p>
                    <button @click="showDetail('affectedSupplyPoints', null)"
                      class="flex items-center justify-center w-8 h-8 hover:bg-blue-100 border border-gray-300 rounded-md transition duration-200">
                      <Icon name="fa6-solid:eye" class="text-gray-600 hover:text-blue-700 text-lg" />
                    </button>
                  </div>
                </div>

                <div v-else class="bg-white shadow-md rounded-lg p-4 border border-gray-200">
                  <p class="text-gray-500 text-center text-sm">
                    {{ $t('common.no_data_found') }}
                  </p>
                </div>
              </div>
              <div v-else class="bg-white shadow-md rounded-lg p-4 border border-gray-200">
                <p class="text-gray-500 text-center text-sm flex items-center mx-10">
                  <Icon name="fa6-solid:spinner" class="animate-spin text-lg text-slate-500 mx-2" />
                  {{ $t('common.loading') }}...
                </p>
              </div>
            </div>

            <div class="relative group p-4 rounded w-[70%]">
              <div v-for="item in selectedContract" :key="item.id" class="bg-green-50 p-2 my-2 rounded">
                <ContractDetail :id="item.id" :isSubRegion="false" :reducedDetail="true" @show-subregion="showDetail" />
              </div>
              <button @click="showDetail('ContractForm', null)"
                class="absolute cursor-pointer shadow-md border text-sm w-8 h-8 bg-white right-3 top-3 rounded-md text-slate-600 opacity-0 transition-all duration-300 group-hover:opacity-100">
                <Icon name="fa6-solid:pencil" />
              </button>
            </div>
          </div>
          <!-- Empty state: the unified bulk dropzone above owns the input;
               the picker is reachable only via its secondary blue link. -->
        </div>


        <!-- BY SUPPLY POINT -->
        <div v-else-if="selectedOriginType == 'SP'">
          <div v-if="selectedSupplyPoints.length > 0">
            <div class="mx-4 mt-10 mb-5 w-[400px]">
              <div v-if="!fetchingData">
                <div v-if="contract_ids.length > 0"
                  class="bg-white shadow-md my-2 rounded-lg p-4 border border-gray-200">
                  <div class="flex items-center justify-between">
                    <p class="text-gray-600 text-sm font-medium">
                      {{ t('contract_block.affected_contracts') }}:
                      <span class="font-semibold text-gray-800">{{ contract_ids.length }}</span>
                    </p>
                    <button @click="showDetail('affectedContracts', null)"
                      class="flex items-center justify-center w-8 h-8 hover:bg-blue-100 border border-gray-300 rounded-md transition duration-200">
                      <Icon name="fa6-solid:eye" class="text-gray-600 hover:text-blue-700 text-lg" />
                    </button>
                  </div>
                </div>

                <div v-else class="bg-white my-2 shadow-md rounded-lg p-4 border border-gray-200">
                  <p class="text-gray-500 text-center text-sm">
                    {{ $t('common.no_data_found') }}
                  </p>
                </div>
              </div>
            </div>

            <div class="relative group">
              <details open class=" border border-gray-300 rounded p-4 bg-white w-full">
                <summary>
                  {{ t("common.show") }} {{ t('service_block.selected_supply_points') }}
                </summary>
                <div v-if="selectedSupplyPoints.length > 1" class="grid grid-cols-1 md:grid-cols-2 gap-4 my-2">
                  <div v-for="item in selectedSupplyPoints" :key="item.id" class="bg-green-50 p-3 rounded-md">
                    <SupplyPointDetail :id="item.id" :isSubRegion="false" :reduced="true" @show-detail="showDetail" />
                  </div>
                </div>
                <div v-else v-for="item in selectedSupplyPoints" :key="item.id" class="bg-green-50 p-3 rounded-md my-2">
                  <SupplyPointDetail :id="item.id" :isSubRegion="false" :reduced="true" @show-detail="showDetail" />
                </div>
              </details>

              <button @click="showDetail('SupplyPointForm', null)"
                class="absolute top-2 right-2 p-2 bg-white rounded-full shadow-md hover:bg-gray-100 transition-colors duration-200 opacity-0 group-hover:opacity-100">
                <Icon name="fa6-solid:pencil" class="text-gray-600" />
              </button>
            </div>
          </div>
        </div>


        <!-- BY STREET -->
        <div v-else-if="selectedOriginType == 'ST'">
          <div class="field mb-4">
            <v-select multiple class="block w-full mr-1 required" :model-value="selectedStreets" :disabled="loading"
              @update:modelValue="updateSelect($event, 'street')" :options="streets" />
          </div>
          <div v-if="selectedStreets.length > 0" class="my-2 w-[200px]">
            <div class="mb-10">
              <span>
                {{ t('common.number') }}
                <span class="text-slate-400 text-sm">
                  ({{ t('common.optional') }})
                </span>
              </span>
              <v-select multiple class="block w-full mr-1 required" :model-value="selectedNumbers" :disabled="loading"
                @update:modelValue="updateSelect($event, 'number')" :options="streetNumbers" />
            </div>
          </div>
          <div v-if="selectedStreets.length > 0" class="mx-4 my-10 w-[400px]">
            <div v-if="!fetchingData">
              <div v-if="supply_point_ids.length > 0" class="bg-white shadow-md rounded-lg p-4 border border-gray-200">
                <div class="flex items-center justify-between">
                  <p class="text-gray-600 text-sm font-medium">
                    {{ t('service_block.affected_sp') }}:
                    <span class="font-semibold text-gray-800">{{ supply_point_ids.length }}</span>
                  </p>
                  <button @click="showDetail('affectedSupplyPoints', null)"
                    class="flex items-center justify-center w-8 h-8 hover:bg-blue-100 border border-gray-300 rounded-md transition duration-200">
                    <Icon name="fa6-solid:eye" class="text-gray-600 hover:text-blue-700 text-lg" />
                  </button>
                </div>
              </div>

              <div v-else class="bg-white shadow-md rounded-lg p-4 border border-gray-200">
                <p class="text-gray-500 text-center text-sm">
                  {{ $t('common.no_data_found') }}
                </p>
              </div>
            </div>
            <div v-else class="bg-white shadow-md rounded-lg p-4 border border-gray-200">
              <p class="text-gray-500 text-center text-sm flex items-center mx-10">
                <Icon name="fa6-solid:spinner" class="animate-spin text-lg text-slate-500 mx-2" />
                {{ $t('common.loading') }}...
              </p>
            </div>

            <div v-if="!fetchingData">
              <div v-if="contract_ids.length > 0" class="bg-white shadow-md my-2 rounded-lg p-4 border border-gray-200">
                <div class="flex items-center justify-between">
                  <p class="text-gray-600 text-sm font-medium">
                    {{ t('contract_block.affected_contracts') }}:
                    <span class="font-semibold text-gray-800">{{ contract_ids.length }}</span>
                  </p>
                  <button @click="showDetail('affectedContracts', null)"
                    class="flex items-center justify-center w-8 h-8 hover:bg-blue-100 border border-gray-300 rounded-md transition duration-200">
                    <Icon name="fa6-solid:eye" class="text-gray-600 hover:text-blue-700 text-lg" />
                  </button>
                </div>
              </div>

              <div v-else class="bg-white my-2 shadow-md rounded-lg p-4 border border-gray-200">
                <p class="text-gray-500 text-center text-sm">
                  {{ $t('common.no_data_found') }}
                </p>
              </div>
            </div>
            <div v-else class="bg-white my-2  shadow-md rounded-lg p-4 border border-gray-200">
              <p class="text-gray-500 text-center text-sm flex items-center mx-10">
                <Icon name="fa6-solid:spinner" class="animate-spin text-lg text-slate-500 mx-2" />
                {{ $t('common.loading') }}...
              </p>
            </div>
          </div>

        </div>


        <div class="col-span-2 flex flex-row-reverse mt-4">
          <!-- Bulk path: paste/upload content present -> preview first -->
          <button v-if="hasBulkInput" @click="handlePreview" :disabled="previewing" class="button-primary">
            <Icon :name="previewing ? 'fa6-solid:spinner' : 'fa6-solid:magnifying-glass'"
              :class="previewing ? 'animate-spin' : ''" />
            &nbsp;
            {{ $t('service_block.bulk_plan_preview') }}
          </button>
          <!-- Picker path: unchanged legacy save -->
          <button v-else @click="save" :disabled="saving" class="button-primary">
            <Icon :name="saving ? 'fa6-solid:spinner' : 'fa6-solid:floppy-disk'" 
            :class="saving ? 'animate-spin' : ''" />
            &nbsp; 
            {{ $t('common.save') }}
          </button>
        </div>

      </div>

    </div>

    <!-- Stage 2 (inline, full width): bulk preview panel swaps the form area -->
    <div v-else-if="stage === 'preview' && preview" class="border border-gray-300 rounded p-4 bg-white">
      <div class="grid grid-cols-2 md:grid-cols-5 gap-4 mb-5">
        <div class="bg-slate-50 border border-slate-200 rounded p-3 text-center">
          <p class="text-2xl font-semibold">{{ preview.stats?.unique ?? 0 }}</p>
          <p class="text-slate-500 text-sm">{{ $t('service_block.bulk_plan_stat_unique') }}</p>
        </div>
        <div class="bg-slate-50 border border-slate-200 rounded p-3 text-center">
          <p class="text-2xl font-semibold">{{ preview.stats?.duplicates_in_input ?? 0 }}</p>
          <p class="text-slate-500 text-sm">{{ $t('service_block.bulk_plan_stat_duplicates') }}</p>
        </div>
        <div class="bg-green-50 border border-green-200 rounded p-3 text-center">
          <p class="text-2xl font-semibold text-green-700">{{ preview.stats?.resolved ?? 0 }}</p>
          <p class="text-green-700 text-sm">{{ $t('service_block.bulk_plan_stat_resolved') }}</p>
        </div>
        <div class="bg-amber-50 border border-amber-200 rounded p-3 text-center">
          <p class="text-2xl font-semibold text-amber-700">{{ preview.stats?.not_found ?? 0 }}</p>
          <p class="text-amber-700 text-sm">{{ $t('service_block.bulk_plan_stat_not_found') }}</p>
        </div>
        <div class="bg-red-50 border border-red-200 rounded p-3 text-center">
          <p class="text-2xl font-semibold text-red-700">{{ preview.stats?.conflicts ?? 0 }}</p>
          <p class="text-red-700 text-sm">{{ $t('service_block.bulk_plan_stat_conflicts') }}</p>
        </div>
      </div>

      <!-- Conflicts -->
      <div v-if="(preview.conflicts ?? []).length" class="mb-5 border border-red-300 bg-red-50 rounded p-4">
        <p class="text-red-800 font-medium mb-2">{{ $t('service_block.bulk_plan_conflicts_title') }}</p>
        <p class="text-red-700 text-sm mb-3">{{ $t('service_block.bulk_plan_conflicts_hint') }}</p>
        <div class="max-h-60 overflow-y-auto space-y-2 mb-3">
          <div v-for="conflict in preview.conflicts" :key="conflict.supply_point_id"
            class="bg-white border border-red-200 rounded p-2 text-sm">
            <span class="font-mono">{{ conflict.supply_point_id }}</span>
            <ul class="mt-1 list-disc list-inside text-slate-600">
              <li v-for="cut in conflict.cuts" :key="cut.id">
                {{ cut.token }} — {{ cut.status }}
                <span v-if="cut.date_start" class="text-slate-400">({{ cut.date_start }}<template
                    v-if="cut.date_end"> → {{ cut.date_end }}</template>)</span>
              </li>
            </ul>
          </div>
        </div>
        <label class="flex items-center gap-2 text-red-800 font-medium">
          <input type="checkbox" v-model="overrideConflicts" />
          {{ $t('service_block.bulk_plan_override_conflicts') }}
        </label>
      </div>

      <!-- Not found -->
      <div v-if="(preview.not_found ?? []).length" class="mb-5 border border-amber-300 bg-amber-50 rounded p-4">
        <p class="text-amber-800 font-medium mb-2">{{ $t('service_block.bulk_plan_not_found_title') }}</p>
        <p class="text-amber-700 text-sm mb-2">{{ $t('service_block.bulk_plan_not_found_hint') }}</p>
        <div class="max-h-40 overflow-y-auto">
          <span v-for="item in preview.not_found" :key="item"
            class="inline-block bg-white border border-amber-200 rounded px-2 py-1 text-sm font-mono mr-2 mb-1">
            {{ item }}
          </span>
        </div>
      </div>

      <!-- Resolved table -->
      <div class="mb-5">
        <p class="text-gray-600 font-medium mb-2">{{ $t('service_block.bulk_plan_resolved_title') }}</p>
        <div class="overflow-x-auto max-h-96 overflow-y-auto border border-gray-200 rounded">
          <table class="w-full text-sm">
            <thead class="bg-slate-50 sticky top-0">
              <tr>
                <th class="text-left px-3 py-2 border-b">{{ $t('supply_point') }}</th>
                <th class="text-left px-3 py-2 border-b">{{ $t('common.identificator') }}</th>
                <th class="text-left px-3 py-2 border-b">{{ $t('address_block.address') }}</th>
                <th class="text-left px-3 py-2 border-b">{{ $t('service_block.bulk_plan_column_conflict') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in preview.resolved" :key="row.supply_point_id" class="border-b last:border-b-0">
                <td class="px-3 py-1 font-mono">{{ row.supply_point_id }}</td>
                <td class="px-3 py-1 font-mono">{{ row.token }}</td>
                <td class="px-3 py-1">{{ row.address }}</td>
                <td class="px-3 py-1">
                  <span v-if="row.has_conflict" class="text-red-600 font-medium">{{ $t('common.yes') }}</span>
                  <span v-else class="text-slate-400">{{ $t('common.no') }}</span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <div class="flex justify-between mt-4">
        <button type="button" class="button-secondary" @click="handleBulkBack">
          <Icon name="fa6-solid:angles-left" /> &nbsp; {{ $t('service_block.bulk_plan_back') }}
        </button>
        <button type="button" class="button-primary" :disabled="!canCreateBulk || bulkSaving" @click="handleBulkCreate">
          <Icon :name="bulkSaving ? 'fa6-solid:spinner' : 'fa6-solid:floppy-disk'"
            :class="bulkSaving ? 'animate-spin' : ''" />
          &nbsp; {{ $t('common.save') }}
        </button>
      </div>
    </div>
    <div role="region" id="right_page"
      class="fixed h-full border-l border-gray-100 top-0 right-0 transition-all duration-500 ease py-2 text-base bg-white z-10"
      :class="{ 'translate-x-0': showRegion, 'translate-x-full': !showRegion, 'w-[95%]': isSubRegionOpen, 'w-[55%]': !isSubRegionOpen }">
      <div id="region_nav" class="mb-3 px-3">
        <button @click="toggleRegion(false)"
          class="px-2 py-1 text-sky-500 hover:bg-slate-200 rounded active:bg-slate-300">
          <Icon name="fa6-solid:angles-right" class="text-slate-500" />
        </button>
      </div>
      <div class="px-10">
        <AddSupplyPoints v-if="showRegionDetailComponent == 'SupplyPointForm'" :selected_items="selectedSupplyPoints"
          @item-clicked="onSupplyPointSelected" :multiple="true" />
        <AddContracts v-if="showRegionDetailComponent == 'ContractForm'" :selected_items="selectedContract"
          @item-clicked="onContractSelected" :multiple="true" />
        <SupplyPointRegion v-if="showRegionDetailComponent == 'SupplyPointRegion'" :id="showRegionDetailId" />
        <ContractRegion v-if="showRegionDetailComponent == 'ContractRegion'" :id="showRegionDetailId" />
        <SupplyCutContractListRegion v-if="showRegionDetailComponent == 'affectedContracts'" 
        :contracts="affectedContracts" @show-detail="handleSubRegionEvent" 
        @exclude-contract="excludeContract" />
        <SupplyCutSupplyListRegion v-if="showRegionDetailComponent == 'affectedSupplyPoints'" 
        :supply_points="affectedSupplyPoints" @show-detail="handleSubRegionEvent" 
        @exclude-supply-point="excludeSupplyPoint" />
      </div>
    </div>
  </div>
</template>
