<script setup>
import { ref, computed, onMounted } from 'vue';
import { useI18n } from 'vue-i18n';
import { useToast } from 'vue-toastification';
import { useNuxtApp } from '#app';
import { formatMoney } from '~/utils/money';
import Date from '~/components/atoms/Date.vue';
import ColorBadge from '~/components/atoms/ColorBadge.vue';
import ContractRegion from './ContractRegion.vue';
import SupplyPointRegion from './SupplyPointRegion.vue';
import SupplyPointMiniDetail from '../molecules/SupplyPointMiniDetail.vue';

const props = defineProps({
  supply_points: {
    type: Array,
    default: () => []
  }
});

const { t } = useI18n();
const toast = useToast();
const emit = defineEmits(['close', 'show-detail', 'change']);

const loading = ref(false);
const searchQuery = ref('');
const searchInput = ref(null);
const localSupplyPoints = ref([]);
const expandedSupplyPoints = ref(new Set());
const showWithoutContracts = ref(false);
const loadingSupplyPointId = ref(null);

const showRegion = ref(false);
const isSubRegionOpen = ref(false);
const showRegionDetailComponent = ref(null);
const regionDetailId = ref(null);

// Funcions per gestionar els contractes expandits
const toggleSupplyPoint = (spId) => {
  if (expandedSupplyPoints.value.has(spId)) {
    expandedSupplyPoints.value.delete(spId)
  } else {
    expandedSupplyPoints.value.add(spId)
  }
}

const isSupplyPointExpanded = (spId) => {
  return expandedSupplyPoints.value.has(spId)
}

// Funció per mostrar detalls
const showDetail = (component, id) => {
  closeAllRegions();
  showRegionDetailComponent.value = component;
  regionDetailId.value = id;
  showRegion.value = true;
  emit('show-detail', true);
}

// Carregar els contractes associats a la reclamació
const loadContracts = async () => {
  loading.value = true;
  try {
    localSupplyPoints.value = props.supply_points;
  } catch (error) {
    toast.error(t('common.error_load'));
    console.error(error);
  } finally {
    loading.value = false;
  }
};

// Filtrar els contractes basats en la cerca i l'estat d'exclusió
const filteredSupplyPoints = computed(() => {
  let supply_points = localSupplyPoints.value || [];
  if (showWithoutContracts.value) {
    supply_points = supply_points.filter(supply_point => supply_point.contracts.length === 0);
  } else {
    supply_points = localSupplyPoints.value || []
  }

  // Filtrar per cerca
  if (!searchQuery.value) return supply_points;

  const query = searchQuery.value.toLowerCase();
  return supply_points.filter(supply_point => {
    const fullName = `${supply_point.address_complete}`.toLowerCase();
    const contractTokens = supply_point.contracts?.map(c => c.token?.toLowerCase() || '').join(' ') || '';
    const supply_pointToken = supply_point.token?.toLowerCase() || '';

    return fullName.includes(query) ||
      contractTokens.includes(query) ||
      supply_pointToken.includes(query);
  });
});

// Excloure un contracte i els seus pagaments
const excludeSupplyPoint = async (supply_point) => {
  if (!confirm(t('confirmation_text_block.confirm_exclude_supply_point'))) return;

  loadingSupplyPointId.value = supply_point.id;
  try {
    localSupplyPoints.value = localSupplyPoints.value.filter(c => c.id !== supply_point.id);
    emit('exclude-supply-point', supply_point);

  } catch (error) {
    toast.error(t('common.error'));
    console.error(error);
  } finally {
    loadingSupplyPointId.value = null;
  }
};


const closeAllRegions = () => {
  showRegion.value = false;
  showRegionDetailComponent.value = null
  regionDetailId.value = null
  emit('show-detail', false);
};

onMounted(async () => {
  await loadContracts();
  searchInput.value?.focus();
});
</script>

