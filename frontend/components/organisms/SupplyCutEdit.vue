<script setup>
import { toRaw, ref, onMounted, watch, watchEffect } from 'vue';
import { useI18n } from 'vue-i18n';
import { useToast } from 'vue-toastification';
import H1 from '~/components/atoms/H1.vue';
import _ from 'lodash';
import ButtonSeleccio from '~/components/atoms/ButtonSeleccio.vue';
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
})


const dateIntervalError = (event) => {
  toast.error(event)
  date_end.value = null
}
</script>

<template>
  <div v-if="objectPermissions?.can_change" id="wrapper" class="text-base p-4 max-w-full">
    <div v-if="loading">
      <AppLoading :text="$t('common.loading')" />
    </div>
    <div v-else class="border border-gray-300 rounded p-4 bg-white">
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

          <div v-else>
            <ButtonSeleccio @click="showDetail('ContractForm', null)">{{ $t('common.select') }} {{ $t('contract') }}
            </ButtonSeleccio>
            <span>{{ selectedContract.value }}</span>
          </div>

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
          <div v-else>
            <ButtonSeleccio @click="showDetail('SupplyPointForm', null)">
              {{ $t('common.select') }} {{ $t('supply_point') }}
            </ButtonSeleccio>
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
          <button @click="save" :disabled="saving" class="button-primary">
            <Icon :name="saving ? 'fa6-solid:spinner' : 'fa6-solid:floppy-disk'" 
            :class="saving ? 'animate-spin' : ''" />
            &nbsp; 
            {{ $t('common.save') }}
          </button>
        </div>

      </div>

    </div>
    <div role="region" id="right_page"
      class="fixed h-full border-l border-gray-100 top-0 right-0 transition-all duration-500 ease py-2 text-base bg-white z-10"
      :class="{ 'translate-x-0': showRegion, 'translate-x-[2000px]': !showRegion, 'w-[95%]': isSubRegionOpen, 'w-[55%]': !isSubRegionOpen }">
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
