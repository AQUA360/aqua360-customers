<script setup>
// components/organisms/ClusterDetail.vue
import { ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import AppLoading from '~/components/atoms/AppLoading.vue';
import ContractDetail from '~/components/molecules/ContractDetail.vue';
import AddBonification from '~/components/molecules/AddBonification.vue';
import AddVariable from '~/components/molecules/AddVariable.vue';
import { useStandaloneVariableTypes } from '~/composables/useStandaloneVariableTypes';
import BonificationDetail from '~/components/molecules/BonificationDetail.vue';
import VariableDetail from '~/components/molecules/VariableDetail.vue';
import _ from 'lodash';
import H1 from '~/components/atoms/H1.vue';
import SupplyPointRegion from '~/components/organisms/SupplyPointRegion.vue';
import { checkPermission } from '~/middleware/permission';
import { useToast } from 'vue-toastification';
const route = useRoute()
const router = useRouter()
const { $ContractApiService, $BonificationApiService, $VariableApiService, $LoggerApiService, $ConfiglistApiService, $ConfigProjectApiService } = useNuxtApp();
const { t } = useI18n();
const toast = useToast();
const objectPermissions = ref(null);
const showRegion = ref(false);
const showRegionComponent = ref(null);
const regionDetailId = ref(null);
const isSubRegionOpen = ref(false);

const editVariable = ref(null);

const id = ref(route.params.id)
const contract = ref(null)

const isLoadingDebtManagements = ref(false)
const selectedDebtManagement = ref("null");

const debtManagements = ref([]);
const bonifications = ref([]);
const variables = ref([]);
const expired_variables = ref(null)
const expired_bonifications = ref(null)

const getData = async function () {
  const response = await $ContractApiService.getDetail(id.value);
  loadBonifications();
  loadVariables();
  getExpiredVariables();
  loadDebtManagements();
  contract.value = response
}

const getExpiredVariables = async () => {
  try {
    const result = await $LoggerApiService.getAll("contract-expired-bonifications-variables", id.value);
    expired_variables.value = result.results

    expired_bonifications.value = result.results.filter(item => item.expired_bonification)
  } catch (error) {
    console.log(error);
  }
}

const loadDebtManagements = async () => {
  isLoadingDebtManagements.value = true
  debtManagements.value = [];
  try {
    let fetchData = await $ConfiglistApiService.getAll('contract/contract-debt-management');
    debtManagements.value = fetchData.results;

    selectedDebtManagement.value = contract.value.debt_management ? contract.value.debt_management.id : "null";
  } catch (err) {
    console.error(err)
  } finally {
    isLoadingDebtManagements.value = false;
  }
}

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

const onEditVariable = (item) => {
  closeAllRegions();
  showRegion.value = true;
  showRegionComponent.value = 'AddVariable';
  editVariable.value = item;
}

const showDetail = (component, id) => {
  showRegionComponent.value = component;
  regionDetailId.value = id;
  showRegion.value = true;
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
  const response = await $VariableApiService.getAll("", ['contract=' + id.value]);
  variables.value = response.results;
  openVariableFromQuery();
}

/** El llapis d'una variable a la fitxa del contracte (`ContractTabs.vue`) hi porta amb
 * `?variable=<id>`: obrim directament el formulari d'aquella variable. */
const openVariableFromQuery = () => {
  const variableId = Number(route.query.variable);
  if (!variableId) return;

  const variable = variables.value.find(item => item.id === variableId);
  if (!variable) return;

  router.replace({ query: { ...route.query, variable: undefined } });
  onEditVariable(variable);
}

const save = async () => {
  try {
    router.push('/contract/contracts?id=' + id.value);
  }
  catch (error) {
    console.log(error)
  }
}

const saveDebtManagement = async () => {
  try {
    const data = {
      id: id.value,
      debt_management_id: selectedDebtManagement.value
    }
    const item_saved = await $ContractApiService.save(data)
  } catch (error) {
    console.log(error)
  }
}

const onBonificationSaved = (item) => {
  loadBonifications();
  loadVariables();
  toggleRegion(false);
}

const onDeleteBonification = () => {
  loadBonifications();
  loadVariables();
}

const onVariableSaved = async (item) => {
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

const handleSubRegionEvent = (event) => {
  isSubRegionOpen.value = event;
}

onMounted(async () => {
  objectPermissions.value = await checkPermission($ContractApiService);
  if (!objectPermissions.value.can_change) {
    toast.error(t('common.no_permissions'));
    return navigateTo('/');
  }
  getData()
});

watch(() => selectedDebtManagement.value, (newVal) => {
  saveDebtManagement();
});

</script>

<template>
  <div v-if="objectPermissions?.can_change" id="wrapper" class="text-base p-4">
    <div v-if="contract == null">
      <div class="flex justify-center items-center">
        <Icon name="fa6-solid:spinner" class="animate-spin text-2xl text-slate-500" />
        <span class="ml-2">{{ $t('common.loading') }}...</span>
      </div>
    </div>
    <div v-else>
      <div class="flex justify-between items-center mb-6">
        <H1>{{ $t(`contract_block.contract_bonifications`) + ' ' + (contract.supply_point ? contract.supply_point.address_complete
          :
          contract.token) }}
        </H1>
      </div>

      <div class="mt-2 mb-5 p-3 border border-slate-300 rounded-lg bg-sky-50">
        <ContractDetail :id="contract.id" :reducedDetail="true" @show-subregion="showDetail" />
      </div>

      <div class="grid grid-cols-3 gap-3">
        <!-- Selecció de Bonificacions -->
        <div class="mb-4">
          <label class="flex text-sm font-medium text-gray-700 mb-3 gap-2">
            <Icon v-show="bonifications.length > 0" name="fa6-solid:circle-check" class="text-xl text-emerald-600" />
            <Icon v-show="bonifications.length == 0" name="fa6-solid:asterisk" class="text-lg text-slate-400" />
            <span>{{ $t('bonifications') }}:</span>
          </label>

          <div>
            <div class="flex items-center gap-3">
              <button name="" class="button-default-xs" @click="openAddBonification">
                <Icon name="fa-solid:plus" class="text-slate-500 mr-1" />
                {{ $t('contract_block.new_bonification') }}
              </button>
            </div>
            <div v-if="bonifications" class="mt-2">
              <BonificationDetail v-for="bonification in bonifications" :key="bonification.id" :item="bonification"
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
              {{ $t('contract_block.new_variable') }}
            </button>

            <div v-if="variables">
              <div v-for="variable in variables" :key="variable.id" class="mt-2 text-sm bg-green-100 p-2">
                <VariableDetail :item="variable" class="bg-green-100" :editButton="true"
                  @delete="onDeleteBonification" @edit="onEditVariable(variable)" />
              </div>
            </div>

          </div>
        </div>
        <!-- /end Selecció de Bonificacions -->

        <div class="mb-4">
          <label class="flex text-sm font-medium text-gray-700 mb-3 gap-2">
            <Icon v-show="selectedDebtManagement != '' && selectedDebtManagement" name="fa6-solid:circle-check"
              class="text-xl text-emerald-600" />
            <Icon v-show="selectedDebtManagement == '' || !selectedDebtManagement" name="fa6-solid:asterisk"
              class="text-lg text-slate-400" />
            <span>{{ $t('contract_block.debt_management_type') }}:</span>
          </label>
          <div class="flex items-center">
            <select id="contractClientType" v-model="selectedDebtManagement"
              class="w-full text-base border border-gray-300 rounded p-2">
              <option value="null">{{ $t('contract_block.no_debt_management_type') }}</option>
              <option v-for="item in debtManagements" :key="item.id" :value="item.id">
                {{ item.name }}
              </option>
            </select>
          </div>
        </div>

      </div><!-- end grid-cols-2 -->

      <hr>
      <!-- <h2 class="my-2 font-semibold">{{ $t('Mètode de pagament') }}</h2>
      <MoleculesPersonBankSelect class="max-w-xl" :persons="[newTenant]" :halfRegion="true" @selected-item="onPersonBankSelected"/> -->
      <div class="flex flex-row-reverse mt-4">
        <button @click="save" class="button-primary">
          <Icon name="fa6-solid:floppy-disk" />&nbsp; {{ $t('common.save') }}
        </button>
        <!-- <button v-if="person != null" @click="deletePerson" :disabled="saving" class="button-delete mr-5">
          <font-awesome icon="trash" />&nbsp; {{ $t('Eliminar') }}</button> -->
      </div>
      <div class="p-3 mt-10">
        <div v-if="expired_variables?.length > 0" class="">
          <span class="text-slate-500 text-sm bg-slate-100 rounded-md px-2 py-1">
            {{ t('contract_block.expired_variables') }}
          </span>
          <div class="grid grid-cols-2 gap-3 mt-2">
            <div v-for="v in expired_variables" class="border rounded p-2 bg-slate-100">
              <MoleculesVariableDetail :item="v.expired_variable" :deleteButton="false" :is_expired="true" />
            </div>
          </div>
        </div>
        <div v-if="expired_variables?.length > 0" class="mt-10">

          <span class="text-slate-500 text-sm bg-slate-100 rounded-md px-2 py-1">
            {{ t('contract_block.expired_bonifications') }}
          </span>
          <div v-for="b in expired_bonifications" class="my-3 bg-slate-100 rounded">
            <BonificationDetail :item="b.expired_bonification" :deleteButton="false" :is_expired="true" />
          </div>
        </div>
      </div>
    </div>

    <div role="region" id="right_page"
      class="fixed h-full border-l border-gray-100 top-0 right-0 transition-all duration-500 ease py-2 text-base bg-white z-10"
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
        <AddVariable v-if="showRegionComponent == 'AddVariable'" :contract="contract" @new-item="onVariableSaved"
          :variable="editVariable" />
        <SupplyPointRegion v-if="showRegionComponent == 'SupplyPointRegion'" :id="parseInt(regionDetailId)"
          :isSubRegion="isSubRegionOpen" @show-subregion="handleSubRegionEvent" />
      </div>
    </div>
  </div>
</template>