<script setup>
// components/molecules/ContractRequestSetup.vue
import { ref, onMounted, watch, computed } from 'vue';
import { useI18n } from 'vue-i18n';
import { format } from 'date-fns';

import ButtonSeleccio from '~/components/atoms/ButtonSeleccio.vue';
import PersonSearch from '~/components/organisms/PersonSearch.vue';
import FastSupplyPointEdit from '~/components/organisms/FastSupplyPointEdit.vue';
import AddSupplyPoints from '~/components/molecules/AddSupplyPoints.vue';
import SupplyPointDetail from '~/components/molecules/SupplyPointDetail.vue';

import ClusterRegion from '~/components/organisms/ClusterRegion.vue';
import MeterRegion from '~/components/organisms/MeterRegion.vue';
import RouteRegion from '~/components/organisms/RouteRegion.vue';
import ConnectionRegion from '~/components/organisms/ConnectionRegion.vue';
import ContractRegion from '../organisms/ContractRegion.vue';
import FieldDetail from '../atoms/FieldDetail.vue';
import InputDate from '../atoms/InputDate.vue';
import { checkPermission } from '~/middleware/permission';
import { AVAILABLE_LANGUAGES } from '~/utils/languages';

const { $ContractRequestTypeApiService, $SupplyPointApiService, $PersonApiService, $ExploitationApiService, $ContractApiService, $ConfigProjectApiService } = useNuxtApp();
const { t } = useI18n();

const props = defineProps({
  request: {
    type: Object,
    required: false
  },
  requireCompany: {
    type: Boolean,
    default: false
  },
  prefillContractId: {
    type: [Number, String],
    default: null
  }
});

const emit = defineEmits(['change', 'show-subregion']);

const showRegion = ref(false);
const isSubRegionOpen = ref(false);
const editingPerson = ref(false);
const editingSupplyPoint = ref(false);
const creatingSupplyPoint = ref(false);

const loadingPerson = ref(true);

const selectedType = ref("");
const selectedPerson = ref(null);
const selectedSupplyPoint = ref(null);
const totalPersons = ref(3);
const selectedSupplyPoints = ref([]);
const editingAditionalSupplyPoint = ref(false);
const billCutReading = ref(false);
const registrationDate = ref(format(new Date(), 'yyyy-MM-dd'));
const config = useRuntimeConfig();
const language = ref(config.public.defaultLocale);
const copiedContractData = ref(null);
const isChangeOfName = ref(false);
const isTypeLocked = ref(false);

const contractRequestTypes = ref([]);
const isLoadingTypes = ref(false);
const typesError = ref(null);

const providerCompanies = ref([]);
const loadingProviderCompanies = ref(false);
const selectedCompanyId = ref('');
/** When GET /service/company reports exactly one row total */
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
    return Number(raw);
  }
  return null;
};

const resolvedCompanyId = computed(() => getResolvedCompanyId());

const syncAutoCompanySelection = () => {
  if (singleCompanyId.value != null) {
    selectedCompanyId.value = String(singleCompanyId.value);
    return;
  }
  if (providerCompanies.value.length === 1) {
    selectedCompanyId.value = String(providerCompanies.value[0].id);
  }
};

const supplyPointPermissions = ref(null);

const getSupplyPointPermissions = async () => {
  const data = await checkPermission($SupplyPointApiService);
  supplyPointPermissions.value = data;
}

const closeAllRegions = () => {
  // Tanquem tots els components
  editingPerson.value = false;
  editingSupplyPoint.value = false;
  creatingSupplyPoint.value = false;
  showRegionDetailComponent.value = '';
  isSubRegionOpen.value = false;
  // Tanquem region
  showRegion.value = false;
};

/** Persones a l'habitatge: mínim 1. Amb 0 la facturació peta (divisió per zero). */
const isTotalPersonsValid = computed(() => {
  if (!selectedType.value?.has_persons) return true;
  const value = Number(totalPersons.value);
  return Number.isInteger(value) && value >= 1;
});

const emitChange = () => {
  let supply_point_ids = selectedSupplyPoints.value.map(x => x.id);

  let data = {
    type: selectedType.value?.id || null,
    person: selectedPerson.value?.id || null,
    supply_point: selectedSupplyPoint.value || null,
    supply_point_ids: supply_point_ids || null,
    total_persons: totalPersons.value || null,
    total_persons_valid: isTotalPersonsValid.value,
    bill_cut_reading: billCutReading.value,
    registration_date: registrationDate.value || null,
    language: language.value || null,
    company: getResolvedCompanyId(),
    copied_contract_data: copiedContractData.value || null,
    is_change_of_name: isChangeOfName.value
  };

  emit('change', data);
};