<template>
  <div class="region__content pr-1">

    <div class="h-full flex flex-col transition-all duration-500 ease" :class="{ 'mr-[48vw]': showRegion }">
      <div class="flex justify-between items-center mb-4">
        <h3 class="text-lg font-semibold">{{ $t('service_block.supply_point_list') }}</h3>
        <!-- <button @click="$emit('close')" class="text-gray-500 hover:text-gray-700">
          <Icon name="fa6-solid:xmark" class="text-xl" />
        </button> -->
      </div>

      <div class="mb-4 space-y-4">
        <div class="relative">
          <div class="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
            <Icon name="fa6-solid:magnifying-glass" class="text-gray-400" />
          </div>
          <input ref="searchInput" v-model="searchQuery" type="text"
            :placeholder="`${$t('dashboard.search')} ${$t('address_block.address')}, ${$t('common.identificator')}  ${$t('common.or')} ${$t('contract')}`"
            class="pl-10 pr-4 py-2 w-full border border-gray-300 rounded-md focus:ring-primary-500 focus:border-primary-500" />
        </div>

        <div class="flex items-center gap-5">
          <label class="inline-flex items-center">
            <input type="checkbox" v-model="showWithoutContracts"
              class="form-checkbox h-4 w-4 text-sky-600 rounded border-gray-300 focus:ring-sky-500" />
            <span class="ml-2 text-sm text-gray-700">{{ $t('common.show') }} {{ $t('contract_block.no_contracts') }}</span>
          </label>
        </div>
      </div>

      <!-- afegim comptadors -->
      <div class="flex gap-3 items-center mb-4" v-if="!loading">
        <div>
          {{ $t('common.supply_points') }}: {{ localSupplyPoints.count }}
        </div>
      </div>

      <div class="flex-1 overflow-y-auto">
        <div v-if="loading && !localSupplyPoints.results?.length" class="flex justify-center items-center h-full">
          <Icon name="fa6-solid:spinner" class="animate-spin text-2xl" />
        </div>
        <div v-else>
          <div class="divide-y divide-gray-200 h-[70vh] overflow-y-auto">
            <div v-if="filteredSupplyPoints.length === 0">
              <div class="footering text-slate-500 p-2">
                {{ t('common.no_data_found') }}
              </div>
            </div>
            <div v-for="(supply_point, index) in filteredSupplyPoints" :key="supply_point.id" class="bg-white">
              <div class="px-4 py-3 flex justify-between items-center hover:bg-gray-50 relative" :class="{
                'bg-white': index % 2 !== 0,
                'bg-sky-50': index % 2 === 0,
              }">
                <div v-if="loadingSupplyPointId === supply_point.id"
                  class="absolute inset-0 bg-white bg-opacity-75 flex items-center justify-center">
                  <Icon name="fa6-solid:spinner" class="animate-spin text-xl text-sky-600" />
                </div>

                <div class="flex items-center space-x-3">
                  <button @click="toggleSupplyPoint(supply_point.id)" class="text-gray-500 hover:text-gray-700"
                    :disabled="loadingSupplyPointId === supply_point.id"
                    :title="`${$t('common.expand')}/${$t('common.collapse')} ${$t('common.short_supply')}`">
                    <Icon
                      :name="isSupplyPointExpanded(supply_point.id) ? 'fa6-solid:chevron-down' : 'fa6-solid:chevron-right'" />
                  </button>
                  <div>
                    <div class="grid grid-cols-[100px,1fr,50px,50px,50px] gap-2">
                      <button @click="showDetail('SupplyPointRegion', supply_point.id)"
                        class="text-sky-500 hover:text-sky-700 underline text-left"
                        :title="`${$t('common.show')} ${$t('common.details')}`">
                        {{ supply_point.token }}
                      </button>
                      <span>{{ supply_point.address_complete }}</span>
                      <abbr v-if="supply_point.current_fraud" :title="t('service_block.supply_with_fraud')"
                        class="mt-auto">
                        <Icon name="fa6-solid:triangle-exclamation" class="font-bold text-lg text-orange-500 m-auto" />
                      </abbr>
                      <span v-else></span>
                      <ColorBadge :color="supply_point.status_color" :value="supply_point.status_name" />
                      <span></span>
                    </div>
                    <div class="text-sm text-gray-500 mt-1 grid grid-cols-[100px,1fr] gap-2">
                      <span>
                        <abbr :title="$t('service_block.potable')" class="mr-2">
                          {{ supply_point.is_potable ? t('service_block.potable') : t('service_block.no_potable') }}
                        </abbr>
                        <abbr v-if="supply_point.type_name" :title="$t('common.type')" class="mr-2">{{ supply_point.type_name
                          }}</abbr>
                      </span>
                    </div>
                  </div>
                </div>
                <button @click="excludeSupplyPoint(supply_point)"
                  class="flex items-center gap-2 text-red-600 hover:text-red-900 text-lg"
                  :disabled="loadingSupplyPointId === supply_point.id" :title="$t('billing_block.exclude')">
                  <Icon name="fa6-solid:ban" /> <span class="text-sm">{{ $t('billing_block.exclude') }}</span>
                </button>
              </div>
              <div v-if="isSupplyPointExpanded(supply_point.id)" class="px-4 py-2 bg-gray-50">
                <div class="bg-white">
                  <div v-if="supply_point.contracts && supply_point.contracts.length != 0"
                    class="min-w-full text-sm text-slate-800 mt-2">
                    <div class="group bg-gray-100 border-b text-left grid grid-cols-[1fr,1fr,2fr]">
                      <span class="p-2 pl-3 text-slate-600"> {{ t('common.status') }} </span>
                      <span class="p-2 pl-3 text-slate-600 flex items-center"> {{ t('contract') }} </span>
                      <span class="p-2 pl-3 text-slate-600 flex items-center"> {{ t("contract_block.holder") }} </span>
                    </div>
                    <div v-for="item in supply_point.contracts"
                      class="border-b group grid grid-cols-[1fr,1fr,2fr] text-sm leading-4 transition-all duration-100">
                      <div class="footering text-slate-500 p-2 w-full">
                        <AtomsColorBadge :value="item.status_name" :color="item.status_color" />
                      </div>
                      <div class="footering text-slate-500 p-2 w-full">
                        <button v-if="!props.isSubRegion" @click="showDetail('ContractRegion', item.id)"
                          class="text-start text-sky-500 underline">{{ item.token }}</button>
                        <span v-else>{{ item.token }}</span>
                      </div>
                      <div class="footering text-slate-500 p-2 w-full">
                        <span>{{ item.holder }}</span>
                      </div>
                    </div>
                  </div>
                  <div v-else class="footering text-slate-500 p-2">
                    {{ t('common.no_records') }}
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
    <div v-if="showRegion == true" role="region" id="subregion"
      class="h-full border-l border-gray-100 transition-all duration-500 ease py-2 text-base bg-white fixed top-0 right-0 w-[48vw] z-50"
      :class="{ 'translate-x-0': showRegion, 'translate-x-full': !showRegion }">
      <div id="region_nav" class="mb-3 px-3">
        <button @click="closeAllRegions()" class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300">
          <Icon name="fa6-solid:angles-right" class="text-slate-500" />
        </button>
      </div>
      <div class="px-10">
        <!-- Subregions aqui -->
        <ContractRegion v-if="showRegionDetailComponent === 'ContractRegion'" :id="regionDetailId"
          :isSubRegion="true" />
        <SupplyPointRegion v-if="showRegionDetailComponent === 'SupplyPointRegion'" :id="regionDetailId"
          :isSubRegion="true" />
        <!-- /end Subregions aqui -->
      </div>
    </div>
  </div>
</template>