const openPersonForm = () => {
  closeAllRegions();
  editingPerson.value = true;
  showRegion.value = true;
};

const openSupplyPointForm = async (value) => {
  await closeAllRegions();
  editingAditionalSupplyPoint.value = value;
  editingSupplyPoint.value = true;
  showRegion.value = true;
};

const createSupplyPoint = async (value) => {
  editingAditionalSupplyPoint.value = value;
  await closeAllRegions();
  creatingSupplyPoint.value = true;
  isSubRegionOpen.value = true;
  showRegion.value = true;
};

const fetchPersonDebt = async (personId) => {
  try {
    const res = await $ContractApiService.getAll(
      '', [], 1, null, false,
      [], [], [], [], [],
      [], [], false, [], '',
      [], [personId], '', null,
      [], null, 'all'
    );
    const contracts = res.results || [];
    return contracts.reduce((sum, c) => sum + (Number(c.debt_amount) || 0), 0);
  } catch (error) {
    console.error('Error carregant el deute de la persona:', error);
    return 0;
  }
};

const onPersonSaved = async (item) => {
  loadingPerson.value = true;
  try {
    selectedPerson.value = await $PersonApiService.getFullDetail(item.id);
    selectedPerson.value.debt_amount = await fetchPersonDebt(item.id);
  } catch (error) {
    console.error('Error carregant el detall de la persona:', error);
    selectedPerson.value = item;
  } finally {
    loadingPerson.value = false;
  }
  emitChange();
  closeAllRegions();
};

const onSupplyPointCreated = async (item) => {
  onSupplyPointSelected(item);
  emitChange();
  closeAllRegions();
};

const onSupplyPointSelected = async (item) => {
  if (editingAditionalSupplyPoint.value) {
    if (selectedSupplyPoints.value.map(x => x.id).includes(item.id)) {
      selectedSupplyPoints.value = selectedSupplyPoints.value.filter(x => x.id !== item.id);
    } else {
      selectedSupplyPoints.value.push(item);
    }
  } else {
    // Fetch detailed info of the selected supply point
    const detail = await $SupplyPointApiService.getDetail(item.id);
    selectedSupplyPoint.value = detail;
    selectedSupplyPoints.value = [];
    copiedContractData.value = null;

    if (detail.contracts && detail.contracts.length > 0) {
      try {
        const activeContractToken = await $ConfigProjectApiService.get('contract_active_token');
        const targetContract = detail.contracts.find(c => activeContractToken && c.status_token == activeContractToken);
        if (targetContract) {
          const contractDetail = await $ContractApiService.getDetail(targetContract.id);
          if (contractDetail) {
            if (!isChangeOfName.value) {
              const typeToFind = contractDetail.contract_request_type || contractDetail.type;
              if (typeToFind) {
                const foundType = contractRequestTypes.value.find(t => t.id === typeToFind.id);
                if (foundType) {
                  selectedType.value = foundType;
                }
              }
            }
            if (contractDetail.company && !selectedCompanyId.value) {
              const cid = typeof contractDetail.company === 'object' && contractDetail.company !== null ? contractDetail.company.id : contractDetail.company;
              selectedCompanyId.value = cid != null ? String(cid) : '';
            }

            const mappedPriceRates = contractDetail.price_rates ? contractDetail.price_rates.map(pr => {
              const rateId = pr.price_rate?.id || pr.price_rate;
              const spId = pr.supply_point?.id || pr.supply_point || detail.id;
              return {
                price_rate: typeof pr.price_rate === 'object' ? pr.price_rate : { id: rateId },
                supply_point: typeof pr.supply_point === 'object' ? pr.supply_point : { id: spId }
              };
            }) : [];

            copiedContractData.value = {
              category: contractDetail.category?.id || null,
              use_type: contractDetail.use_type?.id || null,
              client_type: contractDetail.client_type?.id || null,
              debt_management: contractDetail.debt_management?.id || null,
              use_general_price_rates: contractDetail.use_general_price_rates || false,
              price_rates_ids: mappedPriceRates
            };
          }
        }
      } catch (err) {
        console.error('Error fetching previous contract details:', err);
      }
    }

    if (selectedSupplyPoint.value.supply_point_children_ids.length > 0) {
      for (let i = 0; i < selectedSupplyPoint.value.supply_point_children_ids.length; i++) {
        let new_supply_point = await $SupplyPointApiService.getDetail(selectedSupplyPoint.value.supply_point_children_ids[i]);
        selectedSupplyPoints.value.push(new_supply_point);
      }
    }

    closeAllRegions();
  }

  emitChange();
};

const onAditionalSupplyPointSelect = (item) => {

  emitChange();
};

// Funció per carregar els tipus de contractació des de l'API
const loadContractRequestTypes = async () => {
  isLoadingTypes.value = true;
  try {
    const data = await $ContractRequestTypeApiService.getAll();
    contractRequestTypes.value = data.results;
    // Si hi ha una sol·licitud existent, seleccionar el tipus corresponent
    if (props.request && props.request.type) {
      selectedType.value = contractRequestTypes.value.find(type => type.id === props.request.type.id) || null;
    }
  } catch (error) {
    console.error('Error carregant els tipus de contractació:', error);
    typesError.value = error;
  } finally {
    isLoadingTypes.value = false;
  }
};

const handleSubRegionEvent = (event) => {
  isSubRegionOpen.value = event;
}

const loadCompanyOptionsData = async () => {
  loadingProviderCompanies.value = true;
  singleCompanyId.value = null;
  providerCompanies.value = [];
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

    syncAutoCompanySelection();
    emitChange();
  } catch (error) {
    console.error('Error loading companies:', error);
  } finally {
    loadingProviderCompanies.value = false;
  }
};

const loadData = async () => {
  if (props.request) {
    if (props.request.type) {
      const typeId = typeof props.request.type === 'object' ? props.request.type.id : props.request.type;
      selectedType.value = contractRequestTypes.value.find(type => type.id === typeId) || null;
    }
    if (props.request.company != null) {
      const c = props.request.company;
      const id = typeof c === 'object' && c !== null ? c.id : c;
      selectedCompanyId.value = id != null ? String(id) : '';
    } else {
      selectedCompanyId.value = '';
    }
    if (props.request.supply_point_default) {
      selectedSupplyPoint.value = props.request.supply_point_default;
    }
    if (props.request.total_persons) {
      totalPersons.value = props.request.total_persons;
    }
    if (props.request.supply_points) {
      selectedSupplyPoints.value = props.request.supply_points.filter(x => x.id != props.request.supply_point_default.id);
    }
    if (props.request.person) {
      selectedPerson.value = await $PersonApiService.getFullDetail(props.request.person);
      selectedPerson.value.debt_amount = await fetchPersonDebt(props.request.person);
    }
    if (props.request.bill_cut_reading) {
      billCutReading.value = props.request.bill_cut_reading;
    }
    if (props.request.registration_date) {
      registrationDate.value = props.request.registration_date;
    }
    if (props.request.language) {
      language.value = props.request.language;
    }
    loadingPerson.value = false;
  }
};

const applyChangeOfNamePrefill = async () => {
  try {
    const contract = await $ContractApiService.getDetail(props.prefillContractId);
    if (!contract || !contract.supply_point_default) return;

    isChangeOfName.value = true;
    // No es preomple cap dada de Titular/Propietari/Inquilí: en un "Canvi de nom" aquestes
    // dades les ha d'introduir l'usuari des de zero, no s'ha de reaprofitar el titular anterior.

    await onSupplyPointSelected({ id: contract.supply_point_default.id || contract.supply_point_default });

  } catch (error) {
    console.error('Error prefilling change of name request:', error);
  }
};

onMounted(async () => {
  await getSupplyPointPermissions();
  await loadContractRequestTypes();
  await loadData();
  await loadCompanyOptionsData();
  if (props.prefillContractId && !props.request?.id) {
    await applyChangeOfNamePrefill();
  }
});

// Observa canvis en la sol·licitud per recarregar les dades si cal
watch(() => props.request, async () => {
  await loadData();
  syncAutoCompanySelection();
  emitChange();
});

// Observa canvis en selectedType per emetre l'esdeveniment
watch(selectedType, (newVal) => {
  emitChange();
});

watch(selectedSupplyPoints, (newVal) => {
  emitChange();
});

watch(billCutReading, (newVal) => {
  emitChange();
});

watch(registrationDate, (newVal) => {
  emitChange();
});

watch(selectedCompanyId, () => {
  emitChange();
});


// subregions details
const SubRegion = ref(false);
const showRegionDetailComponent = ref(null);
const regionDetailId = ref(null);

const showDetail = async function (component, id) {
  await closeAllRegions();
  showRegionDetailComponent.value = component;
  regionDetailId.value = id;
  showRegion.value = true;
}

</script>

<template>
  <div id="wrapper" class="text-base">
    <h2 class="text-xl font-semibold mb-4">{{ $t('contract_block.request_setup_title') }}</h2>

    <div v-if="requireCompany" class="mb-4">
      <label for="contractRequestCompany" class="flex text-sm font-medium text-gray-700 mb-3 gap-2">
        <Icon v-show="resolvedCompanyId != null" name="fa6-solid:circle-check"
          class="text-xl text-emerald-600" />
        <Icon v-show="resolvedCompanyId == null" name="fa6-solid:asterisk"
          class="text-lg text-slate-400" />
        <span>{{ $t('contract_block.water_provider_company') }}:</span>
      </label>
      <div class="max-w-md">
        <select id="contractRequestCompany" v-model="selectedCompanyId" class="input h-9"
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

    <!-- Selecció de Tipus -->
    <div class="mb-4 grid grid-cols-2 gap-4">
      <div>
        <label for="contractType" class="flex text-sm font-medium text-gray-700 mb-3 gap-2">
          <Icon v-show="selectedType" name="fa6-solid:circle-check" class="text-xl text-emerald-600" />
          <Icon v-show="!selectedType" name="fa6-solid:asterisk" class="text-lg text-slate-400" />
          <span>{{ $t('contract_block.contracting_type') }}:</span>
        </label>

        <div>
          <select id="contractType" v-model="selectedType" class="input h-9" :disabled="isLoadingTypes">
            <option value="" selected>-- {{ $t('common.select') }} {{ t('common.type') }}</option>
            <option v-for="type in contractRequestTypes" :key="type.id" :value="type">
              {{ type.name }}
            </option>
          </select>

          <div v-if="isLoadingTypes" class="mt-2 text-sm text-gray-500">
            {{ $t('common.loading') }}...
          </div>
          <div v-if="typesError" class="mt-2 text-sm text-red-600">
            {{ $t('common.error_load') }}
          </div>
        </div>
      </div>

      <div v-if="selectedType && selectedType.has_persons == true">
        <div class=" w-[125px]">
          <label class="block text-sm font-medium mb-3"
            :class="isTotalPersonsValid ? 'text-slate-600' : 'text-red-600'">{{ t('common.total') }} {{
              t('common.persons') }}</label>
          <input type="number" min="1" step="1" v-model="totalPersons" class="input"
            :class="{ 'invalid': !isTotalPersonsValid, 'ring-1': !isTotalPersonsValid, 'ring-red-600': !isTotalPersonsValid }"
            @change="emitChange" />
        </div>
        <div v-if="!isTotalPersonsValid"
          class="mt-2 max-w-xl flex items-start gap-2 rounded-md border border-red-300 bg-red-50 p-3 text-sm text-red-700">
          <Icon name="fa6-solid:triangle-exclamation" class="mt-0.5 shrink-0 text-base" />
          <span>{{ t('contract_block.total_persons_min') }}</span>
        </div>
      </div>

      <div v-if="selectedType" class="w-[200px]">
        <InputDate v-model="registrationDate" :label="t('common.registration_date')" :required="true" @update:modelValue="emitChange" />
      </div>

      <div v-if="selectedType" class="w-[200px]">
        <label class="block text-sm font-medium text-slate-600 mb-3">{{ t('common.language') }}</label>
        <select v-model="language" class="input" @change="emitChange">
          <option v-for="lang in AVAILABLE_LANGUAGES" :key="lang.code" :value="lang.code">
            {{ t(lang.name) }}
          </option>
        </select>
      </div>

    </div>
    <!-- /end Selecció de Tipus -->

    <!-- Selecció de Persona -->
    <div class="mb-4">
      <label for="person" class="flex text-sm font-medium text-gray-700 mb-3 gap-2">
        <Icon v-show="selectedPerson" name="fa6-solid:circle-check" class="text-xl text-emerald-600" />
        <Icon v-show="!selectedPerson" name="fa6-solid:asterisk" class="text-lg text-slate-400" />
        <span>{{ isChangeOfName ? t('contract_block.new_holder') : $t('common.requester') }}:</span>
      </label>

      <div v-if="loadingPerson">
        <div class="mt-2 text-sm text-gray-500">
          <Icon name="fa6-solid:spinner" class="animate-spin text-md text-slate-500" />
          {{ $t('common.loading') }}...
        </div>
      </div>
      <div v-else>
        <div v-if="selectedPerson" class="bg-green-100 p-4 rounded relative max-w-xl group">
          <div>
            <p class="text-sm text-slate-500 italic" v-for="observation in selectedPerson.important_observations"
              :key="observation.id">
              {{ observation.observation }}
            </p>
          </div>
          <div class="flex justify-between">
            <div class="grid grid-cols-[auto,1fr] gap-2">
              <div class="my-auto opacity-80">
                <AtomsVulnerabilityCheck v-if="selectedPerson.vulnerability_level > 0"
                  :vulnerability_level="selectedPerson.vulnerability_level" />
              </div>
              <span class="font-semibold ">
                {{ selectedPerson.full_name || selectedPerson.name + ' ' + selectedPerson.surname }} <br>
                <span class="text-sm text-gray-500">{{ selectedPerson.token }}</span>
              </span>
            </div>
            <FieldDetail
              :label="$t('common.debt')"
              class="items-center"
            >
              <span
                class="rounded px-2 py-1 font-medium"
                :class="selectedPerson.debt_amount > 0 ? 'bg-red-500/20 text-red-700' : ''"
              >
                {{ formatMoneyWithCurrency(selectedPerson.debt_amount) }}
              </span>
            </FieldDetail>
          </div>
          <button @click="openPersonForm"
            class="absolute cursor-pointer shadow-md border text-sm w-8 h-8 bg-white right-3 top-3 rounded-md text-slate-600 opacity-0 transition-all duration-300 group-hover:opacity-100">
            <Icon name="fa6-solid:pencil" />
          </button>
        </div>
        <div v-else>
          <ButtonSeleccio @click="openPersonForm">{{ $t('common.select') }} {{ t('common.or') }} {{ t('common.add') }}
            {{ t('common.requester') }}</ButtonSeleccio>
        </div>
      </div>
    </div>
    <!-- /end Selecció de Persona -->

    <!-- Selecció de Punt de Subministrament -->
    <div class="mb-4">
      <label for="supply_point" class="flex text-sm font-medium text-gray-700 mb-3 gap-2">
        <Icon v-show="selectedSupplyPoint" name="fa6-solid:circle-check" class="text-xl text-emerald-600" />
        <Icon v-show="!selectedSupplyPoint" name="fa6-solid:asterisk" class="text-lg text-slate-400" />
        <span>{{ $t('supply_point') }}:</span>
      </label>

      <div v-if="selectedSupplyPoint" class="bg-green-100 p-4 rounded relative max-w-xl group">
        <div>
          <SupplyPointDetail :id="selectedSupplyPoint.id" @show-detail="showDetail" />
        </div>
        <!-- <button v-if="supplyPointPermissions?.can_change" @click="createSupplyPoint(false)"
          class="absolute cursor-pointer shadow-md border text-sm w-8 h-8 bg-white right-10 top-0 rounded-md text-slate-600 opacity-0 transition-all duration-300 group-hover:opacity-100 hover:bg-slate-50">
          <Icon name="fa6-solid:plus" />
        </button> -->
        <button v-if="!isChangeOfName" @click="openSupplyPointForm(false)"
          class="absolute cursor-pointer shadow-md border text-sm w-8 h-8 bg-white right-0 top-0 rounded-md text-slate-600 opacity-0 transition-all duration-300 group-hover:opacity-100 hover:bg-slate-50">
          <Icon name="fa6-solid:pencil" />
        </button>
      </div>
      <div class="flex gap-2" v-else-if="!isChangeOfName">
        <ButtonSeleccio @click="openSupplyPointForm(false)">{{ $t('common.select') }} {{ t('supply_point') }}
        </ButtonSeleccio>
        <div v-if="supplyPointPermissions?.can_change" class="text-sm text-gray-500 content-center"> o </div>
        <!-- <ButtonSeleccio v-if="supplyPointPermissions?.can_change" @click="createSupplyPoint(false)">{{
          $t('service_block.new_supply_point') }}
        </ButtonSeleccio> -->
      </div>

    </div>

    <div class="mb-4" v-if="selectedSupplyPoint">
      <label for="supply_point" class="flex text-sm font-medium text-gray-700 mb-3 gap-2 ">
        <Icon v-show="selectedSupplyPoints.length > 0" name="fa6-solid:circle-check" class="text-xl text-emerald-600" />
        <Icon v-show="selectedSupplyPoints.length === 0" name="fa6-solid:asterisk" class="text-lg text-slate-400" />
        <span>{{ $t('contract_block.additional_supply_points') }}:</span>
      </label>

      <div v-if="selectedSupplyPoints.length > 0" class="relative group"
        :class="selectedSupplyPoints.length > 1 ? 'grid grid-cols-2 gap-3 p-4 w-[73%]' : 'p-4 rounded max-w-xl'">
        <div v-for="item in selectedSupplyPoints" :key="item.id" class="bg-green-50 p-2 rounded">
          <SupplyPointDetail :id="item.id" @show-detail="showDetail" />
        </div>
        <!-- <button v-if="supplyPointPermissions?.can_change" @click="createSupplyPoint(true)"
          class="absolute cursor-pointer shadow-md border text-sm w-8 h-8 bg-white mr-3 right-10 top-3 rounded-md text-slate-600 opacity-0 transition-all duration-300 group-hover:opacity-100 hover:bg-slate-50">
          <Icon name="fa6-solid:plus" />
        </button> -->
        <button v-if="!isChangeOfName" @click="openSupplyPointForm(true)"
          class="absolute cursor-pointer shadow-md border text-sm w-8 h-8 bg-white right-3 top-3 rounded-md text-slate-600 opacity-0 transition-all duration-300 group-hover:opacity-100 hover:bg-slate-50">
          <Icon name="fa6-solid:pencil" />
        </button>
      </div>
      <div v-else-if="!isChangeOfName" class="flex gap-2">
        <ButtonSeleccio @click="openSupplyPointForm(true)">
          {{ $t('common.select') }} {{ t('contract_block.additional_supply_points') }}
        </ButtonSeleccio>
        <!-- <div v-if="supplyPointPermissions?.can_change" class="text-sm text-gray-500 content-center"> {{ t('common.or') }} </div>
        <ButtonSeleccio v-if="supplyPointPermissions?.can_change" @click="createSupplyPoint(true)">
          {{ $t('service_block.new_supply_point') }}
        </ButtonSeleccio> -->
      </div>


    </div>
    <!-- /end Selecció de Punt de Subministrament -->

    <!-- Regió lateral per formularis -->
    <div role="region" id="right_page"
      class="fixed h-full border-l border-gray-100 top-0 right-0 transition-all duration-500 ease py-2 text-base bg-white z-10"
      :class="{
        'translate-x-0': showRegion,
        'translate-x-[2000px]': !showRegion,
        'w-[95%]': isSubRegionOpen,
        'w-1/2': !isSubRegionOpen,
      }">
      <div id="region_nav" class="mb-3 px-3">
        <button @click="showRegion = false" class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300">
          <Icon name="fa6-solid:angles-right" class="text-slate-500" />
        </button>
      </div>
      <div class="px-10">
        <PersonSearch v-if="editingPerson" @saved="onPersonSaved" />
        <AddSupplyPoints v-if="editingSupplyPoint" :selected_items="editingAditionalSupplyPoint ? selectedSupplyPoints :
          selectedSupplyPoint ? [selectedSupplyPoint] : []" @item-clicked="onSupplyPointSelected" :multiple="true" />
        <FastSupplyPointEdit v-if="creatingSupplyPoint" @saved="onSupplyPointCreated" />

        <!-- altres subregions de consulta -->
        <ClusterRegion v-if="showRegionDetailComponent === 'ClusterRegion'" :id="regionDetailId"
          @show-subregion="handleSubRegionEvent" />
        <ContractRegion v-if="showRegionDetailComponent === 'ContractRegion'" :id="regionDetailId"
          @show-subregion="handleSubRegionEvent" />
        <RouteRegion v-if="showRegionDetailComponent === 'RouteRegion'" :id="regionDetailId"
          @show-subregion="handleSubRegionEvent" />
        <MeterRegion v-if="showRegionDetailComponent === 'MeterRegion'" :id="regionDetailId"
          @show-subregion="handleSubRegionEvent" />
        <ConnectionRegion v-if="showRegionDetailComponent === 'ConnectionRegion'" :id="regionDetailId"
          @show-subregion="handleSubRegionEvent" />
      </div>
    </div>
  </div>
</template>